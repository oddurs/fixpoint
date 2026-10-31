; main.asm — the last pixels of row 0. this code is the seed of the universe it draws.
;
; the whole screen is one tape, 64000 cells long. each cell is a byte, so it holds
; eight independent rule 110 universes, one per bit. cell i is computed from the
; three cells one row (320 cells) above it. rule 110 is turing-complete.
bits 16
org ORG

main:
    push cs
    pop ds                  ; ds = 0, where the stub loaded the file
    mov ax, 0x0013          ; 320x200, 256 colours
    int 0x10

    mov dx, 0x3C8           ; the BMP's palette becomes the VGA palette
    xor al, al
    out dx, al
    inc dx
    mov si, 0x8000 + 54
    mov cx, 256
.pal:
    mov al, [si+2]
    shr al, 2
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
    mov di, 320
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
