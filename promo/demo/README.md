# TS-Pico 2.3 guided tour (the release video's demo program)

`tour.bas` is a BASIC program for a real TS-2068 with a TS-Pico on ROM 2.3 and firmware
2.3.1. It walks through what is new since version 1.1, one chapter per feature, for the
release video aimed at 1.1 owners. Each chapter opens with a title card, then runs its
commands a step at a time: the command about to run is shown on a yellow strip, a blue
caption says what to look at, and the presenter presses a key to go on. Nothing moves until
a key is pressed, so the narration sets the pace.

The whole tour was run in the emulator (`tools/emu`: ZEsarUX running
`src/rom/TSPICO-23.ROM`, `pico_host.py` running the real firmware), twice in a row from a
fresh copy of the card, with identical screens both times. See [Testing](#testing).

## Files

| File | What |
|---|---|
| `tour.bas` | The program: zmakebas source, with line numbers. |
| `TOUR.TAP` | The program built from it, starting itself at line 10. |
| `card/` | The demo card's contents (`card/TAP` becomes the card's `TAP` folder). |
| `build.py` | Builds `TOUR.TAP` and everything in `card/TAP`. |
| `emu_tour.py` | Runs the tour in the emulator, answering as the presenter would, and records every screen. |
| `screens/` | One emulator picture per chapter, plus a title card. |

## Building

```bash
python3 promo/demo/build.py                      # compiles tools/zmakebas in a temp folder
python3 promo/demo/build.py --zmakebas /path/to/zmakebas
```

`TOUR.TAP` is what `zmakebas -a 10 -n tour -o TOUR.TAP tour.bas` makes. `card/TAP/` gets:

- `tour.tap`: a copy of `TOUR.TAP`;
- `art.tap`: eight graphics (CODE, 64 bytes: an SD card and a cassette) and a picture
  (SCREEN$), both drawn by `build.py`, the letters from the ROM's own character set;
- `multi.tap` and `hello.tap`: the repo's demo programs (`basic/SD/TAP/demo`);
- `library/`: 26 one-line programs, `alpha.tap` to `zulu.tap`, so one folder is longer than
  the screen.

The card is 136 kB.

## Setting up the card

**The tour ships on both TS-Pico SD cards**, at the top of `TAP` with the tapes it uses:
the repo's `SD card/TAP` (in each release's zip and the web updater's SD card files) and
the TS-2068 Software Library card on archive.org (`tools/sd-archive/build_card.py`). On
either one, `LOAD "tpi:tour.tap"` then `LOAD ""` runs it. After changing the tour, run
`build.py` and copy `card/TAP`'s files over the ones in `SD card/TAP`.

On the Software Library card the top folder also holds the category folders, so chapter 2's
`CAT` and chapter 6's `d:` listing are longer than on the demo card. For the video, use a
card set up as below:

1. Start from a FAT card whose `TAP` folder has nothing called `tour` in it (the tour removes
   a `tour` folder it finds, files and all).
2. Copy `card/TAP` to the top level of the card as `TAP`.
3. Copy the repo's `SD card/help` folder to the top level, next to `TAP`. Chapter 11 needs it:
   `tpi:help` reads `/help` on the card. It is 540 kB, so it isn't duplicated here.

The card then holds `/TAP/{tour,art,hello,multi}.tap`, `/TAP/library/` and `/help/`.

## Running it on the 2068

Switch on, then:

```basic
LOAD "tpi:tour.tap"
LOAD ""
```

The first line mounts the tape, the second loads the program, which starts by itself. It
shows "Getting ready...", turns messages off (`tpi:verbose CODE 1,0`), ejects the tape,
goes to the top folder, and removes a `tour` folder left by a stopped run. Then chapter 1's
title card.

**Keys.**

- **"Press any key"** (white on black, on the bottom line): any key. The tour waits for the
  key to be let go before it carries on.
- **"Start tape, then press any key."** (chapters 5 and 9): press **ENTER**. SPACE works
  only if it's let go at once: SPACE still down when the save starts is BREAK to the tape
  routines, and the save stops with D (tested in the emulator with SPACE held 0.4 s).
- The other keys are in the table below. If a Y or N at an `Erase ... (Y/N)?` question
  doesn't appear on the screen, press it again (finding 9).
- BREAK at a "Press any key" stops the program (L BREAK into program). `RUN` starts it
  again from the beginning, and it tidies up first.

## The chapters

"Steps" are the "Press any key" stops in order (the numbers `emu_tour.py` uses). Times are
the emulator's, from the key that ends the previous chapter to the key that ends this one,
with every key pressed at once; each step includes about a second of the test driver's own
reaction time. The 2068's BASIC runs at its real speed in ZEsarUX, so the drawing (the big
chapter numbers take about 3 s a digit) is as on the real machine; TS-Pico transfers are
slower in the emulator than on the board.

| # | Title | What it shows | Presenter presses | Steps | Time |
|---|---|---|---|---|---|
| 1 | Welcome to TS-Pico 2.3 | `PRINT PEEK 101` gives 35 (ROM 2.3); commands are SAVE now, LOAD "tpi:..." only mounts; `SAVE "tpi:info"` | keys only | 1-3 | 13 s |
| 2 | Listings in color | `CAT`; `CAT "*.tap"`; `CAT "library"`, which stops at `(71%) Scroll? (Y/n)` | **Y** at Scroll? (N stops the list) | 4-7 | 15 s |
| 3 | Folders | `FORMAT "tour/"`, `MOVE TO "tour"`, `SAVE "tpi:path"`, `MOVE TO ""`, `tpi:path`; `CAT` with `<tour>` in it | keys only | 8-10 | 10 s |
| 4 | Copies and new tapes | `MOVE "multi.tap" TO "tour"`; `MOVE TO "tour"`; `MOVE "/art.tap" TO "pics.tap"` (a copy with a new name); `FORMAT "songs.tap"`; `CAT`; `CAT "multi.tap"` (the blocks in a TAP, not mounted); `CAT ""` (the new tape: empty, append on); `SAVE "tpi:close"` | keys only | 11-14 | 12 s |
| 5 | Single files with f: | Draws a picture, `SAVE "f:title.scr" SCREEN$`, wipes the screen, `LOAD "f:title.scr" SCREEN$`. Then two graphics: `SAVE "f:ab.bin" CODE USR "a",16`, wiped, `LOAD "f:ab.bin" CODE` | **ENTER** at each "Start tape" (two) | 15-20 | 32 s |
| 6 | Files as streams | `OPEN #4,"f:notes.txt","w"`, `PRINT #4`, `CLOSE #4`; `INPUT #4` until **8 End of file**, caught with `ON ERR GO TO`; a record file (`"u",12`, `TAB`) as a high-score table; `OPEN #5,"d:/*.tap"`, the top folder's tapes one name at a time | keys only | 21-24 | 18 s |
| 7 | The virtual printer | `SAVE "tpi:picopt"`, `PRINT PEEK 24027` (3); `LPRINT`; `LLIST 9900`; `COPY`; `SAVE "tpi:clprint"`; `SAVE "tpi:ts2040"`, `PEEK 24027` (2); where the files are | keys only | 25-27 | 26 s |
| 8 | Mounting a tape | `LOAD "tpi:pics.tap"`; `CAT ""` (pointer at 00); `LOAD "" CODE USR "a"` (the graphics); `CAT ""` (pointer at 02); `LOAD "" SCREEN$` (the picture); `SAVE "tpi:close"` | keys only | 28-33 | 16 s |
| 9 | Reports, not hangs | With messages on, the 1.1 habit `LOAD "tpi:dir"`: `File does not exist: dir`, Report F caught; `SAVE "my game"`: F, nothing written; `ERASE "*.tap"` asks about `multi.tap`, `pics.tap`, `songs.tap`; `CAT` shows what's left | **ENTER** at "Start tape"; **Y, N, Y** at the three `Erase ... (Y/N)?` (any answers work: the caption says Y erases, N keeps) | 34-37 | 19 s |
| 10 | BREAK is safe | `CAT "/library"` stops at Scroll?; BREAK gives **D BREAK - CONT repeats**, caught with `ON ERR`; the next command, `SAVE "tpi:path"`, works at once | **BREAK** (CAPS SHIFT + SPACE) at Scroll?. Y or N instead: the screen says "No BREAK that time." | 38-39 | 14 s |
| 11 | Help on the card | `SAVE "tpi:help"` (three pages); `SAVE "tpi:help cat"` (two) | **Y** at each Scroll? (N stops) | 40-42 | 21 s |
| 12 | Tidying up | `MOVE TO "/"`; each file in `tour/` erased by name (read with a `d:` stream); `ERASE "tour/"`; `CAT`; the end card: "Next, shown by hand: the menu and the Commander, cartridges, and Spectrum mode." The program ends with **0 OK, 9999:1** on a white screen. | keys only | 43-45 | 23 s |

The whole tour took about 4 minutes in the emulator with every key pressed at once.

## Retakes

`RUN` (or mounting and loading `tour.tap` again) starts the tour from the beginning. It
removes `tour/` at the start as well as the end, so every run starts from the same card and
shows the same screens: in the emulator, a second run straight after the first gave the
same 57 screens (45 steps, 11 prompts and the end), and a run stopped in chapter 8 with a
tape mounted and `tour/` full, then `RUN`, gave the full tour again.

What each run leaves on the card:

- one more file in `/VLPRINT` and one more in `/VSCREEN` (chapter 7's printout and COPY).
  The screen never shows their numbers, so the screens don't change. Delete the two folders
  from a computer after the shoot if you want.
- Nothing else. The free space in the `CAT` and `tpi:info` headers is the card's; on a real
  card it can move by a few kB between runs as those files pile up.

A stopped take (BREAK at a "Press any key", or a report) can leave a tape mounted, `tour/`
on the card, append on (chapter 4) or the printer on the card (chapter 7). `RUN` ejects the
tape (which turns append off), and chapter 7 always ends with `tpi:ts2040`. After a take
stopped in chapter 7, type `SAVE "tpi:ts2040"` if you want the TS 2040 back before the
next `RUN`.

## Left for the hand-shot section, and why

| Feature | Why it isn't in the program |
|---|---|
| The `LOAD ""` menu (nothing mounted) and the TS-Pico Commander | `LOAD ""` with nothing mounted loads the menu program, which replaces the tour. |
| `tpi:cd` and `tpi:idir` menus | `idir` mounts what is picked; both change the state later chapters rely on. Easy by hand. |
| Cartridges, `tpi:dock`, `tpi:boot`, holding D at switch-on | They restart or replace what's running. |
| ZX Spectrum mode (`tpi:zx48`, `OUT 244,3`) | It leaves TS-2068 BASIC. |
| Loading a program from a TAP, `MERGE` | Replaces the tour. |
| `LOAD "name"` that finds nothing ("8 End of file instead of an endless wait") | In the emulator it ends with **R Tape loading error**, not 8, and the next command in a running program can then answer 8 (findings 1 and 2). Left out until that's looked at. |
| BREAK in the middle of a long LOAD or SAVE | Every transfer on the demo card is over in well under a second on the board, too quick to catch. Chapter 10 shows BREAK at a TS-Pico prompt instead. By hand, with a big tape, if wanted. |
| The web updater | Runs on a computer. |

## Testing

```bash
python3 promo/demo/emu_tour.py --runs 2              # two runs, compared
python3 promo/demo/emu_tour.py --runs 2 --stop-at 30 # a take stopped at step 30, then RUN
python3 promo/demo/emu_tour.py --runs 1 --screens    # and rewrite screens/
```

`emu_tour.py` copies `card/` and the repo's `SD card/help` into a temporary folder (the
repo's card folder is never written), starts the emulator on it, types
`LOAD "tpi:tour.tap"` and `LOAD ""`, and answers as in the table: SPACE at every "Press any
key" (held 0.25 s), Y at the Scroll? prompts, ENTER at Start tape, Y N Y at ERASE, and BREAK
(CAPS SHIFT + SPACE held 0.3 s) at chapter 10's Scroll?. A prompt answer that doesn't show
on the screen within 3 s is pressed again, up to six times (finding 9). Later runs start
with `RUN`. It prints each step's time and compares the runs' screens, as text and pixel by
pixel; each step's screen text and picture are kept (`runN/wNN.txt`, `wNN.bmp`). The tour POKEs a step counter at 64000 for it (and
CLEARs 63999 to make room); that has no other effect.

Results on 2026-10-16 (this branch's firmware, `TSPICO-23.ROM`):

- Two runs in a row: both ended with 0 OK, 9999:1 (about 245 s each); all 57 screens'
  text the same, and all 45 step pictures the same pixel for pixel; no firmware traceback.
- A take stopped with BREAK at step 30 (chapter 8: `pics.tap` mounted, seven files in
  `tour/`; it stopped with L BREAK into program, 8945:2), then `RUN`: the full tour again,
  ending 0 OK, 9999:1, every step's text and picture the same as the clean run's.

## Findings

Things that behaved differently from the user manual or the what's-new post, or that a
program has to work round. All seen in the emulator; the ones marked *timing* may not happen
on the board, which is faster and uses DMA.

1. **`LOAD "name"` with no match gives R, not 8.** ([#311](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/311)) With `art.tap` mounted,
   `LOAD "nosuch" CODE` printed each header it passed (`Bytes: picture`, `Bytes: sprites`,
   `Bytes: picture`) and stopped with **R Tape loading error, 0:1**; `LOAD "nosuch"` on
   `multi.tap` the same. The manual (4.1, 11.2 "8 End of file on a LOAD", Appendix B) and
   the what's-new post say 8 End of file. `docs/reference/flows/load.md` says the firmware
   answers status 7 and "ROM 2.2 shows it as R"; ROM 2.3 does too.
2. **After that R, the next command in a running program can answer 8.** ([#311](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/311)) In a program,
   with the R caught by `ON ERR`, the next TS-Pico command sometimes stopped with
   **8 End of file**: `tpi:close` (twice), `tpi:nop`, `tpi:info`; `tpi:path` never did. Not
   every time, and never when the commands were typed. *Timing*, possibly.
3. **A command straight after `CLOSE #` of a `d:` stream got T.** ([#313](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/313)) `CLOSE #4: ERASE "tour/"`
   gave **T TS-Pico reset, try again**; the firmware log shows `Partial pre-header --
   RECOVERED: 2/10` about 1.1 s after `tpi:chclose`, whose TX drain took 155 ms. The tour
   puts `PAUSE 10` after each `CLOSE #`, and it hasn't happened since. *Timing*, possibly.
4. **BREAK: the keys are still down afterwards.** ([#315](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/315)) BREAK at a Scroll? prompt gives D as the
   manual says, but a program that catches it carries on while CAPS SHIFT + SPACE are still
   held: the next statement stops with **L BREAK into program**, or the next TS-Pico command
   with D (seen with `SAVE "tpi:path"` run at once). The tour keeps `ON ERR` set until the
   keys are let go. "The next command works normally" holds once they are.
5. **SPACE held at "Start tape" stops the save with D.** ([#315](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/315)) `SAVE "f:x.scr" SCREEN$` and
   `SAVE "f:y.bin" CODE` with SPACE held 0.4 s at the prompt: both **D**. So is a LOAD that
   starts while SPACE is down. It's the tape routines' BREAK test (SPACE alone), and the
   TS-Pico starts the transfer at once, so the key is still down. Worth a line in the
   manual: press ENTER at "Start tape".
6. **With messages on, an f: SAVE puts its message into the picture.** ([#314](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/314)) With VERBOSE on,
   `SAVE "f:title.scr" SCREEN$` prints `Saving to /tour/title.scr` on the upper screen
   before the screen is saved, so the saved picture has the message in it. The manual
   (5.2) is careful that the Replace? question doesn't spoil a picture; this message does.
   The tour runs with messages off.
7. **A bad SAVE name asks for a key first.** ([#315](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/315)) `SAVE "my game"` shows `Start tape, then press
   any key.` and gives F after the key. The manual's "F before anything is written" is true
   (nothing is written), but the key comes first.
8. Small ([#316](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/316)): `SAVE "tpi:verbose" CODE 1,1` prints `Verbose is now enabled` with no new line, so
   the next PRINT carries on the same line.
9. **`Erase ... (Y/N)?` sometimes misses a key.** ([#312](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/312)) In a 12-round test of `ERASE "*.tap"` with
   three files (36 answers, each key held 0.25 s), 8 presses weren't taken: nothing on the
   screen, the Z80 at 0038h with interrupts off each time. The next press was taken every
   time but once (two misses in a row). In one tour run, N and then Y went untaken for 30 s
   and the run was abandoned. The Scroll? prompts never missed a key in any run. Worth
   trying on the board: if it happens there, the presenter presses the key again.
10. Small ([#316](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/316)): `DISK_ERASE`'s comment in `src/TS/tspico.py` still says "N stops"; the code
    (`PROMPT_EACH`) and the manual say N skips that file and goes on, which is what happens.

Everything else the tour uses behaved as the manual says: `PEEK 101` 35; `CAT` and its
patterns, paging (`(71%) Scroll? (Y/n)`), other folders and TAP contents; `FORMAT` of a folder
and a tape (mounted, append on); `MOVE` copies and `MOVE TO` / `MOVE TO ""`; `f:` SCREEN$ and
CODE; `OPEN #` w/r/u with records and `TAB 0`, `d:` listings; `PEEK 24027` 3 then 2 around
`tpi:picopt`/`tpi:ts2040`; `CAT ""` and its pointer; `LOAD "tpi:dir"` gives F with `File does
not exist:`; `ERASE` with a pattern (N skips and goes on); `tpi:help` and `tpi:help cat`.

**What the emulator can't show:** timing (findings 2 and 3 above may be emulator-only, and
DMA isn't used); how long a key is really held (the tour waits for keys to be let go, which
covers it); the VGA capture's colors. Try a take on the board before the shoot, chapters 7
(COPY) and 10 (BREAK) especially.
