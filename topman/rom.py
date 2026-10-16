"""FC ファミコントップマネジメント (KOEI, 1990) ROM decoding.

All offsets are PRG offsets (file offset - 0x10). See topman/docs/ROM_FORMAT.md.
"""
import os
import unicodedata
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROM = os.path.join(os.path.dirname(HERE), "roms", "Famicom Top Management (Japan).zip")

# New-game WRAM image: bank 11 $B800 is copied to WRAM $6000 (0x7F0 bytes up to the global block)
IMAGE, WRAM_BASE, IMAGE_SIZE = 0x2F800, 0x6000, 0x810
COMPANIES, COMPANY_SIZE, COMPANY_COUNT = 0x65FD, 0x62, 5
PRODUCTS = ["ホビー", "ブック", "スーパー"]  # bank 2 $BA9E table; hobby PC / notebook / super computer
DEPARTMENTS = ["そうむ", "かいはつ", "せいぞう", "えいぎょう"]
MEDIA = ["ざっし", "しんぶん", "テレビ"]
START_YEAR, START_MONTH = 1995, 4

# Demand curves: 3 products x 5 curves x 35 yearly values (u16, x40 units), bank 9 $B6E4.
# New game: curve[p] = pool[p * 5 + random(5)] copied to WRAM $601F + p * 70 (p-code PRG 0xA79).
DEMAND_POOL, DEMAND_CURVES, DEMAND_YEARS, DEMAND_FIRST_YEAR, DEMAND_SCALE = 0x276E4, 5, 35, 1990, 40
DEMAND_WRAM = 0x601F
# Advertising cost curves: 3 media x 5 curves x 12 monthly values (u16), bank 6 $A749.
# New game: medium m gets pool[m * 5 + random(5)] at WRAM $60FD + m * 24 (p-code PRG 0xAB0).
AD_POOL, AD_CURVES, AD_MONTHS = 0x1A749, 5, 12
AD_WRAM = 0x60FD

# BG palettes of the department screens: 11 x 16 bytes, bank 1 $B96C
DEPT_PALETTES, DEPT_PALETTE_COUNT = 0x796C, 11
MEETING_PALETTE = 0xE73D  # bank 3 $A73D, the 年初 meeting-room screen

# Picture descriptor tables: (bank, CPU address, count). Each entry is 3 u16 pointers in the same bank:
# tile data, palette map (one byte 0-3 per 2x2 tiles), tile map (tile ids, first tile = lowest id).
PICTURE_TABLES = [
    (3, 0xBB22, 1, "meeting"),     # 年初 meeting room, 32x16
    (7, 0xA4A4, 4, "season"),      # monthly main screen, 総務 man with spring/summer/autumn/winter props, 16x30
    (8, 0xB5F4, 8, "staff"),       # department screens (which one a department shows differs per game), 16x30
    (6, 0x986B, 5, "logo"),        # entry 0 = KOEI logo
    (6, 0x914C, 3, "title"),       # entry 0 = title screen
    (6, 0xB584, 4, "pic6a"),
    (6, 0xBD54, 3, "pic6b"),
    (7, 0xB686, 3, "pic7"),        # entry 0 = ranking podium
    (7, 0xACC2, 5, "anim7a"),      # company logos NEG/PUJITSU/TOCHIBA/CHARP/IBN
    (7, 0xAD58, 5, "anim7b"),      # company logos, second frame
    (9, 0xB654, 24, "news"),       # テレビよこはま news pictures, 8x8
]
NEWS_PALETTE = 0x13266  # bank 4 $B266, the news screen
# Palette (PRG offset of 16 BG colours) per (tag, index); each staff picture keeps its own palette whatever department
# shows it. All but PALETTE_GUESSED were matched pixel for pixel with the emulator screen (verify.py)
PICTURE_PALETTES = {("meeting", 0): MEETING_PALETTE, **{("season", i): DEPT_PALETTES + 16 * i for i in range(4)},
                    **{("staff", i): DEPT_PALETTES + 16 * n for i, n in {0: 4, 3: 7, 4: 8, 5: 9, 6: 10}.items()},
                    ("staff", 1): DEPT_PALETTES + 16 * 5,
                    # not seen on screen yet: palette 6 is the only department palette left (guess)
                    ("staff", 2): DEPT_PALETTES + 16 * 6,
                    ("staff", 7): DEPT_PALETTES + 16 * 4,
                    **{("news", i): NEWS_PALETTE for i in range(24)}}
# season 1-3 follow the month (palettes 1-3 sit between spring and the department palettes); only spring was
# reached in the emulator. News: picture 18 matched on screen (one news screen); the others share the screen palette
PALETTE_GUESSED = {("staff", 2), ("staff", 7), ("season", 1), ("season", 2), ("season", 3)}

# Text: JIS X0201 kana are shown as hiragana; katakana use the game's own codes (font in bank 6)
KATAKANA = dict(zip(range(0x41, 0x7B), "ナフアイウエケシ今セ位?月チテハトャ昨ニヌノマス年ム?????　フックメモユラホルレタロミNッPキェSィョヒ?コYサ"))
KATAKANA.update({0xA7: "ホ", 0xA8: "ヒ", 0xA9: "ス", 0xAA: "ン", 0xAB: "ハ", 0x2D: "ー"})

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
    """Game text up to NUL: hiragana for JIS X0201 kana, katakana/kanji for the game's own codes."""
    out = []
    for c in b:
        if c == 0:
            break
        if out and out[-1][0] == "%" and out[-1][-1] not in "ds":  # printf specifiers stay ASCII (%s, %4d, %6ld)
            out[-1] += chr(c)
        elif c in KATAKANA:
            out.append(KATAKANA[c])
        elif c == 0x0A:
            out.append("\n")
        else:
            s = unicodedata.normalize("NFKC", bytes([c]).decode("cp932", "replace"))
            out.append("".join(chr(ord(ch) - 0x60) if "ァ" <= ch <= "ヶ" else ch for ch in s))
    return "".join(out)


def join_marks(s: str) -> str:
    """Fold the separate dakuten/handakuten into the preceding kana (シ゛ -> ジ)."""
    return unicodedata.normalize("NFC", s.replace("゛", "゙").replace("゜", "゚"))


def tile_pixels(data: bytes, off: int) -> list[int]:
    """One 2bpp NES tile -> 64 colour indexes."""
    return [((data[off + y] >> (7 - x)) & 1) | (((data[off + 8 + y] >> (7 - x)) & 1) << 1)
            for y in range(8) for x in range(8)]


def u16(b: bytes, o: int) -> int:
    return b[o] | b[o + 1] << 8


def u32(b: bytes, o: int) -> int:
    return u16(b, o) | u16(b, o + 2) << 16


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

    @staticmethod
    def cpu_to_prg(bank: int, addr: int) -> int:
        return bank * 0x4000 + addr - 0x8000

    # ------------------------------------------------------------ new-game image
    def image(self, addr: int, size: int) -> bytes:
        o = IMAGE + addr - WRAM_BASE
        return self.prg[o:o + size]

    def words(self, addr: int, n: int) -> list[int]:
        b = self.image(addr, 2 * n)
        return [u16(b, 2 * i) for i in range(n)]

    def companies(self) -> list[dict]:
        """The 5 companies of the new-game image (company 0 is renamed to the player's name)."""
        out = []
        for k in range(COMPANY_COUNT):
            base = COMPANIES + k * COMPANY_SIZE
            r = self.image(base, COMPANY_SIZE)
            staff, dev, prod, sales = [u16(r, 0x4A + 2 * i) for i in range(4)]
            extra = u16(r, 0x5E)
            a, b, c, d = (self.words(staff, 17), self.words(dev, 12), self.words(prod, 20), self.words(sales, 16))
            out.append({
                "id": k, "name": text(r[0x38:0x40]), "president": text(r[0x40:0x48]), "index": u16(r, 0x48),
                "ranks": [u16(r, 0x0C + 2 * i) for i in range(5)], "cash": u32(r, 0x16), "cash2": u32(r, 0x1A),
                "ai": u16(r, 0x20), "ai2": u16(r, 0x22), "unk58": [u16(r, 0x58 + 2 * i) for i in range(3)],
                "sales_staff": a[0:3], "dev_staff": a[3:6], "prod_staff": a[6:9], "general_staff": a[9],
                "salary": a[10], "bonus": a[11], "staff_unk": a[12:14], "ability": a[14], "ability2": a[15],
                "moral": a[16],
                "dev_unk0": b[0:3], "dev_unk3": b[3:9], "performance": b[9:12],
                "prod_unk0": c[0:3], "lines": c[3], "product_lines": c[4:7], "prod_unk7": c[7:10],
                "prod_unk10": c[10:13], "line_staff": c[13:16], "stock": c[16:19], "productivity": c[19],
                "price": d[0:3], "brand": d[3], "sales_unk4": d[4:10], "quota": d[10:13], "sales_unk13": d[13:16],
                "extra": self.image(extra, 0x6E).hex(" "),
                "ptrs": {"staff": staff, "dev": dev, "prod": prod, "sales": sales, "extra": extra},
            })
        return out

    # ------------------------------------------------------------ curves
    def demand_curve(self, product: int, curve: int) -> list[int]:
        o = DEMAND_POOL + (product * DEMAND_CURVES + curve) * DEMAND_YEARS * 2
        return [u16(self.prg, o + 2 * i) for i in range(DEMAND_YEARS)]

    def ad_curve(self, medium: int, curve: int) -> list[int]:
        o = AD_POOL + (medium * AD_CURVES + curve) * AD_MONTHS * 2
        return [u16(self.prg, o + 2 * i) for i in range(AD_MONTHS)]

    # ------------------------------------------------------------ pictures
    def palette(self, n: int) -> bytes:
        return self.prg[DEPT_PALETTES + 16 * n:DEPT_PALETTES + 16 * n + 16]

    def pictures(self) -> list[dict]:
        """Every descriptor of PICTURE_TABLES with its data ranges (sizes from the next pointer)."""
        out = []
        for bank, addr, count, tag in PICTURE_TABLES:
            for i in range(count):
                o = self.cpu_to_prg(bank, addr + 6 * i)
                t, a, n = (u16(self.prg, o + 2 * j) for j in range(3))
                out.append({"tag": tag, "index": i, "bank": bank, "desc": addr + 6 * i, "tiles": t, "attr": a,
                            "map": n})
        # sizes: a block ends where the next block of the same kind (or the table) starts
        for p in out:
            for key in ("tiles", "attr", "map"):
                starts = sorted({q[k] for q in out if q["bank"] == p["bank"] for k in ("tiles", "attr", "map")}
                                | {q["desc"] for q in out if q["bank"] == p["bank"]})
                nxt = [s for s in starts if s > p[key]]
                p[key + "_size"] = (nxt[0] if nxt else 0xC000) - p[key]
        return out

    def picture_map(self, p: dict, width: int) -> tuple[list[int], list[int]]:
        """Tile ids and per-tile palette indexes for a picture drawn `width` tiles wide."""
        ids = self.prg[self.cpu_to_prg(p["bank"], p["map"]):][:p["map_size"]]
        h = len(ids) // width
        ids = list(ids[:width * h])
        attr = self.prg[self.cpu_to_prg(p["bank"], p["attr"]):]
        aw = (width + 1) // 2
        sub = [attr[(y // 2) * aw + x // 2] & 3 for y in range(h) for x in range(width)]
        return ids, sub

    def picture_pixels(self, p: dict, width: int, pal: bytes) -> tuple[int, int, bytes]:
        ids, sub = self.picture_map(p, width)
        h = len(ids) // width
        first = min(ids)
        tiles = self.cpu_to_prg(p["bank"], p["tiles"])
        px = bytearray(width * 8 * h * 8)
        for k, t in enumerate(ids):
            pix = tile_pixels(self.prg, tiles + (t - first) * 16)
            tx, ty = k % width, k // width
            for i, c in enumerate(pix):
                px[(ty * 8 + i // 8) * width * 8 + tx * 8 + i % 8] = pal[sub[k] * 4 + c] if c else pal[0]
        return width * 8, h * 8, bytes(px)

    def picture_width(self, p: dict) -> int:
        """Pick the drawing width: palette-map size must fit, then the smoothest row seams win."""
        n, a = p["map_size"], p["attr_size"]
        best = None
        for w in range(2, 33):
            if n % w or n // w > 30:
                continue
            h = n // w
            if ((w + 1) // 2) * ((h + 1) // 2) > a:
                continue
            _, _, px = self.picture_pixels(p, w, bytes(range(16)))
            W = w * 8
            cost = sum(px[y * W + x] != px[(y - 1) * W + x] for y in range(8, h * 8, 8) for x in range(W)) / max(1, h - 1) / W
            if best is None or cost < best[0]:
                best = (cost, w)
        return best[1] if best else n

    # ------------------------------------------------------------ strings
    def strings(self, banks=range(16), min_len: int = 4) -> list[tuple[int, str]]:
        """NUL-delimited runs that decode to mostly kana (message text), with PRG offsets."""
        out = []
        for b in banks:
            o, end = b * 0x4000, (b + 1) * 0x4000
            while o < end:
                e = o
                while e < end and self.prg[e] and (self.prg[e] >= 0x20 or self.prg[e] == 0x0A):
                    e += 1
                run = self.prg[o:e]
                kana = sum(0xA6 <= c <= 0xDD for c in run)
                if len(run) >= min_len and kana >= 0.6 * len(run) and (o == b * 0x4000 or self.prg[o - 1] == 0):
                    out.append((o, text(run)))
                o = e + 1
        return out
