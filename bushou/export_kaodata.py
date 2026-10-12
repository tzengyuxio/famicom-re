#!/usr/bin/env python3
"""Export FC 信長の野望・武将風雲録 as a kaodata dataset (bushou-fc, format kaodata/1).

Spec: docs/data-format.md of the kaodata website repo. Pixels are NES colour numbers and the
dataset palette is the 64-colour NES palette.

Composite faces: one variant per head (5 in the table, characters use heads 0-3). The face
code picks one of 4 pages of the head for each of 5 areas (top, bottom, eyes, nose, mouth;
the cells differ per head), which together cover all 30 cells, so every slot has four items (40x48 canvases, 255 outside
the area). The ROM has no readings, so characters carry no `reading`.

Usage: .venv/bin/python bushou/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import zlib

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from export import distinct_characters
from rom import (
    COMPOSITE_HEADS,
    COMPOSITE_SLOTS,
    DEFAULT_ROM,
    NES_PALETTE,
    PORTRAIT_COUNT,
    PORTRAIT_W,
    Rom,
    decode_face_code,
    is_composite,
)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Spec §6 primitives shared with the san1-fc exporter (same module name, so load it by path)
_spec = importlib.util.spec_from_file_location("san1_kaodata", os.path.join(REPO, "sangokushi", "tools", "export_kaodata.py"))
san1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(san1)
blit, crop, get_image, to_rgba = san1.blit, san1.crop, san1.get_image, san1.to_rgba

FORMAT = "kaodata/1"
TRANSPARENT = 255
CANVAS = (40, 48)
PAGES = 4


# ---------------------------------------------------------------- reference renderer (spec §6)

def compose_display(meta: dict, blobs: list[bytes], face: dict) -> tuple[int, int, bytes]:
    if "portrait" in face:
        pt = meta["portraits"][face["portrait"]]
        shown = get_image(meta, blobs, pt["img"])
        return crop(shown, pt["window"]) if "window" in pt else shown
    comp = meta["composite"]
    variant = comp["variants"][face["variant"]]
    cw, ch = comp["canvas"]
    canvas = bytearray([TRANSPARENT]) * (cw * ch)
    for slot, part in zip(comp["slots"], face["parts"]):
        sp = variant["parts"][slot["id"]]
        item = sp["items"][part]
        img, (x, y) = (item, sp.get("at", [0, 0])) if isinstance(item, int) else (item["img"], item["at"])
        blit(canvas, cw, ch, get_image(meta, blobs, img), x, y)
    shown = (cw, ch, bytes(canvas))
    return crop(shown, variant["window"]) if "window" in variant else shown


def checksums(meta: dict, blobs: list[bytes]) -> dict:
    colors = meta["palettes"][0]["colors"]

    def digest(face: dict) -> str:
        return hashlib.sha256(to_rgba(compose_display(meta, blobs, face), colors)).hexdigest()

    entries = {f"ch:{c['id']}": digest(c["face"]) for c in meta["characters"] if "face" in c}
    entries.update({f"pt:{n}": digest({"portrait": n}) for n in range(len(meta["portraits"]))})
    return {"algo": "sha256-rgba", "entries": entries}


# ---------------------------------------------------------------- dataset

def revision() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
                          cwd=REPO).stdout.strip()


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    pal = rom.palette()
    images, blobs = [], [bytearray(), bytearray()]

    def add(px: bytes, blob: int = 0) -> int:
        w, h = CANVAS
        assert len(px) == w * h
        images.append([len(blobs[blob]), w, h, blob] if blob else [len(blobs[blob]), w, h])
        blobs[blob].extend(px)
        return len(images) - 1

    variants = []
    for head in range(COMPOSITE_HEADS):
        parts, areas = {}, rom.composite_areas(head)
        for sid, _, _ in COMPOSITE_SLOTS:
            mask = [i in areas[sid] for i in range(30)]
            parts[sid] = {"items": [add(rom.render_cells(*rom.composite_page(head, p), PORTRAIT_W, pal, mask))
                                    for p in range(PAGES)]}
        variants.append({"id": str(head), "label": f"頭 {head}", "parts": parts})

    portraits = [{"img": add(rom.face_pixels(n), blob=1), "label": f"F{n:03d}"} for n in range(PORTRAIT_COUNT)]

    characters = []
    for c in distinct_characters(rom):
        ch = {"id": c["id"], "name": c["name"]}
        code = c["face_code"]
        if is_composite(code):
            head, pages = decode_face_code(code)
            ch["face"] = {"variant": head, "parts": pages, "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code}
        characters.append(ch)

    meta = {
        "format": FORMAT,
        "id": "bushou-fc",
        "game": "NOBU4",
        "platform": "FC",
        "title": {"ja": "信長の野望・武将風雲録", "zh": "信長之野望・武將風雲錄"},
        "source": {"producer": "fc-sangokushi", "revision": revision(),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "nes", "label": "NES 64 色（色號＝NES 色號）",
                      "colors": [f"#{c:06x}" for c in NES_PALETTE]}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": sid, "label": label} for sid, label, _ in COMPOSITE_SLOTS],
            "variants": variants,
            "code": {"kind": "tuple"},
        },
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(b) for b in blobs]


def write_dataset(out_dir: str, meta: dict, blobs: list[bytes]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    for name, px in zip(meta["blobs"], blobs):
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        with open(os.path.join(out_dir, name), "wb") as f:
            f.write(comp.compress(px) + comp.flush())
    with open(os.path.join(out_dir, "dataset.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(out_dir, "checksums.json"), "w", encoding="utf-8") as f:
        json.dump(checksums(meta, blobs), f, indent=1)


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 bushou-fc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Nobunaga no Yabou - Bushou Fuuun Roku (Japan).zip 或 .nes")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    faces = [c["face"] for c in chars if "face" in c]
    mobs = [f for f in faces if "variant" in f]
    print(f"bushou-fc: {len(chars)} characters ({len(faces) - len(mobs)} portrait, {len(mobs)} composite, "
          f"{len(chars) - len(faces)} without face), {len(meta['composite']['variants'])} heads, "
          f"{len(meta['portraits'])} portraits, {len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
