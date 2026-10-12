#!/usr/bin/env python3
"""匯出 FC 大航海時代 的人物、港口、名稱表、頭像、世界地圖與港町圖。

Usage: .venv/bin/python daikoukai/export.py [--rom ROM] [--out DIR] [--scale N]

Writes persons.csv (player, 20 mates with abilities, 20 admirals), girls.csv, ports.csv,
names.csv (goods, cannons, figureheads, ships, woods, masts, sails) (+ daikoukai.xlsx when
openpyxl is installed), faces/ (persons and girls), portraits/ (F00-F47), mob_parts/,
map.png (full size, 16128 x 8064), map_small.png (1/4, ports marked), towns/ (8 town types
and every port).
"""
import argparse
import csv
import importlib.util
import os

from PIL import Image, ImageDraw
from rom import (
    CHUNK_TILES,
    DEFAULT_ROM,
    FACE_H,
    FACE_W,
    MAP_BLOCKS,
    MAP_H,
    MAP_W,
    NAME_LISTS,
    NES_PALETTE,
    PORTRAIT_COUNT,
    TOWN_H,
    TOWN_IMAGES,
    TOWN_TYPES,
    TOWN_W,
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
NES_P = [v for c in NES_PALETTE for v in (c >> 16, c >> 8 & 0xFF, c & 0xFF)]


def png(px: bytes, w: int, h: int, path: str, scale: int = 1) -> None:
    im = Image.new("RGB", (w, h))
    im.putdata([nes_rgb(c) for c in px])
    if scale > 1:
        im = im.resize((w * scale, h * scale), Image.NEAREST)
    im.save(path)


def face_label(code: int) -> str:
    if not is_composite(code):
        return f"F{code:02d}"
    head, pages = decode_face_code(code)
    return f"組合 頭{head} " + "".join(str(p) for p in pages)


def characters(rom: Rom) -> list[dict]:
    """Everyone with a face: 41 persons (id 0-40), then 20 girls (id 41-60)."""
    out = [{"id": p["id"], "name": p["name"], "role": p["role"], "face_code": p["face"]} for p in rom.persons()]
    out += [{"id": 41 + g["id"], "name": g["name"], "role": "女性", "face_code": g["face"]} for g in rom.girls()]
    return out


def person_rows(rom: Rom) -> list[dict]:
    rows = []
    for p in rom.persons():
        r = {"ID": p["id"], "姓名": p["name"], "身分": p["role"], "國": p["nation"], "戰鬥等級": p["battle"],
             "航海等級": p["sailing"]}
        if "age" in p:
            r.update({"年齡(推定)": p["age"], "統率": p["leadership"], "判断": p["judgment"],
                      "知力": p["intelligence"], "勇気": p["courage"], "強さ": p["strength"]})
        r.update({"頭像": face_label(p["face"]), "頭像碼": f"{p['face']:04X}", "旗標": f"{p['flags']:02X}"})
        rows.append(r)
    return rows


def girl_rows(rom: Rom) -> list[dict]:
    return [{"ID": g["id"], "姓名": g["name"], "頭像": face_label(g["face"])} for g in rom.girls()]


def port_rows(rom: Rom) -> list[dict]:
    rows = []
    for p in rom.ports():
        r = {"ID": p["id"], "港名": p["name"], "種類": "補給港" if p["supply"] else "交易港",
             "chunk_x": p["chunk_x"], "chunk_y": p["chunk_y"], "metatile_x": p["mt_x"], "metatile_y": p["mt_y"],
             "像素_x": p["chunk_x"] * CHUNK_TILES * 8 + p["mt_x"] * 16,
             "像素_y": p["chunk_y"] * CHUNK_TILES * 8 + p["mt_y"] * 16}
        if not p["supply"]:
            r.update({"經濟圈": p["region"], "特產品": p["specialty"], "道具(推定)": p["item"],
                      "byte2": p["byte2"], "byte4": p["byte4"]})
        r.update({"港町圖類型": p["town"], "建物旗標": f"{rom.town_flags(p['id']):02X}"})
        rows.append(r)
    return rows


def name_rows(rom: Rom) -> list[dict]:
    return [{"表": key, "編號": i, "名稱": n} for key in NAME_LISTS for i, n in enumerate(rom.name_list(key))]


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


def world_map(rom: Rom) -> Image.Image:
    """Whole world as a palette image (pixel = NES colour number), pasted metatile by metatile."""
    size = CHUNK_TILES * 8
    im = Image.new("P", (MAP_W * size, MAP_H * size))
    im.putpalette(NES_P)
    cache = {}
    for cy in range(MAP_H):
        s, pal = rom.map_set(cy), rom.map_palette(cy)
        for cx in range(MAP_W):
            for b, block in enumerate(rom.chunk_blocks(cx, cy)):
                for q in range(4):
                    m = rom.prg[MAP_BLOCKS + 4 * block + q]
                    if (s, m) not in cache:
                        cache[s, m] = Image.frombytes("P", (16, 16), rom.metatile_pixels(s, m, pal))
                    im.paste(cache[s, m], (cx * size + b % 7 * 32 + q % 2 * 16, cy * size + b // 7 * 32 + q // 2 * 16))
    return im


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 FC 大航海時代 人物／港口／頭像／地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="頭像與港町圖 PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    sheets = {"人物": person_rows(rom), "女性": girl_rows(rom), "港口": port_rows(rom), "名稱": name_rows(rom)}
    for rows, name in zip(sheets.values(), ["persons", "girls", "ports", "names"]):
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    try:
        write_xlsx(sheets, os.path.join(args.out, "daikoukai.xlsx"))
    except ImportError:
        print("openpyxl 未安裝，略過 .xlsx")

    faces = os.path.join(args.out, "faces")
    os.makedirs(faces, exist_ok=True)
    chars = characters(rom)
    for c in chars:
        png(rom.face_pixels(c["face_code"]), FACE_W * 8, FACE_H * 8,
            os.path.join(faces, f"{c['id']:02d}_{c['name']}.png"), args.scale)
    portraits = os.path.join(args.out, "portraits")
    os.makedirs(portraits, exist_ok=True)
    for f in range(PORTRAIT_COUNT):
        png(rom.face_pixels(f), FACE_W * 8, FACE_H * 8, os.path.join(portraits, f"F{f:02d}.png"), args.scale)

    towns = os.path.join(args.out, "towns")
    os.makedirs(towns, exist_ok=True)
    for t in range(TOWN_TYPES):     # the bare picture of each type, without pieces
        b, o = rom.town_bank(t), TOWN_IMAGES + 4 * t
        tp, ep = b + rom.u16(o) - 0xA000, b + rom.u16(o + 2) - 0xA000
        png(rom.bg_pixels(rom.prg[tp:tp + TOWN_W * TOWN_H], rom.prg[ep:ep + TOWN_W * TOWN_H], TOWN_W, TOWN_H,
                          rom.town_palette(t)), TOWN_W * 8, TOWN_H * 8, os.path.join(towns, f"type{t}.png"), args.scale)
    ports = rom.ports()
    for p in ports:
        png(rom.town_pixels(p["id"]), TOWN_W * 8, TOWN_H * 8, os.path.join(towns, f"{p['id']:02d}_{p['name']}.png"),
            args.scale)

    im = world_map(rom)
    im.save(os.path.join(args.out, "map.png"))
    small = im.convert("RGB").reduce(4)
    d = ImageDraw.Draw(small)
    for r in sheets["港口"]:
        x, y = (r["像素_x"] + 8) // 4, (r["像素_y"] + 8) // 4
        d.rectangle((x - 3, y - 3, x + 3, y + 3), fill=(255, 0, 0) if r["種類"] == "交易港" else (255, 255, 0),
                    outline=(0, 0, 0))
        d.text((x + 5, y - 6), str(r["ID"]), fill=(255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0))
    small.save(os.path.join(args.out, "map_small.png"))

    print(f"已匯出人物 {len(sheets['人物'])} 筆、女性 {len(sheets['女性'])} 筆、港口 {len(ports)} 筆、"
          f"名稱 {len(sheets['名稱'])} 筆 → {args.out}")
    print(f"頭像 {len(chars)} 人＋專屬 {PORTRAIT_COUNT} 張；港町圖 {TOWN_TYPES} 類型＋{len(ports)} 港；"
          f"世界地圖 {im.width}×{im.height}（map_small.png 1/4，紅＝交易港、黃＝補給港）")

    import export_kaodata  # imports this module, so load it only after it has fully initialised

    meta, blobs = export_kaodata.build(args.rom)
    parts_sheet.export_mob_parts(meta, blobs, args.out)


if __name__ == "__main__":
    main()
