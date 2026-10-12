# Phase 6: the status display on the v3 card (proposal)

Phase 6 of the v3 port plan (tspico-hardware `docs/v3-firmware-port-plan.md`)
lists an "OLED status display". This note covers what it shows, when it is
drawn, and the two panels the firmware drives.

Decisions taken with David on 2026-10-12 are marked **(decided)**.

## The panels (decided: support both)

| | SSD1351 | SSD1309 |
|---|---|---|
| Module | Waveshare 1.27" | generic 1.3"/2.4" 4-pin module |
| Pixels | 128 x 96, 16-bit colour | 128 x 64, mono |
| Text (8 x 8 font) | 12 lines of 16 | 8 lines of 16 |
| Bus | SPI1: SCK GP42, MOSI GP43, CS GP41, DC GP34; reset on the expander's P0.2 (nOLED_RST) | I2C1: SCL GP43, SDA GP42, address 3Ch; no reset line |
| Where | J3, the board's 7-pin header (VCC GND DIN CLK CS DC RST), as designed | J3 by four wires: module GND to J3 pin 2, VCC to pin 1 (J3's power pins are the other way round), SCL to pin 3, SDA to pin 4 |

J3's signal pins are plain GPIOs, so the firmware picks their function: SPI1
for the SSD1351, or I2C1 (GP43 and GP42 are I2C1's SCL and SDA) for the
SSD1309. Only the power pins are fixed.

**Proved on proto1 (2026-10-12), SSD1309.** The module answers at 3Ch on
I2C1 at 400 kHz. It ignores horizontal addressing (`20h 00h`): written as
one 1,024-byte stream, every byte lands in page 0. Written a page at a time
(`B0h+p`, column 0, 128 bytes), the test pattern is correct and the right
way up with `A1h`/`C8h`. A full frame takes about 30 ms. The SSD1351 has
not been tried: no module yet.

## What it shows (decided)

One status screen. On the SSD1309, seven of its eight lines:

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

The SSD1351's four extra lines leave room for the slot names or the modem's
number; the layout is a list of fields, so each panel takes as many as fit.
Long names are cut to 16 characters, keeping the end (the extension).

## When it is drawn (decided: between commands only)

The display is on core 0, which also runs the protocol, and an I2C frame
blocks it for up to 30 ms. So:

- **The firmware only sets fields** (`display.set("tap", name)`): a
  string compare and a flag, no I/O, safe anywhere, including inside a
  command handler.
- **The idle loop draws.** Where `modem_service` is called now, between
  commands, `display.service()` redraws only the text rows that changed:
  one page (128 bytes, about 3.5 ms at 400 kHz) for a changed line on the
  SSD1309, one row window on the SSD1351. Nothing is drawn while a command
  runs, so a transfer's lines change once it has ended: the command and
  its result appear together. No progress bar.
- **Core 1 never touches it.** I2C1 and SPI1 are behind the APB bridge
  (issue #254); only core 0 uses them, as with the expander.

## Burn-in (decided: off after N minutes)

OLEDs wear where pixels stay lit. With no change for `DISPLAY_OFF_MIN`
minutes (default 10), the panel is switched off (`AEh`); the next change
switches it on and redraws it.

## Settings (decided: explicit only)

The SSD1351 is write-only and can't be detected, so the panel is named:

- `config.ini`: `DISPLAY` = `"off"` (the default), `"ssd1309"` or
  `"ssd1351"`; `DISPLAY_OFF_MIN` = 10.
- `SAVE "tpi:display ssd1309"` (or `ssd1351`, `off`) sets and saves it, as
  `tpi:modem` does, and starts or stops the display at once.
- If the named panel doesn't answer (the SSD1309 has no ACK at 3Ch), the
  firmware logs it once and runs without a display.

On v2 there is no display: `tpi:display` answers "No display on this
board" (Report F), as `tpi:modem` does.

## The code

- `TS/display.py`: the fields, the layout, the dirty rows, `service()`, the
  off timer; two small drivers behind one interface (`init`, `row(n,
  text)`, `power(on)`): `SSD1309` (I2C, page writes from a 128-byte
  framebuf per row) and `SSD1351` (SPI, a 128 x 8 RGB565 window per row).
  No whole-screen framebuffer: one row's buffer is reused.
- `board_v3.py`: `display_bus(kind)` gives the I2C1 or SPI1 object and the
  pins; `display_reset(on)` drives nOLED_RST through the port-0 shadow.
  `HAS_DISPLAY = True`; v2 `False`.
- `tspico.py`: the `set` calls where the state changes (boot, the mounts,
  `CD`, each command's start and end, the modem poll), the `service()`
  call in the idle loop, the config keys and `tpi:display`.

## Order of work

1. **Drivers and the board's part.** `display.py` with both drivers and a
   test screen; `board_v3.display_bus`/`display_reset`; the config keys.
   On the card: the SSD1309 shows the test screen from the firmware.
2. **The status screen.** The fields, the `set` calls, `service()` in the
   idle loop, the off timer. On the card: LOAD a TAP, change folder, dial
   with MTERM, and watch the lines follow; a command's timing unchanged
   (`TLM` before and after).
3. **`tpi:display`, the reference, the v3 manual.**

Each step is its own PR, tested on proto1, and updates the reference.

## Open questions

1. **The SSD1351 is untested** until a module is fitted. Its driver follows
   the datasheet's init sequence and is kept small, so the first test is
   short.
2. **Whether the board moves to the SSD1309.** If it does, a 4-pin header in
   the modules' order (GND VCC SCL SDA) lets one plug straight in; that is
   the hardware thread's call.
3. **A screen for errors**: whether an SD error or a Report J should stay on
   screen until the next command, or clear with the next change.
