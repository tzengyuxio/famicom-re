#!/usr/bin/env python3
"""
Update explorer HTML to use raw tile data instead of Base64 images.
"""

import os
import re

def main():
    # Read tile_data.js
    with open("tile_data.js", "r") as f:
        tile_data = f.read()

    # Read current HTML
    # The published page (docs/) now redirects to kaodata; keep updating the retired copy here.
    html_path = "mob-kao-explorer.html"
    with open(html_path, "r") as f:
        html = f.read()

    # New embedded data section with tile rendering functions
    new_data = '''// === EMBEDDED DATA START ===
        // Raw NES tile data (16 bytes = 32 hex chars per tile)

        const PALETTE = [
          [0, 0, 0],        // Index 0: Black
          [247, 216, 165],  // Index 1: Light skin
          [234, 158, 34],   // Index 2: Dark skin
          [255, 255, 255],  // Index 3: White
        ];

'''

    # Extract HEAD_TILES from tile_data.js
    head_match = re.search(r'const HEAD_TILES = \[(.+?)\];', tile_data, re.DOTALL)
    if head_match:
        new_data += f'        const HEAD_TILES = [{head_match.group(1)}];\n\n'

    # Extract TEMPLATES
    tmpl_match = re.search(r'const TEMPLATES = \[(.+?)\];', tile_data, re.DOTALL)
    if tmpl_match:
        new_data += f'        const TEMPLATES = [{tmpl_match.group(1)}];\n\n'

    # Extract EYE_TILES
    eye_match = re.search(r'const EYE_TILES = \[(.+?)\];', tile_data, re.DOTALL)
    if eye_match:
        new_data += f'        const EYE_TILES = [{eye_match.group(1)}];\n\n'

    # Extract NOSE_TILES
    nose_match = re.search(r'const NOSE_TILES = \[(.+?)\];', tile_data, re.DOTALL)
    if nose_match:
        new_data += f'        const NOSE_TILES = [{nose_match.group(1)}];\n\n'

    # Extract MOUTH_TILES
    mouth_match = re.search(r'const MOUTH_TILES = \[(.+?)\];', tile_data, re.DOTALL)
    if mouth_match:
        new_data += f'        const MOUTH_TILES = [{mouth_match.group(1)}];\n\n'

    new_data += '''        // Decode NES tile from hex string (16 bytes = 32 hex chars)
        function decodeTile(hexStr) {
            const bytes = [];
            for (let i = 0; i < 32; i += 2) {
                bytes.push(parseInt(hexStr.substr(i, 2), 16));
            }
            const pixels = [];
            for (let y = 0; y < 8; y++) {
                const row = [];
                const plane0 = bytes[y];
                const plane1 = bytes[y + 8];
                for (let x = 7; x >= 0; x--) {
                    const bit0 = (plane0 >> x) & 1;
                    const bit1 = (plane1 >> x) & 1;
                    row.push(bit0 + (bit1 << 1));
                }
                pixels.push(row);
            }
            return pixels;
        }

        // Draw a single tile on canvas at (x, y) with given scale
        function drawTile(ctx, hexStr, x, y, scale) {
            const pixels = decodeTile(hexStr);
            for (let py = 0; py < 8; py++) {
                for (let px = 0; px < 8; px++) {
                    const colorIdx = pixels[py][px];
                    const [r, g, b] = PALETTE[colorIdx];
                    ctx.fillStyle = `rgb(${r},${g},${b})`;
                    ctx.fillRect(x + px * scale, y + py * scale, scale, scale);
                }
            }
        }

        // Draw multiple tiles horizontally
        function drawTilesHorizontal(ctx, tiles, x, y, scale) {
            tiles.forEach((tile, i) => {
                drawTile(ctx, tile, x + i * 8 * scale, y, scale);
            });
        }

        // Draw 6 mouth tiles in 3x2 grid
        function drawMouthTiles(ctx, tiles, x, y, scale) {
            // Layout: [0,1,4], [2,3,5]
            const layout = [[0, 1, 4], [2, 3, 5]];
            for (let row = 0; row < 2; row++) {
                for (let col = 0; col < 3; col++) {
                    const tileIdx = layout[row][col];
                    drawTile(ctx, tiles[tileIdx], x + col * 8 * scale, y + row * 8 * scale, scale);
                }
            }
        }

        // Create a canvas element with tiles rendered
        function createTileCanvas(tiles, width, height, scale) {
            const canvas = document.createElement('canvas');
            canvas.width = width * scale;
            canvas.height = height * scale;
            canvas.style.imageRendering = 'pixelated';
            const ctx = canvas.getContext('2d');

            if (height === 16) {
                // Mouth tiles (3x2 grid)
                drawMouthTiles(ctx, tiles, 0, 0, scale);
            } else {
                // Eye or nose tiles (horizontal)
                drawTilesHorizontal(ctx, tiles, 0, 0, scale);
            }
            return canvas;
        }

        // === EMBEDDED DATA END ==='''

    # Replace the embedded data section
    pattern = r'// === EMBEDDED DATA START ===.*?// === EMBEDDED DATA END ==='
    html = re.sub(pattern, new_data, html, flags=re.DOTALL)

    # Update HEADS to use TEMPLATES
    # Replace the old HEADS definition
    old_heads_pattern = r"const HEADS = \[[\s\S]*?\];\s*const VARIANT_COUNTS"
    html = re.sub(old_heads_pattern, "const VARIANT_COUNTS", html)

    # Update updateVariantSelector to use tile canvas
    old_selector = '''function updateVariantSelector(type, dataObj) {
            const container = document.getElementById(`${type}-selector`);
            container.innerHTML = ''; // Clear existing
            const isMouth = type === 'mouths';
            const baseIdx = getCurrentCat() * 5;
            const currentVal = type === 'eyes' ? currentEyes : (type === 'noses' ? currentNoses : currentMouths);

            for (let i = 0; i < 5; i++) {
                const globalIdx = baseIdx + i;
                const item = document.createElement('div');
                item.className = 'variant-item' + (i === currentVal ? ' selected' : '');
                item.innerHTML = `
                    <img src="${dataObj[globalIdx]}" width="72" height="${isMouth ? 48 : 24}">
                    <span>#${i}</span>
                `;
                item.onclick = () => selectVariant(type, i);
                container.appendChild(item);
            }
        }'''

    new_selector = '''function updateVariantSelector(type, tilesArr) {
            const container = document.getElementById(`${type}-selector`);
            container.innerHTML = ''; // Clear existing
            const isMouth = type === 'mouths';
            const baseIdx = getCurrentCat() * 5;
            const currentVal = type === 'eyes' ? currentEyes : (type === 'noses' ? currentNoses : currentMouths);

            for (let i = 0; i < 5; i++) {
                const globalIdx = baseIdx + i;
                const item = document.createElement('div');
                item.className = 'variant-item' + (i === currentVal ? ' selected' : '');

                const tiles = tilesArr[globalIdx];
                const canvas = createTileCanvas(tiles, 24, isMouth ? 16 : 8, 3);
                item.appendChild(canvas);

                const span = document.createElement('span');
                span.textContent = `#${i}`;
                item.appendChild(span);

                item.onclick = () => selectVariant(type, i);
                container.appendChild(item);
            }
        }'''

    html = html.replace(old_selector, new_selector)

    # Update variant selector calls
    html = html.replace("updateVariantSelector('eyes', EYES)", "updateVariantSelector('eyes', EYE_TILES)")
    html = html.replace("updateVariantSelector('noses', NOSES)", "updateVariantSelector('noses', NOSE_TILES)")
    html = html.replace("updateVariantSelector('mouths', MOUTHS)", "updateVariantSelector('mouths', MOUTH_TILES)")

    # Update updatePreview to use tile rendering
    old_preview = '''async function updatePreview() {
            const canvas = document.getElementById('portrait-canvas');
            const ctx = canvas.getContext('2d');
            ctx.imageSmoothingEnabled = false;

            // Clear canvas
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, 288, 288);

            const scale = 6;
            const cat = getCurrentCat();

            // Calculate global indices for variants
            const globalEyes = cat * 5 + currentEyes;
            const globalNoses = cat * 5 + currentNoses;
            const globalMouths = cat * 5 + currentMouths;

            try {
                // Draw framework (currentHead is now global)
                const frameworkImg = await loadImage(FRAMEWORKS[currentHead]);
                ctx.drawImage(frameworkImg, 0, 0, 288, 288);

                // Draw variants in their positions based on template
                // Eyes go in row 2, columns 1-3
                const eyesImg = await loadImage(EYES[globalEyes]);
                ctx.drawImage(eyesImg, 8 * scale, 16 * scale, 24 * scale, 8 * scale);

                // Noses go in row 3, columns 1-3
                const nosesImg = await loadImage(NOSES[globalNoses]);
                ctx.drawImage(nosesImg, 8 * scale, 24 * scale, 24 * scale, 8 * scale);

                // Mouths go in rows 4-5, columns 1-3
                const mouthsImg = await loadImage(MOUTHS[globalMouths]);
                ctx.drawImage(mouthsImg, 8 * scale, 32 * scale, 24 * scale, 16 * scale);'''

    new_preview = '''function updatePreview() {
            const canvas = document.getElementById('portrait-canvas');
            const ctx = canvas.getContext('2d');
            ctx.imageSmoothingEnabled = false;

            // Clear canvas
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, 288, 288);

            const scale = 6;
            const cat = getCurrentCat();

            // Calculate global indices for variants
            const globalEyes = cat * 5 + currentEyes;
            const globalNoses = cat * 5 + currentNoses;
            const globalMouths = cat * 5 + currentMouths;

            // Draw head framework using TEMPLATES and HEAD_TILES
            const template = TEMPLATES[currentHead];
            const headTiles = HEAD_TILES[currentHead];

            for (let row = 0; row < 6; row++) {
                for (let col = 0; col < 6; col++) {
                    const tileIdx = template[row][col];
                    if (tileIdx !== null && tileIdx < headTiles.length) {
                        drawTile(ctx, headTiles[tileIdx], col * 8 * scale, row * 8 * scale, scale);
                    }
                }
            }

            // Draw variants in their positions
            // Eyes go in row 2, columns 1-3
            drawTilesHorizontal(ctx, EYE_TILES[globalEyes], 8 * scale, 16 * scale, scale);

            // Noses go in row 3, columns 1-3
            drawTilesHorizontal(ctx, NOSE_TILES[globalNoses], 8 * scale, 24 * scale, scale);

            // Mouths go in rows 4-5, columns 1-3
            drawMouthTiles(ctx, MOUTH_TILES[globalMouths], 8 * scale, 32 * scale, scale);'''

    html = html.replace(old_preview, new_preview)

    # Remove the old try-catch block's catch part (no longer needed since no async)
    html = html.replace("} catch (e) {\n                console.error('Preview error:', e);\n            }", "")

    # Remove unused loadImage function and imageCache
    html = re.sub(r'const imageCache = \{\};\s*', '', html)
    html = re.sub(r'// Load image from embedded data\s+function loadImage\(dataUrl\) \{[\s\S]*?return img;\s+\}\);\s+\}', '', html)

    # Remove HEAD_TO_PATTERN (no longer needed in same way)
    # Keep HEADS for grid info - need to transform it

    # Update head hover preview to use canvas
    old_hover = '''function showHeadPreview(e, idx) {
            const preview = document.getElementById('head-preview');
            preview.querySelector('img').src = FRAMEWORKS[idx];
            preview.querySelector('.label').textContent = `H${idx.toString().padStart(2, '0')}`;

            // Position near mouse
            preview.style.display = 'block';
            preview.style.left = (e.clientX + 20) + 'px';
            preview.style.top = (e.clientY - 50) + 'px';
        }'''

    new_hover = '''function showHeadPreview(e, idx) {
            const preview = document.getElementById('head-preview');
            const container = preview.querySelector('.preview-canvas-container') || preview;

            // Create or update canvas for preview
            let canvas = preview.querySelector('canvas');
            if (!canvas) {
                // First time: replace img with canvas
                const img = preview.querySelector('img');
                if (img) img.remove();
                canvas = document.createElement('canvas');
                canvas.width = 144;
                canvas.height = 144;
                canvas.style.imageRendering = 'pixelated';
                container.insertBefore(canvas, preview.querySelector('.label'));
            }

            // Draw head preview
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, 144, 144);

            const template = TEMPLATES[idx];
            const headTiles = HEAD_TILES[idx];
            const scale = 3;

            for (let row = 0; row < 6; row++) {
                for (let col = 0; col < 6; col++) {
                    const tileIdx = template[row][col];
                    if (tileIdx !== null && tileIdx < headTiles.length) {
                        drawTile(ctx, headTiles[tileIdx], col * 8 * scale, row * 8 * scale, scale);
                    }
                }
            }

            preview.querySelector('.label').textContent = `H${idx.toString().padStart(2, '0')}`;

            // Position near mouse
            preview.style.display = 'block';
            preview.style.left = (e.clientX + 20) + 'px';
            preview.style.top = (e.clientY - 50) + 'px';
        }'''

    html = html.replace(old_hover, new_hover)

    # Update HTML structure for head preview (remove img, will be replaced by canvas)
    html = html.replace(
        '<div class="head-preview" id="head-preview">\n            <img src="" width="144" height="144">',
        '<div class="head-preview" id="head-preview" class="preview-canvas-container">'
    )

    # Fix HEADS reference in grid display - need to keep the grid info
    # Add a HEADS object that contains grid info
    heads_grid_data = '''
        // Head grid info (for grid overlay display)
        const HEADS = TEMPLATES.map((grid, idx) => ({
            idx: idx,
            grid: grid
        }));

'''
    # Insert after TEMPLATES
    html = html.replace(
        'const VARIANT_COUNTS',
        heads_grid_data + '        const VARIANT_COUNTS'
    )

    # Write updated HTML
    with open(html_path, "w") as f:
        f.write(html)

    print(f"Updated {html_path}")

    # Check new file size
    new_size = os.path.getsize(html_path)
    print(f"New file size: {new_size:,} bytes ({new_size / 1024:.1f} KB)")


if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
