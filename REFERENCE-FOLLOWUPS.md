# Follow-ups found while writing docs/reference/

Places where the code, its comments, the documents and the user manual
disagree, found while writing the programmer's reference. The reference
documents the code as it is ("the code wins") and does not change it; this
file collects them so each can be decided: a real bug to fix, a doc to
correct, a comment to update, or nothing.

Each item names where it was found and which chapter describes it. Mark
the decision in the last column. Items are added as chapters are written.
When an item is resolved in code, the chapter's entry changes in the same
PR (the rule in [CLAUDE.md](CLAUDE.md)).

Kinds: **bug?** behaviour that looks wrong to the user; **doc** a manual or
design document is wrong; **comment** a comment or docstring in the code is
wrong; **test** a test docstring is wrong.

## Behaviour that may be a bug

| # | Where | What | Chapter | Decision |
|---|---|---|---|---|
| B1 | `tspico.py` `DIR` (2547) | `tpi:dir CODE 1,n`/`2,n` out of range prints "out of range 0-N" with N = the number of files, one past the last index. The manual shows "0-11" for twelve files | [tspico-commands.md](docs/reference/firmware/tspico-commands.md#dirpre-cmd) | |
| B2 | `tspico.py` `MEMDOCK` (5040, 5088) | `tpi:dock CODE 0,2` (swap) builds its message from the `CODE` before the swap: "Change DOCK to MEM=0, PAGE=2". The swap itself is right | [tspico-commands.md](docs/reference/firmware/tspico-commands.md#memdockpre-cmd) | |
| B3 | `tspico.py` `BLKRCV` (4070–4083) | With a mounted file that is not `.DCK`/`.BIN`/`.ROM` (or after `tpi:close`, `f_name = ""`) no branch runs and nothing is sent: the ROM reads the tail's pre-load `01h` as "0 OK" *(inferred)*. The updaters only send it with an image mounted | [tspico-commands.md](docs/reference/firmware/tspico-commands.md#blkrcvpre-cmd) | |
| B4 | `tspico.py` `BLKRCV` (4070) | With nothing mounted since boot, `TSP.f_name` is still `[]` and `[][-4:].upper()` raises `AttributeError` → Report J. (`BOOT_SLOT_CLASH` already guards the same case) | same | |
| B5 | `tspico.py` `BLKRCV` (4076–4081) | `.DCK` path: status 1 is sent before `/TMP/temp.bin` is opened; an error opening/reading it only prints. The 2068 then erases the slot and reads an empty FIFO | same | |
| B6 | `tspico.py` `GETLOG` (4633–4640) | `tpi:log clear`: if `CLEAR_LOG` fails after the user answered Y, "Couldn't clear log file" is sent after the prompt ended the exchange; the ROM never reads it *(inferred)* | [tspico-commands.md](docs/reference/firmware/tspico-commands.md#getlogpre-cmd) | |
| B7 | `tspico.py` `GETLOG` (4664) | `os.stat("/activity.log")` is outside the `try`: no log file at all → `OSError` → Report J instead of a message | same | |
| B8 | `tspico.py` `PROMPT_EACH` (2761) | An empty `prompts` list raises `TypeError` (`32 <= None`). No caller passes one today | [tspico-messages.md](docs/reference/firmware/tspico-messages.md#prompt_eachprompts) | |
| B9 | `tspico.py` `shorten_filename` (1507) | An extension of `l - 1` characters or more returns a string longer than `l`. No caller uses so short an `l` | [tspico-messages.md](docs/reference/firmware/tspico-messages.md#shorten_filenamenom-l) | |
| B10 | `tspico.py` `NEW_TAP` (3765) | Strips `.tap` only when the text from the **first** dot is `.tap`: `tpi:newtap a.b.tap` makes `a.b.tap.tap` | [tspico-commands.md](docs/reference/firmware/tspico-commands.md#new_tappre-cmd) | |
| B11 | `tspico.py` `FWD` (2302–2316) | `tpi:ffw CODE 2,n` on a header with no later header: the pointer stays and the message says "Moved ahead to block # i" | [tspico-commands.md](docs/reference/firmware/tspico-commands.md#fwdpre-cmd) | |
| B12 | `tspico.py` `ACTIVATE_MQ` (762–767) | `MQ.active(1)` before `set(y, 0)`: ~18 µs in which Y holds the previous program's value. Executing the `set` before `active(1)` would close the window *(inferred)* | [tspico-bus.md](docs/reference/firmware/tspico-bus.md#activate_mq) | |
| B13 | `tspico_io.py` `LOAD_ZX_C` | The "no file mounted" branch is unreachable; the boundary test is two bytes short | [tspico_io.md](docs/reference/firmware/tspico_io.md) | |
| B14 | `tspico.py` `SEND_MSG2` and the text rules | The firmware counts only 124 and 126 as keyword-width characters; ERROR_TRAPPING.md lists 123, 125, 127 as keyword tokens too. Whether the ROM prints 123/125/127 as keywords is unverified | [tspico-messages.md](docs/reference/firmware/tspico-messages.md#the-answer-on-the-wire) | |
| B15 | `tspico.py` `MDIR` (4867) | The name is `cmd[10:]`, not `getArgs`: a second space after `tpi:md` becomes part of the name; no character check (FAT refuses with `OSError`, Q) | [tspico-commands.md](docs/reference/firmware/tspico-commands.md#mdirpre-cmd) | |
| B16 | `.mpy` override | `main.py` and `build-dev-mpy.sh` say `/dev_tspico.mpy` is preferred over `/dev_tspico.py`; MicroPython's importer looks for `.py` first. Check on a board with both files | [boot.md](docs/reference/firmware/boot.md#the-dev-overrides) | |
| B17 | ROM 2.1 EXROM 20BEh (`tpi:tape`) | `tpi:tape` sets TPMODE to 0, clearing the printer switch (bit 0) as well as LOAD/SAVE (bit 1); `tpi:sdcard` restores only bit 1. So `tpi:picopt`, `tpi:tape`, `tpi:sdcard` leaves the printer on the 2068. The manual documents the 0, so it may be intended | [rom/sysvars.md](docs/reference/rom/sysvars.md#5ddbh-tpmode-peek-24027) | |
| B18 | ROM 2.1 SESSION_NAMED (1AC4h–1AD9h) | The `NET:` prefix is recognised (TPMODE bits 7+6) but leads nowhere: the switch words ignore it and the firmware answers "Unrecognized command". Dead feature or unfinished? | same | |
| B19 | ROM HOME 0A4Ah | COPY-LINE's entry now thunks to EXROM 17C3h but nothing in ROM 2.1 calls it (its callers were inside the replaced COPY/COPY-BUFF). Dead, or kept for programs that call COPY-LINE? | |
| B20 | `fddcmd.asm` `SEND_FOPEN`, `CH_SEND` | Both read the pre-load status (`BIOS_RX_A`) and ignore it; `SEND_DATA_BLOCK_D` checks it. Harmless while the firmware never refuses at the pre-load | [rom/exrom-fdd.md](docs/reference/rom/exrom-fdd.md#send_fopen) | |

## The user manual

| # | Where | What | Decision |
|---|---|---|---|
| M1 | §10.3 dir | "File index 12 out of range 0-11": the code says 0-12 (B1) | |
| M2 | §10.3 cd | Lists only F for a failed change; a missing folder given as `/tap/x` is Q (`ChangeDir`) | |
| M3 | §10.3 boot | "MEM must be 1 or 2": `CODE 0,s` with `s` ≠ 0 is refused too | |
| M4 | §10.3 ffw/rew/append | Nothing mounted answers 0 OK (message only with VERBOSE), except `append on`, which is Q. Worth saying | |
| M5 | §10.3 dock | The `CODE 0,2` message (B2) | |


## Comments and docstrings that are out of date

| # | Where | What | Decision |
|---|---|---|---|
| C1 | `tspico.py` 686–689 (`DEACTIVATE_SD` header) and 6284–6286 (boot) | Call the GPIO 2–4 clamp the fix for the original Report D; the body comment (703–709) says that was D6, GPIO 8 | |
| C2 | `tspico.py` 726–727 (`ACTIVATE_MQ`), `TS_IO_DUAL`'s docstring in `tspico_io.py` | "PIO can run up to half the CPU clock": it runs at the full system clock (ROM/BANK at 150 MHz on 270) | |
| C3 | `tspico.py` `MQ_BUSY` docstring | "nothing calls this today": `ACTIVATE_MQ` does (767) | |
| C4 | `tspico.py` `MQ_READY` docstring | Cites "Gustavo's V5 doc" for the polling; PROTOCOL.md and `WAIT_PICO_READY` are the authority | |
| C5 | `tspico.py` 2179–2185 (`SEND_MSG`) and other "DUAL-PORT MIGRATION" blocks | "Y kept at READY for the entire session": the PIO drops it on every OUT | |
| C6 | `tspico.py` `SEND_MSG`, `SEND_MSG2` | `st: bytes` annotation; it is an int | |
| C7 | `tspico.py` 2263–2269 (`SEND_MSG2`) | "back to the inline-wrt pattern": pages are built in RAM and sent by `CMD_SEND` | |
| C8 | `tspico.py` 5283–5285 (`SEND_MSG_PROMPT_YN`) | RX drain "moved below MQ_READY": it is above it (`CMD_RX_FLUSH`) | |
| C9 | `tspico.py` 6167–6168 (above `SA_funct`) | Keys of commands taking a name "need a space at the end": none has one | |
| C10 | `tspico.py` `TAPDIR` header | `CODE 1,n` "n headers either side": the window counts blocks | |
| C11 | `tspico.py` `PICO_STATUS.__init__` | `bank_sm` default "0001 0000" (16); the code computes 1 | |
| C12 | `tspico.py` `log_to_serial` comments (1759, 6096) | "instead of" the log; it is "as well as" | |
| C13 | `tspico.py` `TLM_ENABLED` comment, DEVELOPER_GUIDE §8 | Say to edit `main.py` / rebuild; the switch is `TELEMETRY` in `config.ini` | |
| C14 | `tspico_io.py` `set_ctrl` header | "/BE, A14_L, /U10_CE /U10_OE"; the pins are `U10_ENA`/`U13_ENA`, one enable per chip | |
| C15 | `tspico_io.py` `ENA_SD` comment, PROTOCOL.md §6.2 and §13 | "SAVE_TS can't report it… RACE FIX": `SAVE_TS` now sends its final status after the write (`TSP.save_final`); no RACE FIX comment exists | |
| C16 | `tspico_io.py` `LOAD_TS` docstring | Relies on `MQ.put()` blocking, `MQ.get()` echo, watchdog code 2: now `TX_ROOM`, `RX_WORD`, no code 2 | |
| C17 | `tspico_io.py` `REWIND_ABORTED_SEARCH`, `RX_BLOCK` docstrings | Mention a watchdog that no longer exists | |
| C18 | `tspico_io.py` `SAVE_TS` | Log text "no data after 1s" for a 3 s wait | |
| C19 | `tspico_io.py` `REFUSE_SAVE` docstring | Lists four statuses; `SAVE_TS` sends six | |
| C20 | `tspico_io.py` `RX_CAPTURE` docstring | `raw` is `array('H')`; the dispatcher passes `array('I')` | |
| C21 | `tspico_io.py` dead variables | `LOAD_REFUSE`'s `echo`; `LOAD_TS`'s `blq_t`, `crc` | |
| C22 | `tspico.py` `SEND_MSG2`, `ListMenu`, `PROMPT_EACH` | Dead names: `global kill, dead` in `SEND_MSG2`; `need_ready` in the other two; `hdr3` parameter of `ListMenu` | |
| C23 | `tools/build-flash.py` docstring | Names `src/rom/TSPICO.ROM` for slot 1 and `docs/rom-analysis/FLASH_LAYOUT.md`, which does not exist | |
| C24 | `src/upgrade/updater.asm` line 5, `src/upgrade/upgrade.py` line 4 | Name `tools/build-upgrade.sh`; the script is `tools/build-upgrade.py` | |
| C25 | `src/upgrade/updater.asm` `VARS equ 7600h` | Dead; the variables live in the code block | |
| C26 | `src/upgrade/updater.asm` line 214 | "and return, carry set": the carry is `status`'s and nobody reads it | |
| C27 | `src/upgrade/main.py`, `src/main.py` | GPIO 14 named `WAIT` while `TS_IO_DUAL` waits on it as /PICOSEL (hardware.md marks the resolution unverified) | |
| C28 | `src/upgrade/manifest.py` | Filesystem empty "after flash_nuke"; over WebUSB it is erased through PICOBOOT | |
| C29 | `docs/SAVE_1.1C_VS_1.5.md` §7 | `SAVE_ZX` "has not been migrated"; it has | |
| C30 | `tools/build-rom.sh` header | Calls `src/rom/TSPICO.ROM` "the shipping ROM (slot 1)"; slot 1 is `TSPICO-21.ROM`, `TSPICO.ROM` is the v1.7 base ([rom/overview.md](docs/reference/rom/overview.md#where-comments-and-the-code-disagree)) | |
| C31 | `src/rom/patches/tspico-sync.asm` header | Its output `TSPICO-SYNC.ROM` "the shipping slot-1 ROM"; it is 2.1's base | |
| C32 | `tools/romdiff.py` `IMAGES` comment | v1.7 "the ROM currently shipped" | |
| C33 | `src/rom/fdd/README.md` | The 25D6h disk-token hook "is staged"; it is enabled. "$22A1–$2FFF is left for Gustavo"; ROM 2.0 now uses 2300h–23D3h | |
| C34 | `docs/rom-analysis/README.md`, `MEMORY_MAP.md`, `SYMBOLS.md` | List v1.1's port I/O sites as "the only" ones; 2.x adds 2304h, 2311h, 2320h, 23A7h, 23C0h, 3657h. The dead `OUT (0Fh)` at 2236h is not mentioned | |
| C35 | `docs/rom-analysis/PROTOCOL_FROM_ROM.md`, `SYMBOLS.md` sysvar tables | 5D37h "unclassified": it is the EXROM NMI routine's vector (moved from NMIADD 5CB0h, with the Spectrum's inverted test fixed). 5DDBh described only by its prefix bits; the switches are bits 0 (printer) and 1 (LOAD/SAVE) | |
| C36 | `docs/rom-analysis/DIFF_HOME_vs_STOCK.md` | HOME 0065h "TPI BIOS version, medium confidence": it is the ROM version byte read by `PEEK 101`, changed with G_VERS each release. 041Eh–0421h "dead remnants": 2.1 uses 041Ch–0420h as the BEEPER thunk's tail | |
| C37 | `docs/rom-analysis/SYMBOLS.md` | G_VERS "returns 0x0015": v1.1 only (0021h in 2.1) | |
| C38 | `src/rom/fdd/fddcmd.asm` `READ_STATUS EQU $02B9` | Same name as the curated READ_STATUS (0655h) and `tspico-sync.asm`'s, for a different routine (the curated READ_STATUS_BYTE). Rename the module's EQU | |
| C39 | `docs/rom-analysis/SYMBOLS.md` | Lists an "EWAIT" BIOS entry at 184Eh (`JP 2279h`): 184Eh is the last byte of 184Ch's `JP`. Describes BREAK_ABORT as `POP BC / JP 1A61h` (1.x; 2.0 made it `JP BRK_ABORT`) | |
| C40 | `fddcmd.asm` signature comment | `"FDDCMD"` — "build.py verifies this"; `build-rom.py` does not (it checks that `FDD_DISPATCH` is at 3000h). Add the check or fix the comment | |

## Test docstrings

| # | Where | What | Decision |
|---|---|---|---|
| T1 | `src/test/sd_mount_hosttest.py` | "the boot call keeps the blink loop": `TS2068_IO` catches the `OSError` and boots without a card | |
| T2 | `src/test/sd_wedged_hosttest.py` (also `dir_files_eio_hosttest.py`) | The stub `dev_extcmd` comment says the real one annotates with `StateMachine` without importing it; the current file has no annotations | |

## The reference's own limits

| # | What | Decision |
|---|---|---|
| R2 | `tools/romdisasm.sh` merges every `EQU` in 0100h–3FFFh into the EXROM label file, including the module's HOME addresses: EXROM 1BEFh is labelled `H_EXPT_STR` (a HOME routine) in the middle of STATUS_TO_REPORT's lead-in. Filter out the `H_*` names (or anything the source marks HOME) | |
| R1 | `reference_hosttest.py` matches entries by name only. `src/main.py` and `src/upgrade/main.py` share pin names, so both sets index to `firmware/boot.md` (upgrade.md documents the upgrade ones) | |
| R3 | Name collisions the index cannot tell apart: `tspico-zx48-v3.asm`'s BREAK_KEY (Spectrum ROM 1F54h) and `fddcmd.asm`'s BEEPER (2000h) index to exrom-chunk1.md's BREAK_KEY (2009h) and BEEPER (203Fh); fddcmd's READ_STATUS (C38) likewise. Make the test match an entry to its source file, or rename the EQUs | |
