#!/usr/bin/env python3
"""Check the hex map decoding (rom.Rom.map_pixels) against the game's own map drawing (needs py65).

The emulator starts a new game as 坂本龍馬, who begins in 高知 (map 42). Just before the map is
loaded, map record 42 in the ROM is replaced by map m; after the map is drawn and the status window
closed (B), the 13 x 9 cells in the name table (tile col 3 + 2c, tile row 2 + 2r, odd columns one
tile lower) must hold the tile ids and ExRAM bytes of rom.Rom.cell_quad. Cells showing a person or
unit icon (tile ids 0x70 and up) or covered by or bordering a text window (another CHR bank; closing
a window can leave its palette bits on the cell above) are skipped. All 47 maps take about 7 minutes.

Usage: .venv/bin/python ishin/verify_maps.py [--rom ROM] [--maps 0,5,42]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
from nes_emu import Nes
from rom import DEFAULT_ROM, MAP_COUNT, MAP_H, MAP_W, MAPS, Rom
from verify_kaodata_export import play

# Power-on up to the last confirmation before 龍馬's map is loaded
BOOT = ("wait:360 " + "A:120 " * 8 + "START:120 A:120 A:120 A:120 START:200 START:200 A:200 A:200 RIGHT:30 "
        "A:200 A:200 A:200 A:200")
HOME_MAP = 42
MAP_CHR_BANK = 0x0B  # every terrain tile comes from 4KB CHR bank 11


def main() -> None:
    ap = argparse.ArgumentParser(description="以模擬器驗證 HEX 地圖解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--maps", help="逗號分隔的地圖編號（預設全部 47 張）")
    args = ap.parse_args()
    rom = Rom(args.rom)
    maps = [int(x) for x in args.maps.split(",")] if args.maps else range(MAP_COUNT)
    nes = Nes(args.rom)
    play(nes, BOOT)
    state = nes.snapshot()
    bad = []
    for m in maps:
        prg = bytearray(rom.prg)
        dst = MAPS + 117 * HOME_MAP
        prg[dst:dst + 117] = rom.map_values(m)
        nes.restore(state)
        nes.prg = bytes(prg)
        play(nes, "A:1500 B:120")
        diff = skipped = 0
        for i, v in enumerate(rom.map_values(m)):
            r, c = divmod(i, MAP_W)
            x, y = 3 + 2 * c, 2 + (c & 1) + 2 * r
            cells = [(y + dy) * 32 + x + dx for dy in (0, 1) for dx in (0, 1)]
            tiles = bytes(nes.nt_read(0x2000 + a) for a in cells)
            exram = bytes(nes.exram[a] for a in cells)
            below = [nes.exram[(y + 2) * 32 + x + dx] & 0x3F for dx in (0, 1)] if y + 2 < 30 else []
            if tiles[0] >= 0x70 or any(e & 0x3F != MAP_CHR_BANK for e in exram + bytes(below)):
                skipped += 1
            elif (tiles, exram) != rom.cell_quad(v):
                diff += 1
        print(f"  map {m:2d} {rom.map_name(m)}: {'OK' if not diff else f'{diff} cells differ'}"
              f" ({MAP_W * MAP_H - skipped} cells checked)")
        if diff:
            bad.append(m)
    print(f"[maps] {len(maps) - len(bad)}/{len(maps)} maps match the game's drawing")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
