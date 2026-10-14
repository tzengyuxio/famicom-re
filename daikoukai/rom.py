"""FC 大航海時代 (KOEI, 1991) ROM decoding.

All offsets are PRG offsets (file offset - 0x10). See daikoukai/docs/ROM_FORMAT.md.
"""
import os
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Daikoukai Jidai (Japan).zip")

PRG_SIZE = 0x80000
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


def text(raw: bytes) -> str:
    """Half-width kana text up to the first 0: hiragana by default, ESC K / ESC H switch katakana on / off."""
    out, kata, i = "", False, 0
    raw = raw.split(b"\0")[0]
    while i < len(raw):
        b = raw[i]
        if b == 0x1B and i + 1 < len(raw):
            kata = raw[i + 1] == 0x4B
            i += 2
            continue
        if 0xA1 <= b <= 0xDF:
            c = unicodedata.normalize("NFKC", bytes([b]).decode("cp932"))
            if not kata and "ァ" <= c <= "ヶ":
                c = chr(ord(c) - 0x60)
            out += c
        elif b == 0x2D:
            out += "ー"
        elif 0x20 <= b < 0x7F:
            out += chr(b)
        else:
            out += f"<{b:02X}>"
        i += 1
    return unicodedata.normalize("NFC", out.replace("ﾞ", "゙").replace("ﾟ", "゚"))


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


# ---------------------------------------------------------------- initial game state (bank 57 -> WRAM $6000)
INIT = 57 * BANK                    # bank 57 is copied to WRAM $6000 on a new game
NAMES = 58 * BANK                   # bank 58, mapped at $A000: name strings
PERSON_START, PERSON_SIZE, PERSON_COUNT = 0x542, 7, 41   # $6542: player + 40 persons
STAT_START, STAT_SIZE, STAT_COUNT = 0xBBE, 10, 21         # $6BBE: player + 20 mates
NATIONS = ["ポルトガル", "イスパニア", "イスラム", "かいぞく"]  # the game's list, PRG 0x75E36
GIRL_NAMES = 0x7400C                # bank 58 $A00C: 20 LE16 pointers
GIRL_COUNT = 20
GIRL_FACE = 13                      # face of girl k = k + 13 (bank 1 $A620)

# ---------------------------------------------------------------- faces (5 x 6 sprites, 40 x 48)
FACE_W, FACE_H = 5, 6
FACE_BANK = 35 * BANK               # bank 35 at $8000: dedicated faces
FACE_POINTERS = FACE_BANK + 0x1994  # 48 LE16 -> record: 2 CHR banks, then 30 x (dy, tile, attr, dx)
PORTRAIT_COUNT = 48
COMPOSITE_BANK = 36 * BANK          # bank 36 at $8000: composite faces (face code >= 0x1000)
COMPOSITE_CHR = COMPOSITE_BANK + 0xC56   # 4 bytes: CHR bank b of head h ($5120 = b, $5121 = b + 1)
COMPOSITE_PARTS = COMPOSITE_BANK + 0xC5A  # head h: 5 slots x 4 LE16 pointers to sprite lists
COMPOSITE_HEADS = 4
# (slot id, label, code shift): drawn in this order; a later sprite with tile 1 keeps the earlier cell
COMPOSITE_SLOTS = [("top", "上", 8), ("bottom", "下", 0), ("eyes", "眼", 6), ("nose", "鼻", 4), ("mouth", "口", 2)]
COMPOSITE_GROUP = {"top": 0, "eyes": 1, "nose": 2, "mouth": 3, "bottom": 4}  # pointer group in the table
SPRITE_PALETTE = 0x7F376            # bank 63 $F376: sprite palette used for faces


# ---------------------------------------------------------------- ports
PORTS, PORT_SIZE, PORT_COUNT = 0x752D4, 19, 70      # 15-byte name + (chunk x, chunk y, metatile x, metatile y)
PORT_INFO, PORT_INFO_COUNT = 0x75806, 50            # 5 bytes: region, specialty, ?, item, ?
REGIONS = ["地中海", "北歐", "西非", "東非", "新大陸", "阿拉伯", "遠東", "東南亞"]

# ---------------------------------------------------------------- name lists (0-separated strings)
NAME_LISTS = {                      # key: (PRG offset, strings to skip, count)
    "goods": (0x294F8, 0, 26),
    "cannons": (0x2B38B, 0, 3),
    "figureheads": (0x2B550, 0, 6),
    "ships": (0x2D0CC, 0, 6),
    "woods": (0x2D47C, 0, 4),
    "masts": (0x2D47C, 4, 3),
    "sails": (0x2D47C, 7, 2),
}

# ---------------------------------------------------------------- world map (PRG 0x60000)
MAP = 0x60000
MAP_AREAS_W, MAP_AREAS_H = 24, 12   # areas of 3 x 3 chunks
MAP_W, MAP_H = 72, 36               # chunks of 7 x 7 blocks = 14 x 14 metatiles = 28 x 28 tiles
CHUNK_TILES = 28
MAP_BLOCKS = 0x3CCA                 # bank 1 $BCCA: block -> 4 metatiles (TL, TR, BL, BR)
MAP_METATILES = 0x3BAA              # bank 1 $BBAA: set s, metatile m at +0x48 s + 4 m: (tiles ptr, ExRAM ptr)
MAP_PALETTES = 0x3A7A               # bank 1 $BA7A: 16-byte BG palette per set
MAP_GFX = 32 * BANK                 # bank 32 at $A000 holds the 2 x 2 tile / ExRAM data
MAP_BAND = [3, 2, 1, 1, 0, 0, 0, 0, 1, 1, 2, 3]   # metatile set by area row (p-code $B015)

# ---------------------------------------------------------------- port towns (bank 18)
TOWN_TYPE_SUPPLY = 0x25338          # town type of supply ports 50-69
TOWN_PIECES = 0x2534C               # per type 4 x (tiles, ExRAM): 7x4, 6x5, 6x6, 8x5 ($0000 = none)
TOWN_IMAGES = 0x253CC               # per type (tiles, ExRAM) of the 28 x 14 picture at (2, 6)
TOWN_PALETTES = 0x252B8             # 16-byte BG palette per type
TOWN_W, TOWN_H, TOWN_X, TOWN_Y = 28, 14, 2, 6
TOWN_TYPES = 8
TOWN_PIECE_SIZE = [(7, 4), (6, 5), (6, 6), (8, 5)]
TOWN_FLAGS = 0xF76                  # WRAM $6F76 + port: building flags (bank 57 holds the start values)
# (piece, x, y, flag mask, flag value) drawn over the picture by trading ports
TOWN_PIECES_PORT = [(0, 2, 6, 0x04, 0), (3, 22, 6, 0x10, 0x10)]
TOWN_PIECES_SUPPLY = [(0, 9, 6), (0, 2, 6), (0, 2, 12), (1, 16, 6), (2, 24, 14)]   # supply ports 50-69


def is_composite(code: int) -> bool:
    return code >= 0x1000


def decode_face_code(code: int) -> tuple[int, list[int]]:
    """Composite face code -> (head, page per slot in COMPOSITE_SLOTS order)."""
    return code >> 10 & 3, [code >> shift & 3 for _, _, shift in COMPOSITE_SLOTS]


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.data = read_rom(path)
        self.prg = self.data[0x10:CHR_START]
        self.chr = self.data[CHR_START:]

    def u16(self, o: int) -> int:
        return self.prg[o] | self.prg[o + 1] << 8

    def name_at(self, ptr: int) -> str:
        """String in bank 58 ($A000-based pointer)."""
        return text(self.prg[NAMES + ptr - 0xA000:NAMES + ptr - 0xA000 + 32])

    # ------------------------------------------------------------ graphics

    def sprite_pixels(self, banks: bytes, sprites: list[tuple[int, int, int, int]], w: int, h: int,
                      palette: bytes) -> bytes:
        """8x8 sprites (dy, tile, attr, dx) from CHR banks ($5120, $5121, ...) -> NES colour numbers.

        Colour 0 shows palette[0] (the backdrop); earlier sprites stay in front, as on the PPU."""
        out = bytearray([palette[0] & 0x3F]) * (w * h)
        for dy, tile, attr, dx in reversed(sprites):
            o = banks[tile >> 6] * 0x400 + (tile & 0x3F) * 16
            sub = palette[(attr & 3) * 4:(attr & 3) * 4 + 4]
            for y in range(8):
                lo, hi = self.chr[o + y], self.chr[o + 8 + y]
                for x in range(8):
                    c = (lo >> (7 - x) & 1) | (hi >> (7 - x) & 1) << 1
                    if c:
                        out[(dy + y) * w + dx + x] = sub[c] & 0x3F
        return bytes(out)

    # ------------------------------------------------------------ faces

    def portrait(self, f: int) -> tuple[bytes, list[tuple[int, int, int, int]]]:
        """Dedicated face f: (CHR banks, 30 sprites)."""
        o = FACE_BANK + self.u16(FACE_POINTERS + 2 * f) - 0x8000
        return self.prg[o:o + 2], [tuple(self.prg[o + 2 + 4 * i:o + 6 + 4 * i]) for i in range(FACE_W * FACE_H)]

    def composite_part(self, head: int, slot: str, page: int) -> list[tuple[int, int, int, int]]:
        """Sprites of one composite part. The 4 pages of a slot are equal-sized records
        (2 bytes before each pointer, then the sprites), so the size is the pointer spacing."""
        t = COMPOSITE_PARTS + 40 * head + 8 * COMPOSITE_GROUP[slot]
        n = (self.u16(t + 2) - self.u16(t) - 2) // 4
        o = COMPOSITE_BANK + self.u16(t + 2 * page) - 0x8000
        return [tuple(self.prg[o + 4 * i:o + 4 * i + 4]) for i in range(n)]

    def composite_chr(self, head: int) -> bytes:
        b = self.prg[COMPOSITE_CHR + head]
        return bytes([b, b + 1])

    def composite(self, code: int) -> tuple[bytes, list[tuple[int, int, int, int]]]:
        """Composite face: parts laid over each other cell by cell (bank 36 $8003)."""
        head, pages = decode_face_code(code)
        cells = {}
        for (slot, _, _), page in zip(COMPOSITE_SLOTS, pages):
            for dy, tile, attr, dx in self.composite_part(head, slot, page):
                if tile != 1 or (dy, dx) not in cells:
                    cells[dy, dx] = (dy, tile, attr, dx)
        return self.composite_chr(head), [cells[k] for k in sorted(cells)]

    def part_pixels(self, head: int, slot: str, page: int, transparent: int = 255) -> bytes:
        """One composite part on the 40 x 48 canvas, for layering in slot order: its cells are opaque
        (colour 0 = backdrop), the rest transparent. A blank (tile 1) on a cell that an earlier slot
        already covers is transparent too, matching the rule that it keeps the earlier cell (each
        slot covers the same cells on every page)."""
        w, h = FACE_W * 8, FACE_H * 8
        order = [sid for sid, _, _ in COMPOSITE_SLOTS]
        covered = {(dy, dx) for sid in order[:order.index(slot)] for dy, _, _, dx in self.composite_part(head, sid, 0)}
        sprites = [s for s in self.composite_part(head, slot, page) if s[1] != 1 or (s[0], s[3]) not in covered]
        pal = self.prg[SPRITE_PALETTE:SPRITE_PALETTE + 16]
        px = bytearray(self.sprite_pixels(self.composite_chr(head), sprites, w, h, pal))
        cells = {(dy, dx) for dy, _, _, dx in sprites}
        for i in range(w * h):
            if (i // w // 8 * 8, i % w // 8 * 8) not in cells:
                px[i] = transparent
        return bytes(px)

    def face(self, code: int) -> tuple[bytes, list[tuple[int, int, int, int]]]:
        return self.composite(code) if is_composite(code) else self.portrait(code)

    def face_pixels(self, code: int) -> bytes:
        banks, sprites = self.face(code)
        return self.sprite_pixels(banks, sprites, FACE_W * 8, FACE_H * 8, self.prg[SPRITE_PALETTE:SPRITE_PALETTE + 16])

    # ------------------------------------------------------------ people

    def persons(self) -> list[dict]:
        """41 person records ($6542): player, 20 mates, 4 nations x 5 admirals."""
        out = []
        for k in range(PERSON_COUNT):
            r = self.prg[INIT + PERSON_START + PERSON_SIZE * k:][:PERSON_SIZE]
            ptr = r[0] | r[1] << 8
            name = (text(self.prg[INIT + ptr - 0x6000:][:16]) if ptr < 0x8000 else self.name_at(ptr))
            out.append({"id": k, "name": name, "battle": r[2], "sailing": r[3], "face": r[4] | r[5] << 8,
                        "nation": NATIONS[r[6] >> 4], "flags": r[6],
                        "role": "主角" if k == 0 else "航海士" if k <= 20 else "提督"})
        for k in range(STAT_COUNT):
            r = self.prg[INIT + STAT_START + STAT_SIZE * k:][:STAT_SIZE]
            out[k].update(zip(["age", "leadership", "judgment", "intelligence", "courage", "strength"], r))
        return out

    def girls(self) -> list[dict]:
        return [{"id": k, "name": self.name_at(self.u16(GIRL_NAMES + 2 * k)), "face": k + GIRL_FACE}
                for k in range(GIRL_COUNT)]

    # ------------------------------------------------------------ ports and names

    def name_list(self, key: str) -> list[str]:
        o, skip, n = NAME_LISTS[key]
        return [text(p) for p in self.prg[o:o + 0x400].split(b"\0")[skip:skip + n]]

    def ports(self) -> list[dict]:
        goods = self.name_list("goods")
        out = []
        for p in range(PORT_COUNT):
            o = PORTS + PORT_SIZE * p
            cx, cy, mx, my = self.prg[o + 15:o + 19]
            d = {"id": p, "name": text(self.prg[o:o + 15]), "chunk_x": cx, "chunk_y": cy, "mt_x": mx, "mt_y": my,
                 "supply": p >= PORT_INFO_COUNT, "town": self.town_type(p)}
            if p < PORT_INFO_COUNT:
                region, special, unk, item, unk4 = self.prg[PORT_INFO + 5 * p:][:5]
                d.update(region=REGIONS[region], specialty=goods[special] if special < len(goods) else "",
                         byte2=unk, item=item if item != 0xFF else "", byte4=unk4)
            out.append(d)
        return out

    # ------------------------------------------------------------ BG graphics (ExRAM: 4 KB bank, sub-palette)

    def bg_pixels(self, tiles: bytes, ex: bytes, w: int, h: int, palette: bytes) -> bytes:
        """w x h tiles with ExRAM attributes -> NES colour numbers."""
        out = bytearray(w * h * 64)
        for i, (t, e) in enumerate(zip(tiles, ex)):
            o = (e & 0x3F) * 0x1000 + t * 16
            sub = palette[(e >> 6) * 4:(e >> 6) * 4 + 4]
            bx, by = i % w * 8, i // w * 8
            for y in range(8):
                lo, hi = self.chr[o + y], self.chr[o + 8 + y]
                for x in range(8):
                    c = (lo >> (7 - x) & 1) | (hi >> (7 - x) & 1) << 1
                    out[(by + y) * w * 8 + bx + x] = (sub[c] if c else palette[0]) & 0x3F
        return bytes(out)

    # ------------------------------------------------------------ world map

    def chunk_blocks(self, cx: int, cy: int) -> bytes:
        """7 x 7 block ids of chunk (cx, cy)."""
        area = self.u16(MAP + 4 + 5 * (cy // 3 * MAP_AREAS_W + cx // 3))
        k = self.u16(MAP + self.u16(MAP) + 18 * area + 2 * (cy % 3 * 3 + cx % 3))
        o = MAP + self.u16(MAP + 2) + 49 * k
        return self.prg[o:o + 49]

    def map_set(self, cy: int) -> int:
        return MAP_BAND[cy // 3]

    def chunk_tiles(self, cx: int, cy: int) -> tuple[bytes, bytes]:
        """28 x 28 tiles and ExRAM bytes of chunk (cx, cy)."""
        tiles, ex = bytearray(CHUNK_TILES ** 2), bytearray(CHUNK_TILES ** 2)
        s = self.map_set(cy)
        for b, block in enumerate(self.chunk_blocks(cx, cy)):
            for q in range(4):
                m = self.prg[MAP_BLOCKS + 4 * block + q]
                o = MAP_METATILES + 0x48 * s + 4 * m
                tp, ep = MAP_GFX + self.u16(o) - 0xA000, MAP_GFX + self.u16(o + 2) - 0xA000
                x0, y0 = b % 7 * 4 + q % 2 * 2, b // 7 * 4 + q // 2 * 2
                for j in range(4):
                    i = (y0 + j // 2) * CHUNK_TILES + x0 + j % 2
                    tiles[i], ex[i] = self.prg[tp + j], self.prg[ep + j]
        return bytes(tiles), bytes(ex)

    def map_palette(self, cy: int) -> bytes:
        o = MAP_PALETTES + 16 * self.map_set(cy)
        return self.prg[o:o + 16]

    def metatile_pixels(self, s: int, m: int, palette: bytes) -> bytes:
        """16 x 16 pixels of metatile m of set s."""
        o = MAP_METATILES + 0x48 * s + 4 * m
        tp, ep = MAP_GFX + self.u16(o) - 0xA000, MAP_GFX + self.u16(o + 2) - 0xA000
        return self.bg_pixels(self.prg[tp:tp + 4], self.prg[ep:ep + 4], 2, 2, palette)

    def chunk_pixels(self, cx: int, cy: int) -> bytes:
        tiles, ex = self.chunk_tiles(cx, cy)
        return self.bg_pixels(tiles, ex, CHUNK_TILES, CHUNK_TILES, self.map_palette(cy))

    # ------------------------------------------------------------ port towns

    def town_type(self, p: int) -> int:
        """bank 18 $8032: trading ports use their region (ports 2 and 12 -> 5), supply ports a table."""
        if p >= PORT_INFO_COUNT:
            return self.prg[TOWN_TYPE_SUPPLY + p - PORT_INFO_COUNT]
        return 5 if p in (2, 12) else self.prg[PORT_INFO + 5 * p]

    def town_bank(self, t: int) -> int:
        return (32 if t in (3, 5) else 33) * BANK

    def town_flags(self, p: int) -> int:
        return self.prg[INIT + TOWN_FLAGS + p]

    def town_draws(self, p: int, flags: int | None = None) -> list[tuple[int, int, int, int, int, int]]:
        """BG draws of port p's town screen (bank 18 $80CB, svc 9): (x, y, w, h, tiles ptr, ExRAM ptr),
        $A000-based. Trading ports add pieces by the building flags (default: the new-game values)."""
        t = self.town_type(p)
        f = self.town_flags(p) if flags is None else flags
        o = TOWN_IMAGES + 4 * t
        draws = [(TOWN_X, TOWN_Y, TOWN_W, TOWN_H, self.u16(o), self.u16(o + 2))]
        if p >= PORT_INFO_COUNT:
            pieces = TOWN_PIECES_SUPPLY
        else:
            pieces = [(n, x, y) for n, x, y, mask, value in TOWN_PIECES_PORT if f & mask == value]
        for piece, x, y in pieces:
            o = TOWN_PIECES + 16 * t + 4 * piece
            draws.append((x, y, *TOWN_PIECE_SIZE[piece], self.u16(o), self.u16(o + 2)))
        return draws

    def town_tiles(self, p: int) -> tuple[bytes, bytes]:
        """Town picture of port p: the 28 x 14 tiles at (2, 6) with the pieces drawn over it."""
        b = self.town_bank(self.town_type(p))
        tiles, ex = bytearray(TOWN_W * TOWN_H), bytearray(TOWN_W * TOWN_H)
        for x, y, w, h, tp, ep in self.town_draws(p):
            for i in range(w * h):
                j = (y - TOWN_Y + i // w) * TOWN_W + x - TOWN_X + i % w
                tiles[j], ex[j] = self.prg[b + tp - 0xA000 + i], self.prg[b + ep - 0xA000 + i]
        return bytes(tiles), bytes(ex)

    def town_palette(self, t: int) -> bytes:
        return self.prg[TOWN_PALETTES + 16 * t:][:16]

    def town_pixels(self, p: int) -> bytes:
        return self.bg_pixels(*self.town_tiles(p), TOWN_W, TOWN_H, self.town_palette(self.town_type(p)))
