---
layout: post
title: "Still on 1.1? TS-Pico 2.3 Is a Free Upgrade"
lang: en
date: 2026-10-16 00:00:00 -0400
---

**CAT. MOVE. ERASE. FORMAT.** The disk keywords Timex built into the 2068 and never finished
now work, on your TS-Pico's SD card. TS-Pico 2.3 replaces version 1.1 with new firmware and
a new ROM, and installs from a web browser in about fifteen minutes. It's free.

<img src="{{ '/assets/flyer/ts2068-line.svg' | relative_url }}" alt="A TS 2068 with a TS-Pico behind it"
     style="display: block; width: 100%; background: #b4b1ab; border-radius: 4px;">

[Download the flyer (PDF, letter, front and back)]({{ '/assets/flyer/tspico-2.3-flyer.pdf' | relative_url }})
to print or pass on to your user group.

## What's new since 1.1

**Disk commands in BASIC.** `CAT` lists the card, `MOVE` copies files and changes folder,
`ERASE` deletes, and `FORMAT` makes a new tape or folder. Wildcards and paths included:
`CAT "games/b*"`, `MOVE "*.tap" TO "backup"`.

![CAT listing a folder in color]({{ '/assets/img/whats-new/cat.png' | relative_url }})

**Single files with `f:`.** LOAD, SAVE, VERIFY and MERGE a file of its own, outside any TAP:
`SAVE "f:advent.bas" LINE 10`, `LOAD "f:title.scr" SCREEN$`. Screens save as the plain 6,912
bytes your computer's picture tools can open.

**Files your programs can read and write.** `OPEN #`, `PRINT #` and `INPUT #` work with
files on the card: high-score tables, notes, logs, record files with `TAB`, even a folder
listing.

**A printer on the card.** After `SAVE "tpi:picopt"`, `LPRINT` and `LLIST` go to text files
and `COPY` saves the screen as a BMP picture, second screen, hi-color and 512 columns
included.

**A menu when nothing is mounted.** `LOAD ""` with no tape mounted loads a menu: help on
every command, a file picker, and the TS-Pico Commander, a full-screen file manager you drive
with the cursor keys.

**Inside a tape.** `CAT ""` lists the blocks in the mounted TAP and shows where the tape
pointer is. `FORMAT "songs.tap"` starts a new, empty tape.

![CAT "": the blocks on the mounted tape, the next one highlighted]({{ '/assets/img/whats-new/tapdir.png' | relative_url }})

**1,327 programs, ready to copy.** The TS-2068 Software Library: every program test-loaded
with the TS-Pico firmware, sorted into folders, with short names you can type and a catalog. Free, from
archive.org.

**Also:** help pages for every command on the card, a better ZX Spectrum mode, a new User
Manual (as a PDF or a booklet to print) and a Programmer's Manual. The firmware is open
source.

## Fixed since 1.1

- **No more Report D or J on big files.** A rebuilt two-port link with a real ready/busy
  handshake.
- **BREAK works.** CAPS SHIFT + SPACE stops any TS-Pico command, and the next one works
  normally.
- **No twenty-second hangs.** If a transfer goes wrong you get **T TS-Pico reset, try
  again** at once.
- **Swap SD cards freely.** New files show up without a restart; the TS-Pico runs without a
  card.
- **LOAD gives up when there's nothing to find.** One pass of the tape, then **R Tape
  loading error**, instead of an endless wait.
- **Flash slots are safer.** The TS-Pico refuses to overwrite the ROM the 2068 is running.

**One change to know.** TS-Pico commands are now SAVE commands: `SAVE "tpi:dir"`,
`SAVE "tpi:info"`. `LOAD "tpi:name.tap"` mounts a file.

The full list is in [What's New in the TS-Pico Since 1.1]({{ '/updates/whats-new-since-1-1/' | relative_url }}).

## Upgrade in fifteen minutes

1. Switch the TS 2068 off. Keep the TS-Pico's **P10 jumper** fitted.
2. Open the [web updater]({{ site.updater_url | relative_url }}) in Chrome or Edge, connect
   the TS-Pico by USB, and choose **Latest release**. On Windows you can run
   **TS-Pico-Updater.exe** from the
   [latest release](https://github.com/timex-sinclair-projects/tspico-firmware-build/releases/latest)
   instead.
3. Coming from 1.1, leave **Erase the Pico first** and **Update the TS-2068 ROM** ticked, and
   follow the steps. Afterwards `PRINT PEEK 101` gives **35**.
