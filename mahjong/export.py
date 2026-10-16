#!/usr/bin/env python3
"""匯出 FC 麻雀大会 的雀士、台詞、AI 參數、頭像、名牌與麻將牌圖。

Usage: .venv/bin/python mahjong/export.py [--rom ROM] [--out DIR] [--scale N]

Writes players.csv, speech.csv, tiles.csv (+ mahjong.xlsx when openpyxl is installed), portraits/
(P<player>_<expression>), faces.png (all faces in one sheet), names.png (the 16 name plates) and
tiles.png (the 34 tiles plus the back and side pieces). No composite faces in this game, so there
is no mob parts sheet.
"""
import argparse
import csv
import os

from PIL import Image
from rom import (
    AI_PARAM_SIZE,
    CPU_PLAYERS,
    DEFAULT_ROM,
    EXPRESSION_LABELS,
    EXPRESSIONS,
    FACE_PALETTE_FLAG,
    FULL_NAMES,
    HUMAN,
    KIND_LABELS,
    NAMES,
    PLAYERS,
    SPEECH_PER_PLAYER,
    TILE_CODES,
    TILE_NAMES,
    Rom,
    nes_rgb,
)

HERE = os.path.dirname(os.path.abspath(__file__))
# [EXT] what each of the 42 speech situations is about, read from the lines themselves (not from code)
SITUATION_GUESS = [
    "他家がドラを捨てた?", "自分が鳴いた", "他家がドラを鳴いた?", "カン", "他家のカン?", "他家が何度も鳴いた?",
    "他家が鳴いた?", "?", "自分のリーチ", "他家のリーチ?", "危険牌を通す", "一発消し", "早いアガリ?",
    "安いアガリ", "ツモアガリ", "高いアガリ", "?", "一発", "安いロン", "ロン", "ロン(振り込んだ相手へ)",
    "他家にアガられた?", "他家にツモられた", "他家同士のアガリ", "?", "?", "他家の安いアガリ",
    "他家にアガられた", "振り込み", "大きく振り込んだ?", "ドラで振り込み", "流局", "九種九牌・配牌が悪い",
    "流局?", "流局?", "トップになった", "半荘終了・不振?", "差馬を申し込む", "半荘終了・好成績?",
    "持ち点がなくなった", "大会優勝?", "他家の持ち点がなくなった",
]
PARAM_COLUMNS = ["P0_Gate", "P1_Reach_Threshold", "P2_Attack", "P3_Unk", "P4_Attack2", "P5_Defense",
                 "P6_Unk", "P7_Unk"]


def to_hiragana(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def player_rows(rom: Rom) -> list[dict]:
    rows = []
    for p in range(PLAYERS):
        params = rom.ai_params(p) if p < CPU_PLAYERS else [""] * AI_PARAM_SIZE
        rows.append({"Id": p, "Name": NAMES[p], "[EXT]FullName": FULL_NAMES[p],
                     "Face_Palette": rom.prg[FACE_PALETTE_FLAG + p] + 2, "Face_Tiles": rom.pool_size(p),
                     "Expressions": EXPRESSIONS if p < CPU_PLAYERS else 1,
                     **dict(zip(PARAM_COLUMNS, params))})
    return rows


def speech_rows(rom: Rom) -> list[dict]:
    rows = []
    for p in range(CPU_PLAYERS):
        for k in range(SPEECH_PER_PLAYER):
            s = rom.speech(p, k)
            sit = rom.situation_of(k)
            rows.append({"Player": p, "Name": NAMES[p], "Line": k, "Situation": sit,
                         "[EXT]Situation_Guess": SITUATION_GUESS[sit], "Kind": s["kind"],
                         "Kind_Label": KIND_LABELS[s["kind"]], "Face": s["face"],
                         "Text1": s["lines"][0], "Text2": s["lines"][1]})
    return rows


def tile_rows() -> list[dict]:
    return [{"Index": i, "Code": f"{c:02X}", "Name": n} for i, (c, n) in enumerate(zip(TILE_CODES, TILE_NAMES))]


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
        ws.freeze_panes = "C2"
    wb.save(path)
    print(f"已匯出 → {path}")


def to_image(pixels: bytes, w: int, h: int, scale: int = 1) -> Image.Image:
    img = Image.new("RGB", (w, h))
    img.putdata([nes_rgb(p) for p in pixels])
    return img.resize((w * scale, h * scale), Image.NEAREST) if scale > 1 else img


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 FC 麻雀大会 雀士／台詞／頭像／牌")
    ap.add_argument("--rom", default=DEFAULT_ROM)
    ap.add_argument("--out", default=os.path.join(HERE, "output"))
    ap.add_argument("--scale", type=int, default=1, help="PNG 放大倍率")
    args = ap.parse_args()
    rom = Rom(args.rom)
    os.makedirs(args.out, exist_ok=True)

    players, speech, tiles = player_rows(rom), speech_rows(rom), tile_rows()
    for name, rows in [("players", players), ("speech", speech), ("tiles", tiles)]:
        write_csv(rows, os.path.join(args.out, f"{name}.csv"))
    try:
        write_xlsx({"雀士": players, "台詞": speech, "牌": tiles}, os.path.join(args.out, "mahjong.xlsx"))
    except ImportError:
        print("提示: 安裝 openpyxl 可額外匯出 .xlsx")

    s = args.scale
    portraits = os.path.join(args.out, "portraits")
    os.makedirs(portraits, exist_ok=True)
    sheet = Image.new("RGB", (EXPRESSIONS * 36 * s, PLAYERS * 36 * s), (96, 96, 96))
    count = 0
    for p in range(PLAYERS):
        for e in range(EXPRESSIONS if p != HUMAN else 1):
            img = to_image(rom.face_pixels(p, e), 32, 32, s)
            img.save(os.path.join(portraits, f"P{p:02d}_{e}_{NAMES[p]}_{EXPRESSION_LABELS[e].replace(' ', '')}.png"))
            sheet.paste(img, ((e * 36 + 2) * s, (p * 36 + 2) * s))
            count += 1
    sheet.save(os.path.join(args.out, "faces.png"))
    print(f"已匯出 {count} 張頭像（{CPU_PLAYERS} 人 × {EXPRESSIONS} 種表情＋プレイヤー）→ {portraits}、faces.png")

    names = Image.new("RGB", (36 * PLAYERS, 20), (255, 255, 255))
    for p in range(PLAYERS):
        for y, row in enumerate(rom.name_glyph(p)):
            for x, v in enumerate(row):
                if v:
                    names.putpixel((p * 36 + 2 + x, 2 + y), (0, 0, 0))
    names.resize((names.width * max(s, 2), names.height * max(s, 2)), Image.NEAREST).save(
        os.path.join(args.out, "names.png"))

    pieces = Image.new("RGB", (40 * 18, 24), (96, 96, 96))
    for i in range(40):
        pieces.paste(to_image(rom.tile_pixels(i), 16, 24), (i * 18 + 1, 0))
    pieces.resize((pieces.width * max(s, 2), pieces.height * max(s, 2)), Image.NEAREST).save(
        os.path.join(args.out, "tiles.png"))
    print(f"已匯出名牌 names.png、牌 tiles.png（34 種＋牌背／側面）→ {args.out}")


if __name__ == "__main__":
    main()
