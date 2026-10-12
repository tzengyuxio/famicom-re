#!/usr/bin/env python3
"""Check the decoded maps against the game's own drawing code, run in tools/nes_emu.py.

- Battle maps: for each province the emulator runs the loader $ADCB (bank 7 at $A000, header
  bank 2 $8020, X = province, as $E3EB calls it when a battle starts). It reads the record from
  CHR-ROM through $2007, expands the cells with the metatile table and writes nametable 0 and its
  attribute table. Rows 0-19, the attributes and the cell copy in WRAM $6E1A must equal
  Rom.battle_nametable() / Rom.battle_record().
- Strategy map: the emulator runs the RLE screen loader $AD00 (bank 7 at $A000) for screen 0; both
  nametables (terrain map, road map) must equal Rom.screen(0).

The palettes, CHR banks and a full battle screen (洛陽) were compared with emulator screenshots
while playing (docs/ROM_FORMAT.md).

Usage: .venv/bin/python chuugen/verify_battle_maps.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "tools"))
from nes_emu import Nes
from rom import BATTLE_H, BATTLE_W, DEFAULT_ROM, MAP_SCREEN, PROVINCE_COUNT, Rom


def nametable(nes: Nes, base: int, n: int) -> bytes:
    return bytes(nes.vram_read(base + i) for i in range(n))


def run_battle_loader(nes: Nes, province: int) -> None:
    nes.prgreg[1:] = [0x37, 0x3B]          # as $E3F3-$E3FA
    nes.ram[0x00], nes.ram[0x01] = 0x20, 0x80
    nes.ram[0x08] = 0x20                    # nametable 0
    nes.ram[0x39] = 0
    nes.call(0xADCB, x=province)


def main() -> None:
    ap = argparse.ArgumentParser(description="以模擬器驗證戰場與大地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    nes = Nes(args.rom)
    nes.run(30)
    errors = []

    for i in range(PROVINCE_COUNT):
        run_battle_loader(nes, i)
        nt, attrs = rom.battle_nametable(i)
        if nametable(nes, 0x2000, len(nt)) != nt:
            errors.append(f"battle map {i}: nametable differs")
        if nametable(nes, 0x23C0, 64) != attrs:
            errors.append(f"battle map {i}: attributes differ")
        if bytes(nes.wram[0xE1A:0xE1A + BATTLE_W * BATTLE_H]) != rom.battle_record(i)[1]:
            errors.append(f"battle map {i}: cell copy at $6E1A differs")
    print(f"[battle] {PROVINCE_COUNT} maps checked against $ADCB")

    nes.prgreg[1:] = [0x37, 0x3B]
    nes.ram[0x0A], nes.ram[0x0C] = 2 * MAP_SCREEN, 1   # directory entry, 2 KB
    nes.call(0xAD00)
    if nametable(nes, 0x2000, 0x800) != rom.screen(MAP_SCREEN):
        errors.append("strategy map screen differs from $AD00")
    print("[map] screen 0 (terrain + road nametables) checked against $AD00")

    for e in errors[:20]:
        print("NG", e)
    print("All checks passed!" if not errors else f"{len(errors)} errors")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
