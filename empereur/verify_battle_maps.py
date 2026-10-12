#!/usr/bin/env python3
"""Check the battle map decoder (rom.Rom.battle_*) against the game's own code (needs py65).

For each of the 46 maps (one per city), points the attacked-city pointer (WRAM $7CD3) at the
city's record and runs bank 12 $A15C (unpack the terrain from bank 21 into $7748) and $A1D6
(build the 26x25 tile and ExRAM buffers), then compares terrain, both buffers and the arguments
of the image service call (svc 9 at tile (3, 2), 26x25, $7684 / $790E) with the static decode.

Usage: .venv/bin/python empereur/verify_battle_maps.py [--rom ROM]
"""
import argparse

from rom import BATTLE_TILE_H, BATTLE_TILE_W, CITY_COUNT, DEFAULT_ROM, Rom
from tools.pcode_emu import trace_battle_map


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證戰場地圖解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    bad = []
    for n in range(CITY_COUNT):
        terrain, tiles, exram, svc = trace_battle_map(rom.prg, n)
        bt, be = rom.battle_cells(n)
        ok = list(terrain) == rom.battle_terrain(n) and tiles == bytes(bt) and exram == bytes(be)
        ok &= list(svc[:6]) == [3, 2, BATTLE_TILE_W, BATTLE_TILE_H, 0x7684, 0x790E]
        if not ok:
            bad.append(n)
    print(f"[battle] {CITY_COUNT - len(bad)}/{CITY_COUNT} maps match (terrain, tiles, ExRAM, draw call)"
          + (f" (NG {bad})" if bad else ""))
    print("ALL OK" if not bad else f"{len(bad)} problem(s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
