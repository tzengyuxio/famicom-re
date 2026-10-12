"""Minimal MMC5 + 6502 harness for calling KOEI p-code / compiled functions of FC 信長の野望・武将風雲録 (needs py65).

Adapted from genchou/tools/pcode_emu.py. 64 x 8 KB PRG banks, p-code functions start with
JSR $E31E, system calls go through $ED33 (the last pushed value is the service number), bank
shadows live at $90-$94. $5114-$5116 values without bit 7 map a PRG-RAM page instead of ROM.
"""
from py65.devices.mpu6502 import MPU

SYSCALL = 0xED33
HARNESS = 0x0380
RAM_PAGE = 0x100  # Mem.map / call_pcode: map a PRG-RAM page instead of a ROM bank


class Mem:
    def __init__(self, prg: bytes):
        self.prg = prg
        self.ram = bytearray(0x800)
        self.wram = bytearray(0x10000)
        self.exram = bytearray(0x400)
        self.m1 = self.m2 = 0
        # power-on state set by RESET ($F565): $5113=4, $5114/$5115/$5117 = bank 63, $5116 = bank 62
        self.regs = {0x5113: 4, 0x5114: 0xFF, 0x5115: 0xFF, 0x5116: 0xFE, 0x5117: 0xFF}
        self.sync_shadow()

    def sync_shadow(self) -> None:
        for i, reg in enumerate(range(0x5113, 0x5118)):
            self.ram[0x90 + i] = self.regs[reg]

    def map(self, cpu_base: int, bank: int) -> None:
        """bank = PRG ROM bank, or RAM_PAGE | n for PRG-RAM page n."""
        self.regs[0x5114 + ((cpu_base - 0x8000) >> 13)] = bank & 7 if bank & RAM_PAGE else 0x80 | bank
        self.sync_shadow()

    def _ram_page(self, a: int) -> int | None:
        r = self.regs[0x5114 + ((a - 0x8000) >> 13)]
        return None if r & 0x80 or a >= 0xE000 else (r & 7) * 0x2000 + (a & 0x1FFF)

    def __len__(self):
        return 0x10000

    def __getitem__(self, a):
        if isinstance(a, slice):
            return [self[i] for i in range(*a.indices(0x10000))]
        if a < 0x2000:
            return self.ram[a & 0x7FF]
        if a < 0x4000:
            return 0x80 if a & 7 == 2 else 0
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
            if (p := self._ram_page(a)) is not None:
                return self.wram[p]
            return self.prg[(self.regs[0x5114 + ((a - 0x8000) >> 13)] & 0x3F) * 0x2000 + (a & 0x1FFF)]
        return 0

    def __setitem__(self, a, v):
        if isinstance(a, slice):
            for i, x in zip(range(*a.indices(0x10000)), v):
                self[i] = x
        elif a < 0x2000:
            self.ram[a & 0x7FF] = v
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
        elif a >= 0x8000 and (p := self._ram_page(a)) is not None:
            self.wram[p] = v


def stack_args(mem: Mem, n: int) -> list[int]:
    """The n 16-bit values on top of the p-code stack, last pushed first."""
    sp = mem[2] | mem[3] << 8
    return [mem[sp + 2 + 2 * i] | mem[sp + 3 + 2 * i] << 8 for i in range(n)]


def call_pcode(mem: Mem, entry: int, banks: dict[int, int], args: list[int], on_step=None,
               sp: int = 0x0580, max_steps: int = 5_000_000) -> MPU:
    """JSR to a function with 16-bit args on the p-code stack (first arg at SP+2).

    banks maps CPU base ($8000 / $A000 / $C000) to the bank to map there (see Mem.map). on_step(cpu)
    may return True to stop early.
    """
    for base, bank in banks.items():
        mem.map(base, bank)
    mem[0x02], mem[0x03] = sp & 0xFF, sp >> 8
    for i, v in enumerate(args):
        mem[sp + 2 + 2 * i], mem[sp + 3 + 2 * i] = v & 0xFF, v >> 8
    for i, b in enumerate([0x20, entry & 0xFF, entry >> 8, 0x4C, (HARNESS + 3) & 0xFF, (HARNESS + 3) >> 8]):
        mem[HARNESS + i] = b
    cpu = MPU(memory=mem, pc=HARNESS)
    for _ in range(max_steps):
        if cpu.pc == HARNESS + 3:
            return cpu
        if on_step and on_step(cpu):
            return cpu
        cpu.step()
    raise RuntimeError(f"call did not return (pc={cpu.pc:04X})")


def _skip_service(cpu: MPU) -> None:
    """Return from the $ED33 call without running the service."""
    lo = cpu.memory[0x100 + ((cpu.sp + 1) & 0xFF)]
    hi = cpu.memory[0x100 + ((cpu.sp + 2) & 0xFF)]
    cpu.sp = (cpu.sp + 2) & 0xFF
    cpu.pc = ((hi << 8 | lo) + 1) & 0xFFFF


def trace_face(prg: bytes, code: int) -> tuple[bytes, bytes]:
    """Run the face dispatcher (bank 7 at $8000, bank 58 at $A000, $A174) for a face code; returns
    the 5x6 tile ids and ExRAM bytes it hands to the image service (svc 9, source in RAM)."""
    mem, out = Mem(prg), {}

    def on_step(cpu):
        if cpu.pc == SYSCALL and stack_args(cpu.memory, 1)[0] == 9:
            out["a"] = stack_args(cpu.memory, 8)
            return True
        return False

    call_pcode(mem, 0xA174, {0x8000: 7, 0xA000: 58}, [3, 7, code], on_step)
    a = out["a"]
    n = a[3] * a[4]
    return bytes(mem[a[5] + i] for i in range(n)), bytes(mem[a[6] + i] for i in range(n))


BATTLE_WRAM = 0x4000  # WRAM page 2 at $6000 while a battle runs


def trace_battle_screen(prg: bytes, terrain: bytes, castle: bool) -> tuple[bytes, bytes, list[int]]:
    """Run the battle screen builder (bank 23 $A42F) on a terrain grid placed at $7D62.

    Field maps are 14x11, castle maps 13x11 ($7D17 bit 1). Returns the 32x30 tile and ExRAM
    buffers it builds in WRAM page 1 ($8508 / $88C8 with page 1 at $8000) and the arguments of
    its full-screen image service call (svc 9)."""
    mem, out = Mem(prg), {}
    mem.regs[0x5113] = 2
    w, h = (13, 11) if castle else (14, 11)
    mem[0x7D62:0x7D62 + len(terrain)] = terrain
    mem[0x7D17] = 0x04 | (2 if castle else 0)
    mem[0x7D1A], mem[0x7D1B] = 0x08, 0x65
    mem[0x7F4E], mem[0x7F50], mem[0x7F52] = w, h, w * h

    def on_step(cpu):
        if cpu.pc == SYSCALL:
            a = stack_args(cpu.memory, 9)
            if a[0] == 9 and a[3] == 0x20:
                out["a"] = a
                return True
            _skip_service(cpu)
        return False

    call_pcode(mem, 0xA42F, {0x8000: RAM_PAGE | 1, 0xA000: 23}, [0], on_step)
    page = 1 * 0x2000
    return (bytes(mem.wram[page + 0x508:page + 0x508 + 960]), bytes(mem.wram[page + 0x8C8:page + 0x8C8 + 960]),
            out.get("a", []))
