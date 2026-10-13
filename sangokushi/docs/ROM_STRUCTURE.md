# ROM_STRUCTURE.md — FC 三國志 ROM 檔案結構

## 檔案基本資訊

| 項目 | 值 |
|------|------|
| 檔名 | `roms/Sangokushi (Japan).zip` 內的 `Sangokushi (Japan).nes`（SHA-1 `93e760cbc61b748d0375e97147dee3193a153768`） |
| 檔案大小 | 262,160 bytes (256 KB + 16 bytes header) |
| 格式 | iNES (.nes) |
| Mapper | 1 (MMC1) |
| PRG ROM | 256 KB = 16 banks × 16 KB |
| CHR ROM | 0 KB (使用 CHR-RAM) |

---

## iNES Header (0x00000 - 0x0000F)

| 偏移 | 大小 | 內容 | 說明 |
|------|------|------|------|
| 0x00000 | 4 | `4E 45 53 1A` | "NES" + 0x1A 魔數 |
| 0x00004 | 1 | `10` | PRG ROM 大小 (16 × 16KB = 256KB) |
| 0x00005 | 1 | `00` | CHR ROM 大小 (0 = CHR-RAM) |
| 0x00006 | 1 | `10` | Flags 6 (Mapper low nibble = 1) |
| 0x00007 | 1 | `00` | Flags 7 |
| 0x00008-0x0000F | 8 | `00...` | 保留 |

---

## PRG ROM Banks 概覽

PRG ROM 偏移計算: `file_offset = bank × 0x4000 + 0x10`

| Bank | 檔案偏移 | CPU 地址 | 已知內容 |
|------|----------|----------|----------|
| 0 | 0x00010 - 0x0400F | $8000-$BFFF | 程式碼、文字資料 |
| 1 | 0x04010 - 0x0800F | $8000-$BFFF | 程式碼 |
| 2 | 0x08010 - 0x0C00F | $8000-$BFFF | 程式碼 |
| 3 | 0x0C010 - 0x1000F | $8000-$BFFF | 程式碼、tile 資料 |
| 4 | 0x10010 - 0x1400F | $8000-$BFFF | Tile 圖形資料 |
| 5 | 0x14010 - 0x1800F | $8000-$BFFF | Tile 圖形資料 |
| 6 | 0x18010 - 0x1C00F | $8000-$BFFF | Tile 圖形資料 |
| 7 | 0x1C010 - 0x2000F | $8000-$BFFF | Tile 圖形資料 |
| 8 | 0x20010 - 0x2400F | $8000-$BFFF | **假名字體 tile** |
| 9 | 0x24010 - 0x2800F | $8000-$BFFF | 資料表 |
| 10 | 0x28010 - 0x2C00F | $8000-$BFFF | 資料 |
| 11 | 0x2C010 - 0x3000F | $8000-$BFFF | Tile 圖形資料 |
| 12 | 0x30010 - 0x3400F | $8000-$BFFF | 資料 |
| 13 | 0x34010 - 0x3800F | $8000-$BFFF | 資料 |
| 14 | 0x38010 - 0x3C00F | $8000-$BFFF | **武將資料表、姓名表** |
| 15 | 0x3C010 - 0x4000F | $C000-$FFFF | 固定 Bank (程式碼、中斷向量) |

---

## 已解析資料區塊

### Bank 14: 武將資料表

| 偏移 | 大小 | 內容 |
|------|------|------|
| 0x38010 - 0x38013 | 4 | 表頭 `4C 00 00 00` |
| 0x38014 - 0x39113 | 4,352 | 武將資料 (256 筆 × 17 bytes) |
| 0x39114 - ... | ? | 城市資料? (待分析) |

**武將記錄結構 (17 bytes):**
```
+0   Age          年齡 (signed byte)
+1   Body         體力 (15-100)
+2   Intelligence 智力 (15-100)
+3   Military     武力 (15-100)
+4   Charisma     魅力 (15-100)
+5   Luck         運氣 (15-100)
+6   Loyalty      忠誠 (12-100)
+7   Status+Navy  身份/水軍 bitfield
+8,9 Troops       兵士數 (little-endian 16-bit)
+10  City         城市 ID (0-55)
+11  Faction      勢力 ID (0-14)
+12-16 Separator  固定 0A 0A 0A 00 00
```

### Bank 14: 武將姓名表

| 偏移 | 大小 | 內容 |
|------|------|------|
| 0x3A310 - 0x3A313 | 4 | 表頭 `4C 00 00 00` |
| 0x3A314 - 0x3B823 | 3,855 | 姓名資料 (257 筆 × 15 bytes) |

**姓名記錄結構 (15 bytes):**
```
+0-7   Kana        假名 (半角片假名, Shift-JIS 0xA6-0xDF)
+8     Kanji1_ID   第一個漢字 tile ID
+9     Kanji1_Page Page 指示器 (0=Page0, 1=Page1)
+10    Kanji2_ID   第二個漢字 tile ID
+11    Kanji2_Page Page 指示器
+12    Kanji3_ID   第三個漢字 tile ID
+13    Kanji3_Page Page 指示器
+14    Portrait    頭像索引 byte (portrait_index = byte - 1)
```

**頭像索引計算:**
```
portrait_index = name_record[+14] - 1
```
範圍: 0-80 (共 81 個頭像)

### Bank 6-7: 標準頭像系統 (P00-P80)

| 偏移 | 大小 | 內容 |
|------|------|------|
| 0x1B0D4 - 0x1BC37 | 2,916 | 排列表 (81 筆 × 36 bytes) |
| 0x1BC38 - 0x1BD7B | 324 | 頭像指標表 (81 筆 × 4 bytes) |

### Bank 7: 大眾臉頭像系統 (編號 65-254)

| 偏移 | 大小 | 內容 |
|------|------|------|
| 0x1C014 - 0x1DE13 | 7,680 | Head 框架 tiles (20 Heads × 24 tiles × 16 bytes) |
| 0x1DE14 - 0x1E1D3 | 960 | 眼睛變體 (20 組 × 3 tiles × 16 bytes) |
| 0x1E1D4 - 0x1E593 | 960 | 鼻子變體 (20 組 × 3 tiles × 16 bytes) |
| 0x1E594 - 0x1ED13 | 1,920 | 嘴巴變體 (20 組 × 6 tiles × 16 bytes) |
| 0x1ED14 - 0x1EFE3 | 720 | Template 排列表 (20 筆 × 36 bytes) |
| 0x1EFE4 - 0x1F389 | 950 | 組件索引表 (190 筆 × 5 bytes [Cat, Head, Eye, Nose, Mouth]，編號 65 起，見 MOB_PORTRAIT_SYSTEM_PSEUDOCODE.md) |

**20 個 Head 位置 (2026-02-27 更新):**

所有 Head 都佔用 24 tiles 的空間 (384 bytes)。部分 Head 使用重複 tile 或全黑 tile 填充。

| Head | ROM 偏移 | Template | Pattern |
|-------|----------|----------|---------|
| H00 | 0x1C014 | T00 | P1 |
| H01 | 0x1C194 | T01 | P1 |
| H02 | 0x1C314 | T02 | P1 |
| H03 | 0x1C494 | T03 | P1 |
| H04 | 0x1C614 | T04 | P1 |
| H05 | 0x1C794 | T05 | P2 |
| H06 | 0x1C914 | T06 | P3 |
| H07 | 0x1CA94 | T07 | P4 |
| H08 | 0x1CC14 | T08 | P5 |
| H09 | 0x1CD94 | T09 | P3 |
| H10 | 0x1CF14 | T10 | P1 |
| H11 | 0x1D094 | T11 | P3 |
| H12 | 0x1D214 | T12 | P6 |
| H13 | 0x1D394 | T13 | P7 |
| H14 | 0x1D514 | T14 | P8 |
| H15 | 0x1D694 | T15 | P1 |
| H16 | 0x1D814 | T16 | P1 |
| H17 | 0x1D994 | T17 | P1 |
| H18 | 0x1DB14 | T18 | P1 |
| H19 | 0x1DC94 | T19 | P1 |

**注意:** 20 個 Head (H00-H19) 與 20 個 Template (T00-T19) 1:1 對應。每個 Head 佔 24 tiles × 16 bytes = 384 bytes。

**頭像指標表結構 (每筆 4 bytes):**
```
+0   Bank        PRG Bank 編號
+1   TileCount   Tile 數量 (32 或 36)
+2   AddrLo      CPU 地址低位
+3   AddrHi      CPU 地址高位
```

**檔案偏移計算:**
```
file_offset = bank × 0x4000 + (addr - 0x8000) + 0x10
```

**排列表結構 (每筆 36 bytes):**
- 6×6 格 tile 排列資訊
- 值範圍: 1-36 (tile 編號) 或 0/$64-$87 (特殊)
- ROM 原始值需轉換: `tile_num = raw_byte - 0x63` (若 `0x64 <= raw_byte <= 0x87`)

**頭像→排列映射規則:**
```
arrangement_index = portrait_index  (1:1 對應)

- 排列表正好 81 個條目，與頭像數量相同
- 36-tile 標準頭像 (32 個): 使用標準排列 STANDARD_LAYOUT
- 其他頭像: 直接用頭像索引查找排列表
```

**36-tile 標準頭像索引:**
```
6, 7, 8, 24, 25, 26, 29, 35, 38, 40, 41, 43, 44, 45, 46, 47,
49, 51, 58, 59, 61, 66, 68, 69, 70, 72, 74, 75, 76, 77, 79, 80
```

### Bank 8: 假名字體

| 偏移 | 大小 | 內容 |
|------|------|------|
| 0x22CA0 - ... | ~1,024+ | 片假名字體 tile (8×8 pixels, 16 bytes/tile) |

**字體特徵:**
- 按五十音順序排列 (ア、イ、ウ、エ、オ...)
- 每個 tile 包含陰影效果
- 約 50+ tiles (清音 + 濁音符號 + 特殊字元)

---

## 待分析區塊

| 偏移 | 推測內容 | 備註 |
|------|----------|------|
| 0x39114 - 0x3A30F | 城市資料? | 在武將表與姓名表之間 |
| 0x0ADA8 附近 | 遊戲文字 | 有大量半角片假名 |

---

## 編碼參考

### 半角片假名 (Shift-JIS)

| 範圍 | 字元 |
|------|------|
| 0xA6-0xAF | 小字 (ｦ ｧ ｨ ｩ ｪ ｫ ｬ ｭ ｮ ｯ) |
| 0xB0 | 長音 (ｰ) |
| 0xB1-0xBF | ア行-サ行 (ｱ-ｿ) |
| 0xC0-0xCF | タ行-ノ (ﾀ-ﾉ) |
| 0xD0-0xDD | ハ行-ン (ﾊ-ﾝ) |
| 0xDE | 濁點 (ﾞ) |
| 0xDF | 半濁點 (ﾟ) |

---

## 版本歷史

- 2024: 初始分析，解析武將資料表與姓名表
- 2025-02: 完成頭像系統分析 (指標表、排列表、映射規則)
- 2026-02: 完成大眾臉頭像系統分析 (19 Heads, 20 Templates, 8 Patterns)
