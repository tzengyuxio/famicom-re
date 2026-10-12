#!/usr/bin/env python3
"""匯出 FC 三國志II 覇王の大陸 的武將、州、君主、道具、頭像與地圖。

Usage: .venv/bin/python haou/export.py [--rom ROM] [--out DIR] [--scale N]

Writes generals.csv, provinces.csv, lords.csv, items.csv, battle_maps.csv (+ haou.xlsx when openpyxl is
installed), faces/ (one PNG per general), portraits/ (F000-F182, 5 expressions + talking frame each),
map.png (strategy map with castles) and battle_maps/ (30 fields, 512 x 320).
The faces are whole per-character sprites (no composite / mob-face mechanism), so there are no mob parts.
"""
import argparse
import csv
import os

from PIL import Image
from rom import (
    ARMY_TYPES,
    BATTLE_H,
    BATTLE_W,
    DEFAULT_ROM,
    EXPRESSIONS,
    FACE_H,
    FACE_W,
    ITEM_NAMES,
    LORDS,
    NO_LORD,
    PROVINCE_COUNT,
    STATUS,
    Rom,
    nes_rgb,
)

HERE = os.path.dirname(os.path.abspath(__file__))
KANJI_TSV = os.path.join(HERE, "data", "kanji_names.tsv")


def png(px: bytes, w: int, h: int, path: str, scale: int = 1) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata([nes_rgb(c) for c in px])
    if scale > 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    im.save(path)


def kanji_names() -> dict[int, tuple[str, str]]:
    """General id -> ([EXT] kanji, source), from data/kanji_names.tsv."""
    out = {}
    with open(KANJI_TSV, encoding="utf-8") as f:
        next(f)
        for line in f:
            i, _, kanji, source = line.rstrip("\n").split("\t")
            out[int(i)] = (kanji, source)
    return out


def general_rows(rom: Rom) -> list[dict]:
    kanji, faces = kanji_names(), rom.faces()
    names = [p["name"] for p in rom.provinces()]
    lords = {rom.lord_general(o): o for o in range(len(LORDS))}
    owner_of = {g: p["owner"] for p in rom.provinces() for g in p["generals"]}
    rows = []
    for g in rom.generals():
        i = g["index"]
        p = g.get("province")
        owner = owner_of.get(i, NO_LORD)
        rows.append({
            "編號": i, "姓名": g["name"], "[EXT]漢字": kanji[i][0], "[EXT]漢字來源": kanji[i][1],
            "君主": "○" if i in lords else "", "体": g["body"], "武": g["war"], "知": g["intellect"],
            "忠": "--" if i in lords else g["loyalty"], "徳": g["virtue"], "経": g["exp"], "レベル": g["level"],
            "軍種": ARMY_TYPES[g["army"]] + "軍", "兵": g["troops"], "武器": ITEM_NAMES[g["weapon"]],
            "防具": ITEM_NAMES[g["armour"]], "身分(byte11 bit0-1)": STATUS.get(g["status"], g["status"]),
            "所在州": names[p] if p is not None else "", "勢力": LORDS[owner] if owner < len(LORDS) else "",
            "経原值(byte6-7)": g["exp_raw"], "byte5": g["b5"], "頭像": f"F{faces.index(rom.face_of(i)):03d}",
            "頭像CHR": f"{rom.face_of(i)[0]}/{rom.face_of(i)[1]}", "原始資料": g["raw"].hex(" "),
        })
    return rows


def province_rows(rom: Rom) -> list[dict]:
    gens = rom.generals()
    names = [p["name"] for p in rom.provinces()]
    rows = []
    for p in rom.provinces():
        members = [gens[g]["name"] for g in p["generals"]]
        x, y = rom.castle(p["index"])
        rows.append({
            "編號": p["index"], "州": p["name"], "讀音": p["reading"],
            "君主": LORDS[p["owner"]] if p["owner"] < len(LORDS) else "",
            "太守": members[0] if members else "", "金": p["gold"], "米": p["rice"], "人口": p["population"],
            "土地": p["land"], "産業": p["industry"], "防災": p["disaster"], "統治度": p["rule"],
            "武将數": len(members), "兵士": sum(gens[g]["troops"] for g in p["generals"]), "武將": " ".join(members),
            "相鄰": " ".join(names[n] for n, _ in rom.neighbours(p["index"])),
            "相鄰值(未解析)": " ".join(str(v) for _, v in rom.neighbours(p["index"])),
            "城x": x, "城y": y + 1, "byte12-13": p["b12"], "原始資料": p["raw"].hex(" "),
        })
    return rows


def lord_rows(rom: Rom) -> list[dict]:
    kanji = kanji_names()
    rows = []
    for o, name in enumerate(LORDS):
        g = rom.lord_general(o)
        provs = [p["name"] for p in rom.provinces() if p["owner"] == o]
        rows.append({"編號": o, "君主": name, "武將編號": g, "姓名": rom.general_name(g), "[EXT]漢字": kanji[g][0],
                     "州數": len(provs), "州": " ".join(provs)})
    return rows


def item_rows(rom: Rom) -> list[dict]:
    holders = {}
    for g in rom.generals():
        holders.setdefault(g["weapon"], []).append(g["name"])
        holders.setdefault(g["armour"], []).append(g["name"])
    return [{"編號": i, "名稱": n, "種類": "武器" if i < 24 else "防具", "CHR bank": rom.item_record(i)[0],
             "開局持有": " ".join(holders.get(i, []))} for i, n in enumerate(ITEM_NAMES)]


def battle_rows(rom: Rom) -> list[dict]:
    rows = []
    for i in range(PROVINCE_COUNT):
        cells = rom.battle_cells(i)
        rows.append({"編號": i, "州": rom.province(i)["name"], "區塊": " ".join(map(str, rom.battle_blocks(i))),
                     "寬": BATTLE_W, "高": BATTLE_H,
                     "metatile(每列以/分隔)": "/".join(cells[r * BATTLE_W:(r + 1) * BATTLE_W].hex()
                                                    for r in range(BATTLE_H))})
    return rows


def write_csv(rows: list[dict], path: str) -> None:
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


def write_xlsx(sheets: dict[str, list[dict]], path: str) -> None:
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        fields = list(dict.fromkeys(k for r in rows for k in r))
        ws.append(fields)
        for r in rows:
            ws.append([r.get(k, "") for k in fields])
        ws.freeze_panes = "A2"
    wb.save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 FC 覇王の大陸 武將／州／君主／道具／頭像／地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"武將": general_rows(rom), "州": province_rows(rom), "君主": lord_rows(rom), "道具": item_rows(rom),
              "戰場": battle_rows(rom)}
    for rows, name in zip(sheets.values(), ["generals", "provinces", "lords", "items", "battle_maps"]):
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "haou.xlsx"))
    except ImportError:
        print("openpyxl 未安裝，略過 .xlsx")

    kanji, faces = kanji_names(), rom.faces()
    d = os.path.join(args.out, "faces")
    os.makedirs(d, exist_ok=True)
    for i in range(len(kanji)):
        label = rom.general_name(i) + (f"_{kanji[i][0]}" if kanji[i][0] else "")
        png(rom.face_pixels(rom.face_of(i)), FACE_W, FACE_H, os.path.join(d, f"{i:03d}_{label}.png"), args.scale)
    d = os.path.join(args.out, "portraits")
    os.makedirs(d, exist_ok=True)
    for n, f in enumerate(faces):
        for e in range(EXPRESSIONS):
            png(rom.face_pixels(f, e), FACE_W, FACE_H, os.path.join(d, f"F{n:03d}_e{e}.png"), args.scale)
        png(rom.face_pixels(f, 0, talk=True), FACE_W, FACE_H, os.path.join(d, f"F{n:03d}_talk.png"), args.scale)
    png(rom.map_pixels(), 256, 160, os.path.join(args.out, "map.png"), args.scale)
    d = os.path.join(args.out, "battle_maps")
    os.makedirs(d, exist_ok=True)
    for i in range(PROVINCE_COUNT):
        png(rom.battle_pixels(i), 512, 320, os.path.join(d, f"{i:02d}_{rom.province(i)['name']}.png"), args.scale)

    print(f"已匯出 {len(sheets['武將'])} 筆武將、{len(sheets['州'])} 筆州、{len(sheets['道具'])} 筆道具 → {args.out}")
    print(f"頭像 {len(kanji)} 人（{len(faces)} 張臉 × {EXPRESSIONS} 表情＋說話）；大地圖 256×160；戰場 {PROVINCE_COUNT} 張 512×320")


if __name__ == "__main__":
    main()
