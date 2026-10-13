# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

KOEI 等 FC/NES 遊戲的 ROM 逆向工程專案：解析人物資料、頭像、地圖等遊戲內容，並輸出 kaodata 統一格式資料集。

每款遊戲各放一個子資料夾，分析結果記在該資料夾的 `README.md` 與 `docs/`：

| 資料夾 | 遊戲 |
|--------|------|
| `sangokushi/` | 三國志 (KOEI, 1988, MMC1)：武將表、專屬頭像、大眾臉、漢字對照、58 國戰爭地圖、kaodata `san1-fc` |
| `suikoden/` | 水滸伝・天命の誓い (KOEI, 1989, MMC5)：人物、劇本、頭像（專屬＋組合臉）、州地圖、四季戰鬥地圖、kaodata `suikoden-fc` |
| `genchou/` | 蒼き狼と白き牝鹿・元朝秘史 (KOEI, 1992, MMC5)：人物（4 劇本）、國、兵科、交易品、頭像（專屬＋組合臉）、大地圖、47 張戰場地圖、kaodata `genchou-fc` |
| `genghis/` | 蒼き狼と白き牝鹿・ジンギスカン (KOEI, 1988, MMC1)：人物、后妃、頭像（專屬＋組合臉）、國、大地圖、41 張戰場地圖、kaodata `genghis-fc` |
| `empereur/` | ランペルール (KOEI, 1990, MMC5)：人物（4 劇本，含性格）、國、46 都市、頭像（專屬＋組合臉）、大地圖、46 張戰場地圖、kaodata `empereur-fc` |
| `bushou/` | 信長の野望・武将風雲録 (KOEI, 1991, MMC5)：武將（2 劇本＋登場）、國、大名、茶器、頭像（專屬＋組合臉）、大地圖、野戰／城戰場地圖、kaodata `bushou-fc` |
| `ishin/` | 維新の嵐 (KOEI, 1990, MMC5)：人物（2 劇本）、藩、地點、頭像（專屬＋組合臉）、HEX 地圖／全國大地圖、kaodata `ishin-fc` |
| `gunyuu/` | 信長の野望・戦国群雄伝 (KOEI, 1990, MMC5)：武將（2 劇本）、38 國、大名、頭像（專屬＋組合臉）、大地圖、野戰／城戰場地圖、kaodata `gunyuu-fc` |
| `zenkoku/` | 信長の野望・全国版 (KOEI, 1988, MMC1)：大名（50／17 國）、國、相鄰、頭像（大名＋姫 75 張）、地方地圖、戰場地圖、kaodata `nobu2-fc` |
| `royal/` | ロイヤルブラッド (KOEI, 1991, MMC5)：人物（4 劇本）、家、領地、第 5 部隊、頭像（人物 64＋相談役 4＋部隊 23）、戰略地圖、戰場 30 張、kaodata `royal-fc` |
| `daikoukai/` | 大航海時代 (KOEI, 1990, MMC5)：人物、航海士能力、頭像（專屬＋組合臉）、70 港口、世界地圖、港町圖、kaodata `daikoukai-fc` |
| `san2/` | 三國志II (KOEI, 1991, MMC5)：武將 352 人（6 劇本）、41 州（六角相鄰）、頭像（專屬＋組合臉）、大地圖、41 張戰場（可依直欄六角排法拼成全中國戰場圖）、kaodata `san2-fc` |
| `chuugen/` | 三國志 中原の覇者 (Namco, 1988, Namco 163)：武將、州、道路、頭像（共用整張臉 120 張＋表情）、大地圖、戰場地圖、kaodata `chuugen-fc` |
| `haou/` | 三國志II 覇王の大陸 (Namco, 1992, Namco 163)：武將（[EXT] 漢字）、州、君主、道具、頭像（共用整張臉＋5 表情）、大地圖、戰場地圖 30 張、kaodata `haou-fc` |

- ROM 都放 `roms/`（不進版控）：各遊戲（含三國志）的程式都直接讀 `roms/` 裡的 zip。分析時可暫時把 `.nes` 解到根目錄，做完要刪掉，只留 zip 作為來源
- `docs/`：GitHub Pages，只剩兩個大眾臉探索器的轉址頁（已搬到 kaodata.simagame.me），不要放分析文件
- 各遊戲的 kaodata 匯出共用 `sangokushi/tools/export_kaodata.py` 的參考渲染器；`sangokushi/tools/parts_sheet.py` 輸出大眾臉零件總覽圖與各零件 PNG（有組合臉的遊戲由 `export.py` 呼叫，寫進 `output/`）

## 常用指令

在 repo 根目錄執行，Python 一律用 `.venv/bin/python`（依賴：Pillow、openpyxl、py65）。

```bash
# 三國志
.venv/bin/python sangokushi/sangokushi_extract_v2.py
.venv/bin/python sangokushi/tools/export_kaodata.py --out <kaodata>/data-local/san1-fc
.venv/bin/python sangokushi/tools/verify_kaodata_export.py --dataset <輸出目錄>

# 水滸伝
.venv/bin/python suikoden/export.py
.venv/bin/python suikoden/export_kaodata.py --out <kaodata>/data-local/suikoden-fc
.venv/bin/python suikoden/verify_kaodata_export.py --dataset <輸出目錄>

# lint
uvx ruff check --line-length 120 <檔案或資料夾>
```

各遊戲完整的指令、檔案與格式見該資料夾的 `README.md`。kaodata 格式規格見 kaodata repo 的 `docs/data-format.md`。

## 開發慣例

- 新遊戲：開新資料夾，`README.md` 寫指令／檔案／進度，`docs/` 寫 ROM 格式（含尚未解開的部分）
- 外部資料（不是 ROM 解析出來的）欄位名加 `[EXT]` 前綴
- 輸出 CSV 用 UTF-8-BOM（Excel 相容）；匯出結果放各遊戲的 `output/`（不進版控）
- 頭像等解碼要有獨立驗證（模擬器跑遊戲本身的程式、截圖或 Mesen 紀錄）
- 最上層與 `tools/` 的分工兩款不一致，刻意保留、不要統一：
  - `suikoden/`：最上層是執行入口與解碼核心 `rom.py`，`tools/` 只放輔助模組（模擬器）
  - `sangokushi/`：最上層是早期工具；`tools/` 混放正式入口（kaodata 匯出／驗證、`parts_sheet.py`）與研究用小工具
