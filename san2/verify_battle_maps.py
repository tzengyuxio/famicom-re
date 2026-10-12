#!/usr/bin/env python3
"""Check the battle map decoder (rom.Rom.battle_screen) against the game itself (needs py65).

tools/play.py plays scenario 1 in tools/nes_emu.py up to 袁術's attack on 董卓's province 10 and
stops just before the last key press. For each of the 41 maps the 78 bytes of map 10 are replaced
by that map in the emulated ROM, the battle starts, and the 26 x 25 field of the name table
(tile ids and ExRAM bytes, before any unit is drawn) is compared with the static decode.

Usage: .venv/bin/python san2/verify_battle_maps.py [--rom ROM]
"""
import argparse

from rom import BATTLE, DEFAULT_ROM, PROVINCE_COUNT, Rom
from tools.play import TO_BATTLE, TO_COMMAND, boot, play

FIELD_X, FIELD_Y, FIELD_W, FIELD_H = 3, 3, 26, 25  # name table cells of the battle field
TARGET = 9                                         # 0-based province of the scripted battle


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證戰場地圖解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    nes = boot(args.rom, TO_COMMAND, TO_BATTLE[:-1])
    start = nes.snapshot()
    bad = []
    for i in range(PROVINCE_COUNT):
        nes.restore(start)
        prg = bytearray(rom.prg)
        prg[BATTLE + 78 * TARGET:BATTLE + 78 * TARGET + 78] = rom.prg[BATTLE + 78 * i:BATTLE + 78 * i + 78]
        nes.prg = bytes(prg)
        play(nes, TO_BATTLE[-1:])
        tiles, ex = rom.battle_screen(i)
        got = [(nes.nt_read(0x2000 + (FIELD_Y + k // FIELD_W) * 32 + FIELD_X + k % FIELD_W),
                nes.exram[(FIELD_Y + k // FIELD_W) * 32 + FIELD_X + k % FIELD_W]) for k in range(FIELD_W * FIELD_H)]
        if got != list(zip(tiles, ex)):
            bad.append(i + 1)
    print(f"[battle] {PROVINCE_COUNT - len(bad)}/{PROVINCE_COUNT} maps match (tiles, ExRAM)"
          + (f" (NG {bad})" if bad else ""))
    print("ALL OK" if not bad else f"{len(bad)} problem(s)")
    raise SystemExit(1 if bad else 0)


if __name__ == "__main__":
    main()
