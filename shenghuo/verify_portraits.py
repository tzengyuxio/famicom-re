#!/usr/bin/env python3
"""Check the portrait decoder (rom.portrait) against the screens the game's own code draws.

Boots the game in the py65 harness (tools/nes_emu.py), starts a new game, then:

1. status: open SELECT -> 人物 -> 個人資料 -> 資料 for the player, then for each party member 0-12
   redraw the portrait with the screen's own call (bank 0 $B9E1: $64/$65 = $18, $67 = $3C,
   $66 = id + $5B, JSR $E817 builds the sprites) and compare the 32x40 portrait on the screen with
   rom.portrait(id, "status").
2. dialog: walk into the first town (its entry dialogue shows a portrait), then for every speaker
   0-36 set $E3 = id, run the game's portrait routine (bank 0 $C4CE: tiles, CHR bank $8C, attribute)
   and compare the screen with rom.portrait(id, "dialog").

The status portrait is a group of sprites (OAM), the dialogue portrait background tiles. The
portrait is searched for at every pixel position of the rendered screen; a check passes when some
position matches all 1280 pixels.

Usage: .venv/bin/python shenghuo/verify_portraits.py [--rom ROM]
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "tools"))
from nes_emu import Nes
from rom import CHAR_COUNT, DEFAULT_ROM, PORTRAIT_BASE, PORTRAIT_COUNT, TOWN_SCREENS, Rom
from verify_maps import call, new_game


def find(n: Nes, want: list[int]) -> tuple[int, int] | None:
    w, h, px = n.screen()
    for oy in range(h - 40 + 1):
        for ox in range(w - 32 + 1):
            if all(px[(oy + y) * w + ox + x] == want[y * 32 + x] for y in range(40) for x in range(32)):
                return ox, oy
    return None


def open_status(n: Nes) -> None:
    """World map -> SELECT -> 人物 -> 個人資料 -> 資料 (first party member).

    In the harness the first A after DOWN opens 隊伍總表 and the next one returns with the cursor
    on 個人資料, hence the extra A."""
    for button, wait, hold in (("SELECT", 60, 3), ("A", 60, 3), ("DOWN", 40, 8), ("A", 60, 3), ("A", 150, 3),
                               ("A", 150, 3)):
        n.press(button, wait, hold)


def enter_town(rom: Rom, n: Nes) -> None:
    """Run the class-4 (town) cell handler (bank 0 $88ED) as if standing on town 1's world screen ($A2)."""
    n[0xA2] = rom.byte(0, TOWN_SCREENS + 1)
    call(n, 0x88ED, 0)
    n.run(300)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    base = new_game(args.rom)
    start = base.snapshot()
    bad = 0

    open_status(base)
    status = base.snapshot()
    for cid in range(CHAR_COUNT):
        base.restore(status)
        base[0x64], base[0x65], base[0x67], base[0x66] = 0x18, 0x18, 0x3C, PORTRAIT_BASE + cid
        call(base, 0xE817, 0)
        base.run(2)
        pos = find(base, rom.portrait(cid, "status")[2])
        bad += pos is None
        print(f"[status] {cid:2d} {'OK at ' + str(pos) if pos else 'MISMATCH'}")

    base.restore(start)
    enter_town(rom, base)
    town = base.snapshot()
    for pid in range(PORTRAIT_COUNT):
        base.restore(town)
        base[0xE3] = pid
        call(base, 0xC4CE, 0)
        base.run(10)
        pos = find(base, rom.portrait(pid, "dialog")[2])
        bad += pos is None
        print(f"[dialog] {pid:2d} chr {rom.portrait_chr(pid)} {'OK at ' + str(pos) if pos else 'MISMATCH'}")
    print("ALL OK" if not bad else f"{bad} MISMATCHES")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
