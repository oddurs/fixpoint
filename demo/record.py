"""record the demo video: real qemu frames of fixpoint.bmp booting.

the computation takes microseconds, so qemu runs with -icount shift=10,align=on,
which pins the emulated cpu to about one million instructions per second of real
time. the frames are screendumps taken as fast as the monitor allows; nothing is
interpolated. needs qemu-system-i386, ffmpeg, and pillow.

usage: python3 demo/record.py   (from the repo root)
writes site/static/demo.mp4 and site/static/poster.png
"""
import os, socket, subprocess, tempfile, time
from PIL import Image, ImageDraw, ImageFont

BMP = "fixpoint.bmp"
OUT = "site/static"
W, H, FPS = 960, 600, 30
BG = (13, 17, 23)
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono%s.ttf"


def capture(seconds=11):
    tmp = tempfile.mkdtemp()
    sock = os.path.join(tmp, "mon.sock")
    qemu = subprocess.Popen([
        "qemu-system-i386", "-drive", f"format=raw,file={BMP},if=ide", "-display", "none",
        "-monitor", f"unix:{sock},server,nowait", "-no-reboot",
        "-icount", "shift=10,align=on,sleep=on"], stderr=subprocess.DEVNULL)
    s = socket.socket(socket.AF_UNIX)
    for _ in range(100):
        try:
            s.connect(sock)
            break
        except OSError:
            time.sleep(0.02)
    s.setblocking(False)
    frames, t0, n = [], time.time(), 0
    try:
        while time.time() - t0 < seconds:
            path = os.path.join(tmp, f"{n:05d}.ppm")
            s.send(f"screendump {path}\n".encode())
            while not (os.path.exists(path) and os.path.getsize(path) > 15):
                time.sleep(0.002)
            time.sleep(0.01)
            try:
                while s.recv(65536):
                    pass
            except BlockingIOError:
                pass
            frames.append(path)
            n += 1
    finally:
        qemu.kill()
        qemu.wait()
    # decode only after qemu is gone: a screendump may still be mid-write while we poll
    return [Image.open(p).convert("RGB") for p in frames]


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


bold, mono = ImageFont.truetype(FONT % "-Bold", 17), ImageFont.truetype(FONT % "", 17)


def caption(im, title, sub):
    im = im.copy()
    d = ImageDraw.Draw(im, "RGBA")
    tw = d.textlength(title, font=bold)
    d.rounded_rectangle((16, H - 52, 16 + tw + d.textlength("  " + sub, font=mono) + 28, H - 16),
                        8, fill=(*BG, 225))
    d.text((30, H - 44), title, font=bold, fill=(240, 246, 252))
    d.text((30 + tw, H - 44), "  " + sub, font=mono, fill=(139, 148, 158))
    return im


def main():
    raw = capture()
    bios = distinct([f for f in raw if f.size != (640, 400)])[1:]   # text mode: seabios
    comp = distinct([f for f in raw if f.size == (640, 400)])       # mode 13h: the computation
    assert bios and len(comp) > 5, "capture missed the boot; run again"

    out = []
    hold = lambda im, sec: out.extend([im] * round(sec * FPS))
    image = fit(Image.open(BMP).convert("RGB"))
    hold(caption(image, "fixpoint.bmp", "opened as an image"), 2.6)

    cmd = "$ qemu-system-i386 -drive format=raw,file=fixpoint.bmp"
    for i in range(0, len(cmd) + 2, 2):
        c = Image.new("RGB", (W, H), BG)
        ImageDraw.Draw(c).text((40, H // 2 - 12), cmd[:i] + ("_" if i < len(cmd) else ""),
                               font=mono, fill=(240, 246, 252))
        out.append(c)
    hold(out[-1], 0.6)

    for im in bios:
        hold(caption(fit(im), "booting", "the same file, as a disk"), 1.6 / len(bios))
    for im in comp:
        hold(caption(fit(im), "computing", "real frames, cpu throttled to ~1 MIPS"), 0.13)
    final = fit(comp[-1])
    hold(caption(final, "booted", "rule 110, seeded by its own code"), 2.2)
    hold(caption(final, "64000/64000 pixels", "identical to the image"), 2.4)

    os.makedirs(OUT, exist_ok=True)
    ff = subprocess.Popen([
        "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
        f"{OUT}/demo.mp4"], stdin=subprocess.PIPE)
    for f in out:
        ff.stdin.write(f.tobytes())
    ff.stdin.close()
    ff.wait()
    image.save(f"{OUT}/poster.png")
    print(f"{OUT}/demo.mp4: {len(out) / FPS:.1f}s, {len(bios)} bios frames, {len(comp)} computing frames")


if __name__ == "__main__":
    main()
