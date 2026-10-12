#!/usr/bin/env python3
"""Export the 58 per-province battle maps of FC 三國志 as PNG (needs Pillow).

Format notes: docs/BATTLE_MAP.md. Map n (province n+1) is 14 columns x 12 rows of
cells; each cell is a 4x4-tile (32x32 px) terrain block, odd columns shifted down
half a cell like a hex grid. Files are named NN_<state>.png (provinces have only
numbers in this game; the state is the 州 they belong to). Deployment-zone bits and
units are not drawn. Check against the game: tools/verify_battle_maps.py.

Usage: .venv/bin/python sangokushi/export_battle_maps.py [--rom ROM] [--out DIR] [--scale N]
"""
import argparse
import os

from PIL import Image
from romfile import DEFAULT_ROM, read_rom

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# PRG offsets (file offset - 0x10)
MAPS = 0x259A4           # bank 9 $99A4: 58 maps x 168 bytes, value = terrain << 3 | zone bits
MAP_COUNT, COLS, ROWS = 58, 14, 12
TILES = 0xF004           # bank 3 $B004: 87 tiles uploaded to PPU $1640 (tile $64-$BA)
FIRST_TILE = 0x64
CELLS = 0xF574           # bank 3 $B574: 16 tile numbers (4x4, row-major) per terrain
TERRAIN_PALETTE = 0x7A5C  # bank 1 $BA5C: sub-palette per terrain (6 bytes)
BG_PALETTE = 0x7C66      # bank 1 $BC66: 16-byte background palette
TERRAINS = 6
PROVINCES = 0x3B201      # bank 14 $B201: 58 x 14 bytes [x, y, ?, number, state, 9 neighbours (0 = none)]
PROVINCE_SIZE = 14
STATE_NAMES = 0x3B530    # bank 14 $B530: 15 x 12 bytes [kana x 8, (kanji tile, page) x 2]
STATE_COUNT = 15
# Page-0 kanji tiles of the state names, read from the ROM glyphs (see docs/BATTLE_MAP.md)
STATE_KANJI = {0x0B: "益", 0x3D: "荊", 0x48: "交", 0x55: "司", 0x63: "州", 0x6F: "徐", 0x82: "青", 0x96: "代",
               0xD7: "幽", 0xDA: "予", 0xDB: "揚", 0xE8: "涼", 0xED: "隷", 0xF3: "冀", 0xF4: "兗", 0xF5: "幷"}

NES_RGB = [
    0x666666, 0x002A88, 0x1412A7, 0x3B00A4, 0x5C007E, 0x6E0040, 0x6C0600, 0x561D00,
    0x333500, 0x0B4800, 0x005200, 0x004F08, 0x00404D, 0x000000, 0x000000, 0x000000,
    0xADADAD, 0x155FD9, 0x4240FF, 0x7527FE, 0xA01ACC, 0xB71E7B, 0xB53120, 0x994E00,
    0x6B6D00, 0x388700, 0x0C9300, 0x008F32, 0x007C8D, 0x000000, 0x000000, 0x000000,
    0xFFFEFF, 0x64B0FF, 0x9290FF, 0xC676FF, 0xF36AFF, 0xFE6ECC, 0xFE8170, 0xEA9E22,
    0xBCBE00, 0x88D800, 0x5CE430, 0x45E082, 0x48CDDE, 0x4F4F4F, 0x000000, 0x000000,
    0xFFFEFF, 0xC0DFFF, 0xD3D2FF, 0xE8C8FF, 0xFBC2FF, 0xFEC4EA, 0xFECCC5, 0xF7D8A5,
    0xE4E594, 0xCFEF96, 0xBDF4AB, 0xB3F3CC, 0xB5EBF2, 0xB8B8B8, 0x000000, 0x000000,
]


def state_names(prg: bytes) -> list[str]:
    out = []
    for i in range(STATE_COUNT):
        o = STATE_NAMES + i * 12 + 8
        assert prg[o + 1] == prg[o + 3] == 0, "state names use page-0 kanji"
        out.append(STATE_KANJI[prg[o]] + STATE_KANJI[prg[o + 2]])
    return out


def province_states(prg: bytes) -> list[int]:
    """State index (into state_names) of provinces 1-58."""
    out = []
    for n in range(MAP_COUNT):
        rec = prg[PROVINCES + n * PROVINCE_SIZE:PROVINCES + (n + 1) * PROVINCE_SIZE]
        assert rec[3] == n + 1
        out.append(rec[4])
    return out


def rgb(c: int) -> tuple[int, int, int]:
    v = NES_RGB[c & 0x3F]
    return v >> 16, (v >> 8) & 0xFF, v & 0xFF


def tile(prg: bytes, n: int) -> list[list[int]]:
    o = TILES + (n - FIRST_TILE) * 16
    return [[(prg[o + y] >> (7 - x) & 1) | (prg[o + 8 + y] >> (7 - x) & 1) << 1 for x in range(8)] for y in range(8)]


def terrain_cells(prg: bytes) -> list[Image.Image]:
    """32x32 RGB image of each terrain type, drawn with its sub-palette."""
    pal = prg[BG_PALETTE:BG_PALETTE + 16]
    out = []
    for t in range(TERRAINS):
        sub = prg[TERRAIN_PALETTE + t]
        colors = [rgb(pal[0])] + [rgb(pal[sub * 4 + i]) for i in (1, 2, 3)]
        img = Image.new("RGB", (32, 32))
        px = img.load()
        for i, n in enumerate(prg[CELLS + t * 16:CELLS + t * 16 + 16]):
            for y, row in enumerate(tile(prg, n)):
                for x, c in enumerate(row):
                    px[i % 4 * 8 + x, i // 4 * 8 + y] = colors[c]
        out.append(img)
    return out


def battle_map(prg: bytes, n: int, cells: list[Image.Image]) -> Image.Image:
    data = prg[MAPS + n * COLS * ROWS:MAPS + (n + 1) * COLS * ROWS]
    img = Image.new("RGB", (COLS * 32, ROWS * 32 + 16), rgb(prg[BG_PALETTE]))
    for r in range(ROWS):
        for c in range(COLS):
            img.paste(cells[data[r * COLS + c] >> 3], (c * 32, r * 32 + (16 if c % 2 else 0)))
    return img


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 58 國的戰爭地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(REPO, "sangokushi", "output", "battle_maps"))
    ap.add_argument("--scale", type=int, default=2)
    args = ap.parse_args()
    prg = read_rom(args.rom)[16:]
    os.makedirs(args.out, exist_ok=True)
    cells = terrain_cells(prg)
    legend = Image.new("RGB", (TERRAINS * 36, 32), (255, 255, 255))
    for t, img in enumerate(cells):
        legend.paste(img, (t * 36, 0))
    legend.resize((legend.width * args.scale, 32 * args.scale), Image.NEAREST).save(
        os.path.join(args.out, "terrain.png"))
    names = state_names(prg)
    for n, state in enumerate(province_states(prg)):
        img = battle_map(prg, n, cells)
        img.resize((img.width * args.scale, img.height * args.scale), Image.NEAREST).save(
            os.path.join(args.out, f"{n + 1:02d}_{names[state]}.png"))
    print(f"已匯出 {MAP_COUNT} 張戰爭地圖 → {args.out}")


if __name__ == "__main__":
    main()
