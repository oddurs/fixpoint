"""build fixpoint.bmp: a 320x200 bmp whose pixels are a rule 110 universe seeded by
the machine code that computes it. boot the file and it recomputes itself.

  offset  as a bmp                     as x86 / as a disk
  0       "BM"                         inc dx ; dec bp
  2       file size, EB xx 01 00       jmp short into the palette
  10      pixel offset = 1078
  14      info header (top-down)       (bios may patch 11..61 as a floppy bpb; nothing lives there)
  54      palette, 256 x BGRx          the stub, woven between colours
  446     palette entries 98..113      the partition table: status bytes are a valid 0x80
  510     palette entry 0x72           55 AA, the boot signature
  1078    pixels                       row 0 ends with the program
  65078   padding, then a zip          the source, so `unzip fixpoint.bmp` works

usage: python3 build.py   (needs nasm and numpy). writes fixpoint.bmp and stub.asm.
"""
import io, os, struct, subprocess, tempfile, zipfile
from functools import lru_cache

import numpy as np

W, H = 320, 200
PAL, PIX = 54, 1078                  # palette and pixel offsets
LOAD = 0x8000                        # the stub loads the first sectors here
MBR_STATUS = (446, 462, 478, 494)    # partition status bytes: must be 0x00 or 0x80
BPB_END = 62                         # bios floppy emulation may rewrite bytes 11..61
SIGNATURE = 510                      # 55 AA
SOURCES = ("main.asm", "stub.asm", "build.py")


# ------------------------------------------------------------------ assembling

def nasm(source, **defines):
    with tempfile.TemporaryDirectory() as tmp:
        src, out = os.path.join(tmp, "in.asm"), os.path.join(tmp, "out.bin")
        with open(src, "w") as f:
            f.write(source)
        subprocess.run(["nasm", "-f", "bin", src, "-o", out]
                       + ["-D%s=%d" % kv for kv in defines.items()], check=True)
        return open(out, "rb").read()


@lru_cache(maxsize=None)
def encode(lines):
    """bytes for a short run of 16-bit instructions (position-independent ones only)."""
    return nasm("bits 16\n" + lines + "\n")


def build_main():
    """assemble main.asm so it ends exactly at the end of row 0."""
    src = open("main.asm").read()
    n = len(nasm(src, ORG=LOAD, X0=0))
    x0 = W - n
    org = LOAD + PIX + x0
    code = nasm(src, ORG=org, X0=x0)
    assert len(code) == n
    return code, x0, org


# ------------------------------------------------------------------ the picture

ETHER_LEN = 14                       # main.asm ends with one period of the ether
LIGHT = 6                            # the universe whose life sets the light


def universe(program, x0):
    """exactly what main.asm computes: row 0 is the ether then the program, and each
    cell after 320 is rule 110 of the cells 321, 320 and 319 places back."""
    ether = program[-ETHER_LEN:]
    m = np.zeros(W * H, np.uint8)
    m[:x0] = np.resize(np.frombuffer(ether, np.uint8), x0)
    m[x0:W] = np.frombuffer(program, np.uint8)
    rule = lambda l, c, r: (c | r) & ~(l & c & r)
    for y in range(1, H):
        i = W * y + (1 if y == 1 else 0)          # cell 320 has no left neighbour; it stays 0
        j = W * y + W - 1                         # the last cell's right neighbour is in this row
        m[i:j] = rule(m[i - W - 1:j - W - 1], m[i - W:j - W], m[i - W + 1:j - W + 1])
        m[j] = rule(m[j - W - 1], m[j - W], m[j - W + 1])
    return bytes(m)


def palette():
    """the picture's meaning is in its palette.

    row 0 starts out the same in all eight universes except where the program is, so
    a cell where all eight agree (00 or FF) is one the program has not reached: the
    ether, drawn as two close, quiet shades. a cell where they disagree is in the
    program's causal future: universe 6 decides whether it is light or dark there,
    and the other seven decide its hue."""
    def mix(a, b, t):
        return [round(a[k] + (b[k] - a[k]) * t) for k in range(3)]

    pal = []
    for v in range(256):
        if v in (0x00, 0xFF):
            pal.append([10, 12, 22] if v == 0 else [22, 26, 46])
            continue
        others = bin(v & ~(1 << LIGHT) & 0xFF).count("1") / 7
        if v >> LIGHT & 1:
            pal.append(mix((255, 120, 96), (255, 214, 140), others))   # alive: coral to gold
        else:
            pal.append(mix((58, 44, 120), (150, 70, 140), others))     # dead: indigo to plum
    # the boot sector's demands. bit 6 is set in all five entries, so each is already a
    # warm colour, and the changes are small:
    pal[0x72][1:] = [0xAA, 0x55]                     # 55 AA, the signature: blue and green
    for off in MBR_STATUS:                           # partition status: blue must be 00 or 80
        e = (off - PAL) // 4
        pal[e][2] = 0x80 if pal[e][2] >= 0x40 else 0x00
    return pal


# ------------------------------------------------------------------ the stub
#
# the stub's bytes are palette colours, so where they go matters. it is a list of
# units (instructions, or a block that must stay contiguous). between units we may
# put a harmless one-byte filler, or `jmp short` over palette bytes we'd rather
# leave alone. a dynamic program over (units placed, position) finds the layout
# whose bytes, read as colours, disturb the picture least: the cost of a byte is
# its squared distance from the colour channel it replaces, weighted by how many
# pixels use that colour. the bios jumps in from offset 2, so the stub starts
# within reach of a short jump, and after the bpb.

FILLERS = ["nop", "cld", "clc", "stc", "cmc", "inc si", "inc di", "inc bp", "dec si", "dec di"]


def stub_units(main_org):
    es = [("push byte 0", "pop es"), ("xor ax, ax", "mov es, ax")]
    read = ["read: mov ax, 0x0203\nint 0x13\njc read",           # retry until the read works
            "read: mov ah, 2\nmov al, 3\nint 0x13\njc read"]
    free = ["dec dx",                                            # "B" was inc dx: restore the drive
            "mov bx, 0x%04X" % LOAD, "mov cx, 0x0001", "mov dh, 0"]
    jump = "jmp 0x0000:0x%04X" % main_org
    for e in es:
        for r in read:
            # units in `free` + e may go in any order (e[0] before e[1]); then read, then jump
            yield list(free) + list(e), (r, jump)


def place_stub(pal, hist, main_org):
    N = SIGNATURE + 1
    allowed = np.array([BPB_END <= o < SIGNATURE and o not in MBR_STATUS for o in range(N)])
    C = np.zeros((N, 256))                   # C[off, b]: cost of byte b at file offset off
    for off in range(PAL, N):
        e, ch = divmod(off - PAL, 4)
        if ch < 3:
            C[off] = hist[e] * (np.arange(256) - pal[e][2 - ch]) ** 2
    C[~allowed] = np.inf

    fill = {f: encode(f)[0] for f in FILLERS}
    fnames = list(fill)
    fcost = np.stack([C[:, fill[f]] for f in fnames])   # (fillers, N)
    fbest, fpick = fcost.min(0), fcost.argmin(0)
    D = np.arange(1, 128)
    hop = np.full((N, 127), np.inf)                     # hop[p, d-1]: cost of `jmp short d` at p
    for p in range(N - 1):
        hop[p] = C[p, 0xEB] + C[p + 1, D]

    best = None
    for movable, tail in stub_units(main_org):
        units = movable + list(tail)
        enc = [encode(u) for u in units]
        k, T = len(movable), len(tail)
        full = (1 << k) - 1
        must = {k - 1: k - 2}                           # pop es / mov es after its partner
        ucost = np.full((len(units), N), np.inf)        # ucost[i, p]: unit i placed at p
        for i, code in enumerate(enc):
            for p in range(N - len(code)):
                ucost[i, p] = sum(C[p + j, b] for j, b in enumerate(code))

        K = (1 << k) * (T + 1)
        key = lambda mask, t: mask * (T + 1) + t
        dp = np.full((K, N), np.inf)
        back = {}                                       # (key, p) -> (prev key, prev p, move)
        for s in range(BPB_END, min(PAL + 4 * 32, N)):  # within `jmp short` reach of offset 2
            if s - 4 <= 127 and allowed[s]:
                dp[key(0, 0), s] = 0
                back[key(0, 0), s] = (None, None, ("start", s))

        for p in range(BPB_END, N):
            for kk in np.nonzero(np.isfinite(dp[:, p]))[0]:
                c = dp[kk, p]
                mask, t = divmod(int(kk), T + 1)
                if t == T:
                    continue
                if p + 1 < N and c + fbest[p] < dp[kk, p + 1]:
                    dp[kk, p + 1] = c + fbest[p]
                    back[kk, p + 1] = (kk, p, ("fill", fnames[fpick[p]]))
                q1, q2 = p + 3, min(p + 130, N)
                if q1 < q2:
                    cand = c + hop[p, :q2 - q1]
                    better = np.nonzero(cand < dp[kk, q1:q2])[0]
                    for j in better:
                        dp[kk, q1 + j] = cand[j]
                        back[kk, q1 + j] = (kk, p, ("hop", int(j) + 1))
                nxt = ([i for i in range(k) if not mask >> i & 1 and (i not in must or mask >> must[i] & 1)]
                       if mask != full else [k + t])
                for i in nxt:
                    q = p + len(enc[i])
                    if q >= N or not np.isfinite(ucost[i, p]):
                        continue
                    k2 = key(mask | 1 << i, t) if i < k else key(mask, t + 1)
                    if c + ucost[i, p] < dp[k2, q]:
                        dp[k2, q] = c + ucost[i, p]
                        back[k2, q] = (kk, p, ("unit", i))
        end_key = key(full, T)
        q = int(np.argmin(dp[end_key]))
        if np.isfinite(dp[end_key, q]) and (best is None or dp[end_key, q] < best[0]):
            best = (float(dp[end_key, q]), (end_key, q), back, units, enc)

    c, st, back, units, enc = best
    moves = []
    while True:
        pk, pp, move = back[st]
        if pk is None:
            start = move[1]
            break
        moves.append(move)
        st = (pk, pp)
    return c, start, list(reversed(moves)), units, enc, fill


def lay_out(pal, start, moves, units, enc, fill):
    """the stub's bytes, the palette bytes it hops over, and stub.asm."""
    image = bytearray(4 * 256)
    for i, (r, g, b) in enumerate(pal):
        image[4 * i:4 * i + 4] = bytes((b, g, r, 0))

    out, asm, p, label = {}, [], start, 0
    for kind, arg in moves:
        if kind == "fill":
            out[p] = fill[arg]
            asm.append("    %-24s; filler, for its colour" % arg)
            p += 1
        elif kind == "hop":
            label += 1
            out[p], out[p + 1] = 0xEB, arg
            skipped = image[p + 2 - PAL:p + 2 + arg - PAL]
            asm.append("    %-24s; hop over %d palette bytes" % ("jmp short .h%d" % label, arg))
            asm.append("    db " + ", ".join("0x%02X" % b for b in skipped))
            asm.append(".h%d:" % label)
            p += 2 + arg
        else:
            code = enc[arg]
            for j, b in enumerate(code):
                out[p + j] = b
            for line in units[arg].split("\n"):
                asm.append(("%s" if line.endswith(":") or line.startswith("read:") else "    %s")
                           % line.replace("read: ", "read:\n    "))
            p += len(code)
    end = p
    header = ("; stub.asm, generated by build.py: the bootloader, woven into the bmp palette.\n"
              "; the bios jumps here from offset 2. it reads the first three sectors to 0000:%04X\n"
              "; and jumps into the pixels. its bytes are palette colours, so its layout (order,\n"
              "; encodings, fillers, hops) was chosen to disturb the picture least.\n"
              "bits 16\norg 0x%04X\n\n" % (LOAD, 0x7C00 + start))
    return out, end, header + "\n".join(asm) + "\n"


# ------------------------------------------------------------------ the file

def source_zip(prefix_len):
    buf = io.BytesIO()
    buf.write(b"\0" * prefix_len)
    with zipfile.ZipFile(buf, "a", zipfile.ZIP_STORED) as z:
        for name in SOURCES:
            info = zipfile.ZipInfo("fixpoint/" + name, date_time=(1980, 1, 1, 0, 0, 0))
            info.external_attr = 0o644 << 16
            z.writestr(info, open(name, "rb").read())
    return buf.getvalue()[prefix_len:]


def main():
    program, x0, main_org = build_main()
    m = universe(program, x0)
    hist = np.bincount(np.frombuffer(m, np.uint8), minlength=256).tolist()

    pal = palette()
    clash, start, moves, units, enc, fill = place_stub(pal, hist, main_org)
    stub, stub_end, stub_asm = lay_out(pal, start, moves, units, enc, fill)
    open("stub.asm", "w").write(stub_asm)

    size = 0x10000 + ((start - 4) << 8) + 0xEB          # bytes EB, start-4, 01, 00
    f = bytearray(size)
    f[0:14] = b"BM" + struct.pack("<IHHI", size, 0, 0, PIX)
    f[14:PAL] = struct.pack("<IiiHHIIiiII", 40, W, -H, 1, 8, 0, W * H, 2835, 2835, 256, 0)
    for i, (r, g, b) in enumerate(pal):
        f[PAL + 4 * i:PAL + 4 * i + 4] = bytes((b, g, r, 0))
    for off, b in stub.items():
        f[off] = b
    f[PIX:PIX + W * H] = m

    zipped = source_zip(0)
    assert PIX + W * H + len(zipped) <= size, "source zip doesn't fit in the padding"
    f[size - len(zipped):] = source_zip(size - len(zipped))

    # the claims, checked
    assert f[2] == 0xEB and 4 + f[3] == start
    assert f[6:10] == bytes(4)                                   # reserved fields are zero
    assert f[SIGNATURE:SIGNATURE + 2] == b"\x55\xAA"
    assert all(f[o] in (0x00, 0x80) for o in MBR_STATUS)
    assert all(off >= BPB_END for off in stub)
    assert nasm(stub_asm) == bytes(f[start:stub_end])           # stub.asm is the truth
    assert PIX + W <= 3 * 512                                    # the program is in what's loaded
    open("fixpoint.bmp", "wb").write(f)

    changed = [e for e in range(256)
               if tuple(f[PAL + 4 * e:PAL + 4 * e + 3]) != tuple(reversed(pal[e]))]
    px = sum(hist[e] for e in changed)
    print(f"fixpoint.bmp: {size} bytes | program {len(program)} B, row 0 x={x0}..319 | "
          f"stub {len(stub)} B between offsets {start} and {stub_end - 1}, shifting "
          f"{len(changed)} colours ({px} px, {px / 640:.2f}% of the image)")


if __name__ == "__main__":
    main()
