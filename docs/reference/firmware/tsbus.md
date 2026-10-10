# tsbus: the v3 card's bus

Source: [`src/tsbus/`](../../../src/tsbus/): `tsbus.c`, `tsbus.pio`,
`micropython.cmake`.

The v3 card (RP2350B) has no memory chips. It answers every 2068 memory read
it owns from images in its own SRAM, and the TS-Pico ports 0Eh/0Fh from
core 1. `tsbus` is that bus code as a MicroPython C module, built into the
`TSPICO_V3` board ([board-v3.md](board-v3.md)). It is the phase 1 bus test,
`firmware/bringup/bus_card.c` and `bus_card.pio` in the tspico-hardware repo,
moved under MicroPython. Phase 3 of the v3 port plan
(`docs/v3-firmware-port-plan.md` there) built it in three steps: serving the
ROMs, banking and DOCK RAM, the IN/OUT machinery on core 1 and reset control;
the `MQ` object over core 1's queues; and switching images. The v2 firmware
does not use any of it.

What phase 1 learned, and why the code is shaped this way, is in the
bring-up's `README.md`: the bank shadow, early /BE, the /BE pull-up, the DOCK
writes, the IN handler, and "Long IN strobes". This chapter cites it rather
than repeating it.

## Map

| Piece | What it is |
|---|---|
| `tsbus.pio` | the five PIO programs: `serve`, `io_drive` (PIO0); `addr_read`, `mem_write`, `io_snoop` (PIO1) |
| `tsbus.c`, constants and state | the image region, the PIO and DMA handles, the switches, counters, the port queues |
| `tsbus.c`, serve's table and patches | `chunk_target`, `write_table`, `set_serving`, `set_delays` |
| `tsbus.c`, start | `claim_sm`, `add_program`, `claim_dma`, `bus_start` |
| `tsbus.c`, core 1 | `handle_in`, `iord_isr`, core 1's vector table and stack, `core1_main` |
| `tsbus.c`, the 2068 and the clock | `hold_2068`, `bus_clock` |
| `tsbus.c`, Python | `tsbus.start`, `load`, `serve`, `exrom`, `dock`, `hold`, `reset`, `switch`, `stats`; `HOME`, `EXROM`, `DOCK` |
| `tsbus.c`, the MQ object | `tsbus.MQ`: `put`, `get`, `tx_fifo`, `rx_fifo`, `put_block`, `status`, `exec`, `active` |
| `micropython.cmake` | the user-module build |

## How it fits under MicroPython

MicroPython does not know about the bus, so `tsbus` and the board keep the
two apart:

- **Memory.** The images live at `TSBUS_IMAGE_REGION` (`0x20040000`), the top
  256 KB of SRAM. The board's linker override ends the GC heap there. The
  main SRAM is word-striped across all eight banks, so the images share
  banks with the interpreter. The DMA has bus priority (`start`), and
  measured contention is negligible: SRAM0 48 contested accesses in 3.8
  million, and none on the PIO FIFOs' bus, in 50 ms on 2026-10-09.
- **Core 1** runs only `core1_main`, from SRAM. `_thread` is off for the
  board. Core 1 has its own vector table, because MicroPython keeps
  `machine.Pin`'s shared handler (in flash) on `IO_IRQ_BANK0` in the table
  the cores start with.
- **Flash writes.** LittleFS writes stop execute-in-place. MicroPython pauses
  the other core only if it is a multicore lockout victim, which core 1 is
  not. So core 1's code is all `__not_in_flash_func`, touches PIO, DMA and
  SIO registers directly rather than through SDK inline helpers (a
  size-optimised build may leave those out of line in flash), and makes no
  calls into flash after its set-up. Checked in the v1.29.0 build: only
  `core1_main`'s three set-up calls go through flash veneers. 256 KB of
  LittleFS writes while serving left the read rate unchanged (591 per ms).
- **PIO and DMA** are claimed through the SDK. MicroPython's `rp2` refuses
  claimed state machines and frees only what it claimed itself at soft
  reset, so `tsbus` keeps running through Ctrl-D (checked). PIO0 and PIO1
  are full.
- **The clock.** 250 MHz with the core at 1.20 V, set by `start()`, not at
  boot (see `bus_clock`).

## `tsbus.pio`

A copy of `firmware/bringup/bus_card.pio` at tspico-hardware `abdc02c`,
without its PIO2 diagnostic (`iord_len`). Phase 1 proved the programs on a
2068; keep the two copies the same while the bring-up is in use. The
instruction-by-instruction comments are in the file.

| Program | Block, pins | What |
|---|---|---|
| `serve` | PIO0 at offset 0: in/out MD (GP0-7), side-set BE_REQ (GP11) | Instructions 0-7 are the chunk table, one jmp per 8K chunk. On each memory read it waits for addr_read's "U2 is on" (PIO0 flag 1), reads A15..A8, jumps through the table on A15..A13 (`out pc, 3`). For HOME (`path_h`) and EXROM (`path_e`) it side-sets /BE straight away; for DOCK (`path_d`) it does not. It asks addr_read for U3 (`irq next set 2`), reads A7..A0, pushes the 32-bit pointer `X << 18 | address << 2 | slot`, pulls the byte from the DMA chain, and drives it onto MD until /MEMRD (GP15) rises. `tail` releases MD and /BE. The labels `entry`, `path_e`, `path_d`, `path_h`, `req`, `tail` are used by `tsbus.c` |
| `io_drive` | PIO0: out MD | Puts the byte core 1 pushes (the reply to IN 0Eh/0Fh) onto MD |
| `addr_read` | PIO1: side-set the three buffer enables (GP8-10), jmp pin /MEMRD | Sequences U2 (A15..A8) and U1 (A7..A0) onto MD around serve's samples, and turns U3 on when serve asks. `hi_hold` and `lo_hold` are patched by `set_delays` |
| `mem_write` | PIO1: in MD | Reads every memory write (address through U2 and U1, the data through U3) for the DOCK RAM. RX FIFO joined (8 deep) |
| `io_snoop` | PIO1: in MD | Reads every I/O write (port and data) for the bank shadow and OUT 0Eh/0Fh |

## `tsbus.c`

### Constants

| Name | Value | What |
|---|---|---|
| `TSBUS_IMAGE_REGION` | `0x20040000` | the images. Must match `__GcHeapEnd` in the board's linker override |
| `IMAGE_PREFIX` | region >> 18 | serve's X: the pointer's top bits |
| `IMAGE_SIZE` | 256 KB | 64K addresses x 4 bytes: slot 0 HOME, 1 EXROM, 2 DOCK, 3 unused |
| `SLOT_HOME`, `SLOT_EXROM`, `SLOT_DOCK` | 0, 1, 2 | the slot in the low two bits of a pointer |
| `BUS_CLOCK_HZ` | 250 000 000 | the system clock the bus timing was proven at |
| `LOG_N` | 4096 | `addr_log`'s length |
| `TXQ_N`, `RXQ_N` | 1024 | the port queues' lengths |
| `SIDE_BITS`, `DELAY_BITS` | `0x1800`, `0x0700` | serve's side-set (opt, value) and delay fields |
| `FORCE_LOW` | | the IO_BANK0 output-override bits that force a pin low |
| `IORD_MASK`, `IORD_EDGE_FALL` | | /IORD's bit in SIO's input, and its falling-edge bit in the interrupt registers |
| `IO_TIMEOUT_CYC` | 1000 (4 µs) | the IN guard; see `handle_in` |
| `CORE1_NVEC` | 16 + `NUM_IRQS` | core 1's vector table length |

### State

| Name | Type, initial | Set by, read by | What |
|---|---|---|---|
| `pio_serve`, `pio_addr` | `pio0`, `pio1` | | the two blocks |
| `sm_serve`, `sm_iodrv`, `sm_addr`, `sm_write`, `sm_snoop`, `off_addr` | uint | `bus_start` | claimed state machines; addr_read's offset, for `set_delays` |
| `ch_ptr`, `ch_data`, `ch_log` | int | `bus_start` | the DMA chain's channels |
| `started` | bool, false | `tsbus_start` | makes `start()` a no-op once running, across soft resets |
| `serving` | volatile bool, false | `set_serving` | /BE and U3 requests live; false is shadow mode |
| `exrom_on`, `dock_on` | volatile bool, false | `tsbus_exrom`, `tsbus_dock`; `chunk_target` | whether EXROM- and DOCK-bank chunks are served |
| `dock_rw` | volatile bool, true | `tsbus_dock_writes`; `core1_main` | whether the Z80's writes to the dock are stored: on for a RAM dock, off for a flash one |
| `held_2068` | volatile bool, true | `hold_2068`; `iord_isr` | INs are ignored while held (nIORD sits low in reset) |
| `core1_ready` | volatile bool | `core1_main`; `tsbus_start` | core 1's set-up is done |
| `d_hi`, `d_lo`, `hold_hi`, `hold_lo` | 3, 3, 5, 9 | constants | serve's two waits and addr_read's two hold loops, in 4 ns PIO cycles: phase 1's settings |
| `addr_log` | uint32[4096], 16 KB aligned | written by `ch_log` (a DMA ring) | every pointer served, newest at the channel's write address |
| `ring_seen` | uint32 | `core1_main` | how far core 1 has counted `addr_log` |
| `sh_hsr`, `sh_ff` | volatile uint8 | `core1_main` (from `io_snoop`), `hold_2068` | the shadow of ports F4h (HSR) and FFh |
| `io_writes`, `mem_writes`, `dock_writes`, `table_updates`, `served[3]` | volatile uint32 | core 1 | counters for `stats()` |
| `txq`, `txq_head`, `txq_tail` | 1 KB ring | head: core 0 (`MQ.put`, `put_block`); tail: core 1 | replies to IN 0Eh; empty reads 00h |
| `rxq`, `rxq_head`, `rxq_tail`, `rxq_lost` | 1 KB ring of uint16 | head: core 1; tail: core 0 (`MQ.get`) | OUTs to 0Eh/0Fh, port 0Fh as `0x100 \| data`; `rxq_lost` counts drops when full |
| `io_status` | volatile uint8, FFh | core 1 (00h on each OUT); core 0 (`MQ.status`, `MQ.exec`) | what IN 0Fh returns: v2's Y register |
| `tx_drop_req` | volatile bool | set by core 0 (`MQ.exec("pull (noblock)")`), cleared by core 1 | asks core 1 to drop the oldest reply. Only core 1 advances `txq_tail`, because its IN handler pops it |
| `io_ins`, `io_in_ours`, `io_outs_ours`, `io_in_late`, `respond_max` | volatile uint32 | `handle_in`, `core1_main` | IN and OUT counts; INs past the guard; worst cycles from the handler's entry to U3 on |
| `core1_vectors` | uint32[`CORE1_NVEC`], 512-byte aligned | `core1_main` | core 1's vector table |
| `core1_stack` | 4 KB | `multicore_launch_core1_with_stack` | core 1's stack (MicroPython's layout has no core 1 stack: scratch X is 0 bytes) |

### `chunk_target(chunk, hsr, ff)`

In RAM. The serve address for one 8K chunk: if the HSR bit for the chunk is
set, the chunk is banked out, to the EXROM if FFh bit 7 is set and the EXROM
is served (`path_e`), else to the DOCK if served (`path_d`), else not ours
(`tail`). Unbanked chunks 0-1 are HOME (`path_h`); 2-7 are RAM (`tail`).

### `write_table()`

In RAM. Writes the eight chunk-table instructions into PIO0 from the shadow.
serve is at offset 0, so an unconditional jmp encodes as just its target.
Called by core 1 when F4h or FFh changes (an I/O write lasts over a
microsecond, so the table is current before the next read), and by
`exrom`, `dock` and `hold_2068` on core 0. Both cores compute the same
entries, so a race between them is harmless.

### `set_serving(on)`

Patches serve: with `on`, `path_e` and `path_h` side-set /BE and `req` asks
for U3; without, the side-sets are dropped and `req` is a nop with the same
delay (`d_lo`). Shadow mode: the card follows every read, logs it, and never
drives the 2068.

### `set_delays()`

Writes `d_hi` into `entry`'s delay, and `hold_hi`, `hold_lo` into addr_read's
two hold loops. `d_lo` goes in through `set_serving`.

### `claim_sm(pio)`, `add_program(pio, prog)`, `claim_dma()`

Claim a state machine, add a program, claim a DMA channel, or raise `OSError`
naming what was missing. The SDK's own calls panic instead, which would hang
the card.

### `bus_start()`

Sets up both blocks and the DMA chain as phase 1 did, and starts the five
state machines:

1. GPIO base 0 for both blocks.
2. serve at offset 0 (refuses if anything is there): in/out base MD,
   side-set BE_REQ, ISR shifting left with autopush at 18, OSR right; /BE an
   output, low; MD inputs; X loaded with `IMAGE_PREFIX`. Table written, shadow
   mode.
3. io_drive: out base MD.
4. addr_read: side-set the three enables (all high: off), jmp pin /MEMRD,
   `mov status` on PIO1 IRQ flag 2. mem_write: in MD, autopush at 24, RX
   joined. io_snoop: in MD, autopush at 16.
5. `set_delays()`. Input synchronisers bypassed on MD and /MEMRD in PIO0, and
   on those and /IOWR in PIO1.
6. DMA: `ch_ptr` takes serve's pointer (DREQ on serve's RX) and writes it to
   `ch_data`'s read-address trigger, with the ENDLESS count; `ch_data` copies
   that byte into serve's TX FIFO and chains to `ch_log`, which writes the
   pointer into `addr_log` (a 16 KB ring). `ch_ptr` and `ch_data` are high
   priority. The byte is on MD about 124 ns after the strobe (phase 1).

### `handle_in()`

In RAM, inlined into `iord_isr`. An IN is in progress:

1. Forces U1 on with a GPIO override (which works on a PIO-owned pin), waits
   32 ns, reads A7..A0 off MD, releases U1.
2. For 0Eh/0Fh: the reply is `io_status` (0Fh), or the next `txq` byte, or
   00h if it is empty (0Eh). It goes to io_drive, then U3 is forced on.
   `respond_max` keeps the worst time from entry to here: 288 ns measured
   under MicroPython (about 600 ns are available).
3. Waits for /IORD to rise, then releases U3. The guard,
   `IO_TIMEOUT_CYC` on the cycle counter, only keeps U3 from staying on if
   /IORD sticks low: the 2068's SCLD stops the Z80's clock while it updates
   the screen, which stretches some IN cycles to 2.4 µs. The bring-up's first
   2 µs guard was too short for them (tspico-hardware `firmware/bringup/README.md`,
   "Long IN strobes").

Other ports are left to the 2068; the handler still waits for their strobe
to end.

### `iord_isr()`

In RAM. Core 1's `IO_IRQ_BANK0` handler: clears /IORD's edge, and runs
`handle_in()` unless the 2068 is held (nIORD sits low in reset; edges only,
so that is never taken for INs).

### `core1_main()`

In RAM. Set-up, which may call flash code because core 0 waits in
`tsbus.start()` until it is done:

1. Copies the vector table the core started with (core 0's), puts
   `iord_isr` in `IO_IRQ_BANK0`'s slot, and points core 1's VTOR at the copy.
2. Starts the DWT cycle counter.
3. Enables /IORD's falling edge for this core, `IO_IRQ_BANK0` at the top
   priority on core 1's NVIC. Sets `core1_ready`.

Then forever, polling:

- **A drop request** (`tx_drop_req`): drops the oldest reply with interrupts
  masked (`cpsid i`), so `iord_isr` can't pop in the middle, then clears the
  request.
- **I/O writes** (io_snoop): F4h and FFh update the shadow, and the table if
  it changed (for FFh, only bit 7 matters). OUTs to 0Eh/0Fh make the status
  00h (busy, as v2.1's PIO did) and go to `rxq`.
- **Memory writes** (mem_write): stored in the DOCK image when the shadow
  maps the chunk to the DOCK, DOCK serving is on, and `dock_rw` is set (a
  RAM dock).
- **Counting** one `addr_log` entry per pass into `served[]`.

### `hold_2068(hold)`

Drives RESET_HOLD: high holds the 2068 in reset, low releases it. On release,
the shadow is reset to what the SCLD powers up with (both registers 0) and
the table rewritten.

Beware: the SCLD keeps its bank registers through a Z80 reset. A boot that
crashes can leave them set (FFh = FFh after one crash), and the next served
boot then goes wrong too. A power cycle clears them; phase 1 and this module
both met it. A boot from the 2068's own ROM first (shadow mode) is the safe
order after any trouble.

### `bus_clock()`

Raises the system clock to 250 MHz if it is not there: the regulator to
1.20 V, 2 ms, the flash divider for 250 MHz (`rp2_flash_set_timing_for_freq`,
MicroPython's, in RAM; with the board's 84 MHz limit, 3), then
`set_sys_clock_khz`. The order `machine.freq()` uses. `clk_peri` and USB run
from the USB PLL and do not change. The board boots at 150 MHz because the
SDK sets the boot clock before MicroPython sets the flash divider
([board-v3.md](board-v3.md)). If Python later calls `machine.freq()`, the
bus timing is gone; nothing guards against it yet.

### `tsbus.start()`

Once (a no-op afterwards, including after a soft reset): checks the GC heap
ends at or below the image region, raises the clock, fills the images with
FFh, gives the DMA bus priority over the cores, holds the 2068, runs
`bus_start()`, launches core 1 on its own stack and waits up to 100 ms for
`core1_ready`. Raises `OSError` if a state machine, program space or DMA
channel is taken, `RuntimeError` otherwise. The 2068 stays held, in shadow
mode.

### `image_buffer(data, buf)`, `load_slot(slot, buf)`

`image_buffer` gets a bytes-like object's buffer and checks it is 1 to 65536
bytes (`ValueError` otherwise). `load_slot` copies it into a slot, repeated to
fill the slot's 64 KB: a 16 KB HOME ROM or an 8 KB EXROM is mirrored as phase
1 did. The copy is byte by byte into every fourth byte of the region, about
1 ms.

### `slot_range(slot_in, off_in, len, slot, off)`

For `read` and `load_at`: the slot (0–2) and the offset (0 if not given),
checked so that `offset + len` stays inside the slot's 64 KB and `len` isn't
0 (`ValueError` otherwise).

### `tsbus.read(slot, buf[, offset])`

Copies `len(buf)` bytes of the slot's image, from `offset`, out into `buf`,
a writable buffer: every fourth byte of the region, about 0.5 ms for 32 KB.
For the DOCK with the Z80's writes in it, to save a RAM dock before it's
switched away. Core 1 may still be writing as it copies. `board_v3` reads it
in 32 KB halves, because the heap has no 64 KB to spare once the firmware
runs.

### `tsbus.load_at(slot, offset, data)`

Copies `data` into the slot at `offset`, once. `load` repeats a short image
to fill 64 KB; this doesn't. For the DOCK in two 32 KB halves. Takes effect
at once, as `load`: if the 2068 is running, turn the DOCK off for the copy
(`tsbus.dock(False)`), as `switch` does.

### `tsbus.load(slot, data)`

`load_slot` into slot 0 (`HOME`), 1 (`EXROM`) or 2 (`DOCK`). Takes effect at
once with nothing held or gated, so load what the 2068 runs only while it is
held; `switch` does that for you.

### `tsbus.serve(on)`

`set_serving(on)`. Only while the 2068 is held: raises `RuntimeError`
otherwise.

### `tsbus.exrom(on)`, `tsbus.dock(on)`

Serve the chunks the bank registers map to the EXROM (with /BE) or the DOCK
(no /BE; writes stored if `dock_writes` is on), and rewrite the table.

### `tsbus.dock_writes(on)`

`dock_rw`. On, core 1 stores the Z80's writes to dock-mapped chunks in the
DOCK image (a RAM dock, MEM 1). Off, it ignores them (a flash dock, MEM 2), as
v2's flash chip ignores them. On at start. `board_v3` sets it with every dock
it loads ([board.md](board.md#board_v3py)). Checked on proto1: a POKE into a
flash dock read back unchanged, and into a RAM dock it read back the new
value.

### `tsbus.hold(on)`

`hold_2068(on)`.

### `RESET_MS`, `tsbus.reset()`

200 ms, phase 1's reset pulse. `reset()` holds the 2068 that long and
releases it; the shadow starts again from the SCLD's power-up state
(`hold_2068`). The SCLD's own registers are not reset (see `hold_2068`).

### `tsbus.switch(home=None, exrom=None, dock=None)`

Replaces the images given (keyword arguments, bytes-like). Every buffer is
checked before anything changes.

- **A HOME or EXROM change, with the 2068 running:** hold it, load every image
  given, release it `RESET_MS` after the hold began (`mp_event_handle_nowait`
  while waiting). The 2068 starts cleanly in the new ROM: a ROM changed under a
  running Z80 would run a mix of the two. A 32 KB TS-Pico ROM is two
  arguments: `home=m[:16384], exrom=m[16384:]` with `m` a `memoryview`. With
  the 2068 held, the images are loaded and it stays held.
- **A DOCK change on its own:** live, as v2's `tpi:memdock`. DOCK serving is
  turned off (`dock_on`, table rewritten) for the copy, so a DOCK read during
  it sees an empty dock rather than half the new image, then restored. The
  2068 keeps running and is not reset.

What phase 5's slot files and `tpi:memboot`/`tpi:memdock` will call.

### `tsbus.stats()`

A dict: `home`, `exrom`, `dock` (reads served, by slot), `io_writes`,
`mem_writes`, `dock_writes`, `table_updates`, `ins`, `ins_ours`,
`outs_ours`, `late`, `respond_ns`, `rx_lost`, `hsr`, `ff`, `held`,
`status` (what IN 0Fh returns), `tx` and `rx` (the queue levels).

### `store(d, k, v)`

Puts one counter in the dict.

### The MQ object: `tsbus.MQ()`

v2's `MQ`, an `rp2.StateMachine` running `TS_IO_DUAL`
([pio.md](pio.md)), rebuilt over core 1's queues and status byte so the
protocol code can carry over (phase 4 puts it behind the board layer). One
object (`tsbus_mq_obj`, read-only); every call to `tsbus.MQ()` returns it,
after `start()`. The differences from v2:

- The queues hold 1,024 entries, not 4, and `tx_fifo()` and `rx_fifo()`
  report their real levels. v2 code that paces itself on a full 4-deep FIFO
  (`TX_ROOM`, `CMD_PUT`) has to be checked in phase 4.
- `put()` and `get()` block like `StateMachine`'s, but run
  `mp_event_handle_nowait()` while they wait, so Ctrl-C interrupts them. It
  doesn't sleep, so there is no added latency.
- `exec()` understands only the instructions `MQX` sends.
- `active()` does nothing: the bus pins are dedicated on v3, so nothing has
  to stop for SD.

| Method | What |
|---|---|
| `put(value)` | Queues a reply for IN 0Eh (low 8 bits); waits while the queue is full. Publishes the byte before advancing `txq_head` (`__dmb`) |
| `get()` | The next OUT as a 9-bit word: `0x100 \| data` for port 0Fh, `data` for 0Eh. Waits while the queue is empty |
| `tx_fifo()`, `rx_fifo()` | the queue levels |
| `put_block(buf[, wait_ms])` | Queues a block as the Z80 reads it and returns how many bytes it queued. For LOAD and BLKRCV blocks, which v2 sends by DMA because Python can't keep a 4-deep FIFO fed. Without `wait_ms`: waits for room until the whole block is queued (Ctrl-C still works). With `wait_ms` ≥ 0: queues what fits, copying straight into the ring with one `__dmb` per run, waits up to `wait_ms` without progress for more room, and returns early when an OUT is waiting in RX, so the caller can see a BREAK or an echo. `wait_ms` 0 queues what fits now and returns. `tspico_io.STREAM_QUEUE` uses both forms ([tspico_io.md](tspico_io.md#the-v3-card)) |
| `status(value)` | Sets what IN 0Fh returns. An OUT to 0Eh/0Fh still makes it 00h on its own (auto-busy) |
| `exec(instr)` | Spaces ignored. `mov(y,invert(null))` sets FFh; `set(y,N)` sets N; `mov(y,invert(y))` inverts it (so `MQ_STATUS`'s pairs give F7h and FBh); `pull(noblock)` drops the oldest reply through core 1 (`drop_oldest`, which waits for it); `mov(osr,null)` does nothing (there is no OSR). Anything else raises `ValueError` |
| `active([value])` | Returns True |

Helpers: `tsbus_mq_make_new` (no arguments; `RuntimeError` before `start()`),
`tx_level`, `rx_level`, `tx_push` (the waiting push `put` and `put_block`
share), `drop_oldest`, `tsbus_mq_type`, `tsbus_mq_locals_table`.

Checked on proto1 board 1 (2026-10-09), the exit test of phase 3. A Python
echo on the card (`get`, `put`, then `exec("mov(y, invert(null))")`, the
`MQX` string `MQ_STATUS("idle")` uses) answered a BASIC loop that sent
0-255 with `OUT 14`, waited for 255 on `IN 15` and read `IN 14` back:
`Errors: 0`. 256 OUTs, 512 INs (each byte read after one status poll), none
late, none lost, worst response 324 ns. `exec`'s status values were checked
at the REPL: F7h, FBh, FFh and 00h, as on v2.

### Switching, checked on proto1 board 1 (2026-10-10)

- **Live DOCK switch.** The DOCK image was A5h throughout, and `OUT 244,16:
  PRINT PEEK 32768: OUT 244,0` printed 165. Then `switch(dock=b"\x5a")`, and
  the same line printed 90. The 2068 was not reset: the earlier line stayed
  on screen.
- **ROM switch.** `switch(home=…, exrom=…)` from the genuine set to TS-Pico
  ROM 2.3 took 200 ms. The 2068 booted the TS-Pico ROM's screen, with
  2,314 EXROM reads, the same as phase 1's ROM 2.3 boots. Switching back
  gave the genuine screen (1,988 EXROM reads). Typing worked in both.
- **Held.** A switch with the 2068 held left it held, with no reads. An
  empty buffer was refused before anything was loaded.

### `tsbus_module`, `HOME`, `EXROM`, `DOCK`, `MQ`

The module (`MP_REGISTER_MODULE`), the slot numbers and the `MQ` type.

### Checked on proto1 board 1 (2026-10-09, genuine 2068 ROMs)

The sequence: `start()`, `load` HOME (with the copyright line marked, as
phase 1 did) and EXROM, `exrom(True)`, `dock(True)`; a shadow boot
(`hold(False)`); then `hold(True)`, `serve(True)`, `hold(False)`. Results:

- Each boot took 1,988 EXROM reads and 12 DOCK reads, the same as phase 1.
  The 2068 showed the card's marker in the copyright line, and typing
  worked.
- A BASIC DOCK test wrote 256 bytes through chunk 4 and read them back with
  0 errors (`dock_writes` 256).
- Serving went on through a soft reset and 256 KB of LittleFS writes.
- No IN timed out.

## `micropython.cmake`

The user module: an INTERFACE library `usermod_tsbus` with `tsbus.c`, the
pioasm header (`pico_generate_pio_header`), and `hardware_dma`,
`hardware_pio`, `hardware_vreg`, `pico_multicore`. The board sets
`USER_C_MODULES` to this file.

`tsbus.c` includes `tsbus.pio.h` only when `NO_QSTR` is not defined:
MicroPython's QSTR scan preprocesses the file before the header has been
generated, and needs none of its names.

## Where comments and the code disagree

None known.
