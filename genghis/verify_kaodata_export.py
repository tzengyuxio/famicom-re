#!/usr/bin/env python3
"""Independent checks for the genghis-fc kaodata dataset.

1. Every character and portrait drawn by the spec renderer from the dataset equals the face
   composed directly from ROM tiles (rom.Rom.face_pixels), pixel by pixel, expressions included;
   every dedicated portrait is used by some face or expression.
2. checksums.json matches a recomputation.
3. (needs py65) The game draws every face code: boot the ROM, open the scenario menu, and when
   it picks モンゴルへん the portrait routine (bank 10 $80F7(x, y, face, flag)) gets each code
   in turn instead of テムジン's. The 40x48 screen area (tiles 2-6, 6-11; CHR-RAM, attributes,
   palette) must equal rom.face_pixels(code).

Usage: .venv/bin/python genghis/verify_kaodata_export.py --dataset <dir> [--rom ROM] [--no-emu]
"""
import argparse
import json
import os

from export_kaodata import checksums, compose_display, people, san1
from rom import DEFAULT_ROM, PORTRAIT_COUNT, SCENARIOS, Rom

FACE_ROUTINE = 0x80F7   # bank 10, args (x, y, face code, flag); called with (2, 6, code, 4) on the menu
FACE_X, FACE_Y = 2, 6


def check_pixels(rom: Rom, meta: dict, blobs: list[bytes]) -> int:
    errors = 0
    faces = [(f"ch:{c['id']} {c['name']}", c["face"], p["face_code"])
             for c, p in zip(meta["characters"], people(rom))]
    faces += [(f"ch:{c['id']}/{k} {c['name']}", e, code)
              for c, p in zip(meta["characters"], people(rom))
              for k, (e, code) in enumerate(zip(c.get("expressions", []), p["expressions"]), 1)]
    faces += [(f"pt:{n}", {"portrait": n}, n) for n in range(PORTRAIT_COUNT)]
    for label, face, code in faces:
        w, h, px = compose_display(meta, blobs, face)
        if (w, h) != (40, 48) or px != rom.face_pixels(code):
            print(f"  NG {label}")
            errors += 1
    print(f"[pixels] {len(faces) - errors}/{len(faces)} faces match the ROM tile composition")
    used = {f["portrait"] for c in meta["characters"] for f in [c.get("face", {}), *c.get("expressions", [])]
            if "portrait" in f}
    unused = sorted(set(range(PORTRAIT_COUNT)) - used)
    print(f"[portraits] {PORTRAIT_COUNT - len(unused)}/{PORTRAIT_COUNT} used by a face or expression"
          + (f" (unused {unused})" if unused else ""))
    return errors + len(unused)


def check_checksums(meta: dict, blobs: list[bytes], path: str) -> int:
    with open(path, encoding="utf-8") as f:
        stored = json.load(f)
    ok = stored == checksums(meta, blobs)
    print(f"[checksums] {'OK' if ok else 'MISMATCH'} ({len(stored['entries'])} entries)")
    return 0 if ok else 1


def all_codes(rom: Rom) -> list[int]:
    codes = set(range(PORTRAIT_COUNT))
    for sc in SCENARIOS:
        s = rom.scenario(sc)
        for p in s["rulers"] + s["generals"] + s["heirs"] + s["extra"]:
            if p["face"] & 0x8000 and p["face"] != 0x8000:
                codes.add(p["face"])
    return sorted(codes)


def check_emulated(rom_path: str, rom: Rom) -> int:
    try:
        from tools.emu import TO_SCENARIO_MENU, Nes
    except ImportError:
        print("[emulator] skipped (py65 not installed: uv pip install py65)")
        return 0
    nes = Nes(rom_path)
    nes.play(TO_SCENARIO_MENU)
    start = nes.snapshot()
    errors, codes = 0, all_codes(rom)
    for code in codes:
        nes.restore(start)
        calls = []

        def hook(n, a, code=code, calls=calls):
            if a == FACE_ROUTINE and n.prgreg == 10:
                sp = n.ram[2] | n.ram[3] << 8
                calls.append(n.ram[sp + 6] | n.ram[sp + 7] << 8)
                n.ram[sp + 6], n.ram[sp + 7] = code & 0xFF, code >> 8

        nes.read_hook = hook
        nes.press("A", 60)
        nes.run(150)
        nes.read_hook = None
        got = nes.bg_pixels(FACE_X, FACE_Y, 5, 6)
        if not calls or got != rom.face_pixels(code):
            print(f"  NG face {code:04X}: routine called {len(calls)}x, "
                  f"{sum(a != b for a, b in zip(got, rom.face_pixels(code)))} pixels differ")
            errors += 1
    mobs = sum(c >= 0x8000 for c in codes)
    print(f"[emulator] {len(codes) - errors}/{len(codes)} face codes drawn by the game match "
          f"({len(codes) - mobs} dedicated, {mobs} composite)")
    return errors


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 genghis-fc kaodata 資料集")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--no-emu", action="store_true", help="略過模擬器比對")
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = san1.load_dataset(args.dataset)
    errors = check_pixels(rom, meta, blobs)
    errors += check_checksums(meta, blobs, os.path.join(args.dataset, "checksums.json"))
    if not args.no_emu:
        errors += check_emulated(args.rom, rom)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
