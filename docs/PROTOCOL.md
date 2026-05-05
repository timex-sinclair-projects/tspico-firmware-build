# TS-Pico TPI Protocol — Implementation Guide

This document explains how the TS-Pico firmware implements Gustavo Pane's
**TPI v2.4 protocol** (Timex Protocol Interface) — the byte-level handshake
that lets a Timex Sinclair 2068 talk to a Raspberry Pi Pico over a
parallel data bus.

It's written for new developers who want to read or extend the firmware.
You don't need to know PIO assembly or Z80 internals — we'll cover the
parts you need as we go.

> The authoritative protocol spec is `TS-PICO-TPI-PROTOCOL-SPECS_2.3.pdf`
> in the TS2068 reference library. This guide is the *engineering*
> companion: how the protocol actually maps onto the RP2040's hardware
> and our Python firmware.

---

## 1. Why two ports?

The TS-2068 uses two adjacent Z80 I/O port addresses:

| Port  | Decimal | Role                               |
|-------|---------|------------------------------------|
| `$0E` | 14      | **Data** port. Bytes flow here.    |
| `$0F` | 15      | **Status** port. Bit 6 = "ready/continue". |

The Z80 ROM (Gustavo's modified EXROM) uses them like this:

```
Z80 wants to send bytes to Pico  : OUT (0Eh), A    [writes A to bus, port 14]
Z80 wants to read a byte         : IN  A, (0Eh)    [reads bus into A, port 14]
Z80 wants to check Pico is ready : IN  A, (0Fh)    [reads port 15, checks BIT 6]
```

Bit 6 specifically? It's a quirk of the Z80 instruction set — `BIT 6,A`
is a single fast instruction. The protocol could have used any bit, but
bit 6 was free in the original design and stuck.

**Why this is called "dual-port"** — earlier TS-Pico firmware (v1.5 and
older) shared a *single* FIFO between both ports: every Z80 IN, on either
port, drained the same FIFO. The Pico had to interleave status bytes
(0x40, with bit 6 set) with data bytes in the right order. That worked
but was timing-marginal — bus glitches during SD↔PIO transitions could
cause "Report D / BREAK CONT repeats" errors.

The dual-port architecture *separates* the two ports at the PIO layer:
`$0E` reads come from the TX FIFO; `$0F` reads come from a hardware
register (PIO scratch register Y) that's independent of the FIFO. The
Pico controls the ready flag directly without consuming FIFO bytes.

---

## 2. The PIO state machine (`TS_IO_DUAL`)

The Pico's RP2040 has a *Programmable I/O* (PIO) subsystem — small
state machines that run independently of the CPU and can react to bus
events in nanoseconds. We use one PIO state machine to handle every
Z80 bus cycle on ports `$0E` and `$0F`.

```
src/TS/tspico_io.py:
  @asm_pio(...)
  def TS_IO_DUAL():
      ...
```

### What it does, in plain English

For every Z80 I/O cycle on `$0E` or `$0F`:

1. **Wait** for `/PICOSEL` (GPIO 14) to go LOW — that signals "Z80 is
   talking to one of our ports right now".
2. **Check** GPIO 11 (R/W select):
   - HIGH → Z80 is *writing* (an OUT instruction). Sample the data lines
     plus address bit 0 (A0), push 9 bits to the RX FIFO.
   - LOW  → Z80 is *reading* (an IN instruction). Decode A0:
     - **A0 = 0 → port `$0E`**: pull a byte from the TX FIFO (or 0x00 if
       empty), drive it onto D0–D7.
     - **A0 = 1 → port `$0F`**: copy scratch register Y onto D0–D7.
       (FIFO is *not* touched.)
3. **Wait** for `/PICOSEL` to go HIGH — Z80 is done.
4. Loop back to step 1.

### Pin assignments

| GPIO | Role                                          |
|------|-----------------------------------------------|
| 2-9  | D0-D7 (data bus, bidirectional via U6 buffer) |
| 10   | A0 (address bit 0 → distinguishes `$0E`/`$0F`)|
| 11   | R/W select (1 = Z80 OUT, 0 = Z80 IN)          |
| 12   | U6 buffer enable (sideset, active LOW)        |
| 14   | `/PICOSEL` (active LOW = "Z80 is on our port")|

### Why `pull(noblock)` and not `pull(block)`?

When the Z80 reads `$0E` and the TX FIFO is empty, the PIO has two
choices:

- **`pull(block)`** would stall the state machine until Pico writes
  a byte. Sounds great — Pico gets unlimited time. **But** the TS-Pico
  hardware doesn't route the SM's stall to the Z80's `/WAIT` line. So
  the Z80 isn't actually paused — it just reads garbage off the floating
  bus while the SM sits there. Worse, subsequent bus cycles go undetected.
- **`pull(noblock)`** doesn't stall. If the FIFO is empty, the byte
  driven onto the bus is whatever the X register holds (which equals
  the A0 bit, i.e. 0 for `$0E`). The Z80 reads `0x00`.

`0x00` happens to be the Z80 ROM's "Invalid I/O Device" status code, so
an unprepared Pico immediately and obviously fails. That's a feature: it
forces the firmware to obey the protocol contract — keep the right
bytes in the FIFO at the right time.

---

## 3. The "ready forever" architecture

The simplest mental model for the firmware:

> **Y is set to `0xFFFFFFFF` once at boot, and never changed.**

That means port `$0F` always returns `0xFF` (all bits set, including
bit 6). Whenever the Z80 polls `$0F`, it sees "ready" instantly and
moves on.

Since we never make Z80 wait via the status flag, all flow control
happens via the data port:

- **TX FIFO depth (4 bytes deep)** + **Z80's read rate (~47µs/byte)** =
  Pico has plenty of time to fill in the next byte before the FIFO
  empties. `MQ.put()` blocks when full, so `for b in content: MQ.put(b)`
  paces itself.
- **Pre-loaded status byte**: before each command-response cycle, a
  `0x01` "OK" status byte is sitting in the TX FIFO ready for the Z80
  to read. The chain of `0x01`s is maintained by every handler writing
  one at the end of its response (see §5).

You'll see comments in `MQ_BUSY()` and `MQ_READY()` referring to the old
"set Y=0 to make Z80 wait" pattern. Those helpers exist for legacy
paths (SD card transitions, etc.) but in the LOAD/data-block path we
never use them. The Z80 ROM has a long timeout (~20 seconds) on `$0F`
polling, so even if a future handler did set Y=0 briefly for slow work,
the protocol would still succeed.

---

## 4. The byte sequence of one LVM LOAD

This is what actually happens on the wire when you type `LOAD ""` on
the TS-2068. Times are approximate.

```
Time  | Direction  | Bytes / what's happening
------|------------|-----------------------------------------------------
 t=0  | Z80 → Pico | 10-byte pre-header on $0E (one OUT every ~30µs):
      |            |   [0] block_type    (0x00 header / 0xFF data)
      |            |   [1] TADDR         (1 = LOAD)
      |            |   [2] BANK          (0xFF = HOME)
      |            |   [3,4] SESSION_ID  (LE 16-bit)
      |            |   [5,6] MEMORY_ADDR (LE 16-bit)
      |            |   [7,8] BLOCK_LEN   (LE 16-bit, BASIC's view)
      |            |   [9]   CRC         (XOR of pre[0..8])
      |            |
+~290µs           | Z80 → Pico | Done. Z80 reads $0E for status.
                  |            | TX FIFO had 0x01 pre-loaded → Z80 reads
                  |            | 0x01 = "OK".
                  |            |
+~300µs | Pico's main loop sees rx_fifo > 0, drains pre[].
        | Dispatches to LOAD_TS().
        |
        | LOAD_TS opens /TMP/temp.tap at TSP.offset, reads
        | the 3-byte block prefix [len_lo, len_hi, type].
        | Validates type matches pre[0]. Reads content.
        |
        | LOAD_TS streams to TX FIFO:
        |    block_type, content[0], content[1], ..., CRC
        | (For a header: 19 bytes; for the data block: blk_len bytes.)
        |
+...    | Z80 → Pico | Z80 has been polling $0F (always reads 0xFF=ready)
                     | and now reads $0E for the data sequence:
                     |   - block_type (used to seed CRC accumulator)
                     |   - content bytes (stored at IX into RAM)
                     |   - file CRC byte (verified against accumulator)
                     | Z80 reads at ~47µs/byte.
                     |
+...    | Z80 → Pico | After data loop, Z80 OUTs:
                     |   - block_type ack (echoes its expected type)
                     |   - its own computed CRC (for verification)
                     |
+...    | LOAD_TS drains the two echo bytes via MQ.get().
        | Then writes:
        |   MQ.put(0x01)   ← Z80 reads as "final status OK"
        |   MQ.put(0x01)   ← stays in FIFO for the NEXT command's
        |                    initial status read
        | LOAD_TS returns. Main loop resumes.
        |
        | If this was the header block, BASIC now displays
        | "Bytes: <name>" and issues a NEW pre-header for the
        | data block. The cycle repeats from t=0.
```

Key takeaways:

- The Z80's first `$0E` read happens in **microseconds**, not after
  the Pico has had time to drain the pre-header. So the Pico must have
  the status byte in the FIFO **before** the LOAD command is issued.
  We achieve that with the chained pre-load (each handler writes the
  next `0x01` before returning).
- Inside the data loop, Pico writes much faster than Z80 reads. The
  4-deep FIFO + `MQ.put` blocking gives natural backpressure.
- The Z80 echoes its work (ack + CRC) so Pico can verify the transfer
  completed correctly.

---

## 5. Writing a new command handler

If you want to add a handler (for a new TPI command, etc.), follow this
template:

```python
def MY_HANDLER(pre, MQ, TSP):
    """Handler for some Z80 command type."""
    log_entries = ""

    # 1. (optional) Read what Z80 is asking for
    #    e.g., from pre[1..9], TSP.f_name, etc.

    # 2. Prepare the response data
    #    e.g., open a file, format a string, etc.

    # 3. Stream the response to TX FIFO
    for byte in response_bytes:
        MQ.put(byte)         # blocks if FIFO full — paced by Z80 reads

    # 4. Drain any echo bytes the Z80 sends back
    #    (depends on protocol — LOAD echoes 2 bytes, others may differ)
    echo = MQ.get() & 0xFF

    # 5. Final status + next-iteration pre-load — REQUIRED
    MQ.put(0x01)             # final status the Z80 will read
    MQ.put(0x01)             # pre-load for the NEXT command's status

    return MQ, TSP, log_entries
```

The two `MQ.put(0x01)` writes at the end are non-negotiable. Without
them, the next command will see `0x00` for status (FIFO empty) and
fail with "Report J - Invalid I/O Device".

If your handler does *slow* work (SD card I/O, large file reads), and
you want Z80 to clearly see "Pico is busy, please wait" rather than
silently waiting on $0E reads, you can briefly set Y=0:

```python
MQ_BUSY()        # Y = 0, port $0F bit 6 clear, Z80 polls and waits
do_slow_work()
MQ_READY()       # Y = 0xFFFFFFFF restored
# ...continue with response...
```

The Z80 ROM has a ~20-second timeout on `$0F` polling, so this is safe
for any reasonable amount of work. For LVM LOAD specifically, we don't
bother — Pico is always fast enough relative to Z80's read rate.

---

## 6. Debugging: protocol observers

The repo includes test harnesses in `test/protocol_observer_v*.py`:

- `protocol_observer_silent.py` — does nothing but log every Z80 OUT
  to a buffer. Useful for seeing the raw pre-header without any Pico
  response interfering.
- `protocol_observer_v3.py` — captures pre-header + writes a status
  response. Demonstrates the timing constraint (Pico's reaction in
  Python is too slow if you don't pre-load).
- `protocol_observer_v4.py` — pre-loads `0x01` and observes the full
  transaction including Z80's echo bytes.
- `protocol_observer_v5.py` — sends a real header response from
  `/sd/TAP/pt.tap`. The TS-2068 should display "Program: <name>"
  (or similar) if the protocol is working.
- `protocol_observer_v6.py` — handles **both** the header and data
  block, completing a full LOAD. The TS-2068 actually loads and runs
  the program.

These were used to develop and verify the dual-port architecture. They
print buffered logs (no live prints during the protocol — those would
inject ms-scale delays and break timing) and dump them on `Ctrl-C`.

If you're adding a new protocol path, **start by writing an observer**.
Capture what the Z80 actually does, then iterate until your responses
match what the Z80 expects.

---

## 7. Pitfalls

- **Don't `print()` during a protocol exchange.** USB serial prints
  take 5-10 ms, and the PIO RX FIFO is only 4 bytes deep. A print mid-
  pre-header drops Z80 OUTs.
- **Don't `MQ.put()` between draining pre-header and starting the data
  response.** Any byte put there ends up *before* the response in the
  FIFO and shifts the data stream by one byte. Z80's CRC will mismatch
  and you'll see "Report R - Tape Loading Error".
- **Don't toggle Y to BUSY mid-data-block.** The Z80's $0F polling is
  not the bottleneck — its $0E read rate is. Setting Y=BUSY won't speed
  anything up and may confuse future readers of the code.
- **If `LOAD_TS` returns without writing the trailing two `0x01`s, the
  next LOAD will hang or fail with Report J.** The pre-load chain is
  load-bearing; honor it in any new handler.

---

## 8. Where to look in the source

| File                       | What's in it                            |
|----------------------------|-----------------------------------------|
| `src/TS/tspico_io.py`      | PIO programs (`TS_IO_DUAL`, `set_ctrl`, |
|                            | `sel_bank`, etc.); LVM handlers (LOAD_TS, |
|                            | SAVE_TS); helper utilities (LOG_ADD,    |
|                            | END_MSG, ABORT_TX).                     |
| `src/TS/tspico.py`         | Main I/O dispatch loop (`TS2068_IO`),   |
|                            | high-level commands (DIR, CD, etc.),    |
|                            | configuration (`PICO_STATUS`).          |
| `src/TS/sdcard.py`         | SD card driver (SPI).                   |
| `src/TS/extcmd.py`         | User-extensible command dictionary.     |
| `test/protocol_observer_*` | Bus-level test harnesses — see §6.      |
| `manifest.py`              | MicroPython freeze manifest. Adding new |
|                            | files to `src/TS/` requires updating    |
|                            | this so they get baked into the UF2.    |

---

## 9. Further reading

- **Gustavo's spec**: `TS-PICO-TPI-PROTOCOL-SPECS_2.3.pdf` (in the
  TS2068 reference library). Authoritative byte-level documentation.
- **Z80 ROM disassembly**: `gus-exrom.asm` (in the TS2068 reference
  library). The actual machine code that runs on the TS-2068. Search
  for `sub_1a54h` (the WF_NPH polling loop), `sub_2298h` (IN $0E),
  `sub_229dh` (OUT $0E), `l196dh` (LOAD entry point).
- **MicroPython rp2 module**:
  https://docs.micropython.org/en/latest/library/rp2.html
- **RP2040 PIO reference**:
  https://datasheets.raspberrypi.com/rp2040/rp2040-datasheet.pdf
  (Chapter 3 — PIO).
