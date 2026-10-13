# FC 三國志 解析

KOEI, 1988, FC（MMC1，CHR-RAM）。ROM 結構見 [docs/ROM_STRUCTURE.md](docs/ROM_STRUCTURE.md)，武將表格式見 [docs/DATA_FORMAT.md](docs/DATA_FORMAT.md)，研究筆記見 [MEMORY.md](MEMORY.md)。

## 指令

在 repo 根目錄執行；ROM 預設直接讀 `roms/Sangokushi (Japan).zip`（也接受 .nes 或 .zip 路徑，見 `romfile.py`）。

```bash
# 武將資料 → CSV + XLSX（寫在目前目錄）
.venv/bin/python sangokushi/sangokushi_extract_v2.py

# 專屬頭像 P00–P80 → kanji_output/
.venv/bin/python sangokushi/portrait_export.py

# kaodata 統一格式資料集 san1-fc（專屬頭像 81 張 + 大眾臉組合臉 + 255 武將姓名／讀音）
.venv/bin/python sangokushi/tools/export_kaodata.py --out <kaodata>/data-local/san1-fc
# 驗證：和探索器舊算法、截圖、Mesen 紀錄逐 pixel 比對；專屬頭像和 portrait_export.py 比對
.venv/bin/python sangokushi/tools/verify_kaodata_export.py --dataset <輸出目錄>

# 58 國戰爭地圖 → sangokushi/output/battle_maps/（NN_州名.png + terrain.png）
.venv/bin/python sangokushi/export_battle_maps.py [--scale N]
# 驗證：模擬器開戰後逐格比對（需 py65，約 80 秒）
.venv/bin/python sangokushi/tools/verify_battle_maps.py
# 驗證：模擬器裡讓遊戲畫各武將的臉，比對專屬／組合臉分界與畫面像素（需 py65，約 90 秒）
.venv/bin/python sangokushi/tools/verify_face_select.py

# 大眾臉零件 → sangokushi/output/mob_parts.png（總覽）與 mob_parts/（各零件 PNG）；其他遊戲由各自的 export.py 呼叫
.venv/bin/python sangokushi/tools/parts_sheet.py --dataset sangokushi/output/san1-fc --out sangokushi/output
```

依賴：Pillow；openpyxl（可選，匯出 .xlsx）；py65（戰爭地圖驗證）。kaodata 格式規格見 kaodata repo 的 `docs/data-format.md`。專屬頭像（P00–P80）放在 `portraits.bin`，探索器不必下載。頭像編號（byte 14 − 1）小於 65 才是專屬頭像，65 以上一律是組合臉（`verify_face_select.py` 在模擬器裡確認，畫面像素和匯出一致），所以 P65–P80 這 16 張女性頭像沒有武將使用，匯出時標 `"group": "姫"`；編號 65–80 的 16 人（曹昂、于禁…蒋欽）是組合臉。

## 檔案

| 檔案 | 用途 |
|------|------|
| `romfile.py` | 讀 ROM（預設 `roms/` 的 zip）；各腳本共用 |
| `sangokushi_extract_v2.py` | 解析 ROM，匯出武將資料 |
| `portrait_export.py` | 專屬頭像匯出（48×48 PNG） |
| `mob_portrait_export.py` | 大眾臉頭像批量匯出（174 張） |
| `mob_component_extract.py` | 大眾臉組件索引表匯出（CSV） |
| `kanji_export.py` | 漢字字形匯出 |
| `export_battle_maps.py` | 戰爭地圖 PNG 匯出（58 國，`NN_州名.png`＋`terrain.png`） |
| `tools/export_kaodata.py` | kaodata 資料集 `san1-fc` 與參考渲染器（水滸傳的匯出也共用） |
| `tools/verify_kaodata_export.py` | 資料集的獨立驗證 |
| `tools/parts_sheet.py` | 大眾臉零件總覽圖與各零件 PNG（各遊戲共用） |
| `tools/verify_battle_maps.py` | 戰爭地圖的模擬器驗證（需 py65） |
| `tools/verify_face_select.py` | 頭像編號 → 專屬／組合臉的模擬器驗證（需 py65） |
| `tools/nes_emu.py` | MMC1＋6502＋簡易 PPU 模擬器（py65），可重播按鍵、設 PC 中斷 |
| `tools/portrait_generator.py`、`tools/portrait_matcher.py` | 單張大眾臉產生、比對 |
| `tools/mesen_portrait_*.lua` | Mesen 追蹤腳本 |
| `mob_portrait/` | 大眾臉探索器舊版（已搬到 kaodata.simagame.me）、驗證用截圖與產生圖 |
| `data/kanji_tiles.tsv` | 姓名漢字 (page, tile) → 漢字對照表，依 ROM 字形逐一確認；備註「史書作」的 12 個代用字，kaodata 匯出時改成史書寫法（`export_kaodata.py` 的 `NAME_FIXES`） |
| `data/surnames.tsv` | 姓氏讀音，用於 reading 的姓名分隔 |

## 文件

| 文件 | 內容 |
|------|------|
| `docs/ROM_STRUCTURE.md` | ROM 檔案結構（含頭像系統） |
| `docs/DATA_FORMAT.md` | 武將資料表格式 |
| `docs/PORTRAIT_SYSTEM_PSEUDOCODE.md` | 專屬頭像系統 |
| `docs/MOB_PORTRAIT_SYSTEM_PSEUDOCODE.md` | 大眾臉頭像系統 |
| `docs/KANJI_TILES_ANALYSIS.md`、`docs/KANJI_DIFF.md` | 漢字 tile 對照分析 |
| `docs/BATTLE_MAP.md` | 戰爭地圖與國／州表格式 |
| `docs/COMPLETED_ANALYSIS.md` | 已完成的分析彙整 |
| `MEMORY.md` | 逆向工程研究筆記 |

## ROM 重點

- iNES，Mapper 1（MMC1），PRG 256 KB（16 × 16 KB），沒有 CHR ROM（tile 圖形在 PRG）
- bank 位址：`file_offset = bank × 0x4000 + 0x10`
- 武將資料表：bank 14（`0x38010`），256 筆 × 17 bytes
- 頭像 4 色：黑 `(0,0,0)`、淺膚 `(247,216,165)`、深膚 `(234,158,34)`、白 `(255,255,255)`

## 進度

- ✓ 武將資料表（256 筆，含頭像／排列索引）與 CSV／XLSX 匯出
- ✓ 專屬頭像 P00–P80：指標表 `0x1BC38`（81 × 4 bytes）、排列表 `0x1B0D4`（81 × 36 bytes），武將 → 頭像在姓名表 byte 14（−1）；武將只用到 P00–P64，P65–P80（女性）是君主的姫，聯姻時出現。頭像 = P65 + ((3 × 勢力編號 − W) mod 16)，見 docs/PORTRAIT_SYSTEM_PSEUDOCODE.md；已用兩張 Mesen 截圖確認
- ✓ 大眾臉（編號 65–254）：4 類型 × 頭／眼／鼻／口各 5 種，排列模板 `0x1ED14`，組件索引表 `0x1EFE4`（190 × 5 bytes，緊接在模板後；早期文件的 `0x1F034` 是編號 81 那筆）
- ✓ kaodata `san1-fc` 匯出與驗證（專屬頭像＋大眾臉）；大眾臉零件總覽圖
- ✓ 戰爭地圖：58 國 × 14×12 格（bank 9 `0x259A4`），地形 6 種＋布陣區；國→州對照（`0x3B201`／`0x3B530`）；模擬器驗證 5 國（涵蓋全部地形）

## 慣例

- 外部資料（不是 ROM 解析出來的）欄位名加 `[EXT]` 前綴
- 輸出 CSV 用 UTF-8-BOM（Excel 相容）
