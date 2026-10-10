# Phase 4: the board layer (proposal)

Status: agreed 2026-10-10 (decisions at the end), in progress. Phase 4 of the v3 port plan
(tspico-hardware `docs/v3-firmware-port-plan.md`): one source tree that builds
for the v2 board (RP2040) and the v3 card (RP2350B, `tsbus`), with every
hardware touch behind `TS/board.py`. v2 behaviour must not change: the host
tests stay green and a v2.2 board passes its hardware checks.

This comes from a read-through of `main.py`, `tspico.py`, `tspico_io.py`, the
other TS modules, `src/upgrade/` and the host tests (2026-10-10). Line numbers
are `main` at `e5e4ff5`.

## What the read-through found

The hardware is touched in fewer places than the line count suggests. Most of
the protocol code already reaches the bus only through `MQ` and the
`tspico_io` helpers.

| Area | Where | How much |
|---|---|---|
| Boot pins and clock | `main.py` 64-80 | 7 pins, `freq(270 MHz)` |
| Slot state machines (`ROM`, `BANK`) | `TS2068_IO` 6227-6238; `MEMBOOT` 5053; `MEMDOCK` 5174 | 2 SMs, created once; 3 `put` pairs |
| Making `MQ` | `ACTIVATE_MQ` 770; `ZX48_IO` 7193; `tspico_io.ENA_MQ_DUAL` 974; `upgrade/main.py` 38 | 4 constructions |
| SD sharing D0-D2 | `ACTIVATE_SD` 1084, `DEACTIVATE_SD` 703, `ACTIVATE_MQ`, `tspico_io.ENA_SD` 1019, `SAVE_MOUNT` 1178 | 16 / 18 / 17 call sites, all through those functions |
| LED (`Pin(25)`) | `TS2068_IO` 6202, then `led.` | 41 uses; none inside a per-byte loop |
| Core 1 (`_thread`) | `BLINK_LED` during the boot mount (6335); `SAVE_LOG` from the idle heartbeat (6996) | 2 starts, coordinated by `busy`/`dead` |
| Direct PIO registers | `tspico_io.MQX` (`mem32` at PIO0 SM0, 0x502000D8) | 13 call sites in tspico.py, about 20 in tspico_io |
| DMA tied to PIO0 SM0's DREQs | `_RING_SETUP` (at import), `RX_DMA`, `RX_RING`, `STREAM_DMA` | all optional already: `None` falls back to polling |

Three facts shape the design:

1. **The pacing code works on v3 as it is.** `TX_ROOM`, `ZX_ROOM`, `LOAD_TS`'s
   `primed`/READY, the "TX ran dry" count and `sent - txf()` all test
   `tx_fifo() >= TX_DEPTH` (4). `tsbus.MQ().tx_fifo()` reports the real level,
   so these loops still keep four bytes queued, exactly as on v2. The 1 KB
   queue only matters where code puts more than four bytes at once: the DMA
   paths and the 64-pass TX flushes.
2. **`mem32` and `rp2.DMA` exist on the RP2350.** Unguarded, `MQX` would write
   into PIO0 SM0 (which runs `serve` on v3), and `_RING_SETUP` would claim a
   DMA channel paced by PIO0's RX DREQ **at import**. On v3 both must be off.
   `MQX` then falls back to `MQ.exec()`, which `tsbus` already understands.
3. **SD never needs the bus on v3.** The 51 SD call sites all go through
   `ACTIVATE_SD`, `DEACTIVATE_SD`, `ACTIVATE_MQ` and `ENA_SD`. Changing those
   four bodies leaves the call sites alone.

## The proposed `TS/board.py`

Selected at run time by whether the `tsbus` module exists (it is only in the
v3 build). One small dispatcher, two implementations, all frozen in both
builds:

```python
# TS/board.py
try:
    import tsbus
    from TS.board_v3 import *
except ImportError:
    from TS.board_v2 import *
```

Host tests have no `tsbus`, so they get `board_v2`, unchanged. New v3 tests
import `board_v3` directly with a fake `tsbus`.

| Call | v2 (`board_v2`) | v3 (`board_v3`) | Replaces |
|---|---|---|---|
| `NAME` | `"v2"` | `"v3"` | — |
| `PIO_MQ` | `True` | `False`: `tspico_io` turns off `mem32`/DMA paths | `_mem32`/`_DMA` set at import |
| `early_init()` | the 7 pins and `freq(270 MHz)` | `tsbus.start()` (250 MHz, core 1); safe pins already done in C | `main.py` 64-80 |
| `start_memory(rom_sm, bank_sm)` | create `ROM`/`BANK` SMs, `put` both | load the ROM images into `tsbus` (see "Slots" below), serve, release the 2068 | `TS2068_IO` 6227-6238 |
| `map_slots(rom_sm, bank_sm)` | `ROM.put`, `BANK.put` | refuse until phase 5 | `MEMBOOT` 5053, `MEMDOCK` 5174 |
| `make_mq()` | `StateMachine(0, TS_IO_DUAL, …)`, `MQ_BUSY`, `active(1)` | `tsbus.MQ()`, status 00h (busy), queues emptied | `ACTIVATE_MQ`, `ZX48_IO` 7193, `ENA_MQ_DUAL` |
| `restart_mq(MQ)` | `active(0)`, 10 ms, `active(1)` | empty both queues | `ZX48_IO` 7302, 7346 |
| `sd_bus(acquire)` | `acquire`: park SM0 on `NULL_SM`, U6 off, SPI0 on GP2-4 (returns `spi, cs`). Release: unmount, CS high, D0-D2 low | `acquire`: SPI0 on GP38/39/32, CS GP37 (returns `spi, cs`). Release: unmount only. The bus keeps running | bodies of `ACTIVATE_SD`, `DEACTIVATE_SD`, `ENA_SD` |
| `led` | `Pin(25, OUT)` | an object with the same `value`/`on`/`off`/`toggle`, writing XL9555 bit 5 (about 100 µs) | `TS2068_IO` 6202 |
| `background(fn, args)` | `_thread.start_new_thread` | runs `fn` on core 0 and returns | `SAVE_LOG` thread 6996 |
| `blink(on, period)` | starts/stops `BLINK_LED` on core 1 | a `machine.Timer` on core 0 toggles `led` | `BLINK_LED` 6335/6353 |
| `drain_tx(MQ)` | the 64-pass `MQX` pull loop | `MQ.exec("pull (noblock)")` until empty, or a new `tsbus` call | `MQ_TO_IDLE`, `CMD_FLUSH`, `FAIL_CMD`, `ZX_FLUSH_TX`, `ZX48_IO` |

### The `tspico_io` changes

- `_mem32` and `_DMA` are forced to `None` when `board.PIO_MQ` is false. `MQX`,
  `RX_DMA`, `RX_RING` and `_RING_SETUP` then take the paths the host tests
  already cover. On v3 the polled RX paths can't overflow: the queue holds
  1,024.
- `STREAM_DMA` gets a v3 version built on `MQ.put_block`, keeping its return
  contract `(why, sent, word)`. LOAD_TS, LOAD_ZX, CMD_SEND, CH_READ, BLKRCV
  and ZX_TPI rely on it. **This needs a `tsbus` change:** `put_block` today
  waits for room in C and can only be left with Ctrl-C. If the Z80 stops
  reading or sends BREAK, it would wait forever. Proposed:
  `put_block(buf, stall_ms)`. It returns the number of bytes queued, and stops
  early when a port-0Fh word arrives or nothing has moved for `stall_ms`.
- The four 64-pass TX flushes become `board.drain_tx(MQ)`, because a v3
  queue can hold more than 64 bytes after an aborted block.
- `tspico_io` imports `TS.board` at module level, so `board.py` and
  `board_v2.py` go into the upgrade UF2's manifest and the two workflow
  staging lines. `src/CLAUDE.md` and `upgrade_hosttest` require that.

### Things that stay as they are

- The protocol code, the pacing loops, `RX_CAPTURE`, the pre-load chain, and
  every SD call site.
- `src/upgrade/` stays v2-only (RP2040), as the plan says. It picks up the
  `board_v2` paths through `tspico_io`.
- `dev_tspico.py` stays identical to `tspico.py`.

## Slots on v3 in phase 4

Phase 5 turns the 16 slots into files. Phase 4 only needs the 2068 to boot
the TS-Pico ROM:

- `start_memory` loads `/rom/TSPICO-23.ROM` from the flash filesystem (copied
  there by the installer, or `pico-serial put`): HOME the first 16 KB, EXROM
  the second. The DOCK is empty.
- `tpi:memboot`, `tpi:memdock`, `tpi:blkrcv` and the ROM/DCK update paths
  answer "not on v3 yet" (Report F) until phase 5.

**The v3 boot order:** `early_init`, load the images, serve, release the
2068. Then the dispatcher starts as on v2.

There is no shadow boot first (decision 2). The cost: a session that crashed
can leave the SCLD's bank registers set, and the next served boot then fails.
Recovery is to power-cycle the 2068.

## Order of work

Each step is its own PR with host tests green. Each is checked on hardware:
a v2.2 board for 4.1 and 4.2, the v3 card from 4.3.

1. **4.1 `board_v2` only.** Move the v2 code into `board.py`/`board_v2.py`
   behind the calls above, and nothing else. The diff is mechanical. The v2.2
   board passes LOAD, SAVE, `tpi:` commands, BLKRCV and ZX48.
2. **4.2 `tspico_io` guards and `drain_tx`.** No change on v2 (still
   checked on the v2.2 board). Add `put_block(buf, stall_ms)` to `tsbus`
   (C, tested on the card).
3. **4.3 `board_v3`.** The v3 manifest freezes the TS modules. CI's
   `build-v3` stages them. `main.py` runs on both. On the card: ROM 2.3
   boots served, then SYNC and `tpi:info`.
4. **4.4 SD on v3.** The dedicated SPI0 pins; `LOAD ""` and SAVE from SD.
5. **4.5 v3 host tests.** A fake `tsbus.MQ` with a deep queue, driven by the
   existing Z80 models (`load_ts`, `cmd_io`, `zx48_io`, `save_ts`), to show
   the pacing works with 1,024 entries.

**Exit (the plan's):** both UF2s build from one tree, and both boards pass
the same command list, apart from the slot commands deferred to phase 5.

## Decisions (2026-10-10)

1. **Board selection at run time**, by whether `import tsbus` succeeds. One
   set of frozen files, and the host tests keep working unchanged.
2. **No shadow boot on v3:** the card serves from the first boot. After a
   crashed session, power-cycle the 2068.
3. **SD on v3 mounts and unmounts per command**, as v2 does. Keeping the card
   mounted comes later, once the card-swap detection (`SD_NOTE_CARD`) has
   been checked.
4. **Slot commands on v3 refuse until phase 5** instead of half-working.
5. **`put_block(buf, stall_ms)` in `tsbus`** is the v3 `STREAM_DMA`: C
   streams whole blocks, and Python never handles single bytes on these
   paths.

## Progress

- **4.1** #239, **4.2** #240, **4.3** #241: merged 2026-10-10. On the card
  after 4.3: ROM 2.3 boots served, `tpi:info`, `CAT` and LOAD from SD work.
  The v3 LED is dimmed (`LED_BRIGHTNESS` in `config.ini`, default 5 %).
- **4.4** passed on the card, 2026-10-10, with no firmware change beyond
  4.3. `src/test/sd_roundtrip.py`: `LOAD "v3t"` (BASIC, SCREEN$, 16K
  CODE, the 16K block in about 1 s), then `SAVE` of all three and `VERIFY`.
  The saves read back off the card match exactly (the SCREEN$ scrolled one
  row by the typing). `tpi:md`, `tpi:cd`, a SAVE into the new folder,
  `tpi:dir`, `tpi:cd ..`: all good. Card pulled: "No SD card" after five
  quick attempts (about 5 s), no hang; put back, the next `tpi:dir` reads it,
  and `LOAD "v3t"` works again. Test TAPs went onto the card over USB with
  `pico-serial.py put --sd`.
- **4.5** (2026-10-10): `src/test/deep_queue_hosttest.py` runs `load_ts`,
  `cmd_io`, `save_ts` and `zx48_io` again on 1024-entry queues, with a
  `tsbus` module present so `tspico_io` takes its v3 paths, and the model
  Z80 driven by the clock (about 30 bytes a ms, as core 1 serves it whatever
  Python is doing). It found one bug: in ZX48 mode `STREAM_QUEUE` returned
  once a block was queued, with up to 1020 bytes unread, so a block the ROM
  skipped (its next `'L'`) or a Z80 that stopped went unheard and wasn't
  flushed. Fixed: in ZX48 mode it listens until four bytes are left, as
  v2's DMA does. Waiting for the tail everywhere was tried and is wrong:
  the ROM's key press after a page would be swallowed as an echo. Skipped
  on v3, as v2-only: the DMA sections, v2's per-byte TX-dry counter, and
  `tpi:blkrcv` (refused until phase 5). ZX48 itself can't run on the card
  until phase 5 gives it the Spectrum ROM's slot.
