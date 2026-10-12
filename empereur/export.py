#!/usr/bin/env python3
"""匯出 FC ランペルール 的人物、國家、都市、頭像與地圖。

Usage: .venv/bin/python empereur/export.py [--rom ROM] [--out DIR] [--scale N]

Writes characters.csv, scenario_characters.csv, countries.csv, scenario_countries.csv,
cities.csv, scenario_cities.csv (+ empereur.xlsx when openpyxl is installed),
faces/ (one PNG per character), portraits/ (P00-P89), map.png, battle_maps/<variant>/NN_<city>.png
and battle_maps.csv.
"""
import argparse
import csv
import os

from PIL import Image
from rom import (
    ABILITIES,
    BATTLE_W,
    CHAR_SIZE,
    CHAR_TABLE,
    COMPOSITE_PARTS,
    DEFAULT_ROM,
    MAP_H,
    MAP_W,
    PERSONALITY,
    PORTRAIT_COUNT,
    SCENARIOS,
    STATUS_NAMES,
    TERRAIN_NAMES,
    Rom,
    nes_rgb,
)

HERE = os.path.dirname(os.path.abspath(__file__))
# Variant 1 equals variant 0 for every terrain a map uses (0-11), so it is not exported.
VARIANT_LABELS = {0: "normal", 2: "winter"}


def face_label(code: int) -> tuple[str, str]:
    if code & 0x8000:
        parts = "-".join(str(code >> COMPOSITE_PARTS[p][0] & 3) for p in COMPOSITE_PARTS)
        return f"M{code & 0x7FFF:04X}", f"{code & 3}:{parts}"
    return f"P{code:02d}", ""


def character_rows(rom: Rom) -> list[dict]:
    rows = []
    for c in rom.characters():
        face, parts = face_label(c["face_code"])
        row = {"Index": c["id"], "ROM_Offset": f"0x{0x10 + CHAR_TABLE + c['id'] * CHAR_SIZE:05X}",
               "Name": c["name"], "Face": face, "Face_Parts": parts}
        row.update({name: "○" if name in c["personality"] else "" for name, _ in PERSONALITY})
        row.update({"Pers_Unk": c["pers_byte"] & 3, "Unk15": c["unk15"]})
        rows.append(row)
    return rows


def scenario_character_rows(rom: Rom) -> list[dict]:
    names = [c["name"] for c in rom.characters()]
    cities = [c["name"] for c in rom.cities()]
    countries = [c["name"] for c in rom.countries()]
    rows = []
    for s in range(1, len(SCENARIOS) + 1):
        for c in rom.scenario_characters(s):
            rows.append({
                "Scenario": s, "Index": c["id"], "Name": names[c["id"]],
                "Nation": countries[c["nation"]] if c["nation"] < len(countries) else c["nation"],
                "City": cities[c["city"]] if c["city"] < len(cities) else c["city"],
                "Status": STATUS_NAMES.get(c["status"], c["status"]), "Status_Code": c["status"],
                "Age": c["age"],
                **{name: c[name] for name, *_ in ABILITIES},
                "Loyalty": c["loyalty"], "Infantry": c["infantry"], "Cavalry": c["cavalry"],
                "Artillery": c["artillery"], "Morale": c["morale"], "Training": c["training"],
                "Unk3": c["unk3"], "Unk12": c["unk12"],
            })
    return rows


def country_rows(rom: Rom) -> list[dict]:
    return [{"Index": c["id"], "Name": c["name"], "Flags": f"0x{c['flags']:02X}"} for c in rom.countries()]


def scenario_country_rows(rom: Rom) -> list[dict]:
    names = [c["name"] for c in rom.countries()]
    rows = []
    for s in range(1, len(SCENARIOS) + 1):
        sc = rom.scenario_characters(s)
        for c in rom.scenario_countries(s):
            ruler = [x["id"] for x in sc if x["nation"] == c["id"] and x["status"] == 7]
            cities = sum(1 for x in rom.scenario_cities(s) if x["owner"] == c["id"])
            rows.append({"Scenario": s, "Index": c["id"], "Name": names[c["id"]], "Cities": cities,
                         "Ruler": " ".join(rom.characters()[i]["name"] for i in ruler),
                         "Gold": c["gold"], "Food": c["food"], "Unk9": c["unk9"],
                         "Unk0": c["unk0"], "Unk11": c["unk11"]})
    return rows


def city_rows(rom: Rom) -> list[dict]:
    cities = rom.cities()
    return [{
        "Index": c["id"], "Map_No": c["id"] + 1, "Name": c["name"],
        "Neighbors": " ".join(cities[n]["name"] for n in c["neighbors"]),
        "Neighbor_Nos": " ".join(str(n + 1) for n in c["neighbors"]),
        "Map_X": c["map_x"], "Map_Y": c["map_y"],
        "View_X": " ".join(map(str, c["view_x"])), "View_Y": " ".join(map(str, c["view_y"])),
        "Unk12": c["unk12"], "Flags": f"0x{c['flags']:02X}",
    } for c in cities]


def scenario_city_rows(rom: Rom) -> list[dict]:
    names = [c["name"] for c in rom.cities()]
    countries = [c["name"] for c in rom.countries()]
    rows = []
    for s in range(1, len(SCENARIOS) + 1):
        for c in rom.scenario_cities(s):
            rows.append({
                "Scenario": s, "Index": c["id"], "Map_No": c["id"] + 1, "Name": names[c["id"]],
                "Owner": countries[c["owner"]] if c["owner"] < len(countries) else "中立",
                "Population": c["population"], "Hospital": c["hospital"], "Industry": c["industry"],
                "Commerce": c["commerce"], "Agriculture": c["agriculture"],
                "Food_Supply": c["food_supply"], "Goods_Supply": c["goods_supply"], "Hygiene": c["hygiene"],
                "Gold": c["gold"], "Food": c["food"], "Goods": c["goods"],
                "Reserve_Soldiers": c["reserve_soldiers"], "Reserve_Horses": c["reserve_horses"],
                "Reserve_Cannons": c["reserve_cannons"], "Ships": c["ships"], "Flags": f"0x{c['flags']:02X}",
                "Unk0": c["unk0"], "Unk20": c["unk20"], "Unk25": c["unk25"],
            })
    return rows


def battle_rows(rom: Rom) -> list[dict]:
    """One row per battle map cell: terrain type."""
    names = [c["name"] for c in rom.cities()]
    rows = []
    for n, name in enumerate(names):
        for i, t in enumerate(rom.battle_terrain(n)):
            rows.append({"City": n, "Map_No": n + 1, "City_Name": name, "X": i % BATTLE_W, "Y": i // BATTLE_W,
                         "Terrain": t, "Terrain_Name": TERRAIN_NAMES.get(t, "")})
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
    ap = argparse.ArgumentParser(description="匯出 FC ランペルール 人物／國家／都市／頭像／地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {
        "人物": character_rows(rom), "劇本人物": scenario_character_rows(rom),
        "國家": country_rows(rom), "劇本國家": scenario_country_rows(rom),
        "都市": city_rows(rom), "劇本都市": scenario_city_rows(rom),
    }
    files = ["characters", "scenario_characters", "countries", "scenario_countries", "cities", "scenario_cities"]
    for name, rows in zip(files, sheets.values()):
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "empereur.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    for c in rom.characters():
        to_image(rom.face_pixels(c["face_code"]), 40, 48, args.scale).save(
            os.path.join(faces, f"{c['id']:03d}_{c['name']}.png"))
    print(f"已匯出 {len(sheets['人物'])} 張人物頭像 → {faces}")

    portraits = os.path.join(args.out, "portraits")
    os.makedirs(portraits, exist_ok=True)
    for n in range(PORTRAIT_COUNT):
        to_image(rom.face_pixels(n), 40, 48, args.scale).save(os.path.join(portraits, f"P{n:02d}.png"))
    print(f"已匯出 {PORTRAIT_COUNT} 張專屬頭像 → {portraits}")

    path = os.path.join(args.out, "map.png")
    to_image(rom.map_pixels(), MAP_W * 8, MAP_H * 8, args.scale).save(path)
    print(f"已匯出 46 都市大地圖 → {path}")

    for variant, label in VARIANT_LABELS.items():
        out = os.path.join(args.out, "battle_maps", label)
        os.makedirs(out, exist_ok=True)
        for c in rom.cities():
            w, h, px = rom.battle_pixels(c["id"], variant)
            to_image(px, w, h, args.scale).save(os.path.join(out, f"{c['id'] + 1:02d}_{c['name']}.png"))
        print(f"已匯出 {len(sheets['都市'])} 張戰場地圖（{label}）→ {out}")
    write_csv(battle_rows(rom), os.path.join(args.out, "battle_maps.csv"))


if __name__ == "__main__":
    main()
