"""Minimal MMC5 + 6502 harness for calling KOEI p-code / compiled functions of FC 大航海時代 (needs py65).

Adapted from bushou/tools/pcode_emu.py. 64 x 8 KB PRG banks, p-code functions start with
JSR $E4BF, system calls go through $EED4 (the last pushed value is the service number), bank
shadows live at $97-$9B. $5114-$5116 values without bit 7 map a PRG-RAM page instead of ROM.
"""
from py65.devices.mpu6502 import MPU

SYSCALL = 0xEED4
HARNESS = 0x0380
RAM_PAGE = 0x100  # Mem.map / call_pcode: map a PRG-RAM page instead of a ROM bank


class Mem:
    def __init__(self, prg: bytes):
        self.prg = prg
        self.ram = bytearray(0x800)
        self.wram = bytearray(0x10000)
        self.exram = bytearray(0x400)
        self.m1 = self.m2 = 0
        # state after RESET ($F500): WRAM page 5 at $6000, bank 62 at $C000, bank 63 at $E000
        self.regs = {0x5113: 5, 0x5114: 0xC2, 0x5115: 0xC1, 0x5116: 0xFE, 0x5117: 0xFF}
        self.sync_shadow()

    def sync_shadow(self) -> None:
        for i, reg in enumerate(range(0x5113, 0x5118)):
            self.ram[0x97 + i] = self.regs[reg]

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
        elif 0x5113 <= a <= 0x5117 or 0x5120 <= a <= 0x5127:     # PRG banks, sprite CHR banks
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
    """Return from the $EED4 call without running the service."""
    lo = cpu.memory[0x100 + ((cpu.sp + 1) & 0xFF)]
    hi = cpu.memory[0x100 + ((cpu.sp + 2) & 0xFF)]
    cpu.sp = (cpu.sp + 2) & 0xFF
    cpu.pc = ((hi << 8 | lo) + 1) & 0xFFFF




def trace_face(prg: bytes, code: int) -> tuple[bytes, dict[tuple[int, int], tuple[int, int]]]:
    """Run the face drawer (bank 35 / 36 $8000, face code in $738C) on the new-game state.

    Returns the CHR banks written to $5120 / $5121 and the 30 face sprites of the OAM shadow
    ($0600, sprites 33-62) as {(dy, dx): (tile, attr)} relative to the top-left sprite.
    """
    mem = Mem(prg)
    mem.wram[5 * 0x2000:6 * 0x2000] = prg[57 * 0x2000:58 * 0x2000]
    mem[0x738C], mem[0x738D] = code & 0xFF, code >> 8
    mem[0x738A], mem[0x738B] = 5, 6

    def on_step(cpu):
        if cpu.pc in (0xFB63, 0xFB9F):      # NMI waits: clear the flag the NMI handler would clear
            cpu.memory[0x9F] = 0
        elif cpu.pc == 0xFCF0:
            cpu.memory[0xAE] = 0

    call_pcode(mem, 0x8000, {0x8000: 36 if code >= 0x1000 else 35, 0xA000: 1}, [], on_step)
    oam = mem.ram[0x600 + 33 * 4:0x600 + 63 * 4]
    sprites = [oam[4 * i:4 * i + 4] for i in range(30)]
    y0, x0 = min(s[0] for s in sprites), min(s[3] for s in sprites)
    return (bytes([mem.regs[0x5120], mem.regs[0x5121]]),
            {(s[0] - y0, s[3] - x0): (s[1], s[2]) for s in sprites})
