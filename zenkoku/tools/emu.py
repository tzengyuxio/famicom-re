"""Emulator helpers for the 全国版 verifiers (needs py65).

Reuses the MMC1 harness of FC 三國志 (sangokushi/tools/nes_emu.py, loaded by path) and adds an
input-script player and nametable readers. Input scripts are (button, frames to wait) pairs;
the game's prompts take LEFT = Y / RIGHT = N, and numbers are typed digit by digit
(UP raises the digit, RIGHT moves to the next one, A confirms).
"""
import importlib.util
import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location("san1_nes_emu", os.path.join(REPO, "sangokushi", "tools", "nes_emu.py"))
_emu = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_emu)


def number(n: int, wait: int = 150) -> list[tuple[str, int]]:
    """Type a number at a (1-NN) prompt."""
    script = []
    for i, d in enumerate(str(n)):
        if i:
            script.append(("RIGHT", 15))
        script += [("UP", 15)] * int(d)
    return script + [("A", wait)]


# power-on -> new game (Y) -> 50 or 17 provinces -> no CPU-vs-CPU demo -> 1 player -> the province prompt
# (the 50-mode prompt shows regional map 0; B shows the next map)
def to_province_prompt(mode: int) -> list[tuple[str, int]]:
    return [("wait", 240), ("START", 120), ("wait", 60), ("LEFT", 120), ("RIGHT" if mode == 50 else "LEFT", 120),
            ("RIGHT", 120), ("UP", 20), ("A", 200)]


# province prompt -> province n (1-based) -> "...ですね (Y/N)"; LEFT then shows the daimyo with face
def pick_province(n: int) -> list[tuple[str, int]]:
    return number(n, 120)


# province prompt -> province n: accept stats, CPU strength 1, confirm, wait for the 1560 spring command menu
def to_command_menu(n: int) -> list[tuple[str, int]]:
    return (pick_province(n) + [("LEFT", 200)] + [("A", 200)] * 5
            + [("LEFT", 200), ("UP", 20), ("A", 300), ("LEFT", 300), ("wait", 1200)])


# command 2 (せんそう) on province n, 70 soldiers, 50 rice -> "とのじきじきに...(Y/N)"
def war_prompt(n: int) -> list[tuple[str, int]]:
    return [("DOWN", 20), ("A", 150)] + number(n) + number(70) + number(50)


# 50 mode: 尾張 (25, 織田) attacks 美濃 (23)
TO_COMMAND_MENU, TO_WAR_PROMPT = to_command_menu(25), war_prompt(23)
# LEFT (yes, lead in person) -> the battle map with the unit placement prompt
TO_BATTLE = [("LEFT", 300), ("wait", 600)]


class Nes(_emu.Nes):
    def play(self, script) -> None:
        for button, wait in script:
            if button == "wait":
                self.run(wait)
            else:
                self.press(button, wait)

    def nt_tile(self, x: int, y: int) -> int:
        return self.nt[self.nt_index(0x2000 + y * 32 + x)]

    def nt_sub(self, x: int, y: int) -> int:
        a = self.nt[self.nt_index(0x23C0 + (y // 4) * 8 + x // 4)]
        return (a >> (((y % 4) // 2) * 4 + ((x % 4) // 2) * 2)) & 3

    def bg_pixels(self, x0: int, y0: int, w: int, h: int) -> bytes:
        """Screen tiles (x0, y0, w, h) of nametable 0 as NES colour numbers."""
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
