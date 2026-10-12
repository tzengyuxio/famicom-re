#!/usr/bin/env python3
"""
Extract raw tile data from ROM and generate compact JavaScript data.
Each tile is stored as 32 hex characters (16 bytes).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from romfile import read_rom

# 20 Heads - all have 24 tiles
HEADS = [
    0x1C014, 0x1C194, 0x1C314, 0x1C494, 0x1C614,  # H00-H04
    0x1C794, 0x1C914, 0x1CA94, 0x1CC14, 0x1CD94,  # H05-H09
    0x1CF14, 0x1D094, 0x1D214, 0x1D394, 0x1D514,  # H10-H14
    0x1D694, 0x1D814, 0x1D994, 0x1DB14, 0x1DC94,  # H15-H19
]

EYES_START = 0x1DE14    # 20 variants × 3 tiles
NOSES_START = 0x1E1D4   # 20 variants × 3 tiles
MOUTHS_START = 0x1E594  # 20 variants × 6 tiles
TEMPLATE_START = 0x1ED14  # 20 templates × 36 bytes


def read_tiles(rom_data, offset, count):
    """Read tiles and return as list of hex strings."""
    tiles = []
    for i in range(count):
        tile_data = rom_data[offset + i * 16 : offset + (i + 1) * 16]
        tiles.append(tile_data.hex())
    return tiles


def read_template(rom_data, template_idx):
    """Read a 36-byte template and return as 6x6 grid."""
    offset = TEMPLATE_START + template_idx * 36
    template = rom_data[offset:offset + 36]
    grid = []
    for row in range(6):
        row_data = []
        for col in range(6):
            val = template[row * 6 + col]
            if val == 0:
                row_data.append(None)  # Variant position
            else:
                row_data.append(val - 0x64)  # Fixed tile index
        grid.append(row_data)
    return grid


def main():
    rom_data = read_rom()

    # Extract all tile data
    head_tiles = []
    templates = []
    for i, addr in enumerate(HEADS):
        tiles = read_tiles(rom_data, addr, 24)
        head_tiles.append(tiles)
        templates.append(read_template(rom_data, i))

    eye_tiles = []
    for i in range(20):
        tiles = read_tiles(rom_data, EYES_START + i * 3 * 16, 3)
        eye_tiles.append(tiles)

    nose_tiles = []
    for i in range(20):
        tiles = read_tiles(rom_data, NOSES_START + i * 3 * 16, 3)
        nose_tiles.append(tiles)

    mouth_tiles = []
    for i in range(20):
        tiles = read_tiles(rom_data, MOUTHS_START + i * 6 * 16, 6)
        mouth_tiles.append(tiles)

    # Generate JavaScript
    js_lines = []
    js_lines.append("// === TILE DATA START ===")
    js_lines.append("// Raw NES tile data (16 bytes = 32 hex chars per tile)")
    js_lines.append("")
    js_lines.append("const PALETTE = [")
    js_lines.append('  [0, 0, 0],        // Index 0: Black')
    js_lines.append('  [247, 216, 165],  // Index 1: Light skin')
    js_lines.append('  [234, 158, 34],   // Index 2: Dark skin')
    js_lines.append('  [255, 255, 255],  // Index 3: White')
    js_lines.append("];")
    js_lines.append("")

    # Head tiles (20 heads × 24 tiles)
    js_lines.append("const HEAD_TILES = [")
    for i, tiles in enumerate(head_tiles):
        js_lines.append(f'  // H{i:02d}')
        tile_strs = ', '.join(f'"{t}"' for t in tiles)
        js_lines.append(f'  [{tile_strs}],')
    js_lines.append("];")
    js_lines.append("")

    # Templates
    js_lines.append("const TEMPLATES = [")
    for i, tmpl in enumerate(templates):
        grid_str = str(tmpl).replace("None", "null")
        js_lines.append(f'  {grid_str},  // T{i:02d}')
    js_lines.append("];")
    js_lines.append("")

    # Eye tiles (20 × 3 tiles)
    js_lines.append("const EYE_TILES = [")
    for i, tiles in enumerate(eye_tiles):
        tile_strs = ', '.join(f'"{t}"' for t in tiles)
        js_lines.append(f'  [{tile_strs}],  // E{i:02d}')
    js_lines.append("];")
    js_lines.append("")

    # Nose tiles (20 × 3 tiles)
    js_lines.append("const NOSE_TILES = [")
    for i, tiles in enumerate(nose_tiles):
        tile_strs = ', '.join(f'"{t}"' for t in tiles)
        js_lines.append(f'  [{tile_strs}],  // N{i:02d}')
    js_lines.append("];")
    js_lines.append("")

    # Mouth tiles (20 × 6 tiles)
    js_lines.append("const MOUTH_TILES = [")
    for i, tiles in enumerate(mouth_tiles):
        tile_strs = ', '.join(f'"{t}"' for t in tiles)
        js_lines.append(f'  [{tile_strs}],  // M{i:02d}')
    js_lines.append("];")
    js_lines.append("")
    js_lines.append("// === TILE DATA END ===")

    # Write to file
    output_path = "tile_data.js"
    with open(output_path, "w") as f:
        f.write("\n".join(js_lines))

    print(f"Generated {output_path}")

    # Calculate sizes
    total_tiles = 20 * 24 + 20 * 3 + 20 * 3 + 20 * 6
    raw_bytes = total_tiles * 16
    hex_chars = total_tiles * 32
    print(f"Total tiles: {total_tiles}")
    print(f"Raw data: {raw_bytes} bytes")
    print(f"Hex string: {hex_chars} chars (~{hex_chars // 1024} KB)")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
