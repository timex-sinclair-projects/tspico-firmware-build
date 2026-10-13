# Future features

Ideas that are worth doing but not scheduled: each says what it would give
users, what the hardware already allows, and what to settle before starting.
When one is taken up it gets a proposal (`docs/v3-*-proposal.md`) and leaves
this list.

## The v3 card as a cassette player and recorder

*Added 2026-10-12.*

**The hardware is already there.** The v3 card has two plain GPIOs to the
2068's tape signals on the rear connector:

- **TAPE_OUT (GP23) → EAR.** The R2/R3 divider brings it down to about 0.6 V,
  a cassette player's level. Whatever the card drives here, the 2068 hears
  as a tape playing.
- **SPK/TAP → TAPE_IN (GP22),** through the control transceiver (5 V to
  3.3 V). The card can hear what the 2068 sends to tape.

A PIO state machine can drive or time either pin, with no CPU and exact
timing. PIO2 has three spare state machines, and core 1 isn't involved.

**What it would give users:**

1. **A virtual cassette player (the main one).** The TS-Pico's fast LOAD works
   because the ROM intercepts LOAD and the Pico hands it bytes, so it only
   helps programs that use the ROM's loader. Many Spectrum games, and some
   2068 ones, load with their own routines: turbo loaders, Speedlock and other
   copy protection, multi-load levels. The manual's "If a game won't load" is
   about these. Played as audio into EAR, they load as they would from a
   cassette.
   - TAP files hold standard blocks only, which is enough for the ROM loaders.
   - Protected games come as **TZX**, which describes every pulse of a custom
     loader (pure tones, pulse sequences, pauses, "stop the tape" blocks
     for multi-loads). TZX playback is the compatibility win.
   - The ROM side exists: `SAVE "tpi:tape"` sends plain LOAD to the cassette
     routines, and in ZX48 mode the Spectrum ROM reads EAR as well.
   - It plays at tape speed (about 5 minutes for a 48K game), so it's for
     what can't load the fast way, not a replacement for it.
2. **A virtual cassette recorder.** The PIO times the edges on TAPE_IN, and
   core 0 decodes standard blocks into a TAP file. This catches programs that
   save to tape themselves (save-games, utilities, copiers), which the ROM
   never sees.

**How it might work:** pulse lengths in a ring that DMA feeds to the PIO
state machine on GP23, refilled by core 0 from the SD card.
- **TZX timings** are in 3.5 MHz T-states. Playing them in real time suits
  both the 2068's 3.528 MHz and the Spectrum ROM; tape loaders tolerate far
  more than that 0.8 % difference.
- **Starting and stopping the tape** could be by command:
  1. `SAVE "tpi:tape"`;
  2. `LOAD "tpi:game.tzx"`;
  3. `SAVE "tpi:play"`;
  4. `LOAD ""` on the 2068;
  5. a stop command between multi-load levels.

  Later, possibly automatically: the card serves the ROM, so it could see the
  2068 enter the ROM's tape loader and start or pause the tape itself, as
  emulators do.

**To settle first:**

1. **A hardware check on a 2068.**
   - **EAR:** the card toggles GP23 once a second while BASIC runs
     `10 PRINT AT 0,0; IN 254: GO TO 10`; bit 6 (64) should follow.
   - **SPK/TAP:** `BEEP`, or `OUT 254` with the tape bit, while GP22 is
     watched.

   This shows whether R2/R3 are fitted and whether the rear connector's EAR
   pin reaches the 2068's tape input.
2. **Scope:** TAP playback first (small, proves the path), then TZX; the
   recorder after, or not at all.
3. **Control:** commands first; whether automatic start and stop is worth it
   later.

## Dropped, unless it becomes a reported problem

- **Blocking reads through /WAIT** (port plan, phase 6; dropped 2026-10-12).
  The card can hold the Z80 with /WAIT, so an empty FIFO could stall the read
  instead of returning 00h, which the ROM reports as "J". The protocol is fast
  and reliable without it. It would change the protocol contract
  (`docs/PROTOCOL_V2_PROPOSAL.md`) and need a ROM revision.

## Elsewhere

- **AY sound** at $FFFD/$BFFD, with PWM audio: phase 7 of the v3 port plan
  (tspico-hardware `docs/v3-firmware-port-plan.md`).
- **The OLED status display** and **the Kempston joystick** wait on hardware:
  [v3-oled-proposal.md](v3-oled-proposal.md), and the `v3-kempston` branch.
- **The ESP32 as a WiFi file server:** a different role for the modem module,
  noted in [v3-modem-proposal.md](v3-modem-proposal.md) ("Not in this
  proposal").
