# fixpoint

an 88 KB image that boots and computes itself.

*a picture of its own consequences.*

**[the page, with the story and a field guide →](https://fixpoint.oddurs.com)**

![fixpoint.bmp, scaled 3x](docs/preview.png)

`fixpoint.bmp` is an ordinary 320×200 bitmap. open it in anything and you get the picture above. write it to a disk and boot it, and the cpu draws the same picture again, from scratch, byte for byte, without looking. unzip it and it hands you its source.

```
qemu-system-i386 -drive format=raw,file=fixpoint.bmp
unzip fixpoint.bmp
```

on real hardware it needs a legacy bios, or uefi's compatibility mode, and vga. a uefi-only machine won't start it.

## one file, three readings

| offset | as a bmp | as a disk |
|---|---|---|
| 0 | `BM` signature | `inc dx; dec bp` |
| 2 | file size: `EB 59 01 00` = 88,555 | `jmp short` into the palette |
| 6 | reserved, zero | |
| 54 | 256-colour palette | the bootloader, woven between colours |
| 446 | palette entries `0x62`–`0x71` | the partition table, with legal status bytes |
| 510 | palette entry `0x72` | `55 AA`, the boot signature |
| 1,078 | pixels | row 0: the ether, then the program |
| 65,078 | padding, so the size field is true | a zip of the source, for `unzip` |

ask `file` what it is and it says `DOS/MBR boot sector`, with four partitions, all active. it doesn't mention the picture.

- **the file size is a jump instruction.** its low byte is `EB`, `jmp short`, and the next byte is the distance into the palette. the file is padded until the size it claims is true, and the padding holds a zip of `main.asm`, `stub.asm`, and `build.py`.
- **the boot signature is a colour.** `55 AA` is the blue and green of palette entry `0x72`, an orange that appears 107 times in the picture.
- **the partition table is four more colours.** a status byte may only be `00` or `80`, and some bioses check. the four here are blue channels set to `80`: all four partitions claim to be active, which a strict reading of the format wouldn't allow. all five of these entries already had bit 6 set, so they were warm colours before; the boot sector moves them by at most 30 levels in any channel.
- **the bootloader is woven into the palette.** its 36 bytes would otherwise be 36 wrong colours. `build.py` runs a dynamic program over instruction orders, alternate encodings, harmless fillers (`nop`, `inc bp`, `dec di`), and `jmp short` hops over colours it would rather leave alone, and picks the layout whose bytes disturb the picture least: 10 colours shift, about 1% of the pixels. [`stub.asm`](stub.asm) writes out every palette entry it hops over, with its colour.
- **it doesn't care where it starts.** until its final far jump, the bootloader uses only relative jumps, so it runs the same whether the bios starts it at `0000:7C00` or `07C0:0000`.
- **it stays clear of the bpb.** a bios booting a usb stick as a floppy may rewrite bytes 11–61 in memory. nothing executable lives there, and the program reads the palette from a fresh copy off the disk.
- **it retries.** a failed disk read loops back to the read, instead of jumping into whatever happened to be in memory.
- **`B` is `inc dx`.** the bios leaves the boot drive number in `dl`, so the first thing the bootloader does is `dec dx`, to put back what the `B` took.

![figure 2: the first 512 bytes of fixpoint.bmp, read as bmp headers and a palette, with the path the cpu takes through them and the instructions it runs](docs/anatomy.svg)

## what the picture is

![figure 1: fixpoint.bmp at three times its size, with a field guide to the program, the ether, the light cone and the details hidden in it](docs/fieldguide.svg)

every row is the row above it, run through [rule 110](https://en.wikipedia.org/wiki/Rule_110). the top row is 190 cells of rule 110's **ether**, the background pattern that repeats every 14 cells and every 7 rows, followed by the 130-byte program. each pixel is a byte, so every cell holds eight rule 110 universes, one per bit. the ether is the same in all eight; the program's bits differ from universe to universe, so the program is the only thing that can make them disagree, and the palette shows exactly that:

- **all eight agree** (`00` or `FF`): dark. the universe exactly as it would have been without the program.
- **they disagree**: the cell is in the program's light cone. universe 6 picks light (coral to gold) or dark (indigo to plum), the other seven pick the hue.

every cell the program hasn't reached is dark. inside the cone, 384 cells look dark too: 306 by coincidence, and 78 in a triangle under the program's last 14 bytes, which are one period of the ether laid down 12 cells out of phase. the right edge of the cone stalls for 30 rows, then spreads at about 0.62 cells per row, the left at 0.48, near the speeds of rule 110's two fastest gliders (2/3 and 1/2). the second cone on the left is the first one wrapping around, because the screen is one 64,000-cell tape folded into rows of 320. all 256 colours appear. every one of these numbers is a check in `verify.py`.

the whole computation is one loop. a cell's neighbours are the three cells 320 positions back on the tape, so there is no edge handling:

```nasm
    mov di, 321             ; cell 320 has no left neighbour on the tape; it stays 0
.cell:
    mov al, [di-321]        ; left
    mov ah, [di-320]        ; centre
    mov dl, [di-319]        ; right
    mov bl, ah
    or bl, dl               ; c | r
    and al, ah
    and al, dl              ; l & c & r
    not al
    and al, bl              ; rule 110 = (c | r) & ~(l & c & r), on 8 bits at once
    stosb
    cmp di, 64000
    jb .cell
```

the bootloader loads three sectors: the header, the palette, and row 0. the program copies itself to the end of row 0, writes one period of the ether at the start and lets it copy itself across the row, then computes the 63,680 pixels below. the only pixels it reads from the file are its own 130.

### what "fixpoint" means, exactly

the fixed point is the pixel array. the 64,000 bytes an image viewer draws are exactly the 64,000 bytes the program leaves in video memory, and the program is among them. the header and palette are loaded from the file, not computed, and the program finds its own bytes by reading them from memory, which a quine purist would call cheating. they'd be right. this isn't a quine; it's a file that contains its own output.

## build

needs `nasm`, python 3, and the packages in `requirements.txt`. verifying also needs `qemu-system-i386`, and uses ffmpeg and chrome when they're installed.

`scripts/setup` readies a clone: git hooks, a python environment, a toolchain check. `scripts/task check` runs everything ci runs.

```
make            # build fixpoint.bmp, stub.asm, and the figures
make verify     # check every claim above, then boot it
make run        # boot it in a qemu window
make demo       # re-record the video (needs gdb and ffmpeg)
make site       # build the project page into site/build
```

`make verify` runs [`verify.py`](verify.py), which checks:

- with its own rule 110, that every row follows from the one above, and every cell the program hasn't reached is dark
- that pillow, ffmpeg and chrome decode the same pixels
- the header, the boot signature, the partition status bytes, and the jump
- every number the page and this readme quote: 256 colours, 107 oranges, 306 and 78 calm cells, the stall and the two speeds
- that the zip inside matches the source in the repo
- then it boots the image in qemu and reads back video memory: all 64,000 bytes are the file's pixel bytes, and every pixel on screen is the image's colour, at the vga's 6 bits per channel

the build is deterministic. ci rebuilds from source on every push, requires the committed image to be byte-identical, and runs the same checks.

| file | what it is |
|---|---|
| [`main.asm`](main.asm) | the program: palette setup, row 0, and the rule 110 loop |
| [`stub.asm`](stub.asm) | the bootloader, with the palette bytes it hops over. generated by `build.py`, committed so you can read it |
| [`build.py`](build.py) | lays out the file, runs the automaton, places the stub |
| [`verify.py`](verify.py) | checks every claim, then boots the image in qemu and reads back video memory |
| [`demo/record.py`](demo/record.py) | records the demo video: the bios in real time, then the computation under gdb, paused by a breakpoint on the program's own loop every two rows. every frame is the real screen |
| [`demo/figures.py`](demo/figures.py) | draws the figures in `docs/`, tracing the cpu's path by disassembling the file |
| [`site/`](site) | the [project page](https://fixpoint.oddurs.com), sveltekit, prerendered with no client-side js. its text is its own, in [`site/src/post.md`](site/src/post.md) |

## lineage

files that are several things at once have a long, strange history; ange albertini's [funky file formats](https://fahrplan.events.ccc.de/congress/2014/Fahrplan/system/attachments/2562/original/Funky_File_Formats.pdf) is the map. the ether, the gliders, and the proof that they can compute anything are [matthew cook's](https://doi.org/10.25088/ComplexSystems.15.1.1).

## license

[mit](LICENSE)
