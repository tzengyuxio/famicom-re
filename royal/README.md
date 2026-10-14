# FC ロイヤルブラッド 解析

KOEI，1991（日本 1991-08-29 發售；PC-8801 1991-09-27、PC-9801 1991-12-21、MSX2 1991-12-26、X68000 1992-03-27、FM TOWNS 1992-05-01、MD 1992-06-25、SFC 1992-10-22、Windows 98 2005-08-05，ja.wikipedia〈ロイヤルブラッド〉），FC（MMC5，PRG 256 KB、CHR 256 KB、電池）；北美版 *Gemfire*。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 人物（4 劇本）、家、領地、傭兵、頭像 PNG、大地圖、戰場地圖 → royal/output/
.venv/bin/python royal/export.py [--rom ROM] [--out DIR] [--scale N]

# kaodata 統一格式資料集 royal-fc
.venv/bin/python royal/export_kaodata.py --out <kaodata>/data-local/royal-fc
# 驗證：逐 pixel 比對 ROM 表、重算 checksums；裝了 py65 會再用模擬器讓遊戲自己畫 64 人＋相談役 4 人的臉來比對
.venv/bin/python royal/verify_kaodata_export.py --dataset <輸出目錄>
# 驗證大地圖與 30 張戰場地圖：用模擬器跑遊戲（示範模式的第一場戰鬥），換入各領地的地形後比對畫面
.venv/bin/python royal/verify_battle_maps.py
```

ROM 預設直接讀 `roms/Royal Blood (Japan).zip`（`--rom` 也接受 .nes 或 .zip）。
依賴：Pillow；openpyxl（可選，匯出 .xlsx）；py65（驗證時跑模擬器）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：劇本（家、人物、領地）、名稱表、傭兵、頭像、大地圖、戰場地圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | kaodata 資料集 `royal-fc` 與參考渲染器 |
| `verify_kaodata_export.py` | 資料集的獨立驗證（含模擬器） |
| `verify_battle_maps.py` | 大地圖、戰場地圖解碼與遊戲畫面的比對 |
| `tools/nes_emu.py` | 整機模擬（py65，從 `gunyuu/` 複製），可開機、按鍵、截圖、快照 |
| `tools/play.py` | 把模擬器帶到固定畫面的按鍵序列（選家畫面、相談役畫面、示範模式第一場戰鬥） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `characters.csv` | 4 劇本登場人物 37／44／44／39 筆：姓名、年齢、知力、武力、魅力、所在領地、家、身分（当主／家臣／在野）、一族（推定）、未知欄位 |
| `houses.csv` | 4 劇本的家 7／7／6／6 家：当主、支配領地、旗標位元（未知） |
| `provinces.csv` | 4 × 30 領地：支配家、金、食料、兵、開発、作物、民忠（右欄三項依圖示推定）、傭兵候補（推定）、人物、相鄰、地圖標號格 |
| `units.csv` | 23 種第 5 部隊（怪物 9、傭兵 6、魔術 6、パスハ、ドラゴン）：初期兵力與未知欄位 |
| `battle_maps.csv` | 30 張戰場的地形格（10×8，高 4 位元） |
| `royal.xlsx` | 以上各表（需 openpyxl） |
| `faces/CNN_姓名.png` | 64 人的頭像（40×48；頭像編號＝人物編號） |
| `advisers/AN.png` | 4 位相談役 |
| `unit_faces/UNN_名稱.png` | 23 種第 5 部隊的頭像 |
| `map.png` | 戰略地圖（112×152，領地編號已畫在圖上；不含各家標記） |
| `battle_maps/NN_領地.png` | 戰場（160×128，部隊之前的底圖） |

沒有組合臉，所以沒有 `mob_parts`。kaodata 資料集：64 人、91 張 portraits（人物 64＋相談役 4＋部隊 23），`reading` 是片假名轉平假名。P64–P67 的 `group` 是「相談役」（相談役畫面只有臉、沒有名字，所以不給 `name`）；P68–P90 的 `group` 是「第5部隊」，`name` 是 ROM 部隊名稱表（docs §3.4）的片假名。遊戲不存頭像編號（人物臉＝紀錄序號，相談役／部隊＝表內序號），所以 portraits 沒有 `code`。沒有中文版，所以沒有 `nameZh`。像素存 NES 色號，色盤是 NES 64 色。

## 進度

- ✓ MMC5 bank 配置、p-code 入口 `$DED9`、NMI 期間的 tile 傳送 `$F6C0`
- ✓ 劇本 4 個（bank 18，各 0x800 複製到 `$6000`）：家、人物（對照選家畫面 エラン 82/87/76、19 才）、領地（對照 4:バーニシア 畫面）
- ✓ 名稱表：人物 64、領地 30（含相鄰、地圖標記位置）、家 41、部隊 23＋戰鬥標籤 27
- ✓ 頭像 91 張：人物 64 張由遊戲 `$DB3B` 畫出逐 pixel 一致，相談役 4 張與實際畫面一致；kaodata `royal-fc`
- ✓ 戰略地圖（與畫面比對，差異只在 27 個家標記格）
- ✓ 戰場 30 張（10×8）：每張都換進遊戲的戰鬥裡讓遊戲畫，無部隊的格子全部一致
- 未解：見 ROM_FORMAT.md §7
