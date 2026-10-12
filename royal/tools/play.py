"""Input sequences that drive FC ロイヤルブラッド in tools/nes_emu.py to known game states."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nes_emu import Nes

# boot -> title -> intro skipped -> scenario 1 chosen ("何人でプレイしますか?")
TO_PLAYERS = [(None, 300), ("START", 120), ("START", 120), ("START", 200), ("START", 200), ("A", 200),
              ("START", 100), ("START", 100), ("START", 100), ("START", 100), ("START", 100), ("A", 100), ("A", 100)]
HOUSE_SELECT = [("A", 60)]                                  # 1 player -> "どの家をたんとうしますか?"
DEMO = [("RIGHT", 20), ("RIGHT", 20), ("A", 100), ("A", 30)]  # デモプレイ, はい
DEMO_BATTLE_COPY = 3621   # demo frame after the battle grid of リンディニス (province 24) is copied to $6860
DEMO_BATTLE_DRAWN = 3963  # frame by which the battlefield is drawn


def play(nes: Nes, steps) -> Nes:
    for button, wait in steps:
        if button is None:
            nes.run(wait)
        else:
            nes.press(button, wait)
    return nes


def boot(rom_path: str, steps=()) -> Nes:
    return play(play(Nes(rom_path), TO_PLAYERS), steps)
