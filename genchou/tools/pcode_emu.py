"""Minimal MMC5 + 6502 harness for calling KOEI p-code functions of FC 元朝秘史 (needs py65).

Adapted from suikoden/tools/pcode_emu.py. Differences: 64 x 8 KB PRG banks, the p-code
interpreter is entered with JSR $DE22, bank shadows live at $90-$94 and system calls go
through $E837 (the last pushed value is the service number).
"""
from py65.devices.mpu6502 import MPU

SYSCALL = 0xE837
NMI_WAIT_LOOPS = {0xFBC4, 0xFBD1, 0xFC98, 0xFCAC}  # spin until the NMI handler clears $0700, $A7, $7C or ticks $98
HARNESS = 0x0380  # $0701-$0720 is the palette buffer, keep the call stub away from it


class Mem:
    def __init__(self, prg: bytes):
        self.prg = prg
        self.ram = bytearray(0x800)
        self.wram = bytearray(0x10000)
        self.exram = bytearray(0x400)
        self.vram = bytearray(0x4000)
        self.vaddr = self.vhi = self.latch = 0
        self.m1 = self.m2 = 0
        # power-on state set by RESET ($F565): $5113=4, $5114/$5115/$5117 = bank 63, $5116 = bank 62
        self.regs = {0x5113: 4, 0x5114: 0xFF, 0x5115: 0xFF, 0x5116: 0xFE, 0x5117: 0xFF}
        self.sync_shadow()

    def sync_shadow(self) -> None:
        for i, reg in enumerate(range(0x5113, 0x5118)):
            self.ram[0x90 + i] = self.regs[reg]

    def map(self, cpu_base: int, bank: int) -> None:
        self.regs[0x5114 + ((cpu_base - 0x8000) >> 13)] = 0x80 | bank
        self.sync_shadow()

    def __len__(self):
        return 0x10000

    def __getitem__(self, a):
        if isinstance(a, slice):
            return [self[i] for i in range(*a.indices(0x10000))]
        if a < 0x2000:
            return self.ram[a & 0x7FF]
        if a < 0x4000:
            if a & 7 == 2:
                self.latch = 0
                return 0x80
            return 0
        if a == 0x5204:
            return 0x40
        if a == 0x5205:
            return (self.m1 * self.m2) & 0xFF
        if a == 0x5206:
            return (self.m1 * self.m2) >> 8
        if 0x5C00 <= a < 0x6000:
            return self.exram[a - 0x5C00]
        if 0x6000 <= a < 0x8000:
            return self.wram[(self.regs[0x5113] & 7) * 0x2000 + a - 0x6000]
        if a >= 0x8000:
            reg = 0x5114 + ((a - 0x8000) >> 13)
            return self.prg[(self.regs[reg] & 0x3F) * 0x2000 + (a & 0x1FFF)]
        return 0

    def __setitem__(self, a, v):
        if isinstance(a, slice):
            for i, x in zip(range(*a.indices(0x10000)), v):
                self[i] = x
        elif a < 0x2000:
            self.ram[a & 0x7FF] = v
        elif a < 0x4000 and a & 7 == 6:
            if self.latch == 0:
                self.vhi, self.latch = v, 1
            else:
                self.vaddr, self.latch = (self.vhi << 8 | v) & 0x3FFF, 0
        elif a < 0x4000 and a & 7 == 7:
            self.vram[self.vaddr] = v
            self.vaddr = (self.vaddr + 1) & 0x3FFF
        elif 0x5113 <= a <= 0x5117:
            self.regs[a] = v
        elif a == 0x5205:
            self.m1 = v
        elif a == 0x5206:
            self.m2 = v
        elif 0x5C00 <= a < 0x6000:
            self.exram[a - 0x5C00] = v
        elif 0x6000 <= a < 0x8000:
            self.wram[(self.regs[0x5113] & 7) * 0x2000 + a - 0x6000] = v


def stack_args(mem: Mem, n: int) -> list[int]:
    """The n 16-bit values on top of the p-code stack, last pushed first."""
    sp = mem[2] | mem[3] << 8
    return [mem[sp + 2 + 2 * i] | mem[sp + 3 + 2 * i] << 8 for i in range(n)]


def call_pcode(mem: Mem, entry: int, banks: dict[int, int], args: list[int], on_step=None,
               sp: int = 0x0580, max_steps: int = 3_000_000) -> MPU:
    """JSR to a p-code function (entry starts with JSR $DE22) with 16-bit args on the p-code stack.

    banks maps CPU base ($8000 / $A000) to the 8 KB bank to map there. on_step(cpu) may return
    True to stop early.
    """
    for base, bank in banks.items():
        mem.map(base, bank)
    mem[0x02], mem[0x03] = sp & 0xFF, sp >> 8
    for i, v in enumerate(args):  # first arg at FP+$0B = SP+2
        mem[sp + 2 + 2 * i], mem[sp + 3 + 2 * i] = v & 0xFF, v >> 8
    harness = HARNESS
    for i, b in enumerate([0x20, entry & 0xFF, entry >> 8, 0x4C, (harness + 3) & 0xFF, (harness + 3) >> 8]):
        mem[harness + i] = b
    cpu = MPU(memory=mem, pc=harness)
    nmi = mem[0xFFFA] | mem[0xFFFB] << 8
    in_nmi, nmi_sp = False, 0
    for _ in range(max_steps):
        if cpu.pc == harness + 3:
            return cpu
        if cpu.pc in NMI_WAIT_LOOPS and not in_nmi:
            cpu.stPushWord(cpu.pc)
            cpu.stPush(cpu.p)
            cpu.pc, in_nmi, nmi_sp = nmi, True, cpu.sp
        if in_nmi and mem[cpu.pc] == 0x40 and cpu.sp == nmi_sp:  # RTI
            in_nmi = False
        if not in_nmi and on_step and on_step(cpu):
            return cpu
        cpu.step()
    raise RuntimeError(f"p-code call did not return (pc={cpu.pc:04X})")


def trace_syscalls(prg: bytes, entry: int, banks: dict[int, int], args: list[int], services=None,
                   stop_after=None) -> list[list[int]]:
    """Record the stack (11 words, service number first) of every $E837 system call.

    Calls in `services` are recorded and skipped (return to the caller without running the
    service), so drawing services need no PPU emulation. stop_after = number of records
    after which to stop.
    """
    calls = []

    def on_step(cpu):
        if cpu.pc != SYSCALL:
            return False
        a = stack_args(cpu.memory, 11)
        if services is None or a[0] in services:
            calls.append(a)
            # emulate RTS: the p-code VM returns to its dispatch loop
            lo = cpu.memory[0x100 + ((cpu.sp + 1) & 0xFF)]
            hi = cpu.memory[0x100 + ((cpu.sp + 2) & 0xFF)]
            cpu.sp = (cpu.sp + 2) & 0xFF
            cpu.pc = ((hi << 8 | lo) + 1) & 0xFFFF
        return stop_after is not None and len(calls) >= stop_after

    call_pcode(Mem(prg), entry, banks, args, on_step)
    return calls


def _read(mem: Mem, ptr: int, sel: int, n: int) -> bytes:
    """n bytes at a service-9 source pointer: RAM when sel = $FF, else PRG bank sel - $C0 at ptr."""
    if sel == 0xFF:
        return bytes(mem[ptr + i] for i in range(n))
    return bytes(mem.prg[(sel & 0x3F) * 0x2000 + (ptr & 0x1FFF) + i] for i in range(n))


def trace_face(prg: bytes, code: int) -> tuple[bytes, bytes]:
    """Run the face dispatcher (bank 48 $A684) for a face code; returns the 5x6 tile ids and ExRAM
    bytes it hands to the image service."""
    mem, out = Mem(prg), {}

    def on_step(cpu):
        if cpu.pc == SYSCALL and stack_args(cpu.memory, 1)[0] == 9:
            out["a"] = stack_args(cpu.memory, 8)
            return True
        return False

    call_pcode(mem, 0xA684, {0xA000: 48}, [2, 3, code], on_step)
    a = out["a"]
    n = a[3] * a[4]
    return _read(mem, a[5], a[7], n), _read(mem, a[6], a[7], n)


def trace_battle_map(prg: bytes, n: int) -> tuple[bytes, bytes]:
    """Load battle map n (bank 9 $A5A9) and build its screen buffers ($A62B); returns the 32x30 tile
    ids and ExRAM bytes left in WRAM page 3 at $6000 / $63C0."""
    mem = Mem(prg)
    call_pcode(mem, 0xA5A9, {0xA000: 9}, [n])
    call_pcode(mem, 0xA62B, {0xA000: 9}, [0])
    page = 3 * 0x2000
    return bytes(mem.wram[page:page + 0x3C0]), bytes(mem.wram[page + 0x3C0:page + 0x780])
