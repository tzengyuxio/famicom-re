"""Minimal NES harness for FC ロイヤルブラッド (MMC5, CHR-ROM) on py65.

Enough to boot the game and play it from controller input: MMC5 PRG mode 3 banking (ROM or RAM pages),
PRG-RAM pages, ExRAM (extended attribute mode), nametable mapping ($5105), 1 KB sprite
CHR banks, the multiplier, the scanline IRQ, a register-level PPU and controller 1.
No APU and no rendering timing beyond vblank / scanline IRQ. render() draws the
current background (and sprites) for screenshots.
"""
import copy
import os
import sys

from py65.devices.mpu6502 import MPU

BUTTONS = {"A": 0, "B": 1, "SELECT": 2, "START": 3, "UP": 4, "DOWN": 5, "LEFT": 6, "RIGHT": 7}
FRAME_CYCLES, LINE_CYCLES, VBLANK_LINE = 29781, 113.667, 241
STATE = ("ram", "wram", "exram", "ciram", "pal", "oam", "ctrl", "mask", "status", "oamaddr", "v", "t", "w",
         "buf", "regs", "frame", "irq_line", "irq_en", "irq_pend", "in_frame", "m1", "m2", "scroll")


class Nes:
    def __init__(self, rom_path: str):
        """rom_path: a .nes file or the .zip in roms/."""
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from rom import read_rom
        data = read_rom(rom_path)
        self.prg, self.chr = data[16:16 + 0x40000], data[16 + 0x40000:]
        self.ram, self.wram, self.exram = bytearray(0x800), bytearray(0x10000), bytearray(0x400)
        self.ciram, self.pal, self.oam = bytearray(0x800), bytearray(32), bytearray(256)
        self.ctrl = self.mask = self.status = self.oamaddr = 0
        self.v = self.t = self.w = self.buf = 0
        self.scroll = (0, 0, 0)  # (x, y, nametable) latched at the start of the frame
        self.regs = {0x5100: 3, 0x5104: 0, 0x5105: 0, 0x5113: 0, 0x5114: 0xFF, 0x5115: 0xFF, 0x5116: 0xFF,
                     0x5117: 0xFF, 0x5130: 0}
        self.regs.update({0x5120 + i: i for i in range(12)})
        self.irq_line = self.irq_en = self.irq_pend = self.in_frame = 0
        self.m1 = self.m2 = 0
        self.pad = self.padsr = 0
        self.frame = 0
        self.cpu = MPU(memory=self)
        self.cpu.pc = self[0xFFFC] | self[0xFFFD] << 8
        self.breakpoints = {}  # pc -> callback(nes), checked before each instruction
        self.vram_log = None   # list to collect (addr, value) PPU writes, or None

    # ------------------------------------------------------------ CPU bus
    def prg_bank(self, a: int) -> int:
        return self.regs[0x5114 + ((a - 0x8000) >> 13)] & 0x1F

    def __len__(self):
        return 0x10000

    def __getitem__(self, a: int) -> int:
        if a < 0x2000:
            return self.ram[a & 0x7FF]
        if a >= 0x8000:
            r = self.regs[0x5114 + ((a - 0x8000) >> 13)]
            if not r & 0x80 and a < 0xE000:  # PRG-RAM page mapped into $8000-$DFFF
                return self.wram[(r & 7) * 0x2000 + (a & 0x1FFF)]
            return self.prg[(r & 0x1F) * 0x2000 + (a & 0x1FFF)]
        if a >= 0x6000:
            return self.wram[(self.regs[0x5113] & 7) * 0x2000 + a - 0x6000]
        if a < 0x4000:
            r = a & 7
            if r == 2:
                s = self.status
                self.status &= 0x7F
                self.w = 0
                return s
            if r == 4:
                return self.oam[self.oamaddr]
            if r == 7:
                return self.ppu_read()
            return 0
        if a == 0x4016:
            v = self.padsr & 1
            self.padsr = (self.padsr >> 1) | 0x80
            return v | 0x40
        if a == 0x5204:
            s = self.irq_pend << 7 | self.in_frame << 6
            self.irq_pend = 0
            return s
        if a == 0x5205:
            return (self.m1 * self.m2) & 0xFF
        if a == 0x5206:
            return (self.m1 * self.m2) >> 8
        if 0x5C00 <= a < 0x6000:
            return self.exram[a - 0x5C00]
        return 0

    def __setitem__(self, a: int, v: int) -> None:
        if a < 0x2000:
            self.ram[a & 0x7FF] = v
        elif a < 0x4000:
            self.ppu_write(a & 7, v)
        elif a == 0x4014:
            for i in range(256):
                self.oam[(self.oamaddr + i) & 0xFF] = self[(v << 8) + i]
            self.cpu.processorCycles += 513
        elif a == 0x4016:
            self.padsr = self.pad
        elif 0x5100 <= a <= 0x5130:
            self.regs[a] = v
        elif a == 0x5203:
            self.irq_line = v
        elif a == 0x5204:
            self.irq_en = v >> 7
        elif a == 0x5205:
            self.m1 = v
        elif a == 0x5206:
            self.m2 = v
        elif 0x5C00 <= a < 0x6000:
            self.exram[a - 0x5C00] = v
        elif 0x6000 <= a < 0x8000:
            self.wram[(self.regs[0x5113] & 7) * 0x2000 + a - 0x6000] = v
        elif 0x8000 <= a < 0xE000 and not self.regs[0x5114 + ((a - 0x8000) >> 13)] & 0x80:
            self.wram[(self.regs[0x5114 + ((a - 0x8000) >> 13)] & 7) * 0x2000 + (a & 0x1FFF)] = v

    # ------------------------------------------------------------ PPU
    def pal_index(self, a: int) -> int:
        i = a & 0x1F
        return i - 0x10 if i in (0x10, 0x14, 0x18, 0x1C) else i

    def nt_read(self, a: int) -> int:
        q = (a >> 10) & 3
        src = (self.regs[0x5105] >> (2 * q)) & 3
        if src < 2:
            return self.ciram[src * 0x400 + (a & 0x3FF)]
        if src == 2:
            return self.exram[a & 0x3FF]
        return self.regs.get(0x5106, 0) if (a & 0x3FF) < 0x3C0 else 0

    def nt_write(self, a: int, v: int) -> None:
        q = (a >> 10) & 3
        src = (self.regs[0x5105] >> (2 * q)) & 3
        if src < 2:
            self.ciram[src * 0x400 + (a & 0x3FF)] = v
        elif src == 2:
            self.exram[a & 0x3FF] = v

    def vram_read(self, a: int) -> int:
        a &= 0x3FFF
        if a < 0x2000:
            return self.chr[(self.regs[0x5120 + (a >> 10)] * 0x400 + (a & 0x3FF)) % len(self.chr)]
        if a < 0x3F00:
            return self.nt_read(a)
        return self.pal[self.pal_index(a)]

    def vram_write(self, a: int, v: int) -> None:
        a &= 0x3FFF
        if self.vram_log is not None:
            self.vram_log.append((a, v))
        if 0x2000 <= a < 0x3F00:
            self.nt_write(a, v)
        elif a >= 0x3F00:
            self.pal[self.pal_index(a)] = v & 0x3F

    def ppu_read(self) -> int:
        a = self.v & 0x3FFF
        if a >= 0x3F00:
            r, self.buf = self.vram_read(a), self.vram_read(a - 0x1000)
        else:
            r, self.buf = self.buf, self.vram_read(a)
        self.v = (self.v + (32 if self.ctrl & 4 else 1)) & 0x7FFF
        return r

    def ppu_write(self, r: int, v: int) -> None:
        if r == 0:
            self.ctrl = v
            self.t = (self.t & 0xF3FF) | ((v & 3) << 10)
        elif r == 1:
            self.mask = v
        elif r == 3:
            self.oamaddr = v
        elif r == 4:
            self.oam[self.oamaddr] = v
            self.oamaddr = (self.oamaddr + 1) & 0xFF
        elif r == 5:
            if self.w == 0:
                self.t = (self.t & 0xFFE0) | (v >> 3)
                self.fine_x = v & 7
            else:
                self.t = (self.t & 0x8C1F) | ((v & 7) << 12) | ((v >> 3) << 5)
            self.w ^= 1
        elif r == 6:
            if self.w == 0:
                self.t = (self.t & 0x00FF) | ((v & 0x3F) << 8)
            else:
                self.t = (self.t & 0xFF00) | v
                self.v = self.t
            self.w ^= 1
        elif r == 7:
            self.vram_write(self.v, v)
            self.v = (self.v + (32 if self.ctrl & 4 else 1)) & 0x7FFF

    # ------------------------------------------------------------ run
    def _run_until(self, cycle: float) -> None:
        cpu, bps = self.cpu, self.breakpoints
        while cpu.processorCycles < cycle:
            if bps and cpu.pc in bps:
                bps[cpu.pc](self)
            cpu.step()

    def run_frame(self) -> None:
        start = self.cpu.processorCycles
        t = self.t
        self.scroll = (((t & 0x1F) << 3) | getattr(self, "fine_x", 0), ((t >> 5) & 0x1F) * 8 | (t >> 12) & 7,
                       (t >> 10) & 3)
        rendering = self.mask & 0x18
        self.in_frame = 1 if rendering else 0
        for line in range(VBLANK_LINE):
            self._run_until(start + (line + 1) * LINE_CYCLES)
            if rendering and self.irq_line and line + 1 == self.irq_line:
                self.irq_pend = 1
                if self.irq_en and not self.cpu.p & self.cpu.INTERRUPT:
                    self.cpu.irq()
        self.in_frame = 0
        self.status |= 0x80
        if self.ctrl & 0x80:
            self.cpu.nmi()
        self._run_until(start + FRAME_CYCLES)
        self.status &= 0x1F
        self.frame += 1

    def run(self, frames: int, buttons=()) -> None:
        self.pad = 0
        for b in buttons:
            self.pad |= 1 << BUTTONS[b]
        for _ in range(frames):
            self.run_frame()

    def press(self, button: str, wait: int, hold: int = 3) -> None:
        self.run(hold, [button])
        self.run(wait)

    def snapshot(self) -> dict:
        c = self.cpu
        st = {k: copy.copy(getattr(self, k)) for k in STATE}
        st["cpu"] = (c.pc, c.a, c.x, c.y, c.sp, c.p, c.processorCycles)
        return st

    def restore(self, st: dict) -> None:
        for k in STATE:
            setattr(self, k, copy.copy(st[k]))
        c = self.cpu
        c.pc, c.a, c.x, c.y, c.sp, c.p, c.processorCycles = st["cpu"]

    # ------------------------------------------------------------ screenshot
    def bg_cell(self, nt: int, col: int, row: int) -> tuple[int, int]:
        """(CHR byte offset of the tile, sub-palette) for one background cell of nametable nt."""
        a = 0x2000 + nt * 0x400 + row * 32 + col
        tile = self.nt_read(a)
        if self.regs[0x5104] == 1:
            ex = self.exram[row * 32 + col]
            return ((self.regs[0x5130] & 3) << 6 | (ex & 0x3F)) * 0x1000 + tile * 16, ex >> 6
        attr = self.nt_read(0x23C0 + nt * 0x400 + (row // 4) * 8 + col // 4)
        sub = (attr >> (((row & 2) << 1) | (col & 2))) & 3
        base = 0x1000 if self.ctrl & 0x10 else 0
        return (self.regs[0x5120 + 4 + ((base + tile * 16) >> 10)] * 0x400 + (tile * 16 & 0x3FF)), sub

    def render(self, sprites: bool = True) -> list[list[int]]:
        """256x240 NES colour numbers of the background (nametable/scroll at frame start) and sprites."""
        sx, sy, nt0 = self.scroll
        out = [[self.pal[0]] * 256 for _ in range(240)]
        for y in range(240):
            yy = sy + y
            for x in range(256):
                xx = sx + x
                nt = nt0 ^ ((xx // 256) & 1) ^ (((yy // 240) & 1) << 1)
                off, sub = self.bg_cell(nt, (xx % 256) // 8, (yy % 240) // 8)
                py, px = yy % 8, xx % 8
                lo, hi = self.chr[(off + py) % len(self.chr)], self.chr[(off + 8 + py) % len(self.chr)]
                c = ((lo >> (7 - px)) & 1) | (((hi >> (7 - px)) & 1) << 1)
                if c:
                    out[y][x] = self.pal[sub * 4 + c]
        if sprites and self.mask & 0x10:
            tall = self.ctrl & 0x20
            for i in range(63, -1, -1):
                y0, tile, attr, x0 = self.oam[i * 4:i * 4 + 4]
                for r in range(16 if tall else 8):
                    yy = y0 + 1 + r
                    if yy >= 240:
                        continue
                    rr = (15 if tall else 7) - r if attr & 0x80 else r
                    if tall:
                        a = (tile & 1) * 0x1000 + (tile & 0xFE) * 16 + (16 if rr >= 8 else 0) + (rr & 7)
                    else:
                        a = (0x1000 if self.ctrl & 8 else 0) + tile * 16 + rr
                    off = self.regs[0x5120 + (a >> 10)] * 0x400 + (a & 0x3FF)
                    lo, hi = self.chr[off % len(self.chr)], self.chr[(off + 8) % len(self.chr)]
                    for c8 in range(8):
                        px = 7 - c8 if attr & 0x40 else c8
                        c = ((lo >> (7 - px)) & 1) | (((hi >> (7 - px)) & 1) << 1)
                        if c and x0 + c8 < 256:
                            out[yy][x0 + c8] = self.pal[16 + (attr & 3) * 4 + c]
        return out
