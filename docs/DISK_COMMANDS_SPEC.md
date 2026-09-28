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
| `CAT` | `tpi:dir` | The current directory: the cached listing, unchanged |
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
- **The argument is limited to 23 characters.** `SESSION_SETUP` takes `tpi:` names
  of 5–31 characters, and `tpi:dir ` uses 8. Longer is Report F, and nothing is sent.
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
- **Which files:**
  - With no pattern, the listing uses `DIR`'s filter (`TAP TZX DCK ROM BIN`, now
    `catalog.DIR_EXT`).
  - With a pattern, every match is shown, so `CAT "*"` shows everything.
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
- `BAS`/`SCR`/`DAT`/`TXT` in the default filter.

The last waits for native files (§4a), because `DIR`'s filter also decides what `LOAD "tpi:n"` can index.

## 3. `MOVE`, `ERASE`, `FORMAT`

| Form | Meaning | Notes |
|---|---|---|
| `MOVE TO "games"` | **Change directory.** `MOVE TO ".."` goes up, `MOVE TO "/"` goes to the root | Reads as English. With no source it can't be confused with a copy |
| `MOVE "a.tap" TO "b.tap"` | **Copy** a file | Same meaning as TOS `MOVE *` and Interface 1 `MOVE`. The source is untouched |
| `MOVE "*.tap" TO "backup"` | Copy the matching files into a directory | As in TOS, a pattern requires a directory as the destination. Each name is printed as it's copied |
| `ERASE "old.tap"` | Delete a file. One round trip, no prompt | Programs need to delete temp files silently |
| `ERASE "*.bak"` | Delete the matching files, with a TOS-style `Erase <name> (Y/N)?` for each | Wildcard deletes always confirm |
| `ERASE "olddir/"` | Remove a directory. It must be empty, otherwise Report Q | The trailing `/` says "I mean the directory" |
| `FORMAT "new.tap"` | Create an empty TAP and mount it (`NEWTAP`) | Refuses if the file exists (Report F), rather than truncating it |
| `FORMAT "tools/"` | Make a directory | The trailing `/` again |

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

**None of this works until we supply a real channel.** Stock `OPEN #` only knows
K, S and P. The Technical Manual (§4.1) describes the lookup tables involved:

- **SPEC_T** holds the OPEN routine for each device letter.
- **CL_TAB** holds the CLOSE routine for each letter.
- **SELTAB** holds a routine that runs every time a stream using that letter is selected.

Any other letter is Report J. So every form below depends on this work:

1. **A channel record in `CHANS`.** It has the 5-byte header (output address,
   input address, letter `F`), then our state: the Pico handle, mode, record length,
   current record, and the 256-byte block buffer. It is inserted with MAKE-ROOM
   just before the `$80` that ends `CHANS`, the way the Interface 1 builds `M` channels. The
   stream's `STRMS` entry points at it.
2. **Output and input routines that are reachable with HOME paged in**, because
   `RST 10` / INCH call them there. A 9-byte stub per direction jumps to the
   EXROM through the existing returning thunk
   (`LD ($5DCD),HL` / `LD HL,addr` / `JP $03FC`). **Measured: `A` and the flags
   survive both ways**, so the driver code sits with the rest of the module at
   `$3000`, not in RAM.
   - **The record must be inside `CHANS`**, inserted with MAKE-ROOM (`$12BB`).
     Anywhere above the workspace, `INPUT` moves `CURCHL` out from under it.
   - **Both bytes of its `STRMS` offset must be below `$80`**, because channel
     select tests `D OR E`.

   See design doc §6.1 and §10.8.
3. **OPEN and CLOSE hooks. Both are mandatory**: stock `CLOSE #` on an unknown
   letter jumps into its own table and resets the machine (measured).
   - At `$142A`: recognise `f:`/`d:` names, parse mode and record length, open the Pico
     handle, build the record and set `STRMS`.
   - At `$139F`: flush the buffer, close the handle, reclaim the record and zero
     `STRMS`.
4. **Nothing needed in SELTAB.** Measured: an unknown letter misses the K/S/P
   table at `$1293` and select just returns.
5. **`NEW`, `CLEAR` and reset** rebuild `CHANS` and orphan our records. The Pico
   side has to close handles that are orphaned this way (§ reset rule below).

`SYSCON` (Timex's own extension table, design doc §10.7) is not the vehicle.
It's a banked-driver ABI, and the open path that would consult it (`$1488–$14C6`) seems to have
no callers in the HOME ROM. That's a static finding and still needs confirming.

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

The design choices:

- **The `f:` prefix.** Stock `OPEN #` accepts only one-letter channel names (K/S/P). A
  prefix keeps `OPEN #4,"p"` meaning the printer, and leaves room for other
  devices. The Interface 1 precedent is `"m";1;"name"`, but a prefix inside one
  string is simpler and is still a single string expression.
- **Random access** uses `TAB` as the record pointer. See §4b. EOF shows up as Report 8 on
  `INPUT #`, as it does for tape reads today.
- **Streams 4–15 only.** That's 12 at once. The practical limit is buffer RAM:
  about 256 bytes per open channel.
- **After a reset**, all Pico handles are closed. `NEW` and `CLEAR` lose the
  channel records, so `OPEN #` has to be idempotent.

### 4b. Random access: `TAB` is the record pointer

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

### Statements

| Form | Meaning |
|---|---|
| `SAVE "f:foo.bas"` / `SAVE "f:foo.bas" LINE 10` | Write the program (and its variables) to `FOO.BAS`. If the file exists, ask `FOO.BAS exists. Replace (Y/N)?` |
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
  `LOAD "f:game.bin"` as a program is not) gives Report F. Tape gives the equivalent error
  for the same mistake.
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
| CODE loaded from a headerless file | `LOAD "f:x.bin" CODE 32768` takes the address from the statement and loads the whole file. Without an address it gives Report Q. This lets you load binaries made on a PC |
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
- **Still to check:** whether `SAVE "f:x",1` (replace without asking) gets
  past the stock `SAVE` syntax class. If it doesn't, you `ERASE` and then `SAVE`.

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
