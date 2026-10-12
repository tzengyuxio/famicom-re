#!/usr/bin/env python3
"""Export FC 蒼き狼と白き牝鹿・ジンギスカン as a kaodata dataset (genghis-fc, format kaodata/1).

Spec: docs/data-format.md of the kaodata website repo. Pixels are NES colour numbers and the
dataset palette is the 64-colour NES palette (every face uses BG sub-palette 3E 27 38 30).

Usage: .venv/bin/python genghis/export_kaodata.py --out <dir> [--rom ROM]
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
    FACE_PALETTE,
    MOB_CATEGORIES,
    MOB_CHOICES,
    MOB_PARTS,
    NES_PALETTE,
    PORTRAIT_COUNT,
    SCENARIOS,
    Rom,
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
# Part rectangle on the canvas (x, y, w, h); the frame keeps the full canvas with a transparent hole
PART_RECT = {"head": (0, 0, 40, 48), "eyes": (8, 16, 24, 8), "nose": (8, 24, 24, 8), "mouth": (8, 32, 24, 16)}


# ---------------------------------------------------------------- reference renderer (spec §6)

def compose_display(meta: dict, blobs: list[bytes], face: dict) -> tuple[int, int, bytes]:
    if "portrait" in face:
        return get_image(meta, blobs, meta["portraits"][face["portrait"]]["img"])
    comp = meta["composite"]
    variant = comp["variants"][face["variant"]]
    cw, ch = comp["canvas"]
    canvas = bytearray([TRANSPARENT]) * (cw * ch)
    for slot, part in zip(comp["slots"], face["parts"]):
        sp = variant["parts"][slot["id"]]
        x, y = sp.get("at", [0, 0])
        blit(canvas, cw, ch, get_image(meta, blobs, sp["items"][part]), x, y)
    return cw, ch, bytes(canvas)


def checksums(meta: dict, blobs: list[bytes]) -> dict:
    colors = meta["palettes"][0]["colors"]

    def digest(face: dict) -> str:
        return hashlib.sha256(to_rgba(compose_display(meta, blobs, face), colors)).hexdigest()

    entries = {f"ch:{c['id']}": digest(c["face"]) for c in meta["characters"] if "face" in c}
    entries.update({f"pt:{n}": digest({"portrait": n}) for n in range(len(meta["portraits"]))})
    return {"algo": "sha256-rgba", "entries": entries}


# ---------------------------------------------------------------- dataset

def to_hiragana(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def people(rom: Rom) -> list[dict]:
    """Distinct named people (name + face code) over both scenarios, women with their first portrait."""
    seen, out = set(), []

    def add(name: str, code: int, role: str, sc: str) -> None:
        if (name, code) in seen:
            return
        seen.add((name, code))
        out.append({"name": name, "face_code": code, "role": role, "scenario": sc})

    for sc in SCENARIOS:
        s = rom.scenario(sc)
        for p in s["rulers"]:
            add(p["name"], p["face"], "ruler", sc)
        for p in s["generals"]:
            add(p["name"], p["face"], "general", sc)
        for p in s["heirs"]:
            add(p["name"], p["face"], "heir", sc)
    for w in rom.women():
        add(w["name"], w["portraits"][0], "woman", w["scenario"])
    return out


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

    def part_image(cat: int, slot: int, choice: int) -> int:
        x, y, w, h = PART_RECT[MOB_PARTS[slot][0]]
        full = rom.mob_part(cat, slot, choice)
        px = bytes(TRANSPARENT if (v := full[(y + j) * 40 + x + i]) == 255 else FACE_PALETTE[v]
                   for j in range(h) for i in range(w))
        return add(w, h, px)

    variants = [{"id": str(cat), "label": f"類型 {cat}",
                 "parts": {sid: {"at": list(PART_RECT[sid][:2]),
                                 "items": [part_image(cat, slot, k) for k in range(MOB_CHOICES[cat])]}
                           for slot, (sid, *_) in enumerate(MOB_PARTS)}}
                for cat in range(MOB_CATEGORIES)]

    portraits = [{"img": add(*CANVAS, rom.face_pixels(n), blob=1), "label": f"P{n:02d}"}
                 for n in range(PORTRAIT_COUNT)]

    characters = []
    for i, p in enumerate(people(rom)):
        ch = {"id": i, "name": p["name"], "reading": to_hiragana(p["name"]).replace("　", " ")}
        code = p["face_code"]
        if code & 0x8000:
            ch["face"] = {"variant": (code >> 12) & 3, "parts": [(code >> shift) & 7 for *_, shift in MOB_PARTS],
                          "code": f"{code:04X}"}
        else:
            ch["face"] = {"portrait": code}
        characters.append(ch)

    meta = {
        "format": FORMAT,
        "id": "genghis-fc",
        "game": "GENGHIS",
        "platform": "FC",
        "title": {"ja": "蒼き狼と白き牝鹿・ジンギスカン", "zh": "蒼狼與白鹿・成吉思汗"},
        "source": {"producer": "fc-sangokushi", "revision": revision(),
                   "inputs": [{"path": os.path.basename(rom_path), "sha1": hashlib.sha1(rom.data).hexdigest()}]},
        "display": {"scale": 6},
        "palettes": [{"id": "nes", "label": "NES 64 色（色號＝NES 色號）",
                      "colors": [f"#{c:06x}" for c in NES_PALETTE]}],
        "blobs": ["pixels.bin", "portraits.bin"],
        "images": images,
        "composite": {
            "canvas": list(CANVAS),
            "slots": [{"id": sid, "label": label} for sid, label, *_ in MOB_PARTS],
            "variants": variants,
            "code": {"kind": "bitfield", "bits": 16, "fields": [
                {"of": "$variant", "hi": 13, "lo": 12},
                {"of": "head", "hi": 11, "lo": 9},
                {"of": "eyes", "hi": 8, "lo": 6},
                {"of": "nose", "hi": 5, "lo": 3},
                {"of": "mouth", "hi": 2, "lo": 0},
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
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 genghis-fc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="Aoki Ookami to Shiroki Mejika - Genghis Khan (Japan).nes")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c["face"] for c in chars if "variant" in c["face"]]
    print(f"genghis-fc: {len(chars)} characters ({len(chars) - len(mobs)} portrait, {len(mobs)} composite, "
          f"{len({f['code'] for f in mobs})} distinct codes), {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        print(f"  {name}: {os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
