# FC 信長の野望・武将風雲録 解析

KOEI，1991，FC（MMC5）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 武將（2 劇本＋登場武將）、國、茶器、頭像 PNG、大地圖、戰場地圖 → bushou/output/
.venv/bin/python bushou/export.py [--rom ROM] [--out DIR]

# kaodata 統一格式資料集 bushou-fc
.venv/bin/python bushou/export_kaodata.py --out <kaodata>/data-local/bushou-fc
# 驗證：逐 pixel 比對、重算 checksums；裝了 py65 會再用模擬器跑遊戲的頭像程式比對
.venv/bin/python bushou/verify_kaodata_export.py --dataset <輸出目錄>
# 驗證戰場地圖：97 張圖用模擬器跑遊戲的畫面組裝程式，和靜態解碼比對（需 py65）
.venv/bin/python bushou/verify_battle_maps.py
# 組合臉零件總覽圖
.venv/bin/python sangokushi/tools/parts_sheet.py --dataset <輸出目錄> --out bushou_parts.png
```

ROM 預設直接讀 `roms/Nobunaga no Yabou - Bushou Fuuun Roku (Japan).zip`（`--rom` 也接受 .nes 或 .zip）。
依賴：Pillow；openpyxl（可選，匯出 .xlsx）；py65（可選，驗證時跑模擬器）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字（含外字）、武將、國、大名、茶器、頭像、大地圖、戰場地圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | kaodata 資料集 `bushou-fc` 與參考渲染器 |
| `verify_kaodata_export.py` | 資料集的獨立驗證 |
| `verify_battle_maps.py` | 戰場地圖解碼與遊戲程式的比對 |
| `tools/nes_emu.py` | 整機模擬（py65），可開機、按鍵、截圖，用來對照畫面 |
| `tools/pcode_emu.py` | MMC5＋6502 最小模擬，單獨呼叫遊戲的函式（py65） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `generals.csv` | 2 劇本共 721 筆：開局武將（250＋255）、改名（徳川家康、豊臣秀吉）、登場武將（121＋92）；姓名、生年、年齢／登場年、政治、戦闘、教養、魅力、野望、忠誠、相性（推定）、所在國、大名、頭像碼 |
| `provinces.csv` | 2 × 48 國：大名、金、米、石高、治水、町、文化／技術（推定）、兵忠、城、兵、鉄砲、訓練、民忠、武將、相鄰國 |
| `daimyo.csv` | 大名 41＋32 家（大半欄位未解，保留原值） |
| `tea.csv` | 2 × 48 茶器：名稱、持有者、第一個 byte（意義未知） |
| `battle_maps.csv` | 野戰 48＋城 49 張：戰場名、地形格（城另附第二層） |
| `bushou.xlsx` | 以上各表（需 openpyxl） |
| `faces/NNN_姓名.png` | 每個不同人物（姓名＋頭像碼）的頭像（40×48），463 張 |
| `portraits/FNNN.png` | 212 張專屬頭像 |
| `map.png` | 大地圖（240×208） |
| `battle_maps/{field,castle}/NN_國_戰場名.png` | 戰場畫面（256×240，部隊與文字之前的底圖）；`*_winter/` 為冬季調色盤（推定） |
| `battle_maps/metatiles.png` | 41 個戰場圖塊與使用它的地形 |

kaodata 資料集：463 人，212 人用專屬頭像，251 人用組合臉（5 個頭，每頭 5 區 × 4 頁）。ROM 沒有讀音，所以沒有 `reading`。像素存 NES 色號，色盤是 NES 64 色。

## 進度

- ✓ MMC5 bank 配置、p-code 入口與系統呼叫、PRG-RAM 映射到 `$8000`
- ✓ 劇本 2 個：國（對照畫面）、武將（對照畫面）、姓名表、登場武將、大名（部分）、茶器
- ✓ 國名、相鄰關係；外字 8 個（長宗我部、香宗我部、鳥屋尾、佐々木）
- ✓ 專屬頭像 212 個編號、組合臉（每頭的區域表；模擬器 728 個碼全部一致）、kaodata `bushou-fc`
- ✓ 大地圖
- ✓ 戰場：野戰 48 張（14×11）、城 49 張（13×11）、戰場名；畫面組裝規則與遊戲程式逐 tile 一致
- 未解：見 ROM_FORMAT.md §9
