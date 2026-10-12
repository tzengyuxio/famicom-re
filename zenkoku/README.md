# FC 信長の野望・全国版 解析

KOEI，1988，FC（MMC1，CHR-RAM）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 大名、國（50／17 國兩種模式）、頭像 PNG、地方地圖、戰場地圖 → zenkoku/output/
.venv/bin/python zenkoku/export.py [--rom ROM] [--out DIR] [--scale N]

# kaodata 統一格式資料集 nobunaga1-fc
.venv/bin/python zenkoku/export_kaodata.py --out <kaodata>/data-local/nobunaga1-fc
# 驗證：逐 pixel 比對 ROM 直接組出的臉、重算 checksums；裝了 py65 會再讓遊戲本身畫出全部 75 張頭像來比對（約 4 分鐘，--no-emu 略過）
.venv/bin/python zenkoku/verify_kaodata_export.py --dataset <輸出目錄>
# 驗證地方地圖（9 張）與戰場地圖（50 張）：模擬器跑遊戲後和靜態解碼比對（需 py65，約 10 分鐘；--maps 0,1 只跑部分戰場）
.venv/bin/python zenkoku/verify_maps.py
```

ROM 預設直接讀 `roms/Nobunaga no Yabou - Zenkoku Ban (Japan).zip`（`--rom` 也接受 .nes 或 .zip）。
依賴：Pillow；openpyxl（可選，匯出 .xlsx）；py65（可選，驗證時跑模擬器）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、兩種模式的劇本映像（大名、國、擁有者、地方）、相鄰、頭像、地方地圖、戰場地圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | kaodata 資料集 `nobunaga1-fc` 與參考渲染器 |
| `verify_kaodata_export.py` | 資料集的獨立驗證（含模擬器） |
| `verify_maps.py` | 地方地圖與戰場地圖的模擬器驗證 |
| `tools/emu.py` | 沿用 `sangokushi/tools/nes_emu.py`（MMC1＋py65），加上按鍵腳本（開新遊戲、選國、開戰）與名稱表讀取 |

## 輸出

| 檔案 | 內容 |
|------|------|
| `daimyo.csv` | 50 國版 53 筆（50 國大名＋開局沒有國的アケチ／ハシバ／シバタ）、17 國版 17 筆：姓（片假名）與讀音、年齡、健康／野心／運／魅力／知能、頭像、領國 |
| `provinces.csv` | 50＋17 筆：地方編號、大名、金／借金／町／兵糧／石高／治水度／民忠／民財／兵力／兵忠／訓練度／武裝度、未知欄位 `Unk24`、相鄰國、出現在哪幾張地方地圖、戰場圖號 |
| `battle_maps.csv` | 50 張戰場 × 55 格：地形碼與名稱 |
| `zenkoku.xlsx` | 以上各表（需 openpyxl） |
| `portraits/PNN_名.png` | 75 張頭像（48×48）：P00–P52 大名（50 國版編號）、P53–P74 姫 |
| `maps/map50_N.png`、`maps/map17_N.png` | 地方地圖（224×128）：50 國版 7 張、17 國版 2 張；`_labeled` 放大 3 倍並在遊戲印國名的位置標國號 |
| `battle_maps/NN_國名.png`、`terrain.png` | 50 張戰場地圖（11×5 格，352×176）與 6 種地形方塊 |

kaodata 資料集：53 人（50 國版大名表；17 國版大名是同一批人、同一張臉，不重複列），全部用專屬頭像；75 張頭像（含 22 張沒有對應人物的姫）。ROM 只有片假名的姓，`reading` 是平假名。像素存 NES 色號，色盤是 NES 64 色。

本作沒有組合臉，所以不輸出大眾臉零件（`mob_parts`）。

注意：玩家大名的能力在開局時亂數重骰；電腦大名開局時能力與國的數值比 ROM 多 5（電腦強度 1 時觀察到）。ROM 裡沒有漢字姓名，也沒有全國一張的大地圖，遊戲本身就是 7 張（17 國版 2 張）地方地圖輪流切換。

## 進度

- ✓ MMC1 bank 配置、p-code 函式入口、far copy、文字編碼（半形片假名）
- ✓ 50／17 國劇本映像：大名（姓、年齡、5 項能力）、國（12 項數值對過遊戲畫面）、擁有者、地方編號、相鄰（對稱）
- ✓ 頭像 75 張；模擬器 92/92 一致（50＋17 國每個大名畫面、其餘 25 張換進織田的格子）；kaodata `nobunaga1-fc`
- ✓ 地方地圖 9 張（tile、屬性、調色盤、CHR 與遊戲畫面一致；國名標籤位置）
- ✓ 戰場地圖 50 張：地形、方塊表、錯位配置、3 個捲動畫面的屬性表、tile、調色盤（模擬器逐張比對 3 種位移，初始畫面不固定也照樣比對）；17 國版對應
- 未完成：見 ROM_FORMAT.md §6（`Unk24` 與數個 50 bytes 表、相場、部隊與合戰規則、事件）
