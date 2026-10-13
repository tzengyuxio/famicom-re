#!/usr/bin/env python3
"""Export FC 蒼き狼と白き牝鹿・元朝秘史 as a kaodata dataset (genchou-fc, format kaodata/1).

Spec: docs/data-format.md of the kaodata website repo. Pixels are NES colour numbers and the
dataset palette is the 64-colour NES palette.

Composite faces: one variant per head (43). The game draws the head's base record and then,
for each set bit of the face code, copies one area from the head's alternate record, so every
slot has two items: [base cells, alternate cells] (40x48 canvases, 255 outside the area).

Usage: .venv/bin/python genchou/export_kaodata.py --out <dir> [--rom ROM]
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
    FACE_CULTURES,
    HEADS_PER_CULTURE,
    NES_PALETTE,
    PORTRAIT_COUNT,
    PORTRAIT_W,
    Rom,
    decode_face_code,
    is_composite,
    to_hiragana,
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
SLOT_IDS = ["base"] + [sid for sid, *_ in COMPOSITE_SLOTS]  # draw order
WOMEN_ID, CHILDREN_ID = 1000, 2000  # id ranges of the women's and the child tables (README)


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

def face_parts(code: int) -> list[int]:
    """Part index per slot (base always 0); bit set = alternate cells."""
    return [0] + [code >> bit & 1 for *_, bit in COMPOSITE_SLOTS]


def reading(name: str) -> str | None:
    """Kana-only names -> hiragana, '・' and spaces become the word separator; kanji names have none."""
    s = to_hiragana(name).replace("・", " ").replace("　", " ")
    return s if all("ぁ" <= c <= "ゖ" or c in "ー " for c in s) else None


def all_characters(rom: Rom) -> list[dict]:
    """People table (ids 0-), then the women (1000-) and children (2000-), each distinct by name + face code."""
    out = list(distinct_characters(rom))
    for base, rows in ((WOMEN_ID, [w for s in range(4) for w in rom.women(s)]), (CHILDREN_ID, rom.children())):
        seen = []
        for r in rows:
            if (key := (r["name"], r["face_code"])) not in seen:
                seen.append(key)
                out.append({"id": base + len(seen) - 1, "name": r["name"], "face_code": r["face_code"]})
    return out


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
        culture, n = divmod(head, HEADS_PER_CULTURE)
        records = [rom.composite_record(2 * head), rom.composite_record(2 * head + 1)]
        areas = rom.composite_areas(head)
        parts = {"base": {"items": [add(rom.render_cells(*records[0], PORTRAIT_W, pal))]}}
        for sid, *_ in COMPOSITE_SLOTS:
            mask = [i in areas[sid] for i in range(30)]
            parts[sid] = {"items": [add(rom.render_cells(*rec, PORTRAIT_W, pal, mask)) for rec in records]}
        variants.append({"id": str(head), "label": f"{FACE_CULTURES[culture]} {n}" if culture < len(FACE_CULTURES)
                         else f"頭 {head}", "parts": parts})

    portraits = [{"img": add(rom.face_pixels(n), blob=1), "code": f"{n:04X}"} for n in range(PORTRAIT_COUNT)]

    characters = []
    for c in all_characters(rom):
        ch = {"id": c["id"], "name": c["name"]}
        if (r := reading(c["name"])) is not None:
            ch["reading"] = r
        code = c["face_code"]
        if not code & 0x8000:
            ch["face"] = {"portrait": code}
        elif is_composite(code):
            ch["face"] = {"variant": decode_face_code(code)[0], "parts": face_parts(code), "code": f"{code:04X}"}
        characters.append(ch)

    meta = {
        "format": FORMAT,
        "id": "genchou-fc",
        "game": "GENCHOU",
        "platform": "FC",
        "title": {"ja": "蒼き狼と白き牝鹿・元朝秘史", "zh": "蒼狼與白鹿・元朝秘史"},
        "source": {"producer": "famicom-re", "revision": revision(),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "nes", "label": "NES 64 色（色號＝NES 色號）",
                      "colors": [f"#{c:06x}" for c in NES_PALETTE]}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": "base", "label": "基本"}] + [{"id": sid, "label": label} for sid, label, _ in
                                                          COMPOSITE_SLOTS],
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 genchou-fc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Aoki Ookami to Shiroki Mejika - Genchou Hishi (Japan).zip 或 .nes")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    faces = [c["face"] for c in chars if "face" in c]
    mobs = [f for f in faces if "variant" in f]
    print(f"genchou-fc: {len(chars)} characters ({len(faces) - len(mobs)} portrait, {len(mobs)} composite, "
          f"{len(chars) - len(faces)} without face), {len(meta['composite']['variants'])} heads, "
          f"{len(meta['portraits'])} portraits, {len(meta['images'])} images")
    print(f"  without face: {' '.join(c['name'] for c in chars if 'face' not in c) or '-'}")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
