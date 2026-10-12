#!/usr/bin/env python3
"""匯出 FC 三國志 中原の覇者 的武將、州、道路、頭像與地圖。

Usage: .venv/bin/python chuugen/export.py [--rom ROM] [--out DIR] [--scale N]

Writes generals.csv, provinces.csv, roads.csv, battle_maps.csv (+ chuugen.xlsx when openpyxl is
installed), faces/ (one PNG per general), portraits/ (F000-F119 + the 4 expressions x 2 mouth frames
of each face in portraits/expressions/), map.png, roads.png and battle_maps/. The faces are shared
whole faces, not composite ones, so there is no mob_parts output.
"""
import argparse
import csv
import os

from PIL import Image
from rom import (
    ARMY_TYPES,
    BATTLE_H,
    BATTLE_TERRAIN,
    BATTLE_W,
    DEFAULT_ROM,
    EXPRESSIONS,
    FACE_H,
    FACE_W,
    LORDS,
    MAP_ROWS,
    START_MONTH,
    START_YEAR,
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
            i, _, kanji, src = line.rstrip("\n").split("\t")
            if kanji:
                out[int(i)] = (kanji, src)
    return out


def face_ids(rom: Rom) -> dict[tuple[int, int], int]:
    return {f: n for n, f in enumerate(rom.faces())}


def general_rows(rom: Rom) -> list[dict]:
    pnames, kanji, faces = rom.province_names(), kanji_names(), face_ids(rom)
    rows = []
    for g in rom.generals():
        k, src = kanji.get(g["index"], ("", ""))
        prov = g.get("province")
        rows.append({
            "編號": g["index"], "姓名": g["name"], "[EXT]漢字": k, "[EXT]漢字來源": src,
            "君主": LORDS[g["index"]] if g["index"] < len(LORDS) else "",
            "所在州": pnames[prov] if prov is not None else "", "体": g["body"], "知": g["intellect"],
            "武": g["war"], "徳": g["virtue"], "忠": "--" if g["loyalty"] is None else g["loyalty"],
            "軍種": ARMY_TYPES.get(g["army"], str(g["army"])), "兵1": g["troops"][0], "兵2": g["troops"][1],
            "兵3": g["troops"][2], "頭像": f"F{faces[g['face']]:03d}", "CHR bank": g["face"][0],
            "區塊": g["face"][1], "旗標(byte0)": f"{g['flags']:02X}", "未知(byte6低4bit)": g["b6_low"],
            "原值": g["raw"].hex(" "),
        })
    return rows


def province_rows(rom: Rom) -> list[dict]:
    names, kanji = rom.province_names(), kanji_names()
    rows = []
    for p, (x, y) in zip(rom.provinces(), rom.castles()):
        gens = [kanji.get(g, (rom.general_name(g),))[0] for g in p["generals"]]
        rows.append({
            "編號": p["index"], "州": p["name"], "君主": LORDS[p["owner"]],
            "地域旗標(推定)": f"{p['owner_flags']:02X}", "キン": p["gold"], "トチ": p["land"],
            "サンギョウ": p["industry"], "ジンコウ": p["population"], "トウチド": p["rule"],
            "ブショウ數": len(p["generals"]), "武將": " ".join(gens),
            "相鄰(道路編號)": " ".join(f"{names[n]}({r:02X})" for n, r in rom.neighbours(p["index"])),
            "城 x": x, "城 y": y, "原值": p["raw"].hex(" "),
        })
    return rows


def road_rows(rom: Rom) -> list[dict]:
    """One row per road id; both directions as the ROM lists them."""
    names, roads = rom.province_names(), {}
    for i in range(len(names)):
        for n, r in rom.neighbours(i):
            roads.setdefault(r, []).append((i, n))
    return [{"道路編號": f"{r:02X}", "方向": " ".join(f"{names[a]}→{names[b]}" for a, b in sorted(roads[r]))}
            for r in sorted(roads)]


def battle_rows(rom: Rom) -> list[dict]:
    names, rows = rom.province_names(), []
    for i in range(len(names)):
        _, cells = rom.battle_record(i)
        rows.append({
            "編號": i, "州": names[i], "寬": BATTLE_W, "高": BATTLE_H,
            "城格(x,y)": " ".join(f"({k % BATTLE_W},{k // BATTLE_W})" for k, c in enumerate(cells) if c == 0),
            "守方初始格(推定)": " ".join(f"({x},{y})" for x, y in rom.deploy_cells(0, i)),
            "攻方初始格(推定)": " ".join(f"({x},{y})" for x, y in rom.deploy_cells(1, i)),
            "地形(每列以/分隔)": "/".join(cells[r * BATTLE_W:(r + 1) * BATTLE_W].hex() for r in range(BATTLE_H)),
        })
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
    ap = argparse.ArgumentParser(description="匯出 FC 三國志 中原の覇者 武將／州／頭像／地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"武將": general_rows(rom), "州": province_rows(rom), "道路": road_rows(rom), "戰場": battle_rows(rom)}
    for rows, name in zip(sheets.values(), ["generals", "provinces", "roads", "battle_maps"]):
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "chuugen.xlsx"))
    except ImportError:
        print("openpyxl 未安裝，略過 .xlsx")

    faces, kanji = rom.faces(), kanji_names()
    d = os.path.join(args.out, "faces")
    os.makedirs(d, exist_ok=True)
    for g in range(len(sheets["武將"])):
        label = kanji.get(g, (rom.general_name(g),))[0].replace("|", "_")
        png(rom.face_pixels(rom.face_of(g)), FACE_W, FACE_H, os.path.join(d, f"{g:03d}_{label}.png"), args.scale)
    d = os.path.join(args.out, "portraits")
    os.makedirs(os.path.join(d, "expressions"), exist_ok=True)
    for n, f in enumerate(faces):
        png(rom.face_pixels(f), FACE_W, FACE_H, os.path.join(d, f"F{n:03d}.png"), args.scale)
        for e in range(EXPRESSIONS):
            for m in range(2):
                png(rom.face_pixels(f, e, m), FACE_W, FACE_H,
                    os.path.join(d, "expressions", f"F{n:03d}_e{e}m{m}.png"), args.scale)

    png(rom.map_pixels(), 256, MAP_ROWS * 8, os.path.join(args.out, "map.png"), args.scale)
    png(rom.map_pixels(roads=True), 256, MAP_ROWS * 8, os.path.join(args.out, "roads.png"), args.scale)
    d = os.path.join(args.out, "battle_maps")
    os.makedirs(d, exist_ok=True)
    for i, name in enumerate(rom.province_names()):
        png(rom.battle_pixels(i), 256, BATTLE_H * 16, os.path.join(d, f"{i:02d}_{name}.png"), args.scale)

    print(f"已匯出 {len(sheets['武將'])} 筆武將、{len(sheets['州'])} 筆州、{len(sheets['道路'])} 條道路"
          f"（{START_YEAR}年{START_MONTH}月開局）→ {args.out}")
    print(f"頭像 {len(faces)} 張（×{EXPRESSIONS} 表情×2 嘴形）；戰場 {len(sheets['戰場'])} 張；"
          f"地形代碼 {BATTLE_TERRAIN}")


if __name__ == "__main__":
    main()
