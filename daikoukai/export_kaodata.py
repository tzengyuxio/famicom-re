#!/usr/bin/env python3
"""Export FC 大航海時代 as a kaodata dataset (koukai-fc, format kaodata/1).

Spec: docs/data-format.md of the kaodata website repo. Pixels are NES colour numbers and the
dataset palette is the 64-colour NES palette.

Characters: the player, 20 mates, 20 admirals and 20 girls (ids 0-60). Faces are 5 x 6 sprites.
Composite faces: one variant per head (4, labelled 類型 N: the game never names them). The face code picks one of 4 pages for each of 5
slots (top, bottom, eyes, nose, mouth), drawn in that order. Each item is a 40x48 canvas: the
part's cells opaque, 255 elsewhere; blank cells (tile 1) are transparent except in the first
slot, which also fills the backdrop, matching the game's rule that a blank keeps the earlier
cell. The ROM has no readings, so characters carry no `reading`; nameZh comes from data/names_zh.tsv.
Portraits carry `code` = the face code (= portrait number); F01-F12, which no character uses, carry
the group and name of whoever the game draws with them (docs/ROM_FORMAT.md §5.3).

Usage: .venv/bin/python daikoukai/export_kaodata.py --out <dir> [--rom ROM]
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
from export import characters as all_characters
from export import names_zh
from rom import (
    COMPOSITE_HEADS,
    COMPOSITE_SLOTS,
    DEFAULT_ROM,
    NES_PALETTE,
    PORTRAIT_COUNT,
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
# Portraits no character uses, drawn by fixed face codes (docs/ROM_FORMAT.md §5.3): group, name
FIXED_PORTRAITS = {1: ("国王", "ポルトガル国王"), 2: ("国王", "イスパニア国王"), 3: ("国王", "イスラム国王"),
                   4: ("施設", "道具屋"), 5: ("施設", "造船所"), 6: ("施設", "交易所"), 7: ("施設", "酒場"),
                   8: ("特殊人物", "老航海士"), 9: ("施設", "港"), 10: ("施設", "王宮"), 11: ("施設", "宿屋"),
                   12: ("特殊人物", "クリス王女")}


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
    images, blobs = [], [bytearray(), bytearray()]

    def add(px: bytes, blob: int = 0) -> int:
        w, h = CANVAS
        assert len(px) == w * h
        images.append([len(blobs[blob]), w, h, blob] if blob else [len(blobs[blob]), w, h])
        blobs[blob].extend(px)
        return len(images) - 1

    variants = []
    for head in range(COMPOSITE_HEADS):
        parts = {sid: {"items": [add(rom.part_pixels(head, sid, p, TRANSPARENT)) for p in range(PAGES)]}
                 for sid, _, _ in COMPOSITE_SLOTS}
        variants.append({"id": str(head), "label": f"類型 {head}", "parts": parts})

    portraits = []
    for n in range(PORTRAIT_COUNT):
        pt = {"img": add(rom.face_pixels(n), blob=1), "code": f"{n:04X}"}  # = face code
        if n in FIXED_PORTRAITS:
            pt["group"], pt["name"] = FIXED_PORTRAITS[n]
        portraits.append(pt)

    characters, zh = [], names_zh()
    for c in all_characters(rom):
        ch = {"id": c["id"], "name": c["name"], "nameZh": zh[c["id"]]}
        code = c["face_code"]
        if is_composite(code):
            head, pages = decode_face_code(code)
            ch["face"] = {"variant": head, "parts": pages, "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code}
        characters.append(ch)

    meta = {
        "format": FORMAT,
        "id": "koukai-fc",
        "game": "KOUKAI",
        "platform": "FC",
        "title": {"ja": "大航海時代", "zh": "大航海時代"},
        "source": {"producer": "famicom-re", "revision": revision(),
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 koukai-fc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Daikoukai Jidai (Japan).zip 或 .nes")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    faces = [c["face"] for c in chars if "face" in c]
    mobs = [f for f in faces if "variant" in f]
    print(f"koukai-fc: {len(chars)} characters ({len(faces) - len(mobs)} portrait, {len(mobs)} composite, "
          f"{len(chars) - len(faces)} without face), {len(meta['composite']['variants'])} heads, "
          f"{len(meta['portraits'])} portraits, {len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
