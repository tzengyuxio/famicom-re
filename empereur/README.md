# FC ランペルール 解析

KOEI，1990，FC（MMC5）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 人物（4 劇本）、國家、都市、頭像 PNG、大地圖、戰場地圖 → empereur/output/
.venv/bin/python empereur/export.py [--rom ROM] [--out DIR] [--scale N]

# kaodata 統一格式資料集 empereur-fc
.venv/bin/python empereur/export_kaodata.py --out <kaodata>/data-local/empereur-fc
# 驗證：逐 pixel 比對 ROM 直接組出的臉、重算 checksums；裝了 py65 會再用模擬器跑遊戲的頭像程式
# 比對 90 個專屬碼＋4096 個組合碼（約 30 秒）
.venv/bin/python empereur/verify_kaodata_export.py --dataset <輸出目錄>
# 驗證戰場地圖：46 張圖用模擬器跑遊戲的展開與繪製程式，和靜態解碼比對（需 py65，約 25 秒）
.venv/bin/python empereur/verify_battle_maps.py
```

ROM 預設讀 `roms/Empereur, L' (Japan).zip`（zip 內的 .nes）；`--rom` 也接受 .nes 或 .zip。
依賴：Pillow；openpyxl（可選，匯出 .xlsx）；py65（可選，驗證時跑模擬器）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、國家、都市、人物、劇本資料、頭像、大地圖、戰場地圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | kaodata 資料集 `empereur-fc` 與參考渲染器 |
| `verify_kaodata_export.py` | 資料集的獨立驗證 |
| `verify_battle_maps.py` | 戰場地圖解碼與遊戲程式的比對 |
| `tools/pcode_emu.py` | MMC5＋6502 最小模擬，呼叫遊戲的 p-code 函式（py65） |
| `tools/nes_emu.py` | 可實際遊玩的 MMC5 NES 模擬（py65，研究用：畫面、存檔點、系統呼叫 trace） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `characters.csv` | 255 人：姓名、頭像碼（P = 專屬、M = 組合臉＋零件）、性格（単純／冷静／臆病／勇気／魅力／幸運） |
| `scenario_characters.csv` | 4 劇本 × 255 人：所屬國、所在都市、身分、年齡、政治／経済／補給／建設／統率／歩兵／騎兵／砲兵（A–D）、忠義（推定）、兵／馬／砲、士気、訓練 |
| `countries.csv`、`scenario_countries.csv` | 15 國；劇本別君主、都市數、金、食糧 |
| `cities.csv` | 46 都市：相鄰都市、大地圖座標 |
| `scenario_cities.csv` | 4 劇本 × 46 都市：所屬國、人口、病院、工業、商業、農業、食糧／物資充足度、衛生度、金、食糧、物資、予備兵／馬／砲、船 |
| `battle_maps.csv` | 46 張戰場 × 156 格（13 × 12）：地形 |
| `empereur.xlsx` | 以上各表（需 openpyxl） |
| `faces/NNN_姓名.png` | 255 人的頭像（40×48） |
| `mob_parts.png`、`mob_parts/<類型>_<部位>_<n>.png` | 組合臉零件總覽圖（4 倍）與每個零件的 PNG（原尺寸），`export.py` 一併輸出 |
| `portraits/PNN.png` | 90 張專屬頭像 |
| `map.png` | 大地圖（28×18 tiles，224×144，含都市編號） |
| `battle_maps/normal/NN_都市.png` | 46 張戰場地圖（13×12 格，208×200） |
| `battle_maps/winter/NN_都市.png` | 同上，雪地圖塊變體（使用時機未明） |

kaodata 資料集：255 人，88 人用專屬頭像，167 人用組合臉（4 類型，每類 5 個部位 × 4 種）。像素存 NES 色號，色盤是 NES 64 色。

## 進度

- ✓ MMC5 bank 配置、ExRAM 擴充屬性模式、p-code 直譯器入口與系統呼叫（假中斷 `$F961`）
- ✓ 國家、都市（相鄰、地圖座標）、人物主表（性格與外部資料 255/255 一致）
- ✓ 劇本人物：能力 8 項與外部資料 255 × 4 一致；年齡、兵力、士気／訓練以畫面驗證
- ✓ 劇本國家（金、食糧）、劇本都市（以マルセーユ、フランクフルト的畫面驗證）
- ✓ 專屬頭像 90 張、組合臉（模擬器 4186 個碼全部一致）、kaodata `empereur-fc`
- ✓ 大地圖（svc 9 trace 驗證）
- ✓ 戰場地圖 46 張（實戰畫面緩衝區＋模擬器 46/46 一致）
- 未解：見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)「未解」一節（戰場變體選擇、布陣區域資料、數個未知欄位）
