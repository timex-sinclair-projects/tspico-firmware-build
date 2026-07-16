# EXROM: genuine TS2068 → TS-PICO

**The TS-PICO EXROM is the genuine 8K TS2068 EXROM, heavily reworked and doubled to
16K.** Chunk 0 (`0x0000-0x1FFF`) is the genuine ROM with 36 hunks applied; chunk 1
(`0x2000-0x22AD`) is 686 bytes of entirely new code with no genuine ancestor.

**This diff is identical for v1.1 and v1.5w** — everything below `0x22A1` is
byte-for-byte the same in both. See [DIFF_V11_vs_V15W.md](DIFF_V11_vs_V15W.md) for
the 15 bytes that differ.

| | Genuine | TS-PICO v1.1 |
|---|---|---|
| Size | **8192** | **16384** (chunks 0+1, flat at `0x0000-0x3FFF`) |
| crc32 | `ae16233a` | `268649f6` |
| Changed in low 8K | — | 2326 bytes / 36 hunks |
| Free space (`0xFF` runs ≥8B) | 1116 bytes | **84** in chunk 0; 7519 in chunk 1 |

## Baseline

> `2068Exrom.BIN` in `TS2068 Ref Library/2068 ROMS/` (crc32 `526f5676`) is **not
> genuine** — it is 99 bytes / 22 hunks off the real thing, the EXROM half of the
> same modified EPROM set as `WJ-2068-home.bin`. It is kept as
> `ROMs/WJ-2068-exrom.bin` for reference only.

The genuine image (crc32 `ae16233a`) is `ROMs/GENUINE-2068-exrom.bin`, from
`zesarux/src/ts2068.rom` bytes 16384-24575. **Diffing against the W.J. image
inflates this diff from 36 hunks to 51 and fabricates changes that are not
Gustavo's** — see [DIFF_HOME_vs_STOCK.md#baseline](DIFF_HOME_vs_STOCK.md#baseline)
for the full story and proof.

A concrete example of what the bad baseline invents: against `WJ-2068-exrom.bin`,
`BANK_ENABLE` appears to swap `DI`/`EI` for `PUSH BC`/`POP BC` at `0x129A`/`0x131B`
— implying TS-PICO switches banks with interrupts enabled, a genuinely alarming
claim. Against **genuine**, those bytes are *identical in both*. The swap is W.J.'s,
not Gustavo's. **Treat any pre-rebase EXROM analysis with suspicion.**

## How the space was found — the real story of the 36 hunks

Most hunks are not features. They are **space reclamation**, and knowing that makes
the diff legible.

### 1. The genuine ROM repeated a 21-byte thunk 37 times

Every genuine EXROM call into HOME was written out inline:

```asm
dd e5           PUSH IX
d9              EXX
21 xx xx        LD HL,<home_target>
e5              PUSH HL
2e 00           LD L,00h
26 ff           LD H,0FFh
e5              PUSH HL
21 00 00        LD HL,0000h
e5              PUSH HL
e5              PUSH HL
d9              EXX
cd 99 0f        CALL 0F99
```

**21 bytes, 37 times — 777 bytes of near-duplicate code.**

### 2. TS-PICO factored it into `CALL_HOME` at `0x03DD`

Call sites shrank to 9 bytes:

```asm
dd e5           PUSH IX
d9              EXX
21 xx xx        LD HL,<home_target>
c3 dd 03        JP 03DD            ; -> CALL_HOME
```

| | Genuine | TS-PICO |
|---|---|---|
| `CALL 0F99` sites | **43** | 15 |
| Inline 21-byte sites | **37** | 11 |
| Factored 9-byte sites | 0 | **17** |
| `JP 03DD` | **0** | 18 |
| `JP 08DD` | **0** | 6 |

That is why so many hunks look like this — a 21-byte inline sequence collapsing
into a short call plus reclaimed space:

```
01DD-01F3 (23)  old: dd e5 d9 21 30 00 e5 2e 00 26 ff e5 ...
                new: cd e2 01 18 12 dd e5 d9 21 30 00 18 ...
```

The job was left **half done**: 11 genuine inline sites survive untouched at
`0x033B`, `0x048C`, `0x0515`, `0x061D`, `0x072A`, `0x075B`, `0x07A0`, `0x07D1`,
`0x0838`, `0x086F`, `0x08BE`. Converting them would reclaim ~130 more bytes in a
chunk with only 84 left — **the cheapest space available if chunk 0 ever needs it.**

Reproduce:

```bash
python3 - <<'EOF'
import re
inline = re.compile(rb'\xdd\xe5\xd9\x21(..)\xe5\x2e\x00\x26\xff\xe5'
                    rb'\x21\x00\x00\xe5\xe5\xd9\xcd\x99\x0f', re.S)
fact   = re.compile(rb'\xdd\xe5\xd9\x21(..)\xc3\xdd\x03', re.S)
g = open('ROMs/GENUINE-2068-exrom.bin','rb').read()
t = open('ROMs/TSPICO-11-exrom','rb').read()
print("genuine inline:", len(inline.findall(g)))   # 37
print("tspico  inline:", len(inline.findall(t)))   # 11
print("tspico  factored:", len(fact.findall(t)))   # 17
EOF
```

### 3. The 1024-byte hole was filled with the Pico driver

The genuine EXROM had one big gap — `0x1800-0x1BFF`, 1024 bytes of `0xFF`. It is
now completely full and holds the heart of the TS-PICO:

| Addr | What |
|---|---|
| `0x1A54` | `WAIT_PICO_READY` — the ready handshake |
| `0x1A73` | `SESSION_SETUP` — SESSION ID, `TPI:`/`NET:` parsing |
| `0x1B7E` | `SEND_BYTE_CRC` |
| `0x1BA0` | `BUILD_PREHEADER_B` |
| `0x1BF3` | `STATUS_TO_REPORT` |
| `0x1C40` | `SEND_KEY` |

The region `0x1630-0x1D68` is ~1800 bytes of near-total rewrite — "patched genuine
EXROM" understates chunk 0. That range holds the `0x163x` jump table the HOME
thunks target, and `0x1855`.

### 4. Only then was the ROM widened

```
                free space (0xFF runs >= 8 bytes)
genuine EXROM   ####################################  1116 B   (1024 of it at 0x1800)
TSPICO chunk 0  ###                                     84 B   <- effectively full
TSPICO chunk 1  ########################################################  7519 B
```

**Chunk 1 is 92% empty.** That is where new code belongs — appending there moves no
existing address, which is exactly how the v1.5w fix was built.

## Banking: the 8K → 16K change, in three 2-byte edits

`BANK_ENABLE` (EXROM `0x1299`, copied to RAM `0x6499` at boot) does the actual port
work. TS-PICO changed **only the HSR masks**, widening chunk 0 to chunks 0+1:

| Addr | Genuine | TS-PICO | Effect |
|---|---|---|---|
| `0x12DE` | `cb 87` `RES 0,A` | `e6 fc` `AND 0FCh` | clear chunks 0**+1** |
| `0x12E6` | `cb c7` `SET 0,A` | `f6 03` `OR 003h` | set chunks 0**+1** |
| `0x1302` | `cb 87` `RES 0,A` | `e6 fc` `AND 0FCh` | clear chunks 0**+1** |

Plus the boot mask at `0x004A` (`01` → `03`), mirroring HOME `0x0E0C`:

```asm
0049: 3E 03       LD A,003h      ; genuine: 3E 01 -> chunk 0 only (8K)
004B: D3 F4       OUT (0F4h),A   ; HSR: chunks 0+1 -> 0x0000-0x3FFF
```

**That is the entire 16K enablement: four small edits.** Everything else about
banking is untouched genuine code.

Port semantics, confirmed from the code: **`OUT (0F4h)` = HSR**, one bit per 8K
chunk, `1` = chunk from the external bank. **`IN`/`OUT (0FFh)` bit 7**: `0` = DOCK,
`1` = EXROM.

> `0x0F99` (`CALL_B`) and `0x0F8A` (`GOTO_B`) are **byte-identical to genuine** and
> touch **no ports** — they are 15-byte `VIDMOD` dispatchers that jump to the
> RAM-resident `CALL_BANK`/`GOTO_BANK`. The RAM copies (`EXROM 0x13D0`/`0x1372`) are
> also byte-identical to genuine. See
> [DIFF_HOME_vs_STOCK.md](DIFF_HOME_vs_STOCK.md#call_exrom--the-homeexrom-thunk-at-0x3ce3).

## Other chunk-0 functional changes

| Hunk | What |
|---|---|
| `0x0003-0005` | `ff ff ff` → `c3 bc 1c` — a `JP` installed in the reset/entry area. |
| `0x0025` | `00` → `fb` (`EI`). |
| `0x0033-0037` | `ff`×5 → `01 05 ad 07 33` — new data in former filler. |
| `0x005A-006A` | Entry-path rewrite (`c3 ae 1c`). |
| `0x00FC-00FE` | `14 08 15` → `c3 6d 19` — vector into new TS-PICO code. |
| `0x01AB-01D4` | `SESSION_SETUP` entry path. One of the HOME→EXROM entry targets. |
| `0x025C-0285` | Function-chain head — `CP 80h` / `JP NZ,2194` at `0x026F`, plus the `GET_STATUS` bit helpers at `0x025E`/`0x026A`. |
| `0x02B7-02E8` | `READ_STATUS_BYTE` at `0x02B9`. |
| `0x0655-065D` | `READ_STATUS` — `IN A,(0Fh)` behind the BREAK guard. **The only status read in the ROM.** |
| `0x069F-06AB` | `CHECK_BREAK` + `BREAK_ABORT`. |
| `0x08E7` | `EXTINIT`, the EXROM boot entry (HOME `0x0E05` loads it). `21 ea 5e` (`LD HL,5EEA`) → `c3 bc 01` (`JP 01BC`), which does `CALL 221F` then `JP 03F6`. |
| `0x0A52-0A59` | Register reallocation: `CB F9` `SET 7,C` → `CB F8` `SET 7,B`, `71` `LD (HL),C` → `70` `LD (HL),B`. Frees `C` — consistent with the dead `LD C,0Eh` remnant at `0x227F`. |
| `0x0AD4-0AD6` | `2b 36 80` → `cd 82 20` — call into chunk 1. |

## Chunk 1: entirely new (`0x2000-0x22AD`)

No genuine ancestor. Comparing the high 8K against the genuine 8K is meaningless.

```
0x2000-0x203E   entry table  (only 0x2000 is live; 10 slots are JP-self halts)
0x203F-0x2192   BEEPER (relocated verbatim from HOME 0x03F3) + helpers
0x2194-0x2293   FUNCTION dispatch chain (statuses 0x82-0x87)
0x2294-0x22A0   ERR_9, TSPICO_READ_DATA (0x0E), TSPICO_WRITE_DATA (0x0E)
0x22A1-0x22AD   *** v1.5w only: YN_LOOP_GUARD ***
0x22AE-0x3FFF   0xFF filler (7506 bytes free)
```

**`0x203F` is the `BEEPER`**, moved out of HOME to free 43 bytes there. It is
byte-identical to genuine HOME `0x03F3` apart from two `IX` operands (`040F`→`205B`,
`0414`→`2060`), which preserve the same relative offsets. Its four original HOME
call sites (`0x04A7`, `0x0A9A`, `0x0BF7`, `0x0CD5`) are untouched in both ROMs and
now reach it through the `0x03FC` thunk → EXROM `0x2000` → `JP 203F`.

Two things worth repeating:

- **The function chain's head lives in chunk 0** (`0x026F`, `CP 80h`) and jumps to
  chunk 1 (`JP NZ,2194`) for the rest. It straddles both chunks — more proof they
  are mapped together.
- **`CP 86h` appears twice** (`0x21FD`, `0x2213`); the second can never match, so
  its handler at `0x2216` is dead code. See
  [PROTOCOL_FROM_ROM.md](PROTOCOL_FROM_ROM.md#bug-the-second-cp-86h-is-unreachable).

## `0x08DD` — the GOTO counterpart to `0x03DD`

```asm
08D9: D9          EXX                ; <- BADBAS, the genuine "BAD BASIC COMMAND" exit
08DA: 21 ED 1B    LD HL,1BEDh
                                     ; ---- thunk entry ----
08DD: E5          PUSH HL            ; ADDR = HOME target
08DE: 2E 00       LD L,0             ; horizontal select = 00 (all chunks HOME)
08E0: 26 FF       LD H,0FFh          ; bank = FF = HOME
08E2: E5          PUSH HL            ; = FF00
08E3: D9          EXX
08E4: CD 8A 0F    CALL 0F8A          ; GOTO_B -> GOTO_BANK -- NEVER RETURNS
```

`0x08DD-0x08E6` is **byte-identical to genuine** — it is the tail of genuine's
`BADBAS` error exit. Genuine never jumps to `0x08DD`; **TS-PICO's reuse of it as a
shared no-return thunk is the addition.** Callers don't `PUSH IX` because there is
no return to restore it for.

The six `JP 08DD` sites: `0x01B9` (→HOME `0x254F`), `0x01EE` (→`0x24C7`), `0x0249`
(→`0x0008` ERROR), `0x0396` (→`0x2558`), `0x0411` (→`0x3CDC`), `0x17CA` (→`0x0619`).

`0x0411` is a deliberate ping-pong: EXROM → HOME `0x3CDC` → `CALL 1F23` → falls into
the `0x3CE3` thunk → back to EXROM `0x1855`.

## Ports added vs genuine

| Port | Genuine EXROM | TS-PICO EXROM |
|---|---|---|
| `0x0E` | absent | **data port** |
| `0x0F` | absent | **status port** |
| `0xFB` | absent | printer (COPY/LPRINT) |
| `0xFE` | 5 IN | **10 IN** — the five extra are the BREAK polls |

`0xF4`, `0xF5`, `0xF6`, `0xFF`, `0x33`, `0x35`, `0x65` are unchanged. There are **no
register-indirect I/O instructions anywhere**, so this comparison is provably
complete.

## A caveat on the reference disassembly

`TS2068 Ref Library/disassemblies/ts2068 exrom.txt` lists `X_BANK_ENABLE` as
`PUSH AF; PUSH BC; …; RLA; RR C; CCF; RRA` — which matches **neither** shipped
image cleanly. It appears to document **Timex's original source** rather than any
released ROM. Useful for names and intent; **do not trust it byte-for-byte.**
