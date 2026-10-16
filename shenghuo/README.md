# FC 聖火列傳 解析

Computer & Entertainment（C&E，台灣），1991，非授權 FC 卡匣（A-1061；外部資料：製作 Guo Qiyong、監督 Zheng Yi）。元末、聖火教
背景的中文 RPG，玩家是「少主」。mapper 240，PRG 128 KB、CHR-ROM 128 KB。不是 KOEI 作品，引擎從頭分析
（6502 原生碼）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 人物、武功、道具、敵人、遇敵、頭像、字型對照、大地圖與各地圖 → shenghuo/output/
.venv/bin/python shenghuo/export.py [--rom ROM] [--out DIR]

# 驗證：模擬器跑遊戲的地圖進入程式與欄／屬性建構程式，比對 24 張地圖（約 30 秒，需 py65）
.venv/bin/python shenghuo/verify_maps.py
# 驗證：模擬器跑遊戲的頭像程式（個人資料 13 張精靈、對話 36 張 BG），比對畫面（約 40 秒，需 py65）
.venv/bin/python shenghuo/verify_portraits.py
```

ROM 預設直接讀 `roms/Sheng Huo Lie Zhuan (Asia) (Unl).zip`（`--rom` 也接受 .nes）。
依賴：Pillow；openpyxl（可選，匯出 .xlsx）；py65（驗證用）。沒有 kaodata 匯出（非光榮作品）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：字串表、字形、人物章節能力、武功、敵人、遇敵、頭像、地圖（metatile、屬性、入口） |
| `text.py` | 字碼 → 字對照（CHR bank 0、9 兩套字型的人工轉寫，自動檢查一致性） |
| `export.py` | 匯出 CSV（UTF-8-BOM）／XLSX／PNG |
| `verify_maps.py` | 地圖解碼與遊戲程式的比對 |
| `verify_portraits.py` | 頭像解碼與遊戲程式的比對 |
| `tools/nes_emu.py` | mapper 240 整機模擬（沿用 `chuugen/tools/nes_emu.py`，加 bank 切換、水平鏡像、逐掃描線 `$2000`） |

## 輸出

| 檔案 | 內容 |
|------|------|
| `characters.csv` | 13 人：姓名、武功與習得等級（id 4 = 少主） |
| `chapter_stats.csv` | 5 章 × 各人加入時的等級、力量、敏捷、HP、MP |
| `skills.csv` | 人物 × 武功 × 習得等級 |
| `items.csv` | 19 武器、9 消耗品、28 武功名 |
| `enemies.csv` | 30 種敵人：名稱、HP、其他 4 項能力（部分意義推定） |
| `encounters.csv` | 等級 1-10 的遇敵組合（左隊、右隊） |
| `portraits.csv` | 36 張頭像（0-12 隊伍成員，13-35 其他說話者） |
| `entrances.csv` | 大地圖 27 個入口：M1-M20 地圖、T1-T7 城鎮 |
| `maps.csv` | 24 張地圖的尺寸與地形類別 |
| `font00.csv`、`font09.csv` | 字碼 → 字（108 + 119 字） |
| `shenghuo.xlsx` | 以上各表 |
| `maps/world.png` | 大地圖整張 2304 × 1440（9 × 6 畫面，不分區） |
| `maps/world_labelled.png` | 大地圖 2× 並標出 M／T 入口 |
| `maps/map01-23.png` | 各地圖（21-23 是地圖 1 的後期版本） |
| `portraits/dialog/`、`portraits/status/` | 對話頭像 36 張、個人資料頭像 13 張（32 × 40），另有兩張總覽 |
| `text/group00.png`、`text/group09.png` | 字串組 0、9 的字形圖（轉寫依據） |

## 進度

- [x] 遊戲身分、mapper 240、跨 bank 呼叫
- [x] 文字機制（1bpp 雙 plane 字形、依 CHR bank 的字型頁、字串表）；組 0、9 已轉寫
- [x] 人物 13 人：姓名、章節初始能力、武功與習得等級
- [x] 頭像 36 張（含 CHR bank、調色盤選擇），模擬器驗證 49/49
- [x] 大地圖與 23 張地圖、metatile、屬性、地形類別、27 個入口，模擬器驗證
- [x] 敵人 30 種（名稱、HP、能力表）、遇敵表
- [ ] 其餘 18 組字串（對話、商店）的字型與轉寫；說話者 13-35 的姓名
- [ ] 武器攻擊力、武功 MP／威力、敵人其餘欄位意義、勝利獎勵
- [ ] 商店品項與價格、劇情戰對手
