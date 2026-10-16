"""Check the decoded data against the game itself, run in the emulator (needs py65; takes a few minutes).

Plays a 1-player new game from power-on (company エヌイージー), then compares:
  * the WRAM company/staff/department records with the new-game image decoded by rom.py
  * the demand / ad cost curves in WRAM with their pools
  * the 年初 meeting picture, the monthly season picture and every department staff picture with the screen
    (pixel for pixel, NES colour numbers, palette taken from the ROM, not from the emulator)
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rom import (
    AD_CURVES,
    AD_MONTHS,
    AD_POOL,
    AD_WRAM,
    COMPANIES,
    COMPANY_COUNT,
    COMPANY_SIZE,
    DEFAULT_ROM,
    DEMAND_CURVES,
    DEMAND_POOL,
    DEMAND_WRAM,
    DEMAND_YEARS,
    PICTURE_PALETTES,
    Rom,
    u16,
)
from tools.emu import Nes


def press(button: str, hold: int = 10):
    return [("HOLD_" + button, hold)]


NEW_GAME = (
    [("wait", 1200)] + press("START") + [("wait", 300)] + press("A") + [("wait", 900)] + press("A")
    + [("wait", 1400)]                                      # title, disclaimer
    + press("A") + [("wait", 120)]                          # ニューゲーム
    + press("UP", 3) + [("wait", 30)] + press("A") + [("wait", 120)]   # 1 player
    + press("A") + [("wait", 120)] + press("A") + [("wait", 120)]      # company エヌイージー
    + press("LEFT") + [("wait", 120)] + press("A") + [("wait", 120)]   # Y, name prompt
    + (press("A") + [("wait", 30)]) * 3                     # name あああ
    + (press("DOWN", 6) + [("wait", 10)]) * 9 + (press("RIGHT", 6) + [("wait", 10)]) * 5
    + press("A") + [("wait", 120)]                          # おわり
    + press("UP", 3) + [("wait", 30)] + press("A") + [("wait", 120)]   # computer strength 1
    + (press("A") + [("wait", 120)]) * 3                    # message, しょうせん, wait time
    + press("LEFT") + [("wait", 600)] + press("A") + [("wait", 300)]   # すべてよろしいですか Y, meeting
)
END_NENSHO = (press("DOWN", 3) + [("wait", 20)]) * 6 + press("A") + [("wait", 120)] + press("LEFT") + [("wait", 600)]


def bg_match(nes: Nes, rom: Rom, p: dict, width: int, x0: int, rows: int) -> float:
    pal = rom.prg[PICTURE_PALETTES[(p["tag"], p["index"])]:][:16]
    w, h, px = rom.picture_pixels(p, width, pal)
    rows = min(rows, h // 8)
    bg = nes.bg_pixels(x0, 0, width, rows)
    n = rows * 8 * w
    return sum(a == b for a, b in zip(px[:n], bg)) / n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    pics = {(p["tag"], p["index"]): p for p in rom.pictures()}
    ok = True

    def check(name: str, good: bool, detail: str = "") -> None:
        nonlocal ok
        ok &= good
        print(f"{'OK  ' if good else 'FAIL'} {name} {detail}")

    nes = Nes(args.rom)
    nes.play(NEW_GAME)
    check("年初 meeting picture", bg_match(nes, rom, pics[("meeting", 0)], 32, 0, 14) == 1.0)

    # records: everything but the player-entered company 0 name/president fields equals the image
    wram = lambda a, n: bytes(nes.wram[a - 0x6000:a - 0x6000 + n])
    for k in range(COMPANY_COUNT):
        base = COMPANIES + k * COMPANY_SIZE
        live, img = bytearray(wram(base, COMPANY_SIZE)), bytearray(rom.image(base, COMPANY_SIZE))
        live[0x40:0x48] = img[0x40:0x48] = bytes(8)
        ptrs = [u16(img, 0x4A + 2 * i) for i in range(4)] + [u16(img, 0x5E)]
        sizes = [34, 24, 40, 32, 0x6E]
        same = [wram(a, s) == rom.image(a, s) for a, s in zip(ptrs, sizes)]
        # byte 0x61 of company 4 is the first byte of the global block; extra block byte 0 is set at start
        diff = [hex(i) for i in range(0x60) if live[i] != img[i]]
        extra = wram(ptrs[4] + 1, 0x6D) == rom.image(ptrs[4] + 1, 0x6D)
        check(f"company {k} records", live[0x16:0x60] == img[0x16:0x60] and all(same[:4]) and extra,
              f"differing record bytes {diff}")
    for p in range(3):
        live = [u16(wram(DEMAND_WRAM + p * 70, 70), 2 * i) for i in range(DEMAND_YEARS)]
        pool = [[u16(rom.prg, DEMAND_POOL + ((p * DEMAND_CURVES + c) * DEMAND_YEARS + i) * 2) for i in range(DEMAND_YEARS)]
                for c in range(DEMAND_CURVES)]
        check(f"demand curve {p} in pool", live in pool, f"curve {pool.index(live) if live in pool else '-'}")
    for m in range(3):
        live = [u16(wram(AD_WRAM + m * 24, 24), 2 * i) for i in range(AD_MONTHS)]
        pool = [[u16(rom.prg, AD_POOL + ((m * AD_CURVES + c) * AD_MONTHS + i) * 2) for i in range(AD_MONTHS)]
                for c in range(AD_CURVES)]
        check(f"ad cost curve {m} in pool", live in pool, f"curve {pool.index(live) if live in pool else '-'}")

    # monthly screen: skip the 年初 phase and the rival messages until the season picture is up
    nes.play(END_NENSHO)
    for _ in range(40):
        if bg_match(nes, rom, pics[("season", 0)], 16, 16, 18) == 1.0:
            break
        nes.play(press("A") + [("wait", 120)])
    check("monthly season picture (spring)", bg_match(nes, rom, pics[("season", 0)], 16, 16, 18) == 1.0)

    # department screens: which of the 8 staff pictures is drawn is not fixed (it differs between games),
    # so look for the one that matches pixel for pixel with its PICTURE_PALETTES palette
    month = nes.snapshot()
    for d, dept in enumerate(["そうむ", "かいはつ", "せいぞう", "えいぎょう", "じょうほう", "そのた"]):
        nes.restore(month)
        nes.play(press("A", 3) + [("wait", 60)] + (press("DOWN", 3) + [("wait", 20)]) * (d + 1)
                 + press("A", 3) + [("wait", 180)])
        hits = [i for i in range(8) if bg_match(nes, rom, pics[("staff", i)], 16, 16, 18) == 1.0]
        check(f"department {dept} staff picture", len(hits) == 1, f"staff {hits}")
    print("all OK" if ok else "FAILED")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
