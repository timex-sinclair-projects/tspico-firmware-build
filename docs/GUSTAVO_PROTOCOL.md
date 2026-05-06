# Gustavo's Protocol & ROM Modifications

A primer for new contributors to understand **what** Gustavo Pane built
and **why** before reading the firmware.

This document is the high-level design view. The companion document
[`PROTOCOL.md`](PROTOCOL.md) is the firmware-implementation view (what
the Pico does to honor the protocol).

> All credit for the protocol design and the Z80 ROM modifications goes
> to **Gustavo Pane** ([panegustavo@yahoo.com.ar](mailto:panegustavo@yahoo.com.ar)).
> This project's firmware is one implementation of his spec.

---

## 1. The problem Gustavo solved

The Timex Sinclair 2068 (released 1983) is a Z80-based home computer
with 64KB of memory and built-in BASIC. It has cassette tape I/O for
storage, but tape is slow, fragile, and can't share data with modern
systems.

Gustavo wanted a **fast, reliable, modern storage interface** that:

1. Drops in transparently — no soldering, no motherboard mods.
2. Supports SD cards for storage.
3. Can run any program that the original cassette LOAD could run.
4. Adds new commands (directory listings, file management, etc.) without
   breaking BASIC.

His insight was that two things had to change for this to work:

- **The Z80 needed updated ROM code** that knew how to talk to a fast
  parallel device instead of the slow serial cassette interface.
- **The hardware needed a way to expose Z80 I/O ports to a modern MCU**
  (the Raspberry Pi Pico) for the actual data exchange.

Gustavo designed both: the **TPI protocol** (TS-Pico Interface) and a
**modified pair of Z80 ROMs** that implement the TS-2068 side of it.

---

## 2. The TS-2068 has two ROMs

To understand the modifications, you need to know the TS-2068 has two
ROMs that both occupy the lower 16KB of address space (`$0000-$3FFF`):

| ROM | When active | What it does |
|---|---|---|
| **HOME ROM** | After power-on, default | Standard TS-2068 BASIC + tape routines. Mostly compatible with ZX Spectrum. |
| **EXROM** ("Extension ROM") | When BASIC executes a special instruction or accesses certain addresses | Adds Timex-specific features: AROS (Application ROS), bank-switching, extended cartridge support. |

Hardware switches between them by toggling which ROM chip is enabled
on the address bus. Most BASIC stays in the HOME ROM; only certain
operations bank in the EXROM briefly.

Gustavo modified **both**:

- `gus-home.rom` — modified HOME ROM. Source: `gus-home.asm` in the
  TS2068 reference library.
- `gus-exrom.rom` — modified EXROM. Source: `gus-exrom.asm`.

Both modified ROMs live in the **TS-Pico's external flash chip** (the SST 39SF040 flash on the TS-Pico board, separate from the Pico's
own internal flash). When the TS-2068 reads a ROM address, the TS-Pico
hardware routes that read to its flash chip, which serves the modified
byte.

> If you've ever wondered why the TS-2068 won't boot when the Pico
> isn't running our firmware: it's because the Pico's PIO state machine
> (`set_ctrl` in `tspico_io.py`) is what asserts the `/BE` line that
> enables the TS-Pico's flash. No PIO running, no ROM bytes on the bus,
> no boot. See [`PROTOCOL.md`](PROTOCOL.md) §2 for that side of it.

---

## 3. The two new I/O ports

Gustavo's protocol uses two Z80 I/O ports:

| Port | Decimal | Direction | Purpose |
|---|---|---|---|
| `$0E` | 14 | bidirectional 8-bit | **Data port.** Bytes flow here. |
| `$0F` | 15 | bidirectional 8-bit | **Control port.** Bit 6 = "continue/ready". |

Why these specific addresses? The TS-2068 has many existing port
allocations — `$FE` for keyboard/border, `$F4`/`$F5`/`$F6` for the
horizontal scroll register, `$DF`/`$F4` for the dock cartridge. Ports
`$0E` and `$0F` were unused in the original design, so the TS-Pico
hardware can claim them without conflicts.

The Pico decodes `$0E` and `$0F` via its PIO state machine (see
[`PROTOCOL.md`](PROTOCOL.md) §2 for hardware/PIO details). The
decoded address bit A0 distinguishes them: `$0E` has A0=0, `$0F` has
A0=1.

Why bit 6 of `$0F`? The Z80 instruction `BIT 6,A` is a fast (8 T-state)
test that sets the zero flag based on bit 6 alone. Gustavo's code uses
this exact instruction in tight polling loops — fast, compact, and
no register clobbering.

---

## 4. The basic exchange

Every TPI exchange follows a three-phase pattern:

```
                Z80                                 Pico
                 │                                    │
  Phase 1:       │  ──── 10-byte pre-header ───→     │ "I'm starting a
   command       │                                    │  command. Here are
   announcement  │                                    │  the parameters."
                 │                                    │
                 │  ←── 0x01 status (port $0E) ──     │ "OK, ready to
                 │  ←── 0x40 continue (port $0F) ──   │  proceed."
                 │                                    │
  Phase 2:       │  ──── command-specific bulk ───→  │ Body of the
   data exchange │       OR  ←── data response ───   │ command (or its
                 │                                    │ response).
                 │                                    │
                 │  ←── 0x01 status ──                │ "Done; result OK."
                 │                                    │
  Phase 3:       │  (next phase or next command)
```

The exact shape of Phase 2 depends on the command type (LOAD vs SAVE
vs BASIC command), but Phases 1 and 3 are universal.

The 10-byte pre-header (Phase 1) carries the command type and its
parameters. Layout:

| Offset | Field | Notes |
|---|---|---|
| 0 | `BLOCK_TYPE` | Top-level command class — see §5 |
| 1 | `TADDR` | Sub-operation: 0=SAVE, 1=LOAD, 2=VERIFY, 3=MERGE, ... |
| 2 | `BANK` | 0xFF=HOME, 0..N for banked memory |
| 3-4 | `SESSION_ID` | 16-bit LE, identifies a multi-block transaction |
| 5-6 | `MEMORY_ADDR` | Where data goes (for LOAD) or comes from (for SAVE) |
| 7-8 | `BLOCK_LEN` | Size of the upcoming data |
| 9 | `CRC` | XOR of bytes 0..8 |

When the Z80 sees `LOAD ""`, the modified BASIC code builds and OUTs
this 10-byte header to port `$0E`, then waits.

---

## 5. Block types — multiple command families

Byte 0 of the pre-header (`BLOCK_TYPE`) determines what kind of
exchange this is:

| Value | Meaning |
|---|---|
| `0x00` | **HEADER** block (first half of an LVM tape operation) |
| `0xFF` | **DATA** block (second half of an LVM tape operation) |
| `0x42` `'B'` | **BASIC command** (e.g. `TPI:DIR`, `TPI:CD`) |
| `0x43` `'C'` | CP/M CBIOS command (reserved, future) |
| `0x44` `'D'` | DATA block from a BASIC command |
| `0x45` `'E'` | EXTRA data (reserved) |
| `0x42` `'A'` | Assembler command (reserved) |

`LVM` ("Linear Volume Mode" — Gustavo's term) is the BASIC tape
operation family: SAVE, LOAD, VERIFY, MERGE. Each works in two phases
on the wire — first a HEADER block (`BLOCK_TYPE=0x00`), then a DATA
block (`BLOCK_TYPE=0xFF`). This mirrors how the original ZX Spectrum
tape format encoded blocks on cassette.

`BASIC commands` are Gustavo's extension. The Z80 BASIC syntax `LOAD
"TPI:somecommand"` or `SAVE "TPI:somecommand"` triggers these. The Pico
handles them entirely (e.g., listing the SD card directory) and returns
text or status. They're not really LOAD or SAVE — the BASIC keyword is
just the trigger. Inside the protocol they're `BLOCK_TYPE=0x42`.

---

## 6. The CRC formula has a quirk

There are **two CRCs** in the protocol with different formulas:

**Pre-header CRC** (byte 9 of the 10-byte pre-header):
- = `XOR of bytes 0..8` (all bytes, no skipping)

**Block CRC** (last byte of HEADER and DATA blocks):
- = `XOR of [0] + [3..N-1]` — **skips the 2 session-ID bytes** at
  positions [1] and [2]

Why the skip? Because Gustavo wanted his TPI blocks to be **convertible
to standard ZX Spectrum TAP files** (and back). Standard ZX TAP CRC is
XOR of `block_type + content`. Gustavo added the 2-byte session ID for
TPI's multi-block transaction tracking, but kept the CRC formula
matching ZX so converting between formats just means stripping (or
inserting) the session bytes — no CRC recomputation needed.

This matters when you write a SAVE handler that has to verify what the
Z80 sent: the CRC formula skips the session bytes, so your XOR loop
has to do the same.

---

## 7. The "ready forever" timer trick

The original protocol spec (page 2) says:

> In the phase of wait for execution a 2.8ms timer is activated. While
> the TS-2068 is waiting the continue signal, reading the bit 6 at port
> 0x0F, the TS-PICO should execute the command and respond during that
> period of time.

2.8ms is **way too short** for any realistic file I/O (mounting an SD
card, reading a 16KB file). Gustavo's actual ROM uses a much longer
timeout — about **20 seconds** — to give the Pico room to do real work.

This means our firmware doesn't have to race the clock. We keep the
ready flag set most of the time and rely on the Pico being faster than
the Z80's read pace; the long timeout is just a safety net. See
[`PROTOCOL.md`](PROTOCOL.md) §3 for how that works in firmware.

---

## 8. Status codes and error reports

When a command finishes, the Pico sends back a status byte. The Z80
ROM dispatches based on it:

| Code | Meaning | TS-2068 BASIC report |
|---|---|---|
| `0x00` | (no driver) | **Report J** — INVALID I/O DEVICE |
| `0x01` | OK | (silent success or `0 OK`) |
| `0x02` | Tape loading error | **Report R** — TAPE LOADING ERROR |
| `0x03` | Invalid filename | **Report F** — INVALID FILE NAME |
| `0x04` | Parameter error | **Report Q** — PARAMETER ERROR |
| `0x05` | Nonsense in BASIC | **Report C** — NONSENSE IN BASIC |
| `0x06` | Number too big | **Report 6** — NUMBER TOO BIG |
| `0x07` | End of file | **Report 8** — END OF FILE |
| `0x08` | Invalid argument | **Report A** — INVALID ARGUMENT |
| `0x09` | Stop | **Report 9** — STOP |
| `0x0A`+ | misc | **Report J** — INVALID I/O DEVICE |
| `0x80`+ | Function code | (extended, see below) |

The Pico can also return a **function code** (`0x80`-`0xFF`) instead
of a status. These tell the Z80 ROM: "don't just return — do this
post-action with the rest of the data I'm about to send." Useful ones:

| Code | Function |
|---|---|
| `0x81` | PRINT_STRING — print the following NULL-terminated string |
| `0x82` | PRINT_STRING_AND_RETURN_KEY — print, then wait for keypress |
| `0x83` | PRINT_CHARACTER — print a single byte |
| `0x84` | RETURN_KEY — wait for keypress, return the ASCII code |
| `0x85` | GET_STATUS — return device status (KBD/AUX/PRN/DISK) |
| `0x86` | PRINT_STRING_WITH_LOOP — for paged DIR output (Y/N at end) |

These let the Pico render output on the TS-2068 screen without the
Pico itself having a video framebuffer. The DIR command, for instance,
sends `0x86` followed by a directory listing followed by "CONTINUE
(Y/N)?"; the Z80 ROM prints, waits for Y or N, and either loops to the
Pico for another page or stops.

---

## 9. WF_NPH — the heart of the polling loop

The Z80 ROM's `WF_NPH` ("Wait For NoN-Polling Halt"? Gustavo's name)
routine at EXROM `$1A54` is what implements the "wait for ready" side
of the protocol:

```
sub_1a54h:
    push af
    push bc
    ld   b, 0E2h                  ; 226 iterations (= ~8ms at 3.5MHz Z80)
loop:
    call sub_0655h                ; reads port $0F (with BREAK key check)
    bit  6, a                     ; test BIT 6 of result
    jr   nz, success              ; if BIT 6 set → continue
    djnz loop                     ; otherwise loop
    ld   a, 002h                  ; out of iterations → status code 2
    scf                           ; carry set = error
    ret
success:
    ccf                           ; carry clear = OK
    ret
```

In the original disassembly, `B = 0xE2 = 226` gives ~8ms timeout. In
the actual ROM running on real hardware, this counter is larger (giving
~20s). Either an outer-loop wraps this, or the inner counter was
extended. Either way, the firmware can take its time.

`sub_0655h` is interesting because it's also where the BREAK key gets
checked — if the user presses BREAK while the Pico is busy, the Z80
exits the polling loop with an error. This is how programs can be
aborted mid-LOAD.

---

## 10. A complete walk-through: `LOAD ""`

Here's what happens when a user types `LOAD ""` on the TS-2068, in
narrative form:

1. **BASIC tokenizer** parses the line and dispatches to the LVM
   tape-load routine in the modified EXROM.
2. The EXROM's LVM-LOAD code (entry point near `$196D`) builds a
   10-byte pre-header in RAM:
   - `BLOCK_TYPE=0x00` (HEADER block — we want the TAP's header first)
   - `TADDR=0x01` (LOAD)
   - `BANK=0xFF` (HOME bank)
   - `SESSION_ID = some random 16-bit value` (so we can tell this
     LOAD from any subsequent transactions)
   - `MEMORY_ADDR` = a tape-system variable's address (where the
     Z80 wants the loaded header to go in memory)
   - `BLOCK_LEN` = 17 (size of the standard ZX header)
   - `CRC` = XOR of the above
3. The Z80 OUTs each byte of the pre-header to port `$0E` in turn,
   ~30µs apart at 3.5MHz.
4. The Pico's PIO state machine captures each OUT into its RX FIFO
   (4 entries deep). The MicroPython main loop drains them.
5. The Pico's main dispatcher reads `BLOCK_TYPE=0x00, TADDR=0x01` and
   knows this is an LVM LOAD. It calls `LOAD_TS()`.
6. `LOAD_TS()` opens the currently-mounted TAP file at the current
   offset, reads the block prefix (`[len_lo, len_hi, type]`), validates
   that `type` matches `BLOCK_TYPE` from the pre-header, then streams
   `block_type + content_bytes + CRC` (19 bytes total for a header) to
   the TX FIFO.
7. Meanwhile the Z80 has been polling port `$0F` waiting for bit 6 to
   go high. The Pico's Y register is already set to `0xFFFFFFFF` (so
   `$0F` reads as `0xFF`, bit 6 set), so this poll succeeds instantly
   — the Pico doesn't need to do anything special.
8. Z80 then reads port `$0E` for the status byte. The TX FIFO had a
   pre-loaded `0x01` (from the previous transaction's tail, or from
   boot init); Z80 reads it and proceeds.
9. Z80 enters its "data loop" reading port `$0E` repeatedly. Each
   read drains one byte from the TX FIFO. `LOAD_TS()` keeps writing
   bytes to TX as fast as Z80 reads them (Z80 is the bottleneck —
   ~47µs per byte due to its instruction loop).
10. After Z80 reads the last byte (the file's CRC), it OUTs back to
    `$0E` two echo bytes: the block type it expected, and its own
    computed CRC over the data it received. `LOAD_TS()` drains these.
11. `LOAD_TS()` writes two final `0x01` bytes — one as the final
    status (Z80 reads it), one as a pre-load for the *next*
    transaction's status byte. Returns.
12. Z80's BASIC ROM, having received a valid header block, displays
    "Program: tspicotest" on screen (or whatever the header named).
13. **Z80 immediately issues a second pre-header** asking for a DATA
    block (`BLOCK_TYPE=0xFF`) with the same session ID. Steps 3–11
    repeat with the data block instead of the header.
14. When the data block transfers cleanly, the program is in memory.
    BASIC then auto-runs it (if the header's autorun-line field
    indicated so) or returns to the READY prompt.

The whole thing takes a few hundred milliseconds for a small program.
The 14KB `tspicotest` we used during development takes about 700ms,
limited entirely by Z80's read rate.

---

## 11. Reading the Z80 source

If you want to see the Z80 side of all this, the modified EXROM source
is `gus-exrom.asm` in the TS2068 reference library. The interesting
addresses:

| Address | Routine | What it does |
|---|---|---|
| `$0655` | `sub_0655h` | Read `$0F` with BREAK-key check |
| `$1A54` | `sub_1a54h` (`WF_NPH`) | Poll `$0F` until bit 6 set or timeout |
| `$2298` | `sub_2298h` | IN A, ($0E) — read data port |
| `$229D` | `sub_229dh` | OUT ($0E), A — write data port |
| `$1924` | `sub_1924h` | OUT $0E ack helper |
| `$196D` | `l196dh` | LVM dispatch entry (LOAD/SAVE/etc) |
| `$1BF3` | `l1bf3h` | Error dispatcher (status → Report X) |

The original ZX Spectrum LD-BYTES routine at `$0556` is replaced
entirely by Gustavo's TPI version — instead of reading a tape pulse
stream, it reads bytes from `$0E` with `WF_NPH` between phases.

The `gus-rom-analysis.md` doc in the reference library has more
annotation on Gustavo's specific ROM patches.

---

## 12. What this firmware adds on top

Gustavo's protocol spec defines the wire format and the Z80 side. This
project's firmware is the **Pico-side implementation** of the spec.
Its job is:

1. **Decode** Z80 bus cycles into RX bytes + drive TX bytes onto the
   bus — handled by the `TS_IO_DUAL` PIO state machine.
2. **Implement the dispatcher** — receive pre-headers, identify the
   command, route to the right handler.
3. **Implement the command handlers** — `LOAD_TS`, `SAVE_TS`,
   `PROCESS_CMD` (BASIC commands), `PROCESS_ASM` (assembler).
4. **Manage TS-Pico hardware** — the external flash chip serving the
   modified ROMs (via `set_ctrl` and `sel_bank` PIOs), SD card I/O,
   bank-switching for the TS-Pico's flash slots.
5. **Provide a SD-card filesystem** — Gustavo's protocol doesn't say
   anything about where files come from; we use a FAT-formatted SD
   card with a `/TAP/` directory.

For details on the firmware-side implementation, see
[`PROTOCOL.md`](PROTOCOL.md). For the higher-level command set
(`TPI:DIR`, `TPI:CD`, etc.), see the user manual and Gustavo's
"BASIC EXTENSIONS" PDF in the reference library.

---

## 13. Where to learn more

In the [TS2068 reference library](https://github.com/) (separate
private repo Gustavo shares with developers):

- `TS-PICO-TPI-PROTOCOL-SPECS_2.3.pdf` — Gustavo's authoritative
  protocol spec. Read this if you're going to write any wire-level
  code.
- `TS-PICO-TPI_BASIC_EXTRENSIONS_V14_BETA.pdf` — list of TPI BASIC
  commands (`TPI:DIR`, `TPI:CD`, etc.) and their semantics.
- `TS-PICO_FILE_SYSTEM-SPECS-BETA-PRE-RELEASE-V25.pdf` — file system
  conventions (TAP files, DCK cartridges, ROM images).
- `gus-home.asm` — modified HOME ROM source, with comments.
- `gus-exrom.asm` — modified EXROM source.
- `gus-rom-analysis.md` — additional annotations on the ROM mods.
- `tspico-d-error-code-context.txt` — the famous "Report D" error
  investigation notes (background on why we ended up with the dual-port
  architecture).

In this repo:

- [`PROTOCOL.md`](PROTOCOL.md) — firmware implementation guide.
- `test/protocol_observer_*.py` — bus-level observation harnesses,
  great for understanding the protocol by watching it in action.
- `test/save_observer.py` — captures and decodes Z80 SAVE traffic.
- `test/make_test_tap.py` — generates a tiny test TAP file.

If you find an inconsistency between Gustavo's spec and the actual
Z80 ROM behavior: trust the ROM. Gustavo wrote both and the code is
the authoritative reference. The PDFs occasionally have stale details.

---

## 14. Acknowledgments

- **Gustavo Pane** — protocol design, ROM modifications, TS-Pico
  hardware co-designer.
- **Jeff Wilhelm**, **Ricardo F. Lopes** — TS-Pico hardware design.
- **The TS-2068 community** — for keeping a 1983 computer worth
  modernizing.

---

*This document is part of an open-source effort to make the TS-Pico
firmware approachable to new contributors. Corrections, additions, and
better explanations are welcome — open an issue or PR.*
