# TS/tspico_io.py — the bus I/O layer

Source: [`src/TS/tspico_io.py`](../../../src/TS/tspico_io.py) (2919 lines, CRLF).

This module is everything that moves bytes between the Z80 and the Pico. It
holds the PIO program for ports 0Eh and 0Fh and the three ROM-bank programs
(explained in [pio.md](pio.md)); the helpers that read and write the bus state
machine's two 4-deep FIFOs without ever blocking on them; the DMA paths that
keep those FIFOs fed and drained while core0 is busy; the helpers that set the
status byte the Z80 reads on port 0Fh (the PIO's Y register); `LOAD_TS` and
`SAVE_TS`, the two TPI block transfers; the ZX48-mode transfers `LOAD_ZX`,
`LOAD_ZX_C` and `SAVE_ZX`; the UPDATE-mode tape stream the upgrade UF2 serves;
and the SD mount the two SAVEs write through. The dispatcher in
`TS/tspico.py` ([tspico-dispatch.md](tspico-dispatch.md)) imports this module
and calls into it; this module never imports `tspico` at module level, because
`tspico` imports it (the one exception is `SAVE_TS`'s import of `TLM` inside
the function).

It is built into two firmwares. `firmware.uf2` (`src/manifest.py`) freezes
every `TS` module; `upgrade.uf2` (`src/upgrade/manifest.py`), the UF2 the web
updater writes to put a new ROM in flash slots 0 and 1, freezes only
`TS/__init__`, `tspico_io`, `sdcard` and `native`, and its own `main.py` builds
the three state machines from this file and runs `upgrade.serve`
([upgrade.md](upgrade.md)). So a module-level `from TS ...` import added here
that the upgrade manifest does not freeze makes the upgrade UF2 die at boot
with `ImportError`, before it has selected a ROM: the 2068 beeps and nobody can
update. That happened from #82 (`from TS import native`) until it was caught on
hardware on 2026-10-01. A new module-level import of a `TS` module needs a
`freeze()` line in `src/upgrade/manifest.py`, the file added to the `cp`
line in both `.github/workflows/build.yml` and `release.yml`, and no imports
of its own beyond what the upgrade firmware has;
[`upgrade_hosttest.py`](../../../src/test/upgrade_hosttest.py) checks the first
two. An import inside a function is fine as long as the upgrade code never
calls that function. See [DEVELOPER_GUIDE.md §5, "The upgrade UF2 is a second
build of tspico_io.py"](../../DEVELOPER_GUIDE.md).

Four rules shape almost every function here, and the entries below name them
rather than restate them: the two-phase capture rule (no per-byte Python work
while the Z80 is sending into a 4-deep FIFO at ~30 µs a byte;
[`src/CLAUDE.md`](../../../src/CLAUDE.md), "THE TWO-PHASE CAPTURE RULE"); no
allocation on a per-byte path, because a garbage collection stops core0 for
milliseconds ([programmers-manual.md ch. 14](../../manual/programmers-manual.md));
data into TX before READY, never the other way round
([PROTOCOL.md §3.2](../../PROTOCOL.md) and [DEVELOPER_GUIDE.md §7](../../DEVELOPER_GUIDE.md));
and every wait bounded, since issue #51 removed the core1 watchdog that used
to rescue a blocked `MQ.put()` or `MQ.get()`. The pitfalls behind them are
[PROTOCOL.md §13](../../PROTOCOL.md).

Words used below: READY means Y = 0xFFFFFFFF, so port 0Fh reads FFh (READY +
IDLE); "mid" is F7h (READY, transaction open); "recovered" is FBh (READY +
IDLE, RECOVERED low); busy is 00h, which the PIO sets on every Z80 OUT
(auto-busy, [PROTOCOL.md §3](../../PROTOCOL.md)). An RX word is 9 bits: D0–D7
and, in bit 8, A0; "a 0Fh write" is a word with that bit set, which only the
ROM's SYNC and BREAK send (both `OUT (0Fh),03h`; ROM 1.1 never writes
0Fh).

## Map of the file

In source order, with line numbers of the file as it is today:

- 1–16: imports. `rp2.DMA` is imported as `_DMA`, `None` on MicroPython v1.20
  and under the host tests' fake `rp2`; `machine.mem32` as `_mem32` (line
  109), `None` on a PC. `from TS.sdcard import *` and `from TS import native`.
- 18–43: the two-firmware import rule, as a comment.
- 45–95: module state and bus constants: `log_entries`, `_nofile_arch`,
  `PORT_0F`, `TX_DEPTH`, `LOAD_CHUNK`, `_LOAD_BUF`, `_LOAD_MV`.
- 97–150: the v3 card: `_tsbus_mq` (and `_DMA`, `_mem32` switched off),
  `DRAIN_MAX`, `LED`, `_LED`, `CAN_STREAM`.
- 153–198: the fast PIO exec and the status register: `_SM0_EXECCTRL`,
  `_SM0_INSTR`, `_SM0_PINCTRL`, `_ENCODED`, `MQX`, `MQ_STATUS`.
- 200–322: the pre-header capture: `RX_CAPTURE`, class `RxDMA` (`__init__`,
  `arm`, `waiting`, `stop`, `take`), `RX_DMA`.
- 325–364: USB stdin: `_stdin_ipoll`, `_stdin_readinto`, `_stdin_byte`,
  `DRAIN_STDIN`.
- 367–393: `MQ_TO_IDLE`.
- 396–588: sending: `TX_ROOM`, `ECHO_KEEP`, `STREAM_DMA`, `QUEUE_WAIT_MS`,
  `STREAM_QUEUE`, `RX_WORD`.
- 591–747: receiving blocks: `RXB_OK`, `RXB_ABORT`, `RXB_STALL`, `_RING_BITS`,
  `_RING_WORDS`, `_RING_SETUP`, `_ring`, `SAY_READY`, `RX_RING`, `RX_BLOCK`,
  `_SAVE_HDR_RAW`.
- 750–773: `OPEN_NOFILE_TAP`.
- 776–1041: the four PIO programs `sel_bank`, `set_ctrl`, `set_dck` and
  `TS_IO_DUAL`. They are explained instruction by instruction in
  [pio.md](pio.md); this chapter has no entries for them.
- 1044–1101: `REWIND_ABORTED_SEARCH`, `ENA_MQ_DUAL`.
- 1104–1205: the SD card and the log: `SD_MOUNT`, `ENA_SD`, `LOG_ADD`.
- 1208–1285: refusing a LOAD: `_ld_err`, `_ld_err_t`, `_ld_err_staged`,
  `LOAD_REFUSE`, `FIRST_STATUS`, `LOAD_RETRY_DONE`.
- 1288–1897: `LOAD_TS`, `LOAD_SERVE`.
- 1899–1939: ZX48 mode's limits and slow paths: `ZX_STALL_MS`,
  `ZX_BLOCK_GAP_MS`, `ZX_FLUSH_TX`, `ZX_ROOM`.
- 1942–2022: UPDATE mode: `TAPE_STREAM`, `TAPE_STREAM_OF`, `ZX_ARM`,
  `ZX_STREAM`.
- 2025–2308: `LOAD_ZX`, `ZX_C_BLOCKS`, `LOAD_ZX_C`.
- 2311–2417: SAVE helpers: `SAVE_NAME`, `REFUSE_SAVE`, `DRAIN_REFUSED_SAVE`.
- 2420–2893: `SAVE_TS`.
- 2896–3030: `_xor`, `SAVE_ZX`.

The last section of this chapter lists the places where a comment, a design
document and the code disagree.

## Module state and bus constants

### `log_entries`

A `str`, `""` at import. `LOG_ADD` appends one `[ticks_us] message\n` line
per call. `LOAD_TS`, `LOAD_ZX`, `SAVE_TS` and `SAVE_ZX` reset it to `""` on
entry (`LOAD_ZX_C` to `" "`), and each returns it as the last element of its
result tuple; `TS2068_IO` and `ZX48_IO` append that string to `tspico.py`'s own
`log_entries`, a list of a different object with the same name, which
`SAVE_LOG` writes to `/activity.log` on core1 ([tspico-files.md](tspico-files.md)).
Invariant: it holds the entries of the transaction in progress and nothing
earlier; this module never writes flash.

### `_nofile_arch`

A file object or `None` (the initial value). `OPEN_NOFILE_TAP` sets it, once,
during `TS2068_IO`'s setup or lazily from `LOAD_TS`; `LOAD_TS` reads it.
Invariant: when not `None` it is an open read handle on `/assets/nofile.tap`
that is never closed; every close in `LOAD_TS` is guarded by `arch is not
_nofile_arch`. The reason is the open cost: opening the file inside `LOAD_TS`
took ~5 ms on cold flash metadata, long enough for the Z80 to race through its
data loop reading 00h from an empty TX and give Report J
([DUAL_PORT_DEVELOPMENT.md §8](../../DUAL_PORT_DEVELOPMENT.md)). `LOAD_ZX` and
`LOAD_ZX_C` do not use the handle; they open the file by path on every call.

### Bus constants

| Name | Value | What it is |
|---|---|---|
| `_DMA` | `rp2.DMA`, or `None` | Set at import inside `try/except ImportError`: `None` on MicroPython v1.20, under the host tests' fake `rp2`, and on the v3 card (below). Every DMA path tests it and falls back to the polling loop it replaced. |
| `_mem32` | `machine.mem32`, or `None` | `None` on a PC and on the v3 card, where `MQX` falls back to `MQ.exec` and `_RING_SETUP` returns `None`. |
| `PORT_0F` | `const(0x100)` | Bit 8 of an RX word: A0 was 1, the Z80 wrote port 0Fh. `TS_IO_DUAL` samples nine pins, D0–D7 and A0, on every OUT. Tested by every receive loop in this file; only the ROM's SYNC and BREAK set it. |
| `TX_DEPTH` | `const(4)` | `TS_IO_DUAL`'s FIFOs are not joined, so TX holds four words. "TX is full" is `MQ.tx_fifo() >= TX_DEPTH` everywhere below. |
| `LOAD_CHUNK` | `const(256)` | How many bytes a file-streamed LOAD block reads at a time. One `readinto` per byte cost too much on v1.29: the ROMs read blind every ~43–47 µs and the log showed "TX ran dry" in 6914-byte blocks on both the 2068 and ZX48 paths (hardware, 2026-10-02). |
| `_LOAD_BUF` | `bytearray(LOAD_CHUNK)` | The chunk buffer, made once at import so the stream loops allocate nothing. Used by `LOAD_TS` (the checksum pass and the data stream when the block does not fit in RAM) and `LOAD_ZX`. |
| `_LOAD_MV` | `memoryview(_LOAD_BUF)` | Sliced (`_LOAD_MV[:left]`) for the tail of a block: one small allocation per block, not per byte. |

## The v3 card

Phase 4 of the v3 port plan (step 4.2; [board.md](board.md),
[tsbus.md](tsbus.md)). On the v3 card `MQ` is `tsbus.MQ()`, core 1's 1 KB
queues and status byte, not a PIO state machine. PIO0 SM0 runs the memory
program there, so this module must not write its registers or pace DMA on
its DREQs.

| Name | Value | What it is |
|---|---|---|
| `_tsbus_mq` | `tsbus.MQ`, or `None` | Set at import: `from tsbus import MQ`. Not `TS.board` (whose `board_v2` imports this module, a cycle), and not plain `import tsbus` (on a host `src/tsbus/` imports as an empty namespace package). When set, `_DMA` and `_mem32` are forced to `None`, though the RP2350 has both. So `MQX` goes through `MQ.exec` (tsbus understands `MQX`'s instruction strings), `_RING_SETUP` makes no ring, `RX_DMA` returns `None`, and `STREAM_DMA` streams through the queue (`STREAM_QUEUE`). |
| `DRAIN_MAX` | `64`, or `1100` on v3 | The most passes a FIFO flush makes: `MQ_TO_IDLE`, `ZX_FLUSH_TX`, and in `tspico.py` `CMD_RX_FLUSH`, `CMD_FLUSH` and `FAIL_CMD`. A PIO FIFO holds 4, so 64 is plenty, and the bound keeps a stuck state machine from hanging a path that must never hang. A tsbus queue holds 1024 (after an aborted `STREAM_QUEUE`, up to that many bytes). |
| `LED` | `None` | The board's LED object. `TS2068_IO` sets it to `board.make_led()`'s. `None` means the v2 Pico's GPIO 25, made on first use: the upgrade UF2 has no board layer. On the v3 card GPIO 25 is the I2C clock, so this module must never claim it. |

### `_LED()`

`LED`, made from `Pin(25, Pin.OUT)` first if it is still `None`. `LOAD_TS`,
`LOAD_ZX` and `LOAD_ZX_C` use it for their `led` (they built `Pin(25)`
themselves until step 4.2).

### `CAN_STREAM()`

True when `STREAM_DMA` can send a block without Python per byte: DMA into
the PIO FIFO (`_DMA`, v2) or the tsbus queue (v3). `tspico.py`'s
`CMD_SEND`, `CH_READ` and `BLKRCV` test it (they tested `_DMA` until step
4.2, which on v3 would be `None`). A call, not a constant, so a host test's
`io._DMA = FakeDMA` still counts.

## The fast PIO exec and the status register

| Name | Value | What it is |
|---|---|---|
| `_SM0_EXECCTRL` | `const(0x502000CC)` | PIO0's SM0_EXECCTRL register; bit 30 (SIDE_EN) is part of `MQX`'s cache key. |
| `_SM0_INSTR` | `const(0x502000D8)` | PIO0's SM0_INSTR register: writing an encoded instruction here executes it, which is all `pio_sm_exec()` does. |
| `_SM0_PINCTRL` | `const(0x502000DC)` | PIO0's SM0_PINCTRL register; bits 31:29 (SIDESET_COUNT) are the rest of the cache key. |
| `_ENCODED` | `{}` | `MQX`'s cache: `{instruction text: {side-set key: encoded instruction}}`. Grows once per new (instruction, side-set) pair and never shrinks. |

### `MQX(MQ, instr)`

Executes one PIO instruction on the bus state machine without running the
assembler on every call. With no `_mem32` (a PC) it calls `MQ.exec(instr)`, so
the simulated PIO of the host tests still sees the text. On the Pico it builds
the side-set key `ss` from SM0_PINCTRL bits 31:29 and SM0_EXECCTRL bit 30,
looks `instr` up in `_ENCODED`, encodes it on a miss with
`rp2.asm_pio_encode(instr, ss & 7, ss >> 3)`, and writes the code to
SM0_INSTR.

Why: `StateMachine.exec()` given text runs the Python PIO assembler on every
call: 9.6 ms a call on this Pico on MicroPython v1.20 against 18 µs for the
register write (measured 2026-09-27), and still 5.8–7.2 ms on v1.29, where
`src/test/mp_timing_bench.py` times a copy of `MQX` at about 33 µs (measured
2026-10-09, v2.2 board at 270 MHz). v1.29's `exec()` given an already-encoded
int skips the assembler and takes about 5 µs, a possible simplification not
taken here. Each LPRINT/LLIST character is a transaction with a few
execs, so a listing crawled at 30–40 ms a character and looked hung. The
encoding depends on the loaded program's side-set configuration, hence the
two-level cache. MQ is always PIO0 state machine 0: the register addresses are
hard-coded, and the function would drive the wrong machine for any other.
After the first use of an instruction with a given side-set it allocates
nothing; the first use allocates a dict entry, which is why no new instruction
text should be introduced on a per-byte path. `invert(null)` is the only
spelling of ~0 that `asm_pio_encode` accepts (`~null` does not parse on v1.20
or v1.29; the note is on `MQ_READY` in [tspico-bus.md](tspico-bus.md)).

Called by every status change in this file and in `tspico.py` (`MQ_READY`,
`CMD_FLUSH`, `ZX48_IO`'s drains), and by `src/upgrade/upgrade.py`.

### `MQ_STATUS(MQ, st)`

Sets what the Z80 reads on port 0Fh. `"idle"` is one exec, `mov(y,
invert(null))`: Y = 0xFFFFFFFF, the port reads FFh, which is what firmware
always showed, so older ROMs see no difference. `"mid"` is `set(y, 8)` then
`mov(y, invert(y))`: F7h, IDLE (bit 3) clear with READY set. Anything else is
`set(y, 4)` then the invert: FBh, RECOVERED (bit 2, active low) clear, which
tells the ROM this Pico gave up on a transaction by itself; the ROM reports
"T TS-Pico reset, try again" and its next SYNC clears it. The two-exec values
read as busy for the instant between the execs, which a Z80 polling for READY
tolerates by polling again. No logging: this runs on time-critical paths.
The bits are [PROTOCOL.md §3.1](../../PROTOCOL.md); the ROM side is
[../rom/exrom-sync.md](../rom/exrom-sync.md).

Callers: `SAY_READY` (for `"mid"`), `MQ_TO_IDLE`, `SAVE_TS`, and in `tspico.py`
the SYNC branch of the idle loop, `PROCESS_CMD`'s body abort (5947) and
tail, `PRINT_IO`, `CH_READY` (3250, `"mid"`) and the post-SAVE arm point. [`sync_io_hosttest.py`](../../../src/test/sync_io_hosttest.py)
pins the three values.

## The pre-header capture

### `RX_CAPTURE(MQ, raw, n, stall_ms, ready=None)`

Takes a burst of `n` 9-bit words from the Z80 into `raw`, an array (`'H'` or
`'I'`; the dispatcher passes an `array('I')`). Returns `n` when the whole
burst arrived; `k` with `0 <= k < n` when `k` words came and then `stall_ms`
of silence; `-k` when word `k - 1` was a 0Fh write (SYNC or BREAK), after
which the Z80 sends nothing and waits for READY + IDLE. A lone SYNC is `-1`;
the dispatcher's `-got - 1` is the number of data words before the 0Fh write.

With a ring (`_ring` is not `None`) it is one call to `RX_RING(_ring, MQ, raw,
True, n, stall_ms, stall_ms, -1, ready)`, mapped to the same results
(`RXB_ABORT` becomes `-got`; the other codes return `got`). Otherwise it says
READY as `ready` asks (`SAY_READY`), then loops: a word in the FIFO is stored at
once; an empty FIFO is where the decisions go: if the last stored word has
`PORT_0F` set, return `-got`; else read the clock until a word arrives or
`stall_ms` passes, returning `got` on the stall. After the `n`th word, a 0Fh
write as the last word still returns `-n`. The loop stores no bound method
(`rx = MQ.rx_fifo`): that allocation could start a GC as the burst begins, the
FIFO overflows and bytes go missing from the middle of the pre-header
("Partial pre-header 8/10", RECOVERED, Report T; hardware 2026-09-27).

Callers: `TS2068_IO`'s idle loop for the pre-header (10 words, 1000 ms, no
`ready`) when `RX_DMA` gave no channel; `PROCESS_CMD` for a command body
(`long` words, `BODY_READ_TIMEOUT_MS` = 1000, `"mid"`); `SAVE_TS` for the
header block (21 words, 1000 ms, `"mid"`). Pinned by
[`sync_io_hosttest.py`](../../../src/test/sync_io_hosttest.py): a complete
burst, a lone SYNC (`-1`), a partial burst then silence, a SYNC right behind a
partial burst (`-4`), 9-bit words kept intact, and the same through the ring.

### `RxDMA`

The pre-header caught by DMA. While the dispatcher is idle one DMA channel
stands armed on the bus state machine's RX FIFO (DREQ 4: PIO0, state machine
0, RX), and every word the Z80 writes goes straight into `raw`, an
`array('I')` of `n`, whatever core0 is doing. Why (hardware, 2026-10-02,
MicroPython v1.29): the first command after a 2068 power-on gave Report T; its
pre-header arrived with one byte missing from the middle, because core0 had
paused longer than the 4-deep FIFO lasts at ~30 µs a byte and `TS_IO_DUAL`'s
`push noblock` dropped one. A GC, a USB interrupt or a flash write (`SAVE_LOG`
on core1 stops both cores) can each do that.
[`dma_rx_harness.py`](../../../src/test/dma_rx_harness.py) measured polling
losing 400–13979 words under those stalls and the channel none.

One channel, claimed at boot by `RX_DMA(pre_raw)` in `TS2068_IO` and kept for
the firmware's life (the dispatcher keeps it in its `RXD` global too, for
`PROCESS_CMD`'s tail). Invariant: the channel runs only while the idle loop
waits; `take()` always leaves it stopped, so every handler reads RX by hand or
through the ring, as before. Fields: `d` (the `rp2.DMA`), `raw`, `n`, `ctrl`,
`armed`.

### `RxDMA.__init__(self, raw)`

Claims a channel with `_DMA()` (raises when none is free, which `RX_DMA`
turns into `None`), keeps `raw` and `n = len(raw)`, packs `ctrl` once:
`size=2` (32-bit words), `inc_read=False` (the FIFO register), `inc_write=True`,
`treq_sel=4`. `armed` starts `False`.

### `RxDMA.arm(self, MQ)`

If not armed, configures the channel (`read=MQ`, `write=raw`, `count=n`,
`trigger=True`) and marks it armed; a no-op while armed. Called at the top of
every pass of the idle loop, right before IDLE in the loop's SYNC branch (the
pre-header follows IDLE within microseconds), and by `PROCESS_CMD`'s tail
before it says IDLE.

### `RxDMA.waiting(self)`

The number of words the Z80 has written since `arm()`: `n - d.count`, or 0
when not armed. The idle loop's "has the Z80 started?" test.

### `RxDMA.stop(self)`

Reads `n - d.count` before stopping the channel with `active(0)`, clears
`armed`, and returns the count. The order matters: once stopped, the count no
longer says how far the channel got (hardware, 2026-10-03: a lone SYNC came
back as `-10`, all ten words, instead of `-1`). Also called by the service
loop's restart path when the channel was left armed.

### `RxDMA.take(self, stall_ms)`

Waits for the rest of the burst with `RX_CAPTURE`'s contract and returns the
same values. It loops on `g = n - d.count`: when `g >= n` the channel has
finished by itself (`armed` is cleared, no stop needed); when `g` has grown
and the newest word has `PORT_0F` set it returns `-stop()`; when `g` has not
changed for `stall_ms` it returns `stop()`. After all `n`, a 0Fh write in the
last word gives `-n`. It allocates nothing and stores no bound method
([`sync_io_hosttest.py`](../../../src/test/sync_io_hosttest.py) checks its
AST for that). It does not say READY: the pre-header arrives while the status
is already idle. The test also pins ten words, a lone SYNC (`-1` with
`raw[0] == 0x103`), four words then silence after 1000 ms, three words then a
SYNC (`-4`), a 0Fh write as the tenth word (`-10`), re-arming, and a word left
in RX behind the burst.

### `RX_DMA(raw)`

`RxDMA(raw)`, or `None` when there is no `rp2.DMA` or the constructor raised
(no free channel); the dispatcher then polls with `RX_CAPTURE`. Called once,
from `TS2068_IO`'s setup.

## USB stdin

| Name | Initial value | What it is |
|---|---|---|
| `_stdin_ipoll` | `None` | Set on the first `DRAIN_STDIN`: the `ipoll` bound method of a `select.poll` registered on `sys.stdin` for `POLLIN`. `ipoll` reuses its result tuple, so a drain allocates nothing after the first. |
| `_stdin_readinto` | `None` | Set with it: `sys.stdin.buffer.readinto`. |
| `_stdin_byte` | `bytearray(1)` | The one-byte sink the drain reads into. |

### `DRAIN_STDIN(MQ, limit=1024)`

Throws away text the host sent to the running firmware, so that a later Ctrl-C
still reaches it; returns the number of bytes dropped. The first call builds
the poll object and the two bound methods. Then, while fewer than `limit`
bytes have gone and the bus RX FIFO is empty: `ipoll(0)` with nothing waiting
returns `n`; otherwise one byte is read into `_stdin_byte`. A Ctrl-C among the
bytes surfaces as `KeyboardInterrupt` out of this call, which is the point.

Why: MicroPython's rp2 port (v1.20, and still v1.29 in
`shared/tinyusb/mp_usbd_cdc.c`) sees Ctrl-C only while it moves USB bytes into
its 512-byte stdin ring buffer. The firmware never reads stdin, so once 511
bytes of anything else have arrived — a tool writing before its Ctrl-C landed,
a terminal echoing telemetry back — the ring is full, every later byte waits in
TinyUSB behind it, and Ctrl-C is never looked at: the Pico runs on with USB deaf
until a reset (hardware, 2026-09-28: 600 bytes, then no Ctrl-C ever got
through). Polling stdin moves the waiting bytes along.

Run it from the idle heartbeat only: `TS2068_IO` and `ZX48_IO` call it once
per ~2 s heartbeat. It stops at the first byte from the Z80, because a
pre-header arrives 30 µs a byte into a 4-deep FIFO.
[`stdin_drain_hosttest.py`](../../../src/test/stdin_drain_hosttest.py) models
the C path byte for byte, shows the wedge without the drain and the Ctrl-C
getting through with it, and checks that it stops at the first Z80 byte, is
bounded, costs nothing on an empty stdin, and is called by both heartbeats in
`TS/tspico.py` and `dev_tspico.py` ([PROTOCOL.md §13](../../PROTOCOL.md), "Any
idle loop you add must call DRAIN_STDIN").

## Back to idle

### `MQ_TO_IDLE(MQ, recovered=False, status=True, first=0x01)`

The one way back to a known state, whatever happened: TX and RX empty, exactly
one byte staged for the next command's first status read, and the status idle
or recovered. It empties TX with up to `DRAIN_MAX` (64; 1100 on v3) passes
of `pull(noblock)` and `mov(osr, null)` (each pulls one word into the OSR and
discards it; the loop stops as soon as `tx_fifo()` is 0; on v3 `MQ.exec`
drops the oldest queued byte), empties RX with up to `DRAIN_MAX` `get()`s, puts
`first` into TX if there is room, and, if `status`, sets Y to `"recovered"` or
`"idle"`. Bounded on purpose: the FIFOs are four deep, so a few passes are
enough, and spinning longer would mean the state machine is not draining;
this path must never hang.

`first` is 0x01, the pre-load the ROM reads with no wait straight after its
next pre-header ([PROTOCOL.md §4.2](../../PROTOCOL.md)); the dispatcher's SYNC
branch passes `FIRST_STATUS()` instead, which may be the error of a header LOAD
just refused. `status=False` leaves Y alone so the caller chooses the moment:
after a SYNC the Z80 waits up to ~1 s for IDLE, and that is when slow work
goes — the dispatcher waits (bounded, 800 ms) for a core1 flash write, re-arms
the `RxDMA`, and only then says idle, because the pre-header follows IDLE at
once.

Callers: the idle loop (a SYNC; a partial pre-header, with `recovered=True`;
an unrecognised pre-header; the service-loop restart), `PROCESS_CMD`'s and
`PRINT_IO`'s body aborts, `LOAD_TS`'s abort path, `LOAD_REFUSE` and
`LOAD_RETRY_DONE`. [`sync_io_hosttest.py`](../../../src/test/sync_io_hosttest.py)
pins TX = `[01]`, RX empty, the three status choices. Why one byte and not
`LOAD_TS`'s two is [PROTOCOL.md §13](../../PROTOCOL.md), "An early return
re-arms too — and with ONE 0x01, not two".

## Sending

### `TX_ROOM(MQ, echo, stall_ms=3000)`

LOAD's slow path. TX is full, so the Z80 has not read the last byte yet: wait
for room, listening, instead of blocking in `MQ.put()`. Returns 0 when there is
room; 1 on a 0Fh write (BREAK, or a new command's SYNC after a 2068 reset: the
Z80 has stopped reading and waits for IDLE); 3 when TX stayed full for
`stall_ms` (the Z80 has gone). Code 2 was the watchdog, removed in #51. While
it waits, any data word the Z80 writes — the block-type echo it sends just
before its data loop — goes into `echo` through `ECHO_KEEP`.

`echo` is a `bytearray(3)`, never a list: a list append can allocate, an
allocation can start a GC that stops core0 for 15–25 ms, and the Z80 reads a
byte every 50 µs from a 4-deep FIFO, so that pause is ~300 empty reads and
Report R. The loop calls `MQ.tx_fifo()` and `MQ.rx_fifo()` directly, never
through a stored bound method: this runs once per byte of a LOAD, the 16-byte
bound method filled the heap every ~6.5 KB, and each GC froze the Pico ~6 ms
mid-block while the Z80 read ~110 empty bytes, Report R on every block over
~6 KB (hardware, 2026-09-27).

Callers: `LOAD_TS`'s two hand-streaming loops (the default 3000 ms) and
`tspico.py`'s `CMD_PUT` (`CMD_STALL_MS` = 600 000 ms, `_CMD_ECHO`;
[tspico-bus.md](tspico-bus.md)).
[`load_ts_hosttest.py`](../../../src/test/load_ts_hosttest.py) pins the BREAK
heard here mid-block with no `put()` into a full TX;
[`alloc_probe.py`](../../../src/test/alloc_probe.py) and
[`load_stall_probe.py`](../../../src/test/load_stall_probe.py) are the
hardware probes behind the allocation rule.

### `ECHO_KEEP(echo, w)`

Keeps the low byte of the Z80's word `w` in `echo = [count, block type, CRC]`:
the first goes to `echo[1]`, the second to `echo[2]`, anything after the
second is dropped, and `echo[0]` counts. No allocation. `LOAD_TS` reads
`echo[1]` as the block-type acknowledgement and `echo[2]` as the Z80's
computed CRC; it stores both and checks neither.

### `STREAM_DMA(MQ, buf, echo, stall_ms, ready, first_ms=0)`

Sends `buf` (bytes, a bytearray or a memoryview) to the Z80 through the bus
state machine's TX FIFO by DMA, and says READY once the channel is moving.
Returns `None` when there is no `rp2.DMA` or no free channel — the caller then
streams by hand, as before — else `(why, sent, word)`:

| `why` | Meaning |
|---|---|
| 0 | all of `buf` went into the FIFO; the Z80 reads the last few bytes after this returns, as with the hand loop |
| 1 | a 0Fh write: BREAK, or a SYNC after a 2068 reset |
| 3 | the Z80 stopped reading for the limit (`TX_ROOM`'s codes) |
| 4 | `echo is None` (ZX48 mode) and the Z80 wrote a word — any word, 0Fh included, as `ZX_ROOM` reports it — returned in `word` for `ZX48_IO` to dispatch |

`sent` is the number of bytes the channel moved, read before it is stopped
(see `RxDMA.stop`); the channel is stopped when `why` is not 0, and closed in
a `finally` in every case.

Steps: claim a channel; configure it `read=buf`, `write=MQ` (the TX FIFO
register), `count=len(buf)`, `size=0` (bytes), `inc_read=True`,
`inc_write=False`, `treq_sel=0` (DREQ 0: PIO0, state machine 0, TX),
`trigger=True`; then say READY: `ready is True` executes `mov(y,
invert(null))` (READY + IDLE; the FIFO is full by now), a callable (`MQ_READY`,
`CH_READY`) is called, `False` means the caller has already said it. Then
core0 only listens while the channel is active: an RX word is dispatched as
the table says, otherwise kept by `ECHO_KEEP`; each change of the channel's
count restarts the clock, and once more than `2 * TX_DEPTH` bytes have moved
(the Z80 has read past the first FIFO-full) the limit becomes `stall_ms`;
until then it is `first_ms or stall_ms`. `first_ms` exists for `romupdate`,
which erases the slot for seconds before it reads.

Why DMA (hardware, 2026-10-03): the ROMs read a LOAD block blind, a byte every
~47 µs, from a 4-deep FIFO, ~190 µs of slack; a GC, a USB interrupt or a flash
write can be longer, and the FIFO runs dry. The channel feeds it in hardware,
paced by the state machine's "TX not full" request, whatever core0 is doing:
[`dma_tx_harness.py`](../../../src/test/dma_tx_harness.py) saw 0 dry reads
under every stall against 104–1498 for a Python loop. The code's comment says
the channel writes bytes because the FIFO register repeats a byte write across
the word and `TS_IO_DUAL` outputs bits 0–7. The channel must be running before
the Z80 starts reading blind: setting it up takes a few hundred µs on v1.29,
ten of `romupdate`'s 33 µs reads, so it is never started behind a READY the
Z80 is already acting on; READY is said through `ready` instead (hardware,
2026-10-03: ten empty reads at the start of a `romupdate` put 00s into the
flash).

Callers: `LOAD_TS` (a block in RAM; `echo`, 3000 ms, `True`), `LOAD_ZX`
(`None`, `ZX_STALL_MS`, `True`), and in `tspico.py` `CMD_SEND` (`MQ_READY` or
`False`), `CH_READ` (`CH_READY`), the DCK/ROM image stream of `romupdate`
(`False`, `first_ms=CMD_STALL_MS`) and `ZX_TPI` (`None`, `True`); and `upgrade.py`'s
`reply` for an updater block (`None`, `REPLY_STALL_MS`, `True`; since
2026-10-06, [upgrade.md](upgrade.md)). Beware: `why
== 0` says the bytes are in the FIFO, not that the Z80 read them; the claim and
`pack_ctrl` allocate, which is acceptable only because the Z80 is parked in a
ready-wait at that moment. [`load_ts_hosttest.py`](../../../src/test/load_ts_hosttest.py)'s
"by DMA" section pins one channel per block with the flag as its first word,
every channel closed, a BREAK stopping the channel part way with the log
counting the bytes actually read, a stall giving RECOVERED, the data byte for
byte with no "ran dry", and the Python loop when no channel is free;
[`zx48_io_hosttest.py`](../../../src/test/zx48_io_hosttest.py) does the same
for `LOAD_ZX`.

On the v3 card (`_tsbus_mq` set) `STREAM_DMA` returns `STREAM_QUEUE`'s
result instead, with the same contract.

### `QUEUE_WAIT_MS`

`const(10)`: how long one `put_block` call in `STREAM_QUEUE` waits for room
before Python looks at RX and the stall clock again.

### `STREAM_QUEUE(MQ, buf, echo, stall_ms, ready, first_ms=0)`

`STREAM_DMA` on the v3 card, with its return contract `(why, sent, word)`.
There is no FIFO to feed: tsbus's TX queue holds 1024 bytes, and core 1
hands them to the Z80 as it reads. So C does the copying.
`MQ.put_block(buf, wait_ms)` ([tsbus.md](tsbus.md)) queues as much as fits,
waits up to `wait_ms` without progress for more room, returns early when an
OUT is waiting, and returns how many bytes it took.

1. `pos = MQ.put_block(mv, 0)`: the queue is filled first.
2. READY as `STREAM_DMA` says it (`ready` True: `mov(y, invert(null))`; a
   function: called; False: nothing).
3. While `pos < len(buf)`: `k = MQ.put_block(mv[pos:], QUEUE_WAIT_MS)`.
   - On progress the stall clock restarts. Once more than `2 * TX_DEPTH`
     bytes have been read (`pos - tx_fifo()`), the limit drops from
     `first_ms` to `stall_ms`.
   - An RX word: with `echo` None (ZX48 mode), why 4 with the word; a
     port-0Fh write, why 1; otherwise `ECHO_KEEP`.
   - No progress for the limit: why 3.

`sent` is `pos`, the bytes queued. As with DMA, the Z80 has read
`sent - MQ.tx_fifo()`. On an early return the rest stays queued, and the
caller's flush (`MQ_TO_IDLE`, with `DRAIN_MAX`) empties it. Python runs once
per `put_block` call (about every 10 ms while the Z80 reads), never per
byte. [`tsbus_io_hosttest.py`](../../../src/test/tsbus_io_hosttest.py) runs
it against a model Z80 on a 1024-byte queue: a 6912-byte block whole and in
order, a BREAK, a stall, `first_ms`'s grace and ZX48's any-word.

### `RX_WORD(MQ, stall_ms)`

One 9-bit word from the Z80, or `-1` after `stall_ms` of silence — never the
unbounded wait of a bare `MQ.get()`. Bit 8 is returned intact, so callers can
test `PORT_0F`. Callers: `LOAD_TS`'s echo phase (1000 ms), `LOAD_REFUSE`
(1000 ms), `SAVE_ZX` (`ZX_BLOCK_GAP_MS`, for the data block's `'S'`),
`tspico.py`'s `CMD_KEY` (`KEY_WAIT_MS`), and `src/upgrade/upgrade.py` (100 ms).

## Receiving blocks

| Name | Value | What it is |
|---|---|---|
| `RXB_OK` | `const(0)` | `RX_BLOCK` / `RX_RING` result: all `n` words arrived. |
| `RXB_ABORT` | `const(1)` | the burst ended with a 0Fh write (BREAK or SYNC); the Z80 waits for IDLE. |
| `RXB_STALL` | `const(3)` | silence: `first_ms` before the first word, `stall_ms` after it. `RX_RING` also returns it when the ring was overwritten. |
| `_RING_BITS` | `const(12)` | the ring is 2^12 = 4096 bytes, 4096-aligned, as the RP2040 DMA's ring mode requires. |
| `_RING_WORDS` | `const(1024)` | the same ring in 32-bit words; `RX_RING`'s index mask is `_RING_WORDS - 1`. |

The ring exists because the Z80 writes a SAVE block, a command body or a
printer body ~30–43 µs a byte with no handshake into a 4-deep RX FIFO, ~120–170
µs of slack, and a GC, a USB interrupt or a flash write on v1.29 is longer
(`dma_rx_harness`: polling lost 400–13979 words under those stalls, DMA none).
While `RX_BLOCK` or `RX_CAPTURE` run, a DMA channel paced by the RX DREQ drains
the FIFO into a 1024-word ring in RAM, ~44 ms of slack instead of ~0.15 ms, and
core0 copies words out of the ring at its own pace.

### `_RING_SETUP()`

Makes the receive ring once, at import. Returns `(channel, ring address,
ctrl, the memory kept alive, mem32)`, or `None` when there is no `_DMA` or
`_mem32` or anything raises (no free channel included). It allocates
`bytearray(2 << _RING_BITS)` (8192 bytes) and takes the 4096-aligned address
inside it (`base + ((-base) & 4095)`), claims a channel and packs its control
word: `size=2`, `inc_read=False`, `inc_write=True`, `ring_size=_RING_BITS`,
`ring_sel=True` (the write address wraps), `treq_sel=4`. Made once so that
nothing allocates on the time-critical path. The upgrade UF2 imports this
module too, so it claims this channel and ring at boot although nothing in
`upgrade.py` uses them *(inferred from the imports; harmless)*.

### `_ring`

`_RING_SETUP()`'s result: the tuple, or `None`. Read by `RX_CAPTURE` and
`RX_BLOCK`, which take the ring path when it is not `None`, and by
`tspico.py`'s `ZX_TPI` (`tspico_io._ring`, `tspico_io.RX_RING`).
`sync_io_hosttest.py` installs a fake ring to test the ring paths and restores
`None`.

### `SAY_READY(MQ, ready)`

READY for a receive: `"mid"` calls `MQ_STATUS(MQ, "mid")`; any other true
value (`"ready"`, `True`) executes `mov(y, invert(null))` (READY + IDLE);
`None` or `False` does nothing, for a caller that has already said it.

### `RX_RING(ring, MQ, out, wide, n, first_ms, stall_ms, len_at=-1, ready=None)`

Takes up to `n` words from the Z80 by DMA into `out`: the 9-bit words if
`wide` (an array), else their low bytes (a bytearray). Returns `(code, words
taken)` with `code` one of `RXB_*`, exactly as `RX_BLOCK`. Leaves the channel
stopped; words the Z80 sends after the `n` (or after a stop) stay in the FIFO.

Steps: `n <= 0` says READY and returns `(RXB_OK, 0)`. Otherwise the channel is
configured for `total = n` words into the ring and triggered, and only then is
READY said: the Z80 sends the moment it sees READY, and setting the channel up
takes long enough to lose bytes behind it (a ZX `tpi:` name lost 1 of 15,
hardware 2026-10-03) — channel first, then READY. The loop reads `pos = total -
d.count` (capped at `n`) and, when there are new words, copies them out of the
ring (`m32[addr + ((got & mask) << 2)] & 0x1FF`), restarts the clock and
switches the limit from `first_ms` to `stall_ms`; if more than `_RING_WORDS`
arrived since the last copy, core0 was away ~44 ms and words have been
overwritten, which returns `RXB_STALL`. With `len_at >= 0`, word `len_at` is a
length and the burst ends that many words after it: when `got == len_at + 1`,
`n` becomes `min(n, got + (w & 0xFF))`. With no new words, a last word with
`PORT_0F` set returns `RXB_ABORT` (nothing follows a 0Fh write), and the clock
past the limit returns `RXB_STALL`. The `finally` stops the channel; a burst
that completed with a 0Fh write as its last word is `RXB_ABORT`.

Why `len_at`: one run for a header and what follows it; two runs back to back
lose the bytes the Z80 sends while the second is being set up (a ZX `tpi:`
name lost 3 of 13 bytes, Report J; hardware 2026-10-03).

Callers: `RX_CAPTURE`, `RX_BLOCK`, and `ZX_TPI` directly (257 bytes, `len_at
= 1`, `"ready"`). Beware: the overwrite case is reported as `RXB_STALL` though
the words were lost rather than late, and the caller cannot tell the two
apart; with `len_at`, words that arrive after the computed end but before the
stop land in the ring and are dropped, not left in the FIFO.
[`sync_io_hosttest.py`](../../../src/test/sync_io_hosttest.py) pins 3000
bytes through the ring, a BREAK after 501 words (`RXB_ABORT`, 501), silence
after 700 (`RXB_STALL` after at least `stall_ms`), nothing at all
(`RXB_STALL`, 0), ten wide words with a byte left in RX behind them, `len_at`
with a name and with a length of 0, READY said only after the channel is
configured, and `RX_CAPTURE` and `RX_BLOCK` through it.

### `RX_BLOCK(MQ, buf, n, first_ms, stall_ms, ready=None)`

Takes a block of `n` bytes from the Z80 into `buf` (a bytearray) and returns
`(code, words taken)`. With a ring it is `RX_RING(_ring, MQ, buf, False, n,
first_ms, stall_ms, -1, ready)`. Otherwise it says READY as asked, takes the
two bound methods once per call (allocating them once, not per byte — storing
one per byte, as `TX_ROOM` once did, allocates 16 bytes each time and the GCs
that follow freeze the Pico mid-block; `alloc_probe.py`), and per byte does
only: test the FIFO, get, store the low byte. The 0Fh test and the clock run
only when the FIFO is empty, exactly when the Z80 has paused or stopped; a 0Fh
write is always the last thing it sends, so it is the newest word then, and `w`
keeps it (the buffer holds only the low 8 bits). The clock allows `first_ms`
before the first byte and `stall_ms` after it. (Until #181 the docstring
also named "the watchdog flag" among the things tested; there is none.)

Callers: `SAVE_TS` (the data block, `long` bytes, 3000 then 1000 ms, `"mid"`),
`SAVE_ZX` (21 bytes and `n + 4`, `ZX_STALL_MS` both, `"ready"`), `tspico.py`'s
`PRINT_IO` (a COPY body, 1000/1000, `"mid"`) and `ZX_TPI`'s polling path (two
runs, no `ready`). [`save_ts_hosttest.py`](../../../src/test/save_ts_hosttest.py)
pins BREAK mid data block, silence mid-block, a corrupted block, no RX overflow
and no allocation in the capture loop.

### `_SAVE_HDR_RAW`

`array("H", bytes(42))`: 21 zeroed 9-bit words, `SAVE_TS`'s target for the
header block, made once so the capture allocates nothing. Only `SAVE_TS` uses
it, and only one SAVE runs at a time.

### `OPEN_NOFILE_TAP()`

Pre-opens `/assets/nofile.tap` read-only and caches the handle in
`_nofile_arch`. Idempotent: with a handle already cached it returns `True` at
once. Returns `False`, leaving `_nofile_arch` `None`, when the file is missing
from the Pico's flash (the user has to copy `assets/` on; see
[boot.md](boot.md)). Called once by `TS2068_IO`'s setup, which logs a warning
on `False`, and lazily by `LOAD_TS`.

## The PIO programs

Lines 776–1041 define `sel_bank` (bank selection on A15–A18), `set_ctrl` (the
control lines /BE, A14_L, `U10_ENA`, `U13_ENA`), `set_dck` (`U10_ENA` and
`U13_ENA` only, for DOCK access without ROM mapping) and `TS_IO_DUAL` (the two ports; 20
instructions, with the auto-busy `mov(y, null)` of issue #14). They are
explained instruction by instruction, with the Y register contract and the
FIFOs, in [pio.md](pio.md); the hardware they drive is in
[../hardware.md](../hardware.md). `board_v2` ([board.md](board.md)) imports
`TS_IO_DUAL`, `set_ctrl` and `sel_bank`, and builds the state machines the
firmware runs them on; `ENA_MQ_DUAL` builds `TS_IO_DUAL` on state machine 0
at 30 MHz itself (until step 4.2 of the board layer); `src/upgrade/main.py` builds
`TS_IO_DUAL`, `set_ctrl` (SM 4) and `sel_bank` (SM 5) from this file for the
upgrade UF2.

## LOAD support

### `REWIND_ABORTED_SEARCH(TSP)`

Puts the tape back where a LOAD search started. If `TSP.ld_start` is below 0
(read with a default of -1) there is no search in progress and it returns
`False`; otherwise `TSP.offset = TSP.ld_start`, `TSP.tap_idx =
TSP.ld_start_idx` (default 0), `ld_start = -1`, `ld_wrapped = False`, and it
returns `True`. Only a search is rewound: an abort in the middle of a block the
Z80 had already accepted is left alone, because that position is where the
user actually is.

Why: the user's only way out of a LOAD that cannot match is BREAK, and a ROM
without SYNC, such as ROM 1.1, never tells the Pico about it — its abort path writes nothing, and
the whole EXROM holds exactly one `OUT (0Eh),A`
([BREAK_AND_ABORT.md](../../rom-analysis/BREAK_AND_ABORT.md)). The search has
walked an arbitrary distance through the tape by then, so without this the
next LOAD starts wherever the abandoned search stopped. The signal is
`TX_ROOM`'s 3 s stall (`why` 3) or the BREAK's 0Fh write
(`why` 1); until #181 the docstring still said "the watchdog firing". Called only from `LOAD_TS`'s abort path.
[`load_ts_hosttest.py`](../../../src/test/load_ts_hosttest.py) checks the offset
after a BREAK.

### `ENA_MQ_DUAL(MQ)`

Re-creates and activates the bus state machine: `StateMachine(0, TS_IO_DUAL,
freq=30_000_000, out_base=Pin(2), in_base=Pin(2), jmp_pin=Pin(11),
sideset_base=Pin(12))`, deactivated, 10 ms of sleep, activated, then Y = READY,
because a fresh state machine starts with Y undefined and the PIO drops Y on
every Z80 OUT. Returns the new object; the `MQ` argument is not used. Why:
`ENA_SD` re-claims GPIO 2–4 for SPI, so the state machine has to be rebuilt on
the way back to the bus. In 2068 mode the dispatcher does that through
`ACTIVATE_MQ` ([tspico-bus.md](tspico-bus.md)), which leaves Y busy; `ZX48_IO`
never returns to the dispatcher between transactions, so a ZX handler that
touched the card restores the bus itself. The only caller is `SAVE_ZX`.
[PROTOCOL.md §13](../../PROTOCOL.md), "Never call `ENA_MQ()`", is the bug this
replaced: the single-port `TS_IO` at 15 MHz handed back as the session's state
machine. [`zx48_io_hosttest.py`](../../../src/test/zx48_io_hosttest.py) covers
the ZX SAVE that goes through it.

On the v3 card (`_tsbus_mq` set) the bus is never given up for SD, so it
says READY and returns `MQ` unchanged.

## The SD card and the log

### `SD_MOUNT`

A hook: `None` at import; `tspico.py` sets `tspico_io.SD_MOUNT = SAVE_MOUNT` at
its own import (2026-09-30 audit, §2 #21). `SAVE_MOUNT` unmounts any stale
`/sd` and goes through `ACTIVATE_SD` ([tspico-bus.md](tspico-bus.md)): up to
five attempts 0.5 s apart while the card is believed present, and
`SD_NOTE_CARD`'s bookkeeping (a card that has come back or been swapped
repairs the folder, the mount, append mode, the channels and the printer
capture); it raises `OSError` when there is no card. Why a hook: `tspico_io`
cannot import `tspico`, which imports it, and the upgrade UF2 freezes
`tspico_io` without it. Before the hook, `SAVE_TS` and `SAVE_ZX` were the last
callers of the bare mount in `ENA_SD`, one `os.mount` with none of the
bookkeeping, and a card that only came up on a second attempt meant "0 OK" on
the 2068 and a file that was never written. `None` — the harnesses and host
tests that load this module on its own — keeps the bare mount.
[`audit_fixes_hosttest.py`](../../../src/test/audit_fixes_hosttest.py)
(`test_save_mount`) checks the hook is set to `SAVE_MOUNT`.

### `ENA_SD(log_level=0)`

Mounts the SD card on `/sd` for `SAVE_TS` and `SAVE_ZX` to write the captured
TAP. With `SD_MOUNT` set (the firmware) it returns `SD_MOUNT()`'s result and
lets its `OSError` through; both callers catch that as the write failure.
Without it: `Pin(28)` as chip select (pull-up), `Pin(2)`, `Pin(3)`, `Pin(4)` as
`SPI(0)`'s sck, mosi and miso, `SDCard(spi, cs)` (`sdcard.py`'s driver,
[sdcard.md](sdcard.md); its `init_card` is where a missing card actually
fails, before `os.mount` runs), `os.mount(sd, "/sd")`; any `Exception` is
logged through `LOG_ADD` at ERROR with the caller's `log_level` and the
function returns -99, otherwise the `SPI` object. It never raises on the bare
path, and catches `Exception` rather than everything, so a `KeyboardInterrupt`
from the host is not swallowed. A `/sd` that is still mounted makes
`os.mount` fail with EPERM, and the write then works on the existing mount.
`log_level` exists because the function used to read `TSP.LOG_LEVEL`, and
there is no `TSP` in this module: the error path raised `NameError`, which the
callers logged as "name 'TSP' isn't defined", hiding the mount error
(2026-09-30 audit).

Either way the GPIO 2–4 pins are left claimed by SPI and the bus state
machine is off the bus; the caller restores it (`SAVE_ZX` with `ENA_MQ_DUAL`,
`SAVE_TS` by returning to the dispatcher, whose SAVE branch runs
`DEACTIVATE_SD` and `ACTIVATE_MQ`). The long comment above the `try` says
why: the caller's own write then fails, and `SAVE_TS` reports that to the
2068 as Report J, because its final status goes out from the dispatcher
after the write (`TSP.save_final`). (Until #181 the comment said the final
status went out first and the failure could not be reported, citing a
"RACE FIX" comment that no longer exists.) [`audit_fixes_hosttest.py`](../../../src/test/audit_fixes_hosttest.py)
(`test_ena_sd`) pins -99 with the real error logged when there is no card, -99
without raising on EPERM, and Ctrl-C not swallowed;
[`sd_wedged_hosttest.py`](../../../src/test/sd_wedged_hosttest.py)
(`test_save_remount`) runs the dispatcher's SAVE branch when the re-mount
after a successful write fails.

### `LOG_ADD(msg, level, log_level)`

Buffers a log entry for `SAVE_LOG` to write later. Entries whose `level` (0
INFO, 1 WARN, 2 ERROR, 3 CRIT) is below `log_level` (the caller's
`TSP.LOG_LEVEL`) are dropped; the rest are appended to `log_entries` as
`"[" + ticks_us + "] " + msg + "\n"`. It never touches flash, which would block
for tens of milliseconds, but the string concatenation allocates, so every
call in this file is placed after a burst or before READY, never on a per-byte
path. `ticks_us()` wraps after ~71 minutes.

## Refusing a LOAD

| Name | Initial value | What it is |
|---|---|---|
| `_ld_err` | 0 | The error status of a header LOAD `LOAD_REFUSE` has just refused (2 or 7); 0 = none pending. Set by `LOAD_REFUSE`, cleared by `FIRST_STATUS` when stale and by `LOAD_RETRY_DONE` on every LOAD. |
| `_ld_err_t` | 0 | `ticks_ms()` when it was refused; `FIRST_STATUS` treats it as stale after 2000 ms. |
| `_ld_err_staged` | `False` | True while that error is the byte staged in TX for the next first-status read. Set by `LOAD_REFUSE` (no SYNC: the byte waits in TX) and `FIRST_STATUS` (after a SYNC re-staged it); read and cleared by `LOAD_RETRY_DONE`. |

### `LOAD_REFUSE(pre, MQ, st)`

Ends a LOAD with an error instead of a block: status `st`, 2 for Report R, 7
for "End of file" (Report 8 where the ROM maps it; ROM 2.2's header search
shows it as R). Returns 0, or `TX_ROOM`'s 1 or 3 after a BREAK or a stall,
having gone back to idle.

The status cannot simply be written first. The ROM reads a LOAD's first
status with no wait straight after the pre-header (EXROM 19C7h,
[../rom/exrom-driver.md](../rom/exrom-driver.md)), so it gets the 0x01 staged
before the command arrived; a byte written now is read as the block's flag
(19DDh). A flag that does not match fails the block, and then a data block is
Report R and done, while a header's search just asks again (EXROM 04DDh:
`CALL 00FC / JR NC` back), as it does after every failure inside a block — a
bad checksum, or a final status of 2 (1A0Bh goes to the function chain at
026Fh, not the report dispatcher). On hardware on 2026-10-04, a damaged
header was asked for every ~100 ms for ever, until the Pico's stall gave
Report T. The one place a report gets out of a header search is the first
status of the *next* request: anything but 00h or 01h there is `JP 1C3E`, RST
8, Report R ([PROTOCOL.md §13](../../PROTOCOL.md), "A LOAD's first status can't
carry an error").

So the steps are: `MQ.put(st)`, the flag that fails the block (never 00h or
FFh); `MQ.put(st if pre[0] == 0x00 else 0x01)`, the next request's first
status — the error for a header's retry, the plain pre-load for a data block;
READY; then `RX_WORD(MQ, 1000)` for the ROM's flag echo, which it sends before
reading the flag ([PROTOCOL.md §6.1](../../PROTOCOL.md)), after which it stops.
Silence is `why` 3 and a 0Fh write `why` 1: `MQ_TO_IDLE(recovered=(why !=
1))` and return. Otherwise, for a header, the error is recorded in `_ld_err`,
`_ld_err_t` and `_ld_err_staged`, READY is said again (the echo OUT dropped
Y), and 0 is returned. Without SYNC the staged byte waits in TX behind the flag
for the retry; with SYNC (ROM 2.2) the dispatcher's `MQ_TO_IDLE` would drop
it, so the SYNC branch re-stages it from `FIRST_STATUS()`, and `LOAD_TS`,
seeing the retry, goes straight back to idle (`LOAD_RETRY_DONE`). Either way no
stray byte is left behind (the orphan-byte family of
[`src/CLAUDE.md`](../../../src/CLAUDE.md)).

Callers: `LOAD_TS`, with 2 for a missing `/assets/nofile.tap` and for a
damaged or impossible block, 7 for a search that found nothing in a lap (and 7
or 2, by block type, when the TAP holds no block of the requested type).
Beware: `echo = bytearray(3)` on the first line is allocated and never used;
and on a ROM without SYNC the second byte is whatever comes next reads first,
which is by design the ROM's retry within ~100 ms — if the user breaks out of
the search instead, that byte is the next command's first status and that
command gets Report R *(inferred; ROM 1.1's BREAK path writes nothing,
so nothing clears it)*. [`load_ts_hosttest.py`](../../../src/test/load_ts_hosttest.py)
pins "retry, then R, idle" with and without SYNC, R at once for a data block,
and the tape moving past the block.

### `FIRST_STATUS()`

The byte the dispatcher stages after a SYNC for the next command's first
status read: `_ld_err`, if one is pending and less than 2000 ms old (it is
then marked staged); otherwise 0x01, with the error cleared. The ROM's retry
follows a refusal within milliseconds, so after two seconds the error is stale
— a BREAK took the ROM elsewhere — and dropped. Called only from the SYNC
branch of `TS2068_IO`'s idle loop: `MQ_TO_IDLE(MQ, status=False,
first=FIRST_STATUS())`. `load_ts_hosttest.py` uses it to model the ROM's
SYNC and checks a 3 s old error gives 0x01.

### `LOAD_RETRY_DONE(pre, MQ)`

True when this LOAD is the ROM's retry of a header just refused: `_ld_err_staged`
was set and `pre[0]` is 00h. In that case the ROM has read the staged error
with no wait and stopped with Report R, so it waits (at most 200 ms) for TX to
empty, calls `MQ_TO_IDLE(MQ)` for one 0x01 and idle, and returns `True`;
`LOAD_TS` then returns at once. Any LOAD clears `_ld_err` and
`_ld_err_staged`, so any other command drops the error. Called first thing in
`LOAD_TS`.

## `LOAD_TS(pre, MQ, TSP)`

Sends one TAP block to the Z80 through the TPI LOAD exchange of
[PROTOCOL.md §6.1](../../PROTOCOL.md); the flow from the keyword to the last
byte is [../flows/load.md](../flows/load.md). The dispatcher calls it (through
`LOAD_SERVE`) for every pre-header whose first byte is 00h (header) or FFh
(data), except 00h with TADDR 0 (a SAVE) — LOAD, VERIFY, MERGE, and the headerless LOAD
of machine code calling LD-BYTES — after waiting (bounded, 3 s) for any core1
flash write, and without saying READY: the Z80 is parked in `WAIT_PICO_READY`
(EXROM 1A54h, [../rom/exrom-driver.md](../rom/exrom-driver.md)), having read
its pre-load status with no wait, and the ROM allows ~19.9 s there. `pre` is
the ten-byte pre-header: `pre[0]` the block type, `pre[1]` TADDR, `pre[2]` the
bank, `pre[3:5]` the session, `pre[5:7]` the address, `pre[7:9]` the length
the Z80 will read (DE), `pre[9]` the XOR. Returns `(MQ, TSP, log_entries)`.
Nothing runs after it returns — the dispatcher's LOAD branch has no arm point
— so every exit path leaves the link in its final state itself.

State: reads `TSP.f_name`, `totlen`, `offset`, `tap_idx`, `ld_start`,
`ld_wrapped`, `load_file` (the last three with `getattr` defaults, because a
stale `dev_tspico` may predate them), `LOG_LEVEL`; writes `offset`,
`tap_idx`, `ld_start`, `ld_start_idx` (read back only by
`REWIND_ABORTED_SEARCH`), `ld_wrapped`. Files: the
mount's copy on the Pico's flash, `/TMP/temp.tap` (or `TSP.load_file`), or the
cached `/assets/nofile.tap`; never the SD card, which is unmounted while the
dispatcher runs ([../flows/sd-handover.md](../flows/sd-handover.md)).

**Entry.** `log_entries` is reset. `LOAD_RETRY_DONE` returns at once for the
ROM's retry of a refused header. The LED (`_LED()`) goes on; nothing in
`LOAD_TS` turns it off, the dispatcher's idle heartbeat does *(inferred: no
`led.value(0)` follows `LOAD_SERVE` in the dispatcher's LOAD branches)*.

**The source file.** With no mount (`TSP.f_name` empty or `TSP.totlen` 0) the
block comes from `_nofile_arch`, opened lazily if `OPEN_NOFILE_TAP` has not
run; if the file is missing the LOAD is refused with status 2 (Report R, not
the Report J the Z80 would get from an empty TX), logged and printed. Otherwise
`arch = open(TSP.load_file or "/TMP/temp.tap", "rb")`: `load_file` is the
one-shot tape `LOAD_SERVE` swaps in for an `f:` file, and the mount copy's
metadata is hot from `MOUNT_FILE`'s `COPY_FILE`, so the open is sub-ms.

**The bounded search.** The Z80 drives the LOAD retry loop: it asks for a
header, compares the name itself, and asks again on a mismatch, and a ROM
without SYNC (ROM 1.1) cannot tell the Pico it gave up ([BREAK_AND_ABORT.md](../../rom-analysis/BREAK_AND_ABORT.md)),
so the loop is bounded here. A data-block request (`pre[0] == 0xFF`) means
the Z80 accepted a header: `TSP.ld_start = -1`, the search is over. A header
request with no search in progress (`ld_start < 0`) starts one at the current
`offset` and `tap_idx`, with `ld_wrapped = False`. A header request after the
tape has wrapped (`ld_wrapped`) and come back to or past `ld_start` is a full
lap with nothing accepted: the search ends, the file is closed if it is not the
cached handle, and the LOAD is refused with status 7 ("End of file"; ROM 2.2
shows R). One lap is allowed deliberately, because a program that
legitimately needs to wrap cannot rewind — it does not speak TPI — and a second
lap would only repeat the first. Then the end of the tape: `arch_len` is the
file's size, and an `offset` at or past it is reset to block 0 with
`ld_wrapped = True`. A LOAD can start exactly at the end — after a `.ROM`
mount's updater has read its four blocks, or after any TAP's last block — and a
zero length read there used to reach `bytearray(-1)`: a `MemoryError` that
killed the firmware (hardware, 2026-09-30).

**Finding the block.** A loop reads each block's three-byte prefix (`len_lo`,
`len_hi`, `type`; `totbytes` = flag + content + CRC) at `offset`, wrapping at
the end, and skips every block whose type is not `pre[0]`, advancing `offset`
by `totbytes + 2` and `tap_idx` by one, until it finds a match, a block that is
shorter than two bytes or runs past the end of the file, or has skipped
`arch_len` bytes' worth (every block looked at). All the wrong-type blocks go
in one request, not one per request: a block of the wrong type served to the
Z80 failed at its flag byte, the Z80 stopped reading, and the rest of the
block waited in TX until the next command's SYNC, which looked like a BREAK
and rewound the search to where it began, so it never got past. (`BLINK()` used
to be called per skipped block, ~1 s inside the live transaction; that is most
of why a non-matching LOAD felt like a hang.)

**Checking it.** Three things make a block one the Z80 cannot load, each
answered with Report R, the tape moved past the block as a real tape would
have played through it: shorter than type + CRC or running past the end of the
file (a damaged TAP, or not a TAP); not the length the Z80 asked for
(`totbytes != req + 2`, `req` from `pre[7:9]` — it reads exactly that many
bytes and then a checksum, so it would stop part way or read past the end); a
bad XOR checksum. Before this, each of them reached the Z80, which for a
header just asked again (archive tapes under ZEsarUX ended in Report T,
2026-10-04). A lap with no block of the requested type at all ends the search
with status 7 for a header and 2 for a data block. The block is read into RAM
first — `hdr = bytearray(totbytes - 1)`, the content and the CRC, the flag
being `blk_info[2]` — always for a header, and for a data block after a
`gc.collect()` with `MemoryError` falling back to the file (`seek` back to
`offset + 3`, the first content byte). Why RAM: a LittleFS read can stall for a
few hundred µs on a cache refill or a block boundary, longer than the 4-deep TX
FIFO covers at ~47 µs a byte: "TX ran dry" 17 times in a 35795-byte block
streamed a chunk at a time, and the 2068 failed the LOAD (hardware,
2026-10-03); v1.29 has ~180 KB free. The checksum is then the XOR of the flag
and every byte of `hdr`, or of the file in `LOAD_CHUNK` chunks through
`_LOAD_BUF`, which must be 0. Any `bad` logs, closes a local file, sets
`offset = min(offset + 2 + totbytes, arch_len)` and `tap_idx += 1`, ends the
search and calls `LOAD_REFUSE(pre, MQ, 0x02)`.

The comment at this point records the autorun patch that used to live here,
inherited from the single-port firmware and removed on 2026-10-01: a BASIC header with
a "no autorun" line (32768 or more) had its high byte rewritten to 28h. The
ROM already skips the autorun for those (EXROM 06C3h: `LD H,(IX+0Eh) / AND
0C0h / JR NZ`, the same test as the Spectrum, identical in the genuine 2068
EXROM and ROMs 1.1 and 2.2; the 2068's own SAVE without LINE writes
80h there, 0450h), the patch made every non-autorun program autorun at a line
that cannot exist, and its CRC fix-up was only right when the old byte was
exactly 80h, so FFFFh ("no autorun" from some tape tools) reached the Z80 with
a bad checksum. `load_ts_hosttest.py` pins both cases.

**Before READY.** `gc.collect()` runs now, while the Z80 waits: once READY is
up it reads a byte every 50 µs with no handshake, the 4-deep FIFO covers ~200
µs, and a GC that starts mid-stream stops core0 for 15–25 ms (hardware,
2026-09-26: "LOAD watchdog fired with 15772 of 16096 bytes queued" on the
eighth LOAD of a session). There is no watchdog since #51 stage 5: every wait
below is bounded on its own, which the abort harness proved on hardware.

**Phase 1, the stream.** `wrt(blk_info[2])` queues the flag first; the Z80's
data loop reads flag + content + CRC = `totbytes` bytes, and the flag seeds its
running XOR. A nested helper `_close_if_local()` closes `arch` only when it is
not the cached nofile handle. The bookkeeping is `echo = bytearray(3)` for the
Z80's two echo bytes, `why` (0 ok, 1 a 0Fh write, 3 a stall), `sent` (bytes
queued, flag included), `dry` and `dry_at` (times TX was found empty after
READY, and the first byte it happened at: a near miss where the Z80 may have
read 00h), `primed` (READY has been said), `t_ready`, and `prof`, an
`array("I")` with the milliseconds after READY at every 1024th byte queued.
With the block in RAM, `STREAM_DMA(MQ, hdr, echo, 3000, True)` sends it and
says READY once the channel is running; its `(why, sent)` are taken. Without
DMA, or without the block in RAM, a hand loop streams from `hdr` or from the
file in `LOAD_CHUNK` chunks: per byte, `txf()` once; a full TX says READY the
first time (data is waiting) and then waits in `TX_ROOM(MQ, echo)`, whose code
ends the loop; an empty TX after READY counts a `dry`; then `put`. The file
path samples `prof` every 1024 bytes. READY is said here and not by the
dispatcher (#64): an early READY let the Z80 read 00h from an empty TX as the
flag, Report R, seen on hardware after a BREAK; the ROM's ready-wait allows
~20 s, so saying it later costs nothing. A block shorter than the FIFO never
fills it, so READY is said after the loop if it has not been. The hand loop's
per-byte path is one FIFO test and one `put`.

**Phase 2, the echo.** Until `echo` holds two bytes: `RX_WORD(MQ, 1000)`;
silence is `why` 3, a 0Fh write `why` 1, a data word is kept. The Z80 OUTs its
block type before its data loop (usually already collected during `TX_ROOM` or
`STREAM_DMA`) and its computed CRC after it, only once the CRC checked out
([PROTOCOL.md §6.1](../../PROTOCOL.md): the first echo comes before the data,
not after it). A BREAK can also land in the ROM's ready-wait around the block.

**Logs.** A block of 8192 bytes or more logs a DIAG line at WARNING (off by
default; at ERROR it put a line after every large LOAD and the flash write that
followed froze core0 during the next command): milliseconds per KB from `prof`,
where ~52 is the ROM loop's 178 T-states a byte and more means the Z80 was
slowed down. `prof` is only sampled on the file-streaming path, so the line
shows zeros for a block sent by DMA or from RAM. Any `dry` logs an ERROR with
the count and the first byte.

**Abort.** With `why` set: the bytes the Z80 actually read are `sent` minus
what is still in TX (0–4 means it was still in the ready-wait before the data);
`REWIND_ABORTED_SEARCH` puts a search in progress back where it began; the
local file is closed; `MQ_TO_IDLE(MQ, recovered=(why != 1))` empties both
FIFOs, stages one 0x01 and sets the status; a line beginning "INFO:" is logged at
level WARN for a BREAK or ERROR for a stall, with the count and the rewound offset; return. The Z80 then
sees TX = `[01]` and FFh after a BREAK — the ROM is waiting for READY +
IDLE to raise Report D — or FBh after a stall, so its next command gets Report
T.

**Phase 3, success.** The file is closed (the echo's block type and CRC,
`echo[1]` and `echo[2]`, are not checked). Two `wrt(0x01)`: the first is this
transaction's final status, which the Z80 reads after polling 0Fh, the second
the pre-load for the next command's first status read; then READY, because
the echo OUTs dropped Y to busy (issue #14) and without it the two bytes would
sit in TX unread, Report J on the next command. The tape moves on: `tap_idx +=
1`, `offset += totbytes + 2`; a mounted `.TAP` whose `offset` has reached
`totlen` rewinds to block 0 with `ld_wrapped = True` and an INFO line; the
nofile tape rewinds at `os.stat("/assets/nofile.tap")[6]`. No other status is
written here: the old `END_MSG` did, and its third 0x01 became the first byte
of the next data block's read, shifting the Z80's XOR by one — Report R on the
data block ([DUAL_PORT_DEVELOPMENT.md §8, bug 3](../../DUAL_PORT_DEVELOPMENT.md);
[PROTOCOL.md §13](../../PROTOCOL.md)).

**What the tests pin.** [`load_ts_hosttest.py`](../../../src/test/load_ts_hosttest.py)
runs this function against a Z80 that follows the EXROM's LOAD sequence,
interleaved, with a PIO that fails the test on any `put()` into a full TX:
header and data blocks load with both echoes, the final status and one
pre-load; a BREAK mid-block is heard in the send loop and ends in idle with TX
= `[01]` and the next LOAD working first time; a BREAK in the ready-wait
before the data ("read 0–4 bytes"); silence mid-block gives RECOVERED; no
thread is started; a LOAD without SYNC, as ROM 1.1 sends it, which never writes 0Fh, behaves as before; a
damaged or impossible block is Report R with the protocol left idle (at once
for data, through the staged error for a header, with and without SYNC) and
the tape past the block; a search skips every wrong-type block in one request
and one that never matches ends in R after a lap; a BASIC header reaches the
Z80 byte for byte, "no autorun" included; a LOAD starting at the end of the
tape rewinds; and the DMA section listed under `STREAM_DMA`.

**The comments.** The docstring's TIMING NOTE says the loop puts only when
TX has room (`TX_ROOM`) and never blocks in `put`; the echo arrives as RX
words the stream keeps (`ECHO_KEEP`, `RX_WORD`); the comment on `why` gives
its codes, 0, 1 and 3 (2, the watchdog's, is gone), and for older ROMs only
a stall ends the loop early. Until #181 these said the loop relied on a
blocking `MQ.put()`, the echo was drained "with `MQ.get()`", and "only the
watchdog (2) can end the loop early".

### `LOAD_SERVE(pre, MQ, TSP)`

The dispatcher's entry for LOAD, VERIFY and MERGE: serves the mounted TAP
through `LOAD_TS`, or, when the fdd ROM has armed a native file with
`tpi:fopen` (`TSP.native` with `op` not 0, set by `NATIVE_OPEN` in
[tspico-disk.md](tspico-disk.md)), the one-shot tape made from it. With no
arm, or an arm for a SAVE (`op` 0), it is `LOAD_TS`. If the pre-header's
session (`pre[3] | pre[4] << 8`) is not the one `tpi:fopen` was given, the
arm is stale — that statement never loaded — so `TSP.native = None` and
`LOAD_TS` serves the mount. Otherwise it saves `f_name`, `totlen`, `offset`,
`tap_idx`, `ld_start`, `ld_wrapped` and `ld_start_idx`, sets them from the
`native` dict (`tap` = the one-shot file `/TMP/native.tap`, `totlen`, and the
position and search fields with defaults), sets `TSP.load_file = nat["tap"]`
so `LOAD_TS` opens that file, and runs `LOAD_TS`. A `finally` copies the
position and search fields back into the dict, restores the mount's fields,
clears `load_file`, and drops the arm (`TSP.native = None`) once the data
block has been served (`pre[0] == 0xFF`) or the search has given up
(`ld_start < 0`). Nothing else ever sees the swap, and the mount is exactly as
it was afterwards. Returns `LOAD_TS`'s tuple. The dispatcher calls it from
both the LOAD and the headerless-LOAD branches; `load_ts_hosttest.py` covers
the native arm and a stale session.

## ZX48 mode

Spectrum mode ([../flows/zx48.md](../flows/zx48.md), [PROTOCOL.md §10](../../PROTOCOL.md))
has no pre-header, no status byte and no echo: after `'L'` the ROM reads
exactly flag + content + CRC, after `'S'` it writes a block. The pre-load chain
does not apply ([PROTOCOL.md §13](../../PROTOCOL.md), "ZX48 mode is a
different protocol"). `ZX48_IO` in [tspico-dispatch.md](tspico-dispatch.md)
dispatches on the command byte and calls the handlers below; each returns
`(MQ, TSP, log_entries, nxt)`, where `nxt` is a command byte the Z80 wrote in
the middle of the handler's block, to dispatch next, or -1.

| Name | Value | What it is |
|---|---|---|
| `ZX_STALL_MS` | `const(1000)` | A block the Z80 stopped reading or sending. The Spectrum ROM reads a LOAD byte every ~43 µs and writes a SAVE byte every ~83 µs, with ~1 ms pauses around a block's flag and CRC; nothing a live Z80 does in the middle of a block is slower. Also `ZX_TPI`'s limit. |
| `ZX_BLOCK_GAP_MS` | `const(3000)` | SAVE: the ROM pauses ~1 s between the header and the data block; `SAVE_ZX` waits this long for the data block's `'S'`. |

### `ZX_FLUSH_TX(MQ)`

Empties TX: the tail of a block the ROM did not read to the end. Up to
`DRAIN_MAX` passes of `pull(noblock)` and `mov(osr, null)`, like the first half of
`MQ_TO_IDLE`; ZX48 mode has no status pre-load, so the rest of it does not
apply. Callers: `LOAD_ZX` (before the flag goes in, and after an early stop),
`LOAD_ZX_C`, `ZX_ARM`, `tspico.py`'s `ZX_TPI`, and `upgrade.py`.

### `ZX_ROOM(MQ, stall_ms)`

ZX48 LOAD's slow path: TX is full, so wait for room, listening, instead of
blocking in `MQ.put()`. Returns -1 when there is room; -2 when TX stayed full
for `stall_ms` (the Z80 stopped reading); or the 9-bit word the Z80 wrote,
0–511, which means it has left this block and sent its next command (`'L'`,
`'S'`, ...) for `ZX48_IO` to dispatch. Unlike `TX_ROOM`, any word ends it,
because ZX mode has no echo. Why: the ROM reads a block in one DI loop with no
way out, so it only stops early when it asked for fewer bytes than the block
holds — LD-BYTES reads flag + the length it expects + CRC, whatever the block's
own length — and `LOAD "name"` does that with every block before the one it
wants, then prints its name and asks for the next. No allocation, as
`TX_ROOM`. Callers: `LOAD_ZX`, `LOAD_ZX_C`, `ZX_TPI`, and `upgrade.py`'s
`reply` (its short answers, and its fallback when no DMA channel is free).

### UPDATE mode

A board upgraded from 1.1 to this firmware still has its old TS-2068
ROM, which cannot talk to it. Every shipped flash image has the same original
Spectrum ROM in slot 0 (crc32 A8E12A24), and `OUT 244,3` switches to it
whatever the 2068 ROM is, so that ROM loads the updater
([upgrade.md](upgrade.md), [../rom/zx48.md](../rom/zx48.md)). It has no
handshake at all: its LD-BYTES sends `'L'`, waits a fixed ~0.94 ms and reads
the flag, whatever is in TX. So UPDATE mode does not answer `'L'`: TX always
holds the next bytes of the updater tape, kept as one stream — each block's
flag, content and CRC back to back — and the next block's flag is already
queued behind the last block's CRC when the next `'L'` comes. Proven on
hardware with a real flash chip ([`zx_bootstrap_harness.py`](../../../src/test/zx_bootstrap_harness.py)):
BASIC, SCREEN$ and CODE loaded, TX never ran empty, each `'L'` arrived exactly
at its block's flag. The four helpers are used by `src/upgrade/upgrade.py`'s
`serve()`; [`upgrade_hosttest.py`](../../../src/test/upgrade_hosttest.py) runs
that loop against a Z80 following the original ROM's LD-BYTES and then the
real `updater.bin`, and pins the tape reaching the ROM whole and in order,
the tape re-armed after a failed update so `LOAD ""` works again, and the
frozen-module closure of the upgrade UF2.

### `TAPE_STREAM(path)`

Reads the `.tap` file at `path` and returns `TAPE_STREAM_OF` of its bytes. It
has no caller in the firmware or in the upgrade loop, which gets its tape from
the generated `upgrade_data.TAPE`.

### `TAPE_STREAM_OF(raw)`

A `.tap` as one stream: each block's flag + content + CRC, the two-byte
lengths dropped. Walks `raw` by length prefix and returns `(stream, starts)`,
`stream` a bytearray and `starts` the offset of every block in it. Called by
`upgrade.serve`.

### `ZX_ARM(MQ, stream)`

Rewinds the tape: `ZX_FLUSH_TX`, then queues the stream's first bytes, at most
`TX_DEPTH`, so the flag is there when the ROM reads 0.94 ms after its `'L'`.
Returns the stream position (bytes queued). Called by `ZX_STREAM` on its two
rewinds and by `upgrade.serve` at start, after a stray command burst, after a
failed update and after a reset.

### `ZX_STREAM(MQ, stream, pos, rewind_ms)`

Keeps TX fed from `stream[pos:]` until the Z80 writes a word, and returns
`(word, pos)`. It never blocks in `MQ.put()` and never returns on its own: the
per-byte path is a FIFO test and a `put`, and the clock runs only while TX is
full. The tape rewinds by itself, with `ZX_ARM`, in two cases: once the Z80
has read the whole stream and TX is empty, so the next `LOAD ""` starts the
tape again; and after `rewind_ms` with bytes waiting in TX, more than the first
FIFO-full sent (`pos > TX_DEPTH`) and the Z80 not reading — a LOAD that was
stopped (BREAK between blocks, a reset), so the next one does not start in the
middle of the tape. `upgrade.serve` calls it with `REWIND_MS` = 5000 while the
updater is not yet running.

### `LOAD_ZX(MQ, TSP)`

Sends one TAP block to the Spectrum ROM: after the `'L'` that `ZX48_IO`
consumed and the ROM's poll of 0Fh for READY (the customised ZX ROM, not the original in slot 0; up to
~3.8 s, then Report R), the response is exactly `totbytes` bytes, flag +
content + CRC, with no status byte and no pre-load. The LED goes on. The source
is `/assets/nofile.tap` with no mount (`f_name` empty or `totlen` 0; a WARNING
is logged) or `/TMP/temp.tap`, opened by path; `TSP.load_file` is not
consulted. The three-byte prefix is read at `TSP.offset`. `ZX_FLUSH_TX` clears
the tail of a block the ROM did not read to the end, so the flag goes in
clean; `gc.collect()` runs while the ROM waits for READY (a GC mid-block stops
core0 for 5–25 ms and the Z80 reads 00h from an empty TX every 43 µs). The
whole block (content + CRC) is read into `whole = bytearray(totbytes - 1)`,
`MemoryError` falling back to the file a chunk at a time — no file access once
the ROM reads blind ("TX ran dry" 9–10 times a block, hardware 2026-10-02/03).

The flag is queued before READY, because the ROM reads 0Eh the instant READY
rises. With the block in RAM, `STREAM_DMA(MQ, whole, None, ZX_STALL_MS, True)`
sends it: `why` 4 puts the Z80's word in `nxt`, any other non-zero `why`
(a stall) makes `nxt` -2. Without DMA, READY is said by hand after the flag,
and the hand loop from `whole` or from the file through `_LOAD_BUF` streams
byte by byte: a full TX sets `primed` and waits in `ZX_ROOM(MQ, ZX_STALL_MS)`,
whose result other than -1 ends the stream; an empty TX after `primed` counts
a `dry`. The file is closed. An early end (`nxt != -1`) logs the bytes the ROM
read (`sent` minus what TX still holds) and whether it stopped or sent a byte,
flushes TX, and turns -2 into -1. Any `dry` logs an ERROR. The LED goes off.
Then the tape moves on, `offset += totbytes + 2`, `tap_idx += 1`, and rewinds
to 0 when `offset >= TSP.totlen`. Y stays READY afterwards: the Z80's reads do
not touch it, and its next OUT drops it.

Why the stream never blocks and the tape always moves on: the ROM stops
reading early on every block before the one `LOAD "name"` wants (see
`ZX_ROOM`), and before #51 each skipped block waited 3 s for the watchdog and
was then sent again, because the position only moved on a complete read.

Beware: with no mount, `TSP.totlen` is 0, so `offset >= totlen` holds after
every block and the tape rewinds to 0 each time — ZX mode serves only the
first block of `nofile.tap` *(a consequence of the code as written, not
confirmed on hardware)*. [`zx48_io_hosttest.py`](../../../src/test/zx48_io_hosttest.py)
pins `LOAD ""` loading header + data with the position moving on; `LOAD
"name"` skipping a program in front of it, each skipped block ending as soon
as the Z80 sends its next `'L'`, the tape moving on, the unread tail flushed;
a Z80 that stops mid-block giving up after `ZX_STALL_MS` with TX flushed and
the next LOAD working; no `put()` into a full TX; and the same by DMA.

### `ZX_C_BLOCKS(data)`

`LOAD_ZX_C`'s cut of its buffer into whole TAP blocks. Returns `(blocks,
used)`: each block is flag + content + CRC (the TAP block without its 2-byte
length) and `used` the bytes they take. A block the buffer cuts short is left
out, for the next `'L'` to start at, and a lone byte after the last block is
ignored. Why it exists (#172): the inline loop it replaced tested
`long > len(rd_bytes)`, two bytes short, so a block the buffer cut by one or
two bytes was served truncated and counted as read, and one leftover byte
raised `IndexError`. [`zx48_io_hosttest.py`](../../../src/test/zx48_io_hosttest.py)
pins the edges.

### `LOAD_ZX_C(MQ, TSP, buf_size)`

ZX Spectrum LOAD in "compatible" mode (`TSP.ZX_TAPE_COMPAT`; `ZX48_IO` passes
`par2` as `buf_size` when it is at least 16384, else 52100). Where `LOAD_ZX`
answers one `'L'` with one block, this reads up to `buf_size` bytes of the TAP
into memory and streams every block in it back to back, the Z80 pacing it:
blocks the Spectrum ROM skips (wrong name, wrong type) are consumed by its own
LD-BYTES calls as they would be off a tape running continuously, which is what
makes hard-to-load TAPs work here and not in `LOAD_ZX`. It is memory-hungry and
can run the Pico out of memory.

Steps: `log_entries` is `" "`. The file first: `/assets/nofile.tap` when
nothing is mounted (`not TSP.f_name` or `totlen` 0), as `LOAD_ZX` does, with
its own length (seek to the end); else `/TMP/temp.tap` and `TSP.totlen`. A file
that won't open logs and returns -1. If `TSP.offset` is at or past that length
it returns -1 — so at the end of the tape the ROM gets nothing and times out
*(inferred: the ROM's ~3.8 s poll, then Report R)*. Up to `buf_size` bytes are
read from `offset` (a read error, caught by a bare `except`, logs and returns
-1), cut into whole blocks by `ZX_C_BLOCKS`, and `TSP.offset` advances by the
bytes those blocks used, so the next call starts at the first block left out.
`ZX_FLUSH_TX`, `gc.collect()`. The first byte
of the first block is queued before READY (a memoryview keeps the rest from
being copied), and the blocks are streamed with the LED on per block: a full
TX waits in `ZX_ROOM(MQ, ZX_STALL_MS)`, and `'L'` (76) from the ROM — its next
LD-BYTES, which waits for READY — is answered with READY and the stream runs
on; any other byte, or a stall, ends it. The tail then lets the Z80 read what
is left the same way, bounded by `ZX_STALL_MS`: in compatible mode the whole
buffer is streamed, so once the ROM has found its file the rest is never read,
and the old unbounded wait here hung ZX48 mode until reset ([PROTOCOL.md §13](../../PROTOCOL.md),
"`while MQ.tx_fifo() != 0: pass` can hang forever"). An early end logs the
unread count and flushes TX; -2 becomes -1.

Before #172 the file was chosen after the `offset >= totlen` test, so with
nothing mounted at boot (`totlen` 0) the ROM got nothing, and after
`tpi:close` (which leaves `totlen`) `nofile.tap` was read sized by the
forgotten file; and blocks were cut as `ZX_C_BLOCKS` now explains. Beware:
the position moves by the blocks buffered per `'L'`, not by what the ROM read.
`zx48_io_hosttest.py` pins READY for every `'L'`, a bounded tail, the cut and
`nofile.tap` with nothing mounted. (Compatible mode is parked as a whole,
#129.)

## SAVE

### `SAVE_NAME(hdr)`

Extracts the ZX filename from a SAVE header block and judges it. The ten-byte
space-padded name is `hdr[4:14]`. Returns `(name, ok)`: `name` is a printable
rendering with the space padding trimmed by index, any byte outside printable
ASCII (below 20h or 7Fh and above) shown as `?`; `ok` is `True` only when every
byte is alphanumeric, `_` or `-`, the FAT-safe allowlist. Built byte by byte
and never with `bytes.decode()`: a TS-2068 name can carry bytes of 80h and
above (graphics characters, BASIC tokens), `decode()` raises on those, and
`SAVE_TS` runs unguarded in the dispatcher's loop, so the exception would take
the loop down ([PROTOCOL.md §13](../../PROTOCOL.md), "Never call
`bytes.decode()`"). This allowlist is stricter than the one `SAVE "tpi:<name>"`
uses in `tspico.py`, which allows any printable character but the eight
FAT-reserved ones; the divergence is known and left ([PROTOCOL.md §13](../../PROTOCOL.md),
"The two filename allowlists disagree"). Callers: `SAVE_TS` (both values) and
`SAVE_ZX` (the name only; it applies its own, looser test).
[`save_name_hosttest.py`](../../../src/test/save_name_hosttest.py) pins the
refusal of a bad name, a good name saving, an empty name landing on
`noname.tap`, and append ignoring the header's name.

### `REFUSE_SAVE(MQ, status, quiet_ms=500)`

The way to fail a SAVE: at the post-header status read. The Z80 has sent its
header and is polling 0Fh for the mid-phase status; `MQ.put(status)` is the
verdict, Y goes to READY (`mov(y, invert(null))`, FFh), and
`DRAIN_REFUSED_SAVE` resyncs RX. The ROM's `STATUS_TO_REPORT` path RST-8's
with a BASIC report and aborts before the data block is sent. The alternative
— writing 0x01 and bailing out, as the header-CRC and no-data paths once did —
made the Z80 stream the whole data block at a handler that had returned,
nobody drained it, the next pre-header read picked up data bytes, and the
trailing 0x01 was read as the final status: "0 OK" for a transfer that
produced no file ([PROTOCOL.md §13](../../PROTOCOL.md), "Never answer an error
with 0x01" and "Validate a SAVE before you write the final status"). Returns
the bytes drained; the caller returns afterwards. The statuses `SAVE_TS` sends
through it: 0x02 Report R (session mismatch, bad header CRC, no data block),
0x03 Report F (name), 0x06 Report 6 (no memory for the block), 0x08 Report A
(BLEN 0), 0x0A Report J (no SD card) and 0x0B Report D (a native "Replace?"
answered N); the docstring lists all six (until #181, the first four). The mapping is
[PROTOCOL.md §5.3](../../PROTOCOL.md).

### `DRAIN_REFUSED_SAVE(MQ, quiet_ms=500)`

Resyncs the RX FIFO after a refusal: drains words until the bus has been quiet
for `quiet_ms`, and returns how many it dropped. When the refusal lands no data
arrives and it returns 0 after `quiet_ms`; it is the safety net for a Z80 that
sends the data block anyway, whose bytes would otherwise sit in RX and be read
as the next command's pre-header. `SAVE_ZX`'s `fail` uses it (1500 ms) for a
different reason: ZX mode has no status byte to refuse with, so a bad header's
data block, including its `'S'`, has to be swallowed so none of it is
dispatched as a command. It does not test for a 0Fh write: a SYNC within the
quiet window would be drained with the rest *(inferred harmless: the ROM has
raised a report and stopped)*.

### `SAVE_TS(MQ, TSP, pre=None)`

Receives a SAVE: the header block and the data block of
[PROTOCOL.md §6.2](../../PROTOCOL.md), after the dispatcher has read the
pre-header, looked for the card (`SD_PROBE`, leaving `TSP.save_no_card`),
waited for core1, and not said READY; the flow is
[../flows/save.md](../flows/save.md). `pre` is the pre-header, for the session
check. Returns `(MQ, TSP, log_entries, saved)`: `saved` is `True` only if a
file reached the SD card, and is the dispatcher's cue to re-mount it and
refresh the listing (it used to infer that from `"sd" in os.listdir("/")`,
which was wrong for a write that fails after the mount). State: reads
`TSP.f_name`, `append`, `cur_path`, `LOG_LEVEL`, `save_no_card`, `native`;
writes `save_recovered`, `save_final`, `f_name` (the new file's path, or `""`
again when its write failed), `native`, `native_saved`, and the file. `TLM` is
imported from `TS.tspico` inside the function, because a module-level import
would be circular — and the upgrade UF2 never calls `SAVE_TS`. The old
`WATCHDOG` is gone (#51 stage 5): `RX_CAPTURE` and `RX_BLOCK` bound every
wait, and a BREAK or SYNC ends the SAVE at once.

**The header block.** After `gc.collect()` and a TLM line, `RX_CAPTURE(MQ,
_SAVE_HDR_RAW, 21, 1000, "mid")` says "mid" only once it is listening and
takes the 21 words: flag 00h, the session (two bytes, a TPI addition), HDTYPE,
the ten-character name, BLEN, ADDR, HDVARS and the CRC. READY is said here and
not in the dispatcher (#51 stage 3): the Z80 streams all 21 bytes ~43 µs a byte
the moment it sees it, while the dispatcher was still logging and this function
still in its TLM print. Fewer than 21 words: a 0Fh write (BREAK) logs INFO and
returns `False`; silence sets `TSP.save_recovered` (the dispatcher answers
RECOVERED, Report T on the ROM) and logs ERROR. The low bytes go into
`hdr`.

**Refusals at the mid-phase status**, each through `REFUSE_SAVE` and a
return of `False`, in this order: the session (`hdr[1:3]` must repeat
`pre[3:5]` when the pre-header carries one; 0000h means the SAVE did not come
from BASIC and is unchecked) — a mismatch means the bytes are misaligned, R;
the CRC (XOR of `hdr[0]` and `hdr[3:20]`, skipping the session bytes, against
`hdr[20]`) — a mismatch is corruption only the Pico can see, R; no card
(`TSP.save_no_card`) — J, so the 2068 stops before the data block and keeps
its program ([SD_ROBUSTNESS_PROPOSAL.md §0](../../SD_ROBUSTNESS_PROPOSAL.md));
a native SAVE (`TSP.native` with `op` 0 for this session, armed by `tpi:fopen`
for `SAVE "f:path"`; any other SAVE drops a stale arm) whose "Replace (Y/N)?"
was answered N — D; the name, through `SAVE_NAME`, unless the SAVE is native or
an append (`TSP.f_name and TSP.append`, where the target is the mounted TAP
and the header's name is never used) — F (this check used to run at the end,
after the final status had told the 2068 "0 OK", and its `END_MSG` then
blocked in `MQ.put` on a Z80 that had stopped reading: `SAVE "bad file"`
wedged the Pico until reset); BLEN (`hdr[14:16]`) of 0 — A, because the ROM's
SA-BYTES loop decrements DE then tests it, so a zero length floods 65536 bytes
onto the bus; and the block buffer `bytearray(blen + 4)`, retried once after
`gc.collect()` — Report 6, because BLEN is 16 bits, `SAVE "x" CODE 0,65535` is
legal, and an unguarded `MemoryError` dropped the Pico to a REPL while the
2068 waited out its ~19.9 s ([PROTOCOL.md §13](../../PROTOCOL.md), "Guard every
allocation sized by a Z80-supplied field").

**The data block.** `wrt(0x01)` is the mid-phase status, then `MQ_STATUS(MQ,
"mid")`: READY with the transaction open, so the Z80 reads the 0x01 and
streams the data block with no ready-wait before it. `RX_BLOCK(MQ, blk, long,
3000, 1000, "mid")` then takes `long = blen + 4` bytes (flag FFh, session,
data, CRC), allowing 3 s before the first byte because the Z80 does internal
processing first (0.9 s measured for a ten-byte BASIC program, hardware
2026-10-03, so the old 1 s limit had no margin) and 1 s of silence after it.
Note that "mid" is said twice: once here and again inside `RX_BLOCK` through
`SAY_READY`, and the first time is before `RX_RING` has configured its channel,
which is the order `RX_RING`'s own docstring warns against; what makes it safe
is the ROM's pause before the data block *(inferred from the measured 0.9 s
and the code's comments; not tested as such)*. The outcomes: `RXB_STALL` with
nothing received refuses with R ("no data after 3s" in the TLM and log text)
rather than claim OK, which on a slow Z80 meant a data
block streamed into a returned handler, jamming RX for the next command; a
0Fh write (the ROM checks BREAK every 256 bytes) logs INFO and returns
`False` with nothing written, the Z80 waiting for READY + IDLE; a stall
mid-block sets `save_recovered` and logs ERROR. The dispatcher's arm point
afterwards is the way back in every case.

**The data parity.** The XOR of the flag and the content, skipping the two
session bytes, must equal the last byte; the Z80 computed it over what it
sent, so a mismatch means bytes were lost in transit. This path answers
itself: `wrt(0x02)` as the final status (Report R), `wrt(0x01)` as the next
pre-load, `MQ_STATUS(MQ, "idle")`, then a wait of up to 300 ms for the Z80 to
read the 02 (`tx_fifo() <= 1`), because the dispatcher's `ACTIVATE_MQ` rebuilds
the state machine, which throws an unread TX away and stages its own 0x01, and
the Z80 would print "0 OK" for a SAVE that wrote nothing. ERROR logged, return
`False`.

**The final status waits for the card.** The Z80 waits for READY (~20 s)
before it reads the final status, so it is not sent here: the file is written
first, the dispatcher re-mounts and re-reads the folder, and only then does
its single arm point stage this status (`TSP.save_final`), the next pre-load
and READY. This used to send 0x01 here, before the write: the 2068 printed
"0 OK" and went on while the Pico spent ~0.9 s on the card with its bus
interface down, and a BASIC program's next `tpi:` command sent SYNC, waited the
ROM's ~1 s for IDLE, and sent its pre-header into nothing — "Partial pre-header
4/10", Report J (hardware, 2026-10-04, `savetest.bas`). With the bus busy the
Z80 does not read 0Eh during the write, so #40's pin-grab race cannot happen,
and a failed write is reported instead of "0 OK".

**Reconstruction and the target.** Both blocks are rewritten in place into
TAP form: the flag moves to `[2]` and the two session slots become the
little-endian block length (`len - 2`: 19 for the header, `blen + 2` for the
data), so the output is a standard TAP with no recalculation (the block CRC
never included the session bytes). The target is one of three: a native save
writes `nat["path"]` in `"wb"` mode with `native.to_file(hdr[3], BLEN, ADDR,
HDVARS, blk[3:-1])`'s output as the only block ([native.md](native.md)) and
sets `TSP.native_saved` so the dispatcher refreshes the listing without
touching the mount; an append (`TSP.f_name and TSP.append`) writes the mounted
TAP in `"ab"` mode; otherwise `TSP.cur_path + "/" + (save_name or "noname") +
".tap"` in `"wb"` mode, and `TSP.f_name` is set to it (an all-spaces or empty
ZX name is legal and lands on `noname`). No status is written here either.

**The write.** `ENA_SD(TSP.LOG_LEVEL)` mounts the card (through `SAVE_MOUNT`
in the firmware); if the mount found a different card (`SD_NOTE_CARD` turned
`TSP.append` off) and the mode is `"ab"`, an `OSError(19)` is raised rather
than appending to a same-named file on the wrong card; then the header and the
block are written. Any `Exception` — `ENA_SD`'s own failure is swallowed, so a
pulled card surfaces as `OSError` from `open()` — sets `saved = False`, logs
and TLMs it, takes back `TSP.f_name` (set to `""`) for a new file that never
landed, and clears `native_saved`. `os.chdir(TSP.cur_path)` follows, logged if
it fails; the buffers are dropped and collected; a success is logged at INFO;
`TSP.save_final` becomes 0x01 ("0 OK") or 0x0A (Report J: nothing written).
`/sd` is left mounted for the dispatcher's `DEACTIVATE_SD`.

**What the tests pin.** [`save_ts_hosttest.py`](../../../src/test/save_ts_hosttest.py)
runs this function against a Z80 that follows the EXROM's SAVE sequence (the
ready-waits at 18D2h and 190Bh, the data block with no ready-wait, BREAK every
256 bytes) and then does what the dispatcher does: a normal SAVE writes the
right `.tap` with statuses 01 / 01 01; READY is raised here, right before the
header capture, and not by the dispatcher; BREAK in the header block and mid
data block ends the SAVE at once with nothing written and the Z80 getting
READY + IDLE for Report D; silence mid-block gives RECOVERED; a corrupted data
block gives final status 02 and no file; a header whose session does not match
is refused; no RX overflow, and the data capture allocates nothing.
[`save_name_hosttest.py`](../../../src/test/save_name_hosttest.py) pins the
name, CRC, no-memory and card-pulled paths;
[`sd_wedged_hosttest.py`](../../../src/test/sd_wedged_hosttest.py) the
dispatcher after a successful return when the re-mount fails. The record of
how this function diverged from the 1.1c original is
[SAVE_1.1C_VS_1.5.md](../../SAVE_1.1C_VS_1.5.md), whose §10 keeps the still
open 9-of-21 header stall.

### `_xor(buf, start, end)`

The XOR of `buf[start:end]`. `SAVE_ZX` uses it for both blocks' parity
(`_xor(hdr, 2, 21)`, `_xor(blk, 2, n + 4)`: flag, content and CRC together
must give 0).

### `SAVE_ZX(MQ, TSP)`

Receives a SAVE from the Spectrum ROM in ZX48 mode and writes a TAP. SA-BYTES
sends, per block and with no handshake after the READY poll, `'S'` then
`len_lo`, `len_hi`, flag, content, CRC — the two length bytes included, unlike
the 2068's TPI blocks. `ZX48_IO` consumed the header block's `'S'`, so this
reads 21 bytes, then the `'S'` that opens the data block ~1 s later, then
`len + 4` bytes, `len` from the header's length field (`hdr[14:16]`). The Z80
reads nothing back — SA-BYTES ends with EI/RET — so there is no status byte,
and one would be an orphan in TX. A SAVE that fails is logged and not written;
the only thing the Spectrum can be told is that a header refused never gets
READY for its data block, and the ROM then gives Report R after ~3.8 s.
Returns `(MQ, TSP, log_entries, nxt)`.

A nested `fail(why, drain)` logs `"ZX SAVE: <why>; nothing saved."` at
ERROR, drains with `DRAIN_REFUSED_SAVE(MQ, 1500)` when `drain` — swallowing the
rest of what the ROM is sending, the data block's `'S'` included, so none of
it is dispatched as a command — and returns with `nxt` -1. Steps:
`RX_BLOCK(MQ, hdr, 21, ZX_STALL_MS, ZX_STALL_MS, "ready")` (READY once
listening: the `'S'` dropped Y and the ZX ROM polls 0Fh before sending);
not `RXB_OK` fails without a drain. The block must be a tape header: length
17, flag 0, parity 0, else `fail` with a drain. `blk = bytearray(n + 4)` after
a `gc.collect()`, `MemoryError` failing with a drain. `RX_WORD(MQ,
ZX_BLOCK_GAP_MS)` must be `'S'` (83): anything else is logged and returned as
`nxt`, so `ZX48_IO` dispatches a command byte, or -1 for silence. Then
`RX_BLOCK` again for `n + 4` bytes with READY once listening; its length field
must be `n` and its parity 0. The name from `SAVE_NAME` must be non-empty and
contain none of `?:*\/|"<>` — a looser rule than `SAVE_TS`'s `ok`, so a ZX
SAVE allows spaces and dots, and a byte rendered as `?` is rejected by that
character. The two length fields become TAP lengths (19, and `n + 2`), and
the file is `name + ".tap"`.

The write: `ENA_SD(TSP.LOG_LEVEL)`, and only after the mount is the folder
prepended (`TSP.cur_path + "/" + filename`): ZX48 mode has no card check ahead
of the SAVE, so this mount is where a returned or swapped card is noticed and
`SD_REVALIDATE` may move `cur_path` to `/TAP`. Both blocks are written;
`saved = True`; `TSP.listing_stale = True`, because the folder's listing
(CAT, and the names `LOAD "tpi:..."` matches) is now missing this file, and
re-reading it here with the card mounted would keep the bus off the PIO for a
directory scan while the Spectrum may already be sending its next `'L'` or
`'S'` — `tspico.py` re-reads it at the next point that uses it with the Z80
waiting for READY (`PROCESS_CMD` or `ZX_TPI`; hardware 2026-10-02: a ZX `SAVE
"q"` was on the card but CAT did not list it until `tpi:cd`). A failed write
is logged. `/sd` is unmounted (errors ignored) and `MQ = ENA_MQ_DUAL(MQ)`
rebuilds the bus state machine, because `ENA_SD` re-claimed GPIO 2–4; the new
object is returned to `ZX48_IO`. A success is logged at INFO; `nxt` is -1.

[SD_ROBUSTNESS_PROPOSAL.md §0](../../SD_ROBUSTNESS_PROPOSAL.md) records the
limit: the ZX ROM has no way to refuse a SAVE, so one with no card fails after
the fact. [SAVE_1.1C_VS_1.5.md §7](../../SAVE_1.1C_VS_1.5.md) records that
`SAVE_ZX` had not been migrated to dual-port when it was written; it has
since, as a note there now says (the docstring's "DUAL-PORT MIGRATION
(2026-09)" describes the change). [`zx48_io_hosttest.py`](../../../src/test/zx48_io_hosttest.py)
pins the right `.tap` written; a SAVE that stops, fails its parity or has an
unusable name writing nothing; a refused header's data block never getting
READY; and no watchdog.

## Where comments, documents and the code disagree

The code wins in each case.

- `SAVE_TS`: "mid" said both before and inside `RX_BLOCK`, the first time
  before the DMA channel is set up.
- `LOAD_TS`: `prof` is sampled only on the file-streaming path.
- (#181 fixed the rest: `ENA_SD`'s comment and PROTOCOL.md §6.2/§13 on when
  the SAVE's final status goes out, `LOAD_TS`'s, `REWIND_ABORTED_SEARCH`'s,
  `RX_BLOCK`'s and `RX_CAPTURE`'s docstrings, `REFUSE_SAVE`'s status list,
  "no data after 1s", and the unused `echo`, `blq_t` and `crc`.)
