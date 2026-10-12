"""Minimal NES harness for FC 三國志 (MMC1, CHR-RAM) on py65.

Enough to boot the game and play it from controller input: MMC1 banking, 8 KB
PRG-RAM, a register-level PPU (nametables, CHR-RAM, palette, OAM, scroll latch,
vblank/NMI, a crude sprite-0 hit) and controller 1. No APU, no rendering timing.
"""
import copy
import zipfile

from py65.devices.mpu6502 import MPU

BUTTONS = {"A": 0, "B": 1, "SELECT": 2, "START": 3, "UP": 4, "DOWN": 5, "LEFT": 6, "RIGHT": 7}
FRAME_CYCLES, VBLANK_CYCLE = 29781, 27393
STATE = ("ram", "wram", "chr", "nt", "pal", "oam", "ctrl", "mask", "status", "oamaddr", "v", "t", "w",
         "buf", "sr", "mctl", "prgreg", "frame")


class Nes:
    def __init__(self, rom_path: str):
        if rom_path.lower().endswith(".zip"):  # the single .nes inside a roms/ zip
            with zipfile.ZipFile(rom_path) as z:
                (name,) = [n for n in z.namelist() if n.lower().endswith(".nes")]
                self.prg = z.read(name)[16:]
        else:
            with open(rom_path, "rb") as f:
                self.prg = f.read()[16:]
        self.ram, self.wram = bytearray(0x800), bytearray(0x2000)
        self.chr, self.nt, self.pal, self.oam = bytearray(0x2000), bytearray(0x800), bytearray(32), bytearray(256)
        self.ctrl = self.mask = self.status = self.oamaddr = 0
        self.v = self.t = self.w = self.buf = 0
        self.sr, self.mctl, self.prgreg = 0x10, 0x0C, 0
        self.pad = self.padsr = self.strobe = 0
        self.frame = 0
        self.cpu = MPU(memory=self)
        self.cpu.pc = self[0xFFFC] | self[0xFFFD] << 8
        self.breakpoints = {}  # pc -> callback(nes), checked before each instruction

    # ------------------------------------------------------------ CPU bus
    def prg_off(self, a: int) -> int:
        mode, bank = (self.mctl >> 2) & 3, self.prgreg & 0x0F
        if mode < 2:
            b = (bank & 0x0E) | (a >= 0xC000)
        elif mode == 2:
            b = 0 if a < 0xC000 else bank
        else:
            b = bank if a < 0xC000 else 15
        return b * 0x4000 + (a & 0x3FFF)

    def nt_index(self, a: int) -> int:
        a &= 0x0FFF
        m = self.mctl & 3
        if m < 2:
            return m * 0x400 | (a & 0x3FF)
        if m == 2:  # vertical
            return a & 0x7FF
        return ((a >> 1) & 0x400) | (a & 0x3FF)  # horizontal

    def __len__(self):
        return 0x10000

    def __getitem__(self, a: int) -> int:
        if a < 0x2000:
            return self.ram[a & 0x7FF]
        if a >= 0x8000:
            return self.prg[self.prg_off(a)]
        if a >= 0x6000:
            return self.wram[a - 0x6000]
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
            self.strobe = v & 1
            self.padsr = self.pad
        elif 0x6000 <= a < 0x8000:
            self.wram[a - 0x6000] = v
        elif a >= 0x8000:  # MMC1 serial port
            if v & 0x80:
                self.sr = 0x10
                self.mctl |= 0x0C
                return
            done = self.sr & 1
            self.sr = (self.sr >> 1) | ((v & 1) << 4)
            if done:
                reg = (a >> 13) & 3
                if reg == 0:
                    self.mctl = self.sr
                elif reg == 3:
                    self.prgreg = self.sr
                self.sr = 0x10  # CHR registers are irrelevant with 8 KB CHR-RAM

    # ------------------------------------------------------------ PPU
    def pal_index(self, a: int) -> int:
        i = a & 0x1F
        return i - 0x10 if i in (0x10, 0x14, 0x18, 0x1C) else i

    def vram_read(self, a: int) -> int:
        a &= 0x3FFF
        if a < 0x2000:
            return self.chr[a]
        if a < 0x3F00:
            return self.nt[self.nt_index(a)]
        return self.pal[self.pal_index(a)]

    def vram_write(self, a: int, v: int) -> None:
        a &= 0x3FFF
        if a < 0x2000:
            self.chr[a] = v
        elif a < 0x3F00:
            self.nt[self.nt_index(a)] = v
        else:
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
    def _run_until(self, cycle: int, sprite0: int | None = None) -> None:
        cpu, bps = self.cpu, self.breakpoints
        while cpu.processorCycles < cycle:
            if bps and cpu.pc in bps:
                bps[cpu.pc](self)
            cpu.step()
            if sprite0 is not None and cpu.processorCycles >= sprite0:
                self.status |= 0x40
                sprite0 = None

    def run_frame(self) -> None:
        start = self.cpu.processorCycles
        self._run_until(start + VBLANK_CYCLE, start + (self.oam[0] + 1) * 114 if self.mask & 0x18 else None)
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
