"""Emulator verification for FC 天地を喰らうII: play from power-on and compare the screen / RAM with rom.py.

1. new game -> 洛陽 palace: the starting party's (劉備) ぶりょく / ちりょく / すばやさ in battle-slot RAM equal their records
2. the palace screen (BG only) equals the map render of map 13 (rows / cells from rom.py), at the start and after
   walking down
3. ぶしょう status screen: for every general id, poke the shown id ($6627) and compare the 48x48 portrait and the
   kanji name pixel by pixel
4. equip たんけん on 劉備: the attack the game computes equals the item power
5. teleport (a patched warp record, step type forced to "warp") to the middle cell of every world screen the camera
   can show and to every door / warp destination on the other maps; the BG equals the stitched 15-row screens (palette indexes in the frame's palette)
   (--quick: every 10th target)
"""
import argparse
import os
import sys
import time

import export
import rom as R

sys.path.insert(0, os.path.join(R.HERE, "tools"))
from play import new_game, open_general_list

STAT_RAM = {"ぶりょく": (0x6675, 3), "ちりょく": (0x6681, 2), "すばやさ": (0x668D, 4)}  # battle slot arrays
PARTY = 0x6621                  # general id per battle slot (party in slots 4-6, empty = 0)
SHOWN_GENERAL = 0x6627          # general shown by the ぶしょう status screen
PORTRAIT_XY, KANJI_XY = (16, 32), (16, 96)
STEP_TYPE, STEP_CHECK, WARP = 0x86, 0xF5E1, 9   # $86 at $F5E1: 8 = door ($BD45), 9 = warp ($BE5D)
CAMERA = (112, 128)                             # party cell -> top-left of the view, in pixels


def rgb_screen(n) -> list[tuple[int, int, int]]:
    return [R.nes_rgb(c) for c in n.screen(False)[2]]


def check_stats(r: R.Rom, n) -> bool:
    ok = True
    for slot in range(4, 7):
        g = n[PARTY + slot]
        if not g:
            continue
        rec = r.general_record(g)
        got = {k: n[a + slot] for k, (a, _) in STAT_RAM.items()}
        want = {k: rec[i] for k, (_, i) in STAT_RAM.items()}
        ok &= got == want
        print(f"  slot {slot} {r.general_kanji(g)}: RAM {got} ROM {want} {'OK' if got == want else 'NG'}")
    return ok


def check_map(r: R.Rom, n, painter: export.MapPainter) -> bool:
    m, (y, ys, x, xs) = n[0x47], (n[0x60], n[0x61], n[0x62], n[0x63])
    n.run(2)
    shot = rgb_screen(n)
    big = {}
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            row, col = ys + dy, xs + dx
            if 0 <= row < R.GRID_H and 0 <= col < R.GRID_W:
                im = painter.screen(m, row, col)
                big[(dy, dx)] = im.load()

    def at(px: int, py: int):
        sy, sx = py // export.SCREEN_H - 1, px // 256 - 1
        im = big.get((sy, sx))
        return im[px % 256, py % export.SCREEN_H] if im else None

    cx, cy = 256 + x * 16, export.SCREEN_H + y * 16  # player cell in the 3x3 render
    sample = [(sx, sy) for sy in range(0, 240, 7) for sx in range(0, 256, 9)]
    best = (-1, 0, 0)
    for oy in range(cy - 160, cy - 64):
        for ox in range(cx - 160, cx - 96):
            hit = sum(at(ox + sx, oy + sy) == shot[sy * 256 + sx] for sx, sy in sample)
            if hit > best[0]:
                best = (hit, ox, oy)
    _, ox, oy = best
    same = sum(at(ox + i % 256, oy + i // 256) == shot[i] for i in range(256 * 240))
    print(f"  map {m} at screen ({ys},{xs}) cell ({y},{x}): offset ({ox - cx},{oy - cy}), "
          f"{same * 100 / (256 * 240):.2f}% of the screen equal")
    return same == 256 * 240


def screen_indexes(r: R.Rom, m: int, row: int, col: int) -> list[list[int]]:
    t, chr_set = r.tileset(m, row), r.bg_tiles(r.map_info(m)[1])
    px = [[0] * 256 for _ in range(export.SCREEN_H)]
    for y, line in enumerate(r.screen_cells(row, col, t)[:R.SCREEN_ROWS]):
        for x, c in enumerate(line):
            for cy, cells in enumerate(r.cell_pixels(t, c, chr_set)):
                px[y * 16 + cy][x * 16:x * 16 + 16] = cells
    return px


def view_indexes(r: R.Rom, cache: dict, m: int, y: int, ys: int, x: int, xs: int) -> list:
    """Palette indexes of the 256x240 window the camera shows around the party cell (None off the grid). Indexes,
    not colours: several maps cycle palette entries (water, torches), so the frame's colours vary."""
    top, left = ys * export.SCREEN_H + y * 16 - CAMERA[0], xs * 256 + x * 16 - CAMERA[1]
    out = [None] * (256 * 240)
    for py in range(240):
        row, ry = divmod(top + py, export.SCREEN_H)
        if not 0 <= row < R.GRID_H:
            continue
        for px in range(256):
            col, rx = divmod(left + px, 256)
            if 0 <= col < R.GRID_W:
                if (m, row, col) not in cache:
                    cache[(m, row, col)] = screen_indexes(r, m, row, col)
                out[py * 256 + px] = cache[(m, row, col)][ry][rx]
    return out


def force_warp(n) -> None:
    n[STEP_TYPE] = WARP


def check_teleports(r: R.Rom, n, quick: bool) -> tuple[int, list, int]:
    links = r.links()
    world = {(cy // R.SCREEN_ROWS, cx // 16) for cy, cx in export.world_view(r, links)}
    targets = [(0, (7, ys, 8, xs)) for ys, xs in sorted(world)]
    targets += sorted({(k["map"], k["to"]) for k in links if k["map"]})
    if quick:
        targets = targets[::10]
    n.prg = bytearray(n.prg)
    warp = r.off(R.DOOR_BANK, R.WARP_TABLE)
    record = bytes(n.prg[warp:warp + 9])
    start, (y0, ys0, x0, xs0) = n.snapshot(), (n[0x60], n[0x61], n[0x62], n[0x63])
    bad, cycled, cache = [], 0, {}
    for m, (y, ys, x, xs) in targets:
        n.restore(start)
        n.prg[warp:warp + 9] = bytes([y0 + 1, ys0, x0, xs0, y, ys, x, xs, m])  # the cell below the start
        n.breakpoints = {STEP_CHECK: force_warp}
        n.run(16, ["DOWN"])
        for _ in range(60):
            n.run(1)
            if n[0x47] == m and n[0x61] == ys:
                break
        n.breakpoints = {}
        n.run(90)
        state = (n[0x47], n[0x60], n[0x61], n[0x62], n[0x63])
        pal = [R.nes_rgb(c) for c in n.pal]
        cycled += pal[:16] != [R.nes_rgb(c) for c in r.map_palette(m)][:16]
        want = view_indexes(r, cache, m, y, ys, x, xs)
        shot = rgb_screen(n)
        if state != (m, y, ys, x, xs) or any(w is not None and pal[w] != s for w, s in zip(want, shot)):
            bad.append((m, (y, ys, x, xs)))
    n.prg[warp:warp + 9] = record
    n.restore(start)
    return len(targets) - len(bad), bad, cycled


def check_generals(r: R.Rom, n) -> tuple[int, list[int]]:
    pal = [R.nes_rgb(c) for c in R.STATUS_PALETTE]
    base = n.snapshot()
    bad = []
    for g in range(R.GENERAL_COUNT):
        n.restore(base)
        n[SHOWN_GENERAL] = g
        n.press("A", 80)
        shot = rgb_screen(n)
        px, py = PORTRAIT_XY
        ok = all(shot[(py + y) * 256 + px + x] == pal[c] for y, row in enumerate(r.portrait(g)) for x, c in enumerate(row))
        bg = shot[0]
        kx, ky = KANJI_XY
        for j, (s, i) in enumerate(r.general_kanji_codes(g)):
            glyph = r.kanji_glyph(s, i)
            ok &= all((shot[(ky + y) * 256 + kx + 16 * j + x] != bg) == bool(v)
                      for y, line in enumerate(glyph) for x, v in enumerate(line))
        if not ok:
            bad.append(g)
    n.restore(base)
    return R.GENERAL_COUNT - len(bad), bad


def check_equip(r: R.Rom, n) -> bool:
    for button, wait in (("A", 60), ("DOWN", 30), ("DOWN", 30), ("DOWN", 30), ("DOWN", 30), ("A", 80), ("A", 60),
                         ("A", 60), ("DOWN", 30), ("DOWN", 30), ("A", 80)):
        n.press(button, wait)
    slot = next(s for s in range(7) if n[PARTY + s] == 1)
    got, want = n[0x66B1 + slot], r.item_power(8)
    print(f"  劉備 + {r.item(8)[1]}: こうげき RAM {got}, ROM power {want} {'OK' if got == want else 'NG'}")
    return got == want


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=R.DEFAULT_ROM)
    ap.add_argument("--quick", action="store_true", help="teleport to every 10th target only")
    a = ap.parse_args()
    r = R.Rom(a.rom)
    painter = export.MapPainter(r)
    t = time.time()
    n = new_game(a.rom)
    print(f"new game: map {n[0x47]} after {time.time() - t:.0f} s")
    results = {"stats": check_stats(r, n)}
    start = n.snapshot()
    ok = check_map(r, n, painter)
    for _ in range(4):                          # a few steps down, before 関羽 stops the party
        n.run(16, ["DOWN"])
    n.run(60)
    results["map"] = ok & check_map(r, n, painter)
    n.restore(start)
    results["equip"] = check_equip(r, n)
    n.restore(start)
    t = time.time()
    good, bad, cycled = check_teleports(r, n, a.quick)
    print(f"  teleports: {good}/{good + len(bad)} views equal in the frame's palette, {cycled} with cycled colours "
          f"({time.time() - t:.0f} s)"
          + (f", differ: {bad[:20]}" if bad else ""))
    results["teleports"] = not bad
    n.restore(start)
    open_general_list(n)
    good, bad = check_generals(r, n)
    print(f"  ぶしょう screen: {good}/{R.GENERAL_COUNT} portraits + kanji equal" + (f", differ: {bad}" if bad else ""))
    results["generals"] = not bad
    print("result:", " ".join(f"{k}={'OK' if v else 'NG'}" for k, v in results.items()))
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
