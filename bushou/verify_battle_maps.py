#!/usr/bin/env python3
"""Check the battle map decoder (rom.Rom.battle_screen) against the game's own code (needs py65).

For each of the 48 field and 49 castle maps, places the terrain at $7D62 the way the loaders
(bank 23 $A070 / $A1F5) do, sets the size and castle flag, runs the screen builder bank 23
$A42F in an emulator and compares the 32x30 tile and ExRAM buffers and the full-screen image
service call (svc 9: (0, 0) 32x30, $8508 / $88C8) with the static decode.

The rule was first read off the real game: tools/nes_emu.py played into a battle (美濃 墨俣)
and the screen buffers of all 97 maps, captured by switching the battle province, matched too.

Usage: .venv/bin/python bushou/verify_battle_maps.py [--rom ROM]
"""
import argparse

from rom import CASTLE_COUNT, DEFAULT_ROM, FIELD_COUNT, Rom
from tools.pcode_emu import trace_battle_screen


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證戰場地圖解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    errors = 0
    for castle, count, label in ((False, FIELD_COUNT, "field"), (True, CASTLE_COUNT, "castle")):
        bad = []
        for n in range(count):
            tiles, exram, svc = trace_battle_screen(rom.prg, rom.battle_terrain(castle, n), castle)
            ok = (tiles, exram) == rom.battle_screen(castle, n) and svc[:7] == [9, 0, 0, 32, 30, 0x8508, 0x88C8]
            if not ok:
                bad.append(n)
        print(f"[battle] {label}: {count - len(bad)}/{count} maps match (tiles, ExRAM, draw call)"
              + (f" (NG {bad})" if bad else ""))
        errors += len(bad)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
