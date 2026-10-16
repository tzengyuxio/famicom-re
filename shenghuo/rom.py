"""FC 聖火列傳 Sheng Huo Lie Zhuan (C&E, 1991, unlicensed) ROM decoding.

Mapper 240: 4 x 32 KB PRG banks, 16 x 8 KB CHR banks. PRG offsets below are offsets into the
128 KB PRG; CHR offsets into the 128 KB CHR-ROM. See shenghuo/docs/ROM_FORMAT.md.
"""
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Sheng Huo Lie Zhuan (Asia) (Unl).zip")

PRG_SIZE = 0x20000
CHR_SIZE = 0x20000
# ---------------------------------------------------------------- maps (bank 1 $8000 row/column builders, bank 3 attributes)
MAP_BANK = 1
MAP_COUNT = 24                 # map 0 = world; 1-20 entered from world cells; 21-23 later versions of map 1
MAP_POINTERS = 0x8671          # 24 x LE16 -> 240-byte screens (16 x 15 cells), stored column by column
MAP_HEIGHTS = 0x84D9           # 24 bytes: screens tall - 1
MAP_SCREENS = [54, 4, 2, 1, 2, 2, 2, 4, 2, 1, 1, 1, 1, 4, 1, 4, 4, 4, 1, 2, 1, 6, 6, 6]  # from pointer spacing
METATILES = 0x84F1             # 96 x [TL, TR, BL, BR] tile numbers (pattern table $0000 of CHR bank MAP_CHR)
TERRAIN = 0xF361               # 96 bytes: cell class (read at $844B -> $C8)
SCREEN_W, SCREEN_H = 16, 15
ATTR_BANK = 3
ATTR_POINTERS = 0x8230         # 24 x LE16 -> 64-byte attribute tables, one per screen (maps 21-23 share one set)
PALETTE_BANK = 0
MAP_PALETTE = 0xE797           # 32 bytes, BG + sprite palette of every map (uploaded at $8312)
MAP_CHR = 1                    # 8 KB CHR bank of all maps
DUNGEON_SCREENS = 0x88AC       # bank 0: 20 world screens; class-3 cell on screen [i] enters map i + 1 ($8896)
TOWN_SCREENS = 0x891E          # bank 0: 8 world screens (entry 0 unused); class-4 cell enters town i ($88ED)
TOWN_COUNT = 7
TERRAIN_CLASSES = {0: "通行", 1: "1", 2: "不可通行", 3: "地圖入口", 4: "城鎮入口", 5: "事件", 6: "下一層", 7: "上一層"}
# ---------------------------------------------------------------- text (bank 3 $AD98)
TEXT_BANK = 3
TEXT_GROUPS = 0xAE7F           # 20 x LE16 -> string groups; group = LE16 pointers to FF-terminated glyph-code strings
TEXT_GROUP_COUNT = 20
NAME_GROUP, NAME_CHR = 0, 0    # items 1-28, character names 29-41, skills 42-69, battle words 70-83 (font: CHR bank 0)
ENEMY_GROUP, ENEMY_CHR = 9, 9  # enemy names 1-60, battle messages 61-75 (font: CHR bank 9)
CHAR_NAME_BASE = 0x1D          # name string of character id = group 0 entry id + $1D (bank 0 $CB15)
ITEM_COUNT = 28                # group 0 entries 1-19 weapons, 20-28 consumables
SKILL_FIRST, SKILL_LAST = 0x2A, 0x45
# ---------------------------------------------------------------- characters (bank 0)
CHAR_COUNT = 13                # ids 0-12; id 4 = 少主 (the player)
HERO = 4
CHAPTER_STATS = [0x9077, 0x90D2, 0x912D, 0x9188, 0x91E3]  # per chapter ($7C): 7 x 13-byte tables (loader $C311)
CHAPTER_FIELDS = ["level", "力量", "敏捷", "HP", "maxHP", "MP", "maxMP"]
SKILL_OFFSETS = 0x924B         # 13 bytes: offset of each character's lists below
SKILL_LEVELS = 0x9258          # FF-terminated learn levels (status screen 武功 "Lnn")
SKILL_IDS = 0x9282             # FF-terminated group-0 string numbers, same offsets
# ---------------------------------------------------------------- portraits (bank 0)
SPRITE_RECORDS = 0xEAB3        # LE16 pointers; records 0x5B + id are portraits [w, h, sub-palette, 20 tiles]
PORTRAIT_BASE = 0x5B
PORTRAIT_COUNT = 36            # 0-12 party members, 13-35 other speakers (record $5B + 36 = 127 is a 5 x 9 sprite)
PORTRAIT_CHR = 0xC5E8          # per id: CHR bank of the dialogue portrait (pattern table $1000)
PORTRAIT_DIALOG_ATTR = 0xC547  # per id: 0 -> attribute $AA (sub-palette 2), else sub-palette 3
STATUS_PALETTE = 0xE737        # 32 bytes: 個人資料 screen
DIALOG_PALETTE = 0xE777        # 32 bytes: dialogue screen
# ---------------------------------------------------------------- battle (bank 2) and encounters (bank 0)
ENEMY_COUNT = 30
ENEMY_NAME = 0xB791            # bank 2: 30 bytes, enemy type -> group 9 string
ENEMY_STATS = 0xCF21           # bank 2: 5 x 30-byte tables (copied at $B986 to $0780/$0784/$0788/$078C/$0790)
ENEMY_FIELDS = ["stat0", "HP", "stat2", "stat3", "speed"]
ENCOUNTERS = 0xD308            # bank 0: 10 x 4 pairs (enemy types of the two enemy groups), row = min(level, 10) - 1
ITEM_BATTLE_PARAM = 0xABA3     # bank 2: 28 bytes, item 1-28 -> $07BB before the hit check $BEE3 (meaning unknown)

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


class Rom:
    def __init__(self, path: str = DEFAULT_ROM):
        self.data = read_rom(path)
        self.prg = self.data[0x10:0x10 + PRG_SIZE]
        self.chr = self.data[0x10 + PRG_SIZE:0x10 + PRG_SIZE + CHR_SIZE]

    def cpu(self, bank: int, addr: int) -> int:
        """PRG offset of CPU address addr ($8000-$FFFF) with 32 KB bank `bank` mapped."""
        return bank * 0x8000 + addr - 0x8000

    def byte(self, bank: int, addr: int) -> int:
        return self.prg[self.cpu(bank, addr)]

    def bytes(self, bank: int, addr: int, n: int) -> bytes:
        o = self.cpu(bank, addr)
        return self.prg[o:o + n]

    def word(self, bank: int, addr: int) -> int:
        o = self.cpu(bank, addr)
        return self.prg[o] | self.prg[o + 1] << 8

    # ------------------------------------------------------------ CHR
    def tile(self, chr_bank: int, half: int, index: int) -> list[list[int]]:
        """8x8 2-bit pixels of tile `index` in pattern table `half` (0 = $0000, 1 = $1000) of an 8 KB CHR bank."""
        o = chr_bank * 0x2000 + half * 0x1000 + index * 16
        lo, hi = self.chr[o:o + 8], self.chr[o + 8:o + 16]
        return [[((lo[y] >> (7 - x)) & 1) | (((hi[y] >> (7 - x)) & 1) << 1) for x in range(8)] for y in range(8)]

    # ------------------------------------------------------------ maps
    def map_size(self, m: int) -> tuple[int, int]:
        """(screens wide, screens tall) of map m."""
        h = self.byte(MAP_BANK, MAP_HEIGHTS + m) + 1
        return MAP_SCREENS[m] // h, h

    def map_cells(self, m: int) -> list[list[int]]:
        """Metatile numbers of map m, rows of (16 x screens wide) cells. Screens are stored column by column."""
        w, h = self.map_size(m)
        base = self.cpu(MAP_BANK, self.word(MAP_BANK, MAP_POINTERS + 2 * m))
        rows = [[0] * (w * SCREEN_W) for _ in range(h * SCREEN_H)]
        for s in range(w * h):
            sx, sy = divmod(s, h)
            for r in range(SCREEN_H):
                for c in range(SCREEN_W):
                    rows[sy * SCREEN_H + r][sx * SCREEN_W + c] = self.prg[base + s * 240 + r * SCREEN_W + c]
        return rows

    def map_palettes(self, m: int) -> list[list[int]]:
        """BG sub-palette (0-3) of every cell of map m, from the per-screen attribute tables (64 bytes each)."""
        w, h = self.map_size(m)
        base = self.cpu(ATTR_BANK, self.word(ATTR_BANK, ATTR_POINTERS + 2 * m))
        rows = [[0] * (w * SCREEN_W) for _ in range(h * SCREEN_H)]
        for s in range(w * h):
            sx, sy = divmod(s, h)
            for r in range(SCREEN_H):
                for c in range(SCREEN_W):
                    a = self.prg[base + s * 64 + (r // 2) * 8 + c // 2]
                    rows[sy * SCREEN_H + r][sx * SCREEN_W + c] = (a >> (((r & 1) << 2) | ((c & 1) << 1))) & 3
        return rows

    def metatile(self, v: int) -> bytes:
        """[top-left, top-right, bottom-left, bottom-right] BG tiles of metatile v."""
        return self.bytes(MAP_BANK, METATILES + 4 * v, 4)

    def terrain(self, v: int) -> int:
        return self.byte(MAP_BANK, TERRAIN + v)

    def map_pixels(self, m: int) -> tuple[int, int, list[int]]:
        """Map m as NES colour numbers, 16 px per cell."""
        cells, pals = self.map_cells(m), self.map_palettes(m)
        pal = self.bytes(PALETTE_BANK, MAP_PALETTE, 16)
        h, w = len(cells) * 16, len(cells[0]) * 16
        px = [0] * (w * h)
        cache = {}
        for y, row in enumerate(cells):
            for x, v in enumerate(row):
                key = (v, pals[y][x])
                if key not in cache:
                    block = []
                    for k, t in enumerate(self.metatile(v)):
                        block.append((k, self.tile(MAP_CHR, 0, t)))
                    cache[key] = block
                for k, t in cache[key]:
                    ox, oy = x * 16 + (k & 1) * 8, y * 16 + (k >> 1) * 8
                    sub = pals[y][x] * 4
                    for j in range(8):
                        for i in range(8):
                            c = t[j][i]
                            px[(oy + j) * w + ox + i] = pal[sub + c] if c else pal[0]
        return w, h, px

    # ------------------------------------------------------------ text
    def strings(self, g: int) -> list[bytes]:
        """Glyph-code strings of text group g. Entry 0 is a one-byte header (not text)."""
        t = self.word(TEXT_BANK, TEXT_GROUPS + 2 * g)
        out = []
        for i in range((self.word(TEXT_BANK, t) - t) // 2):
            a = o = self.cpu(TEXT_BANK, self.word(TEXT_BANK, t + 2 * i))
            while self.prg[o] != 0xFF:
                o += 1
            out.append(self.prg[a:o])
        return out

    def glyph(self, chr_bank: int, code: int) -> list[list[int]]:
        """16x16 1-bit glyph: cell code & $3F = tiles 4n..4n+3 of pattern table $0000, plane = bit 7."""
        cell, plane = code & 0x3F, code >> 7
        rows = [[0] * 16 for _ in range(16)]
        for k in range(4):
            t = self.tile(chr_bank, 0, cell * 4 + k)
            for y in range(8):
                for x in range(8):
                    rows[(k >> 1) * 8 + y][(k & 1) * 8 + x] = (t[y][x] >> plane) & 1
        return rows

    # ------------------------------------------------------------ portraits
    def portrait_record(self, pid: int) -> bytes:
        p = self.cpu(0, self.word(0, SPRITE_RECORDS + 2 * (PORTRAIT_BASE + pid)))
        return self.prg[p:p + 23]

    def portrait_chr(self, pid: int) -> int:
        return self.byte(0, PORTRAIT_CHR + pid)

    def portrait(self, pid: int, screen: str = "dialog") -> tuple[int, int, list[int]]:
        """32x40 portrait as NES colours. screen 'dialog' (any id, $C4CE) or 'status' (party 0-12, $D1A5).

        Both screens use record bytes 3-22 as 4 x 5 tiles row by row. The status screen draws them as
        sprites (CHR bank 0, sprite sub-palette = record byte 2), the dialogue screen as background
        tiles (CHR bank PORTRAIT_CHR[id], sub-palette from PORTRAIT_DIALOG_ATTR)."""
        rec = self.portrait_record(pid)
        if screen == "status":
            pal, sub, chrb = self.bytes(0, STATUS_PALETTE + 16, 16), rec[2], 0
        else:
            pal, chrb = self.bytes(0, DIALOG_PALETTE, 16), self.portrait_chr(pid)
            sub = 2 if self.byte(0, PORTRAIT_DIALOG_ATTR + pid) == 0 else 3
        px = [0] * (32 * 40)
        for i, t in enumerate(rec[3:23]):
            tile = self.tile(chrb, 1, t)
            ox, oy = (i % 4) * 8, (i // 4) * 8
            for y in range(8):
                for x in range(8):
                    c = tile[y][x]
                    px[(oy + y) * 32 + ox + x] = pal[sub * 4 + c] if c else pal[0]
        return 32, 40, px

    # ------------------------------------------------------------ characters / battle tables
    def chapter_stats(self, chapter: int) -> list[dict]:
        """Stats each character gets when chapter (1-5) starts; None for the player (keeps his own)."""
        base = CHAPTER_STATS[chapter - 1]
        out = []
        for c in range(CHAR_COUNT):
            out.append(None if c == HERO else
                       {f: self.byte(0, base + 13 * k + c) for k, f in enumerate(CHAPTER_FIELDS)})
        return out

    def _ff_list(self, addr: int) -> list[int]:
        out = []
        while (v := self.byte(0, addr)) != 0xFF:
            out.append(v)
            addr += 1
        return out

    def skills(self, cid: int) -> list[tuple[int, int]]:
        """(group-0 string of the skill, learn level) of character cid."""
        o = self.byte(0, SKILL_OFFSETS + cid)
        return list(zip(self._ff_list(SKILL_IDS + o), self._ff_list(SKILL_LEVELS + o)))

    def enemy(self, t: int) -> dict:
        d = {"name_string": self.byte(2, ENEMY_NAME + t)}
        for k, f in enumerate(ENEMY_FIELDS):
            d[f] = self.byte(2, ENEMY_STATS + ENEMY_COUNT * k + t)
        return d

    def encounters(self) -> list[list[tuple[int, int]]]:
        """Per level 1-10: 4 possible (left group, right group) enemy-type pairs ($D2C4)."""
        return [[tuple(self.bytes(0, ENCOUNTERS + 8 * lv + 2 * k, 2)) for k in range(4)] for lv in range(10)]

    def entrances(self) -> list[dict]:
        """World-map cells that lead somewhere: class-3 cells (dungeon / area maps) and class-4 cells (towns)."""
        cells = self.map_cells(0)
        _, h = self.map_size(0)
        dungeon = self.bytes(0, DUNGEON_SCREENS, MAP_COUNT - 4)
        town = self.bytes(0, TOWN_SCREENS, TOWN_COUNT + 1)
        out = []
        for y, row in enumerate(cells):
            for x, v in enumerate(row):
                screen = (x // SCREEN_W) * h + y // SCREEN_H
                kind = self.terrain(v)
                if kind == 3:
                    out.append({"x": x, "y": y, "screen": screen, "kind": "map", "target": dungeon.index(screen) + 1})
                elif kind == 4:
                    out.append({"x": x, "y": y, "screen": screen, "kind": "town", "target": town.index(screen, 1)})
        return out
