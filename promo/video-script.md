# TS-Pico 2.3: the release video

A video for TS-Pico owners still on version 1.1: what 2.3 does, and how to upgrade.
About 15 minutes, shot on a TS-Pico v2 board. v3-only features (speech, the modem, WiFi
downloads, the joystick) are left for a v3 video.

**Revised 2026-11-10.** The tour gained a chapter (7, Looking inside: `LIST "file"`,
`CAT #` and the `x:` channel), a rename in chapter 4 and `RESTORE #` in chapter 6, so the
later chapters moved up one. Chapter 1 now leads with the keywords, as the manual does
(#367). The card label is added to the by-hand section, and the close mentions the Quick
Start and Quick Reference guides.

**Shoot after the next release.** The tour uses `COPY`/`MOVE` as two verbs, `LIST "file"`,
`RESTORE #`, `CAT #` and `x:`, all merged after v2.3.1 (#349, #405, #406). The web updater's
Latest release has to carry them, or a 1.1 owner following the video gets a 2068 that gives
reports where the video shows listings. The demo program is [`demo/`](demo/README.md); the flyer and web post say
the same things, so the video can point to them.

## Sources and shots

| Code | What | How |
|---|---|---|
| **TV** | The 2068's screen | VGA → USB capture, recorded on the Mac. Record at the capture's native size; scale up in the edit. |
| **CAM** | The desk: hands on the keyboard, the TS-Pico, the SD card, the cable | A camera or phone on a stand, over the shoulder or from the side. Soft light, no glare on the keys. |
| **MAC** | The web updater, the emulator, files on the Mac | polyCapture, one window at a time, at a normal zoom. |
| **EMU** | ZEsarUX with the TS-Pico | Pixel-perfect 2068 screens, for stills, title cards and the thumbnail. |
| **GFX** | Titles and lower thirds | Built in Final Cut Pro, in the flyer's look: the warm gray (#b4b1ab), the red/green/blue bars, Poppins. The manual cover's drawing (`tools/manual-pdf/img/ts2068-line.svg`) makes a good opening and closing card. |

**Rehearse in the emulator first.** `promo/demo/emu_tour.py` runs the whole tour in ZEsarUX
with the real firmware. Read the narration against it to time each chapter before you
record the real machine.

**Record the TV and the narration separately.** Run the tour on the 2068 in one take per
chapter, pressing keys at a steady pace, then record the narration to picture. Cut the TV
to fit the words, not the other way round: the tour waits for a key at every step, so
there's always a still frame to hold or trim.

## Before you shoot

- [ ] The 2068 is on the release after 2.3.1, from the web updater's Latest release:
      `PRINT PEEK 101` gives 35, and `SAVE "tpi:info"` shows the new firmware version.
- [ ] The demo card is set up as `demo/README.md` says: `card/TAP` as `TAP`, plus the repo's
      `SD card/help` folder.
- [ ] A Spectrum TAP on the card for the Spectrum-mode piece (`spectrum.tap` below), and a
      2068 game from the Software Library for the menu piece.
- [ ] One full practice take on the board. The first cut ran on a v2 board on 2026-10-17;
      the revised one has run only in the emulator. Watch chapter 7 (new), and 8 (`COPY`
      of the screen) and 11 (BREAK).
- [ ] Chapter 7's `x:` "info" shows the card's free space (a few hundred MB, not
      `Free 0 MB of 1`). Older firmware measured the Pico's flash; fixed 2026-11-10.
- [ ] At every "Start tape, then press any key." press **ENTER**, not SPACE.
- [ ] Note what's in the dock (`SAVE "tpi:info"`), so you can put it back after the
      cartridge piece, and the card's label (`SAVE "tpi:label"`), for the label piece.

## The script

Times are where each segment starts in the finished video.

### 1. Cold open (0:00)

| Picture | Sound |
|---|---|
| **TV**: the 2068 switching on. The start-up line `2026 TS-Pico ROM v2.3`. | (Keyboard and power sounds only.) |
| **TV**: someone types `CAT`. The color listing appears. | "This is a Timex Sinclair 2068, typing a command Timex built into it in 1983 and never finished." |
| **GFX**: title card on the gray, the cover drawing running in from the left. "TS-Pico 2.3". | "Version 2.3 of the TS-Pico makes it work. Let's see what else is new." |

### 2. Who this is for (0:20)

| Picture | Sound |
|---|---|
| **CAM**: the TS-Pico on the back of the 2068; the SD card going in. | "If you have a TS-Pico, the last software you installed was probably version 1.1. Version 2.3 replaces it: new firmware for the Pico, and a new ROM for the 2068." |
| **CAM** close on the board. Lower third: "Free update · About 15 minutes". | "It's free, it installs from a web browser, and it takes about fifteen minutes. We'll do that first, then take a tour." |

### 3. The upgrade (1:00)

Follow the user manual's Appendix A, A.2.

| Picture | Sound |
|---|---|
| **CAM**: the 2068 switched off; the USB cable into the Pico. | "Switch the 2068 off and connect the TS-Pico to your computer by USB." |
| **MAC**: the web updater in Chrome. **Latest release**. **Connect to TS-Pico**. | "Open the web updater in Chrome or Edge and choose Latest release. Connect, and the page reads what's installed." |
| **MAC**: the options. Zoom in on **Erase the Pico first** and **Update the TS-2068 ROM**, both ticked. | "Coming from 1.1, leave both of these ticked. Then Start." |
| **MAC** inset: "TS-Pico-Updater.exe" over a Windows screenshot, or a lower third only. | "On Windows, the TS-Pico Updater program does the same job. It's on the release page." |
| **CAM**: the P10 jumper, close up. | "When the page asks for the ROM step, check the P10 jumper is on." |
| **TV**: the 2068 switched on; `OUT 244,3`; `LOAD ""`; then DONE. Speed up the wait. | "Switch the 2068 on, type OUT 244,3 and LOAD "", and wait for DONE. The page follows along." |
| **MAC**: "The 2068 is off — continue"; the firmware step; **Done**. | "Switch off, continue, and the page finishes the job." |
| **CAM**: unplug USB; switch on. **TV**: `2026 TS-Pico ROM v2.3`. `PRINT PEEK 101` gives 35. | "Unplug the USB cable, switch on, and the start-up line says ROM 2.3." |

### 4. The tour (3:00)

**TV** throughout, except where noted. Each chapter starts on the tour's own title card.
Hold the card for a beat, then cut to the steps.

| Chapter (tour) | Picture | Sound |
|---|---|---|
| Intro | **CAM**: `LOAD "tpi:tour.tap"`, `LOAD ""` typed. **TV**: "Getting ready…" | "I've written a short program that walks through what's new. It's on the card as a tape: mount it, and load it." |
| 1. Welcome (3:15) | `PRINT PEEK 101` gives 35; the keywords step (`CAT COPY MOVE ERASE FORMAT LIST OPEN #`); `SAVE "tpi:info"`. | "First, the big change. The 2068 has disk words Timex never finished: CAT, COPY, MOVE, ERASE, FORMAT. They work now, on the SD card. The rest of the TS-Pico's commands are SAVE "tpi:" commands, and LOAD "tpi:" only mounts a file. Here's info: firmware, ROM and card at a glance." |
| 2. Listings in color (3:45) | `CAT`; `CAT "*.tap"`; `CAT "library"` stopping at `Scroll? (Y/n)`; **Y**. | "CAT lists the card in color, with its size and free space. It takes wildcards, and a long folder stops and asks before it scrolls." |
| 3. Folders (4:15) | `FORMAT "tour/"`, `MOVE TO "tour"`, `tpi:path`, `MOVE TO "-"`. | "FORMAT makes a folder. It never formats your card: it only makes new things. MOVE TO goes into a folder, and MOVE TO "-" comes back." |
| 4. Copies, renames and tapes (4:40) | `COPY "multi.tap" TO "tour"`; `FORMAT "songs.tap"`; `CAT "multi.tap"`; `CAT ""`; `MOVE "songs.tap" TO "tunes.tap"`; `CAT "*.tap"`. | "COPY copies files, and never overwrites one. FORMAT with a file name starts a new, empty tape. CAT with a tape's name lists the blocks inside it, without mounting it. And MOVE, with TO, renames." |
| 5. Single files with f: (5:20) | The picture drawn; `SAVE "f:title.scr" SCREEN$`; the screen wiped; `LOAD "f:title.scr" SCREEN$`. Then the two graphics. | "Until now, everything lived inside TAP files. Put f: in front of a name and LOAD and SAVE use a single file instead. A SCREEN$ is saved as the plain 6,912 bytes, so your computer's picture tools can open it." |
| | **MAC** insert (optional): `title.scr` opened in a viewer on the Mac. | |
| 6. Files as streams (6:10) | `OPEN #4,"f:notes.txt","w"`, `PRINT #4`, `CLOSE #4`; read back until 8 End of file, caught by `ON ERR`; `RESTORE #4` and the first line again; the high-score record file; the `d:` listing. | "Your own programs can read and write files now, with the 2068's OPEN #, PRINT # and INPUT #. Notes, logs, high-score tables. RESTORE # goes back to the start of a file. Record files jump straight to record 3 with TAB. And a d: stream reads a folder listing, one name at a time." |
| 7. Looking inside (7:00) | `LIST "notes.txt"`; `CAT #4;"/*.tap"` into `tapes.txt`, then `LIST "tapes.txt"`; `OPEN #4,"x:"`, `path` and `info` answered. | "LIST with a file name shows the file: text as text, anything else as a hex dump. CAT # writes a listing into a file instead of onto the screen. And an x: stream lets a program ask the TS-Pico what it knows: the folder it's in, what's mounted, the card's free space, the versions." |
| 8. The virtual printer (7:45) | `SAVE "tpi:picopt"`; `LPRINT`; `LLIST`; `COPY`; `SAVE "tpi:ts2040"`. | "No printer? After SAVE "tpi:picopt", LPRINT and LLIST go to text files on the card, and COPY saves the screen as a picture." |
| | **MAC** insert: the card on the Mac; the text file and the BMP from `/VLPRINT` and `/VSCREEN` opened. | "Here they are on the Mac. tpi:ts2040 sends printing back to a real printer." |
| 9. Mounting a tape (8:30) | `LOAD "tpi:pics.tap"`; `CAT ""` with the pointer; `LOAD "" CODE`; `CAT ""` again; `LOAD "" SCREEN$`. | "Tapes work as they always did, with a view inside. CAT "" lists the mounted tape and highlights the next block, so you can see where the tape pointer is." |
| 10. Reports, not hangs (9:10) | `LOAD "tpi:dir"` gives F; `SAVE "my game"` gives F; `ERASE "*.tap"` asking about each file: **Y**, **N**, **Y**; `CAT`. | "When something's wrong, you get a report straight away. LOAD "tpi:dir", the 1.1 habit, looks for a file called dir. A name with a space gives F, and nothing is written. And ERASE with a pattern asks about each file: N skips it and goes on to the next." |
| 11. BREAK is safe (9:55) | `CAT "/library"` at Scroll?; **CAM**: CAPS SHIFT + SPACE pressed; **TV**: D BREAK - CONT repeats; the next command works. | "BREAK works. CAPS SHIFT and SPACE stops any TS-Pico command, and the next one works normally. In 1.1, a stuck transfer meant a twenty-second wait. Now, if the TS-Pico has to give up, it says T, try again, at once." |
| 12. Help (10:25) | `SAVE "tpi:help"`; `SAVE "tpi:help cat"`. | "And if you forget any of this, there's help on the card: a page for every command." |
| 13. Tidying up (10:55) | The tour deleting its files; the end card. | "The tour cleans up after itself. A few things it can't do from inside a program, so let's do those by hand." |

### 5. By hand (11:15)

**The menu and the Commander.**

| Picture | Sound |
|---|---|
| **TV**: `SAVE "tpi:close"`, then `LOAD ""` with nothing mounted. The menu. | "LOAD "" with nothing mounted loads a menu: help, a file picker…" |
| **TV**: **F**, the TS-Pico Commander; the cursor keys through folders; **ENTER** on a game to mount it. | "…and the TS-Pico Commander, a file manager you drive with the cursor keys." |
| **TV** (optional): back to the menu, **T**: the one-line menu at the bottom of the screen. | "T gives a one-line menu for everyday commands, if you'd rather not type them." |

**Naming the card.**

| Picture | Sound |
|---|---|
| **TV**: `FORMAT ":GAMES"`, then `CAT`: GAMES on the card's line. | "A card can have a name. FORMAT with a colon sets the label your computer shows, and CAT shows it too." |
| **TV**: the label put back: `FORMAT ":"` + the card's old name (from the checklist), or `FORMAT ":"` if it had none. | (No narration; trim.) |

**Cartridges, and the D key.**

| Picture | Sound |
|---|---|
| **TV**: `SAVE "tpi:dock" CODE 2,10`, then `NEW`. Flight Simulator starts. | "Cartridges live in the TS-Pico's flash. Put one in the dock and type NEW, and the 2068 starts it, just like a real cartridge." |
| **CAM**: hand on **D**, then **TS Reset**. **TV**: the copyright message, BASIC. | "If you'd rather start in BASIC, hold D while it starts, until the copyright message appears." |
| **TV**: `SAVE "tpi:dock" CODE 2,0`. | "And this puts the Spectrum ROM back in the dock." |

**ZX Spectrum mode.** (Leave this until last: it ends the session.)

| Picture | Sound |
|---|---|
| **TV**: `LOAD "tpi:spectrum.tap"`, `SAVE "tpi:zx48"`, `OUT 244,3`. The © 1982 Sinclair Research screen. | "The TS-Pico also turns the 2068 into a ZX Spectrum, with LOAD and SAVE on the SD card." |
| **TV**: `SAVE "tpi:dir"` on the Spectrum; `LOAD ""`; a game running. | "And now you can list the folder and mount another tape without leaving Spectrum mode." |
| **TV**: `OUT 244,0`, then `OUT 14,14`. | "OUT 244,0 and OUT 14,14 bring the 2068 back." |

### 6. Something to load (13:15)

| Picture | Sound |
|---|---|
| **MAC**: the archive.org page for the TS-2068 Software Library; the zip; the folders on the card. | "A TS-Pico is only as good as what's on the card, so we've made one: 1,327 TS-2068 programs from the Timex Sinclair Software Archive, every one test-loaded with the real TS-Pico firmware, in folders, with short names you can type." |
| **TV**: `MOVE TO "games"`, `CAT`, a game mounted and loaded. | "It's a free download from archive.org, and from the web updater's SD card section." |

### 7. No 2068 on your desk? (14:00)

| Picture | Sound |
|---|---|
| **MAC**: ZEsarUX with the TS-Pico: `CAT` in the emulator window, `pico_host` in a terminal beside it. | "No hardware with you? The real TS-Pico firmware also runs on your computer, next to the ZEsarUX and Fuse emulators. Their 2068 then has a TS-Pico, with a folder for its SD card." |
| **MAC**: the emulator guide page on the site. | "Much of this release was tested that way, and it's handy for writing programs that use the TS-Pico. The guide is on the website." |

### 8. Close (14:45)

| Picture | Sound |
|---|---|
| **GFX**: the flyer's back page, or a card with the three links: web updater, what's new, the manuals. | "Everything's on the TS-Pico website: the web updater, the full list of what's new, the user manual as a PDF, and a flyer you can print for your user group." |
| **GFX**: the Quick Start booklet and the Quick Reference card, side by side. | "If the manual's too much, there's an eight-page Quick Start, and a Quick Reference card in the style of the one that came with the 2068." |
| **CAM**: the 2068 with the TS-Pico, the drawing card fading in. | "TS-Pico 2.3. It's free, it takes about fifteen minutes, and your 2068 finally gets its disk commands." |

## Editing notes

- **The TV picture.** The 2068's screen is small text on a big border. For the tour, crop
  to the paper plus a little border, and scale up so the text reads on a phone. Keep the
  colors as captured; don't sharpen.
- **Speed.** Speed up only waits that carry no information (the ROM step's DONE, a long
  CAT scrolling). Keep typing at real speed: people want to see what to type.
- **Lower thirds** for every command the narration names, so viewers can pause and copy it.
- **Chapter titles.** The tour's own title cards already show "Chapter n of 12". Use them;
  add a GFX title only for the sections outside the tour.
- **Thumbnail.** An EMU still of the color `CAT` beside the cover drawing, with
  "TS-Pico 2.3" and "CAT · COPY · MOVE · ERASE · FORMAT".

## YouTube description (draft)

> TS-Pico 2.3 is a free update for the TS-Pico mass storage interface for the Timex
> Sinclair 2068. If you're on version 1.1, this is what you get, and how to install it in
> about fifteen minutes.
>
> Web updater: https://timex-sinclair-projects.github.io/tspico-firmware-build/updater/
> What's new since 1.1: https://timex-sinclair-projects.github.io/tspico-firmware-build/updates/whats-new-since-1-1/
> User manual and flyer: https://timex-sinclair-projects.github.io/tspico-firmware-build/
> Source: https://github.com/timex-sinclair-projects/tspico-firmware-build
>
> 0:00 TS-Pico 2.3
> 0:20 Who it's for
> 1:00 Upgrading from 1.1
> 3:00 The tour: CAT, folders, copies and renames
> 5:20 Single files and streams
> 7:00 LIST, CAT # and asking the TS-Pico
> 7:45 The virtual printer
> 8:30 Tapes, reports and BREAK
> 10:25 Help on the card
> 11:15 The menu, the card's name, cartridges and Spectrum mode
> 13:15 1,327 programs to load
> 14:00 Try it in an emulator
> 14:45 Where to get it

Update the times from the finished edit. YouTube makes chapters from these lines: the first
must be 0:00, and there need to be at least three, each at least 10 seconds long.
