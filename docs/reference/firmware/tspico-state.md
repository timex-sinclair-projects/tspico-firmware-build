# TS/tspico.py (part 1) — module constants, globals, the caches, `PICO_STATUS`, telemetry

Source: [`src/TS/tspico.py`](../../../src/TS/tspico.py)

This part covers the state that `tspico.py` keeps at module level: the
constants at the top of the file, the constants defined further down next to
the code that uses them, the globals that functions create at run time with a
`global` declaration, the `PICO_STATUS` object that holds the TS-Pico's
settings and the state of the mounted file and the card, and the telemetry
switch. It is the vocabulary the other six parts use. Part 2
([tspico-bus.md](tspico-bus.md)) owns the bus and the SD card functions;
part 3 ([tspico-dispatch.md](tspico-dispatch.md)) the dispatcher that
creates most of the run-time globals; part 4
([tspico-messages.md](tspico-messages.md)) everything that prints on the
2068; part 5 ([tspico-files.md](tspico-files.md)) the functions that fill
the caches described here; part 6 ([tspico-commands.md](tspico-commands.md))
the `tpi:` handlers that read `TSP`; part 7 ([tspico-disk.md](tspico-disk.md))
the ROM's disk commands and the channels.

`NULL_SM` (line 393) is a PIO program and is explained in [pio.md](pio.md).

## Map

| Lines | What |
|---|---|
| 1–318 | The changelog comment: Ryan's history of the single-port firmware ([below](#the-changelog-at-the-top-of-the-file)) |
| 320–376 | Imports; the dual-port migration note on what changed from the single-port import |
| 382–385 | The virtual printer's state: `PRT`, `prn_path`, `bmp_size`, `PRINT_FLUSH_AT` |
| 393 | `NULL_SM` ([pio.md](pio.md)) |
| 404–431 | Module-level caches: `LISTMENU_CHOICES`, `LOG_LABELS`, `sd_active`, `prev_path`, `files`, `files_upper`, `dirs`, `dirs_upper`, `lista`, `alldirs`, `sd_space` |
| 442–447 | Colour codes for `SEND_MSG2`: `INK_`, `PAPER_`, `ATTR_VALUES`, `NORMAL_` |
| 449–460 | `RXD`, `rom_id`, `NO_CARD_MSG` |
| 470–484 | The protocol bytes by name: `FN_*`, `STR_END`, `LOOP_END`, `PRE_*` |
| 487–497 | The eleven status codes `_1_OK` … `_11_D_Break` |
| 526–561 | Telemetry and versions: `TLM_ENABLED`, `BUILD_VERSION`, `FW_VERSION`, `ROM_VERSION`, `_tlm_last` |
| 564–608 | `TLM`, `TLM_RESET` |
| 611–685 | `PICO_STATUS` and `PICO_STATUS.__init__` |
| 762 | `MQ`, the bus state machine (first named in `ACTIVATE_MQ`) |
| 882–890 | `_CMD_ECHO`, `CMD_STALL_MS`, `KEY_WAIT_MS` (command I/O) |
| 1088 | `SD_TRY_MS` (the mount budget) |
| 1364–1381 | `led`, `dead`, `busy` (first named in `BLINK_ERROR` / `BLINK_LED`) |
| 1780–1782 | `log_entries`, `log_to_serial`, `TSP` (first named in `LOG`) |
| 2736–2747 | `SD_FREE`, `SD_QUIET` (which commands need the card) |
| 3124–3126 | `NATIVE_TAP`, `MOD_CODE`, `MOD_SCREEN`, `MOD_DATA`, `MOD_LINE`, `KIND` (`f:` files) |
| 3276–3277 | `CHANNELS`, `CH_STATUS` (`OPEN #` channels) |
| 4437 | `EXT_SA_FUNCT` (first named in `GETHELP`) |
| 5029–5030 | `BANK`, `ROM` (first named in `MEMBOOT`) |
| 7053 | `ZX_REPORT` (status codes for the ZX ROM) |

The run-time globals are listed where their first `global` declaration is,
which is how the inventory in
[`reference_hosttest.py`](../../../src/test/reference_hosttest.py) finds them;
all of them are created by `TS2068_IO` ([tspico-dispatch.md](tspico-dispatch.md)),
and each entry says so.

## The changelog at the top of the file

Lines 1 to 318 are a comment: a header box (`DATE: 2026/04/15`, then the
firmware and ROM versions of that day), a `CHANGELOG` of about 270 one-line items, and a
`TO DO` list. It is Ryan's changelog for the single-port firmware, and it
stops before the dual-port rewrite. The same block heads the archived copy of that
firmware, [`archive/tspico-ryan.py`](../../../archive/tspico-ryan.py), whose
header has one more line (`DEPENDS: tspico_upgrade.py`) that this file has
lost; the 2026-09-30 audit used that copy to trace anything older than the
repository's git history.

The items are not dated and not ordered by release. Read as a whole they
describe the firmware growing from a LOAD/SAVE bridge into a command
processor: the flash and SRAM update path and `ROMPATCH`; the activity log
with its levels; mounting a TAP, appending to it, the offset table, `ffw`
and `rew`; the move of `DIR`, `TAPDIR` and `PATH` from `LOAD` to `SAVE`, so
that `LOAD "tpi:…"` only mounts; `SEND_MSG2`'s paging, line endings, keyword
expansion and colour-free text rules; the interactive `ListMenu` with
sixteen choices; help files on the card; external commands from
`extcmd.py`; the status-code constants and the renumbering that followed a
ROM error-code bug; the `dead`/`busy` handshake with a thread on core1;
the three single-port FIFO helpers; and a long tail of small fixes.

Several of those items describe code that no longer exists. The three FIFO
helpers (`WAIT_TX_RECEIVED`, `EMPTY_TX_FIFO`, `EMPTY_RX_FIFO`) were retired
in the dual-port migration (the comment after `MQ_BUSY` lists where each
call site went). The core1 watchdog that `dead` (and `kill`, removed in
#181) served was removed in issue #51. "Nonexistent/nonworking SD Card … the TS-Pico is
halted" was replaced by the card-as-a-state design of issue #43
([SD_ROBUSTNESS_PROPOSAL.md](../../SD_ROBUSTNESS_PROPOSAL.md) §0). The
`TO DO` list (LPRINT debugging, TZX, a dedicated SPI for the card, an
eject command) is Ryan's, and some of it has since been done another way:
the printer path exists ([printer.md](printer.md)), and a missing card is
reported per command rather than ejected.

Everything after it is recorded elsewhere, not here. The dual-port
migration is told in [DUAL_PORT_DEVELOPMENT.md](../../DUAL_PORT_DEVELOPMENT.md);
the issue and pull-request numbers the code's comments cite (#14, #42,
#43, #51, #64, #101, …) are the history of each change; the 2026-09-30 audit
and its status are in [AUDIT-2026-09-30.md](../../AUDIT-2026-09-30.md); the
release notes are in [`.github/release-notes/`](../../../.github/release-notes/),
one file per release tag; and the git log is the record of all of it. The
changelog comment is kept as history and is not maintained.

## The module header

### `PRT`

A [`printer.TextCapture`](printer.md): the virtual printer's text buffer and
its settings (`buf`, `col`, `line`, `cols`, `lines`, `autolf`, `autopg`).
Created once at import. `PRINT_IO` feeds characters into it (`PRT.feed`,
line 5760); `PRINT_FLUSH` writes `PRT.buf` to the card and empties it
(5681–5694); `PRN_OPEN`, `PRN_CLOSE`, `PRN_FLAG` and `PRN_SIZE` reset or set
its fields; the dispatcher tests `PRT.buf` before every non-printer
transaction to decide whether to flush (6629). The invariant is that text
waits in RAM and reaches the SD card only while the Z80 is parked in a READY
wait ([tspico-dispatch.md](tspico-dispatch.md), `PRINT_FLUSH`).

### `prn_path`

`str` or `None`; `None` at import. The path of the open `/sd/VLPRINT`
capture file (`PRNnnn.TXT`, from `printer.next_name`). `PRINT_FLUSH` opens
one when it is `None` (5685–5686) and appends to it afterwards; `PRN_OPEN`
sets it to a fresh file (5779) or `None` on failure; `PRN_CLOSE` sets it to
`None` (5799); `SD_REVALIDATE` sets it to `None` when a different card is
in, because the file was on the other card (1274). `None` means "the next
flush starts a new file". The buffered text in `PRT.buf` is not dropped
with it, so after a card swap the next flush writes the same text into a
new file on the new card.

### `bmp_size`

`(width, height)` in pixels, `(512, 384)` at import: the size of the `.BMP`
that `COPY` writes. `PRN_BMP` (`SAVE "tpi:bmp" CODE x,y`) sets it (5847);
`COPY_BMP` derives integer scale factors from it (`bmp_size[0] // w0`,
`bmp_size[1] // 192`, 5707–5708). See [printer.md](printer.md).

### `PRINT_FLUSH_AT`

`4096`: when `PRT.buf` holds at least this many bytes, `PRINT_IO` flushes
mid-printout (5761) instead of waiting for the next non-printer
transaction. The number is a RAM bound, not a measurement.

### `LISTMENU_CHOICES`

A `dict` from a key's ASCII code to a menu index: `48`–`57` (`0`–`9`) to
0–9, `81` `87` `69` `82` `84` `89` (`Q W E R T Y`) to 10–15. Read by
`ListMenu` (3657–3658) when the user picks an entry. Made once at import so
the menu loop does not rebuild it (the comment says why). The letters are
the top row of the 2068 keyboard, so sixteen choices fit one hand (Ricardo's
change, per the changelog). The keys are upper-case codes: `ListMenu` looks
up `KEY_UP(ch)`, so a lower-case `q` from ROM 2.3 picks the same entry as
`Q` ([tspico-bus.md](tspico-bus.md#key_upch)).

### `LOG_LABELS`

`("INFO", "WARNING", "ERROR", "CRITICAL", "SPECIAL")`: the prefix `LOG`
puts before a message whose level is 0–4 (1785); `LOGLEVEL` prints the
current level's label (4917, 4935). Note the fifth label: `LOG` accepts
level 4, and because its filter drops a message when `level <
TSP.LOG_LEVEL`, level 4 passes every threshold the manual allows (0–4,
[user manual App. D](../../manual/user-manual.md)). The comment in
`PICO_STATUS.__init__` lists only levels 0–3.

### `sd_active`

`bool`, `False` at import. `True` from `ACTIVATE_SD` (the state machine is
parked on `NULL_SM` and GPIO 2–4 belong to SPI) until the next
`ACTIVATE_MQ` sets it `False` ([tspico-bus.md](tspico-bus.md)). Two readers,
both recovery paths: `FAIL_CMD` (5875) hands the bus back first when a
handler raised while the card had it, and the service-loop restart in
`TS2068_IO` (7044) does the same after an unexpected error. Without that
check a `put()` would go to the parked state machine and the 2068 would
never hear from the Pico again (the comment in `FAIL_CMD`;
[`sd_wedged_hosttest.py`](../../../src/test/sd_wedged_hosttest.py)). Note
that `DEACTIVATE_SD` does not clear it: only `ACTIVATE_MQ` does.

### `prev_path`

`str` or `None`; `None` at import. The current directory before the last
successful change, one level deep like a shell's `cd -`. `CDIR` sets it to
the old path after a change (4256) and goes back to it for `tpi:cd -`
(`MOVE TO ""`, 4196–4197); `SD_REVALIDATE` clears it when the folder is not
on the card that is in (1266–1267).

### `files`

`list` of `str`, `[]` at import and again at the top of `TS2068_IO` (6217).
The names of the files in the current folder that a plain listing indexes:
extension in `catalog.DIR_EXT` (`TAP TZX DCK ROM BIN`), not starting with
`.`, not `dirinfo.tap`, sorted case-insensitively. The position in this list
is the number `LOAD "tpi:nnn"` mounts by. `LIST_DIR_FILES` fills it
(1725) and `DIR_FILES` empties it on a card error (1653)
([tspico-files.md](tspico-files.md)); readers are `DIR` (2586–2611),
`CATALOG` (2701), `IDIR` (3474–3489), `GETINFO` (4675), `LOAD_TPI`
(5305–5357) and `PROCESS_CMD`. Empty until a card has been read: with no
card at boot the commands that list or index are refused by `SD_NEEDED`
until a card is in (the comment above it).

### `files_upper`

The same names upper-cased, filled alongside `files` (1726) and emptied
with it. `LOAD_TPI` matches a typed name against it (5333–5334) so that
mounting is case-insensitive.

### `dirs`

`list` of `str`: the subfolder names of the current folder (type `16384`
in `os.ilistdir`), in listing order. Filled by `LIST_DIR_FILES` (1712),
emptied by `DIR_FILES` on error. Read by `CDIR`'s interactive menu
(4303–4305), with `..` in front except at the top.

### `dirs_upper`

The subfolder names upper-cased (1713). Written by `LIST_DIR_FILES` and
`DIR_FILES` and read by nothing: the changelog says it replaced an `isdir`
dictionary that `tpi:rm` used, and no reader is left.

### `lista`

`str`, `""` at import and in `TS2068_IO`. The text of the plain directory
listing: `DIR_HEADER`'s four 32-column lines (path, card line, column
titles) followed by one row per folder, indexed file and unindexed file,
each 32 characters, with colour codes added at print time by `CAT_COLOUR`.
`LIST_DIR_FILES` builds it (1755–1757); on a card error `DIR_FILES` replaces
it with a header and `SD card error: reseat the card` (1658). `DIR` sends it
(2580) and `CDIR` after a change with `CODE 2,0` (4318). It is the cached
listing: `DIR` looks at the card first (`LISTING_CHECK`,
[tspico-bus.md](tspico-bus.md)) and only rebuilds it when the folder changed.

### `alldirs`

`list` of `str`: every folder under `/sd/TAP`, as paths without the `/sd`
prefix (`/TAP`, `/TAP/GAMES`, …), sorted; `GET_DIRS` walks the card for it
(2528). Set by `SD_REVALIDATE` (1277) and `DISK_REN_WORK` (3112); kept up to
date in place by `MDIR` (append and sort, 4995–4996), `DISK_MAKE_DIR`
(3064–3065) and `DISK_ERASE` (a slice assignment that drops a removed tree,
2958). Read by `CDIR`'s global interactive menu (`CODE 0,1`, 4307).

### `sd_space`

`(total, free)` in bytes from `os.statvfs` of the card, or `None`. Set at
the end of `LIST_DIR_FILES` (1749) and to `None` by `DIR_FILES` on error
(1657). `GETINFO` prints it when `TSP.sd_present` and it is not `None`
(4634–4635); the listing header line is built from it at the same time.

### `INK_`, `PAPER_`, `ATTR_VALUES`, `NORMAL_`

| Name | Value | Meaning |
|---|---|---|
| `INK_` | `"\x10"` | the 2068's INK control code; the next byte is the colour |
| `PAPER_` | `"\x11"` | the PAPER control code |
| `ATTR_VALUES` | a tuple of six tuples | the values RST 10h takes after INK and PAPER (0–9), FLASH and BRIGHT (0, 1, 8), INVERSE and OVER (0, 1), indexed by the code − 10h |
| `NORMAL_` | `PAPER_ + "\x08" + INK_ + "\x08"` | colour 8 for both: back to the screen's own colours |

The comment above them says which values can travel. Up to ROM 2.2 the
string reader stops on `00h` and `03h` even as a code's value, so colours 0
and 3 cannot be sent, and `SEND_MSG2` keeps an INK or PAPER code only when
called with `colour=True` and the value is one of 1, 2, 4–9 (2352–2365).
ROM 2.3's reader passes value bytes through
([../rom/exrom-fdd.md](../rom/exrom-fdd.md#ps_read), #228), so when `ROM23()`
is true `SEND_MSG2` keeps any of the six attribute codes whose value is in
`ATTR_VALUES`. Anything else is still dropped, code and value, because RST
10h answers a bad value with Report K in the middle of the text; in text
sent without `colour=True` every one is dropped. Users: `DIR_HEADER`, `CAT_COLOUR`,
`TAPDIR_COLOUR`, `DIR`, `ListMenu`, `GETINFO`
([tspico-messages.md](tspico-messages.md)). Added for the CAT listing and
`tpi:info` on 2026-10-02.

### `RXD`

`None` at import; `TS2068_IO` sets it to `RX_DMA(pre_raw)` (6485), the
`RxDMA` channel that catches the pre-header while the Pico is idle, or
`None` where there is no `rp2.DMA` or no free channel
([tspico_io.md](tspico_io.md)). The one reader is `PROCESS_CMD`'s tail,
which re-arms it (`RXD.arm(MQ)`) before saying IDLE (6182–6183) so that a
command the Z80 sends the moment IDLE rises is captured. The dispatcher
keeps the same object in its local `rxd`.

### `rom_id`

The second byte of the last command's pre-header, kept by `PROCESS_CMD`
(5914) for `ROM23()` ([tspico-bus.md](tspico-bus.md#rom23)). `FFh` at
import. Up to ROM 2.2 that byte was `BANK_SV`, always `FFh`, and the
firmware ignored it; ROM 2.3 sends its version marker there, `23h`, the
same as `PEEK 101` ([../rom/exrom-driver.md](../rom/exrom-driver.md#build_preheader_b-1ba0h)).
It answers "which ROM is this?" (the question #227 left open) without a
setting in `config.ini`, which could go stale as `ROM_VERSION` did. A
command from the ZX48 ROM does not pass through `PROCESS_CMD`, so it leaves
the value alone; that ROM has no function 86h.

### `NO_CARD_MSG`

`"No SD card. Insert one and\rtry again."`, the one error every command
that needs the card gives when there is none, with status
`_10_J_Invalid_IO`. `SEND_MSG` compares by identity (`msg is NO_CARD_MSG`,
2206) and forces the display whatever `VERBOSE` says, so callers must pass
this object, not a copy of its text. Used by `SD_CALL` (2725) and
`NO_CARD_REPLY` (2765). The comment explains the wording: the `\r` breaks
the 37-character text before the 32-column wrap would, and Report J is the
report that means the device is not there.

### The protocol bytes

Named in issue #16; the numbers are what people know them by, so each use
site also says the number in its comment. All are `const()`.
[PROTOCOL.md §5](../../PROTOCOL.md) describes each function's exchange;
[ports-and-status.md](../appendix/ports-and-status.md) tabulates them.

| Name | Value | Meaning | Used by |
|---|---|---|---|
| `FN_PRINT_STRING` | `0x81` | print the text up to `STR_END` on the main screen; a reply's first byte in place of a status | `SEND_MSG` (2234) |
| `FN_PRINT_STRING_KEY` | `0x82` | print, then wait for a key and send it back | nothing |
| `FN_PRINT_CHAR` | `0x83` | print one character | nothing |
| `FN_RETURN_KEY` | `0x84` | wait for a key and send it back | nothing |
| `FN_GET_STATUS` | `0x85` | the Z80 sends a keyboard/aux mask | nothing |
| `FN_PRINT_LOOP` | `0x86` | pages of text with a key between them, `LOOP_END` ends it | `SEND_MSG2` (2312), `PROMPT_EACH` (2795), `ListMenu` (3561, 3584), `SEND_MSG_PROMPT_YN` (5388) |
| `FN_PRINT_LOOP_LOWER` | `0x88` | `FN_PRINT_LOOP` on the lower screen | `SEND_MSG_PROMPT_YN` with `lower=True`, which only `tpi:fopen`'s prompt passes (5388) |
| `STR_END` | `0x00` | end of the text (`FN_PRINT_STRING`); end of a page, the Z80 waits for a key (`FN_PRINT_LOOP`) | `SEND_MSG` (2243), `SEND_MSG2` (2451), `PROMPT_EACH` (2805), `ListMenu` (3634), `SEND_MSG_PROMPT_YN` (5397) |
| `LOOP_END` | `0x03` | end of the `FN_PRINT_LOOP` loop, no key wait | `SEND_MSG2` (2284), `PROMPT_EACH` (2814), `ListMenu` (3572, 3686), `SEND_MSG_PROMPT_YN` (5421) |
| `PRE_HEADER` | `0x00` | `pre[0]` of a tape header block: LOAD or SAVE | the dispatcher (6646, 6662, 6849, 6865) |
| `PRE_DATA` | `0xFF` | `pre[0]` of a tape data block | the dispatcher (6646, 6849, 6865) |
| `PRE_CMD` | `0x42` | `'B'`: a `tpi:` command, or the printer when `pre[1]` is 4–6 | the dispatcher (6629, 6646, 6877, 6880) |

### The status codes

The byte a command answers with, and the BASIC report the ROM raises for
it. All are `const()` with a leading underscore, which MicroPython
substitutes at compile time and never stores on the module: `TS/extcmd.py`
cannot read them as `tspico._6_6_Num2Big` on the Pico, though CPython lets
it ([PROTOCOL.md §13](../../PROTOCOL.md), "Underscore constants don't cross
modules"). The changelog records that they were renumbered once, when a ROM
error-code bug had reported them off by one. The full map of codes to
reports is in [ports-and-status.md](../appendix/ports-and-status.md).

| Name | Value | Report | Uses in this file |
|---|---|---|---|
| `_1_OK` | 1 | 0 OK | 87 |
| `_2_R_Tape_load` | 2 | R Tape loading error | 6: short `f:` file, `tpi:help` file errors, a mount that failed, `PRINT_IO`, a bad command checksum, `ZX_REPORT` |
| `_3_F_Invalid_file` | 3 | F Invalid file name | 50: "not found", SD card errors (`SD_CALL`), `CH_STATUS["F"]` |
| `_4_Q_Parameter` | 4 | Q Parameter error | 41: bad arguments to the disk commands; the fallback in `CH_CALL` and `ZX_TPI` |
| `_5_C_Nonsense` | 5 | C Nonsense in BASIC | 4: an unknown command (6108), a body that does not decode (6060), `SA_NOT_IMP` (3877), `tpi:chwr` with bad hex (3377) |
| `_6_6_Num2Big` | 6 | 6 Number too big | 1: `tpi:dir CODE 1,n` with `n` past the end |
| `_7_8_EOF` | 7 | 8 End of file | 3: `tpi:chrd` at the end, `tpi:md` of an existing folder |
| `_8_A_Invalid_arg` | 8 | A Invalid argument | 21: `BAD_CODE`, bad `CODE` values |
| `_9_9_STOP` | 9 | 9 STOP statement | none |
| `_10_J_Invalid_IO` | 10 | J Invalid I/O device | 5: no card (`SD_CALL`, `NO_CARD_REPLY`), `CH_STATUS["O"]`, a handler that raised (`FAIL_CMD`) |
| `_11_D_Break` | 11 | D BREAK | none |

### `TLM_ENABLED`

`bool`, `False` in the file. When `False`, `TLM` and `TLM_RESET` return at
once with no formatting, no FIFO read and no print, so the calls scattered
through the hot paths cost nothing. The value that runs is not the one in
the file: `main.py` reads the `TELEMETRY` key of `config.ini` and sets
`TS.tspico.TLM_ENABLED` from it before `TS2068_IO` starts, and mirrors it
onto `dev_tspico` when that override is loaded ([boot.md](boot.md);
[user manual App. D](../../manual/user-manual.md)). The comment above the
constant and [DEVELOPER_GUIDE.md §8](../../DEVELOPER_GUIDE.md) say the
same: set `TELEMETRY` to `true` in `config.ini` (until #181 both told you
to edit `/main.py` or the file itself and rebuild). Per-character printing over USB
takes 5–10 ms and the RX FIFO is four deep, so a trace changes the timing
it observes ([PROTOCOL.md §13](../../PROTOCOL.md), first pitfall).

### `BUILD_VERSION`

`str`: `"<commit>[+dirty] (<branch>)"` from `TS/buildinfo.py`, which
`tools/gen-buildinfo.py` writes from git before the frozen modules are
staged ([boot.md](boot.md)); `"unknown (no buildinfo)"` when that module
is missing, so a hand build still runs. Printed at import, tagged with
`__name__` (`TS.tspico` or `dev_tspico`, the two byte-identical copies);
logged by `LOAD_CONFIG` (4812); shown by `tpi:info` (4630, through
`BUILD_FIT`). The comment records why it is generated: a hand-written
literal rotted. It is assigned inside a `try`, so the inventory does not
list it as a variable.

### `FW_VERSION`, `ROM_VERSION`

`"2.2.1"` and `"2.2"`: the release number of this firmware and the ROM it
ships with. The firmware and its ROM share one `major.minor`,
and a third part marks a firmware-only release on the same ROM (the
comment). `PICO_STATUS.__init__` copies `FW_VERSION` into `TSP` unconditionally
and takes `ROM_VERSION` from `config.ini` with this as the fallback;
`LOAD_CONFIG` writes both into the defaults it fills `config.ini` with
(4837–4838). `tpi:info` reports `TSP.FW_VERSION` and `TSP.ROM_VERSION`.
`config.ini`'s own `FW_VERSION` is kept because `build-payload.sh` and the
web updater read it ([AUDIT-2026-09-30.md](../../AUDIT-2026-09-30.md),
status). Maintained by hand on purpose: `BUILD_VERSION` is the commit
underneath it.

### `_tlm_last`

`int`, microseconds from `time.ticks_us()`; 0 at import. The timestamp of
the previous `TLM` event, so each line can print the delta. Written by
`TLM` (580) and `TLM_RESET` (605–607). `ticks_us` wraps about every 18
minutes (the comment); `ticks_diff` handles the wrap.

### `TLM(action, detail="")`

Prints one telemetry event to the USB console: `[TLM <now> dt=<µs since
the last event> tx=<n> rx=<n>] action: detail`. Steps: return at once if
`TLM_ENABLED` is `False`; take `ticks_us()` (0 if it raises); compute `dt`
against `_tlm_last` (0 for the first event) and store `now`; read
`MQ.tx_fifo()` and `MQ.rx_fifo()`, printing `tx=? rx=?` if that raises —
which it does before `TS2068_IO` has created `MQ`, for instance from
`LOAD_CONFIG`; print. Reads and writes `_tlm_last`; reads `MQ`. Called
from almost every function in the file. Beware that the FIFO counts are
those of whatever program state machine 0 is running: while the card has
the bus they are `NULL_SM`'s. And beware that each print is 5–10 ms on the
bus timeline.

### `TLM_RESET(tag="")`

Resets `_tlm_last` to now and prints `[TLM ===== tag =====]` so the next
event's `dt` counts from here. A no-op when telemetry is off. Nothing in
the firmware calls it today; it is kept for a developer's trace.

### `PICO_STATUS`

The class of `TSP`, the one object that holds the TS-Pico's settings and
the state of the session: the mounted file and the position in it, the
mode (TS-2068 or ZX48), the ROM and DOCK slots, the log level, and the
SD card. It has no methods but the constructor. Every handler reads it
through the global `TSP`; `LOAD_TS`, `SAVE_TS` and the ZX transfers in
[tspico_io.md](tspico_io.md) take it as a parameter and hand the same object
back.

### `PICO_STATUS.__init__(self, init_values)`

`init_values` is the dictionary `LOAD_CONFIG` returns: `config.ini`'s
JSON with every missing key filled from `LOAD_CONFIG`'s defaults, and the
one-shot boot slot applied ([tspico-dispatch.md](tspico-dispatch.md),
`LOAD_CONFIG`). The constructor sets the session fields to their initial
values, then reads seven keys inside `try`/`except` with hard-wired
fallbacks. Because `LOAD_CONFIG` fills all seven before the constructor
sees the dictionary, those fallbacks never run on a normal boot; they
matter only to a caller that builds the object from a partial dictionary,
as the host tests do. The comment says the defaults should live in one
place; today they are in both.

Session state, no `config.ini` key:

| Attribute | Initial value | Meaning | Written later by | Read by |
|---|---|---|---|---|
| `append` | `False` | SAVE appends to the mounted TAP instead of making a new file | `MOUNT_FILE` (`False` on a fresh mount, restored on a remount), `APPEND`, `NEW_TAP`, `DISK_FORMAT`, the dispatcher's SAVE branch (restored after a save), `FORGET_MOUNT`, `SD_REVALIDATE` (`False` on a different card) | `SAVE_TS` (tspico_io), `TAPDIR`, `GETINFO` |
| `bank_sm` | `DCK_SLOT * 16 + ROM_SLOT` (the `0` assigned first is overwritten at the end) | the word `BANK.put()` takes: DOCK slot in bits 4–7, ROM slot in bits 0–3 | `MEMBOOT` (low nibble), `MEMDOCK` (high nibble) | `TS2068_IO` (`BANK.put`), `getBoot`, `getDock` |
| `cur_path` | `"/sd/TAP"` | the current folder, a real path on the card | `CDIR` (`os.getcwd()` after a change), `SD_REVALIDATE` (back to the top when the folder is gone) | 42 sites here, `SAVE_TS`/`SAVE_ZX` in tspico_io |
| `f_name` | `""` | the mounted file's full path; `""` when nothing is mounted, as `FORGET_MOUNT` leaves it. Always a `str`: it started as `[]` until #163, and `CATALOG_TEXT` and `BLKRCV`, which call `.upper()` on it unguarded, raised `AttributeError` (Report J) until the first mount of the session | `MOUNT_FILE`, `FORGET_MOUNT`, the SAVE branch (restored) | 51 sites here, 19 in tspico_io |
| `offset` | `0` | byte offset in `/TMP/temp.tap` of the next block | `OFF_TABLE`, `MOUNT_FILE`, `FWD`, `REW`, `FORGET_MOUNT`, the SAVE branch; advanced by `LOAD_TS` | `LOAD_TS`, `TAPDIR`, `GETINFO` |
| `offset_tbl` | `[]` | one entry per block of the mounted TAP, from `catalog.tap_table` (the offset first) | `OFF_TABLE`, `FORGET_MOUNT` | `FWD`, `REW`, `TAPDIR`, `GETINFO` (23 sites) |
| `ld_start`, `ld_start_idx`, `ld_wrapped` | `-1`, `0`, `False` | LOAD search bookkeeping: where a header search began and whether the tape has been round once, so `LOAD_TS` stops after one pass; there is no BREAK signal to stop it ([BREAK_AND_ABORT.md](../../rom-analysis/BREAK_AND_ABORT.md)) | `LOAD_TS`, `REWIND_ABORTED_SEARCH`, `LOAD_SERVE` (which saves and restores them) (tspico_io only) | tspico_io only |
| `tap_idx` | `0` | index of the next block in the mounted TAP | `OFF_TABLE`, `MOUNT_FILE`, `FWD`, `REW`, `FORGET_MOUNT`, the SAVE branch; advanced by `LOAD_TS` | `LOAD_TS`, `TAPDIR`, `GETINFO`, `LOAD_TPI` |
| `totlen` | `0` | size in bytes of `/TMP/temp.tap` (`MOUNT_FILE` reads it with `os.stat`) | `MOUNT_FILE` (1978); `LOAD_SERVE` swaps in a one-shot tape's length and restores it (tspico_io) | tspico_io only (`LOAD_TS`: the wrap at the end); nothing in tspico.py reads it |
| `zx48` | `False` | the TS-Pico is in ZX Spectrum mode | `ZX48` (`True`), `PROCESS_CMD` at entry, `ZX48_IO` at exit and the service-loop restart (`False`) | the dispatcher after `PROCESS_CMD` (enters `ZX48_IO` when `True`), `ZX48_IO` |

Settings, each from a `config.ini` key ([user manual App. D](../../manual/user-manual.md)):

| Attribute | Key | Default | Meaning | Written later by | Read by |
|---|---|---|---|---|---|
| `DCK_SLOT` | `DCK_SLOT` | `0` | the DOCK slot at switch-on, 0–15 | nothing | the constructor (`bank_sm`, `dck_prev_slot`) |
| `ROM_SLOT` | `ROM_SLOT` | `1` | the BOOT slot; `LOAD_CONFIG` uses any other value once and writes 1 back | nothing | the constructor (`bank_sm`) |
| `ROM_SM` | `ROM_SM` | `0x0A` | the word `ROM.put()` takes: bits 0–1 the BOOT memory, bits 2–3 the DOCK memory, 1 = SRAM, 2 = flash; `LOAD_CONFIG` accepts only 5, 6, 9 and 10 | `MEMBOOT` (bits 0–1), `MEMDOCK` (bits 2–3) | `TS2068_IO` (`ROM.put`), `getBoot`, `getDock`, the constructor (`dck_prev_mem`) |
| `LOG_LEVEL` | `LOG_LEVEL` | `2` | `LOG` drops a message whose level is below it; 0 keeps everything | `LOGLEVEL` | `LOG`, `LOGLEVEL`, `GETINFO`, the dispatcher (a level-0 memory line), tspico_io (42 sites, passed to `LOG_ADD`) |
| `VERBOSE` | `VERBOSE` | `False` | `SEND_MSG` prints its text only when this is set or the caller forces it | `VERB_TOGGLE` | `SEND_MSG`, `GETINFO`, `VERB_TOGGLE` |
| `FW_VERSION` | none | the module's `FW_VERSION` | the firmware's release number; never `config.ini`'s | nothing | `GETINFO` |
| `ROM_VERSION` | `ROM_VERSION` | the module's `ROM_VERSION` | shown by `tpi:info`; nothing else switches on it any more (`SEND_MSG2` used to, see its comment at 2271–2282) | nothing | `GETINFO`, a `TLM` line |
| `ZX_TAPE_COMPAT` | `ZX_TAPE_COMPAT` | `False` | ZX48 mode uses the compatible loader (`LOAD_ZX_C`) rather than the normal one | `ZX48` when its `CODE`'s second value is above 0 | `ZX48`, `ZX48_IO` |

The SD card, kept by `ACTIVATE_SD` and `SD_NOTE_CARD` ([tspico-bus.md](tspico-bus.md)):

| Attribute | Initial value | Meaning | Written later by | Read by |
|---|---|---|---|---|
| `sd_present` | `False` | a card was there at the last mount | `SD_NOTE_CARD` (`True`), `ACTIVATE_SD` on failure, `SD_REVALIDATE` when no `TAP` folder can be made, `TS2068_IO` when the boot mount fails (`False`) | `ACTIVATE_SD` (how many tries), `SD_CALL`, `PROCESS_CMD`'s card gate, `GETINFO`, the idle heartbeats of `TS2068_IO` and `ZX48_IO` (two blinks without a card), `TS2068_IO`'s boot log |
| `sd_cid` | `None` | the CID register of the last card mounted: `None` until one has been seen, 0 when the driver could not read it, otherwise the card's identity | `SD_NOTE_CARD` | `SD_NOTE_CARD`, `ACTIVATE_SD` ("none since power-on") |
| `save_no_card` | `False` | the dispatcher's card check for this SAVE failed | the SAVE branch (from `SD_PROBE`; back to `False` after `SAVE_TS`) | `SAVE_TS` (tspico_io 2475, by `getattr`) refuses at the header with Report J |
| `sd_listing_ok` | `False` | `DIR_FILES` read the current folder without errors | `SD_REVALIDATE`, `LISTING_FRESHEN`, `REFRESH_LISTING` (each from `DIR_FILES`'s result) | `TS2068_IO`'s boot log (`sd_ok`) |
| `listing_stale` | `False` | a ZX48 SAVE wrote into the current folder, and the caches have not been re-read | `SAVE_ZX` (tspico_io 2912, `True`), `REFRESH_LISTING` (`False`) | `PROCESS_CMD` (6044), `ZX_TPI` (7109, 7128), both by `getattr` |

`tpi:dock`'s memory of its previous setting (2026-09-30 audit §2 #19;
[`audit_fixes_hosttest.py`](../../../src/test/audit_fixes_hosttest.py),
`test_dock_prev`):

| Attribute | Initial value | Meaning | Written later by | Read by |
|---|---|---|---|---|
| `dck_prev_slot` | `DCK_SLOT` | the DOCK slot before the last `tpi:dock` | `MEMDOCK` | `MEMDOCK` (`CODE 0,1` reports it, `CODE 0,2` swaps to it) |
| `dck_prev_mem` | `(ROM_SM >> 2) & 3` | the DOCK memory (1 SRAM, 2 flash) before the last `tpi:dock`; it used to be the constant 2, which named the wrong memory when `config.ini` put the DOCK in SRAM | `MEMDOCK` | `MEMDOCK` |

Other code adds attributes the constructor does not set, and reads them
with `getattr` where they may be missing:

| Attribute | Set by | Meaning |
|---|---|---|
| `listing_sig` | `LIST_DIR_FILES` (1706) | `LISTING_SIG` of the folder as last listed; `LISTING_FRESHEN` compares against it |
| `native` | `NATIVE_OPEN` (3142–3167); cleared by `LOAD_TS`/`SAVE_TS` in tspico_io | the pending `f:` operation: `op`, `session`, the path or the one-shot tape ([tspico-disk.md](tspico-disk.md)) |
| `native_saved` | `SAVE_TS` (tspico_io 2719, 2771), the SAVE branch | the save went to an `f:` file: refresh the listing, change no mount |
| `load_file` | `LOAD_TS` (tspico_io 1780, 1790) | the tape `LOAD_TS` is serving when it is not `/TMP/temp.tap` |
| `save_final`, `save_recovered` | `SAVE_TS` (tspico_io 2406–2407, 2424, 2630, 2788); the SAVE branch clears `save_final` | the final status to send after the SD work, and whether `SAVE_TS` gave up on a silent Z80 (RECOVERED) |

## The rest of the file's variables, in source order

### `MQ`

The bus state machine, `rp2.StateMachine` on PIO0 state machine 0; the
object every FIFO read and write and every `MQX` exec goes through. It does
not exist until `TS2068_IO` first calls `ACTIVATE_SD` (6368): before that
`TLM` catches the `NameError` and prints `tx=? rx=?`. Three functions
build it, each a new object on the same hardware state machine:
`ACTIVATE_MQ` (`TS_IO_DUAL` at 30 MHz, running, Y BUSY), `ACTIVATE_SD`
(`NULL_SM` at 15 MHz, started and stopped at once: parked) and `ZX48_IO`
(7213, `TS_IO_DUAL`, started a moment later). The dispatcher and `ZX48_IO`
also take it back from the tuples `SAVE_TS`, `LOAD_SERVE`, `LOAD_ZX`,
`LOAD_ZX_C` and `SAVE_ZX` return (6700, 6859, 6871, 7259, 7263, 7273), which
hand back the object they were given. Lifetime: the session. The invariant
is `sd_active`: when it is `True`, `MQ` is the parked `NULL_SM`, its FIFOs
reach no Z80, and the real program's FIFOs and Y are gone; every SD access
ends with `ACTIVATE_MQ`, which leaves TX empty and Y BUSY
([tspico-bus.md](tspico-bus.md)). Building a state machine empties its
FIFOs, so a pre-load byte still in TX is lost across any rebuild
(`PRELOAD_READ`).

### `_CMD_ECHO`

`bytearray(3)`, made once at import: the scratch `TX_ROOM` and `STREAM_DMA`
keep the Z80's stray writes in while command output waits for room —
`[count, byte, byte]`, never a list, because this runs while the Z80 is
streaming and an allocation can start a GC ([tspico_io.md](tspico_io.md),
`TX_ROOM`). Each user zeroes `_CMD_ECHO[0]` before the call: `CMD_PUT`
(897), `CMD_SEND` (916), `CH_READ` (3411) and `BLKRCV` (4095, which also
logs its contents on a failure). A key the user presses while a listing is
still going out lands here and is dropped.

### `CMD_STALL_MS`, `KEY_WAIT_MS`

| Name | Value | Meaning |
|---|---|---|
| `CMD_STALL_MS` | `600_000` (10 min) | how long command output waits on a Z80 that has stopped reading before giving up with RECOVERED |
| `KEY_WAIT_MS` | `86_400_000` (a day) | how long a key wait waits for the user |

Both are long on purpose: the Z80 legitimately stops reading for as long
as the user takes at the ROM's own "scroll?" prompt or a slow listing, and
a 3 s limit killed `tpi:idir` and a mount-error reply on hardware
(2026-09-27, the comment; #69 in the audit's "still needed" list). A Z80
that has really gone says so at once: BREAK or the next
command's SYNC is a port-0Fh write, which ends either wait
([PROTOCOL.md §3.3](../../PROTOCOL.md)). Users: `CMD_PUT`, `CMD_SEND`,
`CMD_DRAIN`, `CH_READ` (3412), `BLKRCV` (4096, as the limit after the first
FIFO-full), `ZX_TPI` for a listing's pages (7123); `CMD_KEY` for
`KEY_WAIT_MS`.

### `SD_TRY_MS`

`6000` ms: `ACTIVATE_SD` starts no new mount attempt once this long has
gone since its first. The comment gives the arithmetic: an empty slot fails
an attempt in about 0.5 s, so five tries fit in about 5 s; a card that is in
but holds MISO low costs the driver three 1 s busy timeouts before `CMD0`,
about 4 s an attempt, and five of those (20 s, seen on hardware 2026-10-02
after a reflash) outlasted the 2068's ~19.9 s READY wait and gave Report J
while the Pico went on answering nobody. With the budget the worst case is
two such attempts, about 8.5 s. Pinned by
[`sd_state_hosttest.py`](../../../src/test/sd_state_hosttest.py).

### `led`

`machine.Pin(25, Pin.OUT)`, the Pico's on-board LED. Created in
`TS2068_IO` (6222) and never replaced; it does not exist before that, and
`BLINK_ERROR`, `BLINK_LED` and the other functions that name it with
`global led` only read it. On during work the user should see as work:
`MOUNT_FILE`, `DIR`, `CATALOG`, `IDIR`, `GETHELP`, `CDIR`, `GETLOG`, the
dispatcher's SAVE, LOAD and command branches, and `ZX48_IO`'s transfers;
toggled by `BLINK_ERROR` and by `COPY_FILE` as it copies; blinked by
`BLINK_LED` on core1 during boot; and the heartbeat in the idle loops of
`TS2068_IO` and `ZX48_IO` (one 0.1 s flash every 2 s, two without a card,
[tspico-dispatch.md](tspico-dispatch.md)).

### `dead`

`bool`. `TS2068_IO` sets it `True` at the start (6215), `False` just before
it starts `BLINK_LED` on core1 (6354), and `True` again once the card has
been looked for (6373), which is what tells `BLINK_LED` to stop. The only
reader is `BLINK_LED`'s loop. `SEND_MSG2` declares it `global` and does
not use it. Its name is the core1 watchdog's ("whether an IO routine is
alive", the comment at 6199); that watchdog was removed in issue #51
([DUAL_PORT_DEVELOPMENT.md §8](../../DUAL_PORT_DEVELOPMENT.md), Bug 2, for
its history in tspico_io), and the `dead`/`busy` handshake `COPY_FILE`
had with it is gone (the comment at 1404–1427). Nothing else is left of it
here.

### `busy`

`bool`: core1 is writing the log to flash (or, during boot, blinking the
LED). `TS2068_IO` sets it `False` at the start (6214). Set `True` by
`BLINK_LED` on entry and `False` on exit; `True` by `SAVE_LOG` and `False`
in its `finally` (2107, 2121); `True` and `False` around `CLEAR_LOG`'s
write (2159, 2170); and `True` on core0 by the idle loop just before it
spawns `SAVE_LOG` (7014), `False` again if the spawn fails with "core1 in
use" (6912), because then nobody else will clear it. Readers: `WAIT_CORE1`
(bounded; the dispatcher calls it before a SAVE or LOAD), the SYNC path's
800 ms wait before IDLE (6575), the idle loop's `if not busy` before
spawning (6969), `TS2068_IO`'s wait for `BLINK_LED` to stop (6379,
unbounded, and the comment says why that one is safe), and `ZX48_IO`'s
bounded 3 s wait before a transfer (7243). The invariant it carries is
"a flash write stops both cores, so no transfer may start while one is in
progress" ([PROTOCOL.md §13](../../PROTOCOL.md), "Wait for core1" and
"`busy` is set by another core"). Before the 2026-09-30 audit `SAVE_LOG`
cleared it only on success, and a full flash hung every mount, SAVE and
LOAD for good (audit §1 #1;
[`audit_fixes_hosttest.py`](../../../src/test/audit_fixes_hosttest.py),
`test_busy`). `tspico_io` has an unrelated `busy` of its own that nothing
reads.

### `log_entries`

`list` of `str`, `[]` from `TS2068_IO` (6219). `LOG` appends
`"[<ticks_us>]<LABEL>:<msg>\n"` (1816); the dispatcher and `ZX48_IO` append
the one string `SAVE_TS`, `LOAD_SERVE` and the ZX transfers return as
their log (6704, 6861, 6873, 7265, 7275; the comments say an array was
planned). `SAVE_LOG` writes every entry to `/activity.log` and replaces the
list with an empty one in its `finally`, write or no write, so a full flash
cannot make it grow without bound (2111–2120); `CLEAR_LOG` empties it with
the file (2164). The idle heartbeats test it (`if log_entries`) to decide
whether to save (6968, 7343). `SAVE_LOG` runs on core1 in `TS2068_IO`'s
idle loop and synchronously everywhere else; an entry `LOG` appends on
core0 between core1's write loop and its `log_entries = []` is lost with
the replaced list *(inferred: nothing in the code guards that window)*.

### `log_to_serial`

`bool`, `False` from `TS2068_IO` (6220); nothing in the firmware sets it
`True`. When it is, `LOG` prints each message to the console (1789) and
then goes on to append it to `log_entries` as usual: "as well as", as the
comments at 1789 and 6203 say (until #181 they said "instead of"). A
developer flips it at the REPL.

### `TSP`

The `PICO_STATUS` object. `TS2068_IO` creates it (6225) right after
`LOAD_CONFIG` returns the settings, and it lives for the session;
thirty-odd functions declare it `global` and read or write its fields, and
the dispatcher and `ZX48_IO` take it back from the transfer functions'
return tuples (the same object). Before it exists `LOG` must still work,
for the boot messages `LOAD_CONFIG` logs: `LOG` looks it up with
`globals().get("TSP")` and keeps every message until there is a level to
filter by (1811–1814; the comment above tells how the old guard crashed a
boot with a bad `config.ini`; audit §1 #2,
[`audit_fixes_hosttest.py`](../../../src/test/audit_fixes_hosttest.py),
`test_log_before_tsp`).

### `SD_FREE`, `SD_QUIET`

Two `frozenset`s of upper-cased command words, next to `SD_NEEDED` and
`NO_CARD_REPLY`, which use them ([tspico-bus.md](tspico-bus.md)).

`SD_FREE` lists the commands that work without the card: `TPI:INFO`,
`TPI:VERBOSE`, `TPI:LOGLEVEL`, `TPI:LOG`, `TPI:BOOT`, `TPI:MEMBOOT`,
`TPI:DOCK`, `TPI:MEMDOCK`, `TPI:ZX48`, `TPI:NOP`, `TPI:PATH`, `TPI:CLOSE`,
`TPI:TAPDIR`, `TPI:FFW`, `TPI:REW`, `TPI:APPEND`, `TPI:BLKRCV`,
`TPI:CHCLOSE`, the printer settings (`TPI:AUTOLF`, `TPI:NOAUTOLF`,
`TPI:AUTOPG`, `TPI:NOAUTOPG`, `TPI:BMP`, `TPI:PRNSZ`) and the
not-implemented ones (`TPI:CONFIG`, `TPI:DELETE`, `TPI:FRESET`,
`TPI:GETCONFIG`, `TPI:LIST`, `TPI:MEMINFO`, `TPI:STOP`). Everything else
in `SA_funct` needs the card, as do `LOAD "tpi:name"` and `tpi:help
<topic>`; external commands decide for themselves. `TPI:CHCLOSE` is here
although closing a write stream with a part-written record writes to the
card: `CH_CLOSE` mounts the card itself in that one case, and `CLOSE #` of
a read stream must keep working with no card in (the comment at
3427–3447; audit §1 #3).

`SD_QUIET` lists the commands the ROM's disk module sends in the middle of a
BASIC statement (`TPI:CHOPEN`, `TPI:CHWR`, `TPI:CHRD`, `TPI:FOPEN`): a
printed message would move the ROM's current channel, so with no card they
get the bare status from `CH_REPLY` instead of `NO_CARD_MSG`.

### `NATIVE_TAP`, `MOD_CODE`, `MOD_SCREEN`, `MOD_DATA`, `MOD_LINE`, `KIND`

For `SAVE`/`LOAD`/`VERIFY`/`MERGE "f:<path>"`, which the fdd ROM turns into
`tpi:fopen` ([tspico-disk.md](tspico-disk.md), `NATIVE_OPEN`;
[native.md](native.md)).

| Name | Value | Meaning | Used by |
|---|---|---|---|
| `NATIVE_TAP` | `"/TMP/native.tap"` | the one-shot tape `NATIVE_LOAD_PREP` builds on the Pico's flash for `LOAD_TS` to serve; on flash because `LOAD_TS` cannot use the card | `NATIVE_OPEN` (3167, into `TSP.native`), `NATIVE_LOAD_PREP` (3220) |
| `MOD_CODE` | `0xAF` | the BASIC token of `CODE`: the statement's modifier as the ROM sends it | `NATIVE_LOAD_PREP` (3198, 3207) |
| `MOD_SCREEN` | `0xAA` | `SCREEN$` | `NATIVE_LOAD_PREP` (3200, 3207, 3213) |
| `MOD_DATA` | `0xE4` | `DATA` | defined, not used by name |
| `MOD_LINE` | `0xCA` | `LINE` | `NATIVE_LOAD_PREP` (3205) |
| `KIND` | `{native.T_PROGRAM: "a program", native.T_NUMARR: "an array", native.T_CHARARR: "an array", native.T_CODE: "bytes"}` | the words of the refusal "`<file> holds a program`" when the file's +3DOS type does not match the statement | `NATIVE_LOAD_PREP` (3212, `"data"` for any other type) |

### `CHANNELS`, `CH_STATUS`

`CHANNELS` is the `channels.Channels` table of open `OPEN #` streams, made
at import with `SD_FS()`, the file-access object just above it that reads
and writes the card ([channels.md](channels.md);
[tspico-disk.md](tspico-disk.md), `SD_FS`). `CH_OPEN`, `CH_WRITE`,
`CH_READ` and `CH_CLOSE` call its methods through `CH_CALL`, so the card
is active while they run; `SD_REVALIDATE` calls `close_all()` when a
different card is in (1273).

`CH_STATUS` maps a `ChannelError`'s report letter to a status:
`"F"` to `_3_F_Invalid_file`, `"Q"` to `_4_Q_Parameter`, `"O"` to
`_10_J_Invalid_IO`. `CH_CALL` looks the letter up with `_4_Q_Parameter` as
the default (3311). The comment at 3458 points at the ROM side of the same
table (`CH_CLOSE_HOOK` → `CH_STATUS` → `C_FAIL` in
[exrom-fdd.md](../rom/exrom-fdd.md)).

### `EXT_SA_FUNCT`

`dict` from an upper-cased command word to a handler, the external
commands. `TS2068_IO` imports it (6339–6348) from `/dev_extcmd.py` if that
override is on the flash, else from the frozen `TS.extcmd`
([extcmd.md](extcmd.md)), else `{}` with a log line. `TS2068_IO` passes it
to `PROCESS_CMD` as a parameter of the same name, which shadows the global
there (5902, 6100–6104); `GETHELP` reads the global to list the external
commands (4564–4568). Lifetime: the session; nothing rewrites it.

### `BANK`, `ROM`

Two more state machines, created once by `TS2068_IO` and never rebuilt:
`ROM = StateMachine(4, set_ctrl, freq=150_000_000, in_base=Pin(0),
jmp_pin=Pin(26), set_base=Pin(21), out_base=Pin(19))` (6184) drives the
flash and SRAM control lines, and `BANK = StateMachine(5, sel_bank,
freq=150_000_000, jmp_pin=Pin(26), out_base=Pin(15))` (6191) the bank
select lines; the programs are in [pio.md](pio.md), the pins in
[hardware.md](../hardware.md). Each takes one word through its TX FIFO:
`ROM.put(TSP.ROM_SM)` and `BANK.put(TSP.bank_sm)` at boot (6257–6258), and
again from `MEMBOOT` (5071–5072, after a 0.1 s sleep the audit kept) and
`MEMDOCK` (5192–5193) when the user changes a slot. `PROCESS_CMD` declares
both `global` and does not use them. The service-loop restart leaves them
alone on purpose: rebuilding them, or `machine.reset()`, would release the
lines that select the 2068's ROM bank under the running machine (the
comment at 6490–6499). The commented-out alternative at 6250–6252
(`set_dck` on state machine 4) is the DOCK-only mapping. Host harnesses
must never use state machines 4 or 5.

### `ZX_REPORT`

`{_1_OK: 0xFF, _2_R_Tape_load: 0x1A, _3_F_Invalid_file: 0x0E,
_4_Q_Parameter: 0x19}`: the status codes above translated into the byte
the ZX ROM puts in `ERR_NR` for `LOAD "tpi:…"` in ZX48 mode, where
`0xFF` is `0 OK`. `ZX_TPI` sends `ZX_REPORT.get(st, 0x19)` as the first
byte of its reply (7155), so any other status is Report Q. See
[tspico-dispatch.md](tspico-dispatch.md), `ZX_TPI`, and
[zx48.md](../rom/zx48.md).
