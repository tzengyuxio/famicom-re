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
