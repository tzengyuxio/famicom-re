#!/usr/bin/env python3
"""Check the scenario decode (rom.Rom.placement / province) against the game's own set-up (needs py65).

For each of the 6 scenarios tools/nes_emu.py starts the game and the WRAM the scenario loader
builds is compared with the static decode: the 41 province records ($73F5 + 25 i, bytes 8-24) and
every general's 21-byte record (知武魅, faction, loyalty, id). Initial soldiers follow the
flags (ruler 100, flag 0x10 50, others 10) except for a few strong generals the loader raises;
those are listed, not counted as errors.

Usage: .venv/bin/python san2/verify_scenarios.py [--rom ROM]
"""
import argparse

from rom import DEFAULT_ROM, GENERAL_COUNT, PROVINCE_COUNT, PROVINCE_SIZE, PROVINCES, SCENARIO_COUNT, STATS, Rom
from tools.play import TO_COMMAND, boot, play

WRAM_PROVINCES, WRAM_GENERALS, GENERAL_SIZE, SLOTS = 0x13F5, 0x1D, 21, 216


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證劇本武將與州資料")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    nes = boot(args.rom, TO_COMMAND[:3])  # scenario list
    start, errors = nes.snapshot(), 0
    for sc in range(SCENARIO_COUNT):
        nes.restore(start)
        play(nes, [("DOWN", 3, 10)] * sc + [("A", 3, 400)])
        w = nes.wram[0x2000:0x4000]
        prov_ok = sum(w[WRAM_PROVINCES + PROVINCE_SIZE * i + 8:WRAM_PROVINCES + PROVINCE_SIZE * (i + 1)]
                      == rom.prg[PROVINCES + PROVINCE_SIZE * (PROVINCE_COUNT * sc + i) + 8:
                                 PROVINCES + PROVINCE_SIZE * (PROVINCE_COUNT * sc + i + 1)]
                      for i in range(PROVINCE_COUNT))
        found = {}
        for j in range(SLOTS):
            r = w[WRAM_GENERALS + GENERAL_SIZE * j:WRAM_GENERALS + GENERAL_SIZE * (j + 1)]
            n = r[19] | r[20] << 8
            if n < GENERAL_COUNT and r[4:7] == rom.prg[STATS + 3 * n:STATS + 3 * n + 3]:
                found[n] = r
        bad, raised = [], []
        for n in range(GENERAL_COUNT):
            p = rom.placement(n, sc)
            if not p or p["status"] == "未登場":
                if n in found:
                    bad.append(n)
                continue
            r = found.get(n)
            faction = rom.province(sc, p["province"] - 1)["faction"]
            want = (0xFF, 0xFF) if p["status"] == "在野" else (faction, p["loyalty"] if p["loyalty"] is not None else 0xFF)
            if r is None or (r[7], r[8]) != want:
                bad.append(n)
            elif r[12] | r[13] << 8 != p["soldiers"]:
                raised.append(f"{rom.general(n)['name']} {r[12] | r[13] << 8}")
        print(f"[scenario {sc + 1}] provinces {prov_ok}/{PROVINCE_COUNT}, generals {len(found) - len(bad)}"
              f"/{len(found)} match" + (f" (NG {bad[:10]})" if bad else "")
              + (f"; soldiers raised by the loader: {', '.join(raised)}" if raised else ""))
        errors += PROVINCE_COUNT - prov_ok + len(bad)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
