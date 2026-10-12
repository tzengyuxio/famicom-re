#!/usr/bin/env python3
"""Independent checks for the san2-fc kaodata dataset.

1. Every character and portrait drawn by the spec renderer from the dataset equals the face
   composed directly from ROM tiles (rom.Rom.face_pixels), pixel by pixel.
2. checksums.json matches a recomputation.
3. (needs py65) The game itself, in tools/nes_emu.py, draws the same tile ids and ExRAM bytes as
   rom.Rom.face_cells: tools/play.py opens 紀霊's page in 情報/ぶしょう; for each face code his
   code is patched in the emulated ROM and the 5x6 face cells of the name table are compared.
   Codes: dedicated 1-200, every composite code a general uses, and per group every variant of
   every slot.

Usage: .venv/bin/python san2/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os

from export_kaodata import VARIANTS, checksums, compose_display, san1, slot_code
from rom import COMP_GROUPS, COMP_SLOTS, DEFAULT_ROM, FACE_COUNT, PERSONAL, Rom

KIREI = 60
FACE_X, FACE_Y = 3, 13  # name table cell of the face's top-left on the general page


def check_pixels(rom: Rom, meta: dict, blobs: list[bytes]) -> int:
    codes = {g["id"]: g["face"] for g in rom.generals()}
    faces = [(f"ch:{c['id']} {c['name']}", c["face"], codes[c["id"]]) for c in meta["characters"]]
    faces += [(f"pt:{n}", {"portrait": n}, n + 1) for n in range(len(meta["portraits"]))]
    errors = 0
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


def check_emulated(rom: Rom, rom_path: str) -> int:
    try:
        from tools.play import TO_COMMAND, TO_GENERAL_LIST, TO_KIREI, boot, play
    except ImportError:
        print("[emulator] skipped (py65 not installed: uv pip install py65)")
        return 0
    codes = set(range(1, FACE_COUNT + 1)) | {g["face"] for g in rom.generals()}
    codes |= {slot_code(g, s, v) for g in range(COMP_GROUPS) for s in range(len(COMP_SLOTS)) for v in range(VARIANTS)}
    nes = boot(rom_path, TO_COMMAND, TO_GENERAL_LIST, TO_KIREI)
    start, bad = nes.snapshot(), []
    for code in sorted(codes):
        nes.restore(start)
        prg = bytearray(rom.prg)
        prg[PERSONAL + 9 * KIREI + 7:PERSONAL + 9 * KIREI + 9] = code.to_bytes(2, "little")
        nes.prg = bytes(prg)
        play(nes, [("A", 3, 120)])
        cells = [(FACE_Y + i // 5) * 32 + FACE_X + i % 5 for i in range(30)]
        got = ([nes.nt_read(0x2000 + a) for a in cells], [nes.exram[a] for a in cells])
        if got != rom.face_cells(code):
            bad.append(f"{code:04X}")
    print(f"[emulator] general page: {len(codes) - len(bad)}/{len(codes)} face codes match"
          + (f" (NG {' '.join(bad[:10])})" if bad else ""))
    return len(bad)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 san2-fc kaodata 資料集")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--dataset", required=True)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = san1.load_dataset(args.dataset)
    errors = check_pixels(rom, meta, blobs)
    errors += check_checksums(meta, blobs, os.path.join(args.dataset, "checksums.json"))
    errors += check_emulated(rom, args.rom)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
