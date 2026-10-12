"""FC 三國志 中原の覇者 (Namco, 1988) ROM decoding.

All offsets are PRG offsets (file offset - 0x10). Mapper 19 (Namco 163): 8 KB PRG banks, 1 KB CHR
banks. See chuugen/docs/ROM_FORMAT.md.
"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Sangokushi - Chuugen no Hasha (Japan).zip")

PRG_SIZE = 0x20000
CHR_START = 0x10 + PRG_SIZE
BANK = 0x2000

# ---------------------------------------------------------------- bank 1 ($8000): header of 9 pointers
DATA_BANK = 1
PROVINCE_NAMES = 0x261C        # 30 x 8 bytes: 6 chars (01 = blank), 2 dakuten bytes for the row above
NAME_POINTERS = 0x2012         # 241 x LE16 -> general name (last char has bit 7 cleared)
INITIAL_DATA = 0x270C          # 0xC30 bytes copied to WRAM $6000 at game start
TOKU_TABLE = 0x32CC            # 241 bytes: 徳 per general
DEPLOY_A = 0x34CB              # 30 x 16 bytes: battle start cells (y << 4 | x), one table per side
DEPLOY_B = 0x36AB
PROVINCE_COUNT = 30
GENERAL_COUNT = 241
LORD_COUNT = 6                 # generals 0-5 are the lords, in lord-id order
WRAM = 0x6000
PROVINCE_START, PROVINCE_SIZE = 0x000, 36   # WRAM $6000
GENERAL_START, GENERAL_SIZE = 0x438, 8      # WRAM $6438 (accessor $F829)
START_YEAR, START_MONTH = 200, 1

# ---------------------------------------------------------------- faces (sprites, fixed bank $F000-$FFFF)
FACE_BANK_TABLE = 0x1F53B      # $F53B: 241 bytes, 1 KB CHR bank of the general's face
FACE_BLOCK_TABLE = 0x1F62C     # $F62C: 241 bytes, 16-tile block (0-3) inside that bank
FACE_EXPR_POINTERS = 0x1F513   # $F513: 4 expressions x 2 mouth frames -> 3 tiles (left eye, right eye, mouth)
FACE_TEMPLATE = 0x1F71D        # $F71D: 14 sprites [dy, tile, attr, dx], 0x80 end; tiles relative to $80
FACE_W, FACE_H = 24, 32
# sprite sub-palette 2 on the status screen (colour 0 shows the black backdrop)
FACE_PALETTE = bytes([0x0F, 0x20, 0x27, 0x17])
EXPRESSIONS = 4

# ---------------------------------------------------------------- strategy map (fixed bank / bank 12 / bank 2)
CASTLE_X = 0x1DE65             # $DE65: 30 bytes, castle sprite x (also the cursor hit box origin, 16x16)
CASTLE_Y = 0x1DE83             # $DE83: 30 bytes, castle sprite y
REGION_FLAGS = 0x1DEA1         # $DEA1: 30 bytes, 00/40/80 = the same bits 6-7 as the province owner byte
CASTLE_TILE = 0x1DE59          # $DE59: 6 bytes, castle sprite tile per lord; $DE5F: 6 bytes, sprite attribute
CASTLE_ATTR = 0x1DE5F
NEIGHBOUR_POINTERS = 0x19A40   # bank 12 $9A40: 30 x LE16 -> [province, road id] pairs, FF end (checked at $BE29)
SCREEN_ARCHIVE = 0x1C000       # CHR 1 KB banks 112-119: LE16 directory, RLE screens (FF value count, 0 = 256)
MAP_SCREEN = 0                 # 2 nametables: 0 = terrain map, 1 = road map (ミチをみる)
MAP_ROWS = 20                  # rows 20-29 are the message window
MAP_CHR = (4, 5, 14, 7)        # BG pattern table $1000 banks above the IRQ split (terrain map)
ROAD_CHR = (22, 23, 14, 7)     # same for the road map
SPRITE_CHR = (0, 92)           # sprite pattern table $0000-$07FF banks on the map
MAP_PALETTE = 0x4C6E           # bank 2: 32 bytes, BG + sprite palettes of the strategy map
ROAD_PALETTE = 0x19A30         # bank 12 $9A30: 8 bytes, BG sub-palettes 0-1 of the road map ($9A00 = fade steps)

# ---------------------------------------------------------------- battle maps (bank 2 $8020, bank 7 $ADCB)
BATTLE_HEADER = 0x4020         # bank 2 $8020: LE16 metatile table, LE16 map base (PPU-style address in CHR)
BATTLE_W, BATTLE_H = 16, 10    # cells of 16x16 px; the battle map of province i is fought there when attacked
BATTLE_RECORD = 0xE0           # 64 attribute bytes (written to $23C0 as they are) + 160 cell types
BATTLE_CHR = (36, 37, 6, 7)    # BG pattern table $1000 banks on the battle screen
BATTLE_PALETTE = 0x4CCE        # bank 2: 32 bytes ($B231 copies it); the map uses sub-palettes 0-1
BATTLE_TERRAIN = {0: "城", 1: "川", 2: "山", 4: "森", 5: "平地", 6: "荒地", 7: "（上緣空列）"}

LORDS = ["袁紹", "馬騰", "曹操", "孫権", "劉備", "劉璋"]
# army type = general byte 6 high nibble (0-2 used); glyphs from the 2x2-tile table at $B6CB (bank 7 at $A000)
ARMY_TYPES = {0: "平", 1: "木", 2: "山"}

# ---------------------------------------------------------------- text = CHR tile ids of pattern table 1
HIRA = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん・？"
KATA = "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワヲンー！"
SMALL = {0xFA: "ャ", 0xFB: "ュ", 0xFC: "ョ", 0xFD: "ッ", 0xB5: "ゃ", 0xB6: "ゅ", 0xB7: "ょ", 0xB8: "っ", 0x01: " "}
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
    if 0x80 <= b < 0xB0:
        return HIRA[b - 0x80]
    if 0xC0 <= b < 0xF0:
        return KATA[b - 0xC0]
    if 0x60 <= b < 0x6A:
        return str(b - 0x60)
    if 0xF0 <= b < 0xFA:
        return str(b - 0xF0)
    return SMALL.get(b, f"{{{b:02X}}}")


def mark(s: str, b: int) -> str:
    """Apply dakuten (FE) / handakuten (FF) to the last character of s."""
    if not s:
        return s
    table = DAKUTEN if b == 0xFE else HANDAKUTEN
    return s[:-1] + table.get(s[-1], s[-1] + ("゛" if b == 0xFE else "゜"))


def text(raw: bytes) -> str:
    """Tile-id text; FE / FF follow the character they modify."""
    s = ""
    for b in raw:
        s = mark(s, b) if b in (0xFE, 0xFF) else s + char(b)
    return s


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.data = read_rom(path)
        assert self.data[:4] == b"NES\x1a" and self.data[4] == 8 and self.data[5] == 16, "not the expected ROM"
        assert (self.data[6] >> 4 | self.data[7] & 0xF0) == 19, "not mapper 19"
        self.prg = self.data[0x10:CHR_START]
        self.chr = self.data[CHR_START:]
        self.wram = self.prg[INITIAL_DATA:INITIAL_DATA + 0xC30]

    # ------------------------------------------------------------ names

    def general_name_raw(self, i: int) -> bytes:
        o = NAME_POINTERS + 2 * i
        p = (self.prg[o] | self.prg[o + 1] << 8) - 0x8000 + DATA_BANK * BANK
        out = bytearray()
        while True:
            b = self.prg[p]
            p += 1
            last = b < 0x80
            out.append(b | 0x80)
            if last:
                return bytes(out)

    def general_name(self, i: int) -> str:
        """Name in katakana as the game shows it (the ROM has no kanji names, except the 6 lords' tiles)."""
        return text(self.general_name_raw(i))

    def province_name(self, i: int) -> str:
        """6 chars on the lower row; bytes 6-7 are marks on the row above (Bank 3 $A27A).

        5-char names start one column right, so byte 6 sits above char 0 and byte 7 above char 2;
        a 6-char name is shifted left one column and its marks sit above chars 1 and 3.
        """
        r = self.prg[PROVINCE_NAMES + 8 * i:PROVINCE_NAMES + 8 * i + 8]
        chars = [char(b) for b in r[:6]]
        shift = 0 if r[5] == 0x01 else 1
        for k, b in ((shift, r[6]), (shift + 2, r[7])):
            if b in (0xFE, 0xFF):
                chars[k] = mark(chars[k], b)
        return "".join(chars).strip()

    def province_names(self) -> list[str]:
        return [self.province_name(i) for i in range(PROVINCE_COUNT)]

    # ------------------------------------------------------------ records (initial game data)

    def general(self, i: int) -> dict:
        r = self.wram[GENERAL_START + GENERAL_SIZE * i:GENERAL_START + GENERAL_SIZE * (i + 1)]
        return {
            "index": i, "name": self.general_name(i), "flags": r[0],
            "body": r[1], "intellect": r[2], "war": r[3], "virtue": self.prg[TOKU_TABLE + i],
            "loyalty": None if r[5] == 0xFF else r[5],
            "army": r[6] >> 4, "b6_low": r[6] & 15, "b4_low": r[4] & 15,
            "troops": [(r[7] >> 4) * 100, (r[7] & 15) * 100, (r[4] >> 4) * 100],
            "face": self.face_of(i), "raw": bytes(r),
        }

    def generals(self) -> list[dict]:
        out = [self.general(i) for i in range(GENERAL_COUNT)]
        for p in self.provinces():
            for g in p["generals"]:
                out[g]["province"] = p["index"]
        return out

    def province(self, i: int) -> dict:
        r = self.wram[PROVINCE_START + PROVINCE_SIZE * i:PROVINCE_START + PROVINCE_SIZE * (i + 1)]

        def u16(o):
            return r[o] | r[o + 1] << 8

        return {
            "index": i, "name": self.province_name(i), "owner": r[0] & 7, "owner_flags": r[0] & 0xF8,
            "gold": u16(1), "land": u16(4), "industry": u16(6),
            "population": r[8] | r[9] << 8 | r[10] << 16 | r[11] << 24, "rule": u16(14),
            "generals": [g for g in r[16:28] if g != 0xFF], "raw": bytes(r),
        }

    def provinces(self) -> list[dict]:
        return [self.province(i) for i in range(PROVINCE_COUNT)]

    def deploy_cells(self, side: int, i: int) -> list[tuple[int, int]]:
        """16 (x, y) battle start cells of province i for side 0 (DEPLOY_A) or 1 (DEPLOY_B)."""
        o = (DEPLOY_A if side == 0 else DEPLOY_B) + 16 * i
        return [(b & 15, b >> 4) for b in self.prg[o:o + 16]]

    # ------------------------------------------------------------ faces

    def face_of(self, i: int) -> tuple[int, int]:
        """(1 KB CHR bank, 16-tile block) of general i's face."""
        return self.prg[FACE_BANK_TABLE + i], self.prg[FACE_BLOCK_TABLE + i]

    def faces(self) -> list[tuple[int, int]]:
        """Distinct faces in order of first use by general id."""
        return list(dict.fromkeys(self.face_of(i) for i in range(GENERAL_COUNT)))

    def sprite_tile(self, bank: int, tile: int) -> list[list[int]]:
        """Sprite tile $00-$FF with `bank` in CHR slot 2 ($0800): tile $80 + n -> bank offset n * 16."""
        o = (bank * 0x400 + (tile - 0x80) * 16) % len(self.chr)
        b = self.chr[o:o + 16]
        return [[((b[y] >> (7 - x)) & 1) | (((b[y + 8] >> (7 - x)) & 1) << 1) for x in range(8)] for y in range(8)]

    def face_sprites(self, expression: int = 0, mouth: int = 0) -> list[tuple[int, int, int, int]]:
        """(dx, dy, tile, attr) of the 14 face sprites, OAM order (the game's $F47A)."""
        t = self.prg[FACE_TEMPLATE:FACE_TEMPLATE + 0x39]
        sprites = [[t[k + 3], t[k] - 0xE0, t[k + 1], t[k + 2]] for k in range(0, 56, 4)]
        o = FACE_EXPR_POINTERS + 4 * expression + 2 * mouth
        p = (self.prg[o] | self.prg[o + 1] << 8) - 0xE000 + 15 * BANK
        for k in range(3):
            sprites[11 + k][2] = self.prg[p + k]
        return [tuple(s) for s in sprites]

    def face_pixels(self, face: tuple[int, int], expression: int = 0, mouth: int = 0) -> bytes:
        """24x32 NES colour numbers; earlier sprites win (NES sprite priority)."""
        bank, block = face
        px = bytearray([FACE_PALETTE[0]]) * (FACE_W * FACE_H)
        done = [False] * (FACE_W * FACE_H)
        for dx, dy, tile, attr in self.face_sprites(expression, mouth):
            rows = self.sprite_tile(bank, tile + block * 16)
            for y in range(8):
                for x in range(8):
                    c = rows[y][7 - x if attr & 0x40 else x]
                    i = (dy + y) * FACE_W + dx + x
                    if c and not done[i]:
                        px[i], done[i] = FACE_PALETTE[c], True
        return bytes(px)

    # ------------------------------------------------------------ CHR helpers

    def tile_rows(self, offset: int) -> list[list[int]]:
        b = self.chr[offset:offset + 16]
        return [[((b[y] >> (7 - x)) & 1) | (((b[y + 8] >> (7 - x)) & 1) << 1) for x in range(8)] for y in range(8)]

    def render_nametable(self, tiles: bytes, attrs: bytes, rows: int, banks: tuple, palette: bytes) -> bytes:
        """32-column nametable rows -> 256 x rows*8 NES colour numbers; banks = 4 x 1 KB at $1000."""
        out = bytearray(256 * rows * 8)
        for row in range(rows):
            for col in range(32):
                t = tiles[row * 32 + col]
                sub = (attrs[(row // 4) * 8 + col // 4] >> (((row & 2) << 1) | (col & 2))) & 3
                for y, line in enumerate(self.tile_rows(banks[t >> 6] * 0x400 + (t & 63) * 16)):
                    for x, c in enumerate(line):
                        out[(row * 8 + y) * 256 + col * 8 + x] = palette[sub * 4 + c if c else 0] & 0x3F
        return bytes(out)

    # ------------------------------------------------------------ strategy map

    def screen(self, index: int) -> bytes:
        """RLE screen `index` of the CHR archive (2 KB = nametables 0 and 1, as $AD20 writes them)."""
        a = self.chr[SCREEN_ARCHIVE:SCREEN_ARCHIVE + 0x2000]
        o = a[2 * index] | (a[2 * index + 1] & 0x1F) << 8
        out = bytearray()
        while len(out) < 0x800:
            b = a[o]
            o += 1
            if b == 0xFF:
                out += bytes([a[o]]) * (a[o + 1] or 256)
                o += 2
            else:
                out.append(b)
        return bytes(out[:0x800])

    def castles(self) -> list[tuple[int, int]]:
        return [(self.prg[CASTLE_X + i], self.prg[CASTLE_Y + i]) for i in range(PROVINCE_COUNT)]

    def region_flag(self, i: int) -> int:
        return self.prg[REGION_FLAGS + i]

    def neighbours(self, i: int) -> list[tuple[int, int]]:
        """(province, road id) pairs in ROM order."""
        o = NEIGHBOUR_POINTERS + 2 * i
        p = (self.prg[o] | self.prg[o + 1] << 8) - 0x8000 + 12 * BANK
        out = []
        while self.prg[p] != 0xFF:
            out.append((self.prg[p], self.prg[p + 1]))
            p += 2
        return out

    def map_pixels(self, roads: bool = False, castles: bool = True) -> bytes:
        """Terrain map (or road map) with each castle in its 6 lords' colours, 256 x 160."""
        nt = self.screen(MAP_SCREEN)[0x400 if roads else 0:][:0x400]
        pal = self.prg[MAP_PALETTE:MAP_PALETTE + 32]
        if roads:
            pal = self.prg[ROAD_PALETTE:ROAD_PALETTE + 8] + pal[8:]
        px = bytearray(self.render_nametable(nt, nt[0x3C0:], MAP_ROWS, ROAD_CHR if roads else MAP_CHR, pal))
        if castles:
            for i, (x, y) in enumerate(self.castles()):
                owner = self.province(i)["owner"]
                tile, attr = self.prg[CASTLE_TILE + owner], self.prg[CASTLE_ATTR + owner]
                bank = SPRITE_CHR[tile >> 6]
                for dy, line in enumerate(self.tile_rows(bank * 0x400 + (tile & 63) * 16)):
                    for dx, c in enumerate(line):
                        if c and y + 1 + dy < MAP_ROWS * 8:
                            px[(y + 1 + dy) * 256 + x + dx] = pal[16 + (attr & 3) * 4 + c] & 0x3F
        return bytes(px)

    # ------------------------------------------------------------ battle maps

    def battle_record(self, i: int) -> tuple[bytes, bytes]:
        """(64 attribute bytes, 160 cell types) of province i's battle map."""
        h = self.prg[BATTLE_HEADER:BATTLE_HEADER + 4]
        a = ((h[2] | h[3] << 8) + BATTLE_RECORD * i) & 0x7FFF
        o = 0x18000 + a
        return self.chr[o:o + 64], self.chr[o + 64:o + 64 + BATTLE_W * BATTLE_H]

    def battle_nametable(self, i: int) -> tuple[bytes, bytes]:
        """Rows 0-19 of the battle nametable (metatile table, $AEE3) and its attribute table."""
        h = self.prg[BATTLE_HEADER:BATTLE_HEADER + 4]
        mt = (h[0] | h[1] << 8) - 0x8000 + 2 * BANK
        attrs, cells = self.battle_record(i)
        nt = bytearray(32 * BATTLE_H * 2)
        for k, t in enumerate(cells):
            r, c = divmod(k, BATTLE_W)
            m = self.prg[mt + 4 * t:mt + 4 * t + 4]
            nt[(2 * r) * 32 + 2 * c:(2 * r) * 32 + 2 * c + 2] = m[:2]
            nt[(2 * r + 1) * 32 + 2 * c:(2 * r + 1) * 32 + 2 * c + 2] = m[2:]
        return bytes(nt), attrs

    def battle_pixels(self, i: int) -> bytes:
        """256 x 160 NES colour numbers."""
        nt, attrs = self.battle_nametable(i)
        pal = self.prg[BATTLE_PALETTE:BATTLE_PALETTE + 32]
        return self.render_nametable(nt, attrs, BATTLE_H * 2, BATTLE_CHR, pal)
