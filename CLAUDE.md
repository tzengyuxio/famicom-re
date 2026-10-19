# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 專案概述

KOEI 等 FC/NES 遊戲（另有 Namco 2 款、Capcom 2 款、台灣非授權 1 款）的 ROM 逆向工程專案：解析人物資料、頭像、地圖等遊戲內容，並輸出 kaodata 統一格式資料集。

每款遊戲各放一個子資料夾，分析結果記在該資料夾的 `README.md` 與 `docs/`：

| 資料夾 | 遊戲 |
|--------|------|
| `sangokushi/` | 三國志 (KOEI, 1988, MMC1)：武將表、專屬頭像、大眾臉、漢字對照、58 國戰爭地圖、kaodata `san1-fc` |
| `suikoden/` | 水滸伝・天命の誓い (KOEI, 1990, MMC5)：人物、劇本、頭像（專屬＋組合臉）、州地圖、四季戰鬥地圖、kaodata `suikoden-fc` |
| `genchou/` | 蒼き狼と白き牝鹿・元朝秘史 (KOEI, 1993, MMC5)：人物（4 劇本）、國、兵科、交易品、頭像（專屬＋組合臉）、大地圖、47 張戰場地圖、kaodata `genchou-fc` |
| `genghis/` | 蒼き狼と白き牝鹿・ジンギスカン (KOEI, 1988, MMC1)：人物、后妃、頭像（專屬＋組合臉）、國、大地圖、41 張戰場地圖、kaodata `genghis-fc` |
| `mahjong/` | 麻雀大会 (KOEI, 1989, MMC1)：雀士 16 人（名牌）、頭像（15 人 × 7 表情＋玩家）、台詞 1320 句（42 場面）、AI 參數、麻將牌 34 種、kaodata `mahjong-fc` |
| `empereur/` | ランペルール (KOEI, 1991, MMC5)：人物（4 劇本，含性格）、國、46 都市、頭像（專屬＋組合臉）、大地圖、46 張戰場地圖、kaodata `lempe-fc` |
| `bushou/` | 信長の野望・武将風雲録 (KOEI, 1991, MMC5)：武將（2 劇本＋登場）、國、大名、茶器、頭像（專屬＋組合臉）、大地圖、野戰／城戰場地圖、kaodata `nobu4-fc` |
| `ishin/` | 維新の嵐 (KOEI, 1990, MMC5)：人物（2 劇本）、藩、地點、頭像（專屬＋組合臉）、HEX 地圖／全國大地圖、kaodata `ishin-fc` |
| `topman/` | ファミコントップマネジメント (KOEI, 1990, MMC1)：5 社（社長、部門人數、能力、製品性能、價格）、需要曲線、廣告費曲線、部門人物插圖、新聞圖、訊息文字（無頭像，不做 kaodata） |
| `gunyuu/` | 信長の野望・戦国群雄伝 (KOEI, 1990, MMC5)：武將（2 劇本）、38 國、大名、頭像（專屬＋組合臉）、大地圖、野戰／城戰場地圖、kaodata `nobu3-fc` |
| `zenkoku/` | 信長の野望・全国版 (KOEI, 1988, MMC1)：大名（50／17 國）、國、相鄰、頭像（大名＋姫 75 張）、地方地圖、戰場地圖、kaodata `nobu2-fc` |
| `royal/` | ロイヤルブラッド (KOEI, 1991, MMC5)：人物（4 劇本）、家、領地、第 5 部隊、頭像（人物 64＋相談役 4＋部隊 23）、戰略地圖、戰場 30 張、kaodata `royal-fc` |
| `daikoukai/` | 大航海時代 (KOEI, 1991, MMC5)：人物、航海士能力、頭像（專屬＋組合臉）、70 港口、世界地圖、港町圖、kaodata `koukai-fc` |
| `san2/` | 三國志II (KOEI, 1990, MMC5)：武將 352 人（6 劇本）、41 州（六角相鄰）、頭像（專屬＋組合臉）、大地圖、41 張戰場（可依直欄六角排法拼成全中國戰場圖）、kaodata `san2-fc` |
| `chuugen/` | 三國志 中原の覇者 (Namco, 1988, Namco 163)：武將、州、道路、頭像（共用整張臉 120 張＋表情）、大地圖、戰場地圖、kaodata `chuugen-fc` |
| `haou/` | 三國志II 覇王の大陸 (Namco, 1992, Namco 163)：武將（[EXT] 漢字）、州、君主、道具、頭像（共用整張臉＋5 表情）、大地圖、戰場地圖 30 張、kaodata `haou-fc` |
| `shenghuo/` | 聖火列傳 (C&E, 1991, mapper 240, 台灣非授權)：人物 13（5 章能力、武功）、道具、武功、敵人 30、遇敵表、頭像 36、字型對照、大地圖（標註 27 入口）＋23 張地圖；非光榮作品，不做 kaodata |
| `tenchi/` | 天地を喰らう (Capcom, 1989, MMC1)：武將 217 id（能力、兵士數成長）、頭像＋漢字名、道具／商店、策略 30、固定戰鬥 80、遇敵區域（章節）與名單、戰後報酬公式、台詞 886 段、大地圖＋99 個區域的地圖（出入口／寶箱）；非光榮作品，不做 kaodata |
| `tenchi2/` | 天地を喰らうII 諸葛孔明伝 (Capcom, 1991, MMC3)：武將 256（能力、ぶき、ちけい、策略群）、頭像＋漢字名、道具 120、商店、策略 54、經驗值、訊息 2048、遇敵、大地圖＋各地圖（標註門／傳送入口）；非光榮作品，不做 kaodata |

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
- 輸出 CSV 用 UTF-8-BOM（Excel 相容）
- 最上層與 `tools/` 的分工兩款不一致，刻意保留、不要統一：
  - `suikoden/`：最上層是執行入口與解碼核心 `rom.py`，`tools/` 只放輔助模組（模擬器）
  - `sangokushi/`：最上層是早期工具；`tools/` 混放正式入口（kaodata 匯出／驗證、`parts_sheet.py`）與研究用小工具

## RE 共通語言

@~/.claude/re-common.md

本 repo 路徑 ↔ 共通層名（`<game>` 指各遊戲資料夾）：

| 層 | 本 repo 路徑 |
|----|--------------|
| original | `roms/*.zip`（不進版控），各遊戲的程式直接讀 zip；分析時暫解到根目錄的 `.nes`，做完即刪 |
| references | 沒有固定位置；網址記在各遊戲 docs（例：`tenchi/docs/ROM_FORMAT.md` §11、`tenchi2/docs/ROM_FORMAT.md` §9） |
| captures | 沒有固定位置；`verify*.py` 在記憶體裡跑模擬器比對，不留截圖。既有的散在 `sangokushi/output/`（Mesen 截圖）與 `sangokushi/mob_portrait/screenshot/`（進版控） |
| extracted | `<game>/output/` 的 CSV／XLSX、頭像與零件 PNG、解碼出的地圖 |
| generated | `<game>/output/` 的總覽圖（`*_sheet.png`）、標註過的地圖（`world.png`、`maps/`）、拼貼頁（`strips.html`）；`sangokushi/mob_portrait/generated/`、`variant_explorer/`（進版控） |
| runtime | 沒有固定位置（py65 模擬器在記憶體裡跑，沒有模擬器設定檔） |
| export | kaodata dataset：`<game>/export_kaodata.py --out <kaodata>/data-local/<id>`；`sangokushi/output/san1-fc/` |
| docs | `<game>/README.md`、`<game>/docs/`、`<game>/data/`（人工抄錄、會被工具讀的對照表）、`BACKLOG.md`。根目錄 `docs/` 是 GitHub Pages 轉址頁，不是 docs 層 |
| tools | `<game>/` 最上層的 `rom.py`、`export*.py`、`verify*.py` 與 `<game>/tools/`；跨遊戲共用的是 `sangokushi/tools/`（`export_kaodata.py`、`parts_sheet.py`、`nes_emu.py`）與 `tenchi/strips_page.py` |

`<game>/output/` 混著 extracted、generated，有 kaodata 的 `sangokushi/output/` 還含 export；照共通語言 §1，不專程搬家。

## 上下游

依 `~/.claude/repos.md` 的跨 repo 協作規範（用 `handoff` skill）。

- **kaodata**（A 類）：光榮作品的頭像依 kaodata 的 `docs/data-format.md` 匯出；交接時附 revision 與驗證結果
- **素材站**（A 類，規劃中）：非光榮作品（中原の覇者、覇王の大陸、聖火列傳、天地を喰らう I／II）的素材
- **simagame**（B 類）：研究成果要做成推文或配圖時，交接單寫到 simagame 的 `inbox/`
