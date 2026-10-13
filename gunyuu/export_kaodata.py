#!/usr/bin/env python3
"""Export FC 信長の野望・戦国群雄伝 as a kaodata dataset (gunyuu-fc, format kaodata/1).

Spec: docs/data-format.md of the kaodata website repo. Pixels are NES colour numbers and the
dataset palette is the 64-colour NES palette.

Composite faces: one variant per group (6, face code bits 12-14). The code picks one of 5 head
frames, eyes, noses and mouths of the group; each item is a 40x48 canvas (255 outside its cells):
the head frame without the part cells, the parts at their cells (rom.COMPOSITE_LAYOUT). Dedicated
ids 60-64 are unused (the game's formula reads other data) and are left out of `portraits`, so
portrait n of the dataset is face id PORTRAIT_IDS[n]. The ROM has no readings.

Usage: .venv/bin/python gunyuu/export_kaodata.py --out <dir> [--rom ROM]
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
    COMPOSITE_GROUPS,
    COMPOSITE_LAYOUT,
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
VARIANTS = 5
PORTRAIT_IDS = [f for f in range(PORTRAIT_COUNT) if not 60 <= f < 65]


def part_cells(rom: Rom, group: int) -> dict[str, list[int]]:
    """Cells (of the 5x6 grid) of each slot; the head frame gets the rest."""
    cell, w = COMPOSITE_LAYOUT[group]
    out = {}
    for slot, (sid, _, _) in enumerate(COMPOSITE_SLOTS[1:], 1):
        n = len(rom.composite_part(group, slot, 0)[0])
        out[sid] = [cell + k // w * 5 + k % w for k in range(n)]
        cell += 5
    out["head"] = [i for i in range(30) if not any(i in c for c in out.values())]
    return out


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
    from export import distinct_characters  # export.py imports this module
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
    for group in range(COMPOSITE_GROUPS):
        parts, cells = {}, part_cells(rom, group)
        for slot, (sid, _, _) in enumerate(COMPOSITE_SLOTS):
            mask = [i in cells[sid] for i in range(30)]
            items = []
            for v in range(VARIANTS):
                code = 0x8000 | group << 12 | v << COMPOSITE_SLOTS[slot][2]  # other slots 0: covered by mask
                items.append(add(rom.render_cells(*rom.composite_cells(code), PORTRAIT_W, pal, mask)))
            parts[sid] = {"items": items}
        variants.append({"id": str(group), "label": f"組 {group}", "parts": parts})

    portraits = [{"img": add(rom.face_pixels(n), blob=1), "label": f"F{n:03d}"} for n in PORTRAIT_IDS]

    characters = []
    for c in distinct_characters(rom):
        ch = {"id": c["id"], "name": c["name"]}
        code = c["face_code"]
        if is_composite(code):
            group, v = decode_face_code(code)
            ch["face"] = {"variant": group, "parts": v, "code": f"{code:04X}"}
        elif code < PORTRAIT_COUNT:
            ch["face"] = {"portrait": PORTRAIT_IDS.index(code)}
        characters.append(ch)

    meta = {
        "format": FORMAT,
        "id": "gunyuu-fc",
        "game": "NOBU3",
        "platform": "FC",
        "title": {"ja": "信長の野望・戦国群雄伝", "zh": "信長之野望・戰國群雄傳"},
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 gunyuu-fc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Nobunaga no Yabou - Sengoku Gunyuu Den (Japan).zip 或 .nes")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    faces = [c["face"] for c in chars if "face" in c]
    mobs = [f for f in faces if "variant" in f]
    print(f"gunyuu-fc: {len(chars)} characters ({len(faces) - len(mobs)} portrait, {len(mobs)} composite, "
          f"{len(chars) - len(faces)} without face), {len(meta['composite']['variants'])} groups, "
          f"{len(meta['portraits'])} portraits, {len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
