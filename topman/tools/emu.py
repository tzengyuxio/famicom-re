"""Emulator helpers for the Top Management verifiers (needs py65).

Reuses the MMC1 harness of FC 三國志 (sangokushi/tools/nes_emu.py, loaded by path) and adds an
input-script player and a screen renderer (background of nametable 0 plus sprites).
"""
import importlib.util
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location("san1_nes_emu", os.path.join(REPO, "sangokushi", "tools", "nes_emu.py"))
_emu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_emu)


class Nes(_emu.Nes):
    def play(self, script) -> None:
        for button, wait in script:
            if button == "wait":
                self.run(wait)
            elif button.startswith("HOLD_"):
                self.run(wait, [button[5:]])
            else:
                self.press(button, wait)

    def nt_tile(self, x: int, y: int) -> int:
        return self.nt[self.nt_index(0x2000 + (x // 32) * 0x400 + y * 32 + x % 32)]

    def nt_sub(self, x: int, y: int) -> int:
        a = self.nt[self.nt_index(0x2000 + (x // 32) * 0x400 + 0x3C0 + (y // 4) * 8 + (x % 32) // 4)]
        return (a >> (((y % 4) // 2) * 4 + ((x % 4) // 2) * 2)) & 3

    def tile(self, base: int, t: int) -> list[int]:
        o = base + t * 16
        return [((self.chr[o + y] >> (7 - x)) & 1) | (((self.chr[o + 8 + y] >> (7 - x)) & 1) << 1)
                for y in range(8) for x in range(8)]

    def bg_pixels(self, x0: int, y0: int, w: int, h: int) -> bytes:
        """Screen tiles (x0, y0, w, h) of nametable 0 as NES colour numbers."""
        base = 0x1000 if self.ctrl & 0x10 else 0
        px = bytearray(w * 8 * h * 8)
        for ty in range(h):
            for tx in range(w):
                t, sub = self.nt_tile(x0 + tx, y0 + ty), self.nt_sub(x0 + tx, y0 + ty)
                for i, c in enumerate(self.tile(base, t)):
                    px[(ty * 8 + i // 8) * w * 8 + tx * 8 + i % 8] = self.pal[sub * 4 + c] if c else self.pal[0]
        return bytes(px)

    def screen(self) -> bytes:
        """256x240 NES colour numbers: nametable 0 background with 8x8 sprites on top."""
        px = bytearray(self.bg_pixels(0, 0, 32, 30))
        base = 0x1000 if self.ctrl & 0x08 else 0
        for k in range(63, -1, -1):
            y, t, a, x = self.oam[4 * k:4 * k + 4]
            if y >= 0xEF:
                continue
            pix = self.tile(base, t)
            for i, c in enumerate(pix):
                if not c:
                    continue
                dx, dy = i % 8, i // 8
                if a & 0x40:
                    dx = 7 - dx
                if a & 0x80:
                    dy = 7 - dy
                sx, sy = x + dx, y + 1 + dy
                if sx < 256 and sy < 240:
                    px[sy * 256 + sx] = self.pal[16 + (a & 3) * 4 + c]
        return bytes(px)
