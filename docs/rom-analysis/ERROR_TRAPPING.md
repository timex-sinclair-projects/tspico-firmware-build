# TS2068 error trapping: `ON ERR`, `ERRT`, and the report index

Confirmed by disassembling the HOME ROM. Recorded here so nobody has to open a
ROM again to write a test program.

`ROMs/GENUINE-2068-home.bin` and `ROMs/TSPICO-15w-home` are **byte-identical in
this handler**, so everything below holds on stock and TS-PICO machines alike.

## The one-line answer

**The error code lives in `ERRT` at 23739 (`$5CBB`), and it is the report
index** — 0 for `0 OK`, 10 for `A`, 15 for `F`, 27 for `R`. Read it with
`PEEK 23739`.

`SD card/help/onerr.txt` used to say the code was in `ERRC`. It is not; `ERRC`
holds the *line number* the error happened on. That help page has been
corrected.

## The handler, disassembled

Entered from the error-report path at `$0E94`:

```
0E94  33           INC SP
0E95  FD CB 7D 7E  BIT 7,(IY+$7D)   ; (IY+$7D) = $5CB7 = ERRLN high byte
0E99  28 2D        JR Z,$0EC8       ; bit 7 clear -> not trapping, report normally
0E9B  FD CB 7D F6  SET 6,(IY+$7D)   ; mark "an error was taken"
0E9F  3C           INC A            ; <-- A = ERR_NR + 1 = the REPORT INDEX
0EA0  32 BB 5C     LD ($5CBB),A     ; ERRT  = report index          (23739)
0EA3  FD 36 00 FF  LD (IY+$00),$FF  ; ERR_NR = $FF, so BASIC carries on
0EA7  2A 45 5C     LD HL,($5C45)    ; PPC
0EAA  22 B8 5C     LD ($5CB8),HL    ; ERRC  = line of the error      (23736)
0EAD  3A 47 5C     LD A,($5C47)     ; SUBPPC
0EB0  32 BA 5C     LD ($5CBA),A     ; ERRS  = statement of the error (23738)
0EB3  2A B6 5C     LD HL,($5CB6)    ; ERRLN, flag bits still on      (23734)
0EB6  CB BC        RES 7,H
0EB8  CB B4        RES 6,H          ; mask the two flag bits off
0EBA  22 42 5C     LD ($5C42),HL    ; NEWPPC = the ON ERR GO TO line
0EBD  FD 36 0A 01  LD (IY+$0A),$01  ; NSPPC  = statement 1
```

Three consequences worth knowing:

- **`INC A` is why `ERRT` is directly usable.** `ERR_NR` follows the ZX
  convention of holding *code − 1*; `ERRT` is the incremented copy, so it
  indexes the report table with no adjustment.
- **`ERRLN`'s high byte doubles as the flag byte.** Line numbers are < 16384,
  so bit 7 ("trapping armed") and bit 6 ("error taken") ride in the spare bits
  and are masked off before the jump. Re-issuing `ON ERR GO TO n` rewrites the
  whole word, which is the clean way to re-arm between tests.
- **Trapping stays armed after a trap** — the handler never clears bit 7. It
  does leave bit 6 set, so re-arm explicitly if you care about that flag.

## Report index table

`ERRT` value ↔ the report the 2068 would have shown. Report letters continue
past 9 into A–R, so the index is a plain 0–27 counter.

| `ERRT` | Report | | `ERRT` | Report |
|---|---|---|---|---|
| 0  | `0 OK`                | | 14 | `E Out of DATA` |
| 1  | `1 NEXT without FOR`  | | 15 | **`F Invalid file name`** |
| 2  | `2 Variable not found`| | 16 | `G No room for line` |
| 3  | `3 Subscript wrong`   | | 17 | `H STOP in input` |
| 4  | `4 Out of memory`     | | 18 | `I FOR without NEXT` |
| 5  | `5 Out of screen`     | | 19 | **`J Invalid I/O device`** |
| 6  | `6 Number too big`    | | 20 | `K Invalid colour` |
| 7  | `7 RETURN without GOSUB` | | 21 | `L BREAK into program` |
| 8  | `8 End of file`       | | 22 | `M RAMTOP no good` |
| 9  | `9 STOP statement`    | | 23 | `N Statement lost` |
| 10 | **`A Invalid argument`** | | 24 | `O Invalid stream` |
| 11 | `B Integer out of range` | | 25 | `P FN without DEF` |
| 12 | **`C Nonsense in BASIC`** | | 26 | **`Q Parameter error`** |
| 13 | `D BREAK - CONT repeats` | | 27 | **`R Tape loading error`** |

## Closing the loop: Pico status byte → what a BASIC test sees

The bold rows above are the ones TS-Pico firmware can actually produce. Putting
the firmware's status byte (see
[`../GUSTAVO_PROTOCOL.md`](../GUSTAVO_PROTOCOL.md) §8) next to what
`PEEK 23739` returns:

| Pico status | Report | `PEEK 23739` | Firmware site |
|---|---|---|---|
| `0x00` | `J` | 19 | TX FIFO empty when the Z80 read — the classic orphan-byte symptom |
| `0x01` | `0 OK` | *(no trap)* | success |
| `0x02` | `R` | 27 | `REFUSE_SAVE(MQ, 0x02)` — bad header CRC, no data block |
| `0x03` | `F` | 15 | `REFUSE_SAVE(MQ, 0x03)` — filename not in the allowlist |
| `0x04` | `Q` | 26 | parameter errors |
| `0x05` | `C` | 12 | unknown `tpi:` command |
| `0x06` | `6` | 6  | `REFUSE_SAVE(MQ, 0x06)` — data block won't fit in RAM |
| `0x08` | `A` | 10 | `REFUSE_SAVE(MQ, 0x08)` — empty program, `BLEN=0` |

[`basic/SD/TAP/picotest-s.bas`](../../basic/SD/TAP/picotest-s.bas) is built on
this table.

## Writing `ON ERR` in a `.bas`

The vendored `zmakebas` knows the TS2068 keywords. Their token codes sit in the
control-code range rather than after `COPY` ($FF), which is why the ROM's
keyword table lists them last but they tokenize to low bytes:

| Keyword | Token |
|---|---|
| `DELETE` | 12 |
| `ON ERR` | 123 (`{`) |
| `STICK`  | 124 |
| `SOUND`  | 125 |
| `FREE`   | 126 |
| `RESET`  | 127 |

So `on err go to 500` tokenizes to `7B EC …` and `on err reset` to `7B 7F`.

Printed, 124 and 126 always come out as STICK and FREE, but 123, 125 and 127
come out as keywords only while FLAGS bit 4 is clear: HOME's print routine
(063Bh) tests it, and the editor sets it in L mode (1683h). Most of the time
`PRINT CHR$ 123` shows `{` (checked in ZEsarUX; see
[the reference](../reference/firmware/tspico-messages.md)).
Verify with a hex dump of the generated `.tap` if a program misbehaves — a
keyword `zmakebas` failed to recognise shows up as plain ASCII letters.

## How to re-derive this

```sh
python3 - <<'PY'
d = open("ROMs/GENUINE-2068-home.bin","rb").read()
for a in (0x5CB6, 0x5CB8, 0x5CBA, 0x5CBB, 0x5C3A):     # ERRLN ERRC ERRS ERRT ERR_NR
    for op, desc in ((0x32,"LD (nn),A"), (0x22,"LD (nn),HL"),
                     (0x3A,"LD A,(nn)"), (0x2A,"LD HL,(nn)")):
        pat = bytes([op, a & 0xFF, a >> 8])
        i = d.find(pat)
        while i >= 0:
            print("$%04X %-11s $%04X" % (i, desc, a)); i = d.find(pat, i+1)
PY
```
