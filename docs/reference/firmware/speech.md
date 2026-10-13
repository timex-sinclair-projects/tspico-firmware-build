# Speech (`speech.py`, `speech_rules.py`, `sp0256.c`)

The v3 card speaks with the voice of a General Instrument SP0256-AL2, the chip
in the Currah µSpeech and David's Pico Speech Synth 2068 board, emulated from
its ROM ([docs/v3-speech-proposal.md](../../v3-speech-proposal.md)). This
chapter covers the parts that are speech's alone:

- [`src/TS/speech.py`](../../../src/TS/speech.py): English to the AL2's
  allophone numbers, on core 0;
- [`src/TS/speech_rules.py`](../../../src/TS/speech_rules.py): the
  letter-to-sound rules it uses, as data;
- [`src/tsbus/sp0256.h`](../../../src/tsbus/sp0256.h),
  [`sp0256.c`](../../../src/tsbus/sp0256.c),
  [`sp0256_mame.inc`](../../../src/tsbus/sp0256_mame.inc) and
  [`sp0256_al2.inc`](../../../src/tsbus/sp0256_al2.inc): the chip itself, in
  C, which core 1 runs;
- [`tools/sp0256-port.py`](../../../tools/sp0256-port.py) and
  [`tools/speech-rules.py`](../../../tools/speech-rules.py), which generate
  the `.inc` files and `speech_rules.py`.

How they're joined up is elsewhere:
- the ring, the DMA and the ports: [tsbus.md](tsbus.md#speech), in `tsbus.c`;
- the board's calls: [board.md](board.md#speech_startvolume-rate-portstrue);
- `tpi:say`: [tspico-commands.md](tspico-commands.md#saypre-cmd).

There is no speech channel (`OPEN #n,"s:"`): the ROM's `CH_OPEN_HOOK` claims
only `d:` and `f:` specs and gives the rest to the stock 2068 code, whose `s`
is the screen. Adding it would need a ROM change, so it was dropped
(2026-10-12).

Where each piece comes from, and on what terms, is in
[`NOTICE`](../../../NOTICE): Microchip's ROM (acknowledged, as its 2007
permission asks), MAME's BSD-3 core, and the public-domain rules.

## The path of a sentence

```
SAVE "tpi:say HELLO"  -->  SAY  -->  board.say(text)
                                       |  speech.allophones(text)   core 0, ~20-40 ms
                                       v
                                     tsbus.say(bytes)  -->  spk_q  (1024)
OUT 17,n  -------------------------- core 1 io_snoop -->  spk_pq (64)
                                       |
                    core 1 speech_pass: when the chip's LRQ says so, the next
                    allophone into sp0256_ald; sp0256_sample() per 10 kHz tick
                                       v
                    spk_ring (1024 levels) --DMA, timer-paced--> PIO2 spk_pwm --> GP46, GP30
```

## `speech.py`

Plain Python, no hardware: the same file runs on the card (frozen into the v3
build only) and in [`speech_hosttest.py`](../../../src/test/speech_hosttest.py).
It imports only `TS.speech_rules`.

### `NAMES`, `NUMBER`, `PA2`, `PA4`, `PA5`

The AL2's 64 allophones in chip order, so `NAMES[n]` is allophone `n` (PA1 0,
PA5 4, OY 5 … BB2 63), and `NUMBER`, the reverse. `PA2`, `PA4` and `PA5` are
the pauses `allophones` adds: between words, at a comma, at a full stop. The
order is the datasheet's and matches `sp0256.c`'s ROM; `speech_hosttest.py`
checks two of them.

### `EXCEPTIONS`

`dict`: upper-case word → NRL phonemes, for words the rules get wrong. The NRL
report itself puts its rules at about 90 % of words in ordinary text. The
built-in ones came from listening (2026-10-12): BROWN, DOWN and TOWN (the
rules say "own"), HUNDRED (they lose a vowel), HI ("hih"), WANT, ERROR, TS
(spelled), PICO, TIMEX, SINCLAIR, THOUSAND, and a few short words. `load_exceptions` adds to it.

### `load_exceptions(path="/speech.txt")`

Reads `WORD = phonemes` lines from `path` into `EXCEPTIONS`, adding words or
replacing built-in ones. Blank lines, lines starting `#` and lines without
`=` are skipped. Returns how many were read; a missing file is 0, not an
error. `board_v3.speech_start` calls it at boot, so a user's words are in
place before the first `tpi:say`.

### `_vowel(c)`, `_cons(c)`

A, E, I, O, U; and any other upper-case letter. Wasser's `isvowel` and
`isconsonant`.

### `_left(pat, w, t)`, `_right(pat, w, t)`

Wasser's `leftmatch` and `rightmatch` (`phoneme.c`): does the context pattern
match the word `w` to the left of index `t`, read right to left, or from `t`
rightwards? The context symbols:
- `#` one or more vowels;
- `:` zero or more consonants;
- `^` one consonant;
- `.` a voiced consonant (B D V G J L M N R W Z);
- `+` a front vowel (E I Y);
- `%` a suffix (ER, E, ES, ED, ING, ELY), on the right only;
- a space, the edge of the word.

Anything else matches itself. The word arrives with a space at each end, as
Wasser's code adds them.

### `word_phonemes(word)`

One upper-case word to NRL phoneme text. `EXCEPTIONS` first; otherwise each
unmatched letter is looked up in `RULES` under that letter (punctuation under
`''`), and the first rule whose match text and both contexts fit gives its
phonemes and moves past the matched text. A letter no rule matches is
skipped. This is Wasser's `xlate_word` and `find_rule`.

### `phonemes(text)`

NRL phoneme text to a list: upper-case codes are two letters (IY, AE, SH …),
lower-case ones one (p, t, k …); spaces are dropped.

### `_ONES`, `_TENS`, `say_number(n)`

Numbers as words: "two thousand and sixty eight", "one hundred", "forty two".
Up to 999,999 in words; from a million up, digit by digit. `_words` calls it
for every run of digits, so `tpi:say 2068` says the number.

### `_FRONT`, `_VOWELS`, `_SIMPLE`, `_RCOL`, `_VOICED_STOPS`

The tables `word_allophones` works from:
- the front vowels, which choose KK1, GG1 and HH1;
- the vowels, including the r-coloured ones;
- the phonemes that have one AL2 allophone whatever their context;
- the vowel-plus-R pairs that become an r-coloured allophone (AA r → AR,
  AO/OW/UW/UH r → OR, EH/EY/AE r → XR, IH/IY r → YR);
- the voiced stops a PA1 goes before.

### `word_allophones(ph)`

One word's NRL phonemes to AL2 allophone names, choosing each sound's
variant by context as the AL2 datasheet's tables describe:
1. **Merges first:** vowel + r → the r-coloured allophone; n before k or g →
   NG.
2. **Then each phoneme:**
   - T: TT2 at the start of a word or before a vowel (not after S), TT1
     otherwise.
   - D: DD2 initial, DD1 elsewhere. B: BB2 initial before a vowel, BB1
     elsewhere.
   - K: KK1 before a front vowel, KK3 before another vowel, KK2 finally or
     before a consonant.
   - G: GG1 before a front vowel, GG2 before another, GG3 finally.
   - DH: DH1 initial, DH2 elsewhere. H: HH1 before a front vowel, HH2
     otherwise. N: NN2 initial, NN1 elsewhere.
   - L: EL at the end of a word after a consonant, LL otherwise. Y: YY1
     before UW, YY2 otherwise. R: RR1 initial, RR2 elsewhere.
   - UW: UW1 after Y, J, CH, SH, UW2 otherwise. ER: ER2 in a word of three
     phonemes or fewer, ER1 otherwise. AH becomes AX: the AL2 has no AH.
3. **A PA1** goes before a voiced stop inside a word when it is released into
   a vowel, as the datasheet's examples do.

These rules are this firmware's, written from the datasheet and tuned by ear
on 2026-10-12; they aren't Wasser's or the NRL's.

### `_words(text)`

Text to tokens:
- words, upper-cased (letters and apostrophes);
- each run of digits, as `say_number`'s words;
- the punctuation that pauses (`. , ! ? ;`);
- any `[...]` kept whole.

Other characters are dropped.

### `allophones(text)`

Text to a `bytearray` of allophone numbers, always ending in PA5:
- `[...]` gives the names inside it, as they are (spaces or commas between
  them, any case); a name that isn't an allophone is `ValueError`;
- `. ! ? ;` gives PA5, `,` PA4;
- PA2 goes between words, unless a pause is already there;
- each word goes through `word_phonemes`, `phonemes` and `word_allophones`.

On the card a sentence takes 20–40 ms (MicroPython from source on board 2,
2026-10-12; frozen bytecode is quicker). On 5,000 dictionary words it gives
the same allophones as the prototype (`t2a.py`), except one deliberate fix:
an L after an r-coloured vowel is LL, not EL.

## `speech_rules.py`

### `RULES`

`dict`: first letter of the text to match (`''` for punctuation) → a tuple of
`(left, match, right, phonemes)` rules, in Wasser's order, which matters: the
first rule that fits wins. There are 354, from NRL Report 7948 (1976) as John
A. Wasser coded them in `english.c` (1985). Both are public domain.
Generated by `tools/speech-rules.py`: don't edit it. Frozen, so the rules stay
in flash rather than the heap.

## `sp0256.h` and `sp0256.c`

The chip as plain C, with no hardware in it, so core 1 runs it and
[`sp0256_hosttest.py`](../../../src/test/sp0256_hosttest.py) compiles it with
`cc`. It produces one sample per call at the chip's rate.

### `SP0256_RAM(f)`, `SP0256_DATA`

Core 1 never reads flash ([tsbus.md](tsbus.md)). `SP0256_RAM` is
`__not_in_flash_func` on the card (`U8251_ON_PICO`) and nothing on the host;
every function core 1 calls is wrapped in it. `SP0256_DATA` places a table in
RAM by section (`.data.sp0256`). It's needed because GCC put tables nothing
writes in `.rodata`, in flash, even without `const`: found in the first build's
symbol table (2026-10-12). `sp0256.c` also turns off GCC's loop-to-`memset`
transformation (`#pragma GCC optimize`), which would turn MAME's zeroing
loops into calls into flash.

### `SP0256_RATE`, `SP0256_ROM_AT`, `SP0256_ROM_N`

10,000 samples a second: the AL2's 3.12 MHz crystal divided by 312, MAME's
`CLOCK_DIVIDER`. 1000h, where the AL2's ROM sits in the chip's address space,
and 2048, its size.

### `lpc12_t`, `sp0256_t`

MAME's `lpc12_t` (the 12-pole filter: repeat count, period, noise generator,
amplitude, the six stages' coefficients and delays, the encoded registers)
and `sp0256_device`'s members, as struct fields with MAME's names minus
`m_`. The SPB640's FIFO fields are kept, unused (MAME's code refers to them).

### `sp0256_init(s, rom)`

MAME's `device_start` and `device_reset`: everything zeroed (with `memset`),
the noise generator seeded, halted, LRQ ready, the page at 1000h. Not in RAM:
only core 0 calls it, from `tsbus.speech`.

### `sp0256_stop(s)`

Silence from the next sample and ready for an allophone, mid-word if need be:
halted, LRQ set, the repeat count spent. Plain field stores, for core 1
(`tsbus.say(None)`).

### `sp0256_ald(s, n)`, `sp0256_lrq(s)`

MAME's `ald_w`: load allophone `n` if LRQ says the chip can take one (its
address is `n << 4`), else drop it, as the chip does. And LRQ. The chip takes
the loaded allophone when it finishes the one it's speaking, so LRQ comes back
almost at once: a speaker keeps one queued ahead.

### `sp0256_sample(s)`

MAME's `sound_stream_update`, one sample at a time: when the repeat count
runs out, the microsequencer (`sp0256_micro`) reads the next instruction from
the ROM and loads the filter; then one sample of the filter, or silence. The
range is MAME's `HIGH_QUALITY` limiter (±8191) shifted left 2; speech peaks
near 6000.

### `sp0256_idle(s)`

Halted, LRQ ready and nothing to repeat: nothing loaded and nothing left to
say. Once halted, MAME's microsequencer sets a repeat of 1 on each call, so
this reads true on alternate samples. Watch it every sample (as
`speech_pass` and the tests do), not once.

### `sp0256_rom(s, idx)`

MAME reads the ROM from a 64 KB address space. This reads the 2 KB table
for 1000h–17FFh and 0 elsewhere, as MAME's empty region does. It's the one
change to MAME's code beyond its form. `sp0256_hosttest.py` shows it changes
no sample.

### `sp0256_al2`

The ROM: 2048 bytes, `SP0256_DATA`, from `sp0256_al2.inc`.

## `sp0256_mame.inc` and `sp0256_al2.inc`

Generated by `tools/sp0256-port.py`; don't edit them.
- **`sp0256_mame.inc`** is MAME's `src/devices/sound/sp0256.cpp`, lines
  182–1150: the limiter, `lpc12_update`, `lpc12_regdec` and its quantisation
  table, the data-format tables, `bitrev32`/`bitrev8`, `sp0256_getb` and
  `sp0256_micro`. It's turned from a C++ class into C mechanically, under
  MAME's BSD-3 header.
- **`sp0256_al2.inc`** is the AL2 ROM, in MAME's bit order, with Microchip's
  acknowledgment.

Checked against MAME's own C++ (unchanged, around a stand-in device class),
sample for sample: all 64 allophones and two sentences, 257,259 samples, no
difference (2026-10-12; `sp0256_hosttest.py` keeps the hashes).

## `tools/sp0256-port.py`

`python3 tools/sp0256-port.py MAME_SP0256_CPP AL2_BIN` writes both `.inc`
files. It checks its inputs: the first line of MAME's licence header, and the
ROM's SHA-1 once each byte is bit-reversed (`e60fcb5f…`, MAME's
`sp0256-al2.bin`). The `al2.bin` from spatula-city.org is in the opposite bit
order to MAME's.

The port's steps:
- members become `s->` or `f->` fields, the lambda a function, `LOG` calls go;
- every function is wrapped in `SP0256_RAM`, and the four tables are marked
  `SP0256_DATA`;
- ROM reads go through `sp0256_rom`.

Run it again to take a newer MAME, then run the host test.

## `tools/speech-rules.py`

`python3 tools/speech-rules.py ENGLISH_C` writes `speech_rules.py` from
Wasser's `english.c` (the CMU AI Repository's `eng2phon` package). It checks
the file names NRL Report 7948, and maps Wasser's `Anything`/`Nothing`/
`Silent`/`Pause` to `''` and `' '`.

## Checked on the card (board 2, USB only, 2026-10-12)

- **The audio path:** tones from each PWM channel at the jack, and the ROM
  speech by DMA, sounded as the WAVs did on the Mac.
- **On board 1 in a 2068 (2026-10-13)** the DMA into the PWM block crashed
  the 2068 during flash writes and `tpi:` commands that slept on core 0, so
  the audio moved to two PIO2 state machines (`spk_pwm`: 11 bits, about
  41 kHz, instead of the PWM block's 12 bits at 61 kHz). It sounded the same
  to David, and a `tpi:modem` loop then ran 419 commands without a fault
  ([tsbus.md](tsbus.md#speech)).
- **The firmware's own speech** (`tsbus.speech`, `tsbus.say` from the REPL):
  two sentences gave 80,157 samples, exactly MAME's count for them, and
  `s_late` stayed 0. Volume 70 % and 15 % were heard, and `say(None)` was
  silent at once.
- **The boot path:** speech on from `config.ini`, and `board.say` spoke.

Still to try with the card in a 2068 *(unverified)*:
- `tpi:say` and ports 17/37 from BASIC;
- the IN timing while speech plays.
