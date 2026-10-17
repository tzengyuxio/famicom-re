"""Emulator verification for FC 天地を喰らうII: play from power-on and compare the screen / RAM with rom.py.

1. new game -> 洛陽 palace: the starting party's (劉備) ぶりょく / ちりょく / すばやさ in battle-slot RAM equal their records
2. the palace screen (BG only) equals the map render of map 13 (rows / cells from rom.py), at the start and after
   walking down (lines 0-223; the bottom seam row is redrawn by the game while it scrolls)
3. ぶしょう status screen: for every general id, poke the shown id ($6627) and compare the 48x48 portrait and the
   kanji name pixel by pixel
4. equip たんけん on 劉備: the attack the game computes equals the item power
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
        sy, sx = divmod(py, 256)[0] - 1, divmod(px, 256)[0] - 1
        im = big.get((sy, sx))
        return im[px % 256, py % 256] if im else None

    cx, cy = 256 + x * 16, 256 + y * 16          # player cell in the 3x3 render
    sample = [(sx, sy) for sy in range(0, 240, 7) for sx in range(0, 256, 9)]
    best = (-1, 0, 0)
    for oy in range(cy - 160, cy - 64):
        for ox in range(cx - 160, cx - 96):
            hit = sum(at(ox + sx, oy + sy) == shot[sy * 256 + sx] for sx, sy in sample)
            if hit > best[0]:
                best = (hit, ox, oy)
    _, ox, oy = best
    inner = 224 * 256                             # the bottom 16 lines are the seam the game redraws while scrolling
    same = [at(ox + i % 256, oy + i // 256) == shot[i] for i in range(256 * 240)]
    pct, inner_pct = sum(same) * 100 / len(same), sum(same[:inner]) * 100 / inner
    print(f"  map {m} at screen ({ys},{xs}) cell ({y},{x}): offset ({ox - cx},{oy - cy}), "
          f"{inner_pct:.2f}% of lines 0-223 / {pct:.2f}% of the screen equal")
    return inner_pct == 100


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
    open_general_list(n)
    good, bad = check_generals(r, n)
    print(f"  ぶしょう screen: {good}/{R.GENERAL_COUNT} portraits + kanji equal" + (f", differ: {bad}" if bad else ""))
    results["generals"] = not bad
    print("result:", " ".join(f"{k}={'OK' if v else 'NG'}" for k, v in results.items()))
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
