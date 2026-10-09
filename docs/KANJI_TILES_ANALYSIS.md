# 漢字 Tile 圖形分析

## 映射公式 (已確認)

透過 Mesen debugger 追蹤，確認了漢字 tile 的儲存位置：

```
Page 0: PRG_ROM_offset = 0x20004 + tile_id × 32
Page 1: PRG_ROM_offset = 0x22004 + tile_id × 32
File_offset = PRG_ROM_offset + 0x10 (iNES header)
```

| Page | 基址 (PRG) | 基址 (File) | 說明 |
|------|------------|-------------|------|
| Page 0 | 0x20004 | 0x20014 | 基本漢字 (241 個) |
| Page 1 | 0x22004 | 0x22014 | 擴展漢字 (66 個) |

- **每個 tile**: 8 bytes (只有 Plane 0)
- **每個漢字**: 32 bytes (4 tiles × 8 bytes)
- **Tile 排列**: `[0][1]` 在 offset+0, offset+8；`[2][3]` 在 offset+16, offset+24
- **Page 間距**: 0x2000 (8 KB)

### 特殊處理

ROM 中只儲存 Plane 0 (8 bytes/tile)。遊戲載入時將 Plane 0 複製到 Plane 1，
因此漢字只有黑白兩色（無灰階）。

### 驗證範例

「曹」字 (Page 0, tile_id = 0x8E):
- PRG ROM offset = 0x20004 + 0x8E × 32 = 0x211C4 ✓
- 4 tiles 位於: 0x211C4, 0x211CC, 0x211D4, 0x211DC (每個間隔 8 bytes)

「蔡」字 (Page 1, tile_id = 0x08):
- PRG ROM offset = 0x22004 + 0x08 × 32 = 0x22104 ✓
- 4 tiles 位於: 0x22104, 0x2210C, 0x22114, 0x2211C (每個間隔 8 bytes)

---

## 已確認資訊

### 姓名表結構 (0x3A314)
每筆記錄 15 bytes：
```
+0-7:   假名 (半角片假名, 8 bytes)
+8:     第一個漢字 tile ID
+9:     Page 指示器 (0=Page0, 1=Page1)
+10:    第二個漢字 tile ID
+11:    Page 指示器
+12:    第三個漢字 tile ID
+13:    Page 指示器
+14:    頭像索引 byte (portrait_index = byte - 1)
```

### 頭像索引說明
- Byte 14 儲存頭像索引 +1 的值
- 實際頭像索引 = byte_14 - 1
- 範圍: 0-80 (共 81 個頭像)

### Tile ID 分布

| Page | Tile ID 範圍 | 數量 | 說明 |
|------|-------------|------|------|
| Page 0 | 0x01-0xFF | 241 個 | 基本漢字 |
| Page 1 | 0x01-0x42 | 66 個 | 擴展漢字 |
| **總計** | | **307 個** | |

### 漢字規格
- 尺寸: 16×16 像素 (遊戲畫面觀察)
- 組成: 4 個 8×8 NES tiles
- 每個 tile: 8 bytes (只有 Plane 0，遊戲載入時複製到 Plane 1)
- 每個漢字: 32 bytes
- 顏色: 黑白兩色 (無灰階)

### 預估儲存空間
- Page 0: 241 × 32 = 7,712 bytes
- Page 1: 66 × 32 = 2,112 bytes
- 總計: ~9,824 bytes ≈ 9.6 KB

## 儲存位置

所有漢字都在 **Bank 8** (PRG 0x20000-0x23FFF / File 0x20010-0x2400F) 內。

### Page 0 漢字 (已確認)
- **漢字基址**: PRG 0x20004 / File 0x20014
- **範圍**: tile_id 0x01-0xFF (241 個漢字)
- **大小**: 241 × 32 = 7,712 bytes

### Page 1 漢字 (已確認)
- **漢字基址**: PRG 0x22004 / File 0x22014
- **範圍**: tile_id 0x01-0x42 (66 個漢字)
- **大小**: 66 × 32 = 2,112 bytes

### 其他資料
- **假名字體**: PRG 0x22C90 / File 0x22CA0 (同 Bank)

## 已解決問題

### ✓ Tile ID → ROM 偏移映射 (Page 0)
透過 Mesen debugger 追蹤「曹」字確認：
- 基址: `0x20004` (PRG ROM) / `0x20014` (檔案)
- 公式: `offset = base + tile_id × 32`
- 4 tiles 間隔 8 bytes 存放 (offset+0, +8, +16, +24)

### ✓ Page 1 漢字位置
透過 Mesen debugger 追蹤「蔡」字確認：
- 基址: `0x22004` (PRG ROM) / `0x22014` (檔案)
- 公式與 Page 0 相同，僅基址不同 (+0x2000)

## 追蹤方法 (已完成)

使用 **Mesen** 模擬器的 debug 功能：

1. 設定 PPU VRAM 寫入斷點 ($1BE0，「曹」字左上角 tile)
2. 追蹤到 tile 資料先存入 RAM ($04xx)
3. 再往上追蹤到 PRG ROM 讀取位置
4. 最終在 Memory Viewer 搜尋 tile 資料，找到 PRG ROM $211C4

## 漢字查詢方法

### 從 ROM 武將資料查詢漢字

```
┌─────────────────────────────────────────────────────────────┐
│  ROM 武將資料 (0x3A314 + index × 15)                         │
├─────────────────────────────────────────────────────────────┤
│  Bytes 0-7: 假名                                             │
│  Byte 8:  漢字1 Tile ID  ←─┐                                │
│  Byte 9:  漢字1 Page       │                                │
│  Byte 10: 漢字2 Tile ID    │  查表用的 key                   │
│  Byte 11: 漢字2 Page       │                                │
│  Byte 12: 漢字3 Tile ID  ←─┘                                │
│  Byte 13: 漢字3 Page                                        │
└─────────────────────────────────────────────────────────────┘
```

### Tile ID 拆解

Tile ID 的高 4 位為行，低 4 位為列：

```
Tile ID = 0xRC  →  第 R 行, 第 C 列

例: 0x8E = 第 8 行, 第 E 列 → 「曹」
```

### 查表步驟

1. 從 ROM 讀取 Tile ID 和 Page
2. 根據 Page 選擇對應的漢字表圖片
3. 用 Tile ID 的高 4 位找行 (左側標籤)
4. 用 Tile ID 的低 4 位找列 (上方標籤)
5. 行列交叉處即為對應漢字

### 範例: 曹操

```
ROM 資料: 8E 00 8D 00 00 00
         │  │  │  │
         │  │  │  └─ 漢字2 Page = 0
         │  │  └──── 漢字2 Tile ID = 0x8D
         │  └─────── 漢字1 Page = 0
         └────────── 漢字1 Tile ID = 0x8E

漢字1: 0x8E, Page 0 → 第 8 行第 E 列 → 「曹」
漢字2: 0x8D, Page 0 → 第 8 行第 D 列 → 「操」
```

---

## 相關檔案

| 檔案 | 說明 |
|------|------|
| `kanji_export.py` | 漢字圖形匯出工具 |
| `kanji_atlas_page0.png` | Page 0 字型表 (含座標標籤) |
| `kanji_atlas_page1.png` | Page 1 字型表 (含座標標籤) |
| `kanji_output/individual/kanji_p0_*.png` | Page 0 個別漢字 (241 個) |
| `kanji_output/individual/kanji_p1_*.png` | Page 1 個別漢字 (66 個) |

## 地名漢字

地名漢字與人名漢字使用**相同的映射公式**，存放於 Page 0 中未被人名使用的 tile ID。

### 地名專用 Tile IDs (14 個)

| Tile ID | 漢字 | 用途 |
|---------|------|------|
| 0x0B | 益 | 益州 |
| 0x3D | 荊 | 荊州 |
| 0x48 | 交 | 交州 |
| 0x63 | 州 | 各州 |
| 0x82 | 青 | 青州 |
| 0x96 | 代 | (其他) |
| 0xD7 | 幽 | 幽州 |
| 0xDA | 予 | 豫州 |
| 0xDB | 揚 | 揚州 |
| 0xE8 | 涼 | 涼州 |
| 0xED | 隸 | 司隸 |
| 0xF3 | 冀 | 冀州 |
| 0xF4 | 兗 | 兗州 |
| 0xF5 | 幷 | 并州 |

### 與人名共用的地名漢字

| 漢字 | 用途 |
|------|------|
| 徐 | 徐州 (人名: 徐庶、徐晃等) |
| 司 | 司隸 (人名: 司馬懿等) |

### 全部 13 州

荊州、青州、益州、徐州、揚州、幽州、冀州、兗州、豫州、涼州、并州、司隸、交州

---

## 後續工作

1. ~~使用模擬器 debug 功能追蹤實際 tile 載入~~ ✓
2. ~~確認 tile_id → ROM 偏移映射關係~~ ✓
3. ~~匯出所有漢字圖形~~ ✓
4. ~~追蹤 Page 1 漢字的 ROM 位置~~ ✓
5. ~~追蹤地名漢字的位置~~ ✓
6. ~~人工對照建立正確的漢字對照表~~ ✓ → `data/kanji_tiles.tsv`

## 漢字對照表 `data/kanji_tiles.tsv`

- key 是 **(page, tile_id)**：同一個 tile_id 在 Page 0 與 Page 1 是不同的字。`sangokushi_extract_v2.py` 的 `KANJI_TILE_MAP` 忽略 page，這是 `KANJI_DIFF.md` 大部分差異的原因。
- Page 1 的 tile_id 從 0x00 開始 (例：周瑜 = `62 00 00 01`)，所以只有 page 與 tile 都是 0 才表示「沒有字」。
- 共 308 字 (Page 0: 241 字，Page 1: 0x00-0x42 共 67 字)，覆蓋 255 名武將用到的所有 tile。
- 字以 ROM 字形為準 (新字體，例：関、黄、楽)。遊戲用了代用字的地方照字形記錄，並在 note 欄註明史書寫法，例如 許収 (攸)、旬攸 (荀)、李湛 (堪)、蔡仲 (中)、雷同 (銅)、鮑龍 (隆)、呂廣 (曠)、沙摩可 (柯)、刑道栄 (邢)。
