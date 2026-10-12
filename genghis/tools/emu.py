"""Emulator helpers for the Genghis Khan verifiers (needs py65).

Reuses the MMC1 harness of FC 三國志 (sangokushi/tools/nes_emu.py, loaded by path) and adds a
CPU read hook, an input-script player and nametable readers.
"""
import importlib.util
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location("san1_nes_emu", os.path.join(REPO, "sangokushi", "tools", "nes_emu.py"))
_emu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_emu)

# (button, frames to wait) from power-on to the scenario menu (モンゴルへん / せかいへん / データロード)
TO_SCENARIO_MENU = [("wait", 300), ("START", 200)]
# Scenario menu -> モンゴルへん, auto stats, defaults -> the first command menu of 1175 spring
TO_COMMAND_MENU = [("A", 300)] + [("A", 100)] * 5 + [("A", 300), ("wait", 1500)]
# Command menu -> せんそう (13th) on the default target (province 2), 8 soldiers, food, Temujin leads,
# up to the "すべてよろしいですか" prompt
TO_WAR_PROMPT = ([("DOWN", 10)] * 12 + [("A", 200), ("A", 200), ("HOLD_UP", 120), ("wait", 20), ("A", 200),
                                        ("HOLD_UP", 60), ("wait", 20), ("A", 200), ("A", 200)])
# Scenario menu -> せかいへん, 1 player, ジンギスカン, defaults -> the war command's target map
TO_WORLD_WAR_MAP = ([("DOWN", 20), ("A", 300), ("A", 300), ("A", 300)] + [("A", 100)] * 5
                    + [("A", 300), ("wait", 1500)] + [("DOWN", 10)] * 12 + [("A", 200)])
# Prompt -> はい, season processing, the battle summary, then the battle map
TO_BATTLE = [("A", 900), ("A", 60), ("A", 60)]


class Nes(_emu.Nes):
    read_hook = None  # f(nes, addr) before CPU reads in $8000-$FFFF

    def __getitem__(self, a: int) -> int:
        if a >= 0x8000 and self.read_hook:
            self.read_hook(self, a)
        return super().__getitem__(a)

    def play(self, script) -> None:
        for button, wait in script:
            if button == "wait":
                self.run(wait)
            elif button.startswith("HOLD_"):
                self.run(wait, [button[5:]])
            else:
                self.press(button, wait)

    def nt_tile(self, x: int, y: int) -> int:
        """Tile id at virtual nametable position (x 0-63, y 0-29); nametables 0 and 1 side by side."""
        return self.nt[self.nt_index(0x2000 + (x // 32) * 0x400 + y * 32 + x % 32)]

    def nt_sub(self, x: int, y: int) -> int:
        a = self.nt[self.nt_index(0x2000 + (x // 32) * 0x400 + 0x3C0 + (y // 4) * 8 + (x % 32) // 4)]
        return (a >> (((y % 4) // 2) * 4 + ((x % 4) // 2) * 2)) & 3

    def bg_pixels(self, x0: int, y0: int, w: int, h: int) -> bytes:
        """Screen tiles (x0, y0, w, h) of nametable 0 as NES colour numbers (BG pattern table from $2000)."""
        base = 0x1000 if self.ctrl & 0x10 else 0
        px = bytearray(w * 8 * h * 8)
        for ty in range(h):
            for tx in range(w):
                t, sub = self.nt_tile(x0 + tx, y0 + ty), self.nt_sub(x0 + tx, y0 + ty)
                o = base + t * 16
                for y in range(8):
                    for x in range(8):
                        c = ((self.chr[o + y] >> (7 - x)) & 1) | (((self.chr[o + 8 + y] >> (7 - x)) & 1) << 1)
                        px[(ty * 8 + y) * w * 8 + tx * 8 + x] = self.pal[sub * 4 + c] if c else self.pal[0]
        return bytes(px)
