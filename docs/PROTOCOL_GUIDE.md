# How the TS-2068 and the TS-Pico Talk

A plain-language guide to the TS-Pico protocol. It explains what happens when
you type a command, why each step is there, and what the error reports are
telling you. You don't need to know Z80 assembly or Python to follow it.

When you want exact byte values and addresses, [`PROTOCOL.md`](PROTOCOL.md) is
the reference. This guide describes firmware 2.0 with ROM 2.0 and 2.1.

---

## 1. Two computers, one narrow door

The TS-2068 and the TS-Pico are two separate computers. The 2068 has a Z80
processor; the TS-Pico has a Raspberry Pi Pico running Python. They can't see
each other's memory. Everything passes, one byte at a time, through two
**I/O ports**, numbered 14 and 15.

- **Port 14 is the data port.** The 2068 sends a byte with `OUT 14,b` and
  collects one with `IN 14`. Bytes going each way wait in a small queue
  called a **FIFO** ("first in, first out"). Each FIFO holds only **four
  bytes**.
- **Port 15 is the status port.** Reading it tells the 2068 whether the Pico
  is ready. Writing anything to it means "stop, start again" (section 3).

Two facts about this door shape the whole protocol:

1. **The 2068 never waits.** There is no wire that lets the Pico say "hold
   on". If the 2068 reads port 14 before the Pico has put anything there, it
   simply gets 0. If it sends a byte while the Pico's queue is full, the byte
   is lost.
2. **The queues are tiny.** Four bytes is about 150 microseconds of data.

So the two sides agree on rules about who talks when. Those rules are the
protocol.

## 2. The status byte: "are you ready?"

Reading port 15 gives a byte in which three bits matter:

| Bit | Name | When it's 1 |
|-----|------|-------------|
| 6 | **READY** | the Pico has its answer waiting, or is ready for more |
| 3 | **IDLE** | no command is in progress |
| 2 | **RECOVERED** | *(this one is back to front)* 0 means "I had to give up on the last command" |

In practice you'll see:

| Value | Meaning |
|-------|---------|
| 255 (`FF`) | ready and idle: waiting for something to do |
| 247 (`F7`) | ready, but still finishing a command |
| 251 (`FB`) | ready and idle, but the last command was abandoned |
| 0 | busy |

**The busy rule.** Every time the 2068 sends a byte, on either port, the
status drops to 0 by itself, instantly. It's the TS-Pico's hardware that does
this, not its program. The Pico's program sets READY again once it has dealt
with the byte and has its answer queued.

This one rule makes the conversation safe. After sending, the 2068 always
waits for READY before it reads, and the Pico always queues its answer
*before* it says READY. So the 2068 can never read an empty queue by accident.

## 3. Starting clean: SYNC

Every conversation (a **transaction**) starts the same way on ROM 2.0 and
later: the 2068 writes the byte 3 to port 15. This is called **SYNC**.

When the Pico sees it, it:

1. throws away anything half-finished;
2. empties both queues;
3. puts a single **1** in its outgoing queue (the "pre-load", section 4);
4. says ready and idle.

The 2068 waits (up to about a second) for ready-and-idle, then begins. So
whatever happened before, even a program that crashed halfway through a
command, both sides start the new transaction in step.

**BREAK uses the same signal.** Press BREAK while the 2068 is waiting for the
Pico, and the ROM sends that same byte to port 15. The Pico stops what it's
doing, and the ROM reports **D BREAK - CONT repeats**. The next command works
normally, because the link is already clean.

## 4. A command, step by step

Let's follow `SAVE "tpi:dir"`, which asks the Pico for a folder listing.

**Step 1: SYNC.** The 2068 writes 3 to port 15 and waits for ready-and-idle.

**Step 2: the envelope.** The 2068 sends ten bytes called the **pre-header**.
Think of it as the outside of an envelope: it says what kind of message this
is and how long the contents are, without the contents themselves.

| Byte | Contents |
|------|----------|
| 0 | the letter `B`: "a command" |
| 1 | 0 for a `SAVE "tpi:..."` command (1 for `LOAD "tpi:..."`, which mounts a file) |
| 2 | the memory bank (always 255; ignored) |
| 3, 4 | the first `CODE` number, if you gave one |
| 5, 6 | the second `CODE` number |
| 7, 8 | the length of the command text |
| 9 | a checksum of bytes 0–8 |

**Step 3: the pre-load.** Straight after the tenth byte, the 2068 reads port 14
*without waiting*, and expects a **1**. That 1 was put there at the end of the
previous transaction (or by the SYNC). It says "the link is in step". If the
2068 reads 0 instead, nothing was there: that's **Report J Invalid I/O device**.

Why read without waiting? The original ROM was written that way, and the
pre-load is how the Pico can answer "instantly" even though Python is far
slower than the Z80.

**Step 4: the letter.** The Pico says READY (status 247: "listening, still
busy"), and the 2068 sends the **body**: the letter `D`, the length again, the
text `tpi:dir`, and a checksum over all of it. The Pico checks that checksum.
If it's wrong, a byte was lost on the way, and the answer is **Report R Tape
loading error**.

**Step 5: the work.** The Pico looks up `TPI:DIR` in its table of commands and
runs it. The 2068 waits for READY, up to about 20 seconds. That wait is where
the time goes in a slow command.

**Step 6: the answer.** When the Pico says READY, the 2068 reads the answer from
port 14 (section 5).

**Step 7: tidying up.** Once the 2068 has read everything, the Pico empties its
incoming queue, puts a fresh **1** in its outgoing queue for next time, and
says ready and idle. The transaction is over.

```
2068                                        TS-Pico
SYNC  ─────────────────────────────────▶    clean up, queue a 1, ready + idle
10-byte pre-header  ───────────────────▶
read the 1  ◀──────────────────────────     (queued since the SYNC)
wait for READY                              "listening"
body: D, length, "tpi:dir", checksum ──▶    check it, run the command
wait for READY                              queue the answer, then READY
read the answer  ◀─────────────────────
                                            queue the next 1, ready + idle
```

## 5. What the Pico can answer

The first byte of the answer tells the 2068 what kind it is.

**A status (1 to 127).** The simplest answer: 1 means OK, and anything else
becomes a BASIC report:

| Status | Report you see |
|--------|----------------|
| 1 | 0 OK |
| 2 | R Tape loading error |
| 3 | F Invalid file name |
| 4 | Q Parameter error |
| 5 | C Nonsense in BASIC |
| 6 | 6 Number too big |
| 7 | 8 End of file |
| 8 | A Invalid argument |
| 9 | 9 STOP statement |
| 10 | J Invalid I/O device |
| 11 and up | D BREAK - CONT repeats |

That's why a TS-Pico error looks like any other BASIC error: the Pico sends a
number, and the ROM turns it into the report.

**A request to print (128 and up).** These are "response functions": the Pico
asks the 2068 to do something. Each is followed by its own status byte, then
text:

- **129 (`81`) — print this.** One message, ending in a 0. This is what you see
  when VERBOSE is on.
- **134 (`86`) — print this, page by page.** After each page (ending in 0)
  the 2068 waits for a key and sends it back. The Pico uses this for long
  listings ("Scroll? (Y/n)") and for yes/no questions. `N` stops; a digit sets
  how many lines the next page shows; any other key shows a full page. The
  byte 3 ends the whole thing.
- **136 (`88`) — the same on the bottom two lines of the screen.** New in ROM
  2.1, for the question `SAVE "f:x" SCREEN$` asks when the file exists: asking
  on the main screen would write over the picture that's about to be saved.
  ROM 2.0 doesn't know this code, and reports D if it ever sees it.

The ROM prints the text as it reads it. It doesn't wait between characters,
because printing a character takes much longer than the Pico needs to queue
the next one.

**Data.** A command can also send bytes that aren't for printing: the next
chunk of a file (`tpi:chrd`), or a number worked out by a command you added
yourself. Then your own program reads them, and both sides must agree on the
layout. The convention is: status 1, a count, that many bytes, then a
checksum.

## 6. Loading a program

`LOAD ""` uses the same envelope with different contents. The first byte is
the **flag**: 0 for a tape header, 255 for a data block. It's the same flag a
real tape block starts with.

1. SYNC, the pre-header, and the pre-load 1.
2. The 2068 waits for READY; the Pico has found the block in the mounted TAP
   file and queued its start.
3. The 2068 sends the flag back ("echo") and reads the block: the flag, the
   content, and a checksum. It reads one byte every 47 microseconds or so,
   with no handshake. The four-byte queue is enough because the Pico keeps it
   topped up.
4. The 2068 sends back the checksum *it* worked out, waits for READY, and
   reads the final status.

A header block and its data block are two transactions, so you see "Program:
name" between them, just as with a tape.

## 7. Saving a program

Saving is the mirror image, with one important difference in *when* the Pico
can say no.

1. The header block goes to the Pico, and the 2068 reads a status.
   **This is the Pico's only chance to refuse**: a bad name gets F, an empty
   program A.
2. After a short pause the data block goes, with no envelope of its own, and
   the 2068 reads the final status.
3. Only *then* does the Pico write the file to the SD card.

Why write last? The SD card shares wires with the data bus, so the Pico can't
use both at once. By the time the card is written, the 2068 has already
printed "0 OK". If the card fails at that moment, the error goes in the
TS-Pico's log (`SAVE "tpi:log"`) instead.

## 8. Files as streams (ROM 2.1)

`OPEN #4,"f:notes.txt"`, `PRINT #4`, `INPUT #4` and `CLOSE #4` use four
ordinary commands underneath: open, write, read and close. Each is a complete
transaction as in section 4. Writes send their bytes as hexadecimal text,
because a command's text must be text. A read gets a data answer: status 1, a
count, up to 255 bytes, and a checksum. At the end of the file the status is 7
("8 End of file").

These answers say READY but not IDLE (247), because the ROM often sends its
next command at once, and the Pico still has tidying up to do. The ROM waits
for IDLE before its next SYNC.

## 9. When something goes wrong

Each report points at a different part of the conversation:

| Report | What happened |
|--------|---------------|
| **J Invalid I/O device** | The 2068 read 0 where it expected a byte: no pre-load, or no answer. Usually the Pico isn't running (Thonny connected, a crash, a firmware/ROM mismatch), or the previous command broke the chain. |
| **R Tape loading error** | A checksum didn't match: a byte was lost or changed on the way, or an extra byte shifted everything by one. |
| **D BREAK - CONT repeats** | You pressed BREAK, or the Pico sent something the ROM doesn't understand. |
| **T TS-Pico reset, try again** | The Pico gave up on the transaction by itself (the RECOVERED bit), typically because bytes stopped arriving halfway through. Just try again. |
| **F, Q, A, C…** | The command ran and refused: a file that isn't there, a bad CODE number, and so on. |

**Why errors often show up one command late.** Every transaction ends by
queueing the 1 for the *next* one. If a command leaves no 1, the next command
gets J. If it leaves an extra byte, the next command reads that byte in the
wrong place and usually gets R. That's why a bug in one command so often looks
like a bug in the command after it.

## 10. Adding a command to the Pico

The Pico's commands are Python functions. The simplest way to add one is the
**external command** file, `TS/extcmd.py`, or `/dev_extcmd.py` on the Pico's
flash, which you can change without rebuilding the firmware. A command there
is a function and a line in a table:

```python
def HELLO(MQ, TSP, pre, cmd):
    tp.SEND_MSG("Hello from the TS-Pico!", "", tp._1_OK, True)

EXT_SA_FUNCT = {"TPI:.HELLO": HELLO}
```

and `SAVE "tpi:.hello"` runs it. There is one rule that matters more than any
other:

> **Give exactly one answer, and never queue the final 1.**

The Pico adds the 1 for the next command itself, after your function returns.
If your function answers twice, the second answer is read by the next command
in the wrong place. If it doesn't answer at all, the 2068 waits and then
reports J.

Here's the right way and the wrong way to send back a word:

```python
# Right: one answer, a message the ROM prints.
tp.SEND_MSG(word, "", tp._1_OK, True)

# Wrong: "OK" is one answer; the word is a second one nobody asked for.
MQ.put(1)
for c in word:
    MQ.put(c)
```

Two more rules follow from the "2068 never waits" fact:

- **Queue the first bytes, then say READY.** The helpers (`SEND_MSG`,
  `SEND_MSG2`) do this for you. If you send raw data with `tp.CMD_PUT`, call
  `tp.MQ_READY()` after the first byte or two, never before.
- **Do the slow work first.** Reading the SD card (always inside
  `tp.SD_CALL`), calculating, building the text: do it all while the 2068 is
  still waiting for READY.

The examples in `TS/extcmd.py` (`.fact` and `.rndw`) and the *TS-Pico
Programmer's Manual* go further.

## 11. Words used in this guide

| Word | Meaning |
|------|---------|
| **FIFO** | a first-in, first-out queue of bytes; four bytes each way |
| **transaction** | one complete exchange: a command and its answer, or one tape block |
| **SYNC** | the byte 3 written to port 15: "start clean"; also used for BREAK |
| **pre-header** | the ten-byte "envelope" at the start of a transaction |
| **pre-load** | the single 1 waiting in the Pico's queue between transactions |
| **body** | the command text, framed by `D`, its length and a checksum |
| **READY / IDLE / RECOVERED** | the three status bits of port 15 |
| **auto-busy** | the status dropping to 0 on every byte the 2068 sends |
| **response function** | an answer of 128 or more: "print this", "ask this" |
| **checksum (XOR)** | a byte computed from all the others, to catch a lost or changed byte |
| **ROM 2.0 / 2.1** | the TS-2068 ROMs this guide describes; 2.1 adds the disk commands and `f:` files |
