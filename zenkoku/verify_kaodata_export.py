#!/usr/bin/env python3
"""Independent checks for the nobu2-fc kaodata dataset.

1. Every character and portrait drawn by the spec renderer from the dataset equals the face
   composed directly from ROM tiles (rom.Rom.face_pixels), pixel by pixel.
2. checksums.json matches a recomputation.
3. (needs py65) The game itself, run in tools/emu.py: picking each of the 50 provinces (and the
   17 of the 17-mode) shows the daimyo screen; its 6x6-tile face at screen tile (4, 12) must equal
   the portrait rom.py gives that daimyo. Portraits 50-74 have no province, so each one is swapped
   into Oda's slot (pointer entry + layout, PRG copy only) and drawn the same way.

Usage: .venv/bin/python zenkoku/verify_kaodata_export.py --dataset <dir> [--rom ROM] [--no-emu]
"""
import argparse
import json
import os

from export_kaodata import checksums, compose_display, san1
from rom import DEFAULT_ROM, MODES, PORTRAIT_COUNT, PORTRAIT_LAYOUT, PORTRAIT_PTRS, Rom

FACE_X, FACE_Y = 4, 12
ODA = 24


def check_pixels(rom: Rom, meta: dict, blobs: list[bytes]) -> int:
    errors = 0
    faces = [(f"ch:{c['id']} {c['name']}", c["face"]) for c in meta["characters"]]
    faces += [(f"pt:{n}", {"portrait": n}) for n in range(PORTRAIT_COUNT)]
    for label, face in faces:
        w, h, px = compose_display(meta, blobs, face)
        if (w, h) != (48, 48) or px != rom.face_pixels(face["portrait"]):
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
        from tools.emu import Nes, pick_province, to_province_prompt
    except ImportError:
        print("[emulator] skipped (py65 not installed: uv pip install py65)")
        return 0
    errors, shown = 0, set()
    for mode in MODES:
        nes = Nes(rom_path)
        nes.play(to_province_prompt(mode))
        start = nes.snapshot()
        bad = []
        for p in range(MODES[mode][1]):
            nes.restore(start)
            nes.play(pick_province(p + 1) + [("LEFT", 200)])
            face = rom.global_daimyo(mode, p)
            shown.add(face)
            if nes.bg_pixels(FACE_X, FACE_Y, 6, 6) != rom.face_pixels(face):
                bad.append(p + 1)
        print(f"[emulator] {mode}-mode daimyo screens: {MODES[mode][1] - len(bad)}/{MODES[mode][1]} faces match"
              + (f" (NG provinces {bad})" if bad else ""))
        errors += len(bad)
    # remaining portraits through Oda's slot (50 mode, province 25)
    nes = Nes(rom_path)
    nes.play(to_province_prompt(50))
    start = nes.snapshot()
    rest = [n for n in range(PORTRAIT_COUNT) if n not in shown]
    bad = []
    for n in rest:
        prg = bytearray(rom.prg)
        prg[PORTRAIT_PTRS + 4 * ODA:PORTRAIT_PTRS + 4 * ODA + 4] = rom.prg[PORTRAIT_PTRS + 4 * n:PORTRAIT_PTRS + 4 * n + 4]
        prg[PORTRAIT_LAYOUT + 36 * ODA:PORTRAIT_LAYOUT + 36 * ODA + 36] = \
            rom.prg[PORTRAIT_LAYOUT + 36 * n:PORTRAIT_LAYOUT + 36 * n + 36]
        nes.restore(start)
        nes.prg = bytes(prg)
        nes.play(pick_province(ODA + 1) + [("LEFT", 200)])
        if nes.bg_pixels(FACE_X, FACE_Y, 6, 6) != rom.face_pixels(n):
            bad.append(n)
    print(f"[emulator] portraits swapped into Oda's slot: {len(rest) - len(bad)}/{len(rest)} match"
          + (f" (NG {bad})" if bad else ""))
    return errors + len(bad)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 nobu2-fc kaodata 資料集")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--no-emu", action="store_true", help="略過模擬器檢查")
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = san1.load_dataset(args.dataset)
    errors = check_pixels(rom, meta, blobs)
    errors += check_checksums(meta, blobs, os.path.join(args.dataset, "checksums.json"))
    if not args.no_emu:
        errors += check_emulated(rom, args.rom)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
