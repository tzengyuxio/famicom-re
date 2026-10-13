#!/usr/bin/env python3
"""Check which face the game draws for a face index, against export_kaodata.py (needs py65).

Boots the ROM in tools/nes_emu.py and replays verify_battle_maps.py's input script
up to 荀彧's advice before the war prompt, where the game copies his name-table
byte 14 (face index + 1) with the bank-copy routine $C248 and then draws his face.
For each tested general that copy is redirected to the general's own byte 14, and

1. the next copy from the ROM tables shows which path the game takes: the portrait
   table (PORTRAIT_PTR_TABLE entry n) or the component table (COMPONENT_TABLE
   record n), which must match face index < MOB_FIRST / >= MOB_FIRST;
2. the 48x48 face the game leaves on the nametable (2-bit colour per pixel) must
   equal export_kaodata.py's render of that general's face.

Usage: .venv/bin/python sangokushi/tools/verify_face_select.py [--rom ROM] [--generals 15,18,...]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import export_kaodata as ex
from nes_emu import Nes
from verify_battle_maps import SCRIPT

COPY = 0xC248          # native: copy $58/$59 bytes from bank $52:$54 to $56
NAME_CPU = 0xA304      # name table as the CPU sees it (bank 14 at $8000)
ADVISOR = 16           # 荀彧, whose face the script reaches
PTR_CPU = ex.PORTRAIT_PTR_TABLE - 0x10 - 6 * 0x4000 + 0x8000     # bank 6
COMP_CPU = ex.COMPONENT_TABLE - 0x10 - 7 * 0x4000 + 0x8000       # bank 7
FACE_TILE = (3, 11)    # top-left tile of the face window
# P64 / P65 boundary, the 16 generals with face index 65-80, and a few others
DEFAULT = [16, 215, 15, 18, 19, 20, 21, 22, 23, 24, 26, 27, 28, 29, 30, 35, 37, 38, 1, 145, 42]


def screen_face(n: Nes) -> bytes:
    base = 0x1000 if n.ctrl & 0x10 else 0
    out = bytearray(48 * 48)
    for y in range(48):
        for x in range(48):
            tx, ty = FACE_TILE[0] + x // 8, FACE_TILE[1] + y // 8
            t = n.vram_read(0x2000 + (n.ctrl & 3) * 0x400 + ty * 32 + tx)
            lo, hi = n.chr[base + t * 16 + y % 8], n.chr[base + t * 16 + y % 8 + 8]
            out[y * 48 + x] = ((lo >> (7 - x % 8)) & 1) | ((hi >> (7 - x % 8)) & 1) << 1
    return bytes(out)


def main() -> None:
    ap = argparse.ArgumentParser(description="以模擬器驗證頭像編號的專屬／組合臉分界")
    ap.add_argument("--rom", default=ex.DEFAULT_ROM)
    ap.add_argument("--generals", default=",".join(map(str, DEFAULT)))
    args = ap.parse_args()
    meta, blobs = ex.build(args.rom)
    chars = {c["id"]: c for c in meta["characters"]}
    names = ex.general_names(ex.read_rom(args.rom))

    nes = Nes(args.rom)
    print("replaying input up to 荀彧's advice ...")
    for button, wait in SCRIPT[:69]:
        if button == "wait":
            nes.run(wait)
        elif button == "A2":
            nes.press("A", wait, hold=2)
        elif button == "HOLD_UP":
            nes.run(120, ["UP"])
            nes.run(wait)
        else:
            nes.press(button, wait)
    start = nes.snapshot()
    last_button, last_wait = SCRIPT[69]

    failed = False
    for gid in map(int, args.generals.split(",")):
        name, _, fi = names[gid]
        nes.restore(start)
        path = []

        def copy(n: Nes, gid: int = gid, path: list = path) -> None:
            r = n.ram
            src = r[0x54] | r[0x55] << 8
            if r[0x52] == 14 and src == NAME_CPU + ADVISOR * 15 + 14:
                s = NAME_CPU + gid * 15 + 14
                r[0x54], r[0x55] = s & 0xFF, s >> 8
                path.append("name")
            elif path == ["name"] and r[0x52] == 6 and PTR_CPU <= src < PTR_CPU + ex.PORTRAIT_COUNT * 4:
                path.append(("portrait", (src - PTR_CPU) // 4))
            elif path == ["name"] and r[0x52] == 7 and COMP_CPU <= src < COMP_CPU + ex.MOB_COUNT * 5:
                path.append(("mob", ex.MOB_FIRST + (src - COMP_CPU) // 5))

        nes.breakpoints = {COPY: copy}
        nes.press(last_button, last_wait)
        nes.breakpoints = {}
        want = ("portrait" if fi < ex.MOB_FIRST else "mob", fi)
        drawn = screen_face(nes)
        same = drawn == ex.compose_display(meta, blobs, chars[gid]["face"])[2]
        good = len(path) == 2 and path[1] == want and same
        print(f"  {gid:3d} {name}: face index {fi:3d} -> game reads "
              f"{path[1] if len(path) == 2 else path}, drawn face {'=' if same else '!='} export -> "
              f"{'OK' if good else 'NG'}")
        failed |= not good
    print("FAIL" if failed else "OK")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
