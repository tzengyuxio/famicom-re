#!/usr/bin/env python3
"""Independent checks for the nobu4-fc kaodata dataset.

1. Every character and portrait drawn by the spec renderer from the dataset equals the face
   composed directly from ROM tiles (rom.Rom.face_pixels), pixel by pixel.
2. checksums.json matches a recomputation.
3. (needs py65) The game's own face dispatcher ($A174 with banks 7 / 58), run in an emulator,
   hands the image service the same tile ids and ExRAM bytes as rom.py, for all 212 dedicated
   ids, every composite code used by a character, every head x page x area, and a fixed
   pseudo-random sample of 200 full combinations.
4. Static check of the two portraits no character uses (168 沢彦, 169 ルイス=フロイス): the game
   sets them by constant face codes (push code, call the setter $A7A9 in bank 0), and next to
   each call sits the person's name (message 0x4D of bank 20 for 沢彦; the branch on visitor
   type $7D94 == 9, whose name in the bank 16 visitor table is ﾙｲｽ=ﾌﾛｲｽ, for Frois).

Usage: .venv/bin/python bushou/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import json
import os
import re

from export_kaodata import SPECIAL_PORTRAITS, checksums, compose_display, san1
from rom import COMPOSITE_HEADS, COMPOSITE_SLOTS, DEFAULT_ROM, PORTRAIT_COUNT, Rom, text

# face setter far call: push code, push x, push y, push $A7A9, push bank selector C0 (bank 0), call $F304
SETTER_CALL = rb"\x8e(.)\x00[\x60-\x6f][\x60-\x6f]\x8e\xa9\xa7\x8e\xc0\x00\x62\xe9\x04\xf3"
# where each special portrait is set (PRG offset of the push) -- bank 6 is the save/quit screen
SPECIAL_CALLS = {168: [0x22F0C, 0x22F48], 169: [0xC86F, 0x20631]}


def check_pixels(rom: Rom, meta: dict, blobs: list[bytes]) -> tuple[int, set[int]]:
    from export import distinct_characters
    codes = {c["id"]: c["face_code"] for c in distinct_characters(rom)}
    errors = 0
    faces = [(f"ch:{c['id']} {c['name']}", c["face"], codes[c["id"]]) for c in meta["characters"] if "face" in c]
    faces += [(f"pt:{n}", {"portrait": n}, n) for n in range(PORTRAIT_COUNT)]
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
    for head in range(COMPOSITE_HEADS):
        for _, _, bit in COMPOSITE_SLOTS:
            codes |= {0x8000 | page << bit | head for page in range(4)}
    x = 1
    for _ in range(200):  # plus a fixed pseudo-random sample of full combinations
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        codes.add(0x8000 | (x >> 8) & 0x1FF8 | (x >> 4) % COMPOSITE_HEADS)
    bad = []
    for code in sorted(codes):
        if (tuple(map(bytes, rom.face_cells(code)))) != trace_face(rom.prg, code):
            bad.append(f"{code:04X}")
    print(f"[emulator] face dispatcher: {len(codes) - len(bad)}/{len(codes)} codes match"
          + (f" (NG {' '.join(bad[:10])})" if bad else ""))
    return len(bad)


def check_special(rom: Rom, meta: dict) -> int:
    p, errors = rom.prg, 0
    for n, name in SPECIAL_PORTRAITS.items():
        pt = meta["portraits"][n]
        found = [m.start() for m in re.finditer(SETTER_CALL, p, re.DOTALL) if m[1][0] == n]
        if found != SPECIAL_CALLS[n] or (pt.get("group"), pt.get("name"), pt.get("code")) != ("特殊人物", name, f"{n:04X}"):
            print(f"  NG F{n}: calls {[hex(x) for x in found]}, portrait {pt}")
            errors += 1
    # 沢彦: the bank 17 function at $AEE5 prints message 0x4D (8d 4d e9 29 82) after setting face 168
    msg = 0x28000 + (p[0x28F04 + 2 * 0x4D] | p[0x28F05 + 2 * 0x4D] << 8) - 0xA000
    if b"\x8d\x4d\xe9\x29\x82" not in p[0x22F48:0x22F70] or "沢彦" not in text(p[msg:msg + 40]):
        print("  NG 沢彦 label message")
        errors += 1
    # Frois: face 169 in bank 16 is set right after `if $7D94 == 9`; visitor name 9 of the table at $9DD9
    name = 0x20000 + (p[0x21DD9 + 18] | p[0x21DDA + 18] << 8) - 0x8000
    if p[0x20629:0x2062F] != b"\xa5\x94\x7d\x59\xc0\xd8" or "ﾌﾛｲｽ" not in text(p[name:name + 20]):
        print("  NG フロイス visitor branch")
        errors += 1
    print(f"[special] {'OK' if not errors else 'NG'}: F168 沢彦, F169 ルイス=フロイス set by constant codes "
          f"({sum(map(len, SPECIAL_CALLS.values()))} call sites)")
    return errors


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 nobu4-fc kaodata 資料集")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--dataset", required=True)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = san1.load_dataset(args.dataset)
    errors, used = check_pixels(rom, meta, blobs)
    errors += check_checksums(meta, blobs, os.path.join(args.dataset, "checksums.json"))
    errors += check_emulated(rom, used)
    errors += check_special(rom, meta)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
