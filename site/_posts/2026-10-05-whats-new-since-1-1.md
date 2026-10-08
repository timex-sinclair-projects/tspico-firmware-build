---
layout: post
title: "What's New in the TS-Pico Since 1.1"
lang: en
date: 2026-10-05 06:00:00 -0400
---

The last TS-Pico software most owners installed was version 1.1. The current release,
**2.3**, replaces it. It updates both halves of the TS-Pico: the **firmware** on the Pico
(firmware 2.3), and the **TS-2068 ROM** in its flash chip (ROM 2.3). The firmware and
the ROM are made to work together, so install both. The
[web updater]({{ site.updater_url | relative_url }}) does it from Chrome or Edge in about
fifteen minutes.

This post covers what changed. The full details are in the
[User Manual]({{ site.github_repo }}/blob/main/docs/manual/user-manual.md), which is new as
well.

## Fixes and improvements to the commands you know

The link between the 2068 and the Pico has been rebuilt. It now uses two ports, one for data
and one for status, with a real ready/busy handshake between them. Most of the fixes below
come from that.

**Loading and saving**

- **No more Report D or J on bigger files.** Version 1.1 could fail partway through a large
  LOAD or SAVE. The two-port link cures it, and LOAD now streams each block straight from
  the Pico's memory.
- **LOAD gives up when there's nothing to find.** `LOAD "name"` searches the mounted tape
  from the tape pointer and wraps round once. If nothing matches, you get **8 End of file**
  instead of an endless wait.
- **A damaged TAP file gives Report R Tape loading error**, the same report a bad cassette
  gives.
- **SAVE checks the name first.** A plain SAVE name can use letters, digits, `-` and `_`.
  Anything else gives **F Invalid file name** before anything is written. Saving an empty
  program gives **A Invalid argument**.

**BREAK and recovery**

- **BREAK works.** CAPS SHIFT + SPACE stops any TS-Pico command with **D BREAK - CONT
  repeats**, even in the middle of a long LOAD or SAVE, and the next command works normally.
- **A new report, T TS-Pico reset, try again.** If the TS-Pico has to abandon a transfer,
  the 2068 says so at once and the next command starts fresh. In 1.1 the same problem meant
  a twenty-second wait for Report J, and often more J's after it.

**The SD card**

- **The TS-Pico runs without a card.** Take the card out and the commands that need it fail
  with a report. The TS-Pico itself keeps working.
- **Swap cards freely.** The TS-Pico notices a new card. Files copied on from a computer show
  up without a restart.
- **Cards that used to stick.** The TS-Pico gives a cold card time to start, retries one that
  doesn't answer, and recovers one left half-way through a write.

**Files and folders**

- **Clearer listings.** `SAVE "tpi:dir"` shows the folder in colour, with the card's size
  and free space. A long listing stops at `Scroll? (Y/n)` and shows how far through you are;
  press **1** to **9** to scroll that many lines.

  ![CAT on a card with four folders and eight files]({{ '/assets/img/whats-new/cat.png' | relative_url }})

- **Names from your computer.** Characters the 2068 can't show, such as `{`, `|`, `~` or
  accented letters, appear as `?`, and you can type the name with the `?` to load the file.
- **`tpi:newtap` never empties an existing file.** It answers **F** instead.
- **`tpi:rm` removes any file or empty folder.** It refuses the mounted file.
- **Flash slots are safer.** The TS-Pico refuses to write the flash slot the 2068 is
  running from. Doing that used to hang both machines.

**ZX Spectrum mode**

- `LOAD "tpi:name.tap"` mounts another tape without leaving Spectrum mode.
- `SAVE "tpi:dir"` lists the folder, with the new Spectrum ROM (version 4) in flash slot 0.
- You now leave Spectrum mode with `OUT 14,14`. The old `OUT 10,100` no longer works.

  ![SAVE "tpi:dir" in Spectrum mode]({{ '/assets/img/whats-new/zx48-dir.png' | relative_url }})

**One change to get used to.** TS-Pico commands are now `SAVE` commands: `SAVE "tpi:dir"`,
`SAVE "tpi:cd games"` and `SAVE "tpi:info"`. `LOAD "tpi:..."` only mounts a file, so
`LOAD "tpi:dir"` now looks for a file called `dir` and gives Report F. `tpi:upgrade`,
`tpi:rompatch` and `tpi:sys` are gone; the web updater does their job.

## New commands: the disk keywords

The TS-2068 ROM has four keywords that Timex never implemented: **CAT**, **MOVE**, **ERASE**
and **FORMAT**. Timex meant them for a disk drive. The new ROM makes them work on the SD card,
with features borrowed from the Zebra FDD's TOS. They take wildcards
(`*` and `?`), paths, and string expressions such as `CAT a$`.

| Command | What it does |
|---|---|
| `CAT` | List the current folder |
| `CAT "games/b*"` | List matching files in another folder |
| `CAT "frogger.tap"` | List the blocks inside a TAP file |
| `CAT ""` | List the blocks in the mounted TAP, with the tape pointer |
| `MOVE TO "games"` | Change folder (`MOVE TO ""` goes back) |
| `MOVE "a.tap" TO "b.tap"` | Copy a file (never overwrites) |
| `MOVE "*.tap" TO "backup"` | Copy all matching files into a folder |
| `ERASE "old.tap"` | Delete a file |
| `ERASE "*.bak"` | Delete matching files, asking about each one |
| `FORMAT "songs.tap"` | Make a new, empty TAP, ready to append to |
| `FORMAT "tools/"` | Make a folder |

`FORMAT` never formats your SD card. It only makes new things, and it never overwrites a
file that's already there.

![CAT "": the blocks in the mounted TAP, with the next block highlighted]({{ '/assets/img/whats-new/tapdir.png' | relative_url }})

### Single files with `f:`

Until now everything lived inside TAP files, which are recordings of a whole cassette. Put
`f:` in front of a name, and LOAD, SAVE, VERIFY and MERGE use a single file on the card
instead:

```basic
SAVE "f:advent.bas" LINE 10
SAVE "f:title.scr" SCREEN$
SAVE "f:sprites.bin" CODE 50000,768
LOAD "f:title.scr" SCREEN$
```

The mounted TAP and its tape pointer are left alone. SAVE asks before it replaces a file.
Programs, code and arrays get a +3DOS header, the format the Spectrum +3 and most modern
tools use. A SCREEN$ is saved as the plain 6,912 bytes, so picture tools on your computer can
open it.

### Files as streams with `OPEN #`

The 2068's `OPEN #`, `PRINT #`, `INPUT #`, `INKEY$ #`, `LIST #` and `CLOSE #` now work with
files on the card. Your BASIC programs can keep high-score tables, notes, logs and data
files:

```basic
10 OPEN #4,"f:notes.txt","w"
20 PRINT #4;"Hello from the 2068"
30 CLOSE #4
```

Files can be read, written, appended to or updated in place. **Record files** with `TAB`
positioning let a program jump straight to record 57 without reading the 56 before it. And
`OPEN #5,"d:*.tap"` lets a program read a folder listing, one name at a time.

## Other new features

- **The web updater.** Install or update the TS-Pico from a browser: the firmware, the
  TS-2068 ROM, the Pico's files and the SD card files. No Thonny, no dragging files about.
  It works out what your board needs and walks you through it.
- **The virtual printer.** After `SAVE "tpi:picopt"`, `LPRINT` and `LLIST` go to text files
  on the card, and `COPY` saves the screen as a BMP picture you can open on any computer.
  COPY understands the second screen, hi-colour and the 512-column mode. You choose the page
  width, the line endings and the picture size.
- **A menu when nothing is mounted.** `LOAD ""` with no tape mounted loads a small menu, with
  help on every command, a file picker, and the **TS-Pico Commander**, a full-screen file
  manager you drive with the cursor keys.
- **Help on the card.** The `help` folder on the SD card has a page for every TS-Pico
  command and for the BASIC keywords.
- **Cartridges.** `SAVE "tpi:dock" CODE 0,2` swaps back to the cartridge you had in the dock
  before.
- **Under the hood.** The firmware now runs on MicroPython 1.29, and moves data to and from
  the 2068 with the Pico's DMA hardware.
- **Manuals.** A new [User Manual]({{ site.github_repo }}/blob/main/docs/manual/user-manual.md)
  covers every command, with pictures of what you'll see on screen. There's a
  [Programmer's Manual]({{ site.github_repo }}/blob/main/docs/manual/programmers-manual.md)
  too (see below).

## The TS-2068 Software Library on an SD card

A TS-Pico is only as good as what's on the card, so we've made one: **1,327 TS-2068 programs**
from the [Timex Sinclair Software Archive](https://archive.org/details/timex-sinclair-software-archive)
on archive.org, ready to copy to an SD card.

[Download the library (a 5.7 MB zip, from archive.org)](https://archive.org/download/timex-sinclair-software-archive/TS-Pico%20SD%20Card%20-%20TS-2068%20Software%20Library%20(2026)(TS2068)(US)(Collection).zip)

**What's on it**

- **Every program has been tested.** Each one was loaded with `LOAD ""` on a TS-Pico
  running the real firmware, in an emulator (see below). Programs that failed were tried
  again with `LOAD "" CODE` or `RUN`, from the archive's TZX or WAV copies, and on a stock
  2068 for comparison. A tape went on the card only if it loaded and started. Tapes with a
  damaged block were left out.
- **Category folders** under `TAP`: `GAMES`, `ARCADE`, `UTILITY`, `GRAPHICS`, `HOME`,
  `EDUCATE`, `MUSIC`, `DEMOS` and `MISC`. `COLLECT` holds the multi-program collections,
  such as newsletter and user-group tapes, one subfolder each.
- **Short names** you can type: up to eight letters, from the program's title
  (`capimast.tap`).
- **A catalog**, `catalog.csv`, which you can open in any spreadsheet. It lists each program's
  title, folder and file name, a summary and a description, how to load it, and the original
  file in the archive. It also lists the tapes that were left out, and why.
- The `help` folder, with the TS-Pico's help pages.

**Installing it.** Unzip it and copy the `TAP` and `help` folders to the top level of a
FAT-formatted micro SD card. Then, on the 2068:

```basic
CAT
MOVE TO "games"
LOAD "tpi:capimast.tap"
LOAD ""
```

You can also download it from the **SD card files** section of the web updater.

## For developers

The TS-Pico firmware is now open source, on GitHub at
[timex-sinclair-projects/tspico-firmware-build]({{ site.github_repo }}). The code is under
the MIT license and the documentation under CC BY 4.0. Issues and pull requests are welcome.

**Writing programs that use the TS-Pico.** The
[Programmer's Manual]({{ site.github_repo }}/blob/main/docs/manual/programmers-manual.md) is
in two parts:

- **The 2068 side.** It covers the two ports and the status byte, and how a command travels
  between the machines. It includes `picolib.asm`, a small Z80 library that sends commands
  and reads answers, and worked examples: load any file into memory, append a line to a log
  file, count matching files. It also covers the ROM's Pico BIOS.
- **The Pico side.** It explains how the firmware is put together, and how to add a command
  of your own. External commands are MicroPython functions in a file on the Pico, so you can
  add a `SAVE "tpi:.hello"` without rebuilding the firmware.

The protocol is documented byte by byte in
[`docs/PROTOCOL.md`]({{ site.github_repo }}/blob/main/docs/PROTOCOL.md), with a
plain-language introduction in
[`docs/PROTOCOL_GUIDE.md`]({{ site.github_repo }}/blob/main/docs/PROTOCOL_GUIDE.md).

**A TS-Pico in your emulator.** You no longer need the hardware to develop for the TS-Pico.
**`pico_host`** runs the real TS-Pico firmware, unmodified, on your computer, with a folder
standing in for the SD card. Two emulators connect to it, and their TS-2068 then has a
TS-Pico on ports 0Eh and 0Fh, running the TS-Pico ROM:

- **ZEsarUX**, in the
  [zesarux-tspico](https://github.com/timex-sinclair-projects/zesarux-tspico) fork.
- **Fuse**, in [fuse-tspico](https://github.com/timex-sinclair-projects/fuse-tspico) for
  Linux and Windows, and
  [fuse-for-macos-tspico](https://github.com/timex-sinclair-projects/fuse-for-macos-tspico)
  for the Mac.

Each release has a ready-to-run `pico_host` for macOS, Linux and Windows, with no Python
needed. Start it, start the emulator with its TS-Pico turned on, and `CAT` works. Each
emulator repository's `TSPICO.md` says how to set it up. The emulator shows whether your
program and the TS-Pico agree, which is what you need for most development. It can't show
timing problems; those still need a real board.

The link between an emulator and `pico_host` is a small, documented protocol:
[`docs/EMULATOR_BRIDGE.md`]({{ site.github_repo }}/blob/main/docs/EMULATOR_BRIDGE.md). Each
port access is a two-byte message over a socket. If you maintain a TS-2068 emulator, that
page is all you need to add a TS-Pico to it.

**Working on the firmware.** The
[Developer Guide]({{ site.github_repo }}/blob/main/docs/DEVELOPER_GUIDE.md) takes you from a
fresh clone to a tested change. It covers the host tests that CI runs on every pull request,
`tools/pico-serial.py` for flashing and watching a Pico without Thonny, and the emulator
tests in `tools/emu`. The scripts that built and tested the software library are in
`tools/sd-archive`.

## Getting 2.3

1. Switch the TS-2068 off.
2. Open the [web updater]({{ site.updater_url | relative_url }}) in Chrome or Edge, connect
   the TS-Pico by USB, choose **Latest release**, and follow the steps. Coming from 1.1,
   leave **Erase the Pico first** and **Update the TS-2068 ROM** ticked. On Windows, run
   **TS-Pico-Updater.exe** from the
   [latest release](https://github.com/timex-sinclair-projects/tspico-firmware-build/releases/latest)
   instead: it works the same way.
3. Keep the **P10 jumper** fitted. Writing the ROM to the flash chip needs it.

Afterwards, `PRINT PEEK 101` on the 2068 gives **35** (ROM 2.3), and `SAVE "tpi:info"` shows
firmware 2.3 and ROM 2.3.

Thanks to everyone who tested along the way.
