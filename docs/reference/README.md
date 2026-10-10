# TS-Pico programmer's reference

The internals of the TS-Pico, explained down to every function, variable,
PIO instruction and ROM routine: what each one does, why it exists, what it
touches and what will break if you change it. It covers the code as it is on
`main` today: firmware 2.3, ROM 2.3 and the ZX Spectrum ROM v4.

This is the reference for people who want to **change** the platform. If you
want to **use** it, start elsewhere:

- using the TS-Pico from BASIC: [the user manual](../manual/user-manual.md);
- talking to it from machine code, or adding a `tpi:` command: [the
  programmer's manual](../manual/programmers-manual.md), a tutorial;
- testing programs without the hardware, in ZEsarUX or Fuse: [testing in an
  emulator](../manual/emulators.md);
- the wire protocol byte by byte: [PROTOCOL.md](../PROTOCOL.md), whose §13
  is the pitfalls list every contributor should read;
- why the code is shaped the way it is: [DUAL_PORT_DEVELOPMENT.md](../DUAL_PORT_DEVELOPMENT.md)
  and [DEVELOPER_GUIDE.md](../DEVELOPER_GUIDE.md).

Those documents stay where they are. This one explains the code they describe.

## How it is organised

Each chapter follows **one source file, in source order**, so you can read the
file and the chapter side by side, and so a diff of the file maps onto a diff
of the chapter. The flows then cut across the files to follow one operation
from the BASIC keyword to the SD card and back.

| Part | Chapter | Covers |
|---|---|---|---|
| Start | [overview.md](overview.md) | The ecosystem on one page: the two computers, the bus between them, the three state machines, the two cores, the ROM banks; versions; how to read the rest |
| Start | [hardware.md](hardware.md) | What the Pico is wired to, as the code sees it: every GPIO, the bus lines, ports 0Eh/0Fh, the flash and SRAM slots, the SD card, clocks |
| Firmware | [firmware/boot.md](firmware/boot.md) | `src/main.py`, `config.ini`, the freeze manifest and `buildinfo`, the dev overrides, the UF2 build and CI, the flash image |
| Firmware | [firmware/pio.md](firmware/pio.md) | The five PIO programs, instruction by instruction: `TS_IO_DUAL`, `set_ctrl`, `sel_bank`, `set_dck`, `NULL_SM`; the Y register contract; the FIFOs |
| Firmware | [firmware/tspico_io.md](firmware/tspico_io.md) | `src/TS/tspico_io.py`: the bus helpers, DMA, `LOAD_TS`, `SAVE_TS`, the ZX48 transfers, SD enable |
| Firmware | [firmware/tspico-state.md](firmware/tspico-state.md) | `src/TS/tspico.py` part 1: module constants and globals, the caches, `PICO_STATUS`, telemetry |
| Firmware | [firmware/tspico-bus.md](firmware/tspico-bus.md) | part 2: who owns the bus: `ACTIVATE_MQ`, `ACTIVATE_SD`, `MQ_READY`, the `CMD_*` command I/O, the SD card state |
| Firmware | [firmware/tspico-dispatch.md](firmware/tspico-dispatch.md) | part 3: `TS2068_IO`, `PROCESS_CMD`, `FAIL_CMD`, the printer path, `ZX48_IO`, `ZX_TPI`, `LOAD_CONFIG` |
| Firmware | [firmware/tspico-messages.md](firmware/tspico-messages.md) | part 4: everything that prints on the 2068: `SEND_MSG`, `SEND_MSG2`, the prompts, `ListMenu`, colour |
| Firmware | [firmware/tspico-files.md](firmware/tspico-files.md) | part 5: mounting, the folder caches, TAP helpers, the activity log, path helpers |
| Firmware | [firmware/tspico-commands.md](firmware/tspico-commands.md) | part 6: every `tpi:` command handler and the dispatch table |
| Firmware | [firmware/tspico-disk.md](firmware/tspico-disk.md) | part 7: the ROM's disk commands on the Pico: CAT, MOVE, ERASE, FORMAT, `f:` files, the channels |
| Firmware | [firmware/sdcard.md](firmware/sdcard.md) | `src/TS/sdcard.py`: the SPI SD driver and its recovery |
| Firmware | [firmware/channels.md](firmware/channels.md) | `src/TS/channels.py`: `OPEN #` channels, text conversion, records |
| Firmware | [firmware/catalog.md](firmware/catalog.md) | `src/TS/catalog.py`: names, wildcards, paths, listings |
| Firmware | [firmware/native.md](firmware/native.md) | `src/TS/native.py`: +3DOS headers for `f:` files |
| Firmware | [firmware/printer.md](firmware/printer.md) | `src/TS/printer.py`: the virtual printer, text and BMP |
| Firmware | [firmware/extcmd.md](firmware/extcmd.md) | `src/TS/extcmd.py`: the external command table |
| Firmware | [firmware/upgrade.md](firmware/upgrade.md) | `src/upgrade/`: the upgrade UF2, the Z80 updater and its tape, the web updater's part |
| Firmware | [firmware/board.md](firmware/board.md) | `src/TS/board.py`, `board_v2.py`, `board_v3.py`: the board layer, every hardware touch of the firmware behind one module, for the v2 TS-Pico and the v3 card |
| Firmware | [firmware/board-v3.md](firmware/board-v3.md) | `src/boards/TSPICO_V3/`: the MicroPython board for the v3 card (RP2350B), its safe pin state, default pins, heap and clock settings |
| Firmware | [firmware/tsbus.md](firmware/tsbus.md) | `src/tsbus/`: the v3 card's bus as a C module: the PIO programs, the DMA chain, core 1, `tsbus.start`/`load`/`serve`/`hold` |
| ROM | [rom/overview.md](rom/overview.md) | The images and their lineage, banking, how HOME calls EXROM, version bytes, the ROM build and the listings |
| ROM | [rom/sysvars.md](rom/sysvars.md) | The TS-Pico system variables at 5Dxxh, and the stock ones the Pico code uses |
| ROM | [rom/home.md](rom/home.md) | The HOME ROM: every hook and patch |
| ROM | [rom/exrom-driver.md](rom/exrom-driver.md) | EXROM 1800h–1BFFh: the Pico driver, the BIOS table, the SAVE and LOAD paths, the reports |
| ROM | [rom/exrom-chunk1.md](rom/exrom-chunk1.md) | EXROM 2000h–22FDh and the chunk-0 helpers: the function chain, the accessors, the printer path |
| ROM | [rom/exrom-sync.md](rom/exrom-sync.md) | The SYNC/BREAK layer at 2300h: SYNC, BREAK, recovery |
| ROM | [rom/exrom-fdd.md](rom/exrom-fdd.md) | The disk module at 3000h: disk commands, `f:`, channels |
| ROM | [rom/zx48.md](rom/zx48.md) | The ZX Spectrum ROM v4 |
| Flows | [flows/boot.md](flows/boot.md) | Power-on to the first prompt, both sides |
| Flows | [flows/command.md](flows/command.md) | `SAVE "tpi:…"` from keyword to answer |
| Flows | [flows/load.md](flows/load.md) | `LOAD ""` from keyword to the last byte |
| Flows | [flows/save.md](flows/save.md) | `SAVE "name"` into a TAP |
| Flows | [flows/channels.md](flows/channels.md) | `OPEN #`, `PRINT #`, `INPUT #`, `CLOSE #` |
| Flows | [flows/printer.md](flows/printer.md) | `LPRINT`, `LLIST`, `COPY` |
| Flows | [flows/sd-handover.md](flows/sd-handover.md) | How the bus passes between the Z80 and the SD card |
| Flows | [flows/break-and-recovery.md](flows/break-and-recovery.md) | SYNC, BREAK, a dropped transaction |
| Flows | [flows/zx48.md](flows/zx48.md) | `tpi:zx48` and life in Spectrum mode |
| Appendix | [appendix/ports-and-status.md](appendix/ports-and-status.md) | Ports, status bits, status codes to reports, function codes, pre-headers |
| Appendix | [appendix/glossary.md](appendix/glossary.md) | The words |
| Appendix | [appendix/index.md](appendix/index.md) | Every symbol, where it is in the source and where it is explained (generated) |

## Conventions

**Every symbol gets an entry.** A function, class, method, module variable,
PIO program, `tpi:` command or ROM label is introduced by a heading or a table
row with its name in backticks, and that is what
[`src/test/reference_hosttest.py`](../../src/test/reference_hosttest.py)
looks for:

```markdown
### `ACTIVATE_MQ()`
### `PICO_STATUS.__init__(self, init_values)`
### `files`
### `tpi:cd`
### `WAIT_PICO_READY` (1A54h)
| `_1_OK` | 1 | status 1: success | — |
```

A trailing `(…)` is ignored, so a heading may show the signature. Related
constants may share one table, one row each. Methods are named
`Class.method`.

**An entry says six things**, in this order, dropping any that do not
apply: what it is for (one sentence); what it does, step by step, including
every effect on the FIFOs, the Y register, the bus and the SD card; why it
exists in this form, naming the bug, constraint or measurement behind it;
what it takes and returns, with units and sentinels; what state it reads
and writes (globals, `TSP` fields, files); and what to beware of. A
variable's entry says its type, its initial value, who sets it, who reads it,
and the invariant it carries.

**Source order.** Entries appear in the order the symbols appear in the
file. A chapter opens with a map of the file.

**Facts come from the code**, not from the design documents. Where a
comment in the code, a design document and the code itself disagree, the
chapter says so and the code wins. Anything inferred rather than read is
marked *(inferred)*. Anything that could only be settled on hardware and has
not been is marked *(unverified)*.

**Addresses and numbers.** Z80 addresses are written `1A54h`; Pico
registers, GPIOs and bytes on the wire as `0x0E`, `GPIO 14`, `03h` as the
code writes them. ROM addresses are those of ROM 2.2's listings unless a
version is named; ROM 2.3 differs only at the sites its four patches touch
and in the module's `PS_READ` ([rom/overview.md](rom/overview.md)). The listings in [`docs/rom-analysis/disasm/`](../rom-analysis/disasm/)
(`tspico-22-exrom.labelled.asm`, `tspico-22-home.asm`) are the ones cited.

**Links, not copies.** The pitfalls list stays in PROTOCOL.md §13; the
development history stays in DUAL_PORT_DEVELOPMENT.md; a chapter links to
them rather than restating them.

## Keeping it current

The reference is part of the code. A pull request that changes anything
listed in the table below changes the matching chapter in the same PR. CI
runs [`src/test/reference_hosttest.py`](../../src/test/reference_hosttest.py),
which fails when:

- a symbol in the code has no entry (a new function, variable, command or
  ROM label);
- a source below has changed since the reference was checked against it.
  The table records a hash of each file; after re-reading the chapter, and
  the flows and appendices the row lists, and fixing what the change
  affects (including the line numbers the chapters cite:
  `python3 src/test/reference_hosttest.py --relines <source>` lists those
  the change moved, before you re-stamp), refresh the row with `python3 src/test/reference_hosttest.py
  --stamp` (it prints each row with the new hash; paste only the rows you
  re-read);
- a flow or appendix is not listed against any source (a new flow needs
  the sources it follows; `index.md` and `glossary.md` are exempt);
- [`appendix/index.md`](appendix/index.md) is out of date: regenerate it
  with `python3 src/test/reference_hosttest.py --index`.

Re-stamping without re-reading defeats the purpose. The rule for
contributors and AI agents is in [`CLAUDE.md`](../../CLAUDE.md).

A fix for a [`reference-followup`](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues?q=label%3Areference-followup)
issue also updates the chapters that cite it: the entry says the new
behaviour, and the caveat and the issue link go.

### Stamps

| Source | Checked at | Chapter | Flows and appendices |
|---|---|---|---|
| `src/main.py` | `162b8f97be26` | [firmware/boot.md](firmware/boot.md) | [flows/boot.md](flows/boot.md) |
| `src/TS/tspico.py` | `2607f59d6873` | [firmware/tspico-state.md](firmware/tspico-state.md), [tspico-bus.md](firmware/tspico-bus.md), [tspico-dispatch.md](firmware/tspico-dispatch.md), [tspico-messages.md](firmware/tspico-messages.md), [tspico-files.md](firmware/tspico-files.md), [tspico-commands.md](firmware/tspico-commands.md), [tspico-disk.md](firmware/tspico-disk.md) | [flows/boot.md](flows/boot.md), [flows/command.md](flows/command.md), [flows/load.md](flows/load.md), [flows/save.md](flows/save.md), [flows/channels.md](flows/channels.md), [flows/printer.md](flows/printer.md), [flows/sd-handover.md](flows/sd-handover.md), [flows/break-and-recovery.md](flows/break-and-recovery.md), [flows/zx48.md](flows/zx48.md), [appendix/ports-and-status.md](appendix/ports-and-status.md) |
| `src/TS/tspico_io.py` | `136835436e7c` | [firmware/pio.md](firmware/pio.md), [firmware/tspico_io.md](firmware/tspico_io.md) | [flows/boot.md](flows/boot.md), [flows/load.md](flows/load.md), [flows/save.md](flows/save.md), [flows/sd-handover.md](flows/sd-handover.md), [flows/break-and-recovery.md](flows/break-and-recovery.md), [flows/zx48.md](flows/zx48.md), [appendix/ports-and-status.md](appendix/ports-and-status.md) |
| `src/TS/sdcard.py` | `e1c614de390c` | [firmware/sdcard.md](firmware/sdcard.md) | [flows/sd-handover.md](flows/sd-handover.md) |
| `src/TS/channels.py` | `5b1d30b1efe4` | [firmware/channels.md](firmware/channels.md) | [flows/channels.md](flows/channels.md) |
| `src/TS/catalog.py` | `0c79a1e750db` | [firmware/catalog.md](firmware/catalog.md) | — |
| `src/TS/extcmd.py` | `b8ad10ebadd7` | [firmware/extcmd.md](firmware/extcmd.md) | — |
| `src/TS/native.py` | `3f4bb90a622f` | [firmware/native.md](firmware/native.md) | [flows/save.md](flows/save.md) |
| `src/TS/printer.py` | `d8bb84d1d654` | [firmware/printer.md](firmware/printer.md) | [flows/printer.md](flows/printer.md) |
| `src/TS/board.py` | `76b05c62a1d9` | [firmware/board.md](firmware/board.md) | [flows/boot.md](flows/boot.md) |
| `src/TS/board_v2.py` | `a69a5c8f7c1f` | [firmware/board.md](firmware/board.md), [firmware/pio.md](firmware/pio.md) | [flows/boot.md](flows/boot.md), [flows/sd-handover.md](flows/sd-handover.md) |
| `src/TS/board_v3.py` | `6bf7e31168d9` | [firmware/board.md](firmware/board.md) | [flows/boot.md](flows/boot.md), [flows/sd-handover.md](flows/sd-handover.md) |
| `src/upgrade/main.py` | `6ab664e9c744` | [firmware/upgrade.md](firmware/upgrade.md) | — |
| `src/upgrade/upgrade.py` | `5eb55f6dd1fb` | [firmware/upgrade.md](firmware/upgrade.md) | — |
| `src/rom/fdd/fddcmd.asm` | `1ff9cf479f0c` | [rom/exrom-fdd.md](rom/exrom-fdd.md) | [flows/command.md](flows/command.md), [flows/load.md](flows/load.md), [flows/save.md](flows/save.md), [flows/channels.md](flows/channels.md), [appendix/ports-and-status.md](appendix/ports-and-status.md) |
| `src/rom/patches/tspico-sync.asm` | `0aebb5fbe58b` | [rom/exrom-sync.md](rom/exrom-sync.md) | [flows/boot.md](flows/boot.md), [flows/command.md](flows/command.md), [flows/load.md](flows/load.md), [flows/save.md](flows/save.md), [flows/break-and-recovery.md](flows/break-and-recovery.md), [appendix/ports-and-status.md](appendix/ports-and-status.md) |
| `src/rom/patches/tspico-zx48-v3.asm` | `c942ea86b3aa` | [rom/zx48.md](rom/zx48.md) | [flows/zx48.md](flows/zx48.md) |
| `src/upgrade/updater.asm` | `4826d5f78d95` | [firmware/upgrade.md](firmware/upgrade.md) | — |
| `docs/rom-analysis/tspico-exrom-symbols.sym` | `72aa7dccef81` | [rom/exrom-driver.md](rom/exrom-driver.md), [rom/exrom-chunk1.md](rom/exrom-chunk1.md), [rom/home.md](rom/home.md) | [flows/boot.md](flows/boot.md), [flows/command.md](flows/command.md), [flows/load.md](flows/load.md), [flows/save.md](flows/save.md), [flows/channels.md](flows/channels.md), [flows/printer.md](flows/printer.md), [flows/break-and-recovery.md](flows/break-and-recovery.md), [appendix/ports-and-status.md](appendix/ports-and-status.md) |
| `src/config.ini` | `a947fd548ef7` | [firmware/boot.md](firmware/boot.md) | [flows/boot.md](flows/boot.md) |
| `src/manifest.py` | `0e81b89f667b` | [firmware/boot.md](firmware/boot.md) | — |
| `src/upgrade/manifest.py` | `ae1e377eaa80` | [firmware/upgrade.md](firmware/upgrade.md) | — |
| `src/upgrade/loader.bas` | `78d09ea9d4fe` | [firmware/upgrade.md](firmware/upgrade.md) | — |
| `src/boards/TSPICO_V3/mpconfigboard.cmake` | `8cd4d074d032` | [firmware/board-v3.md](firmware/board-v3.md) | — |
| `src/boards/TSPICO_V3/mpconfigboard.h` | `00133414c4a4` | [firmware/board-v3.md](firmware/board-v3.md) | — |
| `src/boards/TSPICO_V3/board_init.c` | `6acb01d09ed8` | [firmware/board-v3.md](firmware/board-v3.md) | — |
| `src/boards/TSPICO_V3/tspico_v3.h` | `e434a184e4fc` | [firmware/board-v3.md](firmware/board-v3.md) | — |
| `src/boards/TSPICO_V3/manifest.py` | `c13df2e99cb4` | [firmware/board-v3.md](firmware/board-v3.md) | — |
| `src/boards/TSPICO_V3/pins.csv` | `a7c2e2d202a2` | [firmware/board-v3.md](firmware/board-v3.md) | — |
| `src/boards/TSPICO_V3/tspico_v3_pins.h` | `781c493b5c9a` | [firmware/board-v3.md](firmware/board-v3.md) | — |
| `src/boards/TSPICO_V3/memmap/section_extra_post_platform_end.incl` | `7f2393c1dc08` | [firmware/board-v3.md](firmware/board-v3.md) | — |
| `src/tsbus/tsbus.c` | `b74797ec9b0d` | [firmware/tsbus.md](firmware/tsbus.md) | — |
| `src/tsbus/tsbus.pio` | `1faa88f642fe` | [firmware/tsbus.md](firmware/tsbus.md) | — |
| `src/tsbus/micropython.cmake` | `7af5480e6052` | [firmware/tsbus.md](firmware/tsbus.md) | — |
| `src/rom/TSPICO.ROM` | `8ecbb6196edd` | [rom/overview.md](rom/overview.md) | — |
| `src/rom/TSPICO-SYNC.ROM` | `1f8615ea905c` | [rom/overview.md](rom/overview.md) | — |
| `src/rom/TSPICO-23.ROM` | `035016a30efc` | [rom/overview.md](rom/overview.md) | [flows/boot.md](flows/boot.md), [appendix/ports-and-status.md](appendix/ports-and-status.md) |
| `src/rom/TSPICO-ZX48-V4.BIN` | `ec57f307bd0d` | [rom/zx48.md](rom/zx48.md) | [flows/zx48.md](flows/zx48.md), [appendix/ports-and-status.md](appendix/ports-and-status.md) |
| `flash/manifest.json` | `37d54aad1795` | [firmware/boot.md](firmware/boot.md) | [flows/boot.md](flows/boot.md) |
| `tools/build-rom.py` | `22badceddc88` | [rom/overview.md](rom/overview.md) | — |
| `tools/build-flash.py` | `e2f58cd4004a` | [firmware/boot.md](firmware/boot.md) | — |
| `tools/build-upgrade.py` | `3a82185e0740` | [firmware/upgrade.md](firmware/upgrade.md) | — |
| `tools/gen-buildinfo.py` | `7ede1626d1da` | [firmware/boot.md](firmware/boot.md) | — |
| `.github/workflows/build.yml` | `9ef22e338caa` | [firmware/boot.md](firmware/boot.md) | — |
| `.github/workflows/release.yml` | `57aa6a7ea309` | [firmware/boot.md](firmware/boot.md) | — |
