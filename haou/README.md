# FC 三國志II 覇王の大陸 解析

Namco，1992，FC（mapper 19 = Namco 163，PRG 256 KB、CHR-ROM 256 KB、電池）。是 `chuugen/`（中原の覇者）的續作，
但引擎、文字編碼、資料格式都不同，從頭分析（6502 原生碼）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 武將、州、君主、道具、戰場、頭像 PNG、大地圖、戰場地圖 → haou/output/
.venv/bin/python haou/export.py [--rom ROM] [--out DIR] [--scale N]

# kaodata 統一格式資料集 haou-fc
.venv/bin/python haou/export_kaodata.py --out <kaodata>/data-local/haou-fc
# 驗證：模擬器逐人跑遊戲的頭像程式比對（另比對開機後君主選擇畫面上的劉備臉），並重算 checksums（需 py65）
.venv/bin/python haou/verify_kaodata_export.py --dataset <輸出目錄>
# 驗證：模擬器開新局、實際出陣，30 張戰場逐張讓遊戲載入後比對名稱表；大地圖比對名稱表與城 sprite（需 py65，約 1 分鐘）
.venv/bin/python haou/verify_battle_maps.py
```

ROM 預設直接讀 `roms/Sangokushi II - Haou no Tairiku (Japan).zip`（`--rom` 也接受 .nes 或 .zip）。
依賴：Pillow；openpyxl（可選，匯出 .xlsx）；py65（驗證用）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：文字（tile 編號）、武將、州、相鄰、城座標、道具名、頭像（sprite）、大地圖、戰場 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | kaodata 資料集 `haou-fc` 與參考渲染器 |
| `verify_kaodata_export.py` | 資料集的模擬器驗證 |
| `verify_battle_maps.py` | 戰場／大地圖解碼與遊戲本身畫面的比對 |
| `tools/nes_emu.py` | Namco 163 整機模擬（py65，取自 `chuugen/`）：開機、按鍵、截圖、單獨呼叫副程式 |
| `data/kanji_names.tsv` | [EXT] 武將漢字（讀音比對 san1-fc／chuugen-fc＋人工判讀，附來源欄） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `generals.csv` | 237 人：片假名姓名、[EXT] 漢字、体、武、知、忠、徳、経、レベル、軍種（平／山／水）、兵、武器、防具、身分（在野／仕官）、所在州、勢力、頭像 |
| `provinces.csv` | 30 州：漢字名（遊戲字形）、讀音、君主、太守、金、米、人口、土地、産業、防災、統治度、武將、兵士、相鄰州、城座標 |
| `lords.csv` | 7 位君主與開局領地 |
| `items.csv` | 32 種道具（武器 0-23、防具 24-31）與開局持有者 |
| `battle_maps.csv` | 30 張戰場：32×20 metatile 編號、使用的 4 個區塊 |
| `haou.xlsx` | 以上各表 |
| `faces/` | 每位武將一張 32×40 頭像（表情 0） |
| `portraits/` | 183 張不重複頭像 F000-F182，各 5 種表情（`_e0`-`_e4`）＋說話嘴形（`_talk`） |
| `map.png` | 大地圖 256×160（含各君主顏色的城；左上年月框是地圖名稱表本身的一部分） |
| `battle_maps/` | 30 張戰場 512×320（被攻州的地圖） |

劇本只有 189 年 1 月一個，可選君主 7 位（董卓、袁紹、曹操、孫策、劉備、劉璋、馬騰）。頭像是 237 人共用 183 張的
完整臉（每張臉自帶 5 種表情，不是組合臉），所以沒有大眾臉零件輸出。

## 外部資料

- [renote.net](https://renote.net/articles/2022)：本作為 1992 年 FC 版、『中原の覇者』的續作。
- [ナムコアンソロジー（ja.wikid.org）](https://ja.wikid.org/%E3%83%8A%E3%83%A0%E3%82%B3%E3%82%A2%E3%83%B3%E3%82%BD%E3%83%AD%E3%82%B8%E3%83%BC)：
  PS『ナムコアンソロジー1』（1998）收錄本作。
- 君主選擇畫面上的城數（劉備×1、曹操×2、孫策×4、袁紹×3、馬騰×3、劉璋×4、董卓×2）與開局州資料的君主欄一致。
- `data/kanji_names.tsv`（[EXT]）：遊戲只有片假名姓名。227 名有漢字：讀音與 `sangokushi/` san1-fc 或 `chuugen/`
  的漢字對照一致者照用（同音多名者依能力值／勢力選定，如ソンケン＝孫権、チョウコウ＝張郃），其餘依三國志演義人名
  人工判讀；10 名（オウケン、ギキョ、ギラン、シカン、ジンソウ、チョウゲツ、テイヘイ、バンイク、リュウヘイ、リケイ）留空。
