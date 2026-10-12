"""FC 信長の野望・戦国群雄伝 (KOEI, 1990) ROM decoding.

All offsets are PRG offsets (file offset - 0x10). See gunyuu/docs/ROM_FORMAT.md.
"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Nobunaga no Yabou - Sengoku Gunyuu Den (Japan).zip")

PRG_SIZE = 0x40000
CHR_START = 0x10 + PRG_SIZE
BANK = 0x2000

# ---------------------------------------------------------------- scenarios (data bank copied to WRAM $6000)
SCENARIOS = [  # (name, data bank, name bank)
    ("群雄割拠", 26, 24),
    ("信長の野望", 27, 25),
]
SCENARIO_COUNT = len(SCENARIOS)
WRAM = 0x6000
BASE_YEAR = 1480                    # years are stored as year - 1480
PROVINCE_COUNT = 38
PROVINCE_START, PROVINCE_SIZE = 0x04D, 25
DAIMYO_START, DAIMYO_SIZE = 0x403, 46
GENERAL_START, GENERAL_SIZE = 0xAD8, 14
GENERAL_SLOTS = 255
NAME_START, NAME_SIZE = 4, 22       # name bank: 22 bytes per general slot

PROVINCE_NAMES = 0x2E004            # bank 23: 38 x 30 bytes = name (9), 7 neighbour ptrs, 7 flag bytes

# ---------------------------------------------------------------- faces
PORTRAIT_W, PORTRAIT_H = 5, 6       # tiles
PORTRAIT_COUNT = 90                 # dedicated face ids 0-89 (60-64 unused); codes 90-0x7FFF draw nothing
FACE_TABLE_A = 0x28004              # bank 20 $A004: ids 0-59 at + 30 * id, ExRAM bytes + 65 * 30 further
FACE_TABLE_B = 0x23AC6              # bank 18 ($9AC6 with bank 18 at $A000): ids 60-89 at + 30 * id, ExRAM + 25 * 30
FACE_PALETTE = 0x28F40              # bank 20 $8F40: BG palette of the face (sub-palettes 0-1 used)
COMPOSITE_PARTS = 0x24004           # bank 18: 120 LE16 tile pointers then 120 ExRAM pointers ($A000 = bank 20)
# per group: (cell of the eyes' left end, part width): the eyes fill that row, the nose the next row,
# the mouth the rows below it (width x rows = its length). From the switch on the group in $CFDE.
COMPOSITE_LAYOUT = [(12, 3), (10, 3), (11, 3), (11, 4), (12, 3), (11, 4)]
# (slot id, label, code bit): each slot takes 3 bits of the face code = variant 0-4
COMPOSITE_SLOTS = [("head", "頭", 9), ("eyes", "眼", 6), ("nose", "鼻", 3), ("mouth", "口", 0)]
COMPOSITE_GROUPS = 6                # face code bits 12-14

# ---------------------------------------------------------------- big map
MAP_SCREENS = (0x26F04, 0x26004)    # bank 19: west and east halves, 32x30 tile ids then 32x30 ExRAM each
MAP_MIDDLE = 0x26784                # bank 19: same layout, columns 16-47 of the whole map (used while scrolling)
MAP_W, MAP_H = 64, 30
MAP_PALETTE = 0x03007               # bank 1: BG palette of the map screen

# ---------------------------------------------------------------- battle maps
BATTLE_W, BATTLE_H = 13, 12         # cells; row-major, one byte per cell
FIELD_MAPS = 0x2A004                # bank 21: 38 x 156 bytes (one per province)
CASTLE_MAPS = 0x2C004               # bank 22: 38 x 156 bytes
METATILE_EXRAM = 0x2B72C            # bank 21 $B72C: 4 ExRAM bytes (TL TR BL BR) per metatile
BATTLE_ORIGIN = (3, 2)              # tile of cell (0, 0); odd columns sit one tile lower
BATTLE_PALETTE = 0x2BC5C            # bank 21 $BC5C: BG palette of field and castle battles ($BC7C = sprites)

# gaiji (SJIS EB9F-EBA8): the game draws these as narrow glyphs so long surnames fit
GAIJI = [(b"\xeb\x9f\xeb\xa0\xeb\xa1", "長宗我部"), (b"\xeb\xa2\xeb\xa0\xeb\xa1", "香宗我部"),
         (b"\xeb\xa3\xeb\xa4", "野々村"), (b"\xeb\xa5\xeb\xa6", "板部岡"), (b"\xeb\xa7\xeb\xa8", "鳥屋尾")]

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
    """SJIS up to the first 0, gaiji replaced."""
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
    """Composite face code -> (group, variant per slot in COMPOSITE_SLOTS order)."""
    return code >> 12 & 7, [code >> bit & 7 for _, _, bit in COMPOSITE_SLOTS]


def portrait_location(f: int) -> int:
    """PRG offset of the 30 tile ids of dedicated face f (the ExRAM bytes follow the whole table)."""
    return (FACE_TABLE_A if f < 60 else FACE_TABLE_B) + 30 * f


def portrait_exram_location(f: int) -> int:
    return portrait_location(f) + (65 * 30 if f < 60 else 25 * 30)


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.data = read_rom(path)
        self.prg = self.data[0x10:CHR_START]
        self.chr = self.data[CHR_START:]

    def u16(self, o: int) -> int:
        return self.prg[o] | self.prg[o + 1] << 8

    # ------------------------------------------------------------ graphics

    def tile(self, exram: int, tile_id: int) -> list[list[int]]:
        o = (exram & 0x1F) * 0x1000 + tile_id * 16  # 128 KB CHR: the 6-bit bank wraps
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

    def palette(self, o: int = FACE_PALETTE) -> bytes:
        return self.prg[o:o + 16]

    # ------------------------------------------------------------ faces

    def portrait_cells(self, f: int) -> tuple[list[int], list[int]]:
        o, e = portrait_location(f), portrait_exram_location(f)
        return list(self.prg[o:o + 30]), list(self.prg[e:e + 30])

    def composite_part(self, group: int, slot: int, variant: int) -> tuple[list[int], list[int]]:
        """(tile ids, ExRAM bytes) of one part. Head frames are 30 cells; eyes/nose/mouth are runs."""
        k = 20 * group + 5 * slot + variant
        t, e = self.u16(COMPOSITE_PARTS + 2 * k), self.u16(COMPOSITE_PARTS + 240 + 2 * k)
        n = e - t
        t, e = t - 0xA000 + 20 * BANK, e - 0xA000 + 20 * BANK
        return list(self.prg[t:t + n]), list(self.prg[e:e + n])

    def composite_cells(self, code: int) -> tuple[list[int], list[int]]:
        group, variants = decode_face_code(code)
        tiles, exram = self.composite_part(group, 0, variants[0])
        cell, w = COMPOSITE_LAYOUT[group]
        for slot in (1, 2, 3):
            t, e = self.composite_part(group, slot, variants[slot])
            for k in range(len(t)):
                i = cell + k // w * 5 + k % w
                tiles[i], exram[i] = t[k], e[k]
            cell += 5
        return tiles, exram

    def face_cells(self, code: int) -> tuple[list[int], list[int]]:
        return self.composite_cells(code) if is_composite(code) else self.portrait_cells(code)

    def face_pixels(self, code: int) -> bytes:
        """40x48 NES colour numbers."""
        return self.render_cells(*self.face_cells(code), PORTRAIT_W, self.palette())

    # ------------------------------------------------------------ provinces

    def province_index(self, ptr: int) -> int:
        return (ptr - WRAM - PROVINCE_START) // PROVINCE_SIZE

    # ------------------------------------------------------------ big map

    def map_cells(self) -> tuple[bytes, bytes]:
        """64x30 tile ids and ExRAM bytes of the whole map (row-major)."""
        tiles, exram = bytearray(), bytearray()
        for row in range(MAP_H):
            for o in MAP_SCREENS:
                tiles += self.prg[o + 32 * row:o + 32 * row + 32]
                exram += self.prg[o + 960 + 32 * row:o + 960 + 32 * row + 32]
        return bytes(tiles), bytes(exram)

    def map_pixels(self) -> bytes:
        """512 x 240 NES colour numbers (without the daimyo crests the game draws over it)."""
        return self.render_cells(*self.map_cells(), MAP_W, self.palette(MAP_PALETTE))

    # ------------------------------------------------------------ battle maps

    def battle_terrain(self, castle: bool, n: int) -> bytes:
        base = CASTLE_MAPS if castle else FIELD_MAPS
        return self.prg[base + n * BATTLE_W * BATTLE_H:base + (n + 1) * BATTLE_W * BATTLE_H]

    @staticmethod
    def field_load(v: int) -> int:
        """Field cell byte as the battle set-up ($AF72) leaves it in WRAM: bits 4, 5 and 7 cleared,
        bit 3 moved to bit 5. Only bits 0-2 decide the picture."""
        return v & 0x47 | (0x20 if v & 8 else 0)

    @staticmethod
    def battle_metatile(castle: bool, v: int) -> tuple[int, int]:
        """(first tile id, metatile index into METATILE_EXRAM) for a cell byte (field: as loaded)."""
        lo = v & 0xF
        if castle:
            return 4 * lo, lo + (19 if v & 0x30 else 0)
        lo &= 7
        return 0x2C + 4 * lo, 11 + lo

    def battle_screen(self, castle: bool, n: int) -> tuple[bytes, bytes]:
        """32x30 tile ids and ExRAM bytes of the battle screen (before units and windows are drawn)."""
        tiles, exram = bytearray(960), bytearray(960)
        x0, y0 = BATTLE_ORIGIN
        for i, v in enumerate(self.battle_terrain(castle, n)):
            r, c = divmod(i, BATTLE_W)
            t, m = self.battle_metatile(castle, v if castle else self.field_load(v))
            ex = self.prg[METATILE_EXRAM + 4 * m:METATILE_EXRAM + 4 * m + 4]
            for k, (dy, dx) in enumerate([(0, 0), (0, 1), (1, 0), (1, 1)]):
                a = (y0 + 2 * r + (c & 1) + dy) * 32 + x0 + 2 * c + dx
                tiles[a], exram[a] = t + k, ex[k]
        return bytes(tiles), bytes(exram)

    def battle_pixels(self, castle: bool, n: int) -> bytes:
        """256x240 NES colour numbers of the whole battle screen."""
        return self.render_cells(*self.battle_screen(castle, n), 32, self.palette(BATTLE_PALETTE))

    def province_names(self) -> list[str]:
        return [text(self.prg[PROVINCE_NAMES + 30 * i:PROVINCE_NAMES + 30 * i + 9]) for i in range(PROVINCE_COUNT)]

    def province_neighbours(self, p: int) -> list[tuple[int, int]]:
        """(province, flag byte) per neighbour."""
        o = PROVINCE_NAMES + 30 * p
        out = []
        for k in range(7):
            ptr = self.u16(o + 9 + 2 * k)
            if ptr:
                out.append((self.province_index(ptr), self.prg[o + 23 + k]))
        return out

    # ------------------------------------------------------------ scenarios

    def bank(self, s: int) -> int:
        return SCENARIOS[s][1] * BANK

    def scenario_info(self, s: int) -> dict:
        b = self.bank(s)
        return {"name": SCENARIOS[s][0], "year": BASE_YEAR + self.prg[b + 8], "header": self.prg[b:b + 0x4D].hex(" ")}

    def name_record(self, s: int, i: int) -> dict:
        o = SCENARIOS[s][2] * BANK + NAME_START + NAME_SIZE * i
        r = self.prg[o:o + NAME_SIZE]
        return {"family": text(r[:7]), "given": text(r[7:14]), "name": text(r[:7]) + text(r[7:14]),
                "birth": BASE_YEAR + r[14], "appear": BASE_YEAR + r[15], "death": BASE_YEAR + r[16],
                "name_raw17_19": r[17:20].hex(" "), "face_code": r[20] | r[21] << 8}

    def general_index(self, ptr: int) -> int:
        return (ptr - WRAM - GENERAL_START) // GENERAL_SIZE

    def daimyo_index(self, ptr: int) -> int:
        return (ptr - WRAM - DAIMYO_START) // DAIMYO_SIZE

    def daimyos(self, s: int) -> list[dict]:
        out = []
        b = self.bank(s)
        d = 0
        while True:
            o = b + DAIMYO_START + DAIMYO_SIZE * d
            ptr = self.u16(o)
            if not ptr:
                break
            g = self.general_index(ptr)
            r = self.prg[o:o + DAIMYO_SIZE]
            out.append({"index": d, "general": g, "name": self.name_record(s, g)["name"],
                        "allies": [x for x in r[2:5] if x != 0xFF], "relations": list(r[5:43]),
                        "raw43_45": r[43:46].hex(" ")})
            d += 1
        return out

    def provinces(self, s: int) -> list[dict]:
        names, b = self.province_names(), self.bank(s)
        out = []
        for p in range(PROVINCE_COUNT):
            o = b + PROVINCE_START + PROVINCE_SIZE * p
            r = self.prg[o:o + PROVINCE_SIZE]

            def w(i, r=r):
                return r[i] | r[i + 1] << 8
            out.append({"index": p, "name": names[p], "owner": self.daimyo_index(w(20)) if w(20) else None,
                        "lord": self.general_index(w(22)) if w(22) else None, "gold": w(4), "rice": w(6),
                        "kokudaka": w(8), "flood": r[10], "town": w(11), "b13": w(13), "soldiers": w(15),
                        "people_loyalty": r[17], "castle": w(18), "b24": r[24]})
        return out

    def generals(self, s: int) -> list[dict]:
        """All 255 general slots of scenario s (index = slot = name index); empty names are skipped."""
        b, info = self.bank(s), self.scenario_info(s)
        out = []
        for i in range(GENERAL_SLOTS):
            nm = self.name_record(s, i)
            if not nm["name"]:
                continue
            r = self.prg[b + GENERAL_START + GENERAL_SIZE * i:b + GENERAL_START + GENERAL_SIZE * (i + 1)]
            out.append({"index": i, **nm, "age": info["year"] - nm["birth"], "politics": r[2], "war": r[3],
                        "charm": r[4], "ambition": r[5], "b6": r[6], "province": r[7],
                        "daimyo": None if r[8] == 0xFF else r[8], "loyalty": r[9], "soldiers": r[10] * 100,
                        "training": r[11], "arms": r[12], "unit": r[13] & 3, "flags": r[13]})
        return out
