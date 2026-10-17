# 三國志II（FC, KOEI, 1990）

FC 版 1990 年 11 月 2 日發售（ja.wikipedia）。

ROM：`roms/Sangokushi II (Japan).zip`（MMC5，PRG 256 KB + CHR 256 KB）。程式直接從 zip 讀取，`--rom` 也接受 `.nes`。

格式細節見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 進度

- ✓ 武將 352 人：姓名、讀音、知武魅、義理、仁徳、野望、相性、一族、生年、頭像碼；每個劇本的所在州、忠誠、君主／在野旗標、登場年、初期兵士
- ✓ 6 劇本 × 41 州：金、兵糧、人口、勢力、民忠、土地、治水、馬、相場
- ✓ 州相鄰表：slot 就是六角方向，41 州、93 條邊可以完整放上六角格
- ✓ 大地圖（ROM 渲染）
- ✓ 頭像：專屬 200 張，組合臉（8 組 × 上半／下半／部件 A/B/C 各 4 種）
- ✓ kaodata 資料集 `san2-fc`（kaodata/1）：16 個代用字／截短的名字改成史書寫法（`export_kaodata.py` 的 `NAME_FIXES`，對照過 SFC 版 san2-sfc 的修正），另把張勳改成日本新字體的張勲（名字一律用新字體）；讀音照 san1-fc 在姓與名之間加空白（姓氏表 `sangokushi/data/surnames.tsv` 加上 `data/surnames.tsv`）。專屬頭像的 `code` 是頭像碼（= 頭像編號 + 1，4 位十六進位）；專屬頭像 F028、F178、F191 沒有武將使用，用途未知
- ✓ 41 張戰場地圖（13×12 六角格，7 種地形）
- ✓ **全中國戰場拼接**：把六角格扭成直欄（41→40→31 垂直疊起，隔欄錯開半張），41 張戰場的河流與地形就跨接縫接起來，輸出 `china_battle_map.png`（另有標州號的 `_labeled` 版，以及加上各州大致外框的 `_framed` 版）。原本的磚牆排法接不起來。證據見 ROM_FORMAT.md〈全中國戰場拼接測試〉
- … 未解：選單文字編碼、配置表 +1 byte、`0x28BE4` 佈陣 nibble 圖、道具／事件表

## 驗證

| 腳本 | 內容 | 結果 |
|------|------|------|
| `verify_kaodata_export.py` | 參考渲染器與 ROM 渲染逐 pixel 比對、checksums，以及模擬器裡換紀霊的頭像碼後比對 name table | 552/552、OK、474/474 |
| `verify_battle_maps.py` | 用每張圖蓋掉第 10 州的戰場資料，在模擬器開戰後比對 name table | 41/41 |
| `verify_scenarios.py` | 6 個劇本開局 WRAM 的州與武將資料，和 ROM 解碼結果比對 | 6/6 劇本全部相符 |

## 用法

```bash
.venv/bin/python san2/export.py                      # → san2/output/（CSV、XLSX、PNG）
.venv/bin/python san2/export_kaodata.py --out <kaodata>/data-local/san2-fc
.venv/bin/python san2/verify_kaodata_export.py --dataset <kaodata>/data-local/san2-fc   # 約 6 分鐘
.venv/bin/python san2/verify_battle_maps.py          # 約 2 分鐘
.venv/bin/python san2/verify_scenarios.py
.venv/bin/python san2/tools/stitch_test.py           # 戰場拼接測試
```

## 工具

- `rom.py`：ROM 解碼（表格位址、頭像、地圖、戰場）
- `tools/nes_emu.py`：py65 MMC5 模擬器，沿用 gunyuu 的版本，另外加了第 2 手把
- `tools/play.py`：從開機到指令畫面、武將頁、戰場的按鍵腳本（← 是 Y、→ 是 N）
- `tools/stitch_test.py`：六角格嵌入、接縫連續性與洗牌基準
