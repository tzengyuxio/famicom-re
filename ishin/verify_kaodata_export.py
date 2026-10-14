#!/usr/bin/env python3
"""Independent checks for the ishin-fc kaodata dataset.

1. Every character and portrait drawn by the spec renderer from the dataset equals the face
   composed directly from ROM tiles (rom.Rom.face_pixels), pixel by pixel.
2. checksums.json matches a recomputation.
3. (needs py65, about 4 minutes) The game itself draws every face: the emulator boots a new game
   (scenario 1, 公議, 坂本龍馬), opens 情報 → じぶん, and for each face code patches 龍馬's face
   code in the ROM and reopens the screen. The 40x48 face area of the emulated screen must equal
   rom.Rom.face_pixels for all character face codes and all 87 portraits.
4. The 藩兵 portrait: no name-table entry uses face code 0x57, the face routine (bank 0 $8003)
   pushes the constant 0x57 when $DAA8 (id >= 201) is true, and only that portrait has
   group "藩兵". With the emulator, the じぶん screen draws face 0x57 when the id passed to $DAA8
   is changed to 201 (the first troop).

Usage: .venv/bin/python ishin/verify_kaodata_export.py --dataset <dir> [--rom ROM] [--no-emulator]
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from export_kaodata import TROOP_FACE, checksums, compose_display, san1
from rom import DEFAULT_ROM, GIVEN_AT, GIVEN_COUNT, NAME_BANK, PORTRAIT_COUNT, Rom

# Power-on to the 情報 menu of a new game as 坂本龍馬 (frames per press)
BOOT = ("wait:360 " + "A:120 " * 8 + "START:120 A:120 A:120 A:120 START:200 START:200 A:200 A:200 RIGHT:30 "
        "A:200 A:200 A:200 A:200 A:1500 RIGHT:20 RIGHT:20 RIGHT:20 A:120")
FACE_X, FACE_Y = 16, 24  # face sprites on the じぶん screen


def play(nes, script: str) -> None:
    for tok in script.split():
        button, frames = tok.split(":")
        if button == "wait":
            nes.run(int(frames))
        else:
            nes.press(button, int(frames))


def check_pixels(rom: Rom, meta: dict, blobs: list[bytes]) -> int:
    codes = {c["id"]: c["face_code"] for c in rom.characters(0)}
    errors = 0
    faces = [(f"ch:{c['id']} {c['name']}", c["face"], codes[c["id"]]) for c in meta["characters"] if "face" in c]
    faces += [(f"pt:{n}", {"portrait": n}, n + 1) for n in range(PORTRAIT_COUNT)]
    for label, face, code in faces:
        w, h, px = compose_display(meta, blobs, face)
        if (w, h) != (40, 48) or px != rom.face_pixels(code):
            print(f"  NG {label}")
            errors += 1
    print(f"[pixels] {len(faces) - errors}/{len(faces)} faces match the ROM tile composition")
    bad = [n for n, pt in enumerate(meta["portraits"]) if pt.get("code") != f"{n + 1:04X}"]
    print(f"[codes] {PORTRAIT_COUNT - len(bad)}/{PORTRAIT_COUNT} portrait codes are record + 1")
    return errors + len(bad)


def check_troop(rom: Rom, meta: dict) -> int:
    p = rom.prg
    used = {p[nb + GIVEN_AT + 10 * i + 7] | p[nb + GIVEN_AT + 10 * i + 8] << 8
            for nb in NAME_BANK for i in range(GIVEN_COUNT)}
    branch = p[0x22:0x2A] == bytes([0x3E, 0xE9, 0xA8, 0xDA, 0x02, 0xD8, 0x5D, 0x80])  # if troop(id) goto $805D
    push = p[0x5D:0x5F] == bytes([0x89, TROOP_FACE])                                   # $805D: push 0x57
    test = p[30 * 0x2000 + 0x1AA8:30 * 0x2000 + 0x1AAF] == bytes([0xA0, 0x02, 0xB1, 0x02, 0xC9, 0xC9, 0xB0])
    groups = {n: pt["group"] for n, pt in enumerate(meta["portraits"]) if "group" in pt}
    ok = TROOP_FACE not in used and branch and push and test and groups == {TROOP_FACE - 1: "藩兵"}
    print(f"[troop] {'OK' if ok else 'NG'}: face {TROOP_FACE:04X} unused by people, drawn for ids >= 201, "
          f"group {groups}")
    return 0 if ok else 1


def check_checksums(meta: dict, blobs: list[bytes], path: str) -> int:
    with open(path, encoding="utf-8") as f:
        stored = json.load(f)
    ok = stored == checksums(meta, blobs)
    print(f"[checksums] {'OK' if ok else 'MISMATCH'} ({len(stored['entries'])} entries)")
    return 0 if ok else 1


def check_emulated(rom: Rom, rom_path: str) -> int:
    try:
        sys.path.insert(0, os.path.join(HERE, "tools"))
        from nes_emu import Nes
    except ImportError:
        print("[emulator] skipped (py65 not installed: uv pip install py65)")
        return 0
    nes = Nes(rom_path)
    play(nes, BOOT)
    state = nes.snapshot()
    at = NAME_BANK[0] + GIVEN_AT + 7  # 龍馬's face code
    codes = sorted({c["face_code"] for c in rom.characters(0)} | set(range(1, PORTRAIT_COUNT + 1)))
    bad = []
    for code in codes:
        prg = bytearray(rom.prg)
        prg[at], prg[at + 1] = code & 0xFF, code >> 8
        nes.restore(state)
        nes.prg = bytes(prg)
        play(nes, "RIGHT:30 A:120")
        screen = nes.render()
        px = bytes(screen[FACE_Y + y][FACE_X + x] & 0x3F for y in range(48) for x in range(40))
        if px != rom.face_pixels(code):
            bad.append(f"{code:04X}")
    print(f"[emulator] じぶん screen: {len(codes) - len(bad)}/{len(codes)} face codes match"
          + (f" (NG {' '.join(bad[:10])})" if bad else ""))

    def as_troop(n) -> None:  # bank 0 $8026: the face routine asks $DAA8 whether its id is a troop
        sp = n.ram[2] | n.ram[3] << 8
        if n.prg_bank(0x8000) == 0 and n.ram[6] | n.ram[7] << 8 == 0x8026:
            n.ram[sp + 2] = 201
    nes.restore(state)
    nes.prg = rom.prg
    nes.breakpoints[0xDAA8] = as_troop
    play(nes, "RIGHT:30 A:120")
    screen = nes.render()
    px = bytes(screen[FACE_Y + y][FACE_X + x] & 0x3F for y in range(48) for x in range(40))
    troop = px == rom.face_pixels(TROOP_FACE)
    print(f"[emulator] id 201 (藩兵) draws face {TROOP_FACE:04X}: {'OK' if troop else 'NG'}")
    return len(bad) + (0 if troop else 1)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 ishin-fc kaodata 資料集")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--no-emulator", action="store_true", help="略過模擬器比對")
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = san1.load_dataset(args.dataset)
    errors = check_pixels(rom, meta, blobs)
    errors += check_troop(rom, meta)
    errors += check_checksums(meta, blobs, os.path.join(args.dataset, "checksums.json"))
    if not args.no_emulator:
        errors += check_emulated(rom, args.rom)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
