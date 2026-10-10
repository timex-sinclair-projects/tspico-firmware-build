# Flow: power-on to the first prompt

Both machines start together when the 2068 is switched on: the Pico is
powered from the 2068's bus. They come up independently and meet at the
first transaction: the 2068 runs its ROM from the Pico's flash as soon as
the Pico's bank state machines answer, and the first time BASIC talks to
the Pico (a LOAD, a `tpi:` command) the Pico must already be waiting with
a pre-load byte in its FIFO. This flow follows each side to that point.
Each step links the entry that explains it.

Notation: **TX** and **RX** are the bus state machine's FIFOs (as the Pico
sees them: TX is what the Z80 will read); **Y** is the status the Z80
reads on port 0Fh (`FF` READY + IDLE, `00` BUSY).

## The Pico

| # | Where | What happens | TX / RX / Y | What can go wrong |
|---|---|---|---|---|
| 1 | MicroPython | `_boot.py` (frozen) mounts the LittleFS flash filesystem; `/main.py` runs | — | a missing `/main.py`: MicroPython stays at the REPL and the 2068 sees no ROM (the bank machines never start) |
| 2 | `main.py` | `import TS.tspico`: the module's top level — constants, globals, the PIO programs assembled, the build stamp printed ([../firmware/tspico-state.md](../firmware/tspico-state.md)) | no state machines yet | an `ImportError` here (a `/TS/` folder on the flash shadowing the frozen package) stops the boot ([../firmware/boot.md](../firmware/boot.md#the-dev-overrides)) |
| 3 | `main.py` | `_telemetry()` reads `TELEMETRY` from `/config.ini` | | |
| 4 | `main.py` | the dev override: `/dev_tspico.py`/`.mpy` if present, else the frozen `TS2068_IO` | | a stale `.mpy` → `ValueError` → the frozen module is used |
| 5 | `main.py` | `board.early_init()` ([../firmware/board.md](../firmware/board.md#early_init)): the seven pins to idle (U6 off, GPIO 12 = 1; the flash and SRAM disabled; /BE inactive), then `machine.freq(270_000_000)` | — | |
| 6 | `main.py` | `TS2068_IO()` | | an exception from here on is logged to `/activity.log` and ends `main.py` |
| 7 | `TS2068_IO` | `LOAD_CONFIG()`: `config.ini` read, defaults filled, the one-shot boot slot taken ([../firmware/tspico-dispatch.md](../firmware/tspico-dispatch.md#load_config)); `TSP = PICO_STATUS(...)`; the log rotated at 64 000 bytes | | a corrupt `config.ini`: defaults, logged |
| 8 | `TS2068_IO` | `board.start_memory`: **ROM** (`set_ctrl`, SM 4) and **BANK** (`sel_bank`, SM 5) started at 150 MHz and given `ROM_SM` and `bank_sm` ([../firmware/pio.md](../firmware/pio.md), [../firmware/board.md](../firmware/board.md)) | | **from here the 2068 has a ROM**: the Pico now answers its memory cycles for the ROM and DOCK areas from the chosen slots |
| 9 | `TS2068_IO` | `/TMP` removed and made again; `SA_funct` built; `EXT_SA_FUNCT` from `/dev_extcmd.py` or the frozen `TS.extcmd` | | |
| 10 | `TS2068_IO`, core 1 | `BLINK_LED` on core 1 (`board.background`) blinks the LED while the card is looked for; v2 only (`board.HAS_CORE1`), the v3 card has no boot blink ([../firmware/tspico-bus.md](../firmware/tspico-bus.md#blink_ledpause)) | | |
| 11 | `ACTIVATE_SD(tries=5)` | `MQ` parked on `NULL_SM`, U6 off, the card mounted (up to five tries, at most 6 s); the first card is noted (`SD_NOTE_CARD`) and set up (`SD_REVALIDATE`: `/TAP` made if missing, the folder listed) ([../firmware/tspico-bus.md](../firmware/tspico-bus.md#activate_sdtriesnone)) | no bus program: the Z80 cannot reach the Pico yet | no card, or a wedged one: `TSP.sd_present = False`, logged, and the boot goes on without a card |
| 12 | `TS2068_IO` | `dead = True`; wait for `BLINK_LED` to stop | | |
| 13 | `DEACTIVATE_SD`, `ACTIVATE_MQ` | `/sd` unmounted, CS high, GPIO 2–4 clamped low; `TS_IO_DUAL` started on SM 0 at 30 MHz, Y set BUSY ([../firmware/tspico-bus.md](../firmware/tspico-bus.md#activate_mq)) | TX [], RX [], Y `00` | |
| 14 | `TS2068_IO` | **the boot-noise flush**: any word in RX is taken and logged until 500 ms of silence | RX emptied, Y `00` | a Z80 already sending is held off by Y BUSY; only its power-on noise can arrive |
| 15 | `TS2068_IO` | **the boot pre-load**: `MQ.put(0x01)`, then `MQ_READY()` — data first, then READY | **TX [01], Y `FF`** | READY before the put would hand the Z80 `00` (Report J) |
| 16 | `TS2068_IO` | `OPEN_NOFILE_TAP()` (the tape `LOAD ""` gets with nothing mounted), the SD outcome logged, `SAVE_LOG`, LED off | | a missing `/assets/nofile.tap`: `LOAD ""` with nothing mounted gives Report R |
| 17 | `TS2068_IO` | the capture buffers; `RX_DMA` claims a DMA channel for the pre-header, or `None` | | no channel: the loop polls instead |
| 18 | the service loop | arm the channel, wait for the Z80's first write; meanwhile the idle heartbeat (an LED flash every 2 s, two without a card) and, on core 1, `SAVE_LOG` | TX [01], Y `FF` | |

On the v3 card ([../firmware/board.md](../firmware/board.md#board_v3py)) step 5 is
`tsbus.start()` (250 MHz, core 1's bus loop; the 2068 held in reset), step 7
also sets the LED's brightness (`LED_BRIGHTNESS`, default 5 %), step 8
loads `/rom/TSPICO-23.ROM` into HOME and EXROM and releases the 2068 (only
now does it start), step 10 is skipped, and step 11 mounts the card on its
own pins without taking the bus.

From step 15 on the Pico is ready for any transaction. The pre-load at
step 15 is the only one staged outside a transaction's tail; every
transaction after it ends by staging the next.

## The 2068

| # | Where | What happens | What can go wrong |
|---|---|---|---|
| 1 | HOME 0000h | the Z80 resets into HOME — the Pico's flash slot `ROM_SLOT` (normally 1, ROM 2.2), served by the ROM state machine | the Pico not yet at step 8: the Z80 reads whatever the bus floats to *(unverified: in practice the Pico's boot is fast enough, and the 2068's own reset delay covers it)* |
| 2 | HOME (genuine) | the 2068's RAM test, system variables, channels | |
| 3 | HOME 0DF1h | the 29-byte boot stub at 0E0Bh is copied to RAM 6000h and run: `OUT (F4h),03h` — chunks 0 and 1 from the cartridge bus (TS-Pico: 03h, genuine 01h), FFh bit 7 set (the EXROM), the 2068's bank-switch code copied from EXROM 1000h–162Fh to RAM 6200h, back to HOME ([../rom/home.md](../rom/home.md#0e0ch-a-16k-exrom)) | an 8K-only EXROM model (an old emulator) fails at the first call into chunk 1 |
| 4 | HOME 0DFFh | the bank stack pointer (65CEh) initialised | |
| 5 | HOME 0E05h | EXTINIT, EXROM 08E7h, called through the RAM bank code | |
| 6 | EXROM 08E7h → 01BCh | the TS-Pico's EXTINIT: `CALL 221Fh` — **TPMODE = 2** (LOAD and SAVE to the Pico, printer to the 2068), 5CBEh and 6315h cleared — then BANK (5DCFh) = FFh ([../rom/sysvars.md](../rom/sysvars.md#5ddbh-tpmode-peek-24027)) | |
| 7 | EXROM 1C49h | the banner: 41 bytes copied to the printer buffer at 5B00h and printed through HOME's PO-MSG: "© 2026 TS-Pico ROM v2.2" ([../rom/exrom-driver.md](../rom/exrom-driver.md#the-boot-message-1c49h)) | |
| 8 | EXROM 1C86h | the rest of the genuine EXTINIT; back to HOME | |
| 9 | HOME | the copyright message, the BASIC prompt | |

Nothing in the 2068's boot talks to the Pico through ports 0Eh/0Fh: the
two meet only at the first transaction.

## The first transaction

1. **2068**: the user types, say, `SAVE "tpi:info"`. The ROM sends SYNC
   (`OUT (0Fh),03h`) and waits up to ~1 s for READY + IDLE
   ([../rom/exrom-sync.md](../rom/exrom-sync.md#sync_write-2300h)).
2. **Pico**: the capture sees a port-0Fh write: `MQ_TO_IDLE` — both FIFOs
   emptied, one 01h staged, Y `FF` ([../firmware/tspico_io.md](../firmware/tspico_io.md#mq_to_idlemq-recoveredfalse-statustrue-first0x01)).
   TX [01], Y `FF` — the same state as after step 15, rebuilt.
3. **2068**: the ten-byte pre-header, then an immediate read of port 0Eh:
   the pre-load, 01h. Everything after this is
   [the command flow](command.md).

With ROM 1.1 (no SYNC) the first transaction starts at step 3 and
depends on the boot pre-load of Pico step 15 being still in TX: a Pico
rebooted without the 2068 (a reflash) still stages it, so the next command
works either way.

## If the two disagree

| Situation | Result |
|---|---|
| The 2068 is reset (its reset button) while the Pico runs | the Pico keeps its state; the 2068's first transaction starts with SYNC, which puts the Pico back to idle |
| The Pico is reset or reflashed while the 2068 runs | the 2068 keeps its ROM only once the Pico is back at step 8; it must be reset afterwards *(the ROM disappears from the bus while the Pico restarts)* |
| No SD card at power-on | the boot completes; commands that need a card answer "No SD card…" (J) until one is inserted ([command.md](command.md)) |
| `ROM_SLOT` points at an empty or bad slot (a one-shot `tpi:boot`) | the 2068 crashes or hangs at step 1; the next power cycle boots flash slot 1 (`LOAD_CONFIG` reset the one-shot) |
| The firmware is older than the ROM (no SYNC support) | the 2068's SYNC byte is read as the first byte of a pre-header: every command misaligned |

## Where to read more

- The Pico side in full: [../firmware/tspico-dispatch.md](../firmware/tspico-dispatch.md#ts2068_io).
- The boot configuration and the files on the flash: [../firmware/boot.md](../firmware/boot.md).
- The pins: [../hardware.md](../hardware.md).
- The 2068's HOME boot changes: [../rom/home.md](../rom/home.md).
