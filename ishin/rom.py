"""FC 維新の嵐 (KOEI, 1990) ROM decoding.

All offsets are PRG offsets (file offset - 0x10). See ishin/docs/ROM_FORMAT.md.
"""
import os
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Ishin no Arashi (Japan).zip")

PRG_SIZE = 0x40000
CHR_START = 0x10 + PRG_SIZE

# Names (bank 23)
SURNAMES = 0x2F166            # 201 x 7 bytes, SJIS
DOMAIN_NAMES = 0x2F0F2        # 23 x 5 bytes: 17 雄藩, 武蔵 (幕府), 6 天領
DOMAIN_COUNT = 23
YUHAN_COUNT = 17
SHINSENGUMI = 0x5B          # 所属 value of 新撰組 members
# Label lists (bank 23): (offset, entry size, count)
RANK_LABELS = (0x2F6F1, 7, 19)    # 天皇 大臣 公卿 朝臣 将軍 老中 奉行 幕臣 藩主 家老 重臣 藩士 海援隊 新撰組 学者 商人 志士 町人 ｿﾉ他
AIM_LABELS = (0x2F776, 9, 6)      # 目的 / 藩論
IDEOLOGY_LABELS = (0x2F7AC, 5, 3)  # 尊王 公議 佐幕
REGION_LABELS = (0x2F7BC, 7, 8)
TOWN_LABELS = (0x2F7F4, 7, 8)     # 江戸 京都 大坂 萩 下関 高知 長崎 鹿児島 (town maps 31-46, two each)
MAP_REGION = 0x2F82C          # 31 bytes: region (index into REGION_LABELS) of each country map
CASTLES = 0x2E004             # 23 x (map, hex, domain); domain 0x11 = 天領 castles
TOWN_SITES = 0x2F081          # 8 x (country map, hex): where each town sits on its country map
FACILITIES = 0x2F091          # (town map, hex, type) until 0; type = study kind / dojo
MAP_POS = 0x2F042             # 47 x (X << 4 | Y): map position on the 8x9 grid of country maps

# Scenarios
SCENARIO_COUNT = 2
CHAR_COUNT = 201
NAME_BANK = [0x30000, 0x32000]   # banks 24/25: 4-byte home records, then 10-byte given names
STATE_BANK = [0x34000, 0x36000]  # banks 26/27: copied to WRAM $A000 as the game state
HOME_AT, GIVEN_AT, GIVEN_COUNT = 4, 0x328, 231  # 201 people + 30 generic given names
STATS_AT = 5                  # 201 x 15 bytes
UNIT_STRENGTH_AT = 0xBCC      # 23 domains x 2 units x (soldiers LE16, training)
PLACE_AT = 0xC56              # 201 x 8 bytes, bytes 0-1 = (map, hex)
UNIT_PLACE_AT = 0x129E        # 46 x 8 bytes, bytes 0-1 = (map, hex)
TRUST_AT = 0x140E             # 201 x 7 bytes: (person, value) x 3 + remainder
DATE_AT = 0x1990              # year - 1800, month - 1, day - 1
DOMAIN_STATS_AT = 0x1999      # 23 x 6 bytes (scenario 1 bank only)

# Faces
PORTRAIT_TABLE = 0x20004      # 87 x 62 bytes: 2 sprite CHR banks, 30 tiles, 30 attributes; code n -> n - 1
PORTRAIT_COUNT = 87
PART_TILES = 0x10B2           # 120 LE16 pointers ($A000 = PRG 0x20000): tiles, attributes follow
PART_ATTRS = 0x11A2           # 120 LE16 pointers; the 2 bytes before the tiles are CHR banks
FACE_PALETTES = 0x0E10        # 6 x 16 bytes: set 0 = portraits, set 1 + category = composites
FACE_W, FACE_H = 5, 6
CATEGORIES = 5
SLOTS = [("head", "頭"), ("eyes", "眼"), ("nose", "鼻"), ("mouth", "口"), ("lower", "下半"), ("body", "身體")]
SLOT_ORDER = [0, 4, 5, 1, 2, 3]       # draw order: head, lower, body, eyes, nose, mouth
# (row, col, width) per slot; categories 0-1 share one layout, 2-4 the other
_LAYOUT_A = [(0, 0, 5), (2, 1, 3), (3, 2, 1), (4, 2, 1), (2, 0, 5), (5, 0, 5)]
_LAYOUT_B = [(0, 0, 5), (2, 0, 3), (3, 1, 1), (4, 1, 2), (3, 0, 4), (5, 0, 5)]
LAYOUTS = [_LAYOUT_A, _LAYOUT_A, _LAYOUT_B, _LAYOUT_B, _LAYOUT_B]
BLANK_TILE = [None, None, 53, 32, 17]  # this tile only fills cells no earlier part has drawn

# Hex maps (bank 22): 47 x 117 bytes = 13 x 9 cells; 0-30 country maps, 31-46 town maps (2 per town)
MAPS = 0x2C004
MAP_COUNT, COUNTRY_MAPS = 47, 31
MAP_W, MAP_H = 13, 9
CELL_PTRS = 0x145B            # 4 bytes per value: LE16 pointer into bank 20 ($A000); ExRAM at ptr, tiles at ptr - 4
MAP_PALETTE = 0x3F456         # BG palette of the map screen (bank 31)
JAPAN_TILES, JAPAN_EXRAM = 0x2830C, 0x284BC  # 勢力図 background: 24 x 18 tiles (screen cols 4-27, rows 3-20)
JAPAN_W, JAPAN_H = 24, 18
TERRAIN = {
    0x00: "道", 0x01: "村", 0x02: "町", 0x03: "港", 0x04: "草原", 0x05: "城", 0x06: "鉱山", 0x07: "関所",
    0x08: "山", 0x09: "海・川", 0x0A: "高山", 0x0E: "学者宅", 0x0F: "剣道場（推定）", 0x12: "御所（推定）",
    0x13: "新撰組屯所（推定）", 0x16: "藩校", 0x1A: "外国商館（推定）", 0x1B: "海軍伝習所",
}
FACILITY_TYPES = ["儒学", "国学", "蘭学", "藩校", "海軍", "剣術（推定）"]

# NES 2C02 palette (common emulator approximation), index = NES colour number
NES_PALETTE = [int(x, 16) for x in ["7C7C7C", "0000FC", "0000BC", "4428BC", "940084", "A80020", "A81000", "881400", "503000", "007800", "006800", "005800", "004058", "000000", "000000", "000000", "BCBCBC", "0078F8", "0058F8", "6844FC", "D800CC", "E40058", "F83800", "E45C10", "AC7C00", "00B800", "00A800", "00A844", "008888", "000000", "000000", "000000", "F8F8F8", "3CBCFC", "6888FC", "9878F8", "F878F8", "F85898", "F87858", "FCA044", "F8B800", "B8F818", "58D854", "58F898", "00E8D8", "787878", "000000", "000000", "FCFCFC", "A4E4FC", "B8B8F8", "D8B8F8", "F8B8F8", "F8A4C0", "F0D0B0", "FCE0A8", "F8D878", "D8F878", "B8F8B8", "B8F8D8", "00FCFC", "F8D8F8", "000000", "000000"]]


def nes_rgb(i: int) -> tuple[int, int, int]:
    c = NES_PALETTE[i & 0x3F]
    return c >> 16, (c >> 8) & 0xFF, c & 0xFF


def load_gaiji() -> dict[int, str]:
    out = {}
    with open(os.path.join(HERE, "data", "gaiji.tsv"), encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                code, ch = line.split("\t")[:2]
                out[int(code, 16)] = ch
    return out


GAIJI = load_gaiji()


def text(raw: bytes) -> str:
    """SJIS with gaiji 0xEBxx; half-width katakana are normalised to full width."""
    out, i = [], 0
    while i < len(raw) and raw[i]:
        b = raw[i]
        if 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
            code = b << 8 | raw[i + 1]
            out.append(GAIJI.get(code) or raw[i:i + 2].decode("cp932", "replace"))
            i += 2
        else:
            out.append(unicodedata.normalize("NFKC", bytes([b]).decode("cp932", "replace")))
            i += 1
    return "".join(out)


def read_rom(path: str) -> bytes:
    """Read a .nes file, or the single .nes inside a .zip (as stored in roms/)."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            (name,) = [n for n in z.namelist() if n.lower().endswith(".nes")]
            return z.read(name)
    with open(path, "rb") as f:
        return f.read()


def hex_cell(pos: int) -> tuple[int, int]:
    """Hex position byte -> (col, row)."""
    return pos >> 4, pos & 0xF


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.data = read_rom(path)
        assert self.data[:4] == b"NES\x1a" and self.data[4] == 16 and self.data[5] == 16, "not the expected ROM"
        self.prg = self.data[0x10:CHR_START]
        self.chr = self.data[CHR_START:]

    def u16(self, o: int) -> int:
        return self.prg[o] | self.prg[o + 1] << 8

    def labels(self, spec: tuple[int, int, int]) -> list[str]:
        o, size, n = spec
        return [text(self.prg[o + size * i:o + size * i + size]).strip() for i in range(n)]

    # ------------------------------------------------------------ names and labels

    def domains(self) -> list[str]:
        return [text(self.prg[DOMAIN_NAMES + 5 * i:DOMAIN_NAMES + 5 * i + 5]) for i in range(DOMAIN_COUNT)]

    def ranks(self) -> list[str]:
        """天皇 大臣 公卿 朝臣 / 将軍 老中 奉行 幕臣 / 藩主 家老 重臣 藩士 / 海援隊 新撰組 / 学者 商人 志士 町人 その他."""
        return self.labels(RANK_LABELS)

    def aims(self) -> list[str]:
        return self.labels(AIM_LABELS)

    def ideologies(self) -> list[str]:
        return self.labels(IDEOLOGY_LABELS)

    def regions(self) -> list[str]:
        return self.labels(REGION_LABELS)

    def towns(self) -> list[str]:
        return self.labels(TOWN_LABELS)

    def rank_name(self, rank: int, domain: int) -> str:
        """身分 byte: high nibble = class (0 朝廷, 1 武士, 2 学者, 3 商人, 4 志士, 5 町人), low nibble = grade.
        武士 of 幕府 (domain 17) use the 幕府 titles, 武士 with domain 0x5B are 新撰組."""
        cls, grade = rank >> 4, rank & 0xF
        r = self.ranks()
        if cls == 0:
            return r[grade]
        if cls == 1:
            return r[13] if domain == SHINSENGUMI else r[(4 if domain == 17 else 8) + grade]
        return {2: r[14], 3: r[15], 4: r[16], 5: r[17]}.get(cls, f"0x{rank:02X}")

    def affiliation(self, rank: int, domain: int) -> str:
        """所属 byte: domain index for 武士; for 学者 it is the school (0 儒学, 1 国学, 2 蘭学, 3 ?)."""
        cls = rank >> 4
        if cls == 1:
            if domain == SHINSENGUMI:
                return "新撰組"
            return "幕府" if domain == 17 else self.domains()[domain] if domain < DOMAIN_COUNT else f"0x{domain:02X}"
        if cls == 2:
            return FACILITY_TYPES[domain] if domain < 3 else f"学問 {domain}"
        return ""

    # ------------------------------------------------------------ people

    def characters(self, scenario: int = 0) -> list[dict]:
        nb, sb = NAME_BANK[scenario], STATE_BANK[scenario]
        out = []
        for i in range(CHAR_COUNT):
            g = self.prg[nb + GIVEN_AT + 10 * i:nb + GIVEN_AT + 10 * i + 10]
            s = self.prg[sb + STATS_AT + 15 * i:sb + STATS_AT + 15 * i + 15]
            home = self.prg[nb + HOME_AT + 4 * i:nb + HOME_AT + 4 * i + 4]
            place = self.prg[sb + PLACE_AT + 8 * i:sb + PLACE_AT + 8 * i + 8]
            t = self.prg[sb + TRUST_AT + 7 * i:sb + TRUST_AT + 7 * i + 7]
            surname = text(self.prg[SURNAMES + 7 * i:SURNAMES + 7 * i + 7])
            given = text(g[:7])
            out.append({
                "id": i, "surname": surname, "given": given, "name": surname + given,
                "face_code": g[7] | g[8] << 8, "age": g[9],
                "hp": s[0], "hp_max": s[1], "spirit": s[2], "learning": s[3], "martial": s[4],
                "gold": s[5] | s[6] << 8, "goods": s[7], "domain": s[8], "rank": s[9],
                "sonno": s[10], "kogi": s[11], "sabaku": s[12], "progress": s[13], "index": s[14],
                "map": place[0], "hex": place[1], "place_rest": place[2:].hex(),
                "home_map": home[0], "home_hex": home[1], "home_unk2": home[2], "home_unk3": home[3],
                "trust": [(t[2 * k], t[2 * k + 1]) for k in range(3) if t[2 * k] != 0xFF], "trust_rest": t[6],
            })
        return out

    def generic_names(self) -> list[tuple[str, int]]:
        """Given names (no surname) with composite face codes, records 201-230 of the name table."""
        nb = NAME_BANK[0]
        out = []
        for i in range(CHAR_COUNT, GIVEN_COUNT):
            g = self.prg[nb + GIVEN_AT + 10 * i:nb + GIVEN_AT + 10 * i + 10]
            out.append((text(g[:7]), g[7] | g[8] << 8))
        return out

    def start_date(self, scenario: int) -> tuple[int, int, int]:
        y, m, d = self.prg[STATE_BANK[scenario] + DATE_AT:STATE_BANK[scenario] + DATE_AT + 3]
        return 1800 + y, m + 1, d + 1

    # ------------------------------------------------------------ domains

    def castles(self) -> list[dict]:
        return [{"map": self.prg[CASTLES + 3 * i], "hex": self.prg[CASTLES + 3 * i + 1],
                 "owner": self.prg[CASTLES + 3 * i + 2]} for i in range(DOMAIN_COUNT)]

    def domain_stats(self) -> list[dict]:
        """Scenario 1 bank 26: 金米 LE16, 石高, 共感, 武装, 藩論 (0 in ROM, set at game start)."""
        b, u = STATE_BANK[0] + DOMAIN_STATS_AT, STATE_BANK[0] + UNIT_STRENGTH_AT
        out = []
        for i in range(DOMAIN_COUNT):
            r = self.prg[b + 6 * i:b + 6 * i + 6]
            v = self.prg[u + 6 * i:u + 6 * i + 6]
            out.append({"money": r[0] | r[1] << 8, "koku": r[2], "sympathy": r[3], "arms": r[4], "policy": r[5],
                        "units": [(v[0] | v[1] << 8, v[2]), (v[3] | v[4] << 8, v[5])]})
        return out

    def unit_places(self, scenario: int) -> list[tuple[int, int]]:
        b = STATE_BANK[scenario] + UNIT_PLACE_AT
        return [(self.prg[b + 8 * i], self.prg[b + 8 * i + 1]) for i in range(2 * DOMAIN_COUNT)]

    def town_sites(self) -> list[tuple[int, int]]:
        return [(self.prg[TOWN_SITES + 2 * i], self.prg[TOWN_SITES + 2 * i + 1]) for i in range(8)]

    def facilities(self) -> list[dict]:
        out, o = [], FACILITIES
        while self.prg[o]:
            out.append({"map": self.prg[o], "hex": self.prg[o + 1], "type": self.prg[o + 2]})
            o += 3
        return out

    def map_name(self, m: int) -> str:
        if m < COUNTRY_MAPS:
            return f"国{m:02d}"
        return f"{self.towns()[(m - COUNTRY_MAPS) // 2]}{(m - COUNTRY_MAPS) % 2 + 1}"

    def map_region(self, m: int) -> int:
        """Region (0 東北 ... 7 九州) of country map m; table right after the region and town names."""
        return self.prg[MAP_REGION + m]

    def map_grid_pos(self, m: int) -> tuple[int, int]:
        """(X, Y) of a map on the 8 x 9 grid of country maps (town maps give their country map's)."""
        v = self.prg[MAP_POS + m]
        return (v >> 4) - 1, (v & 0xF) - 1

    # ------------------------------------------------------------ graphics

    def tile(self, bank_4k: int, tile_id: int) -> list[list[int]]:
        o = (bank_4k & 0x1F) * 0x1000 + tile_id * 16
        b = self.chr[o:o + 16]
        return [[((b[y] >> (7 - x)) & 1) | (((b[y + 8] >> (7 - x)) & 1) << 1) for x in range(8)] for y in range(8)]

    def render_bg(self, tiles, exram, w: int, palettes: bytes) -> bytes:
        """BG tile grid -> NES colour numbers. ExRAM bits 0-5 = 4KB CHR bank, bits 6-7 = sub-palette."""
        h = len(tiles) // w
        out = bytearray(w * 8 * h * 8)
        for i, (t, e) in enumerate(zip(tiles, exram)):
            r, c = divmod(i, w)
            pal = palettes[(e >> 6) * 4:(e >> 6) * 4 + 4]
            for y, row in enumerate(self.tile(e, t)):
                for x, v in enumerate(row):
                    out[(r * 8 + y) * w * 8 + c * 8 + x] = (pal[v] if v else palettes[0]) & 0x3F
        return bytes(out)

    # ------------------------------------------------------------ faces

    def face_palette(self, n: int) -> bytes:
        return self.prg[FACE_PALETTES + 16 * n:FACE_PALETTES + 16 * n + 16]

    def part(self, cat: int, slot: int, v: int) -> tuple[bytes, bytes, bytes]:
        """(CHR banks, tiles, attributes) of one composite part."""
        i = cat * 24 + slot * 4 + v
        t, a = self.u16(PART_TILES + 2 * i), self.u16(PART_ATTRS + 2 * i)
        o, oa = 0x20000 + t - 0xA000, 0x20000 + a - 0xA000
        return self.prg[o - 2:o], self.prg[o:o + a - t], self.prg[oa:oa + a - t]

    def part_cells(self, cat: int, slot: int, v: int) -> dict[tuple[int, int], tuple[int, int]]:
        """(row, col) -> (tile, attr), blank tiles dropped."""
        _, tiles, attrs = self.part(cat, slot, v)
        r0, c0, w = LAYOUTS[cat][slot]
        return {(r0 + i // w, c0 + i % w): (t, a) for i, (t, a) in enumerate(zip(tiles, attrs))
                if t != BLANK_TILE[cat]}

    def category_banks(self, cat: int) -> list[int]:
        b = self.part(cat, 0, 0)[0][0]
        return [b, b + 1, b + 2]

    def face_cells(self, code: int) -> tuple[list[int], dict[tuple[int, int], tuple[int, int]], int]:
        """(sprite 1KB CHR banks, (row, col) -> (tile, attr), palette set) for a face code."""
        if code & 0x8000:
            cat = (code >> 12) & 7
            grid = {}
            for s in SLOT_ORDER:
                v = (code >> (10 - 2 * s)) & 3
                _, tiles, attrs = self.part(cat, s, v)
                r0, c0, w = LAYOUTS[cat][s]
                for i, (t, a) in enumerate(zip(tiles, attrs)):
                    k = (r0 + i // w, c0 + i % w)
                    if t == BLANK_TILE[cat] and k in grid:
                        continue
                    grid[k] = (t, a)
            return self.category_banks(cat), grid, 1 + cat
        o = PORTRAIT_TABLE + (code - 1) * 62
        r = self.prg[o:o + 62]
        grid = {divmod(i, FACE_W): (r[2 + i], r[32 + i]) for i in range(30)}
        return [r[0], r[1]], grid, 0

    def sprite_tile(self, banks: list[int], t: int) -> list[list[int]]:
        o = banks[t >> 6] * 0x400 + (t & 63) * 16
        b = self.chr[o:o + 16]
        return [[((b[y] >> (7 - x)) & 1) | (((b[y + 8] >> (7 - x)) & 1) << 1) for x in range(8)] for y in range(8)]

    def render_sprites(self, banks, grid, palette: bytes, w: int = FACE_W, h: int = FACE_H,
                       empty: int = 0x0F) -> bytes:
        """Sprite cells -> NES colour numbers; colour 0 and empty cells show `empty` (the window background)."""
        out = bytearray([empty]) * (w * 8 * h * 8)
        for (r, c), (t, a) in grid.items():
            pal = palette[(a & 3) * 4:(a & 3) * 4 + 4]
            for y, row in enumerate(self.sprite_tile(banks, t)):
                for x, v in enumerate(row):
                    xx, yy = (7 - x if a & 0x40 else x), (7 - y if a & 0x80 else y)
                    out[(r * 8 + yy) * w * 8 + c * 8 + xx] = pal[v] & 0x3F if v else empty
        return bytes(out)

    def face_pixels(self, code: int) -> bytes:
        """40x48 NES colour numbers (bit 15: composite, else dedicated portrait 1-87)."""
        banks, grid, pal = self.face_cells(code)
        return self.render_sprites(banks, grid, self.face_palette(pal))

    # ------------------------------------------------------------ maps

    def map_values(self, m: int) -> bytes:
        return self.prg[MAPS + 117 * m:MAPS + 117 * m + 117]

    def cell_quad(self, v: int) -> tuple[bytes, bytes]:
        """Map value -> (4 tile ids, 4 ExRAM bytes) for the 2x2 tiles of a cell."""
        p = 0x28000 + self.u16(CELL_PTRS + 4 * v) - 0xA000
        return self.prg[p - 4:p], self.prg[p:p + 4]

    def draw_map(self, out: bytearray, w: int, m: int, x0: int, y0: int) -> None:
        """Draw 13 x 9 hex map m with its top-left at (x0, y0); odd columns sit half a cell lower (screen layout)."""
        pal = self.prg[MAP_PALETTE:MAP_PALETTE + 16]
        for i, v in enumerate(self.map_values(m)):
            r, c = divmod(i, MAP_W)
            px = self.render_bg(*self.cell_quad(v), 2, pal)
            x, y = x0 + c * 16, y0 + r * 16 + (c & 1) * 8
            for k in range(16):
                out[(y + k) * w + x:(y + k) * w + x + 16] = px[k * 16:k * 16 + 16]

    def map_pixels(self, m: int, empty: int = 0x0F) -> tuple[int, int, bytes]:
        """One hex map -> 208 x 152 pixels."""
        w, h = MAP_W * 16, MAP_H * 16 + 8
        out = bytearray([empty]) * (w * h)
        self.draw_map(out, w, m, 0, 0)
        return w, h, bytes(out)

    def world_pixels(self, empty: int = 0x0F) -> tuple[int, int, bytes]:
        """The 31 country maps placed on their 8 x 9 grid; neighbouring maps join seamlessly."""
        w, h = 8 * MAP_W * 16, 9 * MAP_H * 16 + 8
        out = bytearray([empty]) * (w * h)
        for m in range(COUNTRY_MAPS):
            x, y = self.map_grid_pos(m)
            self.draw_map(out, w, m, x * MAP_W * 16, y * MAP_H * 16)
        return w, h, bytes(out)

    def japan_pixels(self) -> tuple[int, int, bytes]:
        n = JAPAN_W * JAPAN_H
        return JAPAN_W * 8, JAPAN_H * 8, self.render_bg(
            self.prg[JAPAN_TILES:JAPAN_TILES + n], self.prg[JAPAN_EXRAM:JAPAN_EXRAM + n], JAPAN_W,
            self.prg[MAP_PALETTE:MAP_PALETTE + 16])
