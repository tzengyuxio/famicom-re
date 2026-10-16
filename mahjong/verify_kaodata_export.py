#!/usr/bin/env python3
"""Independent checks for the mahjong-fc kaodata dataset.

1. Every character face, expression and portrait drawn by the spec renderer from the dataset
   equals the face composed directly from ROM tiles (rom.Rom.face_pixels), pixel by pixel.
2. checksums.json matches a recomputation.
3. (needs py65) The game itself, run in tools/emu.py: the 雀荘 screen draws one card per player
   with the game's own face routine ($EBEC). Each (player, expression) is swapped into a card's
   slot (tile-pool pointer, palette flag and expression-0 layout, PRG copy only) and the card's
   4x4-tile face on screen must equal rom.py's face. Cards the game draws with sprites are skipped
   and covered by the other passes; the human's card is checked on the unpatched screen.

Usage: .venv/bin/python mahjong/verify_kaodata_export.py --dataset <dir> [--rom ROM] [--no-emu]
"""
import argparse
import json
import os

from export_kaodata import HUMAN_PORTRAIT, checksums, compose_display, san1
from rom import (
    CPU_PLAYERS,
    DEFAULT_ROM,
    EXPRESSIONS,
    FACE_LAYOUTS,
    FACE_PALETTE_FLAG,
    FACE_TILE_BASE,
    HUMAN,
    Rom,
)


def portrait_of(n: int) -> tuple[int, int]:
    return (HUMAN, 0) if n == HUMAN_PORTRAIT else divmod(n, EXPRESSIONS)


def check_pixels(rom: Rom, meta: dict, blobs: list[bytes]) -> int:
    errors = 0
    faces = [(f"ch:{c['id']}", c["face"]) for c in meta["characters"]]
    faces += [(f"ch:{c['id']}/{k}", e) for c in meta["characters"] for k, e in enumerate(c["expressions"], 1)]
    faces += [(f"pt:{n}", {"portrait": n}) for n in range(len(meta["portraits"]))]
    for label, face in faces:
        w, h, px = compose_display(meta, blobs, face)
        if (w, h) != (32, 32) or px != rom.face_pixels(*portrait_of(face["portrait"])):
            print(f"  NG {label}")
            errors += 1
    print(f"[pixels] {len(faces) - errors}/{len(faces)} faces match the ROM tile composition")
    return errors


def check_checksums(meta: dict, blobs: list[bytes], path: str) -> int:
    with open(path, encoding="utf-8") as f:
        stored = json.load(f)
    ok = stored == checksums(meta, blobs)
    print(f"[checksums] {'OK' if ok else 'MISMATCH'} ({len(stored['entries'])} entries)")
    return 0 if ok else 1


def check_emulated(rom: Rom, rom_path: str) -> int:
    try:
        from tools.emu import TO_CARDS, TO_MENU, Nes, card_face_xy
    except ImportError:
        print("[emulator] skipped (py65 not installed: uv pip install py65)")
        return 0
    nes = Nes(rom_path)
    nes.play(TO_MENU)
    menu = nes.snapshot()
    todo = [(p, e) for p in range(CPU_PLAYERS) for e in range(EXPRESSIONS)]
    nes.play(TO_CARDS)
    x, y = card_face_xy(HUMAN)
    human_ok = nes.bg_pixels(x, y, 4, 4) == rom.face_pixels(HUMAN)
    done, bad, passes = set(), [], 0
    while todo and passes < 20:
        passes += 1
        prg = bytearray(rom.prg)
        slots = {}
        for q, (p, e) in zip(range(CPU_PLAYERS), todo):
            prg[FACE_TILE_BASE + 2 * q:FACE_TILE_BASE + 2 * q + 2] = rom.prg[FACE_TILE_BASE + 2 * p:FACE_TILE_BASE + 2 * p + 2]
            prg[FACE_PALETTE_FLAG + q] = rom.prg[FACE_PALETTE_FLAG + p]
            o = FACE_LAYOUTS + 16 * q * EXPRESSIONS
            prg[o:o + 16] = bytes(rom.face_layout(p, e))
            slots[q] = (p, e)
        nes.restore(menu)
        nes.prg = bytes(prg)
        nes.play(TO_CARDS)
        for q in range(CPU_PLAYERS):
            x, y = card_face_xy(q)
            if q not in slots or nes.nt_tile(x, y) == 0x01:  # unused slot, or a card drawn with sprites
                continue
            p, e = slots[q]
            if nes.bg_pixels(x, y, 4, 4) != rom.face_pixels(p, e):
                bad.append((p, e))
            done.add((p, e))
        todo = [t for t in todo if t not in done]
    n = CPU_PLAYERS * EXPRESSIONS
    print(f"[emulator] 雀荘 cards: {len(done) - len(bad)}/{n} faces match in {passes} passes"
          + (f" (NG {bad})" if bad else "") + (f" (not shown {todo})" if todo else ""))
    print(f"[emulator] the human's card: {'OK' if human_ok else 'NG'}")
    return len(bad) + len(todo) + (0 if human_ok else 1)


def main() -> None:
    ap = argparse.ArgumentParser(description="驗證 mahjong-fc kaodata 資料集")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--no-emu", action="store_true", help="略過模擬器檢查")
    args = ap.parse_args()
    rom = Rom(args.rom)
    meta, blobs = san1.load_dataset(args.dataset)
    errors = check_pixels(rom, meta, blobs)
    errors += check_checksums(meta, blobs, os.path.join(args.dataset, "checksums.json"))
    if not args.no_emu:
        errors += check_emulated(rom, args.rom)
    print("ALL OK" if not errors else f"{errors} problem(s)")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
