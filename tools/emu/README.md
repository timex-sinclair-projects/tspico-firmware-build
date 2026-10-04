# TS-2068 + TS-Pico with no hardware (issue #35)

ZEsarUX emulates the TS-2068 running the TS-Pico ROM (`src/rom/TSPICO-21.ROM`).
Every Z80 access to ports 0Eh/0Fh goes over a socket to `pico_host.py`, which
runs the **real firmware**: `TS.tspico.TS2068_IO()`,
its own main loop, unmodified. A host folder stands in for the Pico's flash
and the SD card. You type BASIC through ZEsarUX's remote protocol (ZRCP), read
the screen, and save screenshots.

```
 ZEsarUX (TS-2068, TSPICO-21.ROM)          pico_host.py (CPython)
 Z80 OUT/IN (0Eh), IN/OUT (0Fh)  ─socket─▶  BusModel  ─▶  TS2068_IO()  (src/TS)
 ZRCP :10000  ◀── session.py: type, read the screen, screenshots
                                            /tmp/tspico-root/{config.ini, assets, TMP, sd/...}
```

## What it's good for, and what it isn't

- **Good for:** whether the ROM and the firmware agree. That covers command flows, messages and
  reports, menus and prompts, LOAD/SAVE/printer end to end, real screenshots, and ROM
  changes tried without an EPROM or a flash slot.
- **Not for timing.** Every port access is a socket round trip and nothing runs against the
  bus's real clock. A FIFO running dry or overflowing because the Pico was late can't
  happen here, and the DMA paths aren't used (`rp2.DMA` is absent, so the firmware takes its
  polling fallbacks). Bugs like "TX ran dry" or "Partial pre-header" need the hardware.

The protocol between them is [`docs/EMULATOR_BRIDGE.md`](../../docs/EMULATOR_BRIDGE.md): two-byte
frames over TCP `127.0.0.1:2068` or a Unix socket. An emulator implements that and gets a TS-Pico.

## The standalone `pico_host`

`tools/emu/build_standalone.sh` (PyInstaller) makes `pico_host` one executable with the firmware,
its files and a starter card inside: no Python or checkout needed. The `Standalone pico_host`
workflow builds it for macOS (Apple Silicon), Linux and Windows on every change to the firmware,
runs `--selftest` on each (boot, then answer HELLO over TCP), and attaches the three to each
release. On first run it makes `~/TS-Pico-emulator/` (the Pico's flash; the card is its `sd/`).

```bash
pico_host                       # listens on 127.0.0.1:2068 and /tmp/tspico_bridge.sock
pico_host --root DIR --quiet    # another folder, no telemetry
pico_host --selftest            # boot, answer HELLO, exit 0
```

## Setup

1. **Build ZEsarUX with a TS-Pico**, from the fork
   [timex-sinclair-projects/zesarux-tspico](https://github.com/timex-sinclair-projects/zesarux-tspico)
   (branch `tspico-device`: the 16K EXROM and the bridge, version 1):

   ```bash
   git clone https://github.com/timex-sinclair-projects/zesarux-tspico.git
   cd zesarux-tspico/src && ./configure && make
   ```

   Point `$ZESARUX` at the `zesarux` binary it makes. On macOS, copy it out of `src/` first:
   run from there, it takes `src/` for an app bundle and can't find its ROMs. Without
   `$ZESARUX`, `session.py` looks for the lab build in
   `~/Documents/github/zesarux-tspico-lab/work/zesarux-tspico`.
2. **Python 3.10 or later.** Nothing to install. `pico_host.py` supplies its own stand-ins for
   MicroPython's `rp2`, `machine`, `utime`, `micropython` and the SD driver.

## Use

```bash
python3 tools/emu/smoke.py          # the end-to-end check: CAT, LOAD, SAVE, tpi:info,
                                    # the virtual printer, the tpi:cd menu (~2 min)
```

```python
import sys; sys.path.insert(0, "tools/emu")
import session as S
with S.Session(sd="/path/to/a/card/folder") as s:       # default: the repo's "SD card"
    print(s.run(S.CAT))                                  # type CAT, wait for the report
    s.run(S.SAVE, '"tpi:info"')
    s.screenshot("/tmp/info.bmp")
    s.run(S.SAVE, '"tpi:cd"', until="quit?")             # a menu: wait for its prompt...
    s.cmd("send-keys-ascii 120 48")                      # ...and press 0
```

- **Lines:** `run()` takes BASIC tokens (`S.SAVE`, `S.LOAD`, `S.CAT`, …) and text. It types
  placeholders, then writes the tokenised line into the edit line, which is more reliable
  than typing keywords over ZRCP.
- **Files:** the firmware's output goes to `/tmp/pico_host.out` (telemetry on), and its card
  to `/tmp/tspico-root/sd`.
- **Options:** `TSPICO_HOST=dist/pico_host` runs the standalone build instead of the script.
  `TSPICO_TRACE=1` prints every frame (status reads only when they change).
- **Making TAPs:** `S.basic_tap(name, lines)` builds a TAP holding a BASIC program.

## The pieces

| File | What |
|---|---|
| `pico_host.py` | The firmware on the host. `BusModel` stands in for TS_IO_DUAL: 9-bit RX words (bit 8 = a port-0Fh write), the status byte set by the firmware's `exec("mov(y, …)")`, BUSY after each Z80 write, a 4-deep TX FIFO, and an empty FIFO reading as 00h. `HostFS` maps the Pico's paths into a folder. MicroPython-isms are kept too: `bytearray += str`, `const`, and `sys.implementation` reporting 1.29. |
| `session.py` | Starts the host, then ZEsarUX, and drives ZRCP. |
| `smoke.py` | The end-to-end check. |
| `build_standalone.sh` | The standalone `pico_host` (PyInstaller). |
| `manual_screens.py` | The user manual's 2068 screen pictures, captured. |

The original exploration, notes and probe scripts are in the lab
(`~/Documents/github/zesarux-tspico-lab`, `NOTES.md`).
