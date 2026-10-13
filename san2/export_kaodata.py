#!/usr/bin/env python3
"""Export FC 三國志II (KOEI) as a kaodata dataset (san2-fc, format kaodata/1).

Spec: docs/data-format.md of the kaodata website repo. Pixels are NES colour numbers and the
dataset palette is the 64-colour NES palette.

Faces are 5x6 tiles (40x48). Dedicated faces 1-200 are `portraits` (portrait n = face n+1).
Composite faces (code bit 15) have one variant per group (code bits 0-2); each of the five slots
(top half, bottom half, parts a/b/c) has 4 items, each a 40x48 canvas with 255 outside its cells:
the halves without their blank cells, the parts at the blank cells they fill (rom.Rom.part_cells).

Usage: .venv/bin/python san2/export_kaodata.py --out <dir> [--rom ROM]
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
from rom import (
    COMP_GROUPS,
    COMP_SLOTS,
    DEFAULT_ROM,
    FACE_COUNT,
    FACE_W,
    NES_PALETTE,
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
VARIANTS = 4


def slot_cells(rom: Rom, group: int) -> dict[str, list[int]]:
    """Cells (of the 5x6 grid) each slot draws."""
    a, b, c = rom.part_cells(group)
    holes = set(a + b + c)
    return {"top": [i for i in range(15) if i not in holes], "bottom": [i for i in range(15, 30) if i not in holes],
            "a": a, "b": b, "c": c}


def slot_code(group: int, slot: int, v: int) -> int:
    return 0x8000 | group | v << COMP_SLOTS[slot][2]


# ---------------------------------------------------------------- reference renderer (spec §6)

def compose_display(meta: dict, blobs: list[bytes], face: dict) -> tuple[int, int, bytes]:
    if "portrait" in face:
        return get_image(meta, blobs, meta["portraits"][face["portrait"]]["img"])
    comp = meta["composite"]
    variant = comp["variants"][face["variant"]]
    cw, ch = comp["canvas"]
    canvas = bytearray([TRANSPARENT]) * (cw * ch)
    for slot, part in zip(comp["slots"], face["parts"]):
        item = variant["parts"][slot["id"]]["items"][part]
        blit(canvas, cw, ch, get_image(meta, blobs, item), 0, 0)
    return cw, ch, bytes(canvas)


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
    for group in range(COMP_GROUPS):
        parts, cells = {}, slot_cells(rom, group)
        for slot, (sid, _, _) in enumerate(COMP_SLOTS):
            mask = [i in cells[sid] for i in range(30)]
            items = [add(rom.render_cells(*rom.face_cells(slot_code(group, slot, v)), FACE_W, pal, mask))
                     for v in range(VARIANTS)]
            parts[sid] = {"items": items}
        variants.append({"id": str(group), "label": f"組 {group}", "parts": parts})

    portraits = [{"img": add(rom.face_pixels(f), blob=1), "label": f"F{f:03d}"} for f in range(1, FACE_COUNT + 1)]

    characters = []
    for g in rom.generals():
        ch = {"id": g["id"], "name": g["name"], "reading": g["reading"]}
        code = g["face"]
        if is_composite(code):
            group, v = decode_face_code(code)
            ch["face"] = {"variant": group, "parts": v, "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code - 1}
        characters.append(ch)

    meta = {
        "format": FORMAT,
        "id": "san2-fc",
        "game": "SAN2",
        "platform": "FC",
        "title": {"ja": "三國志II", "zh": "三國志II"},
        "source": {"producer": "famicom-re", "revision": revision(),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "nes", "label": "NES 64 色（色號＝NES 色號）",
                      "colors": [f"#{c:06x}" for c in NES_PALETTE]}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": sid, "label": label} for sid, label, _ in COMP_SLOTS],
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 san2-fc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Sangokushi II (Japan).zip 或 .nes")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c["face"]]
    print(f"san2-fc: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} groups, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
