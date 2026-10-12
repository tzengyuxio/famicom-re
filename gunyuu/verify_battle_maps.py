#!/usr/bin/env python3
"""Check the battle map decoder (rom.Rom.battle_screen) against the game's own code (needs py65).

For each of the 38 field and 38 castle maps, places the terrain at $7C88 the way the battle set-up
($AF72 in bank 10) leaves it (field cells through rom.Rom.field_load, castle cells as stored), sets
the castle flag $7A6E, runs the cell drawer (bank 9 $8E14) for every cell in an emulator and
compares the tile ids and ExRAM bytes it hands to the draw-block service with the static decode.

The rest was first read off the real game: tools/nes_emu.py played a field battle (伊勢志摩 → 近江)
and its name table matched the decode; $AF72, run in tools/pcode_emu.py from that game state with the
castle flag cleared / set, loaded and drew field map 18 and castle map 18 exactly as decoded here.

Usage: .venv/bin/python gunyuu/verify_battle_maps.py [--rom ROM]
"""
import argparse

from rom import DEFAULT_ROM, PROVINCE_COUNT, Rom
from tools.pcode_emu import trace_battle_screen


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證戰場地圖解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    errors = 0
    for castle, label in ((False, "field"), (True, "castle")):
        bad = []
        for n in range(PROVINCE_COUNT):
            terrain = rom.battle_terrain(castle, n)
            if not castle:
                terrain = bytes(rom.field_load(v) for v in terrain)
            if trace_battle_screen(rom.prg, terrain, castle) != rom.battle_screen(castle, n):
                bad.append(n)
        print(f"[battle] {label}: {PROVINCE_COUNT - len(bad)}/{PROVINCE_COUNT} maps match (tiles, ExRAM)"
              + (f" (NG {bad})" if bad else ""))
        errors += len(bad)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
