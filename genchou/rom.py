"""FC 蒼き狼と白き牝鹿・元朝秘史 (KOEI, 1992) ROM decoding.

All offsets are PRG offsets (file offset - 0x10). See genchou/docs/ROM_FORMAT.md.
"""
import os
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Aoki Ookami to Shiroki Mejika - Genchou Hishi (Japan).zip")

PRG_SIZE = 0x80000
CHR_START = 0x10 + PRG_SIZE
BANK = 0x2000

# Scenarios: 8KB banks 0-3, each starting with "4C 00 00 00 FF"
SCENARIO_COUNT = 4
GENERAL_START = 5             # 109 slots x 26 bytes
GENERAL_SIZE = 26
GENERAL_SLOTS = 109
FAMILY_START = 0x149E         # scenario 1 only: the player's family, same 26-byte layout
FAMILY_SLOTS = 7
COUNTRY_COUNT_AT = 0x1496     # number of countries in the scenario (14 or 33)
YEAR_AT = 0x1499              # LE16 start year
PROVINCE_START = 0xB1A        # countries: 42 bytes each
PROVINCE_SIZE = 42

# Names
MONGOL_NAMES = 0x723A4        # bank 57: 14 x 16 bytes (Mongol scenario regions)
WORLD_NAMES = 0x725B4         # bank 57: 33 x 16 bytes
HOUSE_NAMES = 0x3E004         # bank 31: 5 sets x 0x232 bytes, 33 x 17 bytes each; set n = scenario n
HOUSE_SET_SIZE = 0x232
HOUSE_SIZE = 17

# Units (bank 4 mapped at $8000): 16 x 8 bytes, names via 16 LE16 pointers
UNIT_TABLE = 0x9B2C
UNIT_NAME_PTRS = 0x9BBC
UNIT_COUNT = 16
UNIT_PRICES = 0x3B680         # bank 29: 16 bytes, conscription price / 100
UNIT_COM_ORDER = 0x3B690      # bank 29: unit ids in the order the computer fills its armies
TRADE_TABLE = 0x3B650         # bank 29: 4 x 12 bytes, merchant x goods (meaning inferred)
GOODS_NAME_PTRS = 0x2912E     # bank 20 mapped at $A000: 12 LE16 pointers
GOODS_COUNT = 12
MERCHANT_NAME_PTRS = 0x291A9  # bank 20: 4 LE16 pointers
MERCHANT_COUNT = 4
UNIT_CLASSES = ["歩兵", "特殊", "騎兵"]
GRADES = "EDCBA"

# Faces
PORTRAIT_TABLE = 0x5C004      # bank 46: 80 x (30 tile ids + 30 ExRAM bytes), 5x6 tiles
PORTRAIT_COUNT = 80
COMPOSITE_TABLE = 0x52004     # bank 41: 86 records x 60 bytes, two per head (base, alternate)
COMPOSITE_LAYOUT = 0x5342C    # bank 41 $942C: layout id per head (culture * 6 + head)
COMPOSITE_PARTS = 0x53456     # bank 41 $9456: 9 bytes per layout = (col, row, width) x eyes, nose, mouth
CULTURES = 7                  # face code bits 8-10
HEADS_PER_CULTURE = 6         # face code bits 5-7 (values 6 and 7 run into the next culture)
COMPOSITE_HEADS = 43          # head = culture * 6 + n; 86 records = 43 heads
FACE_CULTURES = ["モンゴル", "中国", "中央アジア", "インド", "日本", "イスラム", "欧州"]
# Face code bit -> replaced area. "top"/"body" = cells before/after the boundary, minus the part cells.
COMPOSITE_SLOTS = [("top", "上", 4), ("body", "下", 3), ("eyes", "眼", 2), ("nose", "鼻", 1), ("mouth", "口", 0)]
PORTRAIT_W, PORTRAIT_H = 5, 6
# Main BG palette, loaded by bank 52 $A03F from $B338 (also used by the face windows)
MAIN_PALETTE = 0x69338

# Big maps (bank 45): full-screen 32x30 tilemaps, tile ids then ExRAM bytes
MAP_W, MAP_H = 32, 30
MAPS = {"mongol": 0x5A004, "world": 0x5A784}

# Battle maps: 47 records x 0x364 bytes (14 Mongol regions, then 33 world countries)
BATTLE_COUNT = 47
BATTLE_SIZE = 0x364
BATTLE_W, BATTLE_H = 14, 10
BATTLE_TILE_W, BATTLE_TILE_H = 28, 21
BATTLE_FIRST_BANK = [(0, 0x40000), (37, 0x48000)]  # maps 0-36 in banks 32-35, 37-46 from bank 36
BATTLE_TILE_TABLE = 0x12702   # bank 9 $A702: (tile id, ExRAM) per tilemap value, CHR bank 17
# Inferred: the only ROM palette whose sub-palettes 1-3 are green / blue / brown (bank 52 $B324)
BATTLE_PALETTE = 0x69324
TERRAIN_NAMES = {0: "平地", 1: "城", 2: "街", 3: "砂漠", 4: "森林", 5: "山岳", 6: "河川", 7: "湖・海"}

# NES 2C02 palette (common emulator approximation), index = NES colour number
NES_PALETTE = [int(x, 16) for x in ["7C7C7C", "0000FC", "0000BC", "4428BC", "940084", "A80020", "A81000", "881400", "503000", "007800", "006800", "005800", "004058", "000000", "000000", "000000", "BCBCBC", "0078F8", "0058F8", "6844FC", "D800CC", "E40058", "F83800", "E45C10", "AC7C00", "00B800", "00A800", "00A844", "008888", "000000", "000000", "000000", "F8F8F8", "3CBCFC", "6888FC", "9878F8", "F878F8", "F85898", "F87858", "FCA044", "F8B800", "B8F818", "58D854", "58F898", "00E8D8", "787878", "000000", "000000", "FCFCFC", "A4E4FC", "B8B8F8", "D8B8F8", "F8B8F8", "F8A4C0", "F0D0B0", "FCE0A8", "F8D878", "D8F878", "B8F8B8", "B8F8D8", "00FCFC", "F8D8F8", "000000", "000000"]]


def nes_rgb(i: int) -> tuple[int, int, int]:
    c = NES_PALETTE[i & 0x3F]
    return c >> 16, (c >> 8) & 0xFF, c & 0xFF


def text(raw: bytes) -> str:
    """Game text: SJIS kanji, half-width kana shown as hiragana (ESC H, default) or katakana (ESC K)."""
    out, run, kata = [], bytearray(), False

    def flush():
        if run:
            s = unicodedata.normalize("NFKC", run.decode("cp932")).replace("-", "ー")
            out.append(s if kata else "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s))
            run.clear()

    i = 0
    while i < len(raw) and raw[i]:
        b = raw[i]
        if b == 0x1B and i + 1 < len(raw):
            flush()
            kata = raw[i + 1] == ord("K")
            i += 2
        elif 0x81 <= b <= 0x9F or 0xE0 <= b <= 0xFC:
            flush()
            out.append(raw[i:i + 2].decode("cp932"))
            i += 2
        else:
            run.append(b)
            i += 1
    flush()
    return "".join(out)


def to_hiragana(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


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
        assert self.data[:4] == b"NES\x1a" and self.data[4] == 32 and self.data[5] == 32, "not the expected ROM"
        self.prg = self.data[0x10:CHR_START]
        self.chr = self.data[CHR_START:]

    def u16(self, o: int) -> int:
        return self.prg[o] | self.prg[o + 1] << 8

    def cstr(self, o: int) -> str:
        return text(self.prg[o:o + 64])

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
        out = bytearray([255]) * (w * 8 * h * 8)
        for i, (t, e) in enumerate(zip(tiles, exram)):
            if mask is not None and not mask[i]:
                continue
            r, c = divmod(i, w)
            pal = palettes[(e >> 6) * 4:(e >> 6) * 4 + 4]
            for y, row in enumerate(self.tile(e, t)):
                for x, v in enumerate(row):
                    out[(r * 8 + y) * w * 8 + c * 8 + x] = pal[v] & 0x3F
        return bytes(out)

    def palette(self, o: int = MAIN_PALETTE) -> bytes:
        return self.prg[o:o + 16]

    # ------------------------------------------------------------ scenarios

    def scenario_info(self, s: int) -> dict:
        base = s * BANK
        return {"countries": self.prg[base + COUNTRY_COUNT_AT], "year": self.u16(base + YEAR_AT)}

    def general(self, r: bytes) -> dict | None:
        if r[23] == 0x80 or not r[0]:
            return None
        return {
            "name": text(r[0:16]),
            "house": r[16],                    # 0xFF = 在野
            "country": r[17],
            "hp_max": r[18] >> 4, "hp": r[18] & 15,   # 体力 (which nibble is the maximum is assumed)
            "war": r[19] >> 4, "politics": r[19] & 15,    # 戦闘 / 政治, 0 = E ... 4 = A
            "charm": r[20] >> 4, "command": r[20] & 15,   # 魅力 / 指揮
            "age": r[21] - 256 if r[21] >= 0x80 else r[21],
            "culture": (r[22] >> 2) & 7,
            "unk22": r[22] & 0xE3,
            "status": r[23],                   # 3 = 王, 1 = 家臣, 0 = 在野 (inferred)
            "face_code": r[24] | r[25] << 8,
        }

    def generals(self, s: int) -> list[dict]:
        """Scenario s (0-3): occupied slots, plus the player's family in scenario 0."""
        base = s * BANK
        out = []
        for i in range(GENERAL_SLOTS):
            o = base + GENERAL_START + i * GENERAL_SIZE
            g = self.general(self.prg[o:o + GENERAL_SIZE])
            if g:
                out.append({"slot": i, "offset": o, **g})
        if s == 0:
            for i in range(FAMILY_SLOTS):
                o = FAMILY_START + i * GENERAL_SIZE
                g = self.general(self.prg[o:o + GENERAL_SIZE])
                if g:
                    out.append({"slot": f"F{i}", "offset": o, **g})
        return out

    def country_names(self, s: int) -> list[str]:
        if s == 0:
            return [self.cstr(MONGOL_NAMES + 16 * i) for i in range(14)]
        return [self.cstr(WORLD_NAMES + 16 * i) for i in range(33)]

    def house_names(self, s: int) -> dict[int, str]:
        base = HOUSE_NAMES + s * HOUSE_SET_SIZE
        names = {i: text(self.prg[base + i * HOUSE_SIZE:base + (i + 1) * HOUSE_SIZE]) for i in range(33)}
        return {i: n for i, n in names.items() if n}

    def provinces(self, s: int) -> list[dict]:
        base = s * BANK + PROVINCE_START
        names = self.country_names(s)
        out = []
        for i in range(self.scenario_info(s)["countries"]):
            r = self.prg[base + i * PROVINCE_SIZE:base + (i + 1) * PROVINCE_SIZE]
            out.append({
                "id": i, "name": names[i],
                "house": r[0],
                "gold": r[1] | r[2] << 8, "food": r[3] | r[4] << 8, "population": r[5] | r[6] << 8,
                "split": list(r[7:11]),        # 住民配分 % (農業 / 牧畜 / 特産 / 街)
                "unk11": list(r[11:15]),
                "unk15": list(r[15:31]),
                "unk31": list(r[31:33]),
                "unk33": r[33],
                "split2": list(r[34:38]),
                "unk38": r[38:42].hex(),
            })
        return out

    # ------------------------------------------------------------ units and goods

    def units(self) -> list[dict]:
        out = []
        order = list(self.prg[UNIT_COM_ORDER:UNIT_COM_ORDER + UNIT_COUNT])
        for i in range(UNIT_COUNT):
            r = self.prg[UNIT_TABLE + 8 * i:UNIT_TABLE + 8 * i + 8]
            out.append({
                "id": i, "name": self.cstr(self.u16(UNIT_NAME_PTRS + 2 * i)),
                "class": r[0], "morale": r[1], "mobility": r[2],
                "melee": r[3], "charge": r[4], "missile": r[5], "defense": r[6],   # 0 = E ... 4 = A, 5 = none
                "special": r[7],
                "price": self.prg[UNIT_PRICES + i] * 100,
                "com_rank": order.index(i) + 1,
            })
        return out

    def goods(self) -> list[str]:
        return [self.cstr(0x28000 + self.u16(GOODS_NAME_PTRS + 2 * i) - 0xA000) for i in range(GOODS_COUNT)]

    def merchants(self) -> list[str]:
        return [self.cstr(0x28000 + self.u16(MERCHANT_NAME_PTRS + 2 * i) - 0xA000) for i in range(MERCHANT_COUNT)]

    def trade_table(self) -> list[list[int]]:
        return [list(self.prg[TRADE_TABLE + 12 * m:TRADE_TABLE + 12 * m + 12]) for m in range(MERCHANT_COUNT)]

    # ------------------------------------------------------------ faces

    def portrait_cells(self, n: int) -> tuple[bytes, bytes]:
        o = PORTRAIT_TABLE + n * 60
        return self.prg[o:o + 30], self.prg[o + 30:o + 60]

    def composite_record(self, k: int) -> tuple[bytes, bytes]:
        o = COMPOSITE_TABLE + k * 60
        return self.prg[o:o + 30], self.prg[o + 30:o + 60]

    def composite_areas(self, head: int) -> dict[str, set[int]]:
        """Cell indices (row * 5 + col) that each face code bit replaces, for head = culture * 6 + n."""
        layout = self.prg[COMPOSITE_LAYOUT + head]
        p = self.prg[COMPOSITE_PARTS + layout * 9:COMPOSITE_PARTS + layout * 9 + 9]
        areas = {}
        for k, sid in enumerate(["eyes", "nose", "mouth"]):
            col, row, w = p[3 * k:3 * k + 3]
            areas[sid] = {row * 5 + col + i for i in range(w)}
        bound = 20 if layout in (6, 9, 14, 15) else 10 if layout == 19 else 15
        parts = areas["eyes"] | areas["nose"] | areas["mouth"]
        areas["top"] = {i for i in range(bound) if i not in parts}
        areas["body"] = {i for i in range(bound, 30) if i not in parts}
        return areas

    def composite_cells(self, code: int) -> tuple[list[int], list[int]]:
        """Compose a face like bank 48 $A49B: base record, cells of each set bit from the alternate record."""
        head = decode_face_code(code)[0]
        bt, be = self.composite_record(2 * head)
        at, ae = self.composite_record(2 * head + 1)
        tiles, exram = list(bt), list(be)
        areas = self.composite_areas(head)
        for sid, _, bit in COMPOSITE_SLOTS:
            if code >> bit & 1:
                for i in areas[sid]:
                    tiles[i], exram[i] = at[i], ae[i]
        return tiles, exram

    def face_pixels(self, code: int) -> bytes:
        """40x48 NES colour numbers for a face code (bit 15: composite, else dedicated portrait)."""
        tiles, exram = self.composite_cells(code) if code & 0x8000 else self.portrait_cells(code)
        return self.render_cells(tiles, exram, PORTRAIT_W, self.palette())

    # ------------------------------------------------------------ maps

    def map_cells(self, name: str) -> tuple[bytes, bytes]:
        o, n = MAPS[name], MAP_W * MAP_H
        return self.prg[o:o + n], self.prg[o + n:o + 2 * n]

    def battle_record(self, n: int) -> bytes:
        first, base = [b for b in BATTLE_FIRST_BANK if b[0] <= n][-1]
        o = base + (n - first) * BATTLE_SIZE
        return self.prg[o:o + BATTLE_SIZE]

    def battle_terrain(self, n: int) -> list[int]:
        """14x10 terrain per cell, row-major (copied by bank 9 $A412 from record offset 0x2D8)."""
        return list(self.battle_record(n)[0x2D8:0x2D8 + 140])

    def battle_entries(self, n: int) -> list[int | None]:
        """14x10 entry cells: neighbouring country index, None = no entry (record offset 0x24C, $A532)."""
        return [None if v == 0x30 else v for v in self.battle_record(n)[0x24C:0x24C + 140]]

    def battle_cells(self, n: int) -> tuple[list[int], list[int]]:
        """28x21 tile ids and ExRAM bytes of the drawn map (record offset 0, $A5A9 then $A62B)."""
        tm = self.battle_record(n)[:BATTLE_TILE_W * BATTLE_TILE_H]
        return ([self.prg[BATTLE_TILE_TABLE + 2 * v] for v in tm],
                [self.prg[BATTLE_TILE_TABLE + 2 * v + 1] for v in tm])

    def battle_pixels(self, n: int) -> tuple[int, int, bytes]:
        tiles, exram = self.battle_cells(n)
        return (BATTLE_TILE_W * 8, BATTLE_TILE_H * 8,
                self.render_cells(tiles, exram, BATTLE_TILE_W, self.palette(BATTLE_PALETTE)))


def battle_cell_origin(x: int, y: int) -> tuple[int, int]:
    """Top-left tile (col, row) of cell (x, y) in the 28x21 tilemap: even columns sit one tile lower."""
    return 2 * x, 2 * y + (0 if x & 1 else 1)


def decode_face_code(code: int) -> tuple[int, int, int]:
    """Composite face code -> (head = culture * 6 + n, culture, n). Bits 0-4 are the part flags,
    bits 11-14 are ignored by the face routine."""
    culture, n = (code >> 8) & 7, (code >> 5) & 7
    return culture * HEADS_PER_CULTURE + n, culture, n


def is_composite(code: int) -> bool:
    """Bit 15 set and the head inside the 43-head table (head 43+ would read past it)."""
    return bool(code & 0x8000) and decode_face_code(code)[0] < COMPOSITE_HEADS
