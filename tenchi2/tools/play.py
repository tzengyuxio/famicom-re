"""Scripted play from power-on for the verification scripts (deterministic: the harness has no randomness of its own)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from emu import Nes


def mash(n: Nes, frames: int, button: str = "A") -> None:
    """Tap a button every 8 frames."""
    for _ in range(frames // 8):
        n.run(4, [button])
        n.run(4)


def new_game(rom_path: str) -> Nes:
    """Power on, register save slot 1 with the name ああ, start it and skip the opening.

    Ends in 洛陽 (the emperor's hall) with control given to the player, the コマンド window closed."""
    n = Nes(rom_path)
    n.run(400)
    for button, wait in (("START", 120), ("START", 120), ("A", 120), ("A", 200),   # title, れきししょをとうろくする, slot 1
                         ("A", 20), ("A", 20), ("START", 60)):                     # name ああ
        n.press(button, wait)
    for _ in range(9):                                                              # はじめる, slot 1, text speed, …
        n.press("A", 120)
    for _ in range(20):
        n.press("A", 90)
    for _ in range(30):
        n.press("A", 60)
    mash(n, 4000)
    n.run(300)
    n.press("B", 60)
    n.press("B", 60)
    return n


def open_general_list(n: Nes) -> None:
    """コマンド -> ぶしょう: the list of party generals (cursor on the first one)."""
    for button, wait in (("A", 60), ("DOWN", 20), ("DOWN", 20), ("DOWN", 20), ("A", 80)):
        n.press(button, wait)
