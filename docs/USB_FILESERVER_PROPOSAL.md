# USB File Server — Feasibility Study & Implementation Plan

**Status: PROPOSAL — not started, no code written.** Tracker:
[#44](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/44). Written to answer
"how hard would this be?" and to give the team something concrete to
argue with.

The idea: run an application on the user's desktop/laptop that exposes
a folder of TAP/DCK/ROM files to the TS-2068 over the TS-Pico's
existing USB connection, so the TS-Pico behaves exactly as it does with
an SD card — but the files live on the host, where the user is already
editing them.

Origin: Ryan's long-standing ask (develop on a Raspberry Pi 400, run on
the 2068 without a card shuffle), plus the observation that if we can
already *debug* and *update* the TS-Pico over USB, the same link can
carry file traffic.

---

## 1. The verdict up front

**The core file server is a moderate amount of work, and — importantly
— it does not touch the TPI wire protocol at all.**

Three findings from reading the firmware drive that conclusion:

### 1a. The LVM path already reads from Pico flash, not from the SD card

`MOUNT_FILE()` copies the selected file from `/sd/...` to
**`/TMP/temp.tap`** on the Pico's internal flash
([tspico.py:1263](../src/TS/tspico.py:1263)), and `LOAD_TS()` /
`LOAD_ZX()` open `/TMP/temp.tap`
([tspico_io.py:668](../src/TS/tspico_io.py:668),
[864](../src/TS/tspico_io.py:864),
[936](../src/TS/tspico_io.py:936)). The SD card is *never* touched
during a LOAD.

So for the entire read path, a USB backend has to implement exactly one
thing: **"get the bytes of host file X into `/TMP/temp.tap`."**
Everything downstream — `OFF_TABLE`, `LOAD_TS`, `FFW`, `REW`,
`TAPDIR`, headerless LOAD, the `.DCK`/`.ROM` flash-image path via
`/TMP/temp.bin` — works unchanged. No new orphan-byte risk, no new CRC
math, no new FIFO ordering.

That is a very large de-risking. The wire protocol is the part of this
codebase that has historically eaten weeks (see
[`DUAL_PORT_DEVELOPMENT.md`](DUAL_PORT_DEVELOPMENT.md) §8 and the
orphan-byte family in [`../src/CLAUDE.md`](../src/CLAUDE.md)). None of
that is in play here.

### 1b. USB mode *removes* the hardest hazard in the firmware

GPIO 2, 3 and 4 are **shared** between the Z80 data bus (PIO
`out_base=Pin(2)`) and the SD card's SPI bus (`sck=Pin2, mosi=Pin3,
miso=Pin4` — [tspico.py:766-771](../src/TS/tspico.py:766)). That is
why every SD access is bracketed by `DEACTIVATE_SD()` /
`ACTIVATE_MQ()` and why the code is littered with hard-won comments
about tri-state windows, pin-grab races and pre-load ordering.

That bus handover is the root cause of:

- the original Report D failure (`DUAL_PORT_DEVELOPMENT.md` §1),
- the `ACTIVATE_MQ` pre-load bug (§8 "Bug 1"),
- the SAVE post-write pin-grab race fixed in
  [#40](https://github.com/timex-sinclair-projects/tspico-firmware-build/pull/40)
  (the `while MQ.tx_fifo() > 1` wait before `ENA_SD()` in
  [tspico_io.py:1245](../src/TS/tspico_io.py:1245)).

**USB is on completely separate hardware.** The RP2040's USB PHY shares
nothing with GPIO 2-4. In USB mode `ACTIVATE_SD()` / `DEACTIVATE_SD()`
become no-ops, the PIO state machine is never torn down and rebuilt
mid-command, and this entire class of bug is structurally impossible.

This is worth saying out loud to the team: the USB file server is not
just a convenience feature, it is plausibly **the more reliable
storage path**.

### 1c. There is already host-side USB tooling to build on

[`web-updater/`](../web-updater/) is a working WebSerial client with a
vendored ViperIDE transport that already talks to the Pico's USB CDC.
It uses the *raw REPL* (which requires stopping the firmware), so it
can't be reused as-is for a live link — but the transport layer, the
packaging model, and the "here's how we ship a host-side tool" question
are all already solved.

### What's actually hard

1. **The USB byte channel itself.** MicroPython v1.20.0 on rp2 has
   exactly one USB CDC interface and it *is* the REPL — stdin/stdout.
   There's no second data endpoint. See §4.
2. **Making the ~10 SD-touching commands backend-agnostic** without
   destabilising them. Mechanical, but it's ~8 `ACTIVATE_SD()`
   callsites plus `ENA_SD()` in `SAVE_TS`.
3. **Booting with no SD card at all.** Today, a failed SD mount drops
   into an infinite `BLINK_ERROR()` loop
   ([tspico.py:776-783](../src/TS/tspico.py:776)), and so does a failed
   `os.chdir(TSP.cur_path)` ([tspico.py:4295](../src/TS/tspico.py:4295)).
   A Pi 400 user with no card must still boot. Split out into
   [`SD_ROBUSTNESS_PROPOSAL.md`](SD_ROBUSTNESS_PROPOSAL.md) — it is
   worth doing on its own merits, and Tier 1 depends on it.
4. **RAM.** The firmware logs `gc.mem_free()` at eleven points during
   boot because it is genuinely tight. A new frozen module plus
   transfer buffers is a real cost that has to be measured, not
   assumed.

Everything else — archive.org, the previewer, zmakebas integration —
is host-side application work. It's the *bigger* half by volume but
it's the *safe* half: a bug there produces a bad file, not a corrupt
protocol exchange.

---

## 2. Feature set

Organised by tier so we can ship something useful early.

### Tier 1 — Parity with the SD card (the actual product)

Everything the SD card does today, over USB, with a host folder as the
root:

| Capability | Current command | Notes for USB mode |
|---|---|---|
| Mode switch | **new** `SAVE "tpi:usb"` / `SAVE "tpi:sd"` | plus `tpi:drive` to report which is live |
| Directory listing | `tpi:dir`, `tpi:idir` | `IDIR`'s `ListMenu` works unchanged |
| Change directory | `tpi:cd` (interactive + named) | host enforces the sandbox root |
| Show path | `tpi:path` | display host path, not `/sd/...` |
| Mount by name | `LOAD "tpi:<name>"` | host streams file → `/TMP/temp.tap` |
| Mount by index | `LOAD "tpi:*nn"` | index comes from host listing |
| Unmount | `tpi:close` | unchanged |
| TAP block list | `tpi:tapdir` | operates on `/TMP/temp.tap` — unchanged |
| Seek | `tpi:ffw`, `tpi:rew` | unchanged |
| SAVE | `SAVE "name"` | Pico buffers, then pushes to host |
| Append | `tpi:append` | needs a host-side append opcode |
| New TAP | `tpi:newtap` | host creates the file |
| Make dir | `tpi:md` | host creates the folder |
| Delete | `tpi:rm` | host deletes — **confirm-in-host by default** |
| Help text | `tpi:help <topic>` | served from the host, no SD needed |
| DCK / ROM images | `LOAD "tpi:x.dck"` | host streams → `/TMP/temp.bin`, rest unchanged |
| Status | `tpi:info` | add active backend + host app version |
| Liveness probe | **new** `tpi:reconnect` | "is a fileserver actually there?" — see §4.4 |
| Copy host → SD | **new** `tpi:copy` | see §4.5 |
| Boot with no SD | — | must not brick-loop — see [`SD_ROBUSTNESS_PROPOSAL.md`](SD_ROBUSTNESS_PROPOSAL.md) |

Non-goals for Tier 1: streaming LOAD directly from host to Z80 without
the `temp.tap` staging step (see §5, "explicitly rejected").

**Dependency:** Tier 1 needs the graceful-degradation work in
[`SD_ROBUSTNESS_PROPOSAL.md`](SD_ROBUSTNESS_PROPOSAL.md) — specifically
the `try/finally` around the `SA_funct` dispatch. Without it, a handler
that fails (no SD card, no fileserver, host unplugged mid-copy) breaks
the V6 pre-load chain and wedges the next command. "Return an error to
the 2068" is not currently a thing a handler can reliably do.

### Tier 2 — Things only a host can do

These are the reasons to want this beyond "no card shuffling":

- **Live BASIC development (the Ryan feature).** Host watches
  `game.bas`, runs the vendored [`tools/zmakebas`](../tools/zmakebas/)
  on save, and publishes the resulting TAP into the served folder. Edit
  on the Pi 400, `LOAD ""` on the 2068, run. No export step, no card.
- **Reverse path: SAVE → readable source.** A `SAVE` from the 2068
  lands as a `.tap` in the host folder; the host optionally detokenises
  it to `.bas` alongside. ⚠️ zmakebas is **one-way** (text → TAP);
  a detokeniser has to be written or vendored. See §7 Q5.
- **File previewer.** Host-side, before mounting:
  - `SCREEN$` (6912-byte CODE block at 16384) → PNG, correct Spectrum
    palette + attribute handling;
  - TAP block map (header type, name, length, autostart line);
  - BASIC listing (needs the same detokeniser as above);
  - hex view for CODE blocks.
- **Format conversion on the fly.** `.tzx` → `.tap`, `.z80`/`.sna` →
  loadable image, zip members surfaced as if they were loose files. The
  Pico never learns any of these formats.
- **Unified console.** Because the host owns the serial link, the
  firmware's `TLM()` / `LOG()` output can be framed and shown in the
  host app's log pane instead of being lost. Debugging and file serving
  in one window.

### Tier 3 — The software archive

Grabbing from
[archive.org/download/timex-sinclair-software-archive](https://archive.org/download/timex-sinclair-software-archive):

- **Host-side browser/navigator** — search, filter, preview, then
  "mount to 2068" with one click. This is the primary interface.
- **Zip handling.** Archive items are zips containing TOSEC-named TAPs
  *plus* documentation, scans and screenshots. The host must open the
  zip, list only the loadable members, and surface them as virtual
  files. It should also show the docs/screens in the preview pane —
  they're a feature, not noise.
- **Long-filename mapping.** TOSEC names
  (`Ant Attack (1983)(Quicksilva)[a2].tap`) exceed what's comfortable
  on a 32-column display and violate the SAVE-side filename sanitiser
  (`SAVE_TS` allows only alphanumerics, `-`, `_` —
  [tspico_io.py:1216](../src/TS/tspico_io.py:1216)). The host keeps the
  long name and serves a short display alias; `shorten_filename()`
  ([tspico.py:998](../src/TS/tspico.py:998)) already handles the
  display side.
- **Local cache** so the archive works offline and we're polite to
  archive.org (cache aggressively, no bulk crawling, honour rate
  limits).
- **2068-side navigator.** `ListMenu` already gives paged selection
  (16/page, `B`/`F`/`N`) and `IDIR` already uses it. So a *shortlist*
  browser on the 2068 is nearly free. What is **not** free is search —
  the ROM's input primitives give us single keypresses
  (`0x84`/`0x86`), not text entry. Design accordingly: **the host
  stages a candidate list, the 2068 picks from it.** Don't try to build
  a full archive browser on the 2068 side.

---

## 3. Architecture

```
   Host computer                          TS-Pico                     TS-2068
┌────────────────────┐            ┌────────────────────────┐      ┌──────────┐
│  tspico-fileserver │            │  TS2068_IO() main loop │      │          │
│                    │            │                        │      │  Z80 +   │
│  ┌──────────────┐  │  USB CDC   │  ┌──────────────────┐  │ TPI  │  modified│
│  │ RPC server   │◄─┼────────────┼─►│ TS/usbfs.py      │  │ $0E  │  ROMs    │
│  │ (framed)     │  │  framed    │  │ (transport +     │  │ $0F  │          │
│  └──────┬───────┘  │  binary    │  │  storage backend)│  │◄────►│          │
│         │          │            │  └────────┬─────────┘  │      │          │
│  ┌──────▼───────┐  │            │           │            │      └──────────┘
│  │ served       │  │            │      /TMP/temp.tap     │
│  │ folder       │  │            │      (unchanged)       │
│  └──────────────┘  │            │           │            │
│  zmakebas, zip,    │            │      LOAD_TS/SAVE_TS   │
│  preview, archive  │            │      (UNCHANGED)       │
└────────────────────┘            └────────────────────────┘
```

**The load-bearing design rule**, and the one thing a reviewer should
check on every line of new firmware code:

> All USB I/O happens **either** in the main loop's idle branch,
> **or** inside a command handler with `Y = BUSY` asserted. Never
> between draining the pre-header and writing the response.

This is the same rule as the existing "don't `print()` during a
protocol exchange" pitfall ([`PROTOCOL.md`](PROTOCOL.md) §13), for the
same reason: the PIO RX FIFO is 4 bytes deep and the Z80 OUTs every
~30 µs. The Z80's `$0F` poll timeout is ~20 s
([`GUSTAVO_PROTOCOL.md`](GUSTAVO_PROTOCOL.md) §7), which is an enormous
budget for a USB round-trip — so asserting BUSY and taking our time is
both safe and easy.

### Storage backend abstraction

Two candidate approaches. **Spike 2 (§6) decides which.**

**Option A — Python VFS object mounted at `/usb`.** MicroPython's
`extmod/vfs.c` duck-types a mounted object for `ilistdir`, `stat`,
`open`, `mkdir`, `remove`, `rename`, `chdir`. If that works on
v1.20.0/rp2, we write one class and every existing `os.*` call in
`tspico.py` keeps working with only the path root changed. Big win.
⚠️ **This capability is undocumented** — the published filesystem docs
only cover block devices
([docs.micropython.org](https://docs.micropython.org/en/latest/reference/filesystem.html)).
Must be proven on hardware before we design around it.

**Option B — explicit backend functions.** Replace direct `os.*` calls
in the ~12 SD-touching functions with `fs.listdir()`, `fs.stat()`,
`fs.copy_to_temp()`, etc., dispatching on `TSP.storage`. More edits,
zero platform risk, and arguably clearer. This is the fallback and it
is not a bad outcome.

Either way, `ACTIVATE_SD()` and `DEACTIVATE_SD()` gain an early return
when `TSP.storage == "usb"` — two function bodies, covering all eight
callsites.

---

## 4. The USB transport (the genuinely uncertain part)

### The constraint

MicroPython **v1.20.0** (pinned in
[`.github/workflows/build.yml`](../.github/workflows/build.yml)) on rp2
exposes **one** USB CDC interface, and it is stdin/stdout/REPL. Unlike
the STM32 port's `USB_VCP`, rp2 has no way to get a second independent
serial channel in this version.

Three ways forward:

| | Approach | Pros | Cons |
|---|---|---|---|
| **A** | Share the REPL CDC with a framed binary protocol | No firmware version bump. Works today. | Needs `micropython.kbd_intr(-1)`, which **disables Ctrl-C** → breaks Thonny interrupt and the web-updater's "Ctrl-C to interrupt" step while active |
| **B** | Bump to MicroPython ≥1.23 and add a second CDC via `machine.USBDevice` | Clean separation; REPL stays free for Thonny | Large, risky firmware bump (PIO/API/RAM deltas) on a codebase tuned against 1.20 |
| **C** | Custom C-level USB descriptor | Cleanest | Abandons the pure-MicroPython build model |

**Recommendation: A now, B later if it hurts.** The known-good pattern
is `micropython.kbd_intr(-1)` + `select` + `sys.stdin.buffer` /
`sys.stdout.buffer`
([MicroPython discussion #11889](https://github.com/orgs/micropython/discussions/11889)),
and it must be proven by Spike 1 before anything else is built.

Mitigation for the Ctrl-C loss: only disable `kbd_intr` **while USB
mode is active**, and give the host app an explicit "release the link"
button that restores `kbd_intr(3)` so Thonny and the web-updater work
normally again. Document it loudly — a user who can't Ctrl-C into their
Pico and doesn't know why will be very unhappy.

### Framing

Both directions, so the host app can also be the telemetry console:

```
0xAA 0x55 | seq(1) | opcode(1) | len(2, LE) | payload… | crc16(2)
```

The host resynchronises on the `AA 55` magic and treats any
non-conforming bytes as plain console text — which means MicroPython
tracebacks, boot banners and stray `print()`s land in the log pane
instead of corrupting the stream. That robustness is worth the two
magic bytes.

Opcode sketch (host→Pico unless noted):

| Op | Name | Payload |
|---|---|---|
| `0x01` | `HELLO` | protocol version, capabilities, host app version |
| `0x02` | `LIST` | path → entries (name, is_dir, size) |
| `0x03` | `STAT` | path → size, mtime, exists |
| `0x04` | `FETCH` | path → size, then N chunks into `/TMP/temp.tap` |
| `0x05` | `PUT_BEGIN` / `0x06 PUT_CHUNK` / `0x07 PUT_END` | path, mode (`wb`/`ab`), bytes |
| `0x08` | `MKDIR` / `0x09 REMOVE` / `0x0A RENAME` | path(s) |
| `0x0B` | `HELPTEXT` | topic → text |
| `0x0C` | *(host→Pico, unsolicited)* `NOTIFY` | "mount this", "folder changed" |
| `0x80` | *(Pico→host)* `LOG` | level + message — replaces lost `TLM` output |
| `0x81` | *(Pico→host)* `EVENT` | mounted, saved, error |

Chunk size 256–512 B with per-chunk ack. USB CDC at 12 Mbps will do
far better than the Z80's ~21 KB/s read rate, so the link is never the
bottleneck.

### Transport hazards to design against

- **A blocking `sys.stdout.write` when the host stops reading will hang
  the firmware** — same failure class as a blocking `MQ.put`. All
  writes must be bounded/timeout-guarded, and the watchdog pattern in
  `CHK_STATUS`/`WATCHDOG` extended to cover USB stalls.
- **Host app disappears mid-transfer** (unplug, crash, laptop sleep).
  Needs a clean timeout → error status to the Z80 → fall back to
  "no file mounted", not a lock-up.
- **`TLM_ENABLED = True` writes unframed text to the same CDC.** In USB
  mode, telemetry must go through opcode `0x80` or be disabled.
- **Core 1 is not available for a USB service thread.** RP2040
  MicroPython supports exactly one extra thread, and it is already used
  transiently by `BLINK_LED`, `WATCHDOG` and `SAVE_LOG`. USB servicing
  must be **cooperative polling in the main loop's idle branch**, not a
  thread.

### 4.4 Liveness — "am I connected to a fileserver?"

**Detect the app, not the cable.** This distinction drives the whole
design:

- MicroPython v1.20 on rp2 has no CircuitPython-style
  `usb_cdc.connected` — there is no clean hardware-level "host
  present" signal available to us.
- Even if there were, it would answer the wrong question. A cable
  plugged into a phone charger, or into a laptop with the fileserver
  app not running, would both report "connected" while being useless.

So liveness is an **application-level `HELLO` with a short timeout**
(~250 ms is generous — see Spike 1 for the measured round-trip). Three
outcomes the user cares about:

| Result | Meaning | 2068-side message |
|---|---|---|
| `HELLO` answered | Fileserver running, folder served | `Fileserver: <name> (<n> files)` |
| Timeout | No app (cable may or may not be present) | `No fileserver responding` |
| Framing errors | App present, version mismatch | `Fileserver version mismatch` |

`tpi:reconnect` re-runs the probe on demand and reports the result —
the direct analogue of `tpi:remount` for the SD side. The probe also
runs automatically on `tpi:usb` (mode switch) and is cached, so
`tpi:info` and the mount path can report status without a round-trip
on every command.

**Hazard to measure in Spike 1:** what `sys.stdout.write` does when the
CDC is connected but the host is not draining it. If it blocks, a
crashed or suspended host app hangs the firmware — the same failure
class as a blocking `MQ.put()`. All USB writes need to be bounded, and
the `WATCHDOG` / `CHK_STATUS` pattern extended to cover USB stalls.

### 4.5 Copying between backends

**USB and SD share no pins.** SD steals GPIO 2-4 from the PIO; USB is
on the RP2040's own PHY. So during an SD write window the Z80 is blind
(PIO torn down) but the USB link is still fully alive.

Consequence: a host → SD copy can **stream directly**, with no `/TMP`
staging step and therefore no Pico-flash size ceiling. The sequence is:

```
ACTIVATE_SD()            # PIO down, Z80 blind, USB still live
  host FETCH → chunks → write directly to /sd/<path>
DEACTIVATE_SD()
ACTIVATE_MQ()            # PIO back up
SEND_MSG("Copied: ...")  # V6 chain intact
```

The budget is the Z80's ~20 s `$0F` timeout, and the precedent is
`MOUNT_FILE`, which already makes the Z80 wait through a full SD
round-trip ([tspico.py:1185-1274](../src/TS/tspico.py:1185)). A single
TAP (typically ≤48 K) or a 64 K DCK is comfortably inside that.

**Multi-file copies are where this breaks.** Options, in order of
preference:

1. **One file per command.** Simplest, always safe.
2. **Host-driven batch.** The host app copies while the 2068 idles —
   no Z80 timeout pressure at all. This direction should lead.
3. **2068-driven batch that responds first.** `SEND_MSG` the "working"
   reply, let the Z80 complete its command, *then* do the copy. Risk:
   if the user types another command during the window, the pre-header
   lands in a 4-deep RX FIFO with the PIO possibly down → dropped
   bytes → Report J. Same exposure as any long SD op, but longer.

**2068-side UI.** `ListMenu` is single-select, so multi-file selection
needs either a `tpi:copyall`-style "everything in the current host
directory" variant, or a **mark/unmark mode added to `ListMenu`**
(toggle a `*` against an entry, then a key to commit). The latter is
more work but would also improve `IDIR` and `RM`.

**Direction and naming.** Needs deciding (§7 Q2). `tpi:copy <name>`
reads naturally as "bring that file here" when USB is the active
backend, but the reverse (SD → host, e.g. archiving a card) wants a
verb too. `tpi:get` / `tpi:put` is unambiguous but assumes the user
remembers which end is which.

---

## 5. Explicitly rejected: streaming LOAD straight from the host

It is tempting to skip `/TMP/temp.tap` and feed host bytes directly
into the TX FIFO during `LOAD_TS`. Don't — at least not in Tier 1.

It puts a USB round-trip inside the one code path this project has
repeatedly proven is unforgiving of latency, in exchange for saving
~200 ms of staging and some flash wear on a transfer that is already
gated by the Z80 at ~47 µs/byte. Stage to `temp.tap`, keep `LOAD_TS`
byte-for-byte unchanged, and revisit streaming later as a measured
optimisation with its own harness.

---

## 6. Plan

Following the repo's harness-first methodology
([`../src/CLAUDE.md`](../src/CLAUDE.md)): prove each unknown in
isolation before touching production code.

### Phase 0 — Spikes (do these before committing to anything)

| # | Spike | Question it answers | Est. |
|---|---|---|---|
| 1 | `src/test/usb_channel_probe.py` | Can we exchange framed binary over the REPL CDC while the firmware runs? What does `kbd_intr(-1)` break? What throughput and per-call latency do we get? | 1–2 days |
| 2 | `src/test/usb_vfs_probe.py` | Does `os.mount(<python object>, '/usb')` work on v1.20.0/rp2 (Option A), or do we take Option B? | 1 day |
| 3 | RAM budget measurement | `gc.mem_free()` before/after loading the transport module + buffers, at each existing boot checkpoint | 0.5 day |
| 4 | `src/test/usb_load_harness.py` | Full LOAD of a host-served TAP, standalone — no dispatcher, no SD | 2–3 days |

**Spike 1 is the gate.** If binary-over-REPL-CDC turns out to be
unworkable on v1.20.0, the whole plan reroutes through a MicroPython
version bump and the estimates below roughly double.

### Phase 1 — Core file server (Tier 1)

1. `src/TS/usbfs.py` — framing, opcodes, backend implementation.
   Add to [`manifest.py`](../src/manifest.py) (easy to forget; the
   manifest comment says so).
2. Mode switch: `TSP.storage`, `tpi:usb` / `tpi:sd` / `tpi:drive`,
   `config.ini` default, `tpi:info` reporting.
3. `ACTIVATE_SD` / `DEACTIVATE_SD` early-return in USB mode.
4. Liveness probe + `tpi:reconnect` (§4.4).
5. Migrate commands one at a time, hardware-testing each:
   `dir` → `cd` → `path` → mount-by-name → mount-by-index → `LOAD` →
   `SAVE` → `append` → `md`/`rm`/`newtap` → `help` → `.dck`/`.rom`.
6. `tpi:copy` — single file, host → SD (§4.5).
7. Host app v0: Python daemon, framed serial client, folder picker,
   headless + minimal UI.

**Prerequisite:** the graceful-degradation work in
[`SD_ROBUSTNESS_PROPOSAL.md`](SD_ROBUSTNESS_PROPOSAL.md) lands first
(at minimum the `try/finally` dispatch fix and the no-SD boot path).

**Estimate: 3–5 weeks of evenings** for someone fluent in this
codebase, on top of the SD-robustness work. Step 5 dominates and is
where hardware time gets spent.

### Phase 2 — Host application (Tier 2)

Preview pane (SCREEN$ → PNG, TAP block map, hex), zmakebas watch-and-
build, format conversion, unified log console, packaging for Windows /
macOS / Linux / Pi.

**Estimate: 3–4 weeks.** Almost entirely host-side; can proceed in
parallel with Phase 1 once the opcode set is frozen.

### Phase 3 — Software archive (Tier 3)

archive.org index + search, zip member handling, long-name mapping,
local cache, "stage a shortlist for the 2068" flow, `ListMenu`-based
2068-side picker.

**Estimate: 2–3 weeks**, mostly host-side.

### Phase 4 — Reverse toolchain

TAP → BASIC detokeniser (new code — see §7 Q5), SAVE-side auto-export,
round-trip tests.

**Estimate: 1–2 weeks.**

---

## 7. Open questions for the team

**Q1. Host app technology?** Recommendation: a **Python daemon with a
localhost web UI**, packaged with PyInstaller for Windows/macOS and
`pip`/apt for Linux and the Pi 400. Rationale: `pyserial` works
everywhere, zip/PNG/zmakebas handling is trivial in Python, and it
doesn't depend on Chromium-only APIs. The alternative — extending
[`web-updater/`](../web-updater/) with the File System Access API —
needs no install at all but locks users to Chrome/Edge, which is a bad
fit for the Pi 400 audience this feature exists for. The web updater
should stay as-is for firmware updates either way.

**Q2. Command naming.** `tpi:usb` / `tpi:sd` / `tpi:drive`? Or
`tpi:host`? Or a single `tpi:drive usb|sd` toggle? Plus the copy verb
(§4.5): `tpi:copy` vs `tpi:get`/`tpi:put`. And `tpi:reconnect` should
pair sensibly with `tpi:remount` on the SD side. Bikeshed now, it's
cheap; renaming a shipped command isn't.

**Q3. ~~Can SD and USB be active simultaneously?~~ — SETTLED.** They
never need to be. USB shares no pins with the SD/PIO bus, so the two
backends simply *alternate* (§4.5). The copy feature does not
reintroduce the bus-handover hazard that §1b says USB mode avoids.

**Q4. Ctrl-C / `kbd_intr` policy.** How do we make "your Pico is in USB
mode so Thonny can't interrupt it" discoverable rather than
mystifying? Suggestion: host app owns an explicit release button, plus
a note in `tpi:info` and the docs.

**Q5. Detokeniser — write, vendor, or skip?** zmakebas is one-way. The
reverse path (TAP → readable `.bas`) is what makes the round trip feel
finished, but it's real work and there may be an existing MIT/GPL
tool worth vendoring the way we vendored zmakebas.

**Q6. Do we bump MicroPython?** Not for Tier 1 if Spike 1 passes. But
if we ever want the REPL and the data channel simultaneously (Option B
in §4), it becomes the enabling change — worth knowing whether the team
wants that on the roadmap independently.

**Q7. Security/blast radius.** The host app hands a serial peer the
ability to read, write and delete files. It must be sandboxed to the
chosen folder with no `..` escapes, and destructive operations
(`tpi:rm`) should be confirmable in the host UI. Worth deciding the
default posture before writing the opcode handlers, not after.

---

## 8. Summary

- The wire protocol **does not change**. That removes the riskiest
  part of any change to this firmware.
- The read path needs **one** new capability: get host bytes into
  `/TMP/temp.tap`. Everything downstream is untouched.
- USB mode **eliminates** the SD/PIO bus-handover hazard that caused
  Report D, the `ACTIVATE_MQ` pre-load bug and the SAVE pin-grab race.
- Because USB shares no pins with the SD/PIO bus, the two backends
  alternate cleanly — so **host → SD copy streams directly**, with no
  staging step and no flash size ceiling (§4.5).
- Liveness must probe **the app, not the cable** (§4.4).
- The one genuine unknown is the **USB byte channel on MicroPython
  v1.20.0** (single CDC, shared with the REPL). Spike 1 gates
  everything.
- Rough total: **~3–5 weeks of evenings for a usable Tier 1** (after
  the SD-robustness prerequisite), with Tiers 2 and 3 adding another
  6–9 weeks of host-side work that carries much lower risk and can run
  in parallel.
