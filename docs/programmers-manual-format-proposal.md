# Programmer's Manual: a format proposal

**Status:** accepted 2026-10-18, pilot under way. Decided: one book; Chapter 4 keeps excerpts
and the whole `picolib.asm` goes in an appendix (Appendix G); start with a pilot of R5 and R6.
The pilot also has R1. Questions 3 and 4 in section 8 are still open; the pilot groups entries
by job.

**The pilot changed one thing in the plan below:** R6 also holds the EXROM routines outside the
BIOS table (`SYNC_WRITE`, `SYNC_WAIT`, `STATUS_TO_REPORT`) and how to call through 03FCh, so R7
is system variables only.

**The short version.** Split the Programmer's Manual into two voices that never share a page:

- **Narrative chapters** (Parts I and II) explain how the TS-Pico works and why, in the voice of
  *De Re Atari* and the semi-tutorial chapters of the *Commodore 64 Programmer's Reference
  Guide*. They show short excerpts of code and link to the reference for the details.
- **A Reference part** (Part III) lists every routine, port, byte map, status code and helper a
  programmer can use. Each one gets an entry in a fixed format: name, purpose, call, every
  input and output, the formulas behind it, then a description, numbered steps for using it, an
  example, and cross-references. The format is a cross between the C64's KERNAL entries and
  the Amiga's autodocs.

Inside Macintosh did this in every chapter: concepts first, then "Using the Manager," then the
routines, then a summary. We do it at the level of the whole book, because our Parts I and II
already read well as narrative and the reference material is spread through them.

---

## 1. What we looked at

| Manual | What it does well | What we take |
|---|---|---|
| **Commodore 64 Programmer's Reference Guide** (1982) | The KERNAL chapter opens with a one-page "how to use the KERNAL" (set up, call, handle the error), then a quick-list table of all 39 routines with their addresses, then one page per routine: *Purpose, Call address, Communication registers, Preparatory routines, Error returns, Stack requirements, Registers affected*, then *Description*, *How to Use* as numbered steps, and *Example*. The introduction has a page on syntax notation. | The entry fields, almost exactly. The quick-list table before the entries. The numbered "How to use" steps. The notation page. The pull-out quick reference card at the back. |
| **De Re Atari** (Atari, 1982) | Written by the people who built the machine. Each chapter takes one subsystem (display lists, player-missile graphics, the OS) and explains how it works and *why it was designed that way*, so that you can do things the designers didn't plan for. Confident, specific, opinionated. | The voice of Parts I and II: explain the design, give the reasons, and admit the traps. (atariarchives.org now puts a human check in front of the text, so this summary is from memory, not a fresh reading.) |
| **Inside Macintosh** (Apple, 1985 on) | Every chapter: "About This Chapter," the concepts, "Using the X Manager," the "X Manager Routines" one by one, and a "Summary of the X Manager" that lists constants, types, routines and result codes. Pascal is the main interface; an "assembly-language note" gives the registers. | Narrative before reference, with links in both directions. A summary table at the end of each reference chapter. The idea of a second-language note: our entries can show the BASIC way to reach a routine next to the machine-code way. |
| **Amiga ROM Kernel Reference Manual** (Commodore, 1985 on) | Two books: *Libraries* (narrative and examples) and *Includes and Autodocs* (reference). Every autodoc has the same headings: NAME (one line), SYNOPSIS (the call, with registers), FUNCTION, INPUTS, RESULT, EXAMPLE, NOTES, BUGS, SEE ALSO. The style guide wants tested examples and the range of every input. | The **BUGS** and **SEE ALSO** headings. The rule that an example must be tested, and retested when edited. INPUTS gives the valid range of each input, and says what happens outside it. |
| **ZX Spectrum +3 manual, +3DOS chapter** (Amstrad, 1987) | The closest precedent in Z80 land, and our readers will have seen it: each routine has *Entry conditions* and *Exit conditions*, split into "if OK," "otherwise" and "always" (the registers corrupted). | "If OK / Otherwise / Always" for exits. It's the clearest way to say what carry means. (+3DOS sets carry for *success*; we set it for *failure*, like the C64. Our notation page must say so.) |
| **BBC Micro Advanced User Guide** (1983) | Each OSBYTE and OSWORD call lists its registers *on entry* and *on exit*. | The same idea as +3DOS. We haven't checked the book's exact layout. |
| ***Mapping the Commodore 64*** **and *Mapping the Atari*** (COMPUTE!, 1983–84) | A reference arranged by address: each memory location or register gets an entry with a narrative of what it does and how to use it from BASIC. | The format for ports, system variables and ROM addresses (§4.3). |
| **Unix man pages; the Python library docs** | SYNOPSIS, DESCRIPTION, RETURN VALUE, ERRORS, EXAMPLES, SEE ALSO. Python adds the signature with defaults, and "Raises." | The format for the MicroPython helpers of Part II (§4.6). |
| **Diátaxis** (Daniele Procida) | A framework that sorts documentation by what the reader needs: tutorials, how-to guides, reference and explanation. | The reason for the split. Our narrative chapters are tutorial and explanation; Part III is reference. Mixing them is what makes Chapter 4 hard to use as either. |

---

## 2. What's wrong with the manual as it stands

The manual is good narrative. Its trouble is that the reference material is spread through it,
so an outside developer who wants to know "what does `GET_DATA` leave in DE?" has to read a
chapter to find out.

- **Chapter 4** is a tour of `picolib.asm` with the full source of every routine. It reads as
  narrative, but it's the only place the routines are documented, and it never says which
  registers each one corrupts or how much stack it uses.
- **The Pico BIOS** (Chapter 8) is a single table whose "What it does" column carries entry,
  exit and errors in one sentence.
- **The ports and status byte** (Chapter 2), the **pre-header** and **body** byte maps
  (Chapter 3) and the **status codes** (Appendix A) are all reference tables, in three places.
- **The firmware helpers** are in two tables (Chapter 11 and Appendix C) that don't agree:
  Appendix C's `SEND_MSG(msg, msg1, st, force=False)` is `forceDisplay=False` in the source.
- **Formulas** are in the prose ("13 × 65 536 polls of about 86 T"), never written out.
- **Appendix F** (channel code) is a narrative chapter in all but name.

---

## 3. The proposed book

```
Front matter
    About this manual (what's tested and how)
    How to use this book: the two parts and the reference, and the notation (§4.1)

PART I: TALKING TO THE TS-PICO FROM THE 2068              narrative
    1  Before You Start
    2  Two Computers and a Cable          (was 2: the ports, auto-busy, and why)
    3  The Conversation                   (was 3: a transaction, told as a story)
    4  A Machine-Code Toolkit             (was 4: what picolib does and why;
                                           excerpts only, full detail in R5)
    5  Worked Examples                    (as now)
    6  Files as Streams                   (as now)
    7  Other Commands, and What Not to Send
    8  The ROM's Pico BIOS                (the bank switch and its dangers;
                                           the routines themselves move to R6)
    9  Writing Channel Code for the 2068  (was Appendix F)
   10  Rules of the Road for Z80 Programs

PART II: PROGRAMMING THE TS-PICO                           narrative
   11–17  as now (Inside the Firmware ... Rules of the Road for Pico Code)

PART III: REFERENCE                                        API style
    R1  Notation and conventions          (once, here; the front matter links to it)
    R2  Ports and the status byte         (register-map entries, §4.3)
    R3  The transaction, byte by byte     (byte-map entries, §4.4)
    R4  Answers: status codes, reports, response functions 81h/86h/88h, data answers
    R5  picolib routines                  (routine entries, §4.2)
    R6  The Pico BIOS                     (routine entries, by address)
    R7  ROM entry points and system variables
    R8  The channels f: and d:            (OPEN modes, TAB, records, errors)
    R9  The external-command contract     (EXT_SA_FUNCT, the handler signature)
    R10 Firmware helpers                  (Python entries, §4.6)

APPENDICES
    A  Quick reference card               (two pages, printable: the C64's card)
    B  Glossary
    C  The example files
    D  Further reading in the repository
    Index
```

**Each reference chapter opens the same way:** two or three sentences that say what's in it
and which narrative chapter explains the background, then a **quick list** (a table of every
entry, with its address or signature and one line on what it does), then the entries. It ends
with a **summary**, the way Inside Macintosh does it: every constant and code in the chapter
in one table.

**Order inside a reference chapter:** grouped by job, not alphabetical (waiting, sending,
reading, errors). There are at most a dozen entries in a chapter, so the quick list does the
alphabetical job. The index at the back covers everything.

**Numbering:** C64-style, so entries can be cited: R5.3 is `WAIT_READY`. Narrative chapters
cite them as "(R5.3)".

### The rule between the two voices

- A narrative chapter **never** has an entry's fact table in it. It explains the idea, shows
  the few lines of code that make it work, and says "→ R5.3" for the rest.
- A reference entry **never** teaches. Its Description is one or two paragraphs on what the
  routine does; for *why*, it links back: "Background: Chapter 3."
- A fact lives in one place. If Chapter 2 needs the status values, it shows them, and R2 is the
  one that's complete.

---

## 4. Entry formats

### 4.1 Notation (R1)

One page, like the C64's "How to use this reference guide":

- **Numbers.** Hex has an `h` suffix (`0Fh`), as the ROM listings do. Decimal is plain. A value
  BASIC uses gets both: port 15 (0Fh).
- **Carry.** In this book, **carry set means failure**, with the error code in A, and carry
  clear means success. (+3DOS uses the opposite convention.)
- **Error codes** are the bytes `RST 8` takes: 12h for J, 0Ch for D. R4 has the full table.
- **Registers** are listed as *kept* (the same on exit) or *corrupt* (anything). A register not
  mentioned is kept.
- **T-states and time.** Times are worked out at 3.5 MHz. A formula names every symbol and its
  unit (§4.5).
- **Python signatures** are written as in the source, with defaults.
- **`< >`** marks a value you supply; **`[ ]`** an optional part; **`|`** a choice.

### 4.2 A Z80 routine (R5, R6)

**The fields:**

| Field | What it says | From |
|---|---|---|
| Name and number | `R5.3 WAIT_READY` | — |
| Purpose | one line | C64 |
| Call | `call WAIT_READY`, or the address and how to reach it (bank, `DI`) | C64, +3DOS |
| On entry | each register or variable it reads, with the valid range | +3DOS, Amiga INPUTS |
| On exit: if OK | flags and registers on success | +3DOS |
| On exit: if it fails | flags, A, and **each** error code with what caused it | +3DOS, C64 "Error returns" |
| Always | registers corrupt; registers kept | +3DOS, C64 "Registers affected" |
| Calls first | routines that must run before this one, if any | C64 "Preparatory routines" |
| Stack | bytes used, counting its own return address | C64 |
| Time | how long it takes or how long it can wait, with the formula | ours |
| Description | what it does, in one or two paragraphs | C64, Amiga FUNCTION |
| How to use | numbered steps | C64 |
| Example | a tested fragment, with the name of the file it's from | C64, Amiga |
| Notes | traps | Amiga NOTES |
| Bugs | known faults and the issue that tracks them | Amiga BUGS |
| See also | related entries, and the narrative chapter | Amiga SEE ALSO |

Empty fields are left out, except **Always**, which says "nothing" when nothing is corrupt.

**A sample, written from `picolib.asm`:**

> #### R5.3 WAIT_READY
>
> | | |
> |---|---|
> | **Purpose** | Wait for the Pico to set READY, for up to about 20 seconds, watching for BREAK. |
> | **Call** | `call WAIT_READY` |
> | **On entry** | nothing |
> | **If OK** | carry clear. The Pico has an answer ready, or is ready for your next bytes. |
> | **If it fails** | carry set, and A is: **12h** (J) the Pico didn't answer within the timeout; **1Ch** (T) the Pico gave up on the transaction by itself (RECOVERED); **0Ch** (D) the user pressed BREAK. On BREAK the routine has already sent a SYNC and waited for IDLE, so the link is ready for the next command. |
> | **Always** | AF corrupt (A is not the status byte, even on success). BC, DE, HL, IX, IY kept. |
> | **Stack** | 8 bytes |
> | **Time** | Up to *t* = *N* × 65 536 × *T*<sub>poll</sub> / *f* = 13 × 65 536 × 86 / 3 500 000 ≈ **21 s**, where *N* = 13 is the count in C, *T*<sub>poll</sub> ≈ 86 T-states is one pass of the loop, and *f* is the clock. The ROM's own wait is about the same. |
>
> **Description.** Reads the status port (0Fh) until bit 6, READY, is set. Between reads it
> scans the keyboard row with SPACE and the row with CAPS SHIFT; with both down it sends a
> SYNC (`OUT (0Fh),03h`) to abort the command and fails with D. Once READY is set it tests
> RECOVERED, which is only meaningful when READY is set.
>
> **How to use**
>
> 1. Send something to the Pico: a pre-header, a body, or a key.
> 2. `call WAIT_READY`.
> 3. On carry, stop, or `jp RAISE` to give BASIC the report in A.
> 4. On no carry, read the answer from port 0Eh.
>
> **Example** (illustrative; the real entry takes its example from a tested file)
>
> ```asm
>         call SEND_CMD           ; R5.5
>         jp c,RAISE
>         call WAIT_READY
>         jp c,RAISE              ; J, T or D, as BASIC would report it
>         in a,(PORT_DATA)        ; the status byte
> ```
>
> **Notes.** Don't use it to wait for IDLE between commands: that's `WAIT_IDLE` (R5.1), which
> gives up after one second and doesn't watch for BREAK.
>
> **See also.** R5.1 WAIT_IDLE, R5.2 PICO_SYNC, R6.7 WF_NPH (the ROM's version, which returns
> 02h on a timeout), R2.2 the status byte. Background: Chapter 2, "Auto-busy."

(No example file calls `WAIT_READY` on its own yet, so the real entry needs one added to a file
that `test_examples.py` runs. The Amiga style guide's rule: every example is tested, and
retested when edited.)

**The same format for a BIOS routine,** where the call is the hard part:

> #### R6.7 WF_NPH (EXROM 184Ch)
>
> | | |
> |---|---|
> | **Purpose** | Wait for READY, up to about 20 s. Never raises a report. |
> | **Call** | From RAM: `ld hl,184Ch`, `di`, `call 03FCh`, `ei` (R7.1). From the EXROM: `call 184Ch`. |
> | **If OK** | carry clear |
> | **If it fails** | carry set, and A is **02h** (timeout), **0Ch** (BREAK; the Pico has been told) or **1Ch** (the Pico reset the transaction) |
> | **Always** | IX corrupt when called through 03FCh. *Other registers: to check against the ROM source before this goes in the book.* |
> | **ROMs** | 1.1 to 2.3, same address |
>
> ...

A field we can't fill from the code says so, in italics, rather than guessing. That follows
`docs/reference/`'s rule: facts from the code, inferences marked.

### 4.3 A port, register or system variable (R2, R7)

The *Mapping the Commodore 64* form: the address in both bases, then a bit table, then what
it's for and how to use it from BASIC and from machine code.

> #### R2.2 Port 15 (0Fh): status, and SYNC
>
> | | |
> |---|---|
> | **Read** | the status byte |
> | **Write** | any value: SYNC. Abandons any transaction and empties both FIFOs. The ROM writes 03h. |
> | **Auto-busy** | any `OUT` to port 14 or 15 makes this port read 00h until the Pico has dealt with the byte |
>
> | Bit | Name | 1 means | 0 means |
> |---|---|---|---|
> | 7 | — | reserved | |
> | 6 | READY | the Pico has an answer, or is ready for more | busy |
> | 5–4 | — | reserved | |
> | 3 | IDLE | no transaction is open | a command is in progress |
> | 2 | RECOVERED | normal | the Pico abandoned the last transaction (Report T). Test only when READY is 1. |
> | 1–0 | — | reserved | |
>
> | Value | You'll see it when |
> |---|---|
> | FFh | ready and idle |
> | F7h | ready, mid-command |
> | FBh | ready and idle after a RECOVERED |
> | 00h | busy |
>
> **From BASIC:** `PRINT IN 15`. **From machine code:** `in a,(0Fh)`.
> **See also:** R2.1 port 14, R5.1 WAIT_IDLE, R5.3 WAIT_READY. Background: Chapter 2.

### 4.4 A byte map (R3, R4)

Packets, the pre-header, the body and the response functions: a strip diagram first, so the
shape is clear at a glance, then a table with one row per byte.

> #### R3.2 The pre-header
>
> ```
>  0    1    2    3    4    5    6    7    8    9
> ┌────┬────┬────┬─────────┬─────────┬─────────┬─────┐
> │'B' │kind│ROM │ CODE a  │ CODE b  │ length  │ XOR │
> │42h │ 0  │23h │ lo   hi │ lo   hi │ lo   hi │0..8 │
> └────┴────┴────┴─────────┴─────────┴─────────┴─────┘
> ```
>
> | Byte | Name | Value | Notes |
> |---|---|---|---|
> | 0 | type | `'B'` (42h) | ... |
> | ... | | | |
>
> **Checksum:** *X* = *b*<sub>0</sub> ⊕ *b*<sub>1</sub> ⊕ … ⊕ *b*<sub>8</sub> (XOR of bytes 0 to 8).
> The Pico doesn't check this one.

### 4.5 Formulas

Wherever a number comes from arithmetic, the entry shows the arithmetic, in a **Time** or
**Formula** field:

1. the formula, in symbols;
2. what each symbol is, with its unit;
3. the numbers put in, and the answer, rounded the way the prose rounds it.

The ones the book needs, so far:

| What | Formula |
|---|---|
| a `DJNZ` delay of *n* | *T* = 13(*n* − 1) + 8 T-states, plus the `LD B,n` (7 T) |
| T-states to time | *t* = *T* / *f*, *f* = 3.5 MHz, so 1 µs ≈ 3.5 T |
| a polling timeout | *t* = *passes* × *T*<sub>pass</sub> / *f* |
| the XOR checksums | *X* = *b*<sub>first</sub> ⊕ … ⊕ *b*<sub>last</sub>, with the range named |
| the TX/RX pace | bytes per second = *f* / *T*<sub>per byte</sub> |

On the website, pandoc's `--mathjax` or plain HTML sub/superscripts both work. We'd use plain
HTML: it renders on GitHub too, and these formulas don't need more.

### 4.6 A Python helper (R9, R10)

The man-page and Python-docs form, with our own **Wire** field for what goes over the bus,
which is the thing a Pico programmer most needs to know.

> #### R10.4 SEND_MSG
>
> ```python
> tp.SEND_MSG(msg, msg1, st, forceDisplay=False)
> ```
>
> | | |
> |---|---|
> | **Purpose** | Answer a command with a status, and a message if VERBOSE is on or `forceDisplay` is True. |
> | **Module** | `TS.tspico` (or `dev_tspico`: see R9.2 on importing) |
> | **Parameters** | `msg` (str): the first line. `msg1` (str): a second line, or `""` for none. `st` (int, 1–127): the status, as in R4.1. `forceDisplay` (bool): send the message even when VERBOSE is off. |
> | **Wire** | With a message: `81h`, `st`, `0Dh`, *msg*, [`0Dh`, *msg1*], `0Dh`, `00h`. Without: `st` alone. |
> | **Returns** | `None`, once the 2068 has read every byte |
> | **Raises** | `CmdAbort` if the user presses BREAK while it waits |
> | **Reads** | `TSP.VERBOSE` |
>
> **Description.** ... (One answer per command: calling it twice leaves an orphan byte. See R9.4
> and the Cookbook chapter, "What not to do: two answers.")
>
> **Example** (from `dev_extcmd.py`) ...
>
> **See also.** R10.5 SEND_MSG2, R10.6 SEND_STATUS, R4.3 function 81h.

### 4.7 A `tpi:` command, from the programmer's side (R4 or a new chapter)

The User Manual already documents every command for BASIC users. The Programmer's Manual
doesn't repeat that. If we want a programmer's view of the commands, it's a single table: the
command, what CODE *a* and *b* mean, which answer it sends (status, 81h, 86h or data), and its
statuses. The User Manual stays the place for what each command *does*.

---

## 5. The narrative voice

Parts I and II already have it, more or less. To keep it:

- **Follow the house voice guide** (`andertone-voice-and-tone.md`): plain words, short
  sentences, US spelling, "we" for the authors and "you" for the reader.
- **Explain the design, not just the steps.** De Re Atari's lesson: tell the reader *why* the
  status byte has an auto-busy bit, *why* every BREAK sends a SYNC, *why* the Pico queues the
  first bytes of a message before it says READY. A reader who knows why can do things we
  didn't plan for.
- **Tell the trap stories.** "That's how the first version of `.fact` came to answer J instead
  of 6" is worth more than a rule. Keep one per chapter where we have one.
- **Each chapter has one running example**, built up through the chapter, and its file is in
  `examples/` and is tested.
- **Diagrams for anything with a sequence or a shape:** the transaction as a timeline, the
  memory banks, the FIFOs. The C64 guide's memory maps are its most-copied pages.
- **Keep the Chapter Preview and Summary boxes.** They're already doing the job of Inside
  Macintosh's "About This Chapter."

---

## 6. How it looks

**In Markdown** (what we write and what GitHub shows):

- An entry is a `####` heading with its number and name, then a two-column table of fields,
  then bold run-in headings (**Description.**, **How to use**, **Example**, **See also.**).
- No pandoc-only syntax (definition lists, `:::` divs): GitHub shows them as raw text.
- Each entry starts on a new page in print (§ below) and is short enough that it usually fits
  on one, as the C64's do.

**In print and on the website** (when `tools/manual-pdf/` learns to build this manual too):

- The fact table drawn the way the C64 sets its KERNAL headers: field names in small caps,
  a rule above and below, no cell borders.
- A running header with the entry's number and name on reference pages, so a reader flipping
  through the printed book can find R5.3 the way they'd find a word in a dictionary.
- Part III on a tinted page edge (in print) or with a side index (on the web), so the reference
  is easy to find in a closed book.
- A two-page quick reference card at the back, laid out to be cut out or printed separately.

---

## 7. Keeping it true

`docs/reference/` stays as it is: it's for people working *on* the firmware, every symbol in
source order. Part III is for people working *with* the TS-Pico: only what's meant to be used,
and it's a promise. Anything in Part III should keep working from one release to the next, or
the release notes say what changed.

Two checks would keep Part III honest, in the style of `reference_hosttest.py`:

1. Every global label in `picolib.asm` has an R5 entry, and every R5 entry names a label that
   exists.
2. Every **Example** block says which file it's from, and that file is one `test_examples.py`
   or `test_extcmd_host.py` runs.

---

## 8. Decisions for you

1. **One book or two?** The Amiga split narrative and reference into separate volumes. One book
   with a Part III is simpler to keep in step and to print as one booklet; two would let the
   reference be printed on its own. We suggest one.
2. **Does Chapter 4 keep its full source listings?** We suggest excerpts in Chapter 4, the
   interface in R5, and the full annotated `picolib.asm` as an appendix listing, so a reader
   who wants to type it in has it in one piece.
3. **A programmer's command table (§4.7):** in, or leave commands to the User Manual?
4. **Order in reference chapters:** grouped by job (suggested) or alphabetical?
5. **How far to go first:** convert R5 (picolib) and R6 (BIOS) as a pilot, see how it reads, then
   do the rest?

---

## Sources

- *Commodore 64 Programmer's Reference Guide*, Commodore and Howard W. Sams, 1982 (pages
  ix–xi, 29–31, 268–275 read for this proposal).
- *De Re Atari*, Atari, 1982: <https://www.atariarchives.org/dere/>
- *Inside Macintosh*: chapter structure from the volume contents and the 1994 prefaces, e.g.
  <https://www.vintageapple.org/inside_o/pdf/Inside_Macintosh_Volume_IV_1986.pdf> and
  <https://developer.apple.com/legacy/library/documentation/mac/pdf/Processes/Preface.pdf>
- Amiga autodoc headings and rules: <https://wiki.amigaos.net/wiki/Autodoc_Style_Guide>
- +3DOS entry and exit conditions: a scan at World of Spectrum,
  <https://worldofspectrum.org/files/thumb/472bd6281270700/800/800>
- BBC Micro OSBYTE on entry / on exit, in a modern reference:
  <https://benryves.com/bin/bbcbasic/manual/OS_Call_OSBYTE.htm>
- Diátaxis: <https://diataxis.fr/>
