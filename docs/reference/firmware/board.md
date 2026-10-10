# The board layer

Source: [`src/TS/board.py`](../../../src/TS/board.py),
[`src/TS/board_v2.py`](../../../src/TS/board_v2.py),
[`src/TS/board_v3.py`](../../../src/TS/board_v3.py).

Every place the firmware touches the board's hardware, behind one module.
This is phase 4 of the v3 port plan (tspico-hardware
`docs/v3-firmware-port-plan.md`; the design is
[docs/v3-board-layer-proposal.md](../../v3-board-layer-proposal.md)). One
source tree is to build for two boards: the v2 TS-Pico (RP2040, the bus in
PIO state machines) and the v3 card (RP2350B, the bus in the `tsbus` C
module, [tsbus.md](tsbus.md)). `board_v2.py` is the code that was in
`main.py` and `tspico.py`, moved here unchanged (step 4.1).
`src/test/board_hosttest.py` pins every state machine, pin, level and clock
it sets against what the old code set. `board_v3.py` (step 4.3) is the v3
card's, checked by `src/test/board_v3_hosttest.py`; only the v3 build
freezes it ([board-v3.md](board-v3.md#manifestpy)).

Who calls what:

| Call | From |
|---|---|
| `early_init()` | `main.py` (66–67), once, before `TS2068_IO` |
| `start_memory()` | `TS2068_IO` (6236), once |
| `map_slots()` | `MEMBOOT` (5067), `MEMDOCK` (5187) |
| `make_mq()` | `ACTIVATE_MQ` (754), `ZX48_IO` (7194) |
| `restart_mq()` | `ZX48_IO` (7195, 7300, 7342) |
| `sd_take_bus()`, `sd_cs()`, `sd_spi()` | `ACTIVATE_SD` (1098, 1101, 1119) |
| `sd_card_ready()` | `ACTIVATE_SD` (1091), before anything else |
| `sd_release_bus()` | `DEACTIVATE_SD` (707) |
| `make_led()` | `TS2068_IO` (6210) |
| `led_brightness()` | `TS2068_IO` (6214), after `LOAD_CONFIG` |
| `background()` | `TS2068_IO`: `BLINK_LED` at boot (6336, only if `HAS_CORE1`), `SAVE_LOG` from the idle loop (6997) |
| `SLOTS` | `NO_SLOTS`, for `MEMBOOT`, `MEMDOCK`, `BLKRCV` ([tspico-commands.md](tspico-commands.md#no_slots)) |
| `HAS_CORE1` | `TS2068_IO`, the boot blink |

`tspico_io.py` can't import the board layer: `board_v2` imports it for the
PIO programs. So it detects the v3 card itself (step 4.2;
[tspico_io.md](tspico_io.md#the-v3-card)). There it turns off its PIO
register writes and DMA, streams blocks through the tsbus queue, keeps `MQ`
in `ENA_MQ_DUAL`, and takes the LED `TS2068_IO` gives it. On v2 it still
builds its own state machine and SD pins in `ENA_MQ_DUAL` and `ENA_SD`, for
ZX48 SAVEs and the upgrade UF2. The upgrade UF2 (`src/upgrade/`) is
v2-only, keeps its own `main.py`, and doesn't use the board layer.

## `board.py`

### `_tsbus_mq`

`tsbus.MQ` if the `tsbus` C module is present, else `None`. The test that
picks the board. It's not plain `import tsbus`: on a host, `src/tsbus/` (the
module's C sources) imports as an empty namespace package, and the host
tests would then take the v3 path. Only the v3 build has the real module.

The module then does `from TS.board_v3 import *` or `from TS.board_v2
import *`, so `board.X` is the implementation's `X`. The functions run in the
implementation's own namespace, so a test that replaces a constructor
patches `TS.board_v2` (the host tests' `_hw()`), not `TS.board`.

## `board_v2.py`

Imports `machine.Pin`, `SPI`, `freq`, `rp2.StateMachine`, `asm_pio`,
`_thread`, and `TS_IO_DUAL`, `set_ctrl`, `sel_bank` from `tspico_io`.

### `NAME`, `PIO_MQ`

`"v2"`, and `True`: `MQ` is a PIO state machine, so `tspico_io` may write
its registers and pace DMA on its DREQs. Nothing reads `PIO_MQ`:
`tspico_io` makes the same test itself (above).

### `SLOTS`, `HAS_CORE1`

Both `True`. `SLOTS`: the 16 flash and SRAM slots exist, so `tpi:boot`,
`tpi:dock` and `tpi:blkrcv` run (`NO_SLOTS` lets them through). `HAS_CORE1`:
core 1 is free for `background()`, so `TS2068_IO` starts the boot blink.

### `NULL_SM`

The PIO program that parks state machine 0 while the SD card has GPIO 2–4:
[pio.md](pio.md#null_sm). It moved here from `tspico.py` with
`sd_take_bus`, its only user.

### `_rom`, `_bank`

The two slot state machines, `None` until `start_memory`: `_rom` is
`set_ctrl` on state machine 4 (/BE, A14_L and the flash/SRAM chip enables),
`_bank` is `sel_bank` on state machine 5 (the A15–A18 slot lines). Created
once and never rebuilt; [pio.md](pio.md) has the programs. They were the
`ROM` and `BANK` globals in `tspico.py` until step 4.1.

### `early_init()`

What: the bus-control pins at their idle levels, then the clock. `main.py`
calls it once, after the firmware is imported and before `TS2068_IO`.

| Pin | GPIO | Set to | Meaning |
|---|---|---|---|
| `U6_EN` | 12 | out, pull-up, 1 | U6, the data-bus buffer, off: the Pico is off the 2068's data bus until `TS_IO_DUAL` takes the pin as its side-set |
| `WAIT` | 14 | out, pull-down, 1 | named WAIT here; `TS_IO_DUAL` waits on GPIO 14 as `/PICOSEL`, the port 0Eh/0Fh select, an input to the PIO. See below |
| `U10_ENA` | 19 | out, pull-up, 1 | U10, the flash, disabled until `set_ctrl` takes the pin |
| `U13_ENA` | 20 | out, pull-up, 1 | U13, the SRAM, disabled until `set_ctrl` takes the pin |
| `BE` | 21 | out, pull-up, 1 | /BE inactive until `set_ctrl` drives it |
| ROSCS | 26 | in, pull-down | the ROM-area select, read by the slot state machines as their jump pin |
| `U10_WE` | 27 | out, pull-up, 1 | the flash's write enable, held inactive; never written again by the firmware (the Z80 programs the flash) |

Then `freq(270_000_000)`.

Why: between power-on and `TS2068_IO` building its state machines, the Pico
drives nothing onto the 2068's buses and enables no memory. The meanings of
U10, U13 and /BE are as [hardware.md](../hardware.md) gives them, partly
*(inferred)* there. The `Pin` objects are locals: a `Pin` is a handle, and
the pin keeps its state when the object goes. (In `main.py` they were module
globals that nothing read.) Each pin is later taken by a state machine
(`TS_IO_DUAL`, `set_ctrl`, `sel_bank`), or GPIO 12 by `sd_take_bus`, which
sets it to output 1 exactly as here.

GPIO 14's two names: this function (and `src/upgrade/main.py`) calls it
`WAIT` and makes it an output driven 1; `TS_IO_DUAL` uses it as an input it
waits on. Once the PIO program runs, the pin is the PIO's and whatever
drives it externally is what the program sees. Which name is right, and
whether driving it at boot matters, is discussed in
[hardware.md](../hardware.md#the-z80-bus-ports-0eh-and-0fh) and is
*(unverified)* on a scope.

### `start_memory(rom_sm, bank_sm)`

Builds `_rom` (`StateMachine(4, set_ctrl, freq=150_000_000,
in_base=Pin(0, IN), jmp_pin=Pin(26), set_base=Pin(21, OUT),
out_base=Pin(19, OUT))`) and `_bank` (`StateMachine(5, sel_bank,
freq=150_000_000, jmp_pin=Pin(26), out_base=Pin(15, OUT))`), starts both,
then `map_slots(rom_sm, bank_sm)`. `TS2068_IO` passes `TSP.ROM_SM` and
`TSP.bank_sm` ([tspico-state.md](tspico-state.md)). The `set_dck` alternative
for state machine 4 (DOCK only, no ROM mapping) is a comment.

The service-loop restart in `TS2068_IO` leaves these state machines alone on
purpose. Rebuilding them, or `machine.reset()`, would release the lines that
select the 2068's ROM bank under the running machine (the comment at
6470–6479). Host harnesses must never use state machines 4 or 5.

### `map_slots(rom_sm, bank_sm)`

`_rom.put(rom_sm)`, `_bank.put(bank_sm)`: one word each through the TX
FIFOs, which switch the boot and dock slots under the running 2068.
`MEMBOOT` sleeps 0.1 s before calling it (the Z80 is still finishing the
statement in the old ROM).

### `make_mq()`

`StateMachine(0, TS_IO_DUAL, freq=30_000_000, out_base=Pin(2, OUT),
in_base=Pin(2, IN), jmp_pin=Pin(11), sideset_base=Pin(12, OUT))`, returned
**not started**. A new object on the same hardware state machine keeps its
old Y, so `ACTIVATE_MQ` sets BUSY before it starts it (#171,
[tspico-bus.md](tspico-bus.md)). `ZX48_IO` starts it with `restart_mq` and
then sets READY.

### `restart_mq(MQ)`

`MQ.active(0)`, 10 ms, `MQ.active(1)`. `ZX48_IO` uses it on entry, after an
unrecognised byte, and on exit, each time after draining the FIFOs.

### `card_present()`, `sd_card_ready()`

This board's socket has no detect switch: `card_present()` is `None`
(unknown), and `sd_card_ready()` is always `True`, so `ACTIVATE_SD` finds a
missing card by its mount failing, as it always has.

### `sd_take_bus()`

Gives GPIO 2–4 to the SD card:
1. State machine 0 is rebuilt on `NULL_SM` at 15 MHz, started and stopped:
   parked, its program and FIFOs gone.
2. GPIO 12 is driven high, holding U6 off so the 2068 can't fight the card.

Returns the parked state machine, which `ACTIVATE_SD` keeps as `MQ`, and
`make_mq()` hands the pins back. GPIO 2–4 are SPI0 and also Z80 D0–D2
([hardware.md](../hardware.md)).

### `sd_cs()`, `sd_spi()`

The card's chip select, `Pin(28, OUT, PULL_UP)`; and
`SPI(0, sck=Pin(2, IN), mosi=Pin(3, IN), miso=Pin(4, IN))`. `ACTIVATE_SD`
makes a new SPI for each mount attempt, as before.

### `sd_release_bus()`

After the card is unmounted: CS high, and GPIO 2–4 driven low until the bus
state machine takes them back (`ACTIVATE_MQ`, straight after). Kept as
harmless. Whether the clamp is needed at all needs a scope (audit §4): U6
has kept the 2068 off these pins during SD use since #61.

### `make_led()`

`Pin(25, OUT)`, the Pico's LED. `TS2068_IO` keeps it as the global `led`
([tspico-state.md](tspico-state.md#led)).

### `led_brightness(led, pct)`

Does nothing: `config.ini`'s `LED_BRIGHTNESS` is for the v3 card, and the
Pico's own LED is lit at full brightness as before.

### `background(fn, args)`

`_thread.start_new_thread(fn, args)`: `fn` runs on core 1. Callers keep
v2's rules about core 1: `busy`, `WAIT_CORE1`, and setting `busy` before
the call ([tspico-files.md](tspico-files.md), `SAVE_LOG`). An `OSError`
(core 1 still busy) reaches the caller.

## `board_v3.py`

The v3 card (RP2350B). It has no memory chips: `tsbus` serves the 2068's
ROM and DOCK from SRAM and answers ports 0Eh/0Fh from core 1
([tsbus.md](tsbus.md)). The SD card has its own pins, so SD never takes the
bus; the LED is on the XL9555 expander; core 1 belongs to `tsbus`. Imports
`tsbus` and `machine.Pin`, `SPI`, `I2C`, `Timer`. Same names as
`board_v2.py`, so `tspico.py` calls the same functions on either board.

### `NAME`, `PIO_MQ`, `SLOTS`, `HAS_CORE1`

`"v3"`, then all `False`. `PIO_MQ`: `MQ` is `tsbus.MQ()`, whose `exec`
takes only the strings `tspico_io` sends; there are no PIO registers or
DREQs to touch. `SLOTS`: no slots until phase 5 of the v3 port plan, so the
slot commands refuse (`NO_SLOTS`). `HAS_CORE1`: core 1 runs the `tsbus`
loop, so `background()` runs on core 0 and there is no boot blink.

### `SLOTS_DIR`, `SLOT_SIZE`, `MEM_SRAM`, `MEM_FLASH`

`"/slots"` on the Pico's flash filesystem, 32768, and `ROM_SM`'s two memory
codes, 1 and 2. v2's two chips of sixteen 32K slots become files (phase 5,
[docs/v3-slots-proposal.md](../../v3-slots-proposal.md)):
- `Fnn.bin` is flash slot nn, kept;
- `Snn.bin` is SRAM slot nn, deleted at every boot, as v2's SRAM loses its
  contents at power-off.

A missing file, or one that isn't 32K, is an empty slot. A ROM slot is HOME
(16K) then EXROM (16K). `build-flash.py --slots` makes the flash ones
([boot.md](boot.md)).

### `ROM_FILE`

`"/rom/TSPICO-23.ROM"` on the Pico's flash filesystem, the image
`src/rom/TSPICO-23.ROM`. Since phase 5 it is only the last fallback for the
boot ROM (`boot_rom`): the 2068 is never released into an empty ROM. Copied
there by hand on the cards that have one.

### `_SD_CS`, `_SD_SCK`, `_SD_MOSI`, `_SD_MISO`

The SD card's own pins: CS 37, SCK 38, MOSI 39, MISO 32, SPI0
([board-v3.md](board-v3.md#pinscsv)). GPIO 2–4 are MD2–MD4 on this card,
the Z80 data bus, and are never touched by SD.

### `_IOX_ADDR`, `_IOX_IN1`, `_IOX_OUT0`, `_IOX_OUT0_SAFE`, `_X_NLED`, `_X_SD_CD`

The XL9555 at I2C address 20h. Register 1 is input port 1 (the joystick,
nBUSAK_L and the SD card-detect switch); register 2 is output port 0. Its
safe value is E0h (no bus request, no NMI, OLED in reset, ESP32 off, LED
off), as `board_init.c` sets it at start-up. Bit 5 of port 0 (20h) is the
LED, active low: lit, port 0 is C0h. Bit 7 of port 1 (80h) is the detect
switch: the TF-01A's switch closes to GND with a card in, and R38 pulls it
up, so low means a card. Read on the card with the socket empty: port 1 FFh.

### `SD_SETTLE_MS`

250. How long a card the switch has only just seen is left before its first
SPI clock (`sd_card_ready`), so that it is fully seated and powered before
its lines are driven. A judgement, not a measured figure.

### `_i2c`, `_cd_since`

`_i2c`: `I2C(0)`, made on first use by `_iox()` and shared by the LED and
the switch read. `_cd_since`: `ticks_ms` when the switch was first seen
closed, `None` while the socket is empty.

### `_iox()`

`_i2c`, making it first if need be. I2C0 on the board's defaults: SCL 25,
SDA 24.

### `LED_PERIOD_US`, `LED_BRIGHTNESS`

10 000 µs, the dimmer's period (100 Hz, no visible flicker), and 5, the
default on-time in percent. D4 on a 100 Ω resistor is far too bright lit
continuously: the bring-up firmware dims it with a 2.5 % step PWM; 25 % was
still too bright on the card (2026-10-10), 5 % is David's choice.
`config.ini`'s `LED_BRIGHTNESS` overrides it (`led_brightness`).

### `early_init()`

`tsbus.start()`: the clock to 250 MHz, the bus programs, core 1's loop. The
2068 stays held in reset until `start_memory`. The safe pin state was set in
C at start-up ([board-v3.md](board-v3.md#board_initc)), so there are no pins
to set here.

### `slot_path(mem, slot)`

`"/slots/Fnn.bin"`, or `"/slots/Snn.bin"` for `MEM_SRAM`.

### `read_slot_into(mem, slot, buf)`

Reads a slot's 32K into `buf` (a 32K `bytearray` or `memoryview`) in place,
and returns `True`. Returns `False`, `buf` untouched, if there is no file or
it isn't 32K (`os.stat` first). In place because the heap is about 190K: the
first version read each slot into a new 32K block, next to a 64K dock image
and the 32K ROM. On the card that failed at boot with `MemoryError`, and the
2068 stayed held (2026-10-10).

### `read_slot(mem, slot)`

A slot as a new 32K `bytearray`, or `None`. For callers with no buffer to
hand; the boot path doesn't use it.

### `clear_sram_slots()`

Deletes every `S*.bin` in `SLOTS_DIR`, quietly if there is none: the SRAM
slots start empty at every boot.

### `boot_rom(rom_sm, bank_sm)`

The ROM to boot, a 32K `bytearray`, and a note if it isn't the one asked
for. The memory is `rom_sm` bits 0–1, the slot `bank_sm` bits 0–3.

1. That slot's file.
2. Missing: flash slot 1, with the note "no ROM in flash slot 7: booted
   flash slot 1".
3. Missing too: `ROM_FILE`, "no ROM in … or flash slot 1: booted
   /rom/TSPICO-23.ROM". If slot 1 itself was asked for, the note just says
   "no ROM in flash slot 1".

An SRAM boot slot always falls back, because the SRAM slots were just
cleared. On v2 that boots an empty chip and hangs the 2068. A missing
`ROM_FILE` at the last step raises.

### `dock_image(rom_sm, bank_sm)`

The 64K DOCK image. The memory is `rom_sm` bits 2–3, the slot `bank_sm`
bits 4–7. The low 32K is the dock slot. For an even slot the high 32K is
the next slot: v2's 64K cartridge spans two consecutive slots numbered by
the even one. Both halves are read in place into one `bytearray`.

A half with no file is zeros, as an empty v2 slot reads, not a mirror of
the other half. The AROS cartridges in the base image keep everything in
the upper half (8000h–FFFFh), and a mirror would copy them to 0000h too. An
odd dock slot fills the low half only. Slot 0 is the 16K Spectrum ROM,
zero-filled, so the default dock has it at 0000h–3FFFh for ZX48 mode.

### `start_memory(rom_sm, bank_sm)`

`clear_sram_slots()`, then `tsbus.hold(True)`:
1. `boot_rom`'s ROM into HOME (the first 16K) and EXROM (the rest);
2. the ROM buffer dropped and `gc.collect()`, so only one big buffer exists
   at a time;
3. `dock_image` into DOCK;
4. EXROM and DOCK chunks served (`exrom(True)`, `dock(True)`),
   `serve(True)` (/BE live), and `hold(False)`: the 2068 is released into
   the new ROM.

Serving is on before the release, so the Z80's first fetch is answered.
Returns `boot_rom`'s note (also printed, `[board] …`), which `TS2068_IO`
logs at level 2. A missing `ROM_FILE` with no slot to boot raises, and
`main.py` logs it: the 2068 stays in reset.

Checked on proto1 (2026-10-10), with `/slots` from `build-flash.py --slots`:
ROM 2.3 boots from `F01.bin`, `CAT` and a LOAD work, a one-shot boot of
empty slot 7 comes up in ROM 2.3 and `config.ini` goes back to slot 1, and a
one-shot boot of slot 2 runs ZX Diagnostics.

No shadow boot: the 2068 is held from power-on until here, rather than
running a ROM while the firmware loads (a choice made 2026-10-10, step 4.3).
The cost: SCLD bank registers survive a Z80 reset, so a card swapped in
under a running 2068 can boot to a blank screen until the 2068's own reset
or a power cycle *(seen once on hardware)*.

### `map_slots(rom_sm, bank_sm)`

Nothing: the slot commands refuse (`NO_SLOTS`) before they get here.

### `make_mq()`

`tsbus.MQ()`, with both queues emptied (`get` while `rx_fifo()`,
`exec("pull (noblock)")` while `tx_fifo()`), as a new v2 state machine's
FIFOs are empty. The status byte is left as it is: `ACTIVATE_MQ` sets BUSY
itself.

### `restart_mq(MQ)`

Nothing: core 1 is always serving.

### `card_present()`

The detect switch: `True` with a card in, `False` without, and `None` if the
expander doesn't answer (an `OSError`), when only a mount can tell. One
I2C read of input port 1, about 100 µs.

### `sd_card_ready()`

`ACTIVATE_SD` asks this before it touches an SD line.

- `card_present()` is `None`: `True`, and the mount finds out.
- `False`: `_cd_since` cleared and `False`, so `ACTIVATE_SD` fails at once
  and the socket is never clocked.
- `True`: `_cd_since` set if this is the first time the card is seen, then
  `sleep_ms` for whatever is left of `SD_SETTLE_MS`, then `True`. A card in
  for longer goes straight through. One taken out and put back settles
  again.

Why (2026-10-10): two cards died on the card the moment they went into its
socket, each resetting the RP2350B (and so the 2068). The firmware used to
find out whether a card was there by trying to start one. It clocked an
empty socket for about 3.6 s every time it looked, with CS, SCK and MOSI
driven, and a card going in could meet live lines before its VDD contact
made, which can power it through its I/O pins. The board measured healthy
afterwards, and the dead cards read 190 Ω across their supply (a good one
about 6 kΩ). With this function and `sd_release_bus` in place, three hot
inserts were clean: USB only with the firmware stopped and with it running,
and in the 2068. No reset, and the cards stayed cool
(tspico-hardware [#21](https://github.com/factus10/tspico-hardware/issues/21),
which keeps the design question open: switched power for the socket). The
switch is also a faster and surer "no card" than a mount's timeout.

### `sd_take_bus()`

Returns `tsbus.MQ()` and changes nothing: the SD card has its own pins, so
the bus, its queue and the 2068 carry on. `ACTIVATE_SD` keeps it as `MQ`.

### `sd_cs()`, `sd_spi()`

`Pin(37, OUT, value=1)`: driven high, so the card is deselected from the
first instant; `SDCard` drives it from there. And
`SPI(0, sck=Pin(38), mosi=Pin(39), miso=Pin(32))`.

### `sd_release_bus()`

After every unmount: CS, SCK, MOSI and MISO become plain inputs with no
pulls (`Pin(p, IN, pull=None)`), the state `board_init.c` leaves them in at
power-on. Nothing drives the socket between commands. R34 holds CS high, so
a card that is in stays deselected, and R35 holds MISO; SCK and MOSI float
behind their 33 Ω resistors. No pull-downs: RP2350 erratum E9 can latch a
pad with input and pull-down both on. Making the pins inputs takes them
from SPI0, which until 2026-10-10 went on driving SCK and MOSI after every
unmount, while CS was driven high.

### `ExpanderLED`

D4 behind the expander, with `Pin`'s `value`, `on`, `off` and `toggle`, so
`led` is used the same way on both boards. Dimmed: while on, a periodic
`machine.Timer` lights it every `LED_PERIOD_US` and a one-shot timer turns
it off after the on-time. That is two I2C writes (about 100 µs each) a
period whatever the brightness, and none while it is off: both timers are
stopped. The callbacks are soft (run between bytecodes on core 0), so a long
C call there stretches a period; that is a flicker, not a fault.

| Method | What |
|---|---|
| `ExpanderLED.__init__()` | the shared `I2C(0)` (`_iox()`); off; on-time from `LED_BRIGHTNESS`; the two callbacks bound once, so the timer callbacks allocate nothing |
| `ExpanderLED._write(lit)` | writes port 0 (C0h lit, E0h dark) only when `lit` changes; an `OSError` (no expander) is ignored, the LED is cosmetic |
| `ExpanderLED._light(t)` | the period timer: lit, and the one-shot re-armed for the on-time |
| `ExpanderLED._dark(t)` | the one-shot: dark |
| `ExpanderLED._stop()` | both timers stopped and dropped |
| `ExpanderLED._start()` | lit now; below 100 %, the one-shot and the period timer started |
| `ExpanderLED.brightness(pct)` | the on-time, `pct` % of the period; restarts the timers if on |
| `ExpanderLED.value(v=None)` | no argument: the logical state (0/1). Else on (`_start`) or off (`_stop`, dark), only on a change |
| `ExpanderLED.on()`, `ExpanderLED.off()`, `ExpanderLED.toggle()` | `value(1)`, `value(0)`, `value(not v)` |

### `make_led()`

An `ExpanderLED`.

### `led_brightness(led, pct)`

`led.brightness(pct)`. `TS2068_IO` calls it with `config.ini`'s
`LED_BRIGHTNESS`, which `LOAD_CONFIG` has checked is 1–100
([tspico-dispatch.md](tspico-dispatch.md#load_config)).

### `background(fn, args)`

`fn(*args)`, at once, on core 0: core 1 is `tsbus`'s. The caller waits for
it. `SAVE_LOG` from the idle loop is the only caller on v3; `BLINK_LED`,
which would never return, is not started (`HAS_CORE1`).

## Where comments and the code disagree

None known.
