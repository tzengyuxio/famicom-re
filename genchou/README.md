# FC 蒼き狼と白き牝鹿・元朝秘史 解析

KOEI，1992，FC（MMC5）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 人物（4 劇本）、國、兵科、交易品、頭像 PNG、大地圖、戰場地圖 → genchou/output/
.venv/bin/python genchou/export.py [--rom ROM] [--out DIR] [--scale N]

# kaodata 統一格式資料集 genchou-fc
.venv/bin/python genchou/export_kaodata.py --out <kaodata>/data-local/genchou-fc
# 驗證：逐 pixel 比對 ROM 直接組出的臉、重算 checksums；裝了 py65 會再用模擬器跑遊戲的頭像程式比對（約 10 秒）
.venv/bin/python genchou/verify_kaodata_export.py --dataset <輸出目錄>
# 驗證戰場地圖：47 張圖用模擬器跑遊戲的載入與繪製程式，和靜態解碼比對（需 py65，約 30 秒）
.venv/bin/python genchou/verify_battle_maps.py
# 組合臉零件總覽圖（43 個頭 × 基本／上／下／眼／鼻／口）
.venv/bin/python sangokushi/tools/parts_sheet.py --dataset <輸出目錄> --out mob_parts.png
```

ROM 預設直接讀 `roms/Aoki Ookami to Shiroki Mejika - Genchou Hishi (Japan).zip`（`--rom` 也接受 .nes 或 .zip）。
依賴：Pillow；openpyxl（可選，匯出 .xlsx）；py65（可選，驗證時跑模擬器）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、人物、國、王家、兵科、交易品、頭像、大地圖、戰場地圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | kaodata 資料集 `genchou-fc` 與參考渲染器 |
| `verify_kaodata_export.py` | 資料集的獨立驗證 |
| `verify_battle_maps.py` | 戰場地圖解碼與遊戲程式的比對 |
| `tools/pcode_emu.py` | MMC5＋6502 最小模擬，呼叫遊戲的 p-code 函式（py65） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `generals.csv` | 4 劇本共 266 筆：姓名、身分、王家、所在國、年齡、體力、戦闘／政治／魅力／指揮（A–E）、文化、頭像碼 |
| `countries.csv` | 4 劇本共 113 筆：王家、金、食糧、人口、住民配分、各兵科部隊數（推定），未知欄位保留原值 |
| `units.csv` | 16 兵科：分類、戦意、機動、近接／突撃／矢弾／防御、徵兵價格、傭兵價格（×1.5，外部資料）、電腦優先順序 |
| `goods.csv` | 12 交易品 × 4 商人的表（意義推定） |
| `battle_maps.csv` | 47 張戰場 × 140 格：地形、出入國格（相鄰國） |
| `genchou.xlsx` | 以上各表（需 openpyxl） |
| `faces/NNN_姓名.png` | 每個不同人物的頭像（40×48），221 張 |
| `portraits/PNN.png` | 80 張專屬頭像 |
| `map_mongol.png`、`map_world.png` | モンゴル編與世界的大地圖（256×240） |
| `battle_maps/NN_國名.png` | 47 張戰場地圖（14×10 格，224×168；調色盤為推定） |

kaodata 資料集：222 人，35 人用專屬頭像，186 人用組合臉（43 個頭，每頭 5 個可替換區域），ベルグタイ的頭像碼超出表格，所以沒有臉。像素存 NES 色號，色盤是 NES 64 色。

## 進度

- ✓ MMC5 bank 配置、ExRAM 擴充屬性模式、p-code 直譯器入口與系統呼叫
- ✓ 文字編碼（SJIS＋半形假名、ESC K／H）
- ✓ 人物：4 劇本 × 109 格，含劇本 1 的家族區；能力值與外部資料比對過
- ✓ 國、國名、王家名（劇本別）
- ✓ 專屬頭像 80 張、組合臉 43 頭（模擬器 1456 個碼全部一致）、kaodata `genchou-fc`
- ✓ 兵科能力、價格、電腦優先順序；交易品與商人名
- ✓ 大地圖 2 張
- ✓ 戰場地圖 47 張：地形、出入國格、畫面 tilemap（模擬器 47/47 一致）
- 未完成：國的多個欄位、交易表意義、事件、城／街內部地圖、戰場與大地圖調色盤的載入點（見 ROM_FORMAT.md §8）

驗證的限制：
- 目前沒有實機截圖或 Mesen 紀錄。
- 頭像與戰場地圖的依據是：在模擬器裡跑遊戲自己的程式，結果和靜態解碼一致。
- 主畫面調色盤是從程式碼讀出來的。戰場調色盤則是推定。
