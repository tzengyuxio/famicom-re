# 大眾臉頭像系統 Pseudo Code

本文件說明大眾臉頭像系統 (portrait_id 81-254) 的結構與繪製流程。

## 系統概要

| 項目 | 標準頭像系統 | 大眾臉頭像系統 |
|------|--------------|----------------|
| 索引範圍 | 0-80 (81 個) | 81-254 (174 個) |
| 結構 | 完整獨立頭像 | 共用框架 + 可替換組件 |
| Tile 資料 | Banks 4-6 | Bank 7 |
| 排列表 | 0x1B0D4 (81 條) | 0x1ED14 (20 條) |
| 組件索引表 | — | 0x1F034 (174 條 × 5 bytes) |

## 組件式結構

大眾臉頭像由三部分組成：
1. **共用框架** (頭盔、邊框) — 同 Head 內共用
2. **可替換組件** (眼睛、鼻子、嘴巴) — 每個頭像不同
3. **Head 基底** — 決定 tile 資料的 ROM 位置

```
6×6 格子 Layout:
     C0  C1  C2  C3  C4  C5
    ┌───┬───┬───┬───┬───┬───┐
 R0 │ F │ F │ F │ F │ F │ F │  ← 框架 (共用)
    ├───┼───┼───┼───┼───┼───┤
 R1 │ F │ F │ F │ F │ F │ F │  ← 框架 (共用)
    ├───┼───┼───┼───┼───┼───┤
 R2 │ F │ E │ E │ E │ F │ F │  ← 眼睛區 (C1-C3 可替換)
    ├───┼───┼───┼───┼───┼───┤
 R3 │ F │ N │ N │ N │ F │ F │  ← 鼻子區 (C1-C3 可替換)
    ├───┼───┼───┼───┼───┼───┤
 R4 │ F │ M │ M │ M │ F │ F │  ← 嘴巴上 (C1-C3 可替換)
    ├───┼───┼───┼───┼───┼───┤
 R5 │ F │ M │ M │ M │ F │ F │  ← 嘴巴下 (C1-C3 可替換)
    └───┴───┴───┴───┴───┴───┘

F = 框架 tile (固定, 由 Head 決定)
E = 眼睛 tile (可替換)
N = 鼻子 tile (可替換)
M = 嘴巴 tile (可替換)
```

## 資料結構定義

```
// ─── 組件索引表 (已確認, 2026-02-28) ───
// 透過 Mesen Lua 追蹤腳本實際監視遊戲讀取行為驗證
COMPONENT_TABLE = 0x1F034      // 174 筆 × 5 bytes = 870 bytes
COMPONENT_TABLE_END = 0x1F389

// 每筆 5 bytes: [Cat, Head, Eye, Nose, Mouth]
// Cat: 0-3 (分類), 其餘: 0-4 (分類內索引)
// 索引公式: addr = 0x1F034 + (portrait_index - 81) * 5

// 全域索引轉換公式 (0-19):
//   global = cat * 5 + local
// 例: Cat=3, Head=0 → head_global = 3*5+0 = 15 → 使用 H15

// ─── 排列模板表 (20 條 × 36 bytes) ───
TEMPLATE_TABLE = 0x1ED14
// 每個 byte: 0x00 = 變體位置, 其餘 val - 0x64 = tile 編號

// ─── 20 個 Head 框架 (ROM 偏移, 各 24 tiles) ───
HEADS = [
    0x1C014,  // H00       0x1C794,  // H05       0x1CF14,  // H10       0x1D694,  // H15
    0x1C194,  // H01       0x1C914,  // H06       0x1D094,  // H11       0x1D814,  // H16
    0x1C314,  // H02       0x1CA94,  // H07       0x1D214,  // H12       0x1D994,  // H17
    0x1C494,  // H03       0x1CC14,  // H08       0x1D394,  // H13       0x1DB14,  // H18
    0x1C614,  // H04       0x1CD94,  // H09       0x1D514,  // H14       0x1DC94,  // H19
]

// Head → Template: 1:1 對應 (head_global = template_index)

// ─── 變體 Tile 資料位置 ───
EYES_START   = 0x1DE14    // 20 組 × 3 tiles × 16 bytes = 960 bytes
NOSES_START  = 0x1E1D4    // 20 組 × 3 tiles × 16 bytes = 960 bytes
MOUTHS_START = 0x1E594    // 20 組 × 6 tiles × 16 bytes = 1920 bytes
```

## 繪製流程

### 步驟一: 讀取組件索引

```
function get_mob_portrait_params(portrait_index):
    offset = 0x1F034 + (portrait_index - 81) * 5
    cat   = ROM[offset + 0]   // 0-3
    head  = ROM[offset + 1]   // 0-4
    eye   = ROM[offset + 2]   // 0-4
    nose  = ROM[offset + 3]   // 0-4
    mouth = ROM[offset + 4]   // 0-4

    // 轉換為全域索引 (0-19)
    head_g  = cat * 5 + head
    eye_g   = cat * 5 + eye
    nose_g  = cat * 5 + nose
    mouth_g = cat * 5 + mouth

    return { head_g, eye_g, nose_g, mouth_g }
```

### 步驟二: 讀取排列模板

```
function read_template(head_global):
    offset = 0x1ED14 + head_global * 36
    grid = 6×6 array

    for row in 0..5:
        for col in 0..5:
            val = ROM[offset + row * 6 + col]
            if val == 0:
                grid[row][col] = VARIANT  // 變體位置
            else:
                grid[row][col] = val - 0x64  // 框架 tile 編號
    return grid
```

### 步驟三: 載入 Tile 資料

```
function load_tiles(head_g, eye_g, nose_g, mouth_g):
    // 框架 tiles (24 個)
    head_base = HEADS[head_g]
    head_tiles = read_rom_tiles(head_base, 24)

    // 眼睛 tiles (3 個)
    eye_tiles = read_rom_tiles(EYES_START + eye_g * 3 * 16, 3)

    // 鼻子 tiles (3 個)
    nose_tiles = read_rom_tiles(NOSES_START + nose_g * 3 * 16, 3)

    // 嘴巴 tiles (6 個)
    mouth_tiles = read_rom_tiles(MOUTHS_START + mouth_g * 6 * 16, 6)

    return { head_tiles, eye_tiles, nose_tiles, mouth_tiles }
```

### 步驟四: 組合並繪製

```
function render_mob_portrait(portrait_index):
    params = get_mob_portrait_params(portrait_index)
    template = read_template(params.head_g)
    tiles = load_tiles(params.head_g, params.eye_g, params.nose_g, params.mouth_g)

    canvas = new_canvas(48, 48)

    for row in 0..5:
        for col in 0..5:
            cell = template[row][col]

            if cell != VARIANT:
                // 框架 tile
                pixel_data = tiles.head_tiles[cell]
            else:
                // 變體 tile (cols 1-3 of rows 2-5)
                vc = col - 1   // variant column: 0, 1, 2
                if row == 2:   // 眼睛
                    pixel_data = tiles.eye_tiles[vc]
                elif row == 3: // 鼻子
                    pixel_data = tiles.nose_tiles[vc]
                elif row == 4: // 嘴巴上
                    pixel_data = tiles.mouth_tiles[[0, 1, 4][vc]]
                elif row == 5: // 嘴巴下
                    pixel_data = tiles.mouth_tiles[[2, 3, 5][vc]]

            draw_tile(canvas, col * 8, row * 8, pixel_data)

    return canvas
```

### 嘴巴 Tile 排列說明

嘴巴每組 6 tiles，ROM 中連續存放 [0,1,2,3,4,5]，
但在 6×6 格子中的排列為：

```
ROM 順序:  0  1  2  3  4  5
格子位置:
  R4 (上): [0] [1] [4]   → C1, C2, C3
  R5 (下): [2] [3] [5]   → C1, C2, C3
```

## 驗證紀錄

以下透過 Mesen 模擬器實際追蹤遊戲讀取行為確認：

| P_ID | 武將 | Cat | Head | Eye | Nose | Mouth | head_g | 驗證方式 |
|------|------|-----|------|-----|------|-------|--------|----------|
| P081 | 周泰 | 3 | 0 | 2 | 3 | 1 | H15 | Mesen trace ✓ |
| P085 | 曹豹 | 2 | 0 | 1 | 3 | 1 | H10 | Mesen trace, 5 欄位全部吻合 ✓ |
| P157 | 陳登 | 2 | 2 | 4 | 2 | 4 | H12 | 探索器建立頭像與遊戲截圖完全一致 ✓ |

### 驗證過程

1. 建立 Mesen Lua 追蹤腳本 (`tools/mesen_portrait_trace.lua`)
2. 監視 CPU 從 Bank 7 組件索引表區域的讀取操作
3. 確認遊戲每次渲染頭像時，從 `$B024` (ROM `$1F034`) 讀取 5 bytes
4. 確認索引方式為 `portrait_index - 81` (非 char_index - 39)
5. 確認欄位順序為 `[Cat, Head, Eye, Nose, Mouth]`

## ROM 空間配置

```
Bank 7 ($8000-$BFFF → ROM 0x1C010-0x1FFFF):

0x1C014-0x1DDF3  Head 框架 tiles (H00-H19, 各 24 tiles × 16 bytes)
0x1DE14-0x1E1D3  眼睛變體 (20 組 × 3 tiles × 16 bytes = 960 bytes)
0x1E1D4-0x1E593  鼻子變體 (20 組 × 3 tiles × 16 bytes = 960 bytes)
0x1E594-0x1ED13  嘴巴變體 (20 組 × 6 tiles × 16 bytes = 1920 bytes)
0x1ED14-0x1EFC3  排列模板表 (20 條 × 36 bytes = 720 bytes)
0x1F034-0x1F389  組件索引表 (174 條 × 5 bytes = 870 bytes)
```

## 相關檔案

| 檔案 | 用途 |
|------|------|
| `mob_portrait_export.py` | 大眾臉頭像批量匯出 (174 筆 PNG) |
| `mob_component_extract.py` | 組件索引表匯出 (CSV) |
| `tools/mesen_portrait_trace.lua` | Mesen 追蹤腳本 (用於驗證) |
| `tools/portrait_generator.py` | 單張頭像產生工具 |
| `mob_portrait/variant_explorer/` | 大眾臉頭像互動探索器 |
| `portrait_export.py` | 標準頭像匯出工具 (P00-P80) |
| `docs/PORTRAIT_SYSTEM_PSEUDOCODE.md` | 標準頭像系統 pseudo code |
