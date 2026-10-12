#!/usr/bin/env python3
"""匯出 FC 三國志II（KOEI）的武將、州、相鄰、頭像、大地圖與戰場地圖。

Usage: .venv/bin/python san2/export.py [--rom ROM] [--out DIR] [--scale N]

Writes generals.csv (352 generals), general_scenarios.csv (6 scenarios), provinces.csv (6 x 41),
adjacency.csv (+ san2.xlsx when openpyxl is installed), faces/ (one PNG per general), portraits/
(F001-F200), map.png, province_hex(_rot30).png, china_battle_map(_labeled, _framed).png, battle_maps/ (41), mob_parts.png and mob_parts/.
"""
import argparse
import csv
import importlib.util
import math
import os

from PIL import Image, ImageDraw
from rom import (
    BATTLE_COLS,
    BATTLE_PALETTE,
    BATTLE_ROWS,
    DEFAULT_ROM,
    FACE_COUNT,
    FACE_H,
    FACE_W,
    MAP_H,
    MAP_W,
    PROVINCE_COUNT,
    SCENARIO_COUNT,
    SCENARIO_TITLES,
    SCENARIO_YEARS,
    TERRAIN,
    TERRAIN_EXRAM,
    TERRAIN_TILES,
    Rom,
    decode_face_code,
    is_composite,
    nes_rgb,
)

HERE = os.path.dirname(os.path.abspath(__file__))
# mob face parts sheet, shared with the other games (load by path: sangokushi/tools is not a package)
_spec = importlib.util.spec_from_file_location(
    "parts_sheet", os.path.join(os.path.dirname(HERE), "sangokushi", "tools", "parts_sheet.py"))
parts_sheet = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(parts_sheet)

SIDES = ["西", "西南", "東南", "西北", "東北", "東"]  # adjacency slot 0-5, geographic (see ROM_FORMAT.md)


def png(px: bytes, w: int, h: int, path: str, scale: int = 1) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata([nes_rgb(c) for c in px])
    if scale > 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    im.save(path)


def face_label(code: int) -> str:
    if not is_composite(code):
        return f"F{code:03d}"
    group, v = decode_face_code(code)
    return f"組合 {group}-" + "".join(str(x) for x in v)


def general_rows(rom: Rom) -> list[dict]:
    return [{"編號": g["id"], "姓名": g["name"], "讀音": g["reading"], "知力": g["int"], "武力": g["war"],
             "魅力": g["cha"], "義理": g["giri"], "仁徳": g["jintoku"], "野望": g["yabou"], "相性": g["aishou"],
             "一族": f"{g['kin']:04X}" if g["kin"] else "", "生年": g["birth"], "登場年": g["debut"] or "",
             "頭像": face_label(g["face"]), "頭像碼": f"{g['face']:04X}", "未知1": g["unknown1"]}
            for g in rom.generals()]


def scenario_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in range(SCENARIO_COUNT):
        rulers = rom.faction_rulers(sc)
        names = rom.generals()
        for g in names:
            p = g["scenarios"][sc]
            if not p:
                continue
            faction = rom.province(sc, p["province"] - 1)["faction"]
            lord = rulers.get(faction) if p["status"] in ("君主", "武將") else None
            rows.append({"劇本": sc + 1, "年": SCENARIO_YEARS[sc], "編號": g["id"], "姓名": g["name"],
                         "身分": p["status"], "州": p["province"], "君主": names[lord]["name"] if lord is not None else "",
                         "忠誠": p["loyalty"] if p["loyalty"] is not None else "", "兵士": p["soldiers"],
                         "年齡": SCENARIO_YEARS[sc] - g["birth"] + 1})
    return rows


def province_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in range(SCENARIO_COUNT):
        rulers, names = rom.faction_rulers(sc), rom.generals()
        for i in range(PROVINCE_COUNT):
            p = rom.province(sc, i)
            lord = rulers.get(p["faction"])
            rows.append({"劇本": sc + 1, "州": i + 1, "勢力": "" if p["faction"] is None else p["faction"],
                         "君主": names[lord]["name"] if lord is not None else "", "人口": p["population"],
                         "金": p["gold"], "兵糧": p["food"], "民忠": p["loyalty"], "土地": p["land"],
                         "治水": p["flood"], "馬": p["horses"], "相場": p["rate"]})
    return rows


def adjacency_rows(rom: Rom) -> list[dict]:
    pos = rom.hex_layout()
    rows = []
    for i, adj in enumerate(rom.adjacency(), 1):
        q, r = pos[i]
        terrain = [t for row in rom.battle_terrain(i - 1) for t in row]
        row = {"州": i, "六角 q": q, "六角 r": r}
        row.update({SIDES[d]: v or "" for d, v in enumerate(adj)})
        row.update({f"戰場{name}": terrain.count(t) for t, name in enumerate(TERRAIN)})
        rows.append(row)
    return rows


def write_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def write_xlsx(sheets: dict[str, list[dict]], path: str) -> None:
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        ws = wb.create_sheet(name)
        ws.append(list(rows[0]))
        for r in rows:
            ws.append(list(r.values()))
    wb.save(path)


def province_hex(rom: Rom, path: str, turn: int = 0) -> None:
    """The 41 provinces on the hex lattice of the adjacency table, in the column layout of china_battle_map.

    Flat-topped hexes: province (q, r) sits in column -(q + r), row -r, every other column half a hex
    lower, so 41 -> 40 -> 31 stack straight up, as the battle fields do. turn rotates the lattice and
    its hexes clockwise by that many degrees; 30 gives pointy-topped hexes and an outline closer to China.
    """
    size = 28
    cells = {i: (-(q + r), -r) for i, (q, r) in rom.hex_layout().items()}
    pts = {i: (c * size * 1.5, (row - c / 2) * size * 3 ** 0.5) for i, (c, row) in cells.items()}
    a = math.radians(turn)
    pts = {i: (x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)) for i, (x, y) in pts.items()}
    x0, y0 = min(x for x, _ in pts.values()), min(y for _, y in pts.values())
    im = Image.new("RGB", (int(max(x for x, _ in pts.values()) - x0) + 2 * size + 20,
                           int(max(y for _, y in pts.values()) - y0) + 2 * size + 20), "white")
    dr = ImageDraw.Draw(im)
    for i, (x, y) in pts.items():
        cx, cy = x - x0 + size + 10, y - y0 + size + 10
        dr.regular_polygon((cx, cy, size), 6, rotation=-turn, fill=(247, 216, 165), outline="black")
        dr.text((cx, cy), str(i), fill="black", anchor="mm")
    im.save(path)


def china_battle_map(rom: Rom, path: str, labeled_path: str, framed_path: str, scale: int) -> None:
    """All 41 battle fields laid out like province_hex.png, sheared into brick columns.

    The hex side (-1, +1) becomes straight up (41 -> 40 -> 31), so a province sits in column
    -(q + r) and row -r, and every other column drops half a field. Rivers and terrain continue
    across the seams in this layout (tools/stitch_test.py); the game itself never joins the fields.
    Fields stack 24 tiles apart, not 25: odd hex columns stick half a hex out of the bottom of a
    field, into the slot the even columns of the field below leave free, so the hexes interlock.
    """
    fw, fh = 2 * BATTLE_COLS, 2 * BATTLE_ROWS  # field pitch in tiles
    cells = {i: (-(q + r), -r) for i, (q, r) in rom.hex_layout().items()}
    org = {i: (c * fw, row * fh - c * fh // 2) for i, (c, row) in cells.items()}
    x0, y0 = min(x for x, _ in org.values()), min(y for _, y in org.values())
    org = {i: (x - x0, y - y0) for i, (x, y) in org.items()}
    w = max(x for x, _ in org.values()) + fw
    h = max(y for _, y in org.values()) + fh + 1
    tiles, ex, mask = [0] * (w * h), [0] * (w * h), [False] * (w * h)
    for i, (ox, oy) in org.items():
        for r, row in enumerate(rom.battle_terrain(i - 1)):
            for c, t in enumerate(row):
                for k, tid in enumerate(TERRAIN_TILES[t]):
                    a = (oy + 2 * r + c % 2 + k // 2) * w + ox + 2 * c + k % 2
                    tiles[a], ex[a], mask[a] = tid, TERRAIN_EXRAM[t][k], True
    px = rom.render_cells(tiles, ex, w, rom.palette(BATTLE_PALETTE), mask)
    big = Image.new("RGB", (w * 8, h * 8))
    big.putdata([(0, 0, 0) if c == 255 else nes_rgb(c) for c in px])
    big = big.resize((big.width * scale, big.height * scale), Image.NEAREST)
    big.save(path)
    framed, u = big.copy(), 8 * scale
    for im, frame in ((big, False), (framed, True)):
        dr = ImageDraw.Draw(im)
        for i, (ox, oy) in org.items():
            if frame:  # straight box along the middle of the zigzag seam, rough on purpose
                dr.rectangle([ox * u, (oy + 0.5) * u, (ox + fw) * u - 1, (oy + fh + 0.5) * u - 1],
                             outline="white", width=scale)
            cx, cy = (ox + fw / 2) * u, (oy + fh / 2 + 0.5) * u
            dr.rectangle([cx - 12 * scale, cy - 7 * scale, cx + 12 * scale, cy + 7 * scale], fill="white")
            dr.text((cx, cy), str(i), fill="black", anchor="mm", font_size=10 * scale)
    big.save(labeled_path)
    framed.save(framed_path)


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 FC 三國志II 資料")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/Sangokushi II (Japan).zip 或 .nes")
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=2, help="地圖 PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"武將": general_rows(rom), "劇本武將": scenario_rows(rom), "州": province_rows(rom),
              "相鄰": adjacency_rows(rom)}
    for (name, rows), fn in zip(sheets.items(), ("generals", "general_scenarios", "provinces", "adjacency")):
        write_csv(rows, os.path.join(args.out, f"{fn}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "san2.xlsx"))
    except ImportError:
        print("（未安裝 openpyxl，略過 XLSX）")

    faces, portraits = os.path.join(args.out, "faces"), os.path.join(args.out, "portraits")
    os.makedirs(faces, exist_ok=True)
    os.makedirs(portraits, exist_ok=True)
    for g in rom.generals():
        png(rom.face_pixels(g["face"]), FACE_W * 8, FACE_H * 8, os.path.join(faces, f"{g['id']:03d}_{g['name']}.png"))
    for f in range(1, FACE_COUNT + 1):
        png(rom.face_pixels(f), FACE_W * 8, FACE_H * 8, os.path.join(portraits, f"F{f:03d}.png"))

    png(rom.map_pixels(), MAP_W * 8, MAP_H * 8, os.path.join(args.out, "map.png"), args.scale)
    province_hex(rom, os.path.join(args.out, "province_hex.png"))
    province_hex(rom, os.path.join(args.out, "province_hex_rot30.png"), turn=30)
    china_battle_map(rom, os.path.join(args.out, "china_battle_map.png"),
                     os.path.join(args.out, "china_battle_map_labeled.png"),
                     os.path.join(args.out, "china_battle_map_framed.png"), args.scale)
    bdir = os.path.join(args.out, "battle_maps")
    os.makedirs(bdir, exist_ok=True)
    for i in range(PROVINCE_COUNT):
        png(rom.battle_pixels(i), BATTLE_COLS * 16, (BATTLE_ROWS * 2 + 1) * 8, os.path.join(bdir, f"{i + 1:02d}.png"),
            args.scale)

    import export_kaodata  # loads sangokushi/tools/export_kaodata.py by path
    meta, blobs = export_kaodata.build(args.rom)
    parts_sheet.export_mob_parts(meta, blobs, args.out)
    n_sc = len(sheets["劇本武將"])
    print(f"已匯出 352 武將（{', '.join(SCENARIO_TITLES)}：{n_sc} 筆劇本配置）、{len(sheets['州'])} 筆州資料 → {args.out}")
    print(f"頭像 352 人＋專屬 {FACE_COUNT} 張；大地圖 {MAP_W * 8}×{MAP_H * 8}；戰場 {PROVINCE_COUNT} 張")


if __name__ == "__main__":
    main()
