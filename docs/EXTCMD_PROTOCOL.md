# External Commands (`TPI:.XXX`)

External commands let you add a `tpi:` command to the TS-Pico without touching
`tspico.py`, and try it without rebuilding the firmware. This document is the
contract they follow. It matches `src/TS/extcmd.py` and
`src/test/extcmd_hosttest.py`; the wire format is in
[`PROTOCOL.md`](PROTOCOL.md) §5 and §11.

> Earlier versions of this document (status "UNDER DEVELOPMENT") described how
> the dual-port pre-load chain broke the original examples, and asked what the
> ROM does with unknown function codes. Both are settled: the examples were
> rewritten to give one answer each, and the ROM's answer is in §4 below.

## 1. Where they live

| File | Loaded | Use |
|------|--------|-----|
| `src/TS/extcmd.py` | frozen into the UF2, imported by `TS2068_IO()` | the shipped commands |
| `/dev_extcmd.py` on the Pico's flash (repo: `src/dev_extcmd.py`) | **instead of** the frozen module, when present | trying commands without a rebuild; delete it to go back |

Don't put a `/TS/extcmd.py` on the flash: a `/TS/` folder there shadows the
whole frozen `TS` package. The repo keeps `src/dev_extcmd.py` identical to
`src/TS/extcmd.py`; `src/test/dev_sync_hosttest.py` fails CI if they drift.

`SAVE "tpi:help"` lists the external commands that loaded.

## 2. Shape of a command

```python
def HANDLER(MQ, TSP, pre, cmd):
    ...

EXT_SA_FUNCT = {
    "TPI:.NAME": HANDLER,
}
```

- **The key** is the command word, upper case, with its `TPI:`. The dispatcher
  upper-cases what the 2068 sent and splits at the first space, so
  `SAVE "tpi:.name args"` finds `"TPI:.NAME"`. The leading dot is a convention
  that keeps external names clear of built-in ones; built-ins are looked up
  first.
- **`pre`** is the 10-byte pre-header: `tp.PARAMS(pre)` gives the two `CODE`
  numbers.
- **`cmd`** is `"D.."` + the command text; `tp.getArgs(cmd)` gives the text
  after the command word, case kept.
- **`TSP`** is the firmware's state (`TSP.cur_path`, `TSP.VERBOSE`,
  `TSP.f_name`, ...).
- **`MQ`** is the port state machine at the time of the call. SD card work
  rebuilds it, so use the helpers below rather than `MQ` directly.

Import the helpers from the firmware module that is running, as a module:

```python
try:
    import dev_tspico as tp      # the dev override, if one is on the flash
except ImportError:
    import TS.tspico as tp       # the frozen firmware
```

## 3. The contract

1. **Exactly one answer.** A status, a message, scrolling text, a prompt, or
   data (§4). Not zero (the 2068 waits ~20 s, then Report J) and not two (the
   second is read by the next command in the wrong place).
2. **Never write the `0x01` pre-load.** `PROCESS_CMD`'s tail writes it after
   your handler returns, raises or is stopped by BREAK.
3. **Queue with `tp.CMD_PUT(b)`**, not `MQ.put`: it waits while the 4-byte FIFO
   is full and turns a BREAK into `CmdAbort`. Never catch `CmdAbort` (it is a
   `BaseException` for that reason).
4. **Data first, then READY.** Queue the first bytes, then `tp.MQ_READY()`,
   then the rest. The helpers in §4 do this for you.
5. **SD card work inside `tp.SD_CALL(fn, *args)`, before the answer.** The
   card shares GPIO 2–4 with the data bus; `SD_CALL` switches the pins and
   always gives them back. An `OSError` comes back as
   `("SD card error", 3)`.
6. **Errors are statuses** (§4). An exception that escapes becomes Report J.
7. **No `print()` or logging in a loop that feeds the 2068.** Use `tp.LOG`
   before or after.

## 4. Answers

| You want | Call | The 2068 |
|----------|------|----------|
| OK or an error | `tp.SEND_MSG(msg, "", st)` | reports `st`; shows `msg` only when VERBOSE is on |
| OK or an error, never printed | `tp.CMD_PUT(st); tp.MQ_READY()` | reports `st` |
| a message | `tp.SEND_MSG(msg, msg1, st, True)` | prints it (function `$81`) |
| a long text | `tp.SEND_MSG2(text, st)` | prints it with "Scroll?" pages (`$86`) |
| a yes/no | `key = tp.SEND_MSG_PROMPT_YN(prompt)` | asks; `key` is the answer. Send nothing after it. |
| data | `tp.CMD_PUT(1); tp.CMD_PUT(n); tp.MQ_READY()`, then `n` bytes and their XOR | returns OK from the `SAVE`; the program reads the rest with `IN 14` (or machine code) |

Statuses: `tp._1_OK`, `_2_R_Tape_load`, `_3_F_Invalid_file`,
`_4_Q_Parameter`, `_5_C_Nonsense`, `_6_6_Num2Big`, `_7_8_EOF`,
`_8_A_Invalid_arg`, `_9_9_STOP`, `_10_J_Invalid_IO`, `_11_D_Break`. They
become the BASIC report of the same letter.

**Function codes.** A first byte of `$80` or more is a response function. The
ROM handles `$81`–`$87` (and `$88` on ROM 2.1); **any other code is Report D**,
and the bytes behind it are never read. So don't invent codes: a data answer
starts with a status (1), which the ROM takes as OK, and the program reads the
data after that.

**Data format.** Use the `tpi:chrd` layout, `1, n, n bytes, XOR`, so the same
2068 code reads every data answer: the programmer's manual's `GET_DATA`, or in
BASIC:

```basic
10 SAVE "tpi:.fact" CODE 20,0
20 LET c=IN 14: LET m$=""
30 FOR i=1 TO c: LET m$=m$+CHR$ IN 14: NEXT i
40 LET x=IN 14: PRINT m$
```

A program that leaves bytes unread does no lasting harm on ROM 2.0 and later:
the next command's SYNC clears them.

## 5. The examples

`src/TS/extcmd.py`:

- **`.fact`** — `SAVE "tpi:.fact" CODE n,0` answers *n*! (0–32) as data:
  `1, count, digits, XOR`. *n* > 32 answers status 6 (Report 6). Test program:
  `SD card/TAP/test/factorial.tap` (source `basic/SD/TAP/test/factorial.bas`).
- **`.rndw`** — `SAVE "tpi:.rndw"` prints a random word from `/words.txt` on
  the flash (a forced `SEND_MSG`); no file: status 3 (F). Test program:
  `RND WORDS.tap`.

`src/test/extcmd_hosttest.py` runs both through the real `PROCESS_CMD` and
checks every byte, including the single pre-load at the end.

## 6. Installing a command for a try

1. Switch the TS-2068 off (the Pico runs from USB power).
2. Copy your file to the Pico as `/dev_extcmd.py`:
   `tools/pico-serial.py break`, then
   `tools/pico-serial.py put path/to/dev_extcmd.py /dev_extcmd.py`, then
   `tools/pico-serial.py softreset` (or use Thonny, then close it).
3. Reseat the SD card if it doesn't mount, and switch the 2068 on.
4. `SAVE "tpi:help"` should list your command.

To make it permanent, move it into `src/TS/extcmd.py` (and copy that file over
`src/dev_extcmd.py`), or turn it into a built-in (`PROTOCOL.md` §11).
