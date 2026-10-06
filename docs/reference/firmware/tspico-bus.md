# TS/tspico.py (part 2) — who owns the bus

Source: [`src/TS/tspico.py`](../../../src/TS/tspico.py), lines 676–1372
(the handover, the command I/O helpers, the SD card's state, the LED),
2669–2727 (`SD_CALL` and the no-card gate) and 3228–3260 (the channel
replies).

GPIO 2, 3 and 4 are two things at once: bits D0–D2 of the 2068's data bus
(through the U6 buffer) and the SD card's SPI clock, MOSI and MISO. Only one
of them can have the pins at a time. This part of the file is the code that
hands them over, and everything that has to know which side has them: the
helpers that put command output into the bus state machine's TX FIFO
without ever blocking, the record of which SD card is in (if any), and what
a command answers when it needs a card and there is none. The state these
functions read and write — `MQ`, `sd_active`, `TSP.sd_present`, `TSP.sd_cid`
and the rest — is documented once, in [tspico-state.md](tspico-state.md);
this chapter says what the functions do with it. The PIO programs are in
[pio.md](pio.md) (`TS_IO_DUAL`, `NULL_SM`), the low-level FIFO primitives
(`MQX`, `MQ_STATUS`, `TX_ROOM`, `STREAM_DMA`, `RX_WORD`) in
[tspico_io.md](tspico_io.md), the SD driver in [sdcard.md](sdcard.md), and
the operation end to end in [the SD handover flow](../flows/sd-handover.md).

Three words used throughout. **MQ** is the bus state machine, PIO0 state
machine 0, and the module global that holds it. The **Y register** is what
the Z80 reads on port 0Fh: `0xFF` READY and IDLE, `0xF7` READY with a
transaction open ("mid"), `0xFB` READY + IDLE with RECOVERED low, `0` BUSY;
the PIO drops it to `0` by itself after every Z80 OUT
([PROTOCOL.md §3](../../PROTOCOL.md#3-the-status-byte)). The **pre-load**
is the one `0x01` that waits in TX between transactions for the ROM to read
with no wait straight after its pre-header
([PROTOCOL.md §4.2](../../PROTOCOL.md#42-the-pre-load-byte)).

## Map

| Symbol | Line | Role |
|---|---|---|
| `DEACTIVATE_SD()` | 691 | unmount `/sd`, CS high, clamp GPIO 2–4 low |
| `ACTIVATE_MQ()` | 751 | rebuild `TS_IO_DUAL` on state machine 0: TX empty, Y BUSY |
| `MQ_READY()` | 820 | Y = READY + IDLE |
| `CmdAbort` | 868 | the exception that ends a command whose Z80 has gone |
| `CMD_PUT(b)` | 885 | one byte into TX, waiting (bounded, listening) for room |
| `CMD_SEND(buf, ready)` | 895 | a page into TX: by DMA, or the first four bytes, READY, the rest |
| `CmdOut` | 923 | a page built in RAM, sent with `CMD_SEND` |
| `CmdOut.__init__(self)` | 933 | an empty page |
| `CmdOut.__call__(self, x)` | 936 | append a byte or a string |
| `CmdOut.send(self, ready=True)` | 942 | send what was built; READY |
| `CMD_KEY()` | 951 | the Z80's key at a prompt; BREAK raises |
| `CMD_DRAIN()` | 962 | wait until the Z80 has read TX; BREAK raises |
| `PRELOAD_READ(ms=100)` | 974 | wait for the Z80 to read the pre-load before a rebuild |
| `CMD_RX_FLUSH()` | 986 | empty RX before a key wait; a 0Fh write raises |
| `CMD_FLUSH()` | 1001 | empty both FIFOs after a `CmdAbort` |
| `MQ_BUSY()` | 1016 | Y = BUSY |
| `ACTIVATE_SD(tries=None)` | 1066 | park the MQ, U6 off, mount the card (retried), note the card |
| `SAVE_MOUNT()` | 1160 | `tspico_io.SD_MOUNT`: the SAVE writes' mount |
| `SD_NOTE_CARD(cid)` | 1179 | record the card; a returned or different card → `SD_REVALIDATE` |
| `SD_REVALIDATE(changed)` | 1211 | repair the state that belonged to the old card |
| `LISTING_SIG(entries)` | 1255 | a folder listing's fingerprint |
| `LISTING_FRESHEN()` | 1263 | re-read the folder if the card's copy changed |
| `LISTING_CHECK()` | 1283 | mount, `LISTING_FRESHEN`, hand back |
| `REFRESH_LISTING()` | 1300 | re-read the folder after a ZX48 SAVE |
| `SD_PROBE(tries=None)` | 1321 | is there a card? mount, unmount, hand back |
| `BLINK_ERROR()` | 1337 | ten 0.1 s LED toggles |
| `BLINK_LED(pause)` | 1352 | the boot blink on core1 |
| `SD_CALL(fn, *args)` | 2669 | run `fn` with the card, always hand back; errors → (message, status) |
| `SD_NEEDED(load_cmd, cmd_word, cmd_exec, SA_funct)` | 2704 | does this command need the card? |
| `NO_CARD_REPLY(cmd_word)` | 2713 | the answer when it does and there is none |
| `REFRESH_IF(*dirs)` | 2722 | re-list the current folder if a disk command touched it |
| `CH_READY()` | 3228 | READY without IDLE, for the channel driver |
| `CH_REPLY(st)` | 3241 | a bare status, never a message |
| `CH_CALL(fn, *args)` | 3251 | a channel operation under `SD_CALL`; `ChannelError` → its report |

Between `MQ_BUSY` (1016) and `SD_TRY_MS` (1063) the file keeps a comment
block listing three single-port helpers that are gone (`WAIT_TX_RECEIVED`,
`EMPTY_TX_FIFO`, `EMPTY_RX_FIFO`) and where their call sites went; the
module variables of this range (`_CMD_ECHO`, `CMD_STALL_MS`, `KEY_WAIT_MS`,
`SD_TRY_MS`, `SD_FREE`, `SD_QUIET`, `CHANNELS`, `CH_STATUS`) have their
entries in [tspico-state.md](tspico-state.md).

## The bus and how it changes hands

The pins, as the code drives them ([hardware.md](../hardware.md) has the
full table):

- **GPIO 2–9** are the Z80's D0–D7 through U6; `TS_IO_DUAL` uses them as
  its `out`/`in` pins. GPIO 2–4 are also `SPI(0)`'s SCK, MOSI and MISO.
- **GPIO 12** enables U6, active low. `TS_IO_DUAL` drives it by side-set,
  low only for the length of a Z80 cycle on ports 0Eh/0Fh; outside a cycle,
  and whenever the card has the pins, it is high and the Pico is off the
  2068's bus.
- **GPIO 28** is the card's chip select (U3_CS), high when idle.

There are two states, and the global `sd_active` says which one the board
is in:

| | `MQ` is | GPIO 2–4 | GPIO 12 | Y | Made by |
|---|---|---|---|---|---|
| MQ (the normal state) | `TS_IO_DUAL`, 30 MHz, running | the PIO's | the PIO's side-set | as Python and the PIO set it | `ACTIVATE_MQ` |
| SD | `NULL_SM`, 15 MHz, stopped | `SPI(0)` | GPIO output, high | none: the program is gone, the Z80 reads whatever the parked bus gives *(inferred: U6 is off, so not the Pico)* | `ACTIVATE_SD` |

Every SD access goes MQ → SD → MQ with the same three calls:

```python
ACTIVATE_SD()      # park the MQ, U6 off, mount
...                # work on /sd
DEACTIVATE_SD()    # unmount, CS high, clamp GPIO 2-4 low
ACTIVATE_MQ()      # TS_IO_DUAL back on state machine 0; TX empty, Y BUSY
```

`SD_CALL`, `SD_PROBE`, `LISTING_CHECK` and `REFRESH_LISTING` wrap the
pattern with the last two in a `finally`; handlers that need the card for
longer write it out themselves, and `FAIL_CMD`
([tspico-dispatch.md](tspico-dispatch.md)) does the last two for any handler
that raised while `sd_active` was `True`.

What the Z80 sees meanwhile: it has sent a pre-header and is polling port
0Fh for READY, for up to ~19.9 s before it gives Report J
(`WAIT_PICO_READY`, [../rom/exrom-driver.md](../rom/exrom-driver.md)). An SD
access is a few hundred milliseconds (a mount ~0.1–0.3 s, the comments say),
so the Z80 is simply kept waiting. Three things follow, and each was a bug
before it was a rule:

1. **Rebuilding the state machine empties its FIFOs.** A pre-load still in
   TX is lost. Before a rebuild the caller waits for it to be read
   (`PRELOAD_READ`) and puts it back if it was not.
2. **Y must be BUSY when the program comes back, and stay BUSY until the
   reply is in TX.** Otherwise the Z80, which has been polling all along,
   reads an empty TX as `00` and reports J (`ACTIVATE_MQ`).
3. **Nothing may be put into a parked state machine.** It never reaches the
   Z80, and after four words `put()` blocks for good
   ([pio.md](pio.md#null_sm)).

## `DEACTIVATE_SD()`

Ends SD access and leaves the shared pins in a known state for
`ACTIVATE_MQ`, which must follow at once.

1. `os.umount("/sd")`; an exception (nothing mounted) is ignored with a
   `TLM` line, so it is safe to call whether or not a mount succeeded.
2. GPIO 28 (U3_CS) to an output, pulled up, driven `1`: the card is
   deselected.
3. GPIO 2, 3 and 4 to outputs driven `0`.

Why it exists: in the single-port firmware this teardown was inline at the
top of `ACTIVATE_MQ`, as a loop `while True: try: os.umount; except: break`
that cost about 10 ms on every call that had no mount to undo (the comment
at 676–690). The dual-port rewrite split it out so the boot path and the
SAVE branch can call `ACTIVATE_MQ` on its own, and so the order is fixed:
callers must call `DEACTIVATE_SD()` first, then `ACTIVATE_MQ()`.

The clamp. The comment above the function (686–689) still calls it the fix
for the original Report D, a floating D6; the comment in the body (703–709)
corrects that: D6 is GPIO 8, which this never touched, and since #61 U6
keeps the 2068 off GPIO 2–4 during SD use anyway. It is kept as harmless;
whether it is needed at all is an open question for a scope (audit §4,
[AUDIT-2026-09-30.md](../../AUDIT-2026-09-30.md)). The body is right and the
header comment is stale. The comment at the boot call site (6281–6287)
repeats the stale claim.

Takes nothing, returns `None`. Touches the mount table and GPIO 2–4, 28.
Callers: every SD access (the call list in the map of
[tspico-dispatch.md](tspico-dispatch.md), the handlers in
[tspico-files.md](tspico-files.md), [tspico-commands.md](tspico-commands.md)
and [tspico-disk.md](tspico-disk.md)), the boot sequence in `TS2068_IO`, and
`FAIL_CMD`. ZX48 mode has its own pair in `tspico_io`, `ENA_SD` and
`ENA_MQ_DUAL` ([tspico_io.md](tspico_io.md)), which follow the same order.

Beware: it does not touch GPIO 12 or `sd_active`. U6 stays off (as
`ACTIVATE_SD` left it) until `ACTIVATE_MQ` gives the pin back to the PIO,
and `sd_active` stays `True` until then — which is how `FAIL_CMD` knows to
finish the handover if a handler raised in between.

## `ACTIVATE_MQ()`

Gives the bus back to the Z80: builds `TS_IO_DUAL` on state machine 0,
starts it, and sets Y BUSY. Leaves TX empty and does **not** say READY.

1. `sd_active = False`.
2. `MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000,
   out_base=Pin(2, Pin.OUT), in_base=Pin(2, Pin.IN), jmp_pin=Pin(11),
   sideset_base=Pin(12, Pin.OUT))`. A new object on the same hardware state
   machine: the program is loaded, the FIFOs are cleared, and the pins
   named go back to the PIO — GPIO 2–9 as data, GPIO 11 (R/W, [hardware.md](../hardware.md)) as the jump pin, GPIO 12 (U6) as the
   side-set pin.
3. `MQ.active(1)`.
4. `MQ_BUSY()`: `set(y, 0)`.

Why each choice (the comment at 716–750 lists five changes from the
single-port version; DUAL_PORT_DEVELOPMENT.md tells the story):

- **`TS_IO_DUAL`, not `TS_IO`**: port 0Fh is answered from Y, port 0Eh from
  TX, so status no longer competes with data in one FIFO.
- **30 MHz, not 15**: the dual-port decode adds about seven instructions to
  the read path. The comment's justification that "RP2040 PIO can run up to
  half the CPU clock" is wrong — a PIO state machine can run at the full
  system clock, and `ROM`/`BANK` run at 150 MHz on the 270 MHz CPU
  ([pio.md](pio.md)). The 30 MHz figure stands on its own; the reason given
  for its being "conservative" does not.
- **Y BUSY, not READY.** The first dual-port version set Y READY here.
  Between that and the caller's first `put()`, the Z80 — which had been
  polling 0Fh through the whole SD access — saw READY, read 0Eh, found TX
  empty and got `00`: Report J. Handlers that answer at once never lost the
  race; handlers that did SD work first (`tpi:md`, `tpi:rm`, `MOUNT_FILE`,
  `NEW_TAP`, `GETHELP`) lost it reliably. The contract now is: `ACTIVATE_MQ`,
  then the reply into TX, then `MQ_READY` (the `SEND_MSG` family does the
  last two).
- **`MQ_BUSY()` explicitly.** A new `StateMachine` does not clear Y: it
  keeps whatever the last program on state machine 0 left there, so "Y is
  BUSY" was never guaranteed; a READY left over would let the Z80 read an
  empty TX as `00`. The explicit `set(y, 0)` was added by the 2026-09-30
  audit (§4) and costs about 18 µs.
- **No pre-load.** `ACTIVATE_MQ` runs at boot and in the middle of
  commands. Mid-command, the next thing the caller does is put its own
  status into TX; a pre-load added here would leave two `0x01`s, the Z80
  would read one, and the other would sit in TX to be misread later — the
  orphan-byte family of bugs, "Bug 1" in
  [DUAL_PORT_DEVELOPMENT.md §8](../../DUAL_PORT_DEVELOPMENT.md#8-the-three-latent-bugs-we-discovered-post-migration).
  The boot pre-load is staged once, by `TS2068_IO`.

Takes nothing, returns `None`. Writes `MQ` and `sd_active`. Called after every SD access in this
file (two dozen sites), and at boot by `TS2068_IO` (6289) after the first
card check. `tspico_io` never calls it; its comments name it because the
dispatcher's call is what ends a SAVE or LOAD there, and ZX48 mode uses
`ENA_MQ_DUAL` instead.

Beware:

- `MQ.active(1)` comes before `set(y, 0)`, so for the ~18 µs between them Y
  is whatever was left in it *(inferred: the code orders them this way; a
  `set` executed on the stopped machine before `active(1)` would close the
  window)*. On every path through `ACTIVATE_SD` the state machine last ran
  `NULL_SM`, a `nop`, which does not touch Y, so the leftover is the value
  `TS_IO_DUAL` had before the SD access — normally BUSY, since the Z80's
  pre-header OUTs dropped it.
- Anything in TX before the call is gone. See `PRELOAD_READ`.
- The `MQ` object is new. Code holding the old one (a local, a tuple
  element) is talking to nothing; the functions in `tspico_io` take `MQ` as
  a parameter and hand it back in their return tuples for this reason
  ([tspico-state.md](tspico-state.md#mq)).

## `MQ_READY()`

Says READY: `MQX(MQ, "mov(y, invert(null))")`, Y = `0xFFFFFFFF`, which the
Z80 reads on 0Fh as `FFh` — READY (bit 6) and IDLE (bit 3) both set. Its
twin with IDLE clear is `CH_READY`; with RECOVERED low, `MQ_STATUS(MQ,
"recovered")` in [tspico_io.md](tspico_io.md#mq_statusmq-st).

The contract it implements (the docstring, and
[DEVELOPER_GUIDE.md §7](../../DEVELOPER_GUIDE.md#7-the-pio--micropython-ready-contract)):
the PIO drops Y to 0 after every Z80 write to 0Eh or 0Fh (issue #14), so
after any OUT the Z80 waits; Python calls `MQ_READY()` once the reply is in
TX, or once it expects no more input, and only then. Data in TX first, then
READY. In the single-port firmware "ready" was a `0x40` byte written into
TX, interleaved with the data; every `wrt(0x40)` of that code became a call
of this function.

Why `invert(null)` and not `~null`: the tilde form does not parse through
`sm.exec()` at run time on MicroPython 1.20, confirmed at the REPL, nor on
1.29, where `rp2`'s `null` is a plain number.

No logging and no `TLM`, deliberately: it runs on receive paths where a
`print()` (1–10 ms) is long enough for the 4-deep RX FIFO to overflow
(the comment at 816–818).

Callers: the docstring's list (the `PROCESS_CMD` tail, the SAVE path's
final status, `SEND_MSG`/`SEND_MSG2`/`SEND_MSG_PROMPT_YN`, `ListMenu`,
`ZX48_IO`'s echo, `extcmd` handlers that return data) is still right, plus
`CMD_SEND` and `CmdOut.send` (when no DMA channel says it for them),
`FAIL_CMD`, and `STREAM_DMA` as the callable `CMD_SEND` hands it.

## Command I/O that never blocks

Everything a command prints, and every key it waits for, goes through the
helpers in this section (issue #51, stage 4; the comment at 850–867).

Before them, command output used `MQ.put()`, which blocks for good once the
4-deep TX FIFO is full and the Z80 has stopped reading — and no watchdog
covers commands. The 1.8b ROM's BREAK at a "Scroll? (Y/n)" prompt or a menu
key wait arrives as a port-0Fh write (word `0x103`); `MQ.get()` handed it
back as a key, `SEND_MSG2` took it for "next page" and wrote the erase and
the next page into a TX nobody read. The Pico hung until reset.

The contract now:

- **Bytes** go through `CMD_PUT` (one at a time) or `CMD_SEND`/`CmdOut`
  (a page). When TX is full they wait in `TX_ROOM`, bounded by
  `CMD_STALL_MS`, listening to RX.
- **Keys** come through `CMD_KEY`, bounded by `KEY_WAIT_MS`. Before a key
  wait, `CMD_RX_FLUSH` empties RX; after a page, `CMD_DRAIN` waits until
  the Z80 has read it.
- **A 0Fh write** (BREAK, or the next command's SYNC after a 2068 reset)
  or **a Z80 that stopped reading** raises `CmdAbort` from any of them.
- **`PROCESS_CMD` catches it** ([tspico-dispatch.md](tspico-dispatch.md),
  6004): `CMD_FLUSH` empties both FIFOs, the log says which of the two it
  was, and the tail stages the one pre-load and says READY + IDLE — or
  RECOVERED when the Z80 went silent. READY + IDLE is what the 2.x ROM's
  `BRK_ABORT` waits for before it gives Report D
  ([../rom/exrom-sync.md](../rom/exrom-sync.md)).

[`cmd_io_hosttest.py`](../../../src/test/cmd_io_hosttest.py) runs the
production `PROCESS_CMD`, `SEND_MSG` and `SEND_MSG2` against a simulated
Z80 and PIO with 4-deep FIFOs and fails on any `put()` into a full TX. It
pins a short command and a multi-page listing ending with TX = `[01]`, RX
empty, Y `FF`; BREAK at a "Scroll?" prompt stopping the handler at once;
a Z80 that stops reading mid-listing ending in RECOVERED; and BREAK or SYNC
during the command body going straight back to idle.

### `CmdAbort`

`class CmdAbort(BaseException)`, no body. `args[0]` is why, in `TX_ROOM`'s
codes: `1` a port-0Fh write (BREAK or SYNC), `3` the Z80 stopped reading
(TX stayed full, or no key came, for the limit).

Raised by `CMD_PUT`, `CMD_SEND`, `CMD_KEY`, `CMD_DRAIN` and
`CMD_RX_FLUSH` here, and directly by `CH_READ` (3363) and `BLKRCV` (4043)
when their own `STREAM_DMA`/`TX_ROOM` calls report a non-zero code. Caught
by `PROCESS_CMD` (6004), which records the code in `cmd_abort` for its tail.

Why a `BaseException`: so that a handler's `except Exception:` cannot
swallow it and carry on writing to a Z80 that has gone. Handlers are full
of `except Exception` (card errors, bad arguments); `GETLOG` relies on
this (its comment at 4717–4726: `SEND_MSG2` runs outside its `try`, so a
BREAK at the "Scroll?" prompt passes straight through), and so does
`TS2068_IO`'s outer loop (6394), which lets BaseExceptions — Ctrl-C from
the host, `CmdAbort` — pass. `extcmd.py`'s header (line 21) tells external
command writers never to catch it ([extcmd.md](extcmd.md)).

Beware: catching `BaseException` (or a bare `except:`) inside a handler
defeats it. A `CmdAbort` raised outside `PROCESS_CMD` (a command helper
called from somewhere else) is caught by nothing: `TS2068_IO`'s
restart loop lets BaseExceptions through, so it would reach `main.py` and
end the firmware *(inferred from the catch sites listed)*.

### `CMD_PUT(b)`

`MQ.put(b)` for command output, never blocking. If TX already holds
`TX_DEPTH` (4) words it zeroes `_CMD_ECHO[0]` and calls
`TX_ROOM(MQ, _CMD_ECHO, CMD_STALL_MS)`; a non-zero answer raises
`CmdAbort(why)`, else the byte goes in. `b` is an int (a byte); the FIFO
takes it as a word and `TS_IO_DUAL` outputs bits 0–7.

Stray writes from the Z80 while it waits (a key pressed while a listing is
still going out) land in `_CMD_ECHO` and are dropped. Callers: `SEND_MSG`'s
`wrt` (2155, 2174), `CH_REPLY`, `CH_READ`'s short answer (3341), `BLKRCV`,
and `extcmd`'s helpers, which hand it to
external commands as their way of writing (`extcmd.py` 20, 59–71).

### `CMD_SEND(buf, ready)`

Puts a page of command output into TX for a ROM that reads it blind, and
says READY at the right moment. `buf` is a `bytearray`; `ready` is `True`
to say READY here.

The ROM prints each character as it reads it, with no ready-wait between
characters ([PROTOCOL.md §5.4](../../PROTOCOL.md#54-the-answer-a-response-function-status--80)).
`RST 10` is slow, but on MicroPython 1.29 a GC or a flash write can outlast
the four characters in the FIFO, and the ROM then prints whatever it reads
from an empty one. So the page is built in RAM first, and:

- **With DMA** (`tspico_io._DMA` is not `None`): zero `_CMD_ECHO[0]`, then
  `STREAM_DMA(MQ, buf, _CMD_ECHO, CMD_STALL_MS, MQ_READY if ready else
  False)`. The channel feeds the FIFO from `buf` in hardware whatever core0
  does, and `STREAM_DMA` calls `MQ_READY` once the channel is running. A
  result `(why, …)` with `why` non-zero raises `CmdAbort(why)`; `why == 0`
  returns. A result of `None` (no free channel) falls through to:
- **By hand**: `CMD_PUT` the first `min(4, len(buf))` bytes, `MQ_READY()`
  if `ready`, then `CMD_PUT` the rest, each waiting for room as the Z80
  reads.

Either way the data is in TX before READY — the rule every handler keeps
([PROTOCOL.md §13](../../PROTOCOL.md#13-pitfalls)) — and the function
returns when the last byte is in the FIFO, not when the Z80 has read it;
`CMD_DRAIN` waits for that.

Callers: `SEND_MSG` (2214), `SEND_MSG2` (2420, 2460), and `CmdOut.send`;
all pass `ready=True`. `ready=False` is supported and unused.

### `CmdOut`

A page of command output collected in RAM and sent in one `CMD_SEND`:

```python
wrt = CmdOut()
wrt(0x86); wrt("text"); wrt(0x00)
wrt.send()          # into TX, READY, the rest as the Z80 reads it
key = CMD_KEY()
```

It exists so the prompts and menus — `PROMPT_EACH` (2739), `ListMenu`
(3472) and `SEND_MSG_PROMPT_YN` (5287), all printed by the ROM a character
at a time, blind — get the same treatment as `SEND_MSG2`'s pages: nothing
reaches TX before `send()`, and READY goes up only once the first bytes are
in (and, with DMA, the channel is running). Each `send()` sits where the
Pico would otherwise wait for the Z80: before a key read, and at the end.

#### `CmdOut.__init__(self)`

`self.b = bytearray()`: the page being built.

#### `CmdOut.__call__(self, x)`

Appends `x`: a `str` is UTF-8 encoded and extended (the callers pass the
2068's character set already mapped to single bytes by `xstr`, so in
practice one byte per character — see
[tspico-messages.md](tspico-messages.md)); anything else is appended as one
byte, so it must be an int 0–255. Called with the same arguments as
`CMD_PUT`, which is what lets the helpers write `wrt(...)` either way.

#### `CmdOut.send(self, ready=True)`

Takes the page and leaves `self.b` empty, so the object can build the next
page. A non-empty page goes to `CMD_SEND(b, ready)`; an empty one, with
`ready`, is just `MQ_READY()`. Raises `CmdAbort` as `CMD_SEND` does. Every
call in the file uses the default `ready=True`.

### `CMD_KEY()`

The Z80's key at a prompt: its `OUT (0Eh)` of the key code. Waits with
`RX_WORD(MQ, KEY_WAIT_MS)` (a day — the user may take as long as they
like). Returns `w & 0xFF`. A timeout (`-1`) raises `CmdAbort(3)`; a word
with `PORT_0F` (bit 8) set — the 1.8b-and-later ROM's BREAK at the key
wait, or a SYNC — raises `CmdAbort(1)`.

When it returns, the PIO has already dropped Y to BUSY (auto-busy after the
Z80's OUT), so the caller needs no `MQ_BUSY`; it puts the next page into TX
and says READY (`SEND_MSG2`'s comment at 2422–2430). Callers: `SEND_MSG2`
(2434), `PROMPT_EACH` (2754), `ListMenu` (3594), `SEND_MSG_PROMPT_YN`
(5306).

### `CMD_DRAIN()`

Waits until TX is empty — until the Z80 has read everything queued — but
bounded and listening: an RX word with `PORT_0F` set raises `CmdAbort(1)`,
and `CMD_STALL_MS` without TX emptying raises `CmdAbort(3)`. Any other RX
word (a stray key) is read and dropped. It replaces the
`while MQ.tx_fifo() != 0: pass` spins of the single-port code (the retired
`WAIT_TX_RECEIVED`). Callers: the tails of `SEND_MSG` (2224), `SEND_MSG2`
(2463), `PROMPT_EACH` (2764), `ListMenu` (3524, 3636) and
`SEND_MSG_PROMPT_YN` (5327).

Beware: it spins on `MQ.tx_fifo()` with no sleep; that is core0's whole
attention for as long as the Z80 takes to read four bytes, which on a
healthy bus is microseconds.

### `PRELOAD_READ(ms=100)`

Before anything that rebuilds the bus state machine (an SD access), waits —
at most `ms` milliseconds — for the Z80 to read the pre-load status it
reads with no wait straight after its pre-header. Returns `True` if TX is
empty by then. If it returns `False`, the rebuild will throw the byte away,
and the caller must `MQ.put(0x01)` again after the SD access.

Why: on hardware the Z80 reads the pre-load microseconds after the
pre-header, so the race was never seen there. In the emulator
([tools/emu](../../../tools/emu)), every port access is a round trip, and a
SAVE whose card check rebuilt the state machine first lost its pre-load and
gave up on its header (2026-10-04, the comment at 6570–6580). Callers:
`TS2068_IO` before `PRINT_FLUSH` writes buffered printer text (6524) and
before the SAVE branch's `SD_PROBE` (6581), both followed by the
`if _unread: MQ.put(0x01)`.

### `CMD_RX_FLUSH()`

Empties RX before a reply that will wait for keys, so an old byte is not
taken for a key — but a word with `PORT_0F` set found there raises
`CmdAbort(1)`, as `CMD_KEY` would. Bounded to 64 words.

Why it raises instead of draining: a plain drain swallowed the Z80's BREAK
(or the next command's SYNC). The Z80, waiting in its abort for READY +
IDLE, then got the listing's READY + IDLE, raised Report D, and left the
Pico sending to nobody until the next command's SYNC ended it — whose
pre-header was then lost: Report T (audit §4, "RX flushes on entry").
Callers: `SEND_MSG2` (2289), `PROMPT_EACH` (2740), `ListMenu` (3494),
`SEND_MSG_PROMPT_YN` (5293).

### `CMD_FLUSH()`

After a `CmdAbort`, empties both FIFOs, each loop bounded to 64 passes.
TX is emptied from the state machine's side, as the retired
`EMPTY_TX_FIFO` did: `pull(noblock)` then `mov(osr, null)` executed by
`MQX`, which takes a word out of TX into the OSR and then clears the OSR so
the program does not output it. RX is emptied with `MQ.get()`. It stages
no pre-load: `PROCESS_CMD`'s tail does that, once. One caller,
`PROCESS_CMD` (6009). `FAIL_CMD` has the same two loops inline.

### `MQ_BUSY()`

Says BUSY: `MQX(MQ, "set(y, 0)")`. The Z80 reads `00h` on 0Fh.

Its docstring says that, with the PIO's auto-busy, "nothing calls this
today". That is out of date: `ACTIVATE_MQ` calls it (767) since the
2026-09-30 audit, because a new state machine keeps the Y its predecessor
left. The code wins; the docstring's other reason — a path that must assert
BUSY without an inbound write — is the one that came true.

## The SD card's state

Since issue #43 the card is a state the firmware keeps, not a condition for
running: the TS-Pico boots and works without one, a command that needs one
says so, and putting a card in is all it takes to carry on. The state is
three `PICO_STATUS` fields ([tspico-state.md](tspico-state.md#pico_status__init__self-init_values)):

| Field | Meaning here |
|---|---|
| `sd_present` | a card answered the last mount. Decides how hard `ACTIVATE_SD` tries (5 attempts or 1) and whether a command must probe first |
| `sd_cid` | the card's identity, its CID register: `None` until a card has been seen, `0` when the driver could not read it |
| `sd_listing_ok`, `listing_stale`, `listing_sig` | whether the cached listing of the current folder is the card's (see `LISTING_FRESHEN`, `REFRESH_LISTING`) |

Every mount in the firmware goes through `ACTIVATE_SD` — the two SAVE
writes in `tspico_io` too, through `SAVE_MOUNT` — so it is the one place
that notices a card has gone, come back, or been swapped, and
`SD_NOTE_CARD` the one place that acts on it. ZX48 mode's own mount,
`ENA_SD`, also reaches `ACTIVATE_SD` through the same hook.
[`sd_state_hosttest.py`](../../../src/test/sd_state_hosttest.py) pins the
attempts, the revalidation, the no-card gate, `SD_CALL`'s answer and
`tpi:info`; [`sd_mount_hosttest.py`](../../../src/test/sd_mount_hosttest.py)
the retry loop at boot (its docstring's "the boot call keeps the blink
loop" is out of date: `TS2068_IO` catches the `OSError` and boots without a
card, 6261–6265); [`sd_recover_hosttest.py`](../../../src/test/sd_recover_hosttest.py)
the driver's recovery of a card left mid-transfer, which `ACTIVATE_SD`
reports ([sdcard.md](sdcard.md)).

### `ACTIVATE_SD(tries=None)`

Takes the pins from the Z80 and mounts the card on `/sd`. Returns the
`SPI` object; raises `OSError(19, …)` if no attempt succeeds.

1. `tries` defaults to 5 while `TSP.sd_present` is true and 1 once the card
   is known to be missing. With no card each attempt fails in about 0.5 s
   (the driver's `CMD0` timeout), so five tries would make every command
   that looks for a card stall ~5 s; with a card that refused once, five
   are worth it, because a cold card can refuse at first and be fine a few
   seconds later (the boot call passes `tries=5` explicitly for this).
2. Parks the bus: `MQ = StateMachine(0, NULL_SM, freq=15_000_000)`,
   `MQ.active(1)`, `MQ.active(0)` ([pio.md](pio.md#null_sm)); then
   `sd_active = True`. `TS_IO_DUAL` is gone from state machine 0 from here
   until `ACTIVATE_MQ`; TX, RX and Y with it.
3. GPIO 28 (U3_CS) output, pulled up; GPIO 2–4 inputs; **GPIO 12 output,
   driven 1**: U6 off, so the 2068's data bus cannot fight the card on
   GPIO 2–4. `main.py` sets GPIO 12 the same way at boot; `ACTIVATE_MQ`
   hands the pin back to the PIO.
4. Up to `tries` attempts, 0.5 s apart. Before every attempt after the
   first, if `SD_TRY_MS` (6 s) has passed since the first began, it stops
   ("giving up: N ms on K attempt(s)", printed) and counts only the
   attempts made. Each attempt: `SPI(0, sck=GPIO 2, mosi=GPIO 3,
   miso=GPIO 4)`, `SDCard(spi, U3_CS)`, then `os.mount(sd, "/sd")`. If the
   driver's `recovered` attribute is set (the card had been left in the
   middle of a transfer by an interrupted session and the driver brought it
   back without a power cycle; [sdcard.md](sdcard.md)), that is printed and
   logged at level 1. A mount that succeeds on attempt 2 or later is logged
   at level 1 with the previous error. Every failure is **printed** with
   its reason (`print`, not only `LOG`: the log reaches `/activity.log`
   only if logging works, and the console used to show nothing but
   "FAILED").
5. On success: `SD_NOTE_CARD(sd.CID)` (`0` if the driver has no `CID`),
   which may repair state or raise (see `SD_REVALIDATE`); then return the
   `SPI`.
6. On failure: if `TSP.sd_present` was true, the card was there and this
   is an error — logged at level 2 and `SAVE_LOG()` called at once, so
   the entry reaches `/activity.log` on the Pico's flash; if no card has been seen since power-on (`sd_cid is None`),
   "SD card: not found" at level 1; otherwise nothing new is logged. Then
   `TSP.sd_present = False` and `OSError(19, "SD card mount failed after N
   attempts: …")`. Errno 19 is `ENODEV`.

Why it raises: the single-port firmware looped in `BLINK_ERROR` when the
mount failed. This runs inside commands (`tpi:cd`, `tpi:md`, `tpi:rm`,
`tpi:newtap`, `tpi:help`, every `MOUNT_FILE`), and a card that wedged
mid-session — often right after a failed write — bricked the TS-Pico until
a power cycle. Raised, it is one command failing: the caller's `except`
(or `PROCESS_CMD`'s, then `FAIL_CMD`, which sees `sd_active` still `True`
and gives the bus back) answers, and the next command that needs a card
tries again.

Why `SD_TRY_MS`: a card that is in but holds MISO low makes the driver wait
out three 1 s busy timeouts before `CMD0`, about 4 s an attempt; five of
those (20 s, hardware, 2026-10-02, after a reflash) outlasted the 2068's
~19.9 s READY wait, so the 2068 reported J while the Pico went on to answer
nobody. With the 6 s budget the worst case is two such attempts, about
8.5 s ([tspico-state.md](tspico-state.md#sd_try_ms)).

State: writes `MQ`, `sd_active`, `TSP.sd_present`, and through
`SD_NOTE_CARD` `TSP.sd_cid` and more; the mount table; GPIO 2–4, 12, 28.
Callers: `TS2068_IO` at boot (6262), `SD_CALL`, `SD_PROBE`,
`LISTING_CHECK`, `REFRESH_LISTING`, `SAVE_MOUNT`, and the functions that
manage the card themselves: `MOUNT_FILE` (1823), `CATALOG` (2590),
`ChangeDir` (4123), `GETHELP` (4376), `MDIR` (4877), `PRINT_FLUSH` (5572),
`COPY_BMP` (5604), `PRN_OPEN` (5672), `TS2068_IO`'s SAVE and LOAD branches
(6620–6717) and `ZX_TPI` (7006).

Beware:

- It does not unmount first. A `/sd` still mounted makes `os.mount` fail
  with `EPERM`, which counts as a failed attempt and, five times over, as a
  missing card. Every caller in the 2068 path reaches it with `/sd`
  unmounted (the previous access ended with `DEACTIVATE_SD`); `SAVE_MOUNT`
  unmounts first because its callers in `tspico_io` cannot promise that.
- It parks the MQ before the first attempt, even when the card turns out
  to be missing. Every failure path must still end with `DEACTIVATE_SD` +
  `ACTIVATE_MQ`; the wrappers do it in a `finally`.
- A successful return can still be followed by an `OSError` from
  `SD_NOTE_CARD` (a write-protected card with no `TAP` folder), with the
  card mounted.

### `SAVE_MOUNT()`

The mount `SAVE_TS` and `SAVE_ZX` use for their writes, installed at import
as `tspico_io.SD_MOUNT = SAVE_MOUNT` (1176) and reached through
`tspico_io.ENA_SD`. It unmounts `/sd` (ignoring `OSError`), then returns
`ACTIVATE_SD()`.

Why (the 2026-09-30 audit, §2 #21): `SAVE_TS` and `SAVE_ZX` were the last
callers of `ENA_SD`'s bare mount — one `os.mount`, no retries, none of the
card bookkeeping. Their final status has already gone to the 2068 when they
mount (#40), so a card that only came up on a second attempt meant "0 OK"
on the 2068 and a file never written. `tspico_io` cannot import `tspico`
(it is imported by it, and the upgrade UF2 freezes `tspico_io` without it),
hence the hook ([tspico_io.md](tspico_io.md#sd_mount)). The unmount first:
`ENA_SD`'s bare mount used to carry on over a `/sd` left mounted (EPERM,
and the write used the old mount), and `ACTIVATE_SD` would count that EPERM
as a missing card.

Beware: `ACTIVATE_SD` rebinds this module's `MQ` to the parked state
machine while `SAVE_TS` or `SAVE_ZX` still hold the object they were given.
Both refer to the same hardware state machine 0, which now runs `NULL_SM`;
neither uses the bus again before returning, and the dispatcher's (or
`ZX48_IO`'s) handover after the SAVE rebuilds it.

### `SD_NOTE_CARD(cid)`

Records the card `ACTIVATE_SD` has just mounted and, when it is a card the
current state does not belong to, calls `SD_REVALIDATE`. `cid` is the
driver's `CID`, an int, `0` when `CMD10` failed.

```text
first   = sd_cid is None                 # no card seen since power-on
back    = not sd_present                 # it was missing
known   = cid != 0
changed = known and sd_cid not in (None, 0) and cid != sd_cid
sd_present = True
if known or first: sd_cid = cid
if back or changed: SD_REVALIDATE(changed)
```

Logging: "a different card is in" (level 1) when `changed`, "back in"
(level 0) when `back` and not `first`; nothing on the first card.

Why a CID of 0 never counts as a change: the driver's fallback to 0 is from
when the CID was informational. Since #101 the CID is the card's identity,
and a change drops append mode, the open channels and the printer capture.
One failed `CMD10` on the same card then looked like a swap, and two cards
that both failed looked the same (found by the 2026-09-30 audit; the
driver's own comment says the same, `sdcard.py` ~313). Now 0 is "unknown":
it never counts as a change and never replaces a CID that is known. A real
swap with an unreadable CID is still caught when the card was seen to be
out in between (`back`).

Beware: `back` is also true for the first card of the session (`sd_present`
starts `False`), so the first mount always revalidates — which is how the
boot sets up the folder and the caches. A swap done between two commands
without any command seeing the slot empty, between two cards whose CIDs
cannot be read, is invisible here; `LISTING_FRESHEN` catches the folder
part of that.

### `SD_REVALIDATE(changed)`

Brings everything that belongs to the card up to date. Runs with the card
mounted, the first time one is seen and whenever one comes back or is
different (`changed` true for a different card).

1. If the top folder (`catalog.ROOT`, `/sd/TAP`) is missing — a freshly
   formatted card — make it (logged at level 1). If it cannot be made (a
   write-protected card), `TSP.sd_present = False`, log at level 2, and
   raise `OSError(19, "SD card has no TAP folder")`: the card counts as
   missing.
2. `TSP.cur_path` is kept if the card has that folder, else set to the top.
3. `prev_path` (where `tpi:cd -` goes back to) is dropped if the card does
   not have it.
4. The mounted TAP (`TSP.f_name`, when it is a path on `/sd/`) is kept if
   the card has a file of that name, else unmounted with `FORGET_MOUNT`
   ([tspico-files.md](tspico-files.md)) and logged. A mount whose name is
   not under `/sd/` (an image served from the Pico's flash) is never
   touched.
5. A **different** card only: `TSP.append = False` (a SAVE must never land
   in the other card's file), `CHANNELS.close_all()` (their files were on
   the other card; [channels.md](channels.md)) and `prn_path = None` (the
   printer capture file).
6. `os.chdir(TSP.cur_path)`, `TSP.sd_listing_ok = DIR_FILES()` and
   `alldirs = GET_DIRS()`: the folder caches rebuilt
   ([tspico-files.md](tspico-files.md)).

Writes `alldirs`, `prev_path`, `prn_path`, `TSP.cur_path`, `TSP.append`,
`TSP.sd_present`, `TSP.sd_listing_ok`, the mount, the channels, the current
directory. Called only by `SD_NOTE_CARD`; the comments in `GETINFO` (4143),
`TS2068_IO` (6256) and `tspico_io`'s SAVE paths (2747, 2890) describe its
effects. `SAVE_TS` checks one of them: after its mount, `append` gone off
means the card was swapped during the transfer, and it refuses to append to
a file of the same name on the new card.

Beware: a "same file name" on a different card is not the same file. Step
4 keeps the mount if the name exists; only step 5's `append = False`
protects a SAVE. A file kept this way is served from the copy in
`/TMP/temp.tap` that `MOUNT_FILE` made from the old card *(inferred from
`MOUNT_FILE`'s copy, [tspico-files.md](tspico-files.md))*.

### `LISTING_SIG(entries)`

A fingerprint of a folder listing: `hash(tuple((name, type, size) …))` over
`os.ilistdir` entries (size `0` for an entry with fewer than four fields).
Two listings with the same fingerprint name the same files with the same
sizes. `LIST_DIR_FILES` (1676) stores it in `TSP.listing_sig` each time it
lists; `LISTING_FRESHEN` compares a fresh one against it. The order of
`entries` matters; both callers sort by lower-cased name.

Beware: `hash` of a tuple is not stable across firmware builds or reboots
*(inferred: MicroPython hashes strings by content, so in practice it is,
but nothing relies on it — the value lives only in RAM)*. Dates are not in
it, so a file rewritten with the same size is not seen as a change.

### `LISTING_FRESHEN()`

With the card mounted, re-reads the current folder (`DIR_FILES`: `files`,
`lista`, `dirinfo.tap`) if what is on the card no longer matches the last
listing. `os.chdir(TSP.cur_path)` and a sorted `os.ilistdir()`;
`OSError` (the folder has gone) returns quietly. A different `LISTING_SIG`
is logged at level 0 and `TSP.sd_listing_ok = DIR_FILES()`.

Why: the Pico noticed a swapped card only when a command found it missing
or a different card. The same card, taken out, given a file on a Mac and
put back between two commands, kept the old listing: CAT did not show the
file and `LOAD "tpi:"` could not find it until a reboot (hardware,
2026-10-03). Reading the folder is cheap; rebuilding the listing (with
`dirinfo.tap` and the free space) happens only when it changed. Callers:
`LISTING_CHECK`.

### `LISTING_CHECK()`

`ACTIVATE_SD()`, `LISTING_FRESHEN()`, then — always, in a `finally` —
`DEACTIVATE_SD()` and `ACTIVATE_MQ()` (Y BUSY). Returns `False` if the mount
raised (no card), else `True`. Callers: `DIR` (2534) before the regular
listing, which answers `NO_CARD_REPLY` on `False`, so a card taken out
since the last command gets the no-card answer instead of its old files;
and `LOAD_TPI` (5249), which looks once more before saying a name is not
there. One mount costs about 0.2 s (the comment at 2529).

### `REFRESH_LISTING()`

Re-reads the current folder because a ZX48 `SAVE` wrote a file into it:
`SAVE_ZX` sets `TSP.listing_stale`, and nothing re-lists in ZX48 mode.
Clears the flag first, then `ACTIVATE_SD()`, `os.chdir(TSP.cur_path)`,
`TSP.sd_listing_ok = DIR_FILES()`; an `OSError` (no card) is ignored —
the command's own card check answers. The `finally` gives the bus back,
Y BUSY. Callers, both where the Z80 is waiting for READY: the start of
`PROCESS_CMD` (5937) and `ZX_TPI` before it matches a name (7004, 7023).

### `SD_PROBE(tries=None)`

Is there a card? `ACTIVATE_SD(tries)`, and in a `finally`
`DEACTIVATE_SD()` + `ACTIVATE_MQ()`; `True` if the mount worked. A card
that has come back, or is a different one, is set up on the way
(`SD_NOTE_CARD`). The bus is left with the MQ and Y BUSY; TX is empty, so a
caller with a pre-load outstanding uses `PRELOAD_READ` first.

Callers: `PROCESS_CMD`'s card gate (5973: a command that needs the card,
with `sd_present` false, probes once before `NO_CARD_REPLY`, so inserting a
card is all it takes); the SAVE branch of `TS2068_IO` (6582, which sets
`TSP.save_no_card` so `SAVE_TS` refuses the header with Report J and the
program stays in the 2068's memory, instead of "0 OK" and a write that
fails after it); `GETINFO` (4534, so `tpi:info` reports the card as it is
now). With `tries` left `None`, a card believed missing gets one quick try.

## The LED

`led` is GPIO 25, the Pico's on-board LED
([tspico-state.md](tspico-state.md#led)).

### `BLINK_ERROR()`

`led.value(1)`, then ten passes of `utime.sleep(.1)` and `led.toggle()`,
then `led.value(0)`: five flashes in a fixed second. It blocks core0 for
that second. Callers: `MOUNT_FILE` when a mount fails at level 2 or above
(1930), `BLKRCV` when the block asked for runs past the file (4092). The
single-port firmware also called it in a loop when the boot mount failed
and after a failed transaction; both are gone (`ACTIVATE_SD` raises
instead, and the comment at 6812–6819 explains why the dispatcher's
recovery no longer blinks: the second it blocked was time the Z80 could
already be sending its next pre-header).

Beware: a second of core0 is long. Do not call it anywhere the Z80 might
be talking.

### `BLINK_LED(pause)`

The boot blink, on core1. Sets `busy = True`, sleeps 0.2 s, then blinks —
on `pause` seconds, off `pause` seconds — until the global `dead` is true;
then LED off and `busy = False`. `TS2068_IO` starts it with
`_thread.start_new_thread(BLINK_LED, (0.9,))` (6249) just before the
boot's card check and sets `dead = True` after it (6267), then waits
`while busy: pass` for it to finish before core1 is used for anything else
(the log writes). That wait is unbounded and safe: this function only
sleeps and toggles, cannot raise, and sees `dead` within one period.

`busy` doubles as "core1 is in use" for the log writer `SAVE_LOG`, which is
why this sets it ([tspico-state.md](tspico-state.md#busy)). `COPY_FILE`
once used it too; nothing else does now.

## Running a command with the card

Lines 2669–2727 sit at the head of the disk commands
([tspico-disk.md](tspico-disk.md)), which were the first handlers written
around them; every handler written since uses them too.

### `SD_CALL(fn, *args)`

Runs `fn(*args)` with the card mounted and always gives the pins back:

```python
try:
    ACTIVATE_SD()
    return fn(*args)
except OSError as e:
    if not TSP.sd_present:  return NO_CARD_MSG, _10_J_Invalid_IO
    LOG("SD card error: %s" % e, 2)
    return "SD card error", _3_F_Invalid_file
finally:
    DEACTIVATE_SD(); ACTIVATE_MQ()
```

So `fn` must return a `(message, status)` pair, the shape the error paths
return; the handler then answers with `SEND_MSG(msg, "", status)` or
`CH_REPLY(status)` on a bus that is the MQ's again, Y BUSY. An `OSError`
from the mount itself (no card: `ACTIVATE_SD` has cleared `sd_present`)
becomes the no-card answer, Report J, with the very `NO_CARD_MSG` object
that `SEND_MSG` recognises and always shows
([tspico-state.md](tspico-state.md#no_card_msg)); an `OSError` from `fn`
with the card present (a read or write failure, a full card) becomes "SD
card error", Report F, logged at level 2. Anything else `fn` raises passes
through after the handover, to `PROCESS_CMD`'s handler and `FAIL_CMD`.

Callers: the disk commands (`DISK_COPY`, `DISK_ERASE`, `DISK_FORMAT`,
`DISK_REN`, `NATIVE_OPEN`; 2779–3110), `CH_CALL`, `NEW_TAP` (3801), `RM`
(5368–5384), and external commands
(`extcmd.py` 22, [extcmd.md](extcmd.md)). `sd_state_hosttest.py`'s
`test_sd_call` pins the no-card answer.

Beware: a handler that asks the user something (a Y/N prompt, `ERASE`'s
`PROMPT_EACH`) must do it **between** two `SD_CALL`s, never inside one:
inside, the bus belongs to the card and no byte reaches the Z80. `ERASE`
with a pattern shows the pattern: one `SD_CALL` to find the files, the
prompt, a second to erase them.

### `SD_NEEDED(load_cmd, cmd_word, cmd_exec, SA_funct)`

Does this command need the card? `True` for `LOAD "tpi:name"`
(`load_cmd`: a mount reads a file); for `tpi:help`, `True` only with a
topic (`cmd_exec.strip() != cmd_word`), because the topics are files on
the card and the bare list is built in; otherwise `True` for a command in
`SA_funct` that is not in `SD_FREE`
([tspico-state.md](tspico-state.md#sd_free-sd_quiet)). An external
command (not in `SA_funct`) and an unknown word get `False`: external
commands decide for themselves, and an unknown word gets its own error.
`cmd_word` is upper case with the `TPI:` prefix. One caller,
`PROCESS_CMD`'s card gate (5972):

```python
if SD_NEEDED(...) and not TSP.sd_present and not SD_PROBE():
    NO_CARD_REPLY(cmd_word)
```

so a card believed present is not probed (the handler's own mount will
find out), and a card believed missing is looked for once more — putting
one in is all it takes. `test_gate` pins it.

### `NO_CARD_REPLY(cmd_word)`

The answer to a command that needs the card when there is none. Logs
"`cmd_word`: no SD card" at level 1, then: for a command in `SD_QUIET`
(`tpi:chopen`, `tpi:chwr`, `tpi:chrd`, `tpi:fopen` — sent by ROM 2.1 in the
middle of a BASIC statement), `CH_REPLY(_10_J_Invalid_IO)`, a bare status,
because a printed message would move the ROM's current channel; for any
other, `SEND_MSG(NO_CARD_MSG, "", _10_J_Invalid_IO, True)`, the message
forced on whatever `VERBOSE` says. Report J either way. Callers: the card
gate (5974) and `DIR` (2535) when `LISTING_CHECK` finds no card.

### `REFRESH_IF(*dirs)`

After a disk command changed files, re-lists the current folder if it was
one of `dirs` (compared upper-cased, since the card's FAT names are
case-insensitive): `os.chdir(TSP.cur_path)` and `DIR_FILES()`. It must run
with the card mounted — its callers are the `fn`s inside `SD_CALL`
(`DISK_COPY_WORK`, the `DISK_ERASE_*` workers, `DISK_NEW_TAP`,
`DISK_MAKE_DIR`, `DISK_REN_WORK`; 2845–3061).
It does not update `TSP.sd_listing_ok` or rebuild `alldirs`; a command
that makes or removes a folder does that itself.

## The channel replies

ROM 2.1's channel driver (`OPEN #`, `PRINT #`, `INPUT #`, `CLOSE #` on an
`f:` or `d:` stream; [../rom/exrom-fdd.md](../rom/exrom-fdd.md)) sends
`tpi:chopen`, `tpi:chwr`, `tpi:chrd` and `tpi:chclose` from inside a BASIC
statement. Two things differ from an ordinary command, and these three
functions carry them; the handlers are in [tspico-disk.md](tspico-disk.md).

### `CH_READY()`

READY without IDLE: `MQ_STATUS(MQ, "mid")`, Y = `0xF7`.

Why: the channel driver can send its next command the moment it has this
one's answer — `CLOSE #` flushes and closes back to back — and it waits for
IDLE before its SYNC. `MQ_READY` says IDLE too, so that SYNC could land
while `PROCESS_CMD`'s tail was still draining and logging; the tail's own
IDLE then let the pre-header go with nobody capturing it ("Partial
pre-header 4/10", Report T; hardware, 2026-09-29). With `CH_READY` the
answer is readable at once, and the IDLE that counts is the one the tail
says when it has staged the pre-load
([PROTOCOL.md §5.6](../../PROTOCOL.md#56-the-tail-and-ready-vs-idle)).

Callers: `CH_REPLY`, `CH_READ`'s answers (3344–3367), and `STREAM_DMA` as
the `ready` callable `CH_READ` passes it.

### `CH_REPLY(st)`

`CMD_PUT(st)` then `CH_READY()`: the status byte alone, never a message,
whatever `VERBOSE` says. A message printed now would move the ROM's
current channel to the screen in the middle of `PRINT #` or `INPUT #`. The
ROM's `C_END` reads it: 1 is OK, anything else a report. Raises
`CmdAbort` as `CMD_PUT` does. Callers: the channel handlers (3299–3412)
and `NO_CARD_REPLY`.

### `CH_CALL(fn, *args)`

A channel operation on the card: `SD_CALL` of a wrapper that returns
`(fn(*args), _1_OK)`, or, when `fn` raises `channels.ChannelError(message,
letter)`, `(message, CH_STATUS[letter])` — `F` → Report F, `Q` → Q, `O` →
J, anything else Q ([tspico-state.md](tspico-state.md#channels-ch_status),
[channels.md](channels.md)). An `OSError` becomes `SD_CALL`'s answer. So
the caller gets `(result, status)`, where `result` is `fn`'s value on
success and a message otherwise. Callers: `CH_OPEN` (3296, 3312, 3327),
`CH_READ` (3340), `CH_WRITE` (3388), `CH_CLOSE` (3401).

## Where comments and the code disagree

The code wins in each case; the comments are left as they are by this
reference.

- `DEACTIVATE_SD`'s header comment (686–689) and the boot call's comment
  (6284–6286) call the GPIO 2–4 clamp the fix for the original Report D;
  the function's own body comment (703–709) says that was D6, GPIO 8, which
  the clamp never touched.
- `ACTIVATE_MQ`'s header comment (726–727) says the RP2040's PIO runs "up
  to half the CPU clock"; it can run at the full system clock, and the
  bank state machines run at 150 MHz of the 270 MHz. `TS_IO_DUAL`'s
  docstring makes the same mistake ([pio.md](pio.md)).
- `MQ_BUSY`'s docstring says nothing calls it; `ACTIVATE_MQ` does (767).
- `MQ_READY`'s docstring cites "Gustavo's V5 doc" for "the V1.5 protocol";
  the polling it describes is the ROM's `WAIT_PICO_READY`
  ([../rom/exrom-driver.md](../rom/exrom-driver.md)), and the authoritative
  description is [PROTOCOL.md](../../PROTOCOL.md).
- `sd_mount_hosttest.py`'s docstring says the boot call "keeps the blink
  loop"; `TS2068_IO` catches the `OSError` and boots without a card.
