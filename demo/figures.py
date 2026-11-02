"""draw the readme's figures from fixpoint.bmp itself.

docs/preview.png  the image, scaled 3x with no smoothing.
docs/anatomy.svg  figure 1: the boot sector read as a bmp palette, with the path
                  the cpu takes through it and, below, its instructions.

the path is not taken from build.py. it is traced from fixpoint.bmp: start at
byte 0, disassemble one instruction at a time with ndisasm, follow every
`jmp short`, stop at the far jump into the pixels. the instructions are then
named by their lines in stub.asm, checked against the trace.

where the svg is inlined, as on the project page, pointing at an instruction
lights up its bytes and the other way round, with css alone.

the figure is set in computer modern, from the copies matplotlib ships. every
glyph is drawn as an outline, so the svg needs no fonts and looks the same
everywhere, including on github.

usage: python3 demo/figures.py   (from the repo root; needs ndisasm, pillow, matplotlib)
"""
import os, subprocess
from functools import lru_cache

import matplotlib
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from PIL import Image

BMP, OUT, PREVIEW = "fixpoint.bmp", "docs/anatomy.svg", "docs/preview.png"
PAL, SECTOR, PIX = 54, 512, 1078
STATUS = (446, 462, 478, 494)
data = open(BMP, "rb").read()
palette = Image.open(BMP).getpalette()


# ------------------------------------------------------------------ the trace

def one_instruction(off):
    out = subprocess.run(["ndisasm", "-b16", "-o%d" % (0x7C00 + off), "-"],
                         input=data[off:off + 16], capture_output=True, check=True).stdout
    addr, hexbytes, text = out.decode().splitlines()[0].split(None, 2)
    return len(hexbytes) // 2, " ".join(text.split())


def trace():
    """the instructions the cpu executes, in order, as (offset, length, text).

    the two jumps are decoded from their opcodes, not from ndisasm's text, which
    changes between versions: nasm 3 prints `jmp short` as plain `jmp`."""
    path, off = [], 0
    for _ in range(200):
        n, text = one_instruction(off)
        path.append((off, n, text))
        if data[off] == 0xEB:                             # jmp short
            off += 2 + int.from_bytes(data[off + 1:off + 2], signed=True)
        elif data[off] == 0xEA:                           # jmp far: offset, then segment
            return path
        else:
            off += n
    raise RuntimeError("no far jump found")


def far_target(path):
    off = path[-1][0]
    return (int.from_bytes(data[off + 3:off + 5], "little"),
            int.from_bytes(data[off + 1:off + 3], "little"))


# ------------------------------------------------------------------ type
#
# computer modern, drawn as outlines. the bakoma fonts use tex's old encoding,
# so a few characters live at other code points.

FONTS = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
REMAP = {"–": ("cmr10", "{"), "—": ("cmr10", "|"),                  # ot1: 7B is en, 7C is em
         "×": ("cmsy10", chr(0xA3)), "\u00a0": ("cmr10", " ")}


@lru_cache(maxsize=None)
def font(name):
    f = TTFont(os.path.join(FONTS, name + ".ttf"))
    return f, f.getBestCmap(), f.getGlyphSet(), f["head"].unitsPerEm


class Type:
    def __init__(self):
        self.defs = {}

    def glyph(self, face, ch):
        if ch in REMAP:
            face, ch = REMAP[ch]
        f, cmap, glyphs, upm = font(face)
        name = cmap[ord(ch)]
        gid = "%s-%s" % (face, name)
        if gid not in self.defs:
            pen = SVGPathPen(glyphs)
            glyphs[name].draw(pen)
            self.defs[gid] = pen.getCommands()
        return gid, f["hmtx"][name][0], upm

    def width(self, s, face, size):
        return sum(self.glyph(face, c)[1] / self.glyph(face, c)[2] * size for c in s)

    def text(self, x, y, s, face="cmr10", size=10, anchor="start", fill="#000"):
        if anchor != "start":
            x -= self.width(s, face, size) * (0.5 if anchor == "middle" else 1)
        out = []
        for c in s:
            gid, adv, upm = self.glyph(face, c)
            k = size / upm
            if c not in " \u00a0":
                out.append('<use href="#%s" xlink:href="#%s" transform="translate(%.2f %.2f) scale(%.5f -%.5f)"/>'
                           % (gid, gid, x, y, k, k))
            x += adv * k
        return '<g fill="%s">%s</g>' % (fill, "".join(out))

    def runs(self, x, y, runs, size=10, fill="#000"):
        """a line of mixed faces: [(text, face), ...]."""
        out = []
        for s, face in runs:
            out.append(self.text(x, y, s, face, size, fill=fill))
            x += self.width(s, face, size)
        return "".join(out)

    def wrap(self, x, y, width, runs, size=10, leading=13.5):
        """set a paragraph of mixed faces, breaking at spaces."""
        words = []
        for s, face in runs:
            for i, w in enumerate(s.split(" ")):
                if i and words:
                    words.append((" ", face))
                if w:
                    words.append((w, face))
        lines, line, w = [], [], 0
        for word, face in words:
            ww = self.width(word, face, size)
            if word == " ":
                line.append((word, face))
                w += ww
                continue
            if w + ww > width and line:
                while line and line[-1][0] == " ":
                    line.pop()
                lines.append(line)
                line, w = [], 0
            line.append((word, face))
            w += ww
        lines.append(line)
        return "".join(self.runs(x, y + i * leading, l, size) for i, l in enumerate(lines)), len(lines)


# ------------------------------------------------------------------ the listing
#
# panel (c) names each traced instruction with its line in stub.asm, so it reads
# the way the source does. the trace still comes from the file: the names are
# checked against it, instruction for instruction, by ndisasm's mnemonic.

def listing(path):
    """the rows of panel (c): dicts of run, instructions (indices into path), label,
    name, note, and whether they are fillers."""
    asm, label = [], None
    for line in open("stub.asm"):
        if line.startswith("read:"):
            label = "read:"
            continue
        if not line.startswith("    ") or line.split()[0] == "db":
            continue
        ins, _, note = (s.strip() for s in line.partition(";"))
        asm.append((ins, note, label))
        label = None
    head = [("inc dx", "the B", None), ("dec bp", "the M", None),
            ("jmp short", "bfSize: into the palette", None)]
    named = head + asm
    assert len(named) == len(path), "stub.asm and the trace disagree"

    rows, run = [], 0
    for i, ((off, n, text), (ins, note, label)) in enumerate(zip(path, named)):
        assert ins.split()[0] == text.split()[0], (ins, text)
        if ins.startswith("jmp short"):
            ins, note = "jmp short", note.replace("hop over", "over")
        if label:
            rows.append(dict(run=run, ins=[], label=label, name="", note="", filler=False))
        filler = note.startswith("filler")
        if filler and rows and rows[-1]["filler"]:
            rows[-1]["ins"].append(i)
            rows[-1]["name"] += "; " + ins
        else:
            rows.append(dict(run=run, ins=[i], label=None, name=ins, filler=filler,
                             note="fillers, for their colour" if filler else note))
        if data[off] in (0xEB, 0xEA):
            run += 1
    return rows


# ------------------------------------------------------------------ figure 1

INK, GREY, RULE = "#000", "#555", 0.6
COLS, EW, EH = 16, 30, 20                 # palette entries per row, swatch width and height
BW = EW / 4                               # one byte of the palette
HBW = 2 * BW                              # one byte of the file header, drawn wider
X0, GW = 78, COLS * EW                    # left edge and width of panels (a) and (b)
Y_HEAD, HH = 62, 24                       # top and height of the header strip
Y_GRID = Y_HEAD + HH + 84                 # top of the palette
LAST = (SECTOR - 1 - PAL) // 4            # 0x72: the last entry the boot sector reaches
ROWS = LAST // COLS + 1
LEAD = 13.5                               # listing line spacing


def hx(off):
    """left edge of header byte off; the info header is drawn as one block."""
    return X0 + off * HBW if off <= 14 else X0 + GW


def byte_xy(off):
    """centre of a byte, where the path runs through it."""
    if off < 14:
        return X0 + (off + 0.5) * HBW, Y_HEAD + HH * 0.7
    assert off >= PAL, "the cpu never runs the info header"
    e, ch = divmod(off - PAL, 4)
    r, c = divmod(e, COLS)
    return X0 + c * EW + (ch + 0.5) * BW, Y_GRID + r * EH + EH / 2


def byte_boxes(off, n):
    """rectangles covering bytes off..off+n-1, one per row they span."""
    boxes = []
    for b in range(off, off + n):
        x, y = byte_xy(b)
        w, h = (HBW, HH) if b < 14 else (BW, EH)
        x, y = x - w / 2, y - (HH * 0.7 if b < 14 else EH / 2)
        if boxes and abs(boxes[-1][1] - y) < 0.1 and abs(boxes[-1][0] + boxes[-1][2] - x) < 0.1:
            boxes[-1][2] += w
        else:
            boxes.append([x, y, w, h])
    return boxes


def rgb(e):
    return "#%02x%02x%02x" % tuple(palette[3 * e:3 * e + 3])


def arrowhead(x, y, dx, dy, size=4.5):
    """a small filled arrowhead at (x, y), pointing along (dx, dy)."""
    n = (dx * dx + dy * dy) ** 0.5 or 1
    ux, uy = dx / n, dy / n
    px, py = -uy, ux
    pts = [(x, y), (x - ux * size + px * size * 0.42, y - uy * size + py * size * 0.42),
           (x - ux * size - px * size * 0.42, y - uy * size - py * size * 0.42)]
    return '<path d="M%.2f %.2fL%.2f %.2fL%.2f %.2fZ" fill="%s"/>' % (*pts[0], *pts[1], *pts[2], INK)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


# the figure is live where it is inlined (the project page): pointing at a line of
# (c), or at a byte of the path, lights up the other. css only, no script; in an
# <img>, as on github, none of it fires and the figure is simply static.
STYLE = (".hit rect{fill:#fff;fill-opacity:0}.row{outline:none}.row>rect{fill:#ffe7a0;fill-opacity:0}"
         ".row,.hit{cursor:default}")
LIT = ("svg:has(.r{k}:hover,.r{k}:focus,.h{k}:hover) .h{k} rect"
       "{{fill-opacity:.5;stroke:#000;stroke-width:2}}"
       "svg:has(.r{k}:hover,.r{k}:focus,.h{k}:hover) .r{k}>rect{{fill-opacity:1}}")


def anatomy():
    t = Type()
    path = trace()
    rows = listing(path)
    pixels = Image.open(BMP).histogram()
    o, hits = [], []
    line = lambda x1, y1, x2, y2, w=RULE, c=INK: o.append(
        '<path d="M%.2f %.2fL%.2f %.2f" stroke="%s" stroke-width="%s" fill="none"/>' % (x1, y1, x2, y2, c, w))
    box = lambda x, y, w, h, sw=RULE: o.append(
        '<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="none" stroke="%s" stroke-width="%s"/>'
        % (x, y, w, h, INK, sw))

    # --- (a) the header
    o.append(t.runs(X0, Y_HEAD - 32, [("(a)", "cmb10"), ("  Headers, bytes 0–53", "cmr10")], 11.5))
    executed = {b for off, n, _ in path for b in range(off, off + n)}
    for off in range(14):
        o.append('<rect x="%.2f" y="%d" width="%.2f" height="%d" fill="#fff" stroke="#999" stroke-width="0.35"/>'
                 % (hx(off), Y_HEAD, HBW, HH))
        if off in executed:
            o.append(t.text(hx(off) + HBW / 2, Y_HEAD + 9.4, "%02X" % data[off], "cmtt10", 7.6, "middle"))
    o.append(t.text((hx(14) + hx(54)) / 2, Y_HEAD + HH / 2 + 3.2,
                    "320 × 200, top-down, 8 bits per pixel, 256 colours", "cmr10", 9, "middle", GREY))
    for a, b, label in [(0, 2, "bfType"), (2, 6, "bfSize"), (6, 10, "reserved"), (10, 14, "bfOffBits"),
                        (14, 54, "BITMAPINFOHEADER")]:
        box(hx(a), Y_HEAD, hx(b) - hx(a), HH)
        face = "cmr10" if label == "reserved" else "cmtt10"
        o.append(t.text((hx(a) + hx(b)) / 2, Y_HEAD - 6, label, face, 8.8, "middle", GREY))
    for off in (0, 2, 6, 10, 14, 54):
        line(hx(off), Y_HEAD + HH, hx(off), Y_HEAD + HH + 3)
        o.append(t.text(hx(off), Y_HEAD + HH + 12, str(off), "cmr10", 8, "middle", GREY))

    # --- (b) the palette, up to the end of the boot sector
    o.append(t.runs(X0, Y_GRID - 34, [("(b)", "cmb10"), ("  Palette, bytes 54–511", "cmr10")], 11.5))
    for c in range(COLS):
        o.append(t.text(X0 + c * EW + EW / 2, Y_GRID - 7, "%X" % c, "cmtt10", 9, "middle", GREY))
    o.append(t.text(X0 - 50, Y_GRID - 7, "entry", "cmr10", 9, "middle", GREY))
    o.append(t.text(X0 - 8, Y_GRID - 7, "byte", "cmr10", 9, "end", GREY))
    for r in range(ROWS):
        y = Y_GRID + r * EH
        o.append(t.text(X0 - 50, y + EH / 2 + 3, "%X0" % r, "cmtt10", 9, "middle", GREY))
        o.append(t.text(X0 - 8, y + EH / 2 + 3, str(PAL + 4 * COLS * r), "cmr10", 9, "end", GREY))
    for e in range(LAST + 1):
        r, c = divmod(e, COLS)
        o.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s" stroke="#fff" stroke-width="0.8">'
                 '<title>entry %02X, %s, %s pixels</title></rect>'
                 % (X0 + c * EW, Y_GRID + r * EH, EW, EH, rgb(e), e, rgb(e), f"{pixels[e]:,}"))
    # entry 72 straddles byte 512: its red and unused bytes are beyond the sector
    x512, y512 = byte_xy(SECTOR)
    x512 -= BW / 2
    yr = Y_GRID + (ROWS - 1) * EH
    o.append('<rect x="%.2f" y="%d" width="%.2f" height="%d" fill="#fff" fill-opacity="0.7"/>'
             % (x512, yr, 2 * BW, EH))
    o.append('<path d="M%d %dH%dV%dH%.2fV%dH%dZ" fill="none" stroke="%s" stroke-width="%s"/>'
             % (X0, Y_GRID, X0 + GW, yr, x512, yr + EH, X0, INK, RULE))
    line(x512, yr - 4, x512, yr + EH + 4, 1.1)
    o.append(t.text(x512, yr + EH + 15, "byte 512: end of the boot sector", "cmr10", 9, "middle", GREY))
    for off in STATUS:
        x, y = byte_xy(off)
        box(x - BW / 2, y - EH / 2, BW, EH, 1.1)
    x, y = byte_xy(510)
    box(x - BW / 2, y - EH / 2, 2 * BW, EH, 1.1)

    # --- the path the cpu takes
    pts = [(b, byte_xy(b)) for off, n, _ in path for b in range(off, off + n)]
    d, heads, markers = "", [], []
    starts = {path[0][0]} | {off for i, (off, n, _) in enumerate(path) if i and data[path[i - 1][0]] in (0xEB, 0xEA)}
    for i, (b, (x, y)) in enumerate(pts):
        if i == 0:
            d += "M%.2f %.2f" % (x, y)
            markers.append((X0 - 12, y))
            continue
        pb, (px, py) = pts[i - 1]
        if b == pb + 1 and abs(y - py) < 1:
            d += " L%.2f %.2f" % (x, y)
        elif b == pb + 1:                                  # wrapping to the next row
            d += " C%.2f %.2f %.2f %.2f %.2f %.2f" % (px + 14, py, x - 14, y, x, y)
        elif pb < 14:                                      # out of the header: land vertically,
            ye = Y_GRID - 16                               # dropping between two column labels
            k = (ye - py) * 0.55
            d += " C%.2f %.2f %.2f %.2f %.2f %.2f L%.2f %.2f" % (px, py + k, x, ye - k, x, ye, x, y - 3)
            heads.append((x, y - 3, 0, 1))
            markers.append((x - 11, y))
        else:                                              # a hop within the palette
            k = max(36, abs(x - px) * 0.32)
            d += " C%.2f %.2f %.2f %.2f %.2f %.2f" % (px + k, py, x - k, y, x, y)
            heads.append((x - 2.2, y, 1, 0))
            markers.append((x, y - EH / 2))
    o.append('<path d="%s" fill="none" stroke="#fff" stroke-width="3.2" stroke-linejoin="round"/>' % d)
    o.append('<path d="%s" fill="none" stroke="%s" stroke-width="0.9" stroke-linejoin="round"/>' % (d, INK))
    for off, n, _ in path:
        x, y = byte_xy(off)
        o.append('<circle cx="%.2f" cy="%.2f" r="1.7" fill="#fff" stroke="%s" stroke-width="0.6"/>' % (x, y, INK))
    for h in heads:
        o.append(arrowhead(*h))
    ex, ey = pts[-1][1]
    xr = X0 + GW
    o.append('<path d="M%.2f %.2fL%.2f %.2f" stroke="#fff" stroke-width="3.2"/>' % (ex + 3, ey, xr + 18, ey))
    line(ex + 3, ey, xr + 18, ey, 0.9)
    o.append(arrowhead(xr + 22, ey, 1, 0))

    def marker(x, y, n):
        o.append('<circle cx="%.2f" cy="%.2f" r="5.6" fill="#fff" stroke="%s" stroke-width="0.7"/>' % (x, y, INK))
        o.append(t.text(x, y + 2.7, str(n), "cmr10", 8, "middle"))

    for n, (x, y) in enumerate(markers, 1):
        marker(x, y, n)

    # --- annotations in the right margin
    ax = xr + 30
    notes = []

    def note(y, runs, size=9.4):
        notes.append(t.width("".join(s for s, _ in runs), runs[0][1], size))
        o.append(t.runs(ax, y, runs, size, GREY))

    seg, offs = far_target(path)
    note(ey - 3, [("jmp %04X:%04X" % (seg, offs), "cmtt10")])
    note(ey + 9, [("into the pixels: row 0, x = %d" % ((offs - 0x8000 - PIX) % 320), "cmr10")])
    x, y = byte_xy(STATUS[-1])
    line(x + BW / 2, y, ax - 4, y, 0.4, GREY)
    note(y - 8, [("partition status bytes,", "cmr10")])
    note(y + 4, [("blue channels set to 80", "cmr10")])
    x, y = byte_xy(511)
    line(x + BW / 2, y, ax - 4, y, 0.4, GREY)
    note(y + 3, [("boot signature 55 AA,", "cmr10")])
    note(y + 15, [("blue and green of entry 72", "cmr10")])

    # --- (c) the path, disassembled
    yc = Y_GRID + ROWS * EH + 52
    o.append(t.runs(X0, yc, [("(c)", "cmb10"), ("  The path, disassembled", "cmr10")], 11.5))
    size = 8.8
    for row in rows:
        row["hex"] = " ".join("%02X" % data[b] for i in row["ins"]
                              for b in range(path[i][0], path[i][0] + path[i][1]))
    # two columns, split between runs, each as wide as its own widest cells
    half = min(range(1, len(rows)), key=lambda j: abs(2 * j - len(rows)) + 99 * (rows[j]["run"] == rows[j - 1]["run"]))
    cols = []
    for part in (rows[:half], rows[half:]):
        bw = max(t.width(r["hex"], "cmtt10", size) for r in part) + 10
        iw = max(t.width(r["name"] or r["label"], "cmtt10", size) for r in part) + 10
        nw = max(t.width(r["note"], "cmr10", size) for r in part)
        cols.append((bw, iw, 18 + bw + iw + nw))
    lx, gap = X0 - 18, 30
    style = [STYLE]
    for j, row in enumerate(rows):
        col, k = (0, j) if j < half else (1, j - half)
        bw, iw, colw = cols[col]
        cx, y = lx + col * (cols[0][2] + gap), yc + 22 + k * LEAD
        first = j == 0 or row["run"] != rows[j - 1]["run"]
        if first:
            marker(cx + 5.6, y - 3, row["run"] + 1)
        ink = GREY if row["filler"] or row["label"] else INK
        if row["label"]:
            o.append(t.text(cx + 18 + bw, y, row["label"], "cmtt10", size, fill=GREY))
            continue
        cells = (t.text(cx + 18, y, row["hex"], "cmtt10", size, fill=ink)
                 + t.text(cx + 18 + bw, y, row["name"], "cmtt10", size, fill=ink)
                 + t.text(cx + 18 + bw + iw, y, row["note"], "cmr10", size, fill=GREY))
        o.append('<g class="row r%d" tabindex="0"><rect x="%.2f" y="%.2f" width="%.2f" height="%.2f"/>%s</g>'
                 % (j, cx + 14, y - 9.6, colw - 12, LEAD, cells))
        rects = "".join('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f"/>' % tuple(bx)
                        for i in row["ins"] for bx in byte_boxes(*path[i][:2]))
        first_b = path[row["ins"][0]][0]
        last_b = path[row["ins"][-1]][0] + path[row["ins"][-1]][1] - 1
        hits.append('<g class="hit h%d">%s<title>%s, bytes %d–%d</title></g>'
                    % (j, rects, esc(row["name"]), first_b, last_b))
        style.append(LIT.format(k=j))
    o.extend(hits)
    ylist = yc + 22 + (max(half, len(rows) - half) - 1) * LEAD

    W = max(ax + max(notes) + 16, lx + cols[0][2] + gap + cols[1][2] + 16)

    # --- the caption
    jumps = [off for off, n, _ in path if data[off] == 0xEB]
    code = sum(n for off, n, _ in path if off >= PAL)
    touched = len({(b - PAL) // 4 for b, _ in pts if b >= PAL})
    ycap = ylist + 36
    cap, n = t.wrap(16, ycap, W - 32, [
        ("Figure 1.", "cmb10"),
        (" The first 512 bytes of ", "cmr10"), ("fixpoint.bmp", "cmtt10"),
        (". (a) The headers. The CPU starts at byte 0: ", "cmr10"), ("BM", "cmtt10"),
        (" executes as ", "cmr10"), ("inc dx; dec bp", "cmtt10"), (", and the low bytes of ", "cmr10"),
        ("bfSize", "cmtt10"), (", ", "cmr10"), ("EB %02X" % data[3], "cmtt10"),
        (", are a short jump into the palette. (b) The palette up to byte 512, one swatch per entry, "
         "drawn in its own colour. The line is the path the CPU takes, traced by disassembling the "
         "file from byte 0 and following each jump: %d instructions, %d bytes of code in %d palette "
         "entries, and %d short jumps over entries the bootloader leaves alone. Outlined: the four "
         "partition status bytes and the boot signature, which the disk format fixes and the palette "
         "absorbs. (c) The same path as instructions, named as in "
         % (len(path), code, touched, len(jumps) - 1), "cmr10"),
        ("stub.asm", "cmtt10"),
        ("; the fillers, in grey, are there only for their colour.", "cmr10"),
    ], size=10.6, leading=14.5)
    o.append(cap)
    H = ycap + n * 14.5 + 6

    defs = "".join('<path id="%s" d="%s"/>' % (gid, d) for gid, d in sorted(t.defs.items()))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           'viewBox="0 0 %d %d" width="%d" height="%d">\n'
           '<title>Figure 1: the first 512 bytes of fixpoint.bmp, read as bmp headers and a palette, '
           'with the path the cpu takes through them and its instructions</title>\n'
           '<style>%s</style>\n'
           '<rect width="100%%" height="100%%" fill="#fff"/>\n<defs>%s</defs>\n%s\n</svg>\n'
           % (W, H, W * 1.25, H * 1.25, "".join(style), defs, "\n".join(o)))
    open(OUT, "w").write(svg)
    print(f"{OUT}: {len(path)} instructions traced, {code} bytes of code in {touched} palette entries, "
          f"{len(jumps) - 1} hops")


def preview():
    image = Image.open(BMP).convert("RGB")
    image.resize((3 * image.width, 3 * image.height), Image.NEAREST).save(PREVIEW)


if __name__ == "__main__":
    anatomy()
    preview()
