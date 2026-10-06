# src/upgrade/ — the upgrade UF2 and the Z80 updater

Source: [`src/upgrade/main.py`](../../../src/upgrade/main.py),
[`src/upgrade/upgrade.py`](../../../src/upgrade/upgrade.py),
[`src/upgrade/updater.asm`](../../../src/upgrade/updater.asm) (its build,
[`updater.bin`](../../../src/upgrade/updater.bin)),
[`src/upgrade/loader.bas`](../../../src/upgrade/loader.bas),
[`src/upgrade/manifest.py`](../../../src/upgrade/manifest.py);
[`tools/build-upgrade.py`](../../../tools/build-upgrade.py); the ROM step of
[`web-updater/`](../../../web-updater/). Part of the
[programmer's reference](../README.md).

A board on firmware 1.1 or 1.5 has a TS-2068 ROM in flash slot 1 that speaks
the single-port protocol of those releases. Firmware 2.x speaks the dual-port
one ([PROTOCOL.md](../../PROTOCOL.md) §1–§3), so once the Pico has new
firmware the 2068 ROM cannot talk to it, and the ROM can only be rewritten
by the Z80: the flash chip hangs off the 2068's bus, and the firmware's own
ROM-update path (`romupdate.tap`, [tspico-commands.md](tspico-commands.md))
needs a working ROM-to-firmware link. The one thing every shipped flash image
has in common is the original Spectrum ROM in slot 0 (crc32 A8E12A24, the
comment at `tspico_io.py` "UPDATE mode"), and `OUT 244,3` maps it in
whatever the 2068 ROM is: port F4h is the HSR, one bit per 8K chunk, and 3
takes chunks 0–1 from the DOCK ([MEMORY_MAP.md](../../rom-analysis/MEMORY_MAP.md)),
which the Pico fills with flash page 0. That ROM's LD-BYTES has no
handshake: `OUT (0Eh),'L'`, a fixed ~0.94 ms, then it reads, whatever is in
TX ([PATCH_ZX48_HANDSHAKE.md](../../rom-analysis/PATCH_ZX48_HANDSHAKE.md) §1–§2).
So the update path is a second firmware, the **upgrade UF2**, which the web
updater writes before the real one. Its frozen `main.py` brings up the bus
state machines as the firmware does and then runs `serve`, which keeps the
updater tape queued in TX as one continuous stream, flag, content and CRC of
every block back to back, so the flag of the next block is already there
when the next `'L'` comes. The page tells the user to type `OUT 244,3` and
`LOAD ""`; the Spectrum ROM loads a two-line BASIC loader and the updater's
CODE block at 6000h and runs it.

The updater is Z80 code in RAM with interrupts off. It makes three kinds of
request, each an `OUT (0Fh)` (the tape stream never has one) followed by
argument bytes on 0Eh ~50 µs apart; the Pico queues the reply and raises
READY (0Fh bit 6), and the Z80 reads it ~44 µs a byte: `'I'` says hello and
stops the tape, `'R' image,block` fetches 256 bytes of a ROM image plus
their XOR, `'S' code,arg` reports progress. It reaches the flash through the
2068's DOCK bank: with HSR = F6h slot 1 sits at 8000h–FFFFh and the chip's
command addresses 5555h/2AAAh fall in chunks 1–2; with HSR = 07h the lower
16K of slot 0 sits at 0000h–3FFFh. It sends the SST39SF040 command
sequences by writing to those addresses, erases slot 1's eight 4K sectors,
then fetches, programs and verifies its 128 blocks, then does the same for
slot 0's lower 16K (four sectors, 64 blocks), draws a progress cell per
block, prints DONE and halts. Every status reaches the web page as one line
on the Pico's USB serial, `UPG {json}`, and the page shows a message and a
progress bar per event.

Slot 1 goes first on purpose. Until it is written and verified, slot 0, the
Spectrum ROM and the only way back in, is untouched, so a failure in that
phase (`'X'` with a reason: no Pico, the erase did not take because the P10
jumper is missing, a block that kept failing its XOR, a byte that would not
program) prints its message, maps HSR = 03h again and returns to BASIC; the
Pico hears the `'X'`, rewinds the tape, and `LOAD ""` tries again. Once slot
0's erase has started a failure halts with "finish on the web page": the
2068 ROM is new, and the page writes the real firmware next anyway. A reset
of the 2068 part way leaves the Pico in service mode, ignoring whatever ROM
boots, until another `'L'` arrives (`OUT 244,3`, `LOAD ""` again, possible
while slot 0 is intact); then the tape rewinds and the updater starts over
from slot 1. The whole exchange, Pico loop, tape, Z80 binary, banking and
chip model, runs in CPython in
[`src/test/upgrade_hosttest.py`](../../../src/test/upgrade_hosttest.py) and
[`src/test/updater_hosttest.py`](../../../src/test/updater_hosttest.py); the
tape path was proven on hardware with a v15w chip
([`src/test/zx_bootstrap_harness.py`](../../../src/test/zx_bootstrap_harness.py)).

## Map

| Where | What |
|---|---|
| main.py 12–27 | the bus pins at their idle levels, the CPU clock |
| main.py 29–39 | the three state machines: `ROM`, `BANK`, `MQ`, with the default slot mapping |
| main.py 41 | `upgrade.serve(MQ, upgrade_data)` |
| upgrade.py 41–52 | imports from `tspico_io`; `VERSION`, `REWIND_MS`, `REPLY_STALL_MS`, `STATUS_NAMES` |
| upgrade.py 55–107 | `report`, `reply`, `drained` |
| upgrade.py 110–195 | `serve`: tape mode and service mode |
| updater.asm 47–68 | ports, ROM and RAM addresses, HSR values, failure reasons |
| updater.asm 73–119 | `start`: hello, both phases, DONE |
| updater.asm 123–239 | `phase`: erase, then fetch, program, verify, block by block |
| updater.asm 245–309 | `erase`, `program`: the SST39SF040 sequences and DQ7 polling |
| updater.asm 313–405 | the Pico: `request`, `wait_ready`, `send`, `recv`, `status`, `fetch` |
| updater.asm 410–444 | `fail`: back to BASIC, or halt |
| updater.asm 447–533 | the screen: `cls`, `print_msgs`, `print_at`, `char_at`, `tick` |
| updater.asm 536–567 | the messages |
| updater.asm 570–585 | the variables, `code_end` |
| loader.bas | the BASIC loader on the tape |
| manifest.py | what the upgrade UF2 freezes |
| tools/build-upgrade.py | `upgrade_data.py` and `updater.tap` from the manifest's ROMs |
| build.yml, release.yml | the upgrade UF2 in CI |
| web-updater/build-payload.sh | the channel payloads |
| web-updater/app.js, flasher.js | the page's side of `UPG` |

## On the wire

The three requests, as [`serve`](#servemq-data) answers them and the
updater makes them. A request begins with a write to port 0Fh; the PIO
delivers it to the Pico as a 9-bit word with bit 8 set
([pio.md](pio.md), `PORT_0F` in [tspico_io.md](tspico_io.md)), and drops the
status to BUSY, as it does on every Z80 OUT ([PROTOCOL.md](../../PROTOCOL.md)
§3.2). Arguments follow on 0Eh. The reply goes into TX and only then is
READY raised, because the Z80 reads the instant it sees it.

| Request (OUT 0Fh) | Arguments (OUT 0Eh, ~50 µs apart) | Reply (after READY, read ~44 µs apart) | Pico | Z80 |
|---|---|---|---|---|
| 'I' (49h) | none | 'T' (54h), 'P' (50h), `VERSION`, 00h; the tape stops | `serve`, the `'I'` branch | `start` |
| 'R' (52h) | image (00h: slot 0, 01h: slot 1), block (0–127) | the 256 bytes, then their XOR | `serve`, the `'R'` branch | `fetch` |
| 'S' (53h) | code, argument | one byte, 00h | `serve`, the `'S'` branch | `status` |

The status codes, with the argument each carries:

| Code | Argument | When |
|---|---|---|
| 'P' phase start | the image (1, then 0) | before the erase |
| 'E' erased | the image | all sectors erased |
| 'W' block written | the block | after its verify |
| 'V' image verified | the image | the last block done |
| 'D' done | 0 | both images done |
| 'X' failed | the reason: `X_PICO` 1, `X_BLOCKED` 2, `X_XFER` 3, `X_WRITE` 4 | before the return to BASIC or the halt |

What the Pico prints on USB serial, one JSON object per line after `UPG `,
each with an `event` field:

| event | Other fields | Meaning |
|---|---|---|
| waiting | `say` | `serve` has armed the tape |
| tape | `note` when the updater had been running | the first `'L'` of a LOAD; or a LOAD after a reset, the tape rewound |
| ignored | `byte`, `say` | a port-0Eh write that was not `'L'` outside service mode: the old TS-2068 ROM's command burst |
| updater | — | the `'I'` arrived |
| status | `code`, `what` (from `STATUS_NAMES`), `arg` | each `'S'` |
| bad-request | `image`, `block` | an `'R'` for an image or block that does not exist |

## src/upgrade/main.py

The upgrade UF2's `main.py`, frozen into it ([manifest.py](#srcupgrademanifestpy))
so that it runs at boot from an empty filesystem. It is the pin setup of
the firmware's [`src/main.py`](boot.md) (its lines 64–79) and the
state-machine start of `TS2068_IO` ([tspico-dispatch.md](tspico-dispatch.md)),
with the mapping `config.ini` would give by default, then `upgrade.serve`. There is no
`config.ini`, no SD card, no dev override and no crash log: nothing on the
filesystem is read, which is the point.

The pins first. Each is set to the level `src/main.py` lines 64–70 set
([boot.md](boot.md) explains the lines; [hardware.md](../hardware.md) the
wiring); `U3_CS` is the one line the firmware's `main.py` does not touch
here, added so the SD card stays deselected. The order is deliberate: pins,
then the ROM and bank state machines, then the data port. Until `ROM` and
`BANK` run, the 2068 sees no ROM at all and beeps at power-on, which is how
the #82 import failure showed itself (`manifest.py`'s comment).

| Variable | GPIO | Mode, level | What it is |
|---|---|---|---|
| `U6_EN` | 12 | output, pull-up, driven 1 | the U6 bus buffer's enable, also `MQ`'s side-set pin; 1 = the Pico off the bus (`TS_IO_DUAL`'s docstring) |
| `WAIT` | 14 | output, pull-down, driven 1 | named for the Z80's /WAIT line; `TS_IO_DUAL` waits on this very pin (`wait(0, gpio, 14)`) and its docstring calls it /PICOSEL, the bus-cycle strobe, as the line's comment now says. Which name is right is [hardware.md](../hardware.md)'s; the upgrade code only sets it as `src/main.py` does |
| `U10_ENA` | 19 | output, pull-up, driven 1 | the flash's (U10) enable, by `main.py`'s name; `ROM`'s first out pin. `set_ctrl`'s header comment calls its two out pins /U10_CE and /U10_OE, which [hardware.md](../hardware.md) reconciles |
| `U13_ENA` | 20 | output, pull-up, driven 1 | the SRAM's (U13) enable, by `main.py`'s name; `ROM`'s second out pin (see the row above) |
| `BE` | 21 | output, pull-up, driven 1 | bus enable, `ROM`'s set pin |
| `ROSCS` | 26 | input, pull-down | the 2068's ROM chip select; the jump pin of `ROM` and `BANK`: it tells them a HOME-ROM cycle from a DOCK cycle *(inferred from `sel_bank`, below)* |
| `U10_WE` | 27 | output, pull-up, driven 1 | the flash's write enable from the Pico, idle. The upgrade firmware never lowers it: the Z80's writes reach the chip through the P10 jumper, not through this pin *(inferred; see [How the Z80 reaches the flash](#how-the-z80-reaches-the-flash))* |
| `U3_CS` | 28 | output, pull-up, driven 1 | the SD card's chip select, deselected; "not used here" |

`freq(270_000_000)` follows, as in the firmware, so the PIO clocks below
are the ones the firmware runs.

### `ROM`

State machine 4 running `set_ctrl` ([pio.md](pio.md)) at 150 MHz, `in_base`
GPIO 0, `jmp_pin` GPIO 26 (`ROSCS`), `set_base` GPIO 21 (`BE`), `out_base`
GPIO 19 (`U10_ENA`, `U13_ENA`): it drives the chip-enable lines on every
Z80 memory cycle. `ROM.put(10)` loads the control word `config.ini`'s
`ROM_SM` holds by default: bits 2–3 are the ROM's memory and bits 0–1 the
DOCK's (`getBoot`, `getDock` in [tspico-commands.md](tspico-commands.md)),
and 2 means the flash, so 10 = 1010b is "both from flash". Started before
`MQ`, and before `BANK`'s word is put.

### `BANK`

State machine 5 running `sel_bank` ([pio.md](pio.md)) at 150 MHz, `jmp_pin`
GPIO 26, `out_base` GPIO 15: four bits per memory cycle, the slot. The word
is packed as `TSP.bank_sm` is, `DCK_SLOT * 16 + ROM_SLOT`
([tspico-state.md](tspico-state.md)); `BANK.put(1)` is `ROM_SLOT` 1,
`DCK_SLOT` 0, the defaults. `sel_bank` puts the low nibble on the pins when
the jump pin is high and the high nibble when it is low, so a HOME-ROM
cycle gets slot 1 (the TS-2068 ROM) and a DOCK cycle gets page 0, which is
64K: slots 0 and 1 *(inferred from the program; DCK pages are two slots,
[flash/README.md](../../../flash/README.md))*. That mapping is what the
updater counts on: through the DOCK the Z80 sees slot 0 at 0000h–7FFFh and
slot 1 at 8000h–FFFFh of flash page 0, the model
`updater_hosttest.py` encodes ("page 0 of the flash chip (slots 0 and 1:
chip address = Z80 address)"). It never changes during the update.

### `MQ`

State machine 0 running `TS_IO_DUAL` ([pio.md](pio.md)) at 30 MHz:
`out_base`/`in_base` GPIO 2 (D0–D7), `jmp_pin` GPIO 11 (read/write),
`sideset_base` GPIO 12 (`U6_EN`). The same configuration as the firmware's.
Its Y register is 0 at start, so port 0Fh reads BUSY until `serve` raises
READY at the first `'L'`; the original Spectrum ROM never looks. Everything
`serve` does goes through this object: `MQ.put`, `MQ.get`, `MQ.tx_fifo`,
`MQ.rx_fifo`, and `MQX` for the READY instruction.

The last line, `upgrade.serve(MQ, upgrade_data)`, never returns.

## src/upgrade/upgrade.py

The Pico side of the ROM update: one module, four functions, four
constants. It imports from [tspico_io.md](tspico_io.md) exactly what it
relies on: `MQX` (a PIO instruction without the assembler), `TAPE_STREAM_OF`,
`ZX_ARM` and `ZX_STREAM` (the tape as one stream, armed and fed), `ZX_FLUSH_TX`
and `ZX_ROOM` (empty TX; wait for room while listening), `STREAM_DMA` (a
buffer into TX by DMA, READY once it moves), `RX_WORD` (a word or
-1 after a timeout, never a bare `MQ.get()`), `TX_DEPTH` (4: the FIFOs are not
joined) and `PORT_0F` (bit 8 of an RX word). It imports nothing else from
`TS`, but `tspico_io` does, which is why `manifest.py` freezes `TS.sdcard` and
`TS.native` too ([DEVELOPER_GUIDE.md](../../DEVELOPER_GUIDE.md), "The upgrade
UF2 is a second build of `tspico_io.py`"). The module's docstring names its
build script, [`tools/build-upgrade.py`](#toolsbuild-upgradepy) (until #181,
as a `.sh` that does not exist).

### `VERSION`

`int`, 1. The third byte of the `'I'` reply. `serve` sends it; `start`
receives it into `BUF+2` and does not check it. Nothing else reads it. It
is the protocol version of this exchange, not the firmware's.

### `REWIND_MS`

`int`, 5000 ms. `serve` passes it to `ZX_STREAM` as `rewind_ms`: with bytes
waiting in TX and the Z80 not reading for this long part way through the
tape, the stream is re-armed from its start, so a LOAD that was stopped
(BREAK between blocks, a reset) does not leave the next one starting in the
middle of the tape ([tspico_io.md](tspico_io.md) `ZX_STREAM`).

### `REPLY_STALL_MS`

`int`, 1000 ms. How long `reply` waits for the Z80 to take the next byte
before it gives the reply up (`STREAM_DMA`'s `stall_ms`, `ZX_ROOM`'s
`stall_ms` on the hand path). It was a literal 1000 in `reply` until the
2026-10-06 fix.

### `STATUS_NAMES`

`dict`, code letter to word: `P` phase, `E` erased, `W` written, `V`
verified, `D` done, `X` failed. Read by `serve` for the `what` field of a
`status` line; an unknown code gives `?`. The page keys on `code`, not on
`what`.

### `report(event, **kw)`

One line for the web page. Adds `event` to the keyword fields and prints
`"UPG " + json.dumps(kw)` on the USB serial, the Pico's stdout. No return.
The page's reader ignores lines that do not start with `UPG ` and lines
whose JSON does not parse, so a MicroPython traceback on the same port does
no harm to it.

### `reply(MQ, data)`

Queue a reply for the Z80 and say READY. Returns -1 when every byte is in
TX (the last four may still be unread), -2 when the Z80 stopped reading for
`REPLY_STALL_MS`, or 0–511, a word the Z80 wrote mid-reply, which `serve`
then handles as its next request. Steps: `ZX_FLUSH_TX` (whatever was left
in TX, up to 64 pulls); then

- **a reply longer than `TX_DEPTH`** (an `'R'` block, 257 bytes):
  `STREAM_DMA(MQ, data, None, REPLY_STALL_MS, True)`. The channel starts and
  fills the FIFO, and only then is READY raised; the DMA feeds TX in
  hardware as the Z80 reads, while core0 only listens. `why` 0 returns -1;
  `why` 4 (a word, `echo` being `None`) flushes TX and returns the word;
  any other `why` (3, a stall) flushes and returns -2. `None` (no DMA, or no
  free channel) falls through to the hand loop;
- **otherwise, or as the fallback**: put bytes while TX has room, at most
  `TX_DEPTH`; `MQX(MQ, "mov(y, invert(null))")`, READY; then for the rest
  `ZX_ROOM(MQ, REPLY_STALL_MS)` before each put: -1 means room, so put;
  anything else flushes TX and is returned.

Why READY only after TX holds bytes: the PIO dropped the status to BUSY at
the Z80's OUT, the Z80 polls for READY and reads the moment it sees it, and
an empty TX reads as 00h (`TS_IO_DUAL`'s docstring;
[PROTOCOL.md](../../PROTOCOL.md) §3.2).

Why DMA for a block: `recv` reads blind, a byte every ~44 µs, from a 4-deep
FIFO. On MicroPython v1.29 a Python loop putting one byte at a time (with a
`ZX_ROOM` call per byte) falls behind; the FIFO runs dry and the Z80 reads
00h. On hardware (2026-10-06, firmware v2.2, the web updater's
"Latest release") the updater erased slot 1 and then never got a block that
passed its XOR, and gave up with slot 1 blank. `LOAD_TS`, `LOAD_ZX` and
`romupdate` had moved to `STREAM_DMA` for the same reason in #126–#128
([tspico_io.md](tspico_io.md) `STREAM_DMA`); `reply` was the blind stream
left behind. The 1- and 4-byte answers fit the FIFO before READY, so they
need no channel.

Why return the word: the Z80 only writes mid-reply after giving up on this
one, and that word is the first of its next request (`'R'` again, or the
`'S'` of its failure). Before the fix `reply` read it and dropped it, so the
request's argument bytes fell through `serve` as strays and the updater
lost ~4 s in `wait_ready` per occurrence; `serve` now dispatches it.
Calls `ZX_FLUSH_TX`, `STREAM_DMA`, `MQX`, `ZX_ROOM`; called by `serve` for
all three replies. `upgrade_hosttest.py` runs the whole upgrade with every
block sent through a fake DMA channel, and checks a word sent mid-reply
comes back on both paths.

### `drained(MQ, ms)`

Wait, at most `ms`, for the Z80 to read what is left in TX; returns whether
TX is empty. Called by `serve` after an `'X'` with 200 ms, before it
re-arms the tape: `ZX_ARM` begins with `ZX_FLUSH_TX`, and if the 1-byte
`'S'` acknowledgement were flushed before the Z80's `IN`, that `IN` would
take the tape's first byte instead and the next `LOAD ""` would start one
byte in *(inferred)*.

### `serve(MQ, data)`

The update loop; it runs forever, since the Pico has nothing else to do
until the page writes the real firmware. `data` is the generated
`upgrade_data` module: `TAPE`, `IMG1` (32K, slot 1), `IMG0` (16K, slot 0's
lower half).

Setup: `images = {0: IMG0, 1: IMG1}`; `stream, starts = TAPE_STREAM_OF(TAPE)`
(the tape with its 2-byte lengths dropped; `starts` is not used); `blk`, a
257-byte buffer reused for every `'R'`; `service = False`;
`report("waiting", say=...)`; `gc.collect()`; `pos = ZX_ARM(MQ, stream)`, TX
flushed and the first four bytes queued; `loading = False`; `nxt = -1`, a
word a `reply` already read (each `reply`'s result is kept in `nxt`; -1 and
-2 mean none). The images and
the tape are frozen `bytes`, so RAM holds only the stream and the block
*(inferred from the freeze)*.

Each pass first takes `nxt` if it holds a word (and clears it); otherwise
the loop has two modes, chosen by `service`:

- **Tape mode** (`service` false): `w, pos = ZX_STREAM(MQ, stream, pos,
  REWIND_MS)` feeds TX from the stream, byte by byte as room appears, until
  the Z80 writes a word; the stream rewinds itself when fully read or after
  `REWIND_MS` of no reading part way.
- **Service mode** (`service` true, after `'I'`): spin on `MQ.rx_fifo()`,
  then `w = MQ.get()`. Unbounded: the Pico sits here between the updater's
  requests. USB serial still works, so the page's Ctrl-C reaches it.

Then, by what `w` is:

1. **A port-0Eh write** (`not w & PORT_0F`):
   - `w == 0x4C`, the Spectrum ROM's `'L'`. Its bytes are already queued, so
     the only action is `MQX(MQ, "mov(y, invert(null))")`, READY, for a
     board that already has ZX v3 or v4 in slot 0: those ROMs wait for READY
     after `'L'` ([../rom/zx48.md](../rom/zx48.md)), the original does not
     look. (ZX v2 cannot run the upgrade: its `WAIT_RDY` counts in D and
     breaks every LOAD, [PATCH_ZX48_HANDSHAKE.md](../../rom-analysis/PATCH_ZX48_HANDSHAKE.md).)
     In service mode an `'L'` means the 2068 was reset and `LOAD ""` typed
     again: `service = False`, `pos = ZX_ARM(...)`, `report("tape",
     note="the updater stopped; tape rewound")`. In tape mode the first
     `'L'` of a LOAD sets `loading` and reports `tape` once.
   - any other byte in service mode: ignored. The updater opens every
     request on 0Fh, so a 0Eh byte here is a stray.
   - any other byte in tape mode: an old TS-2068 ROM's command, a burst of
     pre-header bytes ([PROTOCOL.md](../../PROTOCOL.md) §4.3; a 1.x ROM never
     writes 0Fh). Swallow RX until 50 ms pass with nothing new, re-arm the
     tape, `loading = False`, `report("ignored", byte=..., say='That was the
     TS-2068 ROM: type OUT 244,3 first')`.
2. **A port-0Fh write**, `c = w & 0xFF`:
   - `'I'` (0x49): `service = True`, `loading = False`, `reply` with
     `'T'`, `'P'`, `VERSION`, 0; `report("updater")`. The tape stops
     because the loop no longer calls `ZX_STREAM`.
   - `'R'` (0x52): `img = RX_WORD(MQ, 100)`, `b = RX_WORD(MQ, 100)`; a
     timeout (-1) on either drops the request without a reply, and the
     updater's `wait_ready` times out and asks again. `images.get(img &
     0xFF)` and `off = (b & 0xFF) * 256`; an unknown image or a block past
     the end is `report("bad-request", ...)` and no reply, which the
     updater also treats as a timeout. Otherwise copy 256 bytes into `blk`,
     XOR them into `blk[256]`, `reply(MQ, blk)`.
   - `'S'` (0x53): `code` and `arg` by `RX_WORD(MQ, 100)`, a timeout drops
     it; `reply(MQ, b"\x00")` first, then `report("status", code=...,
     what=STATUS_NAMES.get(...), arg=...)`. For `'X'`: `drained(MQ, 200)`,
     `service = False`, `pos = ZX_ARM(...)`: the updater is returning to
     BASIC and `LOAD ""` will want the tape from the start. `'D'` changes
     nothing: the Pico stays in service mode with the updater halted until
     the page reboots it.
   - anything else in tape mode: `ZX_FLUSH_TX` and re-arm, "a 0Fh write that
     isn't ours (a 1.8b SYNC)": a ROM 2.0/2.1 board opens every command
     with 03h on 0Fh. In service mode an unknown 0Fh write is ignored.

State: `service`, `loading`, `pos` (the stream position) are locals; the
FIFOs and Y are the only shared state. Nothing is written to the
filesystem. The function reads `data.TAPE`, `data.IMG0`, `data.IMG1`.

Beware:

- `serve` takes `'I'` at any time, including mid-service. The updater only
  sends it once per run, at `start`.
- After `'D'` nothing can bring the tape back but an `'L'`; the page relies
  on `machine.bootloader()` over the REPL instead.
- The RX argument reads are bounded (100 ms) but the service-mode wait is
  not; that is by design, the Pico has nothing else to do.
- The `0x4C` test is on a 0Eh write outside a request only; a block number
  76 or a status argument 76 arrives inside the `'R'`/`'S'` branches, read
  by `RX_WORD`, and is not mistaken for `'L'`.

What the tests pin: `upgrade_hosttest.py` runs this function against a
scripted LD-BYTES and then the real `updater.bin` in `z80core`, with and
without the P10 jumper, and once with a ZX v3-style READY wait after `'L'`;
it checks the lines `waiting, tape, updater, P 1 ... 192 W ... D`, the
flash's final contents, and that after `X 2` TX holds the tape's first four
bytes again. Since 2026-10-06 it runs the whole upgrade once more with every
block sent through a fake DMA channel (`load_ts_hosttest.FakeDMA`), and
checks that a word the Z80 writes mid-reply comes back from `reply` on both
paths. The model's Z80 never reads an empty TX, so none of this can show
the dry FIFO the DMA fixes: that was seen, and must be checked, on
hardware. It also checks that every module-level import of the frozen
files is itself frozen and that both workflows stage exactly the frozen
`TS` files.

## src/upgrade/updater.asm

The Z80 updater: 1308 bytes of sjasmplus source assembled at 6000h to
`updater.bin` (the `OUTPUT` directive), carried on the tape as the CODE
block, started by the loader's `RANDOMIZE USR 24576`. It runs under the
original slot-0 Spectrum ROM with interrupts off, calls no ROM routine,
prints with its own copy of the ROM font, and never fetches an instruction
from the flash chip after it starts; `updater_hosttest.py` checks the last
point on every run. The header comment says it is built by
[`tools/build-upgrade.py`](#toolsbuild-upgradepy) (until #181, by a `.sh`
that does not exist); that script does not assemble: the
`.bin` is committed, and `updater_hosttest.py` reassembles the source and
compares when `sjasmplus` is on the path.

### How the Z80 reaches the flash

The 2068 pages its 64K in eight 8K chunks. Port F4h, the HSR, has one bit
per chunk: 1 takes the chunk from the cartridge bus instead of HOME, and
port FFh bit 7 chooses EXROM or DOCK for those chunks
([MEMORY_MAP.md](../../rom-analysis/MEMORY_MAP.md)). The updater never
writes port FFh: it relies on DOCK being selected already, which is what
made `OUT 244,3` show the Spectrum ROM *(inferred)*. On a DOCK cycle the
Pico's `BANK` machine presents flash page 0, slots 0 and 1, with the Z80's
address as the chip address ([`BANK`](#bank) above). So:

| HSR | Chunks from the DOCK | What the Z80 sees | Used for |
|---|---|---|---|
| 03h | 0, 1 | 0000h–3FFFh: the Spectrum ROM (slot 0's lower 16K) | what `OUT 244,3` set; restored by `fail` before returning to BASIC |
| F6h (`HSR_SLOT1`) | 1, 2, 4, 5, 6, 7 | 8000h–FFFFh: slot 1, the 32K TS-2068 ROM; 2000h–5FFFh: page offsets 2000h–5FFFh, holding the command addresses | erasing and programming slot 1 |
| 07h (`HSR_SLOT0`) | 0, 1, 2 | 0000h–5FFFh: slot 0's lower 24K, the ZX ROM in the first 16K | erasing and programming slot 0 |
| 00h | none | all HOME: the TS-2068 ROM in chunks 0–1, RAM above | everything else: the screen, the Pico I/O, the fetches |

Chunk 3, 6000h–7FFFh, is HOME under every value, which is why the code,
the font copy, the block buffer, the variables and the stack all live
there. The screen is in chunk 2, so it is only written with HSR = 0;
under F6h or 07h chunk 2 is the chip.

The chip is an SST39SF040. Its commands are byte writes to A14–A0 patterns:
AAh to 5555h, 55h to 2AAAh, then 80h, AAh, 55h again and 30h at the sector
for a 4K sector erase; AAh, 55h, A0h then the data byte at its address for a
byte program. 5555h is in chunk 2 and 2AAAh in chunk 1, so both HSR values
map them to the chip; the upper address bits do not matter to the command
decoding *(inferred: `updater_hosttest.py` models the sequence on `a &
0x7FFF`; the data sheet is not in the repo)*. While a command runs the chip
answers every read, at every address, with status bits: DQ7 is the
complement of the byte being written (0 during an erase) and DQ6 toggles.
Hence the rules in the header comment: nothing may be fetched from the chip
until the operation ends, so the code runs from RAM, `DI` keeps the IM 1
fetch from 0038h away, no ROM routine is called, and the code never returns
to a ROM it has touched. A write only reaches the chip's write-enable
through the **P10 jumper** (the user manual's "P10 enables writing to the
Flash chip"; the `X_BLOCKED` reason); without it the command sequence
changes nothing, the sector still reads its data, and `erase` reports
failure *(the wiring itself is [hardware.md](../hardware.md)'s;
`updater_hosttest.py` models P10 as "writes never arrive")*.

What the updater writes: all of slot 1 (chip 8000h–FFFFh, eight sectors,
128 blocks), and the lower 16K of slot 0 (chip 0000h–3FFFh, four sectors,
64 blocks). Slot 0's upper 16K, zeros in the image, and every other slot
are untouched; the tests check the pattern around them survives.

### Ports and addresses

| Name | Value | What it is | Who uses it |
|---|---|---|---|
| `PORT_DATA` | 0Eh | the data port: `IN` reads the Pico's TX FIFO, `OUT` writes its RX FIFO ([PROTOCOL.md](../../PROTOCOL.md) §1) | `send`, `recv` |
| `PORT_STAT` | 0Fh | the status port: `IN` reads the Y register (bit 6 READY), `OUT` reaches RX with bit 8 set and marks a request | `request`, `wait_ready`, `status`, `fetch` |
| `PORT_HSR` | F4h | the 2068's horizontal select register, one bit per 8K chunk ([MEMORY_MAP.md](../../rom-analysis/MEMORY_MAP.md)) | `phase` (set and cleared around flash access), `fail` (cleared, then 03h) |
| `ROMFONT` | 3D00h | the Spectrum ROM's character set, 96 glyphs for 20h–7Fh, 8 bytes each (3D00h–3FFFh) | `start` copies it to `FONT` while the ROM is still there |
| `SCREEN` | 4000h | the 6144-byte pixel file | `cls`, `char_at` |
| `ATTRS` | 5800h | the 768 attribute bytes | `cls` |
| `CODE_AT` | 6000h | where the code is assembled and loaded: chunk 3, RAM under every HSR; `RANDOMIZE USR 24576` | `ORG`; the loader |
| `FONT` | 7000h | the font copy, 768 bytes; glyph 7Fh is overwritten with a solid cell | `start`, `char_at`; `code_end` must not reach it |
| `BUF` | 7400h | one 256-byte block and its XOR, 257 bytes; also the 4-byte `'I'` reply | `start`, `phase`, `fetch` |
| `STACK` | 7FF0h | the updater's stack pointer, set at `start`; BASIC's stack is below 6000h after `CLEAR 24575` | `start` |
| `HSR_SLOT1` | F6h | chunks 1, 2, 4–7 from the DOCK: slot 1 at 8000h–FFFFh plus the command addresses | `phase` |
| `HSR_SLOT0` | 07h | chunks 0–2 from the DOCK: slot 0's lower 24K at 0000h–5FFFh | `phase` |

The failure reasons are the `'X'` argument and the index into `m_fail`:

| Name | Value | Meaning | Raised by |
|---|---|---|---|
| `X_PICO` | 1 | no answer to `'I'`, or not `'T'`,`'P'` | `start` |
| `X_BLOCKED` | 2 | the first erase did not take and nothing has changed yet: P10 not fitted | `phase` `.eraseerr` with `touched` = 0 |
| `X_XFER` | 3 | a block failed its XOR check five times, or five `'R'`s went unanswered | `phase` `.xfererr` |
| `X_WRITE` | 4 | a byte did not program or a block did not verify, twice; or a later erase failed | `phase` `.writeerr`/`.progerr` on the second try, `.eraseerr` with `touched` = 1 |

The Spectrum ROM is used, but never called. What the code depends on:
LD-BYTES at 0556h, through the loader's `LOAD ""CODE`, with its `'L'` at
055Fh–0561h and the fixed delay at 0563h ([PATCH_ZX48_HANDSHAKE.md](../../rom-analysis/PATCH_ZX48_HANDSHAKE.md)
§2); the character set at 3D00h; the USR return into the ROM, which
`updater_hosttest.py` models at 1303h. No system variable is read or
written by the updater; the loader's `CLEAR 24575` sets RAMTOP so BASIC
stays below 6000h.

### `start` (6000h)

Entry from `RANDOMIZE USR 24576`: the ROM has just called 6000h with
interrupts on and its own stack. Exit: never, on success (`DI` + `HALT`);
through `fail` on failure, which returns to BASIC or halts.

1. `DI`; save SP in `saved_sp`; `SP = STACK`; `touched = 0`.
2. Copy 768 bytes from `ROMFONT` to `FONT` (the ROM is still intact and
   readable); overwrite glyph 7Fh (`FONT + 2F8h`) with eight FFh bytes, the
   solid cell `tick` draws.
3. `cls`; `print_msgs m_title`.
4. `A = 'I'`, `request`: `OUT (0Fh),'I'` and wait for READY (~4 s). No
   carry: `.nopico`. `recv` 4 bytes into `BUF`; `BUF` must be `'T'` and
   `BUF+1` `'P'`, else `.nopico`: `A = X_PICO`, `jp fail`. The version byte
   and the fourth byte are not checked.
5. `.go`: `phase` with A = 1 (slot 1), then with A = 0 (slot 0). Each
   returns only on success.
6. `status 'D', C = 0`; `print_msgs m_done`; `DI`; `.stop: HALT; jr .stop`.
   With interrupts off the HALT never ends. HSR is 0 here (the last
   `phase` left it so), so chunks 0–1 are the freshly written TS-2068 ROM,
   which is never fetched.

On the Pico: the `'I'` makes `serve` leave tape mode and answer `'T'`,
`'P'`, 1, 0; the `'D'` is reported and nothing else happens. The page shows
"Both ROMs written and verified" and asks the user to switch the 2068 off.

### `phase` (6068h)

One image: erase, then block by block fetch, program, verify. In: A = the
image, 1 for slot 1 (32K, eight sectors, 128 blocks) or 0 for slot 0 (the
lower 16K, four sectors, 64 blocks). Out: returns through `status 'V'`,
so carry is that call's (set if the Pico answered; the comment's "carry
set" is not guaranteed, and `start` does not look). Corrupts AF, BC, DE,
HL. Two tries at the whole image. Reads and writes `img`, `tries`, `hsr`,
`base`, `nblocks`, `blk`, `zx_touched`, `touched` (through `erase`).

1. `img = A`; `tries = 2`.
2. `.again`: `status 'P', C = img`. Pick the mapping: `img` ≠ 0 gives
   `A = HSR_SLOT1`, `HL = 8000h`, `B = 8`; `img` = 0 gives `HSR_SLOT0`,
   `HL = 0000h`, `B = 4`. `.map`: `hsr = A`. For `img` = 0, `zx_touched = 1`
   now, before the first erase: from here there is no way back to BASIC.
   `base = HL`; `nblocks = B * 16` (four `ADD A,A`); `OUT (F4h),hsr`.
3. `.erase`: `erase` the sector at HL; no carry means `.eraseerr`.
   `HL += 1000h`; `DJNZ .erase`. Then `OUT (F4h),0`; `status 'E', C = img`.
4. `blk = 0`. `.block`: `fetch` block `blk` of image `img` into `BUF`; no
   carry means `.xfererr`. `OUT (F4h),hsr`; `HL = base + blk * 256` (add
   `blk` to H); push HL. `.prog`: 256 times, `A = (DE)`, `program` at HL;
   no carry means `.progerr`. Pop HL. `.verify`: 256 times compare `(DE)`
   with `(HL)`, a read of the chip now idle; a mismatch means `.writeerr`.
   `OUT (F4h),0`; `tick` (one cell on the screen); `status 'W', C = blk`;
   `blk += 1`; loop while `blk` ≠ `nblocks`.
5. `status 'V', C = img` and return.

The error exits:

- `.progerr` pops the HL it pushed, then `.writeerr`: `OUT (F4h),0`;
  `tries -= 1`; if not zero, `.again`: the whole image is erased and
  written over. Else `A = X_WRITE`, `fail`.
- `.xfererr`: `A = X_XFER`, `fail`. No second try: `fetch` already made
  five.
- `.eraseerr`: `OUT (F4h),0`; `A = X_BLOCKED` if `touched` is 0 (no erase
  has changed anything yet: the jumper is missing), else `X_WRITE`; `fail`.
  No retry of an erase.

Why slot 1 first, and why `zx_touched` is set before the erase rather than
after the first sector changes: the Spectrum ROM is the only way back to
BASIC, and the code cannot tell a partly erased sector from an intact one
cheaply, so it treats the ZX ROM as gone from the moment it starts on it.
Conservative: a slot-0 erase that fails without changing anything (P10
pulled between the phases) still ends in the halt, not in BASIC.

The Pico's side: the `'P'`, `'E'`, `'W'`, `'V'` statuses are each one `'S'`
request and one-byte answer; the page turns `'P'` into the phase message,
each `'W'` into `(blocks before + arg + 1) / 192` of the bar, `'V'` into a
log line. Timing per block, as the comments give it: 257 reads at ~44 µs,
256 programs at ~20 µs typical, 256 verify reads; `updater_hosttest.py`
measures 7.8 s of Z80 time for both images in its model *(hardware timing
unverified here)*.

### `erase` (6147h)

Erase the 4K sector at HL, HSR already mapped. In: HL = the sector's
address. Out: carry set = the sector's first byte reads FFh now. Keeps BC,
DE, HL; corrupts AF. Writes `was_data` and `touched`.

1. If `(HL)` is not FFh, `was_data = 1`: the sector held data, so FFh
   afterwards proves the chip took the command.
2. The six-cycle sequence: AAh→5555h, 55h→2AAAh, 80h→5555h, AAh→5555h,
   55h→2AAAh, 30h→(HL).
3. `.poll`: read `(HL)`, `RLA` puts DQ7 in carry; loop while it is 0, at
   most 65536 reads (DE counts down from 0). The comment gives the chip's
   erase as ~0.6 s at most.
4. `.done`: read `(HL)` again; not FFh is `.bad`, carry clear. Otherwise,
   if `was_data`, `touched = 1`; carry set.

Only the first byte of the sector is checked here; the per-byte verify in
`phase` covers the rest. `was_data` is never cleared, so once any sector
held data every later successful erase sets `touched` too; harmless, since
`touched` is only consulted when an erase fails, to choose between
`X_BLOCKED` and `X_WRITE`. A sector that read FFh before and still does
"proves nothing, but then programming it fails straight away, still having
changed nothing" (the comment): with P10 missing, the first sector of
either slot holds the ROM's first byte, so this case does not arise in
practice. Called by `phase`.

### `program` (618Eh)

Program byte A at HL, HSR already mapped. In: A = the byte, HL = the
address. Out: carry set = `(HL)` reads back as A. Keeps BC, DE, HL;
corrupts AF.

1. `C = A`; AAh→5555h, 55h→2AAAh, A0h→5555h, then `(HL) = C`.
2. `.poll`: read `(HL)`, XOR with C, test bit 7: zero means DQ7 now shows
   the data, done; else loop, up to 256 reads (the comment: ~20 µs is
   typical).
3. `.done`: `(HL)` compared with C; equal gives carry set, else clear.

Bits only go from 1 to 0, so this is only correct on an erased sector;
`phase` guarantees that. Called by `phase`'s `.prog` loop, 256 times a
block.

### `request` (61B1h)

`OUT (0Fh),A`, then fall into `wait_ready`. In: A = the request byte
(`start` uses it for `'I'`; `status` and `fetch` write 0Fh themselves).
Out: as `wait_ready`. The write to 0Fh lands in the Pico's RX FIFO with bit
8 set, which is how `serve` tells a request from tape chatter, and drops the
status to BUSY (auto-busy) so that the READY the Z80 then waits for is the
one `reply` raises for this request. Keeps DE, HL; corrupts AF, B.

### `wait_ready` (61B3h)

Poll port 0Fh bit 6 until set. Out: carry set = READY; carry clear after
4 × 65536 polls, ~4 s. Keeps DE (pushed), HL, C; corrupts AF, B. The same
shape as the ZX v3 ROM's `WAIT_RDY` at 3874h ([ROM_CHANGES.md](../../ROM_CHANGES.md),
"ZX Spectrum ROM v3"), with B as the outer and DE as the inner counter. The
timeout path leaves carry clear from the `OR E` that ended the last inner
loop; `DJNZ`, `POP` and `RET` do not touch it. Called by `request`,
`status`, `fetch`.

The ~4 s is what gives `serve`'s 100 ms argument timeouts room: a request
whose arguments the Pico dropped simply times out here and is repeated by
the caller.

### `send` (61CBh)

`OUT (0Eh),A`, then `B = 11`, `DJNZ`: ~50 µs for the Pico's 4-deep RX FIFO
and `RX_WORD`'s polling. In: A = the byte. Keeps everything, including A
and the flags (BC is pushed; `DJNZ` sets no flags). Called by `status` and
`fetch` for the argument bytes; the request byte itself goes out through
`OUT (0Fh)` directly.

### `recv` (61D4h)

Read DE bytes from port 0Eh to (HL), ~44 µs apart. In: HL = destination,
DE = the count, at least 1. Out: HL past the last byte, DE = 0; corrupts
AF, B. Each byte: `B = 8`, `DJNZ`, `IN A,(0Eh)`, store, `INC HL`, `DEC DE`,
loop while DE ≠ 0. There is no handshake per byte and no check: an empty TX
reads 00h. The cadence is LOAD's: too fast for a Python loop on
MicroPython v1.29, which is why `reply` sends a block by DMA (2026-10-06);
`updater_hosttest.py` asserts every reply read is ≥ 40 µs after the previous
and that none came from an empty TX, in a model where the Pico is never
late. Called by `start` (4 bytes), `status` (1), `fetch` (257).

### `status` (61E2h)

Tell the Pico `'S'`, code A, argument C. In: A = the code letter, C = the
argument. Out: carry set = the Pico answered, its byte in `ack`; carry
clear after `wait_ready`'s timeout, `ack` untouched. Keeps DE, HL (pushed),
C; corrupts AF, B.

1. Push HL, DE, AF; `OUT (0Fh),'S'`; pop AF.
2. `send` the code; `send` C.
3. `wait_ready`; no carry means `.done`.
4. `recv` 1 byte into `ack`; `SCF`.
5. `.done`: pop DE, HL; return.

On the Pico: `serve` reads the two arguments with `RX_WORD`, queues the
00h, raises READY, prints the `status` line; for `'X'` it also waits for
the byte to be read and rewinds the tape. No caller checks the carry: a
status is best effort, and with no Pico the update fails on its own
timeouts anyway (`X_PICO` at `start`; later, `X_XFER` through `fetch`).
Called by `start`, `phase`, `fail`.

### `fetch` (6203h)

`BUF` = block `blk` of image `img`, XOR-checked, five tries. Out: carry set
= the 257 bytes are in `BUF` and XOR to zero. Corrupts AF, B, DE, HL.
Reads `img`, `blk`; writes `xtries`.

1. `xtries = 5`.
2. `.try`: `OUT (0Fh),'R'`; `send img`; `send blk`; `wait_ready`; no carry
   means `.retry`.
3. `recv` 257 bytes to `BUF`. XOR all 257 (256 in the `DJNZ` loop, then one
   more): nonzero means `.retry`. Else carry set, return.
4. `.retry`: `xtries -= 1`; if not zero, `.try`; else carry clear, return.

On the Pico: the `'R'` branch of `serve`. A dropped request (argument
timeout) costs one try through `wait_ready`'s ~4 s (an `'R'` that arrives
while the previous reply is still going is handed back by `reply` and
answered); a reply that was
read out of step fails the XOR and costs one try at once. `updater_hosttest.py`
pins both: three bad XORs still complete, endless bad XORs end in `X 3`
with the Spectrum ROM intact. Called by `phase`.

### `fail` (6240h)

Give up with reason A. In: A = the reason, 1–4. Out: to BASIC, with SP
restored, interrupts on and HSR = 03h, when slot 0 is still intact;
otherwise never (halt). Reads `img`, `zx_touched`, `saved_sp`; writes
`reason`.

1. `reason = A`; `OUT (F4h),0` (the screen and HOME RAM back, whatever the
   failing routine had mapped).
2. `status 'X', C = reason`. On the Pico this is the one status with a
   side effect: `serve` drains TX, leaves service mode and re-arms the tape.
3. `HL = m_fail[reason]` (a word table indexed by `reason * 2`);
   `print_msgs`.
4. If `img` ≠ 0 (the failure was in slot 1's phase, or at `start`, where
   `img` is still 0 but `zx_touched` is too), or `zx_touched` = 0: `.basic`.
   Else: `print_msgs m_stuck`; `DI`; `.stop: HALT`.
5. `.basic`: `OUT (F4h),03h`, the Spectrum ROM mapped as `OUT 244,3` left
   it; `SP = saved_sp`; `EI`; `RET`, into the ROM's USR return. BASIC goes
   on with the loader's line 30, `PRINT "LOAD """" to try again."`, and
   stops with 0 OK. BC, the USR result, is whatever was left in it.

What the machine is left in, by path: to BASIC, the Spectrum ROM running,
the screen showing the title and the failure text in black on white,
interrupts on, the TS-2068 ROM in slot 1 either untouched (`X_PICO`,
`X_BLOCKED`, a first-try `X_XFER`) or partly rewritten (slot 1 erased or
half written: a `LOAD ""` runs the updater again, which erases and rewrites
it from the start). Halted, after slot 0 was touched: both images may be
anything; slot 1 is complete and verified, since slot 0's phase only starts
after it, and the page's next steps (firmware, files) proceed; the ZX ROM
can be rewritten later from the new firmware's own ROM-update path with the
`.BIN` from the release *(inferred; the manual's A.4–A.5 describe that path
for slot 1)*. `updater_hosttest.py` checks the stack comes back balanced,
HSR = 03h and interrupts on at the BASIC return.

### `cls` (6281h)

Clear the screen: 6144 pixel bytes to 0, 768 attributes to 38h, black ink
on white paper, with two `LDIR`s. Corrupts BC, DE, HL and the flags `LDIR`
sets; keeps A. Called by `start`. The ROM's own screen variables are not
updated; nothing in the updater uses them, and the return to BASIC prints
over what is there.

### `print_msgs` (629Ch)

Print a message list. In: HL → a sequence of (row byte, text, 00h)
entries ended by a row byte of FFh. Out: HL past the FFh; corrupts AF, BC,
DE. Each entry is printed at column 0 by `print_at`. Called by `start`
(`m_title`, `m_done`) and `fail` (`m_fail`'s entry, `m_stuck`).

### `print_at` (62A9h)

Print the 00h-ended text at HL at row B, column C. Out: HL after the 00h,
C advanced by the length; corrupts AF, DE. One `char_at` per character, no
wrap: the messages are at most 31 characters. Called by `print_msgs`.

### `char_at` (62B3h)

Draw character A at row B (0–23), column C (0–31), from the font copy.
Keeps BC, HL (pushed); corrupts AF, DE. Glyph address: `FONT + (A - 20h) *
8`. Screen address: `D = 40h | (B & 18h)`, `E = (B & 7) << 5 | C`, the
Spectrum's layout (the `RRCA` × 3 of `B & 7` is a shift left by 5 for an
8-bit value); then eight rows, `INC D` between them. No range check: an A
below 20h would read below `FONT`. Called by `print_at` and `tick`.

### `tick` (62DAh)

One filled cell per block. Reads `blk` and `img`; corrupts AF, BC, DE;
keeps HL. Column = `blk & 1Fh`; row within the bar = `blk >> 5` (three
`RLCA` and `AND 7`); the bar starts at row 6 for slot 1 (128 blocks: rows
6–9) and row 12 for slot 0 (64 blocks: rows 12–13); character 7Fh, the
solid cell `start` put into the font copy. Ends with `JP char_at`. Called
by `phase` after each block's verify, with HSR = 0.

### The text

Each table is a `print_msgs` list: row, text, 00h, …, FFh. They are placed
so that the title stays while the failure text (rows 16–18) or the done
text (rows 16–17) appears below the bars.

| Name | Rows | Text | Printed by |
|---|---|---|---|
| `m_title` | 0, 2–3, 5, 11 | "TS-Pico ROM update"; "Don't turn off the 2068 or the / Pico until this says DONE."; "TS-2068 ROM (slot 1):"; "ZX Spectrum ROM (slot 0):" | `start` |
| `m_done` | 16–17 | "DONE. Finish on the web page, / then turn the 2068 off and on." | `start` |
| `m_stuck` | 20–22 | "The ZX ROM is incomplete, but / the 2068 ROM is new: finish on / the web page." | `fail`, after slot 0 was touched |
| `m_fail` | — | a word table: 0, `f_pico`, `f_blocked`, `f_xfer`, `f_write`, indexed by the reason | `fail` |
| `f_pico` | 16–17 | "No answer from the TS-Pico. / Is the upgrade firmware on it?" | `fail`, `X_PICO` |
| `f_blocked` | 16–18 | "The flash can't be written: / fit the P10 jumper, then / LOAD "" again." | `fail`, `X_BLOCKED` |
| `f_xfer` | 16–17 | "The TS-Pico's data keeps coming / in wrong. LOAD "" to try again." | `fail`, `X_XFER` |
| `f_write` | 16–17 | "A write didn't take. / LOAD "" to try again." | `fail`, `X_WRITE` |

The page shows its own wording for the same reasons (`ROM_FAIL` in
`app.js`); `updater_hosttest.py` reads rows 16, 17 and 21 back off the
modelled screen through the font copy.

### The variables

All in the code block, 650Dh–651Bh, reloaded with their assembled values
by every `LOAD ""CODE`, so a second run after a return to BASIC starts
clean. None is cleared at `start` except `touched`.

| Name | Size, initial | Set by | Read by | Invariant |
|---|---|---|---|---|
| `saved_sp` | word, 0 | `start` | `fail` `.basic` | BASIC's SP at entry; valid while the updater runs |
| `img` | byte, 0 | `phase` | `phase`, `fetch`, `tick`, `fail` | the image being written: 1 then 0; 0 before any phase, which `fail` tells apart by `zx_touched` |
| `blk` | byte, 0 | `phase` | `phase`, `fetch`, `tick` | the block being written, 0 to `nblocks` - 1 |
| `nblocks` | byte, 0 | `phase` | `phase` | sectors × 16: 128 or 64 |
| `hsr` | byte, 0 | `phase` | `phase` | `HSR_SLOT1` or `HSR_SLOT0` for the current image |
| `base` | word, 0 | `phase` | `phase` | 8000h or 0000h: the image's Z80 address under `hsr` |
| `tries` | byte, 0 | `phase` | `phase` | tries left for the image, 2 down to 0 |
| `xtries` | byte, 0 | `fetch` | `fetch` | tries left for the block, 5 down to 0 |
| `reason` | byte, 0 | `fail` | `fail` | the `'X'` argument and the message index |
| `touched` | byte, 0 | `start` (0), `erase` (1) | `phase` `.eraseerr` | 1 once any erase has changed the chip: the jumper is there |
| `was_data` | byte, 0 | `erase` | `erase` | 1 once any erased sector held data; never cleared |
| `zx_touched` | byte, 0 | `phase` for image 0 | `fail` | 1 from the moment slot 0's erase is about to start: no way back to BASIC |
| `ack` | byte, 0 | `status` (via `recv`) | nobody | the Pico's one-byte answer to an `'S'`, always 00h |

### `code_end` (651Ch)

The end of the binary: 1308 bytes from 6000h. `ASSERT code_end <= FONT`
keeps the code, text and variables out of the font copy at 7000h; the
build fails rather than overlap. 7000h–7FFFh above it is the font, `BUF`
and the stack. (A `VARS` EQU at 7600h, never used -- the variables live in
the code block, `saved_sp` onwards -- went in #181.)

## src/upgrade/loader.bas

The BASIC loader, the first program on the tape, written in Spectrum tokens
(zmakebas's default) because the original Spectrum ROM is what loads it. It
is the first two blocks of `updater.tap` (header and program, name
`tsupdate`, auto-start at line 10, from `build-upgrade.py`'s `zmakebas -a 10
-n tsupdate`). Every line:

- `10 CLEAR 24575: PRINT "Loading the TS-Pico ROM updater"` — `CLEAR 24575`
  sets RAMTOP to 5FFFh, so BASIC's variables, workspace and stack stay below
  6000h, out of the updater's chunk (the file's comment); the `PRINT` tells
  the user the second block is coming. `CLEAR` also deletes the variables,
  does CLS and clears the GO SUB stack, which is why it runs first.
- `20 LOAD ""CODE : RANDOMIZE USR 24576` — the second `LOAD` takes the
  tape's third and fourth blocks, the `updater` CODE header and its 1308
  bytes, to the header's own address 6000h (`build-upgrade.py` writes 6000h
  as the start and 8000h as the second parameter); `USR 24576` calls `start`.
  On success the call never returns; on a failure before slot 0 is touched
  it returns here and the line ends.
- `30 PRINT "LOAD """" to try again."` — reached only after a return from
  `fail`; the doubled quotes print `LOAD ""`. The program then stops with
  0 OK, and the Pico, having heard the `'X'`, has the tape armed for the
  next `LOAD ""`.

The `tsupdate` program and the `updater` CODE block are what
`upgrade_hosttest.py` checks arrive whole, in order, with their CRCs right.

## src/upgrade/manifest.py

The MicroPython freeze manifest for the upgrade UF2, used in place of
[`src/manifest.py`](boot.md) by `make … FROZEN_MANIFEST=…` (CI copies it to
`ports/rp2/boards/manifest_upgrade.py`). It freezes the port's `_boot.py`
and `rp2.py`, then from `modules-upgrade/`, which CI stages:
`TS/__init__.py`, `TS/tspico_io.py`, `TS/sdcard.py`, `TS/native.py`,
`upgrade.py`, `upgrade_data.py` and `main.py`.

Why `main.py` is frozen: the web page erases the Pico's flash before it
writes this UF2 (its "wipe" step, or `flash_nuke.uf2` by hand), so there is
no filesystem to put a `main.py` on, and MicroPython runs a frozen `main.py`
at boot when the filesystem has none. The other side of that rule: a
`main.py` left on the filesystem takes priority, which is why the page
forces the wipe on whenever the ROM update is ticked (`refreshPlan` in
`app.js`), and why running the upgrade UF2 by hand means renaming `/main.py`
first ([DEVELOPER_GUIDE.md](../../DEVELOPER_GUIDE.md)).

Why `TS/sdcard.py` and `TS/native.py` are frozen though the upgrade never
mounts a card or opens a file: `tspico_io.py` imports them at module level,
and a frozen module whose import fails kills `main.py` before it has
started the ROM and bank state machines. #82 added `from TS import native`
to `tspico_io` without adding it here; until 2026-10-01 the upgrade UF2
died at boot with `ImportError`, the 2068 beeped at power-on, and the ROM
step could not start (the comment; [DEVELOPER_GUIDE.md](../../DEVELOPER_GUIDE.md)).
The rule now: every module `tspico_io` imports at load must be listed here
and staged by both workflows; `upgrade_hosttest.py` checks both, by walking
the frozen files' ASTs outside function bodies (a lazy import inside a
function, like `SAVE_TS`'s `from TS.tspico import TLM`, is allowed as long as
the upgrade never calls it).

`updater.bin` is the assembled `updater.asm`, committed because the build
does not run sjasmplus. `updater_hosttest.py` rebuilds it from the source
and compares when `sjasmplus` is installed, and skips the check otherwise.
Change the `.asm`, reassemble in `src/upgrade/` (the `OUTPUT` directive
names the file), and commit both.

## tools/build-upgrade.py

`python3 tools/build-upgrade.py OUT_DIR` writes `OUT_DIR/upgrade_data.py`
and `OUT_DIR/updater.tap` (default `OUT_DIR`: `build-upgrade/`).

The ROM images come from [`flash/manifest.json`](../../../flash/manifest.json),
so the upgrade installs exactly what the 512K flash image ships
([../rom/overview.md](../rom/overview.md), [flash/README.md](../../../flash/README.md)):
`IMG1` is slot 1's file whole, `src/rom/TSPICO-22.ROM`, 32K, and `IMG0` is
the first 16K of slot 0's, `src/rom/TSPICO-ZX48-V4.BIN`; an `assert` pins
the two lengths. Their crc32s go into the generated file's header comments
and into `IMG1_CRC` and `IMG0_CRC`, which nothing reads yet.

The tape: `zmakebas` (the one on the path, else the vendored
`tools/zmakebas/zmakebas.c` compiled into a temporary directory) tokenizes
`loader.bas` with `-a 10` (auto-start line 10) and `-n tsupdate` (the name)
into a `.tap` of two blocks; then `block()` appends a CODE header, type 3,
name `updater` padded to 10, the length of `updater.bin`, start 6000h,
second parameter 8000h, and the data block with the binary. `block()` is
the TAP format: a 2-byte length, the flag (00h header, FFh data), the
content, and the XOR of flag and content. `TAPE` is those bytes; `serve`
hands them to `TAPE_STREAM_OF`, which strips the lengths again.

`upgrade_data.py` is three `bytes` literals and two ints, with a "do not
edit" header; it is generated into the build and never committed.

## The upgrade build in CI

[`build.yml`](../../../.github/workflows/build.yml) ([boot.md](boot.md) has
the firmware's half):

1. "Run host-side tests" includes `updater_hosttest.py` and
   `upgrade_hosttest.py`, so a change to the asm, the loop, the manifest or
   the workflows' staging line fails before anything is built.
2. "Build the upgrade payload (updater tape + ROM images)":
   `tools/build-upgrade.py "$RUNNER_TEMP/upgrade"`.
3. "Stage the upgrade UF2's frozen modules": copies `src/TS/__init__.py`,
   `tspico_io.py`, `sdcard.py`, `native.py` to `ports/rp2/modules-upgrade/TS/`,
   `src/upgrade/upgrade.py`, `main.py` and the generated `upgrade_data.py`
   to `modules-upgrade/`, and `src/upgrade/manifest.py` to
   `boards/manifest_upgrade.py`. `upgrade_hosttest.py` requires the `cp …
   modules-upgrade/TS/` line to name exactly the manifest's `TS` files.
4. "Build the upgrade UF2": `make -j BUILD=build-UPGRADE
   FROZEN_MANIFEST=$PWD/boards/manifest_upgrade.py` in `ports/rp2`, a
   second MicroPython build next to the firmware's `build-RPI_PICO`.
5. "Upload the upgrade UF2 artifact": `tspico-upgrade-uf2`, holding
   `build-UPGRADE/firmware.uf2` and `updater.tap` (30 days). The UF2 keeps
   its build path inside the artifact, which `pages.yml` and the README's
   local recipe allow for with `find … -path '*build-UPGRADE/firmware.uf2'`.
6. "Test the web updater's flasher with the built UF2s" runs
   `web-updater/test/flasher.test.mjs` against both UF2s.

[`release.yml`](../../../.github/workflows/release.yml) does steps 2–4 in
one step, "Build the upgrade UF2", copies the result to
`$RUNNER_TEMP/upgrade.uf2`, and attaches it to the GitHub Release as
`upgrade.uf2 (ROM updater for boards coming from 1.1)` next to
`firmware.uf2` and the bundle ([v2.1 release notes](../../../.github/release-notes/v2.1.md),
[v2.1.2](../../../.github/release-notes/v2.1.2.md)).
`tools/pico-serial.py flash --upgrade` fetches the `tspico-upgrade-uf2`
artifact instead of the firmware's, for flashing a board by hand.

## web-updater/build-payload.sh — the channels

The page installs from a channel directory it fetches same-origin, because
GitHub's release-asset CDN sends no CORS header and CI artifacts need a
token ([web-updater/README.md](../../../web-updater/README.md)).
`build-payload.sh [SRC_DIR] [TAG] [UF2_PATH]`, with `OUT_DIR`, `CHANNEL`,
`UPGRADE_UF2`, `SDCARD_DIR` and `SOURCE_URL` in the environment, assembles
one:

- `pico/`: `main.py`, `config.ini`, `words.txt` and `assets/*.tap` from
  `SRC_DIR`, the files the firmware needs on its LittleFS, which the UF2
  does not carry. It refuses to build if `nofile.tap`, `romupdate.tap` or
  `dckupdate.tap` is missing, since `tools/build-basic.sh` generates them
  and a board installed without them silently lacks `LOAD ""` with nothing
  mounted and the ROM/DCK updaters.
- `firmware.uf2` and `firmware-uf2.zip` (the zip for Windows setups that
  quarantine a raw `.uf2`), when a UF2 path is given.
- `upgrade.uf2`, when `UPGRADE_UF2` names one; otherwise the manifest's
  `upgrade_uf2` is `null` and the page disables the ROM step for that
  channel.
- `sdcard.zip`, the SD card folder, when present.
- `manifest.json`: `channel`, `tag`, `source_url`, `fw_version` and
  `rom_version` from `config.ini`, `mp_version` (the `MicroPython vX.Y.Z`
  string found in the UF2's 256-byte payloads, so the page can warn before
  installing an older MicroPython over a newer one, whose filesystem
  format the older one reformats), `uf2`, `uf2_zip`, `upgrade_uf2`,
  `sdcard`, and `files` (path and size of each `pico/` file, which the page
  writes and then verifies by size).

[`pages.yml`](../../../.github/workflows/pages.yml) builds two channels
next to the page: `release/` from the latest GitHub Release's `firmware.uf2`
and `upgrade.uf2` assets and the Pico files at its tag, and `main/` from the
latest green `build.yml` run's `tspico-firmware-uf2` and
`tspico-upgrade-uf2` artifacts and the files at its commit, with the TAPs
rebuilt by `build-basic.sh` for that commit. A release from before
`upgrade.uf2` existed has `upgrade_uf2: null`, and the page points at the
other channel.

## The web updater's side of the UPG protocol

[`app.js`](../../../web-updater/app.js) runs the six stages: connect,
BOOTSEL, wipe, ROM, firmware, files. What matters to this chapter is how it
gets the upgrade UF2 onto the Pico, what it does with each `UPG` line, and
how it moves on.

**Deciding to do the ROM step.** `readInstalled` asks the running firmware
for its `FW_VERSION` over the raw REPL (`sys.modules['TS.tspico']` or
`dev_tspico`), falling back to `/config.ini`'s, then to "1.1 (no version in
config.ini)"; `from1x` is a major below 2, and `ver` is the running
module's major.minor (`verOf`), null when it came from `config.ini` or
nowhere. The ROM can't be read over USB, so `romBehind` takes the firmware
version for the ROM's: the ROM step is due when `ver` is older than the
channel's `rom_version`, or unknown (a wiped Pico, a 1.x board), since in
practice every board out there still has 1.1's ROM; only a board already on
the channel's major.minor skips it. `connect`, and `loadChannel` when a
board is already connected, tick "Update the TS-2068 ROM" when
`romBehind()` and the channel has `upgrade_uf2`. `refreshPlan` forces
"Erase the Pico first" on whenever the ROM step is ticked, because the
upgrade UF2's frozen `main.py` must not be shadowed; it warns a 1.x board
that unticks the ROM step that its ROM cannot talk to the new firmware, and
any other board behind the channel that unticking leaves its older ROM.
Before 2.2 it ticked the step for `from1x` alone.

**Getting into BOOTSEL and wiping.** `enterBootsel` runs
`machine.bootloader()` over the REPL (`execNoReply`: raw REPL, the code,
Ctrl-D, close the port) and then takes a handle on the boot ROM from
[`flasher.js`](../../../web-updater/flasher.js): `UsbBootsel` over
WebUSB/PICOBOOT (`Picoboot.requestDevice` or a device already permitted,
`setExclusiveAccess(1)`, `exitXip()`), or `DriveBootsel`, a
`showDirectoryPicker` handle on the RPI-RP2 drive checked by its
`INFO_UF2.TXT`. The wipe is `UsbBootsel.wipe`, PICOBOOT erases of the whole
2 MB in 64K pieces, or `DriveBootsel.wipe`, which writes `flash_nuke.uf2`
onto the drive and waits up to 60 s for RPI-RP2 to come back.

**Writing a UF2.** `writeImage` fetches `${channel}/${path}` and calls
`boot.writeUf2`. Over WebUSB: `checkUf2` (the two magic words; the RP2040
family id when the family flag is set), `uf2ToFlashBuffer` to a flat image
and its address, a bounds check against 0x10000000 + 2 MB, padding to 4K
sectors with 0xFF, PICOBOOT erase in 64K pieces, write in 16K pieces, then
read back and compare every byte, with the progress bar counting erase,
write and read as thirds. Over the drive: write the file, then wait up to
15 s for the drive to vanish, which is the success signal because the Pico
reboots on the last block and Chrome's close of the file is expected to
fail. `UsbBootsel.reboot` is a PICOBOOT reboot; the drive path reboots by
itself.

**The ROM step** (`romUpdate`): `writeImage('rom', …upgrade_uf2…)`,
`boot.reboot()`, `reconnectSerial('rom')`, which polls `navigator.serial.getPorts()`
for a Pico (VID 0x2E8A) the site already has permission for, up to 30 s,
and only then asks for a click. It shows the `rom-steps` box from
`index.html`, the six instructions the user follows on the 2068 (fit P10
and leave it, switch the 2068 on, `OUT 244,3`, `LOAD ""`, wait for DONE,
switch the 2068 off again), and attaches `serial.onReceive`, which buffers
the text, splits on newlines, keeps lines starting with `UPG `, parses the
JSON and calls `onUpg`. Every event but a `W` status is also logged as
`2068: key=value …`. Per event:

| Event | The page |
|---|---|
| waiting | "Waiting for LOAD "" on the 2068…" |
| tape without note | "Loading the updater from the TS-Pico…" |
| tape with note | "The updater stopped; the tape rewound. Type LOAD "" again."; `writing` cleared |
| ignored | "That went to the TS-2068 ROM, not the Spectrum ROM. Type OUT 244,3 first, then LOAD ""." (warning) |
| updater | "The updater is running. Don't turn anything off."; `writing` set; the escape-hatch buttons withdrawn |
| status P | `phase` = `arg`; "Writing the TS-2068 ROM (slot 1)…" or "Writing the ZX Spectrum ROM (slot 0)…" |
| status W | the bar at `(blocks before this phase + arg + 1) / 192`, with `ROM_BLOCKS = {1: 128, 0: 64}` |
| status V | `slot1Done` for phase 1; "Slot n verified." in the log |
| status D | bar full; "Both ROMs written and verified. The 2068 says DONE."; the step resolves |
| status X | `ROM_FAIL[arg]`, the page's wording of the four reasons, plus "The TS-2068 ROM is already new; you can also continue without the ZX ROM." once slot 1 verified; `writing` cleared, the step waits for the user to `LOAD ""` again |
| status E, bad-request | logged only |

A 1 s watchdog rejects the step if the serial port goes away ("The Pico
disconnected during the ROM update…") and, after 45 s without an event
while the updater is not writing, offers "The 2068 says DONE — continue"
and "Stop": the escape hatch for a run whose lines did not arrive. It is
never offered while `writing`, because continuing reboots the Pico and the
updater needs it until DONE.

**Moving on.** When the step resolves, the page detaches the receiver,
marks the stage done, and asks the user to switch the 2068 off before it
continues ("The 2068 is off — continue"), because the next thing it does
is a hard reset of the Pico: a reset while the 2068 runs leaves the SD
card unreadable until it loses power
([sdcard.md](sdcard.md); the manual's §2.6), and the ROM chip is live under
a running 2068. Then `machine.bootloader()` over the REPL again, a new
BOOTSEL handle, `writeImage('firmware', …uf2…)`, `boot.reboot()`.

**What it writes to the Pico's filesystem afterwards** (`uploadFiles`):
`reconnectSerial('files', 45000)`, longer because the first boot after a
wipe formats the filesystem; raw REPL; for each entry of
`manifest.files`, fetch `${channel}/pico/${path}`, `raw.makePath` for its
folder and `raw.writeFile` (ViperIDE's `MpRawMode`: the bytes go over the
REPL in chunks); then `verifyFiles` walks the device with `raw.walkFs` and
compares every manifest path and size, failing the step on a missing file
or a size mismatch; then `machine.reset()`. The done panel tells the user
to unplug USB so the TS-Pico and its card really lose power, then switch
the 2068 on, and to leave P10 fitted.

The README still lists an end-to-end hardware pass on a 1.1 board and a
1.5 board, on macOS and Windows, as to do; the repo's own record of the
updater on a board is the harness that proved the tape path with a v15w
chip. Nothing in this chapter about the page's behaviour on a real board
goes beyond what the code says *(unverified)*.
