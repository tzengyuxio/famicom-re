#!/usr/bin/env python3
"""匯出 FC 信長の野望・戦国群雄伝 的武將、國、大名、頭像與地圖。

Usage: .venv/bin/python gunyuu/export.py [--rom ROM] [--out DIR] [--scale N]

Writes generals.csv (both scenarios, 255 slots each incl. later-appearing generals), provinces.csv,
daimyo.csv, battle_maps.csv (+ gunyuu.xlsx when openpyxl is installed), faces/ (one PNG per distinct
character), portraits/ (F000-F089), map.png, battle_maps/{field,castle}/, mob_parts.png and mob_parts/.
"""
import argparse
import csv
import importlib.util
import os

import export_kaodata
from PIL import Image
from rom import (
    BATTLE_H,
    BATTLE_W,
    DEFAULT_ROM,
    MAP_H,
    MAP_W,
    PORTRAIT_COUNT,
    PROVINCE_COUNT,
    SCENARIO_COUNT,
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

UNIT = {0: "足軽", 1: "騎馬", 2: "鉄砲", 3: "?"}
UNUSED_PORTRAITS = range(60, 65)  # the game's formula reads other data for these ids


def png(px: bytes, w: int, h: int, path: str, scale: int = 1) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata([nes_rgb(c) for c in px])
    if scale > 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    im.save(path)


def face_label(code: int) -> str:
    if not is_composite(code):
        return f"F{code:03d}" if code < PORTRAIT_COUNT else "（無）"
    group, v = decode_face_code(code)
    return f"組合 {group}-" + "".join(str(x) for x in v)


def all_generals(rom: Rom) -> list[dict]:
    pnames = rom.province_names()
    out = []
    for s in range(SCENARIO_COUNT):
        info = rom.scenario_info(s)
        daimyo = {d["index"]: d["name"] for d in rom.daimyos(s)}
        for g in rom.generals(s):
            out.append({"scenario": s + 1, "kind": "開局" if g["appear"] <= info["year"] else "登場", **g,
                        "province_name": pnames[g["province"]] if g["province"] < PROVINCE_COUNT else "",
                        "daimyo_name": daimyo.get(g["daimyo"], "")})
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
    return [{
        "劇本": g["scenario"], "種別": g["kind"], "編號": g["index"], "姓名": g["name"], "姓": g["family"],
        "名": g["given"], "生年": g["birth"], "年齢": g["age"], "登場年": g["appear"], "卒年(推定)": g["death"],
        "政治": g["politics"], "戦闘": g["war"], "魅力": g["charm"], "野望": g["ambition"], "忠誠": g["loyalty"],
        "兵士": g["soldiers"], "訓練": g["training"], "武装": g["arms"], "部隊": UNIT[g["unit"]],
        "所在國": g["province_name"], "大名": g["daimyo_name"], "旗標": f"{g['flags']:02X}",
        "未知(姓名17-19)": g["name_raw17_19"], "頭像碼": f"{g['face_code']:04X}", "頭像": face_label(g["face_code"]),
    } for g in all_generals(rom)]


def province_rows(rom: Rom) -> list[dict]:
    names, rows = rom.province_names(), []
    for s in range(SCENARIO_COUNT):
        daimyo = {d["index"]: d["name"] for d in rom.daimyos(s)}
        info = rom.scenario_info(s)
        gens = [g for g in rom.generals(s) if g["appear"] <= info["year"]]
        for p in rom.provinces(s):
            members = [g["name"] for g in gens if g["province"] == p["index"]]
            rows.append({
                "劇本": s + 1, "編號": p["index"] + 1, "國": p["name"],
                "大名": daimyo.get(p["owner"], "") if p["owner"] is not None else "",
                "城主": rom.name_record(s, p["lord"])["name"] if p["lord"] is not None else "",
                "金": p["gold"], "米": p["rice"], "石高": p["kokudaka"], "治水": p["flood"], "町": p["town"],
                "未知13-14(扇)": p["b13"], "兵": p["soldiers"], "民忠": p["people_loyalty"], "城": p["castle"],
                "武將數": len(members), "武將": " ".join(members),
                "相鄰": " ".join(f"{names[n]}({f:02X})" for n, f in rom.province_neighbours(p["index"]))})
    return rows


def daimyo_rows(rom: Rom) -> list[dict]:
    rows = []
    for s in range(SCENARIO_COUNT):
        ds = rom.daimyos(s)
        names = {d["index"]: d["name"] for d in ds}
        for d in ds:
            rel = d["relations"]
            rows.append({"劇本": s + 1, "編號": d["index"], "大名": d["name"],
                         "同盟": " ".join(names.get(a, str(a)) for a in d["allies"]),
                         "友好度": " ".join(f"{names[k]}:{rel[k]}" for k in names if k > d["index"]),
                         "關係旗標(推定)": " ".join(f"{names[k]}:{rel[k]:02X}" for k in names
                                                if k < d["index"] and rel[k]),
                         "原值(偏移5-42)": bytes(rel).hex(" ")})
    return rows


def battle_rows(rom: Rom) -> list[dict]:
    names, rows = rom.province_names(), []
    for castle in (False, True):
        for n in range(PROVINCE_COUNT):
            t = rom.battle_terrain(castle, n)
            rows.append({"種類": "城" if castle else "野戰", "編號": n + 1, "國": names[n], "寬": BATTLE_W,
                         "高": BATTLE_H,
                         "地形(每列以/分隔)": "/".join(t[r * BATTLE_W:(r + 1) * BATTLE_W].hex()
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
    ap = argparse.ArgumentParser(description="匯出 FC 戦国群雄伝 武將／國／大名／頭像／地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"武將": general_rows(rom), "國": province_rows(rom), "大名": daimyo_rows(rom), "戰場": battle_rows(rom)}
    for rows, name in zip(sheets.values(), ["generals", "provinces", "daimyo", "battle_maps"]):
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "gunyuu.xlsx"))
    except ImportError:
        print("openpyxl 未安裝，略過 .xlsx")

    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    chars = [c for c in distinct_characters(rom) if is_composite(c["face_code"]) or c["face_code"] < PORTRAIT_COUNT]
    for c in chars:
        png(rom.face_pixels(c["face_code"]), 40, 48, os.path.join(faces, f"{c['id']:03d}_{c['name']}.png"), args.scale)
    portraits = os.path.join(args.out, "portraits")
    os.makedirs(portraits, exist_ok=True)
    for f in range(PORTRAIT_COUNT):
        if f not in UNUSED_PORTRAITS:
            png(rom.face_pixels(f), 40, 48, os.path.join(portraits, f"F{f:03d}.png"), args.scale)
    png(rom.map_pixels(), MAP_W * 8, MAP_H * 8, os.path.join(args.out, "map.png"), args.scale)

    names = rom.province_names()
    for castle, kind in ((False, "field"), (True, "castle")):
        d = os.path.join(args.out, "battle_maps", kind)
        os.makedirs(d, exist_ok=True)
        for n in range(PROVINCE_COUNT):
            png(rom.battle_pixels(castle, n), 256, 240, os.path.join(d, f"{n + 1:02d}_{names[n]}.png"), args.scale)

    print(f"已匯出 {len(sheets['武將'])} 筆武將、{len(sheets['國'])} 筆國、{len(sheets['大名'])} 筆大名 → {args.out}")
    print(f"頭像 {len(chars)} 人＋專屬 {PORTRAIT_COUNT - len(UNUSED_PORTRAITS)} 張；戰場 野戰 {PROVINCE_COUNT}＋城 "
          f"{PROVINCE_COUNT} 張；大地圖 {MAP_W * 8}×{MAP_H * 8}")

    meta, blobs = export_kaodata.build(args.rom)
    parts_sheet.export_mob_parts(meta, blobs, args.out)


if __name__ == "__main__":
    main()
