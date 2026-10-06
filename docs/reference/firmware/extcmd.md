# src/TS/extcmd.py — the external command table

Source: [`src/TS/extcmd.py`](../../../src/TS/extcmd.py); its byte-for-byte
copy [`src/dev_extcmd.py`](../../../src/dev_extcmd.py). Part of the
[programmer's reference](../README.md).

External commands are `tpi:` commands that live outside `tspico.py`: a
dictionary, `EXT_SA_FUNCT`, from a command word to a handler, which
`PROCESS_CMD` consults after the built-in table `SA_funct` has not matched
([tspico-dispatch.md](tspico-dispatch.md)). The point is iteration without a
UF2 rebuild: `TS2068_IO` imports the table from `/dev_extcmd.py` on the
Pico's flash when that file exists and from the frozen `TS.extcmd`
otherwise, so a new command can be tried by copying one file to the Pico
([boot.md](boot.md), "The dev overrides"). This module holds the contract
in its docstring, the three status numbers a handler needs, and two worked
examples, `tpi:.fact` and `tpi:.rndw`, which are also the firmware's test
of the data-answer and message-answer shapes. The tutorial is
[programmers-manual.md ch 11–12](../../manual/programmers-manual.md) (ch 10
for where a handler sits, ch 13 for turning one into a built-in); the
contract in reference form is [EXTCMD_PROTOCOL.md](../../EXTCMD_PROTOCOL.md),
with the wire side in [PROTOCOL.md §5 and §11](../../PROTOCOL.md).

## Map

| Lines | What |
|---|---|
| 1–34 | the docstring: the handler shape, the contract, the override, the two examples |
| 36–37 | `import math`, `from random import randint` |
| 39–45 | the import of the running firmware module as `tp` |
| 47–52 | `OK`, `F_BAD_NAME`, `NUM_TOO_BIG` |
| 55–71 | `FACTORIAL` |
| 74–89 | `WORDS`, `RND_WORD` |
| 92–95 | `EXT_SA_FUNCT` |

## How a command gets here

`TS2068_IO` loads the table once at boot, after `SA_funct` is built
(`tspico.py`, "Prefer the dev_extcmd override if present"):

1. `from dev_extcmd import EXT_SA_FUNCT`; on success the log says
   `Loaded EXT_SA_FUNCT from /dev_extcmd.py override`.
2. On `ImportError` (no override): `from TS.extcmd import EXT_SA_FUNCT`,
   logged as `Loaded EXT_SA_FUNCT from frozen TS.extcmd`.
3. Any other exception from that second import leaves `EXT_SA_FUNCT = {}`
   and logs `Unable to import external commands; using empty SA_EXT_CMD
   dictionary: …`.

The first `except` catches only `ImportError`, so an override file that
fails to compile or raises while it is imported (a `SyntaxError`, a
`NameError` at module level) propagates out of `TS2068_IO`'s boot to
`main.py`'s handler, which logs `FATAL ERROR` to `/activity.log` and stops
the Pico ([boot.md](boot.md)). A `/dev_tspico.mpy` built for another
MicroPython has a quieter effect: `main.py` falls back to the frozen
firmware on the `ValueError`, but this module's own `import dev_tspico`
raises the same `ValueError`, which is not an `ImportError`, so step 3 runs
and the external commands are silently absent (inferred from the three
import paths; no test covers it).

`PROCESS_CMD` then, for a `SAVE "tpi:…"` body, upper-cases the text after
`"D.."`, takes the command word up to the first space, and looks it up in
`SA_funct` first and `EXT_SA_FUNCT` second; a hit calls
`EXEC(MQ, TSP, pre, cmd)` with the module globals `MQ` and `TSP`, inside the
`try` whose `finally` is the tail (TX drained for up to 3 s, RX emptied,
the one `0x01` pre-load, the pre-header DMA re-armed, READY + IDLE). A
handler that raises gets Report J from `FAIL_CMD`; a BREAK during its
output raises `CmdAbort`, which empties both FIFOs; the tail runs in every
case (#42). The no-card gate does not apply: `SD_NEEDED` is true only for
built-ins outside `SD_FREE`, so an external command "decides for itself"
whether it needs the card, which it does by calling `tp.SD_CALL`. The word
compares case-insensitively because the dispatcher upper-cases it; the
leading dot is a convention that keeps external names clear of built-in
ones, which are matched first. `tpi:help` lists the loaded keys under
"External commands loaded are:" ([tspico-commands.md](tspico-commands.md)).

## The handler and its helpers

A handler is `def HANDLER(MQ, TSP, pre, cmd)`: `pre` is the 10-byte
pre-header, `tp.PARAMS(pre)` the two `CODE` numbers; `cmd` is `"D.."` plus
the command text with its case kept, `tp.getArgs(cmd)` the text after the
word; `TSP` the `PICO_STATUS` ([tspico-state.md](tspico-state.md)); `MQ`
the port state machine at the time of the call, stale after any SD card
work because `ACTIVATE_MQ` rebuilds it, which is why the helpers are used
instead.

The helpers come from the firmware module that is running, imported as a
module, not by name, so that `tp.MQ` is always the live one:

```python
try:
    import dev_tspico as tp
except ImportError:
    import TS.tspico as tp
```

With the frozen firmware, `TS.tspico` is already in `sys.modules` from
`main.py`, so no second import happens. The contract the docstring sets
out, in the order it gives: exactly one answer (a status byte, a `SEND_MSG`
with `force`, function 81h; `SEND_MSG2`, 86h; or data) with the first bytes
in the FIFO before `MQ_READY`; never the `0x01` pre-load, which the tail
writes; bytes queued with `CMD_PUT`, which waits while the 4-deep FIFO is
full and turns a BREAK into `CmdAbort`, never to be caught; SD card work
inside `SD_CALL`, before the answer. The helpers themselves are
`tspico.py`'s: `CMD_PUT`, `MQ_READY`, `CH_READY` in
[tspico-bus.md](tspico-bus.md); `SEND_MSG`, `SEND_MSG2`,
`SEND_MSG_PROMPT_YN` in [tspico-messages.md](tspico-messages.md);
`SD_CALL`, `PARAMS`, `getArgs`, `LOG` in [tspico-files.md](tspico-files.md)
and [tspico-dispatch.md](tspico-dispatch.md).

**The data-answer convention.** A handler that returns bytes for the
caller's own code to read uses the `tpi:chrd` layout: status 1, a count,
the bytes, their XOR. The ROM takes the 1 as "0 OK" and returns to BASIC,
which then reads the rest with `IN 14` (or `GET_DATA` in machine code,
programmer's manual 4.5 and 5.5–5.6):

```basic
10 SAVE "tpi:.fact" CODE 20,0
20 LET c=IN 14: LET m$=""
30 FOR i=1 TO c: LET m$=m$+CHR$ IN 14: NEXT i
40 LET x=IN 14: PRINT m$
```

The first byte must stay below 80h: a byte of 80h or more is a response
function, the ROM handles 81h–88h, and anything else is
Report D with the data never read (EXTCMD_PROTOCOL.md §4,
[appendix/ports-and-status.md](../appendix/ports-and-status.md)). Bytes a
program leaves unread are cleared by the next command's SYNC.

## `OK`, `F_BAD_NAME`, `NUM_TOO_BIG`

| Constant | Value | Report |
|---|---|---|
| `OK` | 1 | 0 OK |
| `F_BAD_NAME` | 3 | F Invalid file name |
| `NUM_TOO_BIG` | 6 | 6 Number too big |

Why a handler keeps its own: `tspico.py`'s `_1_OK`, `_3_F_Invalid_file`,
`_6_Number_too_big` and the rest are underscore `const()`s, which
MicroPython inlines and never stores on the module. `tp._1_OK` works on a
PC and raises `AttributeError` on the Pico, Report J; the first rewrite of
`.fact` did exactly that. `extcmd_hosttest.py` therefore hands this module a
`tp` stripped of every `_N_…` name, as the Pico presents it. The full map
of status numbers to reports is in
[appendix/ports-and-status.md](../appendix/ports-and-status.md).

## `FACTORIAL(MQ, TSP, pre, cmd)`

`n!` as a data answer, the `tpi:chrd` format. `n` is the first `CODE`
number, `tp.PARAMS(pre)[0]`:

1. `n > 32`: `tp.CMD_PUT(NUM_TOO_BIG)`, `tp.MQ_READY()`, return. The 2068
   gets Report 6. The comment's reason: 33! has 37 digits, "keep it short";
   the audit (§3) notes that the bound is now a documentation, test and
   BASIC choice, since the count byte could carry up to 146!'s 255 digits (147! has 257;
as AUDIT-2026-09-30.md says).
2. `digits = str(math.factorial(n)).encode()`, at most 36 bytes for 32!,
   and `x`, their XOR.
3. `tp.CMD_PUT(1)` (status: data follows), `tp.CMD_PUT(len(digits))`, then
   `tp.MQ_READY()`: the first two bytes are in the FIFO before READY, so the
   Z80's first read cannot find it empty.
4. Each digit and then `x` through `tp.CMD_PUT`, which waits while the
   4-byte FIFO is full as the Z80 drains it.

Nothing is written to the state; no SD card. Pinned by
`extcmd_hosttest.py` through the real `PROCESS_CMD`: for n = 0, 5, 20 and
32 the TX log is `[1, len] + digits + [xor, 1]`, the final 1 being the
tail's single pre-load; for 33 it is `[6, 1]`. The BASIC program
`basic/SD/TAP/test/factorial.bas` (`SD card/TAP/test/factorial.tap`) is the
hardware check. Before #91 this answered a message and then more bytes, two
answers whose orphans corrupted the next command (EXTCMD_PROTOCOL.md's
history note; the test's docstring).

## `WORDS`

`"/words.txt"`: the word list on the Pico's flash root, one word a line
with CR LF endings (`src/words.txt`, 10,000 lines; the release bundle, the
web updater's `pico/` payload and the README's deploy table put it at
`/words.txt`). Only `RND_WORD` reads it; `extcmd_hosttest.py` rebinds it to
the repo copy and then to a non-existent path.

## `RND_WORD(MQ, TSP, pre, cmd)`

A random word from `WORDS`, as a message the ROM prints:

1. Open the file read-only in binary; seek to the end for its size; seek to
   `randint(0, max(0, size - 64))`; `readline()` once to skip the line the
   seek probably landed inside; the next `readline()`, stripped and
   decoded, is the word, or `"the"` when it is empty (a seek that landed in
   the last line, or a file shorter than two lines).
2. `tp.SEND_MSG(word, "", OK, True)`: function 81h with `force`, printed
   whether VERBOSE is on or not, status 1.
3. An `OSError` (no `/words.txt`) answers `tp.SEND_MSG("No /words.txt on the
   Pico", "", F_BAD_NAME)` without `force`: Report F, the text shown only
   when VERBOSE is on.

The 64-byte window always leaves at least one whole line after the skipped
one on the shipped list, whose longest lines are far shorter. Flash files
need no `SD_CALL`. Pinned by `extcmd_hosttest.py`: twenty runs each give
`[0x81, 1, 0x0D] + word + [0, 1]` with a word from the file and no stray
zero, and a missing file gives `[3, 1]`. `basic/SD/TAP/test/RND WORDS.bas`
is the hardware check. Before #91 this answered `01h` and then the word as
extra bytes.

## `EXT_SA_FUNCT`

```python
EXT_SA_FUNCT = {
    "TPI:.FACT": FACTORIAL,
    "TPI:.RNDW": RND_WORD,
}
```

The table `TS2068_IO` imports and `PROCESS_CMD` searches second. Keys are
the upper-case command word with its `TPI:`; a key with a trailing space
would never match, since the dispatcher cuts the word at the first space.
The imported name becomes `tspico`'s global `EXT_SA_FUNCT` (declared
`global` in `TS2068_IO` and `GETHELP`), passed to every `PROCESS_CMD` call.
Two tests stand in for it: `sd_wedged_hosttest.py` (and
`dir_files_eio_hosttest.py`) register an empty `dev_extcmd` module before
importing `tspico`, because the real one imports the firmware module back
(`dev_tspico` or `TS.tspico`, at load) and those tests need none of its
commands; `extcmd_hosttest.py` uses the real table. (Until #183 their comment
gave a reason from the #65 version: annotations with `StateMachine`.)

### `tpi:.fact`

`SAVE "tpi:.fact" CODE n,0`: `FACTORIAL`. `n` from 0 to 32 answers status
1, the digit count, the digits and their XOR, read by the program with
`IN 14`; `n` above 32 is Report 6. The word is matched as `TPI:.FACT`.

### `tpi:.rndw`

`SAVE "tpi:.rndw"`: `RND_WORD`. Prints a random word from `/words.txt`;
with no such file, Report F.

## Keeping the two copies the same

`src/dev_extcmd.py` is the file a developer copies to the Pico as
`/dev_extcmd.py` (`tools/pico-serial.py break`, `put`, `softreset`, with
the 2068 off; EXTCMD_PROTOCOL.md §6, programmer's manual 11.6).
`src/test/dev_sync_hosttest.py` fails CI when it differs from
`src/TS/extcmd.py` other than in line endings; `cmp` reports the two as
different because `.gitattributes` checks out `src/TS/*.py` with CRLF and
`src/dev_extcmd.py` with LF. To add a command permanently, edit
`src/TS/extcmd.py` and `cp` it over `src/dev_extcmd.py`. A `/TS/extcmd.py`
on the flash is never the answer: a `/TS/` folder there shadows the whole
frozen package ([boot.md](boot.md)).
