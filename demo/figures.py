"""draw the readme's figures from fixpoint.bmp itself.

docs/preview.png  the image, scaled 3x with no smoothing.
site/static/favicon.png, site/static/apple-touch-icon.png
                  the edge of the light cone, cut from the image, in big pixels.
site/static/social.png
                  the link preview: the image at 4x, cropped to 1200x630 with the
                  program's row along the top edge.
docs/fieldguide.svg
                  figure 1: the picture at 3x, with a field guide to what's in it,
                  every region computed from the pixels.
docs/anatomy.svg  figure 2: the boot sector read as a bmp palette, with the path
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

import base64
import hashlib
import io
import os
import re
import subprocess
from collections import deque
from functools import cache
from pathlib import Path

import matplotlib
import numpy as np
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont
from PIL import Image

BMP, OUT, PREVIEW = "fixpoint.bmp", "docs/anatomy.svg", "docs/preview.png"
PAL, SECTOR, PIX = 54, 512, 1078
STATUS = (446, 462, 478, 494)
data = Path(BMP).read_bytes()
palette = Image.open(BMP).getpalette()


# ------------------------------------------------------------------ the trace


def one_instruction(off):
    out = subprocess.run(
        ["ndisasm", "-b16", f"-o{0x7C00 + off}", "-"], input=data[off : off + 16], capture_output=True, check=True
    ).stdout
    _addr, hexbytes, text = out.decode().splitlines()[0].split(None, 2)
    return len(hexbytes) // 2, " ".join(text.split())


def trace():
    """the instructions the cpu executes, in order, as (offset, length, text).

    the two jumps are decoded from their opcodes, not from ndisasm's text, which
    changes between versions: nasm 3 prints `jmp short` as plain `jmp`."""
    path, off = [], 0
    for _ in range(200):
        n, text = one_instruction(off)
        path.append((off, n, text))
        if data[off] == 0xEB:  # jmp short
            off += 2 + int.from_bytes(data[off + 1 : off + 2], signed=True)
        elif data[off] == 0xEA:  # jmp far: offset, then segment
            return path
        else:
            off += n
    raise RuntimeError("no far jump found")


def far_target(path):
    off = path[-1][0]
    return (int.from_bytes(data[off + 3 : off + 5], "little"), int.from_bytes(data[off + 1 : off + 3], "little"))


# ------------------------------------------------------------------ type
#
# computer modern, drawn as outlines. the bakoma fonts use tex's old encoding,
# so a few characters live at other code points.

FONTS = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")
REMAP = {
    "–": ("cmr10", "{"),
    "—": ("cmr10", "|"),  # ot1: 7B is en, 7C is em
    "×": ("cmsy10", chr(0xA3)),
    "\u00a0": ("cmr10", " "),
}


@cache
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
        gid = f"{face}-{name}"
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
                out.append(
                    f'<use href="#{gid}" xlink:href="#{gid}" '
                    f'transform="translate({x:.2f} {y:.2f}) scale({k:.5f} -{k:.5f})"/>'
                )
            x += adv * k
        return f'<g fill="{fill}">{"".join(out)}</g>'

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
        return "".join(self.runs(x, y + i * leading, ln, size) for i, ln in enumerate(lines)), len(lines)


# ------------------------------------------------------------------ the listing
#
# panel (c) names each traced instruction with its line in stub.asm, so it reads
# the way the source does. the trace still comes from the file: the names are
# checked against it, instruction for instruction, by ndisasm's mnemonic.


def listing(path):
    """the rows of panel (c): dicts of run, instructions (indices into path), label,
    name, note, and whether they are fillers."""
    asm, label = [], None
    for line in Path("stub.asm").read_text().splitlines(keepends=True):
        if line.startswith("read:"):
            label = "read:"
            continue
        if not line.startswith("    ") or line.split()[0] == "db":
            continue
        ins, _, note = (s.strip() for s in line.partition(";"))
        asm.append((ins, note, label))
        label = None
    head = [("inc dx", "the B", None), ("dec bp", "the M", None), ("jmp short", "bfSize: into the palette", None)]
    named = head + asm
    assert len(named) == len(path), "stub.asm and the trace disagree"

    rows, run = [], 0
    for i, ((off, _n, text), (ins, note, label)) in enumerate(zip(path, named, strict=False)):
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
            rows.append(
                dict(
                    run=run,
                    ins=[i],
                    label=None,
                    name=ins,
                    filler=filler,
                    note="fillers, for their colour" if filler else note,
                )
            )
        if data[off] in (0xEB, 0xEA):
            run += 1
    return rows


# ------------------------------------------------------------------ figure 1

INK, GREY, RULE = "#000", "#555", 0.6
COLS, EW, EH = 16, 30, 20  # palette entries per row, swatch width and height
BW = EW / 4  # one byte of the palette
HBW = 2 * BW  # one byte of the file header, drawn wider
X0, GW = 78, COLS * EW  # left edge and width of panels (a) and (b)
Y_HEAD, HH = 62, 24  # top and height of the header strip
Y_GRID = Y_HEAD + HH + 84  # top of the palette
LAST = (SECTOR - 1 - PAL) // 4  # 0x72: the last entry the boot sector reaches
ROWS = LAST // COLS + 1
LEAD = 13.5  # listing line spacing


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
    r, g, b = palette[3 * e : 3 * e + 3]
    return f"#{r:02x}{g:02x}{b:02x}"


def arrowhead(x, y, dx, dy, size=4.5):
    """a small filled arrowhead at (x, y), pointing along (dx, dy)."""
    n = (dx * dx + dy * dy) ** 0.5 or 1
    ux, uy = dx / n, dy / n
    px, py = -uy, ux
    pts = [
        (x, y),
        (x - ux * size + px * size * 0.42, y - uy * size + py * size * 0.42),
        (x - ux * size - px * size * 0.42, y - uy * size - py * size * 0.42),
    ]
    (x1, y1), (x2, y2), (x3, y3) = pts
    return f'<path d="M{x1:.2f} {y1:.2f}L{x2:.2f} {y2:.2f}L{x3:.2f} {y3:.2f}Z" fill="{INK}"/>'


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


# the figure is live where it is inlined (the project page): pointing at a line of
# (c), or at a byte of the path, lights up the other. css only, no script; in an
# <img>, as on github, none of it fires and the figure is simply static.
STYLE = (
    ".hit rect{fill:#fff;fill-opacity:0}.row{outline:none}.row>rect{fill:#ffe7a0;fill-opacity:0}"
    ".row,.hit{cursor:default}"
)
LIT = (
    "svg:has(.r{k}:hover,.r{k}:focus,.h{k}:hover) .h{k} rect"
    "{{fill-opacity:.5;stroke:#000;stroke-width:2}}"
    "svg:has(.r{k}:hover,.r{k}:focus,.h{k}:hover) .r{k}>rect{{fill-opacity:1}}"
)


def anatomy():
    t = Type()
    path = trace()
    rows = listing(path)
    pixels = Image.open(BMP).histogram()
    o, hits = [], []

    def line(x1, y1, x2, y2, w=RULE, c=INK):
        return o.append(f'<path d="M{x1:.2f} {y1:.2f}L{x2:.2f} {y2:.2f}" stroke="{c}" stroke-width="{w}" fill="none"/>')

    def box(x, y, w, h, sw=RULE):
        return o.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" fill="none" '
            f'stroke="{INK}" stroke-width="{sw}"/>'
        )

    # --- (a) the header
    o.append(t.runs(X0, Y_HEAD - 32, [("(a)", "cmb10"), ("  headers, bytes 0–53", "cmr10")], 11.5))
    executed = {b for off, n, _ in path for b in range(off, off + n)}
    for off in range(14):
        o.append(
            f'<rect x="{hx(off):.2f}" y="{Y_HEAD}" width="{HBW:.2f}" height="{HH}" fill="#fff" '
            'stroke="#999" stroke-width="0.35"/>'
        )
        if off in executed:
            o.append(t.text(hx(off) + HBW / 2, Y_HEAD + 9.4, f"{data[off]:02X}", "cmtt10", 7.6, "middle"))
    o.append(
        t.text(
            (hx(14) + hx(54)) / 2,
            Y_HEAD + HH / 2 + 3.2,
            "320 × 200, top-down, 8 bits per pixel, 256 colours",
            "cmr10",
            9,
            "middle",
            GREY,
        )
    )
    for a, b, label in [
        (0, 2, "bfType"),
        (2, 6, "bfSize"),
        (6, 10, "reserved"),
        (10, 14, "bfOffBits"),
        (14, 54, "BITMAPINFOHEADER"),
    ]:
        box(hx(a), Y_HEAD, hx(b) - hx(a), HH)
        face = "cmr10" if label == "reserved" else "cmtt10"
        o.append(t.text((hx(a) + hx(b)) / 2, Y_HEAD - 6, label, face, 8.8, "middle", GREY))
    for off in (0, 2, 6, 10, 14, 54):
        line(hx(off), Y_HEAD + HH, hx(off), Y_HEAD + HH + 3)
        o.append(t.text(hx(off), Y_HEAD + HH + 12, str(off), "cmr10", 8, "middle", GREY))

    # --- (b) the palette, up to the end of the boot sector
    o.append(t.runs(X0, Y_GRID - 34, [("(b)", "cmb10"), ("  palette, bytes 54–511", "cmr10")], 11.5))
    for c in range(COLS):
        o.append(t.text(X0 + c * EW + EW / 2, Y_GRID - 7, f"{c:X}", "cmtt10", 9, "middle", GREY))
    o.append(t.text(X0 - 50, Y_GRID - 7, "entry", "cmr10", 9, "middle", GREY))
    o.append(t.text(X0 - 8, Y_GRID - 7, "byte", "cmr10", 9, "end", GREY))
    for r in range(ROWS):
        y = Y_GRID + r * EH
        o.append(t.text(X0 - 50, y + EH / 2 + 3, f"{r:X}0", "cmtt10", 9, "middle", GREY))
        o.append(t.text(X0 - 8, y + EH / 2 + 3, str(PAL + 4 * COLS * r), "cmr10", 9, "end", GREY))
    for e in range(LAST + 1):
        r, c = divmod(e, COLS)
        o.append(
            f'<rect x="{X0 + c * EW}" y="{Y_GRID + r * EH}" width="{EW}" height="{EH}" fill="{rgb(e)}" '
            f'stroke="#fff" stroke-width="0.8"><title>entry {e:02X}, {rgb(e)}, {pixels[e]:,} pixels'
            "</title></rect>"
        )
    # entry 72 straddles byte 512: its red and unused bytes are beyond the sector
    x512, _y512 = byte_xy(SECTOR)
    x512 -= BW / 2
    yr = Y_GRID + (ROWS - 1) * EH
    o.append(f'<rect x="{x512:.2f}" y="{yr}" width="{2 * BW:.2f}" height="{EH}" fill="#fff" fill-opacity="0.7"/>')
    o.append(
        f'<path d="M{X0} {Y_GRID}H{X0 + GW}V{yr}H{x512:.2f}V{yr + EH}H{X0}Z" fill="none" stroke="{INK}" '
        f'stroke-width="{RULE}"/>'
    )
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
    {path[0][0]} | {off for i, (off, n, _) in enumerate(path) if i and data[path[i - 1][0]] in (0xEB, 0xEA)}
    for i, (b, (x, y)) in enumerate(pts):
        if i == 0:
            d += f"M{x:.2f} {y:.2f}"
            markers.append((X0 - 12, y))
            continue
        pb, (px, py) = pts[i - 1]
        if b == pb + 1 and abs(y - py) < 1:
            d += f" L{x:.2f} {y:.2f}"
        elif b == pb + 1:  # wrapping to the next row
            d += f" C{px + 14:.2f} {py:.2f} {x - 14:.2f} {y:.2f} {x:.2f} {y:.2f}"
        elif pb < 14:  # out of the header: land vertically,
            ye = Y_GRID - 16  # dropping between two column labels
            k = (ye - py) * 0.55
            d += f" C{px:.2f} {py + k:.2f} {x:.2f} {ye - k:.2f} {x:.2f} {ye:.2f} L{x:.2f} {y - 3:.2f}"
            heads.append((x, y - 3, 0, 1))
            markers.append((x - 11, y))
        else:  # a hop within the palette
            k = max(36, abs(x - px) * 0.32)
            d += f" C{px + k:.2f} {py:.2f} {x - k:.2f} {y:.2f} {x:.2f} {y:.2f}"
            heads.append((x - 2.2, y, 1, 0))
            markers.append((x, y - EH / 2))
    o.append(f'<path d="{d}" fill="none" stroke="#fff" stroke-width="3.2" stroke-linejoin="round"/>')
    o.append(f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="0.9" stroke-linejoin="round"/>')
    for off, _, _ in path:
        x, y = byte_xy(off)
        o.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="1.7" fill="#fff" stroke="{INK}" stroke-width="0.6"/>')
    for h in heads:
        o.append(arrowhead(*h))
    ex, ey = pts[-1][1]
    xr = X0 + GW
    o.append(f'<path d="M{ex + 3:.2f} {ey:.2f}L{xr + 18:.2f} {ey:.2f}" stroke="#fff" stroke-width="3.2"/>')
    line(ex + 3, ey, xr + 18, ey, 0.9)
    o.append(arrowhead(xr + 22, ey, 1, 0))

    def marker(x, y, n):
        o.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5.6" fill="#fff" stroke="{INK}" stroke-width="0.7"/>')
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
    note(ey - 3, [(f"jmp {seg:04X}:{offs:04X}", "cmtt10")])
    note(ey + 9, [(f"into the pixels: row 0, x = {(offs - 0x8000 - PIX) % 320}", "cmr10")])
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
    o.append(t.runs(X0, yc, [("(c)", "cmb10"), ("  the path, disassembled", "cmr10")], 11.5))
    size = 8.8
    for row in rows:
        row["hex"] = " ".join(f"{data[b]:02X}" for i in row["ins"] for b in range(path[i][0], path[i][0] + path[i][1]))
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
        cells = (
            t.text(cx + 18, y, row["hex"], "cmtt10", size, fill=ink)
            + t.text(cx + 18 + bw, y, row["name"], "cmtt10", size, fill=ink)
            + t.text(cx + 18 + bw + iw, y, row["note"], "cmr10", size, fill=GREY)
        )
        o.append(
            f'<g class="row r{j}" tabindex="0"><rect x="{cx + 14:.2f}" y="{y - 9.6:.2f}" '
            f'width="{colw - 12:.2f}" height="{LEAD:.2f}"/>{cells}</g>'
        )
        rects = "".join(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}"/>'
            for i in row["ins"]
            for x, y, w, h in byte_boxes(*path[i][:2])
        )
        first_b = path[row["ins"][0]][0]
        last_b = path[row["ins"][-1]][0] + path[row["ins"][-1]][1] - 1
        hits.append(f'<g class="hit h{j}">{rects}<title>{esc(row["name"])}, bytes {first_b}–{last_b}</title></g>')
        style.append(LIT.format(k=j))
    o.extend(hits)
    ylist = yc + 22 + (max(half, len(rows) - half) - 1) * LEAD

    W = max(ax + max(notes) + 16, lx + cols[0][2] + gap + cols[1][2] + 16)

    # --- the caption
    jumps = [off for off, n, _ in path if data[off] == 0xEB]
    code = sum(n for off, n, _ in path if off >= PAL)
    touched = len({(b - PAL) // 4 for b, _ in pts if b >= PAL})
    ycap = ylist + 36
    cap, n = t.wrap(
        16,
        ycap,
        W - 32,
        [
            ("figure 2.", "cmb10"),
            (" the first 512 bytes of ", "cmr10"),
            ("fixpoint.bmp", "cmtt10"),
            (". (a) the headers. the cpu starts at byte 0: ", "cmr10"),
            ("BM", "cmtt10"),
            (" executes as ", "cmr10"),
            ("inc dx; dec bp", "cmtt10"),
            (", and the low bytes of ", "cmr10"),
            ("bfSize", "cmtt10"),
            (", ", "cmr10"),
            (f"EB {data[3]:02X}", "cmtt10"),
            (
                ", are a short jump into the palette. (b) the palette up to byte 512, one swatch per entry, "
                "drawn in its own colour. the line is the path the cpu takes, traced by disassembling the "
                f"file from byte 0 and following each jump: {len(path)} instructions, {code} bytes of code in "
                f"{touched} palette entries, and {len(jumps) - 1} short jumps over entries the bootloader leaves "
                "alone. outlined: the four partition status bytes and the boot signature, which the disk format "
                "fixes and the palette absorbs. (c) the same path as instructions, named as in ",
                "cmr10",
            ),
            ("stub.asm", "cmtt10"),
            ("; the fillers, in grey, are there only for their colour.", "cmr10"),
        ],
        size=10.6,
        leading=14.5,
    )
    o.append(cap)
    H = ycap + n * 14.5 + 6

    defs = "".join(f'<path id="{gid}" d="{d}"/>' for gid, d in sorted(t.defs.items()))
    body = "\n".join(o)
    # %d truncated these before; int() keeps the svg byte for byte the same
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {int(W)} {int(H)}" width="{int(W * 1.25)}" height="{int(H * 1.25)}">\n'
        "<title>figure 2: the first 512 bytes of fixpoint.bmp, read as bmp headers and a palette, "
        "with the path the cpu takes through them and its instructions</title>\n"
        f"<style>{''.join(style)}</style>\n"
        f'<rect width="100%" height="100%" fill="#fff"/>\n<defs>{defs}</defs>\n{body}\n</svg>\n'
    )
    Path(OUT).write_text(svg)
    print(
        f"{OUT}: {len(path)} instructions traced, {code} bytes of code in {touched} palette entries, "
        f"{len(jumps) - 1} hops"
    )


def save(image, path):
    # pillow versions compress the same pixels differently; rewrite only a real change
    if os.path.exists(path) and Image.open(path).convert("RGB").tobytes() == image.tobytes():
        return
    image.save(path)


def preview():
    image = Image.open(BMP).convert("RGB")
    save(image.resize((3 * image.width, 3 * image.height), Image.NEAREST), PREVIEW)


ICON_CENTRE = (122, 154)  # where the right cone's edge meets the dark ether, row 154
ICONS = {"site/static/favicon.png": (32, 2), "site/static/apple-touch-icon.png": (45, 4)}  # side, scale


def icons():
    image = Image.open(BMP).convert("RGB")
    cx, cy = ICON_CENTRE
    for path, (side, scale) in ICONS.items():
        x, y = cx - side // 2, cy - side // 2
        save(image.crop((x, y, x + side, y + side)).resize((side * scale,) * 2, Image.NEAREST), path)


SOCIAL = "site/static/social.png"  # 1200x630, the shape every link preview wants
SOCIAL_CROP = (40, 0, 1240, 630)  # at 4x: columns 10..309, rows 0..157: row 0 on the top edge, both cones below


def social():
    image = Image.open(BMP).convert("RGB")
    save(image.resize((4 * image.width, 4 * image.height), Image.NEAREST).crop(SOCIAL_CROP), SOCIAL)


# ------------------------------------------------------------------ the field guide
#
# figure 1: the picture at 3x, with what is in it. every region is computed from the
# pixels, not drawn: a pixel is reached if it differs from the same rule run on the
# ether alone. pointing at a name dims everything else; scattered pixels get rings.

GUIDE = "docs/fieldguide.svg"
S = 3  # screen pixels per image pixel


def untouched():
    """the universe without the program: row 0 all ether, then rule 110 on the same tape."""
    px = np.frombuffer(Image.open(BMP).tobytes(), np.uint8)
    t = np.zeros(320 * 200, np.uint8)
    t[:320] = np.resize(px[:14], 320)
    for i in range(321, 320 * 200):
        left, centre, right = int(t[i - 321]), int(t[i - 320]), int(t[i - 319])
        t[i] = (centre | right) & ~(left & centre & right) & 0xFF
    return px.reshape(200, 320), t.reshape(200, 320)


def flood(mask, seeds, diagonal=False):
    """the cells of mask connected to any seed."""
    steps = [(1, 0), (-1, 0), (0, 1), (0, -1)] + ([(1, 1), (1, -1), (-1, 1), (-1, -1)] if diagonal else [])
    out = np.zeros_like(mask)
    todo = deque(s for s in seeds if mask[s])
    for s in todo:
        out[s] = True
    while todo:
        y, x = todo.popleft()
        for dy, dx in steps:
            yy, xx = y + dy, x + dx
            if 0 <= yy < 200 and 0 <= xx < 320 and mask[yy, xx] and not out[yy, xx]:
                out[yy, xx] = True
                todo.append((yy, xx))
    return out


def interior(mask):
    """a point well inside a region: the cell that survives the most erosions."""
    depth, m = np.zeros(mask.shape, int), mask.copy()
    while m.any():
        depth += m
        m = m & np.roll(m, 1, 0) & np.roll(m, -1, 0) & np.roll(m, 1, 1) & np.roll(m, -1, 1)
        m[0, :] = m[-1, :] = m[:, 0] = m[:, -1] = False
    y, x = np.unravel_index(np.argmax(depth), depth.shape)
    return x, y


def png_uri(image):
    buf = io.BytesIO()
    image.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def spotlight(mask):
    """white veil over everything outside the mask."""
    veil = np.where(mask, 0, 200).astype(np.uint8)
    return Image.merge("LA", (Image.new("L", (320, 200), 255), Image.fromarray(veil)))


def regions():
    px, ether = untouched()
    reached = px != ether
    dark = np.isin(px, [0, 255])
    program = np.zeros_like(reached)
    program[0, 190:320] = True
    cone = flood(reached, [(0, x) for x in range(190, 320)])
    corner = flood(reached & dark, [(0, x) for x in range(306, 320)], diagonal=True)
    code = {(b - PAL) // 4 for off, n, _ in trace() for b in range(off, off + n) if b >= PAL}
    return [
        # (name, what it is, mask, ring the pixels, marker or None)
        ("the program", "130 bytes of code at the end of row 0. it draws everything else", program, False, "top"),
        ("the ether", "rule 110's endless background, wherever the program hasn't reached", ~reached, False, "in"),
        ("the light cone", "everywhere the program has reached so far", cone, False, "in"),
        (
            "the cone, wrapped around",
            "the same influence, back on the left. its stripes are gliders",
            reached & ~cone,
            False,
            "in",
        ),
        (
            "out of step",
            "the program's last 14 bytes are ether, laid down 12 cells out of phase",
            corner,
            False,
            "corner",
        ),
        (
            "false calm",
            f"{int((reached & dark & ~corner).sum())} reached pixels that happen to look untouched",
            reached & dark & ~corner,
            True,
            None,
        ),
        (
            "the boot signature",
            f"55 AA is a shade of orange, used {int((px == 0x72).sum())} times",
            px == 0x72,
            True,
            None,
        ),
        (
            "the bootloader",
            f"pixels in the {len(code)} colours that are also code",
            np.isin(px, list(code)),
            True,
            None,
        ),
    ]


GUIDE_STYLE = ".spot,.rings{opacity:0}.item{outline:none;cursor:default}.item>rect{fill:#ffe7a0;fill-opacity:0}"
GUIDE_LIT = (
    "svg:has(.g{k}:hover,.g{k}:focus) .spot{k},svg:has(.g{k}:hover,.g{k}:focus) .rings{k}{{opacity:1}}"
    "svg:has(.g{k}:hover,.g{k}:focus) .item.g{k}>rect{{fill-opacity:1}}"
    "svg:has(.g{k}:hover,.g{k}:focus) .marker.g{k} circle{{fill:#ffe7a0;stroke-width:1.4}}"
)


def pixels_of(svg):
    """the svg with each embedded png replaced by a digest of its decoded pixels."""

    def digest(m):
        image = Image.open(io.BytesIO(base64.b64decode(m.group(1)))).convert("RGBA")
        return hashlib.sha256(image.tobytes()).hexdigest()

    return re.sub(r"data:image/png;base64,([A-Za-z0-9+/=]+)", digest, svg)


def write_svg(path, svg):
    # pillow and zlib versions compress the same pixels differently; rewrite only a real change
    if os.path.exists(path) and pixels_of(Path(path).read_text()) == pixels_of(svg):
        return
    Path(path).write_text(svg)


def fieldguide():
    t = Type()
    found = regions()
    image = Image.open(BMP)
    x0, y0, width = 20, 40, 320 * S
    o, style = [], [GUIDE_STYLE]
    o.append(
        f'<image x="{x0}" y="{y0}" width="{width}" height="{200 * S}" href="{png_uri(image)}" '
        'style="image-rendering:pixelated" image-rendering="optimizeSpeed"/>'
    )
    for k, (_, _, mask, ring, _) in enumerate(found, 1):
        o.append(
            f'<image class="spot spot{k}" x="{x0}" y="{y0}" width="{width}" height="{200 * S}" '
            f'href="{png_uri(spotlight(mask))}" style="image-rendering:pixelated" image-rendering="optimizeSpeed"/>'
        )
        # rings help only where pixels are sparse; past a few hundred the spotlight alone is clearer
        if ring and mask.sum() <= 400:
            ys, xs = np.nonzero(mask)
            circles = "".join(
                f'<circle cx="{x0 + (x + 0.5) * S:.1f}" cy="{y0 + (y + 0.5) * S:.1f}" r="4.5"/>'
                for y, x in zip(ys, xs, strict=True)
            )
            o.append(f'<g class="rings rings{k}" fill="none" stroke="#000" stroke-width="1.2">{circles}</g>')
        style.append(GUIDE_LIT.format(k=k))

    def badge(cx, cy, k, cls):
        return (
            f'<g class="{cls} g{k}" tabindex="0"><circle cx="{cx:.1f}" cy="{cy:.1f}" r="11" fill="#fff" '
            f'stroke="#000" stroke-width="1"/>{t.text(cx, cy + 4.8, str(k), "cmr10", 14, "middle")}</g>'
        )

    for k, (_, _, mask, _, marker) in enumerate(found, 1):
        if marker == "top":  # a bracket over the program, above the picture
            xa, xb = x0 + 190 * S, x0 + 320 * S
            o.append(f'<path d="M{xa} {y0 - 3}V{y0 - 9}H{xb}V{y0 - 3}" fill="none" stroke="#000" stroke-width="0.8"/>')
            o.append(badge((xa + xb) / 2, y0 - 22, k, "marker"))
        elif marker == "corner":  # beside the triangle, pointing at it
            ys, xs = np.nonzero(mask)
            cx, cy = x0 + xs.mean() * S, y0 + ys.mean() * S
            o.append(badge(cx - 34, cy + 22, k, "marker"))
            o.append(
                f'<path d="M{cx - 27:.1f} {cy + 16:.1f}L{cx - 4:.1f} {cy + 2:.1f}" stroke="#000" stroke-width="0.8"/>'
            )
        elif marker == "in":
            x, y = interior(mask)
            o.append(badge(x0 + (x + 0.5) * S, y0 + (y + 0.5) * S, k, "marker"))

    # the legend, two columns under the picture
    yl, lead, col = y0 + 200 * S + 42, 46, width / 2
    for k, (name, what, _, ring, _) in enumerate(found, 1):
        cx = x0 + (col if k > (len(found) + 1) // 2 else 0)
        y = yl + ((k - 1) % ((len(found) + 1) // 2)) * lead
        icon = (
            f'<circle cx="{cx + 11:.1f}" cy="{y - 5:.1f}" r="6.5" fill="none" stroke="#000" stroke-width="1.4"/>'
            if ring
            else f'<circle cx="{cx + 11:.1f}" cy="{y - 5:.1f}" r="11" fill="#fff" stroke="#000" stroke-width="1"/>'
            + t.text(cx + 11, y - 0.2, str(k), "cmr10", 14, "middle")
        )
        assert t.width(what, "cmr10", 13) < col - 44, f"legend line too long for its column: {what}"
        body = t.text(cx + 32, y, name, "cmb10", 15) + t.text(cx + 32, y + 19, what, "cmr10", 13, fill=GREY)
        o.append(
            f'<g class="item g{k}" tabindex="0"><rect x="{cx - 4:.1f}" y="{y - 20:.1f}" width="{col - 8:.1f}" '
            f'height="{lead - 2}"/>{icon}{body}</g>'
        )
    rows = (len(found) + 1) // 2
    ycap = yl + rows * lead + 16
    cap, n = t.wrap(
        x0,
        ycap,
        width,
        [
            ("figure 1.", "cmb10"),
            (" ", "cmr10"),
            ("fixpoint.bmp", "cmtt10"),
            (
                " at three times its size, and a field guide to what's in it. every region is computed from the "
                "pixels: a pixel counts as reached if it differs from the same rule run on the ether alone. "
                "numbered regions are areas; ringed ones are scattered pixels.",
                "cmr10",
            ),
        ],
        size=14,
        leading=19,
    )
    o.append(cap)
    W, H = width + 2 * x0, ycap + n * 19 + 6
    defs = "".join(f'<path id="{gid}" d="{d}"/>' for gid, d in sorted(t.defs.items()))
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
        f'viewBox="0 0 {int(W)} {int(H)}" width="{int(W)}" height="{int(H)}">\n'
        "<title>figure 1: fixpoint.bmp at three times its size, with a field guide to the program, the ether, "
        "the light cone and the details hidden in it</title>\n"
        f"<style>{''.join(style)}</style>\n"
        f'<rect width="100%" height="100%" fill="#fff"/>\n<defs>{defs}</defs>\n' + "\n".join(o) + "\n</svg>\n"
    )
    write_svg(GUIDE, svg)
    print(f"{GUIDE}: {len(found)} regions, {len(svg) // 1024} KB")


if __name__ == "__main__":
    fieldguide()
    anatomy()
    preview()
    icons()
    social()
