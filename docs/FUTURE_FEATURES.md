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

## Speech: the 2068 talks

*Added 2026-10-12. David's particular interest.*

Text in, speech out of the card's audio jack (GP30/GP46 PWM, the filter and
mixer, J4), from BASIC.

**From BASIC,** in ways that suit the 2068:
- **A command:** `SAVE "tpi:say HELLO, I AM YOUR TIMEX"`.
- **A channel:** `OPEN #4,"s:"`, then `PRINT #4;"GAME OVER"`. Anything a
  program prints to it is spoken, so existing programs can be made to talk by
  redirecting a stream, as `OPEN #` already does for files and the printer
  (Chapter 6 of the manual).
- **Phonemes for exact control:** a prefix or a second channel that takes
  phoneme codes rather than English, as the speech units of the time did,
  for words the rules get wrong and for pitch and stress.

**How it might work.** Two stages:
1. **Text to phonemes.** The US Naval Research Laboratory's letter-to-sound
   rules (Elovitz et al., 1976) are a US-government report, the classic choice
   for small machines: a few hundred rules, a few KB.
2. **Phonemes to sound.** Three candidates, each with a different character:
   - **A formant synthesiser** (Klatt-style): clear, adjustable pitch and
     speed, small; the robot voice of the period done well.
   - **SAM-style** (Software Automatic Mouth, C64/Atari/Apple, 1982): the
     most "8-bit" voice. Open reconstructions of it exist, but its licence is
     unclear (the original is proprietary), so it needs checking before use.
   - **SP0256-AL2 allophones** (the chip in the Currah µSpeech and many
     period units): the authentic Spectrum-era sound, built from 59
     allophones. It needs either the chip's allophone data, whose licence
     needs checking, or a model of the chip.

Generation runs in C, faster than real time. The whole utterance (about
11 KB a second at 11 kHz, 8-bit) goes into a buffer, and DMA plays it to the
PWM pins in the background. So `tpi:say` returns at once and the 2068 carries
on while the card speaks, and core 1 isn't involved.

**Later, for Spectrum software in ZX48 mode:** Currah µSpeech compatibility.
Its games (Ultimate's among them) speak by reading particular ROM-area
addresses, and the card serves the ROM, so it could see those reads. It's a
separate step, after the native speech works.

**To settle first:**
1. **The audio check** (as for the AY, below): a tone at the jack from each
   channel, and the 2068's BEEP through the mix.
2. **The voice:** formant, SAM-like or SP0256. Prototypes of each are cheap
   enough to listen to side by side.
3. **The interface:** `tpi:say`, an `s:` channel, phoneme input, or all
   three.
4. **Licences** for whatever synthesiser code or data is used.

## Sounds and music from the SD card

*Added 2026-10-12.*

Play sound files from the SD card through the card's audio jack, started
from BASIC: `SAVE "tpi:play boom.wav"` for a sound effect, or music that
plays in the background while a program runs, with a stop command.
Digitised effects, speech recordings and music are things the 2068 can't
make itself, so this is a new tool for 2068 programmers.

**How it might work:** WAV (8- or 16-bit PCM, resampled to the PWM rate) to
start. A small ring that core 0 refills from the SD card, played by DMA to
the PWM pins, the same output path as speech. Compressed formats (ADPCM,
perhaps MP3) are a later question.

**To settle first:**
- **The audio check.**
- **Whether the SD card can be shared** while it streams: the protocol uses
  the same card for LOAD and SAVE, so background music during a LOAD needs
  the reads interleaved, or the file read into RAM first.
- **Formats.**

## An emulated AY at the Spectrum 128's ports

*Added 2026-10-12; was phase 7 of the v3 port plan.*

An AY-3-8910 at $FFFD (register select, and read-back on IN) and $BFFD
(data), synthesised on core 1 and played through the card's PWM audio
(GP30 right, GP46 left) to the 3.5 mm jack.

**Why it's not scheduled.** The 2068 has a real AY at $F5/$F6, so 2068
software doesn't need one. The emulated AY only helps in ZX48 mode, for
Spectrum software that writes to the 128's ports: 48K games and demos with
128-style AY music. True 128K games still won't run, because the 2068 can't
page the 128's memory. It's a narrow audience.

**Cycles are not the obstacle.** A sample (three tone counters, noise,
envelope, mix) is roughly 100-200 cycles, so a 31 kHz stream is about 2-3 %
of core 1 at 250 MHz. Constraints:
- **Small chunks:** the work goes in a few samples per loop pass, since the
  loop drains the OUT and dock-write FIFOs, which fill in about 15-25 µs.
- **RAM only:** the code runs from RAM, without masking interrupts, as the
  modem does.
- **Output by DMA:** a RAM buffer fed by DMA to the PWM pins, so the CPU
  never touches APB.

The register OUTs reach core 1 through io_snoop already; read-back at $FFFD
is one compare in `handle_in`.

**To settle first:** the audio path is untested. It runs PWM, a two-stage RC
filter, an MCP6002 mixer with the 2068's SOUND line, then the jack. The
check: a test tone from each channel at the jack, and the 2068's own BEEP
through the mix. Then measure core 1's headroom with the diag build's
`max_gap`.

## Dropped, unless it becomes a reported problem

- **Blocking reads through /WAIT** (port plan, phase 6; dropped 2026-10-12).
  The card can hold the Z80 with /WAIT, so an empty FIFO could stall the read
  instead of returning 00h, which the ROM reports as "J". The protocol is fast
  and reliable without it. It would change the protocol contract
  (`docs/PROTOCOL_V2_PROPOSAL.md`) and need a ROM revision.

## Elsewhere

- **The OLED status display** and **the Kempston joystick** wait on hardware:
  [v3-oled-proposal.md](v3-oled-proposal.md), and the `v3-kempston` branch.
- **The ESP32 as a WiFi file server:** a different role for the modem module,
  noted in [v3-modem-proposal.md](v3-modem-proposal.md) ("Not in this
  proposal").
