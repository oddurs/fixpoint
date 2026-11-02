---
name: regenerate
description: Rebuild fixpoint's committed artifacts after changing main.asm, build.py, the palette, or demo/figures.py — fixpoint.bmp, stub.asm, docs/anatomy.svg, docs/preview.png, and the demo video when the pixels change. Use before committing any such change, or when CI says the committed image differs from what the source builds.
---

# Regenerate the artifacts

The committed image and figures must be exactly what the source builds; CI rebuilds
them and fails on any difference.

1. `scripts/task test`. This rebuilds (`make -B all`), shows any artifact diff, then
   runs `verify.py`. A diff here is expected after a source change: it's the new output.
2. Read the `build.py` summary line. If the zip assertion fires, the source no longer fits
   in the padding (about 1.1 KB of headroom). Shrink the source rather than move the
   jump: moving it changes the file size, the stub's position, and every artifact.
3. If `stub.asm` changed beyond comments, the bootloader moved. Check that figure 1 still
   reads well: `rsvg-convert -w 1600 docs/anatomy.svg -o /tmp/fig.png`, and look at it.
4. If the pixels changed (`git diff --stat docs/preview.png`), the video and poster are
   stale: `make demo` (needs gdb and ffmpeg), then check `site/static/demo.mp4` plays.
5. If numbers on the page changed (sizes, counts, percentages), update both
   `site/src/post.md` and `README.md`. They are separate texts; each states its own facts.
6. Commit the source and every regenerated artifact together.
