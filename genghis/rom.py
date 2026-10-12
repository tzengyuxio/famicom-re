"""FC 蒼き狼と白き牝鹿・ジンギスカン (KOEI, 1988) ROM decoding.

All offsets are PRG offsets (file offset - 0x10). See genghis/docs/ROM_FORMAT.md.
"""
import os
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Aoki Ookami to Shiroki Mejika - Genghis Khan (Japan).zip")

# Scenario images: copied to WRAM $63F0 at game start. key -> (PRG base, label)
SCENARIOS = {"mongol": (0x1C008, "モンゴルへん"), "world": (0x1D6B8, "せかいへん")}
WRAM_BASE = 0x63F0
HEADER = 0x65BB          # u16 count, u16 year - 1, 03 00
TRIBES, TRIBE_SIZE = 0x63F0, 17
RULERS, RULER_SIZE = 0x65C1, 32
GENERALS, GENERAL_SIZE = 0x6921, 30
EXTRA8, EXTRA8_SIZE = 0x6B97, 8
HEIRS, HEIR_SIZE = 0x6C6F, 21
PROVINCES, PROVINCE_SIZE = 0x6E13, 83
ADJACENCY, ADJACENCY_SIZE = 0x76D4, 12
SLOTS, GENERAL_SLOTS = 27, 20
STATS = ["統率", "判断", "企画", "説得", "体力", "武力"]
WOMEN, WOMAN_SIZE, WOMAN_COUNT, MONGOL_WOMEN = 0x1EF70, 22, 40, 15

# Province record u16 fields: offset -> (column name, screen label)
PROVINCE_FIELDS = [(0x14, "Busou", "ぶそうど"), (0x16, "Kunren", "くんれんど"), (0x18, "Heishi", "へいしすう"),
                   (0x1A, "Keizai", "けいざいりょく"), (0x1C, "Machi", "まちづくり"),
                   (0x1E, "Shiro_Tsuyosa", "しろのつよさ"), (0x20, "Shirozukuri", "しろづくり"),
                   *[(0x22 + 2 * i, f"Goods{i + 1}", f"とくさんひん{i + 1}") for i in range(10)],
                   (0x36, "Food", "しょくりょう"), (0x38, "Unk38", ""), (0x3A, "Tokusan", "とくさんひんづくり"),
                   (0x3C, "Unk3C", ""), (0x3E, "Food_Make", "しょくりょうづくり"), (0x40, "Gold", "きん"),
                   (0x42, "Moral", "モラル"), (0x44, "Unk44", "")]

# Portraits: 5x6 tiles. Dedicated: pointer table [bank, lo, hi, 0] x 83 (bank 10 $BCB4)
FACE_W, FACE_H = 5, 6
PORTRAIT_PTRS, PORTRAIT_COUNT = 0x2BCB4, 83
# Mob faces: code bit 15 set; cat bits 13-12, frame 11-9, eyes 8-6, nose 5-3, mouth 2-0.
MOB_BANK = 0x28000                                      # bank 10, CPU $8000
MOB_CAT_BASE = 0x2BECC                                  # u16 x 4: first pointer index per category
MOB_PARTS = [("head", "框", 0x2BE00, 9), ("eyes", "眼", 0x2BE20, 6), ("nose", "鼻", 0x2BE40, 3),
             ("mouth", "口", 0x2BE60, 0)]                 # (slot, label, pointer table, code shift)
MOB_CATEGORIES, MOB_CHOICES = 3, [8, 4, 4]
# Cell indexes (row * 5 + col) of each part's tiles on the 5x6 grid, in data order
FRAME_CELLS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 14, 15, 19, 20, 24, 25, 29]
PART_CELLS = {"head": FRAME_CELLS, "eyes": [11, 12, 13], "nose": [16, 17, 18], "mouth": [21, 22, 23, 26, 27, 28]}
# BG palette of the menus that show faces (bank 15 $BF9E, = the scenario menu's palette). Mob faces and
# most portraits use sub-palette 0; byte 3 of a portrait's pointer entry selects another (2 for P70-P79).
UI_PALETTE = 0x3FF9E
FACE_PALETTE = bytes([0x3E, 0x27, 0x38, 0x30])

# Strategic maps (bank 8): 20x16 tile nametable drawn at screen tile (10, 4); tiles from 0x92 at $1000
MAP_W, MAP_H, MAP_X, MAP_Y, MAP_FIRST_TILE = 20, 16, 10, 4, 0x92
MAPS = {"mongol": {"nt": 0x223EC, "attr": 0x218CC, "tiles": 0x2194C, "pal": 0x22672},
        "world": {"nt": 0x2252C, "attr": 0x2190C, "tiles": 0x21EDC, "pal": 0x2268F}}

# Battle maps: 41 x 16x10 cells (idx 0-13 Mongol tribes, 14-40 World countries)
BATTLE_MAPS, BATTLE_COUNT, BATTLE_W, BATTLE_H = 0x24B30, 41, 16, 10
BATTLE_BLOCKS = 0x17B9C   # 16 bytes (4x4 tile ids) per terrain 0-7
# 176 bytes per map: two nametable attribute tables of 8 x 11 bytes (left 32 columns, then right).
# The map is drawn from nametable row 4, so map row y sits on nametable row (y + 4) % 30; the data
# leaves attribute rows 26-27 empty so that map row 26 starts a fresh attribute row at the wrap.
BATTLE_ATTRS, ATTR_SEAM = 0x11702, 26
BATTLE_TILES, BATTLE_FIRST_TILE, BATTLE_TILE_COUNT = 0x24004, 0x92, 110  # tiles $92-$FF
BATTLE_PALETTE = 0x24864
BATTLE_TW, BATTLE_TH = BATTLE_W * 4, BATTLE_H * 4 + 2  # 64 x 42 tiles; odd columns are 2 tiles lower
# Names from the block graphics (battle_maps/terrain.png); bit 7 of a cell = entry cell (推定)
TERRAIN_NAMES = {0: "水", 1: "砂漠", 2: "平原", 3: "森林", 4: "山", 5: "町", 6: "城", 7: "不可進入"}
TERRAIN_TAGS = ["water", "desert", "plain", "forest", "mountain", "town", "castle", "blocked"]

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


def text(b: bytes) -> str:
    """JIS X0201 half-width text; ESC K = katakana, ESC H (default) = hiragana."""
    out, kata, i = [], False, 0
    while i < len(b) and b[i]:
        if b[i] == 0x1B and i + 1 < len(b):
            kata, i = b[i + 1] == 0x4B, i + 2
            continue
        s = unicodedata.normalize("NFKC", bytes([b[i]]).decode("cp932", "replace"))
        if not kata:
            s = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)
        out.append(s)
        i += 1
    return "".join(out).replace("-", "ー")


def tile_pixels(data: bytes, off: int) -> list[int]:
    """One 2bpp NES tile -> 64 colour indexes."""
    return [((data[off + y] >> (7 - x)) & 1) | (((data[off + 8 + y] >> (7 - x)) & 1) << 1)
            for y in range(8) for x in range(8)]


def u16(b: bytes, o: int) -> int:
    return b[o] | b[o + 1] << 8


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
        assert self.data[:4] == b"NES\x1a" and self.data[4] == 16 and self.data[5] == 0, "not the expected ROM"
        self.prg = self.data[0x10:0x10 + 0x40000]

    # ------------------------------------------------------------ scenarios
    def image(self, sc: str, addr: int, size: int) -> bytes:
        o = SCENARIOS[sc][0] + addr - WRAM_BASE
        return self.prg[o:o + size]

    def owner_pointer_base(self, sc: str) -> int:
        """CPU address of ruler 0 as the image's internal pointers see it (bank at $8000)."""
        return 0x8000 + ((SCENARIOS[sc][0] + RULERS - WRAM_BASE) & 0x3FFF)

    def scenario(self, sc: str) -> dict:
        h = self.image(sc, HEADER, 6)
        count = u16(h, 0)

        def person(r: bytes) -> dict:
            return {"name": text(r[:14]), "age": r[14], "stats": [u16(r, 15 + 2 * i) for i in range(6)],
                    "unk27": r[27], "face": u16(r, 28)}

        rulers = []
        for k in range(count):
            r = self.image(sc, RULERS + k * RULER_SIZE, RULER_SIZE)
            rulers.append({**person(r), "id": k, "country": r[30], "unk31": r[31]})
        generals = []
        for k in range(GENERAL_SLOTS):
            r = self.image(sc, GENERALS + k * GENERAL_SIZE, GENERAL_SIZE)
            if any(r[:14]):
                generals.append({**person(r), "slot": k, "family": k // 5})
        heirs = []
        for k in range(GENERAL_SLOTS):
            r = self.image(sc, HEIRS + k * HEIR_SIZE, HEIR_SIZE)
            if any(r[:14]):
                heirs.append({"slot": k, "family": k // 5, "name": text(r[:14]), "age": r[14], "value": u16(r, 15),
                              "unk17": r[17], "unk18": r[18], "face": u16(r, 19)})
        extra = []
        for k in range(count):
            r = self.image(sc, EXTRA8 + k * EXTRA8_SIZE, EXTRA8_SIZE)
            extra.append({"country": k, "age": r[0], "value": u16(r, 1), "unk3": r[3], "unk4": r[4], "unk5": r[5],
                          "face": u16(r, 6)})
        base = self.owner_pointer_base(sc)
        provinces = []
        for k in range(count):
            r = self.image(sc, PROVINCES + k * PROVINCE_SIZE, PROVINCE_SIZE)
            a = self.image(sc, ADJACENCY + k * ADJACENCY_SIZE, ADJACENCY_SIZE)
            p = {"id": k, "name": text(self.image(sc, TRIBES + k * TRIBE_SIZE, TRIBE_SIZE)),
                 "units": r[:20].hex(" "), "tail": r[0x46:0x51].hex(" "),
                 "owner": (u16(r, 0x51) - base) // RULER_SIZE,
                 "x": u16(a, 0), "y": u16(a, 2), "adj_unk4": a[4], "neighbors": [n for n in a[5:12] if n != 0xFF]}
            for off, key, _ in PROVINCE_FIELDS:
                p[key] = u16(r, off)
            provinces.append(p)
        return {"key": sc, "label": SCENARIOS[sc][1], "count": count, "year": u16(h, 2) + 1, "rulers": rulers,
                "generals": generals, "heirs": heirs, "extra": extra, "provinces": provinces}

    def women(self) -> list[dict]:
        out = []
        for k in range(WOMAN_COUNT):
            r = self.prg[WOMEN + k * WOMAN_SIZE:WOMEN + (k + 1) * WOMAN_SIZE]
            out.append({"id": k, "scenario": "mongol" if k < MONGOL_WOMEN else "world", "name": text(r[:13]),
                        "unk13": r[13], "portraits": [u16(r, 16 + 2 * i) for i in range(3)]})
        return out

    # ------------------------------------------------------------ portraits
    def portrait_offset(self, n: int) -> int:
        e = PORTRAIT_PTRS + 4 * n
        return self.prg[e] * 0x4000 + (u16(self.prg, e + 1) & 0x3FFF)

    def grid_pixels(self, tiles: dict[int, int]) -> bytes:
        """{cell index: tile PRG offset} on the 5x6 grid -> 40x48 colour indexes (255 = no tile)."""
        px = bytearray([255]) * (40 * 48)
        for cell, off in tiles.items():
            cx, cy = cell % FACE_W * 8, cell // FACE_W * 8
            for i, c in enumerate(tile_pixels(self.prg, off)):
                px[(cy + i // 8) * 40 + cx + i % 8] = c
        return bytes(px)

    def mob_part_offset(self, slot: int, index: int) -> int:
        return MOB_BANK + (u16(self.prg, MOB_PARTS[slot][2] + 2 * index) & 0x3FFF)

    def mob_part(self, cat: int, slot: int, choice: int) -> bytes:
        """One mob part as a 40x48 image, 255 outside its cells."""
        sid = MOB_PARTS[slot][0]
        off = self.mob_part_offset(slot, u16(self.prg, MOB_CAT_BASE + 2 * cat) + choice)
        return self.grid_pixels({cell: off + 16 * i for i, cell in enumerate(PART_CELLS[sid])})

    def face_indexes(self, code: int) -> bytes:
        """Face code -> 40x48 colour indexes 0-3."""
        if not code & 0x8000:
            base = self.portrait_offset(code)
            return self.grid_pixels({cell: base + 16 * cell for cell in range(30)})
        cat = (code >> 12) & 3
        px = bytearray(40 * 48)
        for slot, (_, _, _, shift) in enumerate(MOB_PARTS):
            part = self.mob_part(cat, slot, (code >> shift) & 7)
            for i, c in enumerate(part):
                if c != 255:
                    px[i] = c
        return bytes(px)

    def face_subpalette(self, code: int) -> int:
        return 0 if code & 0x8000 else self.prg[PORTRAIT_PTRS + 4 * code + 3] & 3

    def face_pixels(self, code: int) -> bytes:
        """Face code -> 40x48 NES colour numbers."""
        sub = self.face_subpalette(code)
        pal = self.prg[UI_PALETTE + 4 * sub:UI_PALETTE + 4 * sub + 4]
        return bytes(pal[c] if c else pal[0] for c in self.face_indexes(code))

    # ------------------------------------------------------------ maps
    def render_tiles(self, ids, w: int, sub, tile_off, pal: bytes) -> bytes:
        """Tile id grid (row-major, width w) + per-tile sub-palette -> NES colour numbers."""
        h = len(ids) // w
        px = bytearray(w * 8 * h * 8)
        for n, t in enumerate(ids):
            off = tile_off(t)
            pix = tile_pixels(self.prg, off) if off is not None else [0] * 64
            tx, ty = n % w, n // w
            for i, c in enumerate(pix):
                px[(ty * 8 + i // 8) * w * 8 + tx * 8 + i % 8] = pal[sub[n] * 4 + c] if c else pal[0]
        return bytes(px)

    def map_pixels(self, sc: str) -> tuple[int, int, bytes]:
        m = MAPS[sc]
        ids = self.prg[m["nt"]:m["nt"] + MAP_W * MAP_H]
        attr = self.prg[m["attr"]:m["attr"] + 64]
        sub = []
        for ty in range(MAP_Y, MAP_Y + MAP_H):
            for tx in range(MAP_X, MAP_X + MAP_W):
                a = attr[(ty // 4) * 8 + tx // 4]
                sub.append((a >> (((ty % 4) // 2) * 4 + ((tx % 4) // 2) * 2)) & 3)

        def tile_off(t: int):
            return m["tiles"] + (t - MAP_FIRST_TILE) * 16 if t >= MAP_FIRST_TILE else None

        pal = self.prg[m["pal"]:m["pal"] + 16]
        return MAP_W * 8, MAP_H * 8, self.render_tiles(ids, MAP_W, sub, tile_off, pal)

    def battle_cells(self, idx: int) -> bytes:
        o = BATTLE_MAPS + idx * BATTLE_W * BATTLE_H
        return self.prg[o:o + BATTLE_W * BATTLE_H]

    def battle_tilemap(self, idx: int) -> tuple[list[int], list[int]]:
        """64x42 tile ids (1 = blank where no cell covers) and their sub-palettes."""
        cells = self.battle_cells(idx)
        ids = [1] * (BATTLE_TW * BATTLE_TH)
        for r in range(BATTLE_H):
            for c in range(BATTLE_W):
                t = cells[r * BATTLE_W + c] & 0x7F
                blk = self.prg[BATTLE_BLOCKS + 16 * t:BATTLE_BLOCKS + 16 * t + 16]
                y0 = 4 * r + 2 * (c & 1)
                for j in range(4):
                    for i in range(4):
                        ids[(y0 + j) * BATTLE_TW + 4 * c + i] = blk[j * 4 + i]
        attr = self.prg[BATTLE_ATTRS + idx * 176:BATTLE_ATTRS + (idx + 1) * 176]
        sub = []
        for y in range(BATTLE_TH):
            ay = y if y < ATTR_SEAM else y + 2  # attribute rows 26-27 are a dummy gap (nametable wrap)
            for x in range(BATTLE_TW):
                a = attr[(x // 32) * 88 + (ay // 4) * 8 + (x % 32) // 4]
                sub.append((a >> (((ay % 4) // 2) * 4 + ((x % 4) // 2) * 2)) & 3)
        return ids, sub

    def battle_pixels(self, idx: int) -> tuple[int, int, bytes]:
        ids, sub = self.battle_tilemap(idx)

        def tile_off(t: int):
            return BATTLE_TILES + (t - BATTLE_FIRST_TILE) * 16 if t >= BATTLE_FIRST_TILE else None

        pal = self.prg[BATTLE_PALETTE:BATTLE_PALETTE + 16]
        return BATTLE_TW * 8, BATTLE_TH * 8, self.render_tiles(ids, BATTLE_TW, sub, tile_off, pal)

    def battle_index(self, sc: str, province: int) -> int:
        return province + (0 if sc == "mongol" else 14)
