#!/usr/bin/env python3
"""Export FC 三國志 as a kaodata dataset (san1-fc, format kaodata/1).

Spec: docs/data-format.md of the kaodata website repo. Writes dataset.json,
pixels.bin + portraits.bin (raw deflate) and checksums.json. The checksums come
from the reference renderer below, which implements spec §6.

Usage: .venv/bin/python sangokushi/tools/export_kaodata.py --out <dir> [--rom ROM]

Face index 0-64 is a dedicated portrait (P00-P64), 65+ a mob (大眾臉) composite
face; the game draws P65-P80 (female portraits) for no general. All 81 portraits
go in portraits.bin so the mob explorer need not download them.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import unicodedata
import zlib

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # sangokushi/ for romfile
from romfile import DEFAULT_ROM, read_rom

FORMAT = "kaodata/1"
TRANSPARENT = 255
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # sangokushi/

PALETTE = [(0, 0, 0), (247, 216, 165), (234, 158, 34), (255, 255, 255)]

# ROM file offsets (see docs/MOB_PORTRAIT_SYSTEM_PSEUDOCODE.md)
HEADS_START = 0x1C014      # 20 heads x 24 tiles
EYES_START = 0x1DE14       # 20 x 3 tiles
NOSES_START = 0x1E1D4      # 20 x 3 tiles
MOUTHS_START = 0x1E594     # 20 x 6 tiles
TEMPLATE_START = 0x1ED14   # 20 x 36 bytes, 0 = variant cell, else tile = val - 0x64
COMPONENT_TABLE = 0x1EFE4  # 190 x [cat, head, eye, nose, mouth], right after the templates
NAME_TABLE = 0x3A314       # 15 bytes per general
PORTRAIT_PTR_TABLE = 0x1BC38  # 81 x [bank, tile count, addr lo, addr hi] (docs/PORTRAIT_SYSTEM_PSEUDOCODE.md)
ARRANGEMENT_TABLE = 0x1B0D4   # 81 x 36 bytes, 6x6 cells, tile = val - 0x63 (1-based)
PORTRAIT_COUNT = 81
GENERAL_IDS = range(1, 256)  # record 0 is the new-ruler template (duplicate of 曹操)
# The game draws face index < 65 from the portrait table and anything else from COMPONENT_TABLE
# (tools/verify_face_select.py), so P65-P80 exist in the ROM but no general shows them.
MOB_FIRST = 65
MOB_COUNT = 190

# Slot id, label, size, position. Variant cells are rows 2-5, cols 1-3 in every template.
SLOTS = [("head", "頭", (48, 48), (0, 0)),
         ("eyes", "眼", (24, 8), (8, 16)),
         ("nose", "鼻", (24, 8), (8, 24)),
         ("mouth", "口", (24, 16), (8, 32))]
VARIANT_CELLS = {(r, c) for r in range(2, 6) for c in range(1, 4)}
MOUTH_ORDER = [0, 1, 4, 2, 3, 5]  # ROM tile order -> 3x2 grid, rows [0,1,4] / [2,3,5]


# ---------------------------------------------------------------- reference renderer (spec §6)

def get_image(meta: dict, blobs: list[bytes], img: int) -> tuple[int, int, bytes]:
    offset, w, h, *rest = meta["images"][img]
    pixels = blobs[rest[0] if rest else 0]
    return w, h, pixels[offset:offset + w * h]


def blit(dst: bytearray, dw: int, dh: int, src: tuple[int, int, bytes], x: int, y: int) -> None:
    sw, sh, data = src
    for sy in range(sh):
        dy = y + sy
        if not 0 <= dy < dh:
            continue
        for sx in range(sw):
            dx = x + sx
            c = data[sy * sw + sx]
            if 0 <= dx < dw and c != TRANSPARENT:
                dst[dy * dw + dx] = c


def crop(src: tuple[int, int, bytes], rect) -> tuple[int, int, bytes]:
    sw, sh, data = src
    x, y, w, h = rect
    out = bytearray([TRANSPARENT]) * (w * h)
    for row in range(h):
        if 0 <= y + row < sh:
            for col in range(w):
                if 0 <= x + col < sw:
                    out[row * w + col] = data[(y + row) * sw + x + col]
    return w, h, bytes(out)


def compose_display(meta: dict, blobs: list[bytes], face: dict) -> tuple[int, int, bytes]:
    """Indexed display image of a face (steps 1-4; this dataset has no backgrounds or windows on portraits)."""
    if "portrait" in face:
        assert "window" not in meta["portraits"][face["portrait"]] and face.get("bg") is None
        return get_image(meta, blobs, meta["portraits"][face["portrait"]]["img"])
    comp = meta["composite"]
    variant = comp["variants"][face["variant"]]
    cw, ch = comp["canvas"]
    canvas = bytearray([TRANSPARENT]) * (cw * ch)
    for slot, part in zip(comp["slots"], face["parts"]):
        sp = variant["parts"][slot["id"]]
        item = sp["items"][part]
        img, (x, y) = (item, sp.get("at", [0, 0])) if isinstance(item, int) else (item["img"], item["at"])
        blit(canvas, cw, ch, get_image(meta, blobs, img), x, y)
    shown = (cw, ch, bytes(canvas))
    if "window" in variant:
        shown = crop(shown, variant["window"])
    assert face.get("bg") is None, "san1-fc has no backgrounds"
    return shown


def to_rgba(src: tuple[int, int, bytes], colors: list[str]) -> bytes:
    rgb = [bytes.fromhex(c[1:]) for c in colors]
    return b"".join(b"\0\0\0\0" if c == TRANSPARENT else rgb[c] + b"\xff" for c in src[2])


def checksums(meta: dict, blobs: list[bytes]) -> dict:
    colors = meta["palettes"][0]["colors"]

    def digest(face: dict) -> str:
        return hashlib.sha256(to_rgba(compose_display(meta, blobs, face), colors)).hexdigest()

    entries = {f"ch:{ch['id']}": digest(ch["face"]) for ch in meta["characters"] if "face" in ch}
    entries.update({f"pt:{n}": digest({"portrait": n}) for n in range(len(meta.get("portraits", [])))})
    return {"algo": "sha256-rgba", "entries": entries}


def load_dataset(out_dir: str) -> tuple[dict, list[bytes]]:
    with open(os.path.join(out_dir, "dataset.json"), encoding="utf-8") as f:
        meta = json.load(f)
    blobs = []
    for name in meta.get("blobs", ["pixels.bin"]):
        with open(os.path.join(out_dir, name), "rb") as f:
            blobs.append(zlib.decompress(f.read(), -15))
    return meta, blobs


# ---------------------------------------------------------------- ROM decoding

def decode_tile(rom: bytes, offset: int) -> list[list[int]]:
    """NES 2bpp tile: plane 0 at +0..7, plane 1 at +8..15."""
    return [[((rom[offset + y] >> (7 - x)) & 1) | (((rom[offset + 8 + y] >> (7 - x)) & 1) << 1)
             for x in range(8)] for y in range(8)]


def tiles_to_image(tiles: dict, cols: int, rows: int) -> bytes:
    """tiles: {(row, col): 8x8 tile or None (transparent)} -> indexed bytes, row-major."""
    w = cols * 8
    out = bytearray([TRANSPARENT]) * (w * rows * 8)
    for (r, c), tile in tiles.items():
        if tile is None:
            continue
        for y in range(8):
            for x in range(8):
                out[(r * 8 + y) * w + c * 8 + x] = tile[y][x]
    return bytes(out)


def head_image(rom: bytes, g: int) -> bytes:
    """Head frame drawn through its template (head g uses template g); variant cells stay 255."""
    tpl = rom[TEMPLATE_START + g * 36:TEMPLATE_START + g * 36 + 36]
    tiles = {}
    for i, val in enumerate(tpl):
        r, c = divmod(i, 6)
        if val == 0:
            assert (r, c) in VARIANT_CELLS, f"template {g}: unexpected variant cell {(r, c)}"
            tiles[(r, c)] = None
        else:
            assert (r, c) not in VARIANT_CELLS, f"template {g}: frame tile in variant cell {(r, c)}"
            tiles[(r, c)] = decode_tile(rom, HEADS_START + g * 24 * 16 + (val - 0x64) * 16)
    return tiles_to_image(tiles, 6, 6)


def strip_image(rom: bytes, start: int, g: int, n: int) -> bytes:
    """Eyes / nose: n tiles in a row."""
    base = start + g * n * 16
    return tiles_to_image({(0, c): decode_tile(rom, base + c * 16) for c in range(n)}, n, 1)


def mouth_image(rom: bytes, g: int) -> bytes:
    base = MOUTHS_START + g * 6 * 16
    return tiles_to_image({divmod(i, 3): decode_tile(rom, base + t * 16) for i, t in enumerate(MOUTH_ORDER)}, 3, 2)


def portrait_image(rom: bytes, n: int) -> bytes:
    """Dedicated portrait Pnn: its tiles placed by arrangement n (portrait n uses arrangement n)."""
    bank, count, lo, hi = rom[PORTRAIT_PTR_TABLE + n * 4:PORTRAIT_PTR_TABLE + n * 4 + 4]
    base = bank * 0x4000 + ((hi << 8 | lo) - 0x8000) + 0x10
    cells = rom[ARRANGEMENT_TABLE + n * 36:ARRANGEMENT_TABLE + n * 36 + 36]
    tiles = {}
    for i, val in enumerate(cells):
        t = val - 0x63
        assert 1 <= t <= count, f"P{n:02d}: cell {i} -> tile {t} of {count}"
        tiles[divmod(i, 6)] = decode_tile(rom, base + (t - 1) * 16)
    return tiles_to_image(tiles, 6, 6)


def component_records(rom: bytes) -> list[tuple[int, int, int, int, int]]:
    """Face index MOB_FIRST+i -> (cat, head, eye, nose, mouth), indices local to the category (0-4)."""
    return [tuple(rom[COMPONENT_TABLE + i * 5:COMPONENT_TABLE + i * 5 + 5]) for i in range(MOB_COUNT)]


# ---------------------------------------------------------------- names

def load_tsv(name: str) -> list[list[str]]:
    with open(os.path.join(REPO, "data", name), encoding="utf-8") as f:
        return [line.rstrip("\n").split("\t") for line in f if line.strip() and not line.startswith("#")]


# The ROM spells these names with a stand-in character (see the notes in data/kanji_tiles.tsv).
# The dataset uses the historical spelling; 許攸's reading follows the ROM's 収 and is fixed too.
NAME_FIXES = {
    "沙摩可": "沙摩柯", "刑道栄": "邢道栄", "許収": "許攸", "旬攸": "荀攸", "李湛": "李堪", "蔡仲": "蔡中",
    "雷同": "雷銅", "鮑龍": "鮑隆", "朱雋": "朱儁", "呂廣": "呂曠", "厳晙": "厳畯", "辛毘": "辛毗",
}
READING_FIXES = {"許攸": "きょ ゆう"}


def kana_to_hiragana(s: str) -> str:
    """Half-width katakana -> full-width hiragana (NFKC merges voiced marks)."""
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in unicodedata.normalize("NFKC", s))


def general_names(rom: bytes) -> dict[int, tuple[str, str, int]]:
    """id -> (kanji name, reading, face index). Raises if a kanji tile is unmapped."""
    kanji = {(int(p), int(t, 16)): k for p, t, k, *_ in load_tsv("kanji_tiles.tsv")}
    surnames = {s: r for s, r in load_tsv("surnames.tsv")}
    out = {}
    for i in GENERAL_IDS:
        rec = rom[NAME_TABLE + i * 15:NAME_TABLE + i * 15 + 15]
        kana = kana_to_hiragana(bytes(b for b in rec[:8] if b).decode("cp932"))
        # (tile, page) pairs at +8..+13; tile 0 on page 0 means no character
        name = "".join(kanji[(rec[9 + 2 * k], rec[8 + 2 * k])] for k in range(3) if rec[8 + 2 * k] or rec[9 + 2 * k])
        family = name[:2] if name[:2] in surnames else name[0]  # surnames.tsv uses the ROM spelling
        reading = surnames.get(family)
        if reading and kana.startswith(reading) and len(kana) > len(reading):
            kana = f"{reading} {kana[len(reading):]}"
        name = NAME_FIXES.get(name, name)
        out[i] = (name, READING_FIXES.get(name, kana), rec[14] - 1)
    return out


# ---------------------------------------------------------------- dataset

def revision() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
                          cwd=REPO).stdout.strip()


def build(rom_path: str) -> tuple[dict, list[bytes]]:
    rom = read_rom(rom_path)

    images, blobs = [], [bytearray(), bytearray()]  # pixels.bin, portraits.bin

    def add(w: int, h: int, px: bytes, blob: int = 0) -> int:
        assert len(px) == w * h
        images.append([len(blobs[blob]), w, h, blob] if blob else [len(blobs[blob]), w, h])
        blobs[blob].extend(px)
        return len(images) - 1

    # 20 global indices per slot; global = cat * 5 + local
    makers = {"head": lambda g: head_image(rom, g),
              "eyes": lambda g: strip_image(rom, EYES_START, g, 3),
              "nose": lambda g: strip_image(rom, NOSES_START, g, 3),
              "mouth": lambda g: mouth_image(rom, g)}
    img = {sid: [add(*size, makers[sid](g)) for g in range(20)] for sid, _, size, _ in SLOTS}

    variants = [{"id": str(cat), "label": f"Cat {cat}",
                 "parts": {sid: {"at": list(at), "items": img[sid][cat * 5:cat * 5 + 5]}
                           for sid, _, _, at in SLOTS}}
                for cat in range(4)]

    portraits = [{"img": add(48, 48, portrait_image(rom, n), blob=1)} for n in range(PORTRAIT_COUNT)]

    records = component_records(rom)
    characters = []
    for gid, (name, reading, face_index) in general_names(rom).items():
        ch = {"id": gid, "name": name, "reading": reading}
        if face_index >= MOB_FIRST:
            cat, *parts = records[face_index - MOB_FIRST]
            ch["face"] = {"variant": cat, "parts": parts, "code": "-".join(map(str, (cat, *parts)))}
        else:
            ch["face"] = {"portrait": face_index}
        characters.append(ch)

    meta = {
        "format": FORMAT,
        "id": "san1-fc",
        "game": "SAN1",
        "platform": "FC",
        "title": {"ja": "三國志", "zh": "三國志"},
        "source": {"producer": "famicom-re", "revision": revision(),
                   "inputs": [{"path": os.path.basename(rom_path),
                               "sha1": hashlib.sha1(rom).hexdigest()}]},
        "display": {"scale": 6},
        "blobs": ["pixels.bin", "portraits.bin"],
        "palettes": [{"id": "main", "label": "FC 頭像 4 色", "colors": [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in PALETTE]}],
        "images": images,
        "composite": {
            "canvas": [48, 48],
            "slots": [{"id": sid, "label": label} for sid, label, _, _ in SLOTS],
            "variants": variants,
            "code": {"kind": "tuple"},
        },
        "portraits": portraits,
        "characters": characters,
    }
    return meta, [bytes(b) for b in blobs]


def write_dataset(out_dir: str, meta: dict, blobs: list[bytes]) -> None:
    os.makedirs(out_dir, exist_ok=True)
    for name, px in zip(meta.get("blobs", ["pixels.bin"]), blobs):
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        with open(os.path.join(out_dir, name), "wb") as f:
            f.write(comp.compress(px) + comp.flush())
    with open(os.path.join(out_dir, "dataset.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(out_dir, "checksums.json"), "w", encoding="utf-8") as f:
        json.dump(checksums(meta, blobs), f, indent=1)


def main() -> None:
    ap = argparse.ArgumentParser(description="匯出 kaodata 統一格式資料集 san1-fc")
    ap.add_argument("--rom", default=DEFAULT_ROM, help="roms/ 的 zip 或 .nes")
    ap.add_argument("--out", required=True, help="輸出目錄")
    args = ap.parse_args()
    meta, blobs = build(args.rom)
    write_dataset(args.out, meta, blobs)
    chars = meta["characters"]
    mobs = [c["face"] for c in chars if "variant" in c.get("face", {})]
    n_pt = sum("portrait" in c.get("face", {}) for c in chars)
    unsplit = [c["name"] for c in chars if " " not in c["reading"]]
    print(f"san1-fc: {len(chars)} characters ({n_pt} portrait, {len(mobs)} composite, "
          f"{len(chars) - n_pt - len(mobs)} without face, "
          f"{len({f['code'] for f in mobs})} distinct combos), {len(meta['portraits'])} portraits, "
          f"{len(meta['images'])} images")
    print(f"  reading without family/given split: {' '.join(unsplit) or '-'}")
    raw = dict(zip(meta["blobs"], blobs))
    for name in [*meta["blobs"], "dataset.json", "checksums.json"]:
        size = f"{len(raw[name])} px -> " if name in raw else ""
        print(f"  {name}: {size}{os.path.getsize(os.path.join(args.out, name))} B")


if __name__ == "__main__":
    main()
