# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

FC/NES 版《三國志》(KOEI, 1988) ROM 逆向工程專案。解析 iNES 格式 ROM 中的武將資料、頭像圖像等遊戲內容。

其他 FC 遊戲各放一個子資料夾，分析結果記在該資料夾的 `README.md` 與 `docs/`：

| 資料夾 | 遊戲 |
|--------|------|
| `suikoden/` | 水滸伝・天命の誓い (KOEI, 1989, MMC5)：人物、劇本、頭像（專屬＋組合臉）、州地圖、kaodata `suikoden-fc` |

待處理的 ROM 放在 `roms/`（zip，不進版控）。

## 常用指令

```bash
# 執行武將資料匯出 (產生 CSV + XLSX)
python3 sangokushi_extract_v2.py

# 指定其他 ROM 檔案
python3 sangokushi_extract_v2.py path/to/rom.nes
```

依賴: Python 3, openpyxl (可選, 用於 Excel 匯出)

```bash
# kaodata 統一格式資料集 san1-fc (大眾臉組合臉 + 255 武將姓名/讀音)
uv venv && uv pip install pillow   # 只有驗證腳本需要 Pillow
.venv/bin/python tools/export_kaodata.py --rom "Sangokushi (Japan).nes" --out <kaodata>/data-local/san1-fc
# 與探索器舊算法、截圖、Mesen 驗證紀錄逐 pixel 比對
.venv/bin/python tools/verify_kaodata_export.py --rom "Sangokushi (Japan).nes" --dataset <輸出目錄>
```

格式規格見 kaodata repo 的 `docs/data-format.md`。專屬頭像 (P00-P80) 尚未匯出，這些武將沒有 `face`。

## 關鍵檔案

| 檔案 | 用途 |
|------|------|
| `sangokushi_extract_v2.py` | 主程式: 解析 ROM 並匯出武將資料 |
| `portrait_export.py` | 頭像匯出工具 (48×48 PNG) |
| `tools/export_kaodata.py` | kaodata 資料集匯出 (san1-fc) + 參考渲染器 |
| `tools/verify_kaodata_export.py` | 匯出結果的獨立驗證 |
| `data/kanji_tiles.tsv` | 姓名漢字 (page, tile) → 漢字對照表，依 ROM 字形逐一確認 |
| `data/surnames.tsv` | 姓氏讀音，用於 reading 的姓名分隔 |
| `docs/DATA_FORMAT.md` | 武將資料表格式技術規格 |
| `docs/ROM_STRUCTURE.md` | ROM 檔案結構 (含頭像系統) |
| `MEMORY.md` | 逆向工程研究筆記 |

## ROM 結構

- 格式: iNES, Mapper 1 (MMC1)
- PRG ROM: 256 KB (16 banks × 16 KB), 偏移 0x00010–0x4000F
- CHR ROM: 0 KB (CHR-RAM, tile 圖形存於 PRG ROM)
- Bank 偏移計算: `file_offset = bank × 0x4000 + 0x10`
- 武將資料表: Bank 14 (0x38010), 256 筆 × 17 bytes

## 開發慣例

- 外部資料 (非 ROM 解析) 欄位名加 `[EXT]` 前綴
- 程式碼註解與文件以中文為主
- 輸出檔案使用 UTF-8-BOM 編碼 (Excel 相容)

## 頭像調色盤

NES 頭像使用 4 色調色盤：

```python
PORTRAIT_PALETTE = [
    (0, 0, 0),        # Index 0: 黑色
    (247, 216, 165),  # Index 1: 淺膚色
    (234, 158, 34),   # Index 2: 深膚色
    (255, 255, 255),  # Index 3: 白色
]
```

## 目前進度

- ✓ 武將資料表完整解析 (256 筆記錄, 含頭像/排列索引)
- ✓ CSV/XLSX 匯出工具
- ✓ 標準頭像系統完整解析 (P00-P80)
  - 頭像指標表: 0x1BC38 (81 筆 × 4 bytes)
  - 排列表: 0x1B0D4 (81 筆 × 36 bytes)
  - 武將→頭像映射: 姓名表 byte 14
  - 頭像→排列映射: 1:1 對應 (`arrangement = portrait`)
- ✓ 大眾臉頭像系統解析 (P81-P254)
  - 19 個 Group 框架 (G00-G18)
  - 20 個 Template 排列模板 (0x1ED14)
  - 20 組眼睛/臉部/嘴巴變體
  - 組件索引表: 0x1F034, 174 筆 × 5 bytes [Cat, Head, Eye, Nose, Mouth]
  - 索引公式: `addr = 0x1F034 + (portrait_index - 81) * 5`
- ✓ 頭像匯出工具 (portrait_export.py)
- ✓ 大眾臉探索器 (mob_portrait/variant_explorer/)
