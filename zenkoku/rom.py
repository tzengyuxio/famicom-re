"""FC 信長の野望・全国版 (KOEI, 1988) ROM decoding.

All offsets are PRG offsets (file offset - 0x10). See zenkoku/docs/ROM_FORMAT.md.
"""
import os
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Nobunaga no Yabou - Zenkoku Ban (Japan).zip")

# ---------------------------------------------------------------- scenario images (bank 3, copied to WRAM $6000)
# mode -> (PRG base, province count, label, adjacency table)
MODES = {50: (0xC003, 50, "50かこく", 0x10004), 17: (0xE003, 17, "17かこく", 0x10300)}
WRAM = 0x6000
OWNERS = 0x6E15                     # province -> owning daimyo
PROVINCES, PROVINCE_SIZE = 0x7001, 26  # 13 u16
DAIMYO, DAIMYO_SIZE = 0x752F, 7     # age, then the 5 stats, then 0
DAIMYO_NAMES, NAME_SIZE = 0x77A8, 9
PROVINCE_NAMES, PROVINCE_NAME_SIZE = 0x7985, 10
REGIONS = 0x7B79                    # region number 1-7 per province
EXTRA_DAIMYO = 3                    # 50-mode name slots 50-52 (アケチ, ハシバ, シバタ): no province at start
ADJ_SIZE = 8                        # neighbours, FF-terminated, zero-padded
START_YEAR = 1560
# Province record fields in order: (column, screen label); the last one is not shown on screen
PROVINCE_FIELDS = [("Gold", "きん"), ("Debt", "しゃっきん"), ("Town", "まち"), ("Rice", "ひょうろう"),
                   ("Kokudaka", "こくだか"), ("Flood", "ちすいど"), ("Loyalty", "たみちゅう"),
                   ("Wealth", "たみざい"), ("Soldiers", "へいりょく"), ("Soldier_Loyalty", "へいちゅう"),
                   ("Training", "くんれんど"), ("Arms", "ぶそうど"), ("Unk24", "")]
STATS = [("Health", "けんこう"), ("Ambition", "やしん"), ("Luck", "うん"), ("Charm", "みりょく"), ("IQ", "ちのう")]
# 17-mode daimyo k = 50-mode daimyo (and face) MODE17_DAIMYO[k]
MODE17_DAIMYO = 0x3F6CB

# ---------------------------------------------------------------- portraits
FACE_W = FACE_H = 6                 # tiles
PORTRAIT_COUNT, DAIMYO_FACES = 75, 53  # 0-52 daimyo (50-mode id), 53-74 princesses
PORTRAIT_PTRS = 0x23BD0             # 75 x [bank][tile count][ptr lo][ptr hi] ($8000-based)
PORTRAIT_LAYOUT = 0x23144           # 75 x 36 tile ids; id - FACE_FIRST_TILE = tile index in the face's data
FACE_FIRST_TILE = 0x5B
FACE_PALETTE = bytes([0x3E, 0x38, 0x28, 0x30])  # BG sub-palette 0 of the screens that show faces

# ---------------------------------------------------------------- regional maps (bank 4)
MAP_W, MAP_H, MAP_X, MAP_Y = 28, 16, 2, 4  # tiles, drawn at screen tile (2, 4)
MAP_TILES, MAP_FIRST_TILE, MAP_TILE_COUNT = 0x103BC, 0x51, 154  # CHR $1510
MAP_PALETTE = 0xB522
# mode -> (nametables 448 B each, attributes 32 B each = nametable attribute rows 1-4, labels 34 B each, views)
MAP_VIEWS = {50: (0x110DC, 0x11D5C, 0x11E80, 7), 17: (0x10D5C, 0x11D1C, 0x11E3C, 2)}

# ---------------------------------------------------------------- battle maps
BATTLE_MAPS, BATTLE_W, BATTLE_H = 0x1256E, 11, 5  # 50 x 55 bytes (row-major), one per 50-mode province
BATTLE_COUNT = 50
BATTLE_ATTRS, BATTLE_VIEW_COLS = 0x14004, (0, 3, 6)  # 50 x 3 views x 48 B (attribute rows 1-6)
BATTLE_TILES, BATTLE_FIRST_TILE, BATTLE_TILE_COUNT = 0x11F6E, 0x57, 96  # CHR $1570
BATTLE_PALETTE = 0xB426
BATTLE_VIEW_X, BATTLE_VIEW_Y, BATTLE_VIEW_W = 10, 4, 5  # screen tile of view cell (0, 0); 5 columns shown
# terrain byte -> (tag, name, sub-palette); the sub-palette also equals the stored attribute views
TERRAIN = {0x02: ("none", "場外", 0), 0x04: ("plain", "平地", 2), 0x08: ("town", "町", 2), 0x10: ("forest", "林", 1),
           0x20: ("castle", "城", 3), 0x40: ("water", "川・海", 3), 0x80: ("mountain", "山", 1)}
# bank 2 $B05C: 16 tile ids (4x4, row-major) per block, in this terrain order; terrain 02 is left blank
BATTLE_BLOCKS, BLOCK_ORDER = 0xB05C, [0x20, 0x10, 0x08, 0x80, 0x04, 0x40]
BLANK_TILE = 0x01

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
    """Half-width katakana up to the first 0, as full-width katakana."""
    return unicodedata.normalize("NFKC", b.split(b"\0")[0].decode("cp932"))


def to_hiragana(s: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in s)


def tile_pixels(data: bytes, off: int) -> list[int]:
    """One 2bpp NES tile -> 64 colour indexes."""
    return [((data[off + y] >> (7 - x)) & 1) | (((data[off + 8 + y] >> (7 - x)) & 1) << 1)
            for y in range(8) for x in range(8)]


def attr_sub(attr: bytes, x: int, y: int, row0: int = 0) -> int:
    """Sub-palette of screen tile (x, y) from attribute bytes that start at attribute row row0."""
    a = attr[(y // 4 - row0) * 8 + x // 4]
    return (a >> (((y % 4) // 2) * 4 + ((x % 4) // 2) * 2)) & 3


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
    def image(self, mode: int, addr: int, size: int) -> bytes:
        o = MODES[mode][0] + addr - WRAM
        return self.prg[o:o + size]

    def global_daimyo(self, mode: int, k: int) -> int:
        """50-mode daimyo id (= portrait) of daimyo k of a mode."""
        return k if mode == 50 else self.prg[MODE17_DAIMYO + k]

    def neighbours(self, mode: int, p: int) -> list[int]:
        o = MODES[mode][3] + ADJ_SIZE * p
        r = self.prg[o:o + ADJ_SIZE]
        return list(r[:r.index(0xFF)])

    def scenario(self, mode: int) -> dict:
        n = MODES[mode][1]
        names = [text(self.image(mode, DAIMYO_NAMES + NAME_SIZE * k, NAME_SIZE))
                 for k in range(n + (EXTRA_DAIMYO if mode == 50 else 0))]
        daimyo = []
        for k, name in enumerate(names):
            r = self.image(mode, DAIMYO + DAIMYO_SIZE * k, DAIMYO_SIZE)
            daimyo.append({"id": k, "name": name, "age": r[0], "stats": list(r[1:6]), "unk6": r[6],
                           "face": self.global_daimyo(mode, k) if k < n else k})
        owners = self.image(mode, OWNERS, n)
        regions = self.image(mode, REGIONS, n)
        provinces = []
        for p in range(n):
            r = self.image(mode, PROVINCES + PROVINCE_SIZE * p, PROVINCE_SIZE)
            prov = {"id": p, "name": text(self.image(mode, PROVINCE_NAMES + PROVINCE_NAME_SIZE * p,
                                                     PROVINCE_NAME_SIZE)),
                    "owner": owners[p], "region": regions[p], "neighbours": self.neighbours(mode, p),
                    "battle_map": self.global_daimyo(mode, p)}
            for i, (key, _) in enumerate(PROVINCE_FIELDS):
                prov[key] = u16(r, 2 * i)
            provinces.append(prov)
        return {"mode": mode, "label": MODES[mode][2], "daimyo": daimyo, "provinces": provinces}

    # ------------------------------------------------------------ portraits
    def portrait_tiles(self, n: int) -> list[int]:
        """PRG offsets of the 36 tiles of portrait n, row-major."""
        e = self.prg[PORTRAIT_PTRS + 4 * n:PORTRAIT_PTRS + 4 * n + 4]
        base, count = e[0] * 0x4000 + (u16(e, 2) - 0x8000), e[1]
        ids = self.prg[PORTRAIT_LAYOUT + 36 * n:PORTRAIT_LAYOUT + 36 * n + 36]
        assert all(0 <= t - FACE_FIRST_TILE < count for t in ids), n
        return [base + 16 * (t - FACE_FIRST_TILE) for t in ids]

    def face_pixels(self, n: int) -> bytes:
        """Portrait n -> 48x48 NES colour numbers."""
        px = bytearray(48 * 48)
        for cell, off in enumerate(self.portrait_tiles(n)):
            cx, cy = cell % FACE_W * 8, cell // FACE_W * 8
            for i, c in enumerate(tile_pixels(self.prg, off)):
                px[(cy + i // 8) * 48 + cx + i % 8] = FACE_PALETTE[c]
        return bytes(px)

    # ------------------------------------------------------------ tile rendering
    def render(self, ids, w: int, subs, tile_off, pal: bytes) -> bytes:
        """Tile id grid (row-major, width w) + per-tile sub-palette -> NES colour numbers."""
        h = len(ids) // w
        px = bytearray(w * 8 * h * 8)
        for n, t in enumerate(ids):
            off = tile_off(t)
            pix = tile_pixels(self.prg, off) if off is not None else [0] * 64
            tx, ty = n % w, n // w
            for i, c in enumerate(pix):
                px[(ty * 8 + i // 8) * w * 8 + tx * 8 + i % 8] = pal[subs[n] * 4 + c] if c else pal[0]
        return bytes(px)

    # ------------------------------------------------------------ regional maps
    def map_view(self, mode: int, v: int) -> tuple[bytes, bytes]:
        """(28x16 tile ids, 32 attribute bytes) of regional map v."""
        nt, at, _, _ = MAP_VIEWS[mode]
        return self.prg[nt + 448 * v:nt + 448 * (v + 1)], self.prg[at + 32 * v:at + 32 * (v + 1)]

    def map_labels(self, mode: int, v: int) -> list[tuple[int, int, int]]:
        """(province, screen tile x, y) of the name labels the game prints on map v."""
        o = MAP_VIEWS[mode][2] + 34 * v
        out = []
        while self.prg[o] != 0xFF:
            x, y, p = self.prg[o:o + 3]
            out.append((p, x, y))
            o += 3
        return out

    def map_pixels(self, mode: int, v: int) -> tuple[int, int, bytes]:
        ids, attr = self.map_view(mode, v)
        subs = [attr_sub(attr, MAP_X + i % MAP_W, MAP_Y + i // MAP_W, 1) for i in range(MAP_W * MAP_H)]

        def off(t: int):
            return MAP_TILES + (t - MAP_FIRST_TILE) * 16 if t >= MAP_FIRST_TILE else None

        pal = self.prg[MAP_PALETTE:MAP_PALETTE + 16]
        return MAP_W * 8, MAP_H * 8, self.render(ids, MAP_W, subs, off, pal)

    # ------------------------------------------------------------ battle maps
    def battle_cells(self, idx: int) -> bytes:
        o = BATTLE_MAPS + idx * BATTLE_W * BATTLE_H
        return self.prg[o:o + BATTLE_W * BATTLE_H]

    def battle_attrs(self, idx: int, view: int) -> bytes:
        o = BATTLE_ATTRS + 144 * idx + 48 * view
        return self.prg[o:o + 48]

    def battle_block(self, v: int) -> bytes:
        if v not in BLOCK_ORDER:
            return bytes([BLANK_TILE]) * 16
        o = BATTLE_BLOCKS + 16 * BLOCK_ORDER.index(v)
        return self.prg[o:o + 16]

    def battle_tilemap(self, idx: int, col0: int = 0, cols: int = BATTLE_W,
                       cells: bytes | None = None) -> tuple[list[int], list[int]]:
        """Tile ids and sub-palettes of columns col0.. of a map (or of the given 11x5 cells), 4 tiles per
        column, 4 x 5 + 2 rows (odd map columns sit 2 tiles lower). Terrain 02 stays blank (sub-palette 0)."""
        cells = self.battle_cells(idx) if cells is None else cells
        tw, th = 4 * cols, 4 * BATTLE_H + 2
        ids, subs = [BLANK_TILE] * (tw * th), [0] * (tw * th)
        for r in range(BATTLE_H):
            for c in range(col0, col0 + cols):
                v = cells[r * BATTLE_W + c]
                sub = TERRAIN[v][2]
                block = self.battle_block(v)
                y0, x0 = 4 * r + 2 * (c & 1), 4 * (c - col0)
                for j in range(4):
                    for i in range(4):
                        ids[(y0 + j) * tw + x0 + i] = block[j * 4 + i]
                        subs[(y0 + j) * tw + x0 + i] = sub
        return ids, subs

    def battle_pixels(self, idx: int) -> tuple[int, int, bytes]:
        ids, subs = self.battle_tilemap(idx)

        def off(t: int):
            return BATTLE_TILES + (t - BATTLE_FIRST_TILE) * 16 if t >= BATTLE_FIRST_TILE else None

        pal = self.prg[BATTLE_PALETTE:BATTLE_PALETTE + 16]
        tw = 4 * BATTLE_W
        return tw * 8, (4 * BATTLE_H + 2) * 8, self.render(ids, tw, subs, off, pal)
