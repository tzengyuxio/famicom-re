"""Minimal MMC5 + 6502 harness for calling KOEI p-code functions of FC L'Empereur (needs py65).

Adapted from genchou/tools/pcode_emu.py. Differences: 32 x 8 KB PRG banks, the p-code
interpreter is entered with JSR $E4F2, bank shadows live at $97-$9B, and system calls are a
fake interrupt (`PHP; JMP ($FFDE)` from $EF12) into $F961 with the service number in $50 and
the arguments in $52-$5F.
"""
from py65.devices.mpu6502 import MPU

SYSCALL = 0xF961
HARNESS = 0x0380


class Mem:
    def __init__(self, prg: bytes):
        self.prg = prg
        self.ram = bytearray(0x800)
        self.wram = bytearray(0x10000)
        self.exram = bytearray(0x400)
        self.m1 = self.m2 = 0
        # power-on state set by RESET ($F55E): $5113=5, $5114/$5115 = bank 0/1, $5116 = 30, $5117 = 31
        self.regs = {0x5113: 5, 0x5114: 0xE0, 0x5115: 0xE1, 0x5116: 0xFE, 0x5117: 0xFF}
        self.sync_shadow()

    def sync_shadow(self) -> None:
        for i, reg in enumerate(range(0x5113, 0x5118)):
            self.ram[0x97 + i] = self.regs[reg]

    def map(self, cpu_base: int, bank: int) -> None:
        self.regs[0x5114 + ((cpu_base - 0x8000) >> 13)] = 0xE0 | bank
        self.sync_shadow()

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
            return 0
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
            return self.prg[(self.regs[reg] & 0x1F) * 0x2000 + (a & 0x1FFF)]
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


def syscall_args(mem: Mem) -> list[int]:
    """Service number ($50) followed by the seven 16-bit arguments at $52-$5F."""
    w = [mem.ram[0x52 + 2 * i] | mem.ram[0x53 + 2 * i] << 8 for i in range(7)]
    return [mem.ram[0x50], *w]


def call_pcode(mem: Mem, entry: int, banks: dict[int, int], args: list[int], services=(),
               on_syscall=None, sp: int = 0x0580, max_steps: int = 3_000_000) -> MPU:
    """JSR to a p-code function (entry starts with JSR $E4F2) with 16-bit args on the p-code stack.

    Every system call is passed to on_syscall(args) (see syscall_args); calls whose service
    number is in `services` are skipped (RTI straight back), the rest run natively.
    on_syscall may return True to stop.
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
    for _ in range(max_steps):
        if cpu.pc == harness + 3:
            return cpu
        if cpu.pc == SYSCALL:
            a = syscall_args(mem)
            if on_syscall and on_syscall(a):
                return cpu
            if a[0] in services:  # emulate RTI of the fake interrupt frame
                st = lambda k: mem.ram[0x100 + ((cpu.sp + k) & 0xFF)]
                cpu.p, cpu.pc = st(1), st(2) | st(3) << 8
                cpu.sp = (cpu.sp + 3) & 0xFF
                continue
        cpu.step()
    raise RuntimeError(f"p-code call did not return (pc={cpu.pc:04X})")


def trace_face(prg: bytes, code: int) -> tuple[bytes, bytes]:
    """Run the face routine (bank 0 $A1F6, args x, y, code) and return the 30 tile ids and 30 ExRAM
    bytes it hands to the image service (svc 9): straight from bank 15 for a dedicated portrait,
    from the WRAM buffer that bank 19 $A000 assembled for a composite face."""
    mem, got = Mem(prg), []
    call_pcode(mem, 0xA1F6, {0xA000: 0}, [3, 10, code], services={9},
               on_syscall=lambda a: a[0] == 9 and bool(got.append(a)))
    *_, tiles, exram, sel = got[-1]
    if sel != 0xFF:  # PRG bank mapped at $A000
        mem.map(0xA000, sel & 0x1F)
    return bytes(mem[tiles + i] for i in range(30)), bytes(mem[exram + i] for i in range(30))


CITY_RECORDS = 0x7004   # WRAM page 5: 28-byte city records (scenario layout); map = (pointer - $7004) / 28
TARGET_CITY = 0x7CD3    # WRAM page 5: pointer to the attacked city's record


def trace_battle_map(prg: bytes, city: int) -> tuple[bytes, bytes, bytes, list[int]]:
    """Build the battle map of `city` with the game's own code: bank 12 $A15C (copy the packed
    terrain from bank 21 and unpack it to WRAM page 5 $7748), then $A1D6 (2x2 tiles per cell into
    WRAM page 1 $7684 / $790E). Returns (terrain 156, tiles 650, ExRAM 650, svc 9 args)."""
    mem = Mem(prg)
    page5 = 5 * 0x2000 - 0x6000
    ptr = CITY_RECORDS + 28 * city
    mem.wram[page5 + TARGET_CITY], mem.wram[page5 + TARGET_CITY + 1] = ptr & 0xFF, ptr >> 8
    call_pcode(mem, 0xA15C, {0xA000: 12}, [])
    terrain = bytes(mem.wram[page5 + 0x7748:page5 + 0x7748 + 156])
    got = []
    call_pcode(mem, 0xA1D6, {0xA000: 12}, [], on_syscall=lambda a: a[0] == 9 and not got.append(a))
    page1 = 0x2000 - 0x6000
    return (terrain, bytes(mem.wram[page1 + 0x7684:page1 + 0x7684 + 650]),
            bytes(mem.wram[page1 + 0x790E:page1 + 0x790E + 650]), got[0][1:] if got else [])
