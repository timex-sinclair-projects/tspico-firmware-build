# The TS-Pico ecosystem on one page

Source: the whole of [`src/`](../../src/), summarised. Part of the
[programmer's reference](README.md).

The TS-Pico is two computers sharing one narrow door. On one side a Timex
Sinclair 2068 runs a patched copy of its own ROMs. On the other a Raspberry
Pi Pico runs MicroPython. Between them are two Z80 I/O ports, 0Eh and 0Fh,
decoded by the board and served by a PIO state machine. Everything in this
reference is one side or the other of that door.

## What runs where

**On the 2068.** The Z80 sees three banks it can page in 8K chunks: HOME (the
computer's ROM and RAM), EXROM (the extension ROM) and DOCK (the cartridge
port). The TS-Pico replaces all three sources:

- **HOME** is the genuine 2068 ROM with ten hunks of patches: hooks in the
  tape and printer routines, a 16K-wide bank switch, and thunks that call
  into the EXROM. The current ROM adds a version byte, a new report, and
  trampolines for the disk keywords and the file channels. [rom/home.md](rom/home.md).
- **EXROM** is 16K, not the genuine 8K. Chunk 0 is the genuine EXROM patched
  in 36 places, with the Pico driver written into its 1K hole at 1800h–1BFFh.
  Chunk 1 holds the TS-Pico's own code: the response-function chain, the port
  accessors and the SAVE-prompt BREAK test at 2000h–22FDh, the SYNC and BREAK code at 2300h,
  and the disk and channel module at 3000h. [rom/overview.md](rom/overview.md)
  and the four EXROM chapters.
- **DOCK** is whatever cartridge page the Pico selects: a `.dck` image, or
  the customised ZX Spectrum ROM that `tpi:zx48` switches to. [rom/zx48.md](rom/zx48.md).

The ROM images live on a 512K flash chip (and can be copied into a 512K
SRAM) on the TS-Pico board, in sixteen 32K slots; a 2068 ROM fills one (16K
HOME + 16K EXROM), the ZX Spectrum ROM one, a cartridge two (64K). The Pico tells two PIO state machines
which slot and which chip to present on every Z80 memory cycle.
[hardware.md](hardware.md).

**On the Pico.** MicroPython 1.29 with the `TS` package frozen in
([firmware/boot.md](firmware/boot.md)):

- `main.py` sets the bus pins to their idle levels, picks the frozen or the
  development copy of the firmware, and calls `TS2068_IO()` inside a handler
  that writes any crash to `/activity.log`.
- `TS2068_IO()` in `TS/tspico.py` is the program. It starts the three state
  machines, mounts the SD card, reads `config.ini`, pre-loads the first
  status byte, and then loops forever: capture a ten-byte pre-header, decide
  what it is, serve it, put the link back to idle.
  [firmware/tspico-dispatch.md](firmware/tspico-dispatch.md).
- `TS/tspico_io.py` is the bus layer: the PIO programs, the FIFO helpers,
  DMA, and the two big transfers, `LOAD_TS` and `SAVE_TS`.
  [firmware/pio.md](firmware/pio.md), [firmware/tspico_io.md](firmware/tspico_io.md).
- `TS/tspico.py`'s other six thousand lines are the command handlers, the
  messages, the file and folder helpers and the SD card's state. Seven
  chapters, [firmware/tspico-state.md](firmware/tspico-state.md) onwards.
- `TS/sdcard.py` drives the card over SPI; `TS/channels.py`, `TS/catalog.py`
  and `TS/native.py` are pure logic (channels, names and listings, +3DOS
  headers); `TS/printer.py` is the virtual printer; `TS/extcmd.py` holds
  user-added commands.

Three PIO state machines run all the time:

| State machine | Program | Clock | Job |
|---|---|---|---|
| PIO 0, SM 0 (`MQ`) | `TS_IO_DUAL` | 30 MHz | every Z80 `IN`/`OUT` on ports 0Eh and 0Fh: TX FIFO out, RX FIFO in, the status byte from register Y |
| SM 4 (`ROM`) | `set_ctrl` | 150 MHz | the ROM chip's control lines on every Z80 memory cycle that selects the TS-Pico's ROM |
| SM 5 (`BANK`) | `sel_bank` | 150 MHz | the slot and page lines |

The RP2040's second core blinks the LED while the card mounts at boot and
writes the activity log; everything that talks to the Z80 is on core 0.
DMA takes the per-byte work out of Python in two places where the Z80's pace
demands it: the pre-header capture and the LOAD stream.

## A transaction in one paragraph

The ROM opens every exchange with `OUT (0Fh),03h` (SYNC) and waits up to a
second for the status to read READY and IDLE; the Pico, seeing a port-0Fh
write, drops whatever it was doing, empties both FIFOs, queues a single 01h
and says idle. The Z80 then writes ten bytes to port 0Eh, the pre-header,
and reads one byte back at once: that 01h, the pre-load, which proves the
Pico is there. The PIO has dropped the status to busy on the Z80's first
write (auto-busy), so the Z80 now polls port 0Fh until the Pico, having
captured the ten bytes and decided what they are, says READY. For a command
the Z80 then sends the body, `'D'`, a length, the text `tpi:…`, an XOR; the
Pico dispatches on the word after `tpi:`, the handler does its work (with
the SD card if it needs it, which means parking the bus state machine and
handing GPIO 2–4 to SPI for the duration) and queues its answer: a status
byte, or a response-function code that asks the 2068 to print something or
show pages and send keys back. Only once the answer is queued does the Pico
say READY. The Z80 reads the answer, runs the response function if there is
one, and turns the final status into a report or `0 OK`. The Pico's tail
waits for the TX FIFO to drain, empties RX, queues the next 01h and says
idle. A LOAD or SAVE is the same shape with a block instead of a body, and
the data flows blind at the Z80's pace, ~45 µs a byte, with no handshake
inside the block. [appendix/ports-and-status.md](appendix/ports-and-status.md)
has every byte; [flows/command.md](flows/command.md), [flows/load.md](flows/load.md)
and [flows/save.md](flows/save.md) follow each kind through both sides.

## The rules that shape the code

Five facts explain most of what looks odd in the firmware. Each has its own
place in the chapters; they are collected here because a reader meets their
consequences before their causes.

1. **There is no /WAIT.** The Pico can never hold the Z80 up. A read of an
   empty TX FIFO returns 00h, which the ROM reads as "no answer" (Report J).
   So the firmware queues answers before it says READY, pre-loads the 01h
   between transactions, and keeps per-byte work out of Python wherever the
   Z80 reads blind. [firmware/pio.md](firmware/pio.md).
2. **Four-deep FIFOs.** The Z80 writes a byte every ~30 µs in a burst and
   Python cannot keep up byte by byte, so bursts are captured whole
   (`RX_CAPTURE`, `RX_BLOCK`, DMA) and decided afterwards. The same rule
   governs every test harness. [firmware/tspico_io.md](firmware/tspico_io.md),
   `src/CLAUDE.md`.
3. **Every byte in TX will be read at some protocol moment.** A byte queued
   in the wrong place is not an error now but a misread later, often a phase
   downstream. Hence the V6 pre-load chain, `CMD_PUT` instead of `MQ.put`,
   and the pitfalls list in `docs/PROTOCOL.md` §13.
4. **GPIO 2–4 are both D0–D2 and the SD card's SPI.** The bus state machine
   and the card take turns; the handover is explicit (`ACTIVATE_SD`,
   `ACTIVATE_MQ`, `SD_CALL`) and the lines are clamped low in between, which
   closed the original "Report D" bug. [firmware/tspico-bus.md](firmware/tspico-bus.md),
   [flows/sd-handover.md](flows/sd-handover.md).
5. **The ROM is binary.** The base image, `src/rom/TSPICO.ROM`, has no
   source; the SYNC/BREAK layer and the disk module are byte patches and a
   module spliced into its free space, built by
   `tools/build-rom.py` with every patch site checked. The listing is the
   ground truth, and the Z80 decrements a status before dispatching on it,
   so `CP 85h` means status 86h. [rom/overview.md](rom/overview.md).

## Versions

| What | Version | Where it is written | How to read it |
|---|---|---|---|
| Firmware | 2.2.1 | `FW_VERSION` in `TS/tspico.py`; `config.ini`'s copy is informational | `SAVE "tpi:info"`; the `[TS.tspico] BUILD_VERSION =` line on USB gives the commit |
| TS-2068 ROM | 2.2 | HOME 0065h (`PEEK 101` = 34), BIOS G_VERS = 0022h, the boot banner | `PEEK 101`; `SAVE "tpi:info"` |
| ZX Spectrum ROM | v4 | the banner byte at 38B7h | the boot screen in ZX48 mode |
| ROM 2.2 module | FDD_VERSION 8 | EXROM 30AFh | — |

The firmware and the ROM share a major.minor number; the third part is a
firmware-only release on the same ROM. ROM 2.2 needs firmware that
understands SYNC; the firmware still serves ROM 1.1, which never writes
port 0Fh. [rom/overview.md](rom/overview.md).

## The sources, by size

| Source | Lines | What | Chapter |
|---|---|---|---|
| `src/TS/tspico.py` | 7,269 | the dispatcher, every command, messages, files, SD state | seven `tspico-*.md` chapters |
| `src/TS/tspico_io.py` | 2,919 | PIO programs, FIFO helpers, DMA, LOAD, SAVE, ZX48 transfers | [pio.md](firmware/pio.md), [tspico_io.md](firmware/tspico_io.md) |
| `src/TS/sdcard.py` | 536 | the SPI SD driver | [sdcard.md](firmware/sdcard.md) |
| `src/TS/channels.py` | 449 | `OPEN #` channels | [channels.md](firmware/channels.md) |
| `src/TS/catalog.py` | 313 | names, wildcards, listings | [catalog.md](firmware/catalog.md) |
| `src/TS/printer.py` | 243 | the virtual printer | [printer.md](firmware/printer.md) |
| `src/TS/native.py` | 146 | +3DOS headers | [native.md](firmware/native.md) |
| `src/TS/extcmd.py` | 95 | external commands | [extcmd.md](firmware/extcmd.md) |
| `src/main.py` | 128 | boot | [boot.md](firmware/boot.md) |
| `src/upgrade/` | ~800 | the upgrade UF2 and the Z80 updater | [upgrade.md](firmware/upgrade.md) |
| `src/rom/fdd/fddcmd.asm` | 1,398 | the disk module | [exrom-fdd.md](rom/exrom-fdd.md) |
| `src/rom/patches/tspico-sync.asm` | 318 | the SYNC/BREAK layer | [exrom-sync.md](rom/exrom-sync.md) |
| `src/rom/patches/tspico-zx48-v3.asm` | 280 | the ZX Spectrum ROM v4 | [zx48.md](rom/zx48.md) |
| `src/rom/TSPICO-22.ROM` | 32K binary | the release ROM | [rom/overview.md](rom/overview.md) and the EXROM chapters |

Line counts are those of the sources the stamps in the [README](README.md)
were taken from; [appendix/index.md](appendix/index.md) has the line of
every symbol.

## How to read this reference

- To change a command or add one: [firmware/tspico-commands.md](firmware/tspico-commands.md),
  then [firmware/tspico-dispatch.md](firmware/tspico-dispatch.md) for what
  happens around a handler, then `docs/PROTOCOL.md` §11 and §13.
- To touch anything that moves bytes: [firmware/pio.md](firmware/pio.md),
  [firmware/tspico_io.md](firmware/tspico_io.md) and
  [firmware/tspico-bus.md](firmware/tspico-bus.md), in that order, and
  `src/CLAUDE.md`'s harness-first rule before editing.
- To change the ROM: [rom/overview.md](rom/overview.md) for the build and
  the listings, then the chapter for the region.
- To follow one operation end to end: the [flows](flows/boot.md).
- To look something up: [appendix/index.md](appendix/index.md) by symbol,
  [appendix/ports-and-status.md](appendix/ports-and-status.md) by number,
  [appendix/glossary.md](appendix/glossary.md) by word.
