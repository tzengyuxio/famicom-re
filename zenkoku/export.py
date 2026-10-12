#!/usr/bin/env python3
"""匯出 FC 信長の野望・全国版 的大名、國、頭像與地圖。

Usage: .venv/bin/python zenkoku/export.py [--rom ROM] [--out DIR] [--scale N]

Writes daimyo.csv, provinces.csv, battle_maps.csv (+ zenkoku.xlsx when openpyxl is installed),
portraits/, maps/map{50,17}_N.png (+ _labeled), battle_maps/NN_name.png and battle_maps/terrain.png.
No composite faces in this game, so there is no mob parts sheet.
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw
from rom import (
    BATTLE_COUNT,
    BATTLE_FIRST_TILE,
    BATTLE_H,
    BATTLE_PALETTE,
    BATTLE_TILES,
    BATTLE_W,
    DAIMYO_FACES,
    DEFAULT_ROM,
    MAP_VIEWS,
    MAP_X,
    MAP_Y,
    MODES,
    PORTRAIT_COUNT,
    PROVINCE_FIELDS,
    START_YEAR,
    STATS,
    TERRAIN,
    Rom,
    nes_rgb,
    to_hiragana,
)

HERE = os.path.dirname(os.path.abspath(__file__))


def face_label(n: int) -> str:
    return f"P{n:02d}"


def daimyo_rows(rom: Rom) -> list[dict]:
    rows = []
    for mode in MODES:
        s = rom.scenario(mode)
        names = [p["name"] for p in s["provinces"]]
        for d in s["daimyo"]:
            owned = [p for p in s["provinces"] if p["owner"] == d["id"]]
            rows.append({"Mode": s["label"], "Id": d["id"], "Name": d["name"], "Reading": to_hiragana(d["name"]),
                         "Age": d["age"], "Born": START_YEAR - d["age"],
                         **{f"{key}[{label}]": v for (key, label), v in zip(STATS, d["stats"])},
                         "Face": face_label(d["face"]), "Province": " ".join(names[p["id"]] for p in owned),
                         "Province_No": " ".join(str(p["id"] + 1) for p in owned)})
    return rows


def province_rows(rom: Rom) -> list[dict]:
    rows = []
    for mode in MODES:
        s = rom.scenario(mode)
        names = [p["name"] for p in s["provinces"]]
        views = [{p for p, _, _ in rom.map_labels(mode, v)} for v in range(MAP_VIEWS[mode][3])]
        for p in s["provinces"]:
            rows.append({"Mode": s["label"], "Id": p["id"], "No": p["id"] + 1, "Name": p["name"],
                         "Region": p["region"], "Daimyo": s["daimyo"][p["owner"]]["name"],
                         **{key + (f"[{label}]" if label else ""): p[key] for key, label in PROVINCE_FIELDS},
                         "Neighbors": " ".join(names[n] for n in p["neighbours"]),
                         "Neighbor_Nos": " ".join(str(n + 1) for n in p["neighbours"]),
                         "Map_Views": " ".join(str(v) for v, ids in enumerate(views) if p["id"] in ids),
                         "Battle_Map": p["battle_map"]})
    return rows


def battle_names(rom: Rom) -> list[str]:
    return [p["name"] for p in rom.scenario(50)["provinces"]]


def battle_rows(rom: Rom) -> list[dict]:
    rows = []
    for idx, name in enumerate(battle_names(rom)):
        for i, v in enumerate(rom.battle_cells(idx)):
            rows.append({"Map": idx, "Name": name, "X": i % BATTLE_W, "Y": i // BATTLE_W, "Terrain": f"{v:02X}",
                         "Terrain_Name": TERRAIN[v][1]})
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
    """Every terrain block (32x32) in the battle palette."""
    pal = rom.prg[BATTLE_PALETTE:BATTLE_PALETTE + 16]
    sheet = Image.new("RGB", (len(TERRAIN) * 40, 46), (255, 255, 255))
    draw = ImageDraw.Draw(sheet)

    def off(t: int):
        return BATTLE_TILES + (t - BATTLE_FIRST_TILE) * 16 if t >= BATTLE_FIRST_TILE else None

    for i, (v, (tag, _, sub)) in enumerate(TERRAIN.items()):
        px = rom.render(rom.battle_block(v), 4, [sub] * 16, off, pal)
        sheet.paste(to_image(px, 32, 32, 1), (i * 40 + 4, 12))
        draw.text((i * 40 + 2, 0), f"{v:02X} {tag}"[:7], fill=(0, 0, 0))
    return sheet.resize((sheet.width * scale, sheet.height * scale), Image.NEAREST)


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 FC 信長の野望・全国版 大名／國／頭像／地圖")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    daimyo, provs, battles = daimyo_rows(rom), province_rows(rom), battle_rows(rom)
    for name, rows in [("daimyo", daimyo), ("provinces", provs), ("battle_maps", battles)]:
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    try:
        write_xlsx({"大名": daimyo, "國": provs, "戰場": battles}, os.path.join(args.out, "zenkoku.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    portraits = os.path.join(args.out, "portraits")
    os.makedirs(portraits, exist_ok=True)
    names = [d["name"] for d in rom.scenario(50)["daimyo"]]
    for n in range(PORTRAIT_COUNT):
        label = names[n] if n < DAIMYO_FACES else "ひめ"
        to_image(rom.face_pixels(n), 48, 48, args.scale).save(os.path.join(portraits, f"P{n:02d}_{label}.png"))
    print(f"已匯出 {PORTRAIT_COUNT} 張頭像（大名 {DAIMYO_FACES}、姫 {PORTRAIT_COUNT - DAIMYO_FACES}）→ {portraits}")

    maps = os.path.join(args.out, "maps")
    os.makedirs(maps, exist_ok=True)
    for mode in MODES:
        for v in range(MAP_VIEWS[mode][3]):
            w, h, px = rom.map_pixels(mode, v)
            img = to_image(px, w, h, 1)
            img.resize((w * args.scale, h * args.scale), Image.NEAREST).save(
                os.path.join(maps, f"map{mode}_{v}.png"))
            big = img.resize((w * 3, h * 3), Image.NEAREST)
            draw = ImageDraw.Draw(big)
            for p, x, y in rom.map_labels(mode, v):
                x, y = (x - MAP_X) * 24, (y - MAP_Y) * 24
                draw.rectangle([x - 24, y, x + 23, y + 23], fill=(0, 0, 0))
                draw.text((x - 20, y + 5), f"{p + 1}", fill=(255, 255, 255))
            big.save(os.path.join(maps, f"map{mode}_{v}_labeled.png"))
    print(f"已匯出地方地圖 50 國版 {MAP_VIEWS[50][3]} 張、17 國版 {MAP_VIEWS[17][3]} 張 → {maps}（_labeled 標上國號）")

    battle = os.path.join(args.out, "battle_maps")
    os.makedirs(battle, exist_ok=True)
    for idx, name in enumerate(battle_names(rom)):
        w, h, px = rom.battle_pixels(idx)
        to_image(px, w, h, args.scale).save(os.path.join(battle, f"{idx + 1:02d}_{name}.png"))
    terrain_sheet(rom, max(args.scale, 2)).save(os.path.join(battle, "terrain.png"))
    print(f"已匯出 {BATTLE_COUNT} 張戰場地圖（{BATTLE_W}×{BATTLE_H} 格）→ {battle}")


if __name__ == "__main__":
    main()
