#!/usr/bin/env python3
"""Check export_battle_maps.py's static decode against the game itself (needs py65).

Boots the ROM in tools/nes_emu.py and replays a fixed input script (scenario 1,
曹操, war from province 7 on province 5) up to the attack confirmation. Then, for
each tested province, it redirects the target-city pointer ($78A5) to that
province when the map loader ($EE79) starts, confirms the attack, and compares
what the game does with the static decode:

1. the 168 bytes the loader copies to $7B95 equal the map at MAPS + (n-1)*168;
2. every cell the game draws (native $C43D) uses tile layout CELLS + 16*terrain
   at the expected nametable position, and the attribute written for it equals
   TERRAIN_PALETTE[terrain];
3. CHR-RAM tiles $64-$BA equal TILES, and the background palette shown after
   the fade-in equals BG_PALETTE.

Usage: .venv/bin/python sangokushi/tools/verify_battle_maps.py [--rom ROM] [--provinces 5,10,...]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export_battle_maps import (
    BG_PALETTE,
    CELLS,
    COLS,
    DEFAULT_ROM,
    FIRST_TILE,
    MAPS,
    ROWS,
    TERRAIN_PALETTE,
    TILES,
)
from nes_emu import Nes

MAP_LOADER = 0xEE79    # p-code: copy map ($78A5 - $73A7) / 22 from bank 9 to $7B95
DRAW_RECT = 0xC43D     # native: fill nametable rect ($52 nt, $54/$56 x0/y0, $5C src)
MAP_RAM = 0x7B95
TARGET_CITY = 0x78A5   # word: pointer to the attacked city's 22-byte record
CITY_TABLE = 0x73A7
CITY_SIZE = 22
CELLS_CPU = CELLS - 0xC000 + 0x8000  # CELLS as the CPU sees it (bank 3 at $8000)

# (button, frames to wait) from power-on to the "攻め込みますか (Y/N)?" prompt
SCRIPT = (
    [("wait", 300), ("START", 60), ("LEFT", 40), ("wait", 60), ("A", 120),   # new game, scenario 1
     ("UP", 20), ("A", 90), ("UP", 20), ("A", 120), ("wait", 120)]           # 1 player, 曹操
    + [("A", 30)] * 5 + [("wait", 60), ("LEFT", 180), ("UP", 20), ("A", 240),  # stats, difficulty
                         ("LEFT", 300), ("LEFT", 300), ("LEFT", 600), ("A", 600)]
    + [("A2", 150)] * 16                                                     # to the first command menu
    + [("UP", 15), ("UP", 15), ("A", 120), ("B", 60), ("wait", 120), ("B", 60), ("wait", 720),
       ("A", 300), ("wait", 200), ("UP", 10), ("UP", 30), ("DOWN", 10), ("DOWN", 10), ("DOWN", 30),
       ("A", 400)]                                                           # command 2 (war)
    + [("UP", 8)] * 4 + [("UP", 30), ("A", 400)]                             # target province 5
    + [("A", 30), ("DOWN", 10), ("A", 30), ("B", 300), ("UP", 10), ("A", 300),  # generals, gold 1
       ("HOLD_UP", 5), ("RIGHT", 20), ("RIGHT", 20), ("A", 300)]            # food 500
)


def replay(nes: Nes) -> None:
    for button, wait in SCRIPT:
        if button == "wait":
            nes.run(wait)
        elif button == "A2":
            nes.press("A", wait, hold=2)
        elif button == "HOLD_UP":
            nes.run(120, ["UP"])
            nes.run(wait)
        else:
            nes.press(button, wait)


def check_province(nes: Nes, start: dict, prov: int) -> list[str]:
    prg = nes.prg
    expect = prg[MAPS + (prov - 1) * COLS * ROWS:MAPS + prov * COLS * ROWS]
    nes.restore(start)
    errors, drawn, first = [], [], {}

    def redirect(n: Nes) -> None:
        ptr = CITY_TABLE + (prov - 1) * CITY_SIZE
        n.wram[TARGET_CITY - 0x6000], n.wram[TARGET_CITY - 0x5FFF] = ptr & 0xFF, ptr >> 8

    def rect(n: Nes) -> None:
        r = n.ram
        if r[0x5E] != 3 or (r[0x58] - r[0x54], r[0x5A] - r[0x56]) != (3, 3):
            return  # not a 4x4 terrain cell (window frames, text)
        gx = r[0x52] * 32 + r[0x54]
        col = (gx - 4) // 4
        row = (r[0x56] - 4 - (2 if col % 2 else 0)) // 4
        attr = n.nt[r[0x52] * 0x400 + 0x3C0 + (r[0x56] // 4) * 8 + r[0x54] // 4]
        sub = (attr >> (((r[0x56] % 4) // 2) * 4 + ((r[0x54] % 4) // 2) * 2)) & 3
        drawn.append((col, row, r[0x5C] | r[0x5D] << 8, sub))
        if not first:  # state when the map has just been loaded (units and palette effects come later)
            first.update(map=bytes(n.wram[MAP_RAM - 0x6000:MAP_RAM - 0x6000 + COLS * ROWS]),
                         chr=bytes(n.chr))

    nes.breakpoints = {MAP_LOADER: redirect, DRAW_RECT: rect}
    nes.press("LEFT", 600)
    nes.run(3, ["A"])
    palettes = set()
    for _ in range(300):
        nes.run_frame()
        if first:
            palettes.add(bytes(nes.pal[:16]))
    nes.breakpoints = {}

    if not first:
        return [f"province {prov}: no map cells drawn"]
    got = first["map"]
    if got != expect:
        errors.append(f"map copy differs in {sum(a != b for a, b in zip(got, expect))} bytes")
    cells = [d for d in drawn if 0 <= d[0] < COLS and 0 <= d[1] < ROWS]
    if not cells:
        errors.append("no map cells drawn")
    for col, row, src, sub in cells:
        terrain = expect[row * COLS + col] >> 3
        if src != CELLS_CPU + 16 * terrain or sub != prg[TERRAIN_PALETTE + terrain]:
            errors.append(f"cell ({col},{row}) terrain {terrain}: src {src:04X} sub-palette {sub}")
    seen = sorted({expect[r * COLS + c] >> 3 for c, r, *_ in cells})
    n_tiles = 0xBB - FIRST_TILE
    if first["chr"][0x1000 + FIRST_TILE * 16:0x1000 + 0xBB * 16] != prg[TILES:TILES + n_tiles * 16]:
        errors.append("CHR-RAM terrain tiles differ")
    if prg[BG_PALETTE:BG_PALETTE + 16] not in palettes:  # the palette fades in, then may flash
        errors.append(f"palette never equals BG_PALETTE: {sorted(p.hex() for p in palettes)}")
    print(f"  province {prov:2d}: {len(cells)} cells drawn, terrains {seen} -> {'OK' if not errors else 'NG'}")
    return errors


def main() -> None:
    ap = argparse.ArgumentParser(description="以模擬器驗證戰爭地圖的靜態解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--provinces", default="5,1,10,26,58")
    args = ap.parse_args()
    nes = Nes(args.rom)
    print("replaying input up to the war declaration ...")
    replay(nes)
    start = nes.snapshot()
    failed = 0
    for prov in (int(p) for p in args.provinces.split(",")):
        for e in check_province(nes, start, prov):
            print("    NG", e)
            failed += 1
    print("ALL OK" if not failed else f"{failed} problem(s)")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
