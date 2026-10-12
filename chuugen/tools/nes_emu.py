"""Minimal NES harness for FC 三國志 中原の覇者 (Namco 163 / mapper 19, CHR-ROM) on py65.

Enough to boot the game and play it from controller input: Namco 163 PRG/CHR/nametable
banking, the 15-bit CPU-cycle IRQ counter, 8 KB PRG-RAM, the 128-byte internal RAM at
$4800/$F800, a register-level PPU (nametables, palette, OAM, scroll latch, vblank/NMI,
a crude sprite-0 hit) and controller 1. No APU. screen() renders background (with scroll and
mid-frame scroll/CHR splits, approximated per scanline) and sprites.
"""
import copy
import zipfile

from py65.devices.mpu6502 import MPU

BUTTONS = {"A": 0, "B": 1, "SELECT": 2, "START": 3, "UP": 4, "DOWN": 5, "LEFT": 6, "RIGHT": 7}
FRAME_CYCLES, VBLANK_CYCLE = 29781, 27393
STATE = ("ram", "wram", "iram", "ciram", "pal", "oam", "ctrl", "mask", "status", "oamaddr", "v", "t", "w",
         "buf", "fx", "prgreg", "chrreg", "ntreg", "iaddr", "irq_counter", "irq_on", "frame")


def read_nes(path: str) -> bytes:
    """Read a .nes file, or the single .nes inside a .zip (as stored in roms/)."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            (name,) = [n for n in z.namelist() if n.lower().endswith(".nes")]
            return z.read(name)
    with open(path, "rb") as f:
        return f.read()


class Nes:
    def __init__(self, rom_path: str):
        data = read_nes(rom_path)
        prg_size = data[4] * 0x4000
        self.prg = data[16:16 + prg_size]
        self.chr_rom = data[16 + prg_size:]
        self.prg_banks = len(self.prg) // 0x2000
        self.ram, self.wram, self.iram = bytearray(0x800), bytearray(0x2000), bytearray(128)
        self.ciram, self.pal, self.oam = bytearray(0x800), bytearray(32), bytearray(256)
        self.ctrl = self.mask = self.status = self.oamaddr = 0
        self.v = self.t = self.w = self.buf = self.fx = 0
        self.prgreg = [0, 0, 0]               # $E000/$E800/$F000 -> $8000/$A000/$C000
        self.chrreg = list(range(8))          # $8000-$B800 -> PPU $0000-$1FFF (1 KB each)
        self.ntreg = [0xE0, 0xE1, 0xE0, 0xE1]  # $C000-$D800 -> PPU $2000-$2FFF
        self.iaddr = 0                        # $F800: internal RAM address, bit 7 = auto-increment
        self.irq_counter, self.irq_on = 0, False
        self.pad = self.padsr = 0
        self.frame = 0
        self.frame_start = 0
        # CHR bank writes of the frame being run and of the last finished frame, for mid-screen splits
        self.chr_writes, self.last_frame_chr = [], (list(self.chrreg), [])
        # scroll state at frame start and (cycle, t, fine x, v reloaded) after each mid-frame scroll write
        self.scroll_writes, self.last_frame_scroll = [], ((0, 0), [])
        self.cpu = MPU(memory=self)
        self.cpu.pc = self[0xFFFC] | self[0xFFFD] << 8
        self.breakpoints = {}  # pc -> callback(nes), checked before each instruction

    # ------------------------------------------------------------ CPU bus
    def prg_off(self, a: int) -> int:
        slot = (a - 0x8000) >> 13
        bank = self.prg_banks - 1 if slot == 3 else (self.prgreg[slot] & 0x3F) % self.prg_banks
        return bank * 0x2000 + (a & 0x1FFF)

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
        if 0x4800 <= a < 0x5000:
            v = self.iram[self.iaddr & 0x7F]
            if self.iaddr & 0x80:
                self.iaddr = 0x80 | ((self.iaddr + 1) & 0x7F)
            return v
        if 0x5000 <= a < 0x5800:
            return self.irq_counter & 0xFF
        if 0x5800 <= a < 0x6000:
            return (self.irq_counter >> 8) | (0x80 if self.irq_on else 0)
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
        elif a < 0x4800:  # APU
            pass
        elif a < 0x5000:
            self.iram[self.iaddr & 0x7F] = v
            if self.iaddr & 0x80:
                self.iaddr = 0x80 | ((self.iaddr + 1) & 0x7F)
        elif 0x5000 <= a < 0x5800:
            self.irq_counter = (self.irq_counter & 0x7F00) | v
        elif 0x5800 <= a < 0x6000:
            self.irq_counter = (self.irq_counter & 0xFF) | ((v & 0x7F) << 8)
            self.irq_on = bool(v & 0x80)
        elif 0x6000 <= a < 0x8000:
            self.wram[a - 0x6000] = v
        elif a < 0xC000:
            self.chrreg[(a - 0x8000) >> 11] = v
            self.chr_writes.append((self.cpu.processorCycles - self.frame_start, (a - 0x8000) >> 11, v))
        elif a < 0xE000:
            self.ntreg[(a - 0xC000) >> 11] = v
        elif a < 0xF800:
            self.prgreg[(a - 0xE000) >> 11] = v
        else:
            self.iaddr = v

    # ------------------------------------------------------------ PPU
    def chr_byte(self, a: int) -> int:
        bank = self.chrreg[a >> 10]
        return self.chr_rom[(bank * 0x400 + (a & 0x3FF)) % len(self.chr_rom)]

    def nt_ref(self, a: int) -> tuple[bytearray | bytes, int]:
        reg = self.ntreg[(a >> 10) & 3]
        if reg >= 0xE0:
            return self.ciram, (reg & 1) * 0x400 + (a & 0x3FF)
        return self.chr_rom, reg * 0x400 + (a & 0x3FF)

    def pal_index(self, a: int) -> int:
        i = a & 0x1F
        return i - 0x10 if i in (0x10, 0x14, 0x18, 0x1C) else i

    def vram_read(self, a: int) -> int:
        a &= 0x3FFF
        if a < 0x2000:
            return self.chr_byte(a)
        if a < 0x3F00:
            mem, i = self.nt_ref(a)
            return mem[i]
        return self.pal[self.pal_index(a)]

    def vram_write(self, a: int, v: int) -> None:
        a &= 0x3FFF
        if 0x2000 <= a < 0x3F00:
            mem, i = self.nt_ref(a)
            if mem is self.ciram:
                mem[i] = v
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
            self._log_scroll(False)
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
                self.fx = v & 7
            else:
                self.t = (self.t & 0x8C1F) | ((v & 7) << 12) | ((v >> 3) << 5)
            self.w ^= 1
            self._log_scroll(False)
        elif r == 6:
            if self.w == 0:
                self.t = (self.t & 0x00FF) | ((v & 0x3F) << 8)
            else:
                self.t = (self.t & 0xFF00) | v
                self.v = self.t
                self._log_scroll(True)
            self.w ^= 1
        elif r == 7:
            self.vram_write(self.v, v)
            self.v = (self.v + (32 if self.ctrl & 4 else 1)) & 0x7FFF

    def _log_scroll(self, reload_v: bool) -> None:
        c = self.cpu.processorCycles - self.frame_start
        if c < VBLANK_CYCLE and self.mask & 0x18:
            self.scroll_writes.append((c, self.t, self.fx, reload_v))

    # ------------------------------------------------------------ run
    def _run_until(self, cycle: int, sprite0: int | None = None) -> None:
        cpu, bps = self.cpu, self.breakpoints
        while cpu.processorCycles < cycle:
            if bps and cpu.pc in bps:
                bps[cpu.pc](self)
            before = cpu.processorCycles
            cpu.step()
            if self.irq_on and self.irq_counter < 0x7FFF:
                self.irq_counter = min(0x7FFF, self.irq_counter + cpu.processorCycles - before)
                if self.irq_counter == 0x7FFF and not cpu.p & cpu.INTERRUPT:
                    cpu.irq()
            if sprite0 is not None and cpu.processorCycles >= sprite0:
                self.status |= 0x40
                sprite0 = None

    def run_frame(self) -> None:
        start = self.cpu.processorCycles
        frame_regs, self.chr_writes, self.frame_start = list(self.chrreg), [], start
        frame_scroll, self.scroll_writes = (self.t, self.fx), []
        self._run_until(start + VBLANK_CYCLE, start + (self.oam[0] + 1) * 114 if self.mask & 0x18 else None)
        self.status |= 0x80
        if self.ctrl & 0x80:
            self.cpu.nmi()
        self._run_until(start + FRAME_CYCLES)
        self.status &= 0x1F
        self.frame += 1
        self.last_frame_chr = (frame_regs, self.chr_writes)
        self.last_frame_scroll = (frame_scroll, self.scroll_writes)

    def run(self, frames: int, buttons=()) -> None:
        self.pad = 0
        for b in buttons:
            self.pad |= 1 << BUTTONS[b]
        for _ in range(frames):
            self.run_frame()

    def call(self, addr: int, a: int = 0, x: int = 0, y: int = 0, limit: int = 2_000_000) -> None:
        """Run the subroutine at addr (no NMI/IRQ) until it returns to a sentinel address."""
        cpu, ret = self.cpu, 0x5FF0  # unmapped: never reached except by the final RTS
        for v in ((ret - 1) >> 8, (ret - 1) & 0xFF):
            self.ram[0x100 + cpu.sp] = v
            cpu.sp = (cpu.sp - 1) & 0xFF
        cpu.pc, cpu.a, cpu.x, cpu.y = addr, a, x, y
        for _ in range(limit):
            if cpu.pc == ret:
                return
            cpu.step()
        raise RuntimeError(f"${addr:04X} did not return")

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
            if k in st:
                setattr(self, k, copy.copy(st[k]))
        c = self.cpu
        c.pc, c.a, c.x, c.y, c.sp, c.p, c.processorCycles = st["cpu"]

    # ------------------------------------------------------------ screen
    def line_chr_banks(self) -> list[list[int]]:
        """CHR bank registers in effect on each of the 240 scanlines of the last finished frame."""
        regs, writes = self.last_frame_chr
        regs, lines, i = list(regs), [], 0
        for line in range(240):
            while i < len(writes) and writes[i][0] < (line + 1) * 341 / 3:
                regs[writes[i][1]] = writes[i][2]
                i += 1
            lines.append(list(regs))
        return lines

    def background(self, table: int = 0) -> tuple[int, int, list[int]]:
        """Nametable `table` (0-3) as 256x240 NES colour numbers, with the CHR banks of each scanline."""
        base = 0x2000 + table * 0x400
        pt = 0x1000 if self.ctrl & 0x10 else 0
        px = [0] * (256 * 240)
        saved, lines = self.chrreg, self.line_chr_banks()
        for row in range(30):
            for col in range(32):
                tile = self.vram_read(base + row * 32 + col)
                attr = self.vram_read(base + 0x3C0 + (row // 4) * 8 + col // 4)
                sub = (attr >> (((row & 2) << 1) | (col & 2))) & 3
                for y in range(8):
                    self.chrreg = lines[row * 8 + y]
                    lo, hi = self.vram_read(pt + tile * 16 + y), self.vram_read(pt + tile * 16 + y + 8)
                    for x in range(8):
                        c = ((lo >> (7 - x)) & 1) | (((hi >> (7 - x)) & 1) << 1)
                        px[(row * 8 + y) * 256 + col * 8 + x] = self.pal[sub * 4 + c if c else 0]
        self.chrreg = saved
        return 256, 240, px

    def line_scroll(self) -> list[tuple[int, int]]:
        """(x, y) in the 512x480 nametable plane of the left pixel of each scanline of the last frame."""
        (t, fx), writes = self.last_frame_scroll

        def hx(t, fx):
            return ((t >> 10) & 1) * 256 + (t & 31) * 8 + fx

        def vy(t):
            return ((t >> 11) & 1) * 240 + ((t >> 5) & 31) * 8 + ((t >> 12) & 7)

        x, y0, start, out, i = hx(t, fx), vy(t), 0, [], 0
        for line in range(240):
            while i < len(writes) and writes[i][0] < line * 341 / 3:
                _, t, fx, reload_v = writes[i]
                x = hx(t, fx)
                if reload_v:
                    y0, start = vy(t), line
                i += 1
            out.append((x, y0 + line - start))
        return out

    def screen(self, sprites: bool = True) -> tuple[int, int, list[int]]:
        """What the TV shows for the last frame, as 256x240 NES colour numbers."""
        pt = 0x1000 if self.ctrl & 0x10 else 0
        px, opaque = [self.pal[0]] * (256 * 240), [False] * (256 * 240)
        saved, lines, scroll = self.chrreg, self.line_chr_banks(), self.line_scroll()
        for sy in range(240):
            self.chrreg = lines[sy]
            x0, y = scroll[sy]
            y %= 480
            ny, ry = divmod(y, 240)
            for sx in range(256):
                x = (x0 + sx) % 512
                nx, rx = divmod(x, 256)
                base = 0x2000 + (ny * 2 + nx) * 0x400
                row, col = ry >> 3, rx >> 3
                tile = self.vram_read(base + row * 32 + col)
                attr = self.vram_read(base + 0x3C0 + (row // 4) * 8 + col // 4)
                sub = (attr >> (((row & 2) << 1) | (col & 2))) & 3
                a = pt + tile * 16 + (ry & 7)
                b = 7 - (rx & 7)
                c = ((self.vram_read(a) >> b) & 1) | (((self.vram_read(a + 8) >> b) & 1) << 1)
                if c:
                    px[sy * 256 + sx], opaque[sy * 256 + sx] = self.pal[sub * 4 + c], True
        if sprites:
            tall = bool(self.ctrl & 0x20)
            for n in range(63, -1, -1):
                sy0, tile, at, sx0 = self.oam[n * 4:n * 4 + 4]
                for dy in range(16 if tall else 8):
                    sy = sy0 + 1 + dy
                    if sy >= 240:
                        continue
                    self.chrreg = lines[sy]
                    r = (15 if tall else 7) - dy if at & 0x80 else dy
                    if tall:
                        a = (tile & 1) * 0x1000 + (tile & 0xFE) * 16 + (r & 8) * 2 + (r & 7)
                    else:
                        a = (0x1000 if self.ctrl & 8 else 0) + tile * 16 + r
                    lo, hi = self.vram_read(a), self.vram_read(a + 8)
                    for dx in range(8):
                        sx = sx0 + dx
                        if sx >= 256:
                            continue
                        b = dx if at & 0x40 else 7 - dx
                        c = ((lo >> b) & 1) | (((hi >> b) & 1) << 1)
                        if c and not (at & 0x20 and opaque[sy * 256 + sx]):
                            px[sy * 256 + sx] = self.pal[16 + (at & 3) * 4 + c]
        self.chrreg = saved
        return 256, 240, px
