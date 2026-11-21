# A cartridge in the 2068's dock with the TS-Pico fitted (proposal)

Status: proposal, 2026-11-21; the PicoCart's bus behavior added the same
day. Firmware written the same day (host tests pass). On a v3 card the
same day, test steps 2 and 4 passed: the dock reads the empty bus with the
mode on and the TS-Pico's slot with it off, and the PicoCart's LROS and
AROS images, its menu and SD card loads with it fitted all work. That run
found one bug, fixed: after a restart in the mode, `CODE 0,2` swapped the
mode for itself. On a v2 board the same day, the same steps passed too.
There the 2068 may show black and white bars for a moment at switch-on,
while the TS-Pico holds it in reset, before the copyright message. Step 5
passed on v2: ZX Spectrum mode works after `CODE 2,0`. The PicoCart's
white LED flickers while the dock is paged in (`OUT 244,3`) and stops at
`OUT 244,0`, presumably its dock-read activity light; ZX48 wasn't
affected. Where the firmware differs from the first draft below,
"Firmware changes" says so.

We have always told owners that a cartridge in the 2068's own DOCK slot
won't work while the TS-Pico is plugged in. That has never been tested.
An RP2350-based dock cartridge for the 2068, the PicoCart, now exists, and owners will
want to use it with the TS-Pico. This proposal gives the TS-Pico a
**cartridge dock** mode: it stops answering dock reads and leaves the dock
to the cartridge, while it keeps serving the boot ROM, the SD card and
everything else.

## Why it doesn't work today

The 2068 chooses, chunk by chunk, what the Z80 sees: HOME, the EXROM or
the DOCK (port F4h, the HSR, and FFh bit 7). On a read of a chunk banked to
the DOCK the SCLD pulls /ROSCS low. That line reaches both the dock
connector and the rear expansion bus, so a cartridge in the dock and the
TS-Pico both see the read, and both answer: two drivers on D0–D7.

/BE doesn't help. The TS-Pico pulls it to switch off the 2068's own memory
on the HOME and EXROM reads it serves; it doesn't switch off a cartridge,
and the TS-Pico doesn't pull it for dock reads anyway (the 2068 has no dock
memory of its own to silence). The clash happens on every boot, because the
2068 ROM reads the dock at reset to look for an LROS cartridge, and the
TS-Pico always serves a dock: flash slot 0, the Spectrum ROM, unless the
user picks another.

The HOME and EXROM side is not a problem for a stock Timex cartridge: it
answers /ROSCS only, so it stays off the bus when the TS-Pico serves the
boot ROM.

## The 2068 PicoCart

The RP2350 cartridge is the 2068 PicoCart (rev 0.1/0.2). Its designer's
notes, from the schematic netlist and firmware, confirmed unless marked:

- **It drives D0–D7 only on a dock read.** U2, a 74LVC245A, is enabled by
  `ROSCS_n OR MREQ_n OR BUS_OFF` (U3, a 74LVC1G332), and its direction
  follows /RD. Nothing else gates it: not A13–A15, /EXROM, /BE or /IORQ.
  It never drives on I/O cycles, writes or HOME reads, and the buffer lets
  go within nanoseconds of /RD, /MREQ or /ROSCS rising.
- **It drives no other line.** /BE goes to an unfitted 0 Ω link (R10);
  /RESET, /WAIT, /INT, /NMI, /BUSRQ and /ROMCS aren't wired. It doesn't
  snoop ports or bank on its own. Its menu, Z80 code on the 2068, writes
  F4h, FFh and FEh itself, as any program does.
- **It answers every dock chunk**, $FF where its 64K image has no data. A
  stock cartridge answers only where its ROM is. With the TS-Pico off the
  dock, that's the dock as the 2068 sees it, so it changes nothing here.
- **It keeps RAM chunks and a write mailbox at BFFFh** for its menu. The
  TS-Pico doesn't store dock writes with the dock off (v3), and has no
  chip enabled to take them (v2).
- **It's on the bus 10 ms after the dock's 5 V is steady** (above 4.4 V).
  Without a TS-Pico, the ROM's first dock read came 1.79 s after that.
  The v3 card holds /RESET for 100 ms after the 2068's power comes up,
  so there the cartridge is ready before the Z80 starts; on v2, which
  doesn't hold /RESET, it's ready long before the ROM's dock check
  *(inferred)*.
- **Its menu has a "no cartridge" entry** that keeps it off the bus
  (BUS_OFF high) until the next power cycle. So for a session, the user can
  leave it fitted and use a TS-Pico dock slot instead, as long as they
  turn the TS-Pico's dock back on after choosing it.
- **Its menu and AROS carts run on top of HOME**, the TS-Pico ROM's font at
  3D00h, and restart with `JP 0` into it.

So it behaves like a Timex cartridge that answers /ROSCS: this proposal
covers it. One point is still open. It doesn't look at /EXROM, so it
would answer an EXROM read if the 2068 pulled /ROSCS low for one. The
TS-Pico's own v2 path says it doesn't. `set_ctrl` serves the boot slot's
EXROM on the ROSCS-high branch, and if ROSCS went low on EXROM reads,
ROM 2.5's EXROM in chunks 0–1 would come from the dock slot instead, and
ROM 2.5 wouldn't run on v2 *(inferred from the v2 path; checked in test
step 4)*.

## Both boards can let the dock go without a hardware change

### v2: a dock setting that enables neither chip

On v2 a dock read (ROSCS low) does one thing in `set_ctrl`
([pio.md](reference/firmware/pio.md#set_ctrl), instructions 9–11): it
drives bits 2–3 of `ROM_SM` onto the two chip enables, GPIO 19 (U10, the
flash) and GPIO 20 (U13, the SRAM), active low. /BE and A14_L stay high.
Today bits 2–3 are 01 (SRAM) or 10 (flash). **11 enables neither chip**,
so the Pico's memory stays off the bus and the cartridge answers. Nothing
else on the board drives D0–D7 on a memory read as far as the reference
shows: U6 only buffers the port 0Eh/0Fh path (hardware.md, GPIO 12)
*(inferred from the reference; to be confirmed on hardware)*.

So v2 needs no PIO change: `map_slots` puts `rom_sm | 12` to the `ROM`
state machine while the dock is off. `sel_bank` keeps driving A15–A18 on
dock reads, which is harmless with both chips disabled.

On v2 the value 3 can't just be stored as a "dock MEM" in `ROM_SM`, because
on v3 MEM 3 already means a slot on the SD card (`MEM_SD`). The off state
is its own setting (below); only `board_v2.map_slots` turns it into the
11 pattern.

### v3: the switch already exists

`tsbus.dock(False)` ([tsbus.md](reference/firmware/tsbus.md)) stops
serving the chunks the bank registers map to the DOCK: `chunk_target`
sends them to `tail`, so the card never asks for U3 and never drives MD.
Dock reads never pulled /BE on v3 (`path_d`), so with DOCK serving off the
card is off the bus for dock chunks. Dock writes are only stored while DOCK
serving is on, so the card ignores the cartridge's writes too. Today
`tsbus.dock(False)` is used only for the moment a new dock image is copied
in (`map_slots`, `load_dock`). In cartridge dock mode `start_memory` would
skip `load_dock` and leave DOCK serving off, which also frees the 64K dock
copy's work at boot.

## What the user sees

### The command

`tpi:dock` already takes `CODE mem,page`. Add one code:

| Command | Does |
|---|---|
| `SAVE "tpi:dock" CODE 0,3` | **new:** the dock belongs to a cartridge in the 2068's dock slot. The TS-Pico stops answering dock reads, now and at every switch-on |
| `SAVE "tpi:dock" CODE 1,m` / `2,m` (and `3,m` on v3) | as today, and also ends cartridge dock mode |
| `SAVE "tpi:dock" CODE 0,0` | as today; in cartridge dock mode it says `DOCK is the cartridge slot` |
| `SAVE "tpi:dock" CODE 0,2` | swaps with the previous setting, as today, so it toggles between a TS-Pico slot and the cartridge, also after a restart in the mode |

The message when it turns on: `DOCK is the cartridge slot` / `Restart to
run the cartridge`. When a slot turns it off again, the second line warns:
`Take the cartridge out first`. The firmware can't tell whether a
cartridge is fitted, so the warning is all it can do.

### The setting

The mode has to survive a restart: the 2068 ROM looks for an LROS cartridge
right after a reset, and the user will usually fit the cartridge with the
power off. So it's a `config.ini` key, written by the command:

| Key | Values | Default |
|---|---|---|
| `DOCK_CART` | `true`: the dock is the 2068's own dock slot; `false`: the TS-Pico serves `DCK_SLOT` | `false` |

`DCK_SLOT` and the dock bits of `ROM_SM` are left alone, so turning the
mode off brings back the slot the user had.

### What isn't available in cartridge dock mode

- **ZX Spectrum mode.** `tpi:zx48` runs the Spectrum ROM from the
  TS-Pico's dock. It refuses: `The dock is the cartridge slot` /
  `Use tpi:dock CODE 2,0 first`.
- **`tpi:dock` with a DCK file**, and anything else that maps a TS-Pico
  slot into the dock, ends the mode (with the warning above).
- **The ROM and cartridge updaters** (`romupdate.tap`, `dckupdate.tap`)
  write the flash through the dock mapping from Z80 code. They need the
  TS-Pico's dock, so the cartridge has to come out first. `BLKRCV` refuses
  in cartridge dock mode with the same two lines as `tpi:zx48`.
- **TS-Pico storage from inside the cartridge.** An LROS cartridge
  replaces chunk 0, so the TS-Pico ROM isn't running under it. This is
  already true of DCK files in the TS-Pico's own dock; storage there needs a
  driver in the cartridge, as Charlie Day's Leap cartridges do.

Everything that doesn't use the dock keeps working: the boot ROM, `LOAD`
and `SAVE` to the SD card, the disk verbs, the printer, and on v3 the
modem, speech, the Kempston port and the Megabank.

## Firmware changes

1. `LOAD_CONFIG`: read `DOCK_CART` (a bool; anything else falls back to
   `false` and is written back, as the other keys do).
2. `MEMDOCK`: `CODE 0,3` sets `TSP.dock_cart`, saves `config.ini`, calls
   `board.dock_cart(True)`. A slot code clears it and calls
   `board.dock_cart(False)` before `map_slots`. `CODE 0,0` reports it.
3. `board_v2`: `dock_cart(on)` keeps a flag and re-puts the `ROM` word;
   `map_slots` and `start_memory` put `rom_sm | 12` while it's set.
4. `board_v3`: `dock_cart(on)` is `tsbus.dock(not on)` (with
   `load_dock` first when turning it off); `start_memory` and `map_slots`
   leave DOCK serving off while it's set.
5. `ZX48` refuses in cartridge dock mode, and so does `BLKRCV` on v2. On
   the v3 card `BLKRCV` writes the slot file itself, with no dock, so it
   goes through; its loader closes the file before offering to dock the
   new cartridge, and answering Y there ends the mode (with the warning),
   so the manual says to answer N.
6. `tpi:info` (the status screen) shows the dock as `cart`.
7. The reference chapters for each of these, the user manual's dock
   section (chapter 8) and the quick reference.

No ROM change is expected: ROM 2.5's boot reads the dock as the stock ROM
does, and holding **D** to skip the cartridge should work the same with a
real cartridge *(inferred; checked in the tests)*.

## Testing

1. **Host tests:** `config.ini` parsing for `DOCK_CART`; `MEMDOCK`'s
   codes and messages; the v2 word (`rom_sm | 12`).
2. **The TS-Pico is off the bus (no cartridge).** With the mode on, PEEK
   the dock from BASIC one high chunk at a time (`OUT 244,16: PRINT PEEK
   32768: OUT 244,0` for chunk 4, as the v3 bring-up did), and chunks 0–1
   with the Leap `dockprobe` cartridge's method. With no cartridge fitted
   the bus floats, so the reads should no longer match the TS-Pico slot's
   contents. A logic analyzer on D0–D7 and /ROSCS shows it directly. v2 and
   v3.
3. **A stock Timex cartridge** in the 2068's dock, mode on: it boots (LROS)
   or runs from BASIC (AROS); **D** skips it; `LOAD` from the SD card still
   works afterwards.
4. **The PicoCart**, the same steps, on v2 and v3, with an LROS image, an
   AROS image and its menu. Then the EXROM point: with the PicoCart fitted
   and on the bus, run something that pages the EXROM in and reads it
   (ROM 2.5's own `tpi:` commands do, in chunks 0–1, and on v3 the Leap
   languages page it in at 8000h and above). A logic analyzer on /ROSCS,
   /EXROM and U2's /OE settles it directly.
5. **Back again:** cartridge out, `tpi:dock CODE 2,0`, ZX Spectrum mode
   works; the mode survives a power cycle, and `CODE 0,2` toggles.

Until step 2 has passed, owners should keep being told not to fit a
cartridge with the TS-Pico plugged in: with today's firmware both drive the
data bus on every boot.

## Open questions

1. **/ROSCS on EXROM reads.** The PicoCart doesn't gate on /EXROM (see
   "The 2068 PicoCart"). The v2 path says /ROSCS is high on EXROM reads;
   test step 4 confirms it. If it turns out wrong, the fix belongs on the
   cartridge (/EXROM into U3), not in the TS-Pico.
2. **The key's name**, and whether `CODE 0,3` or a word form
   (`tpi:dock cart`) reads better in the manual. `tpi:modem` already takes
   words.
3. **Whether the emulator bridge** (`tools/emu`, ZEsarUX) should model the
   mode, so a cartridge `.dck` loaded into the emulator's own dock can be
   tried with the TS-Pico firmware behind it.
