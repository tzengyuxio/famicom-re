"""ROM decoder for FC 天地を喰らう (Capcom, 1989; MMC1, PRG 256 KB, CHR-RAM).

Bank 15 is fixed at $C000; the data banks are switched in at $8000. Everything here reads the ROM
directly; see docs/ROM_FORMAT.md for the formats.
"""
import os
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ROM = os.path.join(REPO, "roms", "Tenchi o Kurau (Japan) (Rev A).zip")

# ---------------------------------------------------------------- text
# Font tiles $00-$7F (pattern table $1000 of the menu screens). $80-$E1 = tile (code & $7F) with a
# dakuten tile ($72) above it, $E2-$EE = tile (code & $7F) - 10 with a handakuten tile ($73) above.
FONT = ("0123456789 └──*★" "かきくけこさしすせそたちつてとな" "にぬねのマメモユヨまみむめもやゆ" "よらりるれろわをんゃゅょっあいう"
        "えおアイウエオカキクケコサシスセ" "ソタチツテトナネハヒフミホはひふ" "へほラリルレロワンュョド金┌┐┘" "▶▼゛゜ヤム「ッ・ー!?/▌▐兵")
_DAKU = str.maketrans("かきくけこさしすせそたちつてとはひふへほカキクケコサシスセソタチツテトハヒフヘホウ",
                      "がぎぐげござじずぜぞだぢづでどばびぶべぼガギグゲゴザジズゼゾダヂヅデドバビブベボヴ")
_HANDAKU = str.maketrans("はひふへほハヒフヘホ", "ぱぴぷぺぽパピプペポ")
CONTROL = {0xEF: "{F0x}", 0xF0: "{dict}", 0xFA: "\n", 0xFB: "{FB}", 0xFC: "\n", 0xFD: "{page}", 0xFE: "", 0xFF: ""}


def char(c: int) -> str:
    if c < 0x80:
        return FONT[c]
    if c < 0xE2:
        b = FONT[c & 0x7F]
        r = b.translate(_DAKU)
        return r if r != b else b + "゛"
    b = FONT[(c & 0x7F) - 10]
    r = b.translate(_HANDAKU)
    return r if r != b else b + "゜"


def decode(bs: bytes) -> str:
    return "".join(char(c) if c < 0xEF else f"{{{c:02X}}}" for c in bs)


def nes_rgb(i: int) -> tuple[int, int, int]:
    c = NES_PALETTE[i & 0x3F]
    return c >> 16, (c >> 8) & 0xFF, c & 0xFF


NES_PALETTE = [int(x, 16) for x in [
    "7C7C7C", "0000FC", "0000BC", "4428BC", "940084", "A80020", "A81000", "881400", "503000", "007800", "006800",
    "005800", "004058", "000000", "000000", "000000", "BCBCBC", "0078F8", "0058F8", "6844FC", "D800CC", "E40058",
    "F83800", "E45C10", "AC7C00", "00B800", "00A800", "00A844", "008888", "000000", "000000", "000000", "F8F8F8",
    "3CBCFC", "6888FC", "9878F8", "F878F8", "F85898", "F87858", "FCA044", "F8B800", "B8F818", "58D854", "58F898",
    "00E8D8", "787878", "000000", "000000", "FCFCFC", "A4E4FC", "B8B8F8", "D8B8F8", "F8B8F8", "F8A4C0", "F0D0B0",
    "FCE0A8", "F8D878", "D8F878", "B8F8B8", "B8F8D8", "00FCFC", "F8D8F8", "000000", "000000"]]


def tile_2bpp(data: bytes, o: int = 0) -> list[int]:
    return [((data[o + y] >> (7 - x)) & 1) | (((data[o + 8 + y] >> (7 - x)) & 1) << 1) for y in range(8) for x in range(8)]


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        if path.lower().endswith(".zip"):
            with zipfile.ZipFile(path) as z:
                (name,) = [n for n in z.namelist() if n.lower().endswith(".nes")]
                data = z.read(name)
        else:
            with open(path, "rb") as f:
                data = f.read()
        self.prg = data[16:]

    def bank(self, b: int) -> bytes:
        return self.prg[b * 0x4000:(b + 1) * 0x4000]

    def byte(self, b: int, addr: int) -> int:
        """Byte at CPU address `addr` with bank `b` at $8000 (bank 15 is always at $C000)."""
        if addr >= 0xC000:
            return self.prg[15 * 0x4000 + addr - 0xC000]
        return self.prg[b * 0x4000 + addr - 0x8000]

    def read(self, b: int, addr: int, n: int) -> bytes:
        return bytes(self.byte(b, addr + i) for i in range(n))

    def string(self, b: int, addr: int, end=(0xFF,)) -> bytes:
        out = bytearray()
        while (c := self.byte(b, addr)) not in end:
            out.append(c)
            addr += 1
        return bytes(out)


# ---------------------------------------------------------------- maps
GRID_ROWS, GRID_COLS = 50, 32  # block grid at bank 9 $A700, 2 bytes per block: (block index, bank)
CHUNK_PAGE = (0x80, 0x8D, 0x9A)  # bank 9 page of the 2x2-metatile chunk table, per tileset ($D950)
METATILE_PAGE = (0x88, 0x95, 0xA2)  # bank 9 page of the metatile tables (TL, TR, BL, BR, attribute) ($F6C9)


class MapRom(Rom):
    def block_ref(self, row: int, col: int) -> tuple[int, int]:
        o = 9 * 0x4000 + 0x2700 + row * 64 + col * 2
        return self.prg[o], self.prg[o + 1]

    def block_metatiles(self, row: int, col: int, ts: int, alt: bool = False) -> list[list[int]]:
        """16x16 metatile ids of grid block (row, col) drawn with tileset `ts`."""
        idx, bank = self.block_ref(row, col)
        if bank == 0x0C and alt:
            bank = 0x0D
        blk = self.bank(bank)[idx * 72:idx * 72 + 72]
        b9 = self.bank(9)
        out = [[0] * 16 for _ in range(16)]
        for r in range(8):
            for c in range(8):
                ch = blk[r * 8 + c] + (256 if blk[0x40 + r] & (0x80 >> c) else 0)
                o = (CHUNK_PAGE[ts] - 0x80) * 256 + ch * 4
                for k in range(4):
                    out[r * 2 + k // 2][c * 2 + k % 2] = b9[o + k]
        return out

    def metatile(self, ts: int, m: int) -> tuple[list[int], int]:
        """The 4 tile numbers (TL, TR, BL, BR) and the attribute byte of metatile `m`."""
        b9 = self.bank(9)
        p = (METATILE_PAGE[ts] - 0x80) * 256 + m
        return [b9[p + k * 256] for k in range(4)], b9[p + 4 * 256]

    def entrances(self) -> list[dict]:
        """Entrance table (bank 7 $8000/$8100, 240 pointers): stepping on (row, col) pushes the current
        area and moves to (dest_row, dest_col) in area `area`. Positions are in metatiles."""
        out = []
        for i in range(0xF0):
            p = self.byte(7, 0x8000 + i) | self.byte(7, 0x8100 + i) << 8
            r = self.read(7, p, 9)
            out.append({"id": i, "ptr": p, "dir": r[0] >> 6, "row": r[1] * 16 + (r[0] & 0x3F), "col": r[3] * 16 + r[2],
                        "dest_row": r[5] * 16 + r[4], "dest_col": r[7] * 16 + r[6], "area": r[8]})
        return out

    def teleports(self) -> list[dict]:
        """Same-level warp table (bank 7 $8200/$82B0, 176 pointers): (row, col) -> (dest, area)."""
        out = []
        for i in range(0xB0):
            p = self.byte(7, 0x8200 + i) | self.byte(7, 0x82B0 + i) << 8
            r = self.read(7, p, 9)
            out.append({"id": i, "ptr": p, "row": r[1] * 16 + r[0], "col": r[3] * 16 + r[2], "flags": r[4] & 0xF0,
                        "dest_row": r[5] * 16 + (r[4] & 0x0F), "dest_col": r[7] * 16 + r[6], "area": r[8]})
        return out

    def area_type(self, area: int) -> int:
        """Area type nibble ($BF98 in bank 14): 0 = field, 1-3 = tileset 1, 4+ = tileset 2."""
        b = self.byte(14, 0xBF98 + area // 2)
        return b & 0x0F if area & 1 else b >> 4

    def area_tileset(self, area: int) -> int:
        t = self.area_type(area)
        return 0 if t == 0 else 1 if t < 4 else 2

    def bg_chr(self, typ: int) -> bytes:
        """BG pattern tiles $80-$FF for an area type: 2 KB at bank 4 + type * $800."""
        return self.prg[4 * 0x4000 + typ * 0x800:4 * 0x4000 + typ * 0x800 + 0x800]

    def bg_palette(self, typ: int) -> bytes:
        """BG palette (16 colours) of an area type: palette packet at $C6B2/$C6C2[type] in bank 15
        (first byte = start index, then colours up to a byte >= $80)."""
        p = self.byte(15, 0xC6B2 + typ) | self.byte(15, 0xC6C2 + typ) << 8
        pal = bytearray(32)
        i = self.byte(15, p)
        p += 1
        while (c := self.byte(15, p)) < 0x80:
            pal[i] = c
            i, p = i + 1, p + 1
        pal[0] = 0x0F if pal[0] == 0 else pal[0]
        return bytes(pal[:16])

    def render_blocks(self, rows: range, cols: range, typ: int, alt: bool = False):
        """PIL image of grid blocks rows x cols drawn as area type `typ`."""
        from PIL import Image
        ts = 0 if typ == 0 else 1 if typ < 4 else 2
        chr_, pal = self.bg_chr(typ), self.bg_palette(typ)
        tiles = {}
        mts = {}
        im = Image.new("RGB", (len(cols) * 256, len(rows) * 256))
        px = im.load()
        rgb = [nes_rgb(c) for c in pal]
        for bi, br in enumerate(rows):
            for bj, bc in enumerate(cols):
                grid = self.block_metatiles(br, bc, ts, alt)
                for y in range(16):
                    for x in range(16):
                        m = grid[y][x]
                        if m not in mts:
                            tl, at = self.metatile(ts, m)
                            mts[m] = (tl, (at & 3) * 4)
                        tl, pb = mts[m]
                        for k, t in enumerate(tl):
                            if t not in tiles:
                                tiles[t] = tile_2bpp(chr_, (t - 0x80) * 16) if t >= 0x80 else [0] * 64
                            ox, oy = bj * 256 + x * 16 + (k & 1) * 8, bi * 256 + y * 16 + (k >> 1) * 8
                            for i, c in enumerate(tiles[t]):
                                px[ox + (i & 7), oy + (i >> 3)] = rgb[pb + c] if c else rgb[0]
        return im


# ---------------------------------------------------------------- people, items, tactics
N_GENERALS = 217  # pointers $A800/$A900 (bank 12); ids 217-255 point into padding
PORTRAIT_FIXED = (0x0F, 0x37, 0x26)  # BG palette 3, colours 0-2, of the status / battle portrait
PORTRAIT_COLOR = (0x0F, 0x21, 0x11, 0x1A, 0x14, 0x00, 0x15, 0x17, 0x18, 0x20)  # colour 3 by +16 & $0F ($D0FD)
SOLDIER_TABLE = 0xBED0  # bank 12: 152 words, 兵士数 by rank (index 1 = 100, about +5 % per step)


def soldiers(rank: int) -> int:
    o = 12 * 0x4000 + SOLDIER_TABLE - 0x8000 + rank * 2
    return Rom._shared.prg[o] | Rom._shared.prg[o + 1] << 8


class GameRom(MapRom):
    def __init__(self, path: str = DEFAULT_ROM):
        super().__init__(path)
        Rom._shared = self

    def soldier_table(self) -> list[int]:
        return [self.byte(12, SOLDIER_TABLE + 2 * i) | self.byte(12, SOLDIER_TABLE + 2 * i + 1) << 8 for i in range(129)]

    def general_ptr(self, i: int) -> int:
        return self.byte(12, 0xA800 + i) | self.byte(12, 0xA900 + i) << 8

    def general(self, i: int) -> dict:
        p = self.general_ptr(i)
        r = self.read(12, p, 20)
        name = self.string(12, p + 20, end=(0xFE, 0xFF))
        kanji = [c for c in r[17:20] if c != 0xFF]
        banks, b = [], 1
        for k in range(len(kanji)):
            if r[16] & (0x80 >> k):
                b += 1
            banks.append(b)
        return {"id": i, "ptr": p, "name": decode(name), "raw": r,
                "buryoku": r[0], "chiryoku": r[1], "region": r[2], "b3": r[3], "weapon": r[4] & 0x1F, "b4_hi": r[4] >> 5,
                "armor": r[5], "enemy_rank": r[6], "ally_rank": r[7], "level": r[8], "speed": r[9],
                "portrait": list(r[10:16]), "color": r[16] & 0x0F, "kanji": list(zip(kanji, banks))}

    def generals(self) -> list[dict]:
        return [self.general(i) for i in range(N_GENERALS)]

    def portrait_tiles(self, chunks: list[int]) -> list[list[int]]:
        """36 tiles (6x6, row-major) of a portrait: chunk v = 6 tiles at bank 2|3 $8800 + (v & $7F) * $60."""
        out = []
        for v in chunks:
            o = (3 if v & 0x80 else 2) * 0x4000 + 0x800 + (v & 0x7F) * 0x60
            out += [tile_2bpp(self.prg, o + t * 16) for t in range(6)]
        return out

    def portrait_image(self, g: dict, scale: int = 1):
        from PIL import Image
        pal = [nes_rgb(c) for c in PORTRAIT_FIXED + (PORTRAIT_COLOR[g["color"]],)]
        im = Image.new("RGB", (48, 48))
        px = im.load()
        for t, pix in enumerate(self.portrait_tiles(g["portrait"])):
            for i, c in enumerate(pix):
                px[(t % 6) * 8 + i % 8, (t // 6) * 8 + i // 8] = pal[c]
        return im.resize((48 * scale, 48 * scale), Image.NEAREST) if scale > 1 else im

    def kanji_glyph(self, code: int, bank: int) -> list[int]:
        """16x16 1bpp glyph (256 values 0/1): 32 bytes at bank $8000 + code * 32, tiles TL, BL, TR, BR."""
        o = bank * 0x4000 + code * 32
        px = [0] * 256
        for t, (tx, ty) in enumerate(((0, 0), (0, 8), (8, 0), (8, 8))):
            for y in range(8):
                b = self.prg[o + t * 8 + y]
                for x in range(8):
                    px[(ty + y) * 16 + tx + x] = (b >> (7 - x)) & 1
        return px

    def kanji_image(self, g: dict, fg=(255, 255, 255), bg=(0, 0, 0)):
        from PIL import Image
        im = Image.new("RGB", (16 * max(1, len(g["kanji"])), 16), bg)
        px = im.load()
        for k, (code, bank) in enumerate(g["kanji"]):
            for i, v in enumerate(self.kanji_glyph(code, bank)):
                if v:
                    px[k * 16 + i % 16, i // 16] = fg
        return im

    # items: pointers $A3C8/$A438 (bank 12), record = price word + name
    def items(self) -> list[dict]:
        out = []
        atk = self.read(14, 0x8602, 20)
        armor = self.read(15, 0xE6D1, 24)
        for i in range(0x70):
            p = self.byte(12, 0xA3C8 + i) | self.byte(12, 0xA438 + i) << 8
            it = {"id": i, "ptr": p, "price": self.byte(12, p) | self.byte(12, p + 1) << 8,
                  "name": decode(self.string(12, p + 2)), "kind": "", "power": ""}
            if 0x40 <= i < 0x53:
                it["kind"], it["power"] = "weapon", atk[i - 0x3F]
            elif 0x58 <= i < 0x70:
                it["kind"], it["power"] = ("armor" if i < 0x66 else "helmet"), armor[i - 0x58]
            out.append(it)
        return out

    def shops(self) -> list[list[int]]:
        """Shop item lists (bank 14, pointers $905D/$9085, FF-terminated item ids)."""
        out = []
        for i in range(40):
            p = self.byte(14, 0x905D + i) | self.byte(14, 0x9085 + i) << 8
            out.append(list(self.string(14, p)))
        return out

    def tactics(self) -> list[dict]:
        learn = {self.byte(14, 0xB884 + lv): lv for lv in range(2, 32)}
        cols = {"group": 0xB8B6, "rank": 0xB8D5, "chiryoku": 0xB8F4, "target1": 0xBB40, "target_all": 0xBB5F,
                "element": 0xBB7E, "power": 0xBB9D, "b_bbbc": 0xBBBC, "sp": 0xBBDB, "field": 0xBBFA}
        out = []
        for i in range(1, 31):
            p = self.byte(12, 0xA700 + i) | self.byte(12, 0xA720 + i) << 8
            t = {"id": i, "name": decode(self.string(12, p)), "level": learn.get(i, "")}
            t.update({k: self.byte(14, a + i) for k, a in cols.items()})
            out.append(t)
        return out

    def place_name(self, area: int) -> str:
        if area < 0x52:
            return ""
        i = area - 0x40
        p = self.byte(12, 0xA140 + i) | self.byte(12, 0xA180 + i) << 8
        return decode(self.string(12, p))
