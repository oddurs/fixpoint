## a picture of its own consequences

most generated art is pretty for its own sake. this one is a diagram. every pixel answers one question: has the program gotten here yet?

the picture is a [cellular automaton](https://en.wikipedia.org/wiki/Elementary_cellular_automaton): a row of cells, each one on or off, and a rule that makes the next row from the one above it. the rule here is [rule 110](https://en.wikipedia.org/wiki/Rule_110). it has a background pattern it likes to settle into, which [matthew cook](https://doi.org/10.25088/ComplexSystems.15.1.1) named the **ether**: a weave that repeats every 14 cells and every 7 rows. left alone, the ether would fill the screen with the same quiet pattern, top to bottom.

it isn't left alone. the top row is 190 cells of ether and then 130 cells that aren't. those 130 bytes are the program that draws the picture. every row after that follows from the row above, so the program's disturbance spreads, one row at a time, and never stops. dark means the news hasn't arrived yet. colour means it has. what you're looking at is the shape of something spreading: the program's [light cone](https://en.wikipedia.org/wiki/Light_cone), to borrow the physics word for everywhere something could have affected so far.

![figure 1: fixpoint.bmp at three times its size, with a field guide to the program, the ether, the light cone and the details hidden in it](docs/fieldguide.svg)

## eight universes in one byte

so how does a picture know where the program has been? each pixel is a byte, and a byte is eight bits, so the screen is really running eight separate copies of rule 110 at once, one per bit. the ether looks the same in all eight. the program doesn't, because its bits are all different. so wherever the eight copies disagree, the program must have gotten there.

the palette is built to show exactly that, and nothing else:

- **dark** means all eight copies agree: the byte is `00` or `FF`. untouched.
- **colourful** means they disagree. copy 6 decides light (coral to gold) or dark (indigo to plum), and the other seven pick the shade. so the big light and dark triangles inside the cone are one universe's pattern, showing through the other seven.

the colours weren't chosen to look nice. they're a measuring instrument that happens to be pretty. all 256 of them turn up somewhere in the picture.

## every byte has two jobs

three programs read this file: an image viewer, a pc's [bios](https://en.wikipedia.org/wiki/BIOS), and `unzip`. none of them know the others exist. keeping all three happy means a lot of bytes have to mean two things at once.

**`BM` is code.** a [bmp](https://en.wikipedia.org/wiki/BMP_file_format) has to start with the letters `BM`. a bios starts running whatever is at byte 0, and `B` and `M` happen to be x86 instructions: [`inc dx`](https://www.felixcloutier.com/x86/inc) and [`dec bp`](https://www.felixcloutier.com/x86/dec). mostly harmless. the bios keeps the boot drive's number in `dl`, and the `B` just added one to it, so the first thing the bootloader does is `dec dx`, to put it back.

**the file size is a jump.** next comes the file's size, four bytes long. the cpu runs straight into it, so it has to be an instruction too, and the one that fits is a [short jump](https://www.felixcloutier.com/x86/jmp): `EB` and then how far. the first version was 66 kb and jumped two bytes, into the "reserved" field right after, which held a second, longer jump. that worked, but the spec says reserved means zero, and i wanted it to. so the whole jump had to fit in the size: `EB 59`, "jump 89 bytes ahead", which lands in the palette. the file grew by 22 kb to say it. it is 88,555 bytes long not because it has that much to store, but because that's the size that spells the right jump. the leftover space at the end holds a [zip](<https://en.wikipedia.org/wiki/ZIP_(file_format)>) of the source code. zip readers start from the end of a file and work backwards, so they never notice the picture in front.

**the boot signature is a colour.** the palette is 256 colours, 4 bytes each, from byte 54 to byte 1,077. that runs straight past the end of the [boot sector](https://en.wikipedia.org/wiki/Master_boot_record) at byte 512, so the bios's rules about the boot sector become rules about colours. a bios wants `55 AA` at byte 510: that's the blue and green of colour `0x72`, a shade of orange that turns up 107 times in the picture. some bioses also want the four partition status bytes to be `00` or `80`. those are blue channels too, so they're `80`, which means all four partitions claim to be active, something a strict reading of the format doesn't allow. qemu doesn't read it that strictly. ask the `file` command what this is and it says `DOS/MBR boot sector`, with four partitions, all active. it doesn't mention the picture.

**some bytes stay empty on purpose.** when some bioses boot a usb stick as a floppy, they overwrite bytes 11 to 61 in memory with disk details they expect to find there (the [bios parameter block](https://en.wikipedia.org/wiki/BIOS_parameter_block)). in the bmp, that's part of the header and the first two colours. so no code lives there, and the program reads its colours fresh from the disk instead of trusting memory.

## code dressed up as colour

the bootloader has to fit in the first 512 bytes too, and the only free room there is the palette. so its 36 bytes of code are also 36 colours. instead of picking the colours, the build script picks the code. it tries different instruction orders, alternate encodings, filler instructions that do nothing (`nop`, `inc bp`, `dec di`), and short jumps over colours it would rather not touch, and keeps whichever version changes the picture least. some of those fillers are there purely because they're the right colour. in the end, 10 colours shift, about 1% of the pixels: the bright blue and magenta specks in the cone are the bootloader showing through.

![figure 2: the first 512 bytes of fixpoint.bmp, read as bmp headers and a palette, with the path the cpu takes through them and the instructions it runs](docs/anatomy.svg)

the bootloader only uses relative jumps, so it works whether the bios starts it at `0000:7C00` or at `07C0:0000` (bioses differ, and have since the eighties). it reads the first three sectors of the disk into memory, tries again if the read fails, and then makes one long jump straight into the pixels: row 0, x = 190, where the program is.

## one loop

i've loved assembly since i first met it, and the reason hasn't changed: it peels the abstraction back until there's nothing underneath but the machine. every layer above it, the compilers and runtimes and formats, suddenly makes sense, because you can see what it was standing on. it feels like solid ground. this whole file is an excuse to spend a weekend down there.

the program switches the screen to [mode 13h](https://en.wikipedia.org/wiki/Mode_13h), 320×200 with 256 colours, and hands the file's palette to the vga. it copies itself to the end of row 0, writes one period of the ether at the start, and lets that copy itself across the rest of the row. after that, it's one loop. the screen is treated as one long tape of 64,000 cells, folded into rows of 320, so a cell's three neighbours are just the three cells 320 positions back, and there are no edges to handle:

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

the only pixels it ever reads from the file are the 130 that are itself. it writes the other 190 of row 0 by hand, and the 63,680 below follow from the rule. the rest of the picture is never consulted. it doesn't need to be.

## things it does that nobody asked for

- **the cone stalls, then runs.** for the first 30 rows, the right edge of the cone barely moves. then it takes off. between rows 30 and 100 it spreads at about 0.62 cells per row to the right and 0.48 to the left, close to the speeds of rule 110's two fastest [gliders](https://en.wikipedia.org/wiki/Rule_110#Interesting_properties), which cook calls A and B: 2/3 and 1/2. the gliders are what his proof computes with. here, the only thing travelling is the program.
- **it wraps around.** the screen is one long tape, so influence that walks off the right edge comes back on the left, one row lower. that's the second cone, and its diagonal stripes are trains of gliders.
- **the program ends out of step.** its last 14 bytes are one period of the ether, but laid down 12 cells out of phase with the ether everywhere else. under them sits a small triangle, 13 rows deep, that looks calm and isn't. the program ends in the fabric it disturbs, just not quite in time with it.
- **false calm.** 306 pixels inside the cone look untouched, because all eight copies happen to agree there again. they aren't.
- **every colour is used.** all 256 palette entries appear somewhere in the picture, including the ones that are secretly code.

## what it isn't

the fixed point is the pixel data. the 64,000 bytes an image viewer shows are exactly the 64,000 bytes the program leaves on screen, and the program is one of them. the header and palette are loaded from the file, not computed. and the program finds its own bytes by reading them from memory, which a [quine](<https://en.wikipedia.org/wiki/Quine_(computing)>) purist would call cheating. they'd be right. it isn't a quine. it's a file that contains its own output.

rule 110 is [turing-complete](https://en.wikipedia.org/wiki/Turing_completeness): in principle, it can compute anything. that's a fact about the rule, not about this picture. the starting row is just whatever bytes the program happens to be, so it isn't computing anything in particular. it just could.

## it checks itself

every claim on this page, numbers included, is checked by a script, [`verify.py`](https://github.com/oddurs/fixpoint/blob/main/verify.py). it recomputes the universe from scratch, has three different image decoders agree on the pixels, and boots the file in [qemu](https://www.qemu.org/) to read back video memory: all 64,000 bytes match. a file called fixpoint should probably be able to prove itself.

## lineage

files that are several things at once have a long, strange history, and ange albertini's [funky file formats](https://fahrplan.events.ccc.de/congress/2014/Fahrplan/system/attachments/2562/original/Funky_File_Formats.pdf) is the best map of it. the ether, the gliders, and the proof that they can compute anything are all [matthew cook's](https://doi.org/10.25088/ComplexSystems.15.1.1). the instructions are intel's, from [1978](https://en.wikipedia.org/wiki/Intel_8086), and still run.

the source is [on github](https://github.com/oddurs/fixpoint): `main.asm` is the program, `build.py` lays out the file, and `demo/figures.py` draws both figures from the image itself.
