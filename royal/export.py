#!/usr/bin/env python3
"""匯出 FC ロイヤルブラッド 的人物、家、領地、傭兵、頭像與地圖。

Usage: .venv/bin/python royal/export.py [--rom ROM] [--out DIR] [--scale N]

Writes characters.csv (4 scenarios, present characters), houses.csv, provinces.csv, units.csv,
battle_maps.csv (+ royal.xlsx when openpyxl is installed), faces/ (64 characters), advisers/ (4),
unit_faces/ (23), map.png, battle_maps/ (30). The game has no composite faces, so there are no mob parts.
"""
import argparse
import csv
import os

from PIL import Image
from rom import (
    BATTLE_H,
    BATTLE_W,
    CHAR_COUNT,
    DEFAULT_ROM,
    FACE_TABLES,
    MAP_H,
    MAP_W,
    PROVINCE_COUNT,
    SCENARIO_NAMES,
    STATUS,
    TERRAIN,
    Rom,
    nes_rgb,
)

HERE = os.path.dirname(os.path.abspath(__file__))
FACE_DIRS = ["faces", "advisers", "unit_faces"]


def png(px: bytes, w: int, h: int, path: str, scale: int = 1) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata([nes_rgb(c) for c in px])
    if scale > 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    im.save(path)


def character_rows(rom: Rom) -> list[dict]:
    pnames = [rom.province_info(p)["name"] for p in range(PROVINCE_COUNT)]
    rows = []
    for s in range(len(SCENARIO_NAMES)):
        for c in rom.characters(s):
            rows.append({
                "劇本": s + 1, "編號": c["id"], "姓名": c["name"], "年齢": c["age"], "知力": c["int"], "武力": c["war"],
                "魅力": c["charm"], "所在領地": f"{c['province'] + 1}:{pnames[c['province']]}",
                "家": rom.house_name(c["house"]), "身分": STATUS.get(c["status"], str(c["status"])),
                "一族(推定)": "" if c["blood"] is None else rom.house_name(c["blood"]),
                "当主值(未知)": c["lord_value"], "姓名表+13(未知)": f"{c['name_unknown']:02X}", "頭像": f"C{c['id']:02d}",
            })
    return rows


def house_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in range(len(SCENARIO_NAMES)):
        provs = rom.provinces(s)
        for h in rom.houses(s):
            owned = [p["id"] + 1 for p in provs if p["owner"] == h["id"]]
            rows.append({"劇本": s + 1, "編號": h["id"], "家": h["name"], "当主": rom.char_name(h["lord"])["name"],
                         "領地數": len(owned), "領地": " ".join(map(str, owned)), "旗標位元(未知)": f"{h['bits']:02X}"})
    return rows


def province_rows(rom: Rom) -> list[dict]:
    units = rom.units()
    rows = []
    for s in range(len(SCENARIO_NAMES)):
        chars = rom.characters(s)
        for p in rom.provinces(s):
            members = [c["name"] for c in chars if c["province"] == p["id"]]
            rows.append({
                "劇本": s + 1, "編號": p["id"] + 1, "領地": p["name"],
                "支配家": rom.house_name(p["owner"]) if p["owner"] is not None else "",
                "金": p["gold"], "食料": p["food"], "兵": p["men"], "開発(山形圖示)": p["land"],
                "作物": p["crops"], "民忠(心形圖示)": p["loyalty"],
                "傭兵候補(推定；種類:兵力/末位元組)": " ".join(f"{units[u['type']]['name']}:{u['hp']}/{u['level']}" for u in p["units"]),
                "人物數": len(members), "人物": " ".join(members),
                "相鄰": " ".join(str(n + 1) for n in p["neighbours"]), "地圖標號格": f"{p['label'][0]},{p['label'][1]}",
            })
    return rows


def unit_rows(rom: Rom) -> list[dict]:
    return [{"編號": u["id"], "名稱": u["name"], "+1(攻擊?)": u["a"], "+2(防禦?)": u["b"], "+3(初期兵力)": u["hp"],
             "+5": u["c"], "+6": u["d"], "+7(類別位元)": f"{u['e']:02X}", "原值(+10..17)": u["raw"],
             "頭像": f"U{u['id']:02d}"} for u in rom.units()]


def battle_rows(rom: Rom) -> list[dict]:
    rows = []
    for p in range(PROVINCE_COUNT):
        g = rom.battle_grid(p)
        rows.append({"編號": p + 1, "領地": rom.province_info(p)["name"], "寬": BATTLE_W, "高": BATTLE_H,
                     "地形(高4位元，每列以/分隔)": "/".join("".join(f"{v >> 4:x}" for v in g[r * BATTLE_W:(r + 1) * BATTLE_W])
                                               for r in range(BATTLE_H)),
                     "地形種類": " ".join(sorted({TERRAIN.get(v >> 4, f"{v >> 4:X}") for v in g}))})
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


def face_file(rom: Rom, table: int, f: int) -> str:
    if table == 0:
        return f"C{f:02d}_{rom.char_name(f)['name']}.png"
    if table == 1:
        return f"A{f}.png"
    return f"U{f:02d}_{rom.units()[f]['name']}.png"


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 FC ロイヤルブラッド 人物／家／領地／傭兵／頭像／地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"人物": character_rows(rom), "家": house_rows(rom), "領地": province_rows(rom), "傭兵": unit_rows(rom),
              "戰場": battle_rows(rom)}
    for rows, name in zip(sheets.values(), ["characters", "houses", "provinces", "units", "battle_maps"]):
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "royal.xlsx"))
    except ImportError:
        print("openpyxl 未安裝，略過 .xlsx")

    for table, sub in enumerate(FACE_DIRS):
        d = os.path.join(args.out, sub)
        os.makedirs(d, exist_ok=True)
        for f in range(FACE_TABLES[table][2]):
            png(rom.face_pixels(table, f), 40, 48, os.path.join(d, face_file(rom, table, f)), args.scale)
    png(rom.map_pixels(), MAP_W * 8, MAP_H * 8, os.path.join(args.out, "map.png"), args.scale)
    d = os.path.join(args.out, "battle_maps")
    os.makedirs(d, exist_ok=True)
    for p in range(PROVINCE_COUNT):
        png(rom.battle_pixels(p), BATTLE_W * 16, BATTLE_H * 16,
            os.path.join(d, f"{p + 1:02d}_{rom.province_info(p)['name']}.png"), args.scale)

    print(f"已匯出 {len(sheets['人物'])} 筆人物（{CHAR_COUNT} 人 × 4 劇本中登場者）、{len(sheets['家'])} 筆家、"
          f"{len(sheets['領地'])} 筆領地、{len(sheets['傭兵'])} 種傭兵 → {args.out}")
    print(f"頭像 人物 {FACE_TABLES[0][2]}＋相談役 {FACE_TABLES[1][2]}＋傭兵 {FACE_TABLES[2][2]}；"
          f"大地圖 {MAP_W * 8}×{MAP_H * 8}；戰場 {PROVINCE_COUNT} 張 {BATTLE_W * 16}×{BATTLE_H * 16}")
    print("戰鬥兵種標籤:", " / ".join(rom.unit_labels()[:4]))


if __name__ == "__main__":
    main()
