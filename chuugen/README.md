# FC 三國志 中原の覇者 解析

Namco，1988，FC（mapper 19 = Namco 163，PRG 128 KB、CHR-ROM 128 KB、電池）。不是 KOEI 作品，引擎從頭分析（6502 原生碼）。
ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 武將、州、道路、戰場、頭像 PNG、大地圖、道路圖、戰場地圖 → chuugen/output/
.venv/bin/python chuugen/export.py [--rom ROM] [--out DIR] [--scale N]

# kaodata 統一格式資料集 chuugen-fc
.venv/bin/python chuugen/export_kaodata.py --out <kaodata>/data-local/chuugen-fc
# 驗證：模擬器逐人跑遊戲的頭像程式與姓名程式比對，並重算 checksums（需 py65）
.venv/bin/python chuugen/verify_kaodata_export.py --dataset <輸出目錄>
# 驗證：30 張戰場與大地圖都用模擬器跑遊戲的載入程式比對（需 py65）
.venv/bin/python chuugen/verify_battle_maps.py
```

ROM 預設直接讀 `roms/Sangokushi - Chuugen no Hasha (Japan).zip`（`--rom` 也接受 .nes 或 .zip）。
依賴：Pillow；openpyxl（可選，匯出 .xlsx）；py65（驗證用）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字（tile 編號）、武將、州、道路、頭像（sprite）、大地圖（CHR 內 RLE 畫面）、戰場 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | kaodata 資料集 `chuugen-fc` 與參考渲染器 |
| `verify_kaodata_export.py` | 資料集的模擬器驗證 |
| `verify_battle_maps.py` | 戰場／大地圖解碼與遊戲程式的比對 |
| `tools/nes_emu.py` | Namco 163 整機模擬（py65）：開機、按鍵、截圖（含 IRQ 換 bank、捲動、sprite）、單獨呼叫副程式 |
| `data/kanji_names.tsv` | [EXT] 武將漢字（讀音比對 san1-fc＋人工判讀，附來源欄） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `generals.csv` | 241 人（0-5 為君主）：片假名姓名、[EXT] 漢字、所在州、体、知、武、徳、忠、軍種（平／木／山）、三種兵數、頭像 |
| `provinces.csv` | 30 州：君主、キン、トチ、サンギョウ、ジンコウ、トウチド、武將、相鄰州（附道路編號）、城座標 |
| `roads.csv` | 64 條道路與方向 |
| `battle_maps.csv` | 30 張戰場：16×10 地形碼、城格、守方／攻方初始格（推定） |
| `chuugen.xlsx` | 以上各表 |
| `faces/` | 每位武將一張 24×32 頭像 |
| `portraits/` | 120 張不重複頭像 F000-F119；`expressions/` 為 4 種表情 × 2 種嘴形 |
| `map.png`、`roads.png` | 大地圖（含各君主顏色的城）、「ミチをみる」道路圖 |
| `battle_maps/` | 30 張戰場（被攻州的地圖） |

劇本只有 200 年 1 月一個。頭像是 241 人共用 120 張的完整臉（不是組合臉），所以沒有大眾臉零件輸出。
