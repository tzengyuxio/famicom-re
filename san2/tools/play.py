"""Scripted play of FC 三國志II in tools/nes_emu.py, from power-on to the screens the verifiers need.

Scenario 1 (189), one player. The ruler cursor lands on 袁術 (荊州-19). Each step is
(button or None, hold frames, wait frames). On Y/N prompts ← means Y and → means N.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nes_emu import Nes

# power-on -> 袁術's first command screen (189/1)
TO_COMMAND = [
    (None, 0, 480), (None, 0, 300), ("START", 3, 120),  # title -> scenario list
    ("A", 3, 400),                                     # scenario 1
    ("RIGHT", 3, 20), ("RIGHT", 3, 20), ("UP", 3, 20), ("A", 3, 150),  # 01 player
    ("A", 3, 200), ("LEFT", 3, 400), (None, 0, 600),   # ruler 袁術, Y
    ("UP", 1, 2), ("A", 3, 300),                       # game level 1
    ("LEFT", 3, 1200), ("LEFT", 3, 1800),              # watch other wars: Y; all OK: Y
    ("RIGHT", 3, 1200),                                # decline 陶謙's secret letter
]
# command screen -> 情報/ぶしょう list -> 紀霊's page (the 3rd general of 荊州)
TO_GENERAL_LIST = [("A", 3, 60), ("DOWN", 1, 10), ("A", 3, 200)]
TO_KIREI = [("DOWN", 1, 10)] * 4
# command screen -> 軍事/せんそう: 袁術 alone attacks 董卓's 10 with 1000 gold, 100 food
TO_BATTLE = [
    ("RIGHT", 2, 60), ("A", 2, 60), ("DOWN", 1, 12), ("DOWN", 1, 12), ("DOWN", 1, 12), ("A", 2, 240),
    ("A", 2, 240), ("UP", 3, 30), ("A", 3, 380), ("A", 3, 120),
    ("RIGHT", 3, 30), ("DOWN", 3, 30), ("DOWN", 3, 30), ("A", 3, 620),
    ("RIGHT", 3, 20), ("UP", 3, 20), ("A", 3, 200), ("UP", 3, 20), ("A", 3, 750),
    ("LEFT", 3, 1800),                                 # attack? Y
    ("A", 3, 300),                                     # 袁胤 keeps 19 -> battle screen of 10
]


def play(nes: Nes, steps) -> None:
    for button, hold, wait in steps:
        if button:
            nes.run(hold, [button])
        nes.run(wait)


def boot(rom_path: str, *scripts) -> Nes:
    nes = Nes(rom_path)
    for s in scripts:
        play(nes, s)
    return nes
