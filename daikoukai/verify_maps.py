#!/usr/bin/env python3
"""Check the world map and port town decoders against the game (needs py65).

1. Port towns: for all 70 ports, runs the town type function bank 18 $8032 and the town screen
   setup bank 18 $80CB (with the new-game building flags at $6F76 + port) in the p-code emulator
   and compares the type and the BG draw calls (svc 9: x, y, w, h, tiles, ExRAM) with
   rom.Rom.town_type / town_draws.
2. World map: plays a new game from power-on with a fixed input script (tools/nes_emu.py):
   name entry, Lisbon, leave port, set a course to the south-west and sail. Every full redraw of
   the sea view (svc 9, 30 x 28 tiles from the WRAM buffer) is compared with the static chunk at
   the fleet position ($6662 / $6663). The Lisbon town screen on the way is compared too.

Usage: .venv/bin/python daikoukai/verify_maps.py [--rom ROM]
"""
import argparse

from rom import CHUNK_TILES, DEFAULT_ROM, PORT_COUNT, TOWN_FLAGS, TOWN_H, TOWN_W, TOWN_X, TOWN_Y, Rom
from tools.pcode_emu import SYSCALL, Mem, _skip_service, call_pcode, stack_args

# new game -> Lisbon -> sea -> sailing south-west. "B:n" press B and wait n frames, "B*k:n" k times,
# "w:n" wait, "H:Bn" hold B for n frames, "town" check the town screen, "sail:n" run n frames
SCRIPT = """
w:1440 S:60 S:60 A:60 w:120
A:20 D*6:10 R*9:10 w:10 R*3:25 w:10 R*3:20 A:60 w:30
A:90 A:90 A:90 w:60 B:60 A:90 A:120 S:60 E:60 A*49:8 w:60 A:90 A:90 D:15 A*12:8 w:60 A:120 A:120
U:20 L:20 A:60 A:120 A:120 A:120
A*6:90 A*6:90 A*6:90 town
A:60 B:40 D:30 R:30 w:120 A:90 A:180 w:120 w:240
A:40 A:40 H:L120 w:30 H:U200 w:30 D:30 A:90 H:L60 w:60 L:30 A:60 w:120 H:L90 A:60 L:30 A:60 w:300
sail:3000
"""
KEYS = {"A": "A", "B": "B", "S": "START", "E": "SELECT", "U": "UP", "D": "DOWN", "L": "LEFT", "R": "RIGHT"}
WRAM5 = 5 * 0x2000


def check_towns(rom: Rom) -> int:
    bad = []
    for p in range(PORT_COUNT):
        mem = Mem(rom.prg)
        call_pcode(mem, 0x8032, {0x8000: 18, 0xA000: 58}, [p])
        draws = []

        def on_step(cpu, draws=draws):
            if cpu.pc == SYSCALL:
                a = stack_args(cpu.memory, 8)
                if a[0] == 9 and a[5]:          # a[5] = 0: drawn from RAM, not in the static picture
                    draws.append(tuple(a[1:7]))
                _skip_service(cpu)

        t = mem[8]
        mem = Mem(rom.prg)
        mem[0x6000 + TOWN_FLAGS + p] = rom.town_flags(p)
        call_pcode(mem, 0x80CB, {0x8000: 18, 0xA000: 58}, [p], on_step, max_steps=200000)
        if t != rom.town_type(p) or draws != rom.town_draws(p):
            bad.append(p)
    print(f"[town] {PORT_COUNT - len(bad)}/{PORT_COUNT} ports: town type and draw calls match"
          + (f" (NG {bad})" if bad else ""))
    return len(bad)


def check_sailing(rom: Rom, path: str) -> int:
    from tools.nes_emu import Nes
    nes = Nes(path)
    caps = []

    def bp(n):
        sp = n[2] | n[3] << 8
        a = [n[sp + 2 + 2 * i] | n[sp + 3 + 2 * i] << 8 for i in range(8)]
        if a[0] == 9 and a[3] == 0x1E and a[4] == 0x1C:
            o = (n.regs[0x5113] & 7) * 0x2000 - 0x6000
            caps.append((n.wram[WRAM5 + 0x662], n.wram[WRAM5 + 0x663],
                         bytes(n.wram[o + a[5]:][:30 * 28]), bytes(n.wram[o + a[6]:][:30 * 28])))

    errors = 0
    for cmd in SCRIPT.split():
        k, _, v = cmd.partition(":")
        if k == "w":
            nes.run(int(v))
        elif k == "H":
            nes.run(int(v[1:]), [KEYS[v[0]]])
        elif k == "sail":
            nes.breakpoints[SYSCALL] = bp
            nes.run(int(v))
        elif k == "town":
            want = list(zip(*rom.town_tiles(0)))
            got = [(nes.nt_read(0x2000 + (TOWN_Y + i // TOWN_W) * 32 + TOWN_X + i % TOWN_W),
                    nes.exram[(TOWN_Y + i // TOWN_W) * 32 + TOWN_X + i % TOWN_W]) for i in range(TOWN_W * TOWN_H)]
            n = sum(g == w for g, w in zip(got, want))
            print(f"[town] Lisbon screen: {n}/{TOWN_W * TOWN_H} tiles match")
            errors += n != TOWN_W * TOWN_H
        else:
            k, _, times = k.partition("*")
            for _ in range(int(times or 1)):
                nes.press(KEYS[k], int(v))
    for x, y, buf, ex in caps:
        tiles, exs = rom.chunk_tiles(x, y)
        n = sum(buf[r * 30 + c + 1] == tiles[r * CHUNK_TILES + c] and ex[r * 30 + c + 1] == exs[r * CHUNK_TILES + c]
                for r in range(CHUNK_TILES) for c in range(CHUNK_TILES))
        print(f"[map] chunk ({x}, {y}): {n}/{CHUNK_TILES ** 2} tiles match")
        errors += n != CHUNK_TILES ** 2
    if not caps:
        print("[map] no sea redraw captured (input script did not reach the sea)")
        errors += 1
    return errors


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證世界地圖與港町圖解碼")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    args = ap.parse_args()
    rom = Rom(args.rom)
    errors = check_towns(rom) + check_sailing(rom, args.rom)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
