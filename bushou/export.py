#!/usr/bin/env python3
"""匯出 FC 信長の野望・武将風雲録 的武將、國、大名、茶器、頭像與地圖。

Usage: .venv/bin/python bushou/export.py [--rom ROM] [--out DIR] [--scale N]

Writes generals.csv (both scenarios: start, renamed and later generals), provinces.csv,
daimyo.csv, tea.csv, battle_maps.csv (+ bushou.xlsx when openpyxl is installed), faces/
(one PNG per distinct character), portraits/ (F000-F211), map.png, battle_maps/{field,castle}/
(normal palette) and battle_maps/{field,castle}_winter/, battle_maps/metatiles.png.
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw
from rom import (
    BATTLE_H,
    BATTLE_PALETTE_LABELS,
    CASTLE_COUNT,
    CASTLE_W,
    DEFAULT_ROM,
    FIELD_COUNT,
    FIELD_TERRAIN,
    FIELD_W,
    MAP_H,
    MAP_W,
    METATILES,
    PORTRAIT_COUNT,
    SCENARIO_COUNT,
    Rom,
    decode_face_code,
    is_composite,
    nes_rgb,
)

HERE = os.path.dirname(os.path.abspath(__file__))


def png(px: bytes, w: int, h: int, path: str, scale: int = 1) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata([nes_rgb(c) for c in px])
    if scale > 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    im.save(path)


def face_label(code: int) -> str:
    if not is_composite(code):
        return f"F{code:03d}"
    head, pages = decode_face_code(code)
    return f"組合 頭{head} " + "".join(str(p) for p in pages)


def all_generals(rom: Rom) -> list[dict]:
    """Start, renamed and later generals of every scenario, with resolved names."""
    pnames = rom.province_names()
    out = []
    for s in range(SCENARIO_COUNT):
        info = rom.scenario_info(s)
        daimyo = {d["index"]: d["name"] for d in rom.daimyos(s)}
        for g in rom.generals(s):
            out.append({"scenario": s + 1, "kind": "開局", **g, "province_name": pnames[g["province"]],
                        "daimyo_name": daimyo.get(g["daimyo"], "")})
        for g in rom.renamed(s):
            out.append({"scenario": s + 1, "kind": "改名", **g, "age": info["year"] - g["birth"]})
        for g in rom.later_generals(s):
            out.append({"scenario": s + 1, "kind": "登場", **g,
                        "province_name": "" if g["province"] is None else pnames[g["province"]]})
    return out


def distinct_characters(rom: Rom) -> list[dict]:
    """Every (name, face code) once, in order of first appearance."""
    seen, out = set(), []
    for g in all_generals(rom):
        key = (g["name"], g["face_code"])
        if key not in seen:
            seen.add(key)
            out.append({"id": len(out), **g})
    return out


def general_rows(rom: Rom) -> list[dict]:
    rows = []
    for g in all_generals(rom):
        rows.append({
            "劇本": g["scenario"], "種別": g["kind"], "編號": g["index"], "姓名": g["name"], "姓": g["family"],
            "名": g["given"], "生年": g["birth"], "年齢": g.get("age", ""), "登場年": g.get("appear", ""),
            "政治": g.get("politics", ""), "戦闘": g.get("war", ""), "教養": g.get("culture", ""),
            "魅力": g["charm"], "野望": g["ambition"], "忠誠": g.get("loyalty", ""),
            "相性(推定)": g["name_b16"], "所在國": g.get("province_name", ""), "大名": g.get("daimyo_name", ""),
            "旗標": f"{g['flags']:02X}" if "flags" in g else "", "未知b8": g.get("b8", g.get("b7", "")),
            "頭像碼": f"{g['face_code']:04X}", "頭像": face_label(g["face_code"])})
    return rows


def province_rows(rom: Rom) -> list[dict]:
    names, rows = rom.province_names(), []
    for s in range(SCENARIO_COUNT):
        daimyo = {d["index"]: d["name"] for d in rom.daimyos(s)}
        gens = rom.generals(s)
        for p in rom.provinces(s):
            rows.append({
                "劇本": s + 1, "編號": p["index"], "國": p["name"],
                "大名": daimyo.get(p["owner"], "") if p["owner"] is not None else "",
                "金": p["gold"], "米": p["rice"], "石高": p["kokudaka"], "治水": p["flood"], "町": p["town"],
                "文化(推定)": p["culture"], "技術(推定)": p["tech"], "兵忠": p["soldier_loyalty"], "城": p["castle"],
                "兵": p["soldiers"], "鉄砲": p["guns"], "訓練": p["training"], "民忠": p["people_loyalty"],
                "武將數": len(p["generals"]), "武將": " ".join(gens[g]["name"] for g in p["generals"]),
                "相鄰": " ".join(names[n] for n, _ in rom.province_neighbours(p["index"])),
                "未知19-21": p["raw19_21"], "未知30-31": p["raw30_31"]})
    return rows


def daimyo_rows(rom: Rom) -> list[dict]:
    return [{"劇本": s + 1, "編號": d["index"], "大名": d["name"], "未知(偏移2-31)": d["raw"]}
            for s in range(SCENARIO_COUNT) for d in rom.daimyos(s)]


def tea_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in range(SCENARIO_COUNT):
        gens = rom.generals(s)
        for t in rom.tea(s):
            rows.append({"劇本": s + 1, "編號": t["index"], "茶器": t["name"], "值(未知)": t["value"],
                         "持有者": "" if t["owner"] is None else gens[t["owner"]]["name"]})
    return rows


def battle_rows(rom: Rom) -> list[dict]:
    pnames, (fnames, cnames) = rom.province_names(), rom.battle_names()
    rows = []
    for castle, count, w, names in ((False, FIELD_COUNT, FIELD_W, fnames), (True, CASTLE_COUNT, CASTLE_W, cnames)):
        for n in range(count):
            terrain = rom.battle_terrain(castle, n)
            row = {"種類": "城" if castle else "野戰", "編號": n, "國": pnames[24 if n == 48 else n],
                   "戰場名": names[n], "寬": w, "高": BATTLE_H,
                   "地形(每列以/分隔)": "/".join(terrain[r * w:(r + 1) * w].hex() for r in range(BATTLE_H))}
            if castle:
                layer = rom.castle_layer(n)
                row["第二層"] = "/".join(layer[r * w:(r + 1) * w].hex() for r in range(BATTLE_H))
            rows.append(row)
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


def metatile_sheet(rom: Rom, path: str, scale: int) -> None:
    """The 41 battle metatiles (bank 52) with their index and the terrain that uses them."""
    use = {m: f"野{t:X}" for t, m in {7: 0, 8: 1, 9: 2, 0xB: 3, 0xC: 5, 0xD: 6}.items()}
    use.update({4: "野B'", 7: "野D'"})
    use.update({m: f"城{t:X}" for t, m in {0: 12, 1: 31, 3: 33, 4: 34, 5: 35, 6: 36, 7: 37, 8: 38, 9: 39, 0xC: 40,
                                            0xD: 28}.items()})
    use[29] = "城D'"
    pal = rom.battle_palette(0)
    im = Image.new("RGB", (11 * 40, 4 * 40), (255, 255, 255))
    d = ImageDraw.Draw(im)
    for m in range(41):
        mt = rom.prg[METATILES + 8 * m:METATILES + 8 * m + 8]
        px = rom.render_cells(mt[:4], mt[4:], 2, pal)
        cell = Image.new("RGB", (16, 16))
        cell.putdata([nes_rgb(c) for c in px])
        x, y = (m % 11) * 40, (m // 11) * 40
        im.paste(cell, (x + 12, y + 2))
        d.text((x + 2, y + 20), f"{m} {use.get(m, '')}", fill=(0, 0, 0))
    im.resize((im.width * scale, im.height * scale), Image.NEAREST).save(path)


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 FC 武将風雲録 武將／國／大名／茶器／頭像／地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"武將": general_rows(rom), "國": province_rows(rom), "大名": daimyo_rows(rom), "茶器": tea_rows(rom),
              "戰場": battle_rows(rom)}
    for rows, name in zip(sheets.values(), ["generals", "provinces", "daimyo", "tea", "battle_maps"]):
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "bushou.xlsx"))
    except ImportError:
        print("openpyxl 未安裝，略過 .xlsx")

    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    chars = distinct_characters(rom)
    for c in chars:
        png(rom.face_pixels(c["face_code"]), 40, 48, os.path.join(faces, f"{c['id']:03d}_{c['name']}.png"), args.scale)
    portraits = os.path.join(args.out, "portraits")
    os.makedirs(portraits, exist_ok=True)
    for f in range(PORTRAIT_COUNT):
        png(rom.face_pixels(f), 40, 48, os.path.join(portraits, f"F{f:03d}.png"), args.scale)
    png(rom.map_pixels(), MAP_W * 8, MAP_H * 8, os.path.join(args.out, "map.png"), args.scale)

    pnames, (fnames, cnames) = rom.province_names(), rom.battle_names()
    bdir = os.path.join(args.out, "battle_maps")
    for castle, count, names, kind in ((False, FIELD_COUNT, fnames, "field"), (True, CASTLE_COUNT, cnames, "castle")):
        for season, suffix in ((0, ""), (1, "_winter")):
            d = os.path.join(bdir, kind + suffix)
            os.makedirs(d, exist_ok=True)
            for n in range(count):
                png(rom.battle_pixels(castle, n, season), 256, 240,
                    os.path.join(d, f"{n:02d}_{pnames[24 if n == 48 else n]}_{names[n]}.png"), args.scale)
    metatile_sheet(rom, os.path.join(bdir, "metatiles.png"), max(args.scale, 2))

    n_gen = sum(1 for r in sheets["武將"])
    print(f"已匯出 {n_gen} 筆武將、{len(sheets['國'])} 筆國、{len(sheets['大名'])} 筆大名、{len(sheets['茶器'])} 筆茶器 → {args.out}")
    print(f"頭像 {len(chars)} 人＋專屬 {PORTRAIT_COUNT} 張；戰場 野戰 {FIELD_COUNT}＋城 {CASTLE_COUNT} 張"
          f"（調色盤：{BATTLE_PALETTE_LABELS[0]}、{BATTLE_PALETTE_LABELS[1]}）；地形 {len(FIELD_TERRAIN)} 種")


if __name__ == "__main__":
    main()
