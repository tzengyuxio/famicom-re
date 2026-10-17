# FC 麻雀大会 解析

KOEI，1989（FC 1989-10-31），FC（MMC1，CHR-RAM）。ROM 結構與各表格式見 [docs/ROM_FORMAT.md](docs/ROM_FORMAT.md)。

## 指令

```bash
# 雀士、台詞、AI 參數、牌、頭像／名牌／牌 PNG → mahjong/output/
.venv/bin/python mahjong/export.py [--rom ROM] [--out DIR] [--scale N]

# kaodata 統一格式資料集 mahjong-fc
.venv/bin/python mahjong/export_kaodata.py --out <kaodata>/data-local/mahjong-fc
# 驗證：逐 pixel 比對 ROM 直接組出的臉、重算 checksums；裝了 py65 會再讓遊戲本身畫出 106 張臉來比對（約 15 秒，--no-emu 略過）
.venv/bin/python mahjong/verify_kaodata_export.py --dataset <輸出目錄>
```

ROM 預設直接讀 `roms/Mahjong Taikai (Japan).zip`（`--rom` 也接受 .nes 或 .zip）。
依賴：Pillow；openpyxl（可選，匯出 .xlsx）；py65（可選，驗證時跑模擬器）。

## 檔案

| 檔案 | 用途 |
|------|------|
| `rom.py` | ROM 解碼：頭像（7 種表情）、名牌、文字碼、台詞、AI 參數、麻將牌 |
| `export.py` | 匯出 CSV／XLSX／PNG |
| `export_kaodata.py` | kaodata 資料集 `mahjong-fc` 與參考渲染器 |
| `verify_kaodata_export.py` | 資料集的獨立驗證（含模擬器） |
| `tools/emu.py` | 沿用 `sangokushi/tools/nes_emu.py`（MMC1＋py65），改成 8 個 PRG bank，補上 APU frame IRQ（本作在 IRQ 裡讀手把），加上進 雀荘 畫面的按鍵腳本 |

## 輸出

| 檔案 | 內容 |
|------|------|
| `players.csv` | 16 位雀士：名牌、`[EXT]FullName`（人物全名）、頭像色盤、tile 數、表情數、AI 參數 P0–P7 |
| `speech.csv` | 1320 句台詞（15 人 × 88 句）：句號、場面號（42 個）、`[EXT]Situation_Guess`（從台詞內容推測的場面）、種類與對應表情、兩行文字 |
| `tiles.csv` | 34 種牌的牌碼與名稱 |
| `mahjong.xlsx` | 以上各表（需 openpyxl） |
| `portraits/PNN_E_名_表情.png` | 106 張頭像（32×32）：15 人 × 7 種表情＋玩家的「You」 |
| `faces.png` | 全部頭像一覽（每列一人、每欄一種表情） |
| `names.png` | 16 個名牌（32×16 字形） |
| `tiles.png` | 34 種牌＋牌背、空白、側面（16×24） |

kaodata 資料集：15 人（電腦對手），全部用專屬頭像；106 張頭像，P0–P104 = 雀士 × 7 + 表情（就是遊戲的排版號），P105 是玩家的臉（`group`「プレイヤー」）。`face` 是表情 0（平常），`expressions` 依序放說話 1、說話 2、怒、哀、喜、驚，各帶 `label`（說話是嘴型動畫，怒／哀／喜／驚是台詞種類換的臉，見 ROM_FORMAT.md §2.2）。遊戲由座位上的雀士與表情算出排版號，沒有另存頭像值，所以頭像不填 `code`。名字照名牌寫（信長、楊妃…）；ROM 沒有讀音，名牌全是片假名的 5 人（シブサワ・コウ 等）給平假名 `reading`。沒有中文版，不填 `nameZh`；`title.zh`「麻雀大會」由使用者確認（2026-10-17；沒有官方中文版）。像素存 NES 色號，色盤是 NES 64 色。

本作沒有組合臉，所以不輸出大眾臉零件；也沒有地圖或場地資料。

## 進度

- ✓ MMC1 bank 配置、APU IRQ 讀手把、線性位址指標（`$E7FA`）
- ✓ 頭像：16 個 tile 池、105 筆排版、色盤旗標；模擬器 105/105＋玩家一致；kaodata `mahjong-fc`
- ✓ 名牌字形 16 個（抄寫成文字）
- ✓ 8×8 字型與文字碼（含濁音合成）；台詞 1320 句、種類→表情、42 場面的句數表；畫面對照 1 句
- ✓ AI 參數表 15 × 8（P1/P2/P4/P5 在有人立直時的調整已解）
- ✓ 麻將牌 34 種的 tile 組合與 CHR（對局畫面 122 個 tile 一致）
- 未完成：見 ROM_FORMAT.md §7（場面號的意義、AI 參數其餘欄位、規則與 雀荘／大会 的資料、16×16 漢字字形與役名表）
