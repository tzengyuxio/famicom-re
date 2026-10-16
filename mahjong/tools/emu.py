"""Emulator helpers for the 麻雀大会 verifiers (needs py65).

Reuses the MMC1 harness of FC 三國志 (sangokushi/tools/nes_emu.py, loaded by path); this ROM has
128 KB PRG (8 banks), so the fixed upper bank is 7 instead of 15. The game reads the controller
in its IRQ handler ($F530), driven by the APU frame-counter IRQ (4-step mode, about once a frame and
acknowledged by reading $4015), so that interrupt is emulated too.
"""
import importlib.util
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location("san1_nes_emu", os.path.join(REPO, "sangokushi", "tools", "nes_emu.py"))
_emu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_emu)


class Nes(_emu.Nes):
    def __init__(self, rom_path: str):
        self.apu_irq, self.irq_inhibit = False, True
        super().__init__(rom_path)

    def __getitem__(self, a: int) -> int:
        if a == 0x4015:
            v = 0x40 if self.apu_irq else 0
            self.apu_irq = False
            return v
        return super().__getitem__(a)

    def __setitem__(self, a: int, v: int) -> None:
        if a == 0x4017:
            self.irq_inhibit = bool(v & 0x40)
            if self.irq_inhibit:
                self.apu_irq = False
        super().__setitem__(a, v)

    def _run_until(self, cycle: int, sprite0: int | None = None) -> None:
        cpu, bps = self.cpu, self.breakpoints
        while cpu.processorCycles < cycle:
            if self.apu_irq and not cpu.p & cpu.INTERRUPT:
                cpu.irq()
            if bps and cpu.pc in bps:
                bps[cpu.pc](self)
            cpu.step()
            if sprite0 is not None and cpu.processorCycles >= sprite0:
                self.status |= 0x40
                sprite0 = None

    def snapshot(self) -> dict:
        return {**super().snapshot(), "apu": (self.apu_irq, self.irq_inhibit)}

    def restore(self, st: dict) -> None:
        super().restore(st)
        self.apu_irq, self.irq_inhibit = st["apu"]

    def run_frame(self) -> None:
        super().run_frame()
        if not self.irq_inhibit:
            self.apu_irq = True

    def prg_off(self, a: int) -> int:
        mode, bank = (self.mctl >> 2) & 3, self.prgreg & 0x07
        if mode < 2:
            b = (bank & 0x06) | (a >= 0xC000)
        elif mode == 2:
            b = 0 if a < 0xC000 else bank
        else:
            b = bank if a < 0xC000 else 7
        return b * 0x4000 + (a & 0x3FFF)

    def play(self, script) -> None:
        for button, wait in script:
            if button == "wait":
                self.run(wait)
            else:
                self.press(button, wait)

    def nt_tile(self, x: int, y: int, base: int = 0x2000) -> int:
        return self.nt[self.nt_index(base + y * 32 + x)]

    def nt_sub(self, x: int, y: int, base: int = 0x2000) -> int:
        a = self.nt[self.nt_index(base + 0x3C0 + (y // 4) * 8 + x // 4)]
        return (a >> (((y % 4) // 2) * 4 + ((x % 4) // 2) * 2)) & 3

    def bg_pixels(self, x0: int, y0: int, w: int, h: int, base: int = 0x2000) -> bytes:
        """Screen tiles (x0, y0, w, h) of a nametable as NES colour numbers."""
        cb = 0x1000 if self.ctrl & 0x10 else 0
        px = bytearray(w * 8 * h * 8)
        for ty in range(h):
            for tx in range(w):
                t, sub = self.nt_tile(x0 + tx, y0 + ty, base), self.nt_sub(x0 + tx, y0 + ty, base)
                o = cb + t * 16
                for y in range(8):
                    for x in range(8):
                        c = ((self.chr[o + y] >> (7 - x)) & 1) | (((self.chr[o + 8 + y] >> (7 - x)) & 1) << 1)
                        px[(ty * 8 + y) * w * 8 + tx * 8 + x] = self.pal[sub * 4 + c] if c else self.pal[0]
        return bytes(px)


# power-on -> title -> START (main menu: 雀荘 大会 ルール ランク 終了)
TO_MENU = [("wait", 300), ("START", 200)]
# main menu -> A (雀荘): the 16 player cards, card n = player n, its 4x4-tile face at FACE_XY(n)
TO_CARDS = [("A", 200)]


def card_face_xy(n: int) -> tuple[int, int]:
    return 2 + 8 * (n % 4), 6 + 6 * (n // 4)
