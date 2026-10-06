# TS-Pico Developer Guide

A hands-on onboarding guide for a new contributor: from "I just
cloned the repo" to "I made an edit, built an `.mpy`, tested it on
hardware, opened a PR." If you've never worked on this codebase
before, start here.

This guide is the **how-to-work-on-it** companion to the three
existing architecture docs:

- [`GUSTAVO_PROTOCOL.md`](GUSTAVO_PROTOCOL.md) — the protocol from the
  Z80 ROM's point of view (the high-level "what is TPI?").
- [`PROTOCOL.md`](PROTOCOL.md) — the firmware-implementation view of the
  same protocol (what the Pico does, instruction by instruction).
- [`DUAL_PORT_DEVELOPMENT.md`](DUAL_PORT_DEVELOPMENT.md) — the
  development narrative behind the current dual-port PIO architecture
  (wrong turns, latent bugs, harnesses).

Skim those first if you haven't, then come back. This document avoids
duplicating them — it cross-references instead.

---

## 1. What is TS-Pico?

TS-Pico is a Raspberry-Pi-Pico-based storage interface for the
Timex Sinclair TS-2068 home computer (a ZX-Spectrum-compatible
machine from 1983). It gives the TS-2068 SD-card access, Flash/SRAM
memory bank management, and ZX Spectrum 48K compatibility.

The system has **two firmware halves** that must agree on a protocol:

- The **Z80 side** — a modified TS-2068 EXROM/HOME ROM that the user
  flashes into a chip on the TS-2068's expansion board. Owned by
  Gustavo. The Z80 drives the protocol by polling the Pico via
  `IN $0F` (status) and `IN/OUT $0E` (data).
- The **Pico side** — this repo. MicroPython running on the RP2040.
  The Python firmware runs a main loop (`TS2068_IO()`) that reacts to
  the Z80's I/O requests; PIO state machines handle the wire-level
  timing. Pico-side lead: Ricardo.

The protocol between them is **TPI** ("TS-Pico Interface"). The
current revision in production is the **dual-port** protocol, which
splits Gustavo's spec-mandated `$0E` (data) and `$0F` (status) ports
across separate PIO TX FIFOs. A future revision is sketched in
[`PROTOCOL_V2_PROPOSAL.md`](PROTOCOL_V2_PROPOSAL.md).

---

## 2. Set up your host machine

### Clone the repo

```bash
git clone https://github.com/timex-sinclair-projects/tspico-firmware-build.git
cd tspico-firmware-build
```

### Install Thonny

Thonny is the editor / file-transfer tool you'll use to push files
to the Pico over USB. Download from [thonny.org](https://thonny.org).
Any recent 4.x works. Configure it for **MicroPython (Raspberry Pi
Pico)** under *Tools → Options → Interpreter*.

### Install `mpy-cross`

`mpy-cross` pre-compiles `.py` → `.mpy` on your host so the Pico can
load the bytecode directly, skipping its limited on-device parser.
**This is mandatory for `dev_tspico.py`** — the file is large enough
that the Pico's parser runs out of memory trying to load it as plain
Python.

The version must match the MicroPython on the Pico (currently
**v1.29.0**; it was v1.20.0 until 2026-10):

```bash
pip install --user mpy-cross==1.29.*
mpy-cross --version    # should report mpy v6.3 (v1.20 wrote 6.1)
```

A `.mpy` built for another MicroPython won't load ("incompatible .mpy
file"); `main.py` then says so and runs the frozen firmware instead.

If you'd rather use the `mpy-cross` produced by the CI's own
MicroPython build, the [`build-dev-mpy.sh`](../build-dev-mpy.sh)
script in the repo root will use whichever `mpy-cross` is on your
`$PATH`.

### Install `gh` CLI

Used for opening PRs, viewing issues, and downloading CI artifacts.
Install from [cli.github.com](https://cli.github.com) and run
`gh auth login` once.

---

## 3. Get the Pico into a known state

### Flash the firmware

The firmware UF2 is built fresh by CI on every branch. You have
three ways to get one:

1. **Latest release UF2** — go to [Releases](https://github.com/timex-sinclair-projects/tspico-firmware-build/releases),
   download the bundle (`tspico-vX.Y.Z.zip`) and use the
   `firmware.uf2` inside. Best starting point for new contributors.
2. **Branch artifact** — every push to any branch builds a UF2. Go to
   the [Actions tab](https://github.com/timex-sinclair-projects/tspico-firmware-build/actions),
   pick a run, download the `firmware-uf2` artifact. Use this when
   testing someone's PR before merge.
3. **Build locally** — clone MicroPython v1.29.0 and run the same
   commands that `.github/workflows/build.yml` runs. Rarely needed
   unless you're debugging the build itself.

Then:

1. Hold **BOOTSEL** on the Pico while plugging in USB.
2. A `RPI-RP2` drive appears on your host.
3. Drag `firmware.uf2` onto it. The Pico reboots into MicroPython.

### Copy the flash content

The system has three deploy targets — the Pico's internal flash, the
TS-2068 EXROM chip, and the SD card. Connect via Thonny for the Pico,
and use a card reader for the SD card. From a release bundle the
sources are pre-arranged under `src/` and `SD card/`; from a fresh
clone they're at the same paths in the repo:

| Target | Source in repo | Lands at | Required? |
|---|---|---|---|
| Pico flash    | `src/main.py`         | `/main.py`          | yes |
| Pico flash    | `src/config.ini`      | `/config.ini`       | yes |
| Pico flash    | `src/words.txt`       | `/words.txt`        | yes (for `tpi:.rndw`) |
| Pico flash    | `src/assets/*.tap`    | `/assets/*.tap`     | yes |
| Pico flash    | built from `src/dev_tspico.py` | `/dev_tspico.mpy` | only if iterating |
| Pico flash    | `src/dev_extcmd.py`   | `/dev_extcmd.py`    | only if iterating |
| TS-2068 EXROM | `src/rom/*.ROM`       | the expansion-board ROM chip | yes |
| SD card       | `SD card/TAP/`        | `/TAP/` on the card | yes |
| SD card       | `SD card/help/`       | `/help/` on the card | yes (for `tpi:help`) |

**Don't create a `/TS/` folder on the Pico.** That's the
shadowing trap — see §5.

### Verify

Reboot the Pico (Ctrl-D in Thonny's REPL, or just unplug and replug).
You should see the boot banner:

```
270000000
INFO: SD Card initialized and mounted OK
```

If `dev_tspico.mpy` (or `.py`) is present at root you'll also see:

```
[__main__] BUILD_VERSION = 654d3db (main)
[DEV] Using /dev_tspico.py override
```

### If the SD card won't mount after a soft reboot

The SD module runs off the Pico's 3V3 (schematic: U3 on the 3V3 rail,
nCS = GP28 with a 4K7 pull-up), so a Ctrl-C, soft reboot, `machine.reset()`
or UF2 flash never power-cycles the card. If one of those lands **during**
an SD access -- Thonny connecting interrupts `main.py`, often inside the
~0.7 s of card work at boot -- the card is left inside the transfer. In
the middle of a multi-block write (CMD25) it is still waiting for data and
swallows the next CMD0 as data, and every boot then reported

```
[ACTIVATE_SD] attempt 1/5 failed: OSError(19, 'no SD card')
```

until the power was pulled. A block refused mid-write (`EIO: write fail`)
did the same, because `writeblocks` raised without sending STOP_TRAN.
Card, wiring and driver are fine otherwise: at the REPL, reads at 1/5/10
MHz and write-and-read-back tests show zero errors, and break-at-idle +
soft reboot mounts every time.

The driver now repairs this itself (`TS/sdcard.py`, tested by
`src/test/sd_recover_hosttest.py`):

- **`init_card` starts with `_recover()`**: 520 x 0xFF with CS low
  (finishes a half-sent block), STOP_TRAN, CMD12, each with a bounded busy
  wait, then the usual CMD0. On a healthy card it's just clocks. When it
  found the card mid-transfer, `ACTIVATE_SD` prints and logs
  `SD card card was mid-transfer (...); recovered without a power cycle`.
  With CRC checks off (the default) the half-sent block is **written**
  with the 0xFF filler -- that sector was mid-rewrite anyway, but it's
  the price of not needing a power cycle.
- **`writeblocks` always ends with STOP_TRAN, `readblocks` with CMD12**,
  also when a block fails or a Ctrl-C lands between blocks. STOP_TRAN
  waits for the card to finish the last block first, or a busy card
  takes it for a clock tick.
- **Every busy wait is bounded** (`_BUSY_TIMEOUT_MS`, 1 s). A card that
  never lets go is an `ETIMEDOUT` error, not a hung Pico.

If the card still won't mount -- seen once, a card that held MISO low
(busy) for over 90 s -- **unplug the USB cable and switch the 2068 off**,
then power up. With USB connected, switching only the 2068 off and on
does not power-cycle the TS-Pico or the card.

**A hard reset of the Pico reliably leaves the card like this** (reproduced
2026-09-30, on the released 2.0 firmware as well as later builds). Every UF2
flash is a hard reset, because it reboots through the bootloader, and so is
`machine.reset()`. A soft reboot (Ctrl-D) does not cause it. Afterwards,
with the card selected, it holds MISO low indefinitely: CMD0 at 100 or 400
kHz gets no reply, and the `_recover()` sequence above doesn't reach it.
The cause is not yet known. The 4K7 pull-up on nCS should keep the card
deselected through the reset, and driving nCS and U6 off as `main.py`'s
very first lines did not prevent it.

**To clear it, do either of these:**

- **Reseat the SD card** (pull it out and push it back in). This
  power-cycles the card by itself; the Pico and the 2068 can stay on, and
  the next `ACTIVATE_SD` mounts.
- **Power-cycle the whole TS-Pico**: unplug the USB cable *and* switch the
  2068 off, then power up.

So after flashing a UF2, reseat the card or power-cycle before using it.

A card can also mount and then fail its first write. `activity.log` then
shows

```
ERROR:DIR_FILES: SD card error, directory listing skipped: [Errno 5] EIO: write fail
WARNING:SD card mounted but failing; continuing without a directory listing
```

and the boot carries on into the dispatcher, so the 2068 still gets a
working TS-Pico for anything that doesn't need the card (LOAD from the
flash assets), and `tpi:dir` says the card failed. The write need not
come from anything that looks like a write -- FatFs flushes a sector
dirtied by an earlier `os.remove` when the next call, even
`os.ilistdir()`, moves on, so `DIR_FILES` catches `OSError` around all of
its SD work.

The same can happen mid-session. Once the card stops answering, every
command that needs it (CD, MD, RM, NEWTAP, HELP, LOAD "tpi:file", the
re-mount after a SAVE) spends its five `ACTIVATE_SD` attempts and then
fails with Report J; `activity.log` shows `Mounting SD Card failed in
ACTIVATE_SD after 5 attempts!` and the handler exception. Everything else
keeps working. Only at boot, with no card at all, does `ACTIVATE_SD`'s
failure still end in the blinking error loop.

---

## 4. Repo layout

Two payload trees:

- **`src/`** — anything that ends up on the Pico's flash filesystem
  or in the TS-2068 EXROM chip.
- **`SD card/`** — anything that ends up on the SD card the user
  plugs into the TS-Pico (test/protocol TAPs, `tpi:help` text).

```
.
├── README.md
├── docs/                          # Architecture, protocol, development narrative
│   ├── GUSTAVO_PROTOCOL.md        # Z80-ROM view of the protocol
│   ├── PROTOCOL.md                # Pico-firmware view
│   ├── DUAL_PORT_DEVELOPMENT.md   # How the dual-port code was earned
│   ├── EXTCMD_PROTOCOL.md         # Writing TPI:.XXX handlers
│   ├── PROTOCOL_V2_PROPOSAL.md    # Future-revision design sketch
│   ├── LOW-LEVEL-PROTOCOL-V5.TXT  # Gustavo's authoritative wire spec
│   ├── OPEN_QUESTIONS.md          # Live design questions
│   ├── AUDIT-2026-09-30.md        # Assumption audit: what is still open
│   └── DEVELOPER_GUIDE.md         # ← this file
├── archive/                       # Historical reference material
├── SD card/                       # Goes on the user's SD card
│   ├── TAP/                       #   .tap library (incl. test/ + pico/ subdirs)
│   └── help/                      #   tpi:help <topic> text
└── src/                           # Goes on the Pico (or the EXROM chip)
    ├── CLAUDE.md          # Contributor conventions (Claude Code)
    ├── main.py            # Boot entry. Sets pins, frequency, then enters TS2068_IO()
    ├── config.ini         # JSON runtime config (log level, ROM/DCK slots, etc.)
    ├── words.txt          # Word list used by tpi:.rndw extcmd
    ├── manifest.py        # MicroPython frozen-module manifest
    ├── build-dev-mpy.sh   # One-liner: dev_tspico.py → dev_tspico.mpy
    │
    ├── TS/                # The frozen package (baked into the UF2)
    │   ├── __init__.py
    │   ├── tspico.py      # Main module (~4000 lines): I/O loop, commands, logging
    │   ├── tspico_io.py   # PIO state machines (TS_IO_DUAL, sel_bank, set_ctrl, set_dck)
    │   ├── sdcard.py      # SD-card SPI driver
    │   ├── extcmd.py      # User-extensible TPI:.XXX command handlers
    │   └── help.py
    │
    ├── dev_tspico.py      # Dev-override copy of TS/tspico.py — edit here
    ├── dev_extcmd.py      # Dev-override copy of TS/extcmd.py
    │
    ├── assets/            # Internal protocol .tap files (live at /assets/ on Pico)
    ├── rom/               # Z80-side EXROM image (programmed into TS-2068 chip)
    │
    └── test/              # Bus-level harnesses for protocol bring-up
        └── _harness_template.py   # READ THIS before writing a new harness

# (BASIC test programs — picotest.tap etc. — now live under "SD card/TAP/".)

# GitHub-managed at root:
.github/workflows/
    ├── build.yml        # Builds firmware.uf2 + dev_tspico.mpy on every push
    └── release.yml      # Builds the release bundle on git tag push
```

---

## 5. The `.mpy` build flow

### Why it exists

`dev_tspico.py` is large (~4800 lines) and growing. When MicroPython
tries to import it as text on the Pico, the parser allocates working
memory roughly proportional to the source size — and runs out before
finishing. The fix is to compile to bytecode (`.mpy`) on the host,
where memory isn't a constraint. The Pico then loads the bytecode
directly with no parser pass.

This is **not optional** for `dev_tspico.py`. It's optional for
`dev_extcmd.py` (small enough to import as text).

### How to build

```bash
./build-dev-mpy.sh
```

The script just runs `mpy-cross dev_tspico.py` and prints sizes. The
output `dev_tspico.mpy` lands next to the source.

### Iteration cycle

1. Edit `dev_tspico.py` on your host.
2. `./build-dev-mpy.sh`
3. In Thonny: upload `dev_tspico.mpy` to the Pico's root.
   **Delete any old `dev_tspico.py` of the same name on the Pico.**
   Don't have both — MicroPython's import order between them is
   not what you want to debug.
4. Reset the Pico (Ctrl-D in Thonny, or physical reset).
5. Test on the TS-2068.

### CI also builds it

`.github/workflows/build.yml` runs `mpy-cross dev_tspico.py` on every
push and uploads `dev_tspico.mpy` as an artifact next to the UF2. So
if you push your branch, you can download a built `.mpy` from the
Actions tab instead of running `mpy-cross` locally.

### The upgrade UF2 is a second build of `tspico_io.py`

CI builds two UF2s from this repo, not one:

| UF2 | Freeze manifest | What it's for |
|---|---|---|
| `firmware.uf2` (`tspico-firmware-uf2`) | `src/manifest.py` | the TS-Pico firmware |
| `upgrade.uf2` (`tspico-upgrade-uf2`) | `src/upgrade/manifest.py` | the web updater's ROM step: it serves the updater tape and writes ROM 2.x to flash slot 1 and ZX ROM v4 to slot 0 |

The upgrade UF2 runs its own frozen `main.py` (`src/upgrade/main.py`) and
reuses the bus code in `src/TS/tspico_io.py`. It freezes only the modules
that code needs, which today are `TS/__init__.py`, `TS/tspico_io.py`,
`TS/sdcard.py` and `TS/native.py`. Anything those import when they load
has to be in that list too.

**So editing `tspico_io.py` can break the ROM updater.** If you add a
module-level import of another `TS` module to it, you must also:

1. add a `freeze()` line for the new module to `src/upgrade/manifest.py`;
2. add the file to the `cp ... $M/modules-upgrade/TS/` line in **both**
   `.github/workflows/build.yml` and `.github/workflows/release.yml`.

Otherwise the upgrade UF2 dies at boot with `ImportError` before it has
selected a ROM. The 2068 gives a high beep at power-on, and the web
updater's ROM update can't start. That is what happened from #82, which
added `from TS import native`, until it was found on hardware on
2026-10-01. Nothing in the normal firmware shows the problem, because the
normal firmware has every module.

`src/test/upgrade_hosttest.py` now checks both steps:
- every module-level import in the frozen files is itself frozen;
- both workflows copy exactly the frozen `TS` files.

An import inside a function isn't checked, and it's safe as long as the
upgrade code never calls that function. `SAVE_TS`'s
`from TS.tspico import TLM` is the example.

**To see why an upgrade UF2 isn't working,** connect to its serial port and
press Ctrl-D (`python3 tools/pico-serial.py softreset`). Its `main.py` runs
again and prints any traceback.

**To run the upgrade UF2 by hand without wiping the Pico,** rename
`/main.py` first, for example to `/main.bak`. A `main.py` on the filesystem
takes priority over the frozen one. The web updater avoids this by erasing
the whole flash first. Put the file back after flashing the normal firmware
again.

---

## 6. The dev-override pattern

`main.py` ends with this:

```python
try:
    from dev_tspico import TS2068_IO
    print("[DEV] Using /dev_tspico.py override")
except ImportError:
    from TS.tspico import TS2068_IO
TS2068_IO()
```

A file named `dev_tspico.py` *or* `dev_tspico.mpy` at the Pico's
flash root activates the override automatically. To revert: delete
the file, reboot. Same pattern for `dev_extcmd.py`.

Inside the override, imports from the `TS` package still resolve to
the **frozen** modules in the UF2 — so the override file imports
`from TS.tspico_io import ...` and gets the frozen PIO definitions
without any extra setup.

### The `/TS/` shadowing trap (read this twice)

**Never create a `/TS/` folder on the Pico's flash filesystem.**

If `/TS/` exists on flash, MicroPython resolves the entire `TS`
package from that flash folder and **stops looking at the frozen
modules.** Since your flash `/TS/` folder almost certainly doesn't
contain the full set of submodules (`tspico_io`, `sdcard`, `extcmd`,
`help`), imports like `from TS.tspico_io import ...` fail at runtime
with `ImportError`, and you get a Pico that won't boot.

The dev-override pattern explicitly **lives at the root**, not under
`/TS/`, so it sidesteps this trap by leaving the `TS` package
resolution alone. That's also why the `.tap` assets live in `/assets/`
and not under `/TS/`.

If you ever do see this failure mode in the wild, the fix is to
delete the `/TS/` folder from flash entirely and reboot.

---

## 7. The PIO ↔ MicroPython "ready" contract

This is the single most important wire-level invariant in the
firmware. Get it wrong and you get intermittent `J errors` or hangs.
The contract was hardened in issue #14 (fix shipped in v1.5.1) and
the rules below assume the post-#14 state of the code.

### Background — the Z80 polling pattern

The Z80 reads status from port `$0F` and tests bit 6:
- **Bit 6 = 1** → "Pico is ready, you may continue / read data."
- **Bit 6 = 0** → "Pico is busy, wait."

It does this inside a WAIT-EXECUTION loop that polls roughly every
2.8 ms and gives up after ~700 ms (256 retries) with `Report J`.

On the Pico side, the PIO state machine drives bit 6 from a register:
`Y = 0xFFFFFFFF` → bit 6 set (READY). `Y = 0` → bit 6 clear (BUSY).

### The auto-busy rule (post-#14)

The PIO data SM is wired so that **every Z80 OUT to `$0E` automatically
drops Y to 0 (BUSY).** The change in `TS/tspico_io.py` is the
`mov(y, null) .side(0)` right after the `push(noblock)` in the
`z80_out` path. This makes Y transient as Gustavo's V5 protocol
expects.

Consequence: after **any** Z80→Pico OUT, the Python side is
implicitly BUSY until it explicitly re-asserts READY.

### The two MicroPython helpers

```python
def MQ_READY():    # Y = 0xFFFFFFFF — bit 6 set
    MQ.exec("mov(y, invert(null))")

def MQ_BUSY():     # Y = 0 — bit 6 clear
    MQ.exec("set(y, 0)")
```

### When to call `MQ_READY()`

Anywhere the Python firmware finishes preparing a response for the
Z80 and wants to release the Z80's WAIT-EXECUTION poll. This includes:

- After the main loop has drained the pre-header bytes from the RX
  FIFO (the OUTs auto-dropped Y; we need to bring it back so the
  Z80's *next* `IN $0F` poll succeeds).
- After `PROCESS_CMD` and `PROCESS_ASM` write the V6 pre-load byte
  (`0x01`) into the TX FIFO at the tail of every command — that byte
  becomes the status the Z80 reads first on the *next* command.
- After `SEND_MSG` has written its three header bytes (`0x81`, `st`,
  `0x0D`) into the TX FIFO — **but not before**.
- After `LOAD_TS` and `SAVE_TS` finish each phase (final status
  write, pre-load byte, mid-status updates, timeout / watchdog
  recovery paths, normal completion).
- In `SEND_MSG2`, after the keypress response in the scroll branch.
- In `SEND_MSG_PROMPT_YN` and `ListMenu` after the keypress is
  consumed, on both `'N'` and continuation paths.

### The cardinal rule

> **You must put a byte into the TX FIFO before calling `MQ_READY()`
> when you're sending data to the Z80.**

If you assert READY with an empty TX FIFO, the Z80 will `IN $0E` and
the PIO will return `0x00` (the empty-FIFO fallback). The Z80
interprets `0x00` at the wrong moment as **Report J — Invalid I/O
Device**, the user sees an error, and you spend an afternoon
chasing a "PIO bug" that was actually a sequencing bug in your
Python.

State this as a checklist when writing any new response code:

1. `MQ.put(byte)` (or `wrt(byte)`) — load the TX FIFO.
2. `MQ_READY()` — only then.
3. Loop back to step 1 if more bytes follow.

`SEND_MSG` is the canonical example: it writes the three header
bytes, *then* asserts READY, *then* enters the body for-loop. If you
inverted that — asserted READY first, then tried to wrt the header
under BUSY — the Z80 would read garbage from an empty FIFO before
your wrts landed.

The TX FIFO is only 4 bytes deep, so `wrt()` blocks while the Z80
hasn't drained it yet. That's *fine* — the back-pressure is part of
the contract. What's not fine is asserting READY with nothing in the
buffer.

### The V6 pre-load chain

A subtler form of the same rule. The Z80's first action on every
command is to read `$0F` for the response status. If the TX FIFO is
empty at that moment, it gets `0x00` → Report J.

To avoid this, every command tail in `PROCESS_CMD` / `PROCESS_ASM`
writes `0x01` (the `STAT_1_OK` byte) into the TX FIFO **before**
returning to the main loop. That byte sits in TX waiting for the
*next* command's first status read. It chains command-to-command
forever; the V6 designation refers to the revision where this was
made universal.

If you add a new command handler, the very last thing it does on
the success path must be the pre-load byte + `MQ_READY()`.

---

## 8. The TLM telemetry switch

The firmware (`TS/tspico.py`, and `dev_tspico.py` when it is loaded) has a
tracing system that prints timing-relevant events over USB serial. It's off
by default (zero overhead). Switch it on with `"TELEMETRY": true` in the
Pico's `/config.ini`; `main.py` reads it at boot and sets `TLM_ENABLED`
for both copies. Releases ship it `false`.

When enabled, lines like

```
[TLM us=12345678 tx=2 rx=0] PROCESS_CMD: pre=[0x86,0x05,...]
```

appear on the REPL. `us` is `ticks_us()` at the event, `tx`/`rx`
are the FIFO occupancies measured *as* the event fired.

To capture it without Thonny -- read-only, so the firmware keeps
running -- use `python3 tools/pico-serial.py watch`. The same tool
flashes UF2s (`flash --branch <name>`, no BOOTSEL buttons), runs REPL
snippets (`run`) and interrupts or restarts the firmware (`break`,
`softreset`); see its docstring and `src/CLAUDE.md`, "Talking to the Pico
directly". It refuses to share the port, so disconnect Thonny first.

You can flip it from the REPL without rebooting:

```python
import dev_tspico
dev_tspico.TLM_ENABLED = True
```

(or `TS.tspico.TLM_ENABLED`, for the frozen module). Leave `TELEMETRY` off
on boards you aren't debugging: the prints are surprisingly expensive in
tight inner loops.

---

## 9. Harness-first methodology

For wire-level bugs — anything that involves Z80/PIO timing, FIFO
depth, race windows — **write a harness in `/test/` before editing
production code.**

Read [`/test/_harness_template.py`](../test/_harness_template.py)
first. It enforces the two-phase capture rule (set up → fire →
capture → assert offline) that keeps the harness's own timing from
distorting the very signals you're trying to measure.

Cross-references:
- The methodology, in depth: `DUAL_PORT_DEVELOPMENT.md` §§ 4–5.
- Why this matters: the same doc, the section on "the three latent
  bugs" — every one was found by a harness, not by reading the
  production code.

The pattern paid off twice during the #14 work: the symptoms looked
like a SEND_MSG2 race, but the fix was structural (PIO auto-busy +
explicit `MQ_READY` discipline), and the harness was what made the
underlying contract visible.

---

## 10. GitHub workflow

The build process is fully on CI; you should rarely need to flash
locally-built UF2s.

### Feature-branch cycle

```bash
git checkout main
git pull
git checkout -b descriptive-name
# ...edit, commit...
git push -u origin descriptive-name
gh pr create --fill         # or write title/body yourself
```

CI fires on push: every branch and PR gets a `firmware.uf2` and a
`dev_tspico.mpy` artifact. You can flash any branch's UF2 to test it
before the PR merges.

When the user has confirmed the change works on hardware, **squash-merge**
to main. Squash because the iteration commit history during a fix
session is usually noisy ("try X", "revert", "try Y") and not worth
preserving on `main`.

### Release cycle

Cutting a release is a single command:

```bash
git tag v1.5.2
git push --tags
```

`release.yml` does the rest:

1. Builds `firmware.uf2` and `dev_tspico.mpy` fresh from the tagged commit.
2. Assembles a `tspico-v1.5.2.zip` bundle with the UF2, every
   Pico-flash file (`main.py`, `config.ini`, `words.txt`,
   `assets/*.tap`, `help/*.txt`, plus optional `dev_*` files), and
   a `DEPLOY.md` with end-user instructions.
3. Publishes a GitHub Release with auto-generated notes (commit
   messages since the previous tag) and both `firmware.uf2` and the
   zip as downloadable assets.

The workflow is idempotent: if a maintainer pre-creates the release
to write custom notes (which itself pushes the tag and triggers the
workflow), the workflow uploads assets to the existing release
rather than failing.

Tag format: `vMAJOR.MINOR.PATCH`. The bundle filename and release
title both derive from the tag.

### CLAUDE.md

If you use Claude for any of this, read `CLAUDE.md` at the repo
root — it captures the workflow conventions (the harness-first
rule, two-phase capture, "when you're stuck" debugging cues) in the
form Claude expects.

---

## 11. Common debugging recipes

### "My code edit isn't taking effect"

Check the boot log:
- `[DEV] Using /dev_tspico.py override` → your `dev_tspico.{py,mpy}`
  loaded. Did you re-upload after editing?
- *No* `[DEV]` line → you're running the frozen `TS.tspico`. Either
  upload `dev_tspico.mpy` to the Pico's root, or you forgot to flash
  the UF2 you built from your branch.

The `BUILD_VERSION` print near the top tells you which **UF2** is on the
board: `tools/gen-buildinfo.py` writes it from git at build time, so it
reads e.g. `654d3db (main)`, with `+dirty` when the tree it was built from
had uncommitted changes. There is nothing to bump by hand — it used to be a
literal and it rotted, describing behaviour the firmware no longer had.

For "is *my edit* the one running", read the `[DEV]` line, not this one: a
dev override is a `.py` on the Pico's flash, while `buildinfo` is frozen
into the UF2 underneath it, so editing the override does not change the
stamp. `tpi:info` shows the same string on a `>Build:` line, which is the
way to read it from the 2068 with no USB console.

### "Pico hangs / LED stops blinking"

The main loop has died. In Thonny: Ctrl-C to interrupt, then read
the traceback. The line number is usually enough to localize the
problem. Or from a shell, with Thonny disconnected:
`python3 tools/pico-serial.py break`.

Subtle case: a 100 ms blink every 2 seconds is the **normal idle
heartbeat**, not a hang. A truly hung Pico shows a steady LED state
(usually on).

### "The port opens but Ctrl-C gets nothing back"

If the 2068 still works but USB is silent -- no `>>>` however many
Ctrl-Cs, only a reset brings it back -- there are two known ways to get
there, and they look alike from the host:

- **Text filled stdin (fixed).** Something sent the running firmware
  511+ bytes of text, which fills MicroPython's stdin buffer, and then
  Ctrl-C is never seen. Reproduced on hardware with 600 bytes. The
  firmware now drains stdin at the idle heartbeat (`DRAIN_STDIN`), so
  Ctrl-C lands within about 2 s; 2.0 and earlier need the reset button.
  Tools should send Ctrl-C and wait for `>>>` before sending anything
  else. Here the port always **opens** at once.
- **USB not serviced at all (unexplained).** Seen once, 2026-09-28,
  during the web-updater tests (PR #74): nothing had written to the
  port, yet Chrome's first `open()` failed outright and the Ctrl-Cs
  that followed got nothing. That points to core0 stuck somewhere that
  never runs the USB task, not to stdin. It came about 15 minutes after
  a first boot on a freshly wiped board, a 2068 power cycle and a
  `SAVE "tpi:dir"`. Not reproduced yet.

If it happens, note whether the port opens, try `python3
tools/pico-serial.py watch` (read-only), and record what the 2068 did
beforehand -- before you reset it.

### "First command after boot returns Report J"

You probably forgot to `MQ_READY()` after the main loop drains the
pre-header bytes. See §7 — every Z80 OUT now auto-drops Y to BUSY,
so the Pico has to explicitly re-assert READY before the Z80's next
status poll. This was the v1.5.1 fix.

### "Some commands work, then a later one hangs in SEND_MSG"

Almost certainly: `SEND_MSG` (or one of its `SEND_MSG2` /
`ListMenu` / `SEND_MSG_PROMPT_YN` cousins) is asserting READY before
its first body byte is in the TX FIFO. The Z80 reads `0x00` from the
empty FIFO and either treats it as a real `0x00` (often a string
terminator) or as Report J.

Fix pattern: header bytes → `MQ_READY()` → body loop. Never
`MQ_READY()` → wrt header.

### "Out of memory at boot when loading `dev_tspico`"

You uploaded `dev_tspico.py` instead of `dev_tspico.mpy`. The parser
runs out trying to ingest the text. Build the `.mpy` and upload that.

### "I deleted the dev override but it's still loading"

Both `dev_tspico.py` *and* `dev_tspico.mpy` exist on the Pico. Delete
both. Same for `dev_extcmd.{py,mpy}`.

### "Everything imports fine in REPL but `TS2068_IO()` is broken in
weird ways"

Check whether you accidentally created a `/TS/` folder on the Pico.
If yes, delete it (§5 — the shadowing trap).

---

## 12. Where to look next

- The current open design questions: [`OPEN_QUESTIONS.md`](OPEN_QUESTIONS.md).
- The 2026-09-30 assumption audit, and which of its items are still
  open: [`AUDIT-2026-09-30.md`](AUDIT-2026-09-30.md). Read its Status
  section first — most items are fixed and merged, and it names the one
  branch still waiting on a hardware run.
- The protocol v2 sketch: [`PROTOCOL_V2_PROPOSAL.md`](PROTOCOL_V2_PROPOSAL.md).
  Read this when thinking about a non-incremental change to the wire
  protocol.
- The Z80-side perspective on TPI: [`GUSTAVO_PROTOCOL.md`](GUSTAVO_PROTOCOL.md).
- The instruction-by-instruction Pico view: [`PROTOCOL.md`](PROTOCOL.md).
- The code itself, symbol by symbol, firmware and ROM: the programmer's
  reference in [`reference/`](reference/README.md). Start with its
  [overview](reference/overview.md); CI keeps it in step with the sources.
- Why the code looks the way it does:
  [`DUAL_PORT_DEVELOPMENT.md`](DUAL_PORT_DEVELOPMENT.md).
- For writing user-extensible commands:
  [`EXTCMD_PROTOCOL.md`](EXTCMD_PROTOCOL.md).
- For everything Claude-related (workflows, conventions, debugging
  heuristics): `CLAUDE.md` at the repo root.

Welcome to the project.
