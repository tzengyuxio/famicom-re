#!/usr/bin/env python3
"""匯出 FC 蒼き狼と白き牝鹿・元朝秘史 的人物、國、兵科、交易品、頭像與地圖。

Usage: .venv/bin/python genchou/export.py [--rom ROM] [--out DIR] [--scale N]

Writes generals.csv (every scenario), countries.csv, units.csv, goods.csv
(+ genchou.xlsx when openpyxl is installed), faces/ (one PNG per distinct character),
portraits/ (P00-P79), map_mongol.png, map_world.png, battle_maps/NN_<country>.png
and battle_maps.csv.
"""
import argparse
import csv
import os

from PIL import Image
from rom import (
    BATTLE_COUNT,
    BATTLE_W,
    DEFAULT_ROM,
    GRADES,
    MAP_H,
    MAP_W,
    PORTRAIT_COUNT,
    SCENARIO_COUNT,
    TERRAIN_NAMES,
    UNIT_CLASSES,
    Rom,
    decode_face_code,
    is_composite,
    nes_rgb,
)

HERE = os.path.dirname(os.path.abspath(__file__))
# Person culture (byte 22 bits 2-4); the names agree with where each person lives in the scenarios
CULTURES = ["モンゴル", "中央アジア", "インド", "日本", "西欧", "東欧", "イスラム", "中国"]
STATUS = {3: "王", 1: "家臣", 0: "在野"}
# [EXT] kanji for the goods names the game spells in kana
GOODS_KANJI = ["毛皮", "絹", "宝石", "貴金属", "医薬品", "木工品", "陶磁器", "ガラス", "織物", "香料", "食糧", "武具"]


def grade(v: int) -> str:
    return GRADES[v] if v < len(GRADES) else "-"


def face_label(code: int) -> str:
    if not code & 0x8000:
        return f"P{code:02d}"
    return f"M{code & 0x7FFF:04X}" if is_composite(code) else f"?{code:04X}"


def battle_name(rom: Rom, n: int) -> str:
    return rom.country_names(0)[n] if n < 14 else rom.country_names(1)[n - 14]


def general_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in range(SCENARIO_COUNT):
        houses, countries = rom.house_names(s), rom.country_names(s)
        year = rom.scenario_info(s)["year"]
        for g in rom.generals(s):
            code = g["face_code"]
            head = decode_face_code(code)[0] if is_composite(code) else ""
            rows.append({
                "Scenario": s + 1, "Year": year, "Slot": g["slot"], "ROM_Offset": f"0x{0x10 + g['offset']:05X}",
                "Name": g["name"],
                "Status": STATUS.get(g["status"], g["status"]),
                "House": g["house"], "House_Name": "在野" if g["house"] == 0xFF else houses.get(g["house"], ""),
                "Country": g["country"] + 1,
                "Country_Name": countries[g["country"]] if g["country"] < len(countries) else "",
                "Age": g["age"],
                "HP": g["hp"], "HP_Max": g["hp_max"],
                "War": grade(g["war"]), "Politics": grade(g["politics"]),
                "Charm": grade(g["charm"]), "Command": grade(g["command"]),
                "Culture": CULTURES[g["culture"]],
                "Face": face_label(code), "Face_Head": head,
                "Unk22": f"{g['unk22']:02X}",
            })
    return rows


def country_rows(rom: Rom) -> list[dict]:
    units = [u["name"] for u in rom.units()]
    rows = []
    for s in range(SCENARIO_COUNT):
        houses = rom.house_names(s)
        for p in rom.provinces(s):
            row = {
                "Scenario": s + 1, "No": p["id"] + 1, "Name": p["name"],
                "House": p["house"], "House_Name": "" if p["house"] == 0xFF else houses.get(p["house"], ""),
                "Gold": p["gold"], "Food": p["food"], "Population": p["population"],
                "Farm%": p["split"][0], "Herd%": p["split"][1], "Craft%": p["split"][2], "Town%": p["split"][3],
                "Unk11_14": " ".join(map(str, p["unk11"])),
            }
            row.update({f"Units_{name}": n for name, n in zip(units, p["unk15"])})
            row.update({"Unk31_32": " ".join(map(str, p["unk31"])), "Unk33": p["unk33"],
                        "Split2": " ".join(map(str, p["split2"])), "Unk38": p["unk38"]})
            rows.append(row)
    return rows


def unit_rows(rom: Rom) -> list[dict]:
    return [{
        "Id": u["id"], "Name": u["name"], "Class": UNIT_CLASSES[u["class"]],
        "Morale": u["morale"], "Mobility": u["mobility"],
        "Melee": grade(u["melee"]), "Charge": grade(u["charge"]),
        "Missile": grade(u["missile"]), "Defense": grade(u["defense"]),
        "Special": "" if u["special"] == 0xFF else u["special"],
        "Price": u["price"], "Mercenary_Price": u["price"] * 3 // 2, "COM_Rank": u["com_rank"],
    } for u in rom.units()]


def goods_rows(rom: Rom) -> list[dict]:
    merchants, table = rom.merchants(), rom.trade_table()
    rows = []
    for i, name in enumerate(rom.goods()):
        row = {"Id": i, "Name": name, "[EXT]Kanji": GOODS_KANJI[i]}
        row.update({f"Table_{m}": table[k][i] for k, m in enumerate(merchants)})
        rows.append(row)
    return rows


def battle_rows(rom: Rom) -> list[dict]:
    rows = []
    for n in range(BATTLE_COUNT):
        name = battle_name(rom, n)
        entry_names = rom.country_names(0 if n < 14 else 1)
        for i, (t, e) in enumerate(zip(rom.battle_terrain(n), rom.battle_entries(n))):
            rows.append({"Map": n + 1, "Country": name, "X": i % BATTLE_W + 1, "Y": i // BATTLE_W + 1,
                         "Terrain": t, "Terrain_Name": TERRAIN_NAMES[t],
                         "Entry": "" if e is None else e + 1,
                         "Entry_Name": "" if e is None else entry_names[e]})
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
        ws.freeze_panes = "B2"
    wb.save(path)
    print(f"已匯出 → {path}")


def to_image(pixels: bytes, w: int, h: int, scale: int) -> Image.Image:
    img = Image.new("RGB", (w, h))
    img.putdata([nes_rgb(p) for p in pixels])
    return img.resize((w * scale, h * scale), Image.NEAREST) if scale > 1 else img


def distinct_characters(rom: Rom) -> list[dict]:
    """Every (name, face code) once, in order of first appearance over the scenarios."""
    seen, out = set(), []
    for s in range(SCENARIO_COUNT):
        for g in rom.generals(s):
            key = (g["name"], g["face_code"])
            if key not in seen:
                seen.add(key)
                out.append({"id": len(out), "scenario": s + 1, **g})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 FC 元朝秘史 人物／國／兵科／交易品／頭像／地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"人物": general_rows(rom), "國": country_rows(rom), "兵科": unit_rows(rom),
              "交易品": goods_rows(rom), "戰場": battle_rows(rom)}
    for (title, rows), name in zip(sheets.items(), ["generals", "countries", "units", "goods", "battle_maps"]):
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "genchou.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    chars = distinct_characters(rom)
    drawn = [c for c in chars if not c["face_code"] & 0x8000 or is_composite(c["face_code"])]
    for c in drawn:
        to_image(rom.face_pixels(c["face_code"]), 40, 48, args.scale).save(
            os.path.join(faces, f"{c['id']:03d}_{c['name']}.png"))
    print(f"已匯出 {len(drawn)} 張人物頭像 → {faces}（{len(chars) - len(drawn)} 人的頭像碼無法解碼，略過）")

    portraits = os.path.join(args.out, "portraits")
    os.makedirs(portraits, exist_ok=True)
    for n in range(PORTRAIT_COUNT):
        to_image(rom.face_pixels(n), 40, 48, args.scale).save(os.path.join(portraits, f"P{n:02d}.png"))
    print(f"已匯出 {PORTRAIT_COUNT} 張專屬頭像 → {portraits}")

    for name in ("mongol", "world"):
        tiles, exram = rom.map_cells(name)
        path = os.path.join(args.out, f"map_{name}.png")
        to_image(rom.render_cells(tiles, exram, MAP_W, rom.palette()), MAP_W * 8, MAP_H * 8, args.scale).save(path)
        print(f"已匯出大地圖 → {path}")

    battle = os.path.join(args.out, "battle_maps")
    os.makedirs(battle, exist_ok=True)
    for n in range(BATTLE_COUNT):
        w, h, px = rom.battle_pixels(n)
        to_image(px, w, h, args.scale).save(os.path.join(battle, f"{n + 1:02d}_{battle_name(rom, n)}.png"))
    print(f"已匯出 {BATTLE_COUNT} 張戰場地圖 → {battle}（調色盤為推定）")


if __name__ == "__main__":
    main()
