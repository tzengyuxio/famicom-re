#!/usr/bin/env python3
"""Check the map decoder (rom.py) against what the game's own code draws.

Boots the game in the py65 harness (tools/nes_emu.py) and starts a new game, then:

1. screen: the world map as first shown, and every map 1-20 entered through the game's own entry code
   (bank 0 $88A4, map number in X: the path a class-3 world cell takes). The visible part of the
   nametables (tiles and attribute sub-palettes, scroll applied) must equal rom.map_cells /
   rom.map_palettes at some position of that map. Attributes of the first / last visible column are
   skipped when that column shares its attribute byte with a column the game has already replaced
   (the nametable is a 16-cell ring buffer).
2. columns: for every map (0-23), screen and tile column, the game's column builder (bank 1 $80BF)
   fills its nametable buffer $0700 (30 tiles) and the attribute builder (bank 3 $8000) its buffer
   $0310 (8 bytes); both must equal the decoder.

Usage: .venv/bin/python shenghuo/verify_maps.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from nes_emu import Nes
from rom import DEFAULT_ROM, MAP_COUNT, SCREEN_H, SCREEN_W, Rom

VIEW_ROWS = 10  # cells above the status window


def new_game(rom_path: str) -> Nes:
    """Title -> 重新玩 -> first frame on the world map."""
    n = Nes(rom_path)
    n.run(480)
    n.press("START", 60)
    n.run(60)
    for wait in (60, 120, 120):
        n.press("A", wait)
    n.press("DOWN", 30, 6)
    n.press("START", 90, 6)
    n.run(540)
    return n


def call(n: Nes, addr: int, bank: int, x: int = 0) -> None:
    """Run a game subroutine in `bank` and resume the interrupted code afterwards."""
    c = n.cpu
    saved = (c.pc, c.a, c.x, c.y, c.sp, c.p, n.prg_bank)
    n.prg_bank = bank
    n.call(addr, 0, x, 0)
    c.pc, c.a, c.x, c.y, c.sp, c.p, n.prg_bank = saved


def view(n: Nes) -> list[list[tuple]]:
    """(tiles, sub-palette) of each visible cell, read through the scroll of scanline 0."""
    x0, y0 = n.line_scroll()[0]
    out = []
    for cy in range(VIEW_ROWS):
        row = []
        for cx in range(SCREEN_W):
            px, py = (x0 + cx * 16) % 256, (y0 + cy * 16) % 480
            base = 0x2000 if py < 240 else 0x2800  # horizontal mirroring: $2000 above $2800
            ty, tx = (py % 240) // 8, px // 8
            tiles = tuple(n.vram_read(base + (ty + j) * 32 + tx + i) for j in (0, 1) for i in (0, 1))
            a = n.vram_read(base + 0x3C0 + (ty // 4) * 8 + tx // 4)
            row.append((tiles, (a >> (((ty & 2) << 1) | (tx & 2))) & 3))
        out.append(row)
    return out


def same(e: tuple, s: tuple, edge: bool) -> bool:
    return e[0] == s[0] and (edge or e[1] == s[1])


def locate(rom: Rom, m: int, seen: list[list[tuple]], odd: bool) -> tuple[int, int, int]:
    """Best (matching cells, x, y) of the visible window inside map m."""
    cells, pals = rom.map_cells(m), rom.map_palettes(m)
    expect = [[(tuple(rom.metatile(v)), p) for v, p in zip(cr, pr)] for cr, pr in zip(cells, pals)]
    edge = [odd and i in (0, SCREEN_W - 1) for i in range(SCREEN_W)]
    best = (-1, 0, 0)
    for y in range(len(cells) - VIEW_ROWS + 1):
        for x in range(len(cells[0]) - SCREEN_W + 1):
            hit = sum(same(expect[y + j][x + i], seen[j][i], edge[i])
                      for j in range(VIEW_ROWS) for i in range(SCREEN_W))
            if hit > best[0]:
                best = (hit, x, y)
                if hit == VIEW_ROWS * SCREEN_W:
                    return best
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description="以遊戲本身的程式驗證聖火列傳地圖解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    n = new_game(args.rom)
    start = n.snapshot()
    total = VIEW_ROWS * SCREEN_W
    ok = True

    def check(label: str, m: int) -> None:
        nonlocal ok
        hit, x, y = locate(rom, m, view(n), (n.line_scroll()[0][0] // 16) % 2 == 1)
        good = hit == total
        ok &= good
        print(f"[{label}] map {m:2d} at cell ({x:3d},{y:3d}): {hit}/{total} cells {'OK' if good else 'MISMATCH'}")

    check("start", 0)
    for m in range(1, 21):
        n.restore(start)
        call(n, 0x88A4, 0, x=m)
        n.run(90)
        assert n.ram[0x9D] == m
        check("enter", m)

    n.restore(start)
    bad = cols = 0
    for m in range(MAP_COUNT):
        cells, pals = rom.map_cells(m), rom.map_palettes(m)
        w, h = rom.map_size(m)
        for s in range(w * h):
            sx, sy = divmod(s, h)
            for tc in range(32):
                n.ram[0x9D], n.ram[0x9E], n.ram[0xA4], n.ram[0x56] = m, 0x80 if m else 0, s, s
                n.ram[0xA7], n.ram[0xA8], n.ram[0x45] = tc, 0, 0
                call(n, 0x80BF, 1)
                want = [rom.metatile(cells[sy * SCREEN_H + ty // 2][sx * SCREEN_W + tc // 2])[(ty & 1) * 2 + (tc & 1)]
                        for ty in range(2 * SCREEN_H)]
                good = list(n.ram[0x700:0x700 + 2 * SCREEN_H]) == want
                if tc % 4 == 0:
                    call(n, 0x8000, 3)
                    for k in range(8):
                        a = n.ram[0x310 + k]
                        for q in range(4):
                            r, c = 2 * k + (q >> 1), tc // 2 + (q & 1)
                            if r < SCREEN_H:
                                good &= (a >> ((q >> 1) * 4 + (q & 1) * 2)) & 3 == pals[sy * SCREEN_H + r][sx * SCREEN_W + c]
                cols += 1
                bad += not good
    ok &= bad == 0
    print(f"[columns] {cols - bad}/{cols} tile columns (+ attribute columns) built by the game match")
    print("ALL OK" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
