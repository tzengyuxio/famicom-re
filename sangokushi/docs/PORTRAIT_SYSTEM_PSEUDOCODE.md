# 標準頭像系統 Pseudo Code

本文件說明標準頭像系統 (portrait_id 0-80) 從武將姓名表的 portrait_id 到 tile 拼接的完整流程。

## 資料結構定義

```
POINTER_TABLE_ADDR  = 0x1BC38    // 81 entries × 4 bytes
ARRANGEMENT_ADDR    = 0x1B0D4    // 81 entries × 36 bytes

// 注意: 每個 portrait_id 在排列表中都有對應的 36 bytes
// 包括 36-tile 標準排列頭像 (其排列資料與標準 2×2 metatile 一致)
// 因此不需要特判，直接從排列表讀取即可
```

### 標準 2×2 Metatile 排列參考

36-tile 頭像使用的排列模式 (已存於排列表中，無需硬編碼):
```
[ 1  2][ 5  6][ 9 10]
[ 3  4][ 7  8][11 12]
[13 14][17 18][21 22]
[15 16][19 20][23 24]
[25 26][29 30][33 34]
[27 28][31 32][35 36]
```

## 步驟一: 從武將獲取 portrait_index

```
function get_portrait_index(character_index):
    // 姓名表位置: 0x3A314, 每筆 15 bytes
    name_record_addr = 0x3A314 + character_index * 15
    portrait_byte = ROM[name_record_addr + 14]
    return portrait_byte - 1   // 轉換為 0-based index
```

遊戲只在 portrait_index < 65 時走本文件的流程（p-code `$EB51`：byte 14 < 66 才呼叫 `$EC58` 畫專屬頭像），65 以上一律是大眾臉（見 MOB_PORTRAIT_SYSTEM_PSEUDOCODE.md）。所以指標表雖有 81 筆，武將只用到 P00–P64；P65–P80 是 16 張女性頭像，是君主的姫（ひめ）。外交聯姻時，派出使者前會出現自己的姫，台詞是「ひめ を よめに やる」；頭像由勢力編號算出（見下）。

`$EC58` 另有兩處直接呼叫：bank 2 `$A93D`（嫁自己的姫）、bank 3 `$8C2D`。兩處都用同一個算式，從君主所屬的勢力算出頭像：

```
f = 使者武將資料 +11（我方勢力編號，1 起）
W = word[$7109 + 48 * (f - 1)]     // 勢力表第 f 筆的 +2，開局都是 3
姫的頭像 = P65 + ((3 * f - W) mod 16)
```

p-code（bank 2，`0D` 是取參數，即派出的使者的武將資料指標，WRAM `$6001` + 17 × 編號）：

```
0D 7B D3 D1 8B 30 B5 8C 09 71 BB B0 B3    push word[$7109 + 48 * (byte[p + 11] - 1)]
0D 7B D3 53 B5 B4 BC 8B 10 B9 B3          A = (3 * byte[p + 11] - pop) mod 16; push A
8D 10 62 E9 58 EC 08                       call $EC58
```

VM opcode：

| opcode | 作用 |
|------|------|
| `0D` | A = 參數 |
| `7x` | A += x |
| `D3` | A = byte[A] |
| `D1` | A −= 1 |
| `8B` | B = imm8 |
| `8C` | B = imm16 |
| `B5` | A ×= B |
| `BB` | A += B |
| `BC` | A −= B |
| `B9` | A = A mod B |
| `B0` | A = word[A] |
| `B3` | push A |
| `B4` | pop 到 B |

把 0–15 換成 P65 起算這一步是用截圖對出來的，`$EC58` 內部沒有細讀。

勢力表：WRAM `$7107` 起，每筆 48 bytes，第 f 筆對應勢力 f。劇本 1 的初始值在 ROM `0x3911A`。

| 偏移 | 內容 |
|------|------|
| 0–1 | 君主（u16）：低位 = 武將編號；高位 1 = 可選君主。劇本 4、5 的曹操是 `0x501`，高位 5 的意思未知 |
| 2–3 | W，開局都是 3。推測是「還沒出嫁的姫的數量」：每個勢力 3 位姫，依序是 3f−3、3f−2、3f−1（mod 16） |
| 4–17 | 14 個 `0x32`（未知） |
| 18 | 未知，65–87。原本誤認為頭像編號，劇本 2 劉璋的截圖推翻了這個判斷 |
| 19 | 未知的序號 |

驗證：
- 兩張 Mesen 截圖都和 ROM 解碼逐像素一致（2304/2304），也符合算式。
- 模擬器照實機操作走一遍：指令 10 → 第一個對象 → 第一個使者 → 3 こんいん。在 `$EC58` 下斷點，再比對畫面上的臉。
  - 改 W：3、2、1 依序畫出 P65、P66、P67；W = 0 時不畫姫。
  - 改使者的勢力：2、5、7、14 依序畫出 P68、P77、P67、P72，全部符合算式。

| 劇本 | 君主 | 勢力 | 算式 | 頭像 |
|------|------|------|------|------|
| 1 | 曹操 | 1 | (3 − 3) mod 16 = 0 | P65 |
| 2 | 劉璋 | 7 | (21 − 3) mod 16 = 2 | P67 |

W 是否真的每嫁一次減 1，還沒在實際連續聯姻中看過；改 W 的實驗只證明了算式。

各劇本的勢力數（WRAM `$6001` 起的武將資料 +11）：

| 劇本 | 年 | 勢力數 |
|------|------|------|
| 1 | 189 | 14 |
| 2 | 195 | 13 |
| 3 | 201 | 7 |
| 4 | 208 | 10 |
| 5 | 215 | 4 |

## 步驟二: 獲取 tile 資料位置

```
function get_tile_data_location(portrait_index):
    pointer_addr = POINTER_TABLE_ADDR + portrait_index * 4

    bank       = ROM[pointer_addr + 0]        // 資料所在 bank (4-6)
    tile_count = ROM[pointer_addr + 1]        // tile 數量 (28-36)
    addr_lo    = ROM[pointer_addr + 2]        // bank 內位址低位
    addr_hi    = ROM[pointer_addr + 3]        // bank 內位址高位

    bank_addr = addr_hi * 256 + addr_lo       // 組合為 16-bit 位址

    // 計算 ROM 檔案偏移
    file_offset = bank * 0x4000 + (bank_addr - 0x8000) + 0x10

    return {
        file_offset: file_offset,
        tile_count: tile_count
    }
```

## 步驟三: 讀取 tile 資料

```
function load_tiles(file_offset, tile_count):
    tiles = []
    for i in range(tile_count):
        tile_data = ROM[file_offset + i * 16 : file_offset + (i+1) * 16]
        tiles.append(tile_data)  // 每個 tile 16 bytes
    return tiles
```

## 步驟四: 獲取排列

```
function get_arrangement(portrait_index):
    // 所有頭像都可以直接從排列表讀取
    // (36-tile 標準排列頭像的資料也存於排列表中)
    arr_addr = ARRANGEMENT_ADDR + portrait_index * 36
    arrangement = []

    for row in range(6):
        row_tiles = []
        for col in range(6):
            ppu_value = ROM[arr_addr + row * 6 + col]
            rom_tile_num = ppu_value - 0x63   // PPU 值轉 ROM tile 編號
            row_tiles.append(rom_tile_num)
        arrangement.append(row_tiles)

    return arrangement
```

## 步驟五: 繪製頭像

```
function render_portrait(character_index):
    portrait_index = get_portrait_index(character_index)

    // 獲取 tile 資料
    location = get_tile_data_location(portrait_index)
    tiles = load_tiles(location.file_offset, location.tile_count)

    // 獲取排列方式
    arrangement = get_arrangement(portrait_index)

    // 建立 48×48 像素畫布
    canvas = new_canvas(48, 48)

    // 按排列繪製 6×6 tiles (共 36 個位置)
    for row in range(6):
        for col in range(6):
            tile_num = arrangement[row][col]
            tile_data = tiles[tile_num - 1]   // tile 編號是 1-based

            // 計算繪製位置
            x = col * 8
            y = row * 8

            draw_tile(canvas, x, y, tile_data)

    return canvas
```

## 繪製順序說明

頭像 6×6 格子繪製順序 (左到右, 上到下):

```
    ┌────┬────┬────┬────┬────┬────┐
    │  0 │  1 │  2 │  3 │  4 │  5 │  Row 0
    ├────┼────┼────┼────┼────┼────┤
    │  6 │  7 │  8 │  9 │ 10 │ 11 │  Row 1
    ├────┼────┼────┼────┼────┼────┤
    │ 12 │ 13 │ 14 │ 15 │ 16 │ 17 │  Row 2
    ├────┼────┼────┼────┼────┼────┤
    │ 18 │ 19 │ 20 │ 21 │ 22 │ 23 │  Row 3
    ├────┼────┼────┼────┼────┼────┤
    │ 24 │ 25 │ 26 │ 27 │ 28 │ 29 │  Row 4
    ├────┼────┼────┼────┼────┼────┤
    │ 30 │ 31 │ 32 │ 33 │ 34 │ 35 │  Row 5
    └────┴────┴────┴────┴────┴────┘
```

繪製公式:
```
position = row * 6 + col
x_pixel = col * 8
y_pixel = row * 8
```

## 範例: 劉備 (character_index = 3)

1. **獲取 portrait_index**
   ```
   portrait_byte = ROM[0x3A314 + 3*15 + 14] = 0x01
   portrait_index = 0x01 - 1 = 0
   ```

2. **查詢指標表** [0x1BC38]
   ```
   bank = 4, tile_count = 32, addr = 0x8000
   file_offset = 4 * 0x4000 + 0 + 0x10 = 0x10010
   ```

3. **查詢排列表** [0x1B0D4]
   ```
   portrait_index=0 不在 STANDARD_36_PORTRAITS
   讀取 36 bytes 排列資料
   ```

4. **載入 tiles**
   ```
   載入 32 個 tiles (每個 16 bytes, 共 512 bytes)
   ```

5. **繪製**
   ```
   依排列逐格繪製 6×6 = 36 個位置
   ```

## 重點總結

1. **兩層間接**: 姓名表 → portrait_index → 指標表/排列表
2. **統一的排列表**: 所有 81 個頭像都有對應的 36 bytes 排列資料
   - 36-tile 標準排列頭像：排列表中存的就是標準 2×2 metatile 排列
   - <36-tile 頭像：排列表中存的是自訂排列 (有 tile 重複利用)
   - **結論：無需特判，直接從排列表讀取即可**
3. **tile 編號轉換**: PPU 值 (0x64+) 轉為 ROM tile 編號 (-0x63)
4. **繪製順序**: 左到右、上到下，每格 8×8 像素

## 相關檔案

- `MEMORY.md` - 詳細的逆向工程研究記錄
- `portrait_export.py` - 實際實作的頭像匯出工具
- `docs/DATA_FORMAT.md` - 武將資料表格式規格
