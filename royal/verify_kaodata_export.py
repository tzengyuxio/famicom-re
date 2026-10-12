#!/usr/bin/env python3
"""Independent checks for the royal-fc kaodata dataset.

1. Every character and portrait image in the dataset equals the face composed directly from the ROM
   tables (rom.Rom.face_pixels), and checksums.json matches a recomputation.
2. (needs py65) tools/nes_emu.py plays scenario 1 to the house-select screen. When the game calls the
   character face routine $DB3B (bank 30; arguments x, y, character record pointer $60AD + 10 * id)
   for the lord of ブランシェ, the pointer is replaced by each of the 64 characters in turn; the 5x6
   cells the game then puts in the name table / ExRAM, drawn with the game's BG palette, must equal
   the dataset portrait of that character pixel by pixel.
3. The 4 adviser faces on the real "そうだんやくはだれにしますか?" screen are compared the same way.
   The 23 unit faces are checked against the ROM tables only (not traced in the game).

Usage: .venv/bin/python royal/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import hashlib
import json
import os

from export_kaodata import FACES, checksums, get_image, san1
from rom import CHAR_COUNT, CHAR_START, DEFAULT_ROM, PORTRAIT_H, PORTRAIT_W, WRAM, Rom

FACE_ROUTINE = 0xDB3B
HOUSE_FACE_AT = (3, 15)                 # where the house-select screen draws the lord's face
ADVISERS_AT = [(3, 11), (9, 11), (3, 17), (9, 17)]
TO_ADVISERS = [("A", 60), ("A", 100), ("A", 100), ("A", 150)]


def screen_face(rom: Rom, nes, x: int, y: int) -> bytes:
    cells = [(y + k // PORTRAIT_W) * 32 + x + k % PORTRAIT_W for k in range(PORTRAIT_W * PORTRAIT_H)]
    tiles, exram = [nes.ciram[a] for a in cells], [nes.exram[a] for a in cells]
    return rom.render_cells(tiles, exram, PORTRAIT_W, bytes(nes.pal[:16]))


def check_static(rom: Rom, meta: dict, blobs: list[bytes], dataset: str) -> list[str]:
    errors = []
    if hashlib.sha1(rom.data).hexdigest() != meta["source"]["inputs"][0]["sha1"]:
        errors.append("ROM SHA-1 differs from source.inputs")
    for n, (t, f) in enumerate(FACES):
        if get_image(meta, blobs, meta["portraits"][n]["img"]) != (40, 48, rom.face_pixels(t, f)):
            errors.append(f"portrait {n} differs from the ROM tables")
    for c in meta["characters"]:
        if FACES[c["face"]["portrait"]] != (0, c["id"]):
            errors.append(f"character {c['id']} does not use face {c['id']}")
    with open(os.path.join(dataset, "checksums.json"), encoding="utf-8") as f:
        if json.load(f) != checksums(meta, blobs):
            errors.append("checksums.json differs from the reference renderer")
    print(f"[static] {len(FACES)} portraits, {len(meta['characters'])} characters, checksums")
    return errors


def check_emulated(rom: Rom, meta: dict, blobs: list[bytes], rom_path: str) -> list[str]:
    try:
        from tools.play import HOUSE_SELECT, boot
    except ImportError:
        print("[emulator] skipped (py65 not installed: uv pip install py65)")
        return []
    errors = []

    def portrait(n):
        return get_image(meta, blobs, meta["portraits"][n]["img"])[2]

    nes = boot(rom_path, HOUSE_SELECT)
    base = nes.snapshot()
    for i in range(CHAR_COUNT):
        nes.restore(base)
        seen = []

        def patch(n, i=i, seen=seen):
            sp = n.ram[2] | n.ram[3] << 8
            ptr = WRAM + CHAR_START + 10 * i
            seen.append(n.ram[sp + 2] | n.ram[sp + 4] << 8)
            n.ram[sp + 6], n.ram[sp + 7] = ptr & 0xFF, ptr >> 8
        nes.breakpoints[FACE_ROUTINE] = patch
        nes.press("A", 60)
        if seen[:1] != [HOUSE_FACE_AT[0] | HOUSE_FACE_AT[1] << 8]:
            errors.append(f"$DB3B not called at {HOUSE_FACE_AT} (got {seen})")
        elif screen_face(rom, nes, *HOUSE_FACE_AT) != portrait(FACES.index((0, i))):
            errors.append(f"character {i}: face drawn by $DB3B differs from the dataset")
    print(f"[emulator] {CHAR_COUNT} character faces drawn by the game's $DB3B")

    nes = boot(rom_path, TO_ADVISERS)
    for f, (x, y) in enumerate(ADVISERS_AT):
        if screen_face(rom, nes, x, y) != portrait(FACES.index((1, f))):
            errors.append(f"adviser {f} on the adviser screen differs from the dataset")
    print(f"[emulator] {len(ADVISERS_AT)} adviser faces on the adviser screen")
    return errors


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 royal-fc kaodata 資料集")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--dataset", required=True)
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = san1.load_dataset(args.dataset)
    errors = check_static(rom, meta, blobs, args.dataset) + check_emulated(rom, meta, blobs, args.rom)
    for e in errors[:20]:
        print("NG", e)
    print("All checks passed!" if not errors else f"{len(errors)} errors")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
