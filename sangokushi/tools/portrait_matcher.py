#!/usr/bin/env python3
"""
Portrait Matcher - 從遊戲截圖自動識別頭像 layout

使用方法:
    python portrait_matcher.py <screenshot.png> <group> [--portrait-id P0XX]

參數:
    screenshot.png  - 遊戲中的頭像截圖 (48×48 或放大版本)
    group          - 使用的 Group: A, B, 或 C
                     A = base 0x1D694
                     B = base 0x1C194
                     C = base 0x1C914
    --portrait-id  - 可選，標註頭像 ID

範例:
    python portrait_matcher.py zhou_tai_screenshot.png A --portrait-id P081
    python portrait_matcher.py zhang_zhao.png C --portrait-id P092
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
    'H': 0x102A4,  # 韓玄 - 不同 ROM 區域
}

ROM_PATH = os.path.join(os.path.dirname(__file__), '..', '..', 'Sangokushi (Japan).nes')


def load_rom_tiles(base_addr, num_tiles=800):
    """從 ROM 載入 tiles"""
    tiles = []
    with open(ROM_PATH, 'rb') as f:
        f.seek(base_addr)
        rom_data = f.read(num_tiles * 16)

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


def extract_tiles_from_screenshot(img_path):
    """從截圖提取 36 個 tiles"""
    img = Image.open(img_path).convert('RGB')
    width, height = img.size

    # 計算縮放比例 (原始應為 48×48)
    if width != height:
        print(f"警告: 圖片不是正方形 ({width}×{height})")

    # 計算 tile 大小
    tile_size = width // 6
    print(f"圖片大小: {width}×{height}, tile 大小: {tile_size}×{tile_size}")

    # 縮放到標準大小 (48×48)
    if width != 48:
        img = img.resize((48, 48), Image.NEAREST)
        tile_size = 8

    # 提取 36 個 tiles
    tiles = []
    for row in range(6):
        row_tiles = []
        for col in range(6):
            y = row * tile_size
            x = col * tile_size

            # 提取 8×8 tile
            tile_pixels = []
            for py in range(8):
                row_pixels = []
                for px in range(8):
                    pixel = img.getpixel((x + px, y + py))
                    row_pixels.append(pixel[:3])  # RGB only
                tile_pixels.append(row_pixels)

            row_tiles.append(tile_pixels)
        tiles.append(row_tiles)

    return tiles


def find_closest_palette_color(pixel):
    """找到最接近的調色盤顏色"""
    min_dist = float('inf')
    best_color = PALETTE[0]
    for pal_color in PALETTE:
        dist = sum((pixel[i] - pal_color[i])**2 for i in range(3))
        if dist < min_dist:
            min_dist = dist
            best_color = pal_color
    return best_color


def compare_tiles(tile1, tile2):
    """比較兩個 tiles，返回相似度 (0-1, 1=完全相同)"""
    total_diff = 0

    for row in range(8):
        for col in range(8):
            # 量化截圖像素到調色盤
            pixel1 = find_closest_palette_color(tile1[row][col])
            pixel2 = tile2[row][col]

            # 計算差異
            diff = sum(abs(pixel1[i] - pixel2[i]) for i in range(3))
            total_diff += diff

    max_diff = 8 * 8 * 3 * 255
    return 1.0 - (total_diff / max_diff)


def find_best_match(screenshot_tile, rom_tiles, threshold=0.95):
    """找到最匹配的 ROM tile"""
    best_match = -1
    best_score = 0

    for tile_num, rom_tile in enumerate(rom_tiles):
        score = compare_tiles(screenshot_tile, rom_tile)
        if score > best_score:
            best_score = score
            best_match = tile_num

        # 完美匹配就提早結束
        if score >= 0.999:
            break

    return best_match, best_score


def match_portrait(screenshot_path, group, portrait_id=None):
    """主函數: 匹配頭像並輸出 layout"""
    print(f"=== Portrait Matcher ===")
    print(f"截圖: {screenshot_path}")
    print(f"Group: {group} (base 0x{GROUP_BASES[group]:X})")
    if portrait_id:
        print(f"Portrait ID: {portrait_id}")
    print()

    # 載入 ROM tiles
    print("載入 ROM tiles...")
    base_addr = GROUP_BASES[group]
    rom_tiles = load_rom_tiles(base_addr, 800)
    print(f"已載入 {len(rom_tiles)} 個 tiles")
    print()

    # 從截圖提取 tiles
    print("分析截圖...")
    screenshot_tiles = extract_tiles_from_screenshot(screenshot_path)
    print()

    # 匹配每個 tile
    print("匹配 tiles...")
    layout = []
    low_scores = []
    for row in range(6):
        row_layout = []
        for col in range(6):
            tile = screenshot_tiles[row][col]
            match, score = find_best_match(tile, rom_tiles)
            row_layout.append(match)

            if score < 0.95:
                low_scores.append((row, col, match, score))

        layout.append(row_layout)

    if low_scores:
        print("  警告: 以下位置匹配度較低:")
        for row, col, match, score in low_scores:
            print(f"    [{row}][{col}] = {match}, 匹配度 {score:.1%}")
    else:
        print("  所有 tiles 匹配度 > 95%")

    print()
    print("=" * 50)
    print("=== 結果 ===")
    print("=" * 50)
    print()

    # 輸出 layout
    if portrait_id:
        print(f"# {portrait_id} Layout (Group {group}, base 0x{GROUP_BASES[group]:X})")
    else:
        print(f"# Layout (Group {group}, base 0x{GROUP_BASES[group]:X})")
    print()
    print("layout = [")
    for row in layout:
        print(f"    {row},")
    print("]")
    print()

    # 分析變體 tiles
    # 所有 Group 共用變體 tiles，但基底不同
    # Group A: eye_base=120, face_base=180, mouth_base=240
    # 其他 Group 的 offset = (Group A base - 該 Group base) / 16
    GROUP_OFFSETS = {
        'A': 0,      # 0x1D694
        'B': 336,    # 0x1C194, diff = +336 tiles
        'C': 216,    # 0x1C914, diff = +216 tiles
        'D': -72,    # 0x1DB14, diff = -72 tiles
        'E': 48,     # 0x1D394, diff = +48 tiles
        'F': -48,    # 0x1D994, diff = -48 tiles
        'G': -96,    # 0x1DC94, diff = -96 tiles
        'H': 3391,   # 0x102A4, diff = +3391 tiles (不同區域)
    }
    GROUP_OFFSET = GROUP_OFFSETS.get(group, 0)
    EYE_BASE = 120 + GROUP_OFFSET
    FACE_BASE = 180 + GROUP_OFFSET
    MOUTH_BASE = 240 + GROUP_OFFSET

    print("=== 變體分析 ===")
    print()

    # 眼睛 (Row 2, cols 1-3)
    eye_tiles = [layout[2][1], layout[2][2], layout[2][3]]
    print(f"眼睛 (Row 2, C1-C3): {eye_tiles}")
    if eye_tiles[0] >= EYE_BASE:
        eye_idx = (eye_tiles[0] - EYE_BASE) // 3
        print(f"  → eye_idx = {eye_idx}")

    # 臉部 (Row 3, cols 1-3)
    face_tiles = [layout[3][1], layout[3][2], layout[3][3]]
    print(f"臉部 (Row 3, C1-C3): {face_tiles}")
    if face_tiles[0] >= FACE_BASE:
        face_idx = (face_tiles[0] - FACE_BASE) // 3
        print(f"  → face_idx = {face_idx}")

    # 嘴巴 (Row 4-5, cols 1-3)
    mouth_r1 = [layout[4][1], layout[4][2], layout[4][3]]
    mouth_r2 = [layout[5][1], layout[5][2], layout[5][3]]
    print(f"嘴巴 R1 (Row 4, C1-C3): {mouth_r1}")
    print(f"嘴巴 R2 (Row 5, C1-C3): {mouth_r2}")
    if mouth_r1[0] >= MOUTH_BASE:
        mouth_idx = (mouth_r1[0] - MOUTH_BASE) // 6
        print(f"  → mouth_idx = {mouth_idx}")

    print()
    print("=== 索引摘要 ===")
    if portrait_id:
        print(f"{portrait_id}: ", end="")

    eye_idx = (eye_tiles[0] - EYE_BASE) // 3 if eye_tiles[0] >= EYE_BASE else "?"
    face_idx = (face_tiles[0] - FACE_BASE) // 3 if face_tiles[0] >= FACE_BASE else "?"
    mouth_idx = (mouth_r1[0] - MOUTH_BASE) // 6 if mouth_r1[0] >= MOUTH_BASE else "?"
    print(f"eye_idx={eye_idx}, face_idx={face_idx}, mouth_idx={mouth_idx}")

    return layout


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    screenshot_path = sys.argv[1]
    group = sys.argv[2].upper()

    if group not in GROUP_BASES:
        print(f"錯誤: Group 必須是 A 或 B, 不是 '{group}'")
        sys.exit(1)

    portrait_id = None
    if '--portrait-id' in sys.argv:
        idx = sys.argv.index('--portrait-id')
        if idx + 1 < len(sys.argv):
            portrait_id = sys.argv[idx + 1]

    if not os.path.exists(screenshot_path):
        print(f"錯誤: 找不到檔案 '{screenshot_path}'")
        sys.exit(1)

    match_portrait(screenshot_path, group, portrait_id)


if __name__ == '__main__':
    main()
