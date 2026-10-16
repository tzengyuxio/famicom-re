#!/usr/bin/env python3
"""Export FC 麻雀大会 as a kaodata dataset (mahjong-fc, format kaodata/1).

Spec: docs/data-format.md of the kaodata website repo. Pixels are NES colour numbers and the
dataset palette is the 64-colour NES palette (faces use BG sub-palette 2 or 3, per player).

Portraits only: the game has no composite faces. Portrait n = player * 7 + expression is the
game's own face-layout number (bank 0 $8030, picked by $EBEC); the human player's face is P105
(group プレイヤー). Characters are the 15 CPU opponents: face = expression 0, the other six in
`expressions`, each with the label of when the game shows it. The ROM has no readings; names
drawn in kana get their hiragana form as `reading`.

Usage: .venv/bin/python mahjong/export_kaodata.py --out <dir> [--rom ROM]
"""
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import zlib

from rom import CPU_PLAYERS, DEFAULT_ROM, EXPRESSION_LABELS, EXPRESSIONS, HUMAN, NAMES, NES_PALETTE, Rom

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Spec §6 primitives shared with the san1-fc exporter (same module name, so load it by path)
_spec = importlib.util.spec_from_file_location("san1_kaodata", os.path.join(REPO, "sangokushi", "tools", "export_kaodata.py"))
san1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(san1)
get_image, to_rgba = san1.get_image, san1.to_rgba

FORMAT = "kaodata/1"
CANVAS = (32, 32)
HUMAN_PORTRAIT = CPU_PLAYERS * EXPRESSIONS


# ---------------------------------------------------------------- reference renderer (spec §6)

def compose_display(meta: dict, blobs: list[bytes], face: dict) -> tuple[int, int, bytes]:
    return get_image(meta, blobs, meta["portraits"][face["portrait"]]["img"])


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

def to_hiragana(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def reading(name: str) -> str | None:
    """Hiragana of a name drawn all in kana (・ between family and given name -> space); None for kanji."""
    if all("ァ" <= c <= "ヶ" or c in "ー・" for c in name):
        return to_hiragana(name).replace("・", " ")
    return None


def revision() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
                          cwd=REPO).stdout.strip()


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = Rom(rom_path)
    images, blob = [], bytearray()

    def add(px: bytes) -> int:
        images.append([len(blob), *CANVAS])
        blob.extend(px)
        return len(images) - 1

    # No code: the game derives the layout number from the seat's player and the expression, it stores no face value
    portraits = [{"img": add(rom.face_pixels(p, e))} for p in range(CPU_PLAYERS) for e in range(EXPRESSIONS)]
    portraits.append({"img": add(rom.face_pixels(HUMAN)), "group": "プレイヤー", "name": NAMES[HUMAN]})

    characters = []
    for p in range(CPU_PLAYERS):
        ch = {"id": p, "name": NAMES[p]}
        if (r := reading(NAMES[p])) is not None:
            ch["reading"] = r
        ch["face"] = {"portrait": p * EXPRESSIONS, "label": EXPRESSION_LABELS[0]}
        ch["expressions"] = [{"portrait": p * EXPRESSIONS + e, "label": EXPRESSION_LABELS[e]}
                             for e in range(1, EXPRESSIONS)]
        characters.append(ch)

    meta = {
        "format": FORMAT,
        "id": "mahjong-fc",
        "game": "MAHJONG",
        "platform": "FC",
        "title": {"ja": "麻雀大会", "zh": "麻雀大會"},
        "source": {"producer": "famicom-re", "revision": revision(),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 8},
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 mahjong-fc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Mahjong Taikai (Japan).zip 或 .nes")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    write_dataset(args.out, meta, blobs)
    print(f"mahjong-fc: {len(meta['characters'])} characters (all portrait, {EXPRESSIONS} looks each), "
          f"{len(meta['portraits'])} portraits, {len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
