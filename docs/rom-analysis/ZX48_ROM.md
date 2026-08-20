# The ZX48-mode Spectrum ROM: tape stubs and wire protocol

`SAVE "tpi:zx48"` puts the machine into ZX Spectrum mode, where `OUT 244,3`
selects a **customized Spectrum ROM**. That ROM — not the TS-PICO EXROM — owns
the wire protocol in ZX mode, and it is a different protocol from TPI.

Everything below is transcribed from the ROM. Recorded here so nobody has to
disassemble it again. The firmware-facing summary lives at
[`../PROTOCOL.md`](../PROTOCOL.md) §7b; this page is the ROM-side evidence.

## Identifying the ROM

**It is not in this repository.** It is user-supplied and served from DOCK, so
none of the images under `ROMs/` contain the tape stubs. Confirmed by
searching every shipped image for the stub opcodes:

```
LD A,'S' ; OUT ($0E),A   ->  0 hits in every ROMs/*.bin and src/rom/TSPICO.ROM
```

The image these notes were taken from:

| | |
|---|---|
| Name | `Spectrum nuevo LD.rom` ("nuevo LD" = new LOAD) |
| Size | 16384 bytes |
| MD5  | `0081359400b68d309f101d8c3f3190bc` |
| Base | stock 48K Spectrum — `RST 0` is `F3 AF 11 FF FF C3 CB 11`, copyright at `$153B` |

To check that a given image is a patched one rather than stock:

```sh
python3 - rom.bin <<'PY'
import sys
d = open(sys.argv[1],"rb").read()
print("SA-BYTES patched:", d[0x04C8:0x04CC] == bytes([0x3E,0x53,0xD3,0x0E]))  # LD A,'S' ; OUT ($0E),A
print("LD-BYTES patched:", d[0x055F:0x0563] == bytes([0x3E,0x4C,0xD3,0x0E]))  # LD A,'L' ; OUT ($0E),A
print("polls $0F:", d.count(bytes([0xDB,0x0F])))                              # expect 0
PY
```

## The three facts that make ZX48 unlike TPI

1. **Port `$0F` is never read.** The ROM contains **zero** `IN A,($0F)`. The Y
   register, `MQ_READY()`, the dual-port ready mechanism — none of it takes
   part. The PIO's issue-#14 auto-busy is harmless here.
2. **There is no status byte.** `$053F`, the shared exit for both tape
   routines, restores the border and `RST 8`s on BREAK; that is the only error
   report in the whole path. A Pico-side failure **cannot** be reported to the
   Z80, so `REFUSE_SAVE()` has no counterpart in ZX mode.
3. **Parity seeds from the flag byte**, not from byte 0 the way TPI's CRC does.

## SAVE — `SA-BYTES`, `$04C2`

```
04C2  21 3F 05     LD HL,$053F        ; common exit (border restore + BREAK)
04C5  E5           PUSH HL
04C6  F5           PUSH AF
04C7  F3           DI
04C8  3E 53        LD A,'S'
04CA  D3 0E        OUT ($0E),A        ; announce the block
04CC  06 FF        LD B,$FF
04CE  10 FE        DJNZ $04CE         ; ~940us
04D0  7B           LD A,E
04D1  D3 0E        OUT ($0E),A        ; length low
04D3  06 FF 10 FE  (delay)
04D7  7A           LD A,D
04D8  D3 0E        OUT ($0E),A        ; length high
04DA  06 FF 10 FE  (delay)
04DE  F1           POP AF
04DF  67           LD H,A             ; parity accumulator SEEDS FROM THE FLAG
04E0  D3 0E        OUT ($0E),A        ; flag: $00 header / $FF data
04E2  06 FF 10 FE  (delay)
04E6  06 10        LD B,$10           ; <- loop head
04E8  10 FE        DJNZ $04E8         ; ~60us between data bytes
04EA  DD 7E 00     LD A,(IX+0)
04ED  6F           LD L,A
04EE  AC           XOR H
04EF  67           LD H,A             ; running XOR
04F0  7D           LD A,L
04F1  D3 0E        OUT ($0E),A        ; data byte
04F3  DD 23        INC IX
04F5  1B           DEC DE             ; <- decremented AFTER the send
04F6  7A B3        LD A,D : OR E
04F8  20 EC        JR NZ,$04E6
04FA  7C           LD A,H
04FB  D3 0E        OUT ($0E),A        ; parity
04FD  FB C9        EI : RET
```

On the wire, per block:

```
'S' , len_lo , len_hi , flag , DE data bytes , parity
```

Blind timed writes — no handshake, the Pico just has to keep up. Note `'S'` is
re-sent for **every** block, so a SAVE puts two of them on the bus (header then
data); `ZX48_IO` consumes the first, `SAVE_ZX` the second.

**`DEC DE` at `$04F5` comes after the send**, so `DE=0` wraps to `$FFFF` and the
Z80 emits 65536 bytes — the ZX "SAVE 0 = SAVE 64K" quirk, the same one
[#40](https://github.com/timex-sinclair-projects/tspico-firmware-build/pull/40)
fixed for TS mode. With no status byte to refuse with, the only ZX-side
mitigation is to swallow the flood.

## LOAD — `LD-BYTES`, `$0556`

```
0556  08           EX AF,AF'
0557  CD 3F 05     CALL $053F
055A  21 3F 05     LD HL,$053F
055D  E5           PUSH HL
055E  F3           DI
055F  3E 4C        LD A,'L'
0561  D3 0E        OUT ($0E),A
0563  DB 0E        IN A,($0E)         ; <- THE HANDSHAKE
0565  FE 40        CP $40
0567  20 FA        JR NZ,$0563        ;    spin until the byte reads 0x40
0569  06 FF 10 FE  (delay ~940us)
056D  DB 0E        IN A,($0E)         ; flag byte
056F  67           LD H,A             ; seeds the parity accumulator
0570  06 FF 10 FE  (delay)
0574  06 04 10 FE  (delay ~15us)      ; <- loop head
0578  DB 0E        IN A,($0E)         ; data byte
057A  4F           LD C,A
057B  08           EX AF,AF'
057C  30 FD        JR NC,$057B        ; LOAD vs VERIFY
057E  DD 71 00     LD (IX+0),C
0581  08           EX AF,AF'
0582  7C A9 67     LD A,H : XOR C : LD H,A
0585  DD 23        INC IX
0587  1B           DEC DE
0588  7A B3        LD A,D : OR E
058A  20 E8        JR NZ,$0574
058C  DB 0E        IN A,($0E)         ; parity
058E  BC           CP H
058F  FB 37 C8     EI : SCF : RET Z
```

On the wire, per block:

```
'L' , (poll until 0x40) , flag , DE data bytes , parity
```

### The `0x40` is on `$0E`, and it is not the single-port continue flag

This is the one that cost a shipped regression. `c649e69` removed `wrt(0x40)`
from `LOAD_ZX` and `MQ.put(64)` from `LOAD_ZX_C` reasoning that "0x40 continue
flag is on port `$0F` (scratch Y)" — true for TPI, wrong here. The poll at
`$0563` reads the **data** port. With nothing matching `0x40` it never exits: TX
drains, the PIO's `pull(noblock)` then drives `0x00` forever, and ZX LOAD hangs.

Because the loop **discards** every non-`0x40` byte it also resynchronises the
stream. That is why `LOAD_ZX` can afford to offer one byte more than
`LD-BYTES` consumes, and why a slow Pico response is tolerable here even though
the equivalent would break `LOAD_TS`.

## Header layout, and why it lines up with TPI

For a header block the Spectrum ROM calls `SA-BYTES` with `DE=17`, `A=$00`, so
21 bytes reach the Pico after the `'S'`. Indexed as `SAVE_ZX` drains them:

| Index | ZX48 | TPI (`SAVE_TS`) |
|---|---|---|
| 0 | TAP length low (17) | block type |
| 1 | TAP length high (0) | session ID low |
| 2 | **flag** ($00/$FF) | session ID high |
| 3 | header type | HDTYPE |
| 4–13 | filename | filename |
| 14,15 | data length | BLEN |
| 16–19 | param 1, param 2 | ADDR, HDVARS |
| 20 | parity | CRC |

**Bytes 3–20 line up exactly**, which is why `hdr[4:14]` and `hdr[14],[15]` work
in both handlers. The heads differ, and that is the trap: TPI seeds its CRC from
`hdr[0]`, ZX seeds parity from `hdr[2]`. Seeding a ZX block from `hdr[0]` gives a
wrong answer on every block.

## Other ROM images, for reference

`src/rom/TSPICO.ROM` is 32768 bytes and is simply `TSPICO-15w-home` followed by
`TSPICO-15w-exrom`, not a separate image:

```sh
python3 -c "
import hashlib
r=open('src/rom/TSPICO.ROM','rb').read()
h=lambda b: hashlib.md5(b).hexdigest()
print(h(r[:16384])==h(open('ROMs/TSPICO-15w-home','rb').read()),
      h(r[16384:])==h(open('ROMs/TSPICO-15w-exrom','rb').read()))"
```

The TS-PICO EXROM contains exactly one `OUT ($0E),A` and one `IN A,($0F)` — the
TPI driver core — and no ZX stubs, which is the other half of the evidence that
ZX48's protocol lives entirely in the DOCK-served Spectrum ROM.
