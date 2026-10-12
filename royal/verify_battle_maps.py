#!/usr/bin/env python3
"""Check the map decoders (rom.Rom.map_cells, rom.Rom.battle_cells) against the game itself (needs py65).

Strategy map: on the "何人でプレイしますか?" screen of scenario 1 the 14 x 19 cells at name table (16, 4)
must equal the static decode except at the marker cell (provinces.csv 地圖標號格) of each owned province,
where the game draws the house marker.

tools/nes_emu.py plays scenario 1 in demo mode until the first battle (リンディニス, province 24): the
game copies that province's 80-byte grid from bank 19 to $6860 at frame DEMO_BATTLE_COPY and has drawn
the battlefield by DEMO_BATTLE_DRAWN. For each of the 30 provinces the grid at $6860 is replaced by that
province's grid right after the copy, the game draws the field, and every cell without a unit (low
nibble of the cell 0 at the end) is compared with the static decode: 2 x 2 tile ids and ExRAM bytes at
name table (6, 7) + 2 * (col, row).

Usage: .venv/bin/python royal/verify_battle_maps.py [--rom ROM]
"""
import argparse

from rom import BATTLE_H, BATTLE_ORIGIN, BATTLE_W, BATTLE_WRAM, DEFAULT_ROM, MAP_H, MAP_W, PROVINCE_COUNT, Rom
from tools.play import DEMO, DEMO_BATTLE_COPY, DEMO_BATTLE_DRAWN, boot


def check_map(rom: Rom, nes) -> int:
    tiles, exram = rom.map_cells()
    diff = set()
    for i in range(MAP_W * MAP_H):
        n = (4 + i // MAP_W) * 32 + 16 + i % MAP_W
        if (nes.ciram[n], nes.exram[n]) != (tiles[i], exram[i]):
            diff.add((i % MAP_W, i // MAP_W))
    markers = {p["label"] for p in rom.provinces(0) if p["owner"] is not None}
    ok = diff == markers
    print(f"[map] {MAP_W * MAP_H - len(diff)}/{MAP_W * MAP_H} cells match; the other {len(diff)} are "
          + ("exactly the house markers of the owned provinces" if ok else f"NOT the markers: {sorted(diff ^ markers)}"))
    return 0 if ok else 1


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證戰場地圖解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    errors = check_map(rom, boot(args.rom))
    nes = boot(args.rom, DEMO)
    while nes.frame < DEMO_BATTLE_COPY:
        nes.run(1)
    assert bytes(nes.wram[BATTLE_WRAM:BATTLE_WRAM + 80]) == rom.battle_grid(23), "demo did not reach the battle"
    start = nes.snapshot()
    x0, y0 = BATTLE_ORIGIN
    for p in range(PROVINCE_COUNT):
        nes.restore(start)
        nes.wram[BATTLE_WRAM:BATTLE_WRAM + 80] = rom.battle_grid(p)
        nes.run(DEMO_BATTLE_DRAWN - DEMO_BATTLE_COPY)
        tiles, exram = rom.battle_cells(p)
        checked = bad = 0
        for i in range(BATTLE_W * BATTLE_H):
            if nes.wram[BATTLE_WRAM + i] & 0x0F:  # a unit stands here
                continue
            r, c = divmod(i, BATTLE_W)
            for k in range(4):
                a = (2 * r + k // 2) * BATTLE_W * 2 + 2 * c + k % 2
                n = (y0 + 2 * r + k // 2) * 32 + x0 + 2 * c + k % 2
                if (nes.ciram[n], nes.exram[n]) != (tiles[a], exram[a]):
                    bad += 1
            checked += 1
        ok = bad == 0 and checked >= 60
        errors += not ok
        print(f"[battle] {p + 1:2d} {rom.province_info(p)['name']}: {checked} cells checked"
              + ("" if ok else f" — {bad} tiles differ"))
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
