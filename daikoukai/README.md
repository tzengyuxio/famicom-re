# FC 大航海時代 解析

KOEI，1990，FC（MMC5）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 人物、航海士能力、港口、名稱表、頭像 PNG、世界地圖、港町圖 → daikoukai/output/
.venv/bin/python daikoukai/export.py [--rom ROM] [--out DIR]

# kaodata 統一格式資料集 daikoukai-fc
.venv/bin/python daikoukai/export_kaodata.py --out <kaodata>/data-local/daikoukai-fc
# 驗證：逐 pixel 比對、重算 checksums；裝了 py65 會再用模擬器跑遊戲的頭像程式比對
.venv/bin/python daikoukai/verify_kaodata_export.py --dataset <輸出目錄>
# 驗證地圖：港町圖用模擬器跑遊戲的選圖程式；世界地圖從開機重放到出港、航行中比對重畫畫面（需 py65）
.venv/bin/python daikoukai/verify_maps.py
```

ROM 預設直接讀 `roms/Daikoukai Jidai (Japan).zip`（`--rom` 也接受 .nes 或 .zip）。
依賴：Pillow；openpyxl（可選，匯出 .xlsx）；py65（可選，驗證時跑模擬器）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、人物、能力、女性、港口、名稱表、頭像、世界地圖、港町圖 |
| `export.py` | 匯出 CSV／XLSX／PNG（含 `mob_parts`） |
| `export_kaodata.py` | kaodata 資料集 `daikoukai-fc` 與參考渲染器 |
| `verify_kaodata_export.py` | 資料集的獨立驗證（含模擬器跑遊戲的頭像程式） |
| `verify_maps.py` | 港町圖與世界地圖解碼和遊戲的比對 |
| `tools/nes_emu.py` | 整機模擬（py65），可開機、按鍵、截圖 |
| `tools/pcode_emu.py` | MMC5＋6502 最小模擬，單獨呼叫遊戲的函式；`trace_face` 跑頭像程式 |

## 輸出

| 檔案 | 內容 |
|------|------|
| `persons.csv` | 41 筆：主角、航海士 20（含年齡（推定）、統率、判断、知力、勇気、強さ）、提督 20（4 國 × 5）；國、戰鬥／航海等級、頭像碼 |
| `girls.csv` | 女性 20 人與頭像 |
| `ports.csv` | 70 港：名稱、交易港／補給港、座標（chunk、metatile、像素）、經濟圈、特產品、港町圖類型、建物旗標 |
| `names.csv` | 交易品 26、大砲 3、船首像 6、船種 6、木材 4、桅數 3、帆 2 |
| `daikoukai.xlsx` | 以上各表（需 openpyxl） |
| `faces/NN_姓名.png` | 61 人的頭像（40×48）：0–40 人物、41–60 女性 |
| `portraits/FNN.png` | 48 張專屬頭像 |
| `mob_parts.png`、`mob_parts/` | 組合臉零件（4 頭 × 5 區 × 4 頁） |
| `map.png` | 世界地圖原尺寸 16128×8064（調色盤 PNG，不含港口記號） |
| `map_small.png` | 1/4 縮圖，紅點＝交易港、黃點＝補給港，標港口編號 |
| `towns/typeN.png`、`towns/NN_港名.png` | 港町圖 8 類型的底圖，以及各港實際畫面（依新遊戲時的建物旗標疊零件），224×112 |

kaodata 資料集：61 人，36 人用專屬頭像，25 人用組合臉。ROM 沒有讀音，所以沒有 `reading`。像素存 NES 色號。

## 外部對照

- 航海士能力與等級：[mikesrpgcenter Uncharted Waters — Mates](https://www.mikesrpgcenter.com/uncharted/mates.html)（SNES 英文版）與本表一致（如 Fernando 6／5、92／80／75／80／75）；英文名不同者如 Alfonso = ファスコ。
- 港口分區：[mikesrpgcenter — Ports](https://www.mikesrpgcenter.com/uncharted/ports.html) 的 8 個經濟圈與屬性 byte 0 一致。
- 船的能力：SNES 版數值在 FC ROM 中找不到；FC 版由船的記錄（材質、桅數、帆型）在 bank 22 的函式算出，見 ROM_FORMAT.md §9。

## 進度

- ✓ MMC5 bank 配置、p-code 入口與系統呼叫、新遊戲初始狀態（bank 57 → WRAM）
- ✓ 人物 41 筆（主角、航海士 20、提督 20）、航海士能力（對照 SNES 版外部資料）、女性 20 人
- ✓ 頭像：專屬 48 張、組合臉（4 頭 × 5 區 × 4 頁），靜態解碼與模擬器一致
- ✓ 港口 70 個：名稱、座標、經濟圈、特產品、文化圈
- ✓ 世界地圖 72 × 36 chunk（16128 × 8064 px），航行中重畫畫面逐 tile 一致
- ✓ 港町圖 8 類型與各港對應（模擬器跑選圖與畫面組裝函式 70 港一致；里斯本實機畫面 392/392 tile 一致）
- 未解：市場行情、船的能力公式、海戰地圖、專屬頭像 1–12 對應的人物（國王等）、港口屬性 byte 2／4、建物旗標 bit 0／1／3
