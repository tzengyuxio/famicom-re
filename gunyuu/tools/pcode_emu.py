"""Minimal MMC5 + 6502 harness for calling KOEI p-code / compiled functions of FC 信長の野望・戦国群雄伝 (needs py65).

Adapted from bushou/tools/pcode_emu.py. 32 x 8 KB PRG banks, p-code functions start with
JSR $E414, the p-code stack pointer is $02-$03 (first argument at SP+2). Image services are
reached with the service number pushed last; service 8 (draw a tile block from RAM) starts at $FB21.
$5114-$5116 values without bit 7 map a PRG-RAM page instead of ROM; bank shadows live at $070C-$070F.
"""
from py65.devices.mpu6502 import MPU

DRAW_BLOCK = 0xFB21  # service 8: (8, x, y, w, h, tile ids, ExRAM bytes) on the p-code stack
HARNESS = 0x0380
RAM_PAGE = 0x100  # Mem.map / call_pcode: map a PRG-RAM page instead of a ROM bank


class Mem:
    def __init__(self, prg: bytes):
        self.prg = prg
        self.ram = bytearray(0x800)
        self.wram = bytearray(0x10000)
        self.exram = bytearray(0x400)
        self.m1 = self.m2 = 0
        # main-game mapping: WRAM page 5 at $6000, bank 30 at $C000, bank 31 at $E000
        self.regs = {0x5113: 5, 0x5114: 0xFF, 0x5115: 0xFF, 0x5116: 0xFE, 0x5117: 0xFF}
        self.sync_shadow()

    def sync_shadow(self) -> None:
        """The game keeps copies of $5113-$5116 at $070C-$070F and restores banks from them."""
        for i, reg in enumerate(range(0x5113, 0x5117)):
            self.ram[0x70C + i] = self.regs[reg]

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
            return self.prg[(self.regs[0x5114 + ((a - 0x8000) >> 13)] & 0x1F) * 0x2000 + (a & 0x1FFF)]
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


FACE_DISPATCH = 0xD147  # bank 30: draw the face of general (WRAM pointer) at (x, y)
NAME_BANK, NAME_START, NAME_SIZE = 24, 4, 22  # scenario 1 name records (face code at +20)
SCENARIO_BANK, GENERAL_PTR, PROBE_SLOT = 26, 0x6AD8, 127


def trace_face(prg: bytes, code: int) -> tuple[bytes, bytes] | None:
    """Run the game's face dispatcher ($D147: copies the face code of the general's name record to
    $78DB, then draws a dedicated face via $CF92 or a composite one via $CFDE) for scenario 1 general
    127 with its face code replaced by code. Returns the 5x6 tile ids and ExRAM bytes handed to the
    draw-block service, or None when nothing is drawn."""
    prg = bytearray(prg)
    o = NAME_BANK * 0x2000 + NAME_START + NAME_SIZE * PROBE_SLOT + 20
    prg[o], prg[o + 1] = code & 0xFF, code >> 8
    mem, out = Mem(bytes(prg)), {}
    mem.wram[0xA000:0xC000] = prg[SCENARIO_BANK * 0x2000:(SCENARIO_BANK + 1) * 0x2000]  # page 5 = scenario

    def on_step(cpu):
        if cpu.pc == DRAW_BLOCK:
            out["a"] = stack_args(cpu.memory, 8)
            return True
        return False

    call_pcode(mem, FACE_DISPATCH, {}, [2, 3, GENERAL_PTR + 14 * PROBE_SLOT], on_step)
    if "a" not in out:
        return None
    a = out["a"]
    n = a[3] * a[4]
    if a[7] == 0xFF:  # source in RAM
        return bytes(mem[a[5] + i] for i in range(n)), bytes(mem[a[6] + i] for i in range(n))
    base = (a[7] & 0x1F) * 0x2000 - 0xA000  # ROM bank a[7] seen at $A000
    return bytes(prg[base + a[5]:base + a[5] + n]), bytes(prg[base + a[6]:base + a[6] + n])


BATTLE_CELL = 0x8E14    # bank 9: draw battle cell (col, row, 1) from the terrain at $7C88
BATTLE_TERRAIN, CASTLE_FLAG = 0x7C88, 0x7A6E


def trace_battle_screen(prg: bytes, terrain: bytes, castle: bool, w: int = 13) -> tuple[bytes, bytes]:
    """Run the game's battle cell drawer for every cell of a terrain grid placed at $7C88 (castle flag
    $7A6E set for castle maps) and assemble the 2x2 blocks it hands to the draw-block service into a
    32x30 tile / ExRAM screen."""
    tiles, exram = bytearray(960), bytearray(960)
    for i in range(len(terrain)):
        row, col = divmod(i, w)
        mem, out = Mem(prg), {}
        mem[BATTLE_TERRAIN:BATTLE_TERRAIN + len(terrain)] = terrain
        mem[CASTLE_FLAG] = 1 if castle else 0

        def on_step(cpu, out=out):
            if cpu.pc == DRAW_BLOCK:
                out["a"] = stack_args(cpu.memory, 8)
                return True
            return False

        call_pcode(mem, BATTLE_CELL, {0x8000: 9, 0xA000: 21}, [col, row, 1], on_step)
        _, x, y, bw, bh, t, e, bank = out["a"]
        src = (bank & 0x1F) * 0x2000 - 0xA000
        for k in range(bw * bh):
            a = (y + k // bw) * 32 + x + k % bw
            tiles[a] = mem[t + k]
            exram[a] = prg[src + e + k] if bank != 0xFF else mem[e + k]
    return bytes(tiles), bytes(exram)
