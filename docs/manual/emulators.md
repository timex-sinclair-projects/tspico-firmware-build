# Testing TS-Pico Programs in an Emulator

### ZEsarUX and Fuse with the real TS-Pico firmware — for TS-Pico 2.2

> **About this guide.** You can write and test software for the TS-Pico without the hardware.
> `pico_host` runs the real TS-Pico firmware, unmodified, on your computer, with a folder
> standing in for the SD card. ZEsarUX and Fuse connect to it, and their TS-2068 has a
> TS-Pico. `CAT`, `LOAD "tpi:…"`, `SAVE`, `OPEN #`, `LPRINT` and the `tpi:` commands all
> behave as they do on the real machine. They aren't imitations: the firmware answering is
> the same code that runs on the Pico.
>
> This guide is for people writing programs for the TS-Pico, in BASIC or machine code. The
> [User Manual](user-manual.md) covers the commands themselves; the
> [Programmer's Manual](programmers-manual.md) covers talking to the TS-Pico from machine code.

---

## Contents

1. What You Need
2. Setting Up
3. A First Session
4. The Everyday Loop
5. Watching the TS-Pico's Side
6. Debugging Z80 Code
7. Automated Tests
8. What an Emulator Won't Show You
9. Gotchas

---

## 1. What You Need

| Piece | Where to get it |
|---|---|
| `pico_host` | Every [TS-Pico firmware release](https://github.com/timex-sinclair-projects/tspico-firmware-build/releases/latest) has `pico_host-macos-arm64.zip`, `pico_host-windows-x86_64.zip` and `pico_host-linux-x86_64.zip`. No Python needed. |
| The TS-Pico ROM | [`src/rom/`](https://github.com/timex-sinclair-projects/tspico-firmware-build/tree/main/src/rom) in the firmware repository: `TSPICO-23.ROM` for ROM 2.3. It's 32K: a 16K HOME ROM and a 16K EXROM. |
| An emulator with the TS-Pico | **ZEsarUX:** [zesarux-tspico](https://github.com/timex-sinclair-projects/zesarux-tspico/releases/latest) for macOS (signed), Windows and Linux. **Fuse:** [fuse-for-macos-tspico](https://github.com/timex-sinclair-projects/fuse-for-macos-tspico/releases/latest) for macOS (signed), [fuse-tspico](https://github.com/timex-sinclair-projects/fuse-tspico/releases/latest) for Windows. |

**Which emulator?** Both run the same firmware, so either will do for most work.

- **ZEsarUX** has a remote-control protocol (ZRCP) that a script can drive: type BASIC, read
  the screen as text, set breakpoints, read and write memory. Choose it for automated tests
  (section 7).
- **Fuse** has a good built-in debugger, with breakpoints on port accesses, and it starts
  LROS cartridges (`.dck`) the way a TS-2068 does. ZEsarUX loads a cartridge's memory but
  doesn't run its autostart.

The emulators and `pico_host` talk over TCP on `127.0.0.1:2068` by default. The protocol is
[EMULATOR_BRIDGE.md](../EMULATOR_BRIDGE.md), if you want to add the TS-Pico to another
emulator.

---

## 2. Setting Up

### 2.1 `pico_host`

Unzip it and run it from a terminal:

```
pico_host
```

It prints the firmware version and where it keeps the Pico's flash and the SD card, then
waits for an emulator:

```
[pico_host] TS-Pico firmware 1a2b3c4 (v2.2.1); flash and card in ~/TS-Pico-emulator
[pico_host] listening on tcp 127.0.0.1:2068
```

- **The SD card is `~/TS-Pico-emulator/sd/`** (on Windows, in your user folder). On the first
  run it gets a starter card: a `TAP` folder and the `help` files.
- **macOS:** the `pico_host` in firmware releases from 2.2.1 on is signed and notarized. The
  first time it runs, macOS checks that online.
- **Options:** `--root FOLDER` keeps the flash and card somewhere else, so you can keep one
  per project. `--quiet` hides the firmware's telemetry (section 5). `--tcp HOST:PORT`
  listens elsewhere.
- **From the source:** in a checkout of the firmware repository,
  `python3 tools/emu/pico_host.py` does the same with Python 3.10 or later. It runs the
  firmware in `src/` as it is, so it's how you test your own changes to the firmware.

Leave it running. One emulator connects at a time.

### 2.2 ZEsarUX

Start it as a TS-2068, on the TS-Pico ROM:

```
zesarux --machine TS2068 --romfile /path/to/TSPICO-23.ROM
```

- **macOS:** the app is **ZEsarUX TS-Pico**. Pass the options with
  `open -a "ZEsarUX TS-Pico" --args --machine TS2068 --romfile /path/to/TSPICO-23.ROM`, or
  set the machine and the ROM in ZEsarUX's settings and save its configuration.
- **Windows:** run `zesarux.exe` with the same options, from the folder you unzipped.

You should see three copyright lines, the last one the TS-Pico's. With only two, ZEsarUX is
running a stock ROM: check `--romfile`. ZEsarUX connects to `pico_host` at the first access
to the TS-Pico's ports, and `pico_host` prints `emulator connected`.

To use another address, set the environment variable `TSPICO_BRIDGE` to `tcp:HOST:PORT`, or,
on macOS and Linux, `unix:PATH` (`pico_host` also listens on `/tmp/tspico_bridge.sock`).

### 2.3 Fuse

Fuse takes the ROM as two 16K halves:

```
head -c 16384 TSPICO-23.ROM > tspico-home.rom
tail -c 16384 TSPICO-23.ROM > tspico-exrom.rom
```

(On Windows, any tool that can split a file at 16384 bytes will do.)

- **Fuse TS-Pico for macOS:** choose the two halves in Preferences > ROMs as the TS2068's
  ROMs, choose **TS-Pico (TS 2068)** in Preferences > Peripherals, then the TS 2068 machine.
- **Fuse for Windows, or built from fuse-tspico:**

  ```
  fuse --machine ts2068 --rom-ts2068-0 tspico-home.rom --rom-ts2068-1 tspico-exrom.rom --tspico
  ```

  `--tspico` is also the **TS-Pico interface** checkbox in Options > Peripherals > General.
  `--tspico-bridge tcp:HOST:PORT` sets the address.

With no `pico_host` running, both emulators carry on as if no TS-Pico were plugged in: the
TS-Pico commands end with a report instead of hanging. Start `pico_host`, then reset the
emulated machine, and it connects.

---

## 3. A First Session

Type `CAT`. You get the starter card's listing, from the folder on your computer:

```
Path:/TAP
SD: 240 MB; free …
File Name
```

Now put a TAP in the card. Copy any TS-2068 program into `~/TS-Pico-emulator/sd/TAP/`, say
`hello.tap`, and on the 2068:

```
LOAD "tpi:hello.tap"
LOAD ""
```

The first line mounts the file; the second loads its first program, as `LOAD ""` does from a
mounted tape on the real TS-Pico. `SAVE "test"` saves into a TAP on the card, and you can see
it on your computer straight away.

Everything else in the [User Manual](user-manual.md) works the same way: folders
(`SAVE "tpi:cd"`), the disk commands, `f:` files, channels, the printer (its output lands
in the card's `VLPRINT` and `VSCREEN` folders).

---

## 4. The Everyday Loop

The card is a folder on your computer, so the loop is short:

1. **Build straight into the card.** Point your assembler or BASIC tool at
   `~/TS-Pico-emulator/sd/TAP/`. Most can write a TAP (sjasmplus, pasmo, z88dk; zmakebas
   for BASIC). There's nothing to copy.
2. **Load it by name.** `LOAD "tpi:myprog.tap"` then `LOAD ""`. When a name isn't in the
   Pico's folder listing, the firmware reads the folder again before giving up, so a file you
   just built is found.
3. **Check what it wrote.** Files your program saves, prints or writes with `OPEN #` are on
   your computer as soon as they're written. Compare them with what you expected, in a hex
   viewer or a script.
4. **Start again cleanly when you need to.** Each `--root` folder is a separate Pico. Delete
   it, or start `pico_host` with a fresh `--root`, for a card in a known state.

**A test card.** Keep the files a test needs in a folder of their own, and start `pico_host`
with `--root` pointing at a copy of it, so every run starts from the same card.

---

## 5. Watching the TS-Pico's Side

The terminal running `pico_host` shows what the firmware is doing. That's something the
hardware only shows through a USB serial cable.

- **Telemetry** is on unless you pass `--quiet`. Every command prints its trace:

  ```
  [TLM … ] PROCESS_CMD enter: load_cmd=1 cmd_len=17 cmd=b'D\r\x00tpi:hello.tap7'
  [TLM … ] PROCESS_CMD parsed: cmd_exec='TPI:HELLO.TAP' rest_cmd='hello.tap'
  [TLM … ] MOUNT_FILE enter: f_name='/sd/TAP/hello.tap' remounting=False
  ```

  If your program sends a command the TS-Pico doesn't expect, this is where you see what
  arrived.
- **Every byte on the bus:** set `TSPICO_TRACE=1` in `pico_host`'s environment and it prints
  every frame between the emulator and the firmware: each `OUT`, each `IN`, and the status
  reads when they change. Use it when your machine code talks to ports 0Eh and 0Fh directly
  ([Programmer's Manual](programmers-manual.md), Part 1) and something goes wrong.
- **When the emulator disconnects,** `pico_host` prints how many times the Z80 read port 0Eh
  with nothing waiting ("underruns"). On the real board that byte reads as 00h too. A
  non-zero count usually means your code read before the TS-Pico said it was ready.

---

## 6. Debugging Z80 Code

Both emulators have a debugger: breakpoints, single steps, registers and memory.

**Fuse.** The debugger is in the menus, under Machine > Debugger. Commands worth knowing:

| Command | What it does |
|---|---|
| `break 0x8000` | stop when the CPU reaches 8000h |
| `break port read 0x0f` | stop on every read of the TS-Pico's status port (matched on the low byte) |
| `break port write 0x0e` | stop on every byte your code sends the TS-Pico |
| `break write 0x5c00` | stop when memory at 5C00h is written |
| `set 0x9c40 0x00` | poke a byte |
| `[23610]` in an expression | the byte at 23610 (`ERR_NR`) |

Breaking on ports 0Eh and 0Fh shows each step of a conversation with the TS-Pico. Look at
`pico_host`'s terminal at the same moment to see the firmware's side.

**ZEsarUX.** Its debugger is in the menu (F5), and everything is also available over ZRCP
(section 7). Breakpoint conditions use names such as `PC`, `MWA` (memory write address),
`MRA`, `PWA` (port write address) and `PRA`. A write breakpoint over a range you expect to
stay untouched, such as `MWA>=8000h and MWA<=BFFFh`, is a quick way to catch code writing
where it shouldn't.

**Cartridges.** To test a `.dck` the way a TS-2068 starts it, use Fuse: it runs the LROS
autostart. ZEsarUX loads the cartridge's memory but starts in BASIC.

---

## 7. Automated Tests

An emulator can run your tests without you: type the commands, wait, read the screen, check
the card. That's how the firmware's own emulator tests work, and the same tools serve your
programs.

### 7.1 ZEsarUX and ZRCP

Start ZEsarUX with `--enable-remoteprotocol` (it listens on port 10000;
`--remoteprotocol-port` changes that). For a test, `--vo null --ao null` runs it with no window
or sound. ZRCP is line-based text over TCP: send a command and a newline, and read up to the
next `command>` prompt. The commands you'll use most:

| Command | Use |
|---|---|
| `get-ocr` | the screen, as text |
| `save-screen file.bmp` / `file.scr` | a screenshot, or the raw 6912-byte screen |
| `read-memory ADDR LEN` / `write-memory ADDR BYTES` | memory, as hex / bytes in decimal |
| `get-registers` / `set-register PC=8000h` | registers |
| `enter-cpu-step` / `cpu-step` / `exit-cpu-step` | stop the CPU, one instruction, carry on |
| `set-breakpoint N CONDITION` / `enable-breakpoints` | breakpoints (section 6) |
| `smartload FILE` | load a tape, snapshot or cartridge by its type |
| `reset-cpu` | restart the 2068 |

**Typing BASIC.** Keying in TS-2068 keywords over ZRCP is fiddly. What works reliably: type a
placeholder line of the right length with `send-keys-ascii`, write the tokenised line into
the edit line with `write-memory` (its address is in the system variable `E_LINE`, 23641),
then press ENTER. Before ENTER, poke 255 into `ERR_NR` (23610); a report then shows up
there as anything but 255.

**A ready-made driver.** In a checkout of the firmware repository,
[`tools/emu/session.py`](../../tools/emu/session.py) does all of this. It starts `pico_host`
and ZEsarUX, types BASIC lines given as tokens and text, waits for the report, reads the
screen and takes screenshots:

```python
import sys; sys.path.insert(0, "tools/emu")
import session as S
with S.Session(sd="/path/to/my/test/card") as s:
    s.run(S.LOAD, '"tpi:mytest.tap"')
    t = s.run(S.LOAD, '""')
    assert "0 OK" in t
    s.screenshot("/tmp/after.bmp")
```

`$ZESARUX` names the ZEsarUX binary and `$TSPICO_HOST` the standalone `pico_host`, if you
don't want the script. [`tools/emu/smoke.py`](../../tools/emu/smoke.py) is a complete
example: CAT, LOAD, SAVE, `tpi:info`, the printer and a menu, with ten checks.

### 7.2 Fuse

Fuse has no remote control, but two of its options are enough for many tests:

- **`--debugger-command`** runs debugger commands from the start. A breakpoint's commands can
  "press" keys the way the ROM's keyboard interrupt does: put the character in `LAST_K`
  (23560) and set bit 5 of `FLAGS` (23611), one key at a time once the ROM has taken the last.
  (Fuse's own auto-load doesn't run with a custom ROM.)
- **A headless Fuse** (built `--with-null-ui --enable-automation`) runs for a set number of
  frames (`--automation-frames`) and saves the final screen (`--automation-capture-screen`).

The test program itself can come from the TS-Pico. With nothing mounted, a bare `LOAD ""`
loads the firmware's `/assets/nofile.tap`. Put your test program there in a test card's
flash folder, and typing `LOAD ""` runs it.
[`tools/emu/fuse_smoke.py`](../../tools/emu/fuse_smoke.py) does exactly this, and has the
debugger print `ERR_NR` and memory at the end, so the script can check them.

---

## 8. What an Emulator Won't Show You

The firmware is real, but the bus between it and the Z80 isn't, and the Pico's other hardware
isn't there at all. Test on a real TS-Pico before you call something finished:

- **Timing.** Every port access is a round trip to `pico_host`, and nothing runs against the
  2068's bus clock. On the real board the TS-Pico has to keep up with the Z80, through
  4-byte FIFOs and DMA. In the emulator it always does. Code that reads too soon, or a
  transfer that's too fast for the board, can pass here and fail on the hardware.
- **DMA.** The firmware's DMA transfers are replaced by its slower polling versions.
- **ROM switching, the flash ROM slots and the dock.** The emulator's ROM comes from its own
  file, and the hardware these commands drive isn't there: `tpi:boot`, writing a ROM slot
  and dock images don't do what they do on the board. `tpi:zx48` switches the firmware to
  Spectrum mode while the emulator goes on running the TS-2068 ROM, so the two stop
  understanding each other; restart `pico_host` to get back.
- **A firmware crash.** As on the Pico, the firmware restarts its service loop after an
  error, and the 2068's next command gets "T TS-Pico reset, try again". After three in a
  minute it stops, and `pico_host` prints `firmware stopped`. Start it again.
- **The SD card hardware.** The card is a folder: no card errors, no slow cards, no
  removing it mid-write.

---

## 9. Gotchas

- **ZRCP addresses are decimal; registers and breakpoints are hex.** `read-memory 8000 8`
  reads address 8000 decimal (1F40h). To read 8000h, use `read-memory 32768 8`.
  `set-register PC=8000h` and breakpoint conditions take hex with an `h` suffix.
- **ZEsarUX saves a snapshot when it's told to exit** (`exit-emulator`, or quitting), as
  `zesarux_autosave.zsf` beside the program, and starts from it next time. A test that quit
  ZEsarUX in the middle of something can leave every later run starting there, often with a
  blank screen. Delete the file, or end ZEsarUX in tests by stopping the process.
- **`reset-cpu`, not `hard-reset-cpu`,** to restart a running 2068 over ZRCP.
- **macOS, ZEsarUX built from source:** run it from outside its `src/` folder. Started inside,
  it takes `src/` for an app bundle, can't find its ROMs, and the 2068 never reaches the
  editor.
- **One emulator per `pico_host`.** A second one waits until the first disconnects. For tests
  in parallel, run a `pico_host` per emulator with its own `--root` and `--tcp` port.
- **Old processes.** A ZEsarUX or `pico_host` left over from an earlier run holds its port,
  and a new one can't start. Stop it first.
