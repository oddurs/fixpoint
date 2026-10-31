"""draw anatomy.svg: the boot sector as the palette it lives in, with the path the
cpu takes through it.

the path is not taken from build.py. it is traced from fixpoint.bmp itself: start
at byte 0, disassemble one instruction at a time with ndisasm, follow every
`jmp short`, stop at the far jump into the pixels.

usage: python3 demo/anatomy.py   (from the repo root; needs nasm's ndisasm and pillow)
"""
import re, subprocess
from PIL import Image

BMP, OUT = "fixpoint.bmp", "anatomy.svg"
PAL, SECTOR = 54, 512
data = open(BMP, "rb").read()
palette = Image.open(BMP).getpalette()


def one_instruction(off):
    out = subprocess.run(["ndisasm", "-b16", "-o%d" % (0x7C00 + off), "-"],
                         input=data[off:off + 16], capture_output=True, check=True).stdout
    addr, hexbytes, text = out.decode().splitlines()[0].split(None, 2)
    return len(hexbytes) // 2, text.strip()


def trace():
    """the bytes the cpu executes, in order, as (offset, instruction) runs."""
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


# ------------------------------------------------------------------ geometry
COLS, CELL_W, CELL_H, GAP = 16, 54, 34, 4
SLOT = CELL_W / 4
X0, Y_HEAD, Y_GRID = 56, 132, 228
HEAD_W = (COLS * (CELL_W + GAP) - GAP) / PAL          # header bytes share the grid's width
ROWS = (SECTOR - PAL + 3) // 4 // COLS + 1            # entries the boot sector reaches


def byte_xy(off):
    """centre of a byte in the figure."""
    if off < PAL:
        return X0 + (off + 0.5) * HEAD_W, Y_HEAD + 14
    e, ch = divmod(off - PAL, 4)
    r, c = divmod(e, COLS)
    return X0 + c * (CELL_W + GAP) + (ch + 0.5) * SLOT, Y_GRID + r * (CELL_H + GAP) + CELL_H / 2


def rgb(e):
    return "#%02x%02x%02x" % tuple(palette[3 * e:3 * e + 3])


def main():
    path = trace()
    executed = {o for off, n, _ in path for o in range(off, off + n)}
    W = X0 * 2 + COLS * (CELL_W + GAP) - GAP
    H = Y_GRID + ROWS * (CELL_H + GAP) + 96
    ink, muted, accent, line = "#f0f6fc", "#8b949e", "#ffd08a", "#30363d"
    mono = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" '
         f'width="{W:.0f}" height="{H:.0f}" font-family="{mono}">',
         f'<rect width="100%" height="100%" rx="10" fill="#0d1117"/>',
         f'<text x="{X0}" y="44" fill="{ink}" font-size="17" font-weight="700">the boot sector, as the cpu reads it</text>',
         f'<text x="{X0}" y="68" fill="{muted}" font-size="12.5">the first 512 bytes of fixpoint.bmp: the header, then palette entries 00 to 72, '
         f'four bytes each (blue, green, red, unused).</text>',
         f'<text x="{X0}" y="86" fill="{muted}" font-size="12.5">the thread is the path the cpu takes, traced from the file by disassembling it.</text>']

    # the header strip
    o.append(f'<text x="{X0}" y="{Y_HEAD - 10}" fill="{muted}" font-size="11">header, bytes 0–53</text>')
    fields = [(0, 2, "BM", True), (2, 6, "size", True), (6, 10, "reserved", True),
              (10, 14, "offset", True), (14, 54, "info header: 320 × −200, 8 bit, 256 colours", False)]
    for a, b, label, below in fields:
        x = X0 + a * HEAD_W
        o.append(f'<rect x="{x + 1:.1f}" y="{Y_HEAD}" width="{(b - a) * HEAD_W - 2:.1f}" height="28" rx="3" '
                 f'fill="#161b22" stroke="{line}"/>')
        if below:
            o.append(f'<text x="{x + (b - a) * HEAD_W / 2:.1f}" y="{Y_HEAD + 46}" fill="{muted}" '
                     f'font-size="10.5" text-anchor="middle">{label}</text>')
        else:
            o.append(f'<text x="{x + 12:.1f}" y="{Y_HEAD + 18}" fill="{muted}" font-size="11">{label}</text>')

    # the palette grid
    o.append(f'<text x="{X0}" y="{Y_GRID - 10}" fill="{muted}" font-size="11">palette, bytes 54–511</text>')
    last = (SECTOR - 1 - PAL) // 4
    for r in range(ROWS):
        o.append(f'<text x="{X0 - 10}" y="{Y_GRID + r * (CELL_H + GAP) + CELL_H / 2 + 4:.1f}" fill="{muted}" '
                 f'font-size="10.5" text-anchor="end">{r * COLS:02X}</text>')
    for e in range(last + 1):
        r, c = divmod(e, COLS)
        x, y = X0 + c * (CELL_W + GAP), Y_GRID + r * (CELL_H + GAP)
        o.append(f'<rect x="{x}" y="{y}" width="{CELL_W}" height="{CELL_H}" rx="4" fill="{rgb(e)}"/>')
    # partition table and signature
    for off in (446, 462, 478, 494):
        x, y = byte_xy(off)
        o.append(f'<rect x="{x - SLOT / 2 + 1:.1f}" y="{y - CELL_H / 2 + 1:.1f}" width="{SLOT - 2:.1f}" '
                 f'height="{CELL_H - 2}" rx="2" fill="none" stroke="{accent}" stroke-width="1.5"/>')
    sx, sy = byte_xy(510)
    o.append(f'<rect x="{sx - SLOT / 2 + 1:.1f}" y="{sy - CELL_H / 2 + 1:.1f}" width="{2 * SLOT - 2:.1f}" '
             f'height="{CELL_H - 2}" rx="2" fill="none" stroke="{ink}" stroke-width="1.5"/>')

    # the thread: straight through consecutive bytes, arcs over the hops
    pts = []
    for off, n, text in path:
        for b in range(off, off + n):
            pts.append((b, byte_xy(b)))
    d = ""
    for i, (b, (x, y)) in enumerate(pts):
        if i == 0:
            d += f"M{x:.1f},{y:.1f}"
            continue
        pb, (px, py) = pts[i - 1]
        if b == pb + 1 and abs(y - py) < 1:
            d += f" L{x:.1f},{y:.1f}"
        elif b == pb + 1:                               # wrapping to the next row of the grid
            d += f" C{px + 18:.1f},{py:.1f} {x - 18:.1f},{y:.1f} {x:.1f},{y:.1f}"
        else:                                           # a jump: a cable that leaves and lands level
            k = max(40, abs(x - px) * 0.35)
            d += f" C{px + k:.1f},{py:.1f} {x - k:.1f},{y:.1f} {x:.1f},{y:.1f}"
    o.append(f'<path d="{d}" fill="none" stroke="#0d1117" stroke-width="5" stroke-linecap="round" '
             f'stroke-linejoin="round" opacity="0.55"/>')
    o.append(f'<path d="{d}" fill="none" stroke="{ink}" stroke-width="1.6" stroke-linecap="round" '
             f'stroke-linejoin="round"/>')
    for b, (x, y) in pts:
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.6" fill="{ink}"/>')
    ex, ey = pts[-1][1]
    o.append(f'<path d="M{ex:.1f},{ey:.1f} l14,0" stroke="{ink}" stroke-width="1.6"/>'
             f'<path d="M{ex + 14:.1f},{ey - 4:.1f} l6,4 l-6,4" fill="none" stroke="{ink}" stroke-width="1.6"/>')

    # notes
    y = Y_GRID + ROWS * (CELL_H + GAP) + 26
    jumps = sum(1 for _, _, t in path if t.startswith("jmp short")) - 1
    code = sum(n for off, n, _ in path if off >= PAL)
    notes = [
        (ink, f"thread: {len(path)} instructions, {code} bytes in the palette, {jumps} hops over colours it leaves alone"),
        (accent, "gold: the four partition status bytes, blue channels set to 80 so bioses accept the disk"),
        (ink, "white: 55 AA, the boot signature, which is the blue and green of palette entry 0x72"),
    ]
    for i, (colour, text) in enumerate(notes):
        o.append(f'<circle cx="{X0 + 4}" cy="{y + i * 20 - 4}" r="3.5" fill="{colour}"/>'
                 f'<text x="{X0 + 16}" y="{y + i * 20}" fill="{muted}" font-size="11.5">{text}</text>')
    o.append("</svg>")
    open(OUT, "w").write("\n".join(o) + "\n")
    print(f"{OUT}: {len(path)} instructions traced, {code} bytes of code in the palette, {jumps} hops")


if __name__ == "__main__":
    main()
