"""check every claim fixpoint.bmp makes, then boot it.

  as a bmp      pillow, ffmpeg and chrome all decode it to the same pixels
  as a disk     55 AA, legal partition status bytes, a jump into the palette
  as a picture  every row follows from the one above by rule 110, and every
                cell the program hasn't reached is dark
  as an archive the zip in its padding is the source in this repo
  as a program  booted in qemu, video memory holds exactly its 64,000 pixel
                bytes, and the screen shows exactly its colours

needs numpy, pillow and qemu-system-i386. ffmpeg and chrome are checked when installed.
usage: python3 verify.py [fixpoint.bmp]
"""

import io
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

W, H = 320, 200
CHROME = (
    "google-chrome",
    "chromium",
    "chromium-browser",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
)
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  {'ok  ' if ok else 'FAIL'}  {name}{'  ' + detail if detail else ''}")


def skip(name, why):
    print(f"  --    {name}  ({why})")


def boot(path, timeout=30):
    """boot in qemu. once the screen is in mode 13h and has stopped changing, return
    it and the 64,000 bytes of video memory at A000:0000, or (None, None)."""
    tmp = tempfile.mkdtemp()
    sock = os.path.join(tmp, "mon.sock")
    qemu = subprocess.Popen(
        [
            "qemu-system-i386",
            "-drive",
            f"format=raw,file={path},if=ide",
            "-display",
            "none",
            "-monitor",
            f"unix:{sock},server,nowait",
            "-no-reboot",
        ],
        stderr=subprocess.DEVNULL,
    )
    try:
        s = socket.socket(socket.AF_UNIX)
        for _ in range(200):
            try:
                s.connect(sock)
                break
            except OSError:
                time.sleep(0.05)
        s.settimeout(10)

        def monitor(cmd=None):  # send a command, wait for the prompt
            if cmd:
                s.send(cmd.encode() + b"\n")
            buf = b""
            while not buf.rstrip().endswith(b"(qemu)"):
                buf += s.recv(65536)

        monitor()
        prev, n, deadline = None, 0, time.time() + timeout
        while time.time() < deadline:
            shot = os.path.join(tmp, f"{n}.ppm")
            n += 1
            monitor(f'screendump "{shot}"')
            im = Image.open(shot)
            if im.size != (2 * W, 2 * H):  # still in the bios text mode
                time.sleep(0.1)
                continue
            frame = im.convert("RGB").resize((W, H), Image.NEAREST)
            if prev is not None and frame.tobytes() == prev.tobytes():
                vram = os.path.join(tmp, "vram.bin")
                monitor(f'pmemsave 0xA0000 {W * H} "{vram}"')
                return frame, Path(vram).read_bytes()
            prev = frame
            time.sleep(0.25)
        return None, None
    finally:
        qemu.kill()
        qemu.wait()
        shutil.rmtree(tmp)


def rule110(row0):
    """the tape, written independently of build.py: cell i = rule 110 of i-321, i-320, i-319."""
    t = np.zeros(W * H, np.uint8)
    t[:W] = row0
    for i in range(W + 1, W * H):
        left, centre, right = int(t[i - W - 1]), int(t[i - W]), int(t[i - W + 1])
        t[i] = (centre | right) & ~(left & centre & right) & 0xFF
    return t


def cone_edges(reached, p0, p1, gens=100):
    """how far past the program's ends the influence has travelled, generation by generation,
    along the tape. past about generation 100 the cone overlaps itself and edges blur."""
    right, left = np.zeros(gens, int), np.zeros(gens, int)
    for g in range(1, gens):
        base = W * g
        for side, start, step in ((right, p1, 1), (left, p0, -1)):
            gap, d = 0, 0
            while gap < 40 and 0 <= base + start + step * (d + 1) < W * H:
                d += 1
                if reached[base + start + step * d]:
                    side[g], gap = d, 0
                else:
                    gap += 1
    return right, left


def out_of_step(calm, x):
    """reached-but-dark cells connected to the program's last 14 cells (8-way, on the screen)."""
    calm = calm.reshape(H, W)
    seen = np.zeros_like(calm)
    todo = [(0, c) for c in range(x, W) if calm[0, c]]
    for cell in todo:
        seen[cell] = True
    while todo:
        y, c = todo.pop()
        for dy in (-1, 0, 1):
            for dc in (-1, 0, 1):
                yy, cc = y + dy, c + dc
                if 0 <= yy < H and 0 <= cc < W and calm[yy, cc] and not seen[yy, cc]:
                    seen[yy, cc] = True
                    todo.append((yy, cc))
    return seen.reshape(-1)


def chrome_decode(path, tmp):
    exe = next((c for c in CHROME if shutil.which(c)), None)
    if not exe:
        return None
    shutil.copy(path, os.path.join(tmp, "img.bmp"))
    with open(os.path.join(tmp, "v.html"), "w") as f:
        f.write('<!doctype html><body style="margin:0"><img src="img.bmp" style="display:block">')
    shot = os.path.join(tmp, "chrome.png")
    subprocess.run(
        [
            exe,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-color-profile=srgb",
            "--force-device-scale-factor=1",
            f"--window-size={W},{H}",
            f"--screenshot={shot}",
            "file://" + os.path.join(tmp, "v.html"),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=60,
    )
    return Image.open(shot).convert("RGB").crop((0, 0, W, H))


def ffmpeg_decode(path, tmp):
    if not shutil.which("ffmpeg"):
        return None
    out = os.path.join(tmp, "ffmpeg.png")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", path, "-pix_fmt", "rgb24", out], check=True)
    return Image.open(out).convert("RGB")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "fixpoint.bmp"
    data = Path(path).read_bytes()

    print("as a bmp")
    ref = Image.open(path)
    check("pillow decodes 320x200, 8 bit", ref.size == (W, H) and ref.mode == "P")
    size, reserved, offset = struct.unpack("<IIL", data[2:14])
    check("file size field is true", size == len(data), f"{size} bytes")
    check("reserved fields are zero", reserved == 0)
    check("pixels are the bytes at the pixel offset", ref.tobytes() == data[offset : offset + W * H])
    rgb = ref.convert("RGB")
    for name, decode in (("ffmpeg", ffmpeg_decode), ("chrome", chrome_decode)):
        with tempfile.TemporaryDirectory() as tmp:
            im = decode(path, tmp)
        if im is None:
            skip(f"{name} decodes the same pixels", "not installed")
        else:
            check(f"{name} decodes the same pixels", im.tobytes() == rgb.tobytes())

    print("as a disk")
    check("boot signature 55 AA", data[510:512] == b"\x55\xaa")
    status = [data[o] for o in (446, 462, 478, 494)]
    check("partition status bytes are legal", all(s in (0, 0x80) for s in status), " ".join(f"{s:02X}" for s in status))
    check(
        "offset 2, the file size, jumps into the palette",
        data[2] == 0xEB and 62 <= 4 + data[3] < 1078,
        f"EB {data[3]:02X}: jmp short to offset {4 + data[3]}",
    )

    print("as a picture")
    pixels = np.frombuffer(ref.tobytes(), np.uint8)
    check("every row follows from the row above by rule 110", (rule110(pixels[:W]) == pixels).all())
    row0 = pixels[:W]
    x0 = next(x for x in range(14, W) if row0[x] != row0[x - 14])
    check(
        "row 0 is the ether, then the program",
        set(row0[:x0].tolist()) <= {0, 255},
        f"ether x=0..{x0 - 1}, program x={x0}..{W - 1}",
    )
    untouched = rule110(np.resize(row0[:14], W))  # the universe without the program
    reached = pixels != untouched
    agree = np.isin(pixels, [0, 255])
    check("every cell the program hasn't reached is dark", not (~reached & ~agree).any(), f"{(~reached).sum()} cells")
    print(
        f"        the program reaches {reached.sum()} cells ({reached.mean():.1%}); "
        f"{(reached & agree).sum()} of them look dark anyway ({(reached & agree).sum() / reached.sum():.2%})"
    )

    print("as a picture, the page's details")
    colours = len(np.unique(pixels))
    check("every one of the 256 colours appears", colours == 256, f"{colours} colours")
    signature = int((pixels == 0x72).sum())
    check("the boot signature's colour, entry 72, appears 107 times", signature == 107, f"{signature} pixels")
    tail = row0[W - 14 :]
    check(
        "the program ends with one period of the ether, 12 cells out of phase",
        (tail == row0[:14]).all() and (W - 14) % 14 == 12,
    )
    corner = out_of_step(reached & agree, W - 14)
    depth = int(np.nonzero(corner.reshape(H, W).any(axis=1))[0].max()) + 1
    check("under it, a triangle of out-of-step ether 13 rows deep", depth == 13, f"{corner.sum()} cells")
    calm = int((reached & agree & ~corner).sum())
    check("306 reached cells elsewhere happen to look untouched", calm == 306, f"{calm} cells")
    right, left = cone_edges(reached, x0, W - 1)
    gens = np.arange(30, 100)
    vr, vl = np.polyfit(gens, right[30:100], 1)[0], np.polyfit(gens, left[30:100], 1)[0]
    check(
        "the cone's right edge stalls for 30 rows, then spreads at about 0.62 a row, the left at about 0.48",
        right[30] <= 6 and abs(vr - 0.62) < 0.03 and abs(vl - 0.48) < 0.03,
        f"right edge +{right[30]} at row 30; {vr:.3f} right, {vl:.3f} left over rows 30-100",
    )

    print("as an archive")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        names = sorted(info.filename.split("/", 1)[1] for info in z.infolist())
        check(
            "carries exactly main.asm, stub.asm and build.py",
            names == ["build.py", "main.asm", "stub.asm"],
            ", ".join(names),
        )
        for info in z.infolist():
            name = info.filename.split("/", 1)[1]
            same = Path(name).exists() and z.read(info) == Path(name).read_bytes()
            check(f"carries {name}", same, "" if same else "differs from the repo")
    except zipfile.BadZipFile:
        check("carries its source as a zip", False)

    print("as a program")
    screen, vram = boot(path)
    if screen is None:
        check("boots into mode 13h", False)
    else:
        same = sum(a == b for a, b in zip(vram, ref.tobytes(), strict=False))
        check("video memory holds exactly the pixel bytes", same == W * H, f"{same}/{W * H} bytes")
        # the vga dac has 6 bits per channel, so compare colours at the dac's precision
        want = np.array(ref.convert("RGB")) >> 2
        got = np.array(screen) >> 2
        same = int((want == got).all(axis=2).sum())
        check(
            "the screen shows exactly the image's colours",
            same == W * H,
            f"{same}/{W * H} pixels, at the dac's 6 bits per channel",
        )

    print("all claims hold" if all(results) else "SOME CLAIMS FAIL")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
