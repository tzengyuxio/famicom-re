#!/usr/bin/env python3
"""Independent checks for the nobu3-fc kaodata dataset.

1. Every character and portrait drawn by the spec renderer from the dataset equals the face
   composed directly from ROM tiles (rom.Rom.face_pixels), pixel by pixel.
2. checksums.json matches a recomputation.
3. (needs py65) The game's own face dispatcher ($D147 in bank 30, which calls $CF92 / $CFDE),
   run in an emulator, hands the draw-block service the same tile ids and ExRAM bytes as rom.py,
   for all 90 dedicated ids and every composite code (6 groups x 5^4 combinations, which include
   every code a character uses). Codes 90-0x7FFF must draw nothing.

Usage: .venv/bin/python gunyuu/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os

from export_kaodata import PORTRAIT_IDS, checksums, compose_display, san1
from rom import COMPOSITE_GROUPS, DEFAULT_ROM, PORTRAIT_COUNT, Rom


def check_pixels(rom: Rom, meta: dict, blobs: list[bytes]) -> tuple[int, set[int]]:
    from export import distinct_characters
    codes = {c["id"]: c["face_code"] for c in distinct_characters(rom)}
    errors = 0
    faces = [(f"ch:{c['id']} {c['name']}", c["face"], codes[c["id"]]) for c in meta["characters"] if "face" in c]
    faces += [(f"pt:{n}", {"portrait": n}, f) for n, f in enumerate(PORTRAIT_IDS)]
    for label, face, code in faces:
        w, h, px = compose_display(meta, blobs, face)
        if (w, h) != (40, 48) or px != rom.face_pixels(code):
            print(f"  NG {label}")
            errors += 1
    print(f"[pixels] {len(faces) - errors}/{len(faces)} faces match the ROM tile composition")
    return errors, set(codes.values())


def check_checksums(meta: dict, blobs: list[bytes], path: str) -> int:
    with open(path, encoding="utf-8") as f:
        stored = json.load(f)
    ok = stored == checksums(meta, blobs)
    print(f"[checksums] {'OK' if ok else 'MISMATCH'} ({len(stored['entries'])} entries)")
    return 0 if ok else 1


def check_emulated(rom: Rom, used: set[int]) -> int:
    try:
        from tools.pcode_emu import trace_face
    except ImportError:
        print("[emulator] skipped (py65 not installed: uv pip install py65)")
        return 0
    codes = set(range(PORTRAIT_COUNT)) | used
    for g in range(COMPOSITE_GROUPS):
        codes |= {0x8000 | g << 12 | (v // 125) << 9 | (v // 25 % 5) << 6 | (v // 5 % 5) << 3 | v % 5
                  for v in range(5 ** 4)}
    bad = [f"{c:04X}" for c in sorted(codes) if tuple(map(bytes, rom.face_cells(c))) != trace_face(rom.prg, c)]
    blank = [c for c in (PORTRAIT_COUNT, 0x100, 0x7FFF) if trace_face(rom.prg, c) is not None]
    print(f"[emulator] face dispatcher: {len(codes) - len(bad)}/{len(codes)} codes match"
          + (f" (NG {' '.join(bad[:10])})" if bad else "") + ("" if not blank else f"; drew for {blank}"))
    return len(bad) + len(blank)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 nobu3-fc kaodata 資料集")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--dataset", required=True)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = san1.load_dataset(args.dataset)
    errors, used = check_pixels(rom, meta, blobs)
    errors += check_checksums(meta, blobs, os.path.join(args.dataset, "checksums.json"))
    errors += check_emulated(rom, used)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
