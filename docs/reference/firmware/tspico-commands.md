# TS/tspico.py (part 6) — the `tpi:` commands

Source: [`src/TS/tspico.py`](../../../src/TS/tspico.py): the handlers at
2505–2577 (`DIR`), 3414–3830 (`IDIR` … `SA_NOT_IMP`), 3895–4113
(`APPEND`, `BLKRCV`), 4205–4718 (`CDIR` … `GETLOG`), 4798–5095
(`LOGLEVEL` … `MEMDOCK`), 5115–5191 (`REW`), 5333–5560 (`BAD_CODE` …
`NOP`) and 5666–5742 (the printer settings); the dispatch table
`SA_funct` at 6170–6220, inside `TS2068_IO`.

`SAVE "tpi:word args" CODE a,b` sends the text `tpi:word args` and the two
numbers to the Pico; `PROCESS_CMD` looks the word up in `SA_funct` and
calls the handler. This chapter is that table, one row per word, and then
every handler of this part of the file in source order: what each form of
the command does, what it answers, which reports it gives and why, what
it needs from the bus and the SD card, and what state it changes. The
handlers of ROM 2.1's disk keywords and channels (`DISK_*`,
`NATIVE_OPEN`, `CH_*`) are in [tspico-disk.md](tspico-disk.md); mounting
(`LOAD "tpi:name"`, `MOUNT_FILE`, `LOAD_TPI`) and the helpers the handlers
share (`getArgs`, `PARAMS`, `ChangeDir`, `getBoot`, `getDock`,
`BOOT_SLOT_CLASH`, `FORGET_MOUNT`, `ResolveIndexName`) in
[tspico-files.md](tspico-files.md); external commands in
[extcmd.md](extcmd.md). For the user's view of each command see the
[user manual, chapter 10](../../manual/user-manual.md#103-the-tpi-commands);
where the manual and the code differ, the entries below say so.

## Map

| Symbol | Line | Command(s) |
|---|---|---|
| `DIR(pre, cmd)` | 2505 | `tpi:dir` |
| `IDIR(pre, cmd)` | 3414 | `tpi:idir` |
| `PATH(pre, cmd)` | 3643 | `tpi:path` |
| `TAPDIR(pre, cmd)` | 3675 | `tpi:tapdir` |
| `NEW_TAP(pre, cmd)` | 3759 | `tpi:newtap` |
| `SA_NOT_IMP(pre, cmd)` | 3827 | the seven reserved words |
| `APPEND(pre, cmd)` | 3895 | `tpi:append` |
| `BLKRCV(pre, cmd)` | 3960 | `tpi:blkrcv` |
| `CDIR(pre, cmd)` | 4205 | `tpi:cd` |
| `FWD(pre, cmd)` | 4265 | `tpi:ffw` |
| `GETHELP(pre, cmd)` | 4354 | `tpi:help` |
| `GETINFO(pre, cmd)` | 4521 | `tpi:info` |
| `GETLOG(pre, cmd)` | 4609 | `tpi:log` |
| `LOGLEVEL(pre, cmd)` | 4798 | `tpi:loglevel` |
| `MDIR(pre, cmd)` | 4857 | `tpi:md` |
| `MEMBOOT(pre, cmd)` | 4922 | `tpi:boot`, `tpi:memboot` |
| `MEMDOCK(pre, cmd)` | 5024 | `tpi:dock`, `tpi:memdock` |
| `REW(pre, cmd)` | 5115 | `tpi:rew` |
| `BAD_CODE(command, par1, par2)` | 5333 | the "Bad CODE" message |
| `BAD_ARG(command, arg)` | 5338 | the "Bad argument" message |
| `RM(pre, cmd)` | 5343 | `tpi:rm` |
| `RM_CHECK(name)` | 5389 | `RM`'s checks, with the card |
| `UNMOUNT(pre, cmd)` | 5407 | `tpi:close` |
| `VERB_TOGGLE(pre, cmd)` | 5435 | `tpi:verbose` |
| `ZX48(pre, cmd)` | 5489 | `tpi:zx48` |
| `NOP(pre, cmd)` | 5543 | `tpi:nop` |
| `PRN_OPEN(pre, cmd)` | 5666 | `tpi:opprint` |
| `PRN_CLOSE(pre, cmd)` | 5687 | `tpi:clprint` |
| `PRN_FLAG(pre, cmd)` | 5698 | `tpi:autolf`, `tpi:noautolf`, `tpi:autopg`, `tpi:noautopg` |
| `PRN_SIZE(pre, cmd)` | 5711 | `tpi:prnsz` |
| `PRN_BMP(pre, cmd)` | 5729 | `tpi:bmp` |

Between these, in the same stretch of the file, are functions other
chapters own: `ListMenu` ([tspico-messages.md](tspico-messages.md)),
`isTapMounted`, `dir_exists`, `file_exists`, `public_path`,
`public_fname`, `ChangeDir`, `getArgs`, `LOAD_CONFIG`, `getBoot`,
`getDock`, `BOOT_SLOT_CLASH`, `REMOVE_DIR`, `ResolveIndexName`,
`LOAD_TPI`, `FORGET_MOUNT` ([tspico-files.md](tspico-files.md),
[tspico-dispatch.md](tspico-dispatch.md)), `xchr`, `xstr`, `BUILD_FIT`,
`SEND_MSG_PROMPT_YN` ([tspico-messages.md](tspico-messages.md)).

## How a handler is called

`PROCESS_CMD` ([tspico-dispatch.md](tspico-dispatch.md)) has read the
pre-header and the body, checked the body's XOR, and decoded the text.
Then:

1. `cmd = "D.." + text`. The three characters stand for the body's `'D'`
   and length bytes, so `cmd[3:]` is the text (`tpi:dir *.tap`) and
   `cmd[7:]` the text after `tpi:`. Handlers index into it at fixed
   offsets (`MDIR` takes `cmd[10:]`, the name after `tpi:md `).
2. The command word is the text up to its first space, upper-cased, with
   `TPI:`: `"TPI:DIR"`. The comment above `SA_funct` (6167–6168) says
   commands that take a name "need a space at the end of their dictionary
   key"; no key has one, and the split on the first space makes it
   unnecessary. The comment is out of date.
3. **The card gate.** If the command needs the card (`SD_NEEDED`: every
   word of `SA_funct` not in `SD_FREE`, and `tpi:help` with a topic) and
   `TSP.sd_present` is false, the card is probed once (`SD_PROBE`); still
   none, and `NO_CARD_REPLY` answers ("No SD card…", Report J) without
   calling the handler ([tspico-bus.md](tspico-bus.md#sd_neededload_cmd-cmd_word-cmd_exec-sa_funct)).
   A card believed present is not probed: the handler's own mount finds
   out.
4. `SA_funct[word](pre, cmd)`. External commands (`EXT_SA_FUNCT`) are
   called as `f(MQ, TSP, pre, cmd)` instead. An unknown word gets "Unrecognized
   command: TPI:WORD" and `SAVE "tpi:help" for info`, Report C.

What a handler gets:

- **`pre`**, the ten pre-header bytes. `PARAMS(pre)` gives the `CODE`
  numbers `(par1, par2)`, each 16-bit; without `CODE` both are 0, which is
  why "no CODE" and `CODE 0,0` are the same command everywhere. Handlers
  that chain to another handler build a fresh `pre = [0] * 10` and set
  `pre[3]` (par1's low byte) and `pre[5]` (par2's low byte).
- **`cmd`**, as above. `getArgs(cmd)` is the text after the first space
  following the word, case kept, not stripped.

What a handler must do:

- **Answer exactly once**, with one of the builders of
  [tspico-messages.md](tspico-messages.md): `SEND_MSG` (a bare status
  unless VERBOSE is on or the message is forced), `SEND_MSG2` (pages),
  `ListMenu`, `SEND_MSG_PROMPT_YN`, `PROMPT_EACH` — or, for the few that
  answer by hand (`NOP`, `BLKRCV`), one status byte and `MQ_READY()`. After
  a builder that waits for keys the exchange is over; nothing more may be
  sent. A handler that answers nothing leaves the ROM to read the tail's
  pre-load `01h` as its status: "0 OK".
- **Give the bus back** after any SD access: `SD_CALL`, or
  `ACTIVATE_SD` … `DEACTIVATE_SD`, `ACTIVATE_MQ` before answering
  ([tspico-bus.md](tspico-bus.md)). Several of the older handlers here
  (`GETHELP`, `MDIR`) call `ACTIVATE_SD` with no `try`: if it raises, the
  exception reaches `PROCESS_CMD`, and `FAIL_CMD` gives the bus back and
  answers Report J.
- **Let `CmdAbort` through.** Never catch `BaseException` or use a bare
  `except:` around an answer builder ([tspico-bus.md](tspico-bus.md#cmdabort)).
- **Not stage the pre-load.** `PROCESS_CMD`'s tail does that.

Status conventions in these handlers: a bad `CODE` or a bad word argument
is Report A (`_8_A_Invalid_arg`) with `BAD_CODE`'s or `BAD_ARG`'s message;
a name that is missing or not allowed is F; a request that cannot be
carried out (the mounted file, a full flash) is Q. "Shown" below means
the message is forced (`SEND_MSG(…, True)`) and appears whatever VERBOSE
says; otherwise only the report is seen with VERBOSE off. The reports
themselves are in [tspico-state.md](tspico-state.md#the-status-codes).

## The dispatch table, `SA_funct`

Built in `TS2068_IO` (6170) as a literal dictionary; `PROCESS_CMD`
receives it as an argument. 48 words, 31 handlers here and 9 in
[tspico-disk.md](tspico-disk.md). "Card" says whether the card gate
applies (the word is not in `SD_FREE`).

| Word | Handler | Card | Forms | Answer |
|---|---|---|---|---|
| `tpi:append` | APPEND | no | no `CODE`: show; `CODE 1,1` or `on`: on; `CODE 1,0` or `off`: off | `SEND_MSG`; the show form shown |
| `tpi:blkrcv` | BLKRCV | no | `CODE len,offset`; sent by the ROM/DCK updater loaders | one status, then a blind byte stream |
| `tpi:cd` | CDIR | yes | `tpi:cd name` (`..`, `/`, `-`, paths); `CODE 1,0`/`1,1`/`1,2`/`2,0` to list, pick, list in full, show; no name: a menu (`CODE 0,1`: of every folder) | `SEND_MSG`, a listing, or `ListMenu` |
| `tpi:close` | UNMOUNT | no | — | `SEND_MSG`, always 0 OK |
| `tpi:dir` | DIR | yes | no `CODE`: the listing; `tpi:dir arg`: CAT `arg`; `CODE 1,n`: file `n`'s full name; `CODE 2,n`: full names from `n` | `SEND_MSG2`, or `SEND_MSG` |
| `tpi:copy` | DISK_COPY ([tspico-disk.md](tspico-disk.md#disk_copypre-cmd)) | yes | `a\|b` from MOVE, or `a b` by hand | `SEND_MSG`, or `SEND_MSG2` for a pattern |
| `tpi:erase` | DISK_ERASE ([tspico-disk.md](tspico-disk.md#disk_erasepre-cmd)) | yes | a name or a pattern | `SEND_MSG`, or `PROMPT_EACH` |
| `tpi:format` | DISK_FORMAT ([tspico-disk.md](tspico-disk.md#disk_formatpre-cmd)) | yes | `x.tap` or `dir/` | `SEND_MSG` |
| `tpi:ren` | DISK_REN ([tspico-disk.md](tspico-disk.md#disk_renpre-cmd)) | yes | `old\|new` or `old new` | `SEND_MSG` |
| `tpi:fopen` | NATIVE_OPEN ([tspico-disk.md](tspico-disk.md#native_openpre-cmd)) | yes | sent by ROM 2.1 before `SAVE`/`LOAD "f:…"` | `SEND_MSG`, or the `88h` prompt |
| `tpi:chopen` | CH_OPEN ([tspico-disk.md](tspico-disk.md#ch_openpre-cmd)) | yes | sent by ROM 2.1's `OPEN #` | `CH_REPLY` |
| `tpi:chwr` | CH_WRITE ([tspico-disk.md](tspico-disk.md#ch_writepre-cmd)) | yes | sent by `PRINT #` | `CH_REPLY` |
| `tpi:chrd` | CH_READ ([tspico-disk.md](tspico-disk.md#ch_readpre-cmd)) | yes | sent by `INPUT #`, `INKEY$ #` | a data phase |
| `tpi:chclose` | CH_CLOSE ([tspico-disk.md](tspico-disk.md#ch_closepre-cmd)) | no | sent by `CLOSE #` | `CH_REPLY` |
| `tpi:ffw` | FWD | no | `CODE 0,n` blocks, `1,n` blocks and list, `2,n` files, `3,n` files and list | `SEND_MSG`, or `TAPDIR`'s listing |
| `tpi:help` | GETHELP | a topic: yes | no argument: the summary; `?`: the topics; a topic | `SEND_MSG2` |
| `tpi:idir` | IDIR | yes | — | `ListMenu` |
| `tpi:info` | GETINFO | no | — | `SEND_MSG2` |
| `tpi:log` | GETLOG | no | `CODE 0,n`: the last `n` bytes; `clear` (asks), `clear` `CODE 255,0` | `SEND_MSG2`, `SEND_MSG`, or the Y/N prompt |
| `tpi:loglevel` | LOGLEVEL | no | no `CODE`: show; `CODE 1,n` or `tpi:loglevel n` | `SEND_MSG`; the show form shown |
| `tpi:md` | MDIR | yes | `tpi:md name`; `CODE 1,0` to go into it | `SEND_MSG`, or `CDIR`'s |
| `tpi:boot` | MEMBOOT | no | no `CODE`: show; `CODE mem,slot` | `SEND_MSG`; the show form shown |
| `tpi:memboot` | MEMBOOT | no | the same | the same |
| `tpi:dock` | MEMDOCK | no | no `CODE`: show; `CODE 0,1`: the previous; `CODE 0,2`: swap; `CODE mem,slot` | `SEND_MSG` |
| `tpi:memdock` | MEMDOCK | no | the same | the same |
| `tpi:nop` | NOP | no | — | `01h` |
| `tpi:path` | PATH | no | no `CODE`: the folder; `CODE 1,0`: the mounted file | `SEND_MSG`, shown |
| `tpi:rew` | REW | no | as `tpi:ffw`, backwards | as `tpi:ffw` |
| `tpi:rm` | RM | yes | a name, a path or an index; `CODE 255,0`: no question | the Y/N prompt, or `SEND_MSG` |
| `tpi:newtap` | NEW_TAP | yes | `tpi:newtap name[.tap]` | `SEND_MSG` |
| `tpi:tapdir` | TAPDIR | no | `CODE 0,n` blocks, `1,n` files, `n` either side of the pointer; `n = 255` a screenful | `SEND_MSG2` |
| `tpi:verbose` | VERB_TOGGLE | no | no `CODE`: show; `CODE 1,n` or `on`/`off` | `SEND_MSG`; the show form shown |
| `tpi:zx48` | ZX48 | no | `CODE a,b`: `a` 1 = no message; `b` 1 normal loader, 2+ compatible, ≥ 16384 its buffer | `SEND_MSG`, then ZX48 mode |
| `tpi:autolf` | PRN_FLAG | no | — | `SEND_MSG` |
| `tpi:autopg` | PRN_FLAG | no | — | `SEND_MSG` |
| `tpi:bmp` | PRN_BMP | no | `CODE width,height` | `SEND_MSG` |
| `tpi:clprint` | PRN_CLOSE | yes | — | `SEND_MSG` |
| `tpi:config` | SA_NOT_IMP | no | reserved | Report C |
| `tpi:delete` | SA_NOT_IMP | no | reserved | Report C |
| `tpi:freset` | SA_NOT_IMP | no | reserved | Report C |
| `tpi:getconfig` | SA_NOT_IMP | no | reserved | Report C |
| `tpi:list` | SA_NOT_IMP | no | reserved | Report C |
| `tpi:meminfo` | SA_NOT_IMP | no | reserved | Report C |
| `tpi:noautolf` | PRN_FLAG | no | — | `SEND_MSG` |
| `tpi:noautopg` | PRN_FLAG | no | — | `SEND_MSG` |
| `tpi:opprint` | PRN_OPEN | yes | — | `SEND_MSG` |
| `tpi:prnsz` | PRN_SIZE | no | `CODE cols,lines`, or `tpi:prnsz cols lines` | `SEND_MSG` |
| `tpi:stop` | SA_NOT_IMP | no | reserved | Report C |

Words the ROM handles itself and never sends — `tpi:tape`, `tpi:sdcard`,
`tpi:picopt`, `tpi:ts2040` — set bits of TPMODE (5DDBh;
[../rom/sysvars.md](../rom/sysvars.md)). Sent raw by machine code they are
"Unrecognized command" ([PROTOCOL.md §5.2](../../PROTOCOL.md#52-the-body)).
`LOAD "tpi:name"` is not in the table: `PROCESS_CMD` sends it to
`LOAD_TPI` ([tspico-files.md](tspico-files.md)).

[`commands_hosttest.py`](../../../src/test/commands_hosttest.py) runs
the production `NEW_TAP`, `RM` and `MEMBOOT` against a temporary card and
`config.ini`;
[`boot_slot_guard_hosttest.py`](../../../src/test/boot_slot_guard_hosttest.py)
pins `MEMDOCK` and `BLKRCV`'s refusal of the booted slot;
[`catalog_hosttest.py`](../../../src/test/catalog_hosttest.py) the
listings `DIR` sends.

## The handlers

### `DIR(pre, cmd)`

`tpi:dir`: the current folder.

| Form | What it does |
|---|---|
| no `CODE`, no argument | `LISTING_CHECK()` — one mount (~0.2 s) to see that the card is still the one listed and the folder unchanged ([tspico-bus.md](tspico-bus.md#listing_check)) — then `SEND_MSG2(CAT_COLOUR(lista), 1, False, True)`: the cached listing in CAT's colours. No card: `NO_CARD_REPLY`, Report J |
| no `CODE`, `tpi:dir arg` | `CATALOG(arg)`: exactly `CAT "arg"` — another folder, a pattern, a TAP's contents ([tspico-disk.md](tspico-disk.md#catalogarg)) |
| `CODE 1,n` | `SEND_MSG("Path: <folder>", "File: <name>", 1, True)`: file `n`'s full name, shown |
| `CODE 2,n` | every file from `n` on, numbered, full names, one to a line: a blue bar with the path, a cyan title row with the count, each number on a cyan chip; `SEND_MSG2(…, 1, True, True)` |
| anything else | `BAD_CODE`, Report A |

`CODE 1,n` and `CODE 2,n` with `n` at or past the number of files: "File
index n out of range 0-N", Report 6, where N is the number of files. The
user manual's example says `File index 12 out of range 0-11` for twelve
files; the code prints `0-12`, one past the last index.

The `CODE 1`/`CODE 2` forms work from the cached `files` list and do not
look at the card; only the plain form checks it. The full names are sent
raw: `SEND_MSG` and `SEND_MSG2` turn anything unprintable into `?`, but `|`
and `~` print as STICK and FREE there, where the plain listing (built
through `catalog.screen_name`, as `xstr` is) shows `?`. The LED is on while the listing goes out.
State read: `files`, `lista`, `TSP.cur_path`. Changes nothing but the
listing caches, through `LISTING_CHECK`.

### `IDIR(pre, cmd)`

`tpi:idir`: pick a file of the current folder from a menu and mount it.
With no files: "Directory is empty:" and the path, shown, 0 OK.
Otherwise every name of `files` becomes `"%03d " + shorten_filename(xstr(name), 26)`
and `ListMenu(List, "Path:<path>", "   #  File Name", …, "Mount file",
"Mounting: ")` runs ([tspico-messages.md](tspico-messages.md#listmenulist-hdr1-hdr2-hdr3-action-chosen-foldersfalse)).
A choice is mounted with `MOUNT_FILE(cur_path + "/" + name)`
([tspico-files.md](tspico-files.md#mount_filef_name-remountingfalse)) after
the menu has ended, so the result cannot be reported to the 2068: a
failed mount reaches only the log ("Can't set or show error now", the
comment). LED on throughout. `files` holds only the indexed types — the ones `LOAD
"tpi:n"` counts ([tspico-files.md](tspico-files.md#list_dir_files)) — so the
menu offers only those.

### `PATH(pre, cmd)`

`tpi:path`: `CODE 0,0` (or none) shows "Current working dir is:" and
`public_path()`, the folder as the user sees it (`/` is the card's `TAP`
folder). `CODE 1,0`: "Current mounted file is:" and `public_fname()`, or
"No file mounted!". All shown, 0 OK. Any other `CODE`: `BAD_CODE`, A.
No card needed: the path is `TSP.cur_path`, the name `TSP.f_name`.

### `TAPDIR(pre, cmd)`

`tpi:tapdir`: the blocks of the mounted TAP, around the tape pointer.
Works from `TSP.offset_tbl` (built by `OFF_TABLE` at mount time) and does
not touch the card.

Nothing mounted, or a mounted file that is not a `.tap` (`isTapMounted`):
the one row ` --  No .TAP file mounted!  -- `, logged, 0 OK.

Otherwise, four header rows — `File:` and the name (27 wide), `Pointer at
block: NN, Append:on`/`off`, the column titles, 32 dashes — and then the
rows, chosen by `CODE v,n`:

| `n` | Rows |
|---|---|
| 0 | every block |
| 1–254 | the pointer's block and `(v+1)·n` blocks either side |
| 255 | a screenful: from `(v+1)·8` blocks before the pointer to `(v+1)·17` blocks after that |

| `v` | View | Row |
|---|---|---|
| 0 | every block | `>` at the pointer, else a space; then `NN offset  len Y/N  name` (`"%02d %6s  %5s %s  %-10s"` of the `offset_tbl` entry) |
| 1 | one line per file | `catalog.tap_header_rows` — the headers, and the pointer's block if it is a data block ([catalog.md](catalog.md#tap_header_rowstbl-cur_idxnone-idx10-idx2none-orphansfalse)) |
| other | — | `BAD_CODE`, Report A, sent before any listing |

An empty table gives `<empty file>`. The text goes through
`TAPDIR_COLOUR(text, v == 1)` and `SEND_MSG2(…, 1, True, True)`. The
window arithmetic for `v = 1` counts blocks, not files, so `CODE 1,3`
scans eight blocks each side and shows the headers among them; that is
the comment's "n headers" only for a tape of header/data pairs.
`FWD` and `REW` chain here with `CODE 0,255` or `CODE 1,255`.

### `NEW_TAP(pre, cmd)`

`tpi:newtap name`: make an empty `name.tap` in the current folder, mount
it, and switch append on — the start of a new tape to SAVE into.

1. No argument: "Name required for new .tap file", shown, Report F.
2. A trailing `.tap` is dropped: the text from the **first** dot must be
   exactly `.tap` (any case), so `a.b.tap` becomes `a.b.tap.tap`. Spaces
   at the ends are stripped.
3. A name with a character below space, `DEL` or above, or any of
   `:*\/|"<>`: 'Filename "x" not allowed', Report F.
4. `SD_CALL(make)`: if a file or folder of that name exists (any case:
   FAT), "File exists:", Report F, and the existing file is left alone
   (it used to be emptied; `commands_hosttest.py` pins the refusal, and
   `FORMAT` refuses too); otherwise an empty file is created and the folder
   re-listed (`DIR_FILES`). An SD error is reported as "Can't create new
   file:", Report F; no card, as `SD_CALL` says it (J).
5. `MOUNT_FILE(path)`. Success: `TSP.append = True`, "New .tap file
   mounted:" and the name, 0 OK. Failure: "Failed to mount new .tap file:",
   Report Q.

The answers are `SEND_MSG`, not shown with VERBOSE off. `FORMAT "x.tap"`
does the same through `DISK_NEW_TAP` ([tspico-disk.md](tspico-disk.md#disk_formatpre-cmd)).
State: the card, `files`/`lista`, the mount (`TSP.f_name`, `offset_tbl`,
`/TMP/temp.tap`), `TSP.append`.

### `SA_NOT_IMP(pre, cmd)`

The seven reserved words — `tpi:config`, `tpi:delete`, `tpi:freset`,
`tpi:getconfig`, `tpi:list`, `tpi:meminfo`, `tpi:stop` — answer "CMD OK,
but not yet implemented", Report C, not shown with VERBOSE off. They are
in the table, and in `SD_FREE`, so that the words are reserved: an
external command cannot take them (`SA_funct` is looked up first) and no
card is looked for. User manual §10.4 lists them.

### `APPEND(pre, cmd)`

`tpi:append`: whether a SAVE goes onto the end of the mounted TAP
(`TSP.append`) instead of into a new file.

| Form | Result |
|---|---|
| none (`CODE 0,0`) | "Append is ON"/"OFF", or "No .tap mounted"; shown, 0 OK |
| `CODE 1,1` (any non-zero), `on` | a TAP mounted: append on, "Append new files to:" and the name, 0 OK. None: "No .tap mounted. Append failed.", Report Q |
| `CODE 1,0`, `off` | append off, "Append is OFF", 0 OK |
| another word | `BAD_ARG`, Report A |
| another `CODE` | `BAD_CODE`, Report A |

A word argument overrides any `CODE` (`par1` is forced to 1). Only the
show form is shown with VERBOSE off. Append is turned off again by every
mount (`MOUNT_FILE`), `FORGET_MOUNT` and a different card
(`SD_REVALIDATE`); `NEW_TAP` and `FORMAT "x.tap"` turn it on. `SAVE_TS`
reads it ([tspico_io.md](tspico_io.md#save_tsmq-tsp-prenone)).

### `BLKRCV(pre, cmd)`

`tpi:blkrcv`: stream the mounted ROM or cartridge image to the Z80, which
writes it into a flash or SRAM slot. Sent by the updater programs
`romupdate.bas` and `dckupdate.bas` (line 280), which `MOUNT_FILE` serves
in place of a `.ROM`, `.BIN` or `.DCK` file: mounting the image copies it
to `/TMP/temp.bin` and mounts the updater tape instead
([tspico-files.md](tspico-files.md#mount_filef_name-remountingfalse);
user manual §8.4).

1. **An image must be mounted.** Unless `TSP.f_name` ends in `.DCK`,
   `.BIN` or `.ROM` (nothing mounted, a TAP, any other file), answer "No
   ROM image mounted" / "Mount a .ROM, .BIN or .DCK", shown, Report F, and
   stop. Neither branch below would send a byte for any other file, so the
   ROM would read the tail's pre-load `01h` as "0 OK" and the updater
   would go on to erase the slot; the refusal stops it at line 280, before
   the erase (#162, #163; [`boot_slot_guard_hosttest.py`](../../../src/test/boot_slot_guard_hosttest.py)).
2. **The boot-slot guard.** `getDock()` is the slot the updater will
   write (the DOCK slot it chose with `tpi:dock`); if
   `BOOT_SLOT_CLASH(mem, page, TSP.f_name)` says it is the slot the 2068
   is running from (for a `.DCK`, either of its two 32K slots), answer
   "Can't write Flash slot N:" / "the 2068 is running from it. Boot
   another slot first.", shown, Report Q, and stop: nothing streamed,
   nothing erased. `MEMDOCK` normally refused the slot already; this is
   the second check ([`boot_slot_guard_hosttest.py`](../../../src/test/boot_slot_guard_hosttest.py)).
3. **The image file.** `/TMP/temp.bin` must exist and, for a `.DCK`, be
   at least 65 536 bytes (`DCK_IMAGE` always writes a full 64K image).
   Otherwise "The ROM image isn't ready" / "Mount the file again", shown,
   Report F, and stop. This comes before any status because once the Z80
   has "0 OK" it erases the slot and reads blind: nothing found wrong after
   that can be reported, and an empty FIFO goes into the flash as `00h`s
   (#164).
4. **`.DCK`**: `/TMP/temp.bin` opened, then status 1 into TX (`MQ.put`),
   `MQ_READY()`, and its 65 536 bytes. An error opening it raises before
   the status, so `FAIL_CMD` answers J and nothing is erased.
5. **`.BIN`/`.ROM`**: `CODE len,offset`. If `len + offset` is past the
   end of `/TMP/temp.bin`, status 3 (Report F) after a one-second
   `BLINK_ERROR`, and nothing more. Otherwise status 1, `MQ_READY()`, and
   `len` bytes from `offset` (`len` 0: to the end of the file).
6. LED on for the transfer, off in a `finally`.

**The stream.** The updater's BASIC prints, erases the slot (`USR
32800`/`32600`) and only then runs its write loop (`USR 32870`/`32670`),
which reads port 0Eh with interrupts off and **no ready check**, one byte
every ~33 µs (117 T-states), until it has the whole image. So the bytes
are queued long before anything reads them, and must then never run dry:
an empty FIFO reads as `00h`, and that `00h` goes into the flash.

- **By DMA** (`tspico_io._DMA` is not `None` and the whole image fits in
  RAM after a `gc.collect()` — a `.DCK` is 64K, v1.29 has about 180K
  free): the file is read into one buffer and sent with
  `STREAM_DMA(MQ, data, _CMD_ECHO, 3000, False, CMD_STALL_MS)` — up to
  `CMD_STALL_MS` for the first read (the erase takes seconds), then 3 s,
  since the write loop never pauses. A BREAK or SYNC (code 1) or a stall
  (code 3) raises `CmdAbort`. The channel starts at once, seconds before
  the loop reads; there is no gate (below), because starting the stream
  late cost ten empty reads — ten `00h`s in the flash (hardware,
  2026-10-03).
- **No channel free, image in RAM**: the first `GATE` = 8 bytes through
  `CMD_PUT`, the rest with `MQ.put`.
- **No DMA**: the file is read 256 bytes at a time into one buffer; the
  first 8 bytes through `CMD_PUT`, then `MQ.put` byte by byte.

Why the gate: if BASIC never reaches the write loop — BREAK during the
PRINTs or the erase, or an error — nothing ever reads, and a plain
`MQ.put()` on the full FIFO blocked for ever: the Pico deaf even to the
next command's SYNC until a power cycle (2026-09-30 audit; #69 had moved
every other output path to `CMD_PUT` but not this one). Eight bytes is
more than the 4-deep FIFO and the status byte, so once they are in, the
Z80's loop is running and will read to the end; from there the fast
`put()` is kept, because `CMD_PUT`'s check on every byte would eat into
the 33 µs. A 2068 reset in the middle of the write loop still leaves the
Pico in `put()` on the non-DMA paths — and a half-written slot, which
needs a power cycle anyway (the comment at 3985–4010).

Beware:

- The status still goes out before the stream, so a read error part way
  through (after the checks above) cannot reach the 2068: it is raised,
  `PROCESS_CMD` logs it and `FAIL_CMD` answers J, and the 2068, already in
  its write loop, takes that status byte as data and then reads an empty
  FIFO for the rest *(inferred)*. The slot is half-written either way. Before #164 the `.DCK` path also sent the status
  before opening the file, and only printed an error opening it.
- The status and the stream use `MQ.put` directly; at this point TX is
  empty (the command body has just been read), so the first `put`s cannot
  block.

### `CDIR(pre, cmd)`

`tpi:cd`: change the current folder. ROM 2.1's `MOVE TO "x"` arrives as
`tpi:cd x` and `MOVE TO ""` as `tpi:cd -`
([../rom/exrom-fdd.md](../rom/exrom-fdd.md)).

**With a name** (`getArgs`, as typed): `ChangeDir(name)` does the work and
the card access — `..`, `/`, `-` (back to the previous folder), paths
relative or from `/`, never above the card's `TAP` folder
([tspico-files.md](tspico-files.md#changedirpotential_new_path-sdactivefalse)).
It returns `(status, message)`. Then:

| `CODE` | After a successful change |
|---|---|
| none, `0,x` | `SEND_MSG(message, "Current: <path>", 1)`, not shown |
| `1,0` | the new folder's listing: `SEND_MSG2(CAT_COLOUR(lista), 1, False, True)` |
| `1,1` | `IDIR` (with a blank `pre`): pick a file to mount |
| `1,2` | `DIR` with `CODE 2,0`: the full names |
| `2,0` | the message, shown |
| `1,3` and above, any other | the message, not shown |

A failed change (status F, "OS error changing to:", or Q) always gets the
message with its status, not shown unless `CODE 2,0`. No `CODE` value is
refused: an unknown one behaves like none.

**Without a name**: a menu of folders through `ListMenu` with
`folders=True` — the folders of the current folder (`dirs`), with `..` in
front unless the current folder is the top (`public_path` is `/TAP`); or,
with any non-zero second `CODE` number (`CODE 0,1` in the manual), every
folder on the card (`alldirs`, built by `GET_DIRS` at mount time and
updated by `MDIR`). A choice goes to `ChangeDir` after the menu has ended,
so its result is not reported. `par1` is ignored here. LED on during the
menu.

State: through `ChangeDir`, `TSP.cur_path`, `prev_path`, the listing
caches, MicroPython's current directory. Needs the card (the gate), and
`ChangeDir` mounts it; an `ACTIVATE_SD` failure there propagates to
`FAIL_CMD` (Report J).

Beware: the empty-list guard of `ListMenu` covers a folder with no
subfolders at the top ("(no items available)"); elsewhere the list always
has `..`. The `CODE 1,1` and `1,2` chains pass `cmd` on, which `IDIR`
ignores and `DIR` reads only for an argument — `DIR`'s `getArgs(cmd)` is
the folder name, but with `par1 = 2` the argument is not used.

### `FWD(pre, cmd)`

`tpi:ffw`: move the tape pointer forward. `n` is the second `CODE`
number, at least 1.

| `CODE` | Move |
|---|---|
| `0,n` or none | `n` blocks |
| `1,n` | `n` blocks, then `TAPDIR` with `CODE 0,255` |
| `2,n` | `n` files |
| `3,n` | `n` files, then `TAPDIR` with `CODE 1,255` |
| `4,x` and above | `BAD_CODE`, Report A |

- Nothing (or not a `.tap`) mounted: "No .tap file mounted", 0 OK, logged.
- The pointer on the last block already: "Can't FWD. Already at end.",
  0 OK.
- **By blocks**: `tap_idx += n`, clamped to the last block. The pointer
  can stand on the last block but never past it.
- **By files**: the `n`-th header block after the pointer, a header being
  a block whose `offset_tbl` entry has `Y` in its "header?" column. The
  scan stops before the last block (which, being last, has no data block
  and is never a file's start). Fewer than `n` headers found: the last one
  found; none, and the pointer was on a header: it stays; none, and it was
  not: the last block.
- After a move: `TSP.offset` = the new block's offset, `gc.collect()`,
  "Moved ahead to block # i" (logged at 0), and either the `TAPDIR`
  listing or `SEND_MSG(msg, "", 1)`, not shown.

The next `LOAD ""` starts at the pointer (`LOAD_TS` serves `offset_tbl`
from `tap_idx`; [tspico_io.md](tspico_io.md#load_tspre-mq-tsp)). Every
answer is 0 OK except a bad `CODE`, including "nothing mounted"; with
VERBOSE off the user sees nothing in either case. No card needed:
`offset_tbl` is in RAM.

### `GETHELP(pre, cmd)`

`tpi:help`: help text, always through `SEND_MSG2` (shown whatever VERBOSE
says), `expandKeywords` off.

- **No argument**: the summary built into the firmware — `LOAD` forms,
  then every `SAVE` command with its `CODE` options, 32-column lines,
  three pages with their own headings — and, if external commands are
  loaded, a list of their words. Status 1. The summary is a literal in
  the code (4437–4490); it must be kept in step with this table by hand.
- **`?`**: the topics: every `*.txt` in `/sd/help` (sorted, without the
  extension, names starting with `.` skipped), packed into 32-column
  lines.
- **A topic**: `/sd/help/<topic>.txt` (the topic lower-cased; the card is
  case-insensitive anyway), read whole, every character but CR and LF
  passed through `catalog.screen_name` — so `| ~ { }` and anything
  non-ASCII show as `?` — while line ends, and the `\*` that `SEND_MSG2`
  turns into ©, are kept. Not there: 'Help for "x" not found', Report F
  (logged as a warning). Unreadable: "Failed to read help file:", Report
  R.
- No `/sd/help` folder: "SD card help folder not found.", Report Q.

With an argument the handler mounts the card itself (`ACTIVATE_SD`, not
in a `try`) and gives it back before answering; the card gate has already
probed for a card, since a topic needs one (`SD_NEEDED`'s special case).
An error in `os.ilistdir` or `ACTIVATE_SD` reaches `FAIL_CMD`, Report J.
The help files are written for the 2068's screen: short lines, CR, LF or
CR LF line ends (the comment at 4359–4361). Error statuses are logged.

### `GETINFO(pre, cmd)`

`tpi:info`: the TS-Pico's state, one screen.

1. `SD_PROBE()` first, so the card is reported as it is now and not as the
   last command left it; a card taken out since shows as gone, a different
   one is read afresh, and the space line is the new card's. One mount,
   ~0.2 s (five tries, once, for a card that has just been pulled).
2. The flash's size and free space from `os.statvfs("")`. The current
   directory is the flash's root at this point: `DEACTIVATE_SD` has just
   unmounted `/sd` *(inferred: MicroPython moves the current directory to
   the root when its filesystem is unmounted)*.
3. The screen, chosen 2026-10-02: a cyan " TS-Pico " badge on a blue strip
   (red when there is no card), " interface status", the © line, then
   label/value rows with the labels in blue:

   | Label | Value |
   |---|---|
   | Firmware | `TSP.FW_VERSION`, and "uPython" with MicroPython's version |
   | ROM | `TSP.ROM_VERSION` (from `config.ini`; not read from the ROM) |
   | Build | `BUILD_FIT(BUILD_VERSION, 22)` |
   | Board | the literal `V2.2`, and the log level |
   | Free RAM | `gc.mem_free()` in kB |
   | Flash | size and free space |
   | SD card | size and free space (`sd_space`, from the last listing), or `none` in red |
   | Boot, Dock | `getBoot()`, `getDock()`: memory (1 SRAM, 2 flash) and slot |
   | Append, Verbose | on/off |
   | Mounted | `public_fname()` or `none` |
   | Block | for a TAP: the pointer's block number, what it is and the name of its file, fitted into 22 columns |
   | Path, Files | `public_path()`, the number of indexed files |

4. `SEND_MSG2(msg, 1, True, True)`.

The Block row: a header block shows its name and the name in the next
block's entry (the data); a data block shows "Data block" (or "Data" when
the name is long) and its own entry. A TAP that ends in a header (an
append cut short) used to raise `IndexError` reading the next entry, and
`tpi:info` gave Report J (2026-09-30 audit); now it says "no data". A
line of 34 characters wrapped "ck" onto a line of its own (the emulator,
`tools/emu`, 2026-10-04); now the name gives way, not the type.

No card needed (`SD_FREE`): it is the command to run when the card is the
problem. `sd_state_hosttest.py`'s `test_info` pins the card lines.

### `GETLOG(pre, cmd)`

`tpi:log`: show or clear `/activity.log`, the log on the Pico's flash
([tspico-files.md](tspico-files.md#save_log)).

| Form | Result |
|---|---|
| none | the whole log, `SEND_MSG2(text, 1)` |
| `CODE 0,n` | the last `n` bytes (the whole log if it is shorter) |
| `clear` | `SEND_MSG_PROMPT_YN("Clear the log file (y/N)?")`; `Y`: `CLEAR_LOG()`, nothing more sent; anything else: nothing done, logged at 0 |
| `clear` `CODE 255,0` | `CLEAR_LOG()` with no question; "Log file was cleared", 0 OK |
| (any form that shows the log) with no `/activity.log`, or an empty one | "The log is empty", 0 OK |
| another word | `BAD_ARG`, Report A |
| `CODE a,b`, `a` not 0 (without `clear`) | `BAD_CODE`, Report A |

`CLEAR_LOG` failing: with `CODE 255,0`, "Couldn't clear log file", Report Q
(before #165's fix the `CODE` check below overwrote it with "LOG: Bad CODE
255,0", Report A). After the Y/N prompt, nothing: the prompt was the
whole answer (function 86h ends the exchange once the key is back), so a
message then would sit unread in TX; `CLEAR_LOG` has logged the failure
(#165).

No log: a fresh flash has no `/activity.log` until the first `LOG()` at or
above `LOG_LEVEL`. `os.stat` failing, or a size of 0, answers "The log is
empty" before the LED goes on; before #166 the `OSError` reached
`FAIL_CMD`, Report J.

Reading: the requested part is read into one `bytearray` and decoded as
UTF-8. The log is trimmed to 64 KB only at boot, so in a long session it
can outgrow the heap: `MemoryError` gives "Log file too large", Report Q
(use `CODE 0,n`); any other read error (a damaged log, a seek into the
middle of a UTF-8 sequence) "Couldn't read the log file", Report Q,
logged. The buffer is dropped before `SEND_MSG2` builds its pages. LED on,
off in a `finally`.

Why the `try` covers only the read (the comment at 4710–4728; 2026-09-30
audit): it was a bare `except:` around the read **and** `SEND_MSG2`. A
BREAK at the "Scroll?" prompt raises `CmdAbort`, a `BaseException`, which
a bare `except:` catches: `GETLOG` ate the BREAK and then sent "Log file
too large" to a 2068 that had stopped listening. Now `CmdAbort` passes
through to `PROCESS_CMD` ([`audit_fixes_hosttest.py`](../../../src/test/audit_fixes_hosttest.py)).

Beware:

- A failed clear after `Y` is in the log only; the 2068 shows nothing.
- No card needed: the log is on the flash.

### `LOGLEVEL(pre, cmd)`

`tpi:loglevel`: show or set `TSP.LOG_LEVEL`, the lowest level `LOG` keeps
([tspico-files.md](tspico-files.md#logmsg-level)).

- None: "LOG level is n LABEL" (`LOG_LABELS`: INFO, WARNING, ERROR,
  CRITICAL, SPECIAL for 0–4), shown, 0 OK.
- `CODE 1,n` or `tpi:loglevel n` (a word argument forces `par1 = 1`;
  not a number: `BAD_ARG`, A): `n` above 4 is "Bad log level: n",
  Report A; otherwise set, "LOG level set to n LABEL", 0 OK.
- Another `CODE`: `BAD_CODE`, A.

The setting is not written to `config.ini`: it lasts until power-off
(`LOAD_CONFIG` reads the boot value; [tspico-dispatch.md](tspico-dispatch.md#load_config)).
Level 4 (SPECIAL) keeps only what is logged at 4.

### `MDIR(pre, cmd)`

`tpi:md name`: make a folder in the current one. `name` is `cmd[10:]`,
everything after `tpi:md ` exactly as typed (one space is assumed; a
second becomes part of the name). No validation of the characters: the
card's filesystem refuses what FAT cannot hold, as `OSError`.

1. No name: "MD: Filename required", Report A.
2. `ACTIVATE_SD()` (not in a `try`), `os.chdir(TSP.cur_path)`.
3. A folder of that name exists: 'MD: directory "x" exists', **Report 8**
   (`_7_8_EOF`) — so that `CODE 1,0` can still go into it (below). A file:
   'MD: file "x" exists', Report F.
4. Otherwise `os.mkdir(name)`; the listing is re-read (`DIR_FILES`)
   unless `CODE 1,0` (the change of folder re-reads it); `alldirs` gets the
   new path (`cur_path` without `/sd`, plus the name) and is sorted, without
   walking the card again. `OSError`: "MD: OS error creating:", Report Q.
5. `DEACTIVATE_SD()`, `ACTIVATE_MQ()`.
6. With `CODE 1,0`, and the folder made or already there: `CDIR` with
   `CODE 2,0` — the change, and its message shown. Otherwise
   `SEND_MSG(message, name, status)` ("Created dir: " and the name, not
   shown).

The manual's reports for `tpi:md` (8, F, A) match the code.

### `MEMBOOT(pre, cmd)`

`tpi:boot` (and `tpi:memboot`): which ROM the 2068 runs — the BOOT
memory (1 SRAM, 2 flash) and slot (0–15). The two settings live in
`TSP.ROM_SM` bits 0–1 and `TSP.bank_sm` bits 0–3, the words the `set_ctrl`
and `sel_bank` state machines take ([pio.md](pio.md#set_ctrl),
[tspico-state.md](tspico-state.md#pico_status__init__self-init_values)).

- None: "BOOT is MEM=m, PAGE=s" (`getBoot()`), shown, 0 OK.
- `CODE 0,s` (s ≠ 0), `CODE m,x` with m > 2, or a slot above 15: "Wrong
  values, MEM=…, PAGE=…" / "OK values: MEM=1..2, PAGE=0..15", Report A,
  logged; nothing changes.
- `CODE m,s`:
  1. `ROM_SM`'s low two bits become `m`, `bank_sm`'s low nibble `s`.
  2. `config.ini` is read, `ROM_SLOT = s` and `ROM_SM`'s low bits = `m`
     (the DOCK bits as the file has them, default 10), and written back.
     `LOAD_CONFIG` at the next power-on uses that boot setting **once** and
     puts flash slot 1 back ([tspico-dispatch.md](tspico-dispatch.md#load_config)):
     a ROM that hangs the 2068 can be escaped by a power cycle.
  3. "Change ROM to MEM=m, PAGE=s", `SEND_MSG` (not shown), logged.
  4. 0.1 s sleep, then `ROM.put(TSP.ROM_SM)` and `BANK.put(TSP.bank_sm)`:
     the ROM changes under the running 2068 at once. `SEND_MSG` has only
     waited for TX to empty; the Z80 is still finishing the statement in
     the old ROM. The sleep is kept (audit §4) because nothing measured
     says it can go. The manual's advice — follow it with `NEW` or a reset
     — is because the 2068 is now running code it did not start in.

`config.ini` is opened by the relative name `"config.ini"`; this relies on
the current directory being the flash root, as it is after any SD access
*(inferred, as for `GETINFO`)*. A failure to write it raises and reaches
`FAIL_CMD` (Report J) — after `TSP` has changed but before the ROM switch.
`commands_hosttest.py` pins that both halves are saved, that `LOAD_CONFIG`
uses them once, and that MEM 3 is refused. The single-port code's
`WAIT_TX_RECEIVED()` after the switch is left commented out.

Beware: never boot a slot that has not been written since power-on (SRAM
is empty at power-on), and never rewrite the slot you booted from
(`BLKRCV`'s and `MEMDOCK`'s guard: on 2026-09-28 a test ROM booted
from flash slot 4 was told to rewrite slot 4, and both machines hung with
the slot half-written).

### `MEMDOCK(pre, cmd)`

`tpi:dock` (and `tpi:memdock`): what appears in the 2068's DOCK
(cartridge) bank — memory in `ROM_SM` bits 2–3, slot in `bank_sm` bits
4–7. Not saved in `config.ini`: it lasts until power-off.

| `CODE` | Result |
|---|---|
| none | "DOCK is MEM=m, PAGE=s", shown, 0 OK |
| `0,1` | "DOCK was previously:" and `TSP.dck_prev_mem`/`dck_prev_slot`, shown, 0 OK |
| `0,2` | swap to the previous setting (as `CODE prev_mem,prev_slot` below), message "Swapped with previous setting" |
| `0,3`…`0,15` | `BAD_CODE`, Report A |
| `m,s` (m 1–2) | change, below |
| `m` > 2 or `s` > 15 | "Wrong values, …", Report A |

The change: `BOOT_SLOT_CLASH(m, s, TSP.f_name)` — with a ROM or DCK image
mounted, this is the updater choosing the slot it is about to erase, and
the booted slot is refused: "Can't write Flash slot N:" / "the 2068 is
running from it. Boot another slot first.", shown, Report Q, nothing
changed ([tspico-files.md](tspico-files.md#boot_slot_clashmem-page-f_name)).
Otherwise the old setting becomes the previous one, the new is written
into `ROM_SM`/`bank_sm`, "Change DOCK to MEM=…, PAGE=…" is sent (not
shown), and `ROM.put`, `BANK.put` switch the bank at once.

Beware: on the swap, the message is built from the `CODE` before the swap,
so it reads "Change DOCK to MEM=0, PAGE=2" rather than the setting swapped
to; the swap itself is right. `CODE 0,0`'s show form is reached only after
the range check, so `CODE 0,16` is "Wrong values", not a show.
[`boot_slot_guard_hosttest.py`](../../../src/test/boot_slot_guard_hosttest.py)
pins the refusal before the DOCK moves or a byte is streamed, and that
another slot, the other memory, plain DOCK use with nothing mounted and a
`.DCK` spanning slots n and n+1 still go through.

### `REW(pre, cmd)`

`tpi:rew`: as `FWD`, backwards — the same `CODE` table and messages ("No
.tap file mounted", "Can't REW. Already at start." when the pointer is on
block 0, "Moved back to block # i"), and the same chaining to `TAPDIR`.
By blocks: `tap_idx -= n`, clamped to 0. By files: the `n`-th header
block before the pointer, counting the pointer's own block if it is a
header; fewer found than asked, the last (earliest) found; none, block 0 —
or, if the pointer is on a header, it stays.
So `CODE 2,1` on a data block goes back to its own header, and on a
header to the header before it. Every answer but a bad `CODE` is 0 OK.

### `BAD_CODE(command, par1, par2)`

Returns `"COMMAND: Bad CODE a,b"`. The message every handler here gives
with Report A for a `CODE` it does not take. Callers: `DIR`, `PATH`,
`TAPDIR`, `APPEND`, `FWD` (as "FFW"), `GETLOG` (as "LOG"), `LOGLEVEL`,
`MEMDOCK` (as "DOCK"), `REW`, `RM`, `VERB_TOGGLE` (as "VERBOSE"), `ZX48`.

### `BAD_ARG(command, arg)`

Returns `"COMMAND: Bad argument: arg"`, for a word argument a handler does
not take (`APPEND`, `GETLOG`, `LOGLEVEL`, `VERB_TOGGLE`), Report A.

### `RM(pre, cmd)`

`tpi:rm name`: remove a file of any kind, or an empty folder. `name` is a
name in the current folder, a path (relative, or from `/`, the card's
`TAP` folder), or a number from the listing (`ResolveIndexName`;
[tspico-files.md](tspico-files.md#resolveindexnamename)).

1. No name: "RM: Filename required", Report A. A `CODE` other than none or
   `255,0`: `BAD_CODE`, A.
2. `SD_CALL(RM_CHECK, name)`: "file" or "dir", or a refusal with its
   status, which is sent (not shown) and logged. All the refusals come
   **before** the question, so the user is never asked about something
   that cannot be removed.
3. No `CODE`: `SEND_MSG_PROMPT_YN('Remove "name" (y/N)?')`. `Y`: 
   `SD_CALL(DISK_ERASE_ONE, name)` — the same removal as `ERASE`
   ([tspico-disk.md](tspico-disk.md#disk_erase_onearg)) — with the result
   only logged, since the question was the answer. Anything else: logged
   at 0, nothing removed.
4. `CODE 255,0`: the removal at once, and its message sent with its status.

A folder's name gets a `/` before `DISK_ERASE_ONE`, which removes only an
empty one ("Directory not empty", Q). `REMOVE_DIR`, the recursive removal
in the same file, is not used by `RM`. [`commands_hosttest.py`](../../../src/test/commands_hosttest.py)
pins all of this.

### `RM_CHECK(name)`

`RM`'s checks, run inside `SD_CALL` (the card is mounted). Returns
`("file", 1)`, `("dir", 1)` or `(message, status)`:

- `catalog.resolve` gives nothing (a path above the top) or the top
  itself: "RM: Not found: name", F;
- a folder that contains the current folder (`catalog.within`): "RM:
  Can't remove the current directory", Q;
- not a file either: "RM: Not found", F;
- the mounted file (compared upper-cased): "RM: File is mounted;
  tpi:close it first", Q.

### `UNMOUNT(pre, cmd)`

`tpi:close`: "Unmounting file.", `SEND_MSG`, 0 OK, always; then
`FORGET_MOUNT()`: `TSP.f_name = ""`, the block table emptied, pointer and
offset 0, append off, `/TMP/temp.bin` and `/TMP/temp.tap` removed from the
flash ([tspico-files.md](tspico-files.md#forget_mount)). The answer goes
first, so the flash work happens while the 2068 carries on. With nothing
mounted it does the same, harmlessly. No card needed. After it,
`LOAD ""` serves the built-in "no file" tape (user manual §3.7).

### `VERB_TOGGLE(pre, cmd)`

`tpi:verbose`: show or set `TSP.VERBOSE`, which makes `SEND_MSG` print its
messages ([tspico-messages.md](tspico-messages.md#send_msgmsg-msg1-st-forcedisplayfalse)).
None: "Verbose is enabled"/"disabled", shown. `CODE 1,n` or `on`/`off`
(a word forces `par1 = 1`; another word is `BAD_ARG`, A): set (any
non-zero `n` is on), "Verbose is now enabled"/"disabled", 0 OK, not
shown — but the new setting already applies, so turning it on shows the
message and turning it off does not. Another `CODE`: `BAD_CODE`, A. Not
saved: at power-on `VERBOSE` comes from `config.ini`.

### `ZX48(pre, cmd)`

`tpi:zx48`: switch the TS-Pico into ZX Spectrum mode. It sets
`TSP.zx48 = True` and answers; the switch itself happens after
`PROCESS_CMD` returns, when the dispatcher sees the flag and runs
`ZX48_IO(pre)` with this command's pre-header
([tspico-dispatch.md](tspico-dispatch.md#zx48_iopre); user manual ch 9;
[the flow](../flows/zx48.md)).

`CODE a,b`:

- `a` 0: the message is shown; 1: not shown (VERBOSE decides); above 1:
  `BAD_CODE`, Report A, and the mode is not entered.
- `b` 0: keep the current loader (`TSP.ZX_TAPE_COMPAT`, from `config.ini`
  at power-on); 1: the normal loader (`LOAD_ZX`); 2 or more: the
  compatible loader (`LOAD_ZX_C`, the whole tape in RAM). A `b` of 16384 or
  more is also its buffer size: `ZX48_IO` reads it from the same
  pre-header (default 52 100 bytes).

The message: "Changing TS-Pico to ZX48 mode.", the loader in use (and the
buffer size), then five lines on how to switch ROMs: `OUT 244,3` for the
Spectrum ROM; `OUT 244,0` then `OUT 14,14` to come back. Each line has its
own CR: the five were once joined relying on each being exactly 32
characters, and two were not ("OUT 14,14to exit"). 0 OK.

`TSP.ZX_TAPE_COMPAT` set here lasts until power-off.

### `NOP(pre, cmd)`

`tpi:nop`: `MQ.put(0x01)`, `MQ_READY()`: 0 OK, whatever VERBOSE says, and
nothing else — the cheapest complete command, used to test that the link
works ("This is to test Ryan's new Commander", the table's comment). The
single-port version put `40h` (the continue flag) before the `01h`; a
`40h` in TX now would be read as data.

## The printer settings

The virtual printer itself — `PRT`, the `TextCapture` that collects
LPRINT/LLIST text, `PRINT_FLUSH`, `COPY_BMP` — is in
[printer.md](printer.md) and [tspico-dispatch.md](tspico-dispatch.md).
These five handlers change its settings. None is saved: all last until
power-off.

### `PRN_OPEN(pre, cmd)`

`tpi:opprint`: close any capture and start the next numbered file.
`PRINT_FLUSH()` writes out what is buffered; then, with the card,
`next_name(VLPRINT, "PRN", "TXT")` picks the next free
`/VLPRINT/PRNnnnn.TXT` and an empty file is created there; `prn_path`
holds it. Any error: `prn_path = None`, "Printer capture: SD error",
Report F, logged. The column and line counters are reset. "Printer
capture: /VLPRINT/PRNnnnn.TXT", 0 OK, not shown. Needs the card.

### `PRN_CLOSE(pre, cmd)`

`tpi:clprint`: `PRINT_FLUSH()`, then `prn_path = None` and the counters
reset; "Printer capture closed: …" or "No printer capture open", 0 OK.
The next character printed opens a new file. In the gate's list of
commands that need the card, because `PRINT_FLUSH` may write.

### `PRN_FLAG(pre, cmd)`

`tpi:autolf`, `tpi:noautolf`, `tpi:autopg`, `tpi:noautopg`: one handler
for four words. The word (`cmd[7:]` to its first space, upper-cased)
starting with `NO` means off; ending in `AUTOLF` sets `PRT.autolf` (ENTER
becomes CR LF instead of LF), otherwise `PRT.autopg` (a form feed every
`PRT.lines` lines). "Printer: CR+LF line ends on/off" or "Printer: paging
every n lines on/off", 0 OK.

### `PRN_SIZE(pre, cmd)`

`tpi:prnsz`: the page, `PRT.cols` (wrap column, 0 = never) and `PRT.lines`
(lines per page for AUTOPG). `CODE cols,lines`, or the words
`tpi:prnsz cols lines` (a comma works too; one number keeps the lines).
Both 0 (or no parameters): report only. A value outside 0–255 or a word
that is not a number: "Printer size: bad parameters", Report Q.
Otherwise "Printer size: c columns, l lines", 0 OK. Note that `CODE 0,0`
cannot set "never wrap" with 0 lines; `CODE 0,n` can.

### `PRN_BMP(pre, cmd)`

`tpi:bmp`: the size of the picture `COPY` saves, `bmp_size`
([tspico-state.md](tspico-state.md#bmp_size)). `CODE x,y` with `x` one of
256, 512, 1024, 2048, 4096 (the larger for hi-res screens, which are 512
wide) and `y` one of 192, 384, 768, 1536; `y = 1596` is taken as 1536,
"as printed in the manual". Anything else: "BMP size: use 256-4096 x
192-1536", Report Q. No parameters: report only. "COPY picture: WxH",
0 OK. `x` and `y` are independent, so a stretched picture is allowed.

## Where the user manual and the code differ

The code is right by definition; these are for the manual's next edit.

- `tpi:dir CODE 1,n`/`2,n` out of range: the manual shows "0-11" for
  twelve files; the code prints "0-12".
- `tpi:dock CODE 0,2`: the manual does not show the message, which names
  the wrong setting (see `MEMDOCK`).
- `tpi:cd`: the manual lists only F for a failed change; a path given as
  `/tap/x` that does not exist is Q (`ChangeDir`).
- `tpi:boot`: the manual says MEM must be 1 or 2; `CODE 0,s` with `s` ≠ 0
  is also refused (and `CODE 0,0` is the show form).
- `tpi:ffw`/`tpi:rew`/`tpi:append` with nothing mounted answer 0 OK (the
  messages show only with VERBOSE on), except `tpi:append on`, which is Q.

And in the code's own comments:

- The comment above `SA_funct` (6167–6168) about a trailing space in the
  keys of commands that take a name: no key has one.
- `TAPDIR`'s header comment says `CODE 1,n` shows `n` headers either side;
  the window is counted in blocks.
