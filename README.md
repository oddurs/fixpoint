# fixpoint

an 86 KB image that boots and computes itself.

**[watch it boot →](https://oddurs.github.io/fixpoint)**

![fixpoint.bmp, scaled 3x](preview.png)

`fixpoint.bmp` is an ordinary 320×200 bitmap. open it in anything and you get the picture above. write it to a disk and boot it, and the cpu computes the same picture from scratch, pixel for pixel. unzip it and you get its source.

```
qemu-system-i386 -drive format=raw,file=fixpoint.bmp
unzip fixpoint.bmp
```

## what you're looking at

the last 100 pixels of the top row are the program. every row below is the row above it, run through [rule 110](https://en.wikipedia.org/wiki/Rule_110), a one-dimensional cellular automaton that is turing-complete. the seed of the universe is the machine code that computes it.

each pixel is a byte, so every cell holds eight independent rule 110 universes, one per bit. the palette is a value ramp, so the high bits dominate: the big triangles are the top universe, and the seven below it are texture. the black triangle is rule 110's signature: a pattern grows left, one cell per generation, and never right.

the screen is treated as one tape, 64,000 cells long, folded into rows of 320. a cell's neighbours are the three cells 320 positions back, so there is no edge handling, and the whole computation is one loop:

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

booting never reads the picture. it loads three sectors (the header, the palette, and the program), then re-derives the other 63,900 pixels.

### what "fixpoint" means, exactly

the fixed point is the pixel array. the 64,000 bytes an image viewer draws are exactly the 64,000 bytes the program writes to the screen, and the program is among them. the header and palette are loaded from the file, not computed. and the program finds its own bytes by reading them from memory, which a quine purist would call cheating; this is not a quine, it's a file that contains its own output.

rule 110 being turing-complete is a property of the rule, not a claim about this picture: the seed is whatever bytes the program happens to be, so the universe isn't computing anything in particular. it just could.

## how one file is a picture, a disk, and an archive

| offset | as a bmp | as a disk |
|---|---|---|
| 0 | `BM` signature | `inc dx; dec bp` |
| 2 | file size: `EB 51 01 00` = 86,507 | `jmp short` into the palette |
| 6 | reserved, zero | |
| 54 | 256-colour palette | the bootloader, woven between colours |
| 446 | palette entries 98–113 | the partition table, with legal status bytes |
| 510 | palette entry 0x72 | `55 AA`, the boot signature |
| 1078 | pixels | row 0 ends with the program |
| 65,078 | padding, so the size field is true | a zip of the source, for `unzip` |

- **the file size is a jump instruction.** its low byte is `EB`, `jmp short`, and the next byte is the distance into the palette. the file is padded until the size it claims is true, and the padding holds a zip of `main.asm`, `stub.asm`, and `build.py`, so the file carries its own source.
- **the boot sector is palette colours.** the signature `55 AA` is the blue and green of entry 0x72, which becomes an orange highlight. the four partition status bytes are blue channels too, nudged to `0x80` so the partition table is legal and bioses don't reject the disk.
- **the bootloader is woven into the palette.** its 41 bytes would otherwise be 41 wrong colours. `build.py` runs a dynamic program over instruction orders, alternate encodings, harmless fillers (`inc bp`, `inc di`), and `jmp short` hops over palette entries it would rather not touch, and picks the layout whose bytes, read as colours, disturb the picture least: 13 colours shift, most of them rare. the green specks you can find are the bootloader showing through.
- **it stays clear of the bpb.** a bios booting a usb stick as a floppy may rewrite bytes 11–61 in memory. nothing executable lives there, and the program reads the palette from a fresh copy off the disk.
- **it retries.** a failed disk read loops back to the read, instead of jumping into whatever happened to be in memory.
- **`B` is `inc dx`.** the bios leaves the boot drive number in `dl`, so the first thing the bootloader does, somewhere, is `dec dx`.

## build

needs `nasm`, python 3, and numpy. verifying also needs pillow and `qemu-system-i386`, and uses ffmpeg and chrome when they're installed.

```
make            # assemble main.asm, place the stub, write fixpoint.bmp and stub.asm
make verify     # check every claim above, then boot it and compare the screen
make run        # boot it in a qemu window
```

`make verify` checks that pillow, ffmpeg, and chrome all decode the same pixels; that the header, signature, and partition table are valid; that the zip inside matches the source in the repo; and that the booted screen equals the image, all 64,000 pixels. the build is deterministic, and ci rebuilds from source on every push, requires the committed image to be byte-identical, and runs the same checks.

| file | what it is |
|---|---|
| `main.asm` | the program: palette setup, the seed copy, and the rule 110 loop. assembled with `ORG` and `X0` defined, so it lands exactly at the end of row 0 |
| `stub.asm` | the bootloader, with the palette bytes it hops over. generated by `build.py`, committed so you can read it |
| `build.py` | lays out the file, runs the automaton, places the stub |
| `verify.py` | checks every claim, then boots the image in qemu and diffs the screen |
| `demo/record.py` | records the demo video from real qemu frames, cpu throttled to ~1 MIPS |
| `site/` | the [project page](https://oddurs.github.io/fixpoint), sveltekit, prerendered with no client-side js |

## caveats

verified in qemu with seabios. it has not been booted on real hardware yet. the partition table is legal and the bpb region is empty, which covers the usual reasons a bios refuses a disk, but bioses vary. if you try it on a real machine, i'd like to know what happens.

## license

[mit](LICENSE)
