#!/usr/bin/env python3
"""Check rom.py's static battle-map decode against the game itself (needs py65).

Boots the ROM in tools/emu.py and replays a fixed input script (モンゴルへん, war on province 2)
up to the "すべてよろしいですか" prompt. For each of the 41 maps it swaps that map's 160 terrain
bytes and 176 attribute bytes into the slots the game loads for province 2 (PRG copy only),
confirms the attack and compares what the game shows with the static decode:

1. the 160 bytes copied to WRAM $615E equal the map;
2. every nametable row holds map row y = (row - 4) mod 30 of rom.battle_tilemap(), tiles and
   sub-palettes, except under the message window;
3. CHR-RAM tiles $92-$FF equal BATTLE_TILES and the BG palette equals BATTLE_PALETTE.

A second run checks that a war in せかいへん loads map 14 + country id, and also compares the two strategic maps (rom.map_pixels) with the screen pixels of the war
command's target map in both scenarios (province flags are sprites, so the BG must match exactly).

Usage: .venv/bin/python genghis/verify_battle_maps.py [--rom ROM] [--maps 0,1,...]
"""
import argparse

from rom import (
    BATTLE_ATTRS,
    BATTLE_COUNT,
    BATTLE_FIRST_TILE,
    BATTLE_H,
    BATTLE_MAPS,
    BATTLE_PALETTE,
    BATTLE_TH,
    BATTLE_TILE_COUNT,
    BATTLE_TILES,
    BATTLE_TW,
    BATTLE_W,
    DEFAULT_ROM,
    MAP_X,
    MAP_Y,
    MAPS,
    Rom,
)
from tools.emu import TO_BATTLE, TO_COMMAND_MENU, TO_SCENARIO_MENU, TO_WAR_PROMPT, TO_WORLD_WAR_MAP, Nes

SLOT = 1            # the script attacks province 2 -> map 1
MAP_RAM = 0x615E
NT_ROW0 = 4         # map row 0 is drawn on nametable row 4
WINDOW_TILES = range(0x8B, 0x91)  # message window frame


def window_box(nes: Nes) -> set[tuple[int, int]]:
    cells = [(x, y) for y in range(30) for x in range(64) if nes.nt_tile(x, y) in WINDOW_TILES]
    if not cells:
        return set()
    xs, ys = [x for x, _ in cells], [y for _, y in cells]
    return {(x, y) for x in range(min(xs), max(xs) + 1) for y in range(min(ys), max(ys) + 1)}


def check_strategic(nes: Nes, rom: Rom, sc: str) -> list[str]:
    w, h, px = rom.map_pixels(sc)
    diff = sum(a != b for a, b in zip(nes.bg_pixels(MAP_X, MAP_Y, w // 8, h // 8), px))
    pal = rom.prg[MAPS[sc]["pal"]:MAPS[sc]["pal"] + 16]
    errors = [f"{diff} pixels differ"] if diff else []
    if bytes(nes.pal[:16]) != pal:
        errors.append(f"BG palette {bytes(nes.pal[:16]).hex()}")
    print(f"  strategic map {sc}: {w}x{h} px -> {'OK' if not errors else 'NG'}")
    return errors


def check_map(nes: Nes, start: dict, rom: Rom, idx: int) -> list[str]:
    size = BATTLE_W * BATTLE_H
    prg = bytearray(rom.prg)
    prg[BATTLE_MAPS + SLOT * size:BATTLE_MAPS + (SLOT + 1) * size] = rom.battle_cells(idx)
    prg[BATTLE_ATTRS + SLOT * 176:BATTLE_ATTRS + (SLOT + 1) * 176] = rom.prg[BATTLE_ATTRS + idx * 176:
                                                                            BATTLE_ATTRS + (idx + 1) * 176]
    nes.restore(start)
    nes.prg = bytes(prg)
    nes.play(TO_BATTLE)
    errors = []
    if bytes(nes.wram[MAP_RAM - 0x6000:MAP_RAM - 0x6000 + size]) != rom.battle_cells(idx):
        errors.append("map copy in WRAM differs")
    ids, sub = rom.battle_tilemap(idx)
    skip = window_box(nes)
    bad_tiles = bad_attr = rows = 0
    for r in range(30):
        y = (r - NT_ROW0) % 30
        cands = [yy for yy in (y, y + 30) if yy < BATTLE_TH]
        best = None
        for yy in cands:
            tb = sum(nes.nt_tile(x, r) != ids[yy * BATTLE_TW + x] for x in range(BATTLE_TW) if (x, r) not in skip)
            ab = sum(nes.nt_sub(x, r) != sub[yy * BATTLE_TW + x] for x in range(BATTLE_TW) if (x, r) not in skip)
            if best is None or tb + ab < best[0] + best[1]:
                best = (tb, ab)
        if best:
            rows += 1
            bad_tiles += best[0]
            bad_attr += best[1]
    if bad_tiles or bad_attr:
        errors.append(f"{bad_tiles} tiles / {bad_attr} sub-palettes differ")
    n = BATTLE_TILE_COUNT * 16
    if bytes(nes.chr[0x1000 + BATTLE_FIRST_TILE * 16:0x1000 + BATTLE_FIRST_TILE * 16 + n]) != \
            rom.prg[BATTLE_TILES:BATTLE_TILES + n]:
        errors.append("CHR-RAM battle tiles differ")
    if bytes(nes.pal[:16]) != rom.prg[BATTLE_PALETTE:BATTLE_PALETTE + 16]:
        errors.append(f"BG palette {bytes(nes.pal[:16]).hex()}")
    print(f"  map {idx:2d}: {rows} rows x {BATTLE_TW} tiles compared ({len(skip)} under the window) -> "
          f"{'OK' if not errors else 'NG'}")
    return errors


def main() -> None:
    ap = argparse.ArgumentParser(description="以模擬器驗證戰場地圖的靜態解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--maps", default=",".join(str(i) for i in range(BATTLE_COUNT)))
    args = ap.parse_args()
    rom = Rom(args.rom)
    nes = Nes(args.rom)
    print("replaying input up to the war confirmation ...")
    nes.play(TO_SCENARIO_MENU + TO_COMMAND_MENU + TO_WAR_PROMPT)
    start = nes.snapshot()
    failed = 0
    for e in check_strategic(nes, rom, "mongol"):
        print("    NG", e)
        failed += 1
    for idx in (int(m) for m in args.maps.split(",")):
        for e in check_map(nes, start, rom, idx):
            print("    NG", e)
            failed += 1
    nes = Nes(args.rom)
    nes.play(TO_SCENARIO_MENU + TO_WORLD_WAR_MAP)
    for e in check_strategic(nes, rom, "world"):
        print("    NG", e)
        failed += 1
    # world war on the default target (country 1, きん) must load map 14 + 1
    nes.play(TO_WAR_PROMPT[12:] + TO_BATTLE)
    loaded = bytes(nes.wram[MAP_RAM - 0x6000:MAP_RAM - 0x6000 + BATTLE_W * BATTLE_H])
    ok = loaded == rom.battle_cells(rom.battle_index("world", 1))
    print(f"  world war on country 1 loads map {rom.battle_index('world', 1)} -> {'OK' if ok else 'NG'}")
    failed += not ok
    print("ALL OK" if not failed else f"{failed} problem(s)")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
