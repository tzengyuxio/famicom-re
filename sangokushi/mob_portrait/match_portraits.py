#!/usr/bin/env python3
"""
Match screenshot portraits to find correct Group and variant indices.
"""

import os
from PIL import Image
import numpy as np

SCREENSHOT_DIR = "screenshot"
EXPLORER_ASSETS = "variant_explorer/assets"

# Palette for comparison (convert to grayscale-ish for simpler matching)
PALETTE = {
    (0, 0, 0): 0,
    (247, 216, 165): 1,
    (234, 158, 34): 2,
    (255, 255, 255): 3,
}

def load_image_as_array(path):
    """Load image and convert to numpy array."""
    img = Image.open(path).convert('RGB')
    return np.array(img)

def extract_region(img_array, row_start, row_end, col_start, col_end, scale=1):
    """Extract a region from the image array."""
    return img_array[row_start*scale:row_end*scale, col_start*scale:col_end*scale]

def compare_images(img1, img2):
    """Compare two images and return similarity score (0-1)."""
    if img1.shape != img2.shape:
        # Resize if needed
        min_shape = (min(img1.shape[0], img2.shape[0]),
                     min(img1.shape[1], img2.shape[1]), 3)
        img1 = img1[:min_shape[0], :min_shape[1]]
        img2 = img2[:min_shape[0], :min_shape[1]]

    diff = np.abs(img1.astype(int) - img2.astype(int))
    similarity = 1 - (np.sum(diff) / (img1.size * 255))
    return similarity

def find_best_match(target_region, variant_dir, variant_prefix, count=20):
    """Find the best matching variant for a target region."""
    best_match = -1
    best_score = 0
    scores = []

    for i in range(count):
        variant_path = os.path.join(variant_dir, f"{variant_prefix}_{i:02d}.png")
        if os.path.exists(variant_path):
            variant_img = load_image_as_array(variant_path)
            score = compare_images(target_region, variant_img)
            scores.append((i, score))
            if score > best_score:
                best_score = score
                best_match = i

    # Sort by score and get top 3
    scores.sort(key=lambda x: -x[1])
    return best_match, best_score, scores[:3]

def find_best_framework(target_img, frameworks_dir, count=19):
    """Find the best matching framework for a target image."""
    best_match = -1
    best_score = 0
    scores = []

    # Extract framework regions (rows 0-1, and edge columns)
    # Scale is 3 in the assets (24x24 pixels per 8x8 tile region)
    scale = 3

    # Top 2 rows (full width)
    target_top = target_img[:16*scale, :]

    for i in range(count):
        framework_path = os.path.join(frameworks_dir, f"framework_{i:02d}.png")
        if os.path.exists(framework_path):
            framework_img = load_image_as_array(framework_path)
            framework_top = framework_img[:16*scale, :]

            score = compare_images(target_top, framework_top)
            scores.append((i, score))
            if score > best_score:
                best_score = score
                best_match = i

    scores.sort(key=lambda x: -x[1])
    return best_match, best_score, scores[:3]

def analyze_screenshot(screenshot_path, assets_dir):
    """Analyze a screenshot and find matching indices."""
    name = os.path.splitext(os.path.basename(screenshot_path))[0]
    print(f"\n{'='*60}")
    print(f"分析: {name}")
    print(f"{'='*60}")

    # Load screenshot
    img = load_image_as_array(screenshot_path)
    print(f"圖片大小: {img.shape}")

    # Determine scale (screenshot might be different size)
    # Expected: 48x48 base, but screenshots might be scaled
    height, width = img.shape[:2]
    scale = height // 48
    print(f"推測縮放比例: {scale}x")

    # Find best framework match
    framework_match, fw_score, fw_top3 = find_best_framework(
        img, assets_dir, 19
    )
    print(f"\n框架匹配: G{framework_match:02d} (相似度: {fw_score:.3f})")
    print(f"  Top 3: {[(f'G{g:02d}', f'{s:.3f}') for g, s in fw_top3]}")

    # Extract variant regions from screenshot
    # Eyes: row 2 (pixels 16-24), cols 1-3 (pixels 8-32)
    # Faces: row 3 (pixels 24-32), cols 1-3 (pixels 8-32)
    # Mouths: rows 4-5 (pixels 32-48), cols 1-3 (pixels 8-32)

    eyes_region = img[16*scale:24*scale, 8*scale:32*scale]
    faces_region = img[24*scale:32*scale, 8*scale:32*scale]
    mouths_region = img[32*scale:48*scale, 8*scale:32*scale]

    # Find best matches for each variant
    variants_dir = os.path.join(assets_dir, "variants")

    eyes_match, eyes_score, eyes_top3 = find_best_match(
        eyes_region, os.path.join(variants_dir, "eyes"), "eyes"
    )
    print(f"\n眼睛匹配: #{eyes_match} (相似度: {eyes_score:.3f})")
    print(f"  Top 3: {[(f'#{i}', f'{s:.3f}') for i, s in eyes_top3]}")

    faces_match, faces_score, faces_top3 = find_best_match(
        faces_region, os.path.join(variants_dir, "faces"), "faces"
    )
    print(f"\n臉部匹配: #{faces_match} (相似度: {faces_score:.3f})")
    print(f"  Top 3: {[(f'#{i}', f'{s:.3f}') for i, s in faces_top3]}")

    mouths_match, mouths_score, mouths_top3 = find_best_match(
        mouths_region, os.path.join(variants_dir, "mouths"), "mouths"
    )
    print(f"\n嘴巴匹配: #{mouths_match} (相似度: {mouths_score:.3f})")
    print(f"  Top 3: {[(f'#{i}', f'{s:.3f}') for i, s in mouths_top3]}")

    return {
        "name": name,
        "group": framework_match,
        "eyes": eyes_match,
        "faces": faces_match,
        "mouths": mouths_match,
        "scores": {
            "group": fw_score,
            "eyes": eyes_score,
            "faces": faces_score,
            "mouths": mouths_score,
        }
    }

def main():
    assets_dir = EXPLORER_ASSETS

    # Find all screenshots
    screenshots = []
    for f in os.listdir(SCREENSHOT_DIR):
        if f.endswith('.png') and not f.startswith('.'):
            screenshots.append(os.path.join(SCREENSHOT_DIR, f))

    screenshots.sort()
    print(f"找到 {len(screenshots)} 個截圖")

    results = []
    for screenshot in screenshots:
        result = analyze_screenshot(screenshot, assets_dir)
        results.append(result)

    # Print summary
    print("\n" + "="*60)
    print("匹配結果摘要")
    print("="*60)
    print(f"{'名稱':<10} {'Group':<8} {'Eyes':<6} {'Faces':<6} {'Mouths':<6}")
    print("-"*60)
    for r in results:
        print(f"{r['name']:<10} G{r['group']:02d}     #{r['eyes']:<4} #{r['faces']:<4} #{r['mouths']:<4}")

    # Generate JavaScript-ready output
    print("\n" + "="*60)
    print("JavaScript 格式 (可直接複製到 explorer)")
    print("="*60)
    print("const KNOWN_COMBINATIONS = [")
    for r in results:
        print(f'    {{ name: "{r["name"]}", group: {r["group"]}, eyes: {r["eyes"]}, faces: {r["faces"]}, mouths: {r["mouths"]} }},')
    print("];")

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    main()
