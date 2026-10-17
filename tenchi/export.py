"""Export 天地を喰らう data to tenchi/output/: CSV (UTF-8-BOM), XLSX and PNG.

  .venv/bin/python tenchi/export.py [--rom ROM] [--out DIR] [--no-maps]
"""
import argparse
import csv
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import strips_page
from rom import (
    BLOCK_H,
    DEFAULT_ROM,
    GENERIC,
    N_GENERALS,
    PORTRAIT_COLOR,
    PORTRAIT_FIXED,
    GameRom,
    decode,
    nes_rgb,
)

TACTIC_GROUP = {0: "火", 1: "水", 2: "回復", 3: "補助（防御）", 4: "補助（妨害）", 5: "攻撃（特殊）"}
ELEMENT = {0: "", 1: "火", 2: "水"}
WORLD_ROWS, WORLD_COLS = range(4, 24), range(3, 24)  # blocks of the field that come on screen (reach(0))
FONT_PATHS = ["/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]


def font(size: int):
    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def write_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------- tables
def general_rows(r: GameRom) -> list[dict]:
    pools = {i: z for z, ids in r.encounter_pools().items() for i in ids}
    forms = {}
    for k, f in enumerate(r.formations()):
        for i in set(f) - {0}:
            forms.setdefault(i, []).append(str(k))
    rows = []
    for g in r.generals():
        raw = g["raw"]
        rank = g["ally_rank"]
        rows.append({
            "id": g["id"], "name": g["name"], "kanji": g["kanji_text"], "kanji_codes": " ".join(f"{c:02X}/b{b}" for c, b in g["kanji"]),
            "ぶりょく": g["buryoku"], "ちりょく": g["chiryoku"], "すばやさ": g["speed"],
            "兵士数": r.soldiers(rank), "兵士数成長": "yes" if rank & 0x80 else "", "soldier_rank(+7)": f"{rank:02X}",
            "enemy_level(+8)": g["level"], "zone(+2)": g["region"], "weapon_class(+4)": g["weapon"],
            "armor(+5)": g["armor"], "enemy_rank(+6)": g["enemy_rank"], "b3": g["b3"], "b4_hi": g["b4_hi"],
            "random_zone": pools.get(g["id"], ""), "fixed_battles": " ".join(forms.get(g["id"], [])),
            "portrait_chunks": " ".join(f"{v:02X}" for v in g["portrait"]), "portrait_color": g["color"],
            "has_portrait": "yes" if g["color"] else "", "raw": raw.hex(" "), "ptr": f"{g['ptr']:04X}"})
    return rows


def growth_rows(r: GameRom) -> list[dict]:
    growers = [g for g in r.generals() if g["ally_rank"] & 0x80]
    seen, rows = set(), []
    for g in growers:
        if g["name"] in seen:
            continue
        seen.add(g["name"])
        rows.append({"id": g["id"], "name": g["name"], "rank": f"{g['ally_rank']:02X}",
                     **{f"Lv{lv}": r.soldiers(g["ally_rank"], lv) for lv in range(1, 61)}})
    return rows


def item_rows(r: GameRom) -> list[dict]:
    kinds = {"weapon": "武器", "armor": "鎧", "helmet": "兜"}
    shop_of = {}
    for k, s in enumerate(r.shops()[:37]):
        for i in s:
            shop_of.setdefault(i, []).append(str(k))
    return [{"id": it["id"], "hex": f"{it['id']:02X}", "name": it["name"], "種類": kinds.get(it["kind"], ""),
             "價格": it["price"], "攻撃力/武装度": it["power"], "shops": " ".join(shop_of.get(it["id"], [])),
             "ptr": f"{it['ptr']:04X}"} for it in r.items()]


def shop_rows(r: GameRom) -> list[dict]:
    items = r.items()
    towns = {}
    for a in range(0x40, 0x80):
        left, right = r.shop_of_area(a)
        if a < 0x71 or a == 0x7F:  # $71-$7E carry the default 0 / 1 and have no shop counter
            for side, k in (("左", left), ("右", right)):
                if k or a == 0x7F:
                    towns.setdefault(k, []).append(f"{r.place_name(a)}({side})")
    rows = []
    for k, s in enumerate(r.shops()[:37]):
        rows.append({"shop": k, "towns": " ".join(towns.get(k, [])),
                     "items": " / ".join(f"{items[i]['name']} {items[i]['price']}" for i in s),
                     "item_ids": " ".join(f"{i:02X}" for i in s)})
    return rows


def tactic_rows(r: GameRom) -> list[dict]:
    rows = []
    for t in r.tactics():
        target = "全體" if t["target_all"] else "單體" if t["target1"] else ""
        side = "我方" if (t["target1"] | t["target_all"]) & 1 else "敵方" if (t["target1"] | t["target_all"]) else ""
        rows.append({"id": t["id"], "name": t["name"], "系統": TACTIC_GROUP.get(t["group"], t["group"]),
                     "rank": t["rank"], "習得レベル": t["level"], "必要ちりょく": t["chiryoku"], "SP": t["sp"],
                     "對象": f"{side}{target}", "屬性": ELEMENT.get(t["element"], t["element"]),
                     "威力": t["power"], "b_BBBC": t["b_bbbc"], "移動中可用": "yes" if t["field"] else "",
                     "target1_raw": f"{t['target1']:02X}", "target_all_raw": f"{t['target_all']:02X}"})
    return rows


def formation_rows(r: GameRom) -> list[dict]:
    gs = r.generals()
    return [{"battle": k, "ids": " ".join(str(i) for i in f if i),
             "enemies": " ".join(gs[i]["name"] for i in f if i)} for k, f in enumerate(r.formations())]


def pool_rows(r: GameRom) -> list[dict]:
    gs = r.generals()
    rows = []
    for z, ids in r.encounter_pools().items():
        rows.append({"zone": z, "generic": GENERIC[4] if z >= 6 else "地形で決まる（" + "／".join(GENERIC.values()) + "）",
                     "count": len(ids), "ids": " ".join(map(str, ids)), "names": " ".join(gs[i]["name"] for i in ids)})
    return rows


def area_name(r: GameRom, a: int) -> str:
    return r.place_name(a) or ("フィールド" if a == 0 else "")


def entrance_rows(r: GameRom) -> list[dict]:
    rows = []
    for e in r.entrances():
        if not (e["row"] or e["col"] or e["area"]):
            continue
        rows.append({"id": e["id"], "row": e["row"], "col": e["col"], "block": f"{e['row'] // BLOCK_H},{e['col'] >> 4}",
                     "dest_area": f"{e['area']:02X}", "dest_name": area_name(r, e["area"]),
                     "dest_type": r.area_type(e["area"]), "dest_row": e["dest_row"], "dest_col": e["dest_col"],
                     "dir": e["dir"]})
    return rows


def teleport_rows(r: GameRom) -> list[dict]:
    return [{"id": t["id"], "row": t["row"], "col": t["col"], "dest_area": f"{t['area']:02X}",
             "dest_name": area_name(r, t["area"]), "dest_row": t["dest_row"], "dest_col": t["dest_col"],
             "flags": f"{t['flags']:02X}"} for t in r.teleports() if t["row"] or t["col"] or t["dest_row"]]


def chest_rows(r: GameRom) -> list[dict]:
    items = r.items()
    return [{"area": f"{c['area']:02X}", "area_name": area_name(r, c["area"]), "slot": c["slot"], "row": c["row"],
             "col": c["col"], "item_id": f"{c['item']:02X}", "item": items[c["item"] & 0x7F]["name"]}
            for c in r.chests()]


def place_rows(r: GameRom) -> list[dict]:
    rows = []
    for a in range(0x80):
        left, right = r.shop_of_area(a) if a >= 0x40 else (0, 0)
        rows.append({"area": f"{a:02X}", "name": area_name(r, a), "type": r.area_type(a), "tileset": r.area_tileset(a),
                     "shop_left": left if 0x52 <= a < 0x71 or a == 0x7F else "",
                     "shop_right": right if 0x52 <= a < 0x71 or a == 0x7F else ""})
    return rows


def zone_rows(r: GameRom) -> list[dict]:
    return [{"block_row": br, **{f"c{bc}": r.zone(br, bc) for bc in WORLD_COLS}} for br in WORLD_ROWS]


# ---------------------------------------------------------------- images
def portraits(r: GameRom, out: str) -> int:
    d = os.path.join(out, "portraits")
    os.makedirs(d, exist_ok=True)
    gs = [g for g in r.generals() if g["color"]]
    seen, uniq = set(), []
    for g in gs:
        r.portrait_image(g, 2).save(os.path.join(d, f"{g['id']:03d}_{g['name']}.png"))
        r.kanji_image(g).save(os.path.join(d, f"{g['id']:03d}_{g['name']}_name.png"))
        key = (tuple(g["portrait"]), g["color"], tuple(g["kanji"]))
        if key not in seen:
            seen.add(key)
            uniq.append(g)
    cols, cw, chh = 16, 56, 84
    sheet = Image.new("RGB", (cols * cw, ((len(uniq) + cols - 1) // cols) * chh), (40, 40, 40))
    dr, f = ImageDraw.Draw(sheet), font(10)
    for k, g in enumerate(uniq):
        x, y = (k % cols) * cw, (k // cols) * chh
        sheet.paste(r.portrait_image(g), (x + 4, y + 4))
        kim = r.kanji_image(g)
        sheet.paste(kim, (x + 4 + (48 - kim.width) // 2, y + 54))
        dr.text((x + 4, y + 71), f"{g['id']}", fill=(200, 200, 200), font=f)
    sheet.save(os.path.join(out, "portraits_sheet.png"))
    return len(gs)


def strip_data(r: GameRom) -> dict:
    """Data for strips_page: strip index = strip code 00-FF, palette id = +16 & $0F (1-9).
    179 (10マメ) is left out: its pointer lands inside 180's record, so its "portrait" is 180's bytes."""
    gens = [{"id": g["id"], "name": g["kanji_text"] or g["name"], "zh": g["kanji_text"], "kana": g["name"],
             "p": g["portrait"], "c": g["color"],
             "k": [strips_page.glyph_hex(r.kanji_glyph(c, b)) for c, b in g["kanji"]]}
            for g in r.generals() if g["color"] and g["id"] != 179]
    strips = []
    for v in range(256):
        tiles = r.portrait_tiles([v])
        strips.append("".join(str(tiles[i // 8 % 6][(i // 48) * 8 + i % 8]) for i in range(384)))

    def hexrgb(c: int) -> str:
        return "#" + "".join(f"{x:02x}" for x in nes_rgb(c))
    return {"game": "tenchi", "title": "天地を喰らう", "group_names": ["兜", "官帽"],
            "fixed": [hexrgb(c) for c in PORTRAIT_FIXED], "colors": [hexrgb(c) for c in PORTRAIT_COLOR],
            "strips": strips, "labels": [f"{v:02X}" for v in range(256)], "generals": gens}


def area_views(r: GameRom) -> list[tuple[list[int], set]]:
    """Areas with the cells that come on screen there (MapRom.reach + visible). Areas that show exactly
    the same cells (one house interior used by several villages) are merged."""
    views = {}
    for a in range(1, 0x80):
        if r.arrivals(a):
            views.setdefault(frozenset(r.visible(r.reach(a))), []).append(a)
    return sorted(((ids, set(cells)) for cells, ids in views.items()), key=lambda v: v[0])


def clusters(cells) -> list[tuple[range, range]]:
    """Block bounding boxes of the 8-connected groups of blocks that hold `cells`."""
    left = {(row // BLOCK_H, col // 16) for row, col in cells}
    out = []
    while left:
        todo = [left.pop()]
        group = set(todo)
        while todo:
            by, bx = todo.pop()
            for nb in ((by + i, bx + j) for i in (-1, 0, 1) for j in (-1, 0, 1)):
                if nb in left:
                    left.remove(nb)
                    group.add(nb)
                    todo.append(nb)
        out.append((range(min(b[0] for b in group), max(b[0] for b in group) + 1),
                    range(min(b[1] for b in group), max(b[1] for b in group) + 1)))
    return sorted(out, key=lambda c: (c[0].start, c[1].start))


def fill_holes(cells, rows: range, cols: range) -> set:
    """`cells` plus the cells it encloses within blocks rows x cols (lake middles, mountain cores)."""
    box = {(row, col) for row in range(rows.start * BLOCK_H, rows.stop * BLOCK_H)
           for col in range(cols.start * 16, cols.stop * 16)}
    todo = [c for c in box - set(cells) if c[0] in (rows.start * BLOCK_H, rows.stop * BLOCK_H - 1)
            or c[1] in (cols.start * 16, cols.stop * 16 - 1)]
    outside = set(todo)
    while todo:
        row, col = todo.pop()
        for nxt in ((row + 1, col), (row - 1, col), (row, col + 1), (row, col - 1)):
            if nxt in box and nxt not in cells and nxt not in outside:
                outside.add(nxt)
                todo.append(nxt)
    return box - outside


def render_cells(r: GameRom, cells, typ: int, marks, f) -> Image.Image:
    """Map image of `cells`: each block group drawn as area type `typ` and cropped to its cells, metatiles
    outside `cells` black, marks on `cells` labelled; several groups are put side by side."""
    ims = []
    for rows, cols in clusters(cells):
        im = r.render_blocks(rows, cols, typ)
        dr = ImageDraw.Draw(im)
        for row in range(rows.start * BLOCK_H, rows.stop * BLOCK_H):
            for col in range(cols.start * 16, cols.stop * 16):
                if (row, col) not in cells:
                    x, y = (col - cols.start * 16) * 16, (row - rows.start * BLOCK_H) * 16
                    dr.rectangle((x, y, x + 15, y + 15), fill=(0, 0, 0))
        label_map(r, im, rows, cols, [m for m in marks if m[:2] in cells], f)
        mine = [(row - rows.start * BLOCK_H, col - cols.start * 16) for row, col in cells
                if row // BLOCK_H in rows and col // 16 in cols]
        ims.append(im.crop((min(c for _, c in mine) * 16, min(r_ for r_, _ in mine) * 16,
                            max(c for _, c in mine) * 16 + 16, max(r_ for r_, _ in mine) * 16 + 16)))
    out = Image.new("RGB", (sum(im.width for im in ims) + 16 * (len(ims) - 1), max(im.height for im in ims)),
                    (40, 40, 40))
    x = 0
    for im in ims:
        out.paste(im, (x, 0))
        x += im.width + 16
    return out


def label_map(r: GameRom, im: Image.Image, rows: range, cols: range, items, f) -> None:
    dr = ImageDraw.Draw(im)
    for row, col, text, colour in items:
        if rows.start * BLOCK_H <= row < rows.stop * BLOCK_H and cols.start * 16 <= col < cols.stop * 16:
            x, y = (col - cols.start * 16) * 16, (row - rows.start * BLOCK_H) * 16
            dr.rectangle((x, y, x + 15, y + 15), outline=colour, width=2)
            dr.text((x + 1, y - 13), text, fill=colour, font=f, stroke_width=2, stroke_fill=(0, 0, 0))


def maps(r: GameRom, out: str) -> int:
    d = os.path.join(out, "maps")
    os.makedirs(d, exist_ok=True)
    f = font(12)
    items = r.items()
    marks = [(e["row"], e["col"], f"{e['area']:02X} {area_name(r, e['area'])}", (255, 255, 0))
             for e in r.entrances() if e["row"] or e["col"]]
    marks += [(t["row"], t["col"], f"→{t['area']:02X}", (0, 255, 255)) for t in r.teleports() if t["row"] or t["col"]]
    chest_marks = {}
    for c in r.chests():
        chest_marks.setdefault(c["area"], []).append((c["row"], c["col"], items[c["item"] & 0x7F]["name"],
                                                      (255, 128, 255)))

    field = r.visible(r.reach(0))
    assert clusters(field) == [(WORLD_ROWS, WORLD_COLS)]
    field = fill_holes(field, WORLD_ROWS, WORLD_COLS)
    render_cells(r, field, 0, marks + chest_marks.get(0, []), f).save(os.path.join(out, "world.png"))
    plain = render_cells(r, field, 0, [], f)
    zones = plain.resize((plain.width // 4, plain.height // 4), Image.BOX)
    dz, fz = ImageDraw.Draw(zones, "RGBA"), font(20)
    tint = [(0, 0, 0, 0), (255, 0, 0, 70), (255, 160, 0, 70), (255, 255, 0, 70), (0, 200, 0, 70), (0, 200, 255, 70),
            (0, 80, 255, 70), (160, 0, 255, 70), (255, 0, 160, 70)]
    for by in WORLD_ROWS:
        for bx in WORLD_COLS:
            z = r.zone(by, bx)
            if z and any((by * BLOCK_H + y, bx * 16 + x) in field for y in range(BLOCK_H) for x in range(16)):
                x, y = (bx * 16 - min(c for _, c in field)) * 4, (by * BLOCK_H - min(r_ for r_, _ in field)) * 4
                dz.rectangle((x, y, x + 63, y + 59), fill=tint[z])
                dz.text((x + 24, y + 18), str(z), fill=(255, 255, 255), font=fz, stroke_width=2, stroke_fill=(0, 0, 0))
    zones.save(os.path.join(out, "world_zones.png"))
    views = area_views(r)
    for ids, cells in views:
        name = "・".join(dict.fromkeys(area_name(r, a) for a in ids if area_name(r, a))) or f"type{r.area_type(ids[0])}"
        marks_a = marks + [m for a in ids for m in chest_marks.get(a, [])]
        im = render_cells(r, cells, r.area_type(ids[0]), marks_a, f)
        im.save(os.path.join(d, f"area_{'+'.join(f'{a:02X}' for a in ids)}_{name}.png"))
    return len(views)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--no-maps", action="store_true")
    a = ap.parse_args()
    r = GameRom(a.rom)
    os.makedirs(a.out, exist_ok=True)
    tables = {
        "generals": general_rows(r), "soldier_growth": growth_rows(r), "items": item_rows(r), "shops": shop_rows(r),
        "tactics": tactic_rows(r), "battles": formation_rows(r), "encounter_pools": pool_rows(r),
        "encounter_zones": zone_rows(r), "places": place_rows(r), "entrances": entrance_rows(r),
        "teleports": teleport_rows(r), "chests": chest_rows(r),
        "dictionary": [{"id": i, "word": decode(r.word(i))} for i in range(256)],
        "messages": [{"bank": m["bank"], "id": m["id"], "ptr": f"{m['ptr']:04X}", "text": m["text"]}
                     for m in r.messages()],
        "soldier_table": [{"rank": k, "兵士数": v} for k, v in enumerate(r.soldier_table())],
    }
    tables["portrait_strips"] = strips_page.write(strip_data(r), a.out)
    for name, rows in tables.items():
        write_csv(os.path.join(a.out, f"{name}.csv"), rows)
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in tables.items():
        ws = wb.create_sheet(name[:31])
        ws.append(list(rows[0]))
        for row in rows:
            ws.append([v if isinstance(v, (int, float)) else str(v) for v in row.values()])
    wb.save(os.path.join(a.out, "tenchi.xlsx"))
    n = portraits(r, a.out)
    print(f"{len(tables['generals'])} generals ({N_GENERALS} ids), {n} portraits, {len(tables['messages'])} messages")
    if not a.no_maps:
        print(f"world.png, world_zones.png, {maps(r, a.out)} area maps")


if __name__ == "__main__":
    main()
