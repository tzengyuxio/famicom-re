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
from rom import BLOCK_H, DEFAULT_ROM, GENERIC, GRID_COLS, GRID_ROWS, N_GENERALS, GameRom, decode

TACTIC_GROUP = {0: "火", 1: "水", 2: "回復", 3: "補助（防御）", 4: "補助（妨害）", 5: "攻撃（特殊）"}
ELEMENT = {0: "", 1: "火", 2: "水"}
WORLD_ROWS, WORLD_COLS = range(4, 24), range(4, 24)  # the overworld (China) part of the block grid
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
            "id": g["id"], "name": g["name"], "kanji_codes": " ".join(f"{c:02X}/b{b}" for c, b in g["kanji"]),
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
    return [{"block_row": br, **{f"c{bc}": r.zone(br, bc) for bc in WORLD_COLS}} for br in range(4, 24)]


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


def strip_users(r: GameRom) -> dict[tuple[int, int], list[dict]]:
    """(row 0-5, strip code) -> generals whose portrait uses that 48x8 strip in that row."""
    users = {}
    for g in r.generals():
        if g["color"]:
            for row, v in enumerate(g["portrait"]):
                users.setdefault((row, v), []).append(g)
    return users


def user_names(gs: list[dict]) -> str:
    """Same-name ids merged: シュウチョウ(1,2,3)."""
    by = {}
    for g in gs:
        by.setdefault(g["name"], []).append(str(g["id"]))
    return "、".join(f"{n}({','.join(ids)})" for n, ids in by.items())


def strip_rows(r: GameRom) -> list[dict]:
    return [{"row": row + 1, "strip": f"{v:02X}", "faces": len({tuple(g["portrait"]) for g in gs}),
             "generals": len(gs), "users": user_names(gs)}
            for (row, v), gs in sorted(strip_users(r).items())]


def wrap(dr: ImageDraw.ImageDraw, text: str, f, width: int) -> list[str]:
    lines, cur = [], ""
    for part in text.split("、"):
        nxt = f"{cur}、{part}" if cur else part
        if cur and dr.textlength(nxt, font=f) > width:
            lines.append(cur + "、")
            nxt = part
        cur = nxt
    return lines + [cur]


def strips(r: GameRom, out: str) -> int:
    """Parts sheet of the 48x8 portrait strips, one section per row, each strip with the generals using it.
    A strip is drawn in the colour 3 most of its users have; strips/ holds each strip at 2x."""
    d = os.path.join(out, "strips")
    os.makedirs(d, exist_ok=True)
    users = strip_users(r)
    f, fb = font(11), font(14)
    sw, lh, width = 96, 15, 1400
    dr = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    blocks = []  # (row, strip, image, faces, name lines)
    for (k, v), gs in sorted(users.items()):
        colors = [g["color"] for g in gs]
        im = r.portrait_image({"portrait": [v] * 6, "color": max(set(colors), key=colors.count)})
        im = im.crop((0, 0, 48, 8)).resize((sw, 16), Image.NEAREST)
        im.save(os.path.join(d, f"{k + 1}_{v:02X}.png"))
        blocks.append((k, v, im, len({tuple(g["portrait"]) for g in gs}), wrap(dr, user_names(gs), f, width - sw - 70)))
    height = sum(max(20, len(b[4]) * lh + 5) for b in blocks) + 6 * 30
    sheet = Image.new("RGB", (width, height), (40, 40, 40))
    dr, y = ImageDraw.Draw(sheet), 0
    for k in range(6):
        sec = [b for b in blocks if b[0] == k]
        dr.text((6, y + 8), f"第 {k + 1} 條（y {k * 8}–{k * 8 + 7}）：{len(sec)} 種", fill=(255, 220, 120), font=fb)
        y += 30
        for _, v, im, faces, lines in sec:
            sheet.paste(im, (6, y + 2))
            dr.text((sw + 12, y + 3), f"{v:02X} ×{faces}", fill=(255, 255, 255), font=f)
            for n, t in enumerate(lines):
                dr.text((sw + 70, y + 3 + n * lh), t, fill=(190, 190, 190), font=f)
            y += max(20, len(lines) * lh + 5)
    sheet.save(os.path.join(out, "strips_sheet.png"))
    return len(users)


def area_blocks(r: GameRom) -> dict[tuple[int, int], int]:
    """Heuristic owner area of each grid block: nearest arrival point (entrance / teleport destination,
    or the field next to a town gate) within 40 metatiles. The ROM has no such table; see ROM_FORMAT.md."""
    seeds = set()
    for e in r.entrances():
        if e["area"] or e["dest_row"]:
            seeds.add((e["dest_row"], e["dest_col"], e["area"]))
        if r.area_type(e["area"]) >= 4:
            seeds.add((e["row"], e["col"], 0))
    for t in r.teleports():
        if t["row"] or t["dest_row"]:
            seeds.add((t["dest_row"], t["dest_col"], t["area"]))
    lab = {}
    for by in range(GRID_ROWS):
        for bx in range(GRID_COLS):
            d, a = min((abs(by * BLOCK_H + 7 - s[0]) + abs(bx * 16 + 8 - s[1]), s[2]) for s in seeds)
            if d < 40:
                lab[by, bx] = a
    return lab


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
    lab = area_blocks(r)
    f = font(12)
    items = r.items()
    marks = [(e["row"], e["col"], f"{e['area']:02X} {area_name(r, e['area'])}", (255, 255, 0))
             for e in r.entrances() if e["row"] or e["col"]]
    marks += [(t["row"], t["col"], f"→{t['area']:02X}", (0, 255, 255)) for t in r.teleports() if t["row"] or t["col"]]
    chest_marks = {}
    for c in r.chests():
        chest_marks.setdefault(c["area"], []).append((c["row"], c["col"], items[c["item"] & 0x7F]["name"],
                                                      (255, 128, 255)))

    def dim(im, rows, cols, keep):
        dr = ImageDraw.Draw(im, "RGBA")
        for i, by in enumerate(rows):
            for j, bx in enumerate(cols):
                if lab.get((by, bx), -1) not in keep:
                    dr.rectangle((j * 256, i * 240, j * 256 + 255, i * 240 + 239), fill=(0, 0, 0, 170))

    world = r.render_blocks(WORLD_ROWS, WORLD_COLS, 0)
    plain = world.copy()
    label_map(r, world, WORLD_ROWS, WORLD_COLS, marks + chest_marks.get(0, []), f)
    world.save(os.path.join(out, "world.png"))
    zones = plain.resize((plain.width // 4, plain.height // 4), Image.BOX)
    dz, fz = ImageDraw.Draw(zones, "RGBA"), font(20)
    tint = [(0, 0, 0, 0), (255, 0, 0, 70), (255, 160, 0, 70), (255, 255, 0, 70), (0, 200, 0, 70), (0, 200, 255, 70),
            (0, 80, 255, 70), (160, 0, 255, 70), (255, 0, 160, 70)]
    for by in range(4, 24):
        for bx in WORLD_COLS:
            z = r.zone(by, bx)
            if z:
                x, y = (bx - WORLD_COLS.start) * 64, (by - WORLD_ROWS.start) * 60
                dz.rectangle((x, y, x + 63, y + 59), fill=tint[z])
                dz.text((x + 24, y + 18), str(z), fill=(255, 255, 255), font=fz, stroke_width=2, stroke_fill=(0, 0, 0))
    zones.save(os.path.join(out, "world_zones.png"))
    n = 0
    for a in sorted(set(lab.values()) - {0}):
        blocks = [k for k, v in lab.items() if v == a]
        rows = range(min(b[0] for b in blocks), max(b[0] for b in blocks) + 1)
        cols = range(min(b[1] for b in blocks), max(b[1] for b in blocks) + 1)
        im = r.render_blocks(rows, cols, r.area_type(a))
        dim(im, rows, cols, (a,))
        label_map(r, im, rows, cols, marks + chest_marks.get(a, []), f)
        im.save(os.path.join(d, f"area_{a:02X}_{area_name(r, a) or f'type{r.area_type(a)}'}.png"))
        n += 1
    return n


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
        "portrait_strips": strip_rows(r),
    }
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
    print(f"{len(tables['generals'])} generals ({N_GENERALS} ids), {n} portraits, {strips(r, a.out)} strips, "
          f"{len(tables['messages'])} messages")
    print(strips_page.write(r, a.out))
    if not a.no_maps:
        print(f"world.png, world_zones.png, {maps(r, a.out)} area maps")


if __name__ == "__main__":
    main()
