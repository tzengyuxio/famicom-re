#!/usr/bin/env python3
"""Export FC ロイヤルブラッド as a kaodata dataset (royal-fc, format kaodata/1).

Spec: docs/data-format.md of the kaodata website repo. Pixels are NES colour numbers and the
dataset palette is the 64-colour NES palette.

Faces: every face is a whole 5x6-tile picture (no composite faces), so the dataset has `portraits`
only: P00-P63 the 64 characters (face = character index), P64-P67 the 4 advisers (group 相談役; the
adviser screen shows no names) and P68-P90 the 23 units of the 5th troop (group 第5部隊: 傭兵隊, wizards,
パスハ, ドラゴン; name = the unit name in the ROM, docs/ROM_FORMAT.md §3.4). The game keeps no face code
(a character's face is its record index, advisers and units are table indices), so portraits have no
`code`. `characters` are the 64 people; `name` is the katakana the game shows and `reading` the same in
hiragana. There is no Chinese release, so there is no nameZh.

Usage: .venv/bin/python royal/export_kaodata.py --out <dir> [--rom ROM]
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
from rom import CHAR_COUNT, DEFAULT_ROM, FACE_TABLES, NES_PALETTE, PORTRAIT_H, PORTRAIT_W, Rom

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Spec §6 primitives shared with the san1-fc exporter (same module name, so load it by path)
_spec = importlib.util.spec_from_file_location("san1_kaodata", os.path.join(REPO, "sangokushi", "tools", "export_kaodata.py"))
san1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(san1)
get_image, to_rgba = san1.get_image, san1.to_rgba

FORMAT = "kaodata/1"
FACE_W, FACE_H = PORTRAIT_W * 8, PORTRAIT_H * 8
FACES = [(t, f) for t in range(len(FACE_TABLES)) for f in range(FACE_TABLES[t][2])]  # portrait n -> (table, face)


# ---------------------------------------------------------------- reference renderer (spec §6)

def compose_display(meta: dict, blobs: list[bytes], face: dict) -> tuple[int, int, bytes]:
    return get_image(meta, blobs, meta["portraits"][face["portrait"]]["img"])


def checksums(meta: dict, blobs: list[bytes]) -> dict:
    colors = meta["palettes"][0]["colors"]

    def digest(face: dict) -> str:
        return hashlib.sha256(to_rgba(compose_display(meta, blobs, face), colors)).hexdigest()

    entries = {f"ch:{c['id']}": digest(c["face"]) for c in meta["characters"] if "face" in c}
    entries.update({f"pt:{n}": digest({"portrait": n}) for n in range(len(meta["portraits"]))})
    return {"algo": "sha256-rgba", "entries": entries}


def hiragana(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


# ---------------------------------------------------------------- dataset

def revision() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
                          cwd=REPO).stdout.strip()


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    units = rom.units()
    images, blob, portraits = [], bytearray(), []
    for n, (t, f) in enumerate(FACES):
        images.append([len(blob), FACE_W, FACE_H])
        blob.extend(rom.face_pixels(t, f))
        portraits.append({"img": n} if t == 0 else {"img": n, "group": "相談役"} if t == 1
                         else {"img": n, "group": "第5部隊", "name": units[f]["name"]})

    characters = []
    for i in range(CHAR_COUNT):
        name = rom.char_name(i)["name"]
        characters.append({"id": i, "name": name, "reading": hiragana(name), "face": {"portrait": FACES.index((0, i))}})

    meta = {
        "format": FORMAT,
        "id": "royal-fc",
        "game": "ROYAL",
        "platform": "FC",
        "title": {"ja": "ロイヤルブラッド", "zh": "魔法皇冠"},
        "source": {"producer": "famicom-re", "revision": revision(),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 royal-fc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Royal Blood (Japan).zip 或 .nes")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    write_dataset(args.out, meta, blobs)
    print(f"royal-fc: {len(meta['characters'])} characters, {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in ["pixels.bin", "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
