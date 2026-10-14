#!/usr/bin/env python3
"""Export FC ランペルール as a kaodata dataset (lempe-fc, format kaodata/1).

Spec: docs/data-format.md of the kaodata website repo. Pixels are NES colour numbers and the
dataset palette is the 64-colour NES palette.

Composite faces: one variant per category (face code bits 0-1, 4 categories). Every slot
(top, bottom, eyes, nose, mouth; face code bits 2-11, two bits each) has 4 items, drawn on a
40x48 canvas (255 outside the cells the part covers) in the game's order.

Usage: .venv/bin/python empereur/export_kaodata.py --out <dir> [--rom ROM]
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
from rom import COMPOSITE_PARTS, DEFAULT_ROM, FACE_PALETTE, NES_PALETTE, PORTRAIT_COUNT, PORTRAIT_W, Rom

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Spec §6 primitives shared with the san1-fc exporter (same module name, so load it by path)
_spec = importlib.util.spec_from_file_location("san1_kaodata", os.path.join(REPO, "sangokushi", "tools", "export_kaodata.py"))
san1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(san1)
blit, crop, get_image, to_rgba = san1.blit, san1.crop, san1.get_image, san1.to_rgba

FORMAT = "kaodata/1"
TRANSPARENT = 255
CANVAS = (40, 48)
CATEGORY_LABELS = ["正面", "向右", "向左", "頭巾"]  # by look of the parts
CATEGORIES = len(CATEGORY_LABELS)
SLOT_LABELS = {"top": "上半", "bottom": "下半", "eyes": "眼", "nose": "鼻", "mouth": "口"}
# Napoleon's face follows his rank: the face-code function $C28D gives P01 at rank 6 and P02 at rank 7.
# Labels: the titles the game prints for his rank 5 / 6 / 7 (bank 2 $A111: シレイカン, ダイ1シッセイ,
# コウテイ), in kanji as lempe-dos writes them.
NAPOLEON_EXPRESSIONS = [1, 2]
NAPOLEON_LABELS = ["司令官", "第一執政", "皇帝"]
NAMES_ZH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "names_zh.tsv")


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
    return [code >> COMPOSITE_PARTS[p][0] & 3 for p in COMPOSITE_PARTS]


def reading(name: str) -> str | None:
    """Katakana names -> hiragana; '・' becomes the word separator."""
    s = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in name).replace("・", " ")
    return s if all("ぁ" <= c <= "ゖ" or c in "ー " for c in s) else None


def revision() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
                          cwd=REPO).stdout.strip()


def part_pixels(rom: Rom, part: str, cat: int, sel: int) -> bytes:
    """One part on the 40x48 canvas, transparent outside its cells."""
    shift = COMPOSITE_PARTS[part][0]
    at, t, e = rom.composite_part(part, cat | sel << shift)
    tiles, exram, mask = [0] * 30, [0] * 30, [False] * 30
    for i in range(len(t)):
        tiles[at + i], exram[at + i], mask[at + i] = t[i], e[i], True
    return rom.render_cells(tiles, exram, PORTRAIT_W, rom.palette(FACE_PALETTE), mask)


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blobs = [], [bytearray(), bytearray()]

    def add(px: bytes, blob: int = 0) -> int:
        w, h = CANVAS
        assert len(px) == w * h
        images.append([len(blobs[blob]), w, h, blob] if blob else [len(blobs[blob]), w, h])
        blobs[blob].extend(px)
        return len(images) - 1

    variants = [{"id": str(cat), "label": CATEGORY_LABELS[cat],
                 "parts": {p: {"items": [add(part_pixels(rom, p, cat, sel)) for sel in range(4)]}
                           for p in COMPOSITE_PARTS}}
                for cat in range(CATEGORIES)]
    portraits = [{"img": add(rom.face_pixels(n), blob=1), "code": f"{n:04X}"} for n in range(PORTRAIT_COUNT)]

    with open(NAMES_ZH, encoding="utf-8") as f:
        next(f)
        names_zh = {int(i): zh for i, _, zh, _ in (line.rstrip("\n").split("\t") for line in f)}
    characters = []
    for c in rom.characters():
        ch = {"id": c["id"], "name": c["name"], "nameZh": names_zh[c["id"]]}
        if (r := reading(c["name"])) is not None:
            ch["reading"] = r
        code = c["face_code"]
        if code & 0x8000:
            ch["face"] = {"variant": code & 3, "parts": face_parts(code), "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code}
        if c["id"] == 0:
            ch["face"]["label"] = NAPOLEON_LABELS[0]
            ch["expressions"] = [{"portrait": n, "label": t} for n, t in zip(NAPOLEON_EXPRESSIONS, NAPOLEON_LABELS[1:])]
        characters.append(ch)

    meta = {
        "format": FORMAT,
        "id": "lempe-fc",
        "game": "LEMPE",
        "platform": "FC",
        "title": {"ja": "ランペルール", "zh": "拿破崙"},
        "source": {"producer": "famicom-re", "revision": revision(),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "nes", "label": "NES 64 色（色號＝NES 色號）",
                      "colors": [f"#{c:06x}" for c in NES_PALETTE]}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": p, "label": SLOT_LABELS[p]} for p in COMPOSITE_PARTS],
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 lempe-fc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="Empereur, L' (Japan).nes 或 roms/ 內的 .zip")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c for c in chars if "variant" in c.get("face", {})]
    print(f"lempe-fc: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite), "
          f"{len(meta['composite']['variants'])} categories, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
