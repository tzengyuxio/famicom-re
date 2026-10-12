#!/usr/bin/env python3
"""匯出 FC 水滸伝・天命の誓い 的人物、州、頭像與地圖。

Usage: .venv/bin/python suikoden/export.py [--rom ROM] [--out DIR] [--scale N]

Writes characters.csv (+ .xlsx when openpyxl is installed), provinces.csv,
faces/ (one PNG per character), portraits/ (P00-P99), map.png,
battle_maps/<season>/NN_<province>.png (all four seasons) and battle_maps.csv.
"""
import argparse
import csv
import importlib.util
import os

import export_kaodata
from PIL import Image
from rom import (
    BATTLE_W,
    DEFAULT_ROM,
    MAP_W,
    PORTRAIT_COUNT,
    SEASONS,
    TERRAIN_NAMES,
    Rom,
    decode_mob_code,
    nes_rgb,
)

HERE = os.path.dirname(os.path.abspath(__file__))
# mob face parts sheet, shared with the other games (load by path: sangokushi/tools is not a package)
_spec = importlib.util.spec_from_file_location(
    "parts_sheet", os.path.join(os.path.dirname(HERE), "sangokushi", "tools", "parts_sheet.py"))
parts_sheet = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(parts_sheet)
# Map palette is assigned at run time (province colours follow their ruler); this one is only for display.
MAP_PALETTE = bytes([0x0F, 0x16, 0x07, 0x30, 0x0F, 0x0F, 0x0F, 0x0F, 0x0F, 0x26, 0x36, 0x0F])


def character_rows(rom: Rom) -> list[dict]:
    provinces = [p["name"] for p in rom.provinces()]
    scenarios = [rom.scenario(n) for n in range(1, 5)]
    rows = []
    for c in rom.characters():
        code = c["face_code"]
        if code & 0x8000:
            cat, sel = decode_mob_code(code)
            face = f"M{code & 0x7FFF:04X}"
            parts = f"{cat}-{sel['head']}-{sel['chin']}-{sel['eyes']}-{sel['nose']}-{sel['mouth']}"
        else:
            face, parts = f"P{code:02d}", ""
        row = {
            "Index": c["id"],
            "ROM_Offset": f"0x{0x10 + 0x36004 + c['id'] * 25:05X}",
            "Name": c["name"],
            "Reading": c["reading"],
            "Face": face,
            "Face_Parts": parts,
            "Sex": "男" if c["male"] else "女",
            "Helm": "○" if c["helm"] else "",
            "Chugi": c["chugi"],
            "Jinai": c["jinai"],
            "Yuuki": c["yuuki"],
            "Flags_Lo": c["flags_lo"],
            "Unk19": c["unk19"],
            "Unk24": c["unk24"],
        }
        for n, sc in enumerate(scenarios, 1):
            s = sc[c["id"]]
            row.update({
                f"S{n}_Age": s["age"],
                f"S{n}_Province": provinces[s["province"]] if s["province"] < len(provinces) else s["province"],
                f"S{n}_Status": s["status"],
                f"S{n}_HP": s["hp"],
                f"S{n}_HP_Max": s["hp_max"],
                f"S{n}_Strength": s["strength"],
                f"S{n}_Skill": s["skill"],
                f"S{n}_Intellect": s["intellect"],
                f"S{n}_Unk13": s["unk13"],
                f"S{n}_Unk16": s["unk16"],
                f"S{n}_Unk17": s["unk17"],
            })
        rows.append(row)
    return rows


def province_rows(rom: Rom) -> list[dict]:
    provinces = rom.provinces()
    return [{
        "Index": p["id"],
        "Map_No": p["id"] + 1,
        "Name": p["name"],
        "Neighbors": " ".join(provinces[n]["name"] for n in p["neighbors"]),
        "Neighbor_Ids": " ".join(str(n) for n in p["neighbors"]),
        "Unk4": p["unk4"], "Unk5": p["unk5"], "Unk6": p["unk6"], "Unk7": p["unk7"],
        "Unk8": p["unk8"], "Unk10": p["unk10"], "Unk20": p["unk20"],
    } for p in provinces]


def battle_rows(rom: Rom) -> list[dict]:
    """One row per battle map cell: terrain type and owning province."""
    names = [p["name"] for p in rom.provinces()]
    rows = []
    for n in range(len(names)):
        for i, (t, g) in enumerate(zip(rom.battle_terrain(n), rom.battle_regions(n))):
            rows.append({"Province": n, "Province_Name": names[n], "X": i % BATTLE_W, "Y": i // BATTLE_W,
                         "Terrain": t, "Terrain_Name": TERRAIN_NAMES[t],
                         "Owner": "" if g == 0xFF else g, "Owner_Name": "" if g == 0xFF else names[g]})
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


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 FC 水滸伝 人物／州／頭像／地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    chars, provs = character_rows(rom), province_rows(rom)
    write_csv(chars, os.path.join(args.out, "characters.csv"))
    write_csv(provs, os.path.join(args.out, "provinces.csv"))
    try:
        write_xlsx({"人物": chars, "州": provs}, os.path.join(args.out, "suikoden.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    for c in rom.characters():
        to_image(rom.face_pixels(c["face_code"]), 40, 48, args.scale).save(
            os.path.join(faces, f"{c['id']:03d}_{c['name']}.png"))
    print(f"已匯出 {len(chars)} 張人物頭像 → {faces}")

    portraits = os.path.join(args.out, "portraits")
    os.makedirs(portraits, exist_ok=True)
    for n in range(PORTRAIT_COUNT):
        to_image(rom.face_pixels(n), 40, 48, args.scale).save(os.path.join(portraits, f"P{n:02d}.png"))
    print(f"已匯出 {PORTRAIT_COUNT} 張專屬頭像 → {portraits}")

    tiles, exram = rom.map_cells()
    path = os.path.join(args.out, "map.png")
    to_image(rom.render_cells(tiles, exram, MAP_W, MAP_PALETTE), MAP_W * 8, len(tiles) // MAP_W * 8,
             args.scale).save(path)
    print(f"已匯出 49 州地圖 → {path}（色盤為示意，非遊戲實際配色）")

    for season, label in enumerate(SEASONS):
        battle = os.path.join(args.out, "battle_maps", label)
        os.makedirs(battle, exist_ok=True)
        for p in rom.provinces():
            w, h, px = rom.battle_pixels(p["id"], season)
            to_image(px, w, h, args.scale).save(os.path.join(battle, f"{p['id'] + 1:02d}_{p['name']}.png"))
        print(f"已匯出 {len(rom.provinces())} 張戰鬥地圖（{label}）→ {battle}")
    write_csv(battle_rows(rom), os.path.join(args.out, "battle_maps.csv"))

    meta, blobs = export_kaodata.build(args.rom)
    parts_sheet.export_mob_parts(meta, blobs, args.out)

if __name__ == "__main__":
    main()
