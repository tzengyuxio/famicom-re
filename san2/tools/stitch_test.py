#!/usr/bin/env python3
"""Can the 41 battle maps be stitched into one map of China along the provinces' hex lattice?

Method of sangokushi/docs/BATTLE_MAP.md §7. Every 13 x 12 map sits in a brick layout given by
rom.Rom.hex_layout (east/west neighbours side by side, the row to the south shifted by half a map).
For each orientation of the maps (as stored, mirrored, flipped, both) and each half-map shift
(6 or 7 hexes) it measures how often the two hexes facing each other across a seam have the same
terrain, and how often a river hex faces a river hex. The best variant is compared with the same
search over randomly shuffled maps and with the rate inside the maps.

The second test is the column layout of export.china_battle_map (the user's idea): the hex side
41 -> 40 -> 31 points straight up, so each province sits in column -(q + r), row -r, and every other
column drops half a map. Vertical seams then join whole map edges, and side seams join with a
half-map (6 row) offset; a row-offset scan shows whether that alignment is a sharp peak.

Usage: .venv/bin/python san2/tools/stitch_test.py [--rom ROM] [--shuffles N]
"""
import argparse
import os
import random
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rom import BATTLE_COLS as W
from rom import BATTLE_ROWS as H
from rom import DEFAULT_ROM, PROVINCE_COUNT, Rom

RIVER = 4
GEO = {"E": 5, "SE": 2, "SW": 1, "W": 0, "NW": 3, "NE": 4}  # adjacency slot of each geographic side


def oriented(m, t):
    if t & 1:
        m = [row[::-1] for row in m]
    return m[::-1] if t & 2 else m


def seams(rom: Rom, maps, t: int, k: int, mirror: bool) -> list[tuple[int, int]]:
    """Facing hex pairs across all seams; mirror swaps east and west (the lattice is 180° turned)."""
    adj = rom.adjacency()
    east, se, sw = ("W", "NW", "NE") if mirror else ("E", "SE", "SW")
    pairs = []
    for i in range(PROVINCE_COUNT):
        a = oriented(maps[i], t)
        for side in (east, se, sw):
            j = adj[i][GEO[side]]
            if j is None:
                continue
            b = oriented(maps[j - 1], t)
            if side == east:
                pairs += [(a[r][W - 1], b[r][0]) for r in range(H)]
            elif side == se:
                pairs += [(a[H - 1][c], b[0][c - k]) for c in range(k, W)]
            else:
                pairs += [(a[H - 1][c], b[0][c + W - k]) for c in range(k)]
    return pairs


def rates(pairs) -> tuple[float, float]:
    same = sum(x == y for x, y in pairs) / len(pairs)
    river = [(x, y) for x, y in pairs if RIVER in (x, y)]
    return same, sum(x == y for x, y in river) / len(river)


def best(rom: Rom, maps):
    return max((rates(seams(rom, maps, t, k, m)), t, k, m) for t in range(4) for k in (6, 7) for m in (False, True))


def column_seams(rom: Rom, maps, s: int = 0) -> tuple[list, list]:
    """Facing hex pairs (vertical, side) in the column layout; s shifts the side seams by s rows."""
    cell = {i - 1: (-(q + r), -r) for i, (q, r) in rom.hex_layout().items()}
    at = {v: k for k, v in cell.items()}
    vert, side = [], []
    for a, (c, row) in cell.items():
        if (c, row + 1) in at:
            vert += list(zip(maps[a][H - 1], maps[at[(c, row + 1)]][0]))
        for dr in (0, 1):
            b = at.get((c + 1, row + dr))
            if b is not None:
                off = (2 * dr - 1) * (H // 2) + s
                side += [(maps[a][k + off][W - 1], maps[b][k][0]) for k in range(H) if 0 <= k + off < H]
    return vert, side


def main() -> None:
    ap = argparse.ArgumentParser(description="戰場地圖六角拼接測試")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--shuffles", type=int, default=60)
    args = ap.parse_args()
    rom = Rom(args.rom)
    pos = rom.hex_layout()
    adj = rom.adjacency()
    edges = sum(v is not None for row in adj for v in row) // 2
    print(f"[lattice] {PROVINCE_COUNT} provinces, {edges} edges: every side lands on a distinct hex "
          f"({len(set(pos.values()))} cells)")
    maps = [rom.battle_terrain(i) for i in range(PROVINCE_COUNT)]
    (same, river), t, k, m = best(rom, maps)
    n = len(seams(rom, maps, t, k, m))
    print(f"[seams] best variant (orientation {t}, shift {k}, mirror {m}): same terrain {same:.3f}, "
          f"river to river {river:.3f} ({n} facing pairs)")
    rnd, base = random.Random(1), []
    for _ in range(args.shuffles):
        perm = maps[:]
        rnd.shuffle(perm)
        base.append(best(rom, perm)[0])
    print(f"[shuffled x{args.shuffles}] same terrain median {statistics.median(b[0] for b in base):.3f} "
          f"max {max(b[0] for b in base):.3f}; river median {statistics.median(b[1] for b in base):.3f} "
          f"max {max(b[1] for b in base):.3f}")
    inner = [(row[c], row[c + 1]) for mp in maps for row in mp for c in range(W - 1)]
    print("[inside maps] same terrain {:.3f}, river to river {:.3f}".format(*rates(inner)))
    curve = []
    for s in range(-4, 5):
        pairs = [(maps[i][r][W - 1], maps[adj[i][GEO["E"]] - 1][r + s][0]) for i in range(PROVINCE_COUNT)
                 if adj[i][GEO["E"]] is not None for r in range(H) if 0 <= r + s < H]
        curve.append(f"{s:+d}:{rates(pairs)[0]:.3f}")
    print("[east-west seams, row offset] " + " ".join(curve))

    vert, side = column_seams(rom, maps)
    print("[column layout] vertical seams same {:.3f}, river {:.3f}".format(*rates(vert))
          + "; side seams same {:.3f}, river {:.3f}".format(*rates(side)))
    base = []
    for _ in range(args.shuffles):
        perm = maps[:]
        rnd.shuffle(perm)
        v, sd = column_seams(rom, perm)
        base.append(rates(v) + rates(sd))
    print(f"[column layout shuffled x{args.shuffles}] max vertical same {max(b[0] for b in base):.3f} "
          f"river {max(b[1] for b in base):.3f}; max side same {max(b[2] for b in base):.3f} "
          f"river {max(b[3] for b in base):.3f}")
    inner = [(mp[y][x], mp[y + 1][x]) for mp in maps for y in range(H - 1) for x in range(W)]
    print("[inside maps, vertical] same {:.3f}, river {:.3f}".format(*rates(inner)))
    curve = [f"{s:+d}:{rates(column_seams(rom, maps, s)[1])[1]:.3f}" for s in range(-4, 5)]
    print("[column layout side seams, river by row offset] " + " ".join(curve))


if __name__ == "__main__":
    main()
