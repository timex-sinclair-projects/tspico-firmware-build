# Glossary

The words this reference uses, with the chapter that says more. Entries are
alphabetical. Z80 addresses are written `1A54h`; Pico values as the code
writes them.

**Auto-busy.** The PIO's rule that every Z80 OUT, to either port, drops the
status byte to 00h until Python says READY again (`mov(y, null)` at the end
of the OUT path, issue #14). The Pico must queue its answer first and say
READY second. [pio.md](../firmware/pio.md), [tspico-bus.md](../firmware/tspico-bus.md).

**Bank.** On the TS2068, one of three 64K address spaces: HOME (the
computer's own ROM and RAM), EXROM (the extension ROM, where the TS-Pico
driver lives) and DOCK (the cartridge port, where the TS-Pico puts a
cartridge image or the Spectrum ROM). Which bank each 8K chunk comes from is
set through ports F4h and FFh. [rom/overview.md](../rom/overview.md).

**Bank stack.** The RAM stack at (65CEh) on which the HOME→EXROM thunk at
03FCh pushes a frame for every call and pops it on return. An error raised
inside the EXROM used to leak one frame per error; ROM 2.1's `GUARDED` and
`H_TRAP` fix it. [exrom-fdd.md](../rom/exrom-fdd.md), [home.md](../rom/home.md).

**BIOS.** The jump table at EXROM 1840h (G_MODE, S_MODE, G_VERS, TX_A, RX_A,
C_END, WF_NPH) that machine-code programs call to talk to the Pico; stable
across ROM versions. [exrom-driver.md](../rom/exrom-driver.md),
[ports-and-status.md](ports-and-status.md).

**Body.** The second part of a command transaction: `'D'`, a 16-bit length,
the command text, an XOR. [ports-and-status.md](ports-and-status.md).

**BREAK abort.** ROM 2.0's handling of CAPS SHIFT + SPACE during a Pico
transaction: `OUT (0Fh),03h`, a wait for READY + IDLE, Report D. The Pico
sees the 0Fh write and goes idle. [exrom-sync.md](../rom/exrom-sync.md),
[flows/break-and-recovery.md](../flows/break-and-recovery.md).

**Chunk.** One of the eight 8K pieces of the Z80's 64K address space on the
TS2068; the unit of bank switching. The TS-Pico EXROM is 16K and takes chunks
0 and 1. [rom/overview.md](../rom/overview.md).

**CmdAbort.** The `BaseException` the command I/O helpers raise when the Z80
writes port 0Fh in the middle of a command (BREAK or a new SYNC); it unwinds
the handler so `PROCESS_CMD`'s tail runs. Never catch it.
[tspico-bus.md](../firmware/tspico-bus.md).

**Core0 / core1.** The RP2040's two processors. Everything that talks to the
Z80 runs on core0 in `TS2068_IO`; core1 blinks the LED during the boot-time
SD mount and writes the activity log. [hardware.md](../hardware.md),
[tspico-files.md](../firmware/tspico-files.md).

**DCK.** A TS2068 cartridge image file (`.dck`), which the Pico can put in a
DOCK slot. [tspico-files.md](../firmware/tspico-files.md) `DCK_IMAGE`.

**Dev override.** A `/dev_tspico.py` (or `.mpy`) or `/dev_extcmd.py` on the
Pico's flash that `main.py` runs instead of the frozen module, for iterating
without a UF2 rebuild. [boot.md](../firmware/boot.md).

**DMA.** The RP2040's memory-to-peripheral engine. The firmware uses it to
capture a pre-header into RAM (`RxDMA`) and to feed a LOAD stream to the TX
FIFO (`STREAM_DMA`) without per-byte Python. [tspico_io.md](../firmware/tspico_io.md).

**DOCK.** See Bank. The TS-Pico fills the DOCK bank from a flash or SRAM
page (a cartridge, or the Spectrum ROM in ZX48 mode).

**Echo.** In a LOAD, the two bytes the Z80 writes back to the Pico: the flag
before the data, and its computed XOR after. [tspico_io.md](../firmware/tspico_io.md) `LOAD_TS`.

**ERR_NR.** The TS2068 system variable (5C3Ah) holding the report code
minus one; the byte after `RST 8`. [ports-and-status.md](ports-and-status.md).

**EXROM.** See Bank. The 16K TS-Pico extension ROM: a patched copy of the
genuine 8K EXROM in chunk 0 and TS-Pico code in chunk 1. [rom/overview.md](../rom/overview.md).

**EXT_SA_FUNCT.** The dictionary of external commands (`tpi:.name`) in
`TS/extcmd.py` or `/dev_extcmd.py`. [extcmd.md](../firmware/extcmd.md).

**`f:` and `d:`.** Name prefixes ROM 2.1 understands: `f:path` is a plain
file on the SD card (a +3DOS-headed file for LOAD/SAVE, a text or binary
file for a channel); `d:pattern` opens a folder listing as a channel.
[tspico-disk.md](../firmware/tspico-disk.md), [exrom-fdd.md](../rom/exrom-fdd.md).

**FIFO.** The PIO state machine's four-entry TX (Pico → Z80) and RX (Z80 →
Pico) queues. [pio.md](../firmware/pio.md).

**Flag byte.** The first byte of a tape block: 00h for a header, FFh for
data. Also the first byte of a LOAD/SAVE pre-header.

**Flash image.** The 512K image written to the TS-Pico's flash chip, holding
the ROM slots and the DOCK pages; `flash/manifest.json` lists them.
[boot.md](../firmware/boot.md), [hardware.md](../hardware.md).

**Frozen module.** A Python module compiled into the UF2 by `manifest.py`
(`TS/*.py`); changing one means a rebuild and a reflash. [boot.md](../firmware/boot.md).

**Function (response function).** An answer whose first byte is ≥ 80h:
81h print a string, 86h paged text with a key between pages, 88h the same on
the lower screen, and so on. [ports-and-status.md](ports-and-status.md),
[exrom-chunk1.md](../rom/exrom-chunk1.md).

**Harness.** A standalone script in `src/test/` that drives the real bus
from the Pico to capture or reproduce one behaviour; the repo's way of
settling protocol questions. `src/CLAUDE.md`.

**HOME.** See Bank. The TS2068's own ROM, patched with hooks that redirect
into the EXROM. [home.md](../rom/home.md).

**Host test.** A `src/test/*_hosttest.py` script that runs firmware code on a
PC against fakes; CI runs them all. [boot.md](../firmware/boot.md).

**IDLE.** Status bit 3: no transaction is open. [ports-and-status.md](ports-and-status.md).

**MQ.** The firmware's name for the `StateMachine` object running
`TS_IO_DUAL` (PIO 0, state machine 0): `MQ.put`, `MQ.get`, `MQ.tx_fifo()`.
[tspico-state.md](../firmware/tspico-state.md).

**Mount.** `LOAD "tpi:name"`: the Pico copies a TAP (or DCK/ROM/BIN) file to
its flash and makes it the tape that `LOAD ""` and `SAVE` use.
[tspico-files.md](../firmware/tspico-files.md) `MOUNT_FILE`.

**nofile.tap.** The tape the Pico serves to a `LOAD ""` with nothing
mounted: a BASIC program that prints a message. Pre-opened at boot.
[tspico_io.md](../firmware/tspico_io.md) `OPEN_NOFILE_TAP`.

**Offset table.** The list of byte offsets of each block in the mounted TAP,
built at mount time, that FFW, REW and the LOAD search walk.
[tspico-files.md](../firmware/tspico-files.md) `OFF_TABLE`.

**Orphan byte.** A byte left in the TX FIFO that the Z80 reads at a later,
wrong moment: the classic dual-port bug. `docs/PROTOCOL.md` §13.

**Pieces reply.** ZX v4's way of reading a reply longer than 255 bytes: a
length 1–255, that many bytes, repeated, then 0. [zx48.md](../rom/zx48.md).

**PIO.** The RP2040's programmable I/O block: small state machines that run
their own instruction set at bus speed. The TS-Pico uses three.
[pio.md](../firmware/pio.md).

**PMR1, PMR2.** Pre-header bytes 3–4 and 5–6: the two `CODE n,m` numbers of
a command. [ports-and-status.md](ports-and-status.md).

**Pre-header.** The ten bytes that open every transaction. [ports-and-status.md](ports-and-status.md).

**Pre-load.** The single 01h that waits in the TX FIFO between transactions,
read by the ROM straight after the tenth pre-header byte. Queued by the tail
of every transaction and by every SYNC; never by a handler.
[tspico-dispatch.md](../firmware/tspico-dispatch.md).

**READY.** Status bit 6. [ports-and-status.md](ports-and-status.md).

**RECOVERED.** Status bit 2, active low: the Pico abandoned a transaction on
its own. The ROM reports T. [ports-and-status.md](ports-and-status.md).

**Record file.** A channel file opened with a record length; `TAB n` seeks
to record *n*. [channels.md](../firmware/channels.md).

**Report.** A BASIC error message (`J Invalid I/O device`, `R Tape loading
error`…). Every Pico status maps to one. [ports-and-status.md](ports-and-status.md).

**ROM_SM, bank_sm.** The two words the firmware sends to the ROM and BANK
state machines: which memory (flash or SRAM) serves the ROM and the DOCK,
and which slot and page. [hardware.md](../hardware.md), [pio.md](../firmware/pio.md).

**SA_funct.** The dictionary of built-in `tpi:` commands in `TS2068_IO`.
[tspico-commands.md](../firmware/tspico-commands.md).

**Session id.** A 16-bit value the ROM derives from FRAMES (+1, never 0)
at the start of a SAVE or LOAD and sends in the pre-headers and in a SAVE's
blocks; it is cleared after the data block. The firmware uses it to tie a
`tpi:fopen` to the SAVE or LOAD that follows, and otherwise ignores it.
[exrom-driver.md](../rom/exrom-driver.md) `SESSION_SETUP`,
[sysvars.md](../rom/sysvars.md#5dd1h-session-id).

**Side-set.** The PIO feature that sets a pin on every instruction; `TS_IO_DUAL`
drives the U6 bus-buffer enable with it. [pio.md](../firmware/pio.md).

**Slot, page.** The flash (or SRAM) is sixteen 32K slots; a 2068 ROM
fills one (HOME + EXROM), the 16K ZX Spectrum ROM one; a DOCK cartridge
image takes two consecutive slots, a 64K page, so cartridge slot numbers step by two. Selected through the BANK
state machine. [hardware.md](../hardware.md), `flash/README.md`.

**Stamp.** In this reference, the hash of a source file recorded in the
README's table, saying which version of the file a chapter was checked
against. [README.md](../README.md).

**Status byte.** What the Z80 reads from port 0Fh. [ports-and-status.md](ports-and-status.md).

**Status − 1 convention.** The ROM decrements a status before dispatching
on it, so `CP 85h` in the function chain matches 86h, and `STATUS_TO_REPORT`
is entered with A = status − 1. [exrom-chunk1.md](../rom/exrom-chunk1.md),
[exrom-driver.md](../rom/exrom-driver.md).

**SYNC.** ROM 2.0's `OUT (0Fh),03h` at the start of every transaction, with
a ~1 s wait for READY + IDLE; the Pico abandons anything in progress and
restores the pre-load. [exrom-sync.md](../rom/exrom-sync.md),
[tspico_io.md](../firmware/tspico_io.md) `MQ_TO_IDLE`.

**TADDR.** Pre-header byte 1: 0 SAVE, 1 LOAD, 2 VERIFY, 3 MERGE for blocks
and mounts; 4–6 the printer; 0 a command. [ports-and-status.md](ports-and-status.md).

**Tail.** The end of `PROCESS_CMD` (and of `LOAD_TS`/`SAVE_TS`): wait for TX
to drain, empty RX, queue the pre-load, say idle. [tspico-dispatch.md](../firmware/tspico-dispatch.md).

**TAP.** The tape-image file format: for each block, a 16-bit length, the
flag byte, the data, the XOR. The Pico's native "tape".

**Telemetry (TLM).** The `[TLM …]` lines on the USB serial port when
`TELEMETRY` is on in `config.ini`. [tspico-state.md](../firmware/tspico-state.md).

**Thunk.** A small routine that switches banks and calls or jumps to an
address in the other ROM: HOME 3CE3h, 0A50h and 03FCh into the EXROM; EXROM
03DDh and 08DDh into HOME. [rom/overview.md](../rom/overview.md).

**TPI.** Gustavo Pane's name for the protocol and the `tpi:` prefix. `docs/GUSTAVO_PROTOCOL.md`.

**TPMODE.** System variable 5DDBh: bit 1 sends LOAD/SAVE to the Pico, bit 0
sends printing to the Pico. [ports-and-status.md](ports-and-status.md).

**TSP.** The `PICO_STATUS` instance that holds the firmware's runtime state
(the mounted file, the current folder, the config, the card).
[tspico-state.md](../firmware/tspico-state.md).

**U3, U6, U10, U13.** Part designators the code names: the SD card socket
(U3, chip select GPIO 28), the data-bus buffer (U6, enable GPIO 12), the
flash (U10) and the SRAM (U13). [hardware.md](../hardware.md).

**UF2.** The file format the RP2040's bootloader accepts; the firmware and
the upgrade payload each ship as one. [boot.md](../firmware/boot.md).

**Upgrade UF2.** The separate firmware that serves the Z80 updater tape and
feeds it the new ROM images, for boards whose ROM predates firmware 2.0.
[upgrade.md](../firmware/upgrade.md).

**V6 pattern, pre-load chain.** The rule, from the sixth protocol observer,
that a handler writes its final status and the next pre-load as a pair and
nothing after. `docs/DUAL_PORT_DEVELOPMENT.md` §5e, §7.

**VERBOSE.** The config and `tpi:verbose` setting that makes commands print
a message (81h) instead of answering a bare status. [tspico-messages.md](../firmware/tspico-messages.md).

**Y register.** The PIO scratch register whose low byte is the status port.
[pio.md](../firmware/pio.md).

**ZX48 mode.** The TS-Pico serving the customised Spectrum ROM from flash
slot 0 and speaking the Spectrum ROM's tape protocol, after `tpi:zx48`.
[zx48.md](../rom/zx48.md), [flows/zx48.md](../flows/zx48.md).
