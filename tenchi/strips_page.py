"""Portrait-strip outputs shared by 天地を喰らう I and II (tenchi2/export.py imports this module).

Both games build a portrait from 6 rows of 48x8 strips listed in the general's record. A game's export.py passes
its strips and generals as a dict; write() then
  - splits the faces: an own face (専屬臉) uses 6 strips no other face uses; the other strips fall into groups,
    the connected parts of "used in the same face" (two per game, which look like 兜 and 官帽 faces);
  - writes strips_sheet.png (parts sheet), strips/<row>_<label>.png (each strip at 2x) and strips_data.json;
  - rebuilds the two-game editor tenchi/output/strips.html from both games' strips_data.json;
  - returns the rows of portrait_strips.csv.

Data dict: game, title, group_names (by lowest strip index), fixed (hex colours 0-2), colors (hex colour 3 per
palette id; one entry = no choice), strips (384 chars '0'-'3' per strip, 48x8 row-major, as shown on screen),
labels (strip code text), generals [{id, name (shown in lists), zh (kanji name), kana, p: 6 strip indexes,
c: palette id, k: kanji glyph hex}].
The page embeds ROM graphics, so it only goes to the git-ignored output/.

  .venv/bin/python tenchi/strips_page.py     # rebuild only the editor from the existing strips_data.json files
"""
import json
import os

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMES = ["tenchi", "tenchi2"]
PAGE = os.path.join(ROOT, "tenchi", "output", "strips.html")
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


def analyse(d: dict) -> None:
    """Add own (own faces, as strip lists), groups [{name, rows: strips per row}] and group (per strip: -1 = own
    face, else the group number) to d."""
    faces = sorted({tuple(g["p"]) for g in d["generals"]})
    count = {}
    for f in faces:
        for v in set(f):
            count[v] = count.get(v, 0) + 1
    own = [f for f in faces if all(count[v] == 1 for v in f)]
    rest = [f for f in faces if f not in own]
    parent = {}

    def find(x: int) -> int:
        while parent.setdefault(x, x) != x:
            x = parent[x]
        return x
    for f in rest:
        for v in f[1:]:
            parent[find(v)] = find(f[0])
    roots = sorted({find(v) for f in rest for v in f}, key=lambda r: min(v for v in parent if find(v) == r))
    if len(roots) != len(d["group_names"]):
        raise ValueError(f"{d['game']}: {len(roots)} strip groups, expected {len(d['group_names'])}")
    d["own"] = [list(f) for f in own]
    d["group"] = [-1] * len(d["strips"])
    d["groups"] = []
    for n, root in enumerate(roots):
        rows = [sorted({f[k] for f in rest if find(f[0]) == root}) for k in range(6)]
        for row in rows:
            for v in row:
                d["group"][v] = n
        d["groups"].append({"name": d["group_names"][n], "faces": sum(find(f[0]) == root for f in rest),
                            "rows": rows})


def group_name(d: dict, v: int) -> str:
    return "專屬" if d["group"][v] < 0 else d["group_names"][d["group"][v]]


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
    return [{"row": k + 1, "strip": d["labels"][v], "group": group_name(d, v),
             "faces": len({tuple(g["p"]) for g in gs}), "generals": len(gs), "users": names(gs)}
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
    sw, lh, width, tx = 96, 15, 1400, 96 + 120
    dr = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    blocks = []  # (row, text, image, name lines)
    for (k, v), gs in sorted(users(d).items(), key=lambda kv: (kv[0][0], d["group"][kv[0][1]], kv[0][1])):
        colors = [g["c"] for g in gs]
        im = strip_image(d, v, max(set(colors), key=colors.count)).resize((sw, 16), Image.NEAREST)
        label = d["labels"][v]
        im.save(os.path.join(sd, f"{k + 1}_{label.replace(':', '-')}.png"))
        text = f"{label} ×{len({tuple(g['p']) for g in gs})}  {group_name(d, v)}"
        blocks.append((k, text, im, wrap(dr, names(gs), f, width - tx - 6)))
    height = sum(max(20, len(b[3]) * lh + 5) for b in blocks) + 6 * 30
    img = Image.new("RGB", (width, height), (40, 40, 40))
    dr, y = ImageDraw.Draw(img), 0
    for k in range(6):
        sec = [b for b in blocks if b[0] == k]
        dr.text((6, y + 8), f"第 {k + 1} 條（y {k * 8}–{k * 8 + 7}）：{len(sec)} 種", fill=(255, 220, 120), font=fb)
        y += 30
        for _, text, im, lines in sec:
            img.paste(im, (6, y + 2))
            dr.text((sw + 12, y + 3), text, fill=(255, 255, 255), font=f)
            for n, t in enumerate(lines):
                dr.text((tx, y + 3 + n * lh), t, fill=(190, 190, 190), font=f)
            y += max(20, len(lines) * lh + 5)
    img.save(os.path.join(out, "strips_sheet.png"))
    return len(blocks)


def page() -> str:
    """The two-game editor, from whichever games' strips_data.json exist."""
    data = []
    for g in GAMES:
        p = os.path.join(ROOT, g, "output", "strips_data.json")
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                data.append(json.load(fh))
    os.makedirs(os.path.dirname(PAGE), exist_ok=True)
    with open(PAGE, "w", encoding="utf-8") as fh:
        fh.write(TEMPLATE.replace("/*DATA*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":"))))
    return PAGE


def write(d: dict, out: str) -> list[dict]:
    """All strip outputs of one game; returns the portrait_strips.csv rows."""
    analyse(d)
    sheet(d, out)
    with open(os.path.join(out, "strips_data.json"), "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, separators=(",", ":"))
    page()
    return csv_rows(d)


TEMPLATE = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>天地を喰らう頭像拼貼</title>
<style>
:root { --bg: #f6f5f2; --fg: #222; --muted: #666; --card: #fff; --line: #ddd; --accent: #c0392b; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #1d1d1f; --fg: #eee; --muted: #9a9a9a; --card: #2a2a2d; --line: #3a3a3e; --accent: #ff7a6b; }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 16px; background: var(--bg); color: var(--fg);
  font: 14px/1.5 -apple-system, "Hiragino Sans", "Noto Sans CJK TC", sans-serif; }
h1 { font-size: 20px; margin: 0 0 8px; }
p.note { color: var(--muted); margin: 0 0 16px; max-width: 64em; }
.tabs { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
.tabs button.on { border-color: var(--accent); color: var(--accent); font-weight: bold; }
.top { display: flex; flex-wrap: wrap; gap: 16px; align-items: flex-start; }
.face { background: var(--card); border: 1px solid var(--line); border-radius: 8px; padding: 12px; }
canvas { image-rendering: pixelated; display: block; }
#face { width: 288px; height: 288px; background: #000; }
#kanji { height: 32px; margin-top: 8px; background: #000; }
.controls { flex: 1; min-width: 260px; display: flex; flex-direction: column; gap: 10px; }
select, button { font: inherit; padding: 4px 8px; border-radius: 6px; border: 1px solid var(--line);
  background: var(--card); color: var(--fg); cursor: pointer; }
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
.own { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.own .pick { text-align: center; font-size: 12px; color: var(--muted); width: 104px; }
.own .pick canvas { width: 96px; height: 96px; margin: 0 auto 2px; }
.users { color: var(--muted); font-size: 12px; min-height: 1.5em; }
</style>
</head>
<body>
<h1>天地を喰らう 頭像拼貼</h1>
<div class="tabs" id="games"></div>
<p class="note" id="note"></p>
<div class="top">
  <div class="face"><canvas id="face" width="48" height="48"></canvas><canvas id="kanji" width="48" height="16"></canvas></div>
  <div class="controls">
    <div><label>載入武將　</label><select id="gen"></select></div>
    <div class="tabs" id="modes"></div>
    <div class="swatches" id="colors"></div>
    <div><button id="rand">隨機拼一張</button></div>
    <div id="match"></div>
  </div>
</div>
<div id="body"></div>
<script>
const GAMES = /*DATA*/null;
let D, cur;
const $ = id => document.getElementById(id);
const hex2 = v => D.labels[v];
const rgb = h => [1, 3, 5].map(i => parseInt(h.slice(i, i + 2), 16));
const same = (a, b) => a.every((v, k) => v === b[k]);
const isOwn = p => D.own.some(f => same(f, p));
const groupOf = p => isOwn(p) ? -1 : (p.map(v => D.group[v]).find(g => g >= 0) ?? -1);

function drawStrip(ctx, v, c, y) {
  const img = ctx.createImageData(48, 8), P = [...D.fixed, D.colors[c]].map(rgb), s = D.strips[v];
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
  const cv = $("kanji"), n = g ? g.k.length : 0;
  cv.width = Math.max(16, n * 16); cv.style.width = cv.width * 2 + "px"; cv.style.height = "32px";
  const ctx = cv.getContext("2d"); ctx.fillStyle = "#000"; ctx.fillRect(0, 0, cv.width, 16);
  ctx.fillStyle = "#fff";
  if (g) g.k.forEach((h, j) => {
    const bits = BigInt("0x" + h).toString(2).padStart(256, "0");
    for (let i = 0; i < 256; i++) if (bits[i] === "1") ctx.fillRect(j * 16 + i % 16, i >> 4, 1, 1);
  });
}
function rowChoices(k) {
  if (cur.mode >= 0) return D.groups[cur.mode].rows[k];
  return [...new Set(D.groups.flatMap(g => g.rows[k]))].sort((a, b) => a - b);  // mode -2: every group
}
function setMode(m) { cur.mode = m; build(); }
function load(g) {
  cur.p = g.p.slice(); cur.c = g.c; cur.g = g.id;
  const m = groupOf(cur.p);
  if (m !== cur.mode && cur.mode !== -2 || m === -1) setMode(m); else render();
}
function render() {
  const ctx = $("face").getContext("2d");
  cur.p.forEach((v, k) => drawStrip(ctx, v, cur.c, k * 8));
  const sameP = D.generals.filter(g => same(g.p, cur.p));
  const exact = sameP.filter(g => g.c === cur.c);
  drawKanji(exact.find(g => g.id === cur.g) || exact[0] || null);
  const hasColor = D.colors.length > 1;
  $("match").innerHTML =
    (exact.length ? `完全相同：<b>${names(exact)}</b>` : "沒有武將用這個組合")
    + (sameP.length > exact.length ? `<br>同樣橫條、不同配色：${names(sameP.filter(g => g.c !== cur.c))}` : "")
    + `<br>橫條：${cur.p.map(hex2).join(" ")}` + (hasColor ? `　配色 ${cur.c}` : "");
  document.querySelectorAll("#colors .sw").forEach((e, i) => e.classList.toggle("on", i + 1 === cur.c));
  document.querySelectorAll("#modes button").forEach(e => e.classList.toggle("on", +e.dataset.m === cur.mode));
  document.querySelectorAll(".row").forEach((row, k) => {
    row.querySelectorAll(".pick").forEach(e => e.classList.toggle("on", +e.dataset.v === cur.p[k]));
    row.querySelector(".users").textContent = "用這條的：" + (names(users(k, cur.p[k])) || "（無）");
    row.querySelectorAll(".pick canvas").forEach(cv => drawStrip(cv.getContext("2d"), +cv.parentNode.dataset.v, cur.c, 0));
  });
  document.querySelectorAll(".own .pick").forEach(e => {
    const f = D.own[+e.dataset.f]; e.classList.toggle("on", same(f, cur.p));
  });
}
function build() {
  const box = $("body"); box.innerHTML = "";
  if (cur.mode === -1) {
    const grid = document.createElement("div"); grid.className = "own";
    D.own.forEach((f, n) => {
      const gs = D.generals.filter(g => same(g.p, f));
      const b = document.createElement("div"); b.className = "pick"; b.dataset.f = n; b.title = names(gs);
      const cv = document.createElement("canvas"); cv.width = 48; cv.height = 48;
      f.forEach((v, k) => drawStrip(cv.getContext("2d"), v, gs[0].c, k * 8));
      b.append(cv, gs[0].name);
      b.onclick = () => { cur.p = f.slice(); cur.c = gs[0].c; cur.g = gs[0].id; $("gen").value = gs[0].id; render(); };
      grid.appendChild(b);
    });
    box.appendChild(grid);
  } else {
    if (cur.p.some(v => D.group[v] < 0) || (cur.mode >= 0 && cur.p.some(v => D.group[v] !== cur.mode))) {
      cur.p = cur.p.map((v, k) => rowChoices(k).includes(v) ? v : rowChoices(k)[0]);
    }
    for (let k = 0; k < 6; k++) {
      const list = rowChoices(k);
      const row = document.createElement("div"); row.className = "row";
      row.innerHTML = `<h2>第 ${k + 1} 條 <span>（y ${k * 8}–${k * 8 + 7}，${list.length} 種）</span></h2>`
        + `<div class="picks"></div><div class="users"></div>`;
      const picks = row.querySelector(".picks");
      for (const v of list) {
        const b = document.createElement("div"); b.className = "pick"; b.dataset.v = v;
        b.title = hex2(v) + "：" + (names(users(k, v)) || "此位置沒人用");
        const cv = document.createElement("canvas"); cv.width = 48; cv.height = 8; b.appendChild(cv);
        b.onclick = () => { cur.p[k] = v; render(); };
        picks.appendChild(b);
      }
      box.appendChild(row);
    }
  }
  $("rand").style.display = cur.mode === -1 ? "none" : "";
  render();
}
function useGame(n) {
  D = GAMES[n];
  document.querySelectorAll("#games button").forEach((e, i) => e.classList.toggle("on", i === n));
  const nOwn = D.own.length, gs = D.groups.map(g => `${g.name} ${g.faces} 張`).join("、");
  $("note").textContent = `每張頭像是 6 條 48×8 的橫條` + (D.colors.length > 1 ? `，加上第 4 色的配色（${D.colors.length - 1} 種）` : `，調色盤固定`)
    + `。6 條都只有自己用的「專屬臉」有 ${nOwn} 張，可直接選；其餘的臉依「同一張臉裡出現過」把橫條連起來，`
    + `正好分成 ${D.groups.length} 組（${gs}），不同組的橫條從來沒有拼在一起過，所以每組只能在組內混搭；`
    + `專屬臉用到的橫條不在任何一組的選項裡。「不分組」可以把各組的橫條混著試。資料與圖形都直接取自 ROM。`;
  $("gen").innerHTML = "";
  for (const g of D.generals) $("gen").add(new Option([g.id, g.zh, g.kana].filter(x => x).join(" "), g.id));
  $("modes").innerHTML = "";
  [[-1, `專屬臉（${nOwn}）`], ...D.groups.map((g, i) => [i, `${g.name}組（${g.faces}）`]), [-2, "不分組"]].forEach(([m, t]) => {
    const b = document.createElement("button"); b.textContent = t; b.dataset.m = m; b.onclick = () => setMode(m);
    $("modes").appendChild(b);
  });
  $("colors").innerHTML = "";
  if (D.colors.length > 1) D.colors.forEach((h, i) => {
    if (!i) return;
    const e = document.createElement("div"); e.className = "sw"; e.style.background = h; e.title = "配色 " + i;
    e.onclick = () => { cur.c = i; render(); };
    $("colors").appendChild(e);
  });
  const g0 = D.generals.find(g => !isOwn(g.p)) || D.generals[0];
  cur = { p: g0.p.slice(), c: g0.c, g: g0.id, mode: groupOf(g0.p) };
  $("gen").value = g0.id;
  build();
}
GAMES.forEach((g, n) => {
  const b = document.createElement("button"); b.textContent = g.title; b.onclick = () => useGame(n);
  $("games").appendChild(b);
});
$("gen").onchange = () => load(D.generals.find(g => g.id === +$("gen").value));
$("rand").onclick = () => {
  cur.p = cur.p.map((_, k) => { const l = rowChoices(k); return l[Math.random() * l.length | 0]; });
  if (D.colors.length > 1) cur.c = 1 + (Math.random() * (D.colors.length - 1) | 0);
  cur.g = null; render();
};
useGame(0);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print(page())
