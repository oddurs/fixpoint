"""record the demo video: real qemu frames of fixpoint.bmp booting.

the bios is captured in real time. the computation takes a fraction of a second,
so it is captured under gdb: a breakpoint on the program's own loop pauses the
machine every two rows, and qemu dumps the screen from there. nothing is rendered
or interpolated: every frame is the real screen of the real machine.

the captions are set in computer modern, from the copies matplotlib ships, like
figure 1.

usage: python3 demo/record.py   (from the repo root; needs qemu-system-i386, gdb,
ffmpeg, pillow, matplotlib). writes site/static/demo.mp4 and site/static/poster.png.
"""

import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path

import matplotlib
from PIL import Image, ImageDraw, ImageFont

BMP = "fixpoint.bmp"
OUT = "site/static"
LOAD = 0x8000  # where the bootloader puts the file
W, H, FPS = 960, 600, 30
CM = os.path.join(os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf")


class Monitor:
    """a qemu monitor on a unix socket: send a command, wait for the next prompt."""

    def __init__(self, path):
        self.s = socket.socket(socket.AF_UNIX)
        for _ in range(200):
            try:
                self.s.connect(path)
                break
            except OSError:
                time.sleep(0.02)
        self.s.settimeout(10)
        self.read()

    def read(self):
        buf = b""
        while not buf.rstrip().endswith(b"(qemu)"):
            buf += self.s.recv(65536)
        return buf

    def __call__(self, cmd):
        self.s.send(cmd.encode() + b"\n")
        return self.read()


def capture_boot(step=0.1, limit=600):
    """the bios, in real time: screendumps until the program switches to mode 13h."""
    tmp = tempfile.mkdtemp()
    sock = os.path.join(tmp, "mon.sock")
    qemu = subprocess.Popen(
        [
            "qemu-system-i386",
            "-drive",
            f"format=raw,file={BMP},if=ide",
            "-display",
            "none",
            "-monitor",
            f"unix:{sock},server,nowait",
            "-no-reboot",
            "-icount",
            "shift=10,align=on,sleep=on",
        ],
        stderr=subprocess.DEVNULL,
    )
    frames = []
    try:
        mon = Monitor(sock)
        for n in range(limit):
            path = os.path.join(tmp, f"{n:05d}.ppm")
            mon("screendump " + path)
            frame = Image.open(path).convert("RGB")
            if frame.size == (640, 400):
                break
            frames.append(frame)
            time.sleep(step)
    finally:
        qemu.kill()
        qemu.wait()
        shutil.rmtree(tmp)
    return frames


def capture_compute(rows_per_frame=2):
    """the computation, under a debugger: a breakpoint on the program's own loop test
    pauses the real machine every few rows, and qemu dumps the screen from there."""
    data = Path(BMP).read_bytes()
    loop = data.index(bytes.fromhex("81FF00FA"), 1078, 1078 + 320)  # cmp di, 64000
    addr = LOAD + loop
    tmp = tempfile.mkdtemp()
    script = os.path.join(tmp, "capture.gdb")
    with open(script, "w") as f:
        f.write(f"""set pagination off
set confirm off
target remote localhost:1234
set $n = 0
break *{addr:#x} if ($edi & 0xffff) % {320 * rows_per_frame} == 0
commands
silent
eval "monitor screendump {tmp}/c%05d.ppm", $n
set $n = $n + 1
continue
end
break *{addr + 6:#x}
commands
silent
eval "monitor screendump {tmp}/c%05d.ppm", $n
kill
quit
end
continue
""")
    qemu = subprocess.Popen(
        ["qemu-system-i386", "-drive", f"format=raw,file={BMP},if=ide", "-display", "none", "-no-reboot", "-s", "-S"],
        stderr=subprocess.DEVNULL,
    )
    try:
        subprocess.run(
            ["gdb", "-batch", "-nx", "-x", script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600
        )
    finally:
        qemu.kill()
        qemu.wait()
    paths = sorted(p for p in os.listdir(tmp) if p.endswith(".ppm"))
    frames = [Image.open(os.path.join(tmp, p)).convert("RGB") for p in paths]
    shutil.rmtree(tmp)  # a hundred 750 KB screendumps
    return frames


def distinct(frames):
    out, prev = [], None
    for f in frames:
        b = f.tobytes()
        if b != prev:
            out.append(f)
            prev = b
    return out


def fit(im):
    s = min(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.NEAREST)
    c = Image.new("RGB", (W, H), (0, 0, 0))
    c.paste(im, ((W - im.width) // 2, (H - im.height) // 2))
    return c


tt = ImageFont.truetype(os.path.join(CM, "cmtt10.ttf"), 19)
it = ImageFont.truetype(os.path.join(CM, "cmti10.ttf"), 21)


def caption(im, title, sub):
    """a caption in the lower left: the title in typewriter, a gloss in italic."""
    im = im.copy()
    d = ImageDraw.Draw(im, "RGBA")
    tw = d.textlength(title, font=tt)
    sw = d.textlength(sub, font=it)
    d.rectangle((18, H - 54, 18 + tw + sw + 46, H - 18), fill=(0, 0, 0, 215))
    d.text((32, H - 44), title, font=tt, fill=(255, 255, 255))
    d.text((32 + tw + 14, H - 46), sub, font=it, fill=(196, 192, 182))
    return im


def main():
    bios = distinct(capture_boot())[1:]  # text mode: seabios
    comp = distinct(capture_compute())  # mode 13h: the computation, two rows a frame
    assert bios and len(comp) > 50, "capture missed the boot; run again"

    out = []

    def hold(im, sec):
        return out.extend([im] * round(sec * FPS))

    image = fit(Image.open(BMP).convert("RGB"))
    hold(caption(image, "fixpoint.bmp", "opened as an image"), 2.6)

    cmd = "$ qemu-system-i386 -drive format=raw,file=fixpoint.bmp"
    for i in range(0, len(cmd) + 2, 2):
        c = Image.new("RGB", (W, H), (0, 0, 0))
        ImageDraw.Draw(c).text(
            (40, H // 2 - 12), cmd[:i] + ("_" if i < len(cmd) else ""), font=tt, fill=(255, 255, 255)
        )
        out.append(c)
    hold(out[-1], 0.6)

    for im in bios:
        hold(caption(fit(im), "booting", "the same file, as a disk"), 1.6 / len(bios))
    per = 4.0 / len(comp)  # the fill plays in four seconds
    for im in comp:
        hold(caption(fit(im), "computing", "real frames, paused every two rows"), per)
    final = fit(comp[-1])
    hold(caption(final, "booted", "the same picture, drawn again without looking"), 2.2)
    hold(caption(final, "dark", "where the program hasn't reached. yet."), 2.2)
    hold(caption(final, "64000/64000 pixels", "identical to the image"), 2.4)

    os.makedirs(OUT, exist_ok=True)
    ff = subprocess.Popen(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-s",
            f"{W}x{H}",
            "-r",
            str(FPS),
            "-i",
            "-",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            f"{OUT}/demo.mp4",
        ],
        stdin=subprocess.PIPE,
    )
    for f in out:
        ff.stdin.write(f.tobytes())
    ff.stdin.close()
    ff.wait()
    image.save(f"{OUT}/poster.png")
    print(f"{OUT}/demo.mp4: {len(out) / FPS:.1f}s, {len(bios)} bios frames, {len(comp)} computing frames")


if __name__ == "__main__":
    main()
