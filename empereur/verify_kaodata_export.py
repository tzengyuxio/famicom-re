#!/usr/bin/env python3
"""Independent checks for the empereur-fc kaodata dataset.

1. Every character and portrait drawn by the spec renderer from the dataset equals the face
   composed directly from ROM tiles (rom.Rom.face_pixels), pixel by pixel.
2. checksums.json matches a recomputation.
3. (needs py65) The game's own face routine (bank 0 $A1F6), run in an emulator, hands the image
   service the same tile ids and ExRAM bytes as rom.py, for all 90 portraits and all 4096
   composite codes (category x 5 two-bit parts).

Usage: .venv/bin/python empereur/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os

from export_kaodata import checksums, compose_display, san1
from rom import DEFAULT_ROM, PORTRAIT_COUNT, Rom


def check_pixels(rom: Rom, meta: dict, blobs: list[bytes]) -> int:
    codes = {c["id"]: c["face_code"] for c in rom.characters()}
    errors = 0
    faces = [(f"ch:{c['id']} {c['name']}", c["face"], codes[c["id"]]) for c in meta["characters"] if "face" in c]
    faces += [(f"pt:{n}", {"portrait": n}, n) for n in range(PORTRAIT_COUNT)]
    for label, face, code in faces:
        w, h, px = compose_display(meta, blobs, face)
        if (w, h) != (40, 48) or px != rom.face_pixels(code):
            print(f"  NG {label}")
            errors += 1
    print(f"[pixels] {len(faces) - errors}/{len(faces)} faces match the ROM tile composition")
    return errors


def check_checksums(meta: dict, blobs: list[bytes], path: str) -> int:
    with open(path, encoding="utf-8") as f:
        stored = json.load(f)
    ok = stored == checksums(meta, blobs)
    print(f"[checksums] {'OK' if ok else 'MISMATCH'} ({len(stored['entries'])} entries)")
    return 0 if ok else 1


def check_emulated(rom: Rom) -> int:
    try:
        from tools.pcode_emu import trace_face
    except ImportError:
        print("[emulator] skipped (py65 not installed: uv pip install py65)")
        return 0
    codes = list(range(PORTRAIT_COUNT)) + [0x8000 | v for v in range(0x1000)]
    bad = []
    for code in codes:
        tiles, exram = rom.face_cells(code)
        if (bytes(tiles), bytes(exram)) != trace_face(rom.prg, code):
            bad.append(f"{code:04X}")
    print(f"[emulator] face routine: {len(codes) - len(bad)}/{len(codes)} codes match"
          + (f" (NG {' '.join(bad[:10])})" if bad else ""))
    return len(bad)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 empereur-fc kaodata 資料集")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--dataset", required=True)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = san1.load_dataset(args.dataset)
    errors = check_pixels(rom, meta, blobs)
    errors += check_checksums(meta, blobs, os.path.join(args.dataset, "checksums.json"))
    errors += check_emulated(rom)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
