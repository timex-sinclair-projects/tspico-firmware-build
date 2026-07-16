# TS-PICO ROM images: layout and banking

## Image inventory

| File | Size | md5 | What it is |
|---|---|---|---|
| `ROMs/TSPICO-11-home` | 16384 | `620d6ded106839b73dd6dac9f98f7ed9` | Shipping HOME ROM (v1.1) |
| `ROMs/TSPICO-15w-home` | 16384 | `620d6ded106839b73dd6dac9f98f7ed9` | **Byte-identical to v1.1** |
| `ROMs/TSPICO-11-exrom` | 16384 | `b4a1596823dfda0f9b8dc3d2dec816cb` | Shipping EXROM (v1.1) |
| `ROMs/TSPICO-15w-exrom` | 16384 | `639c62742fa388750a0624e1270e1583` | Next EXROM (v1.5w), 15 bytes from v1.1 |
| `ROMs/GENUINE-2068-exrom.bin` | **8192** | crc32 `ae16233a` | **Genuine** TS2068 EXROM baseline |
| `ROMs/GENUINE-2068-home.bin` | 16384 | crc32 `bf44ec3f` | **Genuine** TS2068 HOME baseline |

The genuine baselines were extracted from
`~/Documents/github/zesarux-tspico-lab/zesarux/src/ts2068.rom` (HOME = bytes
0-16383, EXROM = 16384-24575).

> **The images in `TS2068 Ref Library/2068 ROMS/` are not stock**, despite their
> names — `2068Home.BIN` (crc32 `7d411fe9`) and `2068Exrom.BIN` (crc32 `526f5676`)
> are a modified, partly bit-rotted EPROM dump. They are deliberately **not** kept
> in `ROMs/`, so nobody flashes or diffs against them by accident; `romdiff.py`
> recognises both by crc32 and names them if one turns up. Diffing against them
> inflates the HOME diff from 10 hunks to 26 and the EXROM diff from 36 to 51,
> fabricating changes that are not Gustavo's. See
> [DIFF_HOME_vs_STOCK.md#baseline](DIFF_HOME_vs_STOCK.md#baseline).

## The headline structural fact: the EXROM is 16K, not 8K

The genuine TS2068 EXROM is **8K**. The TS-PICO EXROM is **16K** — double size. It
occupies TS2068 **chunks 0 and 1 simultaneously**, so it is a flat 16K ROM at Z80
`0x0000-0x3FFF`:

```
Z80 address     EXROM file offset   Contents
0x0000-0x1FFF   0x0000-0x1FFF       chunk 0: genuine TS2068 EXROM, patched (36 hunks)
0x2000-0x22AD   0x2000-0x22AD       chunk 1: NEW TS-PICO code (no genuine ancestor)
0x22AE-0x3FFF   0x22AE-0x3FFF       0xFF filler (unused)
```

**File offset == Z80 address** for every image here (HOME and EXROM alike). No
relocation, no header. An address in any disassembly is a file offset and vice
versa.

### Why we know both chunks are mapped at once

This is not an assumption — the code cannot work any other way. The two halves
call each other **directly**, with no bank switch in between:

- **48** direct `CALL`/`JP` transfers from chunk 0 into chunk 1
  (e.g. `02B9: CALL 2298`, `0AD4: CALL 2082`, `1640: CALL 229D`)
- **34** direct transfers from chunk 1 back into chunk 0
  (e.g. `2198: CALL 02B9`, `20BE: CALL 1861`, `21B7: JP 05FA`)

If chunk 1 were a *separate 8K bank* paged over the same `0x0000-0x1FFF` window,
`CALL 2298` from `0x02B9` would be meaningless. It only resolves if `0x2298` is
live at the same time as `0x02B9`.

Verify it yourself:

```bash
python3 - <<'EOF'
b = open('ROMs/TSPICO-11-exrom','rb').read()
xs = [(i, b[i+1] | (b[i+2] << 8)) for i in range(0x2000)
      if b[i] in (0xC3, 0xCD)]
print(len([1 for i, t in xs if 0x2000 <= t <= 0x22AD]), "chunk0 -> chunk1 transfers")
EOF
```

### Consequence for emulators and tooling

Anything that models the TS-PICO EXROM as 8K will fail the moment chunk-0 code
calls into chunk 1. **ZEsarUX's EXROM must be widened from 8K to 16K** to run these
images — this is the root cause of that requirement, and it applies to any other
emulator, ROM programmer, or cartridge image tool in the chain.

## Chunk 1 is nearly empty — and that matters

Only `0x2000-0x22AD` of the 8K chunk-1 window is used: **686 bytes of code, with
7,506 bytes of `0xFF` filler after it.** The TS-PICO team paid for a whole extra 8K
chunk and has so far used 8% of it.

This is why the v1.5w fix was so cheap: the 13-byte guard stub was simply appended
at `0x22A1`, the first free byte. In v1.1 the last non-`0xFF` byte is `0x22A0`; in
v1.5w it is `0x22AD`. Nothing was displaced, no addresses moved.

**There is room for ~7.5K more code at `0x22AE` without disturbing a single
existing address.** Future patches can follow the same append-and-retarget
pattern.

## HOME ROM layout

```
Z80 address     Contents
0x0000-0x3CDB   Genuine TS2068 HOME ROM, patched in 10 hunks / 242 bytes
0x3CDC-0x3CFD   NEW TS-PICO code written into former 0xFF filler,
                including the HOME -> EXROM call thunk at 0x3CE3
0x3D00-0x3FFF   Character set -- UNTOUCHED, byte-identical to genuine
```

The HOME ROM stayed 16K — it had no room to grow, which is precisely why the
TS-PICO's own logic lives in the widened EXROM and the HOME ROM only carries
hooks that redirect into it.

## Crossing between HOME and EXROM

Both ROMs claim `0x0000-0x3FFF`, so only one is visible at a time and every
cross-ROM call goes through a thunk.

| Direction | Thunk | Returns? | Call convention |
|---|---|---|---|
| HOME → EXROM | HOME `0x3CE3` | no | `EXX` / `LD HL,<exrom_target>` / `JP 3CE3` — bytes `d9 21 xx xx c3 e3 3c` |
| HOME → EXROM | HOME `0x0A50` | no | `LD (5DCD),HL` / `LD HL,tgt` / `JP 0A50` |
| HOME → EXROM | HOME `0x03FC` | **yes** | `LD (5DCD),HL` / `LD HL,tgt` / `JP 03FC` |
| EXROM → HOME | EXROM `0x03DD` | **yes** | `PUSH IX` / `EXX` / `LD HL,<home_target>` / `JP 03DD` — bytes `dd e5 d9 21 xx xx c3 dd 03` |
| EXROM → HOME | EXROM `0x08DD` | no | `EXX` / `LD HL,<home_target>` / `JP 08DD` (no `PUSH IX` — nothing to restore) |

The pushed constants encode the destination bank: **`B` = bank** (`0xFF` = HOME,
`0xFE` = EXROM, `0x00` = DOCK) and **`C` = horizontal select, active-low** — a `0`
bit means "take this 8K chunk from that bank". So HOME→EXROM pushes `0xFEFC`
(`1111_1100` → chunks 0+1 → the full 16K EXROM) where the genuine ROM pushed
`0xFEFE` (chunk 0 only, 8K). EXROM→HOME pushes `0xFF00` (all chunks HOME).

Both thunks funnel into `CALL_B`/`GOTO_B` (`0x0F99`/`0x0F8A`), which are
**byte-identical to genuine and touch no ports** — they are `VIDMOD` dispatchers
that jump to `CALL_BANK`/`GOTO_BANK` **in RAM**. The real port work is in
`BANK_ENABLE`, copied from EXROM `0x1299` to RAM `0x6499` at boot.

The `EXX` stashes the caller's registers in the alternate set while `HL` carries
the target address. Grep for those byte patterns to enumerate every cross-ROM call
site:

```bash
# every HOME -> EXROM call site and its target
python3 - <<'EOF'
b = open('ROMs/TSPICO-11-home','rb').read()
for i in range(len(b)-7):
    if b[i] == 0xD9 and b[i+1] == 0x21 and b[i+4:i+7] == b'\xc3\xe3\x3c':
        print("%04X -> EXROM %04X" % (i, b[i+2] | (b[i+3] << 8)))
EOF
```

See [PROTOCOL_FROM_ROM.md](PROTOCOL_FROM_ROM.md) for the thunks' internals and the
full call-site tables.

## TS2068 banking primer (for context)

The TS2068 divides the 64K space into eight 8K **chunks**. Two ports control what
is visible:

| Port | Name | Role |
|---|---|---|
| `0xF4` | Horizontal Select Register (HSR) | One bit per chunk: 1 = take that chunk from the cartridge bus (DOCK or EXROM) instead of HOME |
| `0xFF` | Display / bank control | Bit 7 selects **EXROM** (1) vs **DOCK** (0) for the chunks that HSR has enabled |

Chunk 0 = `0x0000-0x1FFF`, chunk 1 = `0x2000-0x3FFF`. So a 16K EXROM at
`0x0000-0x3FFF` means **HSR bits 0 and 1 set, with port `0xFF` bit 7 = 1**.

## TS-PICO I/O ports

The TS-PICO adds exactly two ports to the genuine TS2068 set. Neither appears
anywhere in the genuine EXROM.

| Port | Direction | Role |
|---|---|---|
| `0x0E` | in / out | **Data port** — command and payload bytes both ways |
| `0x0F` | in / out | **Status / control port** — bit 6 = Pico READY |

Minimal accessors, both in chunk 1:

```asm
2298: DB 0E  A7  C9     TSPICO_READ_DATA:   IN A,(0Eh) ; AND A ; RET   (carry clear)
229D: D3 0E  A7  C9     TSPICO_WRITE_DATA:  OUT (0Eh),A; AND A ; RET   (carry clear)
```

Status is read via `0x0655`, never with a bare `IN A,(0Fh)` — the wrapper adds the
BREAK escape. Full details in [PROTOCOL_FROM_ROM.md](PROTOCOL_FROM_ROM.md).

> **Watch out when grepping for I/O.** A naive scan for `DB xx` / `D3 xx` opcode
> bytes produces heavy false positives: `db 5d` is usually the low byte of a
> `LD (5Dxx),A` referencing a TS-PICO system variable, not `IN A,(5Dh)`. The only
> genuine TS-PICO port I/O sites are `0x0E` at `0x2298`/`0x229D` and `0x0F` at
> `0x065B`, `0x2020`, `0x2023`, `0x2236`.
