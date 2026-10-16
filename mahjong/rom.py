"""FC 麻雀大会 (KOEI, 1989) ROM decoding.

All offsets are PRG offsets (file offset - 0x10); a "linear" address is the same thing (the game's
pointer helper at $E7FA turns it into bank = bits 14-15, CPU address = $8000 | bits 0-13).
See mahjong/docs/ROM_FORMAT.md.
"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Mahjong Taikai (Japan).zip")

# ---------------------------------------------------------------- players
PLAYERS = 16                 # 15 CPU opponents + the human player (id 15)
CPU_PLAYERS, HUMAN = 15, 15
# [EXT] who the game's short names stand for (not in the ROM)
FULL_NAMES = ["織田信長", "武田信玄", "伊達政宗", "西郷隆盛", "勝海舟", "坂本龍馬", "諸葛孔明", "聖徳太子",
              "シブサワ・コウ", "チンギス・カン", "ナポレオン", "ユリウス・カエサル", "クレオパトラ", "楊貴妃",
              "小野小町", ""]
# the 16 name plates as the game draws them (16x16 glyphs at NAME_GLYPHS, transcribed)
NAMES = ["信長", "信玄", "政宗", "隆盛", "海舟", "龍馬", "孔明", "太子", "シブサワ・コウ", "ジンギス・カン",
         "ナポレオン", "シーザー", "クレオパトラ", "楊妃", "小町", "プレイヤー"]
NAME_GLYPHS, NAME_SIZE = 0x4B20, 0x40   # 16 x 8 tiles of 1bpp (stored inverted), 4x2 tiles, row-major

# ---------------------------------------------------------------- faces (bank 0-1)
FACE_TILE_BASE = 0x0000     # 16 x u16: linear address of each player's tile pool
FACE_PALETTE_FLAG = 0x0020  # 16 bytes: 0 -> BG sub-palette 2, 1 -> sub-palette 3
FACE_LAYOUTS = 0x0030       # 105 x 16 tile ids (4x4, row-major); entry = player * 7 + expression
EXPRESSIONS = 7
FACE_W = FACE_H = 4         # tiles
# BG sub-palettes 2 and 3 of the screens that show faces (雀荘 / 卓)
FACE_PALETTES = {0: bytes([0x2E, 0x21, 0x38, 0x30]), 1: bytes([0x2E, 0x16, 0x37, 0x30])}

# ---------------------------------------------------------------- text
# 8x8 glyphs at linear $8700 (bank 2), one per code ($E9E8); codes A3- are a base glyph plus a
# dakuten / handakuten drawn on the line above ($E993); A2 is a blank.
GLYPHS = 0x8700
CHARSET = ("0123456789!$+,ー.?゛゜。、…"  # 0E is drawn as a dash and only used as the long vowel
           "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゐゆゑよらりるれろわをんっゃゅょぁぃぅぇぉ"
           "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤヰユヱヨラリルレロワヲンッャュョァィゥェォ"
           "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
SPACE = 0xA2
# (first code, last code, base glyph of the first code, mark); the last range has no upper bound in
# the code, so D5 (meant as ヴ in ナポレオン's ヴィヴ・ラ・フランス) is drawn as マ + ゜
VOICED = [(0xA3, 0xB1, 0x1B, "゛"), (0xB2, 0xB6, 0x2F, "゛"), (0xB7, 0xBB, 0x2F, "゜"),
          (0xBC, 0xCA, 0x54, "゛"), (0xCB, 0xCF, 0x68, "゛"), (0xD0, 0xFF, 0x68, "゜")]

# ---------------------------------------------------------------- speech ($EF31)
# per CPU player 88 lines of 15 bytes at linear $EE03: [kind][14 codes + 1], two lines of 7;
# trailing blanks end the text. kind -> face expression ($EFAA); while talking the mouth cycles 2, 1, 0.
SPEECH, SPEECH_PER_PLAYER, SPEECH_SIZE = 0xEE03, 88, 15
SPEECH_FACE = [0, 5, 4, 3, 6]
# the 88 lines are 42 situations with 1-4 alternatives each, one picked at random ($D067, table $D07B)
SITUATION_COUNTS = 0x1D07B
SITUATIONS = 42
# expression labels: 0 normal, 1-2 the talking mouth frames, 3-6 the faces of speech kinds 3, 2, 1, 4
EXPRESSION_LABELS = ["平常", "說話 1", "說話 2", "怒", "哀", "喜", "驚"]
KIND_LABELS = ["平常", "得意", "落胆", "怒り", "驚き"]  # read from the lines' content

# ---------------------------------------------------------------- AI parameters
# 15 x 8 bytes (bank 5 $B8EB, run from its WRAM copy at $78EB), copied to $6293 + player * 8 at
# the start of a game ($B8D8) and loaded into $37-$3E for the seat that is thinking ($C170)
AI_PARAMS, AI_PARAM_SIZE = 0x178EB, 8

# ---------------------------------------------------------------- mahjong tiles
# tile code: 01-09 萬子, 11-19 索子, 21-29 筒子, 31-37 東南西北白發中 -> index 0-33 ($906B)
TILE_NAMES = ([f"{n}萬" for n in "一二三四五六七八九"] + [f"{n}索" for n in "一二三四五六七八九"]
              + [f"{n}筒" for n in "一二三四五六七八九"] + list("東南西北白發中"))
TILE_CODES = [s * 0x10 + n for s in range(3) for n in range(1, 10)] + list(range(0x31, 0x38))
TILE_LAYOUT = 0x1E045       # 4 BG tile ids per index (TL, TR, BL, BR), drawn with 72 73 under them ($EAB1)
TILE_CHR = 0x4F20           # BG tile id n -> 16 bytes at TILE_CHR + 16 * n ($EB35)
TILE_EDGE = (0x72, 0x73)
TILE_PALETTE = bytes([0x2E, 0x09, 0x06, 0x30])  # BG sub-palette 0 of the table screen

# NES 2C02 palette (common emulator approximation), index = NES colour number
NES_PALETTE = [int(x, 16) for x in [
    "7C7C7C", "0000FC", "0000BC", "4428BC", "940084", "A80020", "A81000", "881400", "503000", "007800",
    "006800", "005800", "004058", "000000", "000000", "000000", "BCBCBC", "0078F8", "0058F8", "6844FC",
    "D800CC", "E40058", "F83800", "E45C10", "AC7C00", "00B800", "00A800", "00A844", "008888", "000000",
    "000000", "000000", "F8F8F8", "3CBCFC", "6888FC", "9878F8", "F878F8", "F85898", "F87858", "FCA044",
    "F8B800", "B8F818", "58D854", "58F898", "00E8D8", "787878", "000000", "000000", "FCFCFC", "A4E4FC",
    "B8B8F8", "D8B8F8", "F8B8F8", "F8A4C0", "F0D0B0", "FCE0A8", "F8D878", "D8F878", "B8F8B8", "B8F8D8",
    "00FCFC", "F8D8F8", "000000", "000000"]]


def nes_rgb(i: int) -> tuple[int, int, int]:
    c = NES_PALETTE[i & 0x3F]
    return c >> 16, (c >> 8) & 0xFF, c & 0xFF


def glyph_char(code: int) -> str:
    """One glyph code -> text (dakuten combined, NFC)."""
    import unicodedata
    if code == SPACE:
        return "　"
    for lo, hi, base, mark in VOICED:
        if lo <= code <= hi:
            return unicodedata.normalize("NFC", CHARSET[base + code - lo] + {"゛": "\u3099", "゜": "\u309A"}[mark])
    return CHARSET[code] if code < len(CHARSET) else f"<{code:02X}>"


def text(codes: bytes) -> str:
    return "".join(glyph_char(c) for c in codes)


def u16(b: bytes, o: int) -> int:
    return b[o] | b[o + 1] << 8


def tile_pixels(data: bytes, off: int) -> list[int]:
    """One 2bpp NES tile -> 64 colour indexes."""
    return [((data[off + y] >> (7 - x)) & 1) | (((data[off + 8 + y] >> (7 - x)) & 1) << 1)
            for y in range(8) for x in range(8)]


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
        assert self.data[:4] == b"NES\x1a" and self.data[4] == 8 and self.data[5] == 0, "not the expected ROM"
        self.prg = self.data[0x10:0x10 + 0x20000]

    # ------------------------------------------------------------ faces
    def face_layout(self, player: int, expression: int = 0) -> list[int]:
        """16 tile ids of a face; the human player has one face, tiles 0-15 of its pool ($EBF9)."""
        k = player * EXPRESSIONS + expression
        if k >= CPU_PLAYERS * EXPRESSIONS:
            return list(range(16))
        return list(self.prg[FACE_LAYOUTS + 16 * k:FACE_LAYOUTS + 16 * k + 16])

    def tile_pool(self, player: int) -> int:
        return u16(self.prg, FACE_TILE_BASE + 2 * player)

    def pool_size(self, player: int) -> int:
        """Tiles in a player's pool (up to the next pool; the human's pool ends at the name glyphs)."""
        end = self.tile_pool(player + 1) if player + 1 < PLAYERS else NAME_GLYPHS
        return (end - self.tile_pool(player)) // 16

    def face_palette(self, player: int) -> bytes:
        return FACE_PALETTES[self.prg[FACE_PALETTE_FLAG + player]]

    def face_pixels(self, player: int, expression: int = 0) -> bytes:
        """32x32 NES colour numbers."""
        base, pal = self.tile_pool(player), self.face_palette(player)
        px = bytearray(32 * 32)
        for cell, t in enumerate(self.face_layout(player, expression)):
            cx, cy = cell % FACE_W * 8, cell // FACE_W * 8
            for i, c in enumerate(tile_pixels(self.prg, base + 16 * t)):
                px[(cy + i // 8) * 32 + cx + i % 8] = pal[c]
        return bytes(px)

    # ------------------------------------------------------------ speech
    def speech(self, player: int, k: int) -> dict:
        """Line k of a CPU player: kind, face expression and the two 7-character lines (codes are stored +1)."""
        o = SPEECH + SPEECH_SIZE * (player * SPEECH_PER_PLAYER + k)
        r = self.prg[o:o + SPEECH_SIZE]
        codes = bytes(c - 1 for c in r[1:])
        lines = [text(codes[:7]).rstrip("　"), text(codes[7:]).rstrip("　")]
        return {"kind": r[0], "face": SPEECH_FACE[r[0]] if r[0] < len(SPEECH_FACE) else None, "lines": lines}

    def situation_of(self, k: int) -> int:
        """Situation number of speech line k."""
        total = 0
        for s in range(SITUATIONS):
            total += self.prg[SITUATION_COUNTS + s]
            if k < total:
                return s
        raise ValueError(k)

    # ------------------------------------------------------------ AI parameters
    def ai_params(self, player: int) -> list[int]:
        o = AI_PARAMS + AI_PARAM_SIZE * player
        return list(self.prg[o:o + AI_PARAM_SIZE])

    # ------------------------------------------------------------ mahjong tiles
    def tile_pixels(self, index: int) -> bytes:
        """16x24 NES colour numbers of tile index 0-33 (or the back / blank / side entries 34-39)."""
        o = TILE_LAYOUT + 4 * index
        cells = [*self.prg[o:o + 4], *TILE_EDGE]
        px = bytearray(16 * 24)
        for k, t in enumerate(cells):
            for i, c in enumerate(tile_pixels(self.prg, TILE_CHR + 16 * t)):
                px[(k // 2 * 8 + i // 8) * 16 + k % 2 * 8 + i % 8] = TILE_PALETTE[c]
        return bytes(px)

    # ------------------------------------------------------------ names
    def name_glyph(self, player: int) -> list[list[int]]:
        """32x16 1-bit name plate (1 = ink), as drawn by $EA4F."""
        o = NAME_GLYPHS + NAME_SIZE * player
        rows = [[0] * 32 for _ in range(16)]
        for t in range(8):
            tx, ty = t % 4, t // 4
            for y in range(8):
                b = self.prg[o + 8 * t + y] ^ 0xFF
                for x in range(8):
                    rows[ty * 8 + y][tx * 8 + x] = (b >> (7 - x)) & 1
        return rows
