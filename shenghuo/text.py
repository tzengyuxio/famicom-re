"""Glyph-code -> character tables of 聖火列傳.

There is no global character set: a glyph code (cell = code & $3F, plane = bit 7) indexes the CHR bank
loaded as the font for that piece of text. The tables below were transcribed by eye from the glyph
sheets (export.py writes them to output/text/), one string per group entry, and are turned into a
code -> character map per font by `charmap`. '　' is a blank glyph. Characters in UNCERTAIN are low
resolution guesses.
"""
from rom import ENEMY_CHR, ENEMY_GROUP, NAME_CHR, NAME_GROUP, Rom

# group 0 (font CHR bank 0), entries 1-83
GROUP0 = [
    None, "小刀", "短刀", "單刀", "馬刀", "關刀", "短劍", "長劍", "軟劍", "青鋼劍",
    "短斧", "宣花斧", "開山斧", "短棍", "長棍", "齊眉棍", "長槍", "紅纓槍", "雙槍", "飛鏢",
    "雲南白藥", "金創藥", "七釐散", "人蔘", "保心丹", "辟毒丹", "煙霧彈", "震天雷", "霹靂彈",
    "楊棈", "黃蠶", "秋姬", "葉中", "少主", "林欽", "丁豪", "吳昆", "鄭頤", "陳娟", "郭鏞", "謝雄", "何麗",
    "震天掌", "飛雲斬", "點穴法", "金針渡穴", "太極劍法", "太極掌法", "辟毒掌", "天南毒掌", "天心劍法",
    "金鋼拳", "長青劍法", "小心掌法", "渡人劍法", "散毒法", "白雲槍法", "太秋斧法", "辟金刀法", "七巧劍法",
    "小震天掌", "七創拳", "秋花刀法", "開山棍法", "霹靂槍法", "麗天劍法", "中道棍法", "長飛心法", "飛天心法",
    "飛雲心法",
    "力量", "敏捷", "技巧", "中毒", "垂死", "戰鬥", "裝備", "武技", "道具", "逃跑", "完", "決定", "取消", "戰　鬥",
]

# group 9 (font CHR bank 9), entries 1-75
GROUP9 = [
    None, "黃衣殺手", "青衣殺手", "紫衣殺手", "天　　殺", "地　　殺", "人　　殺", "首　　領", "衙　　役",
    "捕　　快", "捕　　頭", "強　　盜", "頭　　目", "山大王", "小　　偷", "御林軍", "左金吾", "右金吾",
    "太　　監", "總管太監", "鎮國將軍", "保邦元帥", "禁軍統領", "僵　　屍", "惡　　鬼", "楊　　棈", "元　　帝",
    "血　　蛤", "金　　蠶", "一品侍衛", "二品侍衛", "三品侍衛", "　　豹", "　　狼", "　　虎", "蜘　　蛛",
    "陳永", "天性子", "天塵子", "天明子", "天星子", "吳楚", "白勝", "枯竹", "枯木", "枯榮", "靜性", "靜心",
    "慈明", "慈音", "慈性", "陳正", "吳天", "青竹", "青木", "青松", "天明", "天心", "方木", "方性", "方正",
    "戰　鬥", "決　鬥", "你派哪些夥伴迎戰？　　　", "派這些夥伴迎戰嗎？　是否", "勝利", "Gold+", "迎戰的人Exp+",
    "以及找到了", "完", "　" * 12, "迎戰嗎？　是否", "你派這夥伴決鬥？", "你派哪夥伴決鬥？", "是否", "左右金吾",
]

UNCERTAIN = {"棈": "木 + 青 at 16x16 (楊棈, the villain); could be a simplified 楨",
             "蠶": "金蠶 / 黃蠶: 16x16 glyph, top half unclear"}

FONTS = {NAME_CHR: (NAME_GROUP, GROUP0), ENEMY_CHR: (ENEMY_GROUP, GROUP9)}


def charmap(rom: Rom, chr_bank: int) -> dict[int, str]:
    """Glyph code -> character for the font in chr_bank; raises if the transcription contradicts itself."""
    group, texts = FONTS[chr_bank]
    out: dict[int, str] = {}
    for i, (codes, text) in enumerate(zip(rom.strings(group), texts)):
        if text is None:
            continue
        if len(codes) != len(text):
            raise ValueError(f"group {group} entry {i}: {len(codes)} codes vs {text!r}")
        for c, ch in zip(codes, text):
            if out.setdefault(c, ch) != ch:
                raise ValueError(f"code {c:02X}: {out[c]!r} vs {ch!r} (group {group} entry {i})")
    return out


def decode(rom: Rom, chr_bank: int, codes: bytes) -> str:
    m = charmap(rom, chr_bank)
    return "".join(m.get(c, f"[{c:02X}]") for c in codes)
