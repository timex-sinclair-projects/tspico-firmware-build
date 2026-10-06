# The ROMs: images, layout, banking and the build

Source: the images [`src/rom/TSPICO.ROM`](../../../src/rom/TSPICO.ROM)
(v1.7), [`src/rom/TSPICO-SYNC.ROM`](../../../src/rom/TSPICO-SYNC.ROM)
(2.0), [`src/rom/TSPICO-21.ROM`](../../../src/rom/TSPICO-21.ROM) (2.1),
[`src/rom/TSPICO-ZX48-V4.BIN`](../../../src/rom/TSPICO-ZX48-V4.BIN); the
build [`tools/build-rom.py`](../../../tools/build-rom.py) and
[`tools/build-rom.sh`](../../../tools/build-rom.sh); the analysis tools
[`tools/romdiff.py`](../../../tools/romdiff.py) and
[`tools/romdisasm.sh`](../../../tools/romdisasm.sh); the listings in
[`docs/rom-analysis/disasm/`](../../rom-analysis/disasm/).

The TS-Pico replaces the 2068's ROMs. The Pico serves them from a flash or
SRAM slot, so the 2068 runs a modified HOME ROM and a modified, doubled
EXROM, and those carry the Z80 half of everything in this reference: the
driver that talks to ports 0Eh and 0Fh, the hooks that send LOAD, SAVE,
LPRINT and the disk keywords to the Pico, and the reports the 2068 prints
when something fails. This chapter is the map: which images exist and
which one ships, how a 32K image is laid out, how HOME and EXROM call each
other across the 2068's bank switching, how to tell which ROM a machine
has, how ROM 2.1 is built and checked, and how to read the listings. The
code itself is in the chapters that follow:

| Chapter | Covers |
|---|---|
| [sysvars.md](sysvars.md) | the TS-Pico system variables at 5Dxxh and the stock ones the ROM code uses |
| [home.md](home.md) | every HOME hook and patch, 1.1 to 2.1 |
| [exrom-driver.md](exrom-driver.md) | EXROM 1800h–1BFFh: the Pico driver, the BIOS table, the SAVE and LOAD paths, the reports |
| [exrom-chunk1.md](exrom-chunk1.md) | EXROM 2000h–22FDh and the chunk-0 helpers: the function chain, the accessors, the printer path |
| [exrom-sync.md](exrom-sync.md) | ROM 2.0 at 2300h: SYNC, BREAK, recovery |
| [exrom-fdd.md](exrom-fdd.md) | ROM 2.1 at 3000h: disk commands, `f:`, channels |
| [zx48.md](zx48.md) | the ZX Spectrum ROM, v2 to v4 |

The firmware side of each exchange is in [../firmware/](../firmware/), and
the wire protocol is [PROTOCOL.md](../../PROTOCOL.md). The change history,
patch by patch with the bytes, is [ROM_CHANGES.md](../../ROM_CHANGES.md);
this chapter links to it rather than repeating it.

## The images

All checksums below were computed from the files in the repository.

| Image | File | Size | crc32 | PEEK 101 | What it is | Where it is used |
|---|---|---|---|---|---|---|
| genuine HOME | `ROMs/GENUINE-2068-home.bin` | 16K | `BF44EC3F` | — | the stock TS2068 HOME ROM, bytes 0–16383 of ZEsarUX's `ts2068.rom` | the baseline every HOME diff is measured against |
| genuine EXROM | `ROMs/GENUINE-2068-exrom.bin` | 8K | `AE16233A` | — | the stock 8K EXROM, bytes 16384–24575 of the same file | the EXROM baseline |
| v1.1 | `ROMs/TSPICO-11-home`, `-exrom` | 16K + 16K | `E8714BED`, `268649F6` | 15h | Gustavo Pane's ROM as the boards shipped; the only public release before 2.x | what users still have (the upgrade UF2 replaces it; [../firmware/upgrade.md](../firmware/upgrade.md)) |
| v1.5w | `ROMs/TSPICO-15w-home`, `-exrom` | 16K + 16K | `E8714BED`, `CACF18C5` | 15h | v1.1 plus 15 EXROM bytes: a ready-wait and guard in the Y/N loop | history ([DIFF_V11_vs_V15W.md](../../rom-analysis/DIFF_V11_vs_V15W.md)) |
| v1.7 | `src/rom/TSPICO.ROM` (= `ROMs/TSPICO-17-home` + `-exrom`) | 32K | `09D4CA63` | 17h | v1.5w plus BREAK at the SAVE prompt: 89 EXROM bytes and the version byte | the base `tspico-sync.asm` patches |
| 2.0 | `src/rom/TSPICO-SYNC.ROM` | 32K | `56BD89A4` | 20h | v1.7 plus SYNC, BREAK abort, Report T and the BIOS contract; 274 bytes in 15 hunks, new code at EXROM 2300h–23D3h | the base `build-rom.py` patches; never released on its own |
| **2.1** | `src/rom/TSPICO-21.ROM` | 32K | `F3316DCF` | 21h | 2.0 plus 16 patches and the module at EXROM 3000h–3777h; 2023 bytes in 15 hunks | **flash slot 1**: the release ROM, in the flash image, the upgrade UF2 and the web updater |
| ZX v2 | `ROMs/TSPICO-ZX48-V2.BIN` | 16K | `B3D40C73` | — | the TS-Pico ZX Spectrum ROM before this project | the base of v3/v4 |
| ZX v3 | `src/rom/TSPICO-ZX48-V3.BIN` | 16K | `C4A833B8` | — | v2 plus a WAIT_RDY fix and `LOAD "tpi:…"` | superseded by v4 |
| **ZX v4** | `src/rom/TSPICO-ZX48-V4.BIN` | 16K | `2BA800EF` (`083655BF` padded to the 32K slot) | — | v3 plus `SAVE "tpi:dir"` | **flash slot 0**, the DOCK at power-on |

v1.1 and v1.5w share one HOME (`md5 620d6ded…`). The md5s of the 1.x
halves are in [docs/rom-analysis/README.md](../../rom-analysis/README.md#rom-images);
`tools/romdiff.py` checks every image in `ROMs/` against its `EXPECT_CRC`
at each run and names any that differ, because other TS2068 ROM images are
in circulation and every hunk count is only meaningful against these exact
baselines. The slot-0 crc32 in
`flash/manifest.json` is of the image padded with `00h` to 32K, which is
why it differs from the file's own.

The lineage, in one line: genuine → v1.1 (Gustavo) → v1.5w → v1.7
(Gustavo) → 2.0 (`src/rom/patches/tspico-sync.asm`) → 2.1
(`src/rom/fdd/fddcmd.asm` + `build-rom.py`'s patches). From 2.0 on, the ROM
and the firmware share one version number: firmware 2.1.x runs ROM 2.1
([../firmware/boot.md](../firmware/boot.md#releases-releaseyml)). ROM 2.0
and later need firmware that understands the SYNC byte; older firmware
reads it as the first byte of a command
([ROM_CHANGES.md](../../ROM_CHANGES.md#lineage)).

## The 32K file

A 2068 ROM image here is one 32K file: **HOME at file offset 0000h, EXROM
at 4000h**. Within each half, **file offset = Z80 address**: EXROM address
1A54h is file offset 5A54h, HOME address 1A54h is file offset 1A54h. There
is no header and no relocation. The ZX images are a single 16K ROM at
offset 0. Every address in this reference is a Z80 address, and it says
"HOME" or "EXROM" where that is not obvious.

### HOME

| Z80 | Contents |
|---|---|
| 0000h–3CDBh | the genuine HOME ROM, with hooks: 10 hunks (242 bytes) in v1.1, a version byte in v1.7, 14 bytes in 2.0, 100 bytes in 2.1 |
| 3CDCh–3CFDh | new TS-Pico code in the genuine ROM's `FFh` filler, including the HOME→EXROM thunk at 3CE3h |
| 3D00h–3FFFh | the character set, untouched |

HOME stayed 16K and had no room to grow, which is why the TS-Pico's logic
lives in the EXROM and HOME carries only hooks into it. 2.1's HOME patches
reuse dead code (the disk-keyword stub at 25D6h, an unreferenced SYSCON
remnant at 1488h–14C6h) rather than free space. All of it: [home.md](home.md).

### EXROM

The genuine EXROM is 8K. **The TS-Pico EXROM is 16K**, a flat ROM at Z80
0000h–3FFFh occupying the 2068's chunks 0 and 1 at the same time:

| EXROM | Size | Contents | Since | Chapter |
|---|---|---|---|---|
| 0000h–17FFh | | the genuine EXROM, patched (36 hunks, 2326 bytes in v1.1) | 1.1 | [exrom-chunk1.md](exrom-chunk1.md) (the paths), [home.md](home.md) |
| 1800h–1BFFh | 1K | the Pico driver and the BIOS table, in the genuine ROM's empty hole | 1.1 | [exrom-driver.md](exrom-driver.md) |
| 1C00h–1FFFh | | genuine, patched (the banner at 1C6Ch) | 1.1 | [exrom-driver.md](exrom-driver.md) |
| 2000h–22ADh | 686 | chunk 1's first code: the landing pad, the function chain, the accessors | 1.1 (22A1h–22ADh v1.5w) | [exrom-chunk1.md](exrom-chunk1.md) |
| 22AEh–22FDh | 80 | the SAVE-prompt BREAK routine | 1.7 | [exrom-chunk1.md](exrom-chunk1.md) |
| 2300h–23D3h | 212 | SYNC, BREAK abort, the BIOS wait | 2.0 | [exrom-sync.md](exrom-sync.md) |
| 23D4h–2FFFh | 3116 | `FFh`, free | | |
| 3000h–3777h | 1912 | the disk-command module | 2.1 | [exrom-fdd.md](exrom-fdd.md) |
| 376Dh–3FFFh | 2195 | `FFh`, free | | |

Chunk 0 is effectively full: the 1K hole at 1800h was used for the driver,
and the stock "call into HOME" sequence, repeated through the ROM, was
factored from 21 bytes to 9 at 17 sites to reclaim room
([SYMBOLS.md](../../rom-analysis/SYMBOLS.md#cross-rom-machinery)); about
84 bytes are left. **New EXROM code goes in chunk 1.** The fdd module's
README reserves 3000h–3FFFh for that module.

**Why both chunks must be paged at once.** The two halves call each other
directly, with no bank switch between: in v1.1, 48 `CALL`/`JP`s from chunk 0
into chunk 1 and 34 back (e.g. `02B9h: CALL 2298h`, `2198h: CALL 02B9h`),
counted in [MEMORY_MAP.md](../../rom-analysis/MEMORY_MAP.md#why-we-know-both-chunks-are-mapped-at-once).
A raw byte scan of 2.1 finds 51 and 73 (it over-counts: data bytes that
happen to look like a `CALL`). `CALL 2298h` from 02B9h means something only
if 2298h is visible at the same time. So anything that models the TS-Pico
EXROM as 8K — an emulator, a cartridge tool — fails at the first such
call; ZEsarUX's EXROM had to be widened for this reason.

## Banking: how HOME and the EXROM reach each other

The 2068 divides its 64K into eight 8K **chunks**. Two ports decide what
each shows:

| Port | Name | Role |
|---|---|---|
| F4h | HSR, the horizontal select register | one bit per chunk: 1 = take that chunk from the cartridge bus (the DOCK or the EXROM) instead of HOME |
| FFh | display and bank control | bit 7: the EXROM (1) or the DOCK (0), for the chunks the HSR selects |

So the 16K EXROM is HSR bits 0 and 1 set, with FFh bit 7 set. On the
TS-Pico both the "EXROM" and the "DOCK" come from the Pico's memory slots
(the BOOT and DOCK slots of [../hardware.md](../hardware.md) and
[../firmware/pio.md](../firmware/pio.md)); the 2068 does not know.

HOME and the EXROM both claim 0000h–3FFFh, so one cannot call the other
directly. Every crossing goes through a **thunk**, which pushes the target
address and a bank word, then hands over to the 2068's own bank-switching
code:

| Thunk | Direction | Returns | How it is called | Pushes |
|---|---|---|---|---|
| HOME 3CE3h | HOME → EXROM | no | `EXX` / `LD HL,target` / `JP 3CE3h` | target, `FEFCh` |
| HOME 0A50h | HOME → EXROM | no | `LD (5DCDh),HL` / `LD HL,target` / `JP 0A50h` | target, `FEFCh` |
| HOME 03FCh | HOME → EXROM | **yes** | `LD (5DCDh),HL` / `LD HL,target` / `JP` or `CALL 03FCh`; 2.1 wraps every use in `DI` … `EI` | target, `FEFCh`, two zero words |
| EXROM 03DDh | EXROM → HOME | **yes** | `PUSH IX` / `EXX` / `LD HL,target` / `JP 03DDh` | target, `FF00h`, two zero words; `POP IX` after |
| EXROM 08DDh | EXROM → HOME | no | `EXX` / `LD HL,target` / `JP 08DDh` (genuine bytes, the tail of BADBAS, reused) | |

The bank word is `B` = the bank (`FFh` HOME, `FEh` EXROM, `00h` DOCK) and
`C` = the chunks, active low (a 0 bit takes that chunk from the bank).
`FEFCh` is "EXROM, chunks 0 and 1", where the genuine ROM pushed `FEFEh`,
chunk 0 only; `FF00h` is "HOME, every chunk". That one-byte change, and
the HSR mask in the boot code (HOME 0E0Ch, `01` → `03`), are what make the
EXROM 16K.

The thunks end in the genuine `CALL_B`/`GOTO_B` dispatchers (EXROM
0F99h/0F8Ah; HOME keeps a byte-identical copy at 040Dh), which touch no
ports: they test VIDMOD (5CC2h) and jump to the bank-switch code **in RAM**
— 6572h/65D0h with normal video, FD32h/FD90h when VIDMOD is non-zero
(64-column video, where the 2068 moves that code to high RAM to clear the
second display file; [DIFF_HOME_vs_STOCK.md](../../rom-analysis/DIFF_HOME_vs_STOCK.md)). The port work is in
`BANK_ENABLE`, genuine code at EXROM 1299h that the 2068 copies to RAM at
6499h at boot; the TS-Pico widened its HSR masks from chunk 0 to chunks 0+1
(three hunks). The routines in RAM keep a **bank stack** whose pointer is
the word at 65CEh; the returning thunks push a frame there and pop it on
the way back. System variables: [sysvars.md](sysvars.md).

Two things about this machinery shaped ROM 2.1
([ROM_CHANGES.md](../../ROM_CHANGES.md#rom-21-home-and-exrom-patches)):

- **The switch is not atomic.** It writes port FFh, then F4h, with
  interrupts enabled. Between the two, chunk 0 can be the empty DOCK; an
  interrupt there runs `RST 38h` over `FFh` bytes. Stock code switches a
  few times per command and never hit it; a 2.1 file channel switches for
  every character and hit it within a few hundred in ZEsarUX. So every 2.1
  entry into the module is `DI / LD HL,vector / CALL 03FCh / EI`, and the
  BEEPER thunk was moved under `DI` too.
- **A report raised inside a returning thunk leaks the bank stack.** RST 8
  unwinds the Z80 stack to ERR_SP but not the bank stack at 65CEh: each
  error left it 4–8 bytes lower, and after about 16 errors it overwrote the
  bank-switch code below it. 2.1's module runs every entry inside
  `GUARDED`, which installs an error handler in HOME at 14B2h (`H_TRAP`)
  that puts 65CEh back before going on to the old handler
  ([exrom-fdd.md](exrom-fdd.md), [home.md](home.md)).

Every HOME→EXROM call site and its target: [home.md](home.md). The
EXROM→HOME sites (17 factored through 03DDh, 11 unfactored genuine inline
copies): [SYMBOLS.md](../../rom-analysis/SYMBOLS.md#cross-rom-machinery).

## Which ROM is this?

Four places say, and they are changed together:

| Where | v1.1 | v1.7 | 2.0 | 2.1 |
|---|---|---|---|---|
| HOME 0065h (`PEEK 101`) | 15h | 17h | 20h | 21h |
| BIOS G_VERS (EXROM 1844h → 1852h, `LD BC,nnnn`) | | 0017h | 0020h | 0021h |
| the banner at EXROM 1C6Ch, at start-up | | "2025 Timex Pico Interface" | "2026 TS-Pico ROM v2.0" | "2026 TS-Pico ROM v2.1" |
| the module's FDD_VERSION (EXROM 30AFh) | | | | 8 |

A BASIC program tests `PEEK 101`; machine code calls G_VERS through the
BIOS table ([exrom-driver.md](exrom-driver.md)). FDD_VERSION counts
revisions of the module within 2.1 and follows the signature `"FDDCMD"` at
30A8h ([exrom-fdd.md](exrom-fdd.md)). The firmware does not read any of
them: its `ROM_VERSION` is a string in `config.ini`
([../firmware/boot.md](../firmware/boot.md#configini)).

## Where the ROM touches ports 0Eh and 0Fh

Every `IN`/`OUT` on the TS-Pico's two ports in ROM 2.1 (HOME has none):

| EXROM | Instruction | In | Purpose |
|---|---|---|---|
| 065Bh | `IN A,(0Fh)` | READ_STATUS | the status read every ready-wait uses, after a BREAK check |
| 2298h | `IN A,(0Eh)` | the read accessor | every data byte from the Pico |
| 229Dh | `OUT (0Eh),A` | the write accessor | every data byte to the Pico |
| 2304h | `OUT (0Fh),A` (03h) | SYNC_WRITE | SYNC at the start of a transaction |
| 2311h | `IN A,(0Fh)` | SYNC_WAIT | waiting for READY + IDLE after SYNC |
| 2320h | `OUT (0Fh),A` (03h) | BRK_ABORT | the abort on BREAK |
| 23A7h | `IN A,(0Fh)` | BIOS WF_NPH | the BIOS ready-wait |
| 23C0h | `OUT (0Fh),A` (03h) | BIOS WF_NPH | its BREAK abort |
| 3662h | `IN A,(0Fh)` | CH_SEND | a channel command waits for IDLE before its SYNC |
| 2020h, 2023h | `OUT (0Fh),A` (20h, then 00h) | — | dead: after a `RET`, never called ([PROTOCOL_FROM_ROM.md](../../rom-analysis/PROTOCOL_FROM_ROM.md#0x2000-0x203e-is-a-relocation-landing-pad-not-an-api-table)) |
| 2236h | `OUT (0Fh),A` (00h) | — | after a `RET`; nothing jumps or calls here *(inferred unreachable)* |

Data always goes through the two accessors and status through 065Bh, so a
change to the bus protocol on the Z80 side starts there. Since firmware
2.0 any write to port 0Fh is SYNC or BREAK to the Pico
([PROTOCOL.md §4.1](../../PROTOCOL.md#41-sync-rom-20-and-firmware-20)); the
dead writes at 2020h/2023h/2236h would be read that way if they ever ran.
A scan for `DBh`/`D3h` opcode bytes finds many false hits: `DB 5D` is
usually the low byte of an `LD (5Dxxh),A` to a TS-Pico system variable.

## Building the ROMs

Nothing here assembles a whole ROM. Each new ROM is the previous one plus
patches, and every patch states the bytes it expects to replace, so a base
that has changed under it fails the build instead of being silently
corrupted. Both tools use sjasmplus (CI builds v1.22.0 from source; it
makes byte-identical output).

### `tools/build-rom.sh`: ROM 2.0 and the ZX ROMs

Runs sjasmplus three times in `src/rom/` and then the two tests that check
the results:

| Source | Base | Output |
|---|---|---|
| `patches/tspico-sync.asm` | `TSPICO.ROM` (v1.7, crc `09D4CA63`) | `TSPICO-SYNC.ROM` (2.0) |
| `patches/tspico-zx48-v3.asm` | ZX v2 | `TSPICO-ZX48-V3.BIN` |
| the same with `-DZXV=4` | ZX v2 | `TSPICO-ZX48-V4.BIN` |

Each source `INCBIN`s its base image and overlays its patches with `FPOS`
+ `ORG` (hence `-Wno-fileorg`), writing a listing (`.lst`) beside it.
[`rom_sync_hosttest.py`](../../../src/test/rom_sync_hosttest.py) checks every
2.0 patch site and the v1.7 bytes it replaced;
[`rom_zx48_hosttest.py`](../../../src/test/rom_zx48_hosttest.py) the ZX ones.
CI does not run this script — it runs the two tests on the committed
images — so a change to these sources is rebuilt by hand and the image
committed. The script's header notes that `src/rom/TSPICO.ROM`, the v1.7
base, is never modified (slot 1 is `TSPICO-21.ROM`; until #181 the header
called `TSPICO.ROM` the shipping slot-1 ROM). The ZX sources:
[zx48.md](zx48.md); the 2.0 source: [exrom-sync.md](exrom-sync.md).

### `tools/build-rom.py`: ROM 2.1

1. Requires sjasmplus; reads `src/rom/TSPICO-SYNC.ROM` and refuses unless
   its crc32 is `BASE_ROM_CRC` = `56bd89a4`.
2. Assembles `src/rom/fdd/fddcmd.asm` in a temporary directory: the module
   binary (`SAVEBIN`) and its symbols. `FDD_DISPATCH` must equal `FDD_ORG`
   = 3000h (the module's `FDD_BASE`; keep the two in step).
3. Checks every **anchor** (below) in the base: code the module calls or
   jumps into but does not patch.
4. Splices the module in at EXROM 3000h (file 7000h), after asserting that
   the region is all `FFh` and the module ends before EXROM 4000h.
5. Applies the **patches** (below): for each, the bytes at the site must be
   exactly `before`, and `before` and `after` must be the same length.
6. Writes `build/TSPICO-fdd.ROM` and its halves `TSPICO-fdd-home.bin`,
   `TSPICO-fdd-exrom.bin`, prints the crc32, and lists every hunk that
   differs from the base (bytes within 8 of each other are one hunk).
7. `--verify`: fails if any changed byte lies outside the module region and
   the patch sites. `--keep` copies the module's `.bin` and `.sym` to
   `build/`.

`--rebase` is for when a new base ROM is merged: it checks every patch's
`before` bytes and every anchor against the new base and that 3000h–3FFFh
is still free, and only then rewrites `BASE_ROM_CRC` in its own source. A
moved site refuses, naming it: a patch that no longer fits needs a person,
not a new checksum. It leaves `ROMs/` and `romdiff.py`'s `EXPECT_CRC` alone.

After a change to the module or the patches: `python3 tools/build-rom.py
--verify`, copy `build/TSPICO-fdd.ROM` over `src/rom/TSPICO-21.ROM`, and
set slot 1's crc32 in `flash/manifest.json` (`tools/build-flash.py check`
prints it). CI ([../firmware/boot.md](../firmware/boot.md#ci-buildyml))
runs `--verify`, fails if the committed `TSPICO-21.ROM` differs from the
fresh build by a single byte, checks the manifest's crc32, and runs
`rom_cend_hosttest.py` on `C_END2` and `rom_tpmode_hosttest.py` on the
switch words in a Z80 interpreter.

#### The patches

Sixteen, applied in this order. The reason for each is in the source's
`note`, and in full, with what it calls, in the chapter named.

| Site | Before → after | What it does | Chapter |
|---|---|---|---|
| HOME 1946h | `d0 c0 c4 c8` → `d2 c2 c6 ca` | the syntax-table offsets of CAT, FORMAT, MOVE, ERASE skip the string-and-comma prefix: a bare keyword is accepted | [home.md](home.md) |
| EXROM 01D2h | `JP 1A73h` → `JP 3003h` | SAVE-ETC's only jump to SESSION_SETUP now goes through F_HOOK, which takes `f:` names | [exrom-fdd.md](exrom-fdd.md) |
| EXROM 2213h | `CP 86h / RET NZ / CALL 02B9h` → `CP 87h / JP Z,3006h / RET` | the unreachable second `CP 86h` becomes response function 88h, the lower-screen Y/N loop | [exrom-chunk1.md](exrom-chunk1.md) |
| HOME 25D6h | the 14-byte disk-keyword stub → `DI / LD HL,3000h / CALL 03FCh / EI / RET` + 5 × `00` | CAT, FORMAT, MOVE, ERASE enter the module with B = the token, on both passes | [home.md](home.md) |
| HOME 1488h | 55 bytes of dead SYSCON code → four trampolines and H_TRAP | OPEN # (1488h), CLOSE # (1494h), an `F` record's output (14A0h) and input (14A9h), the error trap (14B2h) | [home.md](home.md) |
| HOME 03F3h | the BEEPER thunk → `DI / LD (5DCDh),HL / LD HL,3015h / JR 041Ch` | BEEPER's round trip under `DI` | [home.md](home.md) |
| HOME 041Ch | 5 dead bytes → `CALL 03FCh / EI / RET` | the BEEPER thunk's tail | [home.md](home.md) |
| HOME 145Eh | `CALL 1465h` → `CALL 1488h` | OPEN # through its trampoline | [home.md](home.md) |
| HOME 1438h | `CALL 2569h` → `CALL 14BDh` | OPEN # syntax parses `,mode[,reclen]` | [home.md](home.md) |
| HOME 14BDh | 9 dead bytes → `DI / LD HL,3018h / CALL 03FCh / EI / RET` | the OPEN # syntax trampoline | [home.md](home.md) |
| HOME 13A5h | `CALL 13BEh` → `CALL 1494h` | CLOSE # through its trampoline | [home.md](home.md) |
| EXROM 184Fh | `JP 23CDh` → `JP 301Bh` | BIOS C_END becomes C_END2: a timeout is J, not F | [exrom-driver.md](exrom-driver.md), [exrom-fdd.md](exrom-fdd.md) |
| EXROM 20BEh | `CALL 1861h / JR 2108h` → `JP 301Eh` + 2 × `00` | `tpi:tape` clears only the LOAD/SAVE switch (TPMODE bit 1), through the module's TAPE_MODE; it used to set TPMODE to 0, turning the printer switch off too (#176) | [sysvars.md](sysvars.md#5ddbh-tpmode-peek-24027), [exrom-fdd.md](exrom-fdd.md) |
| EXROM 1C7Eh | `"v2.0"` → `"v2.1"` | the banner | [exrom-driver.md](exrom-driver.md) |
| HOME 0065h | `20h` → `21h` | `PEEK 101` | [home.md](home.md) |
| EXROM 1852h | `LD BC,0020h` → `LD BC,0021h` | BIOS G_VERS | [exrom-driver.md](exrom-driver.md) |

The resulting 2.0 → 2.1 difference, measured on the committed images: 2023
bytes in 15 hunks: 99 in HOME, 16 in the EXROM outside the module, and
1908 in the module's region — 4 of the module's 1912 bytes are `FFh`, the
same as the free space they replaced. The byte-by-byte account is
[ROM_CHANGES.md](../../ROM_CHANGES.md#rom-21-home-and-exrom-patches).

#### The anchors

Base-ROM code the module relies on without patching it. Each is a few
bytes the build checks before it builds (and `--rebase` before it
rebases); the module's `EQU`s name the same addresses, and the two lists
must be kept in step.

| Address | What the module relies on |
|---|---|
| EXROM 1A73h | SESSION_SETUP's entry, which TPI_SEND repeats |
| EXROM 1AACh | SESSION_SETUP past its 5–31-character name gate (SESSION_NAMED) |
| EXROM 03DDh | the EXROM→HOME returning thunk |
| EXROM 0008h | the EXROM's `RST 8` error restart (Reports C, F from the module) |
| HOME 1BEFh | syntax class 0Ah, a string expression |
| HOME 1FBBh | TEST-ROOM |
| EXROM 01D5h | stock SAVE-ETC after SESSION_SETUP's non-command exit |
| EXROM 1A45h | that exit, which F_HOOK copies |
| EXROM 1BF3h | STATUS_TO_REPORT: status − 1 in A → report |
| EXROM 2300h | SYNC_WRITE (ROM 2.0) |
| EXROM 23CDh | ROM 2.0's BIOS C_END |
| EXROM 227Fh | C_END's tail after its wait (C_END2 jumps here) |
| EXROM 1846h | the BIOS table: TX_A, RX_A, C_END, WF_NPH |
| EXROM 01C3h | function 86h's opening (READ_STATUS, then open stream FEh), which LOWER_LOOP reuses |
| EXROM 04F1h | open stream FEh through 0426h |
| EXROM 21E3h | the 86h handler and its loop at 21E6h |
| HOME 03FCh | the returning HOME→EXROM thunk |
| EXROM 2000h | `JP` to the relocated BEEPER (G_BEEP calls it) |
| EXROM 2105h | `CALL S_MODE / CALL 042Fh / JP 1B72h`: where `tpi:sdcard` and `tpi:picopt` store TPMODE and say "0 OK"; TAPE_MODE ends here (MODE_SET_OK) |
| HOME 12BBh | MAKE-ROOM (OPEN # appends a record) |
| HOME 1750h | RECLAIM (CLOSE # removes it) |
| HOME 1230h | CHAN-OPEN; its `D OR E ≥ 80h` test sets the offset rule for records |
| HOME 140Fh | the OPEN/CLOSE # stream fetch: (5CCBh) = n |
| HOME 1461h | OPEN # storing DE in the STRMS entry after the 145Eh call |
| HOME 13A8h | CLOSE # resetting the STRMS entry after the 13A5h call |
| HOME 11EDh | `RST 10` output through CURCHL's record, HL restored after |

### `tools/romdiff.py`

Diffs pairs of images in `ROMs/` and prints the hunks (`--json OUT` also
writes them, as `docs/rom-analysis/hunks.json`): genuine → v1.1 HOME (242
bytes, 10 hunks), genuine → v1.1 EXROM chunk 0 (2326 bytes, 36 hunks), v1.1
→ v1.5w EXROM (15 bytes, 2 hunks), v1.5w → v1.7 (89 EXROM bytes in 4
hunks, 1 HOME byte). It checks each image's crc32 against `EXPECT_CRC` and
says so when one differs. It covers the 1.x line only; the 2.x differences
are produced by `build-rom.py`'s hunk report and the hand-written
[ROM_CHANGES.md](../../ROM_CHANGES.md).

## Reading the listings

[`tools/romdisasm.sh`](../../../tools/romdisasm.sh) regenerates
`docs/rom-analysis/disasm/` with `z80dasm` (org 0 for every image, since
file offset = Z80 address):

| File | What |
|---|---|
| `tspico-21-exrom.labelled.asm` | **ROM 2.1's EXROM, labelled. The one this reference cites.** |
| `tspico-21-exrom-symbols.sym` | its labels, generated: the curated names of `docs/rom-analysis/tspico-exrom-symbols.sym`, plus every label of `tspico-sync.asm` (2300h) and `fddcmd.asm` (3000h) from a fresh sjasmplus assembly, EXROM addresses (0100h–3FFFh) only. Edit the sources, not this |
| `tspico-21-home.asm`, `.sym` | ROM 2.1's HOME, a raw sweep with `z80dasm`'s own `lXXXXh` labels |
| `tspico-11-exrom.labelled.asm`, `tspico-15w-exrom.labelled.asm` | the 1.x EXROMs, labelled with the curated names |
| `tspico-11-exrom.asm`, `tspico-15w-exrom.asm`, `tspico-home.asm`, `genuine-2068-*.asm` (+ `.sym`) | raw sweeps |

How to use them:

- **Find an address** by its comment: every line ends with the address in
  lower-case hex and the bytes, `;1a54  cd 55 06`. In HOME,
  `grep -n ';0f12' tspico-21-home.asm`; an address in the middle of an
  instruction is not found, so try the bytes before it.
- **They are linear sweeps.** Text, tables and `FFh` filler disassemble as
  nonsense, and a sweep that starts inside an instruction stays out of
  step until it happens to resynchronise. Find a known label first and
  read from there. The hand-checked listings in the Markdown documents
  outrank the sweeps.
- **Status − 1.** The function chain reads the Pico's first byte, does
  `DEC A` (EXROM 228Ah), then compares: every `CP nn` there matches status
  `nn + 1`. `CP 85h` is function 86h. Likewise `STATUS_TO_REPORT` at
  1BF3h takes A = status − 1 ([exrom-chunk1.md](exrom-chunk1.md),
  [exrom-driver.md](exrom-driver.md)).
- **Labels.** The curated names (WAIT_PICO_READY, READ_STATUS,
  STATUS_TO_REPORT …) are inferred from what the code does, not Gustavo's;
  the names at 2300h and 3000h are the sources' own. To improve the 1.x
  regions, add a name to `docs/rom-analysis/tspico-exrom-symbols.sym` and
  rerun the script (it needs sjasmplus as well as z80dasm for the 2.1
  listings).

## The analysis documents

[`docs/rom-analysis/`](../../rom-analysis/README.md) holds the
reverse-engineering behind these chapters. Where the ROM and a document
disagree, the ROM wins; the documents flag disagreements rather than
smooth them over.

| Document | Read it for |
|---|---|
| [README.md](../../rom-analysis/README.md) | the images and their checksums, the main findings, the caveats |
| [MEMORY_MAP.md](../../rom-analysis/MEMORY_MAP.md) | layout, banking, the thunks, the proof that the EXROM is 16K |
| [PROTOCOL_FROM_ROM.md](../../rom-analysis/PROTOCOL_FROM_ROM.md) | the wire protocol as the ROM implements it: the ready-wait and its ~19.9 s, status − 1, reports, the function chain, the pre-header, the system variables |
| [SYMBOLS.md](../../rom-analysis/SYMBOLS.md) | an address → name index for both ROMs |
| [DIFF_HOME_vs_STOCK.md](../../rom-analysis/DIFF_HOME_vs_STOCK.md), [DIFF_EXROM_vs_STOCK.md](../../rom-analysis/DIFF_EXROM_vs_STOCK.md) | what v1.1 changed from the genuine ROMs |
| [DIFF_V11_vs_V15W.md](../../rom-analysis/DIFF_V11_vs_V15W.md) | the 15-byte v1.5w fix |
| [REVIEW_ROM_V17_SAVE_BREAK.md](../../rom-analysis/REVIEW_ROM_V17_SAVE_BREAK.md) | v1.7's BREAK at the SAVE prompt |
| [BREAK_AND_ABORT.md](../../rom-analysis/BREAK_AND_ABORT.md) | what BREAK does, and what 1.x never told the Pico |
| [ERROR_TRAPPING.md](../../rom-analysis/ERROR_TRAPPING.md) | how ON ERR reports a code; the 2068's keyword tokens |
| [PATCH_ZX48_HANDSHAKE.md](../../rom-analysis/PATCH_ZX48_HANDSHAKE.md) | the ZX v2 ROM |
| [`hunks.json`](../../rom-analysis/hunks.json) | `romdiff.py`'s output |

The 1.x documents describe v1.1 and v1.5w; where 2.x changed something
(the dead `CP 86h`, now function 88h; the BIOS C_END), the 2.x chapters
here say so. [ROM_CHANGES.md](../../ROM_CHANGES.md) is the account of 2.0,
2.1 and ZX v3/v4.

## Where comments and the code disagree

Tracked in the [`reference-followup` issues](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues?q=label%3Areference-followup).

- [docs/rom-analysis/README.md](../../rom-analysis/README.md) lists the
  port sites of v1.1; 2.0 and 2.1 add the seven at 2304h–23C0h and 3662h
  (the table above).
