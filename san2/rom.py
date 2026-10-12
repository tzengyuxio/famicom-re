"""FC 三國志II (KOEI, 1991) ROM decoding.

All offsets are PRG offsets (file offset - 0x10). See san2/docs/ROM_FORMAT.md.
"""
import os
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Sangokushi II (Japan).zip")

PRG_SIZE = 0x40000
CHR_START = 0x10 + PRG_SIZE
BANK = 0x2000

# ---------------------------------------------------------------- text
GLYPHS = 0x2A004            # bank 21: 419 x [SJIS LE16, 4 x tile LE16] (16x16 kanji glyphs)
GLYPH_COUNT = 419
GAIJI = {  # 0xEBxx -> kanji, identified from the glyphs and the readings of the names that use them
    0xEB9F: "瓚", 0xEBA0: "昱", 0xEBA1: "彧", 0xEBA2: "郃", 0xEBA3: "蒯", 0xEBA4: "蔡", 0xEBA5: "傕",
    0xEBA7: "汜", 0xEBA8: "詡", 0xEBA9: "鄧", 0xEBAA: "兗", 0xEBAB: "龐", 0xEBAC: "繇", 0xEBAD: "邈",
    0xEBAE: "隲", 0xEBAF: "晙", 0xEBB0: "闞", 0xEBB1: "玠", 0xEBB2: "顗", 0xEBB3: "邢", 0xEBB4: "歆",
    0xEBB5: "闓", 0xEBB6: "禕", 0xEBB8: "琬", 0xEBB9: "郝", 0xEBBA: "琮", 0xEBBC: "褚", 0xEBC0: "琦",
    0xEBC1: "琮", 0xEBC3: "幷", 0xEBC4: "璝", 0xEBC6: "彤", 0xEBC7: "琬",
}

# ---------------------------------------------------------------- generals
NAMES = 0x34004             # bank 26: 352 x 15 bytes = name (SJIS, 7) + reading (kana, 8)
NAME_SIZE = 15
GENERAL_COUNT = 352

SCENARIO_TITLES = ["董卓の横暴", "曹操の雄飛", "劉備の雌伏", "諸葛亮登場", "関羽の奮戦", "三國の鼎立"]


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


def sjis(b: bytes) -> str:
    """SJIS text up to the first 0, with the game's gaiji (0xEBxx) mapped to kanji."""
    out, i = [], 0
    b = b.split(b"\0")[0]
    while i < len(b):
        if b[i] >= 0x80 and i + 1 < len(b) and not 0xA1 <= b[i] <= 0xDF:
            code = b[i] << 8 | b[i + 1]
            out.append(GAIJI.get(code) or bytes(b[i:i + 2]).decode("cp932", "replace"))
            i += 2
        else:
            out.append(kana(b[i:i + 1]))
            i += 1
    return "".join(out)


def kana(b: bytes) -> str:
    """Game kana bytes (JIS X 0201 layout, drawn as hiragana) -> hiragana."""
    s = unicodedata.normalize("NFKC", b.split(b"\0")[0].decode("cp932", "replace"))
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)




# ---------------------------------------------------------------- tables (PRG offsets, see docs/ROM_FORMAT.md)
SCENARIO_YEARS = [189, 194, 201, 208, 215, 220]
SCENARIO_COUNT = 6
LOYALTY = 0x32004           # bank 25: 352 x 6 = loyalty per scenario (FF = absent)
PERSONAL = 0x32844          # bank 25: 352 x 9 = 義理 仁徳 野望 相性, kin mask LE16, birth year, face LE16
STATS = 0x334A4             # bank 25: 352 x 3 = 知力 武力 魅力
PLACEMENT = 0x3601C         # bank 27: 352 x 22 = debut year, ?, province x6, id LE16, list link/flags x6
PROVINCE_COUNT = 41
PROVINCES = 0x3013E         # bank 24: 6 x 41 x 25, copied verbatim to WRAM $73F5 at scenario start
PROVINCE_SIZE = 25
ADJACENCY = 0x28004         # bank 20: 41 x 6, 1-based, FF = none; slot d and 5-d are opposite hex sides
CURSOR_GRID = 0x31A8C       # bank 24: 8 x 9 grid of 0-based provinces for the map cursor (FF = none)
HEX_DIRS = [(1, 0), (1, -1), (0, -1), (0, 1), (-1, 1), (-1, 0)]  # axial step of each adjacency slot
MAP = 0x2B062               # bank 21: 28 x 18 tile ids, then 28 x 18 ExRAM bytes
MAP_W, MAP_H = 28, 18
MAP_PALETTE = 0x33CFC       # BG palette of the map and the face screens
BATTLE = 0x26FE8            # bank 19 tail: 41 x 78 = 13 x 12 hexes, 4 bits each (high nibble first)
BATTLE_COLS, BATTLE_ROWS = 13, 12
BATTLE_PALETTE = 0x33D1C
TERRAIN = ["平地", "森", "林", "山", "河", "村", "城"]  # named by how the tiles look
TERRAIN_EXRAM = [(0x6F,) * 4] * 3 + [(0x2F,) * 4] * 2 + [(0x6F,) * 4, (0x6F, 0x6F, 0x2F, 0x2F)]  # CHR bank 0x2F
TERRAIN_TILES = [(0, 1, 2, 3), (4, 5, 6, 7), (8, 9, 10, 11), (12, 13, 14, 15), (16, 16, 16, 16),
                 (17, 18, 19, 20), (21, 22, 23, 24)]
FACE_W, FACE_H = 5, 6
DEDICATED = [(0x2C004, 0x2CFF4, 1, 136), (0x2E004, 0x2E784, 137, 200)]  # tiles, ExRAM, first, last face
FACE_COUNT = 200
COMP_TOP, COMP_BOTTOM, COMP_PARTS = 0x2EF04, 0x2F0E4, 0x2F684  # ExRAM of top/bottom halves at +0x3C0
COMP_GROUPS = 8
COMP_HOLE = (0x7D, 0x24)    # blank cell of a half that a part fills
COMP_SLOTS = [("top", "上半", 3), ("bottom", "下半", 5), ("a", "部件A", 7), ("b", "部件B", 9), ("c", "部件C", 11)]


def is_composite(code: int) -> bool:
    return bool(code & 0x8000)


def decode_face_code(code: int) -> tuple[int, list[int]]:
    """Composite code -> (group, [top, bottom, a, b, c] variants 0-3)."""
    return code & 7, [code >> shift & 3 for _, _, shift in COMP_SLOTS]


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.data = read_rom(path)
        assert self.data[:4] == b"NES\x1a" and self.data[4] == 16 and self.data[5] == 32, "not the expected ROM"
        self.prg = self.data[0x10:CHR_START]
        self.chr = self.data[CHR_START:]

    def u16(self, o: int) -> int:
        return self.prg[o] | self.prg[o + 1] << 8

    def palette(self, o: int = MAP_PALETTE) -> bytes:
        return self.prg[o:o + 16]

    # ------------------------------------------------------------ generals
    def general(self, n: int) -> dict:
        r = self.prg[NAMES + n * NAME_SIZE:NAMES + (n + 1) * NAME_SIZE]
        q = self.prg[PERSONAL + 9 * n:PERSONAL + 9 * n + 9]
        s = self.prg[STATS + 3 * n:STATS + 3 * n + 3]
        pl = self.prg[PLACEMENT + 22 * n:PLACEMENT + 22 * n + 22]
        assert pl[8] | pl[9] << 8 == n
        return {
            "id": n, "name": sjis(r[:7]), "reading": kana(r[7:]),
            "int": s[0], "war": s[1], "cha": s[2], "giri": q[0], "jintoku": q[1], "yabou": q[2], "aishou": q[3],
            "kin": q[4] | q[5] << 8, "birth": q[6], "face": q[7] | q[8] << 8,
            "debut": None if pl[0] == 0xFF else pl[0], "unknown1": pl[1],
            "scenarios": [self.placement(n, sc) for sc in range(SCENARIO_COUNT)],
        }

    def placement(self, n: int, sc: int) -> dict | None:
        """Where general n starts in scenario sc (None = not in the scenario)."""
        pl = PLACEMENT + 22 * n
        prov, loyalty, flags = self.prg[pl + 2 + sc], self.prg[LOYALTY + 6 * n + sc], self.prg[pl + 11 + 2 * sc]
        if prov == 0xFF:
            return None
        debut = self.prg[pl]
        appears = loyalty != 0xFF or debut == SCENARIO_YEARS[sc] - 1  # the game starts in December of the year before
        status = "未登場" if not appears else "君主" if flags & 0x80 else "在野" if flags & 0x20 else "武將"
        soldiers = 0 if not appears or flags & 0x20 else 100 if flags & 0x80 else 50 if flags & 0x10 else 10
        return {"province": prov + 1, "status": status, "loyalty": loyalty if status == "武將" and loyalty != 0xFF else None,
                "soldiers": soldiers}

    def generals(self) -> list[dict]:
        return [self.general(n) for n in range(GENERAL_COUNT)]

    # ------------------------------------------------------------ provinces
    def province(self, sc: int, i: int) -> dict:
        o = PROVINCES + PROVINCE_SIZE * (PROVINCE_COUNT * sc + i)
        r = self.prg[o:o + PROVINCE_SIZE]
        return {"province": i + 1, "gold": self.u16(o + 8), "food": self.u16(o + 10), "population": self.u16(o + 12),
                "faction": None if r[14] == 0xFF else r[14], "loyalty": r[20], "land": r[21], "flood": r[22],
                "horses": r[23], "rate": r[24]}

    def faction_rulers(self, sc: int) -> dict[int, int]:
        """Faction index -> ruler's general id: the ruler (flag 0x80) standing in a province of that faction."""
        out = {}
        for n in range(GENERAL_COUNT):
            p = self.placement(n, sc)
            if p and p["status"] == "君主":
                out[self.province(sc, p["province"] - 1)["faction"]] = n
        return out

    def adjacency(self) -> list[list[int | None]]:
        """Per province, the neighbour (1-based) on each of the 6 hex sides (None = no neighbour)."""
        return [[None if v == 0xFF else v for v in self.prg[ADJACENCY + 6 * i:ADJACENCY + 6 * i + 6]]
                for i in range(PROVINCE_COUNT)]

    def hex_layout(self) -> dict[int, tuple[int, int]]:
        """Axial hex coordinates of every province, following the sides of the adjacency table.

        Raises if two provinces would land on one hex or a side disagrees with the walk."""
        adj, pos, todo = self.adjacency(), {1: (0, 0)}, [1]
        while todo:
            i = todo.pop()
            for d, j in enumerate(adj[i - 1]):
                if j is None:
                    continue
                q = (pos[i][0] + HEX_DIRS[d][0], pos[i][1] + HEX_DIRS[d][1])
                if j in pos:
                    assert pos[j] == q, (i, j)
                else:
                    pos[j] = q
                    todo.append(j)
        assert len(pos) == PROVINCE_COUNT and len(set(pos.values())) == PROVINCE_COUNT
        return pos

    # ------------------------------------------------------------ graphics
    def tile(self, exram: int, t: int) -> list[list[int]]:
        o = (exram & 0x3F) * 0x1000 + t * 16
        lo, hi = self.chr[o:o + 8], self.chr[o + 8:o + 16]
        return [[(lo[y] >> (7 - x) & 1) | (hi[y] >> (7 - x) & 1) << 1 for x in range(8)] for y in range(8)]

    def render_cells(self, tiles, exram, w: int, palettes: bytes, mask=None) -> bytes:
        """Tile grid -> NES colour numbers (row-major); cells with mask[i] false become 255."""
        h = len(tiles) // w
        out = bytearray([255]) * (w * 8 * h * 8)
        for i, (t, e) in enumerate(zip(tiles, exram)):
            if mask is not None and not mask[i]:
                continue
            r, c = divmod(i, w)
            pal = palettes[(e >> 6) * 4:(e >> 6) * 4 + 4]
            for y, row in enumerate(self.tile(e, t)):
                for x, v in enumerate(row):
                    out[(r * 8 + y) * w * 8 + c * 8 + x] = (pal[v] if v else palettes[0]) & 0x3F
        return bytes(out)

    def map_cells(self) -> tuple[list[int], list[int]]:
        n = MAP_W * MAP_H
        return list(self.prg[MAP:MAP + n]), list(self.prg[MAP + n:MAP + 2 * n])

    def map_pixels(self) -> bytes:
        return self.render_cells(*self.map_cells(), MAP_W, self.palette())

    # ------------------------------------------------------------ faces
    def face_cells(self, code: int) -> tuple[list[int], list[int]]:
        """(30 tile ids, 30 ExRAM bytes) of a 5x6 face, as the game puts them in the name table."""
        if not is_composite(code):
            for tiles, ex, first, last in DEDICATED:
                if first <= code <= last:
                    o = 30 * (code - first)
                    return list(self.prg[tiles + o:tiles + o + 30]), list(self.prg[ex + o:ex + o + 30])
            raise ValueError(f"no face {code}")
        group, (top, bottom, *parts) = decode_face_code(code)
        tiles, ex = [], []
        for base, v in ((COMP_TOP, top), (COMP_BOTTOM, bottom)):
            o = base + 15 * (4 * group + v)
            tiles += self.prg[o:o + 15]
            ex += self.prg[o + 0x3C0:o + 0x3C0 + 15]
        for cells, o, v in zip(self.part_cells(group), self.part_offsets(group), parts):
            n = len(cells)
            o += 2 * n * v
            for k, cell in enumerate(cells):
                tiles[cell], ex[cell] = self.prg[o + k], self.prg[o + n + k]
        return tiles, ex

    def part_cells(self, group: int) -> list[list[int]]:
        """Cells of parts a, b, c: the blank cells of the group's halves; a and b take the first two rows
        that have blanks, c all the rest (group 4: two rows)."""
        rows = {}
        for half, base in enumerate((COMP_TOP, COMP_BOTTOM)):
            o = base + 15 * 4 * group
            for k in range(15):
                if (self.prg[o + k], self.prg[o + 0x3C0 + k]) == COMP_HOLE:
                    rows.setdefault(half * 3 + k // 5, []).append(half * 15 + k)
        rs = [rows[r] for r in sorted(rows)]
        assert len(rs) >= 3, (group, rows)
        return [rs[0], rs[1], [cell for r in rs[2:] for cell in r]]

    def part_offsets(self, group: int) -> list[int]:
        """PRG offsets of parts a, b, c of a group (4 variants of n tiles + n ExRAM bytes each)."""
        o, out = COMP_PARTS, []
        for g in range(group + 1):
            for cells in self.part_cells(g):
                if g == group:
                    out.append(o)
                o += 4 * 2 * len(cells)
        return out

    def face_pixels(self, code: int) -> bytes:
        return self.render_cells(*self.face_cells(code), FACE_W, self.palette())

    # ------------------------------------------------------------ battle maps
    def battle_terrain(self, i: int) -> list[list[int]]:
        """13 x 12 terrain ids (rows of columns 0-12) of province i's battle map (0-based)."""
        d = self.prg[BATTLE + 78 * i:BATTLE + 78 * i + 78]
        nib = [v for b in d for v in (b >> 4, b & 15)]
        return [nib[r * BATTLE_COLS:(r + 1) * BATTLE_COLS] for r in range(BATTLE_ROWS)]

    def battle_screen(self, i: int) -> tuple[list[int], list[int]]:
        """26 x 25 tiles + ExRAM of the battle field: each hex is 2x2 tiles, odd columns half a hex lower."""
        w, h = 2 * BATTLE_COLS, 2 * BATTLE_ROWS + 1
        tiles, ex = [0] * (w * h), [0] * (w * h)
        for r, row in enumerate(self.battle_terrain(i)):
            for c, t in enumerate(row):
                y = 2 * r + c % 2
                for k, tid in enumerate(TERRAIN_TILES[t]):
                    a = (y + k // 2) * w + 2 * c + k % 2
                    tiles[a], ex[a] = tid, TERRAIN_EXRAM[t][k]
        return tiles, ex

    def battle_pixels(self, i: int) -> bytes:
        return self.render_cells(*self.battle_screen(i), 2 * BATTLE_COLS, self.palette(BATTLE_PALETTE))
