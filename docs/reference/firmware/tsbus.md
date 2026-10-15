# tsbus: the v3 card's bus

Source: [`src/tsbus/`](../../../src/tsbus/): `tsbus.c`, `tsbus.pio`,
`usart8251.h`, `usart8251.c`, `modem2050.h`, `modem2050.c`,
`micropython.cmake`.

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
([docs/v3-modem-proposal.md](../../v3-modem-proposal.md)), and speech: the
SP0256-AL2 emulated on core 1 and played by DMA through two PIO2 state
machines to the audio pins ([speech.md](speech.md)). The v2 firmware
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
| `tsbus.c`, the modem | the 8251's ports in `handle_in` and `core1_main`, the UART's two DMA channels; `tsbus.modem`, `tsbus.modem_mode`, `tsbus.modem_line`, `tsbus.modem_poll`, `tsbus.modem_pace`, `tsbus.modem_flow`; `tsbus.esp_relay`, to install Zimodem |
| `tsbus.c`, flash writes | `apb_dma_pause`, `apb_dma_resume`, `__wrap_flash_range_erase`, `__wrap_flash_range_program` |
| `tsbus.c`, speech | the ring, its DMA and timer, `speech_pass` on core 1, ports 17 and 37 in `handle_in` and `core1_main`; `tsbus.speech`, `tsbus.say`, `tsbus.speech_volume`, `tsbus.speaking`, `tsbus.speech_ports`. The chip itself is `sp0256.c` ([speech.md](speech.md)) |
| `usart8251.h`, `usart8251.c` | the 8251 itself, as plain C: mode/command state machine, status, its two rings, pacing |
| `modem2050.h`, `modem2050.c` | between the 8251 and the line: Hayes pass-through, or 2050 mode (pulse dialing, Zimodem's results, DSR, hang-up, XON/XOFF) |
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
- **Nor may the DMA write to APB while it matters.** The 2068's memory
  reads are answered by DMA (`ch_ptr`, `ch_data`), and a DMA write held at
  the bridge holds those channels up with it. Speech first played by DMA
  into the PWM block, 10,000 writes a second whenever speech was on
  (silence too), and the 2068 crashed (board 1, 2026-10-13): five 8K flash
  writes from the REPL locked up a 2068 running a BASIC loop, and a
  `tpi:` command that slept on core 0 (`tpi:modem`'s 1 ms waits in
  `tsbus.modem`, even a bare `time.sleep_ms(2)`) crashed it at once. With
  speech's DMA disabled, or pointed at RAM instead of the PWM, neither did.
  Why a sleep on core 0 holds an APB write up is not known *(open)*. So
  speech now plays through PIO2 (`spk_pwm`, on AHB), and the modem's
  channels, which have to use the UART, are paused around every flash
  erase and program (`__wrap_flash_range_erase`, below). A `tpi:modem 2050`
  loop then ran 419 commands without a fault (it had failed at once).
- **PIO and DMA** are claimed through the SDK. MicroPython's `rp2` refuses
  claimed state machines and frees only what it claimed itself at soft
  reset, so `tsbus` keeps running through Ctrl-D (checked). PIO0 and PIO1
  are full: instruction memory in both (32 of 32), and all four state
  machines in PIO1 (the fourth is `sm_en`, which runs no program). PIO2,
  at GPIO base 16 (GP16-47: /IORD and both audio pins), has `iord_watch`
  and `spk_pwm`.
- **The 2068's power and resets.** The card can't see /RESET or the 2068's
  power, and on USB it stays up while the 2068 is switched off and on. Two
  things followed from that (2026-10-11): the 2068 came up frozen mid-read
  at power-on (white border, black screen) until TS Reset was pressed, and
  with it off the card held a never-ending "read" with /BE and U3 on, into
  an unpowered machine. Core 1 now watches the bus instead. No memory read
  for `IDLE_CYC` means the 2068 has stopped, and the card lets go of the bus.
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
| `iord_watch` | PIO2: waits on /IORD (GP17), input synchroniser bypassed | Raises PIO2 IRQ flag 0 on each falling edge of /IORD and waits for it to rise: core 1's IN interrupt (`PIO2_IRQ_0`). It replaced a GPIO edge interrupt, whose acknowledgement goes through APB. PIO2's GPIO base is 16; the SDK adjusts `wait gpio 17` when it loads the program |
| `spk_pwm` | PIO2, one state machine per audio pin: side-set the pin (GP46, GP30) | PWM for the speech, as the pico-examples `pwm` program: ISR holds the period (`SPK_TOP`), `pull noblock` takes a new level from the FIFO or keeps X, `out x, 16` takes the low half (the DMA's 16-bit writes arrive in both halves), and the pin is high from the count equal to the level down to 0. Three cycles a count: (`SPK_TOP` + 1) × 3 + 3 cycles a period, about 41 kHz |

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
| `IDLE_CYC` | 25,000 (100 µs) | no memory read this long: the 2068 has stopped (a running Z80 reads every few T-states, in HALT too) |
| `POWER_OFF_CYC`, `POWER_ON_CYC` | 250,000 (1 ms), 25,000,000 (100 ms) | /MEMWR, /IORD, /IOWR all low this long: the 2068 is off; and how long after they come back the card goes on holding /RESET |
| `OFF_MASK` | | those three strobes' bits in SIO's input |
| `IO_TIMEOUT_CYC` | 1000 (4 µs) | the IN guard; see `handle_in` |
| `MODEM_UART`, `PIN_MODEM_TX`, `PIN_MODEM_RX`, `MODEM_BAUD` | `uart0`, 44, 45, 115200 | the ESP32-C3's UART0 (its GPIO 20/21) and Zimodem's speed, checked on proto1 2026-10-12. 8N1 |
| `LINE_RX_N`, `LINE_RX_BITS`, `LINE_TX_N` | 16384, 14, 1024 | the line's receive ring (a DMA write ring, so aligned to its size) and its log2; its transmit ring. 16 KB, not 4: after the card's XOFF, Zimodem can still send up to its whole 4 KB serial buffer, so XOFF goes at half full (#301) |
| `U_RX_N`, `U_TX_N` | 1024, 1024 | the 8251's own rings |
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
| `bus_idle` | volatile bool | `core1_main` | no memory read for `IDLE_CYC`; while set, io_snoop's F4h/FFh writes are ignored |
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
| `line_rx`, `line_tx` | uint8[16384] (aligned 16384), uint8[1024] | `ch_mrx` writes `line_rx`, `modem` reads it; `modem` writes `line_tx`, `ch_mtx` reads it | the line's rings: Zimodem's bytes, and what goes to it |
| `u_rx`, `u_tx` | uint8[1024] each | `modem` and `usart` | the 8251's rings: what the 2068 will read, and what it wrote |
| `usart` | `u8251_t` | `tsbus_modem` (init); `core1_main` and `handle_in` | the 8251 (`usart8251.h`) |
| `modem` | `m2050_t` | `tsbus_modem` (init); `core1_main` | the line's side (`modem2050.h`) |
| `modem_mode` | uint8, `M2050_2050` | `tsbus_modem_mode`; `tsbus_modem` | the mode `tsbus.modem(True)` sets up |
| `modem_on` | volatile bool, false | `tsbus_modem`; `handle_in`, `core1_main` | core 1 answers 73h/77h and services the line. Off, those ports are left to the 2068, as before phase 6 |
| `pace_set` | bool, false | `tsbus_modem_pace`; `tsbus_modem` | a pace has been set, so `tsbus.modem(True)` keeps it instead of the 300-baud default |
| `ch_mrx`, `ch_mtx` | int, -1 | `tsbus_modem` (claimed once) | the modem's DMA channels: UART0 → `line_rx`, endless; a run of `line_tx` → UART0 |
| `mrx_off` | uint32 | `core1_main`; `tsbus_modem` (0) | where `ch_mrx` had got to in `line_rx` on the last pass |
| `mtx_inflight` | uint32 | `core1_main`; `tsbus_modem` (0) | how many bytes the run `ch_mtx` is sending holds |
| `modem_ins` | volatile uint32 | `handle_in` | INs from 73h/77h answered |
| `modem_wake`, `modem_touched` | volatile bool | set by `core1_main` (an OUT to 73h/77h: both) and `handle_in` (an IN: `modem_touched`); cleared by `tsbus_modem_poll` and `tsbus_modem` | what core 1 saw since core 0 last asked: a program writing to the 8251, and any use of it |
| `modem_line_up` | volatile bool, false | `tsbus_modem_line`; `core1_main` | Zimodem is running. Until then core 1 starts no `ch_mtx` run (what is queued waits in `line_tx`) and drops what `ch_mrx` brings (the boot banner, or noise from an ESP32 that is off). Kept across `tsbus.modem(True)` |
| `PIN_AUDIO_L`, `PIN_AUDIO_R` | 46, 30 | `spk_sm` | the audio outputs, driven by `spk_pwm` on PIO2, to the filter, the MCP6002 mixer and the jack; both play the same |
| `SPK_RING_BITS`, `SPK_RING_N` | 11, 1024 | | the ring: 1024 16-bit levels, 2 KB, aligned to its size for the DMA's ring mode; 100 ms at 10 kHz |
| `SPK_TOP`, `SPK_MID` | 2047, 1023 | | `spk_pwm`'s period (11 bits: about a 41 kHz carrier at 250 MHz, far above the filter) and silence. It was the PWM block's wrap, 4095 (12 bits, 61 kHz), until speech moved to PIO2 |
| `SPK_AHEAD`, `SPK_PER_PASS` | 992, 4 | `speech_pass` | core 1 fills the ring up to `SPK_AHEAD` ahead of the DMA, at most `SPK_PER_PASS` samples a pass, so a pass stays short (the OUT and dock-write FIFOs fill in about 15-25 µs) |
| `SPK_Q_N` | 1024 | | the allophone queue: about 100 s of speech |
| `spk_ring` | uint16[1024] | written by `speech_pass`; read by the DMA | the levels to play |
| `spk_fill` | uint32 | `speech_pass`; `tsbus_speech` (half a ring ahead) | the ring index core 1 writes next, free-running |
| `spk_chip` | `sp0256_t` | `speech_pass` (core 1); `tsbus_speech` resets it with speech off; `handle_in` and `tsbus_speaking` read its LRQ | the chip |
| `spk_q`, `spk_q_head`, `spk_q_tail` | volatile | head: `tsbus_say` (core 0); tail: `speech_pass` (core 1) | the allophones `tsbus.say` queued, one writer each end |
| `sm_spk_l`, `sm_spk_r` | int, -1 | `tsbus_speech` (claimed once, `spk_sm`); `spk_dma`, `spk_rest` | the `spk_pwm` state machines on PIO2 for GP46 and GP30 |
| `speech_on`, `spk_stop_req` | volatile bool | `tsbus_speech`; `tsbus_say(None)`, cleared by `speech_pass` | core 1 runs `speech_pass`; stop now |
| `spk_scale` | volatile int32 | `tsbus_speech_volume` (35 % until called) | sample × scale >> 15 is added to `SPK_MID` |
| `ch_spk_l`, `ch_spk_r`, `spk_timer` | int, -1 | `tsbus_speech`, claimed once | the two DMA channels and the DMA timer that paces them |
| `spk_allophones`, `spk_samples`, `spk_late` | volatile uint32 | `speech_pass` | allophones loaded, samples made, and passes that found the DMA caught up (a gap of stale levels) |
| `SPK_PORT_OUT`, `SPK_PORT_IN`, `SPK_PQ_N` | 11h (17), 25h (37), 64 | | David's Pico Speech Synth 2068 board's ports, and their queue |
| `spk_ports_on` | volatile bool | `tsbus_speech_ports` | answer ports 17 and 37 (while `speech_on`) |
| `spk_pq`, `spk_pq_head`, `spk_pq_tail` | volatile | both core 1's: head `core1_main` (OUT 17), tail `speech_pass` | the allophones OUT 17 wrote; one core both ends, so no lock |
| `spk_port_outs`, `spk_port_ins` | volatile uint32 | `core1_main`, `handle_in` | OUTs to 17 and INs from 37 answered |

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

1. GPIO base 0 for PIO0 and PIO1.
2. serve at offset 0 (refuses if anything is there): in/out base MD,
   side-set BE_REQ, ISR shifting left with autopush at 18, OSR right; /BE an
   output, low; MD inputs; X loaded with `IMAGE_PREFIX`. Table written, shadow
   mode.
3. io_drive: out base MD.
4. addr_read: side-set the three enables (all high: off), jmp pin /MEMRD,
   `mov status` on PIO1 IRQ flag 2. mem_write: in MD, autopush at 24, RX
   joined. io_snoop: in MD, autopush at 16. `sm_en`: set pins GP8-GP10,
   initialised at PC 0 (PIO1's memory is full; it never runs).
   `iord_watch` on PIO2 (GPIO base 16, so its window holds /IORD and the
   audio pins; /IORD's synchroniser bypassed, bit `PIN_NIORD - 16` of the
   window), its IRQ flag 0 cleared and routed to `PIO2_IRQ_0` (`inte0`).
   PIO0's IRQ flag 1, which addr_read raises at the start of every memory
   read and serve clears, is routed to `PIO0_IRQ_1` (`inte1`). No core
   enables that interrupt; the line only latches its pending bit in core
   1's NVIC, which core 1's idle test reads.
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

While `spk_ports_on` and `speech_on`, 25h (37) is answered: FFh while
speech is busy (allophones in either queue, or the chip's LRQ not ready),
7Fh when it can take one. That's bit 7 as David's board's /LRQ on D7. The
board leaves the other bits undriven, so they read as the 2068's floating
bus, which on the card's own late INs read 7Fh. The board's 74HC138 decodes
A4, A5 and /RD with A7 low, so it also answers 20h-2Fh and 60h-6Fh; the card
answers 25h only.

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

### `speech_pass()`

In RAM. One pass of speech on core 1:
1. **How far ahead core 1 is:** the DMA's read address (`ch_spk_l`), which is
   on the bus fabric like the modem's DMA registers, not behind APB. A lead
   of 0 means the DMA caught up: `spk_late` is counted.
2. **A stop request** (`spk_stop_req`) silences the chip (`sp0256_stop`) and
   drops both queues.
3. **Up to `SPK_PER_PASS` samples, while the lead is under `SPK_AHEAD`:**
   - when an allophone waits (port 17's queue first, then `tsbus.say`'s) and
     the chip's LRQ allows, it is loaded (`sp0256_ald`), counted in
     `spk_allophones`;
   - if anything is queued or being spoken, `sp0256_sample` × `spk_scale` >>
     15 is added to `SPK_MID` and clamped to 0..`SPK_TOP`; otherwise the
     level is `SPK_MID`, with no work;
   - the level goes into `spk_ring`.

The chip's code and tables are in RAM (`SP0256_RAM`, `SP0256_DATA`;
[speech.md](speech.md)), so nothing here reads flash.

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
still be used) and the times of the last memory read seen and of the last
power-off and power-on readings, forever, polling:

- **The bus going idle.** A memory read since the last pass shows as
  `PIO0_IRQ_1` pending in core 1's NVIC (see `bus_start`); core 1 clears it
  and notes the time. None for `IDLE_CYC`: the 2068 is in reset or off.
  This used to sample /MEMRD once a pass, and a tight, regular Z80 loop
  (the ROM waiting for a reply) could alias with a regular pass so that
  every sample saw the same level: 199 false "stopped" in about 150
  `tpi:modem` commands on board 1 (2026-10-13), each releasing MD
  mid-read and ignoring bank writes until the next change, and the 2068
  crashed. With the latch, 3 in 419 commands, all at the power-on *(the
  NVIC latching a pulse a few cycles long is the Cortex-M33's documented
  behaviour; the board shows it working)*. Core 1 executes `EN_OFF` on `sm_en` and `serve_release` on
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
  `line_rx` (its write address) goes onto `modem.lrx_head`, and while the
  line isn't up (`modem_line_up`) straight off again; if `ch_mtx` is
  idle, the run it sent comes off `modem.ltx_tail`; then `m2050_poll` (bytes
  between the line and the 8251, dialing, results, DSR, flow control) and
  `u8251_poll` (pacing, the status bits); then, if `ch_mtx` is idle and
  bytes wait and the line is up, it is started on the next run of
  `line_tx`, up to the ring's end
  (`read_addr`, then `al1_transfer_count_trig`). Only DMA registers, on AHB:
  the UART's are behind APB (#254). Nothing is masked here: the IN handler
  must never wait, and the first version, which masked interrupts around the
  8251 updates, made INs late on the card (a floating bus read as ©, 127,
  and the character lost). `usart8251.h` says what keeps it safe unmasked.
- **Speech**, while `speech_on`: `speech_pass`.
- **I/O writes** (io_snoop): F4h and FFh update the shadow, and the table if
  it changed (for FFh, only bit 7 matters); while `bus_idle` they are
  power-down noise and are dropped (`glitch_writes`). OUTs to 0Eh/0Fh make
  the status 00h (busy, as v2.1's PIO did) and go to `rxq`. While
  `modem_on`, OUTs to 77h go to `u8251_control` and to 73h to
  `u8251_data_out`. While `spk_ports_on` and `speech_on`, an OUT to 11h
  (17) puts its low 6 bits in `spk_pq`, if there is room, and counts
  `spk_port_outs`: an allophone for the chip, as on David's board.
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
   frees only channels it claimed itself), both stopped (`stop_dma`).
3. UART0 initialised again, 115200 8N1 with its DMA requests on, and GPIO
   44/45 given to it. Again each time because a MicroPython soft reset calls
   `uart_deinit` on UART0 whoever set it up.
4. `ch_mrx` restarted at the top of `line_rx` (8-bit, a 16 KB write
   ring, the UART's RX DREQ, an endless count); `ch_mtx` configured to write
   the UART's data register on its TX DREQ, not started.
5. `usart` initialised (`u8251_init`): as at power-up, taking commands,
   mode 4Fh. The pace kept if `modem_pace` set one, else 300 baud.
   `modem_wake` and `modem_touched` cleared; `modem_line_up` kept.
   `modem` initialised (`m2050_init`) in `modem_mode`, on-hook; DSR 1 in
   Hayes mode, 0 in 2050 mode until a call connects.
6. `modem_on` set.

`False`: `modem_on` cleared; 73h/77h are left to the 2068 again; and the two
channels stopped (if claimed), so the UART is free for `tsbus.esp_relay` or
`machine.UART`. Powering the ESP32 is `board_v3.modem_power`'s job, not this
one's.

The 1 ms wait in step 1 sleeps core 0 (`mp_hal_delay_ms`), and while speech
still played into the PWM block that sleep, inside a `tpi:modem` command,
crashed the 2068 (under "How it fits"); it no longer does.

### `stop_dma(ch)`

Stops a channel for good: `EN` cleared through the non-triggering
`al1_ctrl` alias, then `dma_channel_abort`. On the RP2350 an abort alone can
let the channel trigger again (erratum RP2350-E5, in the SDK's
`dma_channel_abort` documentation; MicroPython's `DMA.close` does the same).
Used by `tsbus.modem` and `tsbus.speech` for their channels. It was added
while chasing the crashes above, and on its own it didn't stop them.

### `tsbus.modem_mode(m)`

0 (`M2050_HAYES`): every byte both ways, DSR held at 1, so a program
talks to Zimodem directly; for setting it up (`ATW`, `ATP`, `AT&W`). 1
(`M2050_2050`, the default): a TS2050 to unmodified software
([`modem2050.c`](#modem2050h-modem2050c)). Kept for later `tsbus.modem(True)`
calls; with the modem on, it is set up again in the new mode at once
(on-hook). Anything else is `ValueError`.

### `tsbus.modem_line(on)`

Zimodem is up (core 0 powered the ESP32 and gave it time to boot:
`board_v3.modem_service`) or not (`_modem_off`). Sets `modem_line_up`.

### `tsbus.modem_poll()`

For core 0's idle loop, every pass, so a small int and no allocation: bit 0
an OUT to the 8251 since the last poll (`modem_wake`), bit 1 off-hook (2050
mode, not `M2050_ONHOOK`), bit 2 any IN or OUT since the last poll
(`modem_touched`). Bits 0 and 2 are cleared by the read. 0 while the modem
is off.

### `tsbus.modem_pace(baud)`

A received character becomes RxRDY no sooner than one 10-bit character
time at `baud` after the last (33.3 ms at 300); 0: as soon as the last is
read. `usart.pace` in core cycles; kept across `tsbus.modem(True)`
(`pace_set`). A negative baud is `ValueError`.

### `tsbus.modem_flow(on)`

Hayes mode's flow control (#301): sets `modem.flow_want`, which
`m2050_poll` copies into `flow` on its next pass, so core 1 alone sends
XOFF/XON. On, the card pauses Zimodem with XOFF when the line's ring is
over half full and resumes it with XON below a quarter, as 2050 mode does
while connected. For a program that has set Zimodem up for it: Zimodem 4.0.3
obeys XOFF only with `ATF1` (its serial side) *and* on a connection dialled
with the `X` modifier (`ATDTX"host:port"`; the connection's own flag).
Otherwise XOFF and XON reach the host as data. Every `tsbus.modem(True)`
(`m2050_init` zeroes the struct) turns it off again. Why: PicoTerm's
64-column flood at full speed (`MODEM_BAUD` 0) lost 9,798 bytes
(`m_rx_lost`) with no flow control in Hayes mode. On board 1 (2026-10-15):
with `ATF1` alone the test server received the XOFF/XON; dialled with X and
a 4 KB ring with XOFF at 3/4, 825 bytes were still lost, since Zimodem copies
from the socket up to its 4 KB buffer before it looks for XOFF; with the
16 KB ring and XOFF at half, the flood arrived whole (`m_rx_lost` 0, 29.4 s
in 64 columns).

### Speech

The chip runs on core 1 (`speech_pass`), and two DMA channels play
`spk_ring` into the TX FIFOs of two `spk_pwm` state machines on PIO2, one
per audio pin. A DMA timer paces them at the chip's 10 kHz, so core 0 only
queues allophones. Core 0 sets it all up in `tsbus.speech`, once. Nothing
the DMA writes is behind APB: the PWM block was, and its writes crashed the
2068 (under "How it fits"). Board 2 (USB only,
2026-10-12) spoke two sentences from the REPL: 80,157 samples, exactly
MAME's count for them, with `s_late` 0 ([speech.md](speech.md)).

### `spk_sm(pin, off)`, `spk_rest()`, `spk_dma(ch, sm)`

`tsbus.speech`'s helpers:
- `spk_sm`: claims a PIO2 state machine for `spk_pwm` at `off`, the pin to
  PIO2 and an output, side-set on it, OUT shifting right; loads the period
  (`SPK_TOP`, through `pull` and `out isr, 32`), queues `SPK_MID` and
  starts it. Returns the state machine.
- `spk_rest`: both FIFOs cleared and `SPK_MID` queued: the pins at the
  middle level at once (speech off).
- `spk_dma`: a channel moving 16-bit levels from `spk_ring` (read ring of
  `SPK_RING_BITS`, endless) to the state machine's TX FIFO, paced by
  `spk_timer`'s DREQ. A 16-bit write arrives in both halves of the FIFO
  word; `spk_pwm` takes the low one. The state machine drains the FIFO
  four times faster than the timer fills it, holding each level until the
  next.

### `tsbus.speech(on[, rate])`

Speech on or off. First `speech_on` is cleared and core 1 given a
millisecond to leave its pass; if speech was set up, both channels are
stopped (`stop_dma`) and the pins left at `SPK_MID` (`spk_rest`). Off stops
there. On:
1. `rate` (50-150, % of the chip's speed; `ValueError` otherwise) sets the
   timer: clk_sys × 1 / (250 MHz / (10 kHz × rate / 100)), 25000 at 100 %.
   The chip's pitch moves with its speed, as on the real chip's clock.
2. The two channels and the timer are claimed the first time, `spk_pwm`
   loaded into PIO2 and its two state machines started (`spk_sm`); the
   volume starts at 35 % if `tsbus.speech_volume` hasn't been called.
3. The ring filled with `SPK_MID`, the chip reset
   (`sp0256_init`, with `memset`, on core 0 while core 1 is out), both queues
   emptied, `spk_fill` half a ring ahead (50 ms of silence first).
4. Both channels started together (`dma_start_channel_mask`), then
   `speech_on` set.

Raises "tsbus not started" before `tsbus.start()`, and `OSError` if no DMA
timer is free. `board_v3.speech_start` calls it at boot.

### Flash writes: `apb_dma_pause()`, `apb_dma_resume(paused)`, `__wrap_flash_range_erase`, `__wrap_flash_range_program`

The link wraps the SDK's `flash_range_erase` and `flash_range_program`
(`-Wl,--wrap`, `micropython.cmake`), so MicroPython's flash writes
(`rp2_flash.c`: LittleFS, through `rp2_flash_writeblocks` and
`rp2_flash_ioctl`) call these first, already inside its critical section
(interrupts off). Each one calls `apb_dma_pause`, the real function
(`__real_…`), then `apb_dma_resume`. All four are `__not_in_flash_func`:
the real functions turn execute-in-place off.

- `apb_dma_pause`: for each of `ch_mrx` and `ch_mtx` (the modem's: they
  read and write UART0) that is claimed and enabled, clears `EN` through the non-triggering
  `al1_ctrl` alias, which stops new transfers and keeps the sequence where
  it is; returns the paused channels as a bit mask. If any, it waits 1000
  cycles (4 µs at 250 MHz) so a transfer already issued finishes before the
  flash goes busy.
- `apb_dma_resume`: sets `EN` again on those channels; they carry on.

What it costs: the modem's receive channel stops reading the UART, whose
32-byte FIFO can overflow during a long erase at 115200 baud and lose
bytes *(inferred, not tested)*. The 2068-facing channels (`ch_ptr`,
`ch_data`, `ch_log`) and speech's are never paused: they touch only PIO and
SRAM. Speech's were paused too while they wrote the PWM block; that cured
the flash writes but not the sleeps (under "How it fits").

### `tsbus.say(allophones)`

Queue AL2 allophone numbers (bytes-like; each masked to 0-63) after what is
queued already, until the queue is full; returns how many were queued.
`None` asks core 1 to stop now and drop both queues (`spk_stop_req`), and
returns 0. `OSError` ("speech off") unless `speech_on`.

### `tsbus.speech_volume(pct)`

0-100 (`ValueError` otherwise): `spk_scale = pct × 4 × SPK_MID / 100`. Speech
peaks near 6000 of the chip's ±32764, so 100 % takes peaks to about 73 % of
the swing from `SPK_MID` to either end; 35 % (the default) to about 26 %,
the level of the first tests on board 2. Takes effect from the next sample.

### `tsbus.speech_ports(on)`

Answer ports 17 and 37 (OUT 17 an allophone, IN 37 bit 7 busy) while speech
is on. `board_v3.speech_start` passes `config.ini`'s `SPEECH_PORTS`.

### `tsbus.speaking()`

True while speech is on and something is queued (either queue) or the chip
isn't halted and ready: the end of what was said, for a program that waits.

### `tsbus.esp_relay(first_ms, idle_ms)`

The USB serial port and the ESP32-C3's UART0 joined byte for byte, on core 0,
so a host can talk to the ESP32 ROM's serial loader through the card and
install Zimodem (`tools/zimodem-install.py` runs esptool through it; the web
updater's modem step does the same in the browser). The caller has put the
ESP32 in download mode (`board_v3.esp_boot(True)`), switched the modem off
(`RuntimeError` otherwise) and the REPL's Ctrl-C off (`micropython.kbd_intr(-1)`):
a 03h in the data would interrupt.

- UART0 initialised at 115200 8N1, FIFOs on, its DMA requests off, GPIO
  44/45 given to it. 115200 is the loader's own speed, and the relay doesn't
  follow a change: the host must not ask for one (esptool kept at
  `--baud 115200` never does).
- A loop: while `mp_hal_stdio_poll` says the host has sent something and the
  UART has room, `mp_hal_stdin_rx_chr` into `uart_putc_raw`; then up to 64
  bytes from the UART, out raw with `mp_hal_stdout_tx_strn`;
  `mp_event_handle_nowait` (USB, the soft timers). MicroPython's stdin ring
  leaves the USB endpoint undrained while it is full, so a fast host waits
  rather than losing bytes.
- Returns `(to_esp, from_esp)` once the host has been quiet for `idle_ms`
  after its first byte, or sent nothing for `first_ms`.

On proto1 (2026-10-12) esptool 5.5 wrote the 1,170,544-byte Zimodem image
(677,456 compressed) through it in 60.7 s, the hash verified, and Zimodem
came up with its WiFi settings and phonebook kept: `(691977, 1682)`.

### `tsbus.stats()`

A dict: `home`, `exrom`, `dock` (reads served, by slot), `io_writes`,
`mem_writes`, `dock_writes`, `table_updates`, `ins`, `ins_ours`,
`outs_ours`, `late`, `respond_ns`, `rx_lost`, `hsr`, `ff`, `held`,
`status` (what IN 0Fh returns), `tx` and `rx` (the queue levels),
`idle` (`bus_idle`), `idle_resets`, `glitch_writes`, `power_held` and
`power_resets`. The modem: `m_on`, `m_ins` (INs from 73h/77h), `m_status`
(the status bits but RxRDY), `m_mode`, `m_cmd`, `m_rx` (characters the
2068 read), `m_tx` (written to the line), `m_tx_dropped`, `m_rx_lost`, `m_flow` (Hayes flow control on, `modem.flow`),
`m_xoff` (XOFF sent, not yet XON: `modem.xoff_sent`),
`m_rxq` (bytes waiting, the line's ring and the 8251's), `m_pace_us`,
`m_mode_sel` (`modem_mode`), `m_state` (the 2050 state, `M2050_ONHOOK`
0 … `M2050_HANGUP` 5), `m_dials`, `m_connects`, `m_carrier_lost` and
`m_line_up`.
`m_rx_lost` is the line's ring overflowing (`modem.rx_lost`). Speech: `s_on`,
`s_allophones`, `s_samples`, `s_late` (passes that found the DMA caught up),
`s_queued` (`tsbus.say`'s queue), `s_ports`, `s_port_outs`, `s_port_ins`.

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
with the functions above, `modem`, `modem_mode`, `modem_line`,
`modem_poll`, `modem_pace`, `esp_relay`, `speech`, `say`, `speech_volume`,
`speaking` and `speech_ports` among them.

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

### The modem in Hayes mode, checked on proto1 board 1 (2026-10-12)

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

### 2050 mode with MTERM/T, checked on proto1 board 1 (2026-10-12)

Zimodem joined to WiFi and given phonebook entry 1234 for a test host on
the Mac (in Hayes mode, from MODEMTST: `ATW`, `AT&W`, `ATP`; Zimodem's
first `AT&W` prints an `[E] … remove()` log line, harmless). Then the
unmodified MTERM/T tape from the Timex Sinclair archive, in 2050 mode:
- MTERM's auto-dial pulsed 1234 on DTR; the card sent `ATD1234`, Zimodem
  connected, DSR rose, MTERM qualified it and set RTS (command 27h).
- The host's banner: with no hold after CONNECT, MTERM showed none of it;
  held 2 s, 25 characters were lost, held 3.5 s, 22, though the 2068 read
  all 59 (`m_rx`). MTERM drops what it reads while it redraws its screen
  after connecting, whenever the data starts: the dial-up services waited
  for ENTER (MTERM's manual: "a double ENTER to wake up"), and with a host
  that does, the banner came whole. The 3.5 s hold stays: without it the
  data arrived during MTERM's carrier check and was all lost.
- Echoed typing both ways.
- The host hanging up: Zimodem printed `NO CARRIER` straight after the
  host's `> ` prompt, with no line break before it. The first matcher only
  looked at a line's start and passed it to the screen; matched anywhere
  before a line ending, DSR dropped and MTERM hung up by itself.
- MTERM hanging up: 1.1 s of silence, `+++`, 1.2 s, `ATH`; the host saw
  the line close. (Zimodem passes the `+++` on, as a modem must before it
  knows it was an escape.)
- No late INs, no lost bytes, slowest reply 412 ns.

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
`U8251_C_EH` the command bits, `U8251_XON`/`U8251_XOFF` 11h/13h (used by
`modem2050.c`). `u8251_t` holds: what the caller sets (`pace` in ticks of
`now`, `dsr`, which `modem2050.c` sets); the chip (`expect_mode`, `mode`,
`cmd` less ER and IR, `mask` from the character length, `hold`,
`hold_full`, `overrun`, `status`); the receive ring (`rx_buf`, `rx_size`,
`rx_head` the caller's, `rx_tail` ours, `last_release`); the transmit ring (`tx_buf`, `tx_size`,
`tx_head` ours, `tx_tail` the caller's); and counters (`rx_chars`,
`tx_chars`, `tx_dropped`, `rx_lost`).

### `BARRIER()`, `update_status(u)`

`BARRIER()` is a compiler barrier: the loop and the handler share a core, so
program order is all that's needed. `update_status` sets `status`: TxRDY if
the transmit ring has room (whatever TxEN says, as the chip's status bit);
TxEMPTY if TxEN is off or the ring is empty (`tx_tail` is advanced only once
the line has the bytes); OE from `overrun`; DSR from `dsr`. Not RxRDY.

### `u8251_init(u, rx_buf, rx_size, tx_buf, tx_size)`

Everything zero, the rings given; taking commands, with mode 4Fh (8N1,
x64) and mask FFh. The datasheet leaves a chip's state at power-up
undefined (a mode byte, a sync character or a command). Taking commands
means a program that reset the 8251 before the modem came up carries on
(MTERM, started before the modem was switched on, on proto1), and the
BASIC "Modem" dialer, which never resets it, has its first `OUT 119,31`
taken as the off-hook command it means.

### `u8251_control(u, b)` (OUT 77h)

Expecting a mode byte: an async one (baud factor 01, 10 or 11) is taken,
setting `mask` from the length (5-8 bits); a sync one (00) is ignored, so
the datasheet's reset preamble (00h three times, 40h) ends in "expecting a
mode byte" from any state. Otherwise a command: IR (bit 6) goes back to
expecting a mode byte and clears the command, `hold_full` and `overrun`;
ER (bit 4) clears `overrun`; the rest is kept in `cmd`.

### `u8251_data_out(u, b)` (OUT 73h)

With TxEN and room, `b & mask` into the transmit ring; else counted in
`tx_dropped`.

### `u8251_poll(u, now)`

Every loop pass:
1. If the writer has lapped `rx_tail` (more than `rx_size` waiting), the
   oldest are dropped, counted in `rx_lost`, and OE set.
2. If no character is held, one is waiting, RxE is on, and `pace` has
   passed since the last (or none has been read yet, or `pace` is 0): the
   next one, masked, into `hold`, then `hold_full`.
3. `update_status`.

(Step 1 can't happen on the card: `modem2050.c` moves bytes in only while
there is room.)

### `u8251_status(u)` (IN 77h), `u8251_data_in(u)` (IN 73h)

`status` plus RxRDY if `hold_full` and RxE. `hold`; if `hold_full`, it is
cleared and `rx_chars` counted. Reading with nothing held gives the last
character again, as the chip's data register would.

## `modem2050.h`, `modem2050.c`

What stands between the 8251 and the line, plain C like `usart8251.c`,
driven on the host by
[`src/test/modem2050_hosttest.py`](../../../src/test/modem2050_hosttest.py)
(with `modem2050_shim.c`) with MTERM's own timings. `m2050_poll` runs once a
core 1 pass, never from the IN handler; it moves at most `M2050_BURST` (16)
bytes each way a pass.

### Rings, constants and `m2050_t`

Two rings each side: the line's (`lrx` written by DMA, the caller
advancing `lrx_head`; `ltx` read by DMA, the caller advancing `ltx_tail`)
and the 8251's (this advances `usart`'s `rx_head` and `tx_tail`).
`M2050_HAYES` 0, `M2050_2050` 1; the states `M2050_ONHOOK` 0, `OFFHOOK`,
`DIALING`, `CONNECTED`, `DEAD`, `HANGUP` 5. The times, in ms:

| Name | ms | What |
|---|---|---|
| `M2050_BREAK_MAX_MS` | 200 | a DTR break shorter than this is a dial pulse (MTERM's: 58 ms) |
| `M2050_DIGIT_MS` | 300 | DTR on this long after pulses ends a digit (MTERM: 832 ms between digits) |
| `M2050_NUMBER_MS` | 1500 | ... and this long ends the number (MTERM waits 2.38 s) |
| `M2050_ONHOOK_MS` | 400 | DTR off this long is on-hook |
| `M2050_GUARD_MS` | 1100 | Zimodem's `+++` guard time is over 900 ms |
| `M2050_SETTLE_MS` | 3500 | data held back after CONNECT (above, the MTERM check) |

`m2050_t` holds the mode and `tick_ms`, the line's rings, and 2050 mode's
state: `state`, `dtr` and `dtr_at` (DTR's last level and when it changed),
`pulses`, `number` and `ndigits`, `line` and `nline` (a result line being
read), `match` (characters of NO CARRIER held back), `swallow_lf`,
`connected_at`, `hang_phase`, `hang_at`, `last_tx_at`, `xoff_sent`;
`flow_want` (volatile: core 0's request, `tsbus.modem_flow`) and `flow`
(core 1's copy, which Hayes mode's flow control follows); and
counters `dials`, `connects`, `carrier_lost`, `rx_lost`.

### Strings, `STR`, and flash

`no_carrier`, `s_init` (`ATE0V1X0F1\r`: no echo, word results, a short
CONNECT, XON/XOFF), `s_ath`, `s_plus` and the result words (`r_connect`,
`r_answer`, `r_error`, `r_busy`, `r_dialtone`) are deliberately not `const`:
const data goes to `.rodata` in flash, and core 1 must never read flash,
which stalls while core 0 writes it (#254). As `.data` they are copied to
RAM at start-up. Nothing may become a call to `strlen` or `memcpy` either,
which the compiler makes of simple loops and which are in flash: the first
build called `strlen` (through a veneer) from `put_line`. So `put_line`
takes its length (`STR(s)` gives both), and every copy goes through a
ring's masked index. After a change, check the disassembly of the RAM code
(`core1_main` through `m2050_poll`) for branches out of RAM: only
`core1_main`'s set-up may call flash (`irq_set_*`).

### `ms`, `starts`, `put_line`, `put_byte`, `to_2068`

Ticks in n ms; whether a line begins with a word; n bytes for Zimodem if
all fit (else none), one byte if it fits; a byte into the 8251's receive
ring. `put_line` and `put_byte` note `last_tx_at`, for the guard time.

### `m2050_init(m, mode, tick_ms, lrx, lrx_size, ltx, ltx_size)`

Everything zero, the mode and rings given, on-hook.

### `go_onhook(m, now)`

DTR has been off `M2050_ONHOOK_MS`. From connected: `HANGUP`, the escape
to follow (and an XON first if Zimodem was stopped). From dialing: `ATH`
at once (any character aborts a dial; `ATH` makes sure), then on-hook.
Otherwise on-hook.

### `follow_dtr(m, u, now)`

2050 mode's hook and dial, from DTR in the 8251's command:
- DTR rises: from on-hook, off-hook, with `s_init` sent and the number
  cleared; while off-hook, after a break under `M2050_BREAK_MAX_MS`, one
  pulse.
- DTR off for `M2050_ONHOOK_MS` (not already on-hook or hanging up):
  `go_onhook`.
- Off-hook, DTR on: after `M2050_DIGIT_MS` a digit (1-9 pulses, 10 is 0;
  more are ignored); after `M2050_NUMBER_MS` with digits and none pending,
  `ATD<number>\r` (written a byte at a time; next pass if the ring is
  full), `DIALING`, `dials` counted. The number goes to Zimodem's
  phonebook (`ATP`), which maps it to a host.

### `read_result(m, c, now)`

A byte from Zimodem while not connected. Collects a line; at its end,
while dialing: `CONNECT…` connects (`connects` counted, `connected_at`,
the LF after the CR swallowed); `NO CARRIER`, `NO ANSWER`, `ERROR`, `BUSY`
or `NO DIALTONE`: dead. Nothing reaches the 2068.

### `read_data(m, u, c)`

A byte from Zimodem while connected. The LF after CONNECT's CR is
dropped. `NO CARRIER` is held back as it arrives, anywhere in a line;
followed by CR or LF it is the far end gone (dead, `carrier_lost`), and
not shown. On proto1 Zimodem printed it straight after the host's `> `
prompt, with no line break first. A mismatch passes on what was held
back, and the byte (which may start a new match). So a host that sends
the words NO CARRIER and a line ending ends the call.

### `m2050_poll(m, u, now)`

Every pass:
1. If DMA lapped `lrx_tail`, the lost bytes are counted (`rx_lost`) and
   the 8251's OE set.
2. 2050 mode: `follow_dtr`.
3. Zimodem → the 2068, up to `M2050_BURST`, while the 8251's ring has room
   for a held NO CARRIER and one more: Hayes, straight; connected, through
   `read_data`, but not until `M2050_SETTLE_MS` after CONNECT; otherwise
   `read_result`.
4. The 2068 → Zimodem, up to `M2050_BURST`: in Hayes mode and while
   connected, into `ltx` (waiting while it is full); otherwise taken and
   dropped, so TxRDY stays up.
5. Flow control: first `flow` follows `flow_want`, and turning it off
   in Hayes mode while Zimodem is stopped sends XON, so it isn't left
   stopped. Then XOFF when `lrx` is over half full, XON below a quarter:
   in 2050 mode while connected (`ATF1` is in `s_init`, but Zimodem obeys
   it only if the phonebook entry has X, #302); in Hayes mode only with
   `flow` on, since there Zimodem's settings are the program's
   (`tsbus.modem_flow`).
6. Hanging up: once `ltx` is empty and nothing has been sent for
   `M2050_GUARD_MS`, `+++`; after the guard again, `ATH`, on-hook; if DTR
   is already back on (a redial), off-hook again with `s_init`.
7. DSR: 1 in Hayes mode, else only while connected. It never changes
   while on-hook: MTERM counts DSR changes then as rings, and answers
   after four.

## `micropython.cmake`

The user module: an INTERFACE library `usermod_tsbus` with `tsbus.c`,
`usart8251.c`, `modem2050.c` and `sp0256.c`, the pioasm header
(`pico_generate_pio_header`), and `hardware_dma`, `hardware_pio`,
`hardware_uart`, `hardware_vreg`, `pico_multicore` (not `hardware_pwm`
since speech moved to PIO2), and
the link options `-Wl,--wrap=flash_range_erase` and
`-Wl,--wrap=flash_range_program` (the flash-write wrappers in `tsbus.c`).
`U8251_ON_PICO=1` makes the three plain-C files put core 1's functions in
RAM (and `sp0256.c` its tables, `SP0256_DATA`). The board sets `USER_C_MODULES` to this file.

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
