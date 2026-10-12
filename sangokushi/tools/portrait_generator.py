#!/usr/bin/env python3
"""
Portrait Generator - 從 Group 和變體索引產生頭像

使用方法:
    python portrait_generator.py <group> <eye_idx> <face_idx> <mouth_idx> [options]

參數:
    group       - Group 字母: A, B, C, D, E
    eye_idx     - 眼睛索引 (0-19)
    face_idx    - 臉部索引 (0-19)
    mouth_idx   - 嘴巴索引 (0-19)

選項:
    --framework N   - 框架類型 (預設 0)
                      Group A: 0=標準(0-23), 1=72-95
                      Group C: 0=標準(0-23), 1=48-67
    --output FILE   - 輸出檔案 (預設 generated_portrait.png)
    --scale N       - 放大倍率 (預設 8)

範例:
    # P081 周泰 (Group A, eye=17, face=18, mouth=16)
    python portrait_generator.py A 17 18 16 --output zhou_tai.png

    # P182 糜芳 (Group A, framework 1, eye=15, face=15, mouth=15)
    python portrait_generator.py A 15 15 15 --framework 1 --output mi_fang.png

    # P204 韓玄 (Group C, framework 1, eye=5, face=5, mouth=5)
    python portrait_generator.py C 5 5 5 --framework 1 --output han_xuan.png
"""

import sys
import os
from PIL import Image

# 調色盤
PALETTE = [
    (0, 0, 0),          # 0: 黑
    (247, 216, 165),    # 1: 淺膚色
    (234, 158, 34),     # 2: 深膚色
    (255, 255, 255),    # 3: 白
]

# Group 基底位址
GROUP_BASES = {
    'A': 0x1D694,
    'B': 0x1C194,
    'C': 0x1C914,
    'D': 0x1DB14,
    'E': 0x1D394,
    'F': 0x1D994,
    'G': 0x1DC94,
}

# Group 相對於 Group A 的 tile 偏移量
# offset = (GROUP_A_BASE - GROUP_X_BASE) / 16
GROUP_OFFSETS = {
    'A': 0,       # 0x1D694
    'B': 336,     # 0x1C194, (0x1D694 - 0x1C194) / 16 = 0x1500 / 16 = 336
    'C': 216,     # 0x1C914, (0x1D694 - 0x1C914) / 16 = 0x0D80 / 16 = 216
    'D': -72,     # 0x1DB14, (0x1D694 - 0x1DB14) / 16 = -0x0480 / 16 = -72
    'E': 48,      # 0x1D394, (0x1D694 - 0x1D394) / 16 = 0x0300 / 16 = 48
    'F': -48,     # 0x1D994
    'G': -96,     # 0x1DC94
}

# 框架定義
# 每個框架是 6x6 的 tile 編號陣列，變體位置 (C1-C3 of R2-R5) 用 None 標記
FRAMEWORKS = {
    # Group A/B/D 標準框架 (tiles 0-23)
    'standard': [
        [  0,   1,   4,   5,   8,   9],
        [  2,   3,   6,   7,  10,  11],
        [ 12, None, None, None,  14,  15],
        [ 13, None, None, None,  16,  17],
        [ 18, None, None, None,  20,  21],
        [ 19, None, None, None,  22,  23],
    ],
    # Group A 框架 2 (tiles 72-95, 糜芳)
    'A_72': [
        [ 72,  73,  76,  77,  80,  81],
        [ 74,  75,  78,  79,  82,  83],
        [ 84, None, None, None,  86,  87],
        [ 85, None, None, None,  88,  89],
        [ 90, None, None, None,  92,  93],
        [ 91, None, None, None,  94,  95],
    ],
    # Group C 標準框架 (tiles 0-23, 但 R3-R5 邊緣不同)
    'C_standard': [
        [  0,   1,   4,   5,   8,   9],
        [  2,   3,   6,   7,  10,  11],
        [ 12, None, None, None,  14,  15],
        [ 13, None, None, None,  16,  13],  # C5=13
        [ 13, None, None, None,  18,  13],  # C0=13, C5=13
        [ 17, None, None, None,  19,  20],  # C0=17
    ],
    # Group C 框架 2 (tiles 48-67, 韓玄/鞏志)
    'C_48': [
        [ 48,  49,  51,  52,  55,  56],
        [ 48,  50,  53,  54,  57,  58],
        [ 48, None, None, None,  59,  60],
        [ 48, None, None, None,  61,  62],
        [ 48, None, None, None,  64,  65],
        [ 63, None, None, None,  66,  67],
    ],
    # Group E 框架 (特殊邊緣)
    'E_standard': [
        [  0,   1,   4,   5,   8,   9],
        [  2,   3,   6,   7,  10,  11],
        [ 12, None, None, None,  14,  15],
        [ 13, None, None, None,  16,  17],
        [ 13, None, None, None,  19,  13],  # C0=13, C4=19, C5=13
        [ 18, None, None, None,  20,  21],  # C0=18
    ],
}

# Group 到框架的映射
GROUP_FRAMEWORKS = {
    'A': ['standard', 'A_72'],
    'B': ['standard'],
    'C': ['C_standard', 'C_48'],
    'D': ['standard'],
    'E': ['E_standard'],
    'F': ['standard'],
    'G': ['standard'],
}

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from romfile import read_rom


def load_rom_tiles(base_addr, num_tiles=800):
    """從 ROM 載入 tiles"""
    tiles = []
    rom_data = read_rom()[base_addr:base_addr + num_tiles * 16]

    for tile_num in range(num_tiles):
        offset = tile_num * 16
        data = rom_data[offset:offset+16]
        if len(data) < 16:
            break

        bp0 = data[0:8]
        bp1 = data[8:16]

        # 轉換為 8×8 像素陣列
        pixels = []
        for row in range(8):
            row_pixels = []
            for col in range(8):
                bit = 7 - col
                b0 = (bp0[row] >> bit) & 1
                b1 = (bp1[row] >> bit) & 1
                color_idx = b1 * 2 + b0
                row_pixels.append(PALETTE[color_idx])
            pixels.append(row_pixels)

        tiles.append(pixels)

    return tiles


def generate_portrait(group, eye_idx, face_idx, mouth_idx, framework_idx=0, scale=8):
    """產生頭像"""
    # 取得框架
    framework_list = GROUP_FRAMEWORKS.get(group, ['standard'])
    if framework_idx >= len(framework_list):
        framework_idx = 0
    framework_name = framework_list[framework_idx]
    framework = FRAMEWORKS[framework_name]

    # 載入 ROM tiles
    base_addr = GROUP_BASES[group]
    rom_tiles = load_rom_tiles(base_addr, 800)

    # 計算變體 tiles (加上 Group 偏移量)
    # 變體公式相對於 Group A，需加上偏移量轉換到當前 Group
    offset = GROUP_OFFSETS.get(group, 0)
    eye_base = 120 + eye_idx * 3 + offset
    face_base = 180 + face_idx * 3 + offset
    mouth_base = 240 + mouth_idx * 6 + offset

    # 建立完整 layout
    layout = []
    for row in range(6):
        row_layout = []
        for col in range(6):
            tile = framework[row][col]
            if tile is not None:
                row_layout.append(tile)
            else:
                # 變體位置
                if row == 2:  # 眼睛
                    row_layout.append(eye_base + (col - 1))
                elif row == 3:  # 臉部
                    row_layout.append(face_base + (col - 1))
                elif row == 4:  # 嘴巴 R1
                    # 排列: +0, +1, +4
                    offsets = [0, 1, 4]
                    row_layout.append(mouth_base + offsets[col - 1])
                elif row == 5:  # 嘴巴 R2
                    # 排列: +2, +3, +5
                    offsets = [2, 3, 5]
                    row_layout.append(mouth_base + offsets[col - 1])
        layout.append(row_layout)

    # 渲染頭像
    portrait = Image.new('RGB', (48 * scale, 48 * scale), (0, 0, 0))

    for row in range(6):
        for col in range(6):
            tile_num = layout[row][col]
            if tile_num < len(rom_tiles):
                tile_pixels = rom_tiles[tile_num]
                for py in range(8):
                    for px in range(8):
                        color = tile_pixels[py][px]
                        x = (col * 8 + px) * scale
                        y = (row * 8 + py) * scale
                        for sy in range(scale):
                            for sx in range(scale):
                                portrait.putpixel((x + sx, y + sy), color)

    return portrait, layout


def main():
    if len(sys.argv) < 5:
        print(__doc__)
        sys.exit(1)

    group = sys.argv[1].upper()
    eye_idx = int(sys.argv[2])
    face_idx = int(sys.argv[3])
    mouth_idx = int(sys.argv[4])

    # 解析選項
    framework_idx = 0
    output_path = 'generated_portrait.png'
    scale = 8

    i = 5
    while i < len(sys.argv):
        if sys.argv[i] == '--framework' and i + 1 < len(sys.argv):
            framework_idx = int(sys.argv[i + 1])
            i += 2
        elif sys.argv[i] == '--output' and i + 1 < len(sys.argv):
            output_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--scale' and i + 1 < len(sys.argv):
            scale = int(sys.argv[i + 1])
            i += 2
        else:
            i += 1

    if group not in GROUP_BASES:
        print(f"錯誤: Group 必須是 {', '.join(GROUP_BASES.keys())}")
        sys.exit(1)

    print(f"=== Portrait Generator ===")
    print(f"Group: {group} (base 0x{GROUP_BASES[group]:X})")
    print(f"eye_idx: {eye_idx}, face_idx: {face_idx}, mouth_idx: {mouth_idx}")
    print(f"Framework: {framework_idx} ({GROUP_FRAMEWORKS[group][framework_idx]})")
    print()

    portrait, layout = generate_portrait(group, eye_idx, face_idx, mouth_idx, framework_idx, scale)

    print("Layout:")
    for row in layout:
        print(f"  {row}")
    print()

    portrait.save(output_path)
    print(f"已儲存: {output_path}")


if __name__ == '__main__':
    main()
