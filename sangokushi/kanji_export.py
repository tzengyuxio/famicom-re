#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FC 三國志 漢字字型匯出工具

根據逆向工程分析結果，從 ROM 匯出 16×16 漢字圖形。

映射公式:
  Page 0: PRG_ROM_offset = 0x20004 + tile_id × 32
  Page 1: PRG_ROM_offset = 0x22004 + tile_id × 32
  File_offset = PRG_ROM_offset + 0x10 (iNES header)

每個漢字 = 4 個 8×8 tiles = 32 bytes (只有 Plane 0)
4 tiles 排列: [0][1] 在 offset+0, offset+8
              [2][3] 在 offset+16, offset+24
"""

import os
import sys

try:
    from PIL import Image
except ImportError:
    print("需要安裝 Pillow: pip3 install Pillow")
    sys.exit(1)

# ─── 常數 ────────────────────────────────────────────────────

# 漢字 tile 基址 (PRG ROM)
# 每個漢字 = 32 bytes (4 tiles × 8 bytes，只有 Plane 0)
# 公式: PRG_offset = base + tile_id × 32
KANJI_BASE_PRG_PAGE0 = 0x20004
KANJI_BASE_PRG_PAGE1 = 0x22004  # Page 1 在 Page 0 後 8KB
KANJI_BASE_FILE_PAGE0 = KANJI_BASE_PRG_PAGE0 + 0x10  # 加上 iNES header
KANJI_BASE_FILE_PAGE1 = KANJI_BASE_PRG_PAGE1 + 0x10

# 每個漢字的大小 (bytes)
KANJI_SIZE = 32  # 4 tiles × 8 bytes
TILE_SIZE = 8    # 只有 Plane 0

# 姓名表位置
NAME_TABLE_ADDR = 0x3A314
NAME_RECORD_SIZE = 15

# NES 調色板 (灰階)
PALETTE = [
    (255, 255, 255),  # 0: 白
    (170, 170, 170),  # 1: 淺灰
    (85, 85, 85),     # 2: 深灰
    (0, 0, 0),        # 3: 黑
]


def decode_tile_8x8(tile_data, monochrome=False):
    """
    解碼 NES 8×8 tile (16 bytes) 為像素陣列

    NES tile 格式: 2 bitplanes, 每個 8 bytes
    - Plane 0: bytes 0-7
    - Plane 1: bytes 8-15
    - 每個像素 = bit from plane0 + (bit from plane1 << 1)

    Args:
        tile_data: tile 資料 (8 或 16 bytes)
        monochrome: True 時只使用 Plane 0 (黑白模式，用於漢字)
    """
    if len(tile_data) < 8:
        return [[0] * 8 for _ in range(8)]

    pixels = []
    for y in range(8):
        row = []
        plane0 = tile_data[y]
        # 黑白模式: Plane 1 = Plane 0 (遊戲中漢字的實際處理方式)
        if monochrome or len(tile_data) < 16:
            plane1 = plane0
        else:
            plane1 = tile_data[y + 8]
        for x in range(7, -1, -1):
            bit0 = (plane0 >> x) & 1
            bit1 = (plane1 >> x) & 1
            pixel = bit0 + (bit1 << 1)
            row.append(pixel)
        pixels.append(row)
    return pixels


def decode_kanji_16x16(rom, tile_id, page=0):
    """
    解碼 16×16 漢字 (4 個 8×8 tiles)

    排列方式: [0][1]
              [2][3]

    ROM 儲存格式: 每個 tile 只有 8 bytes (Plane 0)
    遊戲載入時會將 Plane 0 複製到 Plane 1 (黑白顯示)

    Args:
        rom: ROM 資料
        tile_id: 漢字 tile ID (0x01-0xFF for page 0, 0x01-0x42 for page 1)
        page: 0 或 1

    Returns:
        16×16 像素陣列
    """
    # 根據 Page 選擇基址
    if page == 1:
        base = KANJI_BASE_FILE_PAGE1
    else:
        base = KANJI_BASE_FILE_PAGE0

    # 計算 ROM 偏移: offset = base + tile_id × 32
    offset = base + tile_id * KANJI_SIZE

    # 讀取 4 個 tiles (每個 8 bytes，共 32 bytes)
    # 排列: [0][1] 在 offset+0, offset+8
    #       [2][3] 在 offset+16, offset+24
    tiles = []
    for i in range(4):
        tile_offset = offset + i * TILE_SIZE
        if tile_offset + TILE_SIZE > len(rom):
            tiles.append([[0] * 8 for _ in range(8)])
        else:
            tile_data = rom[tile_offset:tile_offset + TILE_SIZE]
            tiles.append(decode_tile_8x8(tile_data, monochrome=True))

    # 組合成 16×16
    pixels = []
    for y in range(8):
        pixels.append(tiles[0][y] + tiles[1][y])
    for y in range(8):
        pixels.append(tiles[2][y] + tiles[3][y])

    return pixels


def pixels_to_image(pixels, scale=1, palette=None):
    """將像素陣列轉換為 PIL Image"""
    if palette is None:
        palette = PALETTE

    h = len(pixels)
    w = len(pixels[0]) if h > 0 else 0

    img = Image.new('RGB', (w * scale, h * scale))

    for y, row in enumerate(pixels):
        for x, p in enumerate(row):
            color = palette[p]
            for dy in range(scale):
                for dx in range(scale):
                    img.putpixel((x * scale + dx, y * scale + dy), color)
    return img


def load_name_table(rom):
    """
    載入姓名表，取得所有使用的 tile_id

    Returns:
        list of (index, tile_id, page, kanji_position)
    """
    tiles = []

    for i in range(257):
        offset = NAME_TABLE_ADDR + i * NAME_RECORD_SIZE
        if offset + NAME_RECORD_SIZE > len(rom):
            break

        record = rom[offset:offset + NAME_RECORD_SIZE]

        # 漢字 tile IDs 在 +8, +10, +12
        # Page 指示器在 +9, +11, +13
        for pos, (tile_off, page_off) in enumerate([(8, 9), (10, 11), (12, 13)]):
            tile_id = record[tile_off]
            page = record[page_off]
            if tile_id != 0:
                tiles.append((i, tile_id, page, pos))

    return tiles


def get_unique_tiles(name_table_tiles):
    """取得不重複的 (tile_id, page) 組合"""
    unique = set()
    for idx, tile_id, page, pos in name_table_tiles:
        unique.add((tile_id, page))
    return sorted(unique)


def export_kanji_atlas(rom, output_path, scale=2):
    """
    匯出漢字字型表 (atlas)

    排列: 16 列 × 16 行，tile_id 0x00-0xFF
    """
    COLS = 16
    ROWS = 16
    CHAR_SIZE = 16 * scale
    MARGIN = 1

    img_width = COLS * (CHAR_SIZE + MARGIN) + MARGIN
    img_height = ROWS * (CHAR_SIZE + MARGIN) + MARGIN

    atlas = Image.new('RGB', (img_width, img_height), (240, 240, 240))

    for tile_id in range(256):
        row = tile_id // COLS
        col = tile_id % COLS

        pixels = decode_kanji_16x16(rom, tile_id, page=0)
        char_img = pixels_to_image(pixels, scale=scale)

        x = MARGIN + col * (CHAR_SIZE + MARGIN)
        y = MARGIN + row * (CHAR_SIZE + MARGIN)
        atlas.paste(char_img, (x, y))

    atlas.save(output_path)
    print(f"已儲存: {output_path}")
    return atlas


def export_individual_kanji(rom, output_dir, scale=4):
    """匯出所有使用到的漢字為個別圖片"""
    os.makedirs(output_dir, exist_ok=True)

    # 載入姓名表取得使用的 tiles
    name_tiles = load_name_table(rom)
    unique_tiles = get_unique_tiles(name_tiles)

    print(f"找到 {len(unique_tiles)} 個不同的漢字 tile")

    page0_count = 0
    page1_count = 0

    for tile_id, page in unique_tiles:
        pixels = decode_kanji_16x16(rom, tile_id, page=page)
        char_img = pixels_to_image(pixels, scale=scale)

        filename = f"kanji_p{page}_{tile_id:02X}.png"
        filepath = os.path.join(output_dir, filename)
        char_img.save(filepath)

        if page == 0:
            page0_count += 1
        else:
            page1_count += 1

    print(f"已匯出 Page 0: {page0_count} 個, Page 1: {page1_count} 個")
    print(f"儲存於: {output_dir}/")


def export_sample_kanji(rom, output_dir=".", scale=8):
    """匯出幾個已知漢字作為驗證"""
    os.makedirs(output_dir, exist_ok=True)

    # 已知的 tile_id 對照
    known = [
        (0x8E, "曹"),
        (0x8D, "操"),
        (0x91, "孫"),
        (0x3E, "堅"),
        (0xE3, "劉"),
        (0xBD, "備"),
        (0x9F, "張"),
        (0x24, "關"),
        (0x05, "羽"),
    ]

    print("匯出已知漢字樣本:")
    for tile_id, name in known:
        pixels = decode_kanji_16x16(rom, tile_id, page=0)
        char_img = pixels_to_image(pixels, scale=scale)

        filename = f"kanji_{tile_id:02X}_{name}.png"
        filepath = os.path.join(output_dir, filename)
        char_img.save(filepath)
        print(f"  {filename}")


def main():
    rom_path = sys.argv[1] if len(sys.argv) > 1 else "Sangokushi (Japan).nes"

    if not os.path.exists(rom_path):
        print(f"錯誤: 找不到 ROM 檔案 '{rom_path}'")
        print(f"用法: python {sys.argv[0]} <rom_file.nes>")
        sys.exit(1)

    with open(rom_path, "rb") as f:
        rom = f.read()

    if rom[:4] != b"NES\x1a":
        print("錯誤: 非有效的 iNES ROM 檔案")
        sys.exit(1)

    print(f"載入 ROM: {rom_path}")
    print(f"檔案大小: {len(rom)} bytes")
    print()

    # 建立輸出目錄
    output_dir = "kanji_output"
    os.makedirs(output_dir, exist_ok=True)

    # 1. 匯出已知漢字樣本 (驗證用)
    print("=" * 50)
    print("步驟 1: 匯出已知漢字樣本")
    export_sample_kanji(rom, output_dir, scale=8)
    print()

    # 2. 匯出完整字型表
    print("=" * 50)
    print("步驟 2: 匯出漢字字型表 (Page 0)")
    atlas_path = os.path.join(output_dir, "kanji_atlas_page0.png")
    export_kanji_atlas(rom, atlas_path, scale=2)
    print()

    # 3. 匯出所有個別漢字
    print("=" * 50)
    print("步驟 3: 匯出所有使用的漢字")
    individual_dir = os.path.join(output_dir, "individual")
    export_individual_kanji(rom, individual_dir, scale=4)
    print()

    print("=" * 50)
    print("完成!")
    print(f"所有檔案儲存於: {output_dir}/")


if __name__ == "__main__":
    main()
