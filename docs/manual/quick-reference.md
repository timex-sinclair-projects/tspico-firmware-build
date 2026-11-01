# TS-Pico Quick Reference Guide

<!-- The commands at a glance, after the Quick Reference Guide that came with the Timex Sinclair
     2068: printed by tools/manual-pdf/make.sh on both sides of a letter sheet and folded in
     three. Each "panel" comment starts one panel of the card (quick.py places them; the cover is
     drawn there); quick.py fails the build if a panel runs over, so a line added here may have
     to push another out. Everything here comes from the User Manual (user-manual.md): when it
     changes a command, change it here too. -->

<!-- panel: inside-left -->

## Reference guide notations and format conventions

This guide shows the TS-Pico's commands in the same scheme as the 2068's own Quick Reference
Guide:

**[ ]** Brackets enclose items that are optional. Brackets do not appear in the actual command.

**{ | }** Braces enclose a choice of one of the items. Braces do not appear in the command.

***Italics*** are generic terms: you supply the actual name or value.

**UPPERCASE** Keywords, and the letters `tpi:`, appear exactly as shown. In names and `tpi:`
commands, upper or lower case doesn't matter.

## How TS-Pico commands work

**Commands** are a SAVE of a name that starts with `tpi:`. Nothing is saved: the TS-Pico
carries out the command.<br>
Format: <code>SAVE "tpi:<i>command</i> [<i>argument</i>]" [CODE <i>a</i>,<i>b</i>]</code>

**Mounting** is a LOAD of a name that starts with `tpi:`. The file becomes the "tape" that
`LOAD ""` reads from.<br>
Format: <code>LOAD "tpi:{<i>name</i> | <i>nn</i>}"</code>

**31 characters** The whole name, `tpi:` included, must fit in 31. A longer one gives
**C Nonsense in BASIC** when it runs.

**CODE *a*,*b*** passes the command two numbers. Leaving it off is the same as `CODE 0,0`.

**Keywords** `CAT`, `COPY`, `MOVE`, `ERASE`, `FORMAT` and `LIST` work on the SD card too, with
no `tpi:`.

## Generic terms and definitions

***a*, *b*** The two numbers after `CODE`.

**current folder** The folder `CAT` lists and new files go into. `SAVE "tpi:path"` shows it.

***folder*** A folder name or path: `games`, `games/arcade`, `/games`, `..`, `/`, `-`.

**index number** The three-digit number `CAT` shows beside each file you can mount.

<!-- v2 -->
***mem*** Where a slot is: 1 = RAM, 2 = Flash.
<!-- /v2 -->
<!-- v3 -->
***mem*** Where a slot is: 1 = RAM, 2 = Flash, 3 = SD card.
<!-- /v3 -->

**mount** Make a file the TS-Pico's "tape". One file is mounted at a time.

***name*** A file name. Save with letters, digits, `-` and `_` only.

***nn*** An index number, at least two digits: `03`, `12`.

***pattern*** A name with `*` (any run of characters) or `?` (any one character).

**root** The card's `TAP` folder, the top folder: `/`.

***slot*** A ROM or cartridge slot, 0 to 15.

**TAP** A recording of a cassette: a series of blocks, as on tape.

**tape pointer** The block in the mounted TAP the next LOAD starts from.

**verbose** The TS-Pico's messages, which say what a command did and why one failed. Off at
switch-on: `SAVE "tpi:verbose" CODE 1,1` turns them on, `CODE 1,0` off.

<!-- panel: flap -->

## Switching on

1. Switch the 2068 off before you fit or remove the TS-Pico.
<!-- v2 -->
2. On an expansion bus, set the BUSISO bypass for the TS-Pico's slot. Keep P10 fitted.
<!-- /v2 -->
<!-- v3 -->
2. On an expansion bus, set the BUSISO bypass for the TS-Pico's slot.
<!-- /v3 -->
3. Put the micro SD card in, contacts first, and switch on.
4. Press ENTER and type `CAT`: you see the card's `TAP` folder.

## The light

| What you see | What it means |
|---|---|
| A short flash every couple of seconds | Idle |
| Steady on | Busy with a command |
| Flickering | Copying a file you've mounted |
| A burst of fast blinks | Something went wrong |
| Two short flashes every couple of seconds | No SD card: push it back in, try again |

## Report codes

| Code | From the TS-Pico, it means |
|---|---|
| **0** OK | Done |
| **4** Out of memory | No room to build a command |
| **6** Number too big | A file index out of range |
| **A** Invalid argument | A `CODE a,b` or argument the command doesn't accept |
| **C** Nonsense in BASIC | An unknown `tpi:` word, extra words, or a name over 31 characters |
| **D** BREAK - CONT repeats | You pressed BREAK, or answered N to "Replace?" |
| **F** Invalid file name | Not found, not allowed, or already exists |
| **J** Invalid I/O device | The TS-Pico didn't answer, or the SD card won't mount |
| **Q** Parameter error | Can't be done now: mounted, not empty, wrong type or mode |
| **R** Tape loading error | Nothing on the tape matched a LOAD, or damaged data |
| **T** TS-Pico reset, try again | The TS-Pico reset a transfer that went wrong |

## Keys at a prompt

**Scroll? (Y/n)** Y or ENTER for the next page, **1**-**9** for that many lines, N to stop.

**Pick-from-a-list menus** (`tpi:cd`, `tpi:idir`) **0**-**9**, then **Q W E R T Y** for 10
to 15, to choose; B goes back a page, N quits, any other key goes on.

**Replace *name*? (Y/N)** Y replaces the file; any other key cancels with **D**.

**Start tape, then press any key.** Press ENTER, not SPACE: SPACE is BREAK.

<!-- panel: inside-middle -->

## Files and folders

**CAT** Lists a folder: folders first, in `<angle brackets>`, then files, each one you can
mount with its index number.<br>
Format: <code>CAT ["{<i>folder</i> | <i>pattern</i> | <i>name</i>.tap}"]</code>

| Example | Lists |
|---|---|
| `CAT` | The current folder |
| `CAT "games"` | Another folder, without going there |
| `CAT "*.tap"` | Files matching a pattern |
| `CAT "frogger.tap"` | The blocks inside a TAP |

**MOVE TO** Changes the current folder. `MOVE TO ""` picks one from a menu.<br>
Format: <code>MOVE TO "<i>folder</i>"</code>

| Folder | Is |
|---|---|
| `..` | The folder above |
| `/` | The root, the card's `TAP` folder |
| `-` | The folder you were in before |
| `/games` | A path from the root |

**COPY** Copies a file, or every match of a pattern into a folder. Never overwrites.<br>
Format: <code>COPY "{<i>name</i> | <i>pattern</i>}" TO "{<i>name</i> | <i>folder</i>}"</code>

**MOVE** The same shape, but renames a file or folder, or moves it into a folder.

**LIST** <code>"<i>name</i>"</code> shows a file: text as it is, anything else in hex.

**ERASE** Deletes a file without asking; with a pattern, asks about each one. A slash
erases an empty folder.<br>
Format: <code>ERASE "{<i>name</i> | <i>pattern</i> | <i>folder</i>/}"</code>

**FORMAT** Makes a new, empty TAP (mounted, with append on) or folder, or names the card.
Never formats the card or replaces a file.<br>
Format: <code>FORMAT "{<i>name</i>.tap | <i>folder</i>/ | :<i>label</i>}"</code>

| Command | Does |
|---|---|
| `SAVE "tpi:dir [`*`pattern`*`]"` | The same as `CAT` |
| `SAVE "tpi:dir" CODE 2,0` | Every file's full name and number |
| `SAVE "tpi:cd `*`folder`*`"` | The same as `MOVE TO` |
| `SAVE "tpi:cd"` | Pick a folder from a menu |
| `SAVE "tpi:path"` | Show the current folder |
| `SAVE "tpi:md `*`folder`*`"` | Make a folder |
| `SAVE "tpi:rm `*`name`*`"` | Remove a file or an empty folder, asking first |
| `SAVE "tpi:label [`*`name`*`]"` | Show or set the card's label |

## Native files: f:

A single file on the card, not a TAP: any SAVE or LOAD works with it, and the mounted TAP is
left alone. Replacing a file asks first.<br>
Format: <code>{SAVE | LOAD | VERIFY | MERGE} "f:<i>name</i>" [...]</code>

```
SAVE "f:advent.bas" LINE 10
LOAD "f:title.scr" SCREEN$
SAVE "f:scores.dat" DATA s()
```

<!-- panel: inside-right -->

## Mounting and the tape

**Mount** a TAP from the current folder, by name or index number. LOAD, VERIFY and MERGE then
read it from the tape pointer, going round once; a LOAD that finds nothing gives **R**.<br>
Format: <code>LOAD "tpi:{<i>name</i> | <i>nn</i>}"</code>

| Command | Does |
|---|---|
| `LOAD "tpi:frogger.tap"` | Mount by name; `*` and `?` match |
| `LOAD "tpi:03"` | Mount file number 003 |
| `SAVE "tpi:idir"` | Pick a file to mount from a menu |
| `CAT ""` | The blocks in the mounted TAP; `>` is the tape pointer |
| `SAVE "tpi:ffw" [CODE `*`m`*`,`*`n`*`]` | Wind on *n* blocks (*m* 0), *n* files (*m* 2); *m* 1 or 3 also shows the tape |
| `SAVE "tpi:rew" [CODE `*`m`*`,`*`n`*`]` | Wind back the same way |
| `SAVE "tpi:close"` | Unmount |
| `SAVE "tpi:automount `*`name`*`"` | Mount this TAP at switch-on; `off` to stop |

**Nothing mounted?** `LOAD ""` loads the TS-Pico's menu: **H** help, **C** help on a command,
**P** pick a file and load it, **F** the TS-Pico Commander, **I** TS-Pico information and ROM
version, **T** a one-line `tpi:` menu, **V** Pico Video settings, **Q** quit.

## Loading and saving

**LOAD**, **VERIFY**, **MERGE** As with tape, from the mounted TAP.<br>
Format: <code>LOAD "[<i>name</i>]" [{CODE | SCREEN$ | DATA <i>var</i>()}]</code>

**SAVE** Writes a new *name*`.tap` in the current folder, replacing one of that name without
asking. Names: letters, digits, `-` and `_`.<br>
Format: <code>SAVE "<i>name</i>" [{LINE <i>n</i> | CODE <i>start</i>,<i>length</i> | SCREEN$ | DATA <i>var</i>()}]</code>

**Append** adds every SAVE to the end of the mounted TAP instead. Mounting a file turns it
off.<br>
Format: <code>SAVE "tpi:append [{on | off}]"</code>

| Command | Does |
|---|---|
| `FORMAT "`*`name`*`.tap"` | A new TAP, mounted, with append on |
| `SAVE "tpi:tape"` | LOAD and SAVE use the cassette recorder |
| `SAVE "tpi:sdcard"` | Back to the TS-Pico (as at switch-on) |

## Help and status

| Command | Does |
|---|---|
| `SAVE "tpi:help [`*`word`*`]"` | Help on the commands, or on one word |
| `SAVE "tpi:info"` | Versions, card, slots, mounted file, folder |
| `SAVE "tpi:verbose" CODE 1,{1 \| 0}` | Messages on or off |
| `SAVE "tpi:log"` | The TS-Pico's log |

<!-- panel: back -->

## The virtual printer

| Command | Does |
|---|---|
| `SAVE "tpi:picopt"` | Printing goes to the card |
| `SAVE "tpi:ts2040"` | Back to the TS 2040 printer |
| `SAVE "tpi:clprint"` | Finish the printout file |

With `picopt`, LPRINT and LLIST go to `/VLPRINT/PRN0001.TXT` and on; COPY saves the screen as
`/VSCREEN/SCR0001.BMP`.

## ROM slots and cartridges

**BOOT** is the ROM the 2068 starts from; **DOCK** is the cartridge bank. A BOOT choice lasts
one start; DOCK resets at switch-on.

| Command | Does |
|---|---|
| `SAVE "tpi:boot"` | Show the BOOT slot |
<!-- v2 -->
| `SAVE "tpi:boot" CODE `*`mem`*`,`*`slot`*`: NEW` | Start the 2068 from *slot* |
<!-- /v2 -->
<!-- v3 -->
| `SAVE "tpi:boot" CODE `*`mem`*`,`*`slot`* | Restart the 2068 from *slot* |
<!-- /v3 -->
| `SAVE "tpi:dock" CODE `*`mem`*`,`*`slot`* | Put *slot* in the dock |
| `SAVE "tpi:dock" CODE 0,2` | Swap back to the previous dock |
| `LOAD "tpi:`*`name`*`.dck"`, `LOAD ""` | Put a cartridge, ROM or BIN into a slot |

**Run a cartridge** in the dock: `NEW` or **TS Reset**. Hold **D** while the 2068 starts to
skip it.

## ZX Spectrum mode

1. Mount a TAP of Spectrum programs: `LOAD "tpi:spectrum.tap"`.
2. `SAVE "tpi:zx48"`, then `OUT 244,3`.
3. `LOAD ""` loads; `SAVE "name"` saves a TAP; `SAVE "tpi:dir"` lists.
4. Back to the 2068: `OUT 244,0`, then `OUT 14,14`.

A game that won't load: `SAVE "tpi:zx48" CODE 0,2` for the compatible loader.

## Where to find more

The **TS-Pico User Manual** explains every command and report, with examples, and the
**Quick Start Guide** takes you from the box to a running program. Both are on the website:

**timex-sinclair-projects.github.io/tspico-firmware-build**
