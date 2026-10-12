#!/usr/bin/env python3
"""Draw every composite-face part of a kaodata dataset on one sheet (needs Pillow).

One row per variant, one column group per slot, items in dataset order.
Transparent pixels show as grey. Works for any kaodata/1 dataset with `composite`
(san1-fc, suikoden-fc).

Usage: .venv/bin/python sangokushi/tools/parts_sheet.py --dataset <dir> --out parts.png [--scale N]
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export_kaodata import get_image, load_dataset, to_rgba

GAP, LABEL_W, LABEL_H = 4, 40, 14
BG, CELL_BG, TEXT = (255, 255, 255), (160, 160, 160), (0, 0, 0)


def parts_sheet(meta: dict, blobs: list[bytes], scale: int) -> Image.Image:
    colors = meta["palettes"][0]["colors"]
    comp = meta["composite"]
    slots = [s["id"] for s in comp["slots"]]

    def image_of(item) -> int:
        return item if isinstance(item, int) else item["img"]

    # cell size per slot = largest item of that slot over all variants
    size = {s: [0, 0] for s in slots}
    count = {s: 0 for s in slots}
    for v in comp["variants"]:
        for s in slots:
            items = v["parts"][s]["items"]
            count[s] = max(count[s], len(items))
            for it in items:
                w, h, _ = get_image(meta, blobs, image_of(it))
                size[s] = [max(size[s][0], w), max(size[s][1], h)]
    row_h = max(h for _, h in size.values()) * scale + GAP
    group_w = {s: count[s] * (size[s][0] * scale + GAP) + GAP for s in slots}
    width = LABEL_W + sum(group_w.values())
    sheet = Image.new("RGB", (width, LABEL_H + row_h * len(comp["variants"]) + GAP), BG)
    draw = ImageDraw.Draw(sheet)

    x = LABEL_W
    for s in slots:
        draw.text((x + GAP, 1), s, fill=TEXT)
        x += group_w[s]
    for r, v in enumerate(comp["variants"]):
        y = LABEL_H + r * row_h + GAP
        draw.text((2, y), f"#{v['id']}", fill=TEXT)
        x = LABEL_W
        for s in slots:
            cw, ch = size[s][0] * scale, size[s][1] * scale
            for i, it in enumerate(v["parts"][s]["items"]):
                cx = x + GAP + i * (cw + GAP)
                draw.rectangle([cx, y, cx + cw - 1, y + ch - 1], fill=CELL_BG)
                src = get_image(meta, blobs, image_of(it))
                img = Image.frombytes("RGBA", src[:2], to_rgba(src, colors))
                img = img.resize((src[0] * scale, src[1] * scale), Image.NEAREST)
                sheet.paste(img, (cx, y), img)
            x += group_w[s]
    return sheet


def main() -> None:
    ap = argparse.ArgumentParser(description="大眾臉零件總覽圖")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scale", type=int, default=4)
    args = ap.parse_args()
    meta, blobs = load_dataset(args.dataset)
    parts_sheet(meta, blobs, args.scale).save(args.out)
    print(f"已儲存: {args.out}")


if __name__ == "__main__":
    main()
