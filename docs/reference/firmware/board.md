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
| `start_memory()` | `TS2068_IO` (6218), once |
| `map_slots()` | `MEMBOOT` (5049), `MEMDOCK` (5169) |
| `make_mq()` | `ACTIVATE_MQ` (754), `ZX48_IO` (7174) |
| `restart_mq()` | `ZX48_IO` (7175, 7280, 7322) |
| `sd_take_bus()`, `sd_cs()`, `sd_spi()` | `ACTIVATE_SD` (1091, 1094, 1112) |
| `sd_release_bus()` | `DEACTIVATE_SD` (707) |
| `make_led()` | `TS2068_IO` (6192) |
| `led_brightness()` | `TS2068_IO` (6196), after `LOAD_CONFIG` |
| `background()` | `TS2068_IO`: `BLINK_LED` at boot (6316, only if `HAS_CORE1`), `SAVE_LOG` from the idle loop (6977) |
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
6450–6459). Host harnesses must never use state machines 4 or 5.

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

### `ROM_FILE`

`"/rom/TSPICO-23.ROM"` on the Pico's flash filesystem: HOME (16K), then
EXROM (16K), the image `src/rom/TSPICO-23.ROM`. Copied there by hand for now
(the v3 card has no installer yet). Phase 5 replaces it with the slot files.

### `_SD_CS`, `_SD_SCK`, `_SD_MOSI`, `_SD_MISO`

The SD card's own pins: CS 37, SCK 38, MOSI 39, MISO 32, SPI0
([board-v3.md](board-v3.md#pinscsv)). GPIO 2–4 are MD2–MD4 on this card,
the Z80 data bus, and are never touched by SD.

### `_IOX_ADDR`, `_IOX_OUT0`, `_IOX_OUT0_SAFE`, `_X_NLED`

The XL9555 at I2C address 20h; register 2, output port 0; its safe value
E0h (no bus request, no NMI, OLED in reset, ESP32 off, LED off), as
`board_init.c` sets it at start-up; and bit 5 (20h), the LED, active low.
Lit, port 0 is C0h.

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

### `start_memory(rom_sm, bank_sm)`

Reads `ROM_FILE` whole, then: `tsbus.hold(True)`; HOME from the first 16K,
EXROM from the rest (`tsbus.load`); EXROM and DOCK chunks served
(`exrom(True)`, `dock(True)`); `serve(True)` (/BE live); `hold(False)`, the
2068 released into the new ROM. Serving is on before the release, so the
Z80's first fetch is answered. `rom_sm` and `bank_sm` are not used. A
missing `ROM_FILE` raises, and `main.py` logs it: the 2068 stays in reset.

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

### `sd_take_bus()`

Returns `tsbus.MQ()` and changes nothing: the SD card has its own pins, so
the bus, its queue and the 2068 carry on. `ACTIVATE_SD` keeps it as `MQ`.

### `sd_cs()`, `sd_spi()`

`Pin(37, OUT, PULL_UP)`; `SPI(0, sck=Pin(38), mosi=Pin(39), miso=Pin(32))`.

### `sd_release_bus()`

CS high. No clamp: nothing else uses these pins.

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
| `ExpanderLED.__init__()` | `I2C(0)` (the board's defaults, SCL 25, SDA 24); off; on-time from `LED_BRIGHTNESS`; the two callbacks bound once, so the timer callbacks allocate nothing |
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
