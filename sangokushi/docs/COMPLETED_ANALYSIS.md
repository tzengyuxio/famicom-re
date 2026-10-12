# 已完成分析 — FC 三國志 ROM 逆向工程

本文件收錄已完成且不需進一步探究的分析內容。

---

## 武將資料表

### 位置
- 所在 Bank: 14 (檔案偏移 0x38010–0x3C00F)
- 表頭: 0x38010–0x38013 = `4C 00 00 00`
- 資料起始: 0x38014
- 記錄數: 256 筆
- 資料結束: 0x39113

### 記錄結構 (17 bytes/筆)

```
Offset  Size  欄位             說明
+0      1     Age (signed)     年齡, signed byte. 正=遊戲開始時年齡, 負=尚未出生
+1      1     Body             體力 (15–100), 推測為壽命/健康度
+2      1     Intelligence     智力 (15–100) ✓已驗證
+3      1     Military         武力 (15–100) ✓已驗證
+4      1     Charisma         魅力 (15–100) ✓已驗證
+5      1     Luck             運氣? (15–100), 用途未確認
+6      1     Loyalty          忠誠 (12–100), 君主固定100
+7      1     Status+Navy      複合 bitfield:
                                 bit0 = 水軍旗標 (1=水軍) ✓已驗證
                                 bit1 = 統領旗標 (1=君主或軍師)
+8,+9   2     Troops (LE16)    兵士數, little-endian ✓已驗證
+10     1     City             城市 ID (0–55), 0=未配置
+11     1     Faction          勢力 ID (0–14), 0=無勢力
+12–16  5     Separator        固定 0A 0A 0A 00 00
```

### 統計
- 水軍 151 人 / 非水軍 105 人
- 統領 15 人 (12 君主 + 3 軍師)
- 負年齡 (未出生) 12 人

### 勢力對照
| Faction | 勢力 | Faction | 勢力 |
|---------|------|---------|------|
| 1 | 曹操 | 7 | 董卓 |
| 2 | 孫堅 | 8 | 劉焉 |
| 3 | 劉備 | 9 | 馬騰 |
| 4 | 袁紹 | 10 | 公孫瓚 |
| 5 | 袁術 | 11 | 陶謙 |
| 6 | 劉表 | 12–14 | 其他 |

---

## 武將姓名表

### 位置
- 所在 Bank: 14
- 表頭: 0x3A310–0x3A313 = `4C 00 00 00`
- 資料起始: 0x3A314
- 記錄數: 257 筆

### 記錄結構 (15 bytes/筆)

```
Offset  Size  欄位             說明
+0      8     Name             假名 (半角片假名, Shift-JIS 0xA6–0xDF)
+8      1     Kanji1 TileID    第一個漢字的 tile ID
+9      1     Kanji1 Page      漢字 Page 指示器 (0=Page0, 1=Page1)
+10     1     Kanji2 TileID    第二個漢字的 tile ID
+11     1     Kanji2 Page      漢字 Page 指示器
+12     1     Kanji3 TileID    第三個漢字的 tile ID (複姓用)
+13     1     Kanji3 Page      漢字 Page 指示器
+14     1     Portrait         頭像索引 byte (portrait = byte - 1)
```

### 編碼說明
假名使用 **Shift-JIS 半角片假名** 編碼 (0xA6–0xDF)

---

## 漢字 Tile 對照表

### 圖形儲存位置

```
PRG_ROM_offset = 0x205E4 + (tile_id + 0x30) × 16
File_offset = PRG_ROM_offset + 0x10
```

- **基址 (檔案)**: `0x205F4`
- **所在 Bank**: 8
- **每個漢字**: 64 bytes (4 個 8×8 tiles)

### 統計
- Page 0: **241** 個漢字 tile ID
- Page 1: **67** 個擴展漢字
- 總計: **308** 個漢字

完整對照表定義於 `sangokushi_extract_v2.py` 的 `KANJI_TILE_MAP` 常數中。

---

## 假名字體 tile

### 位置
- 所在 Bank: 8 (檔案偏移 0x20010–0x24010)
- 字體起始: 0x22CA0
- Tile 大小: 8×8 pixels, 16 bytes/tile

Tiles 按五十音順序排列 (ア、イ、ウ...)

---

## 標準頭像系統 (P00-P80)

### 概要
- 總共 **81** 個主要頭像
- 每個頭像 = 6×6 tiles = 48×48 pixels
- Tile 資料存放於 PRG ROM Banks 4-6

### 頭像指標表

**位置**: `0x1BC38` (81 entries × 4 bytes)

每筆記錄結構:
```
+0  Bank        資料所在 bank (4-6)
+1  TileCount   tile 數量 (28-36)
+2  Address     bank 內位址 (little-endian)
```

檔案偏移計算: `file_offset = bank × 0x4000 + (addr - 0x8000) + 0x10`

### 武將→頭像映射

**位置**: 姓名表每筆記錄的 byte 14
```
portrait_index = name_record[+14] - 1
```

### 排列表

**位置**: `0x1B0D4` (81 entries × 36 bytes)

頭像→排列映射: `arrangement_index = portrait_index` (1:1 對應)

### NES Tile 格式
- 每個 tile: 8×8 pixels, 16 bytes
- 2 bitplanes

### 色盤
```
Index 0: (0, 0, 0)         黑色
Index 1: (247, 216, 165)   淺膚色
Index 2: (234, 158, 34)    深膚色
Index 3: (255, 255, 255)   白色
```

---

## 檔案清單

| 檔案 | 說明 |
|------|------|
| `sangokushi_extract_v2.py` | 武將資料解析主程式 |
| `kanji_export.py` | 漢字字型匯出工具 |
| `portrait_export.py` | 頭像匯出工具 |
| `docs/DATA_FORMAT.md` | 武將資料表格式 |
| `docs/ROM_STRUCTURE.md` | ROM 檔案結構 |
| `docs/KANJI_TILES_ANALYSIS.md` | 漢字 tile 映射分析 |
