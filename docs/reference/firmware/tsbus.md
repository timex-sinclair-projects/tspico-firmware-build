# tsbus: the v3 card's bus

Source: [`src/tsbus/`](../../../src/tsbus/): `tsbus.c`, `tsbus.pio`,
`usart8251.h`, `usart8251.c`, `micropython.cmake`.

The v3 card (RP2350B) has no memory chips. It answers every 2068 memory read
it owns from images in its own SRAM, and the TS-Pico ports 0Eh/0Fh from
core 1. `tsbus` is that bus code as a MicroPython C module, built into the
`TSPICO_V3` board ([board-v3.md](board-v3.md)). It is the phase 1 bus test,
`firmware/bringup/bus_card.c` and `bus_card.pio` in the tspico-hardware repo,
moved under MicroPython. Phase 3 of the v3 port plan
(`docs/v3-firmware-port-plan.md` there) built it in three steps: serving the
ROMs, banking and DOCK RAM, the IN/OUT machinery on core 1 and reset control;
the `MQ` object over core 1's queues; and switching images. Phase 6 adds
the TS2050 modem's 8251 at 73h/77h, bridged to the card's ESP32-C3
([docs/v3-modem-proposal.md](../../v3-modem-proposal.md)). The v2 firmware
does not use any of it.

What phase 1 learned, and why the code is shaped this way, is in the
bring-up's `README.md`: the bank shadow, early /BE, the /BE pull-up, the DOCK
writes, the IN handler, and "Long IN strobes". This chapter cites it rather
than repeating it.

## Map

| Piece | What it is |
|---|---|
| `tsbus.pio` | the six PIO programs: `serve`, `io_drive` (PIO0); `addr_read`, `mem_write`, `io_snoop` (PIO1); `iord_watch` (PIO2) |
| `tsbus.c`, constants and state | the image region, the PIO and DMA handles, the switches, counters, the port queues |
| `tsbus.c`, serve's table and patches | `chunk_target`, `write_table`, `set_serving`, `set_delays` |
| `tsbus.c`, start | `claim_sm`, `add_program`, `claim_dma`, `bus_start` |
| `tsbus.c`, core 1 | `handle_in`, `iord_isr`, core 1's vector table and stack, `core1_main`; the `TSBUS_DIAG` measurements |
| `tsbus.c`, the 2068 and the clock | `hold_2068`, `bus_clock` |
| `tsbus.c`, Python | `tsbus.start`, `load`, `serve`, `exrom`, `dock`, `hold`, `reset`, `switch`, `stats`, `diag`, `diag_phase`, `diag_reset`; `HOME`, `EXROM`, `DOCK` |
| `tsbus.c`, the MQ object | `tsbus.MQ`: `put`, `get`, `tx_fifo`, `rx_fifo`, `put_block`, `status`, `exec`, `active` |
| `tsbus.c`, the modem | the 8251's ports in `handle_in` and `core1_main`, the UART's two DMA channels; `tsbus.modem`, `tsbus.modem_pace` |
| `usart8251.h`, `usart8251.c` | the 8251 itself, as plain C: mode/command state machine, status, the two rings, pacing, XON/XOFF |
| `micropython.cmake` | the user-module build, and the `TSBUS_DIAG` switch |

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
  board. Core 1 has its own vector table, with `iord_isr` on `PIO2_IRQ_0`:
  the table the cores start with is core 0's, and MicroPython's handlers in
  it are in flash.
- **Flash writes.** LittleFS writes stop execute-in-place. MicroPython pauses
  the other core only if it is a multicore lockout victim, which core 1 is
  not. So core 1's code is all `__not_in_flash_func`, touches PIO, DMA and
  SIO registers directly rather than through SDK inline helpers (a
  size-optimised build may leave those out of line in flash), and makes no
  calls into flash after its set-up. Checked in the v1.29.0 build: only
  `core1_main`'s set-up calls go through flash veneers. 256 KB of
  LittleFS writes while serving left the read rate unchanged (591 per ms).
- **Flash writes stall the APB bridge.** While core 0 erases or programs
  flash, a read through the APB bridge (IO_BANK0, for one) took up to
  4 µs, against under 1 µs otherwise; PIO and SRAM did not slow down
  (issue [#254](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/254),
  measured 2026-10-11 with the `TSBUS_DIAG` build). An IN gives core 1 about
  600 ns, so nothing on its IN path may touch APB: a stalled access holds
  core 1 off the interrupt and queues the stores after it. The cause is
  inferred, not measured: the ROM's flash routines drive the QMI's
  direct-mode registers, also behind APB. The IN path used to clear a GPIO
  edge interrupt and force U1 and U3 with IO_BANK0 output overrides; it now
  takes a PIO2 interrupt (`iord_watch`) and drives the enables through PIO1's
  spare state machine (`sm_en`), both over AHB. Before that, the 2068 read
  wrong status bytes during flash writes (ZX48 `LOAD "tpi:"` failed with
  "1 NEXT without FOR") and could crash.
- **PIO and DMA** are claimed through the SDK. MicroPython's `rp2` refuses
  claimed state machines and frees only what it claimed itself at soft
  reset, so `tsbus` keeps running through Ctrl-D (checked). PIO0 and PIO1
  are full: instruction memory in both, and all four state machines in PIO1
  (the fourth is `sm_en`, which runs no program). PIO2 has `iord_watch`.
- **The 2068's power and resets.** The card can't see /RESET or the 2068's
  power, and on USB it stays up while the 2068 is switched off and on. Two
  things followed from that (2026-10-11): the 2068 came up frozen mid-read
  at power-on (white border, black screen) until TS Reset was pressed, and
  with it off the card held a never-ending "read" with /BE and U3 on, into
  an unpowered machine. Core 1 now watches the bus instead. /MEMRD still for
  `IDLE_CYC` means the 2068 has stopped, and the card lets go of the bus.
  /MEMWR, /IORD and /IOWR all low together mean it is off, and the card
  holds /RESET until 100 ms after it comes back, as v2's 555 does for a
  board not on USB (see `core1_main`).
- **The clock.** 250 MHz with the core at 1.20 V, set by `start()`, not at
  boot (see `bus_clock`).

## `tsbus.pio`

A copy of `firmware/bringup/bus_card.pio` at tspico-hardware `abdc02c`,
without its PIO2 diagnostic (`iord_len`), plus `iord_watch` (issue #254),
which the bring-up doesn't have: its core 1 runs no flash writes. Phase 1
proved the other programs on a 2068; keep those the same in both copies
while the bring-up is in use. The instruction-by-instruction comments are
in the file.

| Program | Block, pins | What |
|---|---|---|
| `serve` | PIO0 at offset 0: in/out MD (GP0-7), side-set BE_REQ (GP11) | Instructions 0-7 are the chunk table, one jmp per 8K chunk. On each memory read it waits for addr_read's "U2 is on" (PIO0 flag 1), reads A15..A8, jumps through the table on A15..A13 (`out pc, 3`). For HOME (`path_h`) and EXROM (`path_e`) it side-sets /BE straight away; for DOCK (`path_d`) it does not. It asks addr_read for U3 (`irq next set 2`), reads A7..A0, pushes the 32-bit pointer `X << 18 | address << 2 | slot`, pulls the byte from the DMA chain, and drives it onto MD until /MEMRD (GP15) rises. `tail` releases MD and /BE. The labels `entry`, `path_e`, `path_d`, `path_h`, `req`, `tail` are used by `tsbus.c` |
| `io_drive` | PIO0: out MD | Puts the byte core 1 pushes (the reply to IN 0Eh/0Fh) onto MD |
| `addr_read` | PIO1: side-set the three buffer enables (GP8-10), jmp pin /MEMRD | Sequences U2 (A15..A8) and U1 (A7..A0) onto MD around serve's samples, and turns U3 on when serve asks. `hi_hold` and `lo_hold` are patched by `set_delays` |
| `mem_write` | PIO1: in MD | Reads every memory write (address through U2 and U1, the data through U3) for the DOCK RAM. RX FIFO joined (8 deep) |
| `io_snoop` | PIO1: in MD | Reads every I/O write (port and data) for the bank shadow and OUT 0Eh/0Fh |
| `iord_watch` | PIO2: waits on /IORD (GP17), input synchroniser bypassed | Raises PIO2 IRQ flag 0 on each falling edge of /IORD and waits for it to rise: core 1's IN interrupt (`PIO2_IRQ_0`). It replaced a GPIO edge interrupt, whose acknowledgement goes through APB |

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
| `EN_U1`, `EN_U3`, `EN_OFF` | `set pins` 110b, 011b, 111b | the instructions core 1 executes on `sm_en`, over GP8 nAEN_LO, GP9 nAEN_HI, GP10 nDATA_OE (active low): U1 on, U3 on, all off (what PIO1's programs leave between cycles) |
| `IORD_MASK` | | /IORD's bit in SIO's input |
| `IDLE_CYC` | 25,000 (100 µs) | /MEMRD unchanged this long: the 2068 has stopped (a running Z80 reads every few T-states, in HALT too) |
| `POWER_OFF_CYC`, `POWER_ON_CYC` | 250,000 (1 ms), 25,000,000 (100 ms) | /MEMWR, /IORD, /IOWR all low this long: the 2068 is off; and how long after they come back the card goes on holding /RESET |
| `OFF_MASK` | | those three strobes' bits in SIO's input |
| `IO_TIMEOUT_CYC` | 1000 (4 µs) | the IN guard; see `handle_in` |
| `MODEM_UART`, `PIN_MODEM_TX`, `PIN_MODEM_RX`, `MODEM_BAUD` | `uart0`, 44, 45, 115200 | the ESP32-C3's UART0 (its GPIO 20/21) and Zimodem's speed, checked on proto1 2026-10-12. 8N1 |
| `MODEM_RX_N`, `MODEM_RX_BITS`, `MODEM_TX_N` | 4096, 12, 1024 | the modem's receive ring (a DMA write ring, so aligned to its size) and its log2; the transmit ring |
| `CORE1_NVEC` | 16 + `NUM_IRQS` | core 1's vector table length |
| `TSBUS_DIAG` | 0 | 1 builds the measuring in `handle_in` and `core1_main` (see `micropython.cmake`) |
| `DIAG_PHASES`, `DIAG_BUCKETS` | 16, 8 | the phases `diag` keeps, and each histogram's buckets |
| `DIAG_DRIVE_MAX` | 250 (1 µs) | how long the diag build watches MD for the reply |
| `DIAG_APB_PROBE` | 0 | 1 also times an IO_BANK0 read in core 1's loop. Off: that read stalls during flash writes and itself causes late INs |

### State

| Name | Type, initial | Set by, read by | What |
|---|---|---|---|
| `pio_serve`, `pio_addr`, `pio_iord` | `pio0`, `pio1`, `pio2` | | the three blocks |
| `sm_serve`, `sm_iodrv`, `sm_addr`, `sm_write`, `sm_snoop`, `off_addr` | uint | `bus_start` | claimed state machines; addr_read's offset, for `set_delays` |
| `sm_en` | uint | `bus_start`; `handle_in` | PIO1's fourth state machine: never enabled, set pins GP8-GP10. Core 1 writes `EN_*` into its `INSTR` register to drive U1 and U3 for an IN |
| `sm_iord` | uint | `bus_start` | `iord_watch`'s state machine in PIO2 |
| `ch_ptr`, `ch_data`, `ch_log` | int | `bus_start` | the DMA chain's channels |
| `started` | bool, false | `tsbus_start` | makes `start()` a no-op once running, across soft resets |
| `serving` | volatile bool, false | `set_serving` | /BE and U3 requests live; false is shadow mode |
| `exrom_on`, `dock_on` | volatile bool, false | `tsbus_exrom`, `tsbus_dock`; `chunk_target` | whether EXROM- and DOCK-bank chunks are served |
| `dock_rw` | volatile bool, true | `tsbus_dock_writes`; `core1_main` | whether the Z80's writes to the dock are stored: on for a RAM dock, off for a flash one |
| `held_2068` | volatile bool, true | `hold_2068`; `iord_isr`, `core1_main` | core 0's hold. RESET_HOLD is high while this or `power_held` is set, and INs are ignored (nIORD sits low in reset) |
| `power_held` | volatile bool | `core1_main`; `hold_2068`, `iord_isr` | core 1 is holding /RESET for a powered-off or just-powered 2068 |
| `bus_idle` | volatile bool | `core1_main` | /MEMRD has been still for `IDLE_CYC`; while set, io_snoop's F4h/FFh writes are ignored |
| `idle_resets`, `glitch_writes`, `power_resets` | volatile uint32 | `core1_main` | times the bus went idle (and was released); F4h/FFh writes ignored while idle; power-ups held through |
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
| `diag_t`, `diag[DIAG_PHASES]` | all 0 | `handle_in`, `core1_main` (diag build); `tsbus_diag_reset`, `tsbus_diag` | per phase: INs to 0Eh/0Fh; `gone` (/IORD already high at the handler's entry); `missed` (high by the time U3 went on); `min_left` (fewest cycles from entry to the strobe's end); `max_gap` (longest core 1 loop pass); `hist` (entry to strobe end, 64 cycles a bucket); `drive_max`, `drive_never`, `dhist` (cycles from the reply's TX write until MD shows it, 8 a bucket); `pio_rd_max`, `apb_rd_max`, `ram_rd_max` (core 1's slowest read of PIO0, of IO_BANK0 when `DIAG_APB_PROBE` is set, of SRAM). Always built, all zero in a normal build |
| `diag_phase` | volatile uint32, 0 | `tsbus_diag_phase`; core 1 | which `diag` entry the measurements go to |
| `diag_probe` | volatile uint32[256] | `core1_main` (diag build) | the SRAM core 1 reads for `ram_rd_max` |
| `modem_rx`, `modem_tx` | uint8[4096] (aligned 4096), uint8[1024] | `ch_mrx` writes `modem_rx`; `usart8251.c` writes `modem_tx`, `ch_mtx` reads it | the 8251's receive and transmit rings |
| `usart` | `u8251_t` | `tsbus_modem` (init); `core1_main` and `handle_in` | the 8251 (`usart8251.h`) |
| `modem_on` | volatile bool, false | `tsbus_modem`; `handle_in`, `core1_main` | core 1 answers 73h/77h and services the line. Off, those ports are left to the 2068, as before phase 6 |
| `pace_set` | bool, false | `tsbus_modem_pace`; `tsbus_modem` | a pace has been set, so `tsbus.modem(True)` keeps it instead of the 300-baud default |
| `ch_mrx`, `ch_mtx` | int, -1 | `tsbus_modem` (claimed once) | the modem's DMA channels: UART0 → `modem_rx`, endless; a run of `modem_tx` → UART0 |
| `mrx_off` | uint32 | `core1_main`; `tsbus_modem` (0) | where `ch_mrx` had got to in `modem_rx` on the last pass |
| `mtx_inflight` | uint32 | `core1_main`; `tsbus_modem` (0) | how many bytes the run `ch_mtx` is sending holds |
| `modem_ins` | volatile uint32 | `handle_in` | INs from 73h/77h answered |

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

Sets up the three blocks and the DMA chain, and starts six state machines
(`sm_en` is claimed and configured but never started):

1. GPIO base 0 for both blocks.
2. serve at offset 0 (refuses if anything is there): in/out base MD,
   side-set BE_REQ, ISR shifting left with autopush at 18, OSR right; /BE an
   output, low; MD inputs; X loaded with `IMAGE_PREFIX`. Table written, shadow
   mode.
3. io_drive: out base MD.
4. addr_read: side-set the three enables (all high: off), jmp pin /MEMRD,
   `mov status` on PIO1 IRQ flag 2. mem_write: in MD, autopush at 24, RX
   joined. io_snoop: in MD, autopush at 16. `sm_en`: set pins GP8-GP10,
   initialised at PC 0 (PIO1's memory is full; it never runs).
   `iord_watch` on PIO2 (GPIO base 0, /IORD's synchroniser bypassed), its
   IRQ flag 0 cleared and routed to `PIO2_IRQ_0` (`inte0`).
5. `set_delays()`. Input synchronisers bypassed on MD and /MEMRD in PIO0, and
   on those and /IOWR in PIO1.
6. DMA: `ch_ptr` takes serve's pointer (DREQ on serve's RX) and writes it to
   `ch_data`'s read-address trigger, with the ENDLESS count; `ch_data` copies
   that byte into serve's TX FIFO and chains to `ch_log`, which writes the
   pointer into `addr_log` (a 16 KB ring). `ch_ptr` and `ch_data` are high
   priority. The byte is on MD about 124 ns after the strobe (phase 1).

### `handle_in()`

In RAM, inlined into `iord_isr`. An IN is in progress:

1. Turns U1 on by executing `EN_U1` on `sm_en` (PIO1's `INSTR` register,
   over AHB), reads PIO1's `FSTAT` so the store has landed, waits 32 ns,
   reads A7..A0 off MD, and turns U1 off (`EN_OFF`).
2. For 0Eh/0Fh: the reply is `io_status` (0Fh), or the next `txq` byte, or
   00h if it is empty (0Eh). It goes to io_drive, then U3 goes on (`EN_U3`,
   and `FSTAT` read back). `respond_max` keeps the worst time from entry to
   here: 288 ns measured under MicroPython with the old IO_BANK0 overrides
   (about 600 ns are available).
3. Waits for /IORD to rise, then turns U3 off (`EN_OFF`). The guard,
   `IO_TIMEOUT_CYC` on the cycle counter, only keeps U3 from staying on if
   /IORD sticks low: the 2068's SCLD stops the Z80's clock while it updates
   the screen, which stretches some IN cycles to 2.4 µs. The bring-up's first
   2 µs guard was too short for them (tspico-hardware `firmware/bringup/README.md`,
   "Long IN strobes").

While `modem_on`, 73h and 77h are answered the same way, the reply from
`u8251_data_in` or `u8251_status` (decoded from A0-A7 with `port & FBh ==
73h`, A2 choosing). With the modem on, the slowest reply from entry to U3 on
was 412 ns (`respond_ns`, proto1 2026-10-12).

Other ports are left to the 2068; the handler still waits for their strobe
to end.

Nothing here goes through the APB bridge (issue #254, under "How it fits"):
it used to force U1 and U3 with IO_BANK0 output overrides, and the bridge
stalls during flash writes.

In the diag build it also records, for 0Eh/0Fh, whether /IORD was still low
at entry and when U3 went on, the time from entry to the strobe's end, and,
after U3 is on, how long MD took to show the reply (it only watches; the
Z80 sees the same timing).

### `iord_isr()`

In RAM. Core 1's `PIO2_IRQ_0` handler: acknowledges `iord_watch`'s IRQ
flag 0 (a write to PIO2, over AHB), and runs `handle_in()` unless the 2068
is held, by core 0 (`held_2068`) or by core 1's power check (`power_held`).
nIORD sits low in reset; `iord_watch` reacts to edges only, so that is never
taken for INs.

### `core1_main()`

In RAM. Set-up, which may call flash code because core 0 waits in
`tsbus.start()` until it is done:

1. Copies the vector table the core started with (core 0's), puts
   `iord_isr` in `PIO2_IRQ_0`'s slot, and points core 1's VTOR at the copy.
2. Starts the DWT cycle counter.
3. Clears PIO2's IRQ flag 0 and enables `PIO2_IRQ_0` at the top priority on
   core 1's NVIC. Sets `core1_ready`.

Then, with `serve_release` (serve's `mov pindirs, null side 0`, the
instruction after `tail`'s wait, read from the program while flash may
still be used) and the times of /MEMRD's last change and of the last
power-off and power-on readings, forever, polling:

- **The bus going idle.** /MEMRD unchanged for `IDLE_CYC`: the 2068 is in
  reset or off. Core 1 executes `EN_OFF` on `sm_en` and `serve_release` on
  serve, so U1-U3 are off, MD is released and /BE let go. With the 2068 off,
  /MEMRD reads low and serve and addr_read would otherwise sit in a "read"
  driving its data bus. It sets `bus_idle` (cleared at the next change) and
  counts `idle_resets`. The shadow is left alone: the SCLD keeps its
  registers through a reset (`hold_2068`).
- **The 2068's power.** /MEMWR, /IORD and /IOWR all low (`OFF_MASK`) for
  `POWER_OFF_CYC`: it is off, so `power_held` is set and RESET_HOLD driven
  high (`gpio_set`, SIO). Once they have been back for `POWER_ON_CYC`, the
  shadow is cleared (the SCLD powers up with both registers 0) and the table
  rewritten. `power_held` is cleared and `power_resets` counted, and
  RESET_HOLD is released unless core 0 holds (`held_2068`). Without this, a
  2068 switched on under a card on USB came up frozen mid-read until TS
  Reset was pressed.
- **A drop request** (`tx_drop_req`): drops the oldest reply with interrupts
  masked (`cpsid i`), so `iord_isr` can't pop in the middle, then clears the
  request.
- **The modem's line**, while `modem_on`: how far `ch_mrx` has got in
  `modem_rx` (its write address) goes onto `usart.rx_head`; if `ch_mtx` is
  idle, the run it sent comes off `usart.tx_tail`; then `u8251_poll` (pacing,
  overflow, XON/XOFF, the status bits); then, if `ch_mtx` is idle and bytes
  wait, it is started on the next run of `modem_tx`, up to the ring's end
  (`read_addr`, then `al1_transfer_count_trig`). Only DMA registers, on AHB:
  the UART's are behind APB (#254). Nothing is masked here: the IN handler
  must never wait, and the first version, which masked interrupts around the
  8251 updates, made INs late on the card (a floating bus read as ©, 127,
  and the character lost). `usart8251.h` says what keeps it safe unmasked.
- **I/O writes** (io_snoop): F4h and FFh update the shadow, and the table if
  it changed (for FFh, only bit 7 matters); while `bus_idle` they are
  power-down noise and are dropped (`glitch_writes`). OUTs to 0Eh/0Fh make
  the status 00h (busy, as v2.1's PIO did) and go to `rxq`. While
  `modem_on`, OUTs to 77h go to `u8251_control` and to 73h to
  `u8251_data_out`.
- **Memory writes** (mem_write): stored in the DOCK image when the shadow
  maps the chunk to the DOCK, DOCK serving is on, and `dock_rw` is set (a
  RAM dock).
- **Counting** one `addr_log` entry per pass into `served[]`.
- **The diag build** also keeps each pass's length (`max_gap`) and times one
  read of PIO0 and one of SRAM a pass (and of IO_BANK0 with
  `DIAG_APB_PROBE`).

### `hold_2068(hold)`

Core 0's hold (`held_2068`). Drives RESET_HOLD high to hold the 2068 in
reset; on release it stays high while core 1's power check holds
(`power_held`). On release the shadow is reset to what the SCLD powers up
with (both registers 0) and the table rewritten.

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

### `tsbus.modem(on)`

`True`: answer the 8251 at 73h/77h. Every call sets the line up from
scratch:
1. `modem_on` cleared and 1 ms waited, so core 1 is past any pass touching
   `usart` or the channels.
2. The two channels claimed (the first time only; MicroPython's soft reset
   frees only channels it claimed itself), both aborted.
3. UART0 initialised again, 115200 8N1 with its DMA requests on, and GPIO
   44/45 given to it. Again each time because a MicroPython soft reset calls
   `uart_deinit` on UART0 whoever set it up.
4. `ch_mrx` restarted at the top of `modem_rx` (8-bit, a 4096-byte write
   ring, the UART's RX DREQ, an endless count); `ch_mtx` configured to write
   the UART's data register on its TX DREQ, not started.
5. `usart` initialised (`u8251_init`): as at power-up, expecting a mode
   byte. DSR held at 1 (Hayes mode: a program sees carrier and talks to
   Zimodem directly). The pace kept if `modem_pace` set one, else 300 baud.
6. `modem_on` set.

`False`: `modem_on` cleared; 73h/77h are left to the 2068 again. Powering
the ESP32 is `board_v3.modem_power`'s job, not this one's.

### `tsbus.modem_pace(baud)`

A received character becomes RxRDY no sooner than one 10-bit character
time at `baud` after the last (33.3 ms at 300); 0: as soon as the last is
read. `usart.pace` in core cycles; kept across `tsbus.modem(True)`
(`pace_set`). A negative baud is `ValueError`.

### `tsbus.stats()`

A dict: `home`, `exrom`, `dock` (reads served, by slot), `io_writes`,
`mem_writes`, `dock_writes`, `table_updates`, `ins`, `ins_ours`,
`outs_ours`, `late`, `respond_ns`, `rx_lost`, `hsr`, `ff`, `held`,
`status` (what IN 0Fh returns), `tx` and `rx` (the queue levels),
`idle` (`bus_idle`), `idle_resets`, `glitch_writes`, `power_held` and
`power_resets`. The modem: `m_on`, `m_ins` (INs from 73h/77h), `m_status`
(the status bits but RxRDY), `m_mode`, `m_cmd`, `m_rx` (characters the
2068 read), `m_tx` (written to the line), `m_tx_dropped`, `m_rx_lost`,
`m_rxq` (bytes waiting) and `m_pace_us`.

### `tsbus.diag(n)`, `tsbus.diag_phase(n)`, `tsbus.diag_reset()`

The issue-#254 measurements (`diag_t`). `diag_reset()` zeroes every phase
(`min_left` to its maximum); `diag_phase(n)` sends what follows to phase n
(0-15); `diag(n)` returns phase n as `(ins, gone, missed, min_left, max_gap,
(hist...), drive_max, drive_never, (dhist...), pio_rd_max, apb_rd_max,
ram_rd_max)`, cycles at `BUS_CLOCK_HZ`. Always built, because MicroPython's
QSTR scan doesn't see `TSBUS_DIAG`; without it every count stays 0.
[`src/test/st254/stress.py`](../../../src/test/st254/stress.py) uses them.

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

The module (`MP_REGISTER_MODULE`), the slot numbers and the `MQ` type,
with the functions above, `modem` and `modem_pace` among them.

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

### The IN path off APB, checked on proto1 board 1 (2026-10-11, issue #254)

[`src/test/st254/`](../../../src/test/st254/): `st254.asm` reads `IN 15` as
fast as the 2068 can and sends every value that isn't 00h back with
`OUT (0Eh)`; `stress.py` holds the status at 00h and runs ten 8-second
phases (idle, GC, SD mount, read and write, flash read, erase and write,
mixed) on the `TSBUS_DIAG` build.

- **Before** (IO_BANK0 overrides and a GPIO interrupt): no bad reads idle;
  in the first flash-write phase the 2068 read 0Fh (the port, left on MD by
  U1) four times and crashed. Core 1's IO_BANK0 reads took up to 4,032 ns
  during flash writes and 1,376 ns during erases; PIO0 and SRAM reads did
  not slow down.
- **After** (`iord_watch`, `sm_en`): 7.5 million status reads, no bad values,
  no gone, missed or late INs, in every phase; the reply reached MD within
  156 ns at worst (136 ns idle). The 2068 kept running throughout. ZX48
  `LOAD "tpi:v3t.tap"`, which failed before, mounted, loaded and ran.

### Power cycles and resets on USB, checked on proto1 board 1 (2026-10-11)

With the card on USB, switching the 2068 off and on left it frozen at
power-on: a white border, a black screen, and /MEMRD held low. TS Reset
recovered it. With the card holding /RESET through the power-up and
releasing it afterwards, it booted. With the 2068 off, every bus input read
0 V, and the card drove nothing toward it once the bus was released.

With the power hold and the idle release:

- **Power cycles:** 4 of 4 booted clean (`power_resets` 4).
- **Idle and glitches:** the bus went idle and was released 23 times, and 12
  F4h/FFh glitch writes were ignored.
- **TS Reset during Sinistar:** a clean boot, through the copyright screen
  back into the cartridge still in the dock.

### The modem, checked on proto1 board 1 (2026-10-12)

Zimodem 4.0.3 on the ESP32-C3, powered with `board_v3.modem_power(True)`
and `tsbus.modem(True)` from the REPL (step 2 has no command yet), and
`basic/SD/TAP/test/modemtst.bas` on the 2068: the MTERM reset, mode 79
(8N1), command 55, then a terminal loop on IN 119 / IN 115 / OUT 115.
- The status read 133 (DSR, TxEMPTY, TxRDY) idle, what the BASIC dialers
  test for.
- `AT` came back `OK`, and `ATI`'s five lines and Zimodem's banner, 251
  characters at 300 baud, arrived whole: `m_rx_lost` 0, `late` 0, the
  slowest reply 412 ns.
- The first build masked interrupts around the 8251 updates in core 1's
  loop. Characters then came through as © (a late IN reads the floating
  bus, 127) and were lost. Unmasked, none were.

## `usart8251.h`, `usart8251.c`

The TS2050's Intel 8251A as the 2068's software drives it (datasheet
205222-002; [docs/ts2050-software-notes.md](../../ts2050-software-notes.md)).
Plain C with no hardware, so the same file runs on core 1 and in
[`src/test/usart8251_hosttest.py`](../../../src/test/usart8251_hosttest.py),
which compiles it with `usart8251_shim.c` and drives it through `ctypes`
with MTERM's, the BASIC dialers' and the 2068 BBS's sequences.

### Placement and the IN handler

`U8251_FN(f)` is `__not_in_flash_func(f)` on the card: `usart8251.c`
includes `pico.h` when `U8251_ON_PICO` is set (`micropython.cmake`), so
every function core 1 calls is in RAM (checked in the map: `u8251_*` at
2000xxxxh; only `u8251_init`, core 0's, is in flash). On the host it is the
plain name.

The IN handler (`u8251_status`, `u8251_data_in`) interrupts the loop
(`u8251_control`, `u8251_data_out`, `u8251_poll`) on the same core, and
nothing is masked. They share only the received character: the loop writes
`hold`, a compiler barrier, then `hold_full`, and only while it is clear;
the handler clears `hold_full`, only while it is set. RxRDY is never
stored: `u8251_status` adds it from `hold_full` and RxE when 77h is read,
so a status byte can't say a character is waiting after it was read. The
other bits (`status`) are the loop's, at most one pass old.

### Bits and `u8251_t`

`U8251_TXRDY` … `U8251_DSR` are the status bits, `U8251_C_TXEN` …
`U8251_C_EH` the command bits, `U8251_XON`/`U8251_XOFF` 11h/13h.
`u8251_t` holds: what the caller sets (`pace` in ticks of `now`, `dsr`,
`flow`); the chip (`expect_mode`, `mode`, `cmd` less ER and IR, `mask` from
the character length, `hold`, `hold_full`, `overrun`, `status`); the
receive ring (`rx_buf`, `rx_size`, `rx_head` the caller's, `rx_tail` ours,
`last_release`, `xoff_sent`); the transmit ring (`tx_buf`, `tx_size`,
`tx_head` ours, `tx_tail` the caller's); and counters (`rx_chars`,
`tx_chars`, `tx_dropped`, `rx_lost`).

### `BARRIER()`, `update_status(u)`

`BARRIER()` is a compiler barrier: the loop and the handler share a core, so
program order is all that's needed. `update_status` sets `status`: TxRDY if
the transmit ring has room (whatever TxEN says, as the chip's status bit);
TxEMPTY if TxEN is off or the ring is empty (`tx_tail` is advanced only once
the line has the bytes); OE from `overrun`; DSR from `dsr`. Not RxRDY.

### `u8251_init(u, rx_buf, rx_size, tx_buf, tx_size)`

Everything zero, the rings given, expecting a mode byte (a chip fresh from
reset), mask FFh.

### `u8251_control(u, b)` (OUT 77h)

Expecting a mode byte: an async one (baud factor 01, 10 or 11) is taken,
setting `mask` from the length (5-8 bits); a sync one (00) is ignored, so
the datasheet's reset preamble (00h three times, 40h) ends in "expecting a
mode byte" from any state. Otherwise a command: IR (bit 6) goes back to
expecting a mode byte and clears the command, `hold_full` and `overrun`;
ER (bit 4) clears `overrun`; the rest is kept in `cmd`. So the BASIC
dialer's first `OUT 119,31` on a fresh chip is a mode byte, as on the real
8251.

### `u8251_data_out(u, b)` (OUT 73h)

With TxEN and room, `b & mask` into the transmit ring; else counted in
`tx_dropped`.

### `send_flow(u, b)`

XON or XOFF into the transmit ring, behind what the 2068 queued and
whatever TxEN says; false if full.

### `u8251_poll(u, now)`

Every loop pass:
1. If the writer has lapped `rx_tail` (more than `rx_size` waiting), the
   oldest are dropped, counted in `rx_lost`, and OE set.
2. If no character is held, one is waiting, RxE is on, and `pace` has
   passed since the last (or none has been read yet, or `pace` is 0): the
   next one, masked, into `hold`, then `hold_full`.
3. With `flow`: XOFF when more than three quarters of the ring is waiting,
   XON once below a quarter.
4. `update_status`.

### `u8251_status(u)` (IN 77h), `u8251_data_in(u)` (IN 73h)

`status` plus RxRDY if `hold_full` and RxE. `hold`; if `hold_full`, it is
cleared and `rx_chars` counted. Reading with nothing held gives the last
character again, as the chip's data register would.

## `micropython.cmake`

The user module: an INTERFACE library `usermod_tsbus` with `tsbus.c` and
`usart8251.c`, the pioasm header (`pico_generate_pio_header`), and
`hardware_dma`, `hardware_pio`, `hardware_uart`, `hardware_vreg`,
`pico_multicore`. `U8251_ON_PICO=1` makes `usart8251.c` put core 1's
functions in RAM. The board sets `USER_C_MODULES` to this file.

`tsbus.c` includes `tsbus.pio.h` only when `NO_QSTR` is not defined:
MicroPython's QSTR scan preprocesses the file before the header has been
generated, and needs none of its names.

`TSBUS_DIAG=1` in the environment at build time adds `TSBUS_DIAG=1` to the
compile definitions (`add_compile_definitions`), for the issue-#254
diagnostic UF2. Use a separate build directory (`BUILD=build-diag`): CMake
reads the variable only when it configures, and a normal build's objects
would otherwise be reused.

## Where comments and the code disagree

None known.
