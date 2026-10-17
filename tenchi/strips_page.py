"""Portrait-strip outputs shared by 天地を喰らう I and II (tenchi2/ imports this module).

Both games build a portrait from 6 rows of 48x8 strips listed in the general's record. A game passes its strips
and generals as a dict, and this module writes:
  strips.html        interactive page: pick a strip per row (and a colour 3, game I only), see who uses it
  strips_sheet.png   parts sheet, one section per row, each strip with the generals using it
  strips/<row>_<label>.png   each strip at 2x
and returns the rows of portrait_strips.csv.

Data dict: title, note, fixed (hex colours 0-2), colors (hex colour 3 per palette id; one entry = no choice),
strips (384 chars '0'-'3' per strip, 48x8 row-major, already as shown on screen), labels (strip code text),
rows (strip indexes each row uses), generals [{id, name, p: 6 strip indexes, c: palette id, k: kanji glyph hex}].
The page embeds ROM graphics, so it only goes to the git-ignored output/.
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

FONT_PATHS = ["/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"]


def font(size: int):
    for p in FONT_PATHS:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def glyph_hex(bits: list[int]) -> str:
    """256 glyph pixels (0/1, row-major 16x16) -> 64 hex digits."""
    return f"{int(''.join(map(str, bits)), 2):064x}"


def users(d: dict) -> dict[tuple[int, int], list[dict]]:
    """(row 0-5, strip index) -> generals whose portrait uses that strip in that row."""
    out = {}
    for g in d["generals"]:
        for k, v in enumerate(g["p"]):
            out.setdefault((k, v), []).append(g)
    return out


def names(gs: list[dict]) -> str:
    """Same-name ids merged: シュウチョウ(1,2,3)."""
    by = {}
    for g in gs:
        by.setdefault(g["name"], []).append(str(g["id"]))
    return "、".join(f"{n}({','.join(ids)})" for n, ids in by.items())


def csv_rows(d: dict) -> list[dict]:
    return [{"row": k + 1, "strip": d["labels"][v], "faces": len({tuple(g["p"]) for g in gs}),
             "generals": len(gs), "users": names(gs)}
            for (k, v), gs in sorted(users(d).items())]


def strip_image(d: dict, v: int, c: int) -> Image.Image:
    pal = [tuple(int(h[i:i + 2], 16) for i in (1, 3, 5)) for h in d["fixed"] + [d["colors"][c]]]
    im = Image.new("RGB", (48, 8))
    im.putdata([pal[int(ch)] for ch in d["strips"][v]])
    return im


def wrap(dr: ImageDraw.ImageDraw, text: str, f, width: int) -> list[str]:
    lines, cur = [], ""
    for part in text.split("、"):
        nxt = f"{cur}、{part}" if cur else part
        if cur and dr.textlength(nxt, font=f) > width:
            lines.append(cur + "、")
            nxt = part
        cur = nxt
    return lines + [cur]


def sheet(d: dict, out: str) -> int:
    """strips_sheet.png and strips/; a strip is drawn in the colour 3 most of its users have."""
    sd = os.path.join(out, "strips")
    os.makedirs(sd, exist_ok=True)
    f, fb = font(11), font(14)
    sw, lh, width = 96, 15, 1400
    dr = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    blocks = []  # (row, label, image, faces, name lines)
    for (k, v), gs in sorted(users(d).items()):
        colors = [g["c"] for g in gs]
        im = strip_image(d, v, max(set(colors), key=colors.count)).resize((sw, 16), Image.NEAREST)
        label = d["labels"][v]
        im.save(os.path.join(sd, f"{k + 1}_{label.replace(':', '-')}.png"))
        blocks.append((k, label, im, len({tuple(g["p"]) for g in gs}), wrap(dr, names(gs), f, width - sw - 80)))
    height = sum(max(20, len(b[4]) * lh + 5) for b in blocks) + 6 * 30
    img = Image.new("RGB", (width, height), (40, 40, 40))
    dr, y = ImageDraw.Draw(img), 0
    for k in range(6):
        sec = [b for b in blocks if b[0] == k]
        dr.text((6, y + 8), f"第 {k + 1} 條（y {k * 8}–{k * 8 + 7}）：{len(sec)} 種", fill=(255, 220, 120), font=fb)
        y += 30
        for _, label, im, faces, lines in sec:
            img.paste(im, (6, y + 2))
            dr.text((sw + 12, y + 3), f"{label} ×{faces}", fill=(255, 255, 255), font=f)
            for n, t in enumerate(lines):
                dr.text((sw + 80, y + 3 + n * lh), t, fill=(190, 190, 190), font=f)
            y += max(20, len(lines) * lh + 5)
    img.save(os.path.join(out, "strips_sheet.png"))
    return len(blocks)


def write(d: dict, out: str) -> list[dict]:
    """All strip outputs; returns the portrait_strips.csv rows."""
    sheet(d, out)
    with open(os.path.join(out, "strips.html"), "w", encoding="utf-8") as fh:
        fh.write(TEMPLATE.replace("/*TITLE*/", d["title"]).replace("/*NOTE*/", d["note"])
                 .replace("/*DATA*/null", json.dumps(d, ensure_ascii=False, separators=(",", ":"))))
    return csv_rows(d)


TEMPLATE = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>/*TITLE*/</title>
<style>
:root { --bg: #f6f5f2; --fg: #222; --muted: #666; --card: #fff; --line: #ddd; --accent: #c0392b; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #1d1d1f; --fg: #eee; --muted: #9a9a9a; --card: #2a2a2d; --line: #3a3a3e; --accent: #ff7a6b; }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 16px; background: var(--bg); color: var(--fg);
  font: 14px/1.5 -apple-system, "Hiragino Sans", "Noto Sans CJK TC", sans-serif; }
h1 { font-size: 20px; margin: 0 0 4px; }
p.note { color: var(--muted); margin: 0 0 16px; max-width: 60em; }
.top { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }
.face { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 12px; }
canvas { image-rendering: pixelated; display: block; }
#face { width: 288px; height: 288px; background: #000; }
#kanji { height: 32px; margin-top: 8px; background: #000; }
.controls { flex: 1; min-width: 260px; display: flex; flex-direction: column; gap: 10px; }
select, button { font: inherit; padding: 4px 8px; border-radius: 6px; border: 1px solid var(--line);
  background: var(--card); color: var(--fg); }
.swatches { display: flex; gap: 6px; flex-wrap: wrap; }
.swatches:empty { display: none; }
.sw { width: 28px; height: 28px; border-radius: 6px; border: 2px solid var(--line); cursor: pointer; }
.sw.on { border-color: var(--accent); }
#match { color: var(--muted); }
#match b { color: var(--fg); }
.row { margin-top: 14px; }
.row h2 { font-size: 14px; margin: 0 0 6px; }
.row h2 span { color: var(--muted); font-weight: normal; }
.picks { display: flex; flex-wrap: wrap; gap: 4px; padding-bottom: 6px; }
.pick { flex: none; border: 2px solid transparent; border-radius: 4px; cursor: pointer; padding: 1px; }
.pick.on { border-color: var(--accent); }
.pick canvas { width: 96px; height: 16px; }
.users { color: var(--muted); font-size: 12px; min-height: 1.5em; }
label { color: var(--muted); }
</style>
</head>
<body>
<h1>/*TITLE*/</h1>
<p class="note">/*NOTE*/</p>
<div class="top">
  <div class="face"><canvas id="face" width="48" height="48"></canvas><canvas id="kanji" width="48" height="16"></canvas></div>
  <div class="controls">
    <div><label>載入武將　</label><select id="gen"></select></div>
    <div class="swatches" id="colors"></div>
    <div><button id="rand">隨機拼一張</button>　<label><input type="checkbox" id="all"> 不限位置</label></div>
    <div id="match"></div>
  </div>
</div>
<div id="rows"></div>
<script>
const D = /*DATA*/null;
const N = D.strips.length, hasColor = D.colors.length > 1;
const cur = { p: D.generals[0].p.slice(), c: D.generals[0].c, g: D.generals[0].id };
const pal = c => [...D.fixed, D.colors[c]];
const rgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
const choices = k => document.getElementById("all").checked ? [...Array(N).keys()] : D.rows[k];

function drawStrip(ctx, v, c, y) {
  const img = ctx.createImageData(48, 8), P = pal(c).map(rgb), s = D.strips[v];
  for (let i = 0; i < 384; i++) { const q = P[+s[i]]; img.data.set([q[0], q[1], q[2], 255], i * 4); }
  ctx.putImageData(img, 0, y);
}
function users(k, v) { return D.generals.filter(g => g.p[k] === v); }
function names(gs) {
  const by = new Map();
  for (const g of gs) { if (!by.has(g.name)) by.set(g.name, []); by.get(g.name).push(g.id); }
  return [...by].map(([n, ids]) => `${n}(${ids.join(",")})`).join("、");
}
function drawKanji(g) {
  const cv = document.getElementById("kanji"), n = g ? g.k.length : 0;
  cv.width = Math.max(16, n * 16); cv.style.width = cv.width * 2 + "px"; cv.style.height = "32px";
  const ctx = cv.getContext("2d"); ctx.fillStyle = "#000"; ctx.fillRect(0, 0, cv.width, 16);
  ctx.fillStyle = "#fff";
  if (g) g.k.forEach((h, j) => {
    const bits = BigInt("0x" + h).toString(2).padStart(256, "0");
    for (let i = 0; i < 256; i++) if (bits[i] === "1") ctx.fillRect(j * 16 + i % 16, i >> 4, 1, 1);
  });
}
function render() {
  const ctx = document.getElementById("face").getContext("2d");
  cur.p.forEach((v, k) => drawStrip(ctx, v, cur.c, k * 8));
  const same = D.generals.filter(g => g.p.every((v, k) => v === cur.p[k]));
  const exact = same.filter(g => g.c === cur.c);
  drawKanji(exact.find(g => g.id === cur.g) || exact[0] || null);
  document.getElementById("match").innerHTML =
    (exact.length ? `完全相同：<b>${names(exact)}</b>` : "沒有武將用這個組合")
    + (same.length > exact.length ? `<br>同樣橫條、不同配色：${names(same.filter(g => g.c !== cur.c))}` : "")
    + `<br>橫條：${cur.p.map(v => D.labels[v]).join(" ")}` + (hasColor ? `　配色 ${cur.c}` : "");
  document.querySelectorAll(".sw").forEach((e, i) => e.classList.toggle("on", i + 1 === cur.c));
  document.querySelectorAll(".row").forEach((row, k) => {
    row.querySelectorAll(".pick").forEach(e => e.classList.toggle("on", +e.dataset.v === cur.p[k]));
    row.querySelector(".users").textContent = "用這條的：" + (names(users(k, cur.p[k])) || "（無）");
    row.querySelectorAll(".pick canvas").forEach(cv => drawStrip(cv.getContext("2d"), +cv.parentNode.dataset.v, cur.c, 0));
  });
}
function buildRows() {
  const box = document.getElementById("rows");
  box.innerHTML = "";
  for (let k = 0; k < 6; k++) {
    const list = choices(k);
    const row = document.createElement("div"); row.className = "row";
    row.innerHTML = `<h2>第 ${k + 1} 條 <span>（y ${k * 8}–${k * 8 + 7}，${list.length} 種）</span></h2>`
      + `<div class="picks"></div><div class="users"></div>`;
    const picks = row.querySelector(".picks");
    for (const v of list) {
      const b = document.createElement("div"); b.className = "pick"; b.dataset.v = v;
      b.title = D.labels[v] + "：" + (names(users(k, v)) || "此位置沒人用");
      const cv = document.createElement("canvas"); cv.width = 48; cv.height = 8; b.appendChild(cv);
      b.onclick = () => { cur.p[k] = v; render(); };
      picks.appendChild(b);
    }
    box.appendChild(row);
  }
  render();
}
const sel = document.getElementById("gen");
for (const g of D.generals) sel.add(new Option(`${g.id} ${g.name}`, g.id));
sel.onchange = () => { const g = D.generals.find(g => g.id === +sel.value); cur.p = g.p.slice(); cur.c = g.c; cur.g = g.id; render(); };
if (hasColor) D.colors.forEach((h, i) => {
  if (!i) return;
  const e = document.createElement("div"); e.className = "sw"; e.style.background = h; e.title = "配色 " + i;
  e.onclick = () => { cur.c = i; render(); };
  document.getElementById("colors").appendChild(e);
});
document.getElementById("rand").onclick = () => {
  cur.p = cur.p.map((_, k) => { const l = choices(k); return l[Math.random() * l.length | 0]; });
  if (hasColor) cur.c = 1 + (Math.random() * (D.colors.length - 1) | 0);
  render();
};
document.getElementById("all").onchange = buildRows;
buildRows();
</script>
</body>
</html>
"""
