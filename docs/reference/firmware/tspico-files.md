# TS/tspico.py (part 5) — mounting, the folder caches, TAP helpers, the activity log, path helpers

Source: [`src/TS/tspico.py`](../../../src/TS/tspico.py), lines 1418–2225,
2570–2602, 3895–3900, 3993–4052, 4314–4401, 4548–4555, 5386–5443,
5679–5693, 5775–5853 and 6011–6027 (firmware 2.3).

This part holds the functions the command handlers ([part 6](tspico-commands.md))
and the dispatcher ([part 3](tspico-dispatch.md)) call to do their work:
copy a file from the SD card to the Pico's flash and make it the mounted
file; read a folder into the caches that `tpi:dir` and `LOAD "tpi:n"` use, and make
`dirinfo.tap` when it is LOADed; queue and write the activity log;
and turn command arguments, paths and the boot/dock settings into the forms
the handlers need. None of these is a command handler: none of them is in
`SA_funct`, and with one exception (`MOUNT_FILE`, which can call `UNMOUNT`)
none of them sends anything to the 2068. They sit between the bus helpers of
[part 2](tspico-bus.md) — `ACTIVATE_SD`, `DEACTIVATE_SD`, `ACTIVATE_MQ`,
`SD_CALL`, `LISTING_CHECK` — which they call to reach the card, and the
handlers, which call them. The module variables they fill (`files`, `dirs`,
`files_upper`, `dirs_upper`, `lista`, `alldirs`, `sd_space`, `prev_path`,
`log_entries`, `busy`, `led`) and the `TSP` fields they set are described in
[part 1](tspico-state.md); the TAP block table they build is
[`catalog.tap_table`](catalog.md).

The chapter follows the file. Where a function's reason is in a design
document it is linked, not restated: the pitfalls are in
[PROTOCOL.md §13](../../PROTOCOL.md#13-pitfalls), the 2026-09-30 audit in
[AUDIT-2026-09-30.md](../../AUDIT-2026-09-30.md), the flash slot layout in
[flash/README.md](../../../flash/README.md), the user's view in the
[user manual](../../manual/user-manual.md).

## Map

| Symbol | Lines | Role |
|---|---|---|
| `COPY_FILE(src_file, dst_file)` | 1418–1475 | copy a file 512 bytes at a time, after a bounded wait for core1 |
| `DCK_IMAGE()` | 1478–1547 | expand `/TMP/temp.bin` from a `.DCK` into a full 64 KB cartridge image |
| `DIRINFO_ROWS(listing)` | 1790–1806 | `dirinfo.tap`'s rows, one at a time (a generator) |
| `DIRINFO_WRITE()` | 1809–1855 | write `dirinfo.tap` for the current folder, row by row |
| `DIR_FILES()` | 1642–1698 | `LIST_DIR_FILES` with the card-error and out-of-memory handling; returns True/False |
| `LIST_DIR_FILES()` | 1701–1787 | read the current folder: `files`, `dirs`, `lista`, `sd_space` |
| `LOG(msg, level)` | 1858–1898 | queue a log line, filtered by `TSP.LOG_LEVEL` |
| `MOUNT_FILE(f_name, remounting=False)` | 1901–2073 | make a `.tap`, `.rom`, `.bin` or `.dck` the mounted file |
| `NEW_HDR(type_hdr, fname, long)` | 2076–2104 | a TAP header block |
| `OFF_TABLE()` | 2107–2119 | the mounted file's block table, rewound |
| `PARAMS(pre)` | 2122–2128 | the two `CODE` parameters from the pre-header |
| `SAVE_LOG()` | 2131–2174 | write `log_entries` to `/activity.log`; clears `busy` on every path |
| `WAIT_CORE1(limit_ms, who)` | 2177–2202 | bounded wait for a `SAVE_LOG` on core1 |
| `CLEAR_LOG()` | 2205–2223 | truncate `/activity.log` |
| `WALK(top)` | 2570–2583 | recursive folder walk (generator) |
| `GET_DIRS(path='/sd/TAP')` | 2586–2601 | every folder on the card, sorted, as public paths |
| `isTapMounted()` | 3895–3899 | is the mounted file a `.tap`? |
| `dir_exists(filename)` | 3993–3997 | `os.stat` says directory |
| `file_exists(filename)` | 4000–4004 | `os.stat` says not a directory |
| `public_path(n=0)` | 4021–4033 | `TSP.cur_path` without `/sd`, optionally shortened |
| `public_fname(n=0)` | 4036–4051 | `TSP.f_name` without `/sd`, optionally shortened |
| `ChangeDir(potential_new_path, SDactive=False)` | 4314–4401 | the rules of `tpi:cd` / `MOVE TO` |
| `getArgs(cmd)` | 4548–4555 | the text after the command word |
| `getBoot()` | 5386–5394 | (memory, slot) the 2068 boots from |
| `getDock()` | 5397–5405 | (memory, slot) in the DOCK |
| `SYSTEM_SLOT_LOCK(mem, page)` | 5408–5419 | is it flash slot 0, the Spectrum ROM, which `tpi:blkrcv` never writes? |
| `BOOT_SLOT_CLASH(mem, page, f_name)` | 5422–5442 | would the updater erase the booted slot? |
| `REMOVE_DIR(d)` | 5679–5693 | delete a tree (`/TMP` at boot) |
| `ResolveIndexName(name)` | 5775–5795 | a listing number to its file name |
| `LOAD_TPI(name, only_tap=False, fresh=False)` | 5798–5853 | `LOAD "tpi:<name>"`: find the file, mount it, say how it went |
| `FORGET_MOUNT()` | 6011–6027 | nothing mounted: clear the fields, delete the flash copies |
| `AUTO_MOUNT(name)` | 6030–6059 | `config.ini`'s `AUTOMOUNT`, mounted at boot, sending nothing |

### `COPY_FILE(src_file, dst_file)`

Copies one file to another, 512 bytes at a time, blinking the LED while it
runs. The mount uses it to put the file on the Pico's flash; `tpi:copy`
([`DISK_COPY_WORK`](tspico-disk.md)) uses it from card to card.

What it does:

1. `WAIT_CORE1(3000, "COPY_FILE")`: wait up to 3 s for a `SAVE_LOG` running on
   core1 to finish. A flash write stops both cores while a sector is
   programmed, and the comment calls two writers to the flash filesystem from
   two cores "asking for trouble".
2. Allocate a 512-byte buffer; return `False` if that fails.
3. Turn the LED on. Open `src_file` for reading and `dst_file` for writing.
   `readinto` the buffer and write what came back, until a read returns 0.
   Toggle the LED every 15 chunks (7.5 KB).
4. Any exception returns `False`. The `finally` turns the LED off either way.
5. Delete the buffer, `gc.collect()`, return `True`.

Why: the SD card and the Z80 bus share GPIO 2–4 ([part 2](tspico-bus.md)), so
the card cannot be read while the Z80 reads a LOAD block; the file has to be
on the Pico's own flash first ([flows/load.md](../flows/load.md)). The
comment block at the top is the history of the wait. Before the 2026-09-30
audit this function set `dead`/`busy` for a core1 LED thread that no longer
exists (the watchdog went with #51) and then spun `while busy: pass` *after*
the copy. The only thing that wait still waited for was `SAVE_LOG`, and a
`SAVE_LOG` whose flash write failed left `busy` True for ever, so every
`LOAD "tpi:file"` hung the Pico ([audit §1 item 1](../../AUDIT-2026-09-30.md)).
The wait is now bounded and comes *before* the write, which is the only
place it protects anything. [`src/test/audit_fixes_hosttest.py`](../../../src/test/audit_fixes_hosttest.py)
`test_busy` pins it: "COPY_FILE returns with busy stuck at True" and the
copy is byte-exact. The limit: "3 s is far more than a log write takes, and
well inside the ~20 s the Z80 waits for a command's reply".

Takes two paths. Returns `True` or `False`; nothing raises out of it.

State: reads `busy` (through `WAIT_CORE1`); writes `dst_file`; drives `led`.
The SD card must already be active when either path is on it: `COPY_FILE`
opens by name and never calls `ACTIVATE_SD`.

Callers: `MOUNT_FILE` (three times: the file to `/TMP/temp.bin` or
`/TMP/temp.tap`, and `/assets/dckupdate.tap` to `/TMP/temp.tap`),
[`DISK_COPY_WORK`](tspico-disk.md).

Beware: a failed copy leaves a partial destination, and it is the caller's job
to deal with it (`MOUNT_FILE` remounts the previous file). The 3 s wait is
spent inside a command the Z80 is waiting on; the main loop's SAVE and LOAD
branches make the same wait for the same reason
([PROTOCOL.md §13](../../PROTOCOL.md#13-pitfalls), "Wait for core1 before
starting a transfer").

### `DCK_IMAGE()`

Turns the raw `.DCK` file that `MOUNT_FILE` copied to `/TMP/temp.bin` into
the full 64 KB image the Z80 updater writes into a pair of flash or SRAM
slots, in the same place.

What it does:

1. `gc.collect()`; a 9-byte header buffer, a 256-byte chunk buffer and 256
   zero bytes; `rep = 8192 // 256 = 32`. `LOG("Start processing DCK file", 0)`.
2. Open `/TMP/temp.bin` for reading and `/TMP/temp_dck.bin` for writing; read
   the 9-byte DCK header.
3. Byte 0 is the bank the section is for. Only `0x00` (DOCK) is accepted.
   Anything else logs "Not a valid DOCK image; wrong header. Aborting..." at
   level 3, closes both files and returns `False`. The comment lists the other
   values: 254 EXROM, 255 HOME, 1–253 reserved.
4. Bytes 1–8 describe the eight 8 KB chunks of the 64 KB bank. Type 0 or 1:
   the chunk's data is not in the file, write 8 KB of zeros. Type 2 or 3: copy
   8 KB from the file. Any other value: "wrong chunk type", close, `False`.
5. Log success, close both, `os.remove("/TMP/temp.bin")`, rename
   `temp_dck.bin` to `temp.bin`, drop the buffers, `gc.collect()`, `True`.

Why: a DCK file carries only the chunks that exist; the updater
([`basic/assets/dckupdate.bas`](../../../basic/assets/dckupdate.bas)) writes a
whole bank, so the gaps are filled here, and `BLKRCV` streams exactly 65536
bytes of the result ("DCK_IMAGE always writes the full 64K"). A DCK file may
hold further sections after the first, each with its own header (the comment
gives HOME and EXROM replacements as the practical case); only the first
section is read. A cartridge takes two 32 KB slots, which is why the DOCK
slot numbers step by two ([flash/README.md](../../../flash/README.md),
[user manual 8.1](../../manual/user-manual.md#81-the-slots)).

Returns `True` or `False`. Logs its progress at level 0, its refusals at 3.

State: files under `/TMP` only. On a failure `/TMP/temp.bin` is left as the
raw copy and `/TMP/temp_dck.bin` as a partial image; neither is removed
*(inferred: no `os.remove` on those paths)*. `MOUNT_FILE` then remounts the
previous file, which overwrites `temp.bin` again.

Callers: `MOUNT_FILE` for a `.DCK`.

Beware: the chunk-type meaning is the DCK format's, not this code's; the
comment describes types 0 and 1 together as "non-existent chunk type (8kb
data is not in the file)", and the image treats them alike.

### `DIR_FILES()`

Rebuilds the folder caches for the current folder and survives a card error
or a heap too small for the listing. It is the function every "something
changed on the card" path calls.

What it does: try `LIST_DIR_FILES()` and return `True`. On `OSError` or
`MemoryError`: empty `files`, `dirs`, `files_upper` and `dirs_upper` (first,
so the half-built lists' memory is free again), `lista = ""`,
`sd_space = None`. Then, for `OSError`, log
`"DIR_FILES: SD card error, directory listing skipped: <reason>"` at level 2
and set `lista = DIR_HEADER("SD: card error") + "SD card error: reseat the card\r"`;
for `MemoryError`, `gc.collect()`, log `"DIR_FILES: out of memory, directory
listing skipped (<n> bytes free)"` at level 2 and set
`lista = DIR_HEADER("SD: out of memory") + "Too many files to list here\r"`.
Return `False`. Nothing else is caught, and nothing is written to the card.
(It used to remove `dirinfo.tap` here, a half-written one being garbage; the
listing has not written it since #384, so there is none to remove.)

Why `MemoryError` (#384): a 300-file folder on the v2 board ran out of heap
in `NEW_TAPBLK`, which built `dirinfo.tap`'s block as one `bytes` object,
about 9.7K in one piece, when the largest free block was 13.6K and falling
(REPL test, 2026-11-06). That block left the listing in the same issue
([`DIRINFO_WRITE`](#dirinfo_write)), but any allocation of a big enough
listing can still fail the same way. Uncaught, the error
reached `TS2068_IO`'s service-loop handler as an "unexpected error": the 2068
got a recovered status, the listing was left half-built, and three such
errors in a minute stop the firmware (FATAL). Now `MOVE TO` still lands in
the folder, and `tpi:dir` and CAT say why the listing is empty. Checked on a
v2 board at the REPL: `ChangeDir` returned normally and the card was
unmounted after every failing listing.

Why: the docstring records the field failure of 2026-09-26: `EIO` from
`sdcard.writeblocks` raised *inside* `os.ilistdir()`, FatFs flushing the
sector that the previous `os.remove("dirinfo.tap")` had dirtied. Uncaught, it
took `TS2068_IO` down at boot and the 2068 got no TS-Pico at all.
[`src/test/dir_files_eio_hosttest.py`](../../../src/test/dir_files_eio_hosttest.py)
pins both halves: `test_dir_files` (logs an ERROR, returns `False`, no
exception, for `EIO` and for `MemoryError`) and `test_boot` (the boot carries on into the dispatcher). The
"reseat the card" wording replaced "power cycle" in the audit ([§4](../../AUDIT-2026-09-30.md));
the card recovers without one since #66/#101 ([sdcard.md](sdcard.md)).

Precondition: the card is active and MicroPython's current directory is the
folder to list — `LIST_DIR_FILES` calls `os.ilistdir()` with no argument.
Every caller does `os.chdir(TSP.cur_path)` first.

Returns `True` or `False`. [`SD_REVALIDATE`](tspico-bus.md),
[`LISTING_FRESHEN`](tspico-bus.md) and [`REFRESH_LISTING`](tspico-bus.md)
store the result in `TSP.sd_listing_ok`; `ChangeDir`, `MDIR`,
[`DISK_ERASE_ONE`](tspico-disk.md), [`REFRESH_IF`](tspico-disk.md) and the
dispatcher's refresh after a SAVE ignore it.

Beware: after a failure `lista` is a one-line error listing and `files` is
empty, so `LOAD "tpi:n"` says "File does not exist" until the next successful
listing. After a `MemoryError` that lasts as long as the heap stays
fragmented: the folder is there but can't be listed. The cause is the
listing's own layout (#384), not fixed here.

### `LIST_DIR_FILES()`

The listing proper: fills the caches and builds the `tpi:dir` text. Raises
`OSError` on any card error; `DIR_FILES` is the guarded entry. It writes
nothing to the card.

What it does:

1. Reset `files`, `dirs`, `files_upper`, `dirs_upper` to `[]` and `lista` to
   `""`.
2. `ext = catalog.DIR_EXT` (`TAP`, `TZX`, `DCK`, `ROM`, `BIN`); names starting
   with `.` are excluded; `ordered = True` is hard-wired ("could be controlled
   by an option").
3. `listing = sorted(os.ilistdir(), key=lower-cased name)`, and
   `TSP.listing_sig = LISTING_SIG(listing)`: the fingerprint
   [`LISTING_FRESHEN`](tspico-bus.md) compares to notice a folder that changed
   on the card.
4. Folders (type 16384) first: each goes into `dirs`/`dirs_upper`; its shown
   name is `shorten_filename(catalog.screen_name(name), 20)`; the listing row is
   `"<%-21s       0 B" % (name + ">")`, 32 characters.
5. Files (type 32768) whose last three characters, upper-cased, are in `ext`,
   that do not start with `.` and are not `dirinfo.tap`: each goes into
   `files`/`files_upper`; the row is
   `"%03d %-18s%10s" % (i, shorten_filename(screen_name(name), 18), catalog.size_text(size))`,
   also 32 characters (the same row `DIRINFO_ROWS` makes). `i` counts from
   0. **This `i` is the index `LOAD "tpi:n"`, `tpi:dir CODE 1,n` and `tpi:rm n`
   use, and `files[i]` is the file.**
6. Every other file not starting with `.` and not `dirinfo.tap`, after the
   indexed ones: a row with four spaces where the index would be. It is
   not in `files` and not in `dirinfo.tap` (`DIRINFO_ROWS` has the same filter; "spec §2":
   [DISK_COMMANDS_SPEC.md](../../DISK_COMMANDS_SPEC.md)).
7. `os.statvfs("")` on the card: `sd_space = (total, free)` in bytes and
   `sd_stat = catalog.card_line(TSP.sd_label, *sd_space)`: `SD: 240 MB;
   free: 236 MB`, with the card's label in place of `SD` when it has one,
   in at most 32 columns ([catalog.md](catalog.md#card_linelabel-total-free)).
8. `lista = DIR_HEADER(sd_stat) + rows`, or `+ "Directory is empty\r"` when
   there are none ([`DIR_HEADER`](tspico-messages.md) is four 32-column
   lines: path, SD line, column titles, dashes).

Why no `dirinfo.tap` (#384): steps 4 and 5 used to build its rows too, and a
step 9 packed them with `NEW_TAPBLK` (one `bytes` object, about 9.7K for 300
files, grown by concatenation) and wrote the file on every listing. That was
the biggest allocation of every `MOVE TO`, the one a 300-file folder ran out
of heap in, and a card write per listing, though the file's only reader is a
`LOAD "tpi:dirinfo.tap"`. [`DIRINFO_WRITE`](#dirinfo_write) makes it then.
An old `dirinfo.tap` left on the card by earlier firmware is still filtered
out by name in steps 5 and 6. (It used to be deleted before every listing,
the FAT write #62 traced field `EIO` errors to; the audit, §3, made it a name
filter.) The `>` shortening and the `?` for characters the 2068 cannot show
are #120 and #132 ([catalog.md](catalog.md)).

State: writes the six module variables above and `TSP.listing_sig`. Needs the
card active and the current directory set.

Callers: `DIR_FILES` only.

Beware: `nom = bytearray(32)` is dead; the variable is reassigned a string.
The index numbers follow the sorted order, so
adding a file renumbers everything after it; the fingerprint re-read in
`LISTING_FRESHEN` is what keeps `LOAD "tpi:n"` honest after a change.

### `DIRINFO_ROWS(listing)`

The rows of `dirinfo.tap`'s `a$`, as a generator: one 32-character string at
a time, so only one row is held.

What it does: for a listing in `LIST_DIR_FILES`' order (`os.ilistdir()`'s
entries sorted by lower-cased name), yield each folder (type 16384) as
`"%-32s" % shorten_filename(catalog.screen_name(name), 20)`, then each file
`LOAD "tpi:n"` numbers (type 32768, last three characters upper-cased in
`catalog.DIR_EXT`, not starting with `.`, not `dirinfo.tap`) as
`"%03d %-18s%10s" % (i, shorten_filename(screen_name(name), 18),
catalog.size_text(size))`, with `i` from 0.

Why: these are the rows `LIST_DIR_FILES` built into its `dirinfo` list before
#384, with the same filter and order as `files`, so row `i` is `files[i]`.

Callers: `DIRINFO_WRITE` (twice: once to count, once to write).

Beware: the filter is written out a second time here; it must stay the same
as `LIST_DIR_FILES`' steps 5–6, or the numbers in `a$` drift from
`LOAD "tpi:n"`'s. [`dirinfo_hosttest.py`](../../../src/test/dirinfo_hosttest.py)
checks they match.

### `DIRINFO_WRITE()`

Writes `<cur_path>/dirinfo.tap`, the listing as a tape: one character array,
`a$`, row 1 the number of folders, row 2 the number of files, then the folder
names, then `nnn name size` rows. `LOAD "" DATA a$()` reads it; the flash
menu program (`nofile.bas`) uses it for its file browser
([user manual 10.2](../../manual/user-manual.md#102-mounting-load-tpi)).

What it does, with the card active:

1. `os.chdir(TSP.cur_path)`; `listing = sorted(os.ilistdir(), key=lower-cased
   name)`. If `LISTING_SIG(listing)` is not `TSP.listing_sig` the folder
   changed since `files` was built: `DIR_FILES()` first, so the numbers in
   `a$` are the ones `LOAD "tpi:n"` uses.
2. Count: `n_dirs` folders, `n_files` the rest of `DIRINFO_ROWS`;
   `rows = 2 + n_dirs + n_files`; `data = 1 + 4 + 32 * rows` (the dimension
   count, the two dimensions, the rows).
3. Open the file and write `NEW_HDR(2, "dirinfo", data)`, then the block's
   first eight bytes: its TAP length `data + 2` (flag and checksum included),
   `FFh` (data), `2`, `rows` and `32`, low byte first. The `2` is the array's
   number of dimensions, as the 2068 stores an array; the old builder's
   comment called it the "String array type", but the type is the header's
   byte 1 (`NEW_HDR`'s `type_hdr`, 2 for a character array) *(inferred from
   the tape format)*.
4. Each row, the two count rows (`"%-32s" % n`) and then `DIRINFO_ROWS`, is
   encoded and padded or cut to 32 bytes in one reused `bytearray(32)` and
   written; the XOR checksum of everything after the length is kept as it
   goes and written last.

Why (#384): the file used to be built by `LIST_DIR_FILES` on every listing,
as one `bytes` object grown by concatenation (`NEW_TAPBLK`, about 9.7K for
300 files), and written to the card on every `MOVE TO`. That was the
allocation a big folder ran out of heap in, and a card write per listing,
for a file only a `LOAD "tpi:dirinfo.tap"` reads. Made on demand, a listing
writes nothing, and the file holds one row in memory at a time; the folder
read in step 1 is the only transient, the same one a listing has. The bytes
are exactly the old builder's ([`dirinfo_hosttest.py`](../../../src/test/dirinfo_hosttest.py)
compares them).

State: reads `TSP.cur_path` and `TSP.listing_sig`; may rebuild the listing
(`DIR_FILES`); writes `dirinfo.tap` on the card. Raises `OSError` on a card
error and `MemoryError` if even the folder read does not fit.

Callers: [`LOAD_TPI`](#load_tpiname-only_tapfalse-freshfalse), for the name
`dirinfo.tap`.

Beware: `put` is a closure that keeps the checksum with `nonlocal`. A row
longer than 32 bytes once encoded (it can't be: `screen_name` makes every
character printable ASCII) would be cut, not shift the rest.

### `LOG(msg, level)`

Queues one line for the activity log, and prints it when `log_to_serial` is
set.

What it does: for `level` 0–4 prefix `LOG_LABELS[level]` (`INFO`, `WARNING`,
`ERROR`, `CRITICAL`, `SPECIAL`) and a colon; any other level keeps the raw
message. `print(m)` if `log_to_serial`. Look `TSP` up with
`globals().get("TSP")`: if it exists and `TSP.LOG_LEVEL` is nonzero, drop
the message when `level < LOG_LEVEL`. Otherwise append
`"[%d]%s\n" % (time.ticks_us(), m)` to `log_entries`.

Why: the comment block. `TSP` is created in `TS2068_IO` only after
`LOAD_CONFIG` has read `config.ini`, and `LOAD_CONFIG` itself logs when the
file is missing, unreadable or holds a bad `ROM_SM`. The old guard
`if TSP.LOG_LEVEL:` read `TSP` to make the check and raised `NameError`, so
a corrupt `config.ini` — a power cut while `LOAD_CONFIG` rewrites it, which
it does on every boot from a non-default slot — crashed the boot
([audit §1 item 2](../../AUDIT-2026-09-30.md);
[`audit_fixes_hosttest.py`](../../../src/test/audit_fixes_hosttest.py)
`test_log_before_tsp`). Until `TSP` exists every message is kept: those are
the lines that explain why the defaults were used.

Takes a string and an integer level. `LOG_LEVEL` 0 keeps everything; the
default 2 keeps `ERROR` and above ([user manual 10.3 loglevel](../../manual/user-manual.md#loglevel)).
The timestamp is `ticks_us`, which wraps; the comment suggests NTP time on a
Pico W.

State: appends to `log_entries`. Touches neither the card nor the bus;
`SAVE_LOG` writes the list out later.

Callers: everything. Callees: none.

Beware: `log_to_serial` prints over USB, which
[PROTOCOL.md §13](../../PROTOCOL.md#13-pitfalls) forbids during a protocol
exchange ("Don't `print()` during a protocol exchange"); it is a development
switch ([part 1](tspico-state.md)). `LOG` allocates: `PROCESS_CMD` wraps the
`LOG` in its exception handler in its own `try`, because a handler that died
of `MemoryError` may take the log call with it.

### `MOUNT_FILE(f_name, remounting=False)`

Makes `f_name`, a full path on the card such as `/sd/TAP/GAME.TAP`, the
mounted file: copies it to the Pico's flash, sets the `TSP` fields and builds
the block table. For a ROM or cartridge image it also stages the Z80
updater tape that will write the image into a slot. Returns `True` when the
file is mounted. The caller answers the 2068; this function does not, except
through the `UNMOUNT` call described under *Beware*.

**What it accepts.** The decision is by extension, the last four characters
upper-cased:

- `.TAP`: a tape. It is copied to `/TMP/temp.tap`.
- `.BIN`, `.ROM`: a ROM image. It is copied to `/TMP/temp.bin`, and
  `/assets/romupdate.tap`, patched with the image's length, becomes
  `/TMP/temp.tap`. On the v3 card it's `/assets/romupd3.tap`, unpatched.
- `.DCK`: a cartridge. It is copied to `/TMP/temp.bin`, expanded in place by
  `DCK_IMAGE`, and `/assets/dckupdate.tap` (v3: `dckupd3.tap`) becomes
  `/TMP/temp.tap`.
- Anything else: "Wrong filename while mounting".

Names and listing numbers are resolved before the call (`LOAD_TPI`,
`ResolveIndexName`); `MOUNT_FILE` takes only a path. The listing indexes
`.TZX` files too, so a `.TZX` name reaches the last case.

**What it does, step by step.**

1. `TLM`. Save `TSP.offset`, `TSP.tap_idx` and `TSP.append` in locals, for a
   possible remount.
2. `msg = "File %s mounted correctly"`, `err_level = 0`, `remount = False`.
   `remount` means "the previous mount's flash copy has been overwritten, so
   put it back if this fails".
3. `ACTIVATE_SD()`. This raises `OSError(19)` when there is no card
   ([part 2](tspico-bus.md)); nothing here catches it. LED on.
   `totlen = os.stat(f_name)[6]`, which raises `OSError` for a file that is
   not there.
4. **`.BIN`/`.DCK`/`.ROM`**: `COPY_FILE(f_name, "/TMP/temp.bin")`. A failed
   copy: `remount = True`, "Copying file …", level 2. Then:
   - `.DCK`: `DCK_IMAGE()`. If it succeeds, the updater tape is copied to
     `/TMP/temp.tap`: `/assets/dckupdate.tap` on v2 (`board.SLOTS`),
     `/assets/dckupd3.tap` on the v3 card. A failed copy is level 2
     "Copying dckupdate.tap" with `remount = True`. If `DCK_IMAGE`
     fails: `remount = True`, level 2, "Creating DCK image for … See logfile
     for details".
   - `.BIN`/`.ROM` on the v3 card (`board.SLOTS` false):
     `COPY_FILE("/assets/romupd3.tap", "/TMP/temp.tap")`, as it is. A failed
     copy is level 2 "Copying romupd3.tap" with `remount = True`. Nothing is
     patched: the Pico writes the slot itself (`SLOT_WRITE`), so no Z80 code
     needs the length.
   - `.BIN`/`.ROM` on v2: split `totlen` into `len_hi`, `len_lo`. Read
     `/assets/romupdate.tap` whole into a `bytearray`. Walk two TAP blocks
     (each a 2-byte length then that many bytes) to reach block 3, the
     machine code. Patch `len_lo`, `len_hi` at offset +104 into that block
     and again 200 bytes further on: the two places the updater's two write
     routines ("Update LOWER block" is the second) hold the length to
     program. Set `remount = True` and write the patched tape to
     `/TMP/temp.tap`. Any exception in this block gives level 2 "Copying
     romupdate.tap"; `remount` is then whatever it was when the exception
     happened (`False` if the asset could not be read, `True` if the write
     failed).
5. **`.TAP`**: `os.stat` again; if the size is not 0, read the first 7
   bytes. `b"ZXTape!"` is a TZX: level 2 "Wrong file type while mounting: …
   It's a TZX file". Otherwise, if byte 0 is greater than 19, the message
   becomes "Non-standard first block while mounting file … Expected 19, read
   N" but the level stays 0: informational only, the file still mounts. If
   `err_level < 2`: `COPY_FILE(f_name, "/TMP/temp.tap")`; a failed copy is
   level 2 with `remount = True`.
6. **Else**: level 2, "Wrong filename while mounting: …".
7. `DEACTIVATE_SD()`, `ACTIVATE_MQ()`: the bus goes back to the MQ with Y
   BUSY. `LOG(msg, err_level)`.
8. **If `err_level > 1`**: log "Failed to mount: …" and run `BLINK_ERROR()`
   (ten 0.1 s toggles: one second, blocking). Then:
   - if `remounting` (this call *is* the remount) or nothing is mounted
     (`not TSP.f_name`): `UNMOUNT([], [])`, "don't leave a bad file mounted";
   - else if `remount`: `MOUNT_FILE(TSP.f_name, True)`. If that succeeds the
     saved offset, index and append flag are put back, `err_level` is set to
     0 and "Remounted: …" is logged — and this call then returns `True`;
   - else nothing: the previous mount's flash copies were not touched and it
     is still good.
9. **Else (success)**: `totlen = os.stat("/TMP/temp.tap")[6]`;
   `TSP.f_name = f_name`; `TSP.totlen = totlen`; `TSP.append = False`;
   `OFF_TABLE()` (the table from `temp.tap`, position 0). Any exception in
   this block: `UNMOUNT([], [])`.
10. LED off. Return `err_level == 0`.

**Why it is written this way.** The copy to flash is the bus-sharing
constraint under `COPY_FILE`. For a ROM or cartridge the trick is in the
comment at line 1952: the updater tape goes to `temp.tap` but `TSP.f_name`
keeps the image's name, so the next plain `LOAD ""` runs the updater's BASIC
program from `temp.tap`
([`LOAD_TS`](tspico_io.md)), and that program's `SAVE "tpi:blkrcv"` streams
the image from `temp.bin` ([`BLKRCV`](tspico-commands.md#blkrcvpre-cmd);
[user manual 8.4](../../manual/user-manual.md#84-putting-a-rom-or-cartridge-into-a-slot)).
The +104/+200 patch offsets depend on the layout of
[`basic/assets/romupdate.bas`](../../../basic/assets/romupdate.bas)'s code
block; the comment says the BASIC may change as long as block 3 and those
offsets do not, and the audit (§5) checked them against the asset bytes and
notes that no test pins them. The 7-byte comparison is done on bytes, not
decoded text: `.decode()` raised `UnicodeError` on a TAP whose first block
is headerless or whose header name has a byte ≥ 80h, so such tapes could not
be mounted, and the TZX message was overwritten by the "non-standard first
block" one ([audit §2 #16](../../AUDIT-2026-09-30.md);
[`audit_fixes_hosttest.py`](../../../src/test/audit_fixes_hosttest.py)
`test_mount_bytes`: a headerless first block mounts, a TZX is refused and the
log says TZX). The `U3_CS` write that used to deselect the card was removed
by the audit (§3): `DEACTIVATE_SD` and the driver's `init_card` already do
it. The remount exists because a failed new mount may already have
overwritten the only copy of the old file on flash.

Takes `f_name` (`str`) and `remounting` (`bool`, internal). Returns `True`
or `False`. A `True` after a failed new mount means the *previous* file is
mounted again; the caller can only tell by comparing `TSP.f_name`.

State written: `TSP.f_name`, `TSP.totlen`, `TSP.append` (always `False`
after a mount — [user manual 4.3](../../manual/user-manual.md#43-adding-to-a-tap-append-and-format)),
`TSP.offset_tbl`, `TSP.tap_idx`, `TSP.offset` (through `OFF_TABLE`);
`/TMP/temp.tap` and `/TMP/temp.bin`; the LED; the bus (SD, then back to the
MQ). Reads `/assets/romupdate.tap` and `/assets/dckupdate.tap` on the Pico's
flash root (copies under `src/assets/` are gitignored; the release workflow
ships them; see [boot.md](boot.md)).

Callers: `LOAD_TPI` (every `LOAD "tpi:…"`, in both modes), `IDIR`,
[`DISK_FORMAT`](tspico-disk.md), itself (the remount), and the
dispatcher after a SAVE — the re-mount of an appended file, the mount of
a newly saved file when nothing was mounted, and the re-mount of a mounted
TAP the SAVE replaced ([part 3](tspico-dispatch.md), lines 7316, 7333 and
7345, inside a `try` because the card may have gone).

Beware:

- It raises: `ACTIVATE_SD`'s `OSError(19)` with no card, `os.stat`'s
  `OSError` for a missing file. Inside a command, `PROCESS_CMD`'s handler
  turns that into Report J (`FAIL_CMD`) and the tail still runs
  ([PROTOCOL.md §11](../../PROTOCOL.md#11-writing-a-command-handler)); the
  comment there names "MOUNT_FILE's unguarded os.stat() with no SD card" as
  the easy case to hit.
- `UNMOUNT` is the `tpi:close` handler: it calls
  `SEND_MSG("Unmounting file. ", "", _1_OK)` before `FORGET_MOUNT`. Reached
  from here it answers the 2068 in the middle of a mount, and the real
  caller then sends its own answer (`LOAD_TPI` returns "Error mounting
  file:" with Q). *(inferred)* With nothing mounted — the first `LOAD "tpi:"`
  of a session, or after `tpi:close` — a mount that fails without a remount
  (a `.TZX` name, a `.tap` with a TZX signature) therefore hands the Z80
  status 1 first: it prints `0 OK` (or "Unmounting file." when VERBOSE is
  on), and the Q is left in TX until the next command's SYNC, which
  `CMD_DRAIN` takes for a BREAK ("stopped by BREAK" in the log). The manual
  (10.2) says Q for a TZX. No host test sees this: they replace `SEND_MSG`.
  Not observed on hardware.
- *(inferred)* A `.BIN`/`.ROM` whose copy to `temp.bin` succeeded but whose
  `romupdate.tap` could not be read leaves `remount` False: `TSP.f_name`
  still names the previous file while `temp.bin` holds the new image.
- `TSP.totlen` is the size of `temp.tap`: for a ROM or cartridge that is the
  updater tape's size, not the image's.
- An empty `.tap` mounts; `OFF_TABLE` gives it an empty table.
- `BLINK_ERROR` blocks for a second on every failure, inside the Z80's
  ~20 s wait.
- It says nothing to the Z80 about READY, and must not: the caller answers
  after it returns ([PROTOCOL.md §13](../../PROTOCOL.md#13-pitfalls), "Don't
  announce READY and then go do SD work").

### `NEW_HDR(type_hdr, fname, long)`

Builds a 2068 tape header block, with its TAP length word, for a data block
of `long` bytes.

What it does: `long` outside 0–65535 logs "Wrong block length in NEW_HDR" at
level 2 and returns `None`; `type_hdr` outside 0–3 logs "Wrong header type"
and returns `None`. Otherwise the header is `00` (the flag) + the type byte +
`fname` padded or cut to 10 characters + `long` low, high + `69 C1 80 80` +
the XOR of those 18 bytes, prefixed with `13 00` (19, the TAP length). The
comment says the second of the four fixed bytes is the array letter, and the
listing always uses the same variable (`a$`), so the pattern never changes
*(inferred: `C1h` is `A` (`41h`) with bits 7 and 6 set, the 2068's encoding
of a character-array name in a header's parameter 1)*.

Returns a 21-byte `bytearray`, or `None`.

Callers: `DIRINFO_WRITE` (type 2, name `dirinfo`). The `long` arithmetic
uses floating point (`int(long/256)` and the remainder scaled back); every
multiple of 1/256 is exact in a float, so the result is right.

Beware: the name is added as `f"{fname:<10}"[:10].encode()`; it was a plain
`str` added to a `bytearray`, which only MicroPython takes, until #384 made
it run on the host too ([`dirinfo_hosttest.py`](../../../src/test/dirinfo_hosttest.py)).
A `None` return is not checked by the caller.

### `OFF_TABLE()`

Rebuilds `TSP.offset_tbl` from the flash copy of the mounted tape and rewinds
to block 0.

What it does: open `/TMP/temp.tap`; `TSP.offset_tbl = catalog.tap_table(f)`,
one entry per block, `[offset, length, " Y" or " N", name]` where a header's
name is its 10-character filename and a data block's is the type of the
header before it or `Code block` ([catalog.md](catalog.md));
`TSP.tap_idx = 0`; `TSP.offset = 0`; close; `gc.collect()`.

Why: [`LOAD_TS`](tspico_io.md) walks the mounted file by this table;
`FWD`, `REW`, `TAPDIR` and `GETINFO` read it. The comment at the call site
in `MOUNT_FILE` is the point: the table is built from `temp.tap`, never from
`TSP.f_name`, so for a ROM or cartridge it describes the updater tape.

Callers: `MOUNT_FILE` only.

Beware: raises `OSError` when `temp.tap` is missing; `MOUNT_FILE` catches it
and unmounts. The table is a list of lists in RAM, one per block.

### `PARAMS(pre)`

Returns the two `CODE` parameters of a command from its 10-byte pre-header:
`par1 = (pre[4] << 8) | pre[3]`, `par2 = (pre[6] << 8) | pre[5]`, the PMR1
and PMR2 words the ROM sends low byte first
([PROTOCOL.md §5.1](../../PROTOCOL.md#5-commands-b-taddr-0);
[appendix/ports-and-status.md](../appendix/ports-and-status.md)). `SAVE
"tpi:x" CODE a,b` gives `(a, b)`; no `CODE` gives `(0, 0)`; each is 16 bits
unsigned.

Callers: every handler with `CODE` options (24 call sites) and
[`ZX48_IO`](tspico-dispatch.md). A handler that chains to another builds a
pre-header of its own — `pre = [0] * 10` with `pre[3]` and `pre[5]` set —
and passes it: `CDIR` to `DIR` (`CODE 2,0`), `FWD` and `REW` to `TAPDIR`
(`CODE 0,255` or `CODE 1,255`), `MDIR` to `CDIR` (`CODE 2,0`).

### `SAVE_LOG()`

Appends `log_entries` to `/activity.log` on the Pico's flash and empties the
list. It is the one thing the idle loop runs on core1.

What it does: `busy = True`; open `/activity.log` for append and write each
entry (the entries end in `\n` already); in a `finally`, `log_entries = []`
and `busy = False`.

Why, from the comment block: writing to the Pico's flash stops both cores
while a sector is programmed, so a log write must not overlap a LOAD or SAVE
block or the pre-header burst after a SYNC — the Z80 keeps clocking bytes
and the 4-deep PIO FIFO overflows. `busy` is how core0 knows a write is in
progress, and `WAIT_CORE1` is how it waits. Before the audit `busy` was
cleared only on the success path; a write that raised (flash full, a
filesystem error) killed the thread with `busy` True, every
`while busy: pass` then spun for ever, and the idle loop never tried again
because it only starts `SAVE_LOG` when `not busy`
([audit §1 item 1](../../AUDIT-2026-09-30.md);
[PROTOCOL.md §13](../../PROTOCOL.md#13-pitfalls), "`busy` is set by another
core"; [`audit_fixes_hosttest.py`](../../../src/test/audit_fixes_hosttest.py)
`test_busy`: a failed write still clears `busy` and drops the entries). The
entries are dropped even when the write failed: a full flash stays full, and
the list would otherwise grow without bound in the ~150 KB heap; "the error
itself can't be logged: that is the log". `busy = True` is also set by the
idle loop on core0 *before* `start_new_thread`, so there is no window in
which a transfer sees core1 idle as the write begins; setting it again here
covers the synchronous calls.

State: `busy`, `log_entries`, `/activity.log`. The file is rotated at boot
by [`TS2068_IO`](tspico-dispatch.md).

Callers, synchronous on core0: [`LOAD_CONFIG`](tspico-dispatch.md) (after a
failed `config.ini` write, and at its end), `TS2068_IO` at boot (at the
start, after the card setup, before the main loop), `ACTIVATE_SD` when a
card that was present fails to mount, the service-loop restart after an
unexpected error, and `ZX48_IO`'s idle branch. On core1: `TS2068_IO`'s idle
loop, inside `try/except OSError` ("core1 in use") after `busy = True`
([PROTOCOL.md §13](../../PROTOCOL.md#13-pitfalls), "Never call
`_thread.start_new_thread()` unguarded").

Beware: nothing here waits for an earlier write; the synchronous callers all
run on core0 at moments when core1 is idle or when the Z80 is not mid-block.
Never call it between a handler's READY and the Z80's reads.

### `WAIT_CORE1(limit_ms, who)`

Waits, for at most `limit_ms`, until a `SAVE_LOG` on core1 has finished.
Returns `True` if core1 is idle (at once if `busy` is already `False`),
`False` if it gave up, after logging "`who`: gave up waiting `limit_ms` ms
for the log write on core1" at level 2.

Why, from the docstring: the flash write stops both cores, so a transfer
that starts during one can lose bytes mid-block; but `busy` is set and
cleared by another core, and the old unbounded `while busy: pass` turned any
way of it staying `True` into a hang that only a power cycle cleared. Giving
up costs at worst one transfer that overlaps a write, which the 2068 reports
and the user retries; waiting for ever costs the session. The caller picks
the limit from what the Z80 tolerates at that point; a normal log write takes
a few tens of milliseconds.

Callers: `COPY_FILE` (3102); the main loop before a SAVE, a LOAD and a
headerless LOAD (3102 each, [part 3](tspico-dispatch.md)). `ZX48_IO` has an
inline 3 s wait of the same shape (line 7814), because the ZX ROM waits
~3.8 s for READY. Pinned by `audit_fixes_hosttest.py` `test_busy` ("gives up
when busy never clears"; "returns True at once when core1 is idle").

Beware: a busy-wait; nothing else runs on core0 meanwhile.

### `CLEAR_LOG()`

Truncates `/activity.log` and empties `log_entries`. `busy = True`; open the
file for writing (which truncates it) and set `log_entries = []`; log "Log
file was cleared" at level 0, so that is the new log's first line; on any
exception log "OS error clearing log file" at level 2 and return `False`;
`busy = False`; return `True`.

Callers: `GETLOG` for `tpi:log clear`.

Beware: `busy` is not cleared in a `finally`, but nothing between the two
assignments can raise out of the `try/except`. *(inferred)* It does not call
`WAIT_CORE1` first, so a `SAVE_LOG` already running on core1 could be
appending to the file this truncates.

### `WALK(top)`

A generator: `os.ilistdir(top)`, collect the names whose type is `0x4000`,
yield `(top, subdirs)`, then recurse into each subdir as `"%s/%s"`. Depth
first; the recursion depth is the folder depth. Any `OSError` propagates to
`GET_DIRS`. Callers: `GET_DIRS`, itself.

### `GET_DIRS(path='/sd/TAP')`

Returns every folder under `path`, sorted, as public paths: `path[3:]`
strips `/sd`, so the list is `["/TAP", "/TAP/GAMES", "/TAP/GAMES/ARCADE", …]`.
Any exception logs "Unable to succesfully update directories list: …" at
level 2 and returns what had been gathered so far (at least the root).
Success logs at level 0.

Why: `tpi:cd` with `CODE 0,1` offers every folder on the card as a menu
([`CDIR`](tspico-commands.md#cdirpre-cmd)); the card is walked once, not on
every menu.

Callers: [`SD_REVALIDATE`](tspico-bus.md) (the first time a card is seen,
and whenever one comes back or is swapped) stores the result in `alldirs`;
[`DISK_REN`](tspico-disk.md) rebuilds it after renaming a folder. `MDIR`
appends to `alldirs` instead of calling this.

Beware: one `ilistdir` per folder, with the card active; the default
argument is the root's real path, the same string as `catalog.ROOT`.

### `isTapMounted()`

`TSP.f_name and TSP.f_name[-4:].lower() == '.tap'`. Truthy when a `.tap` is
mounted; the value is `[]` or `""` when nothing is, a `bool` otherwise.
Callers: `TAPDIR`, `APPEND` (twice), `FWD`, `REW`, `GETINFO`. `dirinfo.tap`
counts.

### `dir_exists(filename)`

`(os.stat(filename)[0] & 0x4000) != 0`: the directory bit of `st_mode`.
`False` on any `OSError`: a missing path, no card, a card error. Needs the
card active for a path on it. FAT compares names without case, so
`dir_exists("games")` is true for `GAMES`. Callers: `SD_REVALIDATE`,
`ChangeDir`, `GETHELP`, `MDIR`, `REMOVE_DIR`, `RM_CHECK`, and the
disk commands ([part 7](tspico-disk.md)). Beware: a card that has died looks
like "not there" *(inferred from the `except OSError`)*.

### `file_exists(filename)`

The same `os.stat`, true when the directory bit is clear: "exists and is not
a directory". `False` on `OSError`. Callers: `SD_REVALIDATE`,
`GETHELP`, `MDIR`, `RM_CHECK`, the disk commands and channels.

### `public_path(n=0)`

The current folder as the user sees it: `"/" + xstr(TSP.cur_path[4:])`, so
`/sd/TAP/GAMES` is `/TAP/GAMES` and the root is `/TAP`. `xstr`
([part 4](tspico-messages.md)) shows a character the 2068 cannot print as
`?`. With `n`, `shorten_filename(p, n)` cuts the middle out with a `>`.
Callers: `DIR_HEADER` (27), `DIR` (0 and 27), `IDIR` (27), `PATH`, `CDIR`
(27 and 0), `GETINFO`. Note the two public forms in the firmware:
`public_path` keeps `TAP` in the path, `catalog.public()` drops it
(`/sd/TAP/GAMES` → `/GAMES`, [catalog.md](catalog.md)), so `CAT` of the
current folder says `Path:/TAP/GAMES` and `CAT "games"` says `Path:/games`.

### `public_fname(n=0)`

The mounted file as the user sees it: `xstr(TSP.f_name[3:])`
(`/TAP/GAME.TAP`), shortened with `n`; `""` when nothing is mounted.
Callers: `PATH`, `TAPDIR` (27), `APPEND`, `GETINFO`,
[`DISK_FORMAT`](tspico-disk.md).

### `ChangeDir(potential_new_path, SDactive=False)`

The rules of `tpi:cd` and the ROM's `MOVE TO` (which the fdd module sends as
`tpi:cd x`, `"-"` included, and `MOVE TO ""` as `tpi:cd`, the menu:
[rom/exrom-fdd.md](../rom/exrom-fdd.md)). Returns `(status, message)`.

What it does: `TLM`; `status = _1_OK`; unless `SDactive`, `ACTIVATE_SD()`
(raises with no card; not in a `finally`). `old_path = TSP.cur_path`. Then
the first rule that matches:

1. `"-"`: `prev_path` if it is set and `dir_exists`; otherwise stay, with
   status F.
2. `".."` while at the root (`TSP.cur_path.count("/") == 2`, i.e. exactly
   `/sd/TAP`), `"/"`, or `/tap` in any case: the root `/sd/TAP`. "cd .." at
   the top has always meant "stay at the top", not an error.
3. A path beginning `/tap/` in any case: `"/sd" + path`, with no existence
   check.
4. Anything `catalog.resolve(TSP.cur_path, arg)` turns into a real path
   (`a/b`, `../x`, `/games`, `.`; never above the root —
   [catalog.md](catalog.md)) that `dir_exists`: that path.
5. Otherwise stay, status F.

If the status is OK: `os.chdir(new_path)` and `TSP.cur_path = os.getcwd()`;
any exception makes it Q. If still OK: `prev_path = old_path` when the path
actually changed; log `"Changed dir to: <arg>"` at level 0; `DIR_FILES()`
(its result is ignored). Otherwise the message is
`"OS error changing to: <arg>"` at level 2 — for the plain not-found F as well as the Q. Unless
`SDactive`: `DEACTIVATE_SD()`, `ACTIVATE_MQ()`.

Why: the two comment blocks. A hand-made `..` branch from before
`catalog.resolve` existed (#79) built the *relative* path `sd/TAP`, which
only landed in the right place while MicroPython's current directory was the
VFS root, and it ran before the `resolve()` branch and hid it; and a last
`cur_path + "/" + arg` fallback was reached only when `resolve()` had refused
a path that climbs above `/sd/TAP`, so its only effect was to leave the card
root. Both were removed by the audit ([§1 items 4 and 5](../../AUDIT-2026-09-30.md))
and are pinned by [`audit_fixes_hosttest.py`](../../../src/test/audit_fixes_hosttest.py)
`test_cd`: `cd games/arcade`, `cd ..` twice back to the root, `cd ..` at the
root stays, `cd ../..` from one level down is F.

State: `TSP.cur_path`, `prev_path`, the caches through `DIR_FILES`,
MicroPython's current directory; the bus.

Callers: `CDIR` only, twice, both without `SDactive`. *(inferred)* The
`SDactive` parameter is vestigial.

Beware: a folder given as `/tap/x` skips the existence check and fails in
`os.chdir`, so a missing one is Q where a plain `x` is F; the manual lists
only F ([10.3 cd](../../manual/user-manual.md#cd-change-folder)).
`os.getcwd()` returns the name in the case the card stores it, which may
differ from what was typed; the code that compares paths upper-cases
(`RM_CHECK`, `REFRESH_IF`). `dir_exists` swallows card errors, so a dead
card gives F, not J *(inferred)*.

### `getArgs(cmd)`

The arguments of a command: everything after the first space that follows
the command word, case kept, or `""` when there is none.

`cmd` is `"D.." + text` as `PROCESS_CMD` hands it over
([PROTOCOL.md §5.2](../../PROTOCOL.md#5-commands-b-taddr-0)), so `cmd[7:]`
is the text after `tpi:`; the space is looked for there and the slice starts
after it. `getArgs("D..tpi:cd a b")` is `"a b"`; `getArgs("D..tpi:dir")` is
`""`; two spaces after the word leave a leading space in the result (`DIR`,
`RM` and `DISK_FORMAT` strip; `CDIR` and `GETHELP` do not).

Why: the header comment (lines 89–93): the space used to be assumed at the
seventh character because every command with a name argument was two letters
long, so `tpi:dirt` matched `tpi:dir`. Command words are now cut at the first
space in `PROCESS_CMD` and may be any length.

Callers: 17 handlers. `MDIR` uses `cmd[10:]` instead, which is the same slice
for the two-letter `md`.

### `getBoot()`

`(mem, page)` the 2068 boots from: `mem = TSP.ROM_SM & 3` and
`page = TSP.bank_sm & 15`, written as a subtraction of the masked-out bits.

The bit scheme the two helpers share: `TSP.ROM_SM` holds the memory types,
bits 0–1 for BOOT and bits 2–3 for DOCK, 1 = SRAM and 2 = flash, so the
valid values are 5, 6, 9 and 10 (`LOAD_CONFIG` refuses the rest —
[part 3](tspico-dispatch.md)); on the v3 card 3 = a slot on the SD card,
which adds 7, 11 and 13–15; `TSP.bank_sm` holds the slots, bits 0–3 for
BOOT (`ROM_SLOT`) and bits 4–7 for DOCK (`DCK_SLOT`), built by
[`PICO_STATUS.__init__`](tspico-state.md) as `DCK_SLOT * 16 + ROM_SLOT`. The
two values are the words written to the bank state machines by
`board.map_slots` ([board.md](board.md)): on v2 `ROM.put(TSP.ROM_SM)`
(state machine 4, `set_ctrl`) and `BANK.put(TSP.bank_sm)` (state machine 5,
`sel_bank`; [pio.md](pio.md)). A slot is 32 KB of the 512 KB flash or SRAM;
a cartridge takes two ([flash/README.md](../../../flash/README.md)).

Callers: `GETINFO`, `MEMBOOT`, `BOOT_SLOT_CLASH`.

### `getDock()`

`(mem, page)` in the DOCK: `mem = (TSP.ROM_SM & 12) >> 2`,
`page = TSP.bank_sm >> 4`, written as subtractions and integer divisions.
Callers: `BLKRCV`, `GETINFO`, `MEMDOCK`.

### `SYSTEM_SLOT_LOCK(mem, page)`

Would `tpi:blkrcv` write flash slot 0? Returns the refusal as `(msg,
msg1)`, `"Can't write Flash slot 0:"` and `"the Spectrum ROM."`, or `None`
for any other slot and for SRAM (`mem` 1), whose slots are scratch. A 64K
`.DCK` at slot 0 writes slots 0 and 1, and is refused the same way.

Why: slot 0 holds the original Spectrum ROM, which ZX Spectrum mode and
the 1.x upgrade path need ([upgrade.md](upgrade.md)). Nothing installs it
through `tpi:blkrcv`: a flash image holds it, and on the v3 card the web
updater replaces it every time. Until 2026-10-13 the loaders only warned
("Replace it?", "ABSOLUTELY SURE"), and a `tpi:blkrcv` typed by hand wrote
it with no question at all.

Slot 1, the 2068 ROM every power-on boots, is left writable on purpose
(decided 2026-10-13). Reloading `TSPICO-23.ROM` into it with the loader,
from another slot, is the manual's recovery for a damaged slot 1 (A.5),
the one that needs no computer. It stays behind the loader's
"ABSOLUTELY SURE" question, as slots 2 and 3 do. The loaders (`romupdate`,
`dckupdate`, `romupd3`, `dckupd3`) say "Flash slot 0 is locked" and ask
for another slot, so this refusal is the second line of defense.
`boot_slot_guard_hosttest.py` (v2) and `board_v3_hosttest.py` pin both:
slot 0 refused, slot 1 and SRAM 0 written.

Callers: `BLKRCV` on v2, before `BOOT_SLOT_CLASH`, and `SLOT_WRITE` on
the v3 card, after its range check, and `MEMDOCK`, but not to refuse:
docking flash slot 0 is ZX Spectrum mode's ordinary state, image mounted
or not. `MEMDOCK` uses it to skip `BOOT_SLOT_CLASH` for a slot `BLKRCV`
will never write (#372).

### `BOOT_SLOT_CLASH(mem, page, f_name)`

Would the ROM updater, writing the mounted image through DOCK `(mem, page)`,
overwrite the slot the 2068 is running from? Returns the refusal as
`(msg, msg1)` — `"Can't write Flash slot N:"` (or `SRAM`) and
`"the 2068 is running from it." + CR + "Boot another slot first."` — or
`None`.

The rule: `None` unless `f_name` is a `str` whose extension is `.ROM`,
`.BIN` or `.DCK` (the `str` test dates from when `TSP.f_name` started as
`[]`, before #163; it is now always a `str`); `None` unless
`mem` is the boot memory (`getBoot`); `None` unless `page` is the boot slot,
or, for a `.DCK`, the boot slot is `page + 1` — a 64 KB cartridge fills
`page` and `page + 1`. Otherwise the refusal, naming the boot slot.

Why: the hardware incident of 2026-09-28, in the docstring of
[`src/test/boot_slot_guard_hosttest.py`](../../../src/test/boot_slot_guard_hosttest.py):
a test ROM booted from flash slot 4 (`SAVE "tpi:boot" CODE 2,4`), then
`romupdate.tap` was told to write slot 4; it sent `tpi:memdock CODE 2,4` and
`tpi:blkrcv`, the Z80 erased the ROM it was running from, and both machines
hung with slot 4 half-written. The updater erases and writes the DOCK slot
from Z80 code, so the only safe moment to refuse is before the DOCK moves
(`MEMDOCK`) and again before a byte is streamed (`BLKRCV`). The rule is
stated for users in [flash/README.md](../../../flash/README.md) ("You can't
update the slot you booted from") and the
[user manual 8.4](../../manual/user-manual.md#84-putting-a-rom-or-cartridge-into-a-slot)
and A.4. The test pins: nothing mounted passes; a `.ROM` at the boot slot is
Q and neither state machine is written; another slot, the other memory and
an SRAM boot behave; a `.DCK` is refused for `n` and `n + 1`; plain DOCK use
with a `.TAP` mounted is untouched. The `isinstance` test is the fix for
`tpi:dock` with no file mounted raising (Report J), noted in the audit's
status for #128.

Callers: `MEMDOCK` (before it changes anything, unless `SYSTEM_SLOT_LOCK`
locks the slot), `BLKRCV` (after `SYSTEM_SLOT_LOCK`).

`MEMDOCK` skips it for flash slot 0 (since #372). A `.DCK` docked at 2,0
spans slots 0 and 1, so with the usual boot from flash 1 the rule above
refuses it, yet `BLKRCV` never writes there (`SYSTEM_SLOT_LOCK`), so
nothing is protected. And 2,0 is the default `dckupdate.bas` puts the DOCK
back to (lines 650 and 680): when its `tpi:close` at line 600 had failed
(on v2, because `BLKRCV` was still blocked behind the write loop; see
[`BLKRCV`](tspico-commands.md#blkrcvpre-cmd), "Why pieces"), the `.DCK` was
still mounted, both restores came back Report Q, and the
loader stopped with the DOCK still on the cartridge it had just written.

Beware: it compares against the *current* boot setting, which `tpi:boot`
changes at once while the 2068 keeps running the old ROM until `NEW` or a
reset *(inferred from the code; the manual tells the user to `NEW`)*. It
does not look at what the slots contain.

### `REMOVE_DIR(d)`

Deletes `d` and everything under it: if `dir_exists(d)`, recurse into each
entry (skipping `.` and `..`) and `os.rmdir(d)`; otherwise `os.remove(d)`.
Any exception logs "Could not remove directory `d`" at level 1 and stops that
branch. Callers: `TS2068_IO` at boot, `REMOVE_DIR("/TMP"); os.mkdir("/TMP")`,
which is how the flash copies of the last session's mount are cleared; and
itself. Beware: it asks nothing and follows no rules; it is only ever pointed
at `/TMP`.

### `ResolveIndexName(name)`

A listing number to its file: if `int(name)` is in `0 <= i < len(files)`,
`(files[i], i)`; otherwise `(name, -1)` (a `ValueError` from `int()`, or an
index out of range). The `0 <=` is the audit's fix for `LOAD "tpi:-1"`, which
mounted the *last* file through Python's negative indexing
([`audit_fixes_hosttest.py`](../../../src/test/audit_fixes_hosttest.py)
`test_index`: `"1"` is the second file, `"-1"` and a number past the end are
not indexes, a name stays a name). Callers: `LOAD_TPI`, `RM`. *(inferred)*
`int()` also accepts `" 3"` and `"+3"`; `3.tap` is a name.

### `LOAD_TPI(name, only_tap=False, fresh=False)`

`LOAD "tpi:<name>"`: find the file in the current folder, mount it, and
return `(msg, name, status)` for the caller's `SEND_MSG`. `name` is a file
name in any case, a listing number, a name with wildcards, or `dirinfo.tap`.

What it does, in order:

1. `dirinfo.tap`: make it first. `ACTIVATE_SD()`, [`DIRINFO_WRITE()`](#dirinfo_write),
   then `DEACTIVATE_SD()` and `ACTIVATE_MQ()` in a `finally` (`MOUNT_FILE`
   mounts the card itself). An `OSError` or `MemoryError` there logs
   "dirinfo.tap not written: <error>" at level 2 and gives Q with "Error
   mounting file: ". Then `MOUNT_FILE("<cur_path>/dirinfo.tap")`: OK with
   "Mounting dir info: ", or R with "Error mounting file: " (logged at
   level 2). Since #384 the listing no longer keeps the file up to date, so
   this LOAD is where it is made.
2. `ResolveIndexName`; if that gave no index and the upper-cased name is in
   `files_upper`, its position is the index.
3. Still no index and `catalog.has_wild(name)`: the files whose *shown* name
   matches (`catalog.match_shown`: `?` only for a character the listing
   shows as `?`, `*` for any run — [catalog.md](catalog.md)). Exactly one
   hit is the index. Several: F with `"%d files match: "` and, as the second
   line, the name and `Use LOAD "tpi:" with its number.`
4. Still no index and not `fresh`: `LISTING_CHECK()` (mount the card,
   re-read the folder if it changed, hand the bus back —
   [part 2](tspico-bus.md)), then the same call again with `fresh=True`.
5. Still no index: F, "File does not exist: ", logged at level 2.
6. `only_tap` and the file is not a `.TAP`: Q, "Only .tap files in ZX48
   mode: ".
7. `MOUNT_FILE("<cur_path>/<file>")`: OK "File mounted OK", or Q "Error
   mounting file:".

Why: the number form is what the listing and the Commander use; the second
look at the card (#132) is for a file copied onto the same card between two
commands, which used to need a reboot
([user manual 3.3](../../manual/user-manual.md#33-mounting-a-tap-file)); the
wildcards are #132's answer to names with characters the 2068 cannot type.
`.ROM`, `.DCK` and `.BIN` mount a TS-2068 updater program, so ZX48 mode
refuses them (docstring).

Callers: `PROCESS_CMD` for a `LOAD "tpi:"` (pre-header byte 1 = 1, 2 or 3:
[PROTOCOL.md §5.5](../../PROTOCOL.md#5-commands-b-taddr-0)), which answers
`SEND_MSG(msg, name, status, " files match: " in msg)` — the several-matches
hint always shows, everything else only with VERBOSE on
([user manual 10.2](../../manual/user-manual.md#102-mounting-load-tpi));
[`ZX_TPI`](tspico-dispatch.md) with `only_tap=True`, whose statuses go out
through `ZX_REPORT` ([`zx48_tpi_hosttest.py`](../../../src/test/zx48_tpi_hosttest.py):
"a failed mount: Q"); itself, once.

State: through `MOUNT_FILE`; `LISTING_CHECK` may rebuild the caches.

Beware: the no-card case never reaches here — `SD_NEEDED` says a LOAD is
always card work and the dispatcher answers J first
([part 3](tspico-dispatch.md)). `MOUNT_FILE` may still raise when the card
goes mid-command (Report J). The `UNMOUNT` answer inside `MOUNT_FILE` (see
there) is sent before this function's own answer.

### `FORGET_MOUNT()`

Nothing is mounted any more: `TSP.f_name = ""`, `TSP.offset_tbl = []`,
`TSP.offset = 0`, `TSP.tap_idx = 0`, `TSP.append = False`; then remove
`/TMP/temp.bin` and `/TMP/temp.tap`, each in its own `try`, because one that
is missing must not keep the other. Sends nothing and touches only the
Pico's flash.

Callers: `UNMOUNT` (`tpi:close`), [`SD_REVALIDATE`](tspico-bus.md) when
the mounted file is not on the card that has just appeared, and
`AUTO_MOUNT` when its file can't be mounted.

Beware: `TSP.totlen` keeps its old value *(inferred)*. After it `TSP.f_name`
is `""`, not the boot-time `[]`; both are falsy, and `BOOT_SLOT_CLASH`'s
`isinstance(f_name, str)` then falls through on the extension test instead.

### `AUTO_MOUNT(name)`

Mounts `config.ini`'s `AUTOMOUNT` at boot, so the first `LOAD ""` loads that
file instead of the flash's `nofile.tap` menu. `name` is a path from the
card's top folder, as `tpi:automount` saves it (`/GAMES/menu.tap`); a
hand-edited one without the leading `/` resolves the same way.

Called once, from `TS2068_IO`, with the card mounted and the MQ not yet
started, after `BLINK_LED` has stopped
([tspico-dispatch.md](tspico-dispatch.md)). It does what `MOUNT_FILE` does
for a `.tap`, but sends nothing and leaves the SD and the MQ alone:
`MOUNT_FILE` ends with `DEACTIVATE_SD`/`ACTIVATE_MQ`, and when a mount fails
with nothing mounted it calls `UNMOUNT`, whose `SEND_MSG("Unmounting file.
")` would be an orphan ahead of the boot's status pre-load.

1. `catalog.resolve(catalog.ROOT, name)`. `None` (a path out of the top
   folder), a name not ending `.TAP` (any case), or no such file: fails.
2. The first 7 bytes are `ZXTape!` (a TZX): fails.
3. `COPY_FILE(real, "/TMP/temp.tap")`; `False`: fails.
4. `TSP.f_name = real`, `TSP.totlen` the file's size, `TSP.append = False`,
   `OFF_TABLE()`: the block table, pointer at 0.

Any failure (an exception from any step too) calls `FORGET_MOUNT` and logs
"Auto-mount *name*: *why*; LOAD "" gives the menu" at level 1; returns
`False`. Success logs "Auto-mounted *name*" at 0 and returns `True`.
`TSP.cur_path` is not touched: the current folder at power-on stays the
top one (David's choice, 2026-10-13).

Beware: a file renamed or deleted on the card afterwards is caught by
`SD_REVALIDATE` only when the card is seen to change; until then the
flash copy loads *(inferred)*. `board_v3_hosttest.py` pins the mount, the
failures and that nothing reaches the MQ.
