# FC 維新の嵐 解析

KOEI, 1990, FC（MMC5，CHR-ROM 128 KB）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 人物（劇本 1、2）、藩、地點、地圖、頭像 PNG → ishin/output/
.venv/bin/python ishin/export.py [--rom ROM] [--out DIR] [--scale N]

# kaodata 統一格式資料集 ishin-fc
.venv/bin/python ishin/export_kaodata.py --out <kaodata>/data-local/ishin-fc
# 驗證：逐 pixel 比對、重算 checksums、模擬器在「じぶん」畫面畫出全部 202 個頭像碼並比對（需 py65，約 4 分鐘）
.venv/bin/python ishin/verify_kaodata_export.py --dataset <輸出目錄> [--no-emulator]
# 驗證 HEX 地圖：模擬器把開局地圖換成 47 張的每一張，逐格比對（需 py65，約 7 分鐘）
.venv/bin/python ishin/verify_maps.py [--maps 0,31,42]
```

ROM 預設直接讀 `roms/Ishin no Arashi (Japan).zip`（也接受 `--rom` 指定 .nes 或 .zip）。
依賴：Pillow；openpyxl（可選，匯出 .xlsx）；py65（驗證用模擬器）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、人物、藩、頭像、HEX 地圖、勢力図 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | kaodata 資料集 `ishin-fc` 與參考渲染器 |
| `verify_kaodata_export.py` | 資料集的獨立驗證（含模擬器） |
| `verify_maps.py` | HEX 地圖解碼與遊戲繪製的比對 |
| `tools/nes_emu.py` | MMC5＋6502＋簡易 PPU 模擬器（py65），可重播按鍵、存取狀態 |
| `data/gaiji.tsv` | 外字 `0xEB46–0xEB57` → 漢字 |

## 輸出

| 檔案 | 內容 |
|------|------|
| `characters.csv` | 201 人：姓名、頭像碼、組合臉零件；劇本 1／2 各自的年齡、身分、所屬、體力、精神力、學力、武力、先進性、尊王／公議／佐幕、金、特產品、所在地、信賴；未知欄位以 `Unk` 保留原值 |
| `domains.csv` | 23 藩：種類（雄藩／幕府／天領）、城位置、金米、石高、共感、武装、兩支藩兵的兵數／訓練／位置 |
| `places.csv` | 町、城、町內設施（學問種類、藩校、伝習所、道場）、國地圖上的村／港／鉱山／関所 |
| `maps.csv` | 47 張地圖：名稱、方格位置、117 格原始值 |
| `ishin.xlsx` | 以上四表 |
| `faces/NNN_姓名.png`、`portraits/PNN.png` | 每人頭像、87 張專屬頭像（40×48） |
| `mob_parts.png`、`mob_parts/<類型>_<部位>_<n>.png` | 組合臉零件總覽圖（4 倍）與每個零件的 PNG（原尺寸），`export.py` 一併輸出 |
| `maps/NN_名稱.png` | 47 張 HEX 地圖（31 國＋8 町 × 2；208×152） |
| `world_map.png` | 31 張國地圖依位置表拼成的全日本大地圖 |
| `world_map_grid.png` | 同上，加上國地圖格線（白）、地方邊界（紅）與「編號 地方名」標籤 |
| `world_map_2x.png`、`world_map_grid_2x.png` | 以上兩張的 2 倍版（固定 2 倍，不受 `--scale` 影響） |
| `japan.png` | 勢力図底圖（192×144） |

kaodata：86 人用專屬頭像，115 人用組合臉（5 類型 × 6 槽 × 4 種，加一個底色槽）。ROM 沒有讀音，所以沒有 `reading`。

## 進度

- ✓ MMC5 配置、p-code 入口、遊戲狀態 bank 映射到 WRAM
- ✓ 人物 201 人 × 2 劇本（姓名、年齡、能力、思想、身分、所屬、金、特產品、位置、信賴），和遊戲畫面對過
- ✓ 藩 23 個（金米、石高、共感、武装、藩兵兵力），和遊戲畫面對過
- ✓ 專屬頭像 87 張、組合臉規則；模擬器畫出的 202 個頭像碼逐 pixel 一致
- ✓ HEX 地圖 47 張、格子值 → 圖塊、地圖位置表、町／城／設施位置；勢力図底圖
- 未完成：部分地形與町內建築名稱（推定或未知）、人物與藩兵記錄的未知 bytes、國地圖點位／事件表、劇本 2 的藩資料、特產品相場（見 ROM_FORMAT.md §6）
