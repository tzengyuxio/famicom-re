#!/usr/bin/env python3
"""Check the battle map decoder (rom.Rom.battle_*) against the game's own code (needs py65).

For every province and season, runs the battle setup ($A47A) and map drawing ($A319) in the
emulator and compares the block kinds ($7A8C), province ids ($7C84) and the 168 image draws
(screen position, tile and ExRAM pointers) with the static decode.

Usage: .venv/bin/python suikoden/verify_battle_maps.py [--rom ROM] [--seasons 0123]
"""
import argparse

from rom import BATTLE_EXRAM_PTRS, BATTLE_TILE_PTRS, DEFAULT_ROM, PROVINCE_COUNT, SEASONS, Rom
from tools.pcode_emu import trace_battle_map

MONTH_OF_SEASON = [3, 6, 9, 12]  # $D12A: month / 3 = 1, 2, 3 -> season 0, 1, 2; anything else -> 3


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證戰鬥地圖解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--seasons", default="0123", help="要檢查的季節（0=春 … 3=冬）")
    args = ap.parse_args()
    rom = Rom(args.rom)
    errors = 0
    for season in map(int, args.seasons):
        bad = []
        for n in range(PROVINCE_COUNT):
            draws, kinds, regions = trace_battle_map(rom.prg, n, MONTH_OF_SEASON[season])
            got = {(c, r): (t, e) for c, r, t, e in draws}
            expect = {(c, r): (rom.u16(BATTLE_TILE_PTRS + 2 * k), rom.u16(BATTLE_EXRAM_PTRS + 2 * k))
                      for c, r, k in rom.battle_cells(n, season)}
            if (len(draws) != 168 or got != expect or list(kinds) != rom.battle_kinds(n, season)
                    or list(regions) != rom.battle_regions(n)):
                bad.append(n)
        print(f"[battle] {SEASONS[season]}: {PROVINCE_COUNT - len(bad)}/{PROVINCE_COUNT} provinces match"
              + (f" (NG {bad})" if bad else ""))
        errors += len(bad)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
