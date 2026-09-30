# SAVE: v1.1c vs v1.5 — what actually changed

> **Historical record: a July 2026 snapshot, rescued in September 2026.** It
> was written on the v1.5 tree while SAVE did not work, and was never merged
> at the time (branch `claude/tspico-save-dual-port-cb2e81`). Its line
> numbers, "open" items and fix list describe that tree, not today's.
>
> **What changed since:**
> - SAVE was reworked in #48 (the SAVE/LOAD dual-port fixes, including
>   filename refusal) and in #51's stages (#64, #68: SAVE hears BREAK, says
>   READY at the capture, checks data parity). It works on the 2.0 firmware.
> - The branch's code fixes (§8) were not carried over; that code was
>   rewritten.
> - `docs/rom-analysis/` has since landed on main.
>
> **What it is still worth reading for:**
> - §1: which 1.1c sources are the real ones.
> - §4: the transport change from `0x40` to the Y register.
> - §10: the ROM-side findings, including the WF_NPH timing budget.

A line-by-line comparison of the TS-2068 → SD card SAVE path between the
shipping v1.1c firmware and the current v1.5 tree in this repo.

Written because SAVE works on 1.1c and does not work on 1.5, and the
working assumption going in was that "SAVE was never migrated to
dual-port." **That assumption is wrong** — see §2. This document
establishes what the two versions actually do, so the remaining
investigation starts from facts instead of from that premise.

---

## 1. Provenance — which files are really v1.1c

This has to come first, because two of the files commonly reached for as
"the 1.1c source" are not.

### 1.1c's `tspico_io.py` is not on disk in the 1.1c folder

`pico 1.1c/src_new_v1.1/TS/` contains `tspico.py` but **no
`tspico_io.py`** — yet `tspico.py` line 55 does:

```python
from tspico_io import sel_bank, set_ctrl, set_dck, TS_IO, LOAD_TS, LOAD_ZX, LOAD_ZX_C, SAVE_TS, SAVE_ZX
```

`tspico_io` is a *frozen* module, compiled into `firmware_v_1_1c.uf2`.
Its source is not next to `tspico.py`.

### The file to use instead

The real 1.1c sources are inside the beta-testing bundle:

```
pico 1.1c/TS2068-PICO-Beta-Testing.zip
  └── TS2068-PICO-Beta-Testing/docker/src/
        ├── tspico.py       (82,230 bytes)
        └── tspico_io.py    (18,588 bytes)   ← SAVE_TS lives here
```

`docker/src/tspico_io.py` defines exactly the nine symbols `tspico.py`
imports, and defines no `TS_IO_DUAL`. It is the 1.1c IO module.

### Verification that this is what shipped

Checked against `strings firmware_v_1_1c.uf2`:

| Marker | In UF2? | `docker/src/` | `src_new_v1.1/TS/` |
|---|---|---|---|
| `uPython: 1.20.0` | yes | 1.20.0 ✓ | says 1.22.0 ✗ |
| `NULL_SM` | yes | present ✓ | absent ✗ |
| `FW_VERSION` | yes | present ✓ | absent ✗ |
| `"80 - "` (SAVE_TS message) | yes | present ✓ | n/a |
| `ERROR: Bad CRC in SAVE_TS!` | yes | present ✓ | n/a |
| `INFO: Finished SAVE TS successfully` | yes | present ✓ | n/a |

So `firmware_v_1_1c.uf2` was built from `docker/src/`, and
`src_new_v1.1/TS/tspico.py` is a **different, slightly older variant**
that was never the shipped 1.1c. Every 1.1c line number in this document
refers to `docker/src/tspico_io.py` unless stated otherwise.

### The other misattributed file

`Version 1-1/TSPico/TS/tspico_io.py` (3,684 bytes, April 2024) is from
the **v1.1 module layout**, not 1.1c. In that layout the backend lived in
`NEW_backend.py` and `tspico_io.py` was a small helper holding only
`TS_IO`, `ACTIVATE_MQ`, `MQ_READY`, `SEND_MSG`, `SEND_MSG2`. It has no
`SAVE_TS`, no `LOAD_TS`, and none of the three PIO bank/control programs
that 1.1c's `tspico.py` imports. It cannot be 1.1c's `tspico_io`.

---

## 2. Executive summary

**`SAVE_TS` in v1.5 has already been fully migrated to dual-port.** It
was ported in commit `c649e69` ("Port LOAD_TS, SAVE_TS, LOAD_ZX,
LOAD_ZX_C, SAVE_ZX, END_MSG to dual-port") and has been revised since. It
contains no `wrt(0x40)`, drives the Y register for ready/busy, and
implements the same V6 final-status-plus-pre-load chain that `LOAD_TS`
uses. Structurally it matches the LOAD path.

So the difference between working 1.1c SAVE and broken 1.5 SAVE is *not*
"single-port code running under a dual-port PIO." It is a set of smaller,
specific divergences. The ones that carry real behavioral risk:

| # | Divergence | Risk |
|---|---|---|
| A | **Watchdog no longer covers the 21-byte header read** (§5.2) | A Z80 that stops mid-header hangs `MQ.get()` forever. In 1.1c the watchdog fired at 5 s and recovered. This is very likely why the known 9-of-21 stall presents as a lockup rather than a logged error. |
| B | **Filenames with spaces are now rejected** (§5.6) | `SAVE "MY PROG"` worked on 1.1c (saved as `MY PROG.tap`). On 1.5 it aborts with `Filename "MY PROG" not allowed`. A plain behavioral regression. |
| C | **The filename-reject path violates the orphan-byte rule** (§5.6) | It calls `END_MSG()` *after* the two V6 `0x01` writes — exactly what the same file's own comments and `docs/PROTOCOL.md` §7 forbid. Latent corruption of the next transaction. |
| D | **No TX-drain wait before the SD write** (§5.7) | The dispatcher's `ACTIVATE_MQ()` re-creates the state machine and wipes the TX FIFO, potentially destroying the final status byte before the Z80 reads it. **Fixed** — see §8. |
| E | **SAVE is now silent** (§5.5) | 1.1c printed `80 - N bytes saved OK`. 1.5 prints nothing, so a failed SAVE and a successful SAVE look identical to the user. |

Divergences A, B, C and E are still open. D is fixed on this branch.

`SAVE_ZX` (ZX Spectrum compatibility mode) is the routine that genuinely
**has not** been migrated — see §7.

---

## 3. Module layout

| | v1.1c | v1.5 |
|---|---|---|
| Main / dispatcher | `tspico.py` (~2,400 lines) | `src/TS/tspico.py` (~4,600 lines) |
| IO + LVM | `tspico_io.py` (728 lines) | `src/TS/tspico_io.py` (1,403 lines) |
| Other | `sdcard.py` | `sdcard.py`, `extcmd.py`, `help.py`, `tspico_upgrade.py` |
| Import style | `from tspico_io import ...` (flat, frozen) | `from TS.tspico_io import ...` (package) |
| Internal TAPs | `/TS/nofile.tap` | `/assets/nofile.tap` (moved to avoid frozen-package shadowing) |

Function names were renamed during the migration; the mapping is 1:1:

| v1.1c | v1.5 |
|---|---|
| `ENA_MQ()` | `ACTIVATE_MQ()` in `tspico.py` (`ENA_MQ` kept as the legacy single-port version) |
| `ENA_SD()` | `ACTIVATE_SD()` / `DEACTIVATE_SD()` in `tspico.py` (`ENA_SD` kept, still used by `SAVE_TS`) |
| `END_MSG()` | `END_MSG()` (0x40 prefix removed) |
| `LOG_ADD()` | `LOG_ADD()` (unchanged) |
| `WATCHDOG()` | `WATCHDOG()` (unchanged) |

---

## 4. The transport change

This is the change everything else follows from.

### 4.1 The PIO program

| | v1.1c `TS_IO` | v1.5 `TS_IO_DUAL` |
|---|---|---|
| Location | `tspico_io.py:95` | `src/TS/tspico_io.py:178` |
| Instructions | 11 | 20 of 32 |
| Clock | 15 MHz | 30 MHz |
| Ports decoded | one ($0E only) | two ($0E data, $0F status) |
| A0 (GPIO 10) | sampled into RX bit 8, otherwise ignored | decoded on reads to select port |
| Ready signalling | a `0x40` byte in the TX FIFO | the **Y scratch register**, read back on $0F |
| On Z80 OUT | `push(noblock)` | `push(noblock)` **+ `mov(y, null)`** (issue #14 auto-busy) |

### 4.2 What `0x40` was, and what replaced it

The Z80's `WF_NPH` wait loop tests **bit 6** of the byte it reads. In
single-port there was only $0E, so "ready" had to be delivered *as a data
byte* — `0x40` (bit 6 set). Every 1.1c handler therefore interleaves
`wrt(0x40)` (ready) and `wrt(0x01)` (status) in the TX FIFO in a precise
order.

In dual-port, $0F is answered by the PIO from the Y register, entirely
outside the TX FIFO:

```python
MQ.exec("mov(y, invert(null))")   # Y = 0xFFFFFFFF → $0F reads 0xFF → bit 6 set → READY
MQ.exec("set(y, 0)")              # Y = 0          → $0F reads 0x00 → bit 6 clear → BUSY
```

wrapped as `MQ_READY()` / `MQ_BUSY()` in `src/TS/tspico.py:690` and
`:719`.

**So every `wrt(0x40)` becomes an `MQ_READY()` call, and the 0x40 byte
must disappear from TX entirely.** A leftover `0x40` in the TX FIFO is
not ignored — the Z80 reads it as data at some later phase and
misinterprets it. This is the "orphan-byte" family of bugs documented in
`docs/DUAL_PORT_DEVELOPMENT.md` §8.

### 4.3 The issue-#14 wrinkle

`TS_IO_DUAL` drops `Y = 0` (BUSY) after **every** Z80 OUT, in the PIO,
single-cycle. This was added because MicroPython is structurally too slow
to win the race between the Z80's write and its immediately following
bit-6 poll.

The consequence for receive-heavy code like SAVE: after draining a
21-byte header, Y has been dropped 21 times and is BUSY. **Python must
explicitly call `MQ_READY()` before the Z80's next poll will succeed.**
There is no such requirement in 1.1c. Every `MQ_READY()` in v1.5's SAVE
path exists because of this.

---

## 5. `SAVE_TS` side by side

v1.1c: `docker/src/tspico_io.py:482-594` (113 lines)
v1.5: `src/TS/tspico_io.py:991-1208` (218 lines, ~60 of them comments)

Both are called by the dispatcher as `SAVE_TS(MQ, TSP)` with the 10-byte
pre-header already drained, and both return `(MQ, TSP, log_entries)`.

### 5.1 Overall phase structure — unchanged

Both implement the same three-phase protocol:

1. Receive 21-byte header block, verify CRC
2. Emit mid-status, receive `BLEN+4`-byte data block
3. Emit final status, reconstruct a standard TAP, write to SD

### 5.2 Phase 1 — header read (**divergence A**)

**v1.1c:**
```python
hdr = bytearray(21)
_thread.start_new_thread(WATCHDOG, (5, MQ, TSP))   # ← watchdog FIRST
wrt(0x40)                                          # ← single-port ready
for i in r1:
    hdr[i] = MQ.get()
```

**v1.5:**
```python
hdr = bytearray(21)
for i in range(21):
    hdr[i] = MQ.get() & 0xFF                       # ← no watchdog running
# ... CRC check ...
wrt(0x01)
MQ.exec("mov(y, invert(null))")
_thread.start_new_thread(WATCHDOG, (5, MQ, TSP))   # ← watchdog only NOW
```

Three changes:

- The `wrt(0x40)` is gone. Correct — the status byte for this command was
  pre-loaded into TX by the previous command's tail (the V6 chain), and Y
  is set READY by the dispatcher's `MQ_READY()` right after it drains the
  pre-header (`src/TS/tspico.py:4438`).
- `& 0xFF` added. `in_(pins, 9)` pushes 9 bits with A0 in bit 8, so RX
  values can exceed 255. 1.1c got away without the mask because the Z80
  only ever OUTs to $0E (A0 = 0). Defensive, correct.
- **The watchdog no longer covers the header read.** This is a real
  regression. In 1.1c the watchdog was armed *before* the first
  `MQ.get()`, so a Z80 that stopped part-way through the header hit the
  5-second timeout, and the watchdog's `MQ.exec("push (noblock)")` loop
  forced bytes into RX to unblock the stuck `MQ.get()`, logged
  `Abnormal termination`, cleared the FIFOs and recovered. In 1.5 the
  same stall blocks forever with nothing watching.

This last point matters for the open investigation. The known symptom
(recorded in the SAVE stall notes: the Z80 reliably sends **exactly 9 of
21** header bytes and then stops) would, on 1.1c, have produced a logged
error and a recovered interface. On 1.5 it produces a silent hang. **The
watchdog placement doesn't cause the stall, but it explains why the stall
is unrecoverable** — and re-arming it earlier would convert an
undiagnosable lockup into a logged, recoverable event with FIFO state
captured at the moment of failure.

### 5.3 CRC verification — semantically identical

**v1.1c** uses a loop-variable-leak idiom that is easy to misread:

```python
for i in r1:                    # i = 0..20
    if (i == 1) or (i == 2):
        continue                # skip the 2 session-ID bytes
    ant = crc_h                 # ant = crc BEFORE this XOR
    crc_h = crc_h ^ hdr[i]

if (hdr[i] != ant):             # i is 20 here; ant = XOR of [0]+[3..19]
```

After the loop `i == 20`, so `hdr[i]` is the received CRC and `ant` holds
the accumulator from *before* the final XOR — i.e. the expected CRC.

**v1.5** writes the same thing legibly:

```python
crc_calc = hdr[0]
for i in range(3, 20):
    crc_calc ^= hdr[i]
if crc_calc != hdr[20]:
```

Both compute `XOR of hdr[0] + hdr[3..19]`, skipping the two session-ID
bytes at `[1]` and `[2]`. **No behavioral change.** The session bytes are
a TPI extension not present in standard ZX TAP CRC — worth knowing, since
it is the single most non-obvious line in the routine.

On CRC failure, 1.1c returns immediately with no status bytes; 1.5 emits
`0x01, 0x01` plus `MQ_READY()` so the Z80 isn't left polling. 1.5 is
better here.

Block length is computed identically: `long = hdr[14] + 256*hdr[15] + 4`.

### 5.4 Phase 2 — mid-status and data read

**v1.1c:**
```python
wrt(0x40)
wrt(0x01)
for i in r2:
    blk[i] = MQ.get()
    if kill: ... return
```

**v1.5:**
```python
wrt(0x01)
MQ.exec("mov(y, invert(null))")
_thread.start_new_thread(WATCHDOG, (5, MQ, TSP))

t_init = time.ticks_us()                      # ← new: 1s no-data abort
while MQ.rx_fifo() == 0:
    if time.ticks_diff(time.ticks_us(), t_init) >= 1_000_000:
        wrt(0x01); wrt(0x01)
        MQ.exec("mov(y, invert(null))")
        dead = True
        while busy: pass
        return MQ, TSP, log_entries

for i in range(long):
    blk[i] = MQ.get() & 0xFF
    if kill: ... return
```

`0x40` → `MQ_READY()` is the correct translation. The 1-second
no-data abort is new (catches BREAK during SAVE). The `kill` check inside
the loop is preserved in both.

### 5.5 Phase 3 — final status (**divergence E**)

**v1.1c:**
```python
totbytes = long + len(hdr)
msg = "80 - " + str(totbytes) + " bytes saved OK"
END_MSG(MQ, TSP.VERBOSE, msg, [], 1)
dead = True
```

1.1c's `END_MSG` emits `0x40, 0x81, st, 0x0D, msg..., 0x00` when verbose,
or `0x40, st` when not — and blocks until TX drains.

**v1.5:**
```python
wrt(0x01)        # final status — Z80 reads this and reports "0 OK"
wrt(0x01)        # pre-load for the NEXT command's initial status
MQ.exec("mov(y, invert(null))")
dead = True
```

This is the V6 chain, matching `LOAD_TS:779-787`. It is the correct
dual-port pattern, and `END_MSG` is deliberately *not* called (see the
warning at `END_MSG`'s docstring, `src/TS/tspico_io.py:456`).

The tradeoff: **1.1c told the user their SAVE succeeded; 1.5 says
nothing.** A successful SAVE and a silently-failed one are now
indistinguishable on screen. The `END_MSG` docstring notes that
delivering a verbose message would need a different layout — writing
`0x81 + msg` *before* the pre-load `0x01` so the verbose directive is the
final response rather than an extra byte.

### 5.6 Filename handling (**divergences B and C**)

**v1.1c:**
```python
filename = hdr[4:14].decode()
clean_fname = filename.strip()
clean_fname = ''.join(l for l in clean_fname
                      if (l.isalpha() or l.isdigit() or l.isspace()))
if not clean_fname:
    clean_fname = "noname"
filename = TSP.cur_path + "/" + clean_fname + ".tap"
mode = "wb"
```

**v1.5:**
```python
filename = hdr[4:14].decode().strip()
clean_fname = "".join(c for c in filename
                      if c.isalpha() or c.isdigit() or c in "_-")
if clean_fname != filename:
    msg = 'ERROR: Filename "%s" not allowed' % filename
    END_MSG(MQ, True, msg, [], 3)
    return MQ, TSP, log_entries
if not clean_fname:
    clean_fname = "noname"
filename = TSP.cur_path + "/" + clean_fname + ".tap"
mode = "wb"
TSP.f_name = filename                          # ← new
```

Three changes, two of them problems:

- **Allowed character set changed.** 1.1c allowed `isspace()`; 1.5 does
  not, but adds `_` and `-`. So `SAVE "MY PROG"` produced `MY PROG.tap`
  on 1.1c and is **rejected** on 1.5. Given that spaces in TS-2068
  program names are entirely ordinary, this is a regression that will bite
  real users.
- **Silent-clean became hard-reject.** 1.1c dropped disallowed characters
  and carried on; 1.5 aborts the whole SAVE. The data has already been
  received at this point and is sitting in RAM — it gets discarded.
- **The reject path calls `END_MSG()` after the V6 chain.** By the time
  this runs, lines 1136-1138 have already written `0x01`, `0x01` and set
  Y READY. `END_MSG` then appends `0x81, 0x03, 0x0D, msg..., 0x00` behind
  the pre-load byte. That is precisely the orphan-byte violation the same
  file warns against at `:456`, `:805` and `:1186`. Even when the reject
  is *intended*, it corrupts the following transaction.

`TSP.f_name = filename` is new and load-bearing — the dispatcher's
post-SAVE mount logic (`src/TS/tspico.py:4507-4517`) reads it to decide
whether to mount the newly saved file.

### 5.7 TAP reconstruction and SD write (**divergence D**)

The block-header rewrite is **identical** in both — overwrite the two
session-ID bytes with a standard TAP length prefix:

```python
l_hdr = len(hdr) - 2
hdr[2] = hdr[0]               # preserve block_type
hdr[0] = l_hdr & 0xFF         # len_lo where session_lo was
hdr[1] = (l_hdr >> 8) & 0xFF  # len_hi where session_hi was
```
(1.1c does the same arithmetic with `int(x/256)` instead of shifts.)

Both then write `hdr` + `blk` and leave `/sd` mounted for the dispatcher
to clean up; 1.1c has the `os.umount("/sd")` and `ENA_MQ(MQ)` calls
commented out at the tail, and 1.5 simply omits them.

The divergence is in what happens next. In 1.1c, `END_MSG` **blocked
until TX drained** before the SD write began, so the status byte was
provably consumed by the Z80 before anything could disturb the FIFO. 1.5's
two `0x01` writes don't wait, and the state machine gets re-created
downstream — which resets SM0's hardware FIFOs and can wipe an unread
status byte. The SD write usually took long enough to hide this, but it
was a genuine race.

**Both halves of this are now fixed** (§8): `SAVE_TS` waits up to 50 ms
for TX to drain, and it calls `ACTIVATE_SD()` rather than the legacy
`ENA_SD()`. The difference matters — `ENA_SD()` grabs `Pin()`/`SPI()`
directly with no PIO-release step, so SPI took the shared GPIO 2-4 pins
out from under a still-running `TS_IO_DUAL`. `ACTIVATE_SD()` bounces a
`NULL_SM` state machine first to stop the SM cleanly. It's imported
lazily inside the function because `tspico.py` imports `SAVE_TS` from
`tspico_io.py` at module level, so a top-level import would be circular.

---

## 6. The dispatcher's SAVE branch

**v1.1c** (`docker/src/tspico.py:2260`):
```python
if pre[0] == 0 and pre[1] == 0:
    LOG("INFO: Starting SAVE TS", 0)
    led.value(1)
    while busy: pass
    MQ, TSP, new_logs = SAVE_TS(MQ, TSP)
    log_entries += new_logs
    gc.collect()
    DIR_FILES()
    try:
        # os.umount("/sd")
        ACTIVATE_MQ()
    except:
        pass
    led.value(0)
```

**v1.5** (`src/TS/tspico.py:4450`) adds, in order: state snapshot
(`pf_name`/`pappend`/`pidx`), the `SAVE_TS` call, a `save_aborted` probe,
`DEACTIVATE_SD()`, `ACTIVATE_MQ()`, **`MQ.put(0x01)` + `MQ_READY()`**,
then post-save mount/re-mount logic driven by `TSP.f_name` and
`TSP.append`.

Two things worth calling out:

- The explicit `MQ.put(0x01); MQ_READY()` is **required**, not
  redundant. `ACTIVATE_MQ()` re-creates the state machine and leaves
  Y = BUSY with an empty TX FIFO, destroying `SAVE_TS`'s pre-load. This
  restores the V6 chain for the next command.
- The pre-header read at `:4422-4423` is followed immediately by
  `MQ_READY()` at `:4438` — the issue-#14 compensation. Without it the
  Z80 polls $0F for ~700 ms and gives up with Report J before SAVE_TS is
  ever reached. There is no equivalent in 1.1c because single-port had no
  Y register.

The append/re-mount handling is entirely new in 1.5 and has no 1.1c
counterpart.

---

## 7. What genuinely has *not* been migrated

`SAVE_ZX` (`src/TS/tspico_io.py:1211`) is still single-port, and says so
in its own docstring:

> `!!! NOT DUAL-PORT COMPLIANT — see LOAD_ZX docstring for details. !!!`

It calls the legacy `ENA_MQ()` (which spins up the old `TS_IO` state
machine at 15 MHz) and `os.umount("/sd")` directly. `LOAD_ZX` and
`LOAD_ZX_C` are in the same state. These only affect ZX Spectrum
compatibility mode (`SAVE "tpi:zx48"`), not normal TS-2068 SAVE.

If the goal is "make ZX48 mode work under dual-port," `SAVE_TS` is the
template. If the goal is "make normal SAVE work," `SAVE_ZX` is not
involved.

---

## 8. Fixes salvaged from the dead-end branch

Branch `claude/save-crc-sd-card-e10749` was abandoned — it did not make
SAVE work. But it produced **six** genuine production fixes, each
independently correct, which are cherry-picked onto this branch
(`fa12f09`..`151e1de`). The branch's nine `test:` commits — the
`protocol_observer_save_sd_race.py` bus harness and its experimental
trail — were deliberately **not** carried over. What that harness taught
us is recorded in §10; the harness itself was a dead end and is not worth
maintaining.

1. **`sdcard.py` `cmd()`** (`fa12f09`) — no longer raises immediately on
   a CRC-error response bit, letting `init_card()`'s CMD0 retry loop
   actually retry past a transient bus glitch. This matches how every
   other `cmd()` call site already handles a non-matching response.
   Covered by `src/test/test_sdcard_crc_retry.py`, which came with it.
2. **`ENA_SD()` takes `TSP`** (`18b68ce`) — it referenced an undefined
   global `TSP` inside its own except block, so the handler would have
   raised `NameError` instead of logging. The block had simply never
   fired. **This bug is inherited from 1.1c** — identical code at
   `docker/src/tspico_io.py:168`.
3. **Don't `open()` the TAP if SD is unavailable** (`f4c9ef0`) — `ENA_SD`
   reported failure and the caller opened the file anyway.
4. **`SAVE_TS()` uses `ACTIVATE_SD()`** (`a61ea5d`) — see §5.7 for why
   the legacy `ENA_SD()` was unsafe.
5. **50 ms TX-drain wait before the SM bounce** (`a648b40`) — divergence
   D above.
6. **`MQ.put(0x01); MQ_READY()` fires once, after housekeeping**
   (`151e1de`) — previously it signalled ready *before* the post-save
   re-mount and directory refresh, so the Z80 started its next command
   while more `ACTIVATE_SD()` state-machine resets were still coming.
   Confirmed on a TLM trace showing `tx=1 rx=4` — a full, unread RX FIFO
   — right as `MOUNT_FILE`'s `ACTIVATE_SD()` was about to reset SM0.

Note the count: prior notes recorded **five** fixes and missed #3.

**SAVE still does not work end-to-end with all six applied.** They remove
real failure modes downstream of the problem; the blocker is the 9-of-21
header stall in §10, which none of them touch.

---

## 9. Where this leaves the investigation

Established:

- SAVE_TS is properly dual-port. The migration premise was wrong.
- The CRC formula, block-length math, and TAP reconstruction are
  byte-identical to the working 1.1c code. These are not the problem.
- The transport translation (`0x40` → Y register) is correctly applied
  throughout SAVE_TS.

Concrete, actionable divergences, in the order worth addressing:

1. **Re-arm the watchdog before the header read** (§5.2). Doesn't fix
   the stall, but converts it from a silent hang into a logged,
   recoverable event — and the watchdog's FIFO-state logging at the
   moment of failure is exactly the evidence the 9-of-21 investigation
   lacks.
2. **Restore space in the allowed filename set, and drop the hard
   reject** (§5.6) — or at minimum move the `END_MSG` reject path above
   the V6 chain so it stops orphaning bytes.
3. **Consider restoring a success message** (§5.5) using the layout the
   `END_MSG` docstring describes, so SAVE failures are visible on screen.

The six fixes from the abandoned branch are already applied here (§8).

None of these explains the 9-of-21 stall itself. That is documented in
full in §10.

---

## 10. Open: the 9-of-21 header stall

This section records the state of the SAVE investigation so it isn't
re-derived from scratch. **It is prior-session work, carried forward from
notes — the disassembly claims below were verified then, not in the
session that wrote this document.** Treat them as well-sourced but
re-check before betting a day on them.

### The symptom

With a valid pre-header (CRC-correct, captured cleanly every time) and
`Y = READY` explicitly restored after it, the Z80 reliably sends
**exactly 9 of the expected 21 header-block bytes, then stops.**

- Reproducible across multiple runs.
- Immune to continuously re-asserting `Y = READY` for 8+ seconds
  (304 reassertions, zero effect). **Not a ready-signalling problem.**
- Total silence on RX afterward — not a trickle. **Rules out simple FIFO
  overflow on the Pico side**, which would show as dropped-but-continuing
  traffic.

### Z80 disassembly ground truth

Traced against `gus-exrom.asm`. `l1879h` = `W_TAPE`:

- **The 10-byte pre-header is built and sent by `l1879h` itself**, not by
  a separate outer SLVM-level routine. Verified byte-for-byte, including
  a hand-computed XOR CRC matching a real capture.
- **There is exactly one `WF_NPH` (wait-for-bit-6) call between the
  pre-header's status read and the header-block send**, at `$18D2`. Y /
  bit 6 is the sole gate there. No retry on timeout — a hardcoded
  `RST 8` error.
- **The header-content send loop (`l18f3h`) has no conditional exit, no
  port reads, and no delay.** It sends 17 bytes from `(IX)` in a tight
  loop. `sub_229dh` (the `OUT ($0E),A` helper) is exactly
  `OUT ($0E),A; AND A; RET` — and `AND A` always clears carry on a real
  Z80, so the `jr c,...` checks after each call can never fire.

That last point is what makes this a genuine open question rather than
something more disassembly reading will resolve: **per the static code,
once that loop starts it should run straight through uninterrupted.** The
code that is stopping has no visible mechanism to stop.

### Leading hypotheses

1. A hardware/timing effect static disassembly can't show — e.g. TS-2068
   memory contention on whatever `IX` points into for the header buffer.
2. Something about the Z80-side transition *into* that loop. The header-
   content **building** routines `sub_0426h`, `l1230h` and `l073fh` were
   explicitly never traced.

### Dead ends — do not re-chase

- **Ready/Y signalling.** 304 continuous reassertions over 8s changed
  nothing (above).
- **Timing budget.** Settled by disassembly — see below. Do not re-open.

### The WF_NPH timing budget — settled, don't re-derive

This number has been rediscovered wrong at least three times, because the
figure and the *reason* for it come apart. Ground truth is
`docs/rom-analysis/PROTOCOL_FROM_ROM.md`, which computes it from the
instruction stream (`python3 tools/wf_nph_timing.py` recomputes it):

| | T-states | @3.528 MHz |
|---|---|---|
| `07F6` one debounced keyboard read | 30,980 | 8.78 ms |
| `0856` (10× `07F6`) | 310,133 | 87.91 ms |
| **one WF_NPH poll iteration** | 310,284 | **87.95 ms** |
| **full timeout (B=226)** | 70,124,184 | **19.88 s** |

The counter really is `LD B,0E2h` = 226 — `0x1A56` in the shipped binary
is `06 e2`. It was never "extended." The ~20 s comes from each poll
costing ~88 ms, because reading the status port routes through a
debounced keyboard scan (`1A54 WF_NPH → 0655 READ_STATUS → 069F
CHECK_BREAK → 0856 → 10× 07F6`).

So both of these are true at once, which is the trap:

- **~20 s is right.** Anyone who reads `B=0xE2` and concludes
  "milliseconds" is wrong.
- **The counter is not larger than the disassembly shows.**
  `GUSTAVO_PROTOCOL.md:285-288`'s explanation ("this counter is larger")
  is wrong even though its number is right.
- **`DEVELOPER_GUIDE.md:320-322`'s "~700 ms (256 retries)" matches
  neither** — it's 256 × the spec's bogus 2.8 ms.

The operational consequences matter more than the headline:

- The Z80 samples port `0x0F` only **~11 times per second**.
- The **first** poll lands ~88 ms *after* `WF_NPH` is entered, so **every
  `WF_NPH` call costs ≥88 ms even when the Pico was ready immediately.**
  This is the long-noted "88 ms gap" (`DUAL_PORT_DEVELOPMENT.md` §205) —
  it is structural, not something Pico can optimize away.
- BREAK is sampled at that same ~11 Hz.

`docs/rom-analysis/` lands via branch `claude/ts-pico-rom-disassembly-81306c`
and carries ten further doc-vs-ROM discrepancies worth reading before
trusting any protocol doc.

### Tooling — deliberately not kept

The `protocol_observer_save_sd_race.py` bus harness that produced the
9-of-21 finding was **not** carried over from the dead-end branch. It did
its job; the finding is above. If you need to observe this on the wire
again, start from `src/test/_harness_template.py` per `src/CLAUDE.md`
rather than resurrecting it.

Two lessons from it that *do* carry forward:

- **Put a `HARNESS_VERSION` stamp in every harness banner and confirm it
  in the printed output before trusting a result.** Multiple test cycles
  were wasted on stale Thonny buffers — file edited and pushed, but
  Thonny re-ran its old in-memory copy.
- **Two-phase capture is not optional** (`src/CLAUDE.md`). The harness's
  early revisions violated it and produced misleading traces.

The Z80 reference library (`gus-exrom.asm` etc.) lives at
`~/Documents/Projects/TS2068 Ref Library/`, **outside this repo** —
access has to be granted per session. `docs/rom-analysis/disasm/` carries
in-repo disassemblies of the same ROMs.

---

## Appendix: file reference

| What | Where |
|---|---|
| v1.1c `tspico_io.py` (SAVE_TS at :482) | `TS2068-PICO-Beta-Testing.zip` → `docker/src/tspico_io.py` |
| v1.1c `tspico.py` (SAVE branch at :2260) | `TS2068-PICO-Beta-Testing.zip` → `docker/src/tspico.py` |
| v1.1c shipped firmware | `pico 1.1c/firmware_v_1_1c.uf2` |
| v1.5 `SAVE_TS` | [src/TS/tspico_io.py:991](../src/TS/tspico_io.py) |
| v1.5 `LOAD_TS` (migration template) | [src/TS/tspico_io.py:548](../src/TS/tspico_io.py) |
| v1.5 `TS_IO_DUAL` | [src/TS/tspico_io.py:178](../src/TS/tspico_io.py) |
| v1.5 `MQ_READY` / `MQ_BUSY` | [src/TS/tspico.py:690](../src/TS/tspico.py) |
| v1.5 dispatcher SAVE branch | [src/TS/tspico.py:4450](../src/TS/tspico.py) |
| Protocol design | [docs/GUSTAVO_PROTOCOL.md](GUSTAVO_PROTOCOL.md) |
| Firmware implementation + pitfalls | [docs/PROTOCOL.md](PROTOCOL.md) |
| Migration history | [docs/DUAL_PORT_DEVELOPMENT.md](DUAL_PORT_DEVELOPMENT.md) |
| WF_NPH timing ground truth | `docs/rom-analysis/PROTOCOL_FROM_ROM.md` (via `claude/ts-pico-rom-disassembly-81306c`) |
| Doc-vs-ROM discrepancy list | `docs/rom-analysis/PROTOCOL_FROM_ROM.md` §"Doc-vs-ROM discrepancies" |
| New bus harness starting point | `src/test/_harness_template.py` |
| Z80 disassembly (`gus-exrom.asm`) | `~/Documents/Projects/TS2068 Ref Library/` — outside the repo |
