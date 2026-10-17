"""FC 天地を喰らうII 諸葛孔明伝 (Capcom, 1991) ROM decoding.

MMC3, 512 KB PRG (64 x 8 KB banks), 8 KB CHR-RAM. The game maps data with one call ($C6E5, A = b):
8 KB bank b at $8000 and bank b + 1 at $A000, so every "bank" below is a 16 KB window starting at
PRG offset b * $2000. $C000-$FFFF are the last two banks (fixed). See tenchi2/docs/ROM_FORMAT.md.
"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Tenchi o Kurau II - Shokatsu Koumei Den (Japan) (Rev A).zip")
PRG_SIZE = 0x80000

# ---------------------------------------------------------------- text (printer bank 62 $D499)
# 00-09 digits, 0A space, 10-6C kana; 80-B6 = code & 7F with dakuten, B7-C7 = (code & 7F) - 9 with handakuten
# (the mark goes on the row above, tile 72 / 73). C8-F7 control codes, F8 call, FA-FF line / page control.
FONT = {
    0x00: "0123456789　┗━┛＊×",
    0x10: "かきくけこさしすせそたちつてとカ",
    0x20: "キクケコサシスセソタチツテトはひ",
    0x30: "ふへほハヒフホあいうえおなにぬね",
    0x40: "のまみむめもやゆよらりるれろわを",
    0x50: "んゃゅょっアイウエオナネマミメモ",
    0x60: "ユヨラリルレロワンュョド金┏┓┃",
    0x70: "▶▼゛゜ヤム「ッ・ー！？ヌ┃　ャ",
}
DAKUTEN = dict(zip("かきくけこさしすせそたちつてとはひふへほカキクケコサシスセソタチツテトハヒフヘホウ",
                   "がぎぐげござじずぜぞだぢづでどばびぶべぼガギグゲゴザジズゼゾダヂヅデドバビブベボヴ"))
HANDAKUTEN = dict(zip("はひふへほハヒフヘホ", "ぱぴぷぺぽパピプペポ"))
DICT_BANK = 0x1C               # dictionary words: control EA-ED + index byte
DICT_TABLES = {0xEA: 0xAA00, 0xEB: 0xA800, 0xEC: 0xA600, 0xED: 0xA400}  # lo bytes at +0, hi bytes at +$100

# ---------------------------------------------------------------- generals (bank $36)
GENERAL_BANK = 0x36
GENERAL_LO, GENERAL_HI = 0x9E00, 0x9F00  # 256 x pointer (lo / hi byte tables) -> record
GENERAL_COUNT = 256
NAME_OFFSET = 0x19             # kana name, FE/FF-terminated
KANJI_OFFSET = 0x16            # up to 3 kanji indexes (FF = end); bit 2-j of byte $15 selects set 2 for kanji j
KANJI_BANK = 0x0E
KANJI_SET = [0x9800, 0xB800]   # 1-bit 16x16 glyphs, 32 bytes each (tiles TL, BL, TR, BR); set 1 has 256, set 2 64
# portrait: 6 rows of 6 tiles; row k = record[$0E + k], 2-bit bank field in record[$14] / [$15] (loader $D12E)
PORTRAIT_ROW_BYTE = [0x14, 0x14, 0x14, 0x14, 0x15, 0x15]
PORTRAIT_ROW_MASK = [0xC0, 0x30, 0x0C, 0x03, 0xC0, 0x30]
PORTRAIT_ROW_SHIFT = [6, 4, 2, 0, 6, 4]
PORTRAIT_ROW_BYTES = 0x60
STATUS_PALETTE = [0x0F, 0x20, 0x37, 0x26]  # sub-palette 3 of the ぶしょう screen (palette script bank $35 $BF3B)

# ---------------------------------------------------------------- items (bank $34)
ITEM_BANK = 0x34
ITEM_LO, ITEM_HI = 0x8100, 0x8180  # 128 x pointer -> [price LE16, name FF]
ITEM_COUNT = 128

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


def _font() -> dict[int, str]:
    out = {}
    for base, chars in FONT.items():
        for i, c in enumerate(chars):
            out[base + i] = c
    return out


GLYPHS = _font()


def char(code: int) -> str:
    """One printable code (00-C7) as text."""
    if code >= 0xB7:
        b = GLYPHS.get((code & 0x7F) - 9, "?")
        return HANDAKUTEN.get(b, b + "゜")
    if code >= 0x80:
        b = GLYPHS.get(code & 0x7F, "?")
        return DAKUTEN.get(b, b + "゛")
    return GLYPHS.get(code, f"[{code:02X}]")


def katakana(s: str) -> str:
    """Names use the hiragana へ/べ/ぺ tiles (same glyph as katakana); show them as katakana."""
    return s.translate(str.maketrans("へべぺ", "ヘベペ"))


def _load_kanji(name: str) -> str:
    with open(os.path.join(HERE, "data", name), encoding="utf-8") as f:
        return f.read().strip("\n")


KANJI = [_load_kanji("kanji1.txt"), _load_kanji("kanji2.txt")]


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        data = read_rom(path)
        self.prg = data[0x10:0x10 + PRG_SIZE]

    def off(self, bank: int, addr: int) -> int:
        """PRG offset of CPU address addr with window `bank` mapped at $8000-$BFFF ($C000+ = fixed banks)."""
        if addr >= 0xC000:
            return 62 * 0x2000 + addr - 0xC000
        return bank * 0x2000 + addr - 0x8000

    def byte(self, bank: int, addr: int) -> int:
        return self.prg[self.off(bank, addr)]

    def bytes(self, bank: int, addr: int, n: int) -> bytes:
        o = self.off(bank, addr)
        return self.prg[o:o + n]

    def split_ptr(self, bank: int, lo: int, hi: int, i: int) -> int:
        return self.byte(bank, lo + i) | self.byte(bank, hi + i) << 8

    def string(self, o: int, end: tuple[int, ...] = (0xFF,)) -> str:
        out = []
        while self.prg[o] not in end:
            out.append(char(self.prg[o]))
            o += 1
        return "".join(out)

    # ------------------------------------------------------------ generals
    def general_offset(self, gid: int) -> int:
        return self.off(GENERAL_BANK, self.split_ptr(GENERAL_BANK, GENERAL_LO, GENERAL_HI, gid))

    def general_record(self, gid: int) -> bytes:
        o = self.general_offset(gid)
        return self.prg[o:o + NAME_OFFSET]

    def general_name(self, gid: int) -> str:
        return katakana(self.string(self.general_offset(gid) + NAME_OFFSET, (0xFE, 0xFF)))

    def general_kanji_codes(self, gid: int) -> list[tuple[int, int]]:
        """[(set, index)] of the kanji name (set 0 / 1), as the ぶしょう screen draws it ($C033)."""
        rec = self.general_record(gid)
        out = []
        for j, b in enumerate(rec[KANJI_OFFSET:KANJI_OFFSET + 3]):
            if b == 0xFF:
                break
            out.append(((rec[0x15] >> (2 - j)) & 1, b))
        return out

    def general_kanji(self, gid: int) -> str:
        return "".join(KANJI[s][i] if i < len(KANJI[s]) else "?" for s, i in self.general_kanji_codes(gid))

    def kanji_glyph(self, kset: int, index: int) -> list[list[int]]:
        """16x16 1-bit glyph."""
        o = self.off(KANJI_BANK, KANJI_SET[kset]) + index * 32
        px = [[0] * 16 for _ in range(16)]
        for t in range(4):
            tx, ty = (t // 2) * 8, (t % 2) * 8
            for y in range(8):
                b = self.prg[o + t * 8 + y]
                for x in range(8):
                    px[ty + y][tx + x] = (b >> (7 - x)) & 1
        return px

    def portrait_rows(self, gid: int) -> list[tuple[int, int]]:
        """[(window bank, row index)] of the 6 portrait rows."""
        rec = self.general_record(gid)
        out = []
        for k in range(6):
            v = (rec[PORTRAIT_ROW_BYTE[k]] & PORTRAIT_ROW_MASK[k]) >> PORTRAIT_ROW_SHIFT[k]
            out.append((v * 2, rec[0x0E + k]))
        return out

    def portrait(self, gid: int, flip: bool = True) -> list[list[int]]:
        """48x48 2-bit pixels. flip=True is how the ぶしょう screen shows it ($7A = 0: tiles mirrored)."""
        px = [[0] * 48 for _ in range(48)]
        for k, (b, idx) in enumerate(self.portrait_rows(gid)):
            o = b * 0x2000 + idx * PORTRAIT_ROW_BYTES
            for t in range(6):
                lo, hi = self.prg[o + t * 16:o + t * 16 + 8], self.prg[o + t * 16 + 8:o + t * 16 + 16]
                for y in range(8):
                    for x in range(8):
                        px[k * 8 + y][t * 8 + x] = ((lo[y] >> (7 - x)) & 1) | (((hi[y] >> (7 - x)) & 1) << 1)
        if flip:
            px = [row[::-1] for row in px]
        return px

    # ------------------------------------------------------------ items
    def item(self, iid: int) -> tuple[int, str]:
        """(price, name) of item iid."""
        o = self.off(ITEM_BANK, self.split_ptr(ITEM_BANK, ITEM_LO, ITEM_HI, iid))
        return self.prg[o] | self.prg[o + 1] << 8, self.string(o + 2)


CONTROL_NAMES = {0xF3: "{item}", 0xF4: "{general:$4B}", 0xF5: "{general:$4A}", 0xF6: "{general:$4C}",
                 0xF7: "{general:$72}"}


class Text:
    """Message decoder (printer bank 62 $D499, control dispatch $D4E3)."""

    def __init__(self, rom: Rom):
        self.rom = rom

    def word(self, code: int, index: int) -> str:
        r = self.rom
        t = DICT_TABLES[code]
        p = r.byte(DICT_BANK, t + index) | r.byte(DICT_BANK, t + 0x100 + index) << 8
        return r.string(r.off(DICT_BANK, p))

    def decode(self, o: int, limit: int = 2000) -> tuple[str, int]:
        """Decode the message at PRG offset o; returns (text, offset after the FF)."""
        r, p, out = self.rom, self.rom.prg, []
        end = o + limit
        while o < end:
            c = p[o]
            o += 1
            if c == 0xFF:
                break
            if c < 0xC8:
                out.append(char(c))
                continue
            if 0xC8 <= c < 0xF8:
                if not c & 0x20:
                    out.append("　")
                c |= 0x20
                if c in DICT_TABLES:
                    out.append(self.word(c, p[o]))
                    o += 1
                elif c == 0xF1:
                    out.append("{item:" + r.item(p[o])[1] + "}")
                    o += 1
                elif c == 0xF2:
                    out.append("{" + r.general_name(p[o]) + "}")
                    o += 1
                elif c in CONTROL_NAMES:
                    out.append(CONTROL_NAMES[c])
                else:
                    out.append(f"<{c:02X}>")
            elif c in (0xF8, 0xF9):
                out.append(f"<{c:02X}:{p[o] | p[o + 1] << 8:04X}>")
                o += 2
            elif c == 0xFB:
                out.append("\n")
            else:
                out.append(f"<{c:02X}>")
        return "".join(out), o


# ---------------------------------------------------------------- maps (bank 62 $D92B: cell at screen / cell coordinates)
SCREEN_BANK = 0x32
SCREEN_GRID = 0x9000           # 128 rows x 32 columns of [screen id, data bank]; row r, col c at +r*64 + c*2
GRID_W, GRID_H = 32, 128
SCREEN_BYTES = 72              # screen id s at data bank $8000 + s*72: 8x8 block ids + 8 bytes of block bit 8
ALT_SCREEN_BANK = (0x36, 0x38)  # entry bank $36 is read from $38 once the event flag $6320[id] is set
BLOCK_BASE = 0xDA50            # per tileset ($1D): page of the 512 blocks (4 cells each: TL TR BL BR)
TILESET_BANK = 0xDA60          # per tileset: data bank of blocks, cell tiles and cell palettes
CELL_TILES = 0xFAEE            # per tileset: first of 4 pages (TL, TR, BL, BR tile of each cell)
CELL_PALETTE = 0xDA96          # per tileset: page of the cell sub-palette (bits 0-1)
MAP_AREA = 0xB700              # bank $34: nibble per map number ($47): area / tileset ($48); even = high nibble
MAP_CHR = 0xB760               # bank $34: per map: bits 0-4 = 2 KB BG tile set ($49) for tiles $80-$FF
MAP_COUNT = 160
MAP_CHR_BASE = 0x10            # tile set k: bank $10 + (k >> 3) * 2, $8000 + (k & 7) * $800 (loader $DFA6)


def _map_methods():
    def screen_entry(self, row: int, col: int) -> tuple[int, int]:
        o = self.off(SCREEN_BANK, SCREEN_GRID + row * 64 + col * 2)
        return self.prg[o], self.prg[o + 1]

    def screen_blocks(self, sid: int, bank: int) -> list[list[int]]:
        """8x8 block numbers (0-511) of screen sid."""
        o = self.off(bank, 0x8000 + sid * SCREEN_BYTES)
        d = self.prg[o:o + SCREEN_BYTES]
        return [[d[r * 8 + c] | (((d[0x40 + r] >> (7 - c)) & 1) << 8) for c in range(8)] for r in range(8)]

    def tileset_cell(self, t: int, block: int, sub: int) -> int:
        b = self.byte(62, TILESET_BANK + t)
        return self.byte(b, (self.byte(62, BLOCK_BASE + t) << 8) + block * 4 + sub)

    def cell_tiles(self, t: int, cell: int) -> tuple[list[int], int]:
        """([TL, TR, BL, BR] tile numbers, sub-palette) of cell id in tileset t."""
        b, pg = self.byte(62, TILESET_BANK + t), self.byte(62, CELL_TILES + t)
        tiles = [self.byte(b, ((pg + k) << 8) + cell) for k in range(4)]
        return tiles, self.byte(b, (self.byte(62, CELL_PALETTE + t) << 8) + cell) & 3

    def screen_cells(self, row: int, col: int, t: int) -> list[list[int]]:
        """16x16 cell ids of grid screen (row, col) drawn with tileset t."""
        sid, bank = self.screen_entry(row, col)
        blocks = self.screen_blocks(sid, bank)
        return [[self.tileset_cell(t, blocks[y >> 1][x >> 1], (y & 1) * 2 + (x & 1)) for x in range(16)]
                for y in range(16)]

    def map_info(self, m: int) -> tuple[int, int]:
        """(area / tileset $48, BG tile set $49) of map number m."""
        a = self.byte(0x34, MAP_AREA + (m >> 1))
        return (a & 0x0F) if m & 1 else (a >> 4), self.byte(0x34, MAP_CHR + m) & 0x1F

    def bg_tiles(self, chr_set: int) -> bytes:
        """2 KB of tiles $80-$FF ($1800-$1FFF) for BG tile set chr_set."""
        o = self.off(MAP_CHR_BASE + (chr_set >> 3) * 2, 0x8000 + (chr_set & 7) * 0x800)
        return self.prg[o:o + 0x800]

    for f in (screen_entry, screen_blocks, tileset_cell, cell_tiles, screen_cells, map_info, bg_tiles):
        setattr(Rom, f.__name__, f)


_map_methods()


MAP_PALETTE_LO, MAP_PALETTE_HI = 0xB820, 0xB900  # bank $34: per map: -> [first index, colours..., FF] (loader $C838)


def _palette(self, m: int) -> list[int]:
    """32-byte palette after loading map m's palette record over the default ($0F everywhere)."""
    p = self.byte(0x34, MAP_PALETTE_LO + m) | self.byte(0x34, MAP_PALETTE_HI + m) << 8
    o = self.off(0x34, p)
    pal, i = [0x0F] * 32, self.prg[o]
    o += 1
    while self.prg[o] < 0x80:
        pal[i] = self.prg[o]
        i, o = i + 1, o + 1
    return pal


Rom.map_palette = _palette
