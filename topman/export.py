"""Export the decoded Top Management data to topman/output/ (CSV in UTF-8-BOM, xlsx, PNG)."""
import argparse
import csv
import os
import sys

from openpyxl import Workbook
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rom import (
    AD_CURVES,
    AD_MONTHS,
    DEFAULT_ROM,
    DEMAND_CURVES,
    DEMAND_FIRST_YEAR,
    DEMAND_SCALE,
    DEMAND_YEARS,
    MEDIA,
    PALETTE_GUESSED,
    PICTURE_PALETTES,
    PRODUCTS,
    Rom,
    join_marks,
    nes_rgb,
)

GRAY = bytes([0x0F, 0x00, 0x10, 0x30] * 4)  # pictures whose palette is not known
WIDTHS = {"meeting": 32, "season": 16, "staff": 16, "news": 8}


def company_rows(rom: Rom) -> list[dict]:
    rows = []
    for c in rom.companies():
        row = {}
        for k, v in c.items():
            if k == "ptrs":
                row.update({f"ptr_{n}": f"${a:04X}" for n, a in v.items()})
            elif isinstance(v, list):
                row[k] = "/".join(map(str, v))
            else:
                row[k] = join_marks(v) if isinstance(v, str) else v
        rows.append(row)
    return rows


def demand_rows(rom: Rom) -> list[dict]:
    rows = []
    for p, name in enumerate(PRODUCTS):
        for k in range(DEMAND_CURVES):
            row = {"product": p, "name": name, "curve": k}
            row.update({str(DEMAND_FIRST_YEAR + y): v * DEMAND_SCALE for y, v in enumerate(rom.demand_curve(p, k))})
            rows.append(row)
    return rows


def ad_rows(rom: Rom) -> list[dict]:
    rows = []
    for m, name in enumerate(MEDIA):
        for k in range(AD_CURVES):
            row = {"medium": m, "name": name, "curve": k}
            row.update({f"m{i}": v for i, v in enumerate(rom.ad_curve(m, k))})
            rows.append(row)
    assert all(len(r) == 3 + AD_MONTHS for r in rows)
    return rows


def picture_rows(rom: Rom, out: str) -> list[dict]:
    os.makedirs(out, exist_ok=True)
    rows = []
    for p in rom.pictures():
        key = (p["tag"], p["index"])
        width = WIDTHS.get(p["tag"]) or rom.picture_width(p)
        pal_off = PICTURE_PALETTES.get(key)
        pal = rom.prg[pal_off:pal_off + 16] if pal_off is not None else GRAY
        w, h, px = rom.picture_pixels(p, width, pal)
        name = f"{p['tag']}_{p['index']:02d}.png"
        if w and h:
            img = Image.new("RGB", (w, h))
            img.putdata([nes_rgb(c) for c in px])
            img.save(os.path.join(out, name))
        rows.append({"file": name, "tag": p["tag"], "index": p["index"], "bank": p["bank"],
                     "descriptor": f"${p['desc']:04X}", "tiles": f"${p['tiles']:04X}", "attr": f"${p['attr']:04X}",
                     "map": f"${p['map']:04X}", "map_bytes": p["map_size"], "width_tiles": width,
                     "width_from": "screen" if p["tag"] in WIDTHS else "heuristic",
                     "palette": f"0x{pal_off:05X}" if pal_off is not None else "gray",
                     "palette_status": ("guessed" if key in PALETTE_GUESSED else "verified")
                     if pal_off is not None else "unknown",
                     # 1-tile-high results: the width/layout of these blocks is not understood (see docs)
                     "layout": "unsolved" if h <= 8 else "ok"})
    return rows


def string_rows(rom: Rom) -> list[dict]:
    return [{"offset": f"0x{o:05X}", "bank": o // 0x4000, "text": join_marks(s)} for o, s in rom.strings()]


def write_csv(path: str, rows: list[dict]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)
    sheets = {
        "companies": company_rows(rom),
        "demand_curves": demand_rows(rom),
        "ad_curves": ad_rows(rom),
        "pictures": picture_rows(rom, os.path.join(args.out, "pictures")),
        "strings": string_rows(rom),
    }
    wb = Workbook()
    wb.remove(wb.active)
    for name, rows in sheets.items():
        write_csv(os.path.join(args.out, f"{name}.csv"), rows)
        ws = wb.create_sheet(name)
        ws.append(list(rows[0]))
        for r in rows:
            ws.append(list(r.values()))
        print(f"{name}: {len(rows)}")
    wb.save(os.path.join(args.out, "topman.xlsx"))
    assert DEMAND_YEARS == len(sheets["demand_curves"][0]) - 3


if __name__ == "__main__":
    main()
