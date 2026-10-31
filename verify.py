"""boot fixpoint.bmp in qemu, grab the screen, and compare it to the file opened as an image.
needs qemu-system-i386 and pillow. exits non-zero on any mismatch."""
import os, socket, subprocess, sys, tempfile, time
from PIL import Image

bmp_path = sys.argv[1] if len(sys.argv) > 1 else "fixpoint.bmp"
tmp = tempfile.mkdtemp()
sock, shot = os.path.join(tmp, "mon.sock"), os.path.join(tmp, "screen.ppm")
qemu = subprocess.Popen(["qemu-system-i386", "-drive", f"format=raw,file={bmp_path},if=ide",
                         "-display", "none", "-monitor", f"unix:{sock},server,nowait", "-no-reboot"])
try:
    time.sleep(5)                                   # boot, load, compute 199 generations
    s = socket.socket(socket.AF_UNIX); s.connect(sock); time.sleep(0.3); s.recv(4096)
    s.send(f"screendump {shot}\n".encode()); time.sleep(1.5)
finally:
    qemu.kill()

screen = Image.open(shot).convert("RGB").resize((320, 200), Image.NEAREST).load()
img = Image.open(bmp_path)
idx, pal = img.tobytes(), img.getpalette()
# the VGA DAC keeps 6 bits per channel, so allow the 2 bits it drops
bad = sum(1 for y in range(200) for x in range(320)
          if max(abs(a - b) for a, b in zip(pal[3 * idx[y * 320 + x]:][:3], screen[x, y])) > 3)
print(f"{64000 - bad}/64000 pixels match")
sys.exit(1 if bad else 0)
