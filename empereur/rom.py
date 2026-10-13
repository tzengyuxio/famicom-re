"""FC ランペルール (KOEI, 1991) ROM decoding.

All offsets are PRG offsets (file offset - 0x10). See empereur/docs/ROM_FORMAT.md.
"""
import os
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Empereur, L' (Japan).zip")

PRG_SIZE = 0x40000
CHR_START = 0x10 + PRG_SIZE
BANK = 0x2000

# Master tables (bank 26)
COUNTRY_TABLE = 0x34004       # 15 x 9 bytes: name (8), flags
COUNTRY_COUNT, COUNTRY_SIZE = 15, 9
CITY_TABLE = 0x3408B          # 46 x 31 bytes
CITY_COUNT, CITY_SIZE = 46, 31
CHAR_TABLE = 0x3461D          # 255 x 16 bytes
CHAR_COUNT, CHAR_SIZE = 255, 16

# Scenarios: scenario n (1-4) in PRG bank 21 + n, each starting with "4C 00 00 00"
SCENARIO_FIRST_BANK = 22
SCENARIOS = [(1796, "ナポレオンとうじょう"), (1798, "けんりょくへのいし"),
             (1802, "かくめいのしゅうけつ"), (1806, "ていこくのえいこう")]
SC_CHAR_START, SC_CHAR_SIZE = 0x8, 15
SC_COUNTRY_START, SC_COUNTRY_SIZE = 0xEF9, 18
SC_CITY_START, SC_CITY_SIZE = 0x1007, 28

GRADES = "DCBA"
# Scenario character status byte 11 (inferred from who carries it)
STATUS_NAMES = {0: "未登場", 1: "王族", 3: "將軍", 4: "軍團長", 5: "司令", 6: "政治家", 7: "君主", 15: "退場"}
ABILITIES = [("政治", 1, 0), ("経済", 1, 2), ("補給", 1, 4), ("建設", 1, 6),
             ("統率", 2, 0), ("歩兵", 2, 2), ("騎兵", 2, 4), ("砲兵", 2, 6)]  # (name, byte, shift)
PERSONALITY = [("単純", 7), ("冷静", 6), ("臆病", 5), ("勇気", 4), ("魅力", 3), ("幸運", 2)]

# Faces
PORTRAIT_TABLE = 0x1E956      # bank 15 $A956: 30 tile ids + 30 ExRAM bytes per portrait, 5x6 tiles
PORTRAIT_COUNT = 90           # codes 0-89 (characters use 0 and 3-89)
PORTRAIT_W, PORTRAIT_H = 5, 6
PARTS_BANK = 0x26000          # bank 19 mapped at $A000
# Composite face parts: (code shift, record base, per-category stride, record width,
#                        placement cell per category, drawn width per category)
COMPOSITE_PARTS = {
    "top": (2, 0xB5AE, 0x78, 15, (0, 0, 0, 0), (15, 15, 15, 15)),
    "bottom": (4, 0xB78E, 0x78, 15, (15, 15, 15, 15), (15, 15, 15, 15)),
    "eyes": (6, 0xB96E, 0x18, 3, (11, 12, 10, 11), (3, 3, 3, 3)),
    "nose": (8, 0xB9CE, 0x10, 2, (17, 18, 16, 17), (1, 2, 1, 1)),
    "mouth": (10, 0xBA0E, 0x18, 3, (22, 23, 21, 21), (1, 2, 2, 3)),
}
FACE_PALETTE = 0x26014        # bank 19 $A014: BG palette of the command screen (face window)

# World map: 3x3 blocks (widths 9/10/9, 6 rows each) drawn by svc 9 from bank 19
MAP_BLOCK_PTRS = 0x1E8D       # bank 0: 9 tile pointers then 9 ExRAM pointers ($A000-relative, bank 19)
MAP_BLOCK_W = (9, 10, 9)
MAP_BLOCK_H = 6
MAP_W, MAP_H = 28, 18
MAP_VIEWS = 0x1EB1            # bank 0: 4 views x 4 block indices (2x2 blocks on screen)
MAP_PALETTE = 0x26004         # bank 19 $A004

# NES 2C02 palette (common emulator approximation), index = NES colour number
NES_PALETTE = [int(x, 16) for x in ["7C7C7C", "0000FC", "0000BC", "4428BC", "940084", "A80020", "A81000", "881400", "503000", "007800", "006800", "005800", "004058", "000000", "000000", "000000", "BCBCBC", "0078F8", "0058F8", "6844FC", "D800CC", "E40058", "F83800", "E45C10", "AC7C00", "00B800", "00A800", "00A844", "008888", "000000", "000000", "000000", "F8F8F8", "3CBCFC", "6888FC", "9878F8", "F878F8", "F85898", "F87858", "FCA044", "F8B800", "B8F818", "58D854", "58F898", "00E8D8", "787878", "000000", "000000", "FCFCFC", "A4E4FC", "B8B8F8", "D8B8F8", "F8B8F8", "F8A4C0", "F0D0B0", "FCE0A8", "F8D878", "D8F878", "B8F8B8", "B8F8D8", "00FCFC", "F8D8F8", "000000", "000000"]]


def nes_rgb(i: int) -> tuple[int, int, int]:
    c = NES_PALETTE[i & 0x3F]
    return c >> 16, (c >> 8) & 0xFF, c & 0xFF


def text(raw: bytes) -> str:
    """Names: half-width katakana (cp932), 0-padded. Leading control bytes are not part of the name."""
    raw = raw.split(b"\0")[0]
    return unicodedata.normalize("NFKC", raw.decode("cp932")).replace("-", "ー")


def grade(v: int) -> str:
    return GRADES[v & 3]


def read_rom(path: str) -> bytes:
    """Read a .nes file, or the single .nes inside a .zip (as stored in roms/)."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            (name,) = [n for n in z.namelist() if n.lower().endswith(".nes")]
            return z.read(name)
    with open(path, "rb") as f:
        return f.read()


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.data = read_rom(path)
        assert self.data[:4] == b"NES\x1a" and self.data[4] == 16 and self.data[5] == 16, "not the expected ROM"
        self.prg = self.data[0x10:CHR_START]
        self.chr = self.data[CHR_START:]

    def u16(self, o: int) -> int:
        return self.prg[o] | self.prg[o + 1] << 8

    # ------------------------------------------------------------ master tables

    def countries(self) -> list[dict]:
        out = []
        for i in range(COUNTRY_COUNT):
            r = self.prg[COUNTRY_TABLE + i * COUNTRY_SIZE:COUNTRY_TABLE + (i + 1) * COUNTRY_SIZE]
            out.append({"id": i, "name": text(r[:8]), "flags": r[8]})
        return out

    def cities(self) -> list[dict]:
        out = []
        for i in range(CITY_COUNT):
            r = self.prg[CITY_TABLE + i * CITY_SIZE:CITY_TABLE + (i + 1) * CITY_SIZE]
            out.append({
                "id": i, "name": text(r[:12]),
                "unk12": r[12],
                "map_x": r[13], "map_y": r[18],            # label cell on the 28x18 world map
                "view_x": list(r[14:18]), "view_y": list(r[19:23]),  # per-view positions (inferred)
                "neighbors": [n for n in r[23:30] if n != 0xFF],
                "flags": r[30],
            })
        return out

    def characters(self) -> list[dict]:
        out = []
        for i in range(CHAR_COUNT):
            r = self.prg[CHAR_TABLE + i * CHAR_SIZE:CHAR_TABLE + (i + 1) * CHAR_SIZE]
            out.append({
                "id": i, "name": text(r[:12]),
                "face_code": r[12] | r[13] << 8,
                "personality": [name for name, bit in PERSONALITY if r[14] >> bit & 1],
                "pers_byte": r[14],
                "unk15": r[15],
            })
        return out

    # ------------------------------------------------------------ scenarios

    def scenario_base(self, s: int) -> int:
        return (SCENARIO_FIRST_BANK + s - 1) * BANK

    def scenario_characters(self, s: int) -> list[dict]:
        base = self.scenario_base(s) + SC_CHAR_START
        out = []
        for i in range(CHAR_COUNT):
            r = self.prg[base + i * SC_CHAR_SIZE:base + (i + 1) * SC_CHAR_SIZE]
            out.append({
                "id": i, "city": r[0],
                **{name: grade(r[b] >> sh) for name, b, sh in ABILITIES},
                "unk3": r[3], "loyalty": r[4], "age": r[5] - 256 if r[5] >= 0x80 else r[5],
                "infantry": r[6], "cavalry": r[7], "artillery": r[8],
                "morale": r[9], "training": r[10],
                "status": r[11], "unk12": r[12] | r[13] << 8,
                "nation": r[14],
            })
        return out

    def scenario_countries(self, s: int) -> list[dict]:
        base = self.scenario_base(s) + SC_COUNTRY_START
        out = []
        for i in range(COUNTRY_COUNT):
            r = self.prg[base + i * SC_COUNTRY_SIZE:base + (i + 1) * SC_COUNTRY_SIZE]
            out.append({"id": i, "unk0": r[0:5].hex(), "gold": r[5] | r[6] << 8, "food": r[7] | r[8] << 8,
                        "unk9": r[9] | r[10] << 8, "unk11": r[11:18].hex()})
        return out

    def scenario_cities(self, s: int) -> list[dict]:
        base = self.scenario_base(s) + SC_CITY_START
        out = []
        for i in range(CITY_COUNT):
            r = self.prg[base + i * SC_CITY_SIZE:base + (i + 1) * SC_CITY_SIZE]
            out.append({
                "id": i, "unk0": r[0], "owner": r[1], "population": r[2] | r[3] << 8,
                "hospital": r[4], "industry": r[5], "commerce": r[6], "agriculture": r[7],
                "food_supply": r[8], "goods_supply": r[9], "hygiene": r[10],
                "gold": r[11] | r[12] << 8, "food": r[13] | r[14] << 8, "goods": r[15] | r[16] << 8,
                "reserve_soldiers": r[17], "reserve_horses": r[18], "reserve_cannons": r[19],
                "unk20": r[20:23].hex(), "ships": r[23], "flags": r[24], "unk25": r[25:28].hex(),
            })
        return out

    # ------------------------------------------------------------ graphics

    def tile(self, exram: int, tile_id: int) -> list[list[int]]:
        """8x8 2bpp tile; ExRAM bits 0-5 select the 4KB CHR bank (MMC5 extended attribute mode)."""
        o = (exram & 0x3F) * 0x1000 + tile_id * 16
        b = self.chr[o:o + 16]
        return [[((b[y] >> (7 - x)) & 1) | (((b[y + 8] >> (7 - x)) & 1) << 1) for x in range(8)] for y in range(8)]

    def render_cells(self, tiles, exram, w: int, palettes: bytes, mask=None) -> bytes:
        """Tile grid -> NES colour numbers (row-major). ExRAM bits 6-7 pick the sub-palette.

        Cells with mask[i] false become 255 (transparent).
        """
        h = len(tiles) // w
        out = bytearray([0 if mask is None else 255]) * (w * 8 * h * 8)
        for i, (t, e) in enumerate(zip(tiles, exram)):
            if mask is not None and not mask[i]:
                continue
            r, c = divmod(i, w)
            pal = palettes[(e >> 6) * 4:(e >> 6) * 4 + 4]
            for y, row in enumerate(self.tile(e, t)):
                for x, v in enumerate(row):
                    out[(r * 8 + y) * w * 8 + c * 8 + x] = pal[v] & 0x3F
        return bytes(out)

    def palette(self, o: int) -> bytes:
        return self.prg[o:o + 16]

    # ------------------------------------------------------------ faces

    def portrait_cells(self, n: int) -> tuple[bytes, bytes]:
        o = PORTRAIT_TABLE + n * 60
        return self.prg[o:o + 30], self.prg[o + 30:o + 60]

    def composite_part(self, part: str, code: int) -> tuple[int, bytes, bytes]:
        """(first cell, tile ids, ExRAM bytes) of one composite part, as bank 19 $A000 copies it."""
        shift, base, stride, width, cells, widths = COMPOSITE_PARTS[part]
        cat, sel = code & 3, (code >> shift) & 3
        o = PARTS_BANK + base - 0xA000 + cat * stride + sel * 2 * width
        n = widths[cat]
        return cells[cat], self.prg[o:o + n], self.prg[o + width:o + width + n]

    def composite_cells(self, code: int) -> tuple[list[int], list[int]]:
        tiles, exram = [0] * 30, [0] * 30
        for part in COMPOSITE_PARTS:
            at, t, e = self.composite_part(part, code)
            tiles[at:at + len(t)], exram[at:at + len(e)] = t, e
        return tiles, exram

    def face_cells(self, code: int) -> tuple[list[int], list[int]]:
        if code & 0x8000:
            return self.composite_cells(code)
        t, e = self.portrait_cells(code)
        return list(t), list(e)

    def face_pixels(self, code: int) -> bytes:
        """40x48 NES colour numbers for a face code (bit 15: composite, else dedicated portrait)."""
        tiles, exram = self.face_cells(code)
        return self.render_cells(tiles, exram, PORTRAIT_W, self.palette(FACE_PALETTE))

    # ------------------------------------------------------------ world map

    def map_block(self, k: int) -> tuple[bytes, bytes]:
        n = MAP_BLOCK_W[k % 3] * MAP_BLOCK_H
        t = PARTS_BANK + self.u16(MAP_BLOCK_PTRS + 2 * k) - 0xA000
        e = PARTS_BANK + self.u16(MAP_BLOCK_PTRS + 18 + 2 * k) - 0xA000
        return self.prg[t:t + n], self.prg[e:e + n]

    def map_cells(self) -> tuple[list[int], list[int]]:
        """28x18 tile ids and ExRAM bytes of the whole world map, row-major."""
        tiles, exram = [0] * (MAP_W * MAP_H), [0] * (MAP_W * MAP_H)
        for k in range(9):
            bt, be = self.map_block(k)
            w, x0, y0 = MAP_BLOCK_W[k % 3], sum(MAP_BLOCK_W[:k % 3]), (k // 3) * MAP_BLOCK_H
            for i in range(len(bt)):
                o = (y0 + i // w) * MAP_W + x0 + i % w
                tiles[o], exram[o] = bt[i], be[i]
        return tiles, exram

    def map_views(self) -> list[list[int]]:
        return [list(self.prg[MAP_VIEWS + 4 * v:MAP_VIEWS + 4 * v + 4]) for v in range(4)]

    def map_pixels(self) -> bytes:
        tiles, exram = self.map_cells()
        return self.render_cells(tiles, exram, MAP_W, self.palette(MAP_PALETTE))


# Battle maps (bank 21): 46 maps (one per city) x 78 bytes = 13x12 terrain nibbles, high nibble first
BATTLE_MAPS = 0x2A000
BATTLE_W, BATTLE_H = 13, 12
BATTLE_SIZE = 78
BATTLE_AREAS = 0x2AE04        # 46 LE16 offsets (from this table) to per-map cell lists (meaning unknown)
BATTLE_TERRAIN_TILES = 0x26ED4  # bank 19 $AED4: 16 terrain x 3 variants x (2x2 tile ids + 2x2 ExRAM)
BATTLE_TILE_W, BATTLE_TILE_H = 26, 25
BATTLE_PALETTE = 0x26034      # bank 19 $A034: BG palette of the battle screen (emulator-confirmed)
BATTLE_VARIANTS = 3           # variant 2 has snow-coloured tiles; when the game picks it is unknown
TERRAIN_NAMES = {0: "山A", 1: "山B", 2: "山C", 3: "山D", 4: "野原", 5: "森林", 6: "市街", 7: "湿地",
                 8: "浅瀬", 9: "川", 10: "橋", 11: "湖・海"}  # names matched to the manual by tile look


def battle_cell_origin(x: int, y: int) -> tuple[int, int]:
    """Top-left tile (col, row) of cell (x, y) in the 26x25 tilemap: even columns sit one tile lower."""
    return 2 * x, 2 * y + (1 if x % 2 == 0 else 0)


def _battle_methods():
    def battle_terrain(self, n: int) -> list[int]:
        """13x12 terrain values of map n (= city index), row-major."""
        out = []
        for b in self.prg[BATTLE_MAPS + n * BATTLE_SIZE:BATTLE_MAPS + (n + 1) * BATTLE_SIZE]:
            out += [b >> 4, b & 15]
        return out

    def battle_cells(self, n: int, variant: int = 0) -> tuple[list[int], list[int]]:
        """26x25 tile ids and ExRAM bytes, as the battle setup builds them in WRAM $7684 / $790E."""
        tiles, exram = [0] * (BATTLE_TILE_W * BATTLE_TILE_H), [0] * (BATTLE_TILE_W * BATTLE_TILE_H)
        for i, t in enumerate(self.battle_terrain(n)):
            x0, y0 = battle_cell_origin(i % BATTLE_W, i // BATTLE_W)
            o = BATTLE_TERRAIN_TILES + t * 24 + variant * 8
            r = self.prg[o:o + 8]
            for k in range(4):
                p = (y0 + k // 2) * BATTLE_TILE_W + x0 + k % 2
                tiles[p], exram[p] = r[k], r[4 + k]
        return tiles, exram

    def battle_pixels(self, n: int, variant: int = 0) -> tuple[int, int, bytes]:
        tiles, exram = self.battle_cells(n, variant)
        return (BATTLE_TILE_W * 8, BATTLE_TILE_H * 8,
                self.render_cells(tiles, exram, BATTLE_TILE_W, self.palette(BATTLE_PALETTE)))

    return battle_terrain, battle_cells, battle_pixels


Rom.battle_terrain, Rom.battle_cells, Rom.battle_pixels = _battle_methods()
