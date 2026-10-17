"""Emulator verification of the 天地を喰らう decoder (needs py65; about 2 minutes).

Plays a new game from power-on until the party can walk, then checks rom.py against the game's own code:
  0. screen: the room on screen against rom.py's map render, pixel by pixel
  1. map: the game's cell lookup ($D83E) on random cells of the 50x32-block grid, all 3 tilesets
  2. party: ぶりょく / ちりょく / すばやさ / 兵士数 in WRAM against the general records
  3. encounters: the game's random-formation routine (bank 14 $B324) per zone 1-8
  4. portraits and kanji names: every general put in the 大将 slot, status screen compared pixel by pixel

  .venv/bin/python tenchi/verify.py [--rom ROM] [--quick]
"""
import argparse
import collections
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
from emu import ROM, Nes
from rom import BLOCK_H, GENERIC, GRID_COLS, GRID_ROWS, PORTRAIT_COLOR, PORTRAIT_FIXED, GameRom

# power-on -> name entry (empty name) -> 会話 speed -> intro dialogue -> the room of 楼桑村
BOOT = ([("wait", 240), ("START", 120), ("START", 120), ("A", 120), ("A", 120), ("A", 180), ("START", 120)]
        + [("A", 120)] * 4 + [("A", 180)] + [("A", 90)] * 24)
LEADER = 0x60AA  # party slot shown as 大将 on the status screen


def boot(path: str) -> Nes:
    n = Nes(path)
    n.play(BOOT)
    return n


def check_map(n: Nes, r: GameRom, cells: int) -> bool:
    rnd = random.Random(1)
    bad = 0
    for ts in range(3):
        n[0x48] = ts
        for _ in range(cells):
            row, col = rnd.randrange(GRID_ROWS * BLOCK_H), rnd.randrange(GRID_COLS * 16)
            n[0x1C], n[0x1D], n[0x1E], n[0x1F] = row % BLOCK_H, row // BLOCK_H, col & 15, col >> 4
            n.call(0xD83E)  # metatile id -> Y (1 = chest, checked against the opened flags)
            bad += n.cpu.y != r.block_metatiles(row // BLOCK_H, col >> 4, ts)[row % BLOCK_H][col & 15]
    print(f"map: {3 * cells} cells via $D83E, {bad} mismatches")
    return bad == 0


def check_screen(n: Nes, r: GameRom) -> bool:
    """Background on screen (sprites off) against rom.py's render of the 16x15 metatiles around the party."""
    from rom import nes_rgb
    row, col = n[0x61] * BLOCK_H + n[0x60], n[0x63] * 16 + n[0x62]
    top, left = row - 7, col - 8
    rows, cols = range(top // BLOCK_H, (top + 14) // BLOCK_H + 1), range(left // 16, (left + 15) // 16 + 1)
    x0, y0 = (left - cols.start * 16) * 16, (top - rows.start * BLOCK_H) * 16
    mine = list(r.render_blocks(rows, cols, r.area_type(n[0x47])).crop((x0, y0, x0 + 256, y0 + 240)).getdata())
    mask, n.mask = n.mask, n.mask & ~0x10
    game = [nes_rgb(c) for c in n.screen()]
    n.mask = mask
    bad = sum(a != b for a, b in zip(mine, game))
    print(f"screen: area {n[0x47]:02X} at ({row}, {col}), {bad} of {256 * 240} background pixels differ from rom.py")
    return bad == 0


def check_party(n: Nes, r: GameRom) -> bool:
    ok = True
    for s in range(3):
        g = r.general(n[0x60A8 + s])
        got = (n[0x619C + s], n[0x61A8 + s], n[0x61B4 + s], n[0x6160 + 4 * s] | n[0x6161 + 4 * s] << 8)
        want = (g["buryoku"], g["chiryoku"], g["speed"], r.soldiers(g["ally_rank"], n[0x6073] or 1))
        ok &= got == want
        print(f"party slot {s}: {g['name']} WRAM {got} ROM {want}")
    return ok


def check_encounters(n: Nes, r: GameRom, rolls: int) -> bool:
    pools, ok = r.encounter_pools(), True
    for z in range(1, 9):
        n[0x6026] = z
        seen, fixed = collections.Counter(), collections.Counter()
        for _ in range(rolls):
            n[0x75] = 0xFF  # random battle
            n.call(0xC482, 14)
            n.call(0xB324)
            if n[0x75] != 0xFF:  # $B40E switched to a fixed battle (呂布 / 龐統 roaming), formation not built
                fixed[n[0x75]] += 1
                continue
            seen.update(n[0x300 + i] for i in range(5))
        named = {i for i in seen if i >= 8}
        generic = {i for i in seen if 0 < i < 8}
        good = named <= set(pools[z]) and generic <= set(GENERIC)
        ok &= good
        print(f"zone {z}: {rolls} rolls, generic {sorted(generic)}, named {len(named)}/{len(pools[z])} of the pool,"
              f" {'ok' if good else 'NOT IN POOL'}" + (f", fixed battle {dict(fixed)}" if fixed else ""))
    return ok


def find(screen: list[bytes], img: list[bytes]) -> list[tuple[int, int]]:
    hits = []
    for y in range(len(screen) - len(img) + 1):
        x = screen[y].find(img[0])
        while x >= 0:
            if all(screen[y + k][x:x + len(img[k])] == img[k] for k in range(1, len(img))):
                hits.append((x, y))
            x = screen[y].find(img[0], x + 1)
    return hits


def check_portraits(n: Nes, r: GameRom, ids) -> bool:
    bad = []
    for i in ids:
        g = r.general(i)
        pal = PORTRAIT_FIXED + (PORTRAIT_COLOR[g["color"]],)
        tiles = r.portrait_tiles(g["portrait"])
        por = [bytes(pal[tiles[(y // 8) * 6 + x // 8][(y % 8) * 8 + x % 8]] for x in range(48)) for y in range(48)]
        kan = [bytes(r.kanji_glyph(*g["kanji"][x // 16])[y * 16 + x % 16] for x in range(16 * len(g["kanji"])))
               for y in range(16)]
        n[LEADER] = i
        for attempt in range(4):  # the menu sometimes needs another press or a few more frames to settle
            n.play([("SELECT", 50)] if attempt % 2 == 0 else [("wait", 30)])
            px = n.screen()
            rows = [px[y * 256:(y + 1) * 256] for y in range(240)]
            mask = [bytes(1 if c != 0x0F else 0 for c in row) for row in rows]
            p, k = find(rows, por), find(mask, kan)
            if p and k:
                break
        else:
            bad.append((i, g["name"], bool(p), bool(k)))
        n.play([("B", 60)])
    print(f"portraits + kanji names: {len(ids) - len(bad)}/{len(ids)} pixel-exact on the status screen")
    for b in bad:
        print("  mismatch", b)
    return not bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=ROM)
    ap.add_argument("--quick", action="store_true", help="fewer samples, 20 portraits")
    a = ap.parse_args()
    r, n = GameRom(a.rom), boot(a.rom)
    st = n.snapshot()
    ok = check_screen(n, r)
    ok &= check_party(n, r)
    ok &= check_map(n, r, 100 if a.quick else 1000)
    ok &= check_encounters(n, r, 30 if a.quick else 150)
    n.restore(st)
    ids = [g["id"] for g in r.generals() if g["color"]]  # colour 0 = no portrait (palette all black)
    ok &= check_portraits(n, r, ids[::10] if a.quick else ids)
    print("ALL OK" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
