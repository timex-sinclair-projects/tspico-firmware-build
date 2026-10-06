# The PIO programs

Source: [`src/TS/tspico_io.py`](../../../src/TS/tspico_io.py) (`sel_bank`,
`set_ctrl`, `set_dck`, `TS_IO_DUAL`) and
[`src/TS/tspico.py`](../../../src/TS/tspico.py) (`NULL_SM`).

Five programs run on the RP2040's programmable I/O. Four of them stand
between the Z80 and the Pico's memory and ports, and are the only code that
reacts within a Z80 bus cycle; MicroPython is far too slow for that. The
fifth, `NULL_SM`, does nothing, and that is its job. Three state machines
run them: `MQ` (PIO0, state machine 0) runs `TS_IO_DUAL` and answers the two
ports 0Eh and 0Fh; `ROM` (state machine 4) runs `set_ctrl` and drives the
memory enables; `BANK` (state machine 5) runs `sel_bank` and drives the bank
address lines. `set_dck` is an alternative for `ROM` that the shipped
firmware does not use. The wiring the programs assume is in
[hardware.md](../hardware.md); the Python that builds and drives the state
machines is in [tspico-bus.md](tspico-bus.md) (`ACTIVATE_MQ`, `ACTIVATE_SD`,
`MQ_READY`, `MQ_BUSY`) and [tspico_io.md](tspico_io.md) (`MQX`, `MQ_STATUS`,
`ENA_MQ_DUAL`); the wire protocol they serve is
[PROTOCOL.md](../../PROTOCOL.md) §1–3.

The programs are read here instruction by instruction. Cycle counts and
nanoseconds computed in this chapter come from the instruction listings and
the clock each state machine is given; none has been measured, and the
2026-09-30 audit left the settle delays as "a logic-analyser job"
([AUDIT-2026-09-30.md](../../AUDIT-2026-09-30.md) §4). Every such number is
marked *(unverified)*.

## Map

1. [PIO on the RP2040, as these programs use it](#pio-on-the-rp2040-as-these-programs-use-it)
2. [`sel_bank`](#sel_bank): the bank address lines A15–A18
3. [`set_ctrl`](#set_ctrl): the memory enables, /BE and A14_L
4. [`set_dck`](#set_dck): the unused DOCK-only alternative
5. [`TS_IO_DUAL`](#ts_io_dual): the two Z80 ports
6. [`NULL_SM`](#null_sm): the parked bus
7. [The instruction budget](#the-instruction-budget)

## PIO on the RP2040, as these programs use it

What follows is from the RP2040 datasheet, chapter 3, which
[PROTOCOL.md](../../PROTOCOL.md) §15 lists as further reading; it is the
ground the programs stand on, not something the code states.

- The chip has two PIO blocks, each with four state machines and **32
  instruction slots** shared by the programs loaded into that block.
  MicroPython numbers the state machines 0–7: 0–3 are PIO0, 4–7 are PIO1.
  So `MQ` (state machine 0) is PIO0, which `MQX` relies on when it writes
  PIO0's registers directly, and `ROM` and `BANK` (4 and 5) are PIO1.
- Each state machine has a **TX FIFO and an RX FIFO of four 32-bit words**.
  `fifo_join` can merge them into one eight-deep FIFO in one direction; none
  of these programs does, so `TX_DEPTH` is 4 and so is RX
  ([PROTOCOL.md](../../PROTOCOL.md) §1).
- Four registers: **X** and **Y**, 32-bit scratch; the **OSR** (output
  shift register), filled from TX by `pull` and emptied by `out`; the
  **ISR** (input shift register), filled by `in_` and emptied into RX by
  `push`. `out_shiftdir=PIO.SHIFT_RIGHT` makes `out(dst, n)` take the n
  low bits of the OSR; `in_shiftdir=PIO.SHIFT_LEFT` makes `in_(pins, n)`
  shift the ISR up and put the n pins in its low bits, pin `in_base` at
  bit 0.
- `pull(noblock)` on an empty TX FIFO copies **X** into the OSR instead of
  stalling. `push(noblock)` on a full RX FIFO drops the word. Both matter
  here: see [why `pull(noblock)`](#why-pullnoblock-and-pushnoblock).
- `wait(level, gpio, n)` stalls until GPIO n is at the level. `jmp(pin,
  label)` jumps when the state machine's one configured `jmp_pin` is high.
  `jmp(not_x, …)` tests X for zero; `jmp(y_dec, …)` jumps if Y is non-zero
  and decrements it either way. GPIO inputs pass through a two-cycle
  synchroniser before the state machine sees them.
- A **side-set** writes extra pins on the same cycle as the instruction. A
  **delay** `[n]` idles n cycles *after* the instruction has executed, not
  before.
- `StateMachine.exec("…")` writes one encoded instruction into the state
  machine's INSTR register; it executes on the next cycle, even if the
  program is stalled on a `wait`, which then resumes. The firmware's
  `MQX` does the same write by hand, because `exec()` on MicroPython v1.20
  re-ran the assembler every call (9.6 ms against 18 µs, measured
  2026-09-27; see [tspico_io.md](tspico_io.md)).
- Restarting a state machine (what `StateMachine(...)` does when it is
  rebuilt) clears the ISR and the shift counters but **not X, Y or the
  OSR**. The firmware found this out for Y: a rebuilt `MQ` inherits
  whatever Y the last program left, so `ACTIVATE_MQ` says BUSY explicitly
  (audit §4, [tspico-bus.md](tspico-bus.md)).

The decorator `@asm_pio(...)` fixes, per program, the pin counts and their
initial state and direction (`out_init`, `set_init`, `sideset_init`), the
shift directions, and whether the OSR refills itself (`autopull`,
`pull_thresh`). Which GPIOs those pins are is decided when the
`StateMachine` is built (`out_base`, `set_base`, `in_base`, `sideset_base`,
`jmp_pin`); the programs reference them only by position.

## `sel_bank`

Selects which 32K slot of the flash or SRAM an access goes to, by driving
the chips' address lines A15–A18 from a 4-bit slot number: the ROM slot for
a ROM-area access, the DOCK slot for a cartridge access. Runs on `BANK`
(state machine 5, PIO1) at 150 MHz with `out_base=Pin(15)` and
`jmp_pin=Pin(26)`; built in `TS2068_IO` and in
[`src/upgrade/main.py`](../../../src/upgrade/main.py).

### Configuration

| Setting | Value | Effect |
|---|---|---|
| out_init | `(PIO.OUT_LOW,) * 4` | four out pins, GPIO 15–18, outputs, starting low (slot 0) |
| out_shiftdir | `SHIFT_RIGHT` | `out(pins, 4)` drives the four low bits of the OSR, bit 0 to GPIO 15 |
| autopull, pull_thresh | `True`, 8 | the OSR would refill itself after 8 bits; the program pulls by hand every pass, so this never shows *(inferred)* |

No side-set, no set pins, no in pins.

### The word

`BANK.put(TSP.bank_sm)` queues one word. `bank_sm = DCK_SLOT * 16 +
ROM_SLOT` (`PICO_STATUS.__init__`, [tspico-state.md](tspico-state.md)):

| Bits | Meaning | Driven when |
|---|---|---|
| 0–3 | `ROM_SLOT`, 0–15: the slot the 2068 boots from (default 1) | the jump pin (ROSCS, GPIO 26) is high |
| 4–7 | `DCK_SLOT`, 0–15: the slot in the dock (default 0) | ROSCS is low |
| 8–31 | ignored: never shifted out before the next pull | — |

Bit 0 of the driven nibble lands on GPIO 15 (A15), bit 3 on GPIO 18 (A18).
The default word is therefore 1 (dock 0, ROM 1). The comment on `bank_sm`
in `PICO_STATUS` says "Default 0001 0000"; that is 16, and the code
computes 1. The code wins.

### The instructions

9 instructions, no side-set, no delays. One pass serves one memory access.

| # | Instruction | Does |
|---|---|---|
| 1 | `pull(noblock)` | OSR = the next word from TX if there is one, else X. X holds the word of the last pass, so a word put once stays in force for every access until the next `put()` |
| 2 | `mov(x, osr)` | X = the word, for the next pass |
| 3 | `wait(0, gpio, 13)` | stall until the memory-access strobe (GPIO 13, active low) falls. The program spends almost all its time here |
| 4 | `jmp(pin, "low")` | ROSCS (GPIO 26) high: a ROM-area access, go to 8 |
| 5 | `out(null, 4)` | ROSCS low: a DOCK access. Discard bits 0–3 (the ROM slot) |
| 6 | `out(pins, 4)` | drive bits 4–7 (the DOCK slot) onto GPIO 15–18 |
| 7 | `jmp("fin")` | |
| 8 | `out(pins, 4)` | label `low`: drive bits 0–3 (the ROM slot) onto GPIO 15–18 |
| 9 | `wait(1, gpio, 13)` | label `fin`: stall until the strobe rises, then wrap to 1 |

The label `low` is taken when the jump pin is *high*; the label names in
this program and in `set_ctrl` do not describe the pin level.

### Timing

At 150 MHz a cycle is 6.67 ns. From the cycle in which the strobe is seen
low, the DOCK slot is on the pins after instructions 4–6, three cycles
(20 ns); the ROM slot after 4 and 8, two cycles (13 ns). The synchroniser
adds about two cycles before the low is seen. *(unverified: computed from
the listing)*. The lines are **not** released when the strobe rises: they
hold the last slot until the next access changes it.

### State and contracts

- X: the current word. Y: unused. ISR: unused. OSR: the current word,
  partly shifted.
- TX FIFO: holds words from `put()` until the state machine's next pass
  consumes one; the firmware puts one word at a time (`TS2068_IO` at boot,
  `MEMBOOT`, `MEMDOCK`), and the 2068 accesses its ROM continuously, so the
  FIFO is empty again within a bus cycle. A new word takes effect on the
  access after the one in progress: the pass that is stalled at 3 already
  has the old word in X and the OSR *(inferred from the instruction order)*.
- Until the first `put()`, X is whatever the register held, 0 after
  power-up: slot 0 for both *(inferred)*. `TS2068_IO` puts `bank_sm`
  straight after `BANK.active(1)`.

### Beware

- The four slot bits select among sixteen 32K slots. A 64K cartridge (two
  slots) is addressed with an even `DCK_SLOT`; how the Z80's own A15 reaches
  the chip for the cartridge's upper half is not visible in the code
  *(unverified)*. See [hardware.md](../hardware.md).
- `put()` blocks when the TX FIFO holds four words. That cannot happen while
  the 2068 is running, and nothing in the firmware puts more than one word
  per command.

## `set_ctrl`

Drives the lines that let the Pico's flash or SRAM answer a 2068 memory
access: the two chip enables (GPIO 19, 20), /BE and A14_L (GPIO 21, 22).
Chooses flash or SRAM separately for the ROM area and for the dock, from
one word, and for a ROM-area access reads a 2-bit code on GPIO 0–1 that
decides whether the Pico answers at all and what A14_L should be. Runs on
`ROM` (state machine 4, PIO1) at 150 MHz with `in_base=Pin(0)`,
`jmp_pin=Pin(26)`, `set_base=Pin(21)`, `out_base=Pin(19)`.

The header comment calls the four lines "/BE, A14_L, /U10_CE /U10_OE".
[`src/main.py`](../../../src/main.py) names GPIO 19 `U10_ENA` and GPIO 20
`U13_ENA`, one enable per chip, and the bit patterns below only make sense
that way (a MEM value of 2 drives GPIO 19 low and GPIO 20 high; the two
pins are never both low for a valid word). This chapter follows the pin
names and the bit patterns; the "/U10_CE /U10_OE" wording is taken as
stale.

### Configuration

| Setting | Value | Effect |
|---|---|---|
| set_init | `(PIO.OUT_HIGH,) * 2` | two set pins, GPIO 21 (/BE) and 22 (A14_L), outputs, starting high |
| in_shiftdir | `SHIFT_LEFT` | `in_(pins, 2)` puts GPIO 0 in ISR bit 0 and GPIO 1 in bit 1 |
| out_init | `(PIO.OUT_HIGH,) * 2` | two out pins, GPIO 19 and 20, outputs, starting high: both chips disabled, so the enables are active low *(inferred from the idle level)* |
| out_shiftdir | `SHIFT_RIGHT` | `out(pins, 2)` drives OSR bits 0–1, bit 0 to GPIO 19 |
| autopull, pull_thresh | `True`, 8 | as in `sel_bank`: inert *(inferred)* |

No side-set.

### The word

`ROM.put(TSP.ROM_SM)`. `ROM_SM = dock MEM * 4 + boot MEM`, where MEM is 1
for SRAM and 2 for flash (`LOAD_CONFIG`, [tspico-dispatch.md](tspico-dispatch.md));
the only valid values are 5, 6, 9 and 10, and the default is 10, both from
flash.

| Bits | Meaning | Driven when |
|---|---|---|
| 0–1 | boot MEM: 01 = SRAM, 10 = flash | ROSCS high and the GPIO 0–1 code is 0 or 1 |
| 2–3 | dock MEM, same encoding | ROSCS low |
| 4–31 | ignored | — |

Bit 0 of the driven pair goes to GPIO 19 (`U10_ENA`), bit 1 to GPIO 20
(`U13_ENA`), low = enabled. So MEM 2 enables U10 and MEM 1 enables U13: U10
is the flash, U13 the SRAM *(inferred; consistent with `U10_WE`, the flash
write-enable line of the P10 jumper, see [hardware.md](../hardware.md))*.

### The instructions

22 instructions, no side-set, two delays.

| # | Instruction | Does |
|---|---|---|
| 1 | `mov(pins, invert(null))` | out pins = 11: both chips disabled. Runs at the top of every pass, so this is also how an access is ended |
| 2 | `mov(y, null)` | Y = 0 |
| 3 | `set(pins, 3)` | set pins = 11: /BE high, A14_L high |
| 4 | `pull(noblock)` | OSR = a new word from TX, or X (the last word) |
| 5 | `mov(x, osr)` | keep it in X |
| 6 | `wait(0, gpio, 13)` | stall until the access strobe falls |
| 7 | `nop() [2]` | three cycles of settling before the jump pin is tested |
| 8 | `jmp(pin, "low")` | ROSCS high: ROM-area access, go to 12 |
| 9 | `out(null, 2)` | ROSCS low: DOCK access. Discard the boot MEM bits |
| 10 | `out(pins, 2)` | drive the dock MEM bits onto the enables |
| 11 | `jmp("pass")` | done: /BE and A14_L stay high for a DOCK access |
| 12 | `in_(pins, 2)` | label `low`: ISR = GPIO 1:0, a code 0–3. The ISR is 0 beforehand (14 cleared it, or the restart did) |
| 13 | `mov(y, isr)` | Y = the code |
| 14 | `mov(isr, null)` | clear the ISR for the next pass |
| 15 | `jmp(y_dec, "home")` | code 0: fall through. Code 1–3: Y becomes code − 1, go to 18 |
| 16 | `set(pins, 2)` | code 0: /BE low, A14_L high |
| 17 | `jmp("wait")` | |
| 18 | `jmp(y_dec, "pass")` | label `home`. Code 2 or 3 (Y was 1 or 2): go to 22, driving nothing: the Pico does not answer this access. Code 1 (Y was 0): fall through |
| 19 | `set(pins, 0)` | code 1: /BE low, A14_L low |
| 20 | `nop() [10]` | label `wait`: eleven cycles between /BE falling and the chip enable |
| 21 | `out(pins, 2)` | drive the boot MEM bits onto the enables |
| 22 | `wait(1, gpio, 13)` | label `pass`: stall until the strobe rises, then wrap to 1 |

So the 2-bit code on GPIO 0–1 means: 0 and 1, "this ROM-area access is
ours", with A14_L = 1 for code 0 and A14_L = 0 for code 1; 2 and 3, "not
ours". What the two bits are on the board is not named in the code. A 32K
slot holds a HOME ROM at offset 0 and an EXROM at offset 4000h
([`tools/build-rom.py`](../../../tools/build-rom.py)), and A14 is the
address bit that separates those halves, so the code plausibly tells HOME
from EXROM from "neither" in the 2068's bank selection *(inferred)*.

### Timing

At 150 MHz, from the cycle in which the strobe is seen low *(all
unverified: computed from the listing)*:

- DOCK access: enables driven after 7, 8, 9, 10: 6 cycles, 40 ns.
- ROM access, code 0: /BE and A14_L after 7, 8, 12–16: 9 cycles, 60 ns;
  enables after 17, 20, 21: 22 cycles, 147 ns.
- ROM access, code 1: /BE and A14_L after 10 cycles, 67 ns; enables after
  22 cycles, 147 ns.
- Release: the enables go high one cycle after the strobe is seen high
  (instruction 1); /BE and A14_L two cycles later (3).

The two delays are the "PIO settle delays" the audit chose to leave alone;
the code does not say what they were sized against.

### State and contracts

- X: the current word. Y: the code, consumed by the two `y_dec` jumps.
  ISR: the code, cleared each ROM pass. OSR: the word, partly shifted.
- TX FIFO: as `sel_bank`; a word takes effect from the access after the
  one in progress *(inferred)*.
- Before the first `put()`, with X = 0 after power-up, a ROM-area access
  with code 0 or 1 drives 00 onto both enables, enabling both chips at once
  *(inferred)*. `TS2068_IO` puts `ROM_SM` straight after building `BANK`,
  a few instructions after `ROM.active(1)`.

### Beware

- With 22 instructions here and 9 in `sel_bank`, PIO1 has one free slot.
  Adding an instruction to `set_ctrl` needs one removed elsewhere, or
  `sel_bank` moved to PIO0.
- `MEMBOOT` sleeps 0.1 s between the reply and `ROM.put`, because the Z80
  is still finishing the statement in the old ROM when the word changes
  (audit §4 kept it). The switch is immediate at the state machine: the
  next ROM-area access after the pass in progress reads from the new chip.

## `set_dck`

The alternative `ROM` program for a board where the 2068 keeps its own
ROMs and the Pico only supplies the dock: it drives the two chip enables on
a DOCK access and nothing else. `TS2068_IO` has it commented out ("for DCK
access and no ROM mapping"); nothing in the shipped firmware runs it.

### Configuration

`out_init=(PIO.OUT_HIGH,) * 2`, `out_shiftdir=SHIFT_RIGHT`, `autopull=True`,
`pull_thresh=8`: the enables as in `set_ctrl`, no set pins, no in pins.
Built, when it was, with `jmp_pin=Pin(26)` and `out_base=Pin(19)` only.

### The instructions

10 instructions.

| # | Instruction | Does |
|---|---|---|
| 1 | `mov(pins, invert(null))` | both enables high |
| 2 | `pull(noblock)` | OSR = new word, or X |
| 3 | `mov(x, osr)` | keep it |
| 4 | `wait(0, gpio, 13)` | the strobe falls |
| 5 | `nop() [2]` | three cycles of settling |
| 6 | `jmp(pin, "pass")` | ROSCS high: a ROM-area access, not ours |
| 7 | `out(null, 2)` | ROSCS low: discard the boot MEM bits |
| 8 | `out(pins, 2)` | drive the dock MEM bits |
| 9 | `jmp("pass")` | falls through to the next instruction anyway |
| 10 | `wait(1, gpio, 13)` | label `pass`: the strobe rises |

The word is the same `ROM_SM`; only bits 2–3 are ever driven. Instruction 9
jumps to the instruction that follows it and could be dropped.

## `TS_IO_DUAL`

The bus state machine: answers every Z80 `IN` and `OUT` on ports 0Eh and
0Fh. A Z80 read of 0Eh gets the next byte of the TX FIFO; a read of 0Fh
gets the low byte of **Y**, the status; a write to either port lands in the
RX FIFO as a 9-bit word whose bit 8 is A0, and drops Y to 0 (BUSY). It is
the hardware half of the protocol in [PROTOCOL.md](../../PROTOCOL.md) §1–3
and of the "ready contract" in
[DEVELOPER_GUIDE.md](../../DEVELOPER_GUIDE.md) §7. Its docstring and the
comments are the most complete explanation in the source; the development
history is [DUAL_PORT_DEVELOPMENT.md](../../DUAL_PORT_DEVELOPMENT.md) §2–3.

Runs on `MQ` (state machine 0, PIO0) at 30 MHz with `out_base=Pin(2,
Pin.OUT)`, `in_base=Pin(2, Pin.IN)`, `jmp_pin=Pin(11)`,
`sideset_base=Pin(12, Pin.OUT)`. It is built in four places with those
same arguments: `ACTIVATE_MQ` ([tspico-bus.md](tspico-bus.md)) for the
2068 dispatcher, after every SD access; `ENA_MQ_DUAL`
([tspico_io.md](tspico_io.md)) for the ZX48 handlers after `ENA_SD`;
`ZX48_IO` ([tspico-dispatch.md](tspico-dispatch.md)) on entering Spectrum
mode; and [`src/upgrade/main.py`](../../../src/upgrade/main.py). The
single-port predecessor `TS_IO` ran at 15 MHz; the 30 MHz is explained in
`ACTIVATE_MQ`'s comment: the dual-port decode adds about seven cycles to
the read path.

### Configuration

| Setting | Value | Effect |
|---|---|---|
| sideset_init | `(PIO.OUT_HIGH)` | one side-set pin, GPIO 12, the U6 bus-buffer enable, output, starting high (U6 off). With one non-optional side-set bit every instruction must carry `.side()`, and every one does |
| out_init | `(PIO.OUT_LOW,) * 8` | eight out pins, GPIO 2–9 = D0–D7, outputs, starting low |
| out_shiftdir | `SHIFT_RIGHT` | `out(pins, 8)` drives OSR bits 0–7 onto D0–D7; `out(null, 8)` discards bits 0–7 |
| in_shiftdir | `SHIFT_LEFT` | `in_(pins, 9)` puts GPIO 2–10 in ISR bits 0–8: D0–D7 and A0 |

No `autopull` and no `autopush`: every FIFO transfer is an explicit
`pull(noblock)` or `push(noblock)`. No `fifo_join`: four words each way.
The in pins start at GPIO 2 like the out pins, which is why A0 (GPIO 10)
comes in as bit 8 of a 9-pin sample rather than on its own.

The data pins are outputs from the moment the state machine is built and
nothing in the program changes their direction (there is no
`out(pindirs)`). On a Z80 write the state machine samples pins it is itself
driving; how U6 and the Pico's drivers share them during that cycle is a
board matter the code does not show *(unverified)*.

### The instructions

20 instructions; every one sets GPIO 12 through `.side()`: `.side(1)` U6
off, `.side(0)` U6 on. The docstring's "Total: 19 instructions of 32
available" predates the issue-#14 `mov(y, null)`; the comment on that
instruction has the right count, 20.

| # | Instruction | Side | Does |
|---|---|---|---|
| 1 | `wait(0, gpio, 14)` | 1 | idle: stall until /PICOSEL falls. U6 is off, the Pico is off the bus |
| 2 | `jmp(pin, "z80_out")` | 1 | GPIO 11 (R/W) high: the Z80 is writing, go to 15 |
| 3 | `in_(pins, 9)` | 0 | the Z80 is reading. ISR bits 0–8 = D0–D7, A0. U6 goes on |
| 4 | `mov(osr, isr)` | 0 | copy to the OSR so that `out` can shift it |
| 5 | `mov(isr, null)` | 0 | clear the ISR. Not only hygiene: the next write's `in_(pins, 9)` would otherwise shift these nine bits up and the pushed word would carry them above bit 8 |
| 6 | `out(null, 8)` | 0 | discard D0–D7 |
| 7 | `out(x, 1)` | 0 | X = A0 |
| 8 | `jmp(not_x, "rd_data")` | 0 | A0 = 0: port 0Eh, go to 12 |
| 9 | `mov(osr, y)` | 0 | port 0Fh: OSR = Y |
| 10 | `out(pins, 8)` | 0 | drive Y's low byte onto D0–D7: the status |
| 11 | `jmp("fin")` | 0 | |
| 12 | `pull(noblock)` | 0 | label `rd_data`: OSR = next TX word, or X (= 0, A0) if TX is empty |
| 13 | `out(pins, 8)` | 0 | drive its low byte: the data, or 00h |
| 14 | `jmp("fin")` | 0 | |
| 15 | `nop()` | 0 | label `z80_out`: one cycle of settling. U6 goes on |
| 16 | `in_(pins, 9) [2]` | 0 | sample D0–D7 and A0, then idle two cycles |
| 17 | `push(noblock)` | 0 | ISR → RX FIFO as one word; dropped if RX is full |
| 18 | `mov(y, null)` | 0 | Y = 0: BUSY (issue #14) |
| 19 | `wait(1, gpio, 14)` | 0 | label `fin`: stall until /PICOSEL rises |
| 20 | `mov(null, osr)` | 1 | U6 off. The comment says "consume OSR (cleanup)"; a move to `null` leaves the OSR as it was. The instruction's effect is its side-set; the OSR is reloaded by 4, 9 or 12 before it is used again |

Three instructions (4, 6, 7) exist only to get A0 out of the ISR: PIO can
branch on the jump pin, on X or on Y, but not on a bit of the ISR or on an
arbitrary GPIO, so A0 is sampled with the data, moved to the OSR, and
shifted into X *(inferred from the instruction set)*.

The comment on 16 says the `[2]` "adds 2 extra cycles to ensure the Z80's
data is stable before we latch it". By the datasheet a delay follows its
instruction: the sample is taken when 16 begins, and the two cycles idle
afterwards, delaying the push and the BUSY. The settling before the sample
is instructions 2 and 15. The effect on the bus is the same either way
(U6 is on from 15); this is one of the settle delays left to a logic
analyser (audit §4).

### Timing

At 30 MHz a cycle is 33.3 ns. From the cycle in which /PICOSEL is seen low
(about two cycles after it falls, the synchroniser) *(all unverified:
computed from the listing)*:

| Cycle | Which | What |
|---|---|---|
| 2 (67 ns) | Z80 IN, either port | U6 on (3); the pins sampled for A0 |
| 9 (300 ns) | Z80 IN 0Eh | data byte driven (13) |
| 9 (300 ns) | Z80 IN 0Fh | status byte driven (10) |
| 2 (67 ns) | Z80 OUT | U6 on (15) |
| 3 (100 ns) | Z80 OUT | D0–D7 and A0 sampled (16) |
| 6 (200 ns) | Z80 OUT | word in RX (17) |
| 7 (233 ns) | Z80 OUT | Y = 0 (18) |
| +1 after /PICOSEL high | both | U6 off (20) |

The docstring calls 30 MHz "conservative" against "the Z80's data setup
window" without giving the window. The Z80 side paces itself: one `OUT`
every ~30 µs inside a block, one `IN` every ~44–50 µs
([PROTOCOL.md](../../PROTOCOL.md) §3.3), so the state machine is idle for
all but a few hundred nanoseconds of each.

The docstring also says "RP2040 PIO can run up to half the system clock
(135MHz at 270MHz CPU)". The code itself asks for 150 MHz for `ROM` and
`BANK`, and the datasheet's clock divider goes down to 1, the full system
clock; the "half" is not a hardware limit. Treat the sentence as a
rationale for 30 MHz being safe, not as a bound.

### The register contracts

- **X**: A0 of the last Z80 read, 0 or 1. Its only other use is as the
  fallback of `pull(noblock)` at 12, which is reached only when A0 = 0, so
  an empty FIFO reads as 00h. Nothing in Python sets X.
- **Y**: the status byte, bits 0–7 of a 32-bit register. The program only
  reads it (9) and clears it (18). Python writes it with `exec`, below.
  Y survives a rebuild of the state machine, so `ACTIVATE_MQ` clears it
  with `MQ_BUSY()` and `ENA_MQ_DUAL` and `ZX48_IO` set it READY.
- **ISR**: nine bits during a cycle, zero between cycles.
- **OSR**: whatever was last shifted out; reloaded before every use.
- **TX FIFO**: bytes for the Z80 to read on 0Eh, in order, four at most.
  `MQ.put(b)` queues a 32-bit word; only bits 0–7 reach the pins. `MQ.put`
  blocks when the FIFO is full; the DMA path (`STREAM_DMA`,
  [tspico_io.md](tspico_io.md)) feeds the FIFO's register by bytes, which
  the register repeats across the word, paced by DREQ 0 (PIO0 TX0).
- **RX FIFO**: 9-bit words, oldest first, four at most. `MQ.get()` returns
  the word; `w & 0xFF` is the byte, `w & PORT_0F` (0x100) tells a 0Fh
  write from a 0Eh write. `RxDMA` and the ring (`RX_RING`) read the same
  FIFO through DREQ 4 (PIO0 RX0) as 32-bit words.

### Why pull(noblock) and push(noblock)

A blocking `pull` would stall the state machine, not the Z80: the board
does not route a state-machine stall to the Z80's /WAIT line, and a stalled
state machine inside a bus cycle never sees the next /PICOSEL. The
experiment is [DUAL_PORT_DEVELOPMENT.md](../../DUAL_PORT_DEVELOPMENT.md)
§3b: "complete bus freeze". With `noblock`, an unprepared Pico fails
loudly: the Z80 reads 00h, which the ROM reports as J. The contract that
follows, "queue the answer first, then say READY", is
[DEVELOPER_GUIDE.md](../../DEVELOPER_GUIDE.md) §7 and
[PROTOCOL.md](../../PROTOCOL.md) §3.2.

`push(noblock)` is the same choice on the other side: a Z80 that writes
faster than Python drains RX loses bytes rather than hanging the bus. Four
words at ~30 µs a write is ~120 µs of slack; a garbage collection, a USB
interrupt or a flash write exceeds it, which is why the pre-header and the
blocks are now taken by DMA (`RxDMA`, [tspico_io.md](tspico_io.md)) and
why the capture loops do nothing per word (`src/CLAUDE.md`'s two-phase
rule).

### Auto-BUSY after a Z80 OUT

Instruction 18 drops Y to 0 after every write, to either port. Before it
(issue #14), Y stayed at whatever Python last set, and a Z80 that tested
bit 6 right after sending a byte found it still set and read an empty TX
as data; Python could not clear Y fast enough. The rule it imposes on
Python: after any Z80 write, status reads BUSY until `MQ_READY()` or
`MQ_STATUS()` says otherwise, and the answer must be in TX before that
call. The callers that need it are listed in `MQ_READY`'s docstring
([tspico-bus.md](tspico-bus.md)); the design note is
[DEVELOPER_GUIDE.md](../../DEVELOPER_GUIDE.md) §7.

Because 18 is one PIO instruction and the write to 0Fh (SYNC or BREAK in
ROM 2.0) goes through the same path, a 0Fh write also reads BUSY until
Python answers; that is what the ROM's SYNC waits for
([PROTOCOL.md](../../PROTOCOL.md) §4.1).

### How A0 ends up in bit 8 (the PORT_0F mask)

`in_(pins, 9)` at 16 samples GPIO 2–10 into ISR bits 0–8; `push` sends the
whole ISR. GPIO 10 is A0, so a write to 0Fh arrives as `0x100 | value` and
a write to 0Eh as the plain byte. `PORT_0F = const(0x100)` is the mask
([tspico_io.md](tspico_io.md)); `RX_CAPTURE`, `RxDMA.take`, `TX_ROOM`,
`CMD_KEY` and the rest test it. The read path makes the same sample at 3
and keeps only bit 8, as X.

### How Python drives Y

Every status change is one or two instructions written to the state
machine with `MQX(MQ, "…")` (or `MQ.exec` on the host). The exact strings:

| Port 0Fh reads | Y | Instruction(s) | Who |
|---|---|---|---|
| FFh: READY + IDLE | 0xFFFFFFFF | `mov(y, invert(null))` | `MQ_READY()`, `MQ_STATUS(MQ, "idle")`, `ENA_MQ_DUAL`, `ZX48_IO`, `STREAM_DMA(ready=True)`, `SAY_READY`, and the LOAD/SAVE paths directly |
| F7h: READY, transaction open | 0xFFFFFFF7 | `set(y, 8)` then `mov(y, invert(y))` | `MQ_STATUS(MQ, "mid")` |
| FBh: READY + IDLE, RECOVERED | 0xFFFFFFFB | `set(y, 4)` then `mov(y, invert(y))` | `MQ_STATUS(MQ, "recovered")` |
| 00h: BUSY | 0 | `set(y, 0)` | `MQ_BUSY()` |
| 00h: BUSY | 0 | `mov(y, null)` | the program itself, instruction 18, after every Z80 write |

`set` takes a 5-bit immediate, so the two-step form is needed for anything
but small values; between the two steps Y is 8 or 4, bit 6 clear, and a
read in that instant sees BUSY, as `MQ_STATUS`'s docstring says.
`invert(null)` is the spelling that parses in both MicroPython v1.20 and
v1.29 (`~null` does not; `MQ_READY`'s comment). The bit meanings are
[PROTOCOL.md](../../PROTOCOL.md) §3.1.

Two other `MQX` strings touch the FIFOs rather than Y: `MQ_TO_IDLE`,
`ZX_FLUSH_TX`, `CMD_FLUSH`, `FAIL_CMD` and `ZX48_IO` drain TX with
`pull (noblock)` followed by `mov (osr, null)`, one word per pair, bounded
at 64 except in `ZX48_IO`, whose two inline drains (tspico.py 7212, 7256)
loop until TX is empty ([tspico_io.md](tspico_io.md), [tspico-bus.md](tspico-bus.md),
[tspico-dispatch.md](tspico-dispatch.md)). The `pull` moves a word out of
the FIFO into the OSR; the `mov` only tidies the OSR.

An `exec`'d instruction is encoded for the program's side-set layout (that
is what `MQX` caches by: `PINCTRL.SIDESET_COUNT` and `EXECCTRL.SIDE_EN`),
and none of these strings carries a `.side()`, so the side-set field is 0.
If the datasheet's rule that side-set applies to every executed
instruction holds for `INSTR` writes, each `exec` pulls GPIO 12 low, U6
on, for one 33 ns cycle while the program is idle at 1, and the stalled
`wait .side(1)` turns it off again on the next cycle *(inferred;
unverified on hardware)*.

### The ready contract, in the program's terms

The Z80 polls 0Fh for bit 6 before every read of 0Eh that it is allowed to
wait for, and reads a block's data blind, one byte per ~47 µs, trusting the
FIFO ([PROTOCOL.md](../../PROTOCOL.md) §3.3, §6). The state machine
enforces nothing: it serves 0Fh from Y and 0Eh from TX, whatever Python has
done. So:

1. a byte must be in TX before Y says READY, or 12 falls back to X and the
   Z80 reads 00h (Report J);
2. after the Z80's last `OUT` of a phase Y is 0 by 18, and only Python can
   raise it;
3. a blind read that outruns TX reads 00h with no error signalled anywhere;
   the LOAD paths keep TX fed by DMA for that reason.

### State and effects

Builds of `TS_IO_DUAL` replace the program on state machine 0 and set GPIO
2–9 and 12 to PIO0; `ACTIVATE_SD` takes 2–4 and 12 back for the SD card
and parks the state machine on `NULL_SM` meanwhile
([flows/sd-handover.md](../flows/sd-handover.md)). `MQ` is a module global
in `tspico.py`; `tspico_io.py` is handed it as a parameter.

### Beware

- Never `exec` a blocking instruction, and never add `pull(block)` or
  `push(block)` to the program: see above.
- The ZX48 path and the upgrade firmware build the state machine with the
  same arguments and must keep doing so; the pin map is in
  [hardware.md](../hardware.md).
- A rebuilt state machine keeps Y. Say BUSY or READY explicitly after
  every build.
- The Z80 reads 0Fh through U6 like 0Eh. While the SD card has the pins,
  U6 is off and the Pico drives nothing; what the 2068 then reads on 0Fh
  is not determined by this code ([DUAL_PORT_DEVELOPMENT.md](../../DUAL_PORT_DEVELOPMENT.md)
  §1 reports a pull-up on D6 on the 2068 side) *(unverified)*.

## `NULL_SM`

A one-instruction program, `nop()`, that `ACTIVATE_SD` loads onto state
machine 0 before giving GPIO 2–4 to the SD card's SPI:

```python
MQ = StateMachine(0, NULL_SM, freq=15_000_000)
MQ.active(1)
MQ.active(0)
```

Loading it ends `TS_IO_DUAL`: with the bus program gone, no Z80 cycle can
make the state machine drive D0–D7 or switch U6 while the card is on the
same pins, and `MQ` stays a valid `StateMachine` object for any code that
touches it in between. The pair `active(1)`, `active(0)` runs it and stops
it at once; the code does not say why it is started at all, and a stopped
state machine would serve the purpose *(inferred)*. The decorator's
`autopull=True, pull_thresh=8` are copied from the bank programs and do
nothing here: the program never executes an `out`. 15 MHz was the
single-port `TS_IO` rate; for a `nop` the rate is immaterial.

Who uses it: only `ACTIVATE_SD` ([tspico-bus.md](tspico-bus.md)), on every
mount. `sd_active` ([tspico-state.md](tspico-state.md)) records that `MQ`
is parked, and `FAIL_CMD` rebuilds the bus before answering if a handler
died while it was.

Beware: anything `put()` to the parked state machine never reaches the Z80,
and after four words `put()` blocks for good, since nothing pulls from the
FIFO (`FAIL_CMD`'s comment; the blocking is *inferred* from the FIFO
depth). Restore the bus with `DEACTIVATE_SD()` then `ACTIVATE_MQ()` first.

## The instruction budget

Counted from the listings above.

| PIO block | State machine | Program | Instructions | Clock |
|---|---|---|---|---|
| PIO0 | 0 (`MQ`) | `TS_IO_DUAL` | 20 | 30 MHz |
| PIO0 | 0 (`MQ`, during SD access) | `NULL_SM` | 1 | 15 MHz |
| PIO1 | 4 (`ROM`) | `set_ctrl` | 22 | 150 MHz |
| PIO1 | 5 (`BANK`) | `sel_bank` | 9 | 150 MHz |
| PIO1, alternative | 4 (`ROM`) | `set_dck` | 10 | 150 MHz |

PIO0 holds 21 of 32 slots, PIO1 31 of 32. MicroPython adds a program to a
block once and keeps it there across rebuilds of the state machine, which
is why `ACTIVATE_MQ` can rebuild `MQ` on every SD access without exhausting
PIO0 *(inferred from the firmware running for a whole session)*. The
single-port `TS_IO` the audit mentions (§3, "kept on purpose as a
reference") is no longer in the file. State machines 4 and 5 are the ROM
and bank machines; harnesses that build their own state machines must not
take them while a 2068 is attached.
