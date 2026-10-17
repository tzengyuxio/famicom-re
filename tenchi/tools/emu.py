"""Emulator helpers for the 天地を喰らう verifiers (needs py65).

Reuses the MMC1 harness of FC 三國志 (sangokushi/tools/nes_emu.py, loaded by path) and adds an
input-script player, the fine-x scroll latch and a scroll-aware screen renderer (background through
the scroll in effect when the frame starts, plus 8x8 sprites).
"""
import importlib.util
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ROM = os.path.join(REPO, "roms", "Tenchi o Kurau (Japan) (Rev A).zip")
_spec = importlib.util.spec_from_file_location("san1_nes_emu", os.path.join(REPO, "sangokushi", "tools", "nes_emu.py"))
_emu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_emu)
_emu.STATE = _emu.STATE + ("fine_x", "frame_scroll")


class Nes(_emu.Nes):
    fine_x = 0
    frame_scroll = (0, 0)  # (t, fine x) latched when the frame's rendering starts

    def __init__(self, rom_path: str = ROM):
        super().__init__(rom_path)

    def ppu_write(self, r: int, v: int) -> None:
        if r == 5 and self.w == 0:
            self.fine_x = v & 7
        super().ppu_write(r, v)

    def run_frame(self) -> None:
        self.frame_scroll = (self.t, self.fine_x)
        super().run_frame()

    def play(self, script) -> None:
        for button, wait in script:
            if button == "wait":
                self.run(wait)
            elif button.startswith("HOLD_"):
                self.run(wait, [button[5:]])
            else:
                self.press(button, wait)

    def tile(self, base: int, t: int) -> list[int]:
        o = base + t * 16
        return [((self.chr[o + y] >> (7 - x)) & 1) | (((self.chr[o + 8 + y] >> (7 - x)) & 1) << 1)
                for y in range(8) for x in range(8)]

    def bg_full(self) -> list[bytes]:
        """The 2x2 nametable plane (512x480) as NES colour numbers, one bytes object per row."""
        base = 0x1000 if self.ctrl & 0x10 else 0
        cache = {}
        rows = [bytearray(512) for _ in range(480)]
        for q in range(4):
            nt = 0x2000 + q * 0x400
            for ty in range(30):
                for tx in range(32):
                    t = self.nt[self.nt_index(nt + ty * 32 + tx)]
                    a = self.nt[self.nt_index(nt + 0x3C0 + (ty // 4) * 8 + tx // 4)]
                    sub = (a >> (((ty % 4) // 2) * 4 + ((tx % 4) // 2) * 2)) & 3
                    pix = cache.get(t) or cache.setdefault(t, self.tile(base, t))
                    ox, oy = (q & 1) * 256 + tx * 8, (q >> 1) * 240 + ty * 8
                    for i, c in enumerate(pix):
                        rows[oy + i // 8][ox + i % 8] = self.pal[sub * 4 + c] if c else self.pal[0]
        return rows

    def screen(self) -> bytes:
        """256x240 NES colour numbers through the frame's scroll, with 8x8 sprites on top."""
        t, fx = self.frame_scroll
        sx = ((t & 0x1F) << 3 | fx) + (256 if t & 0x400 else 0)
        sy = ((t >> 5) & 0x1F) * 8 + ((t >> 12) & 7) + (240 if t & 0x800 else 0)
        full = self.bg_full()
        px = bytearray(256 * 240)
        for y in range(240):
            row = full[(sy + y) % 480]
            for x in range(256):
                px[y * 256 + x] = row[(sx + x) % 512]
        if self.mask & 0x10:
            base = 0x1000 if self.ctrl & 0x08 else 0
            for k in range(63, -1, -1):
                y, tl, a, x = self.oam[4 * k:4 * k + 4]
                if y >= 0xEF:
                    continue
                for i, c in enumerate(self.tile(base, tl)):
                    if not c:
                        continue
                    dx, dy = i % 8, i // 8
                    if a & 0x40:
                        dx = 7 - dx
                    if a & 0x80:
                        dy = 7 - dy
                    if x + dx < 256 and y + 1 + dy < 240 and not (a & 0x20 and px[(y + 1 + dy) * 256 + x + dx] != self.pal[0]):
                        px[(y + 1 + dy) * 256 + x + dx] = self.pal[16 + (a & 3) * 4 + c]
        return bytes(px)
