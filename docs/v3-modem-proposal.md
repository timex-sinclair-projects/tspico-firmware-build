# Phase 6: the TS2050 modem on the v3 card (proposal)

Phase 6 of the v3 port plan (tspico-hardware `docs/v3-firmware-port-plan.md`)
lists "ESP32-C3: an esptool bridge to install Zimodem through the card's
USB, then the 8251 emulation at $73/$77". This note covers the 8251: the
v3 card answering the 2068 as a **Timex TS2050 modem**, with the card's
ESP32-C3 running Zimodem as the line. The installer comes last (step 6).

Decisions taken with David on 2026-10-12 are marked **(decided)**.

**Status: done, 2026-10-12.** All six steps are merged and tested on proto1
with unmodified MTERM/T; see [Progress](#progress) at the end. The user
side is in the v3 manual's Appendix F, and the code in the reference
(`firmware/tsbus.md`, `firmware/board.md`).

## What the 2068's software expects

Found by disassembling MTERM (Westridge, 1984) and the MTERM II cartridge
(Zebra Systems, 1986), both in the archive.org Timex Sinclair software
archive, and from the BASIC dialers and the 2068 BBS program on
timexsinclair.com:

- **Two ports.** $73 (115) is the 8251's data register, $77 (119) its
  command (OUT) and status (IN). Nothing else is used.
- **The 8251 is set up the datasheet's way:** `OUT 77h` 00h three times,
  40h (internal reset), then the mode byte (MTERM: 7Bh, ×64, 7 bits, even
  parity, 1 stop), then a command byte (MTERM's idle one is 15h: TxEN, RxE,
  ER).
- **Everything is polled.** Status bit 0 (TxRDY) before each `OUT 73h`,
  bit 1 (RxRDY) before each `IN 73h`. No interrupts, no flow control.
- **Dialing is pulse dialing on DTR** (command bit 1): MTERM toggles it once
  per pulse, digit 0 = 10 pulses, with software delays; hanging up clears
  DTR and RTS. The 2050 is a 300-baud Bell 103 modem with no Hayes
  commands.
- **DSR (status bit 7) is carrier.** MTERM waits for it after dialing and
  drops the session when it goes; the BBS checks it before every byte; the
  BASIC dialers compare the whole status with `IN 119=133` (DSR + TxEMPTY +
  TxRDY), so a stray RxRDY or error bit reads as "no carrier".

The TS-2050-Wifi project (timex-sinclair-projects) emulates the 8251 on a
Pico W with its own AT commands; it never sets DSR and has no pulse
decoder, so it doesn't run MTERM's dialer. Nothing from it is reused.

## What the card has

- The ESP32-C3-WROOM-02 on UART0, **GPIO 44 (TX) and 45 (RX)**, with EN on
  the XL9555's port 0 bit 3 (`WIFI_EN`) and IO9 (download mode) on bit 4
  (`WIFI_DL`). No DTR, DCD or RTS/CTS lines are wired.
- **Zimodem 4.0.3** is on David's proto1 (checked 2026-10-12: boot banner,
  then `AT`/`ATI` answered at **115200** 8N1). Its build is tspico-hardware
  `firmware/zimodem/`; the bring-up `esp_bridge.uf2` flashes it.
- Core 1 already answers INs from SRAM (`handle_in`, about 600 ns to the
  data) and sees every OUT (`io_snoop`). The UART's registers are on the
  APB bridge, which **core 1 must never touch** (#254: APB stalls up to
  4 µs during flash writes). DMA and PIO are on AHB.

## Proposal

### The 8251, in core 1

`handle_in` answers $73 and $77 as it answers $0E/$0F (U1 reads the port,
`io_drive` puts the reply on MD, U3 on), from state kept in SRAM:

| | |
|---|---|
| **IN 77h** | the status byte: TxRDY = room in the transmit ring; RxRDY = a received character is waiting (paced, below); TxEMPTY = transmit ring empty; PE/OE/FE = 0; BRKDET = 0; DSR = the modem's "carrier" (below) |
| **IN 73h** | the waiting character, masked to the mode's length (7 bits: bit 7 = 0); clears RxRDY |
| **OUT 73h** | the character into the transmit ring (masked to the length), if TxEN |
| **OUT 77h** | the 8251 state machine: after a reset (power-up, or command bit 6) the next write is the mode byte, then every write is a command; three 00h writes are absorbed as the datasheet's reset preamble. The command's DTR and RTS bits go to the modem model |

Parity and stop bits aren't put on a wire: the link to Zimodem is 8N1, so the
mode byte only sets the character length. A real 8251 sets OE when a
character arrives before the last was read; pacing (below) means that
never happens here.

**The UART by DMA, not by core 1.** One DMA channel copies Zimodem's bytes
from UART0's data register into a 4 KB SRAM ring, endlessly, paced by the
UART's RX DREQ. Core 1 reads where it has got to from the channel's write
address, as it already reads the bus log's. Another channel drains the
transmit ring into the UART, started by core 1 when the ring has bytes and
the channel is idle. Neither core 0 nor a Python loop is in the path, so a
LOAD, a flash write or a busy command never loses a byte. Core 1 sends XOFF
to Zimodem when the receive ring is three-quarters full and XON when it has
drained (Zimodem `ATF1`/`AT&K4`).

**Pacing (decided: 300 baud, configurable).** A received character becomes
visible to the 2068 (RxRDY) no sooner than one character time after the
last: 33 ms at 300 baud, so MTERM sees what a real 2050 would send.
`config.ini`'s `MODEM_BAUD` (300 default; 1200, 2400 … up to "0" for as
fast as it is read) changes it. Transmit is not paced: the 2068 can't send
faster than it polls TxRDY, and the ring absorbs it.

### The modem model (decided: both modes, switchable)

**2050 mode** (the default) makes Zimodem look like a 2050 to unmodified
software:
- **Dialing.** Core 1 times the DTR edges in the command writes (the cycle
  counter): a train of short breaks is one digit, a longer gap ends it,
  and a gap of about 2 s after the last digit ends the number. The
  thresholds come from timing MTERM's own pulses on the card (step 3);
  Zimodem's pulse decoder, for comparison, takes 15–60 ms pulses and
  225–350 ms gaps. The
  number goes to Zimodem as `ATDT<number>`, and Zimodem's **phonebook**
  (`ATP`) maps it to a host:port. A number that isn't in the phonebook
  gives NO CARRIER.
- **Carrier.** The card puts Zimodem in numeric results (`ATV0`, `ATE0`) at
  power-up and reads the result lines itself: `1` (CONNECT) sets DSR, `3`
  (NO CARRIER) clears it (the Hayes codes; Zimodem's own to be checked on
  the card). Result lines never reach the 2068; while
  connected, everything is data.
- **Hanging up.** DTR cleared while connected: the card sends Zimodem's
  escape (`+++` with its guard times) and `ATH`, and clears DSR.

**Hayes mode** passes every byte both ways, with DSR held on, so a terminal
program on the 2068 (MTERM in terminal mode, or a BASIC loop) talks to
Zimodem directly: WiFi setup (`AT+CONFIG`), the phonebook (`ATP`),
`ATDT"host:port"`. `tpi:modem` switches between the modes.

Zimodem's own settings stay Zimodem's: the card only sends `ATE0V0` (and
`ATF1`) when it powers the module in 2050 mode, and `ATE1V1` on a switch to
Hayes mode, never `AT&W`, so the saved profile is the user's.

### Power (decided: on demand)

The ESP32 draws up to about 350 mA in WiFi bursts from the 2068's 5 V rail,
so it is **off at boot**. It is powered when a program first resets the
8251 (the 00h/00h/00h/40h preamble, or a mode byte) or on `tpi:modem on`,
and off again on `tpi:modem off` or after 10 minutes with no connection and
no 8251 traffic. While it boots (about a second) TxRDY stays clear, so
nothing is lost.

**The XL9555's port 0 is shared.** `ExpanderLED` rewrites the whole byte on
every LED edge (100 Hz), which would switch the ESP off. Step 1 makes one
shadow of port 0 in `board_v3.py`, with the LED, `WIFI_EN`/`WIFI_DL` and
(#262, proto2) `SD_PWR_EN` each changing only their own bits, and the
read-modify-write safe against the LED's timer callback. #262 needs the
same shadow.

### Commands and settings

- `SAVE "tpi:modem"`: show the state (off, on, 2050 or Hayes, connected,
  bytes each way).
- `SAVE "tpi:modem on"`, `"tpi:modem off"`, `"tpi:modem hayes"`,
  `"tpi:modem 2050"`.
- `config.ini`: `MODEM_BAUD` (300), `MODEM_MODE` ("2050"), `MODEM_IDLE_MIN`
  (10).

On v2 the board has no modem: `tpi:modem` answers "No modem on this board"
(Report F), and $73/$77 stay unanswered as now.

### Not in this proposal

- **Installing Zimodem from the TS-Pico's USB** was step 6 (see
  [Progress](#progress)); before it, a blank module was flashed with the
  bring-up `esp_bridge.uf2` and `firmware/zimodem/`.
- **The ESP32 as a WiFi file server** (the `claude/esp32-file-server` sketch
  in tspico-hardware): a different role for the module, later.
- **Tone dialing, answer mode, the 8251's sync modes and break.**

## Order of work

1. **Port 0 shared.** The shadow in `board_v3.py`; `board.modem_power(on)`
   and `board.modem_download(on)`; the LED through the shadow. Host test:
   the LED tick never changes another bit. On the card: the LED dims as
   before, and the ESP stays powered through it.
2. **The 8251 in `tsbus`.** Ports $73/$77, the mode/command state machine,
   the rings and the two DMA channels, pacing, Hayes mode only. The 8251
   logic in a plain C file with no hardware in it, so a host test can
   compile it with `cc` and drive it with the MTERM sequences (reset,
   mode, commands, the TxRDY/RxRDY loops, pacing). On the card: a BASIC
   loop (`OUT 115`, `IN 119`, `IN 115`) talks to Zimodem: `AT` gives `OK`.
3. **2050 mode.** The pulse decoder, the result-line filter, DSR, hang-up.
   Host test: MTERM's dial pulses for a number give `ATDT` and that number.
   On the card: MTERM II dials a phonebook entry and reaches a telnet
   host; the BASIC dialer's `IN 119=133`.
4. **`tpi:modem`, `config.ini`, power on demand, the idle timeout.**
5. **Docs:** the reference, the user manual (a chapter or an Appendix F
   section: setting up WiFi and the phonebook, MTERM II), the help files.
6. **The installer:** Zimodem onto a blank module through the TS-Pico's
   USB, from the web updater or a `tools/` script.

Each step is its own PR, tested on proto1, and updates the reference.

## Open questions

1. **What RTS does on a 2050** (originate/answer?). MTERM toggles it around
   the carrier wait. The card ignores it until a schematic or a test says
   otherwise.
2. **Whether 300-baud pacing is enough for MTERM's scrolling**, and whether
   faster settings work with MTERM II. Testing will tell.
3. **A telnet host for testing.** Any public telnet BBS works; a local one
   (a Python script on the Mac) gives repeatable tests.
4. **Whether Specterm-64, ZX-Term*80 and the 2068 BBS program** use the
   same ports and bits. The BBS's listing has one `IN A,(116)`, either a
   typo or a sign the 2050 decodes only part of the address.

## Progress

| Step | PR | What landed |
|---|---|---|
| Proposal | #264 | this document |
| Notes | #265 | [ts2050-software-notes.md](ts2050-software-notes.md): MTERM, MTERM II, the BASIC dialers, Zimodem |
| 1 | #266 | the port-0 shadow; `board.modem_power`, `board.modem_download` |
| 2 | #267 | the 8251 at 73h/77h in `tsbus` (`usart8251.c`, host-tested), bridged to Zimodem over UART0 by DMA; Hayes mode |
| 3 | #268 | 2050 mode (`modem2050.c`): pulse dialing to `ATD`, `CONNECT` raises DSR, hang-up both ways |
| 4 | #269 | `tpi:modem`, `MODEM_MODE`/`MODEM_BAUD`/`MODEM_IDLE_MIN`, power on demand |
| 5 | #270, #271 | the manual in two builds; the v3 one's Appendix F, The Modem |
| 6 | #272 | Zimodem 4.0.3 built in CI (`esp32/zimodem/`), published to the updater channels and releases |
| 6 | #273 | `tsbus.esp_relay`: the card's USB joined to the ESP32's ROM loader; `tools/zimodem-install.py` |
| 6 | #274, #275 | the web updater and the Windows exe write Zimodem through the relay (`espflash.js`, `espflash.py`), MD5-checked |

What testing changed from the design above:

- **The 8251 powers up taking commands** (mode 4Fh), not in reset: MTERM
  resets it before the modem is on, and the reset was lost.
- **Core 1 never masks interrupts.** A `cpsid` around the shared state made
  INs late, read as 127 (the © MTERM printed); the state is lock-free now.
- **`NO CARRIER` can arrive mid-line** (after a host's `> `), so it counts
  anywhere it is followed by a line end.
- **After `CONNECT`, data is held 3.5 s.** MTERM misses what comes in while
  it switches screens. Hosts that wait for ENTER before their banner suit it
  best; MTERM's own manual tells users to press ENTER twice.
- **Zimodem gets word results, not numeric:** `ATE0V1X0F1` at off-hook (no
  echo, word results, a short CONNECT, XON/XOFF), read by `modem2050.c`.
- **The dial thresholds:** a break under 200 ms is a pulse, 300 ms of DTR on
  ends a digit, 1.5 s the number (MTERM's own pulses: 58 ms break, 47.5 ms
  make, 832 ms between digits).
- **Power:** the ESP32 is switched on by any OUT to the 8251, and the line
  declared up when Zimodem prints `READY.` (core 1 watches for it; 8 s,
  `MODEM_BOOT_MS`, is the fallback; it was a fixed 2 s until #300); until
  then what the 8251 sends waits in the card's ring and what arrives is
  dropped. A terminal polling
  the status keeps it on; `MODEM_IDLE_MIN` (10) on-hook and unused switches
  it off.
- **`tpi:modem` takes `2050`, `hayes` or `off`** (saved as `MODEM_MODE`);
  there is no separate on/off for the ESP32's power, which is automatic.
- **Core 1 never reads flash:** the modem's strings are non-const (`.data`),
  and nothing compiles to `strlen`/`memcpy`.

Open questions 1 (RTS on a real 2050) and 4 (Specterm-64, ZX-Term*80, the
2068 BBS) are still open.
