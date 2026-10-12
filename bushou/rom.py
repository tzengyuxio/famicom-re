"""FC 信長の野望・武将風雲録 (KOEI, 1991) ROM decoding.

All offsets are PRG offsets (file offset - 0x10). See bushou/docs/ROM_FORMAT.md.
"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Nobunaga no Yabou - Bushou Fuuun Roku (Japan).zip")

PRG_SIZE = 0x80000
CHR_START = 0x10 + PRG_SIZE
BANK = 0x2000

# ---------------------------------------------------------------- scenarios (bank loaded at WRAM $6000)
SCENARIOS = [  # (name, data bank, name bank, start generals, later-general list offset)
    ("戦国の動乱", 35, 33, 250, 0x4A004),
    ("信長包囲網", 36, 34, 255, 0x4A3D4),
]
SCENARIO_COUNT = len(SCENARIOS)
WRAM = 0x6000
PROVINCE_COUNT = 48
PROVINCE_START, PROVINCE_SIZE = 0x007, 32
TEA_START, TEA_SIZE, TEA_COUNT = 0x607, 3, 48
DAIMYO_START, DAIMYO_SIZE, DAIMYO_SLOTS = 0x698, 32, 48
GENERAL_START, GENERAL_SIZE = 0xC98, 13
NAME_START, NAME_SIZE = 4, 20       # name bank: 20 bytes per name
LATER_FIRST = 256                   # name index of later-appearing general k = 256 + k
LATER_SIZE = 8
BASE_YEAR = 1476                    # years are stored as year - 1476

PROVINCE_NAMES = 0x416B0            # 48 x 13 bytes: name (4 SJIS + 0), ?, neighbours (FF end)

# ---------------------------------------------------------------- faces
PORTRAIT_W, PORTRAIT_H = 5, 6       # tiles
PORTRAIT_COUNT = 212                # dedicated face ids 0-211 (168 and 169 unused)
COMPOSITE_PAGES = 0x745F6           # bank 58 $A5F6: head h page p at + (4h + p) * 60
COMPOSITE_HEADS = 5                 # heads 0-4 in the table (characters use 0-3)
# (slot id, label, code bit): each slot takes 2 bits of the face code = page 0-3
COMPOSITE_SLOTS = [("top", "上", 3), ("bottom", "下", 5), ("eyes", "眼", 7), ("nose", "鼻", 9), ("mouth", "口", 11)]
# bank 58 $A5A6: 8 LE16 per head = split cell, ?, (first cell, count) x eyes, nose, mouth
COMPOSITE_AREAS = 0x745A6
MAIN_PALETTE = 0x7F401              # bank 63 $F401: main-screen BG palette (faces, big map)

# ---------------------------------------------------------------- big map
MAP_TILES, MAP_EXRAM = 0x6A1A8, 0x6A4B4  # bank 53, 30 x 26 tiles drawn at tile (1, 2)
MAP_W, MAP_H = 30, 26

# ---------------------------------------------------------------- battle maps
FIELD_MAPS = 0x62004                # bank 49: 48 x 154 bytes, 14 x 11 cells
CASTLE_MAPS = 0x64004               # bank 50: 49 x 143 bytes, 13 x 11 cells
CASTLE_LAYER = 0x66004              # bank 51: second layer, same shape (not drawn)
FIELD_W, CASTLE_W, BATTLE_H = 14, 13, 11
FIELD_COUNT, CASTLE_COUNT = 48, 49  # castle map 48 = 安土 (近江 with flags set)
FIELD_SCREEN, CASTLE_SCREEN = 0x5EAAC, 0x5E004  # bank 47: 32x30 tile ids then 32x30 ExRAM
FIELD_ORIGIN, CASTLE_ORIGIN = (2, 5), (3, 5)  # tile of cell (0, 0); odd columns sit one tile lower
METATILES = 0x680A8                 # bank 52 $A0A8: 8 bytes = 4 tile ids (TL TR BL BR) + 4 ExRAM
BATTLE_NAMES = 0x2FC92              # bank 23 $BC92: 98 LE16 pointers ($A000-based)
BATTLE_PALETTES = 0x2BEA8           # bank 21 $9EA8: 3 BG palettes, then the sprite palette
BATTLE_PALETTE_LABELS = ["通常", "冬（推定）", "秋（推定）"]
FIELD_TERRAIN = {7: "平地", 8: "丘陵", 9: "林", 0xB: "海・湖（推定）", 0xC: "山", 0xD: "川"}
FIELD_METATILE = {7: 0, 8: 1, 9: 2, 0xB: 3, 0xC: 5, 0xD: 6}
CASTLE_METATILE = {0: 12, 1: 31, 3: 33, 4: 34, 5: 35, 6: 36, 7: 37, 8: 38, 9: 39, 0xC: 40, 0xD: 28}

# gaiji (font table SJIS EB9F-EBA6): 1.5 kanji per glyph, so longer surnames fit the name field
GAIJI = [(b"\xeb\x9f\xeb\xa0\xeb\xa1", "長宗我部"), (b"\xeb\xa2\xeb\xa0\xeb\xa1", "香宗我部"),
         (b"\xeb\xa3\xeb\xa4", "鳥屋尾"), (b"\xeb\xa5\xeb\xa6", "佐々木")]

NES_PALETTE = [int(x, 16) for x in [
    "7C7C7C", "0000FC", "0000BC", "4428BC", "940084", "A80020", "A81000", "881400", "503000", "007800", "006800",
    "005800", "004058", "000000", "000000", "000000", "BCBCBC", "0078F8", "0058F8", "6844FC", "D800CC", "E40058",
    "F83800", "E45C10", "AC7C00", "00B800", "00A800", "00A844", "008888", "000000", "000000", "000000", "F8F8F8",
    "3CBCFC", "6888FC", "9878F8", "F878F8", "F85898", "F87858", "FCA044", "F8B800", "B8F818", "58D854", "58F898",
    "00E8D8", "787878", "000000", "000000", "FCFCFC", "A4E4FC", "B8B8F8", "D8B8F8", "F8B8F8", "F8A4C0", "F0D0B0",
    "FCE0A8", "F8D878", "D8F878", "B8F8B8", "B8F8D8", "00FCFC", "F8D8F8", "000000", "000000"]]


def nes_rgb(i: int) -> tuple[int, int, int]:
    c = NES_PALETTE[i & 0x3F]
    return c >> 16, (c >> 8) & 0xFF, c & 0xFF


def text(raw: bytes) -> str:
    """SJIS (with half-width kana) up to the first 0, gaiji replaced."""
    raw = raw.split(b"\0")[0]
    for code, s in GAIJI:
        raw = raw.replace(code, s.encode("cp932"))
    return raw.decode("cp932")


def read_rom(path: str) -> bytes:
    """Read a .nes file, or the single .nes inside a .zip (as stored in roms/)."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            (name,) = [n for n in z.namelist() if n.lower().endswith(".nes")]
            return z.read(name)
    with open(path, "rb") as f:
        return f.read()


def is_composite(code: int) -> bool:
    return bool(code & 0x8000)


def decode_face_code(code: int) -> tuple[int, list[int]]:
    """Composite face code -> (head, page per slot in COMPOSITE_SLOTS order)."""
    return code & 7, [code >> bit & 3 for _, _, bit in COMPOSITE_SLOTS]


def portrait_location(f: int) -> int:
    """PRG offset of dedicated face f (60 bytes: 30 tile ids + 30 ExRAM bytes)."""
    if f < 72:
        return 0x70004 + 60 * f
    if f < 170:
        return 0x72004 + 60 * (f - 72)
    return 0x70004 + 60 * (f - 98)


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.data = read_rom(path)
        self.prg = self.data[0x10:CHR_START]
        self.chr = self.data[CHR_START:]

    def u16(self, o: int) -> int:
        return self.prg[o] | self.prg[o + 1] << 8

    # ------------------------------------------------------------ graphics

    def tile(self, exram: int, tile_id: int) -> list[list[int]]:
        o = (exram & 0x3F) * 0x1000 + tile_id * 16
        lo, hi = self.chr[o:o + 8], self.chr[o + 8:o + 16]
        return [[(lo[y] >> (7 - x) & 1) | (hi[y] >> (7 - x) & 1) << 1 for x in range(8)] for y in range(8)]

    def render_cells(self, tiles, exram, w: int, palettes: bytes, mask=None) -> bytes:
        """Tile grid -> NES colour numbers (row-major). ExRAM bits 6-7 pick the sub-palette.

        Cells with mask[i] false become 255 (transparent).
        """
        h = len(tiles) // w
        out = bytearray([255]) * (w * 8 * h * 8)
        for i, (t, e) in enumerate(zip(tiles, exram)):
            if mask is not None and not mask[i]:
                continue
            r, c = divmod(i, w)
            pal = palettes[(e >> 6) * 4:(e >> 6) * 4 + 4]
            for y, row in enumerate(self.tile(e, t)):
                for x, v in enumerate(row):
                    out[(r * 8 + y) * w * 8 + c * 8 + x] = (pal[v] if v else palettes[0]) & 0x3F
        return bytes(out)

    def palette(self, o: int = MAIN_PALETTE) -> bytes:
        return self.prg[o:o + 16]

    # ------------------------------------------------------------ faces

    def portrait_cells(self, f: int) -> tuple[list[int], list[int]]:
        o = portrait_location(f)
        return list(self.prg[o:o + 30]), list(self.prg[o + 30:o + 60])

    def composite_page(self, head: int, page: int) -> tuple[list[int], list[int]]:
        o = COMPOSITE_PAGES + (4 * head + page) * 60
        return list(self.prg[o:o + 30]), list(self.prg[o + 30:o + 60])

    def composite_areas(self, head: int) -> dict[str, list[int]]:
        """Cells (of the 5x6 grid) per slot. Eyes, nose and mouth are runs of cells; the other
        cells go to the top before the split cell and to the bottom from it on."""
        w = [self.u16(COMPOSITE_AREAS + 16 * head + 2 * i) for i in range(8)]
        areas = {sid: list(range(w[2 + 2 * k], w[2 + 2 * k] + w[3 + 2 * k]))
                 for k, sid in enumerate(["eyes", "nose", "mouth"])}
        rest = [i for i in range(30) if not any(i in a for a in areas.values())]
        return {"top": [i for i in rest if i < w[0]], "bottom": [i for i in rest if i >= w[0]], **areas}

    def composite_cells(self, code: int) -> tuple[list[int], list[int]]:
        head, pages = decode_face_code(code)
        areas = self.composite_areas(head)
        tiles, exram = [0] * 30, [0] * 30
        for (sid, _, _), page in zip(COMPOSITE_SLOTS, pages):
            cells = areas[sid]
            pt, pe = self.composite_page(head, page)
            for i in cells:
                tiles[i], exram[i] = pt[i], pe[i]
        return tiles, exram

    def face_cells(self, code: int) -> tuple[list[int], list[int]]:
        return self.composite_cells(code) if is_composite(code) else self.portrait_cells(code)

    def face_pixels(self, code: int) -> bytes:
        """40x48 NES colour numbers."""
        return self.render_cells(*self.face_cells(code), PORTRAIT_W, self.palette())

    # ------------------------------------------------------------ provinces

    def province_names(self) -> list[str]:
        return [text(self.prg[PROVINCE_NAMES + 13 * i:PROVINCE_NAMES + 13 * i + 5]) for i in range(PROVINCE_COUNT)]

    def province_neighbours(self, p: int) -> list[tuple[int, int]]:
        """(province, high 2 bits) per neighbour."""
        o = PROVINCE_NAMES + 13 * p + 6
        out = []
        for b in self.prg[o:o + 7]:
            if b == 0xFF:
                break
            out.append((b & 0x3F, b >> 6))
        return out

    # ------------------------------------------------------------ scenarios

    def bank(self, s: int) -> int:
        return SCENARIOS[s][1] * BANK

    def name_record(self, s: int, i: int) -> dict:
        o = SCENARIOS[s][2] * BANK + NAME_START + NAME_SIZE * i
        r = self.prg[o:o + NAME_SIZE]
        return {"family": text(r[:7]), "given": text(r[7:14]), "name": text(r[:7]) + text(r[7:14]),
                "charm": r[14], "ambition": r[15], "name_b16": r[16], "birth": BASE_YEAR + r[17],
                "face_code": r[18] | r[19] << 8}

    def scenario_info(self, s: int) -> dict:
        b = self.bank(s)
        return {"name": SCENARIOS[s][0], "year": BASE_YEAR + self.prg[b + 5], "month": self.prg[b + 6]}

    def general_index(self, ptr: int) -> int:
        return (ptr - WRAM - GENERAL_START) // GENERAL_SIZE

    def daimyo_general(self, s: int, d: int) -> int | None:
        """General index of daimyo d, None for an empty slot."""
        ptr = self.u16(self.bank(s) + DAIMYO_START + DAIMYO_SIZE * d)
        return self.general_index(ptr) if ptr else None

    def daimyos(self, s: int) -> list[dict]:
        out = []
        for d in range(DAIMYO_SLOTS):
            g = self.daimyo_general(s, d)
            if g is None:
                continue
            o = self.bank(s) + DAIMYO_START + DAIMYO_SIZE * d
            out.append({"index": d, "general": g, "name": self.name_record(s, g)["name"],
                        "raw": self.prg[o + 2:o + 32].hex(" ")})
        return out

    def provinces(self, s: int) -> list[dict]:
        names = self.province_names()
        out = []
        for p in range(PROVINCE_COUNT):
            o = self.bank(s) + PROVINCE_START + PROVINCE_SIZE * p
            r = self.prg[o:o + PROVINCE_SIZE]

            def w(i, r=r):
                return r[i] | r[i + 1] << 8
            owner = (w(22) - WRAM - DAIMYO_START) // DAIMYO_SIZE if w(22) else None
            members, ptr = [], w(0)
            while ptr:
                g = self.general_index(ptr)
                members.append(g)
                ptr = self.u16(self.bank(s) + GENERAL_START + GENERAL_SIZE * g)
            out.append({"index": p, "name": names[p], "owner": owner, "gold": w(4), "rice": w(6), "kokudaka": w(8),
                        "flood": r[10], "town": w(11), "culture": r[13], "tech": w(14), "soldier_loyalty": r[16],
                        "castle": w(17), "soldiers": w(24), "guns": w(26), "training": r[28], "people_loyalty": r[29],
                        "generals": members, "ptr2": w(2), "raw19_21": r[19:22].hex(" "), "raw30_31": r[30:32].hex(" ")})
        return out

    def generals(self, s: int) -> list[dict]:
        """Generals present at the start of scenario s (index = slot = name index)."""
        b, info = self.bank(s), self.scenario_info(s)
        out = []
        for i in range(SCENARIOS[s][3]):
            r = self.prg[b + GENERAL_START + GENERAL_SIZE * i:b + GENERAL_START + GENERAL_SIZE * (i + 1)]
            nm = self.name_record(s, i)
            out.append({"index": i, **nm, "age": info["year"] - nm["birth"], "politics": r[4], "war": r[5],
                        "culture": r[6], "flags": r[7], "b8": r[8], "province": r[10], "daimyo": r[11],
                        "loyalty": r[12]})
        return out

    def later_generals(self, s: int) -> list[dict]:
        """Generals that appear during scenario s (name index 256 + k)."""
        o, out = SCENARIOS[s][4], []
        while self.prg[o] != 0:
            r = self.prg[o:o + LATER_SIZE]
            k = len(out)
            nm = self.name_record(s, LATER_FIRST + k)
            out.append({"index": LATER_FIRST + k, **nm, "appear": BASE_YEAR + r[0],
                        "province": None if r[1] == 0xFF else r[1], "b2": r[2], "politics": r[3], "war": r[4],
                        "culture": r[5], "flags": r[6], "b7": r[7]})
            o += LATER_SIZE
        return out

    def renamed(self, s: int) -> list[dict]:
        """Name records 250-255 that hold later names of start generals (徳川家康, 豊臣秀吉)."""
        out = []
        for i in range(SCENARIOS[s][3], LATER_FIRST):
            nm = self.name_record(s, i)
            if nm["name"]:
                out.append({"index": i, **nm})
        return out

    def tea(self, s: int) -> list[dict]:
        name_bank = SCENARIOS[s][2] * BANK
        names_at = name_bank + NAME_START + NAME_SIZE * (LATER_FIRST + len(self.later_generals(s))) + NAME_SIZE
        out = []
        for t in range(TEA_COUNT):
            o = self.bank(s) + TEA_START + TEA_SIZE * t
            ptr = self.u16(o + 1)
            out.append({"index": t, "name": text(self.prg[names_at + 13 * t:names_at + 13 * t + 13]),
                        "value": self.prg[o], "owner": self.general_index(ptr) if ptr else None})
        return out

    # ------------------------------------------------------------ big map

    def map_pixels(self) -> bytes:
        """240 x 208 NES colour numbers."""
        n = MAP_W * MAP_H
        return self.render_cells(self.prg[MAP_TILES:MAP_TILES + n], self.prg[MAP_EXRAM:MAP_EXRAM + n], MAP_W,
                                 self.palette())

    # ------------------------------------------------------------ battle maps

    def battle_names(self) -> tuple[list[str], list[str]]:
        """(field names for the 48 provinces, castle names for the 49 castle maps)."""
        names = []
        for i in range(98):
            p = self.u16(BATTLE_NAMES + 2 * i) - 0xA000 + 23 * BANK
            names.append(text(self.prg[p:p + 16]))
        return names[:48], names[49:98]

    def battle_terrain(self, castle: bool, n: int) -> bytes:
        w, base = (CASTLE_W, CASTLE_MAPS) if castle else (FIELD_W, FIELD_MAPS)
        return self.prg[base + n * w * BATTLE_H:base + (n + 1) * w * BATTLE_H]

    def castle_layer(self, n: int) -> bytes:
        return self.prg[CASTLE_LAYER + n * CASTLE_W * BATTLE_H:CASTLE_LAYER + (n + 1) * CASTLE_W * BATTLE_H]

    def battle_metatiles(self, castle: bool, n: int) -> list[int]:
        """Metatile per cell (row-major) as drawn by bank 23 $A42F."""
        w = CASTLE_W if castle else FIELD_W
        terrain = self.battle_terrain(castle, n)
        table, water = (CASTLE_METATILE, (0, 0xD)) if castle else (FIELD_METATILE, (0xB, 0xD))
        out = []
        for i, v in enumerate(terrain):
            t = v & 0xF
            m = table[t]
            if t in (0xB, 0xD) and (i < w or terrain[i - w] & 0xF in water):
                m += 1  # the water continues from the cell above
            out.append(m)
        return out

    def battle_screen(self, castle: bool, n: int) -> tuple[bytes, bytes]:
        """32x30 tile ids and ExRAM bytes of the battle screen (before units and texts are drawn)."""
        base = CASTLE_SCREEN if castle else FIELD_SCREEN
        tiles, exram = bytearray(self.prg[base:base + 960]), bytearray(self.prg[base + 960:base + 1920])
        w = CASTLE_W if castle else FIELD_W
        x0, y0 = CASTLE_ORIGIN if castle else FIELD_ORIGIN
        for i, m in enumerate(self.battle_metatiles(castle, n)):
            r, c = divmod(i, w)
            mt = self.prg[METATILES + 8 * m:METATILES + 8 * m + 8]
            for k, (dy, dx) in enumerate([(0, 0), (0, 1), (1, 0), (1, 1)]):
                a = (y0 + 2 * r + (c & 1) + dy) * 32 + x0 + 2 * c + dx
                tiles[a], exram[a] = mt[k], mt[4 + k]
        return bytes(tiles), bytes(exram)

    def battle_palette(self, season: int = 0) -> bytes:
        return self.prg[BATTLE_PALETTES + 16 * season:BATTLE_PALETTES + 16 * season + 16]

    def battle_pixels(self, castle: bool, n: int, season: int = 0) -> bytes:
        """256x240 NES colour numbers of the whole battle screen."""
        return self.render_cells(*self.battle_screen(castle, n), 32, self.battle_palette(season))
