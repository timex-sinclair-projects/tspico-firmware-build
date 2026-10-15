# Disk commands for the TS-Pico — recommended specification

**Status: proposal.** This is the user-facing contract: what each statement
accepts and what it does. The ROM mechanism is in
[`FDD_COMMANDS_DESIGN.md`](FDD_COMMANDS_DESIGN.md), and this spec assumes it.

**Inputs:**

- The Zebra FDD-3 manual ([`ZEBRA_FDD_TOS_MANUAL.md`](ZEBRA_FDD_TOS_MANUAL.md)).
  TOS is used for its feature ideas, not its syntax.
- The TS2068 HOME ROM's statement tables.
- What the firmware already does behind `SAVE "tpi:..."`.

**Non-goals:**

- FDD-3 compatibility.
- The `*` suffix and the RST 8 vector.
- Microdrive-style device arguments (`"m";1;"name"`).
- Drive letters, serial ports (SCPs), the TOS directory stack (`GO SUB *` and `DRAW *`), and `ATTR *` protection.

---

## 1. What the ROM lets us have

The HOME ROM gives us **six keywords** to work with. The rest of the TOS
command set can't be copied without `*`.

| Keyword | Token | Stock behaviour | After the hook |
|---|---|---|---|
| `CAT` | `$CF` | Syntax needs `CAT "x",…`, then Report J at run time | We parse everything after the keyword |
| `FORMAT` | `$D0` | Same | Same |
| `MOVE` | `$D1` | Same | Same |
| `ERASE` | `$D2` | Same | Same |
| `OPEN #` | `$D3` | `OPEN #n,"x"`. Anything other than K/S/P gives Report J | We extend the channel letters (phase 3) |
| `CLOSE #` | `$D4` | `CLOSE #n` | Same |

Each of the first four has a stock parameter-table entry of `0A 2C 05 xx 25`:
string expression, literal `,`, then routine. This is why `CAT` and
`CAT "x"` are syntax errors on a stock machine, and only `CAT "x",` gets
through. The hook moves each entry two bytes forward, so it starts at class `$05`
("the routine checks its own syntax"). That takes 4 bytes at `$1946–$1949` plus 3 at `$25D6`.
It has been verified in ZEsarUX.

**So bare `CAT` works, and so does `CAT "*.tap"`, `CAT a$`, `CAT #3`, or any
other form. None of them needs a trailing comma or an empty string.** The only
rule is that each form is parsed by our own routine in both passes:

- **Syntax pass:** consume the arguments and accept the line.
- **Run pass:** evaluate the arguments and send the command.

### Why the other TOS verbs can't come along

TOS overloads `GO TO *`, `GO SUB *`, `DIM *`, `LET *`, `LIST *`, `DRAW *` and
`ATTR *`. Without the `*`, each of those is a core statement with a fixed
syntax class. For example, `GO TO` wants a number, so `GO TO "games"` is Nonsense in
BASIC at line entry. Taking them over would mean patching the core statements'
syntax paths, and every `GO TO` in every program would pay for it. Don't.
Change-directory, make-directory and rename go onto the four free keywords
through keyword-inside-argument forms (§3), or stay on `SAVE "tpi:..."`.

### Argument rules common to all four

- **Every string argument is a string *expression*.** `CAT a$`,
  `ERASE "old"+n$` and so on must work. The routine calls the ROM's expression
  evaluator (`SCANNING` or `EXPT-EXP`), not a scan of the literal line text.
  *The fdd3000 branch currently takes literals only, so this is a change.*
- **Paths:** `/` is the separator, a leading `/` means from the SD root, and `..` goes up.
  Case-insensitive, as the firmware already is.
- **Wildcards:** `*` matches any run of characters and `?` matches one character.
  They are allowed only in the last path component. TOS used `+` for "any";
  everyone now expects `*`.
- **Errors come back as normal reports**, so `ON ERR` and `ERRT` work:
  - F *Invalid file name*: a bad name, or no match.
  - Q *Parameter error*: bad syntax at run time, a wildcard where one isn't allowed, or a non-empty directory.
  - 8 *End of file*: the target is missing.
  - J *Invalid I/O device*: kept for "the Pico didn't answer".

  The firmware already maps status to report for the `'B'` block.
- **Long output** uses the existing `Scroll? (Y/n)` pager. BREAK stops it.

---

## 2. `CAT` — catalogue

**Implemented** (ROM `fddcmd.asm` v4, firmware `CATALOG` + `TS/catalog.py`).
`CAT` is a front end for `tpi:dir`, so **`SAVE "tpi:dir <arg>"` behaves the same
as `CAT "<arg>"`**. There is one implementation, in the firmware.

| Form | Sends | Meaning |
|---|---|---|
| `CAT` | `tpi:dir` | The current directory: the cached listing, after one quick look at the card (a swapped card is read afresh; no card gives "No SD card") |
| `CAT "games"` | `tpi:dir games` | Another directory, without changing into it |
| `CAT "*.tap"`, `CAT "games/b*"` | `tpi:dir *.tap` | The matching entries. `*` matches any run, `?` one character, case-insensitive, last path component only |
| `CAT "name.tap"` | `tpi:dir name.tap` | The blocks inside that TAP. It doesn't have to be mounted |
| `CAT ""` | `tpi:tapdir` | The mounted TAP. It mirrors `LOAD ""`, which means "the tape" |
| `CAT #s` … | — | **Not yet.** The ROM's print path always opens the main screen. Redirecting it needs its own ROM change |

- **The argument is any string expression** (`CAT a$`, `CAT d$+"/*.tap"`), checked
  at line entry by HOME's class-`$0A` routine:
  - `CAT 5` and `CAT "x"5` are rejected with the usual `?` marker.
  - An undefined variable is Report 2 at run time.
  - `CAT "x": PRINT 1` runs both statements.
- **The argument can be up to 64 characters** (Report F beyond, nothing sent). See §3
  for how the module gets past SESSION_SETUP's 31-character limit.
- **Paths:** `/` starts at the SD root (`/sd/TAP`) and `..` goes up, but never above the
  root. Names are matched case-insensitively.

Treating a TAP as a directory whose entries are blocks is the TOS model: a
container you can `CAT` into. It removes the need for a separate "tape
directory" command.

### What a listing shows

Filtered and other-directory listings use **the existing `tpi:dir` layout**:
32-column rows, the `Path:` line, `File Name … Size`. They read like the listing
users already know. Only the second header line changes, to the match count.
Real output (a small test directory), one screen row per line:

```text
CAT "*"                                   CAT "advent.tap"
Path:/                                    File:/advent.tap
*: 3 files, 1 dir                         5 blocks
File Name                   Size          Blk Type         Len  Name
--------------------------------          --------------------------------
<GAMES>                      0 B           00 Program       102 ADVENT
000 ADVENT.TAP             504 B           02 Code block    302 ADVCODE
001 CHESS.TAP           16.00 kB           04 Data block     52 headerless
    README.TXT              12 B
```

- **Directories first** in `<>`, then files, each group sorted case-insensitively.
- **The index is the number `LOAD "tpi:n"` uses.** It is shown only for names in the
  current directory's `files[]`. Other files (another directory, or a type `DIR`
  doesn't index, such as `.TXT`) get a blank index.
- **Which files:** every file, bare `CAT` included (and so bare `SAVE "tpi:dir"`).
  - The types `LOAD "tpi:n"` indexes (`TAP TZX DCK ROM BIN`, `catalog.DIR_EXT`) come
    first, with their numbers.
  - Every other file follows, unnumbered. `files[]` and `dirinfo.tap` still hold only
    the numbered ones, so the numbers and `dirinfo.tap` readers are unchanged.
  - With a pattern, every match is shown in name order.
  - Dotfiles and `dirinfo.tap` are hidden unless the pattern names them.
- **Misses are Report F:** no match, a missing name, a pattern under a file, an
  empty directory, or a path above the root.

A TAP listing is `tpi:tapdir CODE 1`'s header layout. The code is shared
(`catalog.tap_header_rows`), so it looks the same. In addition, it also lists data blocks
with no header in front of them. For the mounted file it uses the live
block table and marks the tape position with `>`.

**Not yet, from the earlier draft:**

- a mark on the mounted TAP in directory listings;
- a free-space footer;
- autostart line and load address in TAP listings;
- numbers for `BAS`/`SCR`/`DAT` files.

The last waits for native files (§4a), because `DIR`'s filter also decides what `LOAD "tpi:n"` can index.

## 3. `MOVE`, `ERASE`, `FORMAT`

**Implemented** (ROM `fddcmd.asm` v5, firmware `DISK_COPY` / `DISK_ERASE` /
`DISK_FORMAT` / `DISK_REN` + `ChangeDir`). Every argument is a string
expression, up to 64 characters.

| Form | Sends | Meaning |
|---|---|---|
| `MOVE TO "games"` | `tpi:cd games` | **Change directory.** `".."` goes up, `"/"` is the root, and paths such as `"a/b"`, `"../x"` and `"/games"` work |
| `MOVE TO ""` | `tpi:cd -` | Back to the directory before the last change (one level, like `cd -`) |
| `MOVE "a.tap" TO "b.tap"` | `tpi:copy a.tap\|b.tap` | **Copy** a file. The source is untouched. If the destination is a directory, the copy keeps its name |
| `MOVE "*.tap" TO "backup"` | `tpi:copy *.tap\|backup` | Copy every match into a directory, listing each file as `copied` or `exists` |
| `ERASE "old.tap"` | `tpi:erase old.tap` | Delete a file. No prompt, and silent unless `VERBOSE` |
| `ERASE "*.bak"` | `tpi:erase *.bak` | `Erase <name> (Y/N)?` for each match. **Y** erases it, **N** stops, any other key skips it |
| `ERASE "olddir/"` | `tpi:erase olddir/` | Remove an empty directory (`dirinfo.tap` doesn't count). Not empty is Report Q |
| `FORMAT "new.tap"` / `FORMAT "new"` | `tpi:format new.tap` | Create an empty TAP and mount it with append on, as `tpi:newtap` does |
| `FORMAT "tools/"` | `tpi:format tools/` | Make a directory |
| — | `tpi:ren old\|new` | Rename (or move into a directory). It has no keyword |

- **The separator.** `MOVE` joins its two names with `|`, which a FAT name can't contain.
  Typed by hand, `SAVE "tpi:copy a b"` with a space also works.
- **Nothing is ever overwritten.** An existing destination is Report F: `MOVE`
  onto a file, `FORMAT` of an existing name, `tpi:ren` onto a name.
- **Report Q is for requests that can't be carried out:**
  - the mounted file or the current directory (or one of its parents) for `ERASE`/`tpi:ren`;
  - a directory as `MOVE`'s source;
  - a pattern copied to something that isn't a directory;
  - `FORMAT` of a name that isn't `.tap`.
- **Report F is for names:** a missing file, a path above the root, an empty name, or a name
  longer than 64 characters (checked in the ROM, and nothing is sent).
- **Why N stops instead of skipping.** The ROM's function-`$86` prompt loop ends the whole exchange on N,
  so N can't mean "skip this one". Other keys skip. The erasing happens after the
  exchange, because the SD card and the 2068 link share pins. That means the
  per-file results aren't printed; errors go to the log.
- **No more 31-character limit.** The module sends through `TPI_SEND`, which is
  SESSION_SETUP entered past its 5–31 character name gate. Everything past the
  gate handles 16-bit lengths, and the Pico sizes its buffer from the pre-header.
  This also lifts `CAT`'s old 23-character limit. `build-rom.py` checks the bytes at
  every base-ROM address the module relies on (`ANCHORS`).

**Decided: `MOVE "a" TO "b"` copies.** This is what TOS and the Interface 1
mean, and a mistyped name can't lose data. Rename becomes a new firmware verb,
`SAVE "tpi:ren a b"`, and doesn't get a keyword.

`MOVE TO ""` goes back to the previous directory, like `cd -`. There is one
level of memory. It stands in for TOS's `GO SUB *` / `DRAW *` directory
stack in the case that matters: a menu or loader program changes directory to
find its files, then puts the user back where they started.

**FORMAT never touches the SD card's file system.** A BASIC statement that can wipe
the card is one mistyped line away from disaster. Formatting stays in the web updater.

---

## 4. `OPEN #` / `CLOSE #` — file channels (phase 3)

**Stage 1 is implemented** (sequential text and binary files: `OPEN #n,"f:path"[,"mode"]`,
`PRINT #`, `INPUT #`, `LIST #`, `INKEY$ #`, `CLOSE #`). Stage 2 (records, `TAB`, `u`) and
stage 3 (`d:`) follow. Stock `OPEN #` only knows K, S and P, and stock `CLOSE #` on any
other letter runs off the end of its table and crashes, so the channel needs all of this:

1. **A channel record in `CHANS`.** `OPEN #` inserts 512 bytes with MAKE-ROOM (`$12BB`) just
   before the `$80` that ends `CHANS`, the way the Interface 1 builds `M` channels. The record
   is the 5-byte header (output address, input address, letter `F`), then the stream number,
   the pad, a 64-byte output buffer and a 255-byte input buffer. The stream's `STRMS` entry
   points at it.
   - **The record must be inside `CHANS`.** Anywhere above the workspace, `INPUT` moves
     `CURCHL` out from under it.
   - **Both bytes of its `STRMS` offset must be below `$80`**, because channel select
     (`$1239`) tests `D OR E`. The record is padded into its 512 bytes to make that true, and
     because 512 is a multiple of 256, closing one record never changes the low byte of
     another's offset.
   - On the 2068 one spare byte sits between the `$80` and `PROG`.
2. **Output and input routines reachable with HOME paged in**, because `RST 10` / INCH call
   them there. They are two fixed 9-byte stubs in HOME (`$14A0`, `$14A9`: `DI` / `LD HL,vector` /
   `CALL $03FC` (the returning thunk) / `EI` / `RET`). Every `F` record points at the same two,
   so a record holds no address that has to move with it. **Measured: `A` and the flags survive
   both ways.**
3. **OPEN and CLOSE hooks.** Each is one redirected `CALL` into a 10-byte trampoline in
   `$1488–$14C6`, a remnant of a SYSCON open path that nothing references (the byte scans in
   design doc §10.8 settle the earlier doubt). The trampoline calls the module and, if it
   returns NC, carries on to the stock routine.
   - `OPEN #` at `$145E`. An `f:` name reads the optional `,"mode"` (the syntax pass skips
     everything after the comma, so it is parsed at run time), sends `tpi:chopen <mode>
     <path>` (PMR1 = stream), then builds the record. A Pico error raises its report and
     builds nothing. K/S/P go to the stock `$1465`.
   - `CLOSE #` at `$13A5`. An `F` record is flushed, `tpi:chclose` goes to the Pico, the
     512 bytes are reclaimed, every later `STRMS` offset moves down, and if `CURCHL` was
     the record, S is selected. Stock `$13A8` then resets the entry.
4. **Nothing needed in SELTAB.** Measured: an unknown letter misses the K/S/P table at
   `$1293` and select just returns.
5. **`NEW` and reset** rebuild `CHANS` and orphan our records. `RUN` and `CLEAR` leave them.
   The Pico forgets a stream's old entry whenever that stream is opened again.
6. **An error trap around every module entry.** HOME's returning thunk (`$03FC`) keeps its
   own stack at `($65CE)`, and an error unwinds the Z80 stack but not that one. Each report
   raised inside the module (`CAT`/`MOVE`/`ERASE`/`FORMAT` included) left it 4–8 bytes
   lower, and after about 16 errors it overwrote the bank-switch code. The module now runs
   under an `ERR_SP` trap (HOME `$14B2`) that puts `($65CE)` back, re-enables interrupts and
   passes the error on.
7. **Interrupts off across every bank round trip.** The 2068's bank switch (Timex's code, the
   RAM copy of EXROM `$12BE`/`$134A`) writes port `FFh` and then `F4h` with interrupts on. For
   a few T-states between the two, chunk 0 can be the empty DOCK bank, and an interrupt there
   runs `RST 38` over `$FF` bytes until memory is wiped. Stock runs its Pico traffic under `DI`
   and switches only a few times per command. A channel switches twice per character, and in
   ZEsarUX it hit the window within a few hundred characters. So every HOME entry into the
   module (the stubs, both trampolines and the `$25D6` disk-keyword hook) is `DI` … `EI`
   around the whole thunk.
   - The key click is the other hot path. TS-Pico 2.0 moved BEEPER to EXROM behind HOME's
     `$03F3` thunk, and BEEPER ends in `EI`, so its switch back ran with interrupts on. The
     editor clicks once per character, including every character `INPUT #` reads from a file.
     `$03F3` now runs under `DI` too (tail at `$041C`), and the module's `G_BEEP` turns
     interrupts off again after BEEPER. In stock 2.0 this window exists for every keypress
     and `BEEP`, just far less often.

The 2068's own `SYSCON` extension table (design doc §10.7) is not the vehicle, because it is a
banked-driver ABI.

The stage 1 wire commands are `tpi:chopen`, `tpi:chwr <hex>` (at most 64 bytes, sent when
the buffer fills and on `CLOSE`), `tpi:chrd` (PMR2 = up to 255 bytes; the answer is status 1,
count, bytes, XOR, or status 7 at the end of the file, which becomes Report 8), and
`tpi:chclose`. The Pico drops output to a read channel, which is where `INPUT #`'s prompt
items go.

Design doc §6 covers the buffering and the handshake timing. The statement
surface this spec recommends is:

| Form | Meaning |
|---|---|
| `OPEN #4,"f:data.txt"` | Open to read (the default mode) |
| `OPEN #4,"f:data.txt","w"` | Mode `r` = read, `w` = write (truncate), `a` = append, `u` = update (read/write). Adding `b` (`"rb"`, `"wb"` …) makes it binary. Without `b`, the file is text (§4a) |
| `OPEN #4,"f:rec.dat","u",32` | Update, with fixed 32-byte records, for random access |
| `PRINT #4;…`, `INPUT #4;…`, `LIST #4`, `INKEY$ #4` | Stock statements through the channel. No new syntax |
| `OPEN #4,"d:*.tap"` | Read a directory listing as a stream, one name per `INPUT #4`, ending with Report 8. TOS couldn't do this. It lets menu and loader programs build their lists without screen-scraping `CAT` |
| `CLOSE #4` | Flush and close. `CLOSE #` on a stream that isn't open is a no-op, as on stock |

**Stage 3 (`d:`) is implemented.**
- `OPEN #n,"d:[path/][pattern]"` lists what `CAT` with the same argument would: directories
  first, each ending in `/`, then files. Patterns and hidden-file rules come from the
  same code (`catalog.select`).
- `INPUT #n;a$` returns one name per line, and Report 8 after the last.
  `INPUT #n;TAB 0;k` returns the number of names.
- A missing directory is Report F at `OPEN`. A pattern that matches nothing opens
  normally, and its first read gives Report 8.
- A mode other than `r`, or a record length, is Report Q.
- The ROM sends the name with its `d:` intact (FAT names can't contain `:`), and the
  Pico builds the listing in memory when the stream is opened.

Test program: `basic/SD/TAP/test/chtest4.bas`.

The design choices:

- **The `f:` prefix.** Stock `OPEN #` accepts only one-letter channel names (K/S/P). A
  prefix keeps `OPEN #4,"p"` meaning the printer, and leaves room for other
  devices. The Interface 1 precedent is `"m";1;"name"`, but a prefix inside one
  string is simpler and is still a single string expression.
- **Random access** uses `TAB` as the record pointer. See §4b. EOF shows up as Report 8 on
  `INPUT #`, as it does for tape reads today.
- **Any stream 0–15**, as stock `OPEN #` allows. Streams 4–15 are the usual choice;
  `OPEN #2,"f:log.txt","w"` redirects ordinary `PRINT` to a file until `CLOSE #2`.
  The practical limit is RAM: 512 bytes per open channel.
- **After `NEW` or a reset**, the records are gone. The Pico forgets a stream's old
  entry when the stream is opened again, so `OPEN #` is idempotent. `CLEAR` and
  `RUN` keep open channels.

### 4b. Random access: `TAB` is the record pointer

**Stage 2 is implemented** as described below, with these decisions made along the way:

- **Record file or stream.** A channel opened with a record length (`OPEN #4,"f:x","u",40`)
  is a record file: 1–254 bytes a record, so a record and its CR fit in one read. Without
  one it is a stream, as in stage 1, and `TAB n` means byte n. Stage 1 programs are
  unchanged.
- **Mode `u`** reads and writes and creates a missing file. Reads on a `u` stream stop at
  each line end, so a `PRINT #` after an `INPUT #` writes just after that line.
- **Syntax.** Stock `OPEN #` skipped everything after the comma in the syntax pass,
  which also skipped storing the hidden form of each number, so a record length
  couldn't be evaluated. `$1438` now checks `,"mode"[,length]` properly, and extra
  arguments to a K/S/P `OPEN #` are now a syntax error rather than a runtime Report C.
- **Order on the wire.**
  - The ROM sends any printed bytes before it asks for more input, so the `TAB` in
    `INPUT #4;TAB 7;a$` reaches the Pico first.
  - A `TAB` discards whatever was read ahead.
  - On a record file each CR is sent at once, so Report Q comes from the `PRINT` that
    made the record too long.
- **Byte 23 is always `TAB`**, in binary files too, as it is on the screen. A binary
  file can't hold a raw 23 written with `PRINT #`.
- **The prompt on a `u` channel.** Text in `INPUT #`'s prompt is written to the file on
  a `u` channel; only `TAB` belongs there. On an `r` channel it is dropped.

Test program: `basic/SD/TAP/test/chtest3.bas`.

TOS writes `PRINT *#4;a$;AT p` and `INPUT *#4;a$;AT p`. Stock BASIC can't
parse a trailing `AT p` on `PRINT #`. What it already has is **`TAB n` as an ordinary
print item that sends a 16-bit number to the channel**:

- HOME `$21AD–$21C1`: the `TAB` item evaluates its argument with FIND-INT2, so values
  0–65535 are accepted and anything else is Report B.
- It then does `RST 10` three times: `CHR$ 23`, the low byte, the high byte.
- Those go to the *current channel's* output routine. On the screen channel they
  mean "move to column n". On a disk channel the driver owns them, so they mean
  "move to record n".

So random access needs **no new statements and no parser changes**:

```basic
10 OPEN #4,"f:people.dat","u",40      : REM 40-byte records
20 PRINT #4;TAB 7;n$;TAB 7;          : REM wrong: see below
20 PRINT #4;TAB 7;n$                  : REM write record 7
30 INPUT #4;TAB 7;a$                  : REM read record 7 back
40 PRINT #4;TAB 3;n$( TO 20);p$( TO 20) : REM two fields, one record
50 CLOSE #4
```

The rules:

| Situation | Behaviour |
|---|---|
| Record numbering | **1-based**, like TOS and BASIC arrays. Record n starts at byte `(n-1) × reclen` |
| No record length given | `reclen` = 1, so `TAB n` is "byte n" and a stream file can still be read at any byte. The 16-bit limit caps this at the first 64 KB. A fixed record length reaches further (65535 × reclen) |
| `PRINT #4;TAB n;…` then end of statement | The items go into record n. The ending CR is **not stored**. It closes the record, and the rest is padded with spaces (text mode) or `CHR$ 0` (binary mode). Anything longer than `reclen` gives Report Q; nothing is silently cut off |
| `PRINT` ending in `;` | The record stays open, and the next `PRINT #4` adds to it (as TOS allows). The next `TAB` or CR closes it |
| `INPUT #4;TAB n;a$` | Stock `INPUT #` prints its prompt items to the same stream, so the `TAB` reaches the driver before the read. The driver then supplies exactly `reclen` bytes followed by a CR, so the file needs no line ends. `a$` is the whole fixed-width record, padding included, and you split fields with slices as in the TOS example (manual §5.5) |
| No `TAB` | Sequential: the next record after the last one read or written. A plain loop of `INPUT #4;a$` walks the file |
| Reading past the last record | Report 8, as tape does, so `ON ERR` can trap it |
| Writing past the end | The file grows, and any records skipped over are filled with padding |
| `INPUT #4;TAB 0;n` | **Record 0 is the header query.** It returns the record count as text, so `n` is the file's size in records. TOS had no way to ask for this, and without it, appending to a random file means guessing |
| `PRINT #4;TAB 0;…` | Report Q |

**Line 20's first version is the trap to document.** `TAB` is a seek, so a second
`TAB` inside one `PRINT` moves to another record. It does not skip a field.
Multi-field records put the fields next to each other, as in line 40.

**Why not `MOVE #4 TO p`** (the earlier draft)? That needed its own statement,
so you had to seek and read in two separate statements. `INPUT #4;TAB p;a$` does both in
one, `TAB` is already how Sinclair BASIC says "position", and it costs no ROM
parser code.

**Verified in ZEsarUX** (design doc §10.8), with a dummy `F` channel:

- `PRINT #4;TAB 7;"x"` hands the channel `17 07 00 78 0D`.
- `INPUT #4;"P?";TAB 7;b$` sends `50 3F 17 07 00` to the channel's *output*
  routine, then reads through its *input* routine up to CR.

So both the seek and the read happen in one statement, exactly as described
above. `LIST #4` delivers tokens unexpanded, so text mode has to expand them
itself (§4a).

**Buffering.** The driver keeps one block (256 bytes) of the file in RAM per
channel:

- A `TAB` inside the current block costs nothing.
- A `TAB` outside it writes back the block if it's dirty and fetches the new one.
  That's one Pico round trip per seek.
- Updates reach the card when a block is evicted or on `CLOSE #`. As in TOS (manual
  Appendix B, `CLOSE #*`), **a reset before `CLOSE #` loses the unwritten changes**.
- `reclen` is limited to 255, so a record always fits inside one buffer.

**Open files.** A file can be open on only one stream at a time. A second `OPEN #`
of the same file gives Report F. `CAT` marks open files, like TOS's `S` column
(§2).

---

## 4a. Native SD files: `SAVE`/`LOAD`/`MERGE`/`VERIFY "f:name"`

**Goal: the SD card works the way TOS treats a disk.** `foo.bas` is a
BASIC program and `foo.txt` is a plain text file. Each is a file of its own on the
card. Neither is wrapped in a TAP, and neither is tied to what is mounted. TAPs
are still how tapes are emulated, but they stop being the only way to store
things.

**Implemented** for `SAVE`/`LOAD`/`VERIFY`/`MERGE` (ROM `fddcmd.asm` v6 `F_HOOK`,
firmware `NATIVE_OPEN` + `TS/native.py`, `SAVE_TS`/`LOAD_SERVE`). The text-file
rows below need channels (§4) and are not built yet.

### How it works

The stock SAVE-ETC code has one runtime jump into `SESSION_SETUP` (EXROM `$01D2`),
and it is patched to `F_HOOK`. Any name not starting `f:` (or `F:`) goes on as before. For
`f:<path>` the module:

1. makes the statement's session ID, as `SESSION_SETUP` would;
2. sends `tpi:fopen <path>` by hand through the Pico Interface BIOS (`SYNC_WRITE`,
   `TX_A`, `WF_NPH`, `C_END`). The BIOS returns to the caller, prints only what the
   Pico sends, and never touches `CH_ADD`, so a `CODE a,b` after the name is left
   for the stock code.
   - PMR1 is the operation (T-ADDR: 0 SAVE, 1 LOAD, 2 VERIFY, 3 MERGE) plus 256 × the
     token after the name (`CODE`, `SCREEN$`, `DATA`, `LINE`).
   - PMR2 is the session.
   - An error status raises its report through `$1BF3`, exactly as for `tpi:` commands.
3. shortens the name on the calculator stack: for SAVE, the path cut to 10 characters (the
   header needs one, and the Pico ignores it); for LOAD, VERIFY and MERGE, `""`;
4. continues into the stock body at `$01D5`, as `SESSION_SETUP`'s non-command exit does.

On the Pico, `tpi:fopen` arms `TSP.native` for that session:

- **SAVE:** `SAVE_TS` writes the header and data it receives to `<path>` as a
  native file, instead of `<name>.tap`. The mount, its position and append are untouched.
- **LOAD/VERIFY/MERGE:** the file becomes a one-shot two-block tape in `/TMP/native.tap`
  (flash, because the loader can't use the card). `LOAD_SERVE` serves it by swapping
  state in and out around the unchanged `LOAD_TS` on each call. After the data block,
  the mounted tape carries on exactly where it was.

**Prompts on the lower screen.** Response function `$86` (the Y/N "print string with
loop") always prints on the main screen. For `SAVE "f:x" SCREEN$` that would put the
prompt into the saved picture. The fdd ROM adds function `$88`, the same loop on stream `$FD`
(the lower screen). It is implemented as `LOWER_LOOP`, reached from the dispatcher's last check at
`$2213`, a duplicate `CP 86h` that could never match, now patched to `CP 87h`. The
Pico sends `$88` only for `tpi:fopen`, which only this ROM sends. The shipping ROM has no
`$88`, so other prompts (`ERASE "*.x"`, `tpi:rm`, …) stay on `$86` until the Pico can tell
which ROM it is talking to.

The type is checked when `tpi:fopen` arrives:

- a program for a plain `LOAD`/`MERGE`;
- bytes for `CODE`/`SCREEN$`;
- an array for `DATA`.

A mismatch is Report Q before anything loads, not a failed tape search. An arm whose
session doesn't match the next SAVE or LOAD is stale and is dropped.

### Statements

| Form | Meaning |
|---|---|
| `SAVE "f:foo.bas"` / `SAVE "f:foo.bas" LINE 10` | Write the program (and its variables) to `foo.bas`. If the file exists, ask `Replace foo.bas? (Y/N)` **on the lower screen**, so it can't end up in a `SCREEN$`. Y overwrites. N gives Report D, because the ROM can't see the answer, so the Pico refuses the SAVE header that follows |
| `SAVE "f:pic.scr" SCREEN$` | Write the screen to `PIC.SCR` |
| `SAVE "f:game.bin" CODE 32768,4000` | Write the bytes to `GAME.BIN` |
| `SAVE "f:d.dat" DATA a()` | Write the array to `D.DAT` |
| `LOAD "f:foo.bas"` (and `CODE`, `SCREEN$`, `DATA`), `MERGE`, `VERIFY` | Read the file directly. The mounted TAP and its position are left alone |
| `OPEN #4,"f:foo.txt","w"` … `PRINT #4` / `INPUT #4` | Text files, through channels (§4) |
| `LIST #4` into an open `.txt` | Export a readable program listing. This comes from stock `LIST #` |

- **No default extension.** The name you type is the name on the card. `.bas`,
  `.scr`, `.bin` and `.dat` are conventions, not rules. What a file contains is
  recorded in the file itself (see below), so `LOAD "f:x"` works whatever
  it's called. Loading a file as the wrong kind (`LOAD "f:pic.scr" CODE` is fine,
  `LOAD "f:prog.bas" CODE` is not) gives Report Q. A file that is neither a
  +3DOS file nor a raw screen gives Report F, except as `CODE`, where it loads whole
  (at the statement's address, else 32768).
- **Paths and `MOVE TO` apply**, so `LOAD "f:games/advent.bas"` works.
- **`f:` stays required**, and plain `SAVE`/`LOAD` still mean the tape. Later,
  there could be a setting such as `SAVE "tpi:files on"` that makes plain `SAVE`/`LOAD`
  mean SD files, for people who never use tapes. That is a policy change for later,
  not a new syntax.

### File format — the +3DOS header (decided)

A program can't be a bare byte dump. `LOAD` needs to know:

- the program length versus the variables length,
- the autostart line,
- the load address for `CODE`,
- the array name and type for `DATA`.

On tape, a 17-byte header carries all of this. On a file system, the Spectrum
world already has a standard for it: the **128-byte +3DOS header**. It starts
with the signature `PLUS3DOS`, then the file length, then the same fields as the
tape header, then a checksum. After it comes the raw data. This is the format
used by +3DOS, esxDOS/divMMC and NextZXOS when they write `foo.bas` to a card.
TOS did the same thing with a smaller header: a file's size is "the number of bytes
the programme will use in RAM … plus 5 or 7 bytes for use of the system"
(manual §3.4).

| Content | On disk |
|---|---|
| Program, CODE, DATA | +3DOS header, then the raw bytes. **The type comes from the header, not the extension** |
| `SCREEN$` | **Raw 6912 bytes, with no header.** Every emulator and graphics tool reads `.scr` in this form, and the length already tells you what it is |
| CODE loaded from a headerless file | `LOAD "f:x.bin" CODE 32768` loads the whole file at the statement's address. Without one, it goes to 32768: the Pico can't see whether an address was given. This lets you load binaries made on a PC |
| Text (`OPEN #` in text mode) | Plain bytes, see below |

The firmware already builds tape headers, so writing a +3DOS header only means
laying the same fields out differently. The header costs 128 bytes per file.

2068 programs contain tokens (`ON ERR`, `STICK`, `SOUND`, …) that no Spectrum
has. A 2068 `.bas` is therefore not a Spectrum `.bas`, even though the
container is the same. The header's issue/version bytes can mark a file as
2068.

### Text files

- **Text or binary is decided by the `OPEN #` mode, not the extension:**
  `"r"`/`"w"`/`"a"`/`"u"` are text, and adding `b` (`"rb"`, `"wb"`, …) makes it binary. This
  is TOS's "Text or bytes (T/B)" choice, which it made for serial ports.
- **In text mode:**
  - The Spectrum's CR (13) is written as LF, and CR, LF or CRLF are all accepted on read. So a
    `.txt` edited on a PC reads back cleanly.
  - Tokens are expanded, so `LIST #4` and `PRINT #4;"x";` write readable words, not
    token bytes. This is the same thing the Interface 1 `t` channel does.
  - Print control codes (`AT`, `TAB`, `INK` …) and their parameter bytes are
    dropped. The comma control becomes spaces up to the next 16-column tab stop.
- **Binary mode** passes every byte through unchanged.
- **Long deferred: loading a text listing as a program**, i.e. `MERGE` from `.txt`.
  That needs a tokeniser, which is zmakebas-sized work in MicroPython. The file
  format doesn't rule it out. It isn't on the build order.

### What changes elsewhere

- **`CAT`:**
  - The default filter adds `BAS`, `SCR`, `DAT` and `TXT`.
  - For files with a +3DOS header, the row shows the type and autostart line or
    load address, read from the header, like the TAP-block listing in §2.
- **`MOVE` / `ERASE`:** these work on any file. `MOVE "foo.bas" TO "backup"` copies the
  file as it is.
- **Firmware:**
  - One new source/sink for the existing SAVE/LOAD block path: a named file
    instead of the mounted TAP. It covers header ↔ +3DOS conversion, headerless
    `.scr` and CODE, and replace-if-exists.
  - The ROM already sorts names by prefix in `SESSION_SETUP` (EXROM `$1A73`,
    `TPI:`/`NET:`). Adding `F:` there sends `f:` names down that path.
- **Replace without asking** (`SAVE "f:x",1`) isn't built. A program can `ERASE` first
  (silent), then `SAVE`.

---

## 5. Not included, and why

| TOS feature | Why it's left out |
|---|---|
| `GO TO *`, `GO SUB *`, `DRAW *` (cd and the directory stack) | The keywords can't be reused without `*` (§1). `MOVE TO` replaces cd, and `MOVE TO ""` covers the stack's real use (§3) |
| `DIM *` (create file or directory) | `FORMAT "dir/"` makes directories. `OPEN #` with `w` creates files |
| `LET *` (rename) | `SAVE "tpi:ren a b"`, or `MOVE` then `ERASE` |
| `ATTR *` (protect or hide) | MicroPython's FAT VFS has no call to set attributes. The use that matters, keeping `ERASE` off a file, could later be a firmware-side protect list |
| `LIST *`, `LIST *#` (status) | `CAT` shows the current path. Add a `SAVE "tpi:chans"` verb only if channels need debugging |
| SCPs, drive letters, `FORMAT *` of a disk | There's one storage device. The serial ports aren't on this hardware |
| `SAVE *`, `LOAD *`, `MERGE *`, `VERIFY *` | Kept, as native files with the `f:` prefix (§4a) |

---

## 6. Build order

1. **`CAT` in full**: bare, pattern, path, TAP contents, and `#s`. It's the most-used
   command and it proves the argument evaluator and the report mapping.
   Firmware: a pattern and path argument for `DIR`, a TAP-block listing for any
   file, and the header and footer.
2. **`MOVE TO`**, then `ERASE`, then `FORMAT`. These are thin wrappers over `CD`,
   `RM`, `MD` and `NEWTAP`, plus one new single-round-trip `ERASE` verb.
3. **`MOVE a TO b`** (copy), plus the `tpi:ren` verb.
4. **Native files: `SAVE`/`LOAD "f:name"`** (§4a), with +3DOS headers and
   headerless `.scr`/CODE. It's the biggest improvement to everyday use after `CAT`, and it
   needs no new wire protocol. Text files come with channels (step 5).
5. **Channels** (§4). This needs Gustavo to sign off the block type.

**Base ROM:** the build patches `TSPICO-SYNC.ROM` (ROM 2.0, crc `0x56bd89a4`), which is
v1.7 plus `patches/tspico-sync.asm`. The sync patch touches nothing the disk
module uses:

- It uses EXROM `$2300–$23D3`. The module is at `$3000`.
- The hook sites (HOME `$1946`, `$25D6`), the `$03FC` thunk and the `$1A73` send
  entry are unchanged.
