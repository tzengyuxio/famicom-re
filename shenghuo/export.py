#!/usr/bin/env python3
"""匯出 FC 聖火列傳 的人物、武功、道具、敵人、遇敵表、頭像、字型對照與地圖。

Usage: .venv/bin/python shenghuo/export.py [--rom ROM] [--out DIR]

Writes characters.csv, chapter_stats.csv, skills.csv, items.csv, enemies.csv, encounters.csv,
portraits.csv, entrances.csv, maps.csv, font00.csv / font09.csv (+ shenghuo.xlsx), portraits/
(dialog/ 36 + status/ 13 PNGs and two sheets), text/ (glyph sheets of string groups 0 and 9) and
maps/ (world.png, world_labelled.png, map01-23.png).
"""
import argparse
import csv
import os

from PIL import Image, ImageDraw, ImageFont
from rom import (
    CHAPTER_FIELDS,
    CHAR_COUNT,
    CHAR_NAME_BASE,
    DEFAULT_ROM,
    ENEMY_CHR,
    ENEMY_COUNT,
    ENEMY_FIELDS,
    ENEMY_GROUP,
    HERO,
    ITEM_BATTLE_PARAM,
    ITEM_COUNT,
    MAP_COUNT,
    NAME_CHR,
    NAME_GROUP,
    PORTRAIT_COUNT,
    SKILL_FIRST,
    SKILL_LAST,
    TERRAIN_CLASSES,
    Rom,
    nes_rgb,
)
from text import FONTS, charmap, decode

HERE = os.path.dirname(os.path.abspath(__file__))
WEAPONS = range(1, 20)  # group 0 entries 1-19 can be equipped (WEA); 20-28 are consumables


def image(w: int, h: int, px: list[int]) -> Image.Image:
    im = Image.new("RGB", (w, h))
    im.putdata([nes_rgb(c) for c in px])
    return im


def write_csv(path: str, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def glyph_sheet(rom: Rom, chr_bank: int, path: str) -> None:
    """Every entry of the string group using this font, as glyph images, 2x."""
    group, _ = FONTS[chr_bank]
    strings = rom.strings(group)
    width = max(len(s) for s in strings)
    im = Image.new("L", (40 + width * 17, len(strings) * 18), 0)
    d = ImageDraw.Draw(im)
    for i, s in enumerate(strings):
        d.text((2, i * 18 + 3), str(i), fill=160)
        for j, c in enumerate(s):
            g = rom.glyph(chr_bank, c)
            for y in range(16):
                for x in range(16):
                    if g[y][x]:
                        im.putpixel((40 + j * 17 + x, i * 18 + 1 + y), 255)
    im.resize((im.width * 2, im.height * 2), Image.NEAREST).save(path)


def labelled_world(rom: Rom, world: Image.Image, path: str) -> list[list]:
    """World map at 2x with every class-3 (M = map number) and class-4 (T = town number) cell marked."""
    im = world.resize((world.width * 2, world.height * 2), Image.NEAREST)
    d = ImageDraw.Draw(im)
    font = ImageFont.load_default(size=22)
    rows = []
    for e in rom.entrances():
        x, y = e["x"] * 32, e["y"] * 32
        label = ("M" if e["kind"] == "map" else "T") + str(e["target"])
        colour = (255, 60, 60) if e["kind"] == "map" else (255, 230, 0)
        d.rectangle([x - 2, y - 2, x + 33, y + 33], outline=colour, width=4)
        box = d.textbbox((x + 38, y + 4), label, font=font)
        d.rectangle([box[0] - 3, box[1] - 3, box[2] + 3, box[3] + 3], fill=(0, 0, 0), outline=colour, width=2)
        d.text((x + 38, y + 4), label, fill=colour, font=font)
        rows.append([e["kind"], e["target"], e["x"], e["y"], e["screen"]])
    im.save(path)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    out = args.out
    for sub in ("maps", "portraits/dialog", "portraits/status", "text"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)
    names0 = rom.strings(NAME_GROUP)
    name0 = [decode(rom, NAME_CHR, s) for s in names0]
    sheets: dict[str, tuple[list[str], list[list]]] = {}

    def table(name: str, header: list[str], rows: list[list]) -> None:
        write_csv(os.path.join(out, name + ".csv"), header, rows)
        sheets[name] = (header, rows)

    # ---------------------------------------------------------------- characters
    rows, stats, skills = [], [], []
    for c in range(CHAR_COUNT):
        sk = rom.skills(c)
        rows.append([c, name0[c + CHAR_NAME_BASE], c + CHAR_NAME_BASE, c,
                     " ".join(f"{name0[s]}(L{lv})" for s, lv in sk), "player" if c == HERO else ""])
        for s, lv in sk:
            skills.append([c, name0[c + CHAR_NAME_BASE], s, name0[s], lv])
    table("characters", ["id", "name", "name_string", "portrait", "skills", "note"], rows)
    for ch in range(1, 6):
        for c, st in enumerate(rom.chapter_stats(ch)):
            if st and any(st.values()):
                stats.append([ch, c, name0[c + CHAR_NAME_BASE]] + [st[f] for f in CHAPTER_FIELDS])
    table("chapter_stats", ["chapter", "id", "name"] + CHAPTER_FIELDS, stats)
    table("skills", ["char_id", "char_name", "skill_string", "skill", "learn_level"], skills)

    # ---------------------------------------------------------------- items / skills
    rows = []
    for i in range(1, ITEM_COUNT + 1):
        rows.append([i, name0[i], "weapon" if i in WEAPONS else "consumable",
                     rom.byte(2, ITEM_BATTLE_PARAM + i - 1)])
    rows += [[s, name0[s], "skill", ""] for s in range(SKILL_FIRST, SKILL_LAST + 1)]
    table("items", ["string", "name", "kind", "battle_param"], rows)

    # ---------------------------------------------------------------- enemies
    names9 = rom.strings(ENEMY_GROUP)
    enemy_names = []
    rows = []
    for t in range(ENEMY_COUNT):
        e = rom.enemy(t)
        name = decode(rom, ENEMY_CHR, names9[e["name_string"]]).replace("　", "")
        enemy_names.append(name)
        rows.append([t, name, e["name_string"]] + [e[f] for f in ENEMY_FIELDS])
    table("enemies", ["type", "name", "name_string"] + ENEMY_FIELDS, rows)
    rows = []
    for lv, pairs in enumerate(rom.encounters(), 1):
        for k, (a, b) in enumerate(pairs):
            rows.append([lv, k, a, enemy_names[a], b, enemy_names[b]])
    table("encounters", ["level", "slot", "left_type", "left", "right_type", "right"], rows)

    # ---------------------------------------------------------------- fonts
    for chr_bank in (NAME_CHR, ENEMY_CHR):
        m = charmap(rom, chr_bank)
        table(f"font{chr_bank:02d}", ["code", "cell", "plane", "char"],
              [[f"{c:02X}", c & 0x3F, c >> 7, ch] for c, ch in sorted(m.items())])
        glyph_sheet(rom, chr_bank, os.path.join(out, "text", f"group{FONTS[chr_bank][0]:02d}.png"))

    # ---------------------------------------------------------------- portraits
    rows = []
    dialog, status = [], []
    for p in range(PORTRAIT_COUNT):
        im = image(*rom.portrait(p, "dialog"))
        im.save(os.path.join(out, "portraits", "dialog", f"{p:02d}.png"))
        dialog.append(im)
        name = name0[p + CHAR_NAME_BASE] if p < CHAR_COUNT else ""
        rows.append([p, name, rom.portrait_chr(p), f"dialog/{p:02d}.png",
                     f"status/{p:02d}.png" if p < CHAR_COUNT else ""])
        if p < CHAR_COUNT:
            im = image(*rom.portrait(p, "status"))
            im.save(os.path.join(out, "portraits", "status", f"{p:02d}.png"))
            status.append(im)
    table("portraits", ["id", "name", "chr_bank", "dialog", "status"], rows)
    for name, ims, cols in (("dialog_sheet", dialog, 10), ("status_sheet", status, 13)):
        sheet = Image.new("RGB", (cols * 36, ((len(ims) + cols - 1) // cols) * 44))
        for i, im in enumerate(ims):
            sheet.paste(im, ((i % cols) * 36 + 2, (i // cols) * 44 + 2))
        sheet.resize((sheet.width * 3, sheet.height * 3), Image.NEAREST).save(
            os.path.join(out, "portraits", name + ".png"))

    # ---------------------------------------------------------------- maps
    rows = []
    for m in range(MAP_COUNT):
        im = image(*rom.map_pixels(m))
        w, h = rom.map_size(m)
        if m == 0:
            im.save(os.path.join(out, "maps", "world.png"))
            table("entrances", ["kind", "target", "x", "y", "screen"],
                  labelled_world(rom, im, os.path.join(out, "maps", "world_labelled.png")))
            fname = "world.png"
        else:
            fname = f"map{m:02d}.png"
            im.save(os.path.join(out, "maps", fname))
        cls = sorted({rom.terrain(v) for row in rom.map_cells(m) for v in row})
        rows.append([m, w, h, w * 16, h * 15, fname, " ".join(TERRAIN_CLASSES[c] for c in cls)])
    table("maps", ["map", "screens_w", "screens_h", "cells_w", "cells_h", "png", "terrain_classes"], rows)

    # ---------------------------------------------------------------- xlsx
    try:
        from openpyxl import Workbook
    except ImportError:
        return
    wb = Workbook()
    wb.remove(wb.active)
    for name, (header, rows) in sheets.items():
        ws = wb.create_sheet(name)
        ws.append(header)
        for r in rows:
            ws.append(r)
    wb.save(os.path.join(out, "shenghuo.xlsx"))


if __name__ == "__main__":
    main()
