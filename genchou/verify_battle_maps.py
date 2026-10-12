#!/usr/bin/env python3
"""Check the battle map decoder (rom.Rom.battle_*) against the game's own code (needs py65).

For each of the 47 maps, runs the map loaders of bank 9 in an emulator: $A5A9 + $A62B (tilemap
into the 32x30 screen buffers at WRAM $6000/$63C0, map area at tile (2, 2)), $A412 (terrain
into $7A9E) and $A532 (entry cells into $7A12), and compares with the static decode.

Usage: .venv/bin/python genchou/verify_battle_maps.py [--rom ROM]
"""
import argparse

from rom import BATTLE_COUNT, BATTLE_TILE_H, BATTLE_TILE_W, DEFAULT_ROM, Rom
from tools.pcode_emu import Mem, call_pcode, trace_battle_map


def loaded(prg: bytes, entry: int, n: int, dst: int, size: int) -> bytes:
    mem = Mem(prg)
    call_pcode(mem, entry, {0xA000: 9}, [n])
    page = (mem.regs[0x5113] & 7) * 0x2000 + dst - 0x6000  # these loaders keep the current WRAM page
    return bytes(mem.wram[page:page + size])


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證戰場地圖解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    bad = []
    for n in range(BATTLE_COUNT):
        tiles, exram = trace_battle_map(rom.prg, n)
        bt, be = rom.battle_cells(n)
        ok = all(tiles[(y + 2) * 32 + x + 2] == bt[y * BATTLE_TILE_W + x]
                 and exram[(y + 2) * 32 + x + 2] == be[y * BATTLE_TILE_W + x]
                 for y in range(BATTLE_TILE_H) for x in range(BATTLE_TILE_W))
        ok &= list(loaded(rom.prg, 0xA412, n, 0x7A9E, 140)) == rom.battle_terrain(n)
        entries = [0x30 if e is None else e for e in rom.battle_entries(n)]
        ok &= list(loaded(rom.prg, 0xA532, n, 0x7A12, 140)) == entries
        if not ok:
            bad.append(n)
    print(f"[battle] {BATTLE_COUNT - len(bad)}/{BATTLE_COUNT} maps match (tilemap, ExRAM, terrain, entries)"
          + (f" (NG {bad})" if bad else ""))
    print("ALL OK" if not bad else f"{len(bad)} problem(s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
