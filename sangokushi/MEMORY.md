# MEMORY.md — 三國志 NES ROM 逆向工程研究記錄

> **已完成的分析** (武將表、姓名表、標準頭像等) 已移至 `docs/COMPLETED_ANALYSIS.md`

---

## ROM 概要

| 項目 | 值 |
|------|------|
| 檔名 | `Sangokushi (Japan).nes` |
| Mapper | 1 (MMC1) |
| PRG ROM | 256 KB = 16 banks × 16 KB |
| PRG 偏移 | 0x00010 – 0x4000F |
| CHR ROM | 0 KB (CHR-RAM) |
| Bank 換算 | `file_offset = bank × 0x4000 + 0x10` |

---

## 大眾臉頭像系統 (P81-P254) — 已完成

### 概要

| 項目 | 值 |
|------|------|
| 索引範圍 | 81-254 (174 個頭像) |
| 結構 | 20 Heads × 可變 variants |
| Tile 資料 | Bank 7 |
| 排列模板表 | 0x1ED14 (20 條 × 36 bytes) |
| 組件索引表 | 0x1F034 (174 條 × 5 bytes) |

### 組件索引表 (2026-02-28 Mesen 追蹤確認)

```
位置: ROM 0x1F034
格式: 每筆 5 bytes = [Cat, Head, Eye, Nose, Mouth]
索引: addr = 0x1F034 + (portrait_index - 81) * 5
全域轉換: global = cat * 5 + local  (0-19)
```

驗證: 周泰(P081) ✓, 曹豹(P085) 5欄位全吻合 ✓, 陳登(P157) 遊戲截圖一致 ✓

### 20 個 Head 位置表與武將分佈

| Head | ROM 基底 | 武將數 | Head | ROM 基底 | 武將數 |
|------|----------|--------|------|----------|--------|
| H00 | 0x1C014 | 5 | H10 | 0x1CF14 | 6 |
| H01 | 0x1C194 | 9 | H11 | 0x1D094 | 6 |
| H02 | 0x1C314 | 10 | H12 | 0x1D214 | 4 |
| H03 | 0x1C494 | 8 | H13 | 0x1D394 | 4 |
| H04 | 0x1C614 | 8 | H14 | 0x1D514 | 3 |
| H05 | 0x1C794 | 7 | H15 | 0x1D694 | 7 |
| H06 | 0x1C914 | 11 | H16 | 0x1D814 | 15 |
| H07 | 0x1CA94 | 11 | H17 | 0x1D994 | 15 |
| H08 | 0x1CC14 | 11 | H18 | 0x1DB14 | 15 |
| H09 | 0x1CD94 | 5 | H19 | 0x1DC94 | 14 |

### 變體組件位置

| 組件 | ROM 位置 | 結構 |
|------|----------|------|
| 眼睛 (Eye) | 0x1DE14 | 20 組 × 3 tiles × 16 bytes |
| 鼻子 (Nose) | 0x1E1D4 | 20 組 × 3 tiles × 16 bytes |
| 嘴巴 (Mouth) | 0x1E594 | 20 組 × 6 tiles × 16 bytes |

### Category 系統

所有索引都是 Category-local (0-4)，global = category * 5 + local。
Head → Template: 1:1 對應 (head_global = template_index)。

---

---

## 工具

| 工具 | 說明 |
|------|------|
| `mob_portrait_export.py` | 大眾臉頭像批量匯出 (174 筆 PNG) |
| `mob_component_extract.py` | 組件索引表匯出 (CSV) |
| `portrait_export.py` | 標準頭像匯出 (P00-P80) |
| `tools/mesen_portrait_trace.lua` | Mesen 追蹤腳本 |
| `mob_portrait/variant_explorer/` | 大眾臉頭像探索器 |
