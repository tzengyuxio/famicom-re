#!/usr/bin/env python3
"""Export FC 水滸伝・天命の誓い as a kaodata dataset (suikoden-fc, format kaodata/1).

Spec: docs/data-format.md of the kaodata website repo. Pixels are NES colour numbers
and the dataset palette is the 64-colour NES palette, because every face carries its
own pair of 4-colour sub-palettes.

Usage: .venv/bin/python suikoden/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import zlib

from rom import (
    DEFAULT_ROM,
    MOB_CATEGORIES,
    MOB_LAYOUT,
    MOB_SLOTS,
    NES_PALETTE,
    PORTRAIT_COUNT,
    Rom,
    decode_mob_code,
    load_tsv,
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
SLOT_IDS = [sid for sid, *_ in MOB_SLOTS]  # head, chin, eyes, nose, mouth (= draw order)


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

def split_reading(name: str, kana: str, surnames: dict[str, list[str]]) -> str:
    family = name[:2] if name[:2] in surnames else name[0]
    for r in surnames.get(family, []):
        if kana.startswith(r) and len(kana) > len(r):
            return f"{r} {kana[len(r):]}"
    return kana


def revision() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
                          cwd=REPO).stdout.strip()


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blobs = [], [bytearray(), bytearray()]

    def add(w: int, h: int, px: bytes, blob: int = 0) -> int:
        assert len(px) == w * h
        images.append([len(blobs[blob]), w, h, blob] if blob else [len(blobs[blob]), w, h])
        blobs[blob].extend(px)
        return len(images) - 1

    variants = []
    for cat in range(MOB_CATEGORIES):
        pal = rom.mob_palette(cat)
        parts = rom.mob_parts(cat)
        at = dict(zip(SLOT_IDS, [0, 20, *MOB_LAYOUT[cat]]))
        variants.append({
            "id": str(cat), "label": f"類型 {cat}",
            "parts": {sid: {"at": [at[sid] % 5 * 8, at[sid] // 5 * 8],
                            "items": [add(w * 8, len(t) // w * 8, rom.render_cells(t, e, w, pal))
                                      for w, t, e in parts[sid]]}
                      for sid in SLOT_IDS},
        })

    portraits = []
    for n in range(PORTRAIT_COUNT):
        portraits.append({"img": add(*CANVAS, rom.face_pixels(n), blob=1), "label": f"P{n:02d}"})

    surnames = {s: r.split(",") for s, r in load_tsv("surnames.tsv")}
    characters = []
    for c in rom.characters():
        ch = {"id": c["id"], "name": c["name"], "reading": split_reading(c["name"], c["reading"], surnames)}
        code = c["face_code"]
        if code & 0x8000:
            cat, sel = decode_mob_code(code)
            ch["face"] = {"variant": cat, "parts": [sel[s] for s in SLOT_IDS], "code": f"{code & 0x7FFF:04X}"}
        else:
            ch["face"] = {"portrait": code}
        characters.append(ch)

    meta = {
        "format": FORMAT,
        "id": "suikoden-fc",
        "game": "SUIKODEN",
        "platform": "FC",
        "title": {"ja": "水滸伝・天命の誓い", "zh": "水滸傳・天命之誓"},
        "source": {"producer": "fc-sangokushi", "revision": revision(),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "nes", "label": "NES 64 色（色號＝NES 色號）",
                      "colors": [f"#{c:06x}" for c in NES_PALETTE]}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": sid, "label": label} for sid, label, *_ in MOB_SLOTS],
            "variants": variants,
            "code": {"kind": "bitfield", "bits": 16, "fields": [
                {"of": "$variant", "hi": 12, "lo": 10},
                {"of": "head", "hi": 9, "lo": 8},
                {"of": "eyes", "hi": 7, "lo": 6},
                {"of": "nose", "hi": 5, "lo": 4},
                {"of": "mouth", "hi": 3, "lo": 2},
                {"of": "chin", "hi": 1, "lo": 0},
            ]},
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 suikoden-fc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="Suikoden - Tenmei no Chikai (Japan).nes")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c["face"] for c in chars if "variant" in c["face"]]
    print(f"suikoden-fc: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite, "
          f"{len({f['code'] for f in mobs})} distinct codes), {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    unsplit = [c["name"] for c in chars if " " not in c["reading"]]
    print(f"  reading without family/given split: {' '.join(unsplit) or '-'}")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
