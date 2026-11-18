# Phase 6: the status display on the v3 card (proposal)

Phase 6 of the v3 port plan (tspico-hardware `docs/v3-firmware-port-plan.md`)
lists an "OLED status display". This note covers the panel, what it shows,
and when it is drawn.

Decisions taken with David on 2026-10-12 are marked **(decided)**.

**Status: set aside, 2026-10-12, until the board is redone for the SSD1309.**
Writing to the panel is proved (below); the firmware waits for the board,
which fixes the bus and the pins.

## The panel (decided: SSD1309)

A 128 x 64 mono OLED with an **SSD1309** controller on **I2C**, the common
4-pin module (GND VCC SCL SDA): 8 lines of 16 characters in the 8 x 8 font.

proto1 was designed for a Waveshare 1.27" SSD1351 (SPI, color) on J3, a
7-pin header (VCC GND DIN CLK CS DC RST). The board is being redone for
the SSD1309 instead (the hardware thread): it settles the header and its
pin order, the I2C pins, and whether there is a reset line. Until then
the firmware's bus and pins are open; the drivers below need only an I2C
object and the address.

**Proved on proto1 (2026-10-12).** The module was wired to J3 by four
wires: GND to J3 pin 2 and VCC to pin 1 (J3's power pins are the other way
round), SCL to pin 3 (GP43, I2C1's SCL) and SDA to pin 4 (GP42, I2C1's SDA).
It answers at 3Ch on I2C1 at 400 kHz. It ignores horizontal addressing
(`20h 00h`): written as one 1,024-byte stream, every byte lands in page 0.
Written a page at a time (`B0h+p`, `00h`, `10h`, then 128 bytes), the test
pattern is correct and the right way up with `A1h`/`C8h`. A full frame
takes about 30 ms.

## What it shows (decided)

One status screen, seven of the panel's eight lines:

```
TS-Pico 2.3.1
Boot F01  Dock -
SD in  /TAP/GAMES
TAP sinistar.tap
> LOAD "tpi:..."
  OK
Modem connected
```

1. The firmware version.
2. The boot ROM slot and the dock slot, as MEM and slot (`F01`: flash slot 1;
   `S03` SRAM, `D05` SD; `-` for none).
3. The SD card: in or out, and the current folder.
4. The mounted TAP.
5. The last command (`tpi:` or LOAD/SAVE/VERIFY with its name).
6. Its result (OK, or the report it ended with).
7. The modem's state: off, on-hook, dialling, connected (from
   `board.modem_status`).

The eighth line is spare (the slot names, or the modem's number). Long names
are cut to 16 characters, keeping the end (the extension).

## When it is drawn (decided: between commands only)

The display is on core 0, which also runs the protocol, and an I2C frame
blocks it for up to 30 ms. So:

- **The firmware only sets fields** (`display.set("tap", name)`): a
  string compare and a flag, no I/O, safe anywhere, including inside a
  command handler.
- **The idle loop draws.** Where `modem_service` is called now, between
  commands, `display.service()` redraws only the text rows that changed:
  one page (128 bytes, about 3.5 ms at 400 kHz) for a changed line.
  Nothing is drawn while a command
  runs, so a transfer's lines change once it has ended: the command and
  its result appear together. No progress bar.
- **Core 1 never touches it.** The I2C controllers are behind the APB bridge
  (issue #254); only core 0 uses them, as with the expander.

## Burn-in (decided: off after N minutes)

OLEDs wear where pixels stay lit. With no change for `DISPLAY_OFF_MIN`
minutes (default 10), the panel is switched off (`AEh`); the next change
switches it on and redraws it.

## Settings (decided: explicit only)

The display is switched on by name, not found by a probe at boot:

- `config.ini`: `DISPLAY` = `"off"` (the default) or `"ssd1309"`;
  `DISPLAY_OFF_MIN` = 10. A name rather than true/false leaves room for
  another panel later.
- `SAVE "tpi:display ssd1309"` (or `off`) sets and saves it, as
  `tpi:modem` does, and starts or stops the display at once.
- If the panel doesn't answer at 3Ch, the firmware logs it once and runs
  without a display.

On v2 there is no display: `tpi:display` answers "No display on this
board" (Report F), as `tpi:modem` does.

## The code

- `TS/display.py`: the fields, the layout, the dirty rows, `service()`, the
  off timer, and the `SSD1309` driver (`init`, `row(n, text)`,
  `power(on)`): page writes from one 128-byte framebuf, reused for every
  row. No whole-screen framebuffer.
- `board_v3.py`: `display_bus()` gives the I2C object for the redone
  board's pins (and drives a reset line, if it has one, through the port-0
  shadow). `HAS_DISPLAY = True`; v2 `False`.
- `tspico.py`: the `set` calls where the state changes (boot, the mounts,
  `CD`, each command's start and end, the modem poll), the `service()`
  call in the idle loop, the config keys and `tpi:display`.

## Order of work

1. **The driver and the board's part.** `display.py` with the driver and a
   test screen; `board_v3.display_bus`; the config keys. On the card: the
   test screen from the firmware.
2. **The status screen.** The fields, the `set` calls, `service()` in the
   idle loop, the off timer. On the card: LOAD a TAP, change folder, dial
   with MTERM, and watch the lines follow; a command's timing unchanged
   (`TLM` before and after).
3. **`tpi:display`, the reference, the v3 manual.**

Each step is its own PR, tested on proto1, and updates the reference.

## Open questions

1. **The redone board's pins**: the I2C controller and pins, the header's
   pin order (GND VCC SCL SDA lets a module plug straight in), and whether
   the module's reset is wired. Step 1 starts from those.
2. **A screen for errors**: whether an SD error or a Report J should stay on
   screen until the next command, or clear with the next change.
3. **Detection.** The SSD1309 answers on I2C, so it could be found at boot
   instead of named. The decision was "explicit only" while the write-only
   SSD1351 was in the plan; it can be revisited now.
