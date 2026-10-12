"""FC 三國志II 覇王の大陸 (Namco, 1992) ROM access: generals, provinces, faces, strategy map, battle maps.

All offsets are PRG offsets (file offset - 0x10). See docs/ROM_FORMAT.md.
"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Sangokushi II - Haou no Tairiku (Japan).zip")

PRG_SIZE = 0x40000
CHR_START = 0x10 + PRG_SIZE
BANK = 0x2000

# bank 16 ($8000 when the game maps 0x30): text and the initial game data
GENERAL_NAMES = 0x2101A       # 237 x 10 bytes katakana, 00 padding
PROVINCE_READINGS = 0x21A1A   # 30 x 8 bytes katakana
ITEM_POINTERS = 0x21B12       # 32 x LE16 (+$8000): [CHR bank, 8 upper tiles, 8 lower tiles] (16x16 kanji)
NEIGHBOURS = 0x21D72          # 30 x 8 bytes: adjacent provinces, FF padding
NEIGHBOUR_VALUES = 0x21E62    # 30 x 8 bytes: one value 0-3 per neighbour (meaning unknown)
INITIAL_DATA = 0x20C00        # copied to WRAM $6000 at game start (provinces)
PROVINCE_SIZE = 32
GENERAL_TABLE = 0x22000       # = WRAM $63C0, 237 x 12 bytes
GENERAL_SIZE = 12
MAP_NAMETABLE = 0x20000       # strategy map nametable (rows 0-19) + attribute table at +0x3C0
# bank 29 $A000
PROVINCE_KANJI = 0x3B683      # 30 x 13 bytes: [CHR bank, 6 upper tiles, 6 lower tiles]
# bank 28 $C000
CASTLE_X = 0x39EE9            # $DEE9: 30 bytes
CASTLE_Y = 0x39F07            # $DF07: 30 bytes (sprite y; drawn one line lower)
CASTLE_TILE = 0x39FC0         # $DFC0: 8 bytes, castle sprite tile per lord (7 = no lord)
CASTLE_ATTR = 0x39FC8         # $DFC8: 8 bytes, castle sprite attribute per lord
# bank 26 $C000 / bank 1 $8000: faces
FACE_BANK = 0x34ED6           # $CED6: 237 bytes, 1 KB CHR bank of the face
FACE_BASE = 0x39A0            # $99A0: 237 bytes, template index 0/5/10/15 (+ expression 0-4)
FACE_HEAD = 0x3AA0            # $9AA0: 20 x LE16 -> head sprites [dy, tile, attr, dx], 0x80 end
FACE_PARTS = 0x3BAC           # $9BAC: 20 x LE16 -> eyes + mouth sprites
FACE_TALK = 0x3D64            # $9D64: 20 x LE16 -> eyes + open mouth (talking frame)
FACE_W, FACE_H = 32, 40
FACE_PALETTE = bytes([0x0F, 0x20, 0x27, 0x17])  # sprite sub-palette 3
EXPRESSIONS = 5
# fixed bank
MAP_PALETTE = 0x3DBEB         # $DBEB: 32 bytes, strategy map BG + sprites
BATTLE_PALETTE = 0x3DC0B      # $DC0B: 16 bytes, battle BG
METATILES = 0x3F477           # $F477: 124 x [TL, TR, BL, BR]
METATILE_COUNT = 124
CHR_PRESETS = 0x346C          # bank 1 $946C: 16 bytes per screen mode = CHR banks per IRQ band
# battle maps: bank 24 $DF4A -> 4 block ids; bank 23 $A642 block pointers, $A822 block banks
BATTLE_LAYOUTS = 0x31F4A
BLOCK_POINTERS = 0x2E642       # 120 x LE16: metatile ids of a block
BLOCK_ATTRS = 0x2E732          # 120 x LE16: its 64-byte attribute table (stored just before the cells)
BLOCK_BANKS = 0x2E822
BATTLE_W, BATTLE_H = 32, 20   # metatiles (16x16 px); upper blocks 16x15, lower blocks 16x5
TOP_ROWS, BOTTOM_ROWS = 15, 5
BATTLE_CHR = (0x88, 0x89, 0x8A, 0x88)  # BG $1000 banks (screen mode 3; the game cycles slot 4 for water)

GENERAL_COUNT = 237
PROVINCE_COUNT = 30
LORDS = ["董卓", "袁紹", "曹操", "孫策", "劉備", "劉璋", "馬騰"]  # owner ids 0-6 (lord select kanji tiles)
LORD_KANA = ["トウタク", "エンショウ", "ソウソウ", "ソンサク", "リュウビ", "リュウショウ", "バトウ"]
NO_LORD = 7
ARMY_TYPES = {0: "平", 1: "山", 2: "水", 3: "?"}
STATUS = {1: "在野", 2: "仕官", 3: "?"}
# kanji as drawn by the game (glyphs read from the CHR tiles of PROVINCE_KANJI / ITEM_POINTERS)
PROVINCE_KANJI_NAMES = [
    "遼東", "幽州", "并州", "青州", "冀州", "西安陽", "涼州", "安定", "長安", "西平関", "徐州", "兗州", "洛陽", "新野",
    "予州", "建業", "揚州", "建安", "交州", "郁林", "江夏", "荊州", "衡陽", "長沙", "零陵", "漢中", "成都", "涪陵",
    "雲南", "永昌"]
ITEM_NAMES = [
    "短剣", "飛剣", "長剣", "破斬剣", "大剣", "青釭の剣", "倚天の剣", "七星宝剣", "薙刀", "眉尖刀", "三尖刀", "鉤鎌刀",
    "偃月刀", "鳳嘴刀", "龍牙刀", "関王刀", "矛", "双戟", "単鈎鎗", "戦斧", "雙鈎鎗", "方天画戟", "狼牙鎗", "蛇矛",
    "綸巾", "籠手", "兜", "硬皮", "鶴氅", "甲冑", "聖者の衣", "竜鱗の鎧"]

KATA = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンー"
HIRA = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
SMALL = {0x35: "ャ", 0x36: "ュ", 0x37: "ョ", 0x38: "ッ", 0x01: " "}
DAKUTEN = {c: chr(ord(c) + 1) for c in "かきくけこさしすせそたちつてとはひふへほカキクケコサシスセソタチツテトハヒフヘホ"}
HANDAKUTEN = {c: chr(ord(c) + 2) for c in "はひふへほハヒフヘホ"}

# NES 2C02 palette (common emulator approximation), index = NES colour number
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


def read_rom(path: str) -> bytes:
    """Read a .nes file, or the single .nes inside a .zip (as stored in roms/)."""
    if path.lower().endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            (name,) = [n for n in z.namelist() if n.lower().endswith(".nes")]
            return z.read(name)
    with open(path, "rb") as f:
        return f.read()


def char(b: int) -> str:
    if 0x04 <= b <= 0x32:
        return KATA[b - 0x04]
    if 0x44 <= b <= 0x71:
        return HIRA[b - 0x44]
    if 0x76 <= b <= 0x7F:
        return str(b - 0x76)
    return SMALL.get(b, f"{{{b:02X}}}")


def text(raw: bytes) -> str:
    """Tile-id text, 00 = end; 39 / 3A (dakuten / handakuten) follow the character they modify."""
    s = ""
    for b in raw:
        if b == 0x00:
            break
        if b in (0x39, 0x3A) and s:
            table = DAKUTEN if b == 0x39 else HANDAKUTEN
            s = s[:-1] + table.get(s[-1], s[-1] + ("゛" if b == 0x39 else "゜"))
        else:
            s += char(b)
    return s


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.data = read_rom(path)
        assert self.data[:4] == b"NES\x1a" and self.data[4] == 16 and self.data[5] == 32, "not the expected ROM"
        assert (self.data[6] >> 4 | self.data[7] & 0xF0) == 19, "not mapper 19"
        self.prg = self.data[0x10:CHR_START]
        self.chr = self.data[CHR_START:]

    def u16(self, o: int) -> int:
        return self.prg[o] | self.prg[o + 1] << 8

    # ------------------------------------------------------------ names

    def general_name(self, i: int) -> str:
        return text(self.prg[GENERAL_NAMES + 10 * i:GENERAL_NAMES + 10 * i + 10])

    def province_reading(self, i: int) -> str:
        return text(self.prg[PROVINCE_READINGS + 8 * i:PROVINCE_READINGS + 8 * i + 8])

    def lord_general(self, owner: int) -> int:
        return [self.general_name(g) for g in range(GENERAL_COUNT)].index(LORD_KANA[owner])

    # ------------------------------------------------------------ records (initial game data, 189 年 1 月)

    def general(self, i: int) -> dict:
        r = self.prg[GENERAL_TABLE + GENERAL_SIZE * i:GENERAL_TABLE + GENERAL_SIZE * (i + 1)]
        return {
            "index": i, "name": self.general_name(i),
            "body": r[0], "war": r[1], "intellect": r[2], "loyalty": r[3], "virtue": r[4], "b5": r[5],
            "exp_raw": r[6] | r[7] << 8, "exp": (r[6] | r[7] << 8) * 2 // 100,
            "troops": r[8] | (r[9] & 3) << 8, "weapon": r[10] & 0x1F, "armour": 24 + (r[10] >> 5),
            "status": r[11] & 3, "army": (r[11] >> 2) & 3, "level": (r[11] >> 4) + 1, "raw": bytes(r),
        }

    def generals(self) -> list[dict]:
        out = [self.general(i) for i in range(GENERAL_COUNT)]
        for p in self.provinces():
            for g in p["generals"]:
                out[g]["province"] = p["index"]
        return out

    def province(self, i: int) -> dict:
        o = INITIAL_DATA + PROVINCE_SIZE * i
        r = self.prg[o:o + PROVINCE_SIZE]

        def u16(k):
            return r[k] | r[k + 1] << 8

        return {
            "index": i, "name": PROVINCE_KANJI_NAMES[i], "reading": self.province_reading(i), "owner": r[0],
            "b1": r[1], "gold": u16(2), "rice": u16(4), "population": u16(6) * 100, "land": u16(8),
            "disaster": r[10], "rule": r[11], "b12": u16(12), "industry": u16(14), "b16": r[16],
            "generals": [g for g in r[17:27] if g != 0xFF], "raw": bytes(r),
        }

    def provinces(self) -> list[dict]:
        return [self.province(i) for i in range(PROVINCE_COUNT)]

    def neighbours(self, i: int) -> list[tuple[int, int]]:
        """(province, value) pairs in ROM order."""
        a, v = NEIGHBOURS + 8 * i, NEIGHBOUR_VALUES + 8 * i
        return [(self.prg[a + k], self.prg[v + k]) for k in range(8) if self.prg[a + k] != 0xFF]

    def castle(self, i: int) -> tuple[int, int]:
        return self.prg[CASTLE_X + i], self.prg[CASTLE_Y + i]

    # ------------------------------------------------------------ CHR helpers

    def tile_rows(self, offset: int) -> list[list[int]]:
        b = self.chr[offset:offset + 16]
        return [[((b[y] >> (7 - x)) & 1) | (((b[y + 8] >> (7 - x)) & 1) << 1) for x in range(8)] for y in range(8)]

    def bank_tile(self, bank: int, tile: int) -> list[list[int]]:
        """Tile `tile` (only the low 6 bits select inside the 1 KB bank)."""
        return self.tile_rows((bank * 0x400 + (tile & 63) * 16) % len(self.chr))

    def render_nametable(self, tiles: bytes, attrs: bytes, rows: int, banks, palette: bytes) -> bytes:
        """32-column nametable rows -> 256 x rows*8 NES colour numbers; banks(row) -> 4 x 1 KB at $1000."""
        out = bytearray(256 * rows * 8)
        for row in range(rows):
            bk = banks(row)
            for col in range(32):
                t = tiles[row * 32 + col]
                sub = (attrs[(row // 4) * 8 + col // 4] >> (((row & 2) << 1) | (col & 2))) & 3
                for y, line in enumerate(self.bank_tile(bk[t >> 6], t)):
                    for x, c in enumerate(line):
                        out[(row * 8 + y) * 256 + col * 8 + x] = palette[sub * 4 + c if c else 0] & 0x3F
        return bytes(out)

    def kanji_pixels(self, record: bytes, width: int) -> tuple[int, bytes]:
        """[bank, `width` upper tiles, `width` lower tiles] -> (pixel width, 2-colour 0/1 pixels 16 high)."""
        bank, w = record[0], width * 8
        px = bytearray(w * 16)
        for row in range(2):
            for k in range(width):
                t = record[1 + row * width + k]
                if t == 0x01:
                    continue
                for y, line in enumerate(self.bank_tile(bank, t)):
                    for x, c in enumerate(line):
                        px[(row * 8 + y) * w + k * 8 + x] = 1 if c else 0
        return w, bytes(px)

    def item_record(self, i: int) -> bytes:
        p = 0x20000 + (self.u16(ITEM_POINTERS + 2 * i) & 0x1FFF)
        return self.prg[p:p + 17]

    def province_kanji_record(self, i: int) -> bytes:
        return self.prg[PROVINCE_KANJI + 13 * i:PROVINCE_KANJI + 13 * i + 13]

    # ------------------------------------------------------------ faces

    def face_of(self, i: int) -> tuple[int, int]:
        """(1 KB CHR bank, template index) of general i's face."""
        return self.prg[FACE_BANK + i], self.prg[FACE_BASE + i]

    def faces(self) -> list[tuple[int, int]]:
        """Distinct faces in order of first use by general id."""
        return list(dict.fromkeys(self.face_of(i) for i in range(GENERAL_COUNT)))

    def sprite_list(self, ptr: int) -> list[tuple[int, int, int, int]]:
        o = self.u16(ptr) - 0x8000 + BANK
        out = []
        while self.prg[o] != 0x80:
            out.append(tuple(self.prg[o:o + 4]))
            o += 4
        return out

    def face_sprites(self, base: int, expression: int = 0, talk: bool = False) -> list[tuple[int, int, int, int]]:
        """[dy, tile, attr, dx] in OAM order: head, then eyes + mouth (the game's $CE37 / $F1B7)."""
        k = 2 * (base + expression)
        return self.sprite_list(FACE_HEAD + k) + self.sprite_list((FACE_TALK if talk else FACE_PARTS) + k)

    def face_pixels(self, face: tuple[int, int], expression: int = 0, talk: bool = False) -> bytes:
        """32x40 NES colour numbers; earlier sprites win (NES sprite priority). Tiles $80+ = CHR slot 2."""
        bank, base = face
        px = bytearray([FACE_PALETTE[0]]) * (FACE_W * FACE_H)
        done = [False] * (FACE_W * FACE_H)
        for dy, tile, attr, dx in self.face_sprites(base, expression, talk):
            rows = self.bank_tile(bank, tile - 0x80)
            for y in range(8):
                for x in range(8):
                    c = rows[y][7 - x if attr & 0x40 else x]
                    i = (dy + y) * FACE_W + dx + x
                    if c and not done[i]:
                        px[i], done[i] = FACE_PALETTE[c], True
        return bytes(px)

    # ------------------------------------------------------------ strategy map

    def chr_preset(self, mode: int) -> bytes:
        return self.prg[CHR_PRESETS + 16 * mode:CHR_PRESETS + 16 * mode + 48]

    def map_pixels(self, castles: bool = True) -> bytes:
        """Strategy map (nametable rows 0-19) with each castle in its lord's colour, 256 x 160."""
        nt = self.prg[MAP_NAMETABLE:MAP_NAMETABLE + 0x400]
        pal = self.prg[MAP_PALETTE:MAP_PALETTE + 32]
        preset = self.chr_preset(0)  # 6 x 8 banks: band 0, message window, bands 1-4 (32 lines each)
        bands = [preset[0:8]] + [preset[8 * k:8 * k + 8] for k in range(2, 6)]
        px = bytearray(self.render_nametable(nt, nt[0x3C0:], 20, lambda r: bands[r // 4][4:8], pal))
        if castles:
            for i in range(PROVINCE_COUNT):
                x, y = self.castle(i)
                owner = self.province(i)["owner"]
                tile, attr = self.prg[CASTLE_TILE + owner], self.prg[CASTLE_ATTR + owner]
                for dy, line in enumerate(self.bank_tile(preset[0], tile)):
                    for dx, c in enumerate(line):
                        if c and y + 1 + dy < 160 and x + dx < 256:
                            px[(y + 1 + dy) * 256 + x + dx] = pal[16 + (attr & 3) * 4 + c] & 0x3F
        return bytes(px)

    # ------------------------------------------------------------ battle maps

    def battle_blocks(self, i: int) -> list[int]:
        """Block ids [upper left, upper right, lower left, lower right] of province i's battlefield."""
        p = self.u16(BATTLE_LAYOUTS + 2 * i) - 0xC000 + 24 * BANK
        a, b, c, d = self.prg[p:p + 4]
        return [a, b, c, d]

    def block(self, b: int, rows: int) -> tuple[bytes, bytes]:
        """(rows x 16 metatile ids, 64 attribute bytes) of block b."""
        base = (self.prg[BLOCK_BANKS + b] & 31) * BANK - 0x8000
        o, a = base + self.u16(BLOCK_POINTERS + 2 * b), base + self.u16(BLOCK_ATTRS + 2 * b)
        return self.prg[o:o + 16 * rows], self.prg[a:a + 64]

    def battle_cells(self, i: int) -> bytes:
        """32 x 20 metatile ids of province i's battlefield."""
        ul, ur, ll, lr = self.battle_blocks(i)
        out = bytearray()
        for (left, right), rows in (((ul, ur), TOP_ROWS), ((ll, lr), BOTTOM_ROWS)):
            lc, rc = self.block(left, rows)[0], self.block(right, rows)[0]
            for r in range(rows):
                out += lc[16 * r:16 * r + 16] + rc[16 * r:16 * r + 16]
        return bytes(out)

    def battle_block_nametable(self, b: int, rows: int) -> tuple[bytes, bytes]:
        """One block as the game streams it: nametable (2 x rows tile rows) + its attribute table."""
        cells, attrs = self.block(b, rows)
        nt = bytearray(32 * 2 * rows)
        for k, t in enumerate(cells):
            r, c = divmod(k, 16)
            m = self.prg[METATILES + 4 * t:METATILES + 4 * t + 4]
            nt[(2 * r) * 32 + 2 * c:(2 * r) * 32 + 2 * c + 2] = m[:2]
            nt[(2 * r + 1) * 32 + 2 * c:(2 * r + 1) * 32 + 2 * c + 2] = m[2:]
        return bytes(nt), attrs

    def battle_tiles(self, i: int) -> tuple[list[list[int]], list[list[int]]]:
        """(tile ids, BG sub-palettes) of the 64 x 40 tile battlefield."""
        tiles = [[0] * 64 for _ in range(40)]
        subs = [[0] * 64 for _ in range(40)]
        for n, b in enumerate(self.battle_blocks(i)):
            rows = TOP_ROWS if n < 2 else BOTTOM_ROWS
            nt, attrs = self.battle_block_nametable(b, rows)
            for r in range(2 * rows):
                for c in range(32):
                    tiles[30 * (n >> 1) + r][32 * (n & 1) + c] = nt[r * 32 + c]
                    a = attrs[(r // 4) * 8 + c // 4]
                    subs[30 * (n >> 1) + r][32 * (n & 1) + c] = (a >> (((r & 2) << 1) | (c & 2))) & 3
        return tiles, subs

    def battle_pixels(self, i: int) -> bytes:
        """512 x 320 NES colour numbers (2 x 2 blocks; the lower blocks are 80 px high)."""
        pal = self.prg[BATTLE_PALETTE:BATTLE_PALETTE + 16]
        out = bytearray(512 * 320)
        for n, b in enumerate(self.battle_blocks(i)):
            rows = TOP_ROWS if n < 2 else BOTTOM_ROWS
            nt, attrs = self.battle_block_nametable(b, rows)
            px = self.render_nametable(nt, attrs, 2 * rows, lambda r: BATTLE_CHR, pal)
            x0, y0 = 256 * (n & 1), 240 * (n >> 1)
            for y in range(16 * rows):
                out[(y0 + y) * 512 + x0:(y0 + y) * 512 + x0 + 256] = px[y * 256:y * 256 + 256]
        return bytes(out)
