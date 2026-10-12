#!/usr/bin/env python3
"""Check rom.py's regional and battle map decode against the game itself (needs py65).

Regional maps: at the province prompt the game shows map 0 and B steps to the next one (and wraps).
For every map of both modes the 28x16 tiles at screen (2, 4) equal rom.map_view() except where the
game prints province labels (font tiles < $51), the attribute rows 1-4 and the BG palette are
equal, and CHR-RAM $1510 holds the map tiles.

Battle maps: the input script attacks 美濃 (map 22) from 尾張. For each of the 50 maps, its 11x5
cells (and attribute view) are swapped into map 22's slots (PRG copy only) and the battle screen is
compared with the static decode: the map as is, with its three attribute views, and the map shifted left by 6 and by 4
columns (an even shift keeps the column parity; shift 6 brings view 2 with it). The game may open on
any view (column 0, 3 or 6; rule not known), so the best matching view is taken. Each run
compares the 20x22 tiles at screen (10, 4), the pixels of non-blank cells where the stored
attributes apply, the BG palette and CHR-RAM tiles $57-$B6. The defender's units are already on the map as 4x2-tile markers (tiles outside the
terrain range $57-$B0); those tiles are skipped and counted. Statically, every stored attribute view (columns 0-4, 3-7, 6-10) equals the per-terrain
sub-palette rule on non-blank cells. A 17-mode war on ミノ checks that 17-mode province p uses
map rom.global_daimyo(17, p).

Usage: .venv/bin/python zenkoku/verify_maps.py [--rom ROM] [--maps 0,1,...]
"""
import argparse

from rom import (
    BATTLE_ATTRS,
    BATTLE_COUNT,
    BATTLE_FIRST_TILE,
    BATTLE_H,
    BATTLE_MAPS,
    BATTLE_PALETTE,
    BATTLE_TILE_COUNT,
    BATTLE_TILES,
    BATTLE_VIEW_COLS,
    BATTLE_VIEW_W,
    BATTLE_VIEW_X,
    BATTLE_VIEW_Y,
    BATTLE_W,
    BLANK_TILE,
    DEFAULT_ROM,
    MAP_FIRST_TILE,
    MAP_H,
    MAP_PALETTE,
    MAP_TILE_COUNT,
    MAP_TILES,
    MAP_VIEWS,
    MAP_W,
    MAP_X,
    MAP_Y,
    MODES,
    TERRAIN,
    Rom,
    attr_sub,
)
from tools.emu import TO_BATTLE, TO_COMMAND_MENU, TO_WAR_PROMPT, Nes, to_command_menu, to_province_prompt, war_prompt

SLOT = 22                    # the script attacks province 23 (美濃)
VIEW_TW, VIEW_TH = 4 * BATTLE_VIEW_W, 4 * BATTLE_H + 2
LAST_TERRAIN_TILE = BATTLE_FIRST_TILE + 90 - 1  # $57-$B0 are the terrain blocks' tiles


def check_regional(rom: Rom, rom_path: str) -> int:
    errors = 0
    for mode in MODES:
        nes = Nes(rom_path)
        nes.play(to_province_prompt(mode))
        count = MAP_VIEWS[mode][3]
        for step in range(count + 1):  # one extra B: back to map 0
            if step:
                nes.play([("B", 200)])
            v = step % count
            ids, attr = rom.map_view(mode, v)
            other = labels = 0
            for i in range(MAP_W * MAP_H):
                t = nes.nt_tile(MAP_X + i % MAP_W, MAP_Y + i // MAP_W)
                if t != ids[i]:
                    labels += t < MAP_FIRST_TILE
                    other += t >= MAP_FIRST_TILE
            label_ok = all(nes.nt_tile(x, y) < MAP_FIRST_TILE for _, x, y in rom.map_labels(mode, v))
            nt_attr = bytes(nes.nt[nes.nt_index(0x23C8):nes.nt_index(0x23C8) + 32])
            n = MAP_TILE_COUNT * 16
            ok = (not other and label_ok and nt_attr == attr
                  and bytes(nes.pal[:16]) == rom.prg[MAP_PALETTE:MAP_PALETTE + 16]
                  and bytes(nes.chr[0x1000 + MAP_FIRST_TILE * 16:0x1000 + MAP_FIRST_TILE * 16 + n])
                  == rom.prg[MAP_TILES:MAP_TILES + n])
            print(f"  {mode}-mode map {v}{' (wrap)' if step == count else ''}: {MAP_W * MAP_H - labels - other} tiles"
                  f" equal, {labels} under labels -> {'OK' if ok else 'NG'}")
            errors += not ok
    return errors


def check_attr_views(rom: Rom) -> int:
    bad = 0
    for idx in range(BATTLE_COUNT):
        cells = rom.battle_cells(idx)
        for view, col0 in enumerate(BATTLE_VIEW_COLS):
            attr = rom.battle_attrs(idx, view)
            for c in range(col0, min(col0 + BATTLE_VIEW_W, BATTLE_W)):
                for r in range(BATTLE_H):
                    v = cells[r * BATTLE_W + c]
                    if v not in TERRAIN or rom.battle_block(v)[0] == BLANK_TILE:
                        continue
                    x, y = BATTLE_VIEW_X + 4 * (c - col0), BATTLE_VIEW_Y + 4 * r + 2 * (c & 1)
                    subs = {attr_sub(attr, x + i, y + j, 1) for i in (0, 2) for j in (0, 2)}
                    bad += subs != {TERRAIN[v][2]}
    print(f"  stored attribute views vs terrain sub-palettes: {bad} cell(s) differ -> {'OK' if not bad else 'NG'}")
    return int(bad > 0)


def compare_battle(nes: Nes, rom: Rom, cells: bytes, pixels: set[int]) -> tuple[list[str], int, int]:
    """Compare the battle screen with cells (11x5). The game may open on any stored view (map column 0,
    3 or 6; the rule is not known), so the view with the fewest differing tiles is taken; pixels are
    compared only for views in `pixels` (those whose stored attributes match the cells).
    Returns errors, the view's first column and the number of tiles under unit markers (the
    defender's units are already placed: 4x2-tile markers of non-terrain tiles, outside $57-$B0)."""
    best = None
    for col0 in BATTLE_VIEW_COLS:
        ids, subs = rom.battle_tilemap(0, col0, BATTLE_VIEW_W, cells)
        masked, bad = set(), 0
        for i, t in enumerate(ids):
            got = nes.nt_tile(BATTLE_VIEW_X + i % VIEW_TW, BATTLE_VIEW_Y + i // VIEW_TW)
            if got != t:
                if BATTLE_FIRST_TILE <= got <= LAST_TERRAIN_TILE:
                    bad += 1
                else:
                    masked.add(i)
        if best is None or bad < best[0]:
            best = (bad, col0, ids, subs, masked)
    bad, col0, ids, subs, masked = best
    errors = []
    if bad:
        errors.append(f"{bad} tiles differ")
    if col0 in pixels:
        def off(t: int):
            return BATTLE_TILES + (t - BATTLE_FIRST_TILE) * 16 if t >= BATTLE_FIRST_TILE else None
        want = rom.render(ids, VIEW_TW, subs, off, rom.prg[BATTLE_PALETTE:BATTLE_PALETTE + 16])
        got = nes.bg_pixels(BATTLE_VIEW_X, BATTLE_VIEW_Y, VIEW_TW, VIEW_TH)
        diff = 0
        for i, (a, b) in enumerate(zip(got, want)):
            cell = (i // (VIEW_TW * 64)) * VIEW_TW + (i % (VIEW_TW * 8)) // 8
            diff += a != b and ids[cell] != BLANK_TILE and cell not in masked
        if diff:
            errors.append(f"{diff} pixels differ")
    n = BATTLE_TILE_COUNT * 16
    if bytes(nes.chr[0x1000 + BATTLE_FIRST_TILE * 16:0x1000 + BATTLE_FIRST_TILE * 16 + n]) != \
            rom.prg[BATTLE_TILES:BATTLE_TILES + n]:
        errors.append("CHR-RAM battle tiles differ")
    if bytes(nes.pal[:16]) != rom.prg[BATTLE_PALETTE:BATTLE_PALETTE + 16]:
        errors.append(f"BG palette {bytes(nes.pal[:16]).hex()}")
    return errors, col0, len(masked)


def check_battles(rom: Rom, rom_path: str, maps: list[int]) -> int:
    nes = Nes(rom_path)
    nes.play(to_province_prompt(50) + TO_COMMAND_MENU + TO_WAR_PROMPT)
    start = nes.snapshot()
    size = BATTLE_W * BATTLE_H
    failed = 0
    for idx in maps:
        cells = rom.battle_cells(idx)
        results = []
        for shift in (0, 4, 6):
            moved = bytearray(cells)
            for r in range(BATTLE_H):
                row = cells[r * BATTLE_W + shift:(r + 1) * BATTLE_W]
                moved[r * BATTLE_W:r * BATTLE_W + len(row)] = row
            prg = bytearray(rom.prg)
            prg[BATTLE_MAPS + SLOT * size:BATTLE_MAPS + (SLOT + 1) * size] = moved
            attrs = BATTLE_ATTRS + 144 * SLOT
            if shift == 0:  # all three stored views
                prg[attrs:attrs + 144] = b"".join(rom.battle_attrs(idx, v) for v in range(3))
                pixels = set(BATTLE_VIEW_COLS)
            elif shift == 6:  # columns 6-10 with their view
                prg[attrs:attrs + 48] = rom.battle_attrs(idx, 2)
                pixels = {0}
            else:
                pixels = set()
            nes.restore(start)
            nes.prg = bytes(prg)
            nes.play(TO_BATTLE)
            errs, col0, masked = compare_battle(nes, rom, bytes(moved), pixels)
            shown = f"cols {shift + col0}-{min(shift + col0 + 4, BATTLE_W - 1)}" if shift + col0 + 4 <= 10 or not shift \
                else f"shift {shift} view {col0}"
            results.append(f"{shown} " + (f"OK ({masked} under units)" if not errs else "NG " + "; ".join(errs)))
            failed += bool(errs)
        print(f"  battle map {idx:2d}: " + ", ".join(results))
    return failed


def check_17(rom: Rom, rom_path: str) -> int:
    nes = Nes(rom_path)
    mino = 8  # 17-mode 尾張 = province 17 attacks ミノ = province 9
    nes.play(to_province_prompt(17) + to_command_menu(MODES[17][1]) + war_prompt(mino + 1) + TO_BATTLE)
    idx = rom.global_daimyo(17, mino)
    errs, _, _ = compare_battle(nes, rom, rom.battle_cells(idx), set())
    print(f"  17-mode war on province {mino + 1} uses map {idx} -> {'OK' if not errs else 'NG ' + '; '.join(errs)}")
    return bool(errs)


def main() -> None:
    ap = argparse.ArgumentParser(description="以模擬器驗證地方地圖與戰場地圖的靜態解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--maps", default=",".join(str(i) for i in range(BATTLE_COUNT)))
    args = ap.parse_args()
    rom = Rom(args.rom)
    print("[regional maps]")
    failed = check_regional(rom, args.rom)
    print("[battle maps]")
    failed += check_attr_views(rom)
    failed += check_battles(rom, args.rom, [int(m) for m in args.maps.split(",")])
    failed += check_17(rom, args.rom)
    print("ALL OK" if not failed else f"{failed} problem(s)")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
