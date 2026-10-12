#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大眾臉頭像匯出工具

從 ROM 讀取 174 筆大眾臉頭像 (P081-P254) 的組件索引，組合並匯出為 PNG。

組件索引表: ROM 0x1F034, 每筆 5 bytes [Cat, Head, Eye, Nose, Mouth]
索引公式: addr = 0x1F034 + (portrait_index - 81) * 5
全域索引: global = cat * 5 + local
"""

import csv
import os
import sys

try:
    from PIL import Image
except ImportError:
    print("需要安裝 Pillow: pip3 install Pillow")
    sys.exit(1)

# ─── 常數 ────────────────────────────────────────────────────

PALETTE = [
    (0, 0, 0),          # 0: 黑
    (247, 216, 165),    # 1: 淺膚色
    (234, 158, 34),     # 2: 深膚色
    (255, 255, 255),    # 3: 白
]

# 組件索引表
COMP_TABLE_OFFSET = 0x1F034
PORTRAIT_START = 81
PORTRAIT_END = 254
PORTRAIT_COUNT = PORTRAIT_END - PORTRAIT_START + 1  # 174

# 20 個 Head 框架的 ROM 位址
HEADS = [
    0x1C014, 0x1C194, 0x1C314, 0x1C494, 0x1C614,  # H00-H04
    0x1C794, 0x1C914, 0x1CA94, 0x1CC14, 0x1CD94,  # H05-H09
    0x1CF14, 0x1D094, 0x1D214, 0x1D394, 0x1D514,  # H10-H14
    0x1D694, 0x1D814, 0x1D994, 0x1DB14, 0x1DC94,  # H15-H19
]
HEAD_TILE_COUNT = 24

# 變體資料位址
EYES_START = 0x1DE14    # 20 variants × 3 tiles × 16 bytes
NOSES_START = 0x1E1D4   # 20 variants × 3 tiles × 16 bytes
MOUTHS_START = 0x1E594  # 20 variants × 6 tiles × 16 bytes

# 排列模板
TEMPLATE_START = 0x1ED14  # 20 templates × 36 bytes

# 嘴巴 tile 排列: ROM 順序 [0,1,2,3,4,5] → 格子位置 (col, row)
MOUTH_LAYOUT = [(0, 0), (1, 0), (0, 1), (1, 1), (2, 0), (2, 1)]

# 武將資料 CSV
CHARACTERS_CSV = "output/Sangokushi (Japan)_characters_v2.csv"


# ─── 工具函數 ────────────────────────────────────────────────

def decode_tile(data):
    """解碼 NES 8×8 tile (16 bytes → 8×8 pixels)"""
    pixels = []
    for y in range(8):
        plane0 = data[y]
        plane1 = data[y + 8]
        row = []
        for x in range(7, -1, -1):
            bit0 = (plane0 >> x) & 1
            bit1 = (plane1 >> x) & 1
            row.append(bit0 + (bit1 << 1))
        pixels.append(row)
    return pixels


def read_template(rom, template_idx):
    """讀取 36-byte 排列模板，回傳 6×6 grid (None = 變體位置)"""
    offset = TEMPLATE_START + template_idx * 36
    data = rom[offset:offset + 36]
    grid = []
    for row in range(6):
        row_data = []
        for col in range(6):
            val = data[row * 6 + col]
            if val == 0:
                row_data.append(None)
            else:
                row_data.append(val - 0x64)
        grid.append(row_data)
    return grid


def load_portrait_names():
    """從 CSV 載入 portrait_index → 武將名稱"""
    names = {}
    if not os.path.exists(CHARACTERS_CSV):
        return names
    with open(CHARACTERS_CSV, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            pi = int(row['Portrait'])
            name = row.get('[EXT]Name', '')
            if pi >= PORTRAIT_START and name and pi not in names:
                names[pi] = name
    return names


def read_component_table(rom):
    """讀取組件索引表"""
    records = []
    for i in range(PORTRAIT_COUNT):
        offset = COMP_TABLE_OFFSET + i * 5
        records.append({
            'portrait_index': PORTRAIT_START + i,
            'cat': rom[offset],
            'head': rom[offset + 1],
            'eye': rom[offset + 2],
            'nose': rom[offset + 3],
            'mouth': rom[offset + 4],
        })
    return records


# ─── 頭像渲染 ────────────────────────────────────────────────

def render_portrait(rom, cat, head_local, eye_local, nose_local, mouth_local):
    """從組件索引組合頭像，回傳 48×48 PIL Image"""
    # 轉換為全域索引
    head_g = cat * 5 + head_local
    eye_g = cat * 5 + eye_local
    nose_g = cat * 5 + nose_local
    mouth_g = cat * 5 + mouth_local

    # 讀取排列模板
    template = read_template(rom, head_g)

    # 讀取框架 tiles
    head_base = HEADS[head_g]
    head_tiles = []
    for i in range(HEAD_TILE_COUNT):
        offset = head_base + i * 16
        head_tiles.append(decode_tile(rom[offset:offset + 16]))

    # 讀取變體 tiles
    eye_tiles = []
    for i in range(3):
        offset = EYES_START + (eye_g * 3 + i) * 16
        eye_tiles.append(decode_tile(rom[offset:offset + 16]))

    nose_tiles = []
    for i in range(3):
        offset = NOSES_START + (nose_g * 3 + i) * 16
        nose_tiles.append(decode_tile(rom[offset:offset + 16]))

    mouth_tiles = []
    for i in range(6):
        offset = MOUTHS_START + (mouth_g * 6 + i) * 16
        mouth_tiles.append(decode_tile(rom[offset:offset + 16]))

    # 組合 48×48 圖像
    img = Image.new('RGB', (48, 48), PALETTE[0])

    for row in range(6):
        for col in range(6):
            tile_idx = template[row][col]

            if tile_idx is not None:
                # 框架 tile
                if tile_idx < HEAD_TILE_COUNT:
                    pixels = head_tiles[tile_idx]
                else:
                    continue
            else:
                # 變體位置 (cols 1-3 of rows 2-5)
                vc = col - 1  # variant column (0-2)
                if row == 2:
                    pixels = eye_tiles[vc]
                elif row == 3:
                    pixels = nose_tiles[vc]
                elif row == 4:
                    # 嘴巴 R1: tile indices 0, 1, 4
                    mouth_idx = [0, 1, 4][vc]
                    pixels = mouth_tiles[mouth_idx]
                elif row == 5:
                    # 嘴巴 R2: tile indices 2, 3, 5
                    mouth_idx = [2, 3, 5][vc]
                    pixels = mouth_tiles[mouth_idx]
                else:
                    continue

            # 繪製 tile
            for y in range(8):
                for x in range(8):
                    img.putpixel((col * 8 + x, row * 8 + y), PALETTE[pixels[y][x]])

    return img


# ─── 主程式 ────────────────────────────────────────────────

def main():
    rom_path = sys.argv[1] if len(sys.argv) > 1 else "Sangokushi (Japan).nes"

    if not os.path.exists(rom_path):
        print(f"錯誤: 找不到 ROM 檔案 '{rom_path}'")
        sys.exit(1)

    with open(rom_path, 'rb') as f:
        rom = f.read()

    if rom[:4] != b"NES\x1a":
        print("錯誤: 非有效的 iNES ROM 檔案")
        sys.exit(1)

    # 讀取武將名稱
    names = load_portrait_names()

    # 讀取組件索引表
    records = read_component_table(rom)

    # 匯出設定
    scale = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    output_dir = "output/mob_portraits" if scale > 1 else "output/mob_portraits_48"
    os.makedirs(output_dir, exist_ok=True)

    print(f"匯出 {PORTRAIT_COUNT} 個大眾臉頭像到 {output_dir}/")
    print(f"  縮放: {scale}x ({48*scale}×{48*scale} pixels)")
    print()

    for r in records:
        pi = r['portrait_index']
        name = names.get(pi, '')

        img = render_portrait(rom, r['cat'], r['head'], r['eye'], r['nose'], r['mouth'])

        if scale > 1:
            img = img.resize((48 * scale, 48 * scale), Image.NEAREST)

        # 檔名: P081_周泰.png
        if name:
            filename = f"P{pi:03d}_{name}.png"
        else:
            filename = f"P{pi:03d}.png"

        img.save(os.path.join(output_dir, filename))

    print(f"完成! 已匯出 {PORTRAIT_COUNT} 個頭像")

    # 匯出總覽圖
    atlas_path = os.path.join(output_dir, "_atlas.png")
    cols = 15
    rows = (PORTRAIT_COUNT + cols - 1) // cols
    size = 48 * scale
    margin = 2

    atlas = Image.new('RGB', (
        cols * (size + margin) + margin,
        rows * (size + margin) + margin
    ), (128, 128, 128))

    for i, r in enumerate(records):
        pi = r['portrait_index']
        img = render_portrait(rom, r['cat'], r['head'], r['eye'], r['nose'], r['mouth'])
        if scale > 1:
            img = img.resize((size, size), Image.NEAREST)

        row = i // cols
        col = i % cols
        x = margin + col * (size + margin)
        y = margin + row * (size + margin)
        atlas.paste(img, (x, y))

    atlas.save(atlas_path)
    print(f"已匯出總覽圖: {atlas_path}")


if __name__ == "__main__":
    main()
