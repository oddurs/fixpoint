; main.asm — the last pixels of row 0. this code is the seed of the universe it draws.
;
; the whole screen is one tape, 64000 cells long. each cell is a byte, so it holds
; eight independent rule 110 universes, one per bit. cell i is computed from cells
; i-321, i-320 and i-319: the three cells above it, one row of 320 back.
; rule 110 is turing-complete.
;
; assembled by build.py with ORG (where this lands in memory) and X0 (where it
; lands in row 0) defined, so that it ends exactly at the end of the row.
bits 16
org ORG

main:
    cld                     ; string ops go forward; don't trust the BIOS to say so
    push cs
    pop ds                  ; ds = 0, where the stub loaded the file
    mov ax, 0x0013          ; 320x200, 256 colours; clears the screen
    int 0x10

    mov dx, 0x3C8           ; the BMP's palette becomes the VGA palette
    xor al, al
    out dx, al
    inc dx
    mov si, 0x8000 + 54
    mov cx, 256
.pal:
    mov al, [si+2]          ; BMP stores B, G, R, x; the DAC wants R, G, B
    shr al, 2               ; and 6 bits per channel
    out dx, al
    mov al, [si+1]
    shr al, 2
    out dx, al
    mov al, [si]
    shr al, 2
    out dx, al
    add si, 4
    loop .pal

    push 0xA000
    pop es
    mov si, main
    mov di, X0
    mov cx, LEN
    rep movsb               ; row 0 is the program

    push es
    pop ds
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

.halt:
    hlt
    jmp .halt

LEN equ $ - main
