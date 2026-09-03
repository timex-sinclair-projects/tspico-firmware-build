# TS-Pico TPI Protocol — Implementation Guide

This document explains how the TS-Pico firmware implements Gustavo Pane's
**TPI v2.4 protocol** (Timex Protocol Interface) — the byte-level handshake
that lets a Timex Sinclair 2068 talk to a Raspberry Pi Pico over a
parallel data bus.

It's written for new developers who want to read or extend the firmware.
You don't need to know PIO assembly or Z80 internals — we'll cover the
parts you need as we go.

> **Source-code paths in this doc** (e.g. `TS/tspico_io.py`) are
> Python-package paths. The actual files live under `src/` in the repo
> — `TS/tspico_io.py` is at `src/TS/tspico_io.py`.

> **Looking for the design context first?** Read
> [`GUSTAVO_PROTOCOL.md`](GUSTAVO_PROTOCOL.md) — it explains the
> protocol from the design side: what Gustavo built, why he modified
> the Z80 ROM, what the high-level command flow looks like.
> This document picks up where that one ends, focusing on the
> Pico/firmware side.

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
TS/tspico_io.py:
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
- **An early return re-arms too — and with ONE `0x01`, not two.**
  `LOAD_TS`'s abort paths skip the V6 chain by construction, and the
  watchdog has just drained both FIFOs, so TX comes back empty and Y is
  left wherever the partial Z80 OUTs dropped it. That is the rule above
  firing on an error path: the next command's status read finds nothing
  and gets Report J. `REARM_AFTER_LOAD_ABORT()` writes the one pre-load
  byte and restores Y, *after* `ABORT_TX` (anything staged before it is
  eaten by the watchdog's `pull(noblock)` cleanup loop). One byte,
  because the pair on the normal path exists only so the Z80 can consume
  the first as this transaction's final status — after an abort it has
  already reported and gone, and a second byte would be read as the
  first byte of the next response: the one-byte shift that surfaces as
  Report R. `SAVE_TS` is exempt only because the dispatcher calls
  `ACTIVATE_MQ()` after it and re-arms with its own `MQ.put(0x01)`;
  **nothing runs after `LOAD_TS` returns.** Found via VERIFY, which
  makes the Z80 abandon the transfer mid-block as soon as the comparison
  fails — the R is correct, the J on everything after it was not.
- **Don't pre-load `0x01` inside `ACTIVATE_MQ()`.** It's tempting (the
  pre-load chain expects a status byte ready in TX after the SM is
  re-activated), but `ACTIVATE_MQ` is called both at boot AND mid-
  command (e.g., after SD card access in `MOUNT_FILE`). Mid-command,
  the next call in the chain is usually `SEND_MSG` which writes its
  own status byte — pre-loading inside `ACTIVATE_MQ` would put TWO
  status bytes in TX, the Z80 reads ONE and considers the response
  done, and `SEND_MSG`'s drain-wait loops forever. Pre-loading
  belongs **at boot** (one explicit `MQ.put(0x01)` in `TS2068_IO()`)
  and at the **tail of each command handler** (the V6 chain).
- **Don't call `END_MSG()` after the final status + pre-load writes
  in LVM handlers.** `END_MSG` writes its own `0x01` status byte to TX
  for the non-verbose case (and a verbose directive header for verbose
  mode). If your handler already wrote `MQ.put(0x01)` × 2 (final +
  pre-load), `END_MSG` adds a THIRD `0x01`. The first two are consumed
  correctly (final status + next-iter status) but the third sits in TX
  and gets read as the FIRST byte of the next iteration's data-loop
  reads, where the Z80 expects the block_type byte. The Z80's running
  CRC accumulator drifts by one byte from the start, the final CRC
  check fails, and you get "Report R — Tape Loading Error" on the data
  block. If you want a verbose status message, write the directive
  bytes BEFORE the pre-load `0x01` so the directive IS the final
  response, not an addition.
- **Validate a SAVE before you write the final status, not after.** The
  V6 chain's `MQ.put(0x01)` final status IS the Z80 printing `0 OK` —
  once it's in TX, the transaction is decided. Any check that runs after
  it can only report into a Z80 that has already gone back to the BASIC
  prompt and stopped reading `$0E`, so the report has nowhere to go and
  the handler blocks in `MQ.put` on a full 4-deep TX FIFO. The `WATCHDOG`
  can't rescue it either: `dead = True` is set alongside the final status,
  so that thread has already exited. `SAVE "bad file"` used to do exactly
  this — a false `0 OK` followed by a wedged Pico until reset.

  The place to refuse a SAVE is the **post-header status read**, where
  `SAVE_TS` writes the mid-phase `0x01`. Write an error status there
  instead and the Z80's `STATUS_TO_REPORT` path RST-8's, shows the BASIC
  report, and aborts *before* sending the data block. Both current guards
  use this: `BLEN == 0` → `0x08` (Report A, empty program) and a
  disallowed filename → `0x03` (Report F). Follow either as a template,
  and finish with `DRAIN_REFUSED_SAVE()` so a Z80 that sends the data
  block anyway doesn't leave bytes in RX to be misread as the next
  command's pre-header.
- **Never call `bytes.decode()` on anything the Z80 sent.** A TS-2068
  filename can legitimately contain bytes >= 0x80 (graphics characters,
  BASIC tokens), and `decode()` raises on those. `SAVE_TS` and `LOAD_TS`
  run *unguarded* inside the dispatcher's main loop — there's no
  try/except around the call in `tspico.py` — so an exception doesn't
  produce an error report, it takes the whole loop down. Build the string
  byte-by-byte instead; `SAVE_NAME()` in `TS/tspico_io.py` is the pattern.
- **The two filename allowlists disagree, deliberately for now.**
  `SAVE_TS` accepts only alphanumerics, `_` and `-`. The
  `SAVE "tpi:<name>"` create path in `TS/tspico.py` is far more
  permissive — any printable character except the eight FAT-reserved
  ones — so spaces, dots and parens produce a file that way but a
  Report F via a plain `SAVE`. Worth reconciling; until then, don't
  "fix" one side in isolation and assume the other matches.
- **Never answer an error with `0x01`.** Two SAVE paths used to write
  "OK" and bail out — the header-CRC failure and the no-data timeout —
  on the theory that the Z80 would notice the problem itself. It won't:
  it validated the bytes *it* sent and is satisfied, so a CRC mismatch is
  something only the Pico can see. Answering OK makes the Z80 stream the
  entire data block at a handler that has already returned. Nothing
  drains it, so the dispatcher's next pre-header read consumes data bytes
  and dispatches on garbage, and the trailing `0x01` is read as the final
  status — "0 OK" on screen for a save that never wrote a file. Refuse at
  the post-header status read via `REFUSE_SAVE()` instead.
- **Never call `_thread.start_new_thread()` unguarded.** If core1 is
  still finishing a previous watchdog's cleanup — which ends with a ~1
  second `BLINK()` — the call raises `OSError` "core1 in use". Nothing up
  the stack catches it: it leaves `TS2068_IO` and reaches `main.py`,
  which has no try/except either, so the Pico drops to a REPL and the
  user sees "locked up, LED stopped blinking". Use `START_WATCHDOG()`,
  which logs and runs the transaction unguarded rather than taking the
  dispatcher down. Don't "fix" a failed spawn by retrying with a sleep —
  a few ms of sleep with the Z80 streaming into a 4-deep RX FIFO trades a
  rare hang for routine corruption.
- **After the watchdog fires, wait for core1 before touching the SM.**
  Its cleanup does `MQ.active(0)` → `BLINK()` → `MQ.active(1)`, and BLINK
  blocks for ~1 second. A handler that returns as soon as it sees `kill`
  lets core0 race into the dispatcher's `ACTIVATE_MQ()` and status
  pre-load while core1 is still bouncing the same hardware state machine.
  Call `ABORT_TX()`, which sets `dead` and waits. And don't stage status
  bytes before it — the watchdog is pumping `pull(noblock)` through TX the
  whole time it waits, so they are discarded.
- **Don't announce READY and then go do SD work.** `ACTIVATE_SD()` grabs
  GPIO 2-4 for SPI, and GPIO 2 is D0. Any `$0E` or `$0F` cycle that lands
  after the grab reads corrupted data — this is the pin-grab race #40
  fixed inside `SAVE_TS`, and the post-SAVE dispatcher block reintroduced
  it by arming TX + `MQ_READY()` and *then* calling `MOUNT_FILE` and
  `DIR_FILES`. The 2068 prints `0 OK` and returns to the prompt while the
  Pico is still working, so the window is reachable in normal use. Arm
  exactly once, after the last SD access; leave Y at BUSY until then.
- **Guard every allocation sized by a Z80-supplied field.** `BLEN` is
  16 bits and `SAVE "x" CODE 0,65535` is legal, so there is no sane bound
  to clamp to — only an allocation that may fail. An unguarded
  `MemoryError` reaches `main.py` and drops the Pico to a REPL, and if the
  allocation sits before the mid-phase status write the 2068 *also* hangs
  to its ~19.9s `WF_NPH` timeout. Collect, retry once, then refuse.
- **A failed SD write cannot be reported, by design.** The final status
  must go out before `ENA_SD()` (see the pin-grab race above), so by the
  time `open()` fails the 2068 has already printed `0 OK`. That is an
  accepted consequence of the ordering — but still wrap the write, or an
  `OSError` from a pulled card takes the dispatcher down on top of losing
  the file.
- **`END_MSG()` has no callers and should keep it that way.** It is
  retained as documented context for the trap above, not as an API.

- **ZX48 mode is a different protocol. Do not apply this section to it.**
  See §7b below — the one time someone reasoned about ZX mode using TPI
  rules, they shipped a hang.

---

## 7b. ZX48 mode is NOT TPI

`SAVE "tpi:zx48"` puts the 2068 into ZX Spectrum mode, where `OUT 244,3`
selects a customized Spectrum ROM — a stock 48K image whose `SA-BYTES`
($04C2) and `LD-BYTES` ($0556) are replaced with TS-Pico stubs. Everything
below is transcribed from that ROM, not from the TPI spec.

Three properties make it incompatible with the rest of this document:

- **Port `$0F` is never read.** The ROM contains zero `IN A,($0F)`. The Y
  register, `MQ_READY()`, the whole dual-port ready mechanism — none of it
  participates. The PIO's issue-#14 auto-busy is harmless here.
- **There is no status byte.** `$053F`, the shared exit for both tape
  routines, restores the border and `RST 8`s on BREAK; that is the only
  error report in the entire path. A Pico-side failure **cannot** be
  communicated to the Z80. `REFUSE_SAVE()` has no counterpart — a guard can
  only log, or swallow bytes to keep the FIFO in sync.
- **Parity seeds from the flag byte**, not from byte 0 as TPI's CRC does.

### SAVE — `SA-BYTES` $04C2, per block. No handshake.

```
OUT $0E,'S'      ; then ~940us  (LD B,$FF / DJNZ)
OUT $0E,len_lo   ; then ~940us
OUT $0E,len_hi   ; then ~940us
OUT $0E,flag     ; 0x00 header / 0xFF data, then ~940us
DE x  OUT $0E,b  ; ~60us apart  (LD B,$10 / DJNZ)
OUT $0E,parity   ; XOR of flag and every data byte
```

Blind timed writes — the Pico just has to keep up. `DE` is decremented
*after* the send, so `DE=0` wraps to `$FFFF` and floods 65536 bytes: the
same quirk [#40](https://github.com/timex-sinclair-projects/tspico-firmware-build/pull/40)
fixed for TS mode. With no status byte to refuse with, the only option is
to swallow the flood and write nothing.

Note `SA-BYTES` sends a fresh `'S'` for **every** block. `ZX48_IO` consumes
the header block's; the data block's is consumed inside `SAVE_ZX`.

### LOAD — `LD-BYTES` $0556, per block. One handshake.

```
OUT $0E,'L'
poll IN $0E until the byte reads 0x40      <-- the handshake
~940us, then IN $0E -> flag  (seeds the parity accumulator)
DE x  IN $0E -> data byte                  (~15us apart)
IN $0E -> parity, compared against the accumulator
```

**The `0x40` is load-bearing, and it is not the single-port continue flag.**
It is polled on `$0E`, the *data* port. The dual-port compliance sweep in
`c649e69` stripped `wrt(0x40)` from `LOAD_ZX` and `LOAD_ZX_C` reasoning
that "0x40 continue flag is on port $0F (scratch Y)" — true for TPI, wrong
here. With nothing matching `0x40` the poll never exits: TX drains,
`pull(noblock)` drives `0x00` forever, and ZX LOAD hangs hard. That
regression shipped.

Because the poll **discards** every non-`0x40` byte, the handshake also
resynchronises the stream. That is why `LOAD_ZX` can afford to be one byte
generous, and why a slow Pico response is fine here even though the
equivalent would break `LOAD_TS`.

### Two `busy` flags, not one

`tspico.py` imports named symbols from `tspico_io`, and `busy` is not among
them — so its `global busy` binds a **different** module-level variable,
the one its own `SAVE_LOG` / `BLINK_LED` / `CHK_STATUS` threads set. A
`while busy:` in `tspico.py` does **not** wait for the LVM watchdog,
however much it reads like it does. Core1 is one resource, so anything
deciding whether it can spawn must consult both: its own `busy` and
`CORE1_BUSY()`.

The three `while busy:` waits in `tspico.py`'s main LVM loop are subject to
this and are deliberately unchanged — they are unbounded spins, so making
them wait on something that can actually be True would turn a no-op into a
potential hang. `START_WATCHDOG()` tolerating a failed spawn is what
protects those paths today.

---

## 8. Where to look in the source

| File                       | What's in it                            |
|----------------------------|-----------------------------------------|
| `TS/tspico_io.py`      | PIO programs (`TS_IO_DUAL`, `set_ctrl`, |
|                            | `sel_bank`, etc.); LVM handlers (LOAD_TS, |
|                            | SAVE_TS); helper utilities (LOG_ADD,    |
|                            | END_MSG, ABORT_TX).                     |
| `TS/tspico.py`         | Main I/O dispatch loop (`TS2068_IO`),   |
|                            | high-level commands (DIR, CD, etc.),    |
|                            | configuration (`PICO_STATUS`).          |
| `TS/sdcard.py`         | SD card driver (SPI).                   |
| `TS/extcmd.py`         | User-extensible command dictionary.     |
| `test/protocol_observer_*` | Bus-level test harnesses — see §6.      |
| `manifest.py`              | MicroPython freeze manifest. Adding new |
|                            | files to `TS/` requires updating    |
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
