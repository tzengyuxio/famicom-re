#!/usr/bin/env python3
"""匯出 FC 蒼き狼と白き牝鹿・ジンギスカン 的人物、國、頭像與地圖。

Usage: .venv/bin/python genghis/export.py [--rom ROM] [--out DIR] [--scale N]

Writes characters.csv, provinces.csv, women.csv, battle_maps.csv (+ genghis.xlsx when openpyxl
is installed), faces/, portraits/, map_{mongol,world}.png (+ _labeled), battle_maps/NN_name.png
and battle_maps/terrain.png.
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw
from rom import (
    BATTLE_BLOCKS,
    BATTLE_COUNT,
    BATTLE_FIRST_TILE,
    BATTLE_H,
    BATTLE_PALETTE,
    BATTLE_TILES,
    BATTLE_W,
    DEFAULT_ROM,
    MAP_X,
    MAP_Y,
    PORTRAIT_COUNT,
    PROVINCE_FIELDS,
    SCENARIOS,
    STATS,
    TERRAIN_NAMES,
    TERRAIN_TAGS,
    Rom,
    nes_rgb,
)

HERE = os.path.dirname(os.path.abspath(__file__))
ROLES = {"ruler": "君主", "general": "將軍", "heir": "子女", "extra": "繼承人?", "woman": "女性"}


def face_label(code: int) -> str:
    if code == 0x8000:
        return ""
    if code & 0x8000:
        return f"M{code & 0x7FFF:04X}"
    return f"P{code:02d}"


def face_parts(code: int) -> str:
    if not code & 0x8000 or code == 0x8000:
        return ""
    return f"{(code >> 12) & 3}-{(code >> 9) & 7}-{(code >> 6) & 7}-{(code >> 3) & 7}-{code & 7}"


def character_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in SCENARIOS:
        s = rom.scenario(sc)
        names = [p["name"] for p in s["provinces"]]
        rulers = s["rulers"]

        def add(role: str, p: dict, country: int | None, s=s, names=names, **extra) -> None:
            stats = p.get("stats", [""] * 6)
            rows.append({"Scenario": s["label"], "Role": ROLES[role], "Name": p["name"], "Age": p["age"],
                         "Country": "" if country is None else names[country],
                         **dict(zip(STATS, stats)), "Face": face_label(p["face"]), "Face_Code": f"{p['face']:04X}",
                         "Face_Parts": face_parts(p["face"]), **extra})

        for r in rulers:
            add("ruler", r, r["country"], Value="", Unk=f"unk27={r['unk27']} unk31={r['unk31']}")
        for g in s["generals"]:
            lord = rulers[g["family"]] if sc == "mongol" else rulers[[0, 6, 10, 18][g["family"]]]
            add("general", g, lord["country"], Value="", Unk=f"unk27={g['unk27']} lord={lord['name']}")
        for h in s["heirs"]:
            lord = rulers[h["family"]] if sc == "mongol" else rulers[[0, 6, 10, 18][h["family"]]]
            add("heir", h, lord["country"], Value=h["value"],
                Unk=f"unk17={h['unk17']} unk18={h['unk18']} parent={lord['name']}")
        for e in s["extra"]:
            if e["face"]:
                add("extra", {"name": "", **e}, e["country"], Value=e["value"],
                    Unk=f"unk3={e['unk3']} unk4={e['unk4']} unk5={e['unk5']}")
    return rows


def province_rows(rom: Rom) -> list[dict]:
    rows = []
    for sc in SCENARIOS:
        s = rom.scenario(sc)
        names = [p["name"] for p in s["provinces"]]
        for p in s["provinces"]:
            rows.append({"Scenario": s["label"], "Id": p["id"], "No": p["id"] + 1, "Name": p["name"],
                         "Ruler": s["rulers"][p["owner"]]["name"],
                         **{f"{key}" + (f"[{label}]" if label else ""): p[key] for _, key, label in PROVINCE_FIELDS},
                         "Neighbors": " ".join(names[n] for n in p["neighbors"]),
                         "Neighbor_Nos": " ".join(str(n + 1) for n in p["neighbors"]),
                         "Map_X": p["x"], "Map_Y": p["y"], "Adj_Unk4": p["adj_unk4"],
                         "Units_Raw": p["units"], "Tail_Raw": p["tail"],
                         "Battle_Map": rom.battle_index(sc, p["id"])})
    return rows


def women_rows(rom: Rom) -> list[dict]:
    return [{"Id": w["id"], "Scenario": SCENARIOS[w["scenario"]][1], "Name": w["name"], "Unk13": w["unk13"],
             "Portraits": " ".join(f"P{n:02d}" for n in w["portraits"])} for w in rom.women()]


def battle_names(rom: Rom) -> list[str]:
    names = []
    for sc in SCENARIOS:
        names += [p["name"] for p in rom.scenario(sc)["provinces"]]
    return names


def battle_rows(rom: Rom) -> list[dict]:
    rows = []
    for idx, name in enumerate(battle_names(rom)):
        for i, v in enumerate(rom.battle_cells(idx)):
            rows.append({"Map": idx, "Name": name, "X": i % BATTLE_W, "Y": i // BATTLE_W, "Terrain": v & 0x7F,
                         "Terrain_Name": TERRAIN_NAMES[v & 0x7F], "Entry": "○" if v & 0x80 else ""})
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
        ws.freeze_panes = "D2"
    wb.save(path)
    print(f"已匯出 → {path}")


def to_image(pixels: bytes, w: int, h: int, scale: int) -> Image.Image:
    img = Image.new("RGB", (w, h))
    img.putdata([nes_rgb(p) for p in pixels])
    return img.resize((w * scale, h * scale), Image.NEAREST) if scale > 1 else img


def terrain_sheet(rom: Rom, scale: int) -> Image.Image:
    """The 8 terrain blocks (32x32 each) with the battle palette, sub-palette per quadrant from map data."""
    pal = rom.prg[BATTLE_PALETTE:BATTLE_PALETTE + 16]
    sheet = Image.new("RGB", (8 * 40, 46), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    sub_of = {}
    for idx in range(BATTLE_COUNT):  # first sub-palettes seen for each terrain's top-left cell
        ids, sub = rom.battle_tilemap(idx)
        cells = rom.battle_cells(idx)
        for n, v in enumerate(cells):
            c, r = n % BATTLE_W, n // BATTLE_W
            y0 = 4 * r + 2 * (c & 1)
            sub_of.setdefault(v & 0x7F, [sub[(y0 + j) * BATTLE_W * 4 + 4 * c + i] for j in range(4) for i in range(4)])
    for t in range(8):
        ids = rom.prg[BATTLE_BLOCKS + 16 * t:BATTLE_BLOCKS + 16 * t + 16]

        def off(tid: int):
            return BATTLE_TILES + (tid - BATTLE_FIRST_TILE) * 16 if tid >= BATTLE_FIRST_TILE else None

        px = rom.render_tiles(ids, 4, sub_of.get(t, [0] * 16), off, pal)
        sheet.paste(to_image(px, 32, 32, 1), (t * 40 + 4, 12))
        draw.text((t * 40 + 4, 0), f"{t} {TERRAIN_TAGS[t]}"[:7], fill=(0, 0, 0))
    return sheet.resize((sheet.width * scale, sheet.height * scale), Image.NEAREST)


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 FC ジンギスカン 人物／國／頭像／地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    chars, provs, women, battles = character_rows(rom), province_rows(rom), women_rows(rom), battle_rows(rom)
    for name, rows in [("characters", chars), ("provinces", provs), ("women", women), ("battle_maps", battles)]:
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    try:
        write_xlsx({"人物": chars, "國": provs, "女性": women, "戰場": battles}, os.path.join(args.out, "genghis.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    n = 0
    for i, c in enumerate(chars):
        code = int(c["Face_Code"], 16)
        if code == 0x8000:
            continue
        sc = "M" if c["Scenario"] == SCENARIOS["mongol"][1] else "W"
        label = c["Name"] or f"{c['Country']}_{c['Role']}"
        to_image(rom.face_pixels(code), 40, 48, args.scale).save(
            os.path.join(faces, f"{sc}{i:03d}_{c['Role']}_{label}.png"))
        n += 1
    print(f"已匯出 {n} 張人物頭像 → {faces}")

    portraits = os.path.join(args.out, "portraits")
    os.makedirs(portraits, exist_ok=True)
    for p in range(PORTRAIT_COUNT):
        to_image(rom.face_pixels(p), 40, 48, args.scale).save(os.path.join(portraits, f"P{p:02d}.png"))
    print(f"已匯出 {PORTRAIT_COUNT} 張專屬頭像 → {portraits}")

    for sc in SCENARIOS:
        w, h, px = rom.map_pixels(sc)
        img = to_image(px, w, h, 1)
        img.resize((w * args.scale, h * args.scale), Image.NEAREST).save(os.path.join(args.out, f"map_{sc}.png"))
        big = img.resize((w * 3, h * 3), Image.NEAREST)
        draw = ImageDraw.Draw(big)
        for p in rom.scenario(sc)["provinces"]:
            x, y = (p["x"] - MAP_X) * 24, (p["y"] - MAP_Y) * 24
            draw.rectangle([x, y, x + 47, y + 23], fill=(0, 0, 0))
            draw.text((x + 4, y + 5), f"{p['id'] + 1}", fill=(255, 255, 255))
        big.save(os.path.join(args.out, f"map_{sc}_labeled.png"))
    print(f"已匯出大地圖 → {args.out}/map_*.png（_labeled 標上國號）")

    battle = os.path.join(args.out, "battle_maps")
    os.makedirs(battle, exist_ok=True)
    for idx, name in enumerate(battle_names(rom)):
        w, h, px = rom.battle_pixels(idx)
        to_image(px, w, h, args.scale).save(os.path.join(battle, f"{idx:02d}_{name}.png"))
    terrain_sheet(rom, max(args.scale, 2)).save(os.path.join(battle, "terrain.png"))
    print(f"已匯出 {BATTLE_COUNT} 張戰場地圖（{BATTLE_W}×{BATTLE_H} 格）→ {battle}")


if __name__ == "__main__":
    main()
