# tspico.py part 7 — ROM 2.1's commands on the Pico: CAT, MOVE, ERASE, FORMAT, `f:` files, the channels

Source: [`src/TS/tspico.py`](../../../src/TS/tspico.py), lines 2591–3423.
The Z80 side is [rom/exrom-fdd.md](../rom/exrom-fdd.md)
([`src/rom/fdd/fddcmd.asm`](../../../src/rom/fdd/fddcmd.asm)).

ROM 2.1 gives the four stock disk keywords (CAT, MOVE, ERASE, FORMAT) a
meaning, adds `f:` names to SAVE, LOAD, VERIFY and MERGE, and adds `f:` and
`d:` channels to OPEN # and CLOSE #. None of that is new wire protocol: the
ROM's module at EXROM 3000h turns each statement into an ordinary `'B'`
command whose text starts `tpi:`, and the handlers in this part of
`tspico.py` answer it. The handlers are thin: the rules live in three pure
modules tested on the host, [catalog.py](catalog.md) (names, paths,
listings), [native.py](native.md) (the +3DOS header) and
[channels.py](channels.md) (streams, records, text conversion), and this
part does the SD access, the bus answer and the bookkeeping around them.
[DISK_COMMANDS_SPEC.md](../../DISK_COMMANDS_SPEC.md) is the contract these
handlers implement; [FDD_COMMANDS_DESIGN.md](../../FDD_COMMANDS_DESIGN.md)
is the ROM mechanism; [ROM_CHANGES.md](../../ROM_CHANGES.md) lists the ROM
2.1 patches.

## Map of the file

| Lines | What | Chapter |
|---|---|---|
| 2591–2670 | `CATALOG`, `CATALOG_TEXT` — CAT and `SAVE "tpi:dir <arg>"` | here |
| 2679–2775 | `SD_CALL`, `SD_FREE`, `SD_QUIET`, `SD_NEEDED`, `NO_CARD_REPLY`, `REFRESH_IF`, `PROMPT_EACH` | [tspico-bus.md](tspico-bus.md), [tspico-state.md](tspico-state.md), [tspico-messages.md](tspico-messages.md) |
| 2778–3072 | `DISK_COPY` … `DISK_REN_WORK` — MOVE, ERASE, FORMAT and `tpi:ren` | here |
| 3082–3085 | `NATIVE_TAP`, `MOD_CODE`, `MOD_SCREEN`, `MOD_DATA`, `MOD_LINE`, `KIND` | [tspico-state.md](tspico-state.md) |
| 3088–3194 | `NATIVE_OPEN`, `NATIVE_SAVE_TARGET`, `NATIVE_LOAD_PREP` — `SAVE`/`LOAD "f:path"` | here |
| 3208–3235 | `SD_FS`; `CHANNELS`, `CH_STATUS` | here; [tspico-state.md](tspico-state.md) |
| 3238–3270 | `CH_READY`, `CH_REPLY`, `CH_CALL` | [tspico-bus.md](tspico-bus.md) |
| 3273–3423 | `DIR_NAMES`, `CH_OPEN`, `CH_WRITE`, `CH_READ`, `CH_CLOSE` — the channel commands | here |

## The two sides of every command

The table says, for each statement, what ROM 2.1 sends and which handler
answers. The strings are the `CMD_*` constants at the end of `fddcmd.asm`;
the ROM sends every one as a `'B'` command with T-ADDR 0, so `PROCESS_CMD`
([tspico-dispatch.md](tspico-dispatch.md)) looks the word up in `SA_funct`
([tspico-commands.md](tspico-commands.md)) and calls the handler with the
ten-byte pre-header and the decoded body. PMR1 and PMR2 are the pre-header's
bytes 3–4 and 5–6, read with `PARAMS(pre)` ([tspico-files.md](tspico-files.md)).

| Statement | The ROM sends | PMR1 | PMR2 | Handler | Answer |
|---|---|---|---|---|---|
| **CAT** | `tpi:dir` | 0 | 0 | `DIR` ([tspico-commands.md](tspico-commands.md)) | the cached listing, function 86h |
| **CAT ""** | `tpi:tapdir` | 0 | 0 | `TAPDIR` ([tspico-commands.md](tspico-commands.md)) | the mounted TAP's blocks, 86h |
| **CAT x$** | `tpi:dir x` | 0 | 0 | `DIR` → [`CATALOG`](#catalogarg) | a listing (86h) or a status |
| **MOVE TO x$** | `tpi:cd x`; `""` sends `tpi:cd -` | 0 | 0 | `CDIR` ([tspico-commands.md](tspico-commands.md)) | a status |
| **MOVE a$ TO b$** | `tpi:copy a\|b` | 0 | 0 | [`DISK_COPY`](#disk_copypre-cmd) | a status, or one row per file (86h) |
| **ERASE x$** | `tpi:erase x` | 0 | 0 | [`DISK_ERASE`](#disk_erasepre-cmd) | a status, or a Y/N prompt per match (86h) |
| **FORMAT x$** | `tpi:format x` | 0 | 0 | [`DISK_FORMAT`](#disk_formatpre-cmd) | a status |
| — (no keyword) | `tpi:ren a\|b` | 0 | 0 | [`DISK_REN`](#disk_renpre-cmd) | a status |
| **SAVE/LOAD/VERIFY/MERGE "f:path"** | `tpi:fopen path` | op + 256 × token | the session id | [`NATIVE_OPEN`](#native_openpre-cmd) | a status; for a SAVE over a file, a Y/N prompt on the lower screen (88h) |
| **OPEN #n,"f:path"[,mode[,len]]** | `tpi:chopen mode path` | stream n | record length (0 = stream) | [`CH_OPEN`](#ch_openpre-cmd) | a bare status |
| **OPEN #n,"d:spec"** | `tpi:chopen r d:spec` | stream n | 0 | [`CH_OPEN`](#ch_openpre-cmd) | a bare status |
| **PRINT #n;…** (the driver's flush) | `tpi:chwr <hex>` | stream n | 0 | [`CH_WRITE`](#ch_writepre-cmd) | a bare status |
| **INPUT #n / INKEY$ #n** (the driver's fetch) | `tpi:chrd` | stream n | bytes wanted (255) | [`CH_READ`](#ch_readpre-cmd) | status 1, count, bytes, XOR; or status 7 |
| **CLOSE #n** | `tpi:chclose` | stream n | 0 | [`CH_CLOSE`](#ch_closepre-cmd) | a bare status |

**How the ROM sends them.** The four keywords and `tpi:cd` go through the
stock `SAVE "tpi:…"` machinery: `FDD_MAIN` builds the text in the
calculator-stack workspace and `TPI_SEND` enters `SESSION_SETUP` past its
5–31 character name gate (`SESSION_NAMED`, 1AACh), so an argument may be 64
characters (`MAX_ARG`; longer, or empty, is Report F in the ROM and nothing
is sent). The stock function chain then shows the answer, so these commands
may print. `tpi:fopen` (`SEND_FOPEN`) and the channel commands (`CH_SEND`)
are sent by hand through the Pico Interface BIOS, because they go out in the
middle of a statement: pre-header `'B'`, 00h, BANK, PMR1 (two bytes), PMR2
(two bytes), LEN, 00h, XOR; then the preloaded status is read and the ROM
waits READY (`BIOS_WF_NPH`); then the body `'D'`, LEN, 00h, the text, XOR.
After the body, `SEND_FOPEN` and `CH_STATUS` call `BIOS_C_END` (`C_END2` on
ROM 2.1) and raise the report of an error status through `C_FAIL`;
`CH_FETCH` reads the `tpi:chrd` data phase itself.

**What the Pico answers.** A plain status is one byte below 80h, written
with `CMD_PUT` and followed by READY; `SEND_MSG` sends that, or, when
`TSP.VERBOSE` is on or the message is forced, function 81h with the status
and the text ([tspico-messages.md](tspico-messages.md), PROTOCOL
[§5.3–5.4](../../PROTOCOL.md)). A listing or a per-file report goes through
`SEND_MSG2`: function 86h, the status, then pages with the "Scroll? (Y/n)"
prompt. ERASE's per-match prompts are one 86h loop built by `PROMPT_EACH`;
the "Replace x? (Y/N)" prompt before an `f:` SAVE is function 88h, the
same loop on the lower screen, which only ROM 2.1 has. The channel commands
answer with the bare status alone, whatever VERBOSE says, because a printed
message would move the ROM's current channel mid-statement (`CH_REPLY`).
`tpi:chrd` is the one command with a data phase: status 1, a count, the
bytes and their XOR, read blind by the ROM (`CH_READ`).

**The bus and the card.** The SD card shares GPIO 2–4 with the 2068 bus, so
a handler runs its card work inside `SD_CALL` (or `CH_CALL`, which also
turns a `ChannelError` into its status): `ACTIVATE_SD` parks the bus state
machine, the work runs, `DEACTIVATE_SD` and `ACTIVATE_MQ` rebuild
`TS_IO_DUAL` with the Y register at BUSY and TX empty, and only then does
the handler queue its answer and say READY. No file stays open between
commands. `CATALOG` brackets its own access the same way. The disk keywords
answer with `MQ_READY` (Y = FFh, READY and IDLE); the channel commands
answer with `CH_READY` (F7h, READY without IDLE): the ROM's channel driver
sends its next command the moment it has the answer, and `CH_SEND` waits up
to ~1 s for IDLE before its SYNC. `PROCESS_CMD`'s tail is what sets IDLE,
after draining and the pre-load. With IDLE already up, the SYNC landed while
the tail was still running and the pre-header behind it was lost (Report T;
[tspico-bus.md](tspico-bus.md), PROTOCOL [§5.6](../../PROTOCOL.md), §13
"A reply the ROM answers straight away must say READY, not IDLE").

**State between calls.** `TSP.cur_path` is the directory every path resolves
from; `TSP.f_name`, `TSP.offset_tbl` and `TSP.tap_idx` are the mounted TAP,
which ERASE, `tpi:ren` and an `f:` SAVE refuse to touch; `files` and
`alldirs` are the current folder's index and the directory list that
`REFRESH_IF`, `DISK_MAKE_DIR` and `DISK_ERASE_ONE` keep current;
`TSP.native` is the arm `tpi:fopen` leaves for the SAVE or LOAD transaction
of the same session, and `NATIVE_TAP` the one-shot tape in flash it points
at; `CHANNELS` holds each open stream's path and position
([tspico-state.md](tspico-state.md)).

## CAT: tpi:dir with an argument

### `CATALOG(arg)`

Lists what `arg` names: another directory, the entries matching a pattern
in its last component, or the blocks of a TAP file. It is the one
implementation behind CAT x$ and `SAVE "tpi:dir x"` (spec
[§2](../../DISK_COMMANDS_SPEC.md)); bare CAT is `DIR`'s cached `lista`
([tspico-commands.md](tspico-commands.md)), and `CAT ""` is `TAPDIR`.

1. Lights the LED and calls `ACTIVATE_SD()`: the card is mounted and the bus
   state machine replaced by `NULL_SM`.
2. Calls [`CATALOG_TEXT(arg)`](#catalog_textarg). An `OSError` from the card
   becomes `"SD card error"` with status 3 (F), logged at level 2.
3. In `finally`: `DEACTIVATE_SD()`, `ACTIVATE_MQ()`. The bus state machine is
   rebuilt with Y = BUSY and an empty TX FIFO.
4. Status 1: `SEND_MSG2(CAT_COLOUR(msg), 1, False, True)` — function 86h,
   the listing in CAT's colours, keywords not expanded, paged with "Scroll?".
   Any other status: the message is logged (level 1) and `SEND_MSG(msg, arg,
   st)` answers with the status byte, or with function 81h and
   `msg`, CR, `arg` when VERBOSE is on.
5. LED off.

It brackets the SD access itself instead of using `SD_CALL` because a card
error here is answered as `"SD card error"`/F, and a missing card never
reaches it: `TPI:DIR` is not in `SD_FREE`, so `PROCESS_CMD`'s `SD_NEEDED`
check answers `NO_CARD_REPLY` first ([tspico-bus.md](tspico-bus.md)).

Takes `arg`, the text after `tpi:dir `, already stripped by `DIR`. Returns
nothing. Reads `TSP.cur_path`, `TSP.f_name`, `TSP.offset_tbl`,
`TSP.tap_idx` and `files` through `CATALOG_TEXT`; writes nothing but the
bus. Called by `DIR` when PMR1 is 0 and an argument is present. `ZX_TPI`
(ZX ROM v4's `SAVE "tpi:dir"`, [tspico-dispatch.md](tspico-dispatch.md))
calls `CATALOG_TEXT` directly inside its own SD bracket.

Pinned by `src/test/catalog_hosttest.py` (`test_dir`): the card is activated
and handed back on every path, errors included; "no match", a missing name,
a path above the root, a pattern under a file and an empty directory are all
Report F; the listing is whole 32-character rows.

### `CATALOG_TEXT(arg)`

Builds the listing text for `CATALOG`. The SD card must be active. Returns
`(text, status)`; a card error propagates as `OSError`.

1. `catalog.split_arg(arg)` gives `(where, pat)`: `pat` is the last path
   component when it holds `*` or `?`, else `None`.
   `catalog.resolve(TSP.cur_path, where)` gives the real path, or `None`
   when the path climbs above the root: `"Not found: <arg>"`, F.
2. `os.stat(real)`: an `OSError` is `"Not found: <arg>"`, F. Bit 14 of the mode
   says whether it is a directory.
3. **One file, no pattern.** If its name ends `.TAP` (any case): the block
   table is the mounted file's live `TSP.offset_tbl` with `TSP.tap_idx` as
   the position when `TSP.f_name` is this file (case-insensitive) and the
   table is non-empty, otherwise `catalog.tap_table` over the file on the
   card, with no position. Four header rows of 32 characters — `"File:"` +
   the public path shortened to 27; `"<n> blocks"`, `", mounted"` when the
   live table was used; `"Blk Type         Len  Name      "`; 32 dashes —
   then `catalog.tap_header_rows(tbl, cur, orphans=True)`, or
   `"<empty file>\r"` when there are none. Returns that, status 1.
   Any other file: its name is replaced by the name as stored (a scan of
   the parent's `os.ilistdir`, case-insensitive), `entries` is that one
   `(name, False, size)` and the path shown is the parent's.
4. **A directory, or a pattern.** A pattern under a file is
   `"Not a directory: <where>"`, F. `entries = catalog.select(os.ilistdir(real),
   pat)`: directories, then files, then (bare listing only) the types `DIR`
   does not index. Nothing: `"No match for <pat>"` or `"Directory is empty"`,
   F.
5. The index column: only when the listed directory is `TSP.cur_path`
   (case-insensitive) is `index_of(name)` the position of the name in
   `files`, the list `DIR_FILES` built; elsewhere every index is blank.
   Line 2 is `"<pat>: "` (if any) + `catalog.counts(nf, nd)`, the numbers of files and folders in `entries`. The text
   is `DIR_HEADER(line2, path)` ([tspico-files.md](tspico-files.md): four
   32-character rows, `Path:` first) followed by
   `catalog.dir_rows(entries, index_of, shorten_filename)`.

Names pass through `xstr` ([tspico-files.md](tspico-files.md)), which is
`catalog.screen_name`: a character the 2068 cannot print or type becomes
`?`. The rows carry no CR: the 32-column screen wraps them, and
`CAT_COLOUR` recognises the layout by the `Path:` prefix and the 128-byte
header. A TAP listing starts `File:` and goes through `CAT_COLOUR`
unchanged.

Pinned by `catalog_hosttest.py`: matches carry the `LOAD "tpi:n"` index;
the count line and its plurals; every match including unindexed types and
directories, never dotfiles or `dirinfo.tap`; another directory lists with
no indices, other types after the `DIR` types; an absolute path with a
pattern; a TAP's blocks with its headerless block and no position mark; the
mounted TAP from its live table with `>` on the position; a file typed in
lower case listed by its stored name; from a subdirectory, `../*.tzx` lists
the parent unindexed.

## MOVE, ERASE, FORMAT and tpi:ren

The comment at line 2793 states the rules all four share: paths resolve
like CAT's, nothing overwrites, and an existing target is Report F (spec
[§3](../../DISK_COMMANDS_SPEC.md)). Report Q is for a request that cannot
be carried out (the mounted file, the current directory, a directory as a
copy source); Report F for a name (missing, above the root, not allowed).
`src/test/disk_cmds_hosttest.py` runs these handlers against a temporary
directory with FAT's case-insensitive names.

### `DISK_COPY(pre, cmd)`

MOVE a$ TO b$ — `tpi:copy a|b`. Copies a file to a new name or into a
directory, or every file matching a pattern into a directory. The source
is never touched.

1. `catalog.split_pair(getArgs(cmd))` splits on `|`, or on a single space
   when typed by hand. Either half missing: `"Copy needs a source and a
   destination"`, Q.
2. LED on; `SD_CALL(DISK_COPY_WORK, a, b)`; LED off.
3. Status 1 with a list: `SEND_MSG2("".join(rows), 1, False)` — the
   pattern case, one 32-character row per file, keywords not expanded.
   Otherwise `SEND_MSG(msg, "", st)`, logged at level 1 when it is an error.

`pre` is not used. On the ROM side `FDD_MOVE` pops both strings, builds
`CMD_COPY` + source + `'|'` + destination and sends it through `TPI_SEND`;
`|` cannot occur in a FAT name, so it is a safe separator.

Pinned by `disk_cmds_hosttest.py` (`test_copy`): file to new name, whole
contents, source untouched, listing refreshed; file into a directory keeps
its name; existing target F and not overwritten; missing source F; a
directory as source Q; missing destination directory F; pattern into a
directory lists each file as `copied`, and `exists` the second time;
pattern to a file Q; no match F; above the root F; one name only Q; typed
with a space and absolute paths, the copy keeps the stored name.

### `DISK_COPY_WORK(a, b)`

The copy, with the SD card active. Returns `(message, status)` or
`(rows, 1)`.

1. `split_arg(a)`; `dst = resolve(cur, b)`, `None` → `"Not found: b"`, F.
   `dst_is_dir = dir_exists(dst)`.
2. **Pattern.** The source directory must resolve and exist (`"Not found:
   a"`, F) and the destination must be a directory (`"Copy them to a
   directory"`, Q). Jobs are the directory's entries sorted
   case-insensitively, skipping directories, `dirinfo.tap`, non-matches and
   dot names unless the pattern starts with a dot; each goes to `dst/<name>`.
   No jobs: `"No match for <pat>"`, F.
3. **One name.** The source must be a file (`"Not found: a"`, F; a directory
   is `"Can't copy a directory"`, Q). Its name is taken as stored, not as
   typed. The job's target is `dst/<name>` when `dst` is a directory, else
   `dst`.
4. For each job: the same file (case-insensitive) is `same file`; an
   existing file or directory at the target is `exists`; a missing parent is
   `no such dir`; otherwise `COPY_FILE(s, d)` ([tspico-files.md](tspico-files.md):
   512-byte chunks, the LED toggling, `WAIT_CORE1` first) and on failure the
   partial target is removed (`copy failed`). Each successful target's parent
   is remembered for `REFRESH_IF`.
5. One name: `REFRESH_IF` runs and the answer is `"Copied <name>"` (1),
   `"Copy failed: <name>"` (Q) or `"<public target>: <why>"` (F). Pattern:
   each row is `"%-32s"` of the name shortened to 18, a space and the word,
   cut to 32; after the loop `REFRESH_IF(*touched)` rebuilds `files`, `lista`
   and `dirinfo.tap` if the current folder received a copy.

Reads `TSP.cur_path`; writes files on the card and, through `REFRESH_IF`,
the folder caches. Beware: `COPY_FILE` returns `False` on any exception,
including a full card; the half-written target is deleted but the row
only says `copy failed`, and the reason is not logged here.

### `DISK_ERASE(pre, cmd)`

ERASE x$ — `tpi:erase x`. Deletes one file (no prompt), the files matching
a pattern (a Y/N prompt each), or an empty directory (`dir/`).

1. `arg = getArgs(cmd).strip()`; empty: `"Name required"`, Q.
2. No wildcard: `SD_CALL(DISK_ERASE_ONE, arg)`; an error is logged;
   `SEND_MSG(msg, "", st)` — a status alone unless VERBOSE.
3. A pattern: `SD_CALL(DISK_ERASE_MATCHES, where, pat)` lists the files
   first; an error (no such directory, no match) is sent and that is all.
4. `PROMPT_EACH(["Erase <public path, shortened to 20> (Y/N)?" …])`
   ([tspico-messages.md](tspico-messages.md)): one function-86h exchange,
   one prompt per file, the bus active and the card not. It returns the
   indexes answered Y. N ends the ROM's loop, so N stops the whole exchange;
   any other key skips that file.
5. If anything was chosen: `SD_CALL(DISK_ERASE_LIST, [...])`. Nothing more
   is sent: the 86h exchange carried the status, and the per-file results
   go to the log only.

The order — list, then ask, then erase — is forced by the pins: the card
and the 2068 link cannot be active at once, so the whole prompt exchange
happens between two SD sessions (spec §3, "Why N stops instead of
skipping"). Pinned by `disk_cmds_hosttest.py` (`test_erase`): a file goes
with no prompt and a `SEND_MSG` answer; missing F; a directory without `/`
Q and kept; a non-empty directory Q; an empty directory (bar `dirinfo.tap`)
removed and dropped from `alldirs`; the current directory's parent Q; the
mounted file Q; a pattern asks one prompt per match, sorted, erases only
those answered Y, and sends nothing after the exchange; no match F with no
prompt. `test_prompt_each` pins `PROMPT_EACH`'s byte sequence.

### `DISK_ERASE_ONE(arg)`

One file, or one empty directory when `arg` ends in `/`. SD active.
Returns `(message, status)`.

- Resolves `arg` (without its trailing `/`); `None`: `"Not found"`, F.
- **Directory.** Not a directory: F. `catalog.within(cur, real)` — the
  current directory or one of its parents: `"Can't erase the current
  directory"`, Q. `real/dirinfo.tap` is removed first (`DIR_FILES`' own
  file does not make a directory non-empty), then `os.rmdir`; an `OSError`
  is `"Directory not empty"`, Q. `alldirs` loses every entry at or below
  `real[3:]` (the list holds paths without `/sd`), `REFRESH_IF(parent)`,
  `"Erased <public>"`, 1.
- **File.** A directory named without `/`: `'A directory: ERASE "x/"'`, Q.
  Missing: F. The mounted file (`TSP.f_name`, case-insensitive): `"File is
  mounted"`, Q. `os.remove`, `REFRESH_IF(parent)`, `"Erased <public>"`, 1.

Writes the card, `alldirs` and the folder caches. Reads `TSP.cur_path`,
`TSP.f_name`.

### `DISK_ERASE_MATCHES(where, pat)`

The real paths of the files a pattern names, SD active: the directory
`where` must resolve and exist (`"Not found: <where>"`, F); its entries,
sorted case-insensitively, keep only files that are not `dirinfo.tap`,
match `pat` (`catalog.match`) and are not dot names unless the pattern
starts with a dot. None: `"No match for <pat>"`, F. Returns `(list, 1)`.
Directories are never offered.

### `DISK_ERASE_LIST(paths)`

After the prompts, SD active: each path is removed, unless it is the
mounted file (kept, logged at level 1); an `OSError` is logged at level 2.
Then `REFRESH_IF` with every parent. Returns `(None, 1)`; nothing is sent
to the 2068.

### `DISK_FORMAT(pre, cmd)`

FORMAT x$ — `tpi:format x`. Makes an empty `.tap` and mounts it with
append on, as `tpi:newtap` does, or makes a directory when the name ends
in `/`. It never formats the card and never overwrites.

1. `arg` empty: `"Name required"`, Q.
2. Ends in `/`: `SD_CALL(DISK_MAKE_DIR, arg.rstrip('/'))` and `SEND_MSG`.
3. Otherwise the base name gets `.tap` when it has no dot; an extension that
   is not `.TAP` is `'FORMAT makes "x.tap" or "dir/"'`, Q.
4. `SD_CALL(DISK_NEW_TAP, arg)` returns the real path or an error
   (logged, sent).
5. `MOUNT_FILE(real)` ([tspico-files.md](tspico-files.md)), which does its
   own SD session; a false return is `"Made it, but can't mount it"`, Q.
6. `TSP.append = True`; `SEND_MSG("New .tap mounted: ", public_fname(), 1)`.

`FORMAT "/"` ends in `/`, so it reaches `DISK_MAKE_DIR` with an empty name,
which resolves to the current directory: `"Not allowed"` at the root,
`"Already exists"` elsewhere — F either way, and the card's file system is
never touched. Pinned by `disk_cmds_hosttest.py` (`test_format`): a name
without `.tap` makes an empty `new.tap`, mounted with append on; a
subdirectory path; an existing file F, not truncated, not mounted; not a
`.tap` Q; a missing directory F; `dir/` made and added to `alldirs`, and F
the second time; `/` F.

### `DISK_NEW_TAP(name)`

An empty TAP, SD active. Returns `(real path, 1)` or `(message, status)`:
`None` from `resolve` is `"Not found"`, F; a base name that is empty or
holds a character outside `' '`–`'~'` or one of `: * ? \ | " < >` is
`"Name not allowed"`, F; an existing file or directory is `"Already
exists"`, F; a missing parent is `"Not found: <parent>"`, F. Creates the
file with `open(real, "wb")` and runs `REFRESH_IF(parent)`.

### `DISK_MAKE_DIR(name)`

`FORMAT "dir/"`, SD active. The root itself or a path above it is `"Not
allowed: <name>/"`, F; an existing name `"Already exists"`, F; a missing
parent `"Not found"`, F. `os.mkdir`, then `real[3:]` is appended to
`alldirs` and the list sorted (inside a bare `try`, so a failure there is
ignored), `REFRESH_IF(parent)`, `"Made <public>/"`, 1.

### `DISK_REN(pre, cmd)`

`SAVE "tpi:ren old|new"` — rename, or move into a directory. No keyword
sends it: MOVE copies (spec §3, "Decided"). `split_pair` as `DISK_COPY`
(`"Rename needs two names"`, Q); `SD_CALL(DISK_REN_WORK, a, b)`;
`SEND_MSG(msg, "", st)`. Nothing is logged here.

### `DISK_REN_WORK(a, b)`

SD active. The source must exist (F). A directory that is the current one
or a parent of it: `"Can't rename the current directory"`, Q. The mounted
file, or a directory holding it (`catalog.within(TSP.f_name, src)`):
`"File is mounted"`, Q. The destination must resolve (F); an existing
directory means "into it", `dst/<basename of src>`. An existing target
`"Already exists"`, F; a missing parent `"Not found: b"`, F; a directory
into itself `"Can't move a directory into itself"`, Q. `os.rename`; for a
directory `alldirs = GET_DIRS()` re-walks the card; `REFRESH_IF` with both
parents; `"Renamed to <public dst>"`, 1. Pinned by `test_cd_and_ren`:
rename, move into a directory, onto an existing name F, a directory into
itself Q, the mounted file Q.

## Native SD files: SAVE, LOAD, VERIFY and MERGE "f:path"

The comment at line 3075 and spec [§4a](../../DISK_COMMANDS_SPEC.md)
describe the mechanism. On the ROM, `F_HOOK` (the patched jump at EXROM
01D2h) sees an `f:` name on the calculator stack, makes the statement's
session id (FRAMES+1, never 0) and sends `tpi:fopen <path>` with
`SEND_FOPEN`: PMR1 low = T-ADDR (0 SAVE, 1 LOAD, 2 VERIFY, 3 MERGE), PMR1
high = the token after the name (CODE AFh, SCREEN$ AAh, DATA E4h, LINE
CAh, else 0), PMR2 = the session. An error status raises its report and
the statement ends there. Otherwise `F_HOOK` shortens the name in place —
a SAVE keeps up to 10 characters of the path, a stand-in the Pico ignores;
LOAD, VERIFY and MERGE get `""` — and carries on into the stock SAVE-ETC
body. The next transaction is therefore the ordinary SAVE header block or
LOAD pre-header, carrying the same session id in bytes 3–4. The constants
`NATIVE_TAP`, `MOD_CODE`, `MOD_SCREEN`, `MOD_DATA`, `MOD_LINE` and `KIND`
are in [tspico-state.md](tspico-state.md).

### `NATIVE_OPEN(pre, cmd)`

`tpi:fopen <path>`: checks the name or the file and arms `TSP.native` for
the SAVE or LOAD that follows in the same session.

1. `op, mod, session = par1 & 0xFF, par1 >> 8, par2`; `path` is the text
   after the word. `TSP.native = None`: whatever an earlier statement left
   is dropped. An empty path: `"Name required"`, F.
2. **SAVE (op 0).** `SD_CALL(NATIVE_SAVE_TARGET, path)` gives `(real,
   exists)` or an error (logged, sent). The arm is set: `dict(op=0,
   path=real, session=session, refuse=False)`. If the file exists:
   `SEND_MSG_PROMPT_YN("Replace <base name shortened to 16>? (Y/N)",
   lower=True)` — function 88h, the status 1, the prompt, 00h; the key; for
   `N` (78) nothing more; for any other key, `n` included, its echo (or `Y`
   if unprintable), a CR and 03h. `refuse` becomes true for
   any key but `Y`/`y`. The function returns without another `SEND_MSG`:
   the 88h exchange's status was the command's answer. A new file:
   `SEND_MSG("Saving to <public>", "", 1)`.
3. **LOAD, VERIFY, MERGE (op 1–3).** `SD_CALL(NATIVE_LOAD_PREP, path, op,
   mod)` returns the one-shot tape's length or an error (logged, sent). The
   arm is `dict(op=op, session=session, tap=NATIVE_TAP, totlen=res)` and
   the answer `SEND_MSG("Loading <path>", "", 1)`.

Who consumes the arm: `SAVE_TS` ([tspico_io.md](tspico_io.md)) clears
`TSP.native` on entry and uses it only when the SAVE pre-header's session
matches; `refuse` makes it answer the header with `REFUSE_SAVE` → Report
D, because the ROM cannot see the key the Pico read. `LOAD_SERVE` swaps the
one-shot tape in around `LOAD_TS` while the session matches and clears the
arm once the data block is served or the search gives up; a LOAD of
another session drops a stale arm.

Why the lower screen: `SAVE "f:x" SCREEN$` saves the display, and an 86h
prompt on the main screen would be in the picture (spec §4a, PROTOCOL
[§5.4](../../PROTOCOL.md)). Function 88h exists only on ROM 2.1 and the
Pico sends it only here, because only that ROM sends `tpi:fopen`. The
prompt is cut to 31 characters so that it and the key echo fit one
lower-screen line. `TPI:FOPEN` is in `SD_QUIET`, so a missing card gets
the bare status J; the handler itself answers with `SEND_MSG`, which prints
when VERBOSE is on, and that is harmless here because SAVE and LOAD are not
inside PRINT # or INPUT #.

Beware: the arm is set before the prompt, so a BREAK at the prompt
(`CmdAbort` out of `SEND_MSG_PROMPT_YN`) leaves `TSP.native` armed with
`refuse` false; the statement was abandoned on the 2068, so no SAVE of that
session follows, and the next SAVE or LOAD of any other session drops it.

Pinned by `disk_cmds_hosttest.py` (`test_native_open`): a new file arms
`op=0` for the session; an existing file asks `Replace advent.tap? (Y/N)`
on the lower screen and Y arms to overwrite, N to refuse; a long name is
cut to fit; a directory Q; no such directory, a name FAT can't hold, no
name F, nothing armed; the mounted file Q; a +3DOS program arms a one-shot
tape equal to `native.as_tap(...)`; a raw `.scr` as SCREEN$ is CODE 6912 at
16384; a headerless file as CODE loads whole; a headerless file as a
program F; a program as CODE, MERGE of a screen, SCREEN$ of 300 bytes Q; a
missing file F.

### `NATIVE_SAVE_TARGET(path)`

SD active. The real path and whether it exists, for a SAVE: `None` from
`resolve` or the root itself is `"Not allowed"`, F; a base name that is
empty or holds a character outside `' '`–`'~'` or one of `: * ? \ | " < >`
is `"Name not allowed"`, F; a directory is `"A directory"`, Q; a missing
parent `"Not found: <parent>"`, F; the mounted file `"File is mounted"`,
Q. Returns `((real, file_exists(real)), 1)`. This allowlist is the one
`DISK_NEW_TAP` uses; `SAVE_NAME` in `tspico_io.py` has its own (PROTOCOL
§13, "The two filename allowlists disagree").

### `NATIVE_LOAD_PREP(path, op, mod)`

SD active. Checks the file against the statement and writes the one-shot
tape. Returns `(length of the tape, 1)` or `(message, status)`.

1. The file must exist (F). `size` from `os.stat`; the first
   `native.HDR_LEN` (128) bytes go to `native.describe(head, size)`, which
   gives `(type, length, param1, param2, data offset)` for a +3DOS file or
   a raw 6912-byte screen, else `None`. For `None`: with CODE the whole file
   is taken as `native.headerless_code(size)` (CODE at 32768; the ROM
   loads at the statement's address if one was given, which the Pico
   cannot see); with SCREEN$ `"Not a screen"`, Q; otherwise `"Not a
   TS-Pico file"`, F.
2. What the statement wants: MERGE, or no token, or LINE → a program;
   CODE or SCREEN$ → bytes; DATA → a number or character array. A mismatch
   is `"<name> holds <KIND[type]>"`, Q, before anything loads. SCREEN$ also
   needs `length == native.SCREEN_LEN` (`"Not a screen"`, Q).
3. The tape: `native.tap_block(0x00, native.tape_header(typ,
   native.tape_name(real), length, p1, p2))` is the 21-byte header block.
   The data block is written by hand into `NATIVE_TAP` (`/TMP/native.tap`,
   Pico flash — `LOAD_TS` serves from flash because the card's pins are the
   bus during a LOAD): two length bytes `length + 2`, the flag FFh, then the
   file from `start` in 512-byte chunks with the XOR running from FFh, then
   the XOR byte. A file shorter than its header says: `"Short file"`, status
   2 (R); the tape is left incomplete and nothing is armed.
4. Returns `21 + length + 4`, which becomes `TSP.totlen` while the tape is
   served.

Beware: a +3DOS file whose header length exceeds the file describes as
`None`; loaded as CODE it is taken whole, header included.

## OPEN # channels: tpi:chopen, tpi:chwr, tpi:chrd, tpi:chclose

The comment at line 3197 lists the four commands. The ROM's channel driver
([rom/exrom-fdd.md](../rom/exrom-fdd.md)) keeps a 200h-byte record per
stream in CHANS with a 64-byte output buffer and a 255-byte input buffer;
`CH_OUT` buffers what BASIC prints and `CH_FLUSH` sends it as `tpi:chwr
<hex>` when 64 bytes are up, at every CR on a record file, before a fetch
and at CLOSE #; `CH_IN` hands out buffered bytes and `CH_FETCH` refills
with `tpi:chrd` (PMR2 = 255). The Pico keeps each stream's path, mode and
position in `CHANNELS` ([tspico-state.md](tspico-state.md)), an instance
of `channels.Channels` over `SD_FS`, and does the text translation there
([channels.md](channels.md)). `CH_STATUS` maps a `ChannelError`'s letter
to a status: `F` 3, `Q` 4, `O` 10 (J); `CH_CALL` applies it and makes any
other letter Q. The card is unmounted between commands, so every operation
opens the file, seeks, reads or writes, and closes it.

### `SD_FS`

The file access `channels.Channels` is given on the Pico: four methods
over the SD card, which must be active while they run (`CH_CALL`). The host
test gives `Channels` a dictionary instead (`channels_hosttest.MemFS`), so
nothing in `channels.py` knows about the card.

### `SD_FS.exists(self, p)`

`file_exists(p)` ([tspico-files.md](tspico-files.md)): true for an existing
path that is not a directory.

### `SD_FS.size(self, p)`

`os.stat(p)[6]`, the size in bytes. Raises `OSError` for a missing file.

### `SD_FS.read(self, p, pos, n)`

Opens `p` read-only, seeks to `pos`, returns `f.read(n)`: up to `n` bytes,
fewer at the end of the file.

### `SD_FS.write(self, p, pos, data, truncate)`

`truncate` true: `open(p, "wb")` and write `data` — the file is created or
emptied even when `data` is empty (that is how `Channels.open` creates a
file). Otherwise `"ab"` when `pos` is at or past the end (the position is
then implied) and `"r+b"` with a seek to `pos` when it is inside the file:
bytes are overwritten in place and the file never shrinks.
`Channels._put` pads any gap first, so `pos` never exceeds the size.

### `DIR_NAMES(arg)`

The names `OPEN #n,"d:arg"` serves, SD active: what `CAT "arg"` would list,
one per entry, a directory's ending in `/`. `split_arg`, `resolve`, and
`os.stat` as `CATALOG_TEXT`; an unresolvable or missing path raises
`ChannelError("Not found", "F")`; a pattern under a file `("Not a
directory", "F")`; a single file names itself (as typed, not as stored);
a directory gives `catalog.select(os.ilistdir(real), pat)` — the same
order and the same hidden-file rules as CAT (spec §4, stage 3). Called by
`CH_OPEN` inside `CH_CALL`, so the names are read into memory at OPEN and
the stream never touches the card again.

### `CH_OPEN(pre, cmd)`

`tpi:chopen <mode> <path>`: opens stream PMR1 on an `f:` file or a `d:`
listing. PMR2 is the record length, 0 for a stream.

1. `stream = PMR1 & 0xFF`; the text splits at its first space into the mode
   and the path (no space: mode `r`, the whole text as the path).
2. **`d:`** (the first two characters, any case): the mode must be `r` and
   the record length 0, else `ChannelError("d: is read-only, no record
   length", "Q")`; `CHANNELS.open_list(stream, DIR_NAMES(spec))` inside
   `CH_CALL`. An error is logged at level 1. `CH_REPLY(st)`.
3. **`f:`** (the ROM strips the prefix; the Pico sees the bare path).
   `catalog.resolve(TSP.cur_path, path)`; an empty path, a path above the
   root or the root itself is `CH_REPLY(3)` (F) with no SD access. Then,
   inside `CH_CALL`: a directory is `("A directory", "Q")`; a missing
   parent `("Not found", "F")`; `CHANNELS.open(stream, real, mode, reclen)`
   — which drops any stale entry for the stream, checks the mode and the
   length (Q), requires the file for `r` (F), truncates for `w`, creates
   for `a` and `u`. Errors are logged. `CH_REPLY(st)`.

On the ROM, `CH_OPEN_HOOK` takes `f:` and `d:` specs (a `k`/`s`/`p` spec
goes to the stock code untouched), reads the optional `,"mode"[,len]`
(`OPEN_SYNTAX` makes the syntax pass store the number's hidden form, which
stock skipped), checks that the record and the command fit (Report 4),
sends the command with the stream in PMR1 and the length in PMR2 (a length
over 255 is sent as 255 so the Pico answers Q), calls `CH_STATUS`, and only
then builds the record and points STRMS at it: an error status from here
raises its report and the 2068 keeps no channel. NEW and a reset orphan the
ROM's records; the Pico's `table.pop` at the next OPEN of the stream makes
that harmless (spec §4, item 5).

Pinned by `disk_cmds_hosttest.py` (`test_channels`): `w` creates; a
missing file for `r` F; a missing directory F; a directory Q; a bad mode Q;
`u` with PMR2 6 is a record file; a length over 254 Q; `d:` lists
directories first with `/`, then files, then end of file; `d:*.bak` and
`d:games/*`; no match opens and reads end of file at once; a missing
directory F; mode `w` or a record length with `d:` Q. The audit test pins
`chopen u` with a record length.

### `CH_WRITE(pre, cmd)`

`tpi:chwr <hex>`: what BASIC printed to stream PMR1, as hexadecimal pairs
in the command text (the body must be text, and 9 + 128 characters stay
under the 256-byte command). The pairs are decoded with `int(.., 16)`; a
bad digit is `CH_REPLY(5)` (C) and nothing is written.
`CH_CALL(CHANNELS.write, stream, data)` mounts the card, stores the bytes
at the stream's position with the TAB escape (23, lo, hi) honoured and
text translated, and gives the card back; a stream that is not open is
`O` → J, `TAB 0` followed by data or a record overrun `Q`.
`CH_REPLY(st)`. Output to a read stream is accepted and dropped — INPUT #'s
prompt items. The ROM's `CH_FLUSH` zeroes its count before sending, so
bytes the Pico refuses are dropped with the report and CLOSE # can still
close the stream. Pinned by `test_channels`: two writes translated and
appended; bad hex C; binary bytes as sent; `TAB 2` into record 2, padded.

### `CH_READ(pre, cmd)`

`tpi:chrd`: up to PMR2 bytes from stream PMR1, as a data phase read blind
by the ROM. `n = max(1, min(255, PMR2 or 255))`.

1. `CH_CALL(CHANNELS.read, stream, n)` gives the bytes (`b""` at the end of
   the file) or an error status.
2. An error, or no bytes: one byte — the status, or 7 (`_7_8_EOF`) for the
   end of the file — then `CH_READY()`. Return.
3. `gc.collect()` first, so no collection pauses the stream. `x` is the XOR
   of the bytes.
4. With DMA (`tspico_io._DMA`): the whole reply, `1`, the count, the bytes
   and `x`, is one buffer for `STREAM_DMA(MQ, out, _CMD_ECHO, CMD_STALL_MS,
   CH_READY)` ([tspico_io.md](tspico_io.md)): the channel feeds the TX FIFO
   from hardware and calls `CH_READY` once it is running. A port-0Fh write
   (BREAK, SYNC) or a stall returns a reason, raised as `CmdAbort` for
   `PROCESS_CMD`. `None` means no DMA: fall through.
5. By hand: `CMD_PUT(1)`, `CMD_PUT(count)`, `CH_READY()` — data in TX before
   READY — then each byte and `x`, each `CMD_PUT` waiting for room.

The ROM (`CH_FETCH`) waits READY after the body, reads the status, and for
1 reads the count, then each byte after a 16-iteration delay loop, then the
XOR; a mismatch is Report R ("a starved FIFO"); 7 makes `CH_IN` return NC
NZ, which the ROM's WAIT-KEY turns into Report 8; any other status is
`status − 1` to `STATUS_REPORT`. It reads with no handshake per byte, so
the Pico must never pause longer than the four-deep FIFO covers: the
comment here says ~70 µs a byte and ~280 µs of slack; `fddcmd.asm`,
PROTOCOL [§7](../../PROTOCOL.md) and ROM_CHANGES.md say ~75 µs
*(unverified: the figure is the 2068's loop timing, and the two numbers in
the sources differ)*. The count is one byte, so a reply is at most 255
bytes; `Channels.read` never returns more than asked.

Pinned by `test_channels`: `chrd 6` gives `1, 6, READY, the bytes, XOR`;
then the rest, then `7, READY`; a stream that is not open gives its status
alone. `test_channels` also pins that no handler calls `MQ_READY`
(READY + IDLE) here.

### `CH_CLOSE(pre, cmd)`

`tpi:chclose`: closes stream PMR1. Closing a stream that is not open is
status 1. `CHANNELS.close_writes(stream)` asks whether closing will write —
only a record file with a record left open by a trailing `;` (`PRINT
#4;TAB n;"ab";`), which `Channels.close` pads to its full length on the
card. If not: `CHANNELS.close(stream)` without the card, `CH_REPLY(1)`. If
so: `CH_CALL(CHANNELS.close, stream)`, which mounts the card; an error
(no card: J; an SD error: F) is logged and sent, and the stream stays in
`CHANNELS`.

The long comment at line 3385 is the history. When channels arrived (#83)
`close()` only dropped the entry, so `CH_CLOSE` never activated the card
and `TPI:CHCLOSE` went into `SD_FREE`. Records (#84) made `close()` write
the padding, onto a card that was not mounted: an `OSError`, Report J and a
short record, found by the [2026-09-30 audit](../../AUDIT-2026-09-30.md)
(§1 item 3). `TPI:CHCLOSE` stays in `SD_FREE` on purpose: CLOSE # of a
read stream, or of a write stream with nothing pending, must work with no
card in, so the dispatcher must not refuse it up front. Keeping the stream
open on an error is deliberate too: the ROM's `CH_CLOSE_HOOK` flushes,
sends `tpi:chclose`, and calls `CH_STATUS`, which raises the report before
the record is reclaimed, so BASIC still has the stream and CLOSE # can be
repeated once the card is back, writing the padding then.

Pinned by `src/test/audit_fixes_hosttest.py` (`test_ch_close`): an open
record is padded with the card active and nothing touches the card while it
is inactive; a read stream closes with no card; an open record with no card
answers J and the stream stays open; with the card back the same CLOSE #
pads and closes. `disk_cmds_hosttest.py`: `chclose` of a stream that is
not open is status 1.
