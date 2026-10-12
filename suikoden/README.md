# FC 水滸伝・天命の誓い 解析

KOEI, 1989, FC（MMC5）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 人物（含 4 劇本）、州、頭像 PNG、地圖、戰鬥地圖 → suikoden/output/
.venv/bin/python suikoden/export.py [--rom ROM] [--out DIR] [--scale N]

# kaodata 統一格式資料集 suikoden-fc
.venv/bin/python suikoden/export_kaodata.py --out <kaodata>/data-local/suikoden-fc
# 驗證：逐 pixel 比對 ROM 直接組出的臉、重算 checksums；裝了 py65 會再用模擬器核對組合臉規則
.venv/bin/python suikoden/verify_kaodata_export.py --dataset <輸出目錄>
# 驗證戰鬥地圖：49 州 × 4 季節，模擬器跑遊戲的繪製程式和靜態解碼逐格比對（需 py65，約 2 分鐘）
.venv/bin/python suikoden/verify_battle_maps.py
# 大眾臉零件總覽圖（5 類型 × 頭／顎／眼／鼻／口）
.venv/bin/python sangokushi/tools/parts_sheet.py --dataset <輸出目錄> --out mob_parts.png
```

ROM 預設直接讀 `roms/Suikoden - Tenmei no Chikai (Japan).zip`（也接受 `--rom` 指定 .nes 或 .zip）。
依賴：Pillow；openpyxl（可選，匯出 .xlsx）；py65（可選，驗證時跑模擬器）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、人物、劇本、州、頭像、地圖、戰鬥地圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | kaodata 資料集 `suikoden-fc` 與參考渲染器 |
| `verify_kaodata_export.py` | 資料集的獨立驗證 |
| `verify_battle_maps.py` | 戰鬥地圖解碼與遊戲程式的比對 |
| `tools/pcode_emu.py` | MMC5＋6502 最小模擬，呼叫遊戲的 p-code 函式（py65） |
| `data/gaiji.tsv` | 外字 `0xEB9F–0xEBAF` → 漢字 |
| `data/surnames.tsv` | 姓氏讀音，用於 reading 的姓名分隔 |

## 輸出

| 檔案 | 內容 |
|------|------|
| `characters.csv` | 255 人：姓名、讀音、頭像碼、性別、操舵、忠義／仁愛／勇気，以及劇本 1–4 的年齡、所在州、體力、腕力、技量、知力；未知欄位以 `Unk` 保留原值 |
| `provinces.csv` | 49 州：名稱、相鄰州 |
| `faces/NNN_姓名.png` | 每人的頭像（40×48） |
| `portraits/PNN.png` | 100 張專屬頭像 |
| `map.png` | 49 州地圖（色盤為示意） |
| `battle_maps/{春,夏,秋,冬}/NN_州名.png` | 49 州戰鬥地圖，四季各一套（14×12 六角格，224×200；調色盤為推定） |
| `battle_maps.csv` | 每州 168 格：地形（0–7 與推定名稱）、所屬州 |

kaodata 資料集：95 人用專屬頭像（`portraits`），160 人用組合臉（`composite`，5 類型 × 頭／顎／眼／鼻／口各 4 種）。像素存 NES 色號，色盤是 NES 64 色。

## 進度

- ✓ MMC5 bank 配置、ExRAM 擴充屬性模式、p-code 直譯器入口與暫存器
- ✓ 漢字字形表（SJIS → tile）與 17 個外字
- ✓ 人物表（姓名、讀音、頭像碼、性別、操舵、忠義／仁愛／勇気）
- ✓ 劇本 1–4（年齡、所在州、體力、腕力、技量、知力）
- ✓ 專屬頭像 100 張與調色盤
- ✓ 組合臉：碼的位元欄位、零件表、各類型放置位置（模擬器確認）
- ✓ 州表（名稱、相鄰關係）與 49 州地圖
- ✓ kaodata `suikoden-fc` 匯出；自家驗證與 kaodata `pnpm verify` 都通過（355 張）
- ✓ 戰鬥地圖：地形、州歸屬、四季圖塊、六角格配置（49 州 × 4 季節與模擬器一致）；州表偏移 5 = 城數
- 未完成：其餘未知欄位、108 星對應、地圖與戰鬥畫面的實際配色、戰鬥部隊層、其他圖像（見 ROM_FORMAT.md §8）

驗證的限制：目前沒有實機截圖或 Mesen 紀錄。頭像正確性的依據是：組合規則由模擬器跑遊戲本身的程式碼得到，加上 255 張臉目視都是完整的臉。能力值欄位的依據是外部資料集的數值比對。
