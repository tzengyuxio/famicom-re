#!/usr/bin/env python3
"""Verify the battle maps and the strategy map of rom.py against the game itself (tools/nes_emu.py).

Strategy map: after starting a new game (劉備), nametable 0 rows 4-19 and the attribute table must equal
PRG 0x20000 (rows 0-3 hold the year box drawn over the map), and every castle sprite in OAM must match
rom.py (position, tile, attribute).

Battle maps: the script plays to the first battle (劉備 attacks 幽州 from 并州), then for every province
reloads the battle from the saved state with the target ($050E) replaced, lets the game draw the field and
compares each visible tile of nametable 0 (tile id + attribute sub-palette) with rom.battle_tiles() at the
camera offset that fits best. Tiles covered by unit markers differ, so a field passes at >= 90 % matches.

Usage: .venv/bin/python haou/verify_battle_maps.py [--rom ROM]
"""
import argparse
import os
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
from nes_emu import Nes
from rom import CASTLE_ATTR, CASTLE_TILE, DEFAULT_ROM, HIRA, KATA, MAP_NAMETABLE, PROVINCE_COUNT, Rom

TARGET = 0x050E  # province attacked
SMALL_KANA = {"ャ": 0x35, "ュ": 0x36, "ョ": 0x37, "ッ": 0x38}

# new game with 劉備 (title: 1 player, level 1, first lord) up to the strategy map
TO_MAP = [("START", 120), ("A", 120), ("START", 120), ("START", 120), ("A", 120), ("A", 200), ("A", 200)]


def encode(s: str) -> bytes:
    """Lower-row tile ids of a message (dakuten / handakuten marks sit on the row above)."""
    out = bytearray()
    for c in s:
        base = unicodedata.normalize("NFD", c)[0]
        if base in SMALL_KANA:
            out.append(SMALL_KANA[base])
            continue
        for table, first in ((KATA, 0x04), (HIRA, 0x44)):
            if base in table:
                out.append(first + table.index(base))
                break
        else:
            out.append(0x01)
    return bytes(out)


def on_screen(nes: Nes, msg: str) -> bool:
    raw = bytes(nes.vram_read(0x2000 + k) for k in range(0x800))
    return encode(msg) in raw


def step(nes: Nes, button: str | None, msg: str, limit: int = 1800) -> None:
    """Press `button` (None = just wait), then run until `msg` is on screen; A also skips other messages."""
    if button:
        nes.press(button, 10)
    for _ in range(limit // 10):
        if on_screen(nes, msg):
            nes.run(30)
            return
        nes.run(10)
    raise RuntimeError(f"「{msg}」 not reached")


def to_map(nes: Nes) -> None:
    """Power on -> new game with 劉備, waiting through the other lords' turns until 劉備 gives orders."""
    nes.run(720)
    for b, w in TO_MAP:
        nes.press(b, w)
    for _ in range(100):
        if on_screen(nes, "あたえますか"):
            return
        nes.press("A", 30) if on_screen(nes, "メイレイショは") else nes.run(30)
    raise RuntimeError("strategy map not reached")


def to_battle(nes: Nes) -> None:
    """劉備 attacks 幽州 from 并州 with himself; stops at his last words before the battle."""
    step(nes, "A", "どこへ")             # 并州 (the cursor starts on its castle)
    step(nes, "RIGHT", "どこへ")
    step(nes, "A", "グンタイです メイレイをしてください")  # 軍隊
    step(nes, "A", "せめこみますか")      # 出陣
    for button, k, goal in (("RIGHT", 3, 0xB0), ("UP", 0, 0x18)):  # pointer sprite onto 幽州's castle
        for _ in range(240):
            if nes.oam[k] == goal:
                break
            nes.run(1, [button])
    nes.run(5)
    step(nes, "A", "えらんでください")
    nes.press("A", 60)                   # mark 劉備
    for _ in range(3):
        nes.press("DOWN", 20)
    step(nes, "A", "いきますか")          # おわり -> gold / rice to take (0 / 0)
    nes.press("A", 120)
    step(nes, "A", "よろしいですか")
    step(nes, "A", "ヒツヨウです")        # はい -> order cost
    step(nes, "A", "かならずや")          # はい -> 劉備's face and words


def check_map(nes: Nes, rom: Rom) -> list[str]:
    errors = []
    nt = bytes(nes.vram_read(0x2000 + i) for i in range(0x400))
    ref = rom.prg[MAP_NAMETABLE:MAP_NAMETABLE + 0x400]
    if nt[4 * 32:20 * 32] != ref[4 * 32:20 * 32] or nt[0x3C0:] != ref[0x3C0:]:
        errors.append("strategy map nametable differs")
    sprites = {(nes.oam[k + 3], nes.oam[k], nes.oam[k + 1], nes.oam[k + 2]) for k in range(0, 256, 4)}
    for i in range(PROVINCE_COUNT):
        x, y = rom.castle(i)
        owner = rom.province(i)["owner"]
        if (x, y, rom.prg[CASTLE_TILE + owner], rom.prg[CASTLE_ATTR + owner]) not in sprites:
            errors.append(f"castle {i} sprite not found")
    return errors


def check_battle(nes: Nes, rom: Rom, i: int) -> tuple[float, tuple[int, int]]:
    nt = [nes.vram_read(0x2000 + k) for k in range(0x400)]
    tiles, subs = rom.battle_tiles(i)

    def sub(r, c):
        return (nt[0x3C0 + (r // 4) * 8 + c // 4] >> (((r & 2) << 1) | (c & 2))) & 3

    best = (0.0, (0, 0))
    for cy in range(21):
        for cx in range(33):
            hit = total = 0
            for sy in range(20):
                for sx in range(32):
                    wy, wx = cy + sy, cx + sx
                    r, c = wy % 30, wx % 32
                    total += 1
                    hit += nt[r * 32 + c] == tiles[wy][wx] and sub(r, c) == subs[wy][wx]
            best = max(best, (hit / total, (cx, cy)))
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description="以模擬器驗證 覇王の大陸 大地圖與戰場")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom, nes = Rom(args.rom), Nes(args.rom)
    to_map(nes)
    errors = check_map(nes, rom)
    print("大地圖：" + ("OK" if not errors else "; ".join(errors)))
    to_battle(nes)
    state = nes.snapshot()
    failed = 0
    for i in range(PROVINCE_COUNT):
        nes.restore(state)
        nes.ram[TARGET] = i
        for _ in range(60):  # until the field layout pointer ($A8 -> $00AA) is set, then let it draw
            nes.press("A", 10)
            if nes.ram[0xA8] == 0xAA:
                break
        nes.run(60)
        rate, cam = check_battle(nes, rom, i)
        ok = rate >= 0.9
        failed += not ok
        print(f"戰場 {i:2d} {rom.province(i)['name']}: {rate:.1%} 相符（鏡頭 tile {cam}）{'' if ok else ' ← 失敗'}")
    print(f"戰場 {PROVINCE_COUNT - failed}/{PROVINCE_COUNT} 通過")
    sys.exit(1 if failed or errors else 0)


if __name__ == "__main__":
    main()
