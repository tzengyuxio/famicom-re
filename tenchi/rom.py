"""ROM decoder for FC 天地を喰らう (Capcom, 1989; MMC1, PRG 256 KB, CHR-RAM).

Bank 15 is fixed at $C000; the data banks are switched in at $8000. Everything here reads the ROM
directly; see docs/ROM_FORMAT.md for the formats.
"""
import os
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ROM = os.path.join(REPO, "roms", "Tenchi o Kurau (Japan) (Rev A).zip")
KANJI_TSV = os.path.join(REPO, "tenchi", "data", "kanji.tsv")  # name glyph (code, bank) -> character, read by eye


def kanji_table() -> dict[tuple[int, int], str]:
    """Transcribed glyphs used in general names; "" for the two picture tiles of ザントウ (D6, D7)."""
    with open(KANJI_TSV, encoding="utf-8") as f:
        rows = [line.rstrip("\n").split("\t") for line in f][1:]
    return {(int(c, 16), int(b)): ch for c, b, ch in rows}

# ---------------------------------------------------------------- text
# Font tiles $00-$7F (pattern table $1000 of the menu screens). $80-$E1 = tile (code & $7F) with a
# dakuten tile ($72) above it, $E2-$EE = tile (code & $7F) - 10 with a handakuten tile ($73) above.
FONT = ("0123456789 └──*★" "かきくけこさしすせそたちつてとな" "にぬねのマメモユヨまみむめもやゆ" "よらりるれろわをんゃゅょっあいう"
        "えおアイウエオカキクケコサシスセ" "ソタチツテトナネハヒフミホはひふ" "へほラリルレロワンュョド金┌┐┘" "▶▼゛゜ヤム「ッ・ー!?/▌▐兵")
_DAKU = str.maketrans("かきくけこさしすせそたちつてとはひふへほカキクケコサシスセソタチツテトハヒフヘホウ",
                      "がぎぐげござじずぜぞだぢづでどばびぶべぼガギグゲゴザジズゼゾダヂヅデドバビブベボヴ")
_HANDAKU = str.maketrans("はひふへほハヒフヘホ", "ぱぴぷぺぽパピプペポ")
# Message controls ($D250): EF n = place name of area n, F0 n = dictionary word n, F1 n = item n, F2 n = general n,
# F3-F7 = names held in variables (item $4D, ..., the event's general $05F0), F8 lo hi = call code at hi:lo,
# FA / FC = newline, FB = wait for a key, FD = new page, FE / FF = end.
CONTROL = {0xF3: "{item}", 0xF4: "{name4}", 0xF5: "{name5}", 0xF6: "{name6}", 0xF7: "{name}", 0xF9: "{F9}",
           0xFA: "\n", 0xFB: "{key}", 0xFC: "\n", 0xFD: "{page}"}


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
        self.kanji_chars = kanji_table()

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
BLOCK_H = 15  # a block is one screen: 16 x 15 metatiles (its 8x8 chunks hold 16 rows; row 15 is never shown)
CHUNK_PAGE = (0x80, 0x8D, 0x9A)  # bank 9 page of the 2x2-metatile chunk table, per tileset ($D950)
METATILE_PAGE = (0x88, 0x95, 0xA2)  # bank 9 page of the metatile tables (TL, TR, BL, BR, attribute) ($F6C9)


class MapRom(Rom):
    def block_ref(self, row: int, col: int) -> tuple[int, int]:
        o = 9 * 0x4000 + 0x2700 + row * 64 + col * 2
        return self.prg[o], self.prg[o + 1]

    def block_metatiles(self, row: int, col: int, ts: int, alt: bool = False) -> list[list[int]]:
        """16x16 metatile ids of grid block (row, col) drawn with tileset `ts` (rows 0-14 are the screen)."""
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
        area and moves to (dest_row, dest_col) in area `area`. Positions are world metatiles
        (row = block row * 15 + row in block, col = block col * 16 + col in block)."""
        out = []
        for i in range(0xF0):
            p = self.byte(7, 0x8000 + i) | self.byte(7, 0x8100 + i) << 8
            r = self.read(7, p, 9)
            out.append({"id": i, "ptr": p, "dir": r[0] >> 6, "row": r[1] * BLOCK_H + (r[0] & 0x3F), "col": r[3] * 16 + r[2],
                        "dest_row": r[5] * BLOCK_H + r[4], "dest_col": r[7] * 16 + r[6], "area": r[8]})
        return out

    def teleports(self) -> list[dict]:
        """Same-level warp table (bank 7 $8200/$82B0, 176 pointers): (row, col) -> (dest, area)."""
        out = []
        for i in range(0xB0):
            p = self.byte(7, 0x8200 + i) | self.byte(7, 0x82B0 + i) << 8
            r = self.read(7, p, 9)
            out.append({"id": i, "ptr": p, "row": r[1] * BLOCK_H + r[0], "col": r[3] * 16 + r[2], "flags": r[4] & 0xF0,
                        "dest_row": r[5] * BLOCK_H + (r[4] & 0x0F), "dest_col": r[7] * 16 + r[6], "area": r[8]})
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
        im = Image.new("RGB", (len(cols) * 256, len(rows) * BLOCK_H * 16))
        px = im.load()
        rgb = [nes_rgb(c) for c in pal]
        for bi, br in enumerate(rows):
            for bj, bc in enumerate(cols):
                grid = self.block_metatiles(br, bc, ts, alt)
                for y in range(BLOCK_H):
                    for x in range(16):
                        m = grid[y][x]
                        if m not in mts:
                            tl, at = self.metatile(ts, m)
                            mts[m] = (tl, (at & 3) * 4)
                        tl, pb = mts[m]
                        for k, t in enumerate(tl):
                            if t not in tiles:
                                tiles[t] = tile_2bpp(chr_, (t - 0x80) * 16) if t >= 0x80 else [0] * 64
                            ox, oy = bj * 256 + x * 16 + (k & 1) * 8, bi * BLOCK_H * 16 + y * 16 + (k >> 1) * 8
                            for i, c in enumerate(tiles[t]):
                                px[ox + (i & 7), oy + (i >> 3)] = rgb[pb + c] if c else rgb[0]
        return im

    # ------------------------------------------------------------ reachability
    def terrain(self, row: int, col: int, ts: int, alt: bool = False) -> int:
        """Terrain of world metatile (row, col) in tileset `ts`: bank 9 page $B7 + ts ($D743)."""
        cache = self.__dict__.setdefault("_blocks", {})
        k = (row // BLOCK_H, col // 16, ts, alt)
        if k not in cache:
            cache[k] = self.block_metatiles(*k)
        return self.byte(9, 0xB700 + ts * 256 + cache[k][row % BLOCK_H][col % 16])

    def passable(self, row: int, col: int, ts: int) -> bool:
        """The walk routine ($F315) refuses terrain >= $10. A bank-$0C block counts as passable when either
        version is, since an event ($6570) can swap in the bank-$0D one (bridges and the like)."""
        if not (0 <= row < GRID_ROWS * BLOCK_H and 0 <= col < GRID_COLS * 16):
            return False
        if self.terrain(row, col, ts) < 0x10:
            return True
        return self.block_ref(row // BLOCK_H, col // 16)[1] == 0x0C and self.terrain(row, col, ts, True) < 0x10

    def arrivals(self, area: int) -> list[tuple[int, int]]:
        """Where the game puts the party in `area`: entrance destinations, and teleport destinations
        (area 0 = the field: the cave and castle exits that lead out onto the world map)."""
        cells = [(e["dest_row"], e["dest_col"]) for e in self.entrances() if e["area"] == area]
        cells += [(t["dest_row"], t["dest_col"]) for t in self.teleports() if t["area"] == area and (t["row"] or t["col"])]
        return sorted(set(cells))

    def reach(self, area: int) -> set[tuple[int, int]]:
        """Cells the party can stand on in `area`, walking from its arrival points. Stepping on terrain $0E
        runs the entrance check ($BC79; a record covers its cell and the one to the right) and $0F the teleport
        check ($BD77); without a match either one leaves the area ($BE2F). Leaving an entrance puts the party
        back on the entrance cell, so the walk goes on from there; teleports and exits lead elsewhere.
        On the field the record-less $0E cells are the pass gates (metatiles $3C / $64): at the start they turn
        the party back, and the story opens them later, so the walk goes through them there."""
        ts = self.area_tileset(area)
        doors = {(e["row"], e["col"] + d) for e in self.entrances() for d in (0, 1)}
        seeds = self.arrivals(area)
        seen, todo = set(seeds), list(seeds)
        while todo:
            row, col = cell = todo.pop()
            t = self.terrain(row, col, ts)
            if cell not in seeds and (t == 0x0F or t == 0x0E and area and cell not in doors):
                continue
            for nxt in ((row + 1, col), (row - 1, col), (row, col + 1), (row, col - 1)):
                if nxt not in seen and self.passable(*nxt, ts):
                    seen.add(nxt)
                    todo.append(nxt)
        return seen

    @staticmethod
    def visible(cells) -> set[tuple[int, int]]:
        """Cells that come on screen: the camera shows rows -7..+7 and columns -8..+7 around the party."""
        return {(row + dr, col + dc) for row, col in cells for dr in range(-7, 8) for dc in range(-8, 8)}


# ---------------------------------------------------------------- people, items, tactics
N_GENERALS = 217  # pointers $A800/$A900 (bank 12); ids 217-255 point into padding
PORTRAIT_FIXED = (0x0F, 0x37, 0x26)  # BG palette 3, colours 0-2, of the status / battle portrait
PORTRAIT_COLOR = (0x0F, 0x21, 0x11, 0x1A, 0x14, 0x00, 0x15, 0x17, 0x18, 0x20)  # colour 3 by +16 & $0F ($D0FD)
SOLDIER_TABLE = 0xBED0  # bank 12: 152 words, 兵士数 by rank (index 1 = 100, about +5 % per step)

GROWTH_RATE = 0xB569  # bank 14: 25 rates; soldiers x (256 + rate) / 256 per level up to 49 ($B4E0)
GROWTH_STEP = 0xB582  # bank 14: levels 10, 20, 30, 40 move to the next rate
N_FORMATIONS = 80  # fixed battles, bank 12 $8D60, 5 general ids each
GENERIC = {1: "カイゾク", 2: "サンゾク", 3: "トウゾク", 4: "へイシ"}  # ids the random formations fill with


class GameRom(MapRom):
    def soldier_table(self) -> list[int]:
        return [self.byte(12, SOLDIER_TABLE + 2 * i) | self.byte(12, SOLDIER_TABLE + 2 * i + 1) << 8 for i in range(129)]

    def soldiers(self, rank: int, level: int = 1) -> int:
        """兵士数 of soldier rank byte (record +7). Bit 7 set: grows with the party level from 100."""
        if not rank & 0x80:
            return self.byte(12, SOLDIER_TABLE + 2 * rank) | self.byte(12, SOLDIER_TABLE + 2 * rank + 1) << 8
        y, v = rank & 0x7F, 100
        steps = self.read(14, GROWTH_STEP, 5)
        for f in range(1, 256):
            if f in steps:
                y += 1
            if f == level:
                return v
            v = ((v & 0xFFFF) * (256 + self.byte(14, GROWTH_RATE + y)) >> 8) if f < 50 else v + 2000
        return v

    def general_ptr(self, i: int) -> int:
        return self.byte(12, 0xA800 + i) | self.byte(12, 0xA900 + i) << 8

    def general(self, i: int) -> dict:
        p = self.general_ptr(i)
        r = self.read(12, p, 20)
        name = self.string(12, p + 20, end=(0xFE, 0xFF))
        kanji = [c for c in r[17:20] if c != 0xFF]
        banks = [2 if r[16] & (0x80 >> k) else 1 for k in range(len(kanji))]  # glyph bank per kanji ($D4C9)
        return {"id": i, "ptr": p, "name": decode(name), "raw": r,
                "buryoku": r[0], "chiryoku": r[1], "region": r[2], "b3": r[3], "weapon": r[4] & 0x1F, "b4_hi": r[4] >> 5,
                "armor": r[5], "enemy_rank": r[6], "ally_rank": r[7], "level": r[8], "speed": r[9],
                "portrait": list(r[10:16]), "color": r[16] & 0x0F, "kanji": list(zip(kanji, banks)),
                "kanji_text": "".join(self.kanji_chars.get(k, "?") for k in zip(kanji, banks))}

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

    def shop_of_area(self, area: int) -> tuple[int, int]:
        """(left, right) shop index of a town: $8F9D+area if the block column $63 < 7, else $8FDD+area."""
        return self.byte(14, 0x8F9D + area), self.byte(14, 0x8FDD + area)

    def chests(self) -> list[dict]:
        """Treasure chests (bank 12 $8800/$8880 per area; 5-byte records row, block row, col, block col,
        item; an area owns the records up to the next area's pointer). Opened flags: bit 7>>n of $6600+area."""
        out = []
        ptr = [self.byte(12, 0x8800 + a) | self.byte(12, 0x8880 + a) << 8 for a in range(0x81)]
        for a in range(0x80):
            for k in range(max(0, ptr[a + 1] - ptr[a]) // 5):
                r = self.read(12, ptr[a] + k * 5, 5)
                out.append({"area": a, "slot": k, "row": r[1] * BLOCK_H + r[0], "col": r[3] * 16 + r[2], "item": r[4]})
        return out

    def zone(self, brow: int, bcol: int) -> int:
        """Encounter zone ($6026) of an overworld block: nibbles at bank 13 $BE98, 12 bytes per block row
        rows 4-23 (high nibble = even column)."""
        if not 4 <= brow < 24 or bcol >= 24:
            return 0
        b = self.byte(13, 0xBE98 + (brow - 4) * 12 + bcol // 2)
        return b & 0x0F if bcol & 1 else b >> 4

    def formations(self) -> list[list[int]]:
        return [list(self.read(12, 0x8D60 + k * 5, 5)) for k in range(N_FORMATIONS)]

    def enemy_flags(self) -> bytes:
        """New-game random-encounter flags: bit (0x80 >> (id & 7)) of bank 13 $98C7[id >> 3] -> $6300 = $98."""
        return self.read(13, 0x98C7, 32)

    def encounter_pools(self) -> dict[int, list[int]]:
        """Named generals a random battle in zone z may draw: flagged ids 1-$E0 whose record +2 == z
        (bank 14 $B43B). Events can add ids later (lists at $E397 calls)."""
        fl = self.enemy_flags()
        pools = {z: [] for z in range(1, 9)}
        for i in range(1, N_GENERALS):
            z = self.byte(12, self.general_ptr(i) + 2)
            if fl[i >> 3] & (0x80 >> (i & 7)) and z in pools:
                pools[z].append(i)
        return pools

    def word(self, n: int) -> bytes:
        """Dictionary word n (bank 13, pointers $B700/$B800)."""
        return self.string(13, self.byte(13, 0xB700 + n) | self.byte(13, 0xB800 + n) << 8, end=(0xFE, 0xFF))

    def text(self, bs: bytes, depth: int = 0) -> str:
        out, i = [], 0
        while i < len(bs):
            c = bs[i]
            i += 1
            if c < 0xEF:
                out.append(char(c))
            elif c in (0xEF, 0xF0, 0xF1, 0xF2) and i < len(bs):
                n = bs[i]
                i += 1
                if c == 0xEF:
                    out.append(self.place_name(n) or f"{{place{n:02X}}}")
                elif c == 0xF0:
                    out.append(self.text(self.word(n), depth + 1) if depth < 3 else "{word}")
                elif c == 0xF1:
                    out.append(self.item_name(n))
                else:
                    out.append(self.general(n)["name"] if n < N_GENERALS else f"{{general{n:02X}}}")
            elif c == 0xF8 and i + 1 < len(bs):
                out.append(f"{{call {bs[i + 1]:02X}{bs[i]:02X}}}")
                i += 2
            elif c in (0xFE, 0xFF):
                break
            else:
                out.append(CONTROL.get(c, f"{{{c:02X}}}"))
        return "".join(out)

    def item_name(self, i: int) -> str:
        i &= 0x7F
        p = self.byte(12, 0xA3C8 + i) | self.byte(12, 0xA438 + i) << 8
        return decode(self.string(12, p + 2))

    def messages(self) -> list[dict]:
        """Dialogue: banks 10 and 11, 512 pointers each at $8000 (low) / $8200 (high), FF-terminated."""
        out = []
        for b in (10, 11):
            for i in range(512):
                p = self.byte(b, 0x8000 + i) | self.byte(b, 0x8200 + i) << 8
                if 0x8400 <= p < 0xC000:
                    raw = self.string(b, p)
                    out.append({"bank": b, "id": i, "ptr": p, "text": self.text(raw), "raw": raw})
        return out

    def place_name(self, area: int) -> str:
        if area < 0x52:
            return ""
        i = area - 0x40
        p = self.byte(12, 0xA140 + i) | self.byte(12, 0xA180 + i) << 8
        return decode(self.string(12, p))
