#!/usr/bin/env python3
"""Export FC 維新の嵐 as a kaodata dataset (ishin-fc, format kaodata/1).

Spec: docs/data-format.md of the kaodata website repo. Pixels are NES colour numbers and the
dataset palette is the 64-colour NES palette. Faces are sprites; sprite colour 0 shows the
window background (NES colour 0x0F).

Composite faces: one variant per category (face code bits 12-14, 5 categories). Slot "base" is a
plain 0x0F canvas; the six parts (face code bits 10-11 head, 8-9 eyes, 6-7 nose, 4-5 mouth,
2-3 lower, 0-1 body) each have 4 items, drawn in the game's order head, lower, body, eyes, nose,
mouth. The category's blank tile is left transparent (the game draws it only into empty cells,
which the base already shows as 0x0F).

The game has no readings for names, so no character has `reading`.

Portrait `code` is the game's face code (record n is code n + 1). Code 0x57 (P87) belongs to no
person: the face routine (bank 0 $8003) draws it for ids 201-246, the 46 domain troops (藩兵), so
it has group "藩兵" (docs/ROM_FORMAT.md §5).

Usage: .venv/bin/python ishin/export_kaodata.py --out <dir> [--rom ROM]
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
from rom import CATEGORIES, DEFAULT_ROM, FACE_H, FACE_W, NES_PALETTE, PORTRAIT_COUNT, SLOT_ORDER, SLOTS, Rom

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Spec §6 primitives shared with the san1-fc exporter (same module name, so load it by path)
_spec = importlib.util.spec_from_file_location("san1_kaodata", os.path.join(REPO, "sangokushi", "tools", "export_kaodata.py"))
san1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(san1)
blit, crop, get_image, to_rgba = san1.blit, san1.crop, san1.get_image, san1.to_rgba

FORMAT = "kaodata/1"
TRANSPARENT = 255
CANVAS = (FACE_W * 8, FACE_H * 8)
BACKGROUND = 0x0F
TROOP_FACE = 0x57  # face code drawn for a domain troop (藩兵)
CATEGORY_LABELS = ["類型 0", "類型 1", "類型 2", "類型 3", "類型 4"]
SLOT_IDS = ["base"] + [SLOTS[s][0] for s in SLOT_ORDER]  # draw order


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
    entries.update({f"ch:{c['id']}/{k}": digest(e) for c in meta["characters"]
                    for k, e in enumerate(c.get("expressions", []), 1)})
    entries.update({f"pt:{n}": digest({"portrait": n}) for n in range(len(meta["portraits"]))})
    return {"algo": "sha256-rgba", "entries": entries}


# ---------------------------------------------------------------- dataset

def face_parts(code: int) -> list[int]:
    """Item index per slot in SLOT_IDS order (base always 0)."""
    return [0] + [(code >> (10 - 2 * s)) & 3 for s in SLOT_ORDER]


def revision() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
                          cwd=REPO).stdout.strip()


def part_pixels(rom: Rom, cat: int, slot: int, v: int) -> bytes:
    """One part on the 40x48 canvas, transparent outside its (non-blank) cells."""
    grid = rom.part_cells(cat, slot, v)
    px = rom.render_sprites(rom.category_banks(cat), grid, rom.face_palette(1 + cat), empty=TRANSPARENT)
    # colour 0 inside a drawn cell is the window background, not transparent
    w = CANVAS[0]
    out = bytearray(px)
    for (r, c) in grid:
        for y in range(8):
            for x in range(8):
                i = (r * 8 + y) * w + c * 8 + x
                if out[i] == TRANSPARENT:
                    out[i] = BACKGROUND
    return bytes(out)


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blobs = [], [bytearray(), bytearray()]

    def add(px: bytes, blob: int = 0) -> int:
        assert len(px) == CANVAS[0] * CANVAS[1]
        images.append([len(blobs[blob]), *CANVAS, blob] if blob else [len(blobs[blob]), *CANVAS])
        blobs[blob].extend(px)
        return len(images) - 1

    base = add(bytes([BACKGROUND]) * (CANVAS[0] * CANVAS[1]))
    variants = []
    for cat in range(CATEGORIES):
        parts = {"base": {"items": [base]}}
        for s in SLOT_ORDER:
            parts[SLOTS[s][0]] = {"items": [add(part_pixels(rom, cat, s, v)) for v in range(4)]}
        variants.append({"id": str(cat), "label": CATEGORY_LABELS[cat], "parts": parts})
    portraits = [{"img": add(rom.face_pixels(n + 1), blob=1), "code": f"{n + 1:04X}"}
                 for n in range(PORTRAIT_COUNT)]
    portraits[TROOP_FACE - 1]["group"] = "藩兵"

    characters = []
    for c in rom.characters(0):
        ch = {"id": c["id"], "name": c["name"]}
        code = c["face_code"]
        if code & 0x8000:
            ch["face"] = {"variant": (code >> 12) & 7, "parts": face_parts(code), "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code - 1}
        characters.append(ch)

    meta = {
        "format": FORMAT,
        "id": "ishin-fc",
        "game": "ISHIN",
        "platform": "FC",
        "title": {"ja": "維新の嵐", "zh": "維新之嵐"},
        "source": {"producer": "famicom-re", "revision": revision(),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "nes", "label": "NES 64 色（色號＝NES 色號）",
                      "colors": [f"#{c:06x}" for c in NES_PALETTE]}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": "base", "label": "底色"}] + [{"id": SLOTS[s][0], "label": SLOTS[s][1]}
                                                          for s in SLOT_ORDER],
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 ishin-fc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Ishin no Arashi (Japan).zip 或 .nes")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c.get("face", {})]
    print(f"ishin-fc: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} categories, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
