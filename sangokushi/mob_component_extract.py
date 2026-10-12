#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
大眾臉頭像組件索引表匯出工具

從 ROM 讀取 174 筆大眾臉頭像 (P081-P254) 的組件索引資料。

組件索引表結構:
  位置: ROM 0x1F034
  索引: portrait_index - 81
  每筆 5 bytes: [Cat, Head, Eye, Nose, Mouth]
  公式: addr = 0x1F034 + (portrait_index - 81) * 5
"""

import csv
import os
import sys

# ─── 常數 ────────────────────────────────────────────────────

# 組件索引表
COMP_TABLE_OFFSET = 0x1F034  # ROM 檔案偏移 (含 iNES header)
COMP_RECORD_SIZE = 5
COMP_NAMES = ["cat", "head", "eye", "nose", "mouth"]

# 大眾臉頭像範圍
PORTRAIT_START = 81
PORTRAIT_END = 254   # inclusive
PORTRAIT_COUNT = PORTRAIT_END - PORTRAIT_START + 1  # 174

# 武將姓名表 (用於標注武將名稱)
NAME_TABLE = 0x3A314
NAME_RECORD_SIZE = 15
CHARACTER_COUNT = 256


def load_rom(path):
    with open(path, 'rb') as f:
        return f.read()


def read_character_names(rom):
    """讀取武將姓名 (2 bytes 漢字編碼 × 最多 4 字)"""
    # 簡化版：回傳 char_index → portrait_index 映射
    char_to_portrait = {}
    for ci in range(CHARACTER_COUNT):
        offset = NAME_TABLE + ci * NAME_RECORD_SIZE + 14
        if offset < len(rom):
            portrait_idx = rom[offset] - 1
            char_to_portrait[ci] = portrait_idx
    return char_to_portrait


def read_component_table(rom):
    """讀取組件索引表，回傳 list of dict"""
    records = []
    for i in range(PORTRAIT_COUNT):
        portrait_idx = PORTRAIT_START + i
        offset = COMP_TABLE_OFFSET + i * COMP_RECORD_SIZE
        data = rom[offset:offset + COMP_RECORD_SIZE]

        record = {
            "portrait_index": portrait_idx,
            "rom_offset": f"0x{offset:05X}",
        }
        for j, name in enumerate(COMP_NAMES):
            record[name] = data[j]

        records.append(record)

    return records


def build_portrait_to_chars(rom):
    """建立 portrait_index → [char_indices] 映射"""
    char_to_portrait = read_character_names(rom)
    portrait_to_chars = {}
    for ci, pi in char_to_portrait.items():
        if pi not in portrait_to_chars:
            portrait_to_chars[pi] = []
        portrait_to_chars[pi].append(ci)
    return portrait_to_chars


def export_csv(records, output_path):
    """匯出為 CSV"""
    fieldnames = ["portrait_index", "rom_offset"] + COMP_NAMES
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            writer.writerow(r)


def print_summary(records):
    """印出統計摘要"""
    # 各組件的值分佈
    for name in COMP_NAMES:
        values = [r[name] for r in records]
        unique = sorted(set(values))
        counts = {v: values.count(v) for v in unique}
        print(f"  {name:5s}: 值域 {min(values)}-{max(values)}, "
              f"分佈 {dict(sorted(counts.items()))}")


def main():
    rom_path = sys.argv[1] if len(sys.argv) > 1 else "Sangokushi (Japan).nes"

    if not os.path.exists(rom_path):
        print(f"錯誤: 找不到 ROM 檔案 '{rom_path}'")
        sys.exit(1)

    rom = load_rom(rom_path)
    if rom[:4] != b"NES\x1a":
        print("錯誤: 非有效的 iNES ROM 檔案")
        sys.exit(1)

    print(f"載入 ROM: {rom_path}")
    print()

    # 讀取組件索引表
    records = read_component_table(rom)

    # 印出所有記錄
    print(f"大眾臉組件索引表: {len(records)} 筆 (P{PORTRAIT_START:03d}-P{PORTRAIT_END:03d})")
    print(f"ROM 位置: 0x{COMP_TABLE_OFFSET:05X} - 0x{COMP_TABLE_OFFSET + PORTRAIT_COUNT * COMP_RECORD_SIZE - 1:05X}")
    print()

    print(f"{'P_ID':>5s}  {'Offset':>9s}  {'Cat':>3s}  {'Head':>4s}  {'Eye':>3s}  {'Nose':>4s}  {'Mouth':>5s}")
    print(f"{'----':>5s}  {'---------':>9s}  {'---':>3s}  {'----':>4s}  {'---':>3s}  {'----':>4s}  {'-----':>5s}")
    for r in records:
        print(f"P{r['portrait_index']:03d}  {r['rom_offset']:>9s}  {r['cat']:>3d}  {r['head']:>4d}  {r['eye']:>3d}  {r['nose']:>4d}  {r['mouth']:>5d}")

    print()
    print("組件值分佈:")
    print_summary(records)

    # 匯出 CSV
    output_dir = "output"
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "mob_component_index.csv")
    export_csv(records, csv_path)
    print()
    print(f"已匯出: {csv_path}")


if __name__ == "__main__":
    main()
