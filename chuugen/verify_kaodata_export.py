#!/usr/bin/env python3
"""Check a chuugen-fc kaodata dataset against the game's own code, run in tools/nes_emu.py.

For every general the emulator runs
  - the face routine $F47A (A = general id): it copies the sprite template, picks the CHR bank
    ($F53B, left in $78) and the tile block ($F62C), and writes the 14 sprites to the OAM buffer.
    Those sprites are drawn from CHR with the bank in slot 2 and the sprite palette the game loads
    (bank 2 $8C7E), then compared pixel by pixel with the dataset portrait of that character;
  - the name routine $F1C7 (A = general id): the 8 + 8 byte name buffer ($05DE chars, $05D6 marks
    above them) is read back and must give the dataset name.
Then the dataset checksums are recomputed with the reference renderer.

Usage: .venv/bin/python chuugen/verify_kaodata_export.py --dataset <dir> [--rom ROM]
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
from rom import DEFAULT_ROM, FACE_H, FACE_PALETTE, FACE_W, GENERAL_COUNT, MAP_PALETTE, Rom, char, mark

OAM_START = 0x84   # $3C: first OAM buffer offset used for the face on the status screen
FACE_SPRITES = 14


def load(dataset: str) -> tuple[dict, list[bytes]]:
    with open(os.path.join(dataset, "dataset.json"), encoding="utf-8") as f:
        meta = json.load(f)
    blobs = []
    for name in meta.get("blobs", ["pixels.bin"]):
        with open(os.path.join(dataset, name), "rb") as f:
            blobs.append(zlib.decompress(f.read(), -15))
    return meta, blobs


def emulated_face(nes: Nes, rom: Rom, gid: int) -> bytes:
    ram = nes.ram
    ram[0x3C], ram[0x6A4], ram[0x604] = OAM_START, 0, 0   # OAM slot, expression 0, mouth closed
    ram[0x54:0x58] = bytes(4)                               # no scroll offset
    ram[0x06], ram[0x07] = 0x40, 0x80                       # screen position
    nes.call(0xF47A, a=gid)
    bank = ram[0x78]
    oam = [ram[0x200 + OAM_START + 4 * k:0x200 + OAM_START + 4 * k + 4] for k in range(FACE_SPRITES)]
    x0, y0 = min(s[3] for s in oam), min(s[0] for s in oam)
    nes.chrreg = [0, 0, bank, 0, 0, 0, 0, 0]
    pal = rom.prg[MAP_PALETTE + 16:MAP_PALETTE + 32]
    px, done = bytearray([pal[0]]) * (FACE_W * FACE_H), [False] * (FACE_W * FACE_H)
    for y, tile, attr, x in oam:                            # lower OAM index wins (NES priority)
        for dy in range(8):
            lo, hi = nes.vram_read(tile * 16 + dy), nes.vram_read(tile * 16 + dy + 8)
            for dx in range(8):
                b = dx if attr & 0x40 else 7 - dx
                c = ((lo >> b) & 1) | (((hi >> b) & 1) << 1)
                i = (y - y0 + dy) * FACE_W + x - x0 + dx
                if c and not done[i]:
                    px[i], done[i] = pal[(attr & 3) * 4 + c], True
    return bytes(px)


def emulated_name(nes: Nes, gid: int) -> str:
    nes.call(0xF1C7, a=gid)
    low, high = nes.ram[0x5DE:0x5E6], nes.ram[0x5D6:0x5DE]
    s = ""
    for col in range(8):
        if high[col] in (0xFE, 0xFF):  # the mark sits right after (above-right of) its character
            s = mark(s, high[col])
        if low[col] not in (0x00, 0x01, 0xFF):  # blank / buffer filler
            s += char(low[col])
    return s


def main() -> None:
    ap = argparse.ArgumentParser(description="以模擬器驗證 chuugen-fc 資料集")
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    meta, blobs = load(args.dataset)
    rom = Rom(args.rom)
    errors = []
    if hashlib.sha1(rom.data).hexdigest() != meta["source"]["inputs"][0]["sha1"]:
        errors.append("ROM SHA-1 differs from source.inputs")
    if bytes(rom.prg[MAP_PALETTE + 24:MAP_PALETTE + 28]) != FACE_PALETTE:
        errors.append("FACE_PALETTE is not sprite sub-palette 2 of the game")

    nes = Nes(args.rom)
    nes.run(30)  # RESET code done
    chars = {c["id"]: c for c in meta["characters"]}
    for gid in range(GENERAL_COUNT):
        c = chars[gid]
        w, h, px = get_image(meta, blobs, meta["portraits"][c["face"]["portrait"]]["img"])
        if (w, h, px) != (FACE_W, FACE_H, emulated_face(nes, rom, gid)):
            errors.append(f"face of general {gid} differs from $F47A")
        name = emulated_name(nes, gid)
        if name != c["name"]:
            errors.append(f"name of general {gid}: game {name} / dataset {c['name']}")
    print(f"[faces/names] {GENERAL_COUNT} generals checked against $F47A / $F1C7")

    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        if json.load(f) != checksums(meta, blobs):
            errors.append("checksums.json differs from the reference renderer")
    for e in errors[:20]:
        print("NG", e)
    print("All checks passed!" if not errors else f"{len(errors)} errors")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
