#!/usr/bin/env python3
"""Independent checks for the suikoden-fc kaodata dataset.

1. Every character and portrait drawn by the spec renderer from the dataset equals
   the face composed directly from ROM tiles (rom.Rom.face_pixels), pixel by pixel.
2. checksums.json matches a recomputation.
3. (needs py65) The mob face layout and palettes match what the game's own face
   routine does, traced in an emulator for every category.

Usage: .venv/bin/python suikoden/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os

from export_kaodata import checksums, compose_display, san1
from rom import DEFAULT_ROM, MOB_CATEGORIES, MOB_LAYOUT, MOB_PALETTES, MOB_POINTERS, PORTRAIT_COUNT, Rom


def check_pixels(rom: Rom, meta: dict, blobs: list[bytes]) -> int:
    errors = 0
    faces = [(f"ch:{c['id']} {c['name']}", c["face"], rom.characters()[c["id"]]["face_code"])
             for c in meta["characters"]]
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


def check_emulated_layout(rom: Rom) -> int:
    try:
        from tools.pcode_emu import trace_face_copies
    except ImportError:
        print("[emulator] skipped (py65 not installed: uv pip install py65)")
        return 0
    errors = 0
    for cat in range(MOB_CATEGORIES):
        for code in (cat << 10, cat << 10 | 0x3FF, cat << 10 | 0x1B6):
            copies = trace_face_copies(rom.prg, code)
            tile_dst = copies[0][2]  # head tiles start the 5x6 tile buffer
            got = tuple(dst - tile_dst for _, _, dst, _ in copies[2:5])
            pal = copies[-1][1]
            expect_pal = 0xA000 + MOB_PALETTES - 0x28000 + cat * 8
            # part pointers (head, chin, eyes, nose, mouth) must be picked by the expected code fields
            fields = [(code >> 8) & 3, code & 3, (code >> 6) & 3, (code >> 4) & 3, (code >> 2) & 3]
            ptr = [MOB_POINTERS + cat * 0x50 + 2 * (slot * 4 + f) for slot, f in enumerate(fields)]
            srcs = [rom.prg[p] | rom.prg[p + 1] << 8 for p in ptr]
            if got != MOB_LAYOUT[cat] or pal != expect_pal or [c[1] for c in copies[:5]] != srcs:
                print(f"  NG cat {cat} code {code:04X}: layout {got} palette {pal:04X}")
                errors += 1
    print(f"[emulator] face routine layout/palette/parts {'OK' if not errors else 'MISMATCH'} "
          f"for {MOB_CATEGORIES} categories x 3 codes")
    return errors


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 suikoden-fc kaodata 資料集")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--dataset", required=True)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = san1.load_dataset(args.dataset)
    errors = check_pixels(rom, meta, blobs)
    errors += check_checksums(meta, blobs, os.path.join(args.dataset, "checksums.json"))
    errors += check_emulated_layout(rom)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
