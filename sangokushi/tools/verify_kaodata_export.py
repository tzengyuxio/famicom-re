#!/usr/bin/env python3
"""Check an exported san1-fc dataset against independent renders.

1. All 190 mob component records rendered the "old way" (port of
   mob_portrait/variant_explorer/mob-kao-explorer.html: its embedded tile hex + TEMPLATES + mouth layout,
   not the ROM decode in export_kaodata.py) vs the dataset render (spec §6).
2. Every ch:<id> in checksums.json vs the sha256 of the old-way render.
3. Mesen-verified component records (P081 周泰, P085 曹豹, P157 陳登).
4. Ground truth images: mob_portrait/generated/*.png (8x) and
   mob_portrait/screenshot/*.png (game screenshots, ~4x).
5. Dedicated portraits P00-P80 vs portrait_export.py (its own tile decode, hardcoded
   standard layout and PIL drawing), plus their pt:/ch: checksums. No game
   screenshot of a dedicated portrait exists yet.

Usage: .venv/bin/python sangokushi/tools/verify_kaodata_export.py --dataset <dir> [--rom ROM]
"""
import argparse
import hashlib
import json
import os
import re
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import export_kaodata as ex
import portrait_export as pe  # sangokushi/, on sys.path via export_kaodata
from romfile import DEFAULT_ROM, read_rom

REPO = ex.REPO
MESEN = {81: ("周泰", (3, 0, 2, 3, 1)), 85: ("曹豹", (2, 0, 1, 3, 1)), 157: ("陳登", (2, 2, 4, 2, 4))}


def explorer_data() -> dict:
    with open(os.path.join(REPO, "mob_portrait", "variant_explorer", "mob-kao-explorer.html"), encoding="utf-8") as f:
        html = f.read()
    out = {}
    for name in ["PALETTE", "HEAD_TILES", "TEMPLATES", "EYE_TILES", "NOSE_TILES", "MOUTH_TILES"]:
        m = re.search(rf"const {name} = (\[.*?\n\s*\]);", html, re.DOTALL)
        src = re.sub(r"//[^\n]*", "", m.group(1))
        out[name] = json.loads(re.sub(r",(\s*\])", r"\1", src))
    return out


def old_way_rgba(d: dict, rec) -> bytes:
    """Port of updatePreview() in the explorer: frame via template, then eyes/nose/mouth."""
    cat, h, e, n, m = rec
    px = [[None] * 48 for _ in range(48)]

    def draw(hexstr, x0, y0):
        b = bytes.fromhex(hexstr)
        for y in range(8):
            for x in range(8):
                px[y0 + y][x0 + x] = ((b[y] >> (7 - x)) & 1) + (((b[y + 8] >> (7 - x)) & 1) << 1)

    g = cat * 5 + h
    for row in range(6):
        for col in range(6):
            t = d["TEMPLATES"][g][row][col]
            if t is not None:
                draw(d["HEAD_TILES"][g][t], col * 8, row * 8)
    for i, tile in enumerate(d["EYE_TILES"][cat * 5 + e]):
        draw(tile, 8 + i * 8, 16)
    for i, tile in enumerate(d["NOSE_TILES"][cat * 5 + n]):
        draw(tile, 8 + i * 8, 24)
    for row, idxs in enumerate([[0, 1, 4], [2, 3, 5]]):
        for col, t in enumerate(idxs):
            draw(d["MOUTH_TILES"][cat * 5 + m][t], 8 + col * 8, 32 + row * 8)
    return b"".join(bytes(d["PALETTE"][c]) + b"\xff" for row in px for c in row)


def sample(path: str, scale: int, ox: int, oy: int):
    img = Image.open(path).convert("RGB")
    w, h = img.size
    return [img.getpixel((x * scale + ox, y * scale + oy))
            if 0 <= x * scale + ox < w and 0 <= y * scale + oy < h else None
            for y in range(48) for x in range(48)]


def compare_png(path: str, rgba: bytes, scale: int, search: int):
    """Best (matching, compared) over sampling offsets; colours compared with 2-level tolerance."""
    ref = [tuple(rgba[i * 4:i * 4 + 3]) for i in range(48 * 48)]
    best = (0, 0)
    for oy in range(scale // 2 - search, scale // 2 + search + 1):
        for ox in range(scale // 2 - search, scale // 2 + search + 1):
            got = sample(path, scale, ox, oy)
            pairs = [(a, b) for a, b in zip(got, ref) if a is not None]
            ok = sum(max(abs(p - q) for p, q in zip(a, b)) <= 2 for a, b in pairs)
            best = max(best, (ok, len(pairs)))
    return best


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--dataset", required=True)
    args = ap.parse_args()
    rom = read_rom(args.rom)
    meta, blobs = ex.load_dataset(args.dataset)
    with open(os.path.join(args.dataset, "checksums.json"), encoding="utf-8") as f:
        sums = json.load(f)["entries"]
    colors = meta["palettes"][0]["colors"]
    d = explorer_data()
    records = ex.component_records(rom)
    failed = False

    # 1. all 190 records
    same = 0
    renders = {}
    for i, rec in enumerate(records):
        old = old_way_rgba(d, rec)
        new = ex.to_rgba(ex.compose_display(meta, blobs, {"variant": rec[0], "parts": list(rec[1:])}), colors)
        renders[ex.MOB_FIRST + i] = new
        same += old == new
    print(f"[1] old-way vs dataset render: {same}/{len(records)} records pixel-identical")
    failed |= same != len(records)

    # 2. characters: face tuple + checksum vs old-way render of the general's own record
    names = ex.general_names(rom)
    chars = {c["id"]: c for c in meta["characters"]}
    ok = n = 0
    for gid, (_, _, fi) in names.items():
        if fi < ex.MOB_FIRST:
            failed |= chars[gid].get("face") != {"portrait": fi}
            continue
        n += 1
        rec = records[fi - ex.MOB_FIRST]
        face = chars[gid]["face"]
        ok += ((face["variant"], *face["parts"]) == rec
               and sums[f"ch:{gid}"] == hashlib.sha256(old_way_rgba(d, rec)).hexdigest())
    n_pt = sum(fi < ex.MOB_FIRST for _, _, fi in names.values())
    print(f"[2] characters with mob face: {ok}/{n} match record + checksum; checksums.json has {len(sums)} entries")
    failed |= ok != n or len(sums) != n + n_pt + len(meta["portraits"])

    # 3. Mesen-verified records
    by_face = {fi: name for name, _, fi in names.values()}
    for fi, (name, rec) in MESEN.items():
        good = records[fi - ex.MOB_FIRST] == rec and by_face.get(fi) == name
        print(f"[3] P{fi:03d} {name}: record {records[fi - ex.MOB_FIRST]} general {by_face.get(fi)} -> "
              f"{'ok' if good else 'MISMATCH'}")
        failed |= not good

    # 4. ground truth images
    gen_dir = os.path.join(REPO, "mob_portrait", "generated")
    for fn in sorted(os.listdir(gen_dir)):
        fi = int(fn[1:4])
        got, total = compare_png(os.path.join(gen_dir, fn), renders[fi], 8, 0)
        print(f"[4] generated {fn}: {got}/{total} pixels match")
        failed |= got != total
    shot_dir = os.path.join(REPO, "mob_portrait", "screenshot")
    face_of = {name: fi for name, _, fi in names.values()}
    for fn in sorted(os.listdir(shot_dir)):
        name = os.path.splitext(fn)[0]
        fi = face_of[name]
        got, total = compare_png(os.path.join(shot_dir, fn), renders[fi], 4, 2)
        print(f"[4] screenshot {fn} (P{fi:03d}): {got}/{total} sampled pixels match ({got / total:.1%})")

    # 5. dedicated portraits
    pts = pe.read_portrait_ptr_table(rom)
    layouts = pe.build_portrait_arrangement_mapping(pts, pe.load_all_arrangements(rom))
    ok = 0
    for p in pts:
        n = p["index"]
        old = pe.generate_portrait(rom, p, layouts[n]).convert("RGBA").tobytes()
        new = ex.to_rgba(ex.compose_display(meta, blobs, {"portrait": n}), colors)
        ok += old == new and sums[f"pt:{n}"] == hashlib.sha256(old).hexdigest()
    users = [(gid, fi) for gid, (_, _, fi) in names.items() if fi < ex.MOB_FIRST]
    ch_ok = sum(sums[f"ch:{gid}"] == sums[f"pt:{fi}"] for gid, fi in users)
    print(f"[5] dedicated portraits vs portrait_export.py: {ok}/{len(pts)} pixel-identical + checksum; "
          f"{ch_ok}/{len(users)} generals' ch: equal their pt:")
    failed |= ok != len(pts) or len(meta["portraits"]) != len(pts) or ch_ok != len(users)

    print("FAIL" if failed else "OK")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
