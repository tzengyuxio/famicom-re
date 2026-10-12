#!/usr/bin/env python3
"""匯出 FC 維新の嵐 的人物、藩、頭像與地圖。

Usage: .venv/bin/python ishin/export.py [--rom ROM] [--out DIR] [--scale N]

Writes characters.csv (both scenarios), domains.csv, facilities.csv, maps.csv
(+ ishin.xlsx when openpyxl is installed), faces/, portraits/, maps/NN_name.png,
world_map.png (31 country maps on their grid), world_map_grid.png (with country map and region lines),
_2x versions of both, and japan.png (勢力図 background).
"""
import argparse
import csv
import importlib.util
import os

import export_kaodata
from PIL import Image, ImageDraw, ImageFont
from rom import (
    CHAR_COUNT,
    COUNTRY_MAPS,
    DEFAULT_ROM,
    DOMAIN_COUNT,
    FACILITY_TYPES,
    MAP_COUNT,
    MAP_H,
    MAP_PALETTE,
    MAP_W,
    PORTRAIT_COUNT,
    SCENARIO_COUNT,
    SLOTS,
    TERRAIN,
    Rom,
    hex_cell,
    nes_rgb,
)

HERE = os.path.dirname(os.path.abspath(__file__))
# mob face parts sheet, shared with the other games (load by path: sangokushi/tools is not a package)
_spec = importlib.util.spec_from_file_location(
    "parts_sheet", os.path.join(os.path.dirname(HERE), "sangokushi", "tools", "parts_sheet.py"))
parts_sheet = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(parts_sheet)


def face_label(code: int) -> tuple[str, str]:
    if code & 0x8000:
        cat = (code >> 12) & 7
        parts = "-".join(str((code >> (10 - 2 * s)) & 3) for s in range(len(SLOTS)))
        return f"M{code:04X}", f"{cat}:{parts}"
    return f"P{code:02d}", ""


def place(rom: Rom, m: int, h: int) -> str:
    if m >= MAP_COUNT:
        return f"0x{m:02X}"
    c, r = hex_cell(h)
    return f"{rom.map_name(m)} ({c},{r})"


def character_rows(rom: Rom) -> list[dict]:
    scen = [rom.characters(s) for s in range(SCENARIO_COUNT)]
    rows = []
    for i in range(CHAR_COUNT):
        base = scen[0][i]
        face, parts = face_label(base["face_code"])
        row = {"Index": i, "Name": base["name"], "Surname": base["surname"], "Given": base["given"],
               "Face": face, "Face_Parts": parts}
        for n, sc in enumerate(scen, 1):
            c = sc[i]
            row.update({
                f"S{n}_Age": c["age"],
                f"S{n}_Rank": rom.rank_name(c["rank"], c["domain"]),
                f"S{n}_Affiliation": rom.affiliation(c["rank"], c["domain"]),
                f"S{n}_Rank_Raw": f"0x{c['rank']:02X}", f"S{n}_Domain_Raw": c["domain"],
                f"S{n}_HP": c["hp"], f"S{n}_HP_Max": c["hp_max"], f"S{n}_Spirit": c["spirit"],
                f"S{n}_Learning": c["learning"], f"S{n}_Martial": c["martial"], f"S{n}_Progress": c["progress"],
                f"S{n}_Sonno": c["sonno"], f"S{n}_Kogi": c["kogi"], f"S{n}_Sabaku": c["sabaku"],
                f"S{n}_Gold": c["gold"], f"S{n}_Goods": c["goods"],
                f"S{n}_Place": place(rom, c["map"], c["hex"]),
                f"S{n}_Trust": " ".join(f"{sc[p]['name'] if p < CHAR_COUNT else p}:{v}" for p, v in c["trust"]),
                f"S{n}_Unk_Home": f"{c['home_unk2']:02X}{c['home_unk3']:02X}",
                f"S{n}_Unk_Place": c["place_rest"],
            })
        rows.append(row)
    return rows


def domain_rows(rom: Rom) -> list[dict]:
    names = rom.domains()
    stats = rom.domain_stats()
    castles = rom.castles()
    units = rom.unit_places(0)
    rows = []
    for i in range(DOMAIN_COUNT):
        s, c = stats[i], castles[i]
        kind = "雄藩" if i < 17 else "幕府" if i == 17 else "天領"
        rows.append({
            "Index": i, "Name": names[i], "Kind": kind, "Castle": place(rom, c["map"], c["hex"]),
            "Owner_Raw": c["owner"],
            "Money": s["money"], "Koku": s["koku"], "Sympathy": s["sympathy"], "Arms": s["arms"],
            "Unit1_Soldiers": s["units"][0][0], "Unit1_Training": s["units"][0][1],
            "Unit1_Place": place(rom, *units[2 * i]),
            "Unit2_Soldiers": s["units"][1][0], "Unit2_Training": s["units"][1][1],
            "Unit2_Place": place(rom, *units[2 * i + 1]),
        })
    return rows


def facility_rows(rom: Rom) -> list[dict]:
    rows = []
    towns = rom.towns()
    for t, (m, h) in enumerate(rom.town_sites()):
        rows.append({"Map": rom.map_name(m), "Map_No": m, "Col": h >> 4, "Row": h & 15, "Kind": "町",
                     "Detail": towns[t]})
    for i, c in enumerate(rom.castles()):
        rows.append({"Map": rom.map_name(c["map"]), "Map_No": c["map"], "Col": c["hex"] >> 4,
                     "Row": c["hex"] & 15, "Kind": "城", "Detail": rom.domains()[i]})
    for f in rom.facilities():
        rows.append({"Map": rom.map_name(f["map"]), "Map_No": f["map"], "Col": f["hex"] >> 4, "Row": f["hex"] & 15,
                     "Kind": TERRAIN.get(rom.map_values(f["map"])[(f["hex"] & 15) * 13 + (f["hex"] >> 4)], "?"),
                     "Detail": FACILITY_TYPES[f["type"]]})
    for m in range(COUNTRY_MAPS):
        for i, v in enumerate(rom.map_values(m)):
            if v in (1, 3, 6, 7):
                rows.append({"Map": rom.map_name(m), "Map_No": m, "Col": i % 13, "Row": i // 13,
                             "Kind": TERRAIN[v], "Detail": ""})
    return rows


def map_rows(rom: Rom) -> list[dict]:
    rows = []
    for m in range(MAP_COUNT):
        x, y = rom.map_grid_pos(m)
        rows.append({"Map_No": m, "Name": rom.map_name(m), "Grid_X": x, "Grid_Y": y,
                     "Values": rom.map_values(m).hex()})
    return rows


def write_csv(rows: list[dict], path: str) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"已匯出 {len(rows)} 筆 → {path}")


def write_xlsx(sheets: dict[str, list[dict]], path: str) -> None:
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        ws.append(list(rows[0]))
        for r in rows:
            ws.append(list(r.values()))
        ws.freeze_panes = "C2"
    wb.save(path)
    print(f"已匯出 → {path}")


def to_image(pixels: bytes, w: int, h: int, scale: int) -> Image.Image:
    img = Image.new("RGB", (w, h))
    img.putdata([nes_rgb(p) for p in pixels])
    return img.resize((w * scale, h * scale), Image.NEAREST) if scale > 1 else img


JP_FONT = "/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc"


REGION_LINE = (255, 64, 64)
LEGEND_TERRAIN = [5, 2, 1, 3, 6, 7, 0, 4, 8, 0x0A, 9]  # 城 町 村 港 鉱山 関所, then the plain terrain


def titled(rom: Rom, img: Image.Image, grid: bool) -> Image.Image:
    """Title over a credit bar (the bar doubles as the rule under it), legend in the empty north-west."""
    font = lambda size: ImageFont.truetype(JP_FONT, size)
    unit = img.width // 100
    top = unit * 10
    out = Image.new("RGB", (img.width, img.height + top), "black")
    out.paste(img, (0, top))
    dr = ImageDraw.Draw(out)
    title = dr.textbbox((unit * 2, unit * 1.5), "維新の嵐 (FC) 全日本図", font=font(unit * 3))
    dr.text((unit * 2, unit * 1.5), "維新の嵐 (FC) 全日本図", fill="white", font=font(unit * 3))
    bar = [0, title[3] + unit, title[2] + unit * 3, title[3] + unit * 3.5]  # bleeds off the left edge
    dr.rectangle(bar, fill=(32, 80, 176))
    dr.text((unit * 2, (bar[1] + bar[3]) / 2), "FB：司馬Game 遊戲存檔", fill="white", font=font(unit * 6 // 5),
            anchor="lm")

    f, icon, row = font(unit), unit * 2, unit * 2.6
    x, y = unit * 2, top + unit * 2
    dr.text((x, y), "圖例", fill="white", font=font(unit * 3 // 2))
    y += unit * 3
    if grid:
        lx = x
        for colour, width, text in ((REGION_LINE, 3, "地方界"), ("white", 1, "國界")):
            dr.line([lx, y + icon // 2, lx + icon, y + icon // 2], fill=colour, width=width * img.width // 1664)
            dr.text((lx + icon + unit // 2, y + icon // 2), text, fill="white", font=f, anchor="lm")
            lx += unit * 9
        y += row
    pal = rom.prg[MAP_PALETTE:MAP_PALETTE + 16]
    for k, v in enumerate(LEGEND_TERRAIN):
        cx, cy = x + (k // 6) * unit * 9, y + (k % 6) * row
        out.paste(to_image(rom.render_bg(*rom.cell_quad(v), 2, pal), 16, 16, 1).resize((icon, icon), Image.NEAREST),
                  (cx, round(cy)))
        dr.text((cx + icon + unit // 2, cy + icon // 2), TERRAIN[v], fill="white", font=f, anchor="lm")
    return out


def world_map_grid(rom: Rom, img: Image.Image, scale: int) -> Image.Image:
    """world_map.png with thin lines around each country map, thick lines around each region and labels."""
    img, u = img.copy(), scale
    mw, mh = MAP_W * 16 * u, MAP_H * 16 * u
    pos = {rom.map_grid_pos(m): m for m in range(COUNTRY_MAPS)}
    try:
        font = ImageFont.truetype(JP_FONT, 12 * u)
    except OSError:  # no Japanese font: labels fall back to numbers
        font = None
    dr, regions = ImageDraw.Draw(img), rom.regions()
    for (x, y), m in pos.items():
        dr.rectangle([x * mw, y * mh, (x + 1) * mw - 1, (y + 1) * mh - 1], outline="white", width=u)
    for (x, y), m in pos.items():
        g = rom.map_region(m)
        for dx, dy, line in ((1, 0, [(x + 1) * mw, y * mh, (x + 1) * mw, (y + 1) * mh]),
                             (-1, 0, [x * mw, y * mh, x * mw, (y + 1) * mh]),
                             (0, 1, [x * mw, (y + 1) * mh, (x + 1) * mw, (y + 1) * mh]),
                             (0, -1, [x * mw, y * mh, (x + 1) * mw, y * mh])):
            n = pos.get((x + dx, y + dy))
            if n is None or rom.map_region(n) != g:
                dr.line(line, fill=REGION_LINE, width=3 * u)
    for (x, y), m in pos.items():
        label = f"{m:02d} {regions[rom.map_region(m)]}" if font else f"{m:02d}/{rom.map_region(m)}"
        cx, cy = x * mw + mw // 2, y * mh + mh // 2
        box = dr.textbbox((cx, cy), label, font=font, anchor="mm")
        dr.rectangle([box[0] - 2 * u, box[1] - 2 * u, box[2] + 2 * u, box[3] + 2 * u], fill="white")
        dr.text((cx, cy), label, fill="black", font=font, anchor="mm")
    return img


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 FC 維新の嵐 人物／藩／頭像／地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"人物": character_rows(rom), "藩": domain_rows(rom), "地點": facility_rows(rom), "地圖": map_rows(rom)}
    for (title, rows), name in zip(sheets.items(), ["characters", "domains", "places", "maps"]):
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "ishin.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    for c in rom.characters(0):
        to_image(rom.face_pixels(c["face_code"]), 40, 48, args.scale).save(
            os.path.join(faces, f"{c['id']:03d}_{c['name']}.png"))
    print(f"已匯出 {CHAR_COUNT} 張人物頭像 → {faces}")
    portraits = os.path.join(args.out, "portraits")
    os.makedirs(portraits, exist_ok=True)
    for n in range(1, PORTRAIT_COUNT + 1):
        to_image(rom.face_pixels(n), 40, 48, args.scale).save(os.path.join(portraits, f"P{n:02d}.png"))
    print(f"已匯出 {PORTRAIT_COUNT} 張專屬頭像 → {portraits}")

    maps = os.path.join(args.out, "maps")
    os.makedirs(maps, exist_ok=True)
    for m in range(MAP_COUNT):
        w, h, px = rom.map_pixels(m)
        to_image(px, w, h, args.scale).save(os.path.join(maps, f"{m:02d}_{rom.map_name(m)}.png"))
    print(f"已匯出 {MAP_COUNT} 張 HEX 地圖（國 {COUNTRY_MAPS}、町 {MAP_COUNT - COUNTRY_MAPS}）→ {maps}")
    w, h, px = rom.world_pixels()
    for scale, suffix in ((args.scale, ""), (2, "_2x")):
        world = to_image(px, w, h, scale)
        grid = world_map_grid(rom, world, scale)
        if suffix:  # the 2x versions are the ones to share: title, legend and credit
            world, grid = titled(rom, world, False), titled(rom, grid, True)
        world.save(os.path.join(args.out, f"world_map{suffix}.png"))
        grid.save(os.path.join(args.out, f"world_map_grid{suffix}.png"))
    w, h, px = rom.japan_pixels()
    to_image(px, w, h, args.scale).save(os.path.join(args.out, "japan.png"))
    print("已匯出 → world_map(_grid)(_2x).png（31 張國地圖依位置表排列，grid 加國／地方格線）、japan.png（勢力図底圖）")

    meta, blobs = export_kaodata.build(args.rom)
    parts_sheet.export_mob_parts(meta, blobs, args.out)

if __name__ == "__main__":
    main()
