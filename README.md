# famicom-re

FC／NES 歷史策略遊戲（KOEI 為主，另有 2 款 Namco、2 款 Capcom、1 款台灣非授權）的 ROM 逆向工程：解析人物、頭像（專屬＋組合臉）、地圖、攻略數值，並匯出 [kaodata](https://kaodata.simagame.me) 統一格式資料集（kaodata/1）。

每款遊戲一個資料夾，指令、輸出檔、進度寫在該資料夾的 `README.md`，ROM 格式（含未解部分）寫在 `docs/`。

## 遊戲

| 資料夾 | 遊戲 | 發行 | Mapper | kaodata |
|--------|------|------|--------|---------|
| [`zenkoku/`](zenkoku/) | 信長の野望・全国版 | KOEI 1988 | MMC1 | `nobu2-fc` |
| [`sangokushi/`](sangokushi/) | 三國志 | KOEI 1988 | MMC1 | `san1-fc` |
| [`genghis/`](genghis/) | 蒼き狼と白き牝鹿・ジンギスカン | KOEI 1988 | MMC1 | `genghis-fc` |
| [`mahjong/`](mahjong/) | 麻雀大会 | KOEI 1989 | MMC1 | `mahjong-fc` |
| [`gunyuu/`](gunyuu/) | 信長の野望・戦国群雄伝 | KOEI 1990 | MMC5 | `nobu3-fc` |
| [`suikoden/`](suikoden/) | 水滸伝・天命の誓い | KOEI 1990 | MMC5 | `suikoden-fc` |
| [`ishin/`](ishin/) | 維新の嵐 | KOEI 1990 | MMC5 | `ishin-fc` |
| [`san2/`](san2/) | 三國志II | KOEI 1990 | MMC5 | `san2-fc` |
| [`topman/`](topman/) | ファミコントップマネジメント | KOEI 1990 | MMC1 | —（無頭像） |
| [`daikoukai/`](daikoukai/) | 大航海時代 | KOEI 1991 | MMC5 | `koukai-fc` |
| [`empereur/`](empereur/) | ランペルール | KOEI 1991 | MMC5 | `lempe-fc` |
| [`royal/`](royal/) | ロイヤルブラッド | KOEI 1991 | MMC5 | `royal-fc` |
| [`bushou/`](bushou/) | 信長の野望・武将風雲録 | KOEI 1991 | MMC5 | `nobu4-fc` |
| [`genchou/`](genchou/) | 蒼き狼と白き牝鹿・元朝秘史 | KOEI 1993 | MMC5 | `genchou-fc` |
| [`chuugen/`](chuugen/) | 三國志 中原の覇者 | Namco 1988 | Namco 163 | `chuugen-fc` |
| [`haou/`](haou/) | 三國志II 覇王の大陸 | Namco 1992 | Namco 163 | `haou-fc` |
| [`shenghuo/`](shenghuo/) | 聖火列傳 | C&E 1991（台灣非授權） | Mapper 240 | —（非光榮） |
| [`tenchi/`](tenchi/) | 天地を喰らう | Capcom 1989 | MMC1 | —（非光榮） |
| [`tenchi2/`](tenchi2/) | 天地を喰らうII 諸葛孔明伝 | Capcom 1991 | MMC3 | —（非光榮） |

發行年是 FC 版日本發售年，依發售順序排列（非光榮作品放最後）。光榮 FC 共 14 款，已全部解析；發售日對照 ja.wikipedia 與 [fc.game-kit.net 光榮 FC 一覧](https://fc.game-kit.net/fc-db/fc-s/?fc-maker=%E5%85%89%E6%A0%84)，水滸伝另對照 ROM 內的版權字串，見各資料夾 README。

## 環境

- ROM 放 `roms/`（不進版控），程式直接讀 zip；分析時解出的 `.nes` 用完即刪。
- Python 一律用 `.venv/bin/python`，依賴 Pillow、openpyxl、py65（模擬器驗證用）。
- lint：`uvx ruff check --line-length 120 <檔案或資料夾>`

```bash
# 例：匯出並驗證 kaodata 資料集
.venv/bin/python zenkoku/export_kaodata.py --out <kaodata>/data-local/nobu2-fc
.venv/bin/python zenkoku/verify_kaodata_export.py --dataset <kaodata>/data-local/nobu2-fc
```

各遊戲的 kaodata 匯出共用 `sangokushi/tools/export_kaodata.py` 的參考渲染器；頭像等解碼都有獨立驗證（模擬器跑遊戲本身的程式、截圖或 Mesen 紀錄）。外部資料（不是從 ROM 解出來的，例如中文譯名）欄位名加 `[EXT]`。

`docs/` 是 GitHub Pages，只剩兩個大眾臉探索器的轉址頁（已搬到 kaodata.simagame.me）。待辦見 [BACKLOG.md](BACKLOG.md)。
