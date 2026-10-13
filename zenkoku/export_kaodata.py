#!/usr/bin/env python3
"""Export FC 信長の野望・全国版 as a kaodata dataset (nobu2-fc, format kaodata/1).

Spec: docs/data-format.md of the kaodata website repo. Pixels are NES colour numbers and the
dataset palette is the 64-colour NES palette (every face uses BG sub-palette 3E 38 28 30).

Portraits only: the game has no composite faces. Characters are the 53 daimyo of the 50-mode
name list (the 17-mode daimyo are the same people with the same faces). The ROM only has the
family name in katakana; `reading` is its hiragana form. Portraits 53-74 (princesses) have
no named character and carry group 姫.

Usage: .venv/bin/python zenkoku/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import zlib

from rom import DAIMYO_FACES, DEFAULT_ROM, NES_PALETTE, PORTRAIT_COUNT, Rom, to_hiragana

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Spec §6 primitives shared with the san1-fc exporter (same module name, so load it by path)
_spec = importlib.util.spec_from_file_location("san1_kaodata", os.path.join(REPO, "sangokushi", "tools", "export_kaodata.py"))
san1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(san1)
get_image, to_rgba = san1.get_image, san1.to_rgba

FORMAT = "kaodata/1"
CANVAS = (48, 48)


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


# ---------------------------------------------------------------- dataset

def revision() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
                          cwd=REPO).stdout.strip()


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blob = [], bytearray()
    portraits = []
    for n in range(PORTRAIT_COUNT):
        images.append([len(blob), *CANVAS])
        blob.extend(rom.face_pixels(n))
        # No code: the game picks a face by daimyo number, it stores no face value
        portraits.append({"img": n} if n < DAIMYO_FACES else {"img": n, "group": "姫"})

    characters = [{"id": d["id"], "name": d["name"], "reading": to_hiragana(d["name"]), "face": {"portrait": d["face"]}}
                  for d in rom.scenario(50)["daimyo"]]

    meta = {
        "format": FORMAT,
        "id": "nobu2-fc",
        "game": "NOBU2",
        "platform": "FC",
        "title": {"ja": "信長の野望・全国版", "zh": "信長之野望・全國版"},
        "source": {"producer": "famicom-re", "revision": revision(),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "nes", "label": "NES 64 色（色號＝NES 色號）",
                      "colors": [f"#{c:06x}" for c in NES_PALETTE]}],
        "blobs": ["pixels.bin"],
        "images": images,
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(blob)]


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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 nobu2-fc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Nobunaga no Yabou - Zenkoku Ban (Japan).zip 或 .nes")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    write_dataset(args.out, meta, blobs)
    print(f"nobu2-fc: {len(meta['characters'])} characters (all portrait), {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
