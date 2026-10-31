"""check every claim fixpoint.bmp makes, then boot it.

  - it is a valid bmp: pillow, ffmpeg and chrome all decode it to the same pixels
  - it is a valid boot sector: 55 AA, legal partition status bytes, zero reserved fields
  - it carries its source: the zip in its padding matches the files in this repo
  - it is a fixed point: booted in qemu, the screen equals the image, pixel for pixel

needs pillow and qemu-system-i386. ffmpeg and chrome are checked when installed.
usage: python3 verify.py [fixpoint.bmp]
"""
import io, os, shutil, socket, struct, subprocess, sys, tempfile, time, zipfile
from PIL import Image

W, H = 320, 200
CHROME = ("google-chrome", "chromium", "chromium-browser")
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(f"  {'ok  ' if ok else 'FAIL'}  {name}{'  ' + detail if detail else ''}")


def skip(name, why):
    print(f"  --    {name}  ({why})")


def boot(path, timeout=30):
    """boot in qemu; return the screen once it has been in mode 13h and stopped changing."""
    tmp = tempfile.mkdtemp()
    sock = os.path.join(tmp, "mon.sock")
    qemu = subprocess.Popen(["qemu-system-i386", "-drive", f"format=raw,file={path},if=ide",
                             "-display", "none", "-monitor", f"unix:{sock},server,nowait",
                             "-no-reboot"], stderr=subprocess.DEVNULL)
    try:
        s = socket.socket(socket.AF_UNIX)
        for _ in range(200):
            try:
                s.connect(sock)
                break
            except OSError:
                time.sleep(0.05)
        s.settimeout(5)
        s.recv(4096)
        prev, n, deadline = None, 0, time.time() + timeout
        while time.time() < deadline:
            shot = os.path.join(tmp, f"{n}.ppm")
            n += 1
            s.send(f"screendump {shot}\n".encode())
            s.recv(4096)                                  # the monitor echoes when it's done
            time.sleep(0.05)
            try:
                im = Image.open(shot)
                im.load()
            except OSError:
                continue
            if im.size != (2 * W, 2 * H):                 # still in the bios text mode
                continue
            frame = im.convert("RGB").resize((W, H), Image.NEAREST)
            if prev is not None and frame.tobytes() == prev.tobytes():
                return frame
            prev = frame
            time.sleep(0.25)
        return None
    finally:
        qemu.kill()
        qemu.wait()


def chrome_decode(path, tmp):
    exe = next((c for c in CHROME if shutil.which(c)), None)
    if not exe:
        return None
    shutil.copy(path, os.path.join(tmp, "img.bmp"))
    with open(os.path.join(tmp, "v.html"), "w") as f:
        f.write('<!doctype html><body style="margin:0"><img src="img.bmp" style="display:block">')
    shot = os.path.join(tmp, "chrome.png")
    subprocess.run([exe, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                    "--force-color-profile=srgb", "--force-device-scale-factor=1",
                    f"--window-size={W},{H}", f"--screenshot={shot}",
                    "file://" + os.path.join(tmp, "v.html")],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60)
    return Image.open(shot).convert("RGB").crop((0, 0, W, H))


def ffmpeg_decode(path, tmp):
    if not shutil.which("ffmpeg"):
        return None
    out = os.path.join(tmp, "ffmpeg.png")
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", path, "-pix_fmt", "rgb24", out],
                   check=True)
    return Image.open(out).convert("RGB")


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "fixpoint.bmp"
    data = open(path, "rb").read()
    tmp = tempfile.mkdtemp()

    print("as a bmp")
    ref = Image.open(path)
    check("pillow decodes 320x200, 8 bit", ref.size == (W, H) and ref.mode == "P")
    size, reserved, offset = struct.unpack("<IIL", data[2:14])
    check("file size field is true", size == len(data), f"{size} bytes")
    check("reserved fields are zero", reserved == 0)
    check("pixels are the bytes at the pixel offset", ref.tobytes() == data[offset:offset + W * H])
    rgb = ref.convert("RGB")
    for name, decode in (("ffmpeg", ffmpeg_decode), ("chrome", chrome_decode)):
        im = decode(path, tmp)
        if im is None:
            skip(f"{name} decodes the same pixels", "not installed")
        else:
            check(f"{name} decodes the same pixels", im.tobytes() == rgb.tobytes())

    print("as a disk")
    check("boot signature 55 AA", data[510:512] == b"\x55\xAA")
    status = [data[o] for o in (446, 462, 478, 494)]
    check("partition status bytes are legal", all(s in (0, 0x80) for s in status),
          " ".join("%02X" % s for s in status))
    check("first instruction jumps into the palette", data[2] == 0xEB and 62 <= 4 + data[3] < 1078,
          f"jmp short to offset {4 + data[3]}")

    print("as an archive")
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        for info in z.infolist():
            name = info.filename.split("/", 1)[1]
            same = os.path.exists(name) and z.read(info) == open(name, "rb").read()
            check(f"carries {name}", same, "" if same else "differs from the repo")
    except zipfile.BadZipFile:
        check("carries its source as a zip", False)

    print("as a program")
    screen = boot(path)
    if screen is None:
        check("boots into mode 13h", False)
    else:
        pal = ref.getpalette()
        idx, px = ref.tobytes(), screen.load()
        # the vga dac keeps 6 bits per channel, so allow for the 2 it drops
        bad = sum(1 for i in range(W * H)
                  if max(abs(a - b) for a, b in zip(pal[3 * idx[i]:3 * idx[i] + 3],
                                                    px[i % W, i // W])) > 3)
        check("booted screen equals the image", bad == 0, f"{W * H - bad}/{W * H} pixels")

    print("all claims hold" if all(results) else "SOME CLAIMS FAIL")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
