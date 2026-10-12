# FC 信長の野望・戦国群雄伝 解析

KOEI，1990，FC（MMC5，PRG 256 KB、CHR 128 KB、電池）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 武將（2 劇本，含登場武將）、國、大名、頭像 PNG、組合臉零件、大地圖、戰場地圖 → gunyuu/output/
.venv/bin/python gunyuu/export.py [--rom ROM] [--out DIR] [--scale N]

# kaodata 統一格式資料集 gunyuu-fc
.venv/bin/python gunyuu/export_kaodata.py --out <kaodata>/data-local/gunyuu-fc
# 驗證：逐 pixel 比對、重算 checksums；裝了 py65 會再用模擬器跑遊戲的頭像程式比對
.venv/bin/python gunyuu/verify_kaodata_export.py --dataset <輸出目錄>
# 驗證戰場地圖：76 張圖每格都用模擬器跑遊戲的畫格程式，和靜態解碼比對（需 py65）
.venv/bin/python gunyuu/verify_battle_maps.py
```

ROM 預設直接讀 `roms/Nobunaga no Yabou - Sengoku Gunyuu Den (Japan).zip`（`--rom` 也接受 .nes 或 .zip）。
依賴：Pillow；openpyxl（可選，匯出 .xlsx）；py65（可選，驗證時跑模擬器）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字（含外字）、武將、國、大名、頭像、大地圖、戰場地圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | kaodata 資料集 `gunyuu-fc` 與參考渲染器 |
| `verify_kaodata_export.py` | 資料集的獨立驗證 |
| `verify_battle_maps.py` | 戰場地圖解碼與遊戲程式的比對 |
| `tools/nes_emu.py` | 整機模擬（py65），可開機、按鍵、截圖，用來對照畫面 |
| `tools/pcode_emu.py` | MMC5＋6502 最小模擬，單獨呼叫遊戲的函式（py65） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `generals.csv` | 2 劇本 × 255 筆：開局 217＋215、之後登場 38＋40；姓名、生年、年齢、登場年、卒年（推定）、政治、戦闘、魅力、野望、忠誠、兵士、訓練、武装、部隊、所在國、大名、頭像碼 |
| `provinces.csv` | 2 × 38 國：大名、城主、金、米、石高、治水、町、兵、民忠、城、開局武將、相鄰國（附旗標） |
| `daimyo.csv` | 大名 28＋10 家：同盟、對各家友好度、關係旗標（推定） |
| `battle_maps.csv` | 野戰 38＋城 38 張的地形格（13×12） |
| `gunyuu.xlsx` | 以上各表（需 openpyxl） |
| `faces/NNN_姓名.png` | 每個不同人物（姓名＋頭像碼）的頭像（40×48），429 張 |
| `mob_parts.png`、`mob_parts/<組>_<部位>_<n>.png` | 組合臉零件總覽圖（4 倍）與每個零件的 PNG（原尺寸），`export.py` 一併輸出 |
| `portraits/FNNN.png` | 85 張專屬頭像（F000–F089，不含沒用到的 60–64） |
| `map.png` | 大地圖（512×240，不含家紋） |
| `battle_maps/{field,castle}/NN_國.png` | 戰場畫面（256×240，部隊與視窗之前的底圖） |

kaodata 資料集：429 人，85 人用專屬頭像，344 人用組合臉（6 組，每組頭框／眼／鼻／口各 5 種）。ROM 沒有讀音，所以沒有 `reading`。像素存 NES 色號，色盤是 NES 64 色。

## 進度

- ✓ MMC5 bank 配置、p-code 入口 `$E414`、跨 bank 複製 `$DB6B`、畫圖服務 8、bank 影子 `$070C`
- ✓ 劇本 2 個：姓名表、武將（對照畫面）、國（對照畫面）、大名（同盟、友好度）
- ✓ 國名、相鄰關係；外字 5 個（長宗我部、香宗我部、野々村、板部岡、鳥屋尾，逐一在畫面上確認）
- ✓ 專屬頭像 90 個編號（兩張表）、組合臉（6 組；模擬器 3840 個碼全部一致）、kaodata `gunyuu-fc`
- ✓ 大地圖（與遊戲畫面比對）
- ✓ 戰場：野戰 38、城 38 張（13×12）；畫格規則與遊戲程式逐格一致
- 未解：見 ROM_FORMAT.md §6
