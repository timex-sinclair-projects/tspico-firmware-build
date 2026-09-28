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

| Form | Meaning |
|---|---|
| `CAT` | List the current SD directory |
| `CAT "games"` | List another directory (it doesn't change into it) |
| `CAT "*.tap"`, `CAT "games/b*"` | List only the matching entries |
| `CAT "name.tap"` | List the **blocks inside** that TAP (like `tpi:tapdir`, but for any TAP, not only the mounted one) |
| `CAT ""` | List the blocks in the **mounted** TAP. It mirrors `LOAD ""`, which means "the tape" |
| `CAT #s` / `CAT #s,"*.tap"` | Send the listing to stream `s` instead of the screen, e.g. `CAT #3` to the (virtual) printer |

Treating a TAP as a directory whose entries are blocks is the TOS model: a
container you can `CAT` into. It removes the need for a separate "tape
directory" command.

### What a directory listing shows

Taken from TOS's `CAT *` (manual §3.3), trimmed to what applies:

```text
/GAMES                         TAP: ADVENT.TAP
 #  Name                      Size
 1  <ARCADE>
 2  <UTILS>
 3  ADVENT.TAP               48213 *
 4  CHESS.TAP                16384
 5  MANIC.TZX                40960
3 files, 2 dirs      SD free 7.21G
```

- **Header:** the current path, which is TOS's first line. After it, the mounted TAP, if
  there is one.
- **Entries:**
  - Directories come first, in `<>`.
  - Then files, sorted case-insensitively.
  - Each row has an index, the name and the size in bytes.
  - The index is the same number `LOAD "tpi:3"` already accepts.
  - `*` marks the mounted TAP. This stands in for TOS's `S` (open) column.
  - Names longer than the column width are cut short with `~`. `CAT "x"` on a single file prints its full name.
- **Footer:** the file and directory counts and the SD free space. This stands in for TOS's `MAX / CUR / REM`.
- **Which files:** bare `CAT` shows the types the TS-Pico can use (TAP, TZX, DCK,
  ROM, BIN, BAS, SCR, DAT, TXT, BMP), which is today's filter plus native files
  (§4a) and the virtual-printer output.
  An explicit pattern shows every name that matches, so `CAT "*"` shows everything.
  Dotfiles are hidden unless a pattern names them.

### What a TAP listing shows

```text
ADVENT.TAP (mounted)
 #  Type      Name         Len
 1  Program   ADVENT       1823  LINE 10
 2  Bytes     ADVCODE     41000  @32768
```

- Block number, type, header name and length.
- The autostart line for a program, and the start address for bytes.
- Headerless blocks are listed as `Data`.
- `>` marks the tape position, i.e. what `LOAD ""` will read next.

---

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

The channel design is in `FDD_COMMANDS_DESIGN.md` §6: a `CHANS` record, a
driver in RAM, buffered blocks, and its own polling of port `$0F`. The statement
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
- **Random access.** The TOS `PRINT *#n;x$;AT p` needs statement interception.
  Instead, set the record pointer with a statement form we own:
  `MOVE #4 TO p`, which reads as "move stream 4 to record p". It keeps
  PRINT and INPUT stock. EOF shows up as Report 8 on `INPUT #`, as it does for
  tape reads today.
- **Streams 4–15 only.** That's 12 at once. The practical limit is buffer RAM:
  about 256 bytes per open channel.
- **After a reset**, all Pico handles are closed. `NEW` and `CLEAR` lose the
  channel records, so `OPEN #` has to be idempotent.

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

### File format — **recommend the +3DOS header**

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
- **Out of scope for now: loading a text listing as a program**, i.e. `MERGE` from `.txt`.
  That needs a tokeniser, which is zmakebas-sized work in MicroPython. The file
  format doesn't rule it out. Worth doing later, because it would make editing BASIC
  on a PC a round trip.

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

**Before any of this: re-base this branch.** Its commit a1499e9 anchors to
`src/rom/TSPICO.ROM`, which is v1.7 (crc `0x09d4ca63`). The ROM that ships as 2.0
is `TSPICO-SYNC.ROM` (crc `0x56bd89a4`), which is v1.7 plus
`patches/tspico-sync.asm`. The two regions don't collide: the sync patch uses
EXROM `$2300–$23D3`, and the FDD module is at `$3000`.
