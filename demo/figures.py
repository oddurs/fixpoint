"""draw the readme's figures from fixpoint.bmp itself.

docs/preview.png  the image, scaled 3x with no smoothing.
docs/anatomy.svg  figure 1: the boot sector read as a bmp palette, with the path
                  the cpu takes through it.

the path is not taken from build.py. it is traced from fixpoint.bmp: start at
byte 0, disassemble one instruction at a time with ndisasm, follow every
`jmp short`, stop at the far jump into the pixels.

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
    """the instructions the cpu executes, in order, as (offset, length, text)."""
    path, off = [], 0
    for _ in range(200):
        n, text = one_instruction(off)
        path.append((off, n, text))
        if text.startswith("jmp short"):
            off = int(text.split()[-1], 16) - 0x7C00
        elif text.startswith("jmp") and ":" in text:
            return path
        else:
            off += n
    raise RuntimeError("no far jump found")


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


# ------------------------------------------------------------------ figure 1

INK, GREY, RULE = "#000", "#555", 0.6
COLS, EW, EH = 16, 40, 24                 # palette entries per row, entry width and height
X0, Y_HEAD, HH = 104, 70, 22              # left edge of the grid, top and height of the header strip
HB = COLS * EW / PAL                      # width of one header byte
Y_GRID = Y_HEAD + 112
ROWS = 8                                  # entries 00-7F; the boot sector ends inside 72


def byte_xy(off):
    """centre of a byte in the figure."""
    if off < PAL:
        return X0 + (off + 0.5) * HB, Y_HEAD + 16
    e, ch = divmod(off - PAL, 4)
    r, c = divmod(e, COLS)
    return X0 + c * EW + (ch + 0.5) * EW / 4, Y_GRID + r * EH + EH / 2


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


def anatomy():
    t = Type()
    path = trace()
    o = []
    W = X0 + COLS * EW + 196
    line = lambda x1, y1, x2, y2, w=RULE, c=INK, extra="": o.append(
        '<path d="M%.2f %.2fL%.2f %.2f" stroke="%s" stroke-width="%s" fill="none"%s/>'
        % (x1, y1, x2, y2, c, w, extra))

    # --- (a) the header
    o.append(t.runs(X0, Y_HEAD - 34, [("(a)", "cmb10"), ("  Headers, bytes 0–53", "cmr10")], 11))
    executed = {b for off, n, _ in path for b in range(off, off + n)}
    for off in range(PAL):
        x = X0 + off * HB
        o.append('<rect x="%.2f" y="%d" width="%.2f" height="%d" fill="#fff" stroke="#999" stroke-width="0.35"/>'
                 % (x, Y_HEAD, HB, HH))
        if off in executed:
            o.append(t.text(x + HB / 2, Y_HEAD + 8.6, "%02X" % data[off], "cmtt10", 6.6, "middle"))
    fields = [(0, 2, "bfType"), (2, 6, "bfSize"), (6, 10, "reserved"), (10, 14, "bfOffBits"),
              (14, 54, "BITMAPINFOHEADER: 320 × 200, top-down, 8 bits per pixel, 256 colours")]
    for a, b, label in fields:
        x1, x2 = X0 + a * HB, X0 + b * HB
        o.append('<rect x="%.2f" y="%d" width="%.2f" height="%d" fill="none" stroke="%s" stroke-width="%s"/>'
                 % (x1, Y_HEAD, x2 - x1, HH, INK, RULE))
        face = "cmtt10" if label.startswith("bf") else "cmr10"
        if b - a <= 4:                                     # small fields: named above the strip
            o.append(t.text((x1 + x2) / 2, Y_HEAD - 6, label, face, 8, "middle", GREY))
        else:                                              # the info header: bracketed below
            y = Y_HEAD + HH + 17
            line(x1 + 1, y, x1 + 1, y + 3)
            line(x2 - 1, y, x2 - 1, y + 3)
            line(x1 + 1, y + 3, x2 - 1, y + 3)
            o.append(t.text((x1 + x2) / 2, y + 15, label, face, 8.6, "middle", GREY))
    for off in (0, 2, 6, 10, 14, 54):
        x = X0 + off * HB
        line(x, Y_HEAD + HH, x, Y_HEAD + HH + 3)
        o.append(t.text(x, Y_HEAD + HH + 11, str(off), "cmr10", 7.2, "middle", GREY))

    # --- (b) the palette
    yb = Y_GRID - 30
    o.append(t.runs(X0, yb, [("(b)", "cmb10"), ("  Palette, bytes 54–511", "cmr10")], 11))
    for c in range(COLS):
        o.append(t.text(X0 + c * EW + EW / 2, Y_GRID - 7, "%X" % c, "cmtt10", 8.6, "middle", GREY))
    o.append(t.text(X0 - 38, Y_GRID - 7, "entry", "cmr10", 8.6, "middle", GREY))
    o.append(t.text(X0 - 10, Y_GRID - 7, "byte", "cmr10", 8.6, "end", GREY))
    last = (SECTOR - 1 - PAL) // 4                        # 0x72: the last entry the sector reaches
    for r in range(ROWS):
        y = Y_GRID + r * EH
        o.append(t.text(X0 - 38, y + EH / 2 + 3, "%X0" % r, "cmtt10", 8.6, "middle", GREY))
        o.append(t.text(X0 - 10, y + EH / 2 + 3, str(PAL + 4 * COLS * r), "cmr10", 8.6, "end", GREY))
        for c in range(COLS):
            e = r * COLS + c
            x = X0 + c * EW
            beyond = e > last
            o.append('<rect x="%d" y="%d" width="%d" height="%d" fill="%s" fill-opacity="%s" '
                     'stroke="#fff" stroke-width="0.8"/>' % (x, y, EW, EH, rgb(e), "0.28" if beyond else "1"))
    o.append('<rect x="%d" y="%d" width="%d" height="%d" fill="none" stroke="%s" stroke-width="%s"/>'
             % (X0, Y_GRID, COLS * EW, ROWS * EH, INK, RULE))

    # the end of the boot sector: byte 512 falls between green and red of entry 72
    x512, y512 = byte_xy(SECTOR)
    xs = x512 - EW / 8
    line(xs, y512 - EH / 2 - 5, xs, y512 + EH / 2 + 5, 1.1)
    o.append(t.text(xs, y512 + EH / 2 + 16, "byte 512: end of the boot sector", "cmr10", 8.6, "middle", GREY))

    # the boot sector's demands, outlined
    for off in STATUS:
        x, y = byte_xy(off)
        o.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="none" stroke="%s" stroke-width="1.1"/>'
                 % (x - EW / 8, y - EH / 2, EW / 4, EH, INK))
    x, y = byte_xy(510)
    o.append('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="none" stroke="%s" stroke-width="1.1"/>'
             % (x - EW / 8, y - EH / 2, EW / 2, EH, INK))

    # --- the path the cpu takes
    pts = [(b, byte_xy(b)) for off, n, _ in path for b in range(off, off + n)]
    d, labels = "", []
    for i, (b, (x, y)) in enumerate(pts):
        if i == 0:
            d += "M%.2f %.2f" % (x, y)
            continue
        pb, (px, py) = pts[i - 1]
        if b == pb + 1 and abs(y - py) < 1:
            d += " L%.2f %.2f" % (x, y)
        elif b == pb + 1:                                  # wrapping to the next row
            d += " C%.2f %.2f %.2f %.2f %.2f %.2f" % (px + 14, py, x - 14, y, x, y)
        elif pb < PAL:                                     # out of the header: leave and land vertically,
            ye = Y_GRID - 15                               # dropping between two column labels
            k = (ye - py) * 0.6
            d += " C%.2f %.2f %.2f %.2f %.2f %.2f L%.2f %.2f" % (px, py + k, x, ye - k, x, ye, x, y - 3)
            labels.append((x, y - 3, 0, 1))
        else:                                              # a hop within the palette
            k = max(36, abs(x - px) * 0.32)
            d += " C%.2f %.2f %.2f %.2f %.2f %.2f" % (px + k, py, x - k, y, x, y)
            labels.append((x - 2.2, y, x - (x - k), 0))
    o.append('<path d="%s" fill="none" stroke="#fff" stroke-width="3.2" stroke-linejoin="round"/>' % d)
    o.append('<path d="%s" fill="none" stroke="%s" stroke-width="0.9" stroke-linejoin="round"/>' % (d, INK))
    for b, (x, y) in pts:
        o.append('<circle cx="%.2f" cy="%.2f" r="1.55" fill="#fff" stroke="%s" stroke-width="0.6"/>' % (x, y, INK))
    for x, y, dx, dy in labels:
        o.append(arrowhead(x, y, dx, dy))
    # the far jump out of the boot sector
    ex, ey = pts[-1][1]
    xr = X0 + COLS * EW
    o.append('<path d="M%.2f %.2fL%.2f %.2f" stroke="#fff" stroke-width="3.2"/>' % (ex + 3, ey, xr + 18, ey))
    line(ex + 3, ey, xr + 18, ey, 0.9)
    o.append(arrowhead(xr + 22, ey, 1, 0))

    # --- annotations in the right margin
    ax = xr + 30

    def note(y, runs, size=8.6):
        o.append(t.runs(ax, y, runs, size, GREY))

    seg, offs = (int(v, 16) for v in path[-1][2].split()[-1].split(":"))
    note(ey - 4, [("jmp %04X:%04X" % (seg, offs), "cmtt10")])
    note(ey + 8, [("into the pixels: row 0, x = %d" % ((offs - 0x8000 - PIX) % 320), "cmr10")])
    x, y = byte_xy(STATUS[-1])
    line(x + EW / 8, y, ax - 4, y, 0.4, GREY)
    note(y - 6, [("partition status bytes,", "cmr10")])
    note(y + 6, [("blue channels set to ", "cmr10"), ("80", "cmtt10")])
    x, y = byte_xy(511)
    line(x + EW / 8, y, ax - 4, y, 0.4, GREY)
    note(y + 3, [("boot signature ", "cmr10"), ("55 AA", "cmtt10"), (",", "cmr10")])
    note(y + 15, [("blue and green of entry ", "cmr10"), ("72", "cmtt10")])

    # --- the caption
    jumps = [(off, txt) for off, n, txt in path if txt.startswith("jmp short")]
    code = sum(n for off, n, _ in path if off >= PAL)
    touched = len({(b - PAL) // 4 for b, _ in pts if b >= PAL})
    yc = Y_GRID + ROWS * EH + 50
    cap, n = t.wrap(X0 - 66, yc, W - (X0 - 66) - 24, [
        ("Figure 1.", "cmb10"),
        (" The first 512 bytes of ", "cmr10"), ("fixpoint.bmp", "cmtt10"),
        (". (a)\u00a0The headers. The CPU starts at byte 0: ", "cmr10"), ("BM", "cmtt10"),
        (" executes as ", "cmr10"), ("inc dx; dec bp", "cmtt10"), (", and the low bytes of ", "cmr10"),
        ("bfSize", "cmtt10"), (", ", "cmr10"), ("EB %02X" % data[3], "cmtt10"),
        (", are a short jump into the palette. (b)\u00a0The palette, one swatch per entry, drawn in its "
         "own colour; faded swatches lie beyond the boot sector. The line is the path the CPU "
         "takes, obtained by disassembling the file from byte 0 and following each jump: %d "
         "instructions, %d bytes of code in %d palette entries, and %d short jumps over entries "
         "the bootloader leaves alone. Outlined: the four partition status bytes and the boot "
         "signature, which the disk format fixes and the palette absorbs."
         % (len(path), code, touched, len(jumps) - 1), "cmr10"),
    ], size=10, leading=13.5)
    o.append(cap)
    H = yc + n * 13.5 + 14

    defs = "".join('<path id="%s" d="%s"/>' % (gid, d) for gid, d in sorted(t.defs.items()))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
           'viewBox="0 0 %d %d" width="%d" height="%d">\n'
           '<rect width="100%%" height="100%%" fill="#fff"/>\n<defs>%s</defs>\n%s\n</svg>\n'
           % (W, H, W * 1.2, H * 1.2, defs, "\n".join(o)))
    open(OUT, "w").write(svg)
    print(f"{OUT}: {len(path)} instructions traced, {code} bytes of code in {touched} palette entries, "
          f"{len(jumps) - 1} hops")


def preview():
    image = Image.open(BMP).convert("RGB")
    image.resize((3 * image.width, 3 * image.height), Image.NEAREST).save(PREVIEW)


if __name__ == "__main__":
    anatomy()
    preview()
