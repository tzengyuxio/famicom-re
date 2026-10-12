"""FC 水滸伝・天命の誓い (KOEI, 1989) ROM decoding.

All offsets are PRG offsets (file offset - 0x10). See suikoden/docs/ROM_FORMAT.md.
"""
import os
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "Suikoden - Tenmei no Chikai (Japan).nes")

PRG_SIZE = 0x40000
CHR_START = 0x10 + PRG_SIZE

# Characters (bank 27): 255 x 25 bytes
NAME_TABLE = 0x36004
NAME_SIZE = 25
CHAR_COUNT = 255
# Provinces: 49 x 21 bytes, right after the name table
PROVINCE_TABLE = NAME_TABLE + NAME_SIZE * CHAR_COUNT  # 0x378EB
PROVINCE_SIZE = 21
PROVINCE_COUNT = 49
# Scenarios 1-4 (8KB banks 23-26): 255 x 18 bytes from bank offset 5
SCENARIO_BANKS = [23, 24, 25, 26]
SCENARIO_START = 5
SCENARIO_SIZE = 18
# Kanji glyph table (bank 17): [SJIS code LE16, 4 x tile LE16] x 457
GLYPH_TABLE = 0x22004
GLYPH_COUNT = 457

# Dedicated portraits (bank 18): 100 x 60 bytes = 30 tile ids + 30 ExRAM bytes (5x6 tiles)
PORTRAIT_TABLE = 0x24004
PORTRAIT_COUNT = 100
PORTRAIT_PALETTES = 0x25904   # 100 x 8 bytes = 2 sub-palettes
PORTRAIT_W, PORTRAIT_H = 5, 6  # tiles

# Mob (composite) faces: pointer table at $BE10 in bank 16, part data at $A000 in bank 20
MOB_POINTERS = 0x21E10        # 5 categories x 0x50 bytes = 20 tile ptrs + 20 ExRAM ptrs
MOB_DATA = 0x28000            # bank 20, mapped at $A000
MOB_PALETTES = 0x285C4        # 5 x 8 bytes
MOB_CATEGORIES = 5
# Slot -> (first pointer index, size in tiles (w, h) or None = width from pointer table)
MOB_SLOTS = [("head", "頭", 0, (5, 4)), ("chin", "顎", 4, (5, 2)), ("eyes", "眼", 8, None),
             ("nose", "鼻", 12, None), ("mouth", "口", 16, None)]
# Canvas cell index (row * 5 + col) of eyes / nose / mouth per category; head at 0, chin at 20.
# Traced by running the face routine ($AEBB, bank 16) in an emulator (tools/trace_mob_layout.py).
MOB_LAYOUT = {0: (10, 15, 20), 1: (12, 17, 23), 2: (11, 17, 22), 3: (12, 17, 22), 4: (11, 17, 22)}

# Province map (bank 19): 28 x 17 tiles, tile ids then ExRAM bytes
MAP_TILES = 0x26004
MAP_EXRAM = 0x261E0
MAP_W, MAP_H = 28, 17

# NES 2C02 palette (common emulator approximation), index = NES colour number
NES_PALETTE = [int(x, 16) for x in ["7C7C7C", "0000FC", "0000BC", "4428BC", "940084", "A80020", "A81000", "881400", "503000", "007800", "006800", "005800", "004058", "000000", "000000", "000000", "BCBCBC", "0078F8", "0058F8", "6844FC", "D800CC", "E40058", "F83800", "E45C10", "AC7C00", "00B800", "00A800", "00A844", "008888", "000000", "000000", "000000", "F8F8F8", "3CBCFC", "6888FC", "9878F8", "F878F8", "F85898", "F87858", "FCA044", "F8B800", "B8F818", "58D854", "58F898", "00E8D8", "787878", "000000", "000000", "FCFCFC", "A4E4FC", "B8B8F8", "D8B8F8", "F8B8F8", "F8A4C0", "F0D0B0", "FCE0A8", "F8D878", "D8F878", "B8F8B8", "B8F8D8", "00FCFC", "F8D8F8", "000000", "000000"]]


def nes_rgb(i: int) -> tuple[int, int, int]:
    c = NES_PALETTE[i & 0x3F]
    return c >> 16, (c >> 8) & 0xFF, c & 0xFF


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        with open(path, "rb") as f:
            self.data = f.read()
        assert self.data[:4] == b"NES\x1a" and self.data[4] == 16 and self.data[5] == 16, "not the expected ROM"
        self.prg = self.data[0x10:CHR_START]
        self.chr = self.data[CHR_START:]
        self.gaiji = load_gaiji()

    # ------------------------------------------------------------ graphics

    def tile(self, exram: int, tile_id: int) -> list[list[int]]:
        """8x8 2bpp tile; ExRAM bits 0-5 select the 4KB CHR bank (MMC5 extended attribute mode)."""
        o = (exram & 0x3F) * 0x1000 + tile_id * 16
        b = self.chr[o:o + 16]
        return [[((b[y] >> (7 - x)) & 1) | (((b[y + 8] >> (7 - x)) & 1) << 1) for x in range(8)] for y in range(8)]

    def render_cells(self, tiles, exram, w: int, palettes: bytes) -> bytes:
        """Tile grid -> NES colour numbers (row-major). ExRAM bits 6-7 pick the 4-colour sub-palette."""
        h = len(tiles) // w
        out = bytearray(w * 8 * h * 8)
        for i, (t, e) in enumerate(zip(tiles, exram)):
            r, c = divmod(i, w)
            pal = palettes[(e >> 6) * 4:(e >> 6) * 4 + 4]
            for y, row in enumerate(self.tile(e, t)):
                for x, v in enumerate(row):
                    out[(r * 8 + y) * w * 8 + c * 8 + x] = pal[v] & 0x3F
        return bytes(out)

    # ------------------------------------------------------------ text

    def sjis(self, raw: bytes) -> str:
        """Null-terminated big-endian SJIS (2 bytes per char); gaiji EBxx via data/gaiji.tsv."""
        s = ""
        for i in range(0, len(raw) - 1, 2):
            code = raw[i] << 8 | raw[i + 1]
            if code == 0:
                break
            s += self.gaiji.get(code) or raw[i:i + 2].decode("cp932")
        return s

    def glyphs(self) -> list[tuple[int, list[int]]]:
        """Kanji glyph table: (SJIS code, 4 tile numbers TL TR BL BR, 11-bit = 4KB bank * 256 + tile)."""
        out = []
        for k in range(GLYPH_COUNT):
            o = GLYPH_TABLE + k * 10
            r = self.prg[o:o + 10]
            out.append((r[0] | r[1] << 8, [r[2 + 2 * j] | r[3 + 2 * j] << 8 for j in range(4)]))
        return out

    # ------------------------------------------------------------ tables

    def characters(self) -> list[dict]:
        out = []
        for i in range(CHAR_COUNT):
            r = self.prg[NAME_TABLE + i * NAME_SIZE:NAME_TABLE + (i + 1) * NAME_SIZE]
            face = r[17] | r[18] << 8
            out.append({
                "id": i,
                "name": self.sjis(r[0:7]),
                "reading": kana(r[7:16]),
                "face_code": face,           # bit 15 set: composite face, else dedicated portrait index
                "unk16": r[16],
                "unk19": r[19],
                "male": bool(r[20] & 0x80),
                "helm": bool(r[20] & 0x40),   # 操舵 (can steer ships)
                "flags_lo": r[20] & 0x3F,
                "chugi": r[21],               # 忠義
                "jinai": r[22],               # 仁愛
                "yuuki": r[23],               # 勇気
                "unk24": r[24],
            })
        return out

    def scenario(self, n: int) -> list[dict]:
        """Scenario n (1-4) initial state per character."""
        base = SCENARIO_BANKS[n - 1] * 0x2000 + SCENARIO_START
        out = []
        for i in range(CHAR_COUNT):
            r = self.prg[base + i * SCENARIO_SIZE:base + (i + 1) * SCENARIO_SIZE]
            out.append({
                "id": i,
                "unk0": r[0] | r[1] << 8,
                "age": r[2],
                "status": r[3],               # meaning not confirmed
                "province": r[4],             # 0-based index into provinces()
                "hp": r[5], "hp_max": r[6],   # 体力
                "strength": r[7],             # 腕力
                "skill": r[8],                # 技量
                "intellect": r[9],            # 知力
                "unk10": r[10:13].hex(),
                "unk13": r[13],
                "unk14": r[14:16].hex(),
                "unk16": r[16],
                "unk17": r[17],
            })
        return out

    def provinces(self) -> list[dict]:
        out = []
        for i in range(PROVINCE_COUNT):
            r = self.prg[PROVINCE_TABLE + i * PROVINCE_SIZE:PROVINCE_TABLE + (i + 1) * PROVINCE_SIZE]
            out.append({
                "id": i,
                "name": self.sjis(r[0:4]) + "州",
                "unk4": r[4], "unk5": r[5], "unk6": r[6], "unk7": r[7],
                "unk8": r[8] | r[9] << 8, "unk10": r[10] | r[11] << 8,
                "neighbors": [x for x in r[12:20] if x != 0xFF],
                "unk20": r[20],
            })
        return out

    # ------------------------------------------------------------ faces

    def portrait_cells(self, n: int) -> tuple[bytes, bytes, bytes]:
        o = PORTRAIT_TABLE + n * 60
        return self.prg[o:o + 30], self.prg[o + 30:o + 60], self.prg[PORTRAIT_PALETTES + n * 8:PORTRAIT_PALETTES + n * 8 + 8]

    def mob_parts(self, cat: int) -> dict[str, list[tuple[int, bytes, bytes]]]:
        """slot -> 4 x (width in tiles, tile ids, ExRAM bytes)."""
        base = MOB_POINTERS + cat * 0x50

        def ptr(k: int) -> int:
            return self.prg[base + 2 * k] | self.prg[base + 2 * k + 1] << 8

        parts = {}
        for sid, _, first, size in MOB_SLOTS:
            items = []
            for k in range(first, first + 4):
                tp, ep = ptr(k), ptr(20 + k)
                n = ep - tp  # tile ids are immediately followed by the ExRAM bytes
                w = size[0] if size else n
                assert n == (w * size[1] if size else w), f"cat {cat} slot {sid}: {n} tiles"
                items.append((w, self.prg[MOB_DATA + tp - 0xA000:MOB_DATA + tp - 0xA000 + n],
                              self.prg[MOB_DATA + ep - 0xA000:MOB_DATA + ep - 0xA000 + n]))
            parts[sid] = items
        return parts

    def mob_palette(self, cat: int) -> bytes:
        return self.prg[MOB_PALETTES + cat * 8:MOB_PALETTES + cat * 8 + 8]

    def mob_cells(self, code: int) -> tuple[list[int], list[int], bytes]:
        """Compose a 5x6 face the way the game does: head, chin, then eyes/nose/mouth on top."""
        cat, sel = decode_mob_code(code)
        parts = self.mob_parts(cat)
        tiles, exram = [0] * 30, [0] * 30
        eyes, nose, mouth = MOB_LAYOUT[cat]
        for sid, at in zip(["head", "chin", "eyes", "nose", "mouth"], [0, 20, eyes, nose, mouth]):
            w, t, e = parts[sid][sel[sid]]
            for i in range(len(t)):
                r, c = divmod(i, w)
                tiles[at + r * 5 + c], exram[at + r * 5 + c] = t[i], e[i]
        return tiles, exram, self.mob_palette(cat)

    def face_pixels(self, code: int) -> bytes:
        """40x48 NES colour numbers for a character's face code."""
        tiles, exram, pal = self.mob_cells(code) if code & 0x8000 else self.portrait_cells(code)
        return self.render_cells(tiles, exram, PORTRAIT_W, pal)

    def map_cells(self) -> tuple[bytes, bytes]:
        n = MAP_W * MAP_H
        return self.prg[MAP_TILES:MAP_TILES + n], self.prg[MAP_EXRAM:MAP_EXRAM + n]


def decode_mob_code(code: int) -> tuple[int, dict[str, int]]:
    """15-bit mob face code (bit 15 = mob flag): category in bits 10-12, then 2-bit part indices."""
    return (code >> 10) & 7, {"head": (code >> 8) & 3, "eyes": (code >> 6) & 3, "nose": (code >> 4) & 3,
                              "mouth": (code >> 2) & 3, "chin": code & 3}


def kana(raw: bytes) -> str:
    """Game kana bytes (JIS X 0201 layout, hiragana glyphs at A6-DD) -> full-width hiragana."""
    raw = raw.split(b"\0", 1)[0]
    s = unicodedata.normalize("NFKC", raw.decode("cp932"))
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def load_tsv(name: str) -> list[list[str]]:
    with open(os.path.join(HERE, "data", name), encoding="utf-8") as f:
        return [line.rstrip("\n").split("\t") for line in f if line.strip() and not line.startswith("#")]


def load_gaiji() -> dict[int, str]:
    return {int(code, 16): ch for code, ch, *_ in load_tsv("gaiji.tsv")}
