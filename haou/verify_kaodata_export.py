#!/usr/bin/env python3
"""Check a haou-fc kaodata dataset against the game's own code, run in tools/nes_emu.py.

For every general the emulator runs the status-screen face routine $CE37 (bank 26 at $C000, $0000 =
general id, X = 0, expression $A4 = 0): it picks the 1 KB CHR bank ($CED6, left in $B8), the head and
eye/mouth sprite lists ($99A0 / $9AA0 / $9BAC) and writes the 20 sprites to the OAM buffer $0200 via
$F1B7. Those sprites are drawn from CHR with the bank in slot 2 and sprite sub-palette 3 of the game's
palette, then compared pixel by pixel with the dataset portrait of that character. The face of 劉備 on
the real lord-select screen (after power-on) is compared too. Then the dataset checksums are
recomputed with the reference renderer.

Usage: .venv/bin/python haou/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import hashlib
import json
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
from export_kaodata import checksums, get_image
from nes_emu import Nes
from rom import DEFAULT_ROM, FACE_H, FACE_PALETTE, FACE_W, GENERAL_COUNT, Rom

FACE_SPRITES = 20
Y_ORIGIN, X_ORIGIN = 0xA7, 0x10   # $0A / $0C as the status screen sets them
TO_LORD_STATUS = [("START", 120), ("A", 120), ("START", 120), ("START", 120), ("A", 120), ("A", 200)]


def load(dataset: str) -> tuple[dict, list[bytes]]:
    with open(os.path.join(dataset, "dataset.json"), encoding="utf-8") as f:
        meta = json.load(f)
    with open(os.path.join(dataset, "pixels.bin"), "rb") as f:
        return meta, [zlib.decompress(f.read(), -15)]


def draw_oam(nes: Nes, oam: list[bytes], bank: int, pal: bytes) -> bytes:
    """Face sprites (OAM order, lower index wins) with `bank` in CHR slot 2, origin at the template's."""
    saved = list(nes.chrreg)
    nes.chrreg[2] = bank
    px, done = bytearray([pal[0]]) * (FACE_W * FACE_H), [False] * (FACE_W * FACE_H)
    for y, tile, attr, x in oam:
        for dy in range(8):
            lo, hi = nes.vram_read(tile * 16 + dy), nes.vram_read(tile * 16 + dy + 8)
            for dx in range(8):
                b = dx if attr & 0x40 else 7 - dx
                c = ((lo >> b) & 1) | (((hi >> b) & 1) << 1)
                i = (y - Y_ORIGIN + dy) * FACE_W + x - X_ORIGIN + dx
                if c and not done[i]:
                    px[i], done[i] = pal[(attr & 3) * 4 + c], True
    nes.chrreg = saved
    return bytes(px)


def emulated_face(nes: Nes, gid: int) -> bytes:
    ram = nes.ram
    ram[0x00], ram[0xA4], ram[0x7C], ram[0x0A], ram[0x4BC] = gid, 0, 0, Y_ORIGIN, 0
    nes.prgreg[2] = 0x3A  # bank 26 at $C000
    nes.call(0xCE37, x=0)
    oam = [bytes(ram[0x200 + 4 * k:0x204 + 4 * k]) for k in range(FACE_SPRITES)]
    return draw_oam(nes, oam, ram[0xB8], bytes([FACE_PALETTE[0]]) + bytes(nes.pal[17:32]))


def screen_face(nes: Nes) -> bytes:
    """劉備's face on the lord-select status window (OAM entries whose tiles are $80-$BF)."""
    oam = [bytes(nes.oam[k:k + 4]) for k in range(0, 256, 4) if 0x80 <= nes.oam[k + 1] < 0xC0 and nes.oam[k] < 0xEF]
    return draw_oam(nes, oam, nes.line_chr_banks()[200][2], bytes([FACE_PALETTE[0]]) + bytes(nes.pal[17:32]))


def main() -> None:
    ap = argparse.ArgumentParser(description="以模擬器驗證 haou-fc 資料集")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    meta, blobs = load(args.dataset)
    rom = Rom(args.rom)
    errors = []
    if hashlib.sha1(rom.data).hexdigest() != meta["source"]["inputs"][0]["sha1"]:
        errors.append("ROM SHA-1 differs from source.inputs")

    nes = Nes(args.rom)
    nes.run(720)
    for b, w in TO_LORD_STATUS:
        nes.press(b, w)
    if bytes(nes.pal[28:32])[1:] != FACE_PALETTE[1:]:
        errors.append("FACE_PALETTE is not sprite sub-palette 3 of the game")
    chars = {c["id"]: c for c in meta["characters"]}

    def portrait(gid):
        return get_image(meta, blobs, meta["portraits"][chars[gid]["face"]["portrait"]]["img"])

    liu_bei = rom.lord_general(4)
    if portrait(liu_bei) != (FACE_W, FACE_H, screen_face(nes)):
        errors.append("劉備's face on the lord-select screen differs from the dataset")
    print("[screen] 劉備 status window face checked")

    for gid in range(GENERAL_COUNT):
        if portrait(gid) != (FACE_W, FACE_H, emulated_face(nes, gid)):
            errors.append(f"face of general {gid} differs from $CE37")
    print(f"[faces] {GENERAL_COUNT} generals checked against $CE37")

    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        if json.load(f) != checksums(meta, blobs):
            errors.append("checksums.json differs from the reference renderer")
    for e in errors[:20]:
        print("NG", e)
    print("All checks passed!" if not errors else f"{len(errors)} errors")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
