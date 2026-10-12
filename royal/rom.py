"""FC ロイヤルブラッド (KOEI, 1991; NES: Gemfire) ROM decoding.

All offsets are PRG offsets (file offset - 0x10). See royal/docs/ROM_FORMAT.md.
"""
import os
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Royal Blood (Japan).zip")

PRG_SIZE = 0x40000
CHR_START = 0x10 + PRG_SIZE
BANK = 0x2000


def read_rom(path: str) -> bytes:
    """Read a .nes file, or the single .nes inside a .zip (as stored in roms/)."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            (name,) = [n for n in z.namelist() if n.lower().endswith(".nes")]
            return z.read(name)
    with open(path, "rb") as f:
        return f.read()


def kana(raw: bytes) -> str:
    """Half-width katakana (cp932 A6-DF) up to the first 0 byte, as full-width text."""
    raw = raw.split(b"\0")[0]
    return unicodedata.normalize("NFKC", raw.decode("cp932", errors="replace"))
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


# ---------------------------------------------------------------- scenarios (bank 18: 4 x 0x800, copied to WRAM $6000)
SCENARIO_BANK_OFFSET = 0x24000      # scenario s at + 0x800 * s; the game copies it to $6000-$67FF (WRAM page 0)
SCENARIO_SIZE = 0x800
SCENARIO_NAMES = ["エランとレッドワルト", "フェリアス家のきき", "ティリアンの戦い", "ロイヤルブラッド"]
WRAM = 0x6000
YEAR_OFFSET = 0x06                  # years since scenario 1 (0, 5, 10, 15)
HOUSE_START, HOUSE_SIZE, HOUSE_SLOTS = 0x35, 4, 30   # (house id, lord, controller, flag bits)
CHAR_START, CHAR_SIZE, CHAR_COUNT = 0xAD, 10, 64
PROVINCE_START, PROVINCE_SIZE, PROVINCE_COUNT = 0x32D, 36, 30
UNIT_SLOTS = 5                      # province +16: 5 x (unit type, strength LE16, unknown); FF = empty

# ---------------------------------------------------------------- name tables (bank 19)
CHAR_NAMES = 0x26004                # 64 x 14: name (10), 0, age base, 0, unknown
PROVINCE_NAMES = 0x26384            # 30 x 21: name (11), 8 neighbours (0-based, FF = none), map label x, y
UNIT_NAMES = 0x265FA                # 23 x 18: name (10), 8 bytes (+3 = max HP)
HOUSE_NAMES = 0x26798               # 41 x 11 (family names; ids 0-10 are the houses that rule provinces)
HOUSE_NAME_COUNT = 41
UNIT_COUNT = 23
UNIT_LABELS = 0x1A5CA               # bank 13 ($A5CA): 27 LE16 pointers ($A000 = bank 13) to battle labels:
                                    # 4 army units (重装騎兵 重装歩兵 長弓兵 重装歩兵) then the 23 units above

# ---------------------------------------------------------------- faces (bank 21, CHR 4 KB banks 16-26)
PORTRAIT_W, PORTRAIT_H = 5, 6       # tiles
FACE_TABLES = [                     # (tile ids, ExRAM bytes, count): 30 bytes per face each
    (0x2A004, 0x2A784, 64),         # characters (face = character index); $DB3B in bank 30
    (0x2AF04, 0x2AF7C, 4),          # extra faces
    (0x2AFF4, 0x2B2A6, 23),         # units (same order as UNIT_NAMES)
]
UI_PALETTE = 0x3F070                # bank 31 $F070: BG palette of the strategy screens (faces, map)

# ---------------------------------------------------------------- strategy map (bank 20)
MAP_TILES, MAP_EXRAM = 0x286E8, 0x287F2   # 14 x 19 cells, drawn at name table (16, 4)
MAP_W, MAP_H = 14, 19

# ---------------------------------------------------------------- battle maps
BATTLE_GRIDS = 0x26A66              # bank 19: 30 x 80 (10 x 8 cells, row-major); high nibble = terrain
BATTLE_W, BATTLE_H = 10, 8
BATTLE_ORIGIN = (6, 7)              # name table tile of cell (0, 0); cells are 2 x 2 tiles
BATTLE_WRAM = 0x0860                # WRAM page 0 offset ($6860) the grid is copied to; low nibble = unit 1-10
METATILES = 0x2E6D6                 # bank 23: 16 x 4 tile ids (TL TR BL BR), then 16 x 4 ExRAM bytes
BATTLE_PALETTE = 0x13DD0            # bank 9: BG palette of battles ($13DE0 = sprites)
TERRAIN = {0: "平地", 1: "?", 2: "守方本陣", 3: "攻方本陣", 4: "林", 5: "丘", 6: "山",
           12: "城門", 13: "城牆", 14: "城角(上)", 15: "城角(下)"}

STATUS = {1: "当主", 2: "家臣", 4: "在野"}
PROVINCE_STATS = [("gold", "金"), ("food", "食料"), ("men", "兵")]
PROVINCE_RATES = [("land", "開発(山形圖示)"), ("crops", "作物"), ("loyalty", "民忠(心形圖示)")]


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

    def render_cells(self, tiles, exram, w: int, palettes: bytes) -> bytes:
        """Tile grid -> NES colour numbers (row-major). ExRAM bits 6-7 pick the sub-palette."""
        h = len(tiles) // w
        out = bytearray(w * 8 * h * 8)
        for i, (t, e) in enumerate(zip(tiles, exram)):
            r, c = divmod(i, w)
            pal = palettes[(e >> 6) * 4:(e >> 6) * 4 + 4]
            for y, row in enumerate(self.tile(e, t)):
                for x, v in enumerate(row):
                    out[(r * 8 + y) * w * 8 + c * 8 + x] = (pal[v] if v else palettes[0]) & 0x3F
        return bytes(out)

    def palette(self, o: int = UI_PALETTE) -> bytes:
        return self.prg[o:o + 16]

    # ------------------------------------------------------------ faces

    @staticmethod
    def face_location(table: int, f: int) -> tuple[int, int]:
        t, e, n = FACE_TABLES[table]
        assert 0 <= f < n
        return t + 30 * f, e + 30 * f

    def face_cells(self, table: int, f: int) -> tuple[bytes, bytes]:
        t, e = self.face_location(table, f)
        return self.prg[t:t + 30], self.prg[e:e + 30]

    def face_pixels(self, table: int, f: int) -> bytes:
        """40x48 NES colour numbers."""
        return self.render_cells(*self.face_cells(table, f), PORTRAIT_W, self.palette())

    # ------------------------------------------------------------ names

    def char_name(self, i: int) -> dict:
        o = CHAR_NAMES + 14 * i
        r = self.prg[o:o + 14]
        return {"name": kana(r[:10]), "age_base": r[11], "name_unknown": r[13]}

    def province_info(self, p: int) -> dict:
        o = PROVINCE_NAMES + 21 * p
        r = self.prg[o:o + 21]
        return {"name": kana(r[:11]), "neighbours": [x for x in r[11:19] if x != 0xFF], "label": (r[19], r[20])}

    def house_name(self, h: int) -> str:
        return kana(self.prg[HOUSE_NAMES + 11 * h:HOUSE_NAMES + 11 * h + 11])

    def unit_labels(self) -> list[str]:
        """Battle labels; the 5th-unit ones start with the control bytes 1B 4B."""
        out = []
        for k in range(4 + UNIT_COUNT):
            o = self.u16(UNIT_LABELS + 2 * k) - 0xA000 + 13 * BANK
            out.append(kana(self.prg[o:o + 16].removeprefix(b"\x1bK")))
        return out

    def units(self) -> list[dict]:
        out = []
        for u in range(UNIT_COUNT):
            r = self.prg[UNIT_NAMES + 18 * u:UNIT_NAMES + 18 * u + 18]
            out.append({"id": u, "name": kana(r[:10]), "a": r[11], "b": r[12], "hp": r[13], "c": r[15],
                        "d": r[16], "e": r[17], "raw": r[10:].hex(" ")})
        return out

    # ------------------------------------------------------------ scenarios

    def scenario(self, s: int) -> bytes:
        o = SCENARIO_BANK_OFFSET + SCENARIO_SIZE * s
        return self.prg[o:o + SCENARIO_SIZE]

    def year_offset(self, s: int) -> int:
        return self.scenario(s)[YEAR_OFFSET]

    def houses(self, s: int) -> list[dict]:
        b, out = self.scenario(s), []
        for k in range(HOUSE_SLOTS):
            h, lord, ctrl, bits = b[HOUSE_START + 4 * k:HOUSE_START + 4 * k + 4]
            if h != 0xFF:
                out.append({"id": h, "name": self.house_name(h), "lord": lord, "controller": ctrl, "bits": bits})
        return out

    def characters(self, s: int) -> list[dict]:
        """Present characters of scenario s (slot = character / face index)."""
        b, out = self.scenario(s), []
        off = self.year_offset(s)
        for i in range(CHAR_COUNT):
            r = b[CHAR_START + CHAR_SIZE * i:CHAR_START + CHAR_SIZE * (i + 1)]
            if r[5] == 0xFF:
                continue
            n = self.char_name(i)
            out.append({"id": i, **n, "age": n["age_base"] + off + 1, "int": r[2], "war": r[3], "charm": r[4],
                        "province": r[5], "house": r[6], "status": r[7],
                        "blood": None if r[8] == 0xFF else r[8], "lord_value": r[9]})
        return out

    def provinces(self, s: int) -> list[dict]:
        b, out = self.scenario(s), []
        for p in range(PROVINCE_COUNT):
            r = b[PROVINCE_START + PROVINCE_SIZE * p:PROVINCE_START + PROVINCE_SIZE * (p + 1)]
            units = []
            for k in range(UNIT_SLOTS):
                t, lo, hi, lv = r[16 + 4 * k:20 + 4 * k]
                if t != 0xFF:
                    units.append({"type": t, "hp": lo | hi << 8, "level": lv})
            out.append({"id": p, **self.province_info(p), "gold": r[2] | r[3] << 8, "food": r[4] | r[5] << 8,
                        "men": r[6] | r[7] << 8, "land": r[8], "crops": r[9], "loyalty": r[10],
                        "flags": r[11:14].hex(" "), "owner": None if r[14] == 0xFF else r[14], "units": units})
        return out

    # ------------------------------------------------------------ strategy map

    def map_cells(self) -> tuple[bytes, bytes]:
        n = MAP_W * MAP_H
        return self.prg[MAP_TILES:MAP_TILES + n], self.prg[MAP_EXRAM:MAP_EXRAM + n]

    def map_pixels(self) -> bytes:
        """112 x 152 NES colour numbers (without the province numbers and house markers the game draws over it)."""
        return self.render_cells(*self.map_cells(), MAP_W, self.palette())

    # ------------------------------------------------------------ battle maps

    def battle_grid(self, p: int) -> bytes:
        o = BATTLE_GRIDS + BATTLE_W * BATTLE_H * p
        return self.prg[o:o + BATTLE_W * BATTLE_H]

    def metatile(self, v: int) -> tuple[bytes, bytes]:
        t = v >> 4
        return self.prg[METATILES + 4 * t:METATILES + 4 * t + 4], self.prg[METATILES + 64 + 4 * t:METATILES + 68 + 4 * t]

    def battle_cells(self, p: int) -> tuple[bytes, bytes]:
        """20 x 16 tile ids and ExRAM bytes of the battlefield of province p (no units)."""
        w = BATTLE_W * 2
        tiles, exram = bytearray(w * BATTLE_H * 2), bytearray(w * BATTLE_H * 2)
        for i, v in enumerate(self.battle_grid(p)):
            r, c = divmod(i, BATTLE_W)
            t, e = self.metatile(v)
            for k in range(4):
                a = (2 * r + k // 2) * w + 2 * c + k % 2
                tiles[a], exram[a] = t[k], e[k]
        return bytes(tiles), bytes(exram)

    def battle_pixels(self, p: int) -> bytes:
        """160 x 128 NES colour numbers."""
        return self.render_cells(*self.battle_cells(p), BATTLE_W * 2, self.palette(BATTLE_PALETTE))
