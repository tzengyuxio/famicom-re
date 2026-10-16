# FC 蒼き狼と白き牝鹿・ジンギスカン 解析

KOEI，1988，FC（MMC1，CHR-RAM）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 人物（2 劇本）、國、女性、頭像 PNG、大地圖、戰場地圖 → genghis/output/
.venv/bin/python genghis/export.py [--rom ROM] [--out DIR] [--scale N]

# kaodata 統一格式資料集 genghis-fc
.venv/bin/python genghis/export_kaodata.py --out <kaodata>/data-local/genghis-fc
# 驗證：逐 pixel 比對 ROM 直接組出的臉、重算 checksums；裝了 py65 會再讓遊戲本身畫出全部 168 個頭像碼來比對（約 4 分鐘，--no-emu 略過）
.venv/bin/python genghis/verify_kaodata_export.py --dataset <輸出目錄>
# 驗證戰場地圖（41 張）與大地圖（2 張）：模擬器開戰後和靜態解碼比對（需 py65，約 6 分鐘；--maps 0,1 只跑部分）
.venv/bin/python genghis/verify_battle_maps.py
```

ROM 預設直接讀 `roms/Aoki Ookami to Shiroki Mejika - Genghis Khan (Japan).zip`（`--rom` 也接受 .nes 或 .zip）。
依賴：Pillow；openpyxl（可選，匯出 .xlsx）；py65（可選，驗證時跑模擬器）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字、劇本（君主、將軍、子女、國、相鄰）、女性、頭像、大地圖、戰場地圖 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | kaodata 資料集 `genghis-fc` 與參考渲染器 |
| `data/names_zh.tsv` | [EXT] 人物中文譯名與依據 |
| `verify_kaodata_export.py` | 資料集的獨立驗證（含模擬器） |
| `verify_battle_maps.py` | 戰場地圖與大地圖的模擬器驗證 |
| `tools/emu.py` | 沿用 `sangokushi/tools/nes_emu.py`（MMC1＋py65），加上讀取 hook、按鍵腳本、名稱表讀取 |

## 輸出

| 檔案 | 內容 |
|------|------|
| `characters.csv` | 2 劇本共 121 筆：君主、將軍、子女、無名的「繼承人?」表；年齡、統率／判断／企画／説得／体力／武力、所屬國、頭像碼與組合臉零件，未知欄位放 `Unk` |
| `provinces.csv` | 41 筆（モンゴル編 14 部族、世界編 27 國）：君主、武裝度、訓練度、兵士、經濟力、町／城づくり、城的強度、10 種特產品庫存、食糧、特產品／食糧づくり、金、モラル、相鄰國、地圖座標、對應戰場圖號、未知欄位原值 |
| `women.csv` | 40 位女性：劇本、3 個頭像編號 |
| `battle_maps.csv` | 41 張戰場 × 160 格：地形（推定名稱）、進入格 |
| `genghis.xlsx` | 以上各表（需 openpyxl） |
| `faces/` | 每個君主／將軍／子女／繼承人的頭像（40×48），115 張 |
| `mob_parts.png`、`mob_parts/<類型>_<部位>_<n>.png` | 組合臉零件總覽圖（4 倍）與每個零件的 PNG（原尺寸），`export.py` 一併輸出 |
| `portraits/PNN.png` | 83 張專屬頭像 |
| `map_mongol.png`、`map_world.png` | 兩張大地圖（160×128），`_labeled` 放大 3 倍並標上國號 |
| `battle_maps/NN_名稱.png`、`terrain.png` | 41 張戰場地圖（16×10 格，512×336）與 8 種地形方塊 |

kaodata 資料集：115 人（兩劇本去重；女性的 3 個頭像碼是 3 種表情，第一張當 face，其餘不重複的放 expressions，checksum 鍵 `ch:<id>/<k>`），61 人用專屬頭像，54 人用組合臉（3 類型；類型 0 各零件 8 種，類型 1、2 各 4 種）。`nameZh` 是外部資料的中文譯名（`data/names_zh.tsv`）：取自 DOS 中文版人名，依 id 從 kaodata `genghis-pc98` 的 `nameZh` 取用（含 kaodata-re 1e23305 改正的錯字）；FC 版有些名字寫平假名（例如源頼朝、宣宗），仍是同一人。像素存 NES 色號，色盤是 NES 64 色。專屬頭像的 `code` 是頭像碼（bit 15 = 0 時就是編號，4 位十六進位）。

注意：玩家可選的君主（テムジン、ジンギスカン）在 ROM 裡的能力是佔位值（100／400），遊戲開始時會亂數決定；將軍與子女在選「自動決定」時也會重算。

## 進度

- ✓ MMC1 bank 配置、p-code 直譯器入口與暫存器、文字編碼
- ✓ 兩個劇本的君主、將軍、子女、國（主要欄位對過遊戲畫面）、相鄰關係與地圖座標、女性表
- ✓ 專屬頭像 83 張（含子調色盤旗標）、組合臉；模擬器 168/168 一致；kaodata `genghis-fc`
- ✓ 大地圖 2 張（模擬器 pixel 一致）
- ✓ 戰場地圖 41 張：地形、方塊、錯位配置、屬性表（含名稱表捲回的縫）、tile、調色盤（模擬器逐張比對）
- 未完成：見 ROM_FORMAT.md §7（部隊區、若干未知欄位、兵種與特產品價格、事件）

驗證的限制：沒有實機截圖或 Mesen 紀錄，也沒找到可交叉比對的外部數值表。頭像與地圖的依據是在模擬器裡跑遊戲本身的程式；能力值與國的欄位依據是模擬器裡的遊戲畫面。
