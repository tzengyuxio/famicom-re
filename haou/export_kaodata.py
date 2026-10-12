#!/usr/bin/env python3
"""Export FC 三國志II 覇王の大陸 as a kaodata dataset (haou-fc, format kaodata/1).

Spec: docs/data-format.md of the kaodata website repo. Pixels are NES colour numbers and the
dataset palette is the 64-colour NES palette.

Faces: the game has 183 whole 32x40 sprite faces shared by the 237 generals (CHR bank + template
per general, 5 expressions each), so the dataset has `portraits` only (expression 0, as on the status
screen) and no `composite`. The ROM names are katakana: `name` is the katakana the game shows,
`nameZh` the [EXT] kanji of data/kanji_names.tsv when known, `reading` the name in hiragana,
split after the surname when the kanji surname is in sangokushi/data/surnames.tsv.

Usage: .venv/bin/python haou/export_kaodata.py --out <dir> [--rom ROM]
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
from rom import DEFAULT_ROM, FACE_H, FACE_W, GENERAL_COUNT, NES_PALETTE, Rom

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Spec §6 primitives shared with the san1-fc exporter (same module name, so load it by path)
_spec = importlib.util.spec_from_file_location("san1_kaodata", os.path.join(REPO, "sangokushi", "tools", "export_kaodata.py"))
san1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(san1)
get_image, to_rgba = san1.get_image, san1.to_rgba

FORMAT = "kaodata/1"
SURNAMES = os.path.join(REPO, "sangokushi", "data", "surnames.tsv")
KANJI_TSV = os.path.join(REPO, "haou", "data", "kanji_names.tsv")


# ---------------------------------------------------------------- reference renderer (spec §6)

def compose_display(meta: dict, blobs: list[bytes], face: dict) -> tuple[int, int, bytes]:
    pt = meta["portraits"][face["portrait"]]
    return get_image(meta, blobs, pt["img"])


def checksums(meta: dict, blobs: list[bytes]) -> dict:
    colors = meta["palettes"][0]["colors"]

    def digest(face: dict) -> str:
        return hashlib.sha256(to_rgba(compose_display(meta, blobs, face), colors)).hexdigest()

    entries = {f"ch:{c['id']}": digest(c["face"]) for c in meta["characters"] if "face" in c}
    entries.update({f"pt:{n}": digest({"portrait": n}) for n in range(len(meta["portraits"]))})
    return {"algo": "sha256-rgba", "entries": entries}


# ---------------------------------------------------------------- names

def hiragana(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def load_kanji() -> dict[int, str]:
    out = {}
    with open(KANJI_TSV, encoding="utf-8") as f:
        next(f)
        for line in f:
            i, _, kanji, _ = line.rstrip("\n").split("\t")
            if kanji and "|" not in kanji:
                out[int(i)] = kanji
    return out


def load_surnames() -> dict[str, str]:
    out = {}
    with open(SURNAMES, encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                kanji, reading = line.rstrip("\n").split("\t")
                out[kanji] = reading
    return out


def reading(kana: str, kanji: str | None, surnames: dict[str, str]) -> str:
    r = hiragana(kana)
    if kanji:
        for sur in (kanji[:2], kanji[:1]):
            s = surnames.get(sur)
            if s and r.startswith(s) and len(r) > len(s):
                return f"{r[:len(s)]} {r[len(s):]}"
    return r


# ---------------------------------------------------------------- dataset

def revision() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
                          cwd=REPO).stdout.strip()


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blob = [], bytearray()
    faces = rom.faces()
    portraits = []
    for n, f in enumerate(faces):
        images.append([len(blob), FACE_W, FACE_H])
        blob.extend(rom.face_pixels(f))
        portraits.append({"img": n, "label": f"F{n:03d}"})

    kanji, surnames = load_kanji(), load_surnames()
    characters = []
    for i in range(GENERAL_COUNT):
        kana = rom.general_name(i)
        ch = {"id": i, "name": kana, "reading": reading(kana, kanji.get(i), surnames)}
        if i in kanji:
            ch["nameZh"] = kanji[i]
        ch["face"] = {"portrait": faces.index(rom.face_of(i))}
        characters.append(ch)

    meta = {
        "format": FORMAT,
        "id": "haou-fc",
        "game": "HAOU",
        "platform": "FC",
        "title": {"ja": "三國志II 覇王の大陸", "zh": "三國志II 霸王的大陸"},
        "source": {"producer": "fc-sangokushi", "revision": revision(),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 8},
        "palettes": [{"id": "nes", "label": "NES 64 色（色號＝NES 色號）",
                      "colors": [f"#{c:06x}" for c in NES_PALETTE]}],
        "images": images,
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(blob)]


def write_dataset(out_dir: str, meta: dict, blobs: list[bytes]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    with open(os.path.join(out_dir, "pixels.bin"), "wb") as f:
        f.write(comp.compress(blobs[0]) + comp.flush())
    with open(os.path.join(out_dir, "dataset.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(out_dir, "checksums.json"), "w", encoding="utf-8") as f:
        json.dump(checksums(meta, blobs), f, indent=1)


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 haou-fc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Sangokushi II - Haou no Tairiku (Japan).zip 或 .nes")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    print(f"haou-fc: {len(chars)} characters ({sum('nameZh' in c for c in chars)} with [EXT] kanji), "
          f"{len(meta['portraits'])} portraits, {len(meta['images'])} images")
    for name in ["pixels.bin", "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
