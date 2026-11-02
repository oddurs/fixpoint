## what you're looking at

every row is the row above it, run through [rule 110](https://en.wikipedia.org/wiki/Rule_110), a one-dimensional cellular automaton that is turing-complete. the top row is where it starts: the last 130 pixels are the program, and the 190 before them are rule 110's **ether**, a background pattern that repeats every 14 cells and every 7 generations. the ether is the fabric of [matthew cook's proof](https://doi.org/10.25088/ComplexSystems.15.1.1) that rule 110 is universal: his gliders, the moving structures that carry information, travel through it. here, the only thing travelling is the program.

each pixel is a byte, so every cell holds eight rule 110 universes, one per bit. the ether is the same in all eight. the program's bits differ from universe to universe, so the program is the only thing that can make them disagree, and the palette shows exactly that:

- **where all eight universes agree**, the cell is `00` or `FF`, drawn in two close, quiet shades. this is the woven dark V: the universe exactly as it would have been if the program weren't there. it hasn't heard yet.
- **where they disagree**, the cell is in the program's causal future: its light cone. universe 6 decides whether it's light (coral to gold) or dark (indigo to plum), so its triangles show through, and the other seven set the hue.

every cell the program hasn't reached is dark, without exception. inside the cone, 0.93% of cells happen to agree anyway, and look dark too. they look untouched. they aren't.

the cone's edges move at about 0.63 cells per generation to the right and 0.49 to the left, close to the speeds of rule 110's two fastest gliders, which cook calls A and B: 2/3 and 1/2. the left cone is the program's influence leaving the right edge of the screen and coming back on the left, because the screen is one continuous tape. the diagonal stripes in it are glider trains. and the dark corner at the top right is the program's own last 14 bytes, which are one period of the ether, so the program ends in the fabric it disturbs.

## three readers, one file

an image viewer, a bios, and `unzip` all read this file, and none of them knows the others exist. the whole trick is finding bytes all three can live with. here they are in the order the cpu meets them.

**byte 0.** a bmp has to begin with `BM`. a bios jumps to byte 0 and runs whatever it finds, and `B` and `M` happen to be instructions: `inc dx` and `dec bp`. almost harmless. the bios leaves the number of the drive it booted from in `dl`, and the `B` just added one to it, so the first thing the bootloader will do, once it gets control, is `dec dx`, and put it back.

**bytes 2 to 5.** next comes the file's size, four bytes, and the cpu reaches it third, so it has to be an instruction too. its low byte is `EB`, `jmp short`, and the byte after it is how far to jump: `59`, into the palette. so the file is 88,555 bytes long because of where that jump needs to land, not because of anything it has to hold. it's padded until the size it claims is true, and the padding holds a zip of its own source. zip readers start from the end of a file, so they never notice the picture in front of it.

**bytes 11 to 61.** a bios booting a usb stick as a floppy may overwrite this stretch, in memory, with the disk geometry it expects to find there. in a bmp that's the end of the file header, the info header, and the first two colours. nothing that runs lives there, and the program reads its colours from a fresh copy off the disk, not from whatever the bios left in memory.

**the palette.** 256 colours, four bytes each, from byte 54 to byte 1,077, straight through the end of the boot sector at byte 512. so the boot sector's rules become rules about colour. a bios wants `55 AA` at byte 510: that's the blue and green of entry `0x72`. some bioses refuse a disk unless the four partition status bytes each hold `00` or `80`: those are blue channels too, set to `80`. all five entries have bit 6 set, so they were warm colours already, and none moves by more than 30 levels in any channel. the two bytes every bios looks for first are one of the oranges in the cone. they appear 107 times in the picture, if you know where to look.

the price is a partition table in which all four partitions claim to be active, which a strict reading of the format wouldn't allow. ask `file` what this is and it says `DOS/MBR boot sector`, with four partitions, all active. it doesn't mention the picture.

**the bootloader.** it has to live in the first 512 bytes, and the only room there is the palette, so its 36 bytes would be 36 wrong colours. instead of choosing the colours, the build chooses the code. it searches over instruction orders, alternate encodings, harmless one-byte fillers (`nop`, `inc bp`, `dec di`), and `jmp short` hops over colours it would rather leave alone, and keeps the layout whose bytes disturb the picture least. 10 colours shift, about 1% of the pixels. the saturated blue and magenta specks in the cone are the bootloader showing through.

![figure 1: the first 512 bytes of fixpoint.bmp, read as bmp headers and a palette, with the path the cpu takes through them and the instructions it runs](docs/anatomy.svg)

it uses only relative jumps, so it runs the same whether the bios starts it at `0000:7C00` or `07C0:0000`. it reads the first three sectors of the disk, the headers, the palette and the first row of pixels, into memory at `0000:8000`, and if the read fails it tries again rather than jump into whatever was there. then one far jump, its only absolute one: into the pixels, row 0, x = 190, where the program is.

## one loop

the program sets the screen to 320 × 200 in 256 colours and copies the file's palette into the vga. it writes itself into the end of row 0, writes one period of the ether at the start, and lets that copy itself across the rest of the row. everything after that is one loop.

the screen is treated as one tape, 64,000 cells long, folded into rows of 320. a cell's neighbours are the three cells 320 positions back, so there's no edge handling:

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

booting never reads the picture. apart from the 130 pixels that are the program, it doesn't need to: the other 63,680 follow.

### what "fixpoint" means, exactly

the fixed point is the pixel array. the 64,000 bytes an image viewer draws are exactly the 64,000 bytes the program leaves in video memory, and the program is among them. the header and palette are loaded from the file, not computed. and the program finds its own bytes by reading them from memory, which a quine purist would call cheating. they'd be right. this isn't a quine; it's a file that contains its own output.

rule 110 being turing-complete is a property of the rule, not a claim about this picture: the seed is whatever bytes the program happens to be, so the universe isn't computing anything in particular. it just could.

## you don't have to take my word for it

a script, [`verify.py`](https://github.com/oddurs/fixpoint/blob/main/verify.py), checks every claim on this page. it runs rule 110 itself, written apart from the build, and confirms that every row follows from the one above and that every cell the program hasn't reached is dark. it has pillow, ffmpeg and chrome decode the file and compares their pixels. it checks the header, the boot signature and the partition table, and that the zip inside is the source in the repo. then it boots the file in qemu and reads back video memory: all 64,000 bytes are the file's pixel bytes, and every pixel on the screen is the image's colour, at the vga's 6 bits per channel. the build is deterministic, and every push rebuilds the image from source and requires it to come out byte for byte the same.

## lineage

files that are several things at once have a long, strange history; ange albertini's [funky file formats](https://fahrplan.events.ccc.de/congress/2014/Fahrplan/system/attachments/2562/original/Funky_File_Formats.pdf) is the map. the ether, the gliders, and the proof that they can compute anything are [matthew cook's](https://doi.org/10.25088/ComplexSystems.15.1.1).
