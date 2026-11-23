# A TS2068 emulated on the v3 card, shown by the PicoVideo (proposal)

Status: proposal, 2026-11-23. Nothing is built yet. Nothing here has been
tried on hardware; what comes from the code or the schematics says so, and
the rest is marked as inferred or unverified.

This is an alternate firmware for the v3 card. The v3 runs the whole
TS2068 (Z80, memory, SCLD, AY) as an emulator. A PicoVideo draws its
screen, fed over a USB cable from the v3. The real 2068 is only the
keyboard: its Z80 runs a short loop from a PicoCart in the dock that reads
the keys and hands them to the v3.

The idea of emulating the 2068 on the Pico and using the 2068 as the
keyboard is Jay Carlson's.

Two ways of getting the screen to the PicoVideo are described below: a
USB cable (the plan) and the real Z80 copying the screen into real RAM,
for the PicoVideo to snoop as it does now (the fallback, needing no
PicoVideo change).

## Why

- **The real 2068's RAM and video don't matter any more.** The loop reads
  the keyboard without using RAM, and the picture comes from the
  PicoVideo, not from the 2068's video output. A 2068 with failing RAM or
  a dead video output can still be a keyboard (with one catch, under
  "The keyboard loop").
- **Things a real Z80 can't do:** save states, a faster-than-real-time
  mode, a debugger, and the Megabank or other memory without the board.
  None of these are in the first phases; they are why the emulator is worth
  having once it runs.
- **Most of the code already exists.** The TS2068 machine layer (SCLD,
  HOME/DOCK/EXROM paging, AY, 60 Hz frame timing) is in esp32-2068
  (`machine/`, lifted from Fuse), with Fuse's Z80 core (`z80/`). The
  TS-Pico side is this repo's MicroPython firmware, which esp32-2068
  already runs next to an emulator on the P4's other core.

## The pieces

```
 2068 keyboard ──► real Z80 ──► OUT to a v3 port ──┐
 (SCLD port FEh)   (LROS loop                      │
                    on the PicoCart)               ▼
                                     ┌─────────── v3 card (RP2350B) ───────────┐
                                     │ core 1: emulator (C)                    │
                                     │   Z80 + TS2068 machine, keys from the   │
                                     │   loop, dirty screen bytes, USB host    │
                                     │ core 0: TS-Pico MicroPython firmware    │
                                     │   tpi:, SD, WiFi, modem, through queues │
                                     └──────────────┬──────────────────────────┘
                                                    │ USB (v3 = host)
                                                    ▼
                                     PicoVideo, link-mode firmware ──► VGA
```

### Why not draw the screen on the v3

The v3 has no free pins for video. The RP2350's HSTX (DVI) pins are
GP12–GP19. On the v3, GP12 is WAIT_REQ and GP13–GP18 are bus inputs
(`src/boards/TSPICO_V3/tspico_v3_pins.h`). The spare pads (GP36, GP40)
are too few for VGA. The PicoVideo already draws every SCLD mode and its
own extra modes, so it is the screen.

### Getting the screen to the PicoVideo

The PicoVideo builds its picture by snooping the 2068's bus. Its core 0
watches memory writes into the display files and writes to ports FEh/FFh,
F4h, ULA+ and its own registers (PicoVideo `firmware/coreB/busMain.c`).
The emulated Z80's writes never reach the bus, so the PicoVideo needs
another way to get them. There are three:

| | USB link (the plan) | Z80 relay (the fallback) | A wire |
|---|---|---|---|
| Change to the PicoVideo | link-mode firmware | none | firmware, and a wire soldered on |
| Full redraws a second | 60, every mode *(inferred)* | about 24 (INIR), maybe about 48 (PUSH) | 60 |
| Needs the 2068's RAM | only to start (see the keyboard loop) | yes | only to start |
| The 2068's own video output | shows nothing useful | shows the screen too | shows nothing useful |
| The v3 on the PC while running | no | yes | yes |
| New v3 bus work | none beyond the keyboard OUTs | answering INs at speed with no CPU | a PIO link |

The wire (a spare v3 pad, GP36 or GP40, to a spare PicoVideo pin, running
a PIO link) is fast but means modifying both boards, so it isn't
described further. The other two are.

### Why USB

USB needs only a cable, and has the bandwidth. Full-speed USB is 12 Mbit/s,
and an RP2040 handles roughly 1 MB/s of bulk transfers in practice
*(inferred, measured in phase 2)*. Every byte of the standard screen
(6,912 bytes) at 60 frames a second is about 415 KB/s. The 12K hi-res and
dual-screen modes at 60 are about 737 KB/s. The link sends only the bytes
that changed, so a typical frame is far smaller than that.

## The v3 firmware

### Core 1: the emulator

- **The Z80 and the machine** come from esp32-2068 (`z80/`, `machine/`),
  built with the Pico SDK. The machine layer's frame timing came from
  Fuse's Spectrum code and esp32-2068's PLAN.md says it must be checked;
  the same check applies here.
- **Memory in SRAM.** HOME 16K, EXROM 16K (the TS-Pico ROM's), RAM 48K and
  the dock 64K: about 144K of the 520K. Not in PSRAM: a Z80 memory access
  happens about a million times a second and PSRAM through the cache is
  too slow and uneven for that *(inferred)*. Emulated Megabank memory
  could live in PSRAM later.
- **No frame buffer.** The v3 never draws pixels. It keeps a bitmap of
  which display-file bytes changed this frame (DF1 4000h–5AFFh, DF2
  6000h–7AFFh) and sends them at the end of the frame.
- **The PicoVideo's own registers are emulated on the v3.** A program that
  writes ULA+ or reads the PicoVideo's version register must get an answer
  without waiting for USB. The v3 keeps a copy of the PicoVideo's state,
  answers reads from it and forwards the writes. esp32-2068 and
  ts2068-esp32 keep a local copy of the TS-Pico's state the same way.
- **The core 1 rules still hold.** Nothing on core 1 may run from flash
  (`tools/check-core1-ram.py`, #306), and no DMA may touch PSRAM (#411).
  The Z80 core, the machine and the USB host stack all have to be placed in
  RAM. The size of TinyUSB's host code in RAM is unmeasured.
- **Speed is expected to be fine** *(inferred)*: fruit-bat's
  pico-zxspectrum runs a 128K Spectrum on the slower RP2040. Fuse's Z80
  core was not written for speed; phase 1 measures it, and Redcode's Z80
  core (fruit-bat's choice) is the fallback.

### Core 0: the TS-Pico firmware

The TS-Pico MicroPython firmware runs as it does now, with an emulated bus
in place of tsbus: the emulator puts the emulated Z80's accesses to the
TS-Pico ports on a queue, and the firmware's answers come back on another.
That is esp32-2068's `p4bridge` design, so `tpi:`, the SD card, WiFi and
the modem keep working without a rewrite. MicroPython's heap stays in
PSRAM (#410).

MicroPython's own USB (REPL, the drive) has to be off in this build,
because core 1's C code owns USB as the host.

### Sound

The emulated beeper and AY play through the v3's AUDIO_L/AUDIO_R pins
(GP46, GP30), the PIO2 PWM path speech already uses (#286). The real
2068's AY could play the emulated AY's register writes instead; that's an
option for later, not the plan.

## The USB link

- **The v3 is the host.** It runs TinyUSB in host mode on the RP2350's
  native USB. The PicoVideo is the device, with one vendor-class bulk
  endpoint.
- **What goes over it:** runs of display-file bytes (address, length,
  bytes); writes to FEh (the border), FFh (the screen mode), F4h, ULA+
  and the PicoVideo's registers; and an end-of-frame marker, so the
  PicoVideo can change the picture between frames and not mid-frame.
  The format is still to be written.
- **Power** *(from the schematics, unverified on hardware)*. Neither
  board puts power on VBUS. The v3's USB-C VBUS only feeds its
  diode-OR with the edge connector (tspico-hardware
  `docs/v3-architecture.md`), and the Pico module on the PicoVideo
  feeds VBUS to VSYS through a diode. With both boards powered from the
  2068, nothing back-feeds. Both sides tell their USB controller that
  VBUS is present in software, so they enumerate with no VBUS on the
  cable.
- **The cable.** The PicoVideo carries a standard Pico, so the cable is
  USB-C (v3) to micro-USB (PicoVideo).
- **The cost:** while the link is up, the v3 is not on the PC. No REPL,
  no web updater, no USB drive, and `tools/pico-serial.py` can't drive it.
  BOOTSEL flashing still works, because that's the RP2350's boot ROM.
  Debugging is over SWD or a UART on a spare pad.

## The PicoVideo link-mode firmware

Today the PicoVideo's core 0 sits in the timing-critical bus loop and
core 1 draws VGA, so there is no spare CPU for USB. In link mode, core 0
runs TinyUSB's device stack instead of `busMain()`. It writes what comes
in into the same video memory and registers that `busMain()` fills from
the bus now. The renderer (`coreV/`) does not change.

In link mode the PicoVideo ignores the real bus. The keyboard loop's own
I/O never reaches it.

This firmware is a branch of the PicoVideo repository, not this one.

## The keyboard loop

In this firmware the v3 never answers memory reads (it never pulls /BE
low). The 2068 starts from its own HOME and EXROM ROMs. The EXROM's
start-up reads the dock's LROS header and runs the cartridge
(`docs/reference/rom/exrom-driver.md`, EXTINIT), so the loop is an LROS
image on the PicoCart, which already runs LROS images
(`docs/dock-cartridge-proposal.md`).

The loop needs no RAM and no stack. A sketch, untested:

```
        di
top:    ld   b,0FEh          ; first keyboard row
row:    ld   c,0FEh
        in   a,(c)           ; read row B: bits 0-4, 0 = pressed
        ld   c,KEYPORT
        out  (c),a           ; A15-A8 carry B, so the v3 knows the row
        rlc  b
        jr   c,row           ; 8 rows: FE, FD, FB, F7, EF, DF, BF, 7F
        ld   a,14            ; AY register 14: the joystick port
        out  (0F5h),a
        in   a,(0F6h)
        ld   b,0             ; row 0 means "joystick"
        ld   c,KEYPORT
        out  (c),a
        ld   b,0             ; 256 DJNZs, about 1 ms, before the next scan
wait:   djnz wait
        jr   top
```

- **The v3 reads the OUTs.** It sees the whole address through its
  multiplexed buffers, so it gets the row from A15–A8 and the keys from
  D0–D7. tsbus's I/O write path already does this for the TS-Pico ports.
  KEYPORT is still to be chosen. 0Eh is the obvious candidate: this
  firmware doesn't serve the TS-Pico's own ports on the real bus.
- **About 1,000 scans a second.** The DJNZ wait (256 × 13 T-states) keeps
  the stream of OUTs small: nine per scan, about 9,000 a second, cheap
  enough to collect with a PIO and DMA. A longer wait needs a second
  counter, still in registers.
  The emulator reads the latest value of each row when the emulated ROM
  scans the keyboard.
- **The 2068's reset button resets the real Z80.** The loop starts again
  from the ROM. The v3 sees it start (a message the loop sends first) and
  can reset the emulated machine too.
- **The catch with bad RAM** *(inferred)*: HOME's start-up uses RAM (the
  stack and the system variables) before the EXROM runs the LROS, so a
  2068 with badly failing RAM may never reach the loop. The loop itself
  needs none.

## The fallback: the Z80 relays the screen

Here there is no USB link. The real Z80 copies the emulated screen into
the 2068's own RAM, and the PicoVideo, running its normal firmware,
snoops those writes exactly as it does a real program's. The same loop
reads the keyboard.

What this buys: the PicoVideo needs no change, the 2068's own video
output shows the screen too (so the PicoVideo is optional), and the v3's
USB stays free for the PC. What it costs: speed, working RAM in the 2068,
and new bus work on the v3.

### The loop

The v3 keeps a queue of what changed since the last frame. The loop asks
for it through a port, LINKPORT, and copies it. A sketch, untested; the
keyboard part is the loop under "The keyboard loop", run once per pass
without its DJNZ wait (the copying is the wait):

```
next:   ld   c,LINKPORT
        in   l,(c)           ; address low
        in   h,(c)           ; address high; below 40h = a command
        ld   a,h
        cp   40h
        jr   c,command
        in   b,(c)           ; how many bytes (0 = 256)
        inir                 ; B bytes from LINKPORT to (HL) onward
        jr   next
command:
        or   a
        jr   z,keys          ; H = 0: nothing left this frame
        in   a,(c)           ; H = 1: a port write, L = the port
        ld   c,l
        out  (c),a           ; FEh (border), FFh (mode), ULA+, the
        jr   next            ; PicoVideo's registers
keys:   ...                  ; the keyboard scan, then jr next
```

`INIR` puts B on A15–A8, so LINKPORT must be decoded on A7–A0 only.
`OUT (C),A` with C = FEh also writes the beeper and MIC bits; the v3
sends FEh writes with those bits as the emulated machine has them,
or clear *(to be decided)*. The PicoVideo sees F4h writes too, so the
relay must not send any that would page the display files away from
where it expects them.

### Speed

INIR is 21 T-states a byte: about 168K bytes a second at 3.528 MHz,
roughly 24 full redraws of the standard screen a second against the
2068's 60, and about 13 of the 12K hi-res screen. Most programs change
far less than the whole screen a frame, so most run at full speed; one
that redraws everything every frame drops frames *(inferred)*.

A faster version: the v3 answers memory reads in an otherwise unused
area with a stream of `LD HL,nn` / `PUSH HL` pairs, with SP set into the
display file. That's 21 T-states per two bytes, about twice INIR's speed.
But the Z80 then runs code the v3 serves, which on the v3 is core 1's
memory-read path (tsbus, /BE), the work this design wants off core 1.

### What the v3 has to do

Answer an IN on LINKPORT every 21 T-states, about 6 µs, with no CPU: a
PIO fed by DMA from the queue. The v3's current IN path goes through a
PIO2 interrupt and the CPU (#254, #255); at 168K INs a second that would
take too much of core 1 from the emulator *(inferred)*, so this is new PIO
work. WAIT_REQ (GP12) can stretch a cycle if the PIO falls behind.

### Where it fits

It's the fallback if the USB link doesn't work out (the bandwidth, the
power with nothing on VBUS, or TinyUSB's host code not fitting in RAM
beside the emulator). It also suits an owner who has no PicoVideo: the
2068's own video output shows the emulated screen. Phase 2 tries the USB
link first; if it fails, phase 2 becomes this.

## Where the code lives

Not in this repository. Fuse's code is GPL-2 and this repository is MIT,
so the emulator firmware goes in a new GPL repository, as esp32-2068 and
ts2068-esp32 do. It takes this repository as a submodule, for the TS-Pico
firmware and the v3 board layer. Nothing in this repository changes until
the v3 board layer needs to, and then that change updates
`docs/reference/` as usual.

## Phases

1. **The emulator alone on the v3.** The machine and the Z80 built with
   the Pico SDK, on core 1, running the stock ROM, with no bus, no USB and
   no screen. Check the speed, and the RAM used, and compare its frames and
   traces with Fuse using esp32-2068's `tools/host/` comparisons.
   **Done when** the stock ROM reaches BASIC and a test program runs at
   full speed with time to spare.
2. **The link.** v3 as the USB host, PicoVideo link mode, a test pattern
   first, then the emulator's screen. Measure the bandwidth and check the
   power with nothing on VBUS. **Done when** the copyright screen shows on
   VGA and a full-screen redraw every frame doesn't drop frames. If the
   link doesn't work out, this phase becomes the Z80 relay instead, done
   when the copyright screen shows and typical BASIC programs run without
   visible lag.
3. **The keyboard.** The LROS loop on the PicoCart, the v3 collecting the
   OUTs, the emulator's keyboard matrix. **Done when** you can type a BASIC
   program on the 2068 and run it.
4. **The TS-Pico.** The MicroPython firmware on core 0 through the queues,
   booting the TS-Pico ROM. **Done when** `LOAD "tpi:..."` loads a program
   from the SD card.
5. **Sound.** Beeper and AY through AUDIO_L/R.
6. **Living with the PC.** How the v3 chooses between the link and being
   on the PC (an open question below), and a way back to the normal
   firmware.

## Open questions

1. **How the v3 chooses its USB role.** A config.ini key read at boot, a
   key held on the 2068 at power-on, or start as a device and switch to
   host if no PC answers. Two hosts on one cable see nothing and harm
   nothing *(inferred)*, which may make detecting a PicoVideo simple.
2. **KEYPORT.** 0Eh or another port.
3. **Timing.** Whether the emulator paces itself from its own 60 Hz timer
   or from the PicoVideo's frame, and whether the difference shows.
4. **One firmware or two.** A separate firmware is simpler. Building the
   emulator into the normal v3 firmware, as a mode, saves reflashing but
   puts both sets of core 1 code in RAM at once.
5. **Whether the PicoVideo's audio jack has a use** here, for the
   emulated sound.
