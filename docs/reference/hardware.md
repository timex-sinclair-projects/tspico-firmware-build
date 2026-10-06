# The hardware, as the code sees it

Source: [`src/main.py`](../../src/main.py),
[`src/upgrade/main.py`](../../src/upgrade/main.py),
[`src/TS/tspico_io.py`](../../src/TS/tspico_io.py),
[`src/TS/tspico.py`](../../src/TS/tspico.py),
[`src/TS/sdcard.py`](../../src/TS/sdcard.py),
[`flash/README.md`](../../flash/README.md),
[`flash/manifest.json`](../../flash/manifest.json).

The repository holds no schematic. What it holds is code that drives
twenty-four of the Pico's GPIOs by number, names some of them, and comments
on a few; the user manual's tour of the board
([user-manual.md](../manual/user-manual.md) ch. 2.3); and the design notes.
This chapter assembles the board from those, and keeps two kinds of
statement apart: what the code **states** (a pin name, a comment, a
constant) and what is **inferred** from how the code uses a pin. The
inferences are marked *(inferred)*; what only a scope could settle is
marked *(unverified)*. The only part numbers used are the four the code
names: U3, U6, U10 and U13.

The TS-Pico is a Raspberry Pi Pico (RP2040) on a board that plugs into the
TS-2068's expansion connector. Three things on the board are the Pico's to
drive: an 8-bit port pair on the Z80 I/O space (ports 0Eh and 0Fh), 512K
of flash and 512K of SRAM that stand in for the 2068's ROMs and its
cartridge dock, and a micro SD card. The Pico runs MicroPython; the parts
that must answer inside a Z80 bus cycle run on its PIO state machines
([firmware/pio.md](firmware/pio.md)), everything else in Python on core 0.

## Map

1. [The GPIO map](#the-gpio-map)
2. [The Z80 bus: ports 0Eh and 0Fh](#the-z80-bus-ports-0eh-and-0fh)
3. [The SD card and the shared pins](#the-sd-card-and-the-shared-pins)
4. [The memory: flash, SRAM, slots and pages](#the-memory-flash-sram-slots-and-pages)
5. [Clocks](#clocks)
6. [The two cores](#the-two-cores)
7. [DMA](#dma)
8. [The PIO budget](#the-pio-budget)
9. [The LED](#the-led)
10. [Stated and inferred](#stated-and-inferred)

## The GPIO map

Every GPIO the firmware touches, with the name the code gives it (or none),
where it is set up, and what it does. "ROM" and "BANK" are the state
machines of [firmware/pio.md](firmware/pio.md); "MQ" is the bus state
machine. `main.py` means both `src/main.py` and `src/upgrade/main.py`,
which set up the same pins the same way.

| GPIO | Name in the code | Set up by | Direction | Role |
|---|---|---|---|---|
| 0 | — | `set_ctrl`, `in_base=Pin(0)` | in | bit 0 of a 2-bit code read on a ROM-area access: 0 or 1 means the Pico answers, 2 or 3 that it does not. Not named anywhere |
| 1 | — | same | in | bit 1 of that code |
| 2 | `D0` (SD setup) | `TS_IO_DUAL` out/in base; `SPI(0, sck=…)` | PIO out, or SPI SCK | Z80 D0 through the U6 buffer; the SD card's clock |
| 3 | `D1` | same; SPI MOSI | PIO out, or SPI TX | Z80 D1; the SD card's data in |
| 4 | `D2` | same; SPI MISO | PIO out, or SPI RX | Z80 D2; the SD card's data out |
| 5–9 | — | `TS_IO_DUAL` out pins | PIO out | Z80 D3–D7 through U6. D6 is GPIO 8 (`DEACTIVATE_SD`'s comment) |
| 10 | `A0` (docstring) | nothing; read by `in_(pins, 9)` | in | address bit 0 of the Z80 I/O cycle: 0 = port 0Eh, 1 = port 0Fh |
| 11 | `R/W` (docstring) | `TS_IO_DUAL`, `jmp_pin=Pin(11)` | in | 1 = the Z80 is writing (OUT), 0 = reading (IN). The Z80's own /WR is active low, so this is a decoded signal *(inferred)* |
| 12 | `U6_EN` | `main.py` (out, pull-up, 1); `TS_IO_DUAL` side-set; `ACTIVATE_SD` (out, 1) | out | U6 bus-buffer enable, active low. 1 = the Pico is off the 2068's data bus |
| 13 | — | nothing; `wait(0/1, gpio, 13)` in `set_ctrl`, `set_dck`, `sel_bank` | in | the memory-access strobe: low for the duration of a 2068 access to the ROM area or the dock *(inferred from the waits)*. Not named anywhere |
| 14 | `WAIT` (`main.py`); `/PICOSEL` (`TS_IO_DUAL`) | `main.py` (out, pull-down, 1); `wait(0/1, gpio, 14)` in `TS_IO_DUAL` | out in `main.py`, read by the PIO | the chip select for ports 0Eh/0Fh, low during a bus cycle on either port. See [the two names](#the-z80-bus-ports-0eh-and-0fh) |
| 15–18 | — | `sel_bank`, `out_base=Pin(15)` | PIO out | A15–A18 of the flash and SRAM: the 32K slot. GPIO 15 is A15 |
| 19 | `U10_ENA` | `main.py` (out, pull-up, 1); `set_ctrl` out pin 0 | PIO out | enable of U10, the flash, active low *(inferred)* |
| 20 | `U13_ENA` | `main.py` (out, pull-up, 1); `set_ctrl` out pin 1 | PIO out | enable of U13, the SRAM, active low *(inferred)* |
| 21 | `BE` | `main.py` (out, pull-up, 1); `set_ctrl` set pin 0 | PIO out | /BE, driven low by the Pico during a ROM-area access it answers. What it enables is not in the code *(unverified)* |
| 22 | — | `set_ctrl` set pin 1 | PIO out | the line `set_ctrl`'s header calls A14_L: high or low by the GPIO 0–1 code on a ROM-area access *(the name is inferred from the comment's order)* |
| 23, 24 | — | not touched | — | (the Pico board's own SMPS-mode and VBUS-sense pins) |
| 25 | `led` | `TS2068_IO`, `LOAD_TS`, `LOAD_ZX`, `LOAD_ZX_C` | out | the Pico's on-board LED |
| 26 | `ROSCS` | `main.py` (in, pull-down); `jmp_pin` of ROM and BANK | in | ROM-area select: high = the access is to the ROM area, low = to the dock *(inferred from the branches)* |
| 27 | `U10_WE` | `main.py` (out, pull-up, 1) | out | the flash's write enable, held inactive by the Pico; never written again *(inferred: the Z80 programs the flash, see below)* |
| 28 | `U3_CS` | `main.py` (upgrade only), `ACTIVATE_SD`, `ENA_SD`, `DEACTIVATE_SD` (out, pull-up, 1) | out | the SD card's chip select, active low; "nCS = GP28 with a 4K7 pull-up" ([DEVELOPER_GUIDE.md](../DEVELOPER_GUIDE.md) §3) |

`src/main.py` sets up 12, 14, 19, 20, 21, 26 and 27 after importing the
firmware (which runs `tspico_io`'s module level) and before calling
`TS2068_IO`, all outputs driven high except ROSCS, an input: U6 off, both memory
chips disabled, /BE and the write enable inactive. `src/upgrade/main.py`
does the same and adds `U3_CS` high. The state machines then take their
pins over: building `ROM` and `BANK` moves 15–22 to PIO1, building `MQ`
moves 2–9 and 12 to PIO0 ([firmware/boot.md](firmware/boot.md),
[firmware/tspico-dispatch.md](firmware/tspico-dispatch.md)).

## The Z80 bus: ports 0Eh and 0Fh

The TS-Pico occupies two I/O addresses, 0Eh (14) and 0Fh (15). Port 0Eh is
data: a Z80 `IN` takes the next byte of the Pico's TX FIFO, an `OUT` puts
the byte in its RX FIFO. Port 0Fh is status: an `IN` reads the status byte
from the PIO's Y register, an `OUT` lands in RX like any other, tagged
([PROTOCOL.md](../PROTOCOL.md) §1; the bits are §3 and
[appendix/ports-and-status.md](appendix/ports-and-status.md)).

The board decodes the pair, not the port: one chip-select line, /PICOSEL
on GPIO 14, goes low for a cycle on either address, and A0 on GPIO 10 says
which. The state machine samples A0 with the data lines and keeps it: on
a read it chooses between the FIFO and Y; on a write it stays as bit 8 of
the 9-bit word in RX, which is the `PORT_0F` mask Python tests
([firmware/pio.md](firmware/pio.md)). The direction comes from GPIO 11.
Port 0Ah, which the ZX48 exit-by-byte once relied on, is not decoded at
all (issue #9, [OPEN_QUESTIONS.md](../OPEN_QUESTIONS.md)): the decoder is
specific to 0Eh and 0Fh. The JP4 jumper selects the port range 00h–0Fh
(user manual 2.3); the firmware has no knowledge of it.

The data lines D0–D7 reach GPIO 2–9 through a buffer, U6, that the state
machine enables (GPIO 12 low) only between /PICOSEL falling and rising.
Outside a cycle, and whenever the SD card has the pins, U6 is off and the
Pico is invisible to the 2068's bus. There is no /WAIT: the Pico cannot
hold the Z80 up, which is why the state machine never blocks and an
unanswered read gives 00h ([PROTOCOL.md](../PROTOCOL.md) §2,
[DUAL_PORT_DEVELOPMENT.md](../DUAL_PORT_DEVELOPMENT.md) §3b).

**The two names of GPIO 14.** `main.py` calls it `WAIT`, makes it an
output with a pull-down and drives it high, before any state machine
exists; `TS_IO_DUAL` waits on it as `/PICOSEL`, an input. Nothing in
between reconfigures the pin: the state machine is built without it in any
pin group, so it stays an SIO output driving high while the PIO reads its
level. For /PICOSEL to be seen low the board's decoder has to pull the pin
down against that drive, or the pin's function differs on the board from
what `main.py` assumes. The name suggests a /WAIT line was once planned on
this GPIO *(inferred)*; the firmware works as shipped, so the conflict is
resolved on the board somehow, and how is *(unverified)*.

**The data pins' direction.** `TS_IO_DUAL`'s `out_init` makes GPIO 2–9
outputs, and the program never changes that. During a Z80 `OUT` the state
machine samples pins it is driving; U6 must be driving them too. The code
does not show what U6 is or which way it faces; the result works on
hardware *(unverified beyond that)*.

## The SD card and the shared pins

The card is on SPI0: SCK on GPIO 2, MOSI on 3, MISO on 4, chip select on
GPIO 28 (`U3_CS`). The driver ([firmware/sdcard.md](firmware/sdcard.md))
clocks it at 100 kHz to initialise and 5 MHz after
(`SDCard(spi, cs, baudrate=5_000_000)`); the audit kept the 5 MHz
([AUDIT-2026-09-30.md](../AUDIT-2026-09-30.md) §5). U3, the card socket or
its level shifter, runs off the Pico's 3V3 rail with a 4K7 pull-up on nCS,
so nothing the Pico does short of losing power power-cycles the card
([DEVELOPER_GUIDE.md](../DEVELOPER_GUIDE.md) §3, the SD power note); a
card wedged mid-transfer is recovered by the driver, and a card wedged by a
hard reset needs reseating or a power cycle of the whole board.

GPIO 2, 3 and 4 are also D0, D1 and D2 of the Z80 bus. That one fact
shapes the firmware's bus handover
([flows/sd-handover.md](flows/sd-handover.md)):

- the Pico cannot talk to the card and the Z80 at the same time. Every SD
  access is bracketed: `ACTIVATE_SD` parks the bus state machine on
  `NULL_SM`, holds U6 off (`Pin(12, Pin.OUT, value=1)`), hands GPIO 2–4 to
  `SPI(0, …)` and mounts `/sd`; `DEACTIVATE_SD` unmounts, raises `U3_CS`,
  and drives GPIO 2–4 low as plain outputs; `ACTIVATE_MQ` rebuilds
  `TS_IO_DUAL`, which takes 2–9 and 12 back
  ([firmware/tspico-bus.md](firmware/tspico-bus.md));
- while the card has the pins the Z80 must be waiting on status, and
  status must say BUSY: "don't announce READY and then go do SD work"
  ([PROTOCOL.md](../PROTOCOL.md) §13, the pin-grab race of #40). A
  command's SD work therefore goes inside `SD_CALL`, before its answer
  (§11);
- the clamp low in `DEACTIVATE_SD` was once credited with fixing Report D.
  The comment and the audit retract that: Report D was a floating D6, and
  D6 is GPIO 8, not 2–4. The clamp is kept as harmless; whether it does
  anything is a scope job (audit §4, "The GPIO 2-4 clamp (#139): kept").
  The Report D story itself, a floating bus during the SPI-to-PIO handover
  read as "ready" through the 2068's pull-up on D6, is
  [DUAL_PORT_DEVELOPMENT.md](../DUAL_PORT_DEVELOPMENT.md) §1;
- the driver's leading `_spiff()` (0xFF with CS high) is "because GPIO 2-4
  are shared with the Z80 bus" (audit §5).

The ZX48 handlers, which never return to the dispatcher, do the same by
hand with `ENA_SD` and `ENA_MQ_DUAL` ([firmware/tspico_io.md](firmware/tspico_io.md)).

## The memory: flash, SRAM, slots and pages

### The chips

Two 512K devices sit on the 2068's memory bus: a flash chip and an SRAM.
The code names U10 and U13 and gives each an enable; `set_ctrl` drives GPIO
19 (`U10_ENA`) low for MEM = 2, which `LOAD_CONFIG`, `MEMBOOT` and the
user manual all call flash, and GPIO 20 (`U13_ENA`) low for MEM = 1,
SRAM. So U10 is the flash and U13 the SRAM *(inferred)*; `U10_WE`, the
flash write enable, fits. The flash keeps its contents; the SRAM does not
(user manual 8.1).

The Pico never writes either chip. Images reach the flash in two ways,
neither through the Pico's GPIOs: a programmer burns the whole 512K image
([`flash/README.md`](../../flash/README.md), "Deploying"), or the Z80 runs
`romupdate.tap` and erases and writes a slot through the dock mapping,
with the P10 jumper fitted (user manual 8.4). The Pico's part in that is
to stream the image to the Z80 (`BLKRCV`) and to refuse the slot the 2068
is running from (`BOOT_SLOT_CLASH`,
[firmware/tspico-commands.md](firmware/tspico-commands.md)). GPIO 27 is
driven high at boot and never touched again, so the Pico only holds its
copy of the line inactive *(inferred)*; the jumper and the Z80 side are
not in the code.

### Slots and pages

Each chip is addressed as **16 slots of 32K**: A15–A18 come from the Pico
(`sel_bank`, GPIO 15–18) and select the slot; the Z80's own address lines
select within it. The flash's slots are laid out in
[`flash/README.md`](../../flash/README.md) and
[`flash/manifest.json`](../../flash/manifest.json): slot 0 the ZX Spectrum
ROM v4, slot 1 the TS-2068 ROM 2.1, slots 2 and 3 third-party ROMs, 4–7
spare, and DCK cartridges at 8, 10, 12 and 14. The SRAM has sixteen slots
of its own (user manual 8.1).

A **ROM** slot holds a HOME ROM at offset 0 and an EXROM at offset 4000h,
32K in all; file offset equals Z80 address within each half
([`tools/build-rom.py`](../../tools/build-rom.py),
[rom/overview.md](rom/overview.md)). The two halves share Z80 addresses
0000h–3FFFh and are told apart by the 2068's bank selection
([MEMORY_MAP.md](../rom-analysis/MEMORY_MAP.md), "TS2068 banking primer"),
which on the Pico's side appears as the 2-bit code on GPIO 0–1 and the
A14_L line `set_ctrl` drives from it *(inferred; the code names neither
the code's bits nor which half is which)*.

A **DOCK** entry is a 64K cartridge: **two consecutive slots**, numbered by
the even one, which is why the cartridge slots step by 2. The firmware
drives all four bank lines from the one `DCK_SLOT` value, so how the
cartridge's upper 32K is reached when the Z80's A15 is high is a board
matter the code does not show *(unverified)*.

"Slot" and "page" are the same thing. `config.ini` and `flash/README.md`
say slot (`ROM_SLOT`, `DCK_SLOT`); `MEMBOOT`, `MEMDOCK` and the user manual
say PAGE (`BOOT is MEM=2, PAGE=1`); `src/upgrade/main.py`'s comment says
"the dock on flash page 0". All mean a 32K unit numbered 0–15.

### What the state machines are told

Two words configure the mapping, both fields of `TSP`
([firmware/tspico-state.md](firmware/tspico-state.md)):

- **`ROM_SM`**, put to the `ROM` state machine: `dock MEM * 4 + boot MEM`,
  MEM 1 = SRAM, 2 = flash. Valid values 5, 6, 9, 10; default 10 (binary
  1010, "both assigned to Flash"). Bits 0–1 go to the enables on a
  ROM-area access, bits 2–3 on a dock access.
- **`bank_sm`**, put to `BANK`: `DCK_SLOT * 16 + ROM_SLOT`, four bits
  each; default 1 (dock 0, ROM 1). Bits 0–3 go to A15–A18 on a ROM-area
  access, bits 4–7 on a dock access.

They are put three times: in `TS2068_IO` at boot, right after the two
state machines are built; in `MEMBOOT` (`tpi:boot`), after writing the
new boot setting to `config.ini` and sleeping 0.1 s; and in `MEMDOCK`
(`tpi:dock`), once `BOOT_SLOT_CLASH` has passed and the reply has been
sent (a refused slot is never put). The upgrade
firmware puts the defaults, 10 and 1. The state machines keep the last
word in their X register and apply it to every access until the next
`put()`: the change is immediate, which is why the user manual says to
follow `tpi:boot` with `NEW` and why `MEMBOOT`'s 0.1 s wait exists (audit
§4 kept it). A boot slot other than flash slot 1 lasts one power cycle:
`LOAD_CONFIG` uses it once and writes slot 1 back
([firmware/tspico-dispatch.md](firmware/tspico-dispatch.md)).

### The strobe and the select

Both memory state machines wait for GPIO 13 to fall, act, and wait for it
to rise: it is the "a 2068 memory access that may be ours is in progress"
strobe, active low *(inferred)*. Both then branch on GPIO 26, `ROSCS`:
high, the access is to the ROM area and the ROM slot and boot MEM apply;
low, it is to the dock and the DOCK slot and dock MEM apply *(inferred
from which half of each word the branches drive)*. `main.py` pulls it
down, so with no 2068 driving it the Pico sees "dock". On a ROM-area
access `set_ctrl` also reads the 2-bit code on GPIO 0–1 and only answers
for codes 0 and 1 (driving /BE low and A14_L high or low respectively);
on codes 2 and 3 it leaves every line idle and the access is somebody
else's. The cycle-by-cycle account is [firmware/pio.md](firmware/pio.md).

The unused `set_dck` program is the "DCK access and no ROM mapping"
variant: it answers only dock accesses, for a board where the 2068 keeps
its own ROMs.

## Clocks

| Clock | Value | Set by | Why |
|---|---|---|---|
| CPU (both cores) | 270 MHz | `freq(270_000_000)` in both `main.py`s; printed at boot | not stated beyond the PIO rate below. The RP2040's rated maximum is 133 MHz (datasheet); the audit lists "270 MHz" with the PIO settle delays as "bus timing, logic analyser only; leave them" (§4) |
| the bus state machine (MQ, running TS_IO_DUAL) | 30 MHz | `StateMachine(0, …, freq=30_000_000)` | the dual-port decode added ~7 cycles to the read path over the single-port program's 15 MHz; 30 MHz "keeps the total under the Z80's data setup window with margin" (`TS_IO_DUAL`'s docstring, `ACTIVATE_MQ`'s comment). A cycle is 33 ns; a read is answered in 9 cycles *(computed, unverified)* |
| the memory state machines (ROM and BANK) | 150 MHz | `StateMachine(4/5, …, freq=150_000_000)` | not stated. A cycle is 6.7 ns; the ROM path's enables follow the strobe by up to 22 cycles *(computed, unverified)*. This exceeds the "half the system clock" the `TS_IO_DUAL` docstring gives as the PIO's limit; the datasheet's divider goes down to 1, so the code, not the comment, is right |
| the parked bus state machine (NULL_SM) | 15 MHz | `ACTIVATE_SD` | the old single-port rate; irrelevant for a `nop` |
| SPI0 | 100 kHz, then 5 MHz | `sdcard.py` | the SD initialisation sequence needs a slow clock; 5 MHz kept by the audit (§5) |

The Z80 side is not in the code. What it imposes is in
[PROTOCOL.md](../PROTOCOL.md) §3.3: an `OUT` every ~30 µs inside a block,
an `IN` every ~44–50 µs, no handshake, so four FIFO entries are ~120 µs
of slack on receive and ~190 µs on send (`STREAM_DMA`'s docstring).

## The two cores

Core 0 runs `main.py`, `TS2068_IO` and every handler: all bus traffic,
all SD work, all command processing. Core 1 runs exactly two things,
both started with `_thread.start_new_thread`:

- `BLINK_LED(0.9)` during the SD mount at boot, stopped with `dead =
  True` and waited for with `while busy` (safe unbounded, as the comment
  argues: it only sleeps and toggles);
- `SAVE_LOG`, the log flush, started from the idle loop when there are
  entries and core 1 is free.

`busy` is the flag that says core 1 is at work. The reason it matters is
the flash: a write to the Pico's own flash stops **both** cores while a
sector programs, and a Z80 streaming a block or a pre-header into a
4-deep FIFO does not stop with them. So every transfer waits, bounded, for
core 1 first (`WAIT_CORE1`; [PROTOCOL.md](../PROTOCOL.md) §13, "Wait for
core1 before starting a transfer"), and `COPY_FILE` waits before writing
the flash itself. A second `start_new_thread` while core 1 has not
returned raises `OSError("core1 in use")`; the idle loop sets `busy`
before the spawn and clears it on that error. The core-1 watchdog
(`CHK_STATUS`) that once policed transfers was removed in issue #51; the
flags it left were removed by the audit (§3). See
[firmware/tspico-files.md](firmware/tspico-files.md) for `SAVE_LOG` and
[firmware/tspico-state.md](firmware/tspico-state.md) for `busy` and
`dead`.

## DMA

On MicroPython v1.22 and later (`rp2.DMA`), three uses of the RP2040's DMA
move bytes between RAM and the bus state machine's FIFOs without core 0's
help, paced by the state machine's own data requests: DREQ 0 (PIO0, state
machine 0, TX) and DREQ 4 (PIO0 SM0 RX). All are in
[firmware/tspico_io.md](firmware/tspico_io.md):

| Use | Channel | Direction | Transfer | Why |
|---|---|---|---|---|
| the pre-header capture (RxDMA, held in RXD) | claimed at boot, kept; armed while idle | RX FIFO → `pre_raw` | 10 × 32-bit words | the first command after a 2068 power-on lost a pre-header byte to a core-0 pause (hardware, 2026-10-02) |
| the block and body capture (RX_RING on the _ring channel) | claimed at import, kept | RX FIFO → a 4096-byte ring | 32-bit words, write address wrapping | the blocks and bodies, taken with the same contract as `RX_CAPTURE` |
| the LOAD send (STREAM_DMA) | claimed per call, closed in `finally` | RAM → TX FIFO | bytes; the FIFO register repeats a byte across the word | the ROMs read a LOAD block blind; 0 dry reads under every stall, against 104–1498 for a Python loop (hardware, 2026-10-03) |

Where `rp2.DMA` is missing (v1.20, the host tests) or no channel is free,
every path falls back to the polling loops. The channel must be running
before the Z80 reads blind: setting one up takes a few hundred
microseconds on v1.29.

## The PIO budget

Two PIO blocks of 32 instruction slots each. PIO0 holds `TS_IO_DUAL` (20)
and `NULL_SM` (1); PIO1 holds `set_ctrl` (22) and `sel_bank` (9), one slot
from full. State machine 0 is `MQ`; 4 and 5 are `ROM` and `BANK`. The
counts and what they imply are in
[firmware/pio.md](firmware/pio.md#the-instruction-budget).

## The LED

GPIO 25, the Pico's own LED, is the only indicator. Its patterns, from the
code; the user manual's table (ch. 2.3) describes the same ones:

| Pattern | Code | When |
|---|---|---|
| 0.9 s on, 0.9 s off | `BLINK_LED(0.9)` on core 1 | boot, while the SD card mounts |
| off | `led.value(0)` at the end of `TS2068_IO`'s setup | from the first prompt |
| one 0.1 s flash every 2 s | the idle loop's heartbeat | idle with a card |
| two flashes (0.1 s, 0.15 s gap, 0.1 s) every 2 s | the same, `not TSP.sd_present` | idle without a card |
| steady on | `led.value(1)` at the start of a SAVE, a LOAD (`LOAD_TS`, `LOAD_ZX`, `LOAD_ZX_C`) and most command handlers; off at their end | a transaction in progress |
| flicker, one toggle per 7.5 KB | `COPY_FILE` | a mounted file being copied to the Pico's flash |
| about a second of fast blinks (10 toggles 0.1 s apart) | `BLINK_ERROR` | a mount or copy that failed |
| off, then on and off around each block | `ZX48_IO` | Spectrum mode |

The idle heartbeat is the one the user sees most, and "LED stopped
blinking" has been the symptom of every hang that dropped core 0 out of
the idle loop ([DEVELOPER_GUIDE.md](../DEVELOPER_GUIDE.md) §11).

## Stated and inferred

For the editor and the next board revision, the two lists apart.

**Stated by the code** (a name, a comment or a constant): GPIO 2–9 are
D0–D7 through U6 and GPIO 2–4 are the SD card's SCK/MOSI/MISO; GPIO 10 is
A0; GPIO 11 is R/W, high for a Z80 OUT; GPIO 12 is `U6_EN`, active low;
GPIO 14 is `/PICOSEL` to the PIO and `WAIT` to `main.py`; GPIO 15–18 are
"A15..A18"; GPIO 19 is `U10_ENA`, 20 `U13_ENA`, 21 `BE`, 26 `ROSCS`, 27
`U10_WE`, 28 `U3_CS`; the `set_ctrl` header names "/BE, A14_L" and
`U10_ENA`, `U13_ENA` (before #181, "/U10_CE /U10_OE"); U3 is on the 3V3 rail with a 4K7 pull-up on nCS; the flash is
512K in 16 slots of 32K and a DCK takes two; the clocks are 270, 30, 150,
15 MHz and 5 MHz; D6 is GPIO 8; there is no /WAIT line; port 0Ah is not
decoded.

**Inferred here** (from how the pins are used): U10 is the flash and U13
the SRAM; the enables are active low; GPIO 13 is an active-low access
strobe; ROSCS high means a ROM-area access; GPIO 22 is the A14_L of the
comment; the 2-bit code on GPIO 0–1 is the 2068's bank selection for the
chunk; GPIO 11 is a decoded direction signal; GPIO 27 is only held
inactive by the Pico; "page" and "slot" are synonyms.

**Only hardware can settle** *(unverified)*: how GPIO 14 is read low while
`main.py` drives it high; how U6 and the PIO's output drivers share GPIO
2–9 during a Z80 OUT; what /BE enables; how a 64K cartridge's upper half is
addressed; what the 2068 reads on 0Fh while U6 is off; every cycle count
in [firmware/pio.md](firmware/pio.md) and whether the settle delays are
needed; whether the GPIO 2–4 clamp does anything.
