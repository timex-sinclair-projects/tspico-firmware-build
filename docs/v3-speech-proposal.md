# Speech on the v3 card (proposal)

The v3 card speaks: English from BASIC becomes the voice of a General
Instrument SP0256-AL2, the chip in the Currah µSpeech, Radio Shack's speech
kits and David's Pico Speech Synth 2068 board, out of the card's audio jack.
It began as an entry on the future-features list (2026-10-12).

Decisions taken with David on 2026-10-12 are marked **(decided)**.

**Status (2026-10-12):** built on branch `v3-speech`, everything but the
tests that need the card in a 2068; see [Progress](#progress). The speech
channel (`s:`) was dropped: the ROM can't reach it.

## What the prototypes settled

Three voices were rendered on the Mac and compared by ear: SAM (the 1982
C64/Atari voice), the SP0256-AL2, and a formant synthesizer written for the
comparison.

- **The voice: the SP0256-AL2 (decided),** emulated from its ROM. A first
  SP0256 version strung together recordings of the chip's 64 allophones
  (from cpcwiki, as David's board uses). It popped at the joins, because many
  recordings start or end with a full-scale click. Measured against the ROM,
  the recordings also run about 25 % slow (every allophone 1.25 times the
  ROM's length, as from 8 kHz material labeled 10 kHz), and several are
  mis-cut (PP, GG2, HH1, HH2). Emulated from the ROM, the chip plays a
  sentence as one continuous stream: no joins, 4–5 times fewer large sample
  steps, and the speed of a real AL2 on its 3.12 MHz crystal. "Way better"
  (David).
- **SAM is out:** the only source is a reconstruction of proprietary code with
  no license.
- **The formant voice** worked and could do intonation (questions, and
  "Canadian" uptalk), but the SP0256 is the character wanted. Its code stays
  with the prototypes.

The prototype tools (`sentences.py`, `t2a.py`, `sp0256_rom.cpp`,
`render_rom.py`) are the starting point for the code below.

## Where everything comes from

| Part | Source | Terms |
|---|---|---|
| The AL2's allophone data | `al2.bin`, 2 KB, the chip's ROM ([spatula-city.org/~im14u2c/sp0256-al2](http://spatula-city.org/~im14u2c/sp0256-al2/); bit-reversed relative to MAME's `sp0256-al2.bin`, SHA-1 `e60fcb5f…` once reversed) | Copyright Microchip Technology Inc. In 2007 Microchip's legal department told Joe Zbiciak he may distribute the ROM data "so long as you acknowledge Microchip's ownership of the algorithms". MAME and others ship it with that acknowledgment, and so would we. |
| The chip emulation | MAME's `src/devices/sound/sp0256.cpp` (Joseph Zbiciak, Tim Lindner) | BSD-3-Clause: fine beside the firmware's MIT license. GmEsoft's SP0256/CTS256A emulator is GPL-3, so we don't take code from it. |
| English to phonemes | The US Naval Research Laboratory's letter-to-sound rules (NRL Report 7948, 1976) as John A. Wasser coded them (`english.c`, 1985, CMU AI Repository) | Public domain: a US-government report, and Wasser's own "all public domain and I make no copyright claims on it". |

The acknowledgments go in a `NOTICE` file and the manual. Strictly,
Microchip's 2007 permission was given to Joe Zbiciak. Shipping the ROM with
the acknowledgment is the community norm (MAME and others do), but our own
note from Microchip would make it airtight (open question 1). Recording
David's own chip wouldn't avoid this: the allophones are Microchip's data
however they're captured.

## The design

### Text to allophones (core 0, Python)

As `t2a.py` does:
1. **Numbers to words.**
2. **Words to NRL phonemes** by the rules: Wasser's 354 rules, turned into a
   Python table by a build tool, and his matcher.
3. **An exception dictionary** for the words the rules get wrong (about one in
   ten, by the NRL report's own count). A built-in list, plus `/speech.txt` on
   the Pico's flash, so users can add words (`TIMEX = tAYmEHks`).
4. **Phonemes to AL2 allophones** by context, as the datasheet describes:
   - word-initial and final variants (TT2/TT1, DD2/DD1, DH1/DH2, BB2/BB1);
   - KK1/KK3/KK2 and GG1/GG2/GG3 by the following vowel;
   - the r-colored vowels (AR, OR, XR, YR) and NG before K or G;
   - pauses for spaces and punctuation.

A line of text takes milliseconds, so it can run inside a command.

### The chip (core 1, C, in `tsbus`)

MAME's SP0256 core, unchanged apart from its device wrapper, built into
`tsbus` from RAM like the 8251. It reads from two places:

- **an allophone queue:** core 0 puts a sentence's allophones in, and the
  chip takes the next one when it's ready for it (its LRQ);
- **the ROM:** `al2.bin` at its address, 0x1000, as on the chip.

It produces one 10 kHz sample at a time into a ring, and DMA paced by a
timer plays the ring to the PWM pins: GP30 and GP46, both channels the same.
From there the audio runs through the RC filter and the MCP6002 mixer,
alongside the 2068's own SOUND, to the jack.

Why core 1, and what it costs:
- **Speech goes on while the 2068 does other things,** including TS-Pico
  commands, which keep core 0 busy for long stretches. Core 1 is never busy
  that way.
- **The 2068's own programs can drive it** (port 17, below), so allophones
  arrive by Z80 OUT, which core 1 sees first.
- **Its cost:** the 12-pole filter at 10 kHz is roughly 1–2 % of core 1. It
  works a few samples per pass of the loop, as the AY entry's analysis
  showed it must, and nothing touches APB except the DMA, which is outside
  the IN path.

### From BASIC

- **`SAVE "tpi:say HELLO, I AM YOUR TIMEX"`** speaks a line and returns at
  once. The 2068 carries on while the card talks; a second `tpi:say` queues
  behind the first. `SAVE "tpi:say"` with nothing after it stops speech.
- **Allophones by name,** for exact control: `SAVE "tpi:say [HH1 EH LL OW]"`.
  The square brackets mark allophones rather than English.
- ~~**A speech channel:** `OPEN #4,"s:"`, then `PRINT #4;"GAME OVER"`.~~
  **Dropped (decided):** the ROM's `CH_OPEN_HOOK` claims only `d:` and `f:`
  specs and gives the rest to the stock 2068 code, where `s` is the screen,
  so `OPEN #4,"s:"` never reaches the Pico. It would need a ROM change. The
  firmware side was built and tested, then removed.
- **Waiting for speech to finish:** `IN 37`, bit 7, as on David's board
  (below).

### David's board's ports, for the 2068's own software

David's Pico Speech Synth 2068 takes an allophone number on `OUT 17` and
reports on `IN 37`, bit 7 (LRQ: low, ready for the next). The v3 card
answers both:
- core 1 queues the allophone from the OUT;
- `handle_in` answers IN 37 from the queue's state, one compare, like
  1Fh.

So programs written for his board speak through the TS-Pico. The ports are
on by default, with a `config.ini` key (`SPEECH_PORTS`) to turn them off if
something else on the 2068 uses them. They work in ZX48 mode too, where
`tpi:` commands are limited.

### Settings

- `config.ini`: `SPEECH_VOLUME` (35, %: asked for once the speech was heard),
  `SPEECH_RATE` (100: the chip's speed in %, since the AL2's speed and pitch
  are both its clock; 80 gives the slower, lower voice of the cpcwiki
  recordings), `SPEECH_PORTS` (true).
- On v2 there is no audio output: `tpi:say` answers "No speech on this board"
  (Report F), and ports 17 and 37 stay unanswered.

## Order of work

1. **The audio path.** A tone from each PWM channel at the jack, and the
   2068's BEEP through the mix, on the board in a 2068. Nothing else starts
   until this works.
2. **The chip in `tsbus`:** MAME's core, the allophone queue, the PWM ring and
   its DMA, and `tsbus.say(allophones)`.
   - **Host test:** the same core built with `cc`; a test sentence's samples
     must match a stored hash, made from the prototype's rendering.
   - **On the card:** "HELLO" from the REPL, then the timing (`stats`'
     slowest IN reply unchanged with speech playing).
3. **Text:** the rules table and its build tool, the matcher, numbers, the
   exception dictionary and `/speech.txt`, and `tpi:say` (text and
   `[allophones]`). Host test: known words to known allophones.
4. ~~**The `s:` channel.**~~ Dropped (above).
5. **Ports 17 and 37,** tested with a program written for David's board.
6. **Docs:** the reference, the v3 manual (an appendix, "Speech": `tpi:say`,
   the channel, the ports, the allophone table, adding words), and `NOTICE`
   with the three acknowledgments.

Each step is its own PR, tested on the card, and updates the reference.

## Open questions

1. **Our own permission from Microchip** for the AL2 data, quoting their 2007
   reply to Joe Zbiciak. It isn't needed to start, but it's worth asking before
   a release ships the ROM.
2. **The audio hardware** is untested, and the board is being revised. Step 1
   depends on a board in a 2068 with the audio parts fitted.
3. **Intonation.** The AL2 has none, and neither does the real chip. The
   chip's clock could be nudged per phrase to raise the pitch for a question,
   but speed would change with it. Leave it out unless asked for.
4. **The Currah µSpeech** (Spectrum games in ZX48 mode). Its interface needs
   checking against its documentation, and it's a later step.
5. ~~**Port numbers 17 and 37**~~ (settled from the board's schematic): its
   74HC138 decodes A4, A5 and /RD with A7 low, so the board answers OUTs to
   10h-1Fh and 50h-5Fh and INs from 20h-2Fh and 60h-6Fh. Programs use 17 and
   37, so the card decodes exactly those, leaving 1Fh (Kempston) alone. IN 37
   reads FFh busy, 7Fh ready: bit 7 is the board's /LRQ on D7, and the
   rest copy the 2068's floating bus.

## Progress

On branch `v3-speech` (2026-10-12):

| Step | State |
|---|---|
| 1. The audio path | **Done** on board 2, on USB power with no 2068: tones on each channel at the jack, and the ROM speech played by DMA at 10 kHz |
| 2. The chip in `tsbus` | **Done.** `sp0256.c` (MAME's core via `tools/sp0256-port.py`), checked bit for bit against MAME's C++ (`sp0256_hosttest.py`). Core 1 runs it into a ring that two DMA channels play to GP46/GP30. Core 1 never reads flash: the tables had to be placed in RAM by name, because GCC put them in `.rodata` even without `const`. On board 2: 80,157 samples for two sentences, exactly MAME's count, never late |
| 3. Text and `tpi:say` | **Done.** `speech.py`, the rules generated from Wasser's `english.c`, `/speech.txt`, `tpi:say`, and speech started at boot with `SPEECH_VOLUME`/`SPEECH_RATE`/`SPEECH_PORTS` |
| 4. The `s:` channel | **Dropped**: needs a ROM change |
| 5. Ports 17 and 37 | **Done** in the firmware; untested from a 2068 |
| 6. Docs | **Done**: the reference (`firmware/speech.md`, `tsbus.md`, `board.md` and others), the v3 manual's Appendix G, `NOTICE` |

Still to do, with the card in a 2068: `tpi:say` from BASIC, a program
written for the speech board (OUT 17 / IN 37), and the IN timing while speech
plays (`respond_ns`, no late INs).
