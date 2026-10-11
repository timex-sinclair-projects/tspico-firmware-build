# TS/tspico.py (part 4) — what the 2068 prints

Source: [`src/TS/tspico.py`](../../../src/TS/tspico.py), lines 1519–1608
(`shorten_filename`, `DIR_HEADER`, the colour helpers), 2169–2500
(`MSG_BYTE`, `SEND_MSG`, `SEND_MSG2`), 2764–2802 (`PROMPT_EACH`),
3483–3675 (`ListMenu`), 3878–3890 (`xchr`, `xstr`), 4565–4577
(`BUILD_FIT`) and 5378–5445 (`SEND_MSG_PROMPT_YN`).

A `tpi:` command answers the 2068 with one byte — a status — or with a
**response function**: a byte of `80h` or more that makes the ROM print
text, wait for keys and send them back
([PROTOCOL.md §5.3–5.4](../../PROTOCOL.md#54-the-answer-a-response-function-status--80)).
Every such answer in the firmware is built by the functions in this
chapter: `SEND_MSG` for a status or one message, `SEND_MSG2` for long text
in pages with a "Scroll?" prompt, `ListMenu` for a menu, `PROMPT_EACH` and
`SEND_MSG_PROMPT_YN` for Y/N questions; and by the small helpers that
format names and listings for a 32-column screen. The bytes go into the
FIFO through the never-blocking command I/O of
[tspico-bus.md](tspico-bus.md) (`CMD_PUT`, `CMD_SEND`, `CmdOut`,
`CMD_KEY`); the ROM code at the other end is the function chain in
[../rom/exrom-chunk1.md](../rom/exrom-chunk1.md). The protocol constants
(`FN_PRINT_STRING` … `LOOP_END`), the colour codes (`INK_`, `PAPER_`,
`NORMAL_`), `LISTMENU_CHOICES` and `NO_CARD_MSG` are module variables:
[tspico-state.md](tspico-state.md).

## Map

| Symbol | Line | Role |
|---|---|---|
| `shorten_filename(nom, l)` | 1519 | a name cut to `l` characters in the middle, extension kept |
| `DIR_HEADER(sd_stat, path=None)` | 1540 | the four 32-column header rows of a folder listing |
| `CAT_COLOUR(text)` | 1546 | a plain folder listing → CAT's colours |
| `TAPDIR_COLOUR(text, headers)` | 1582 | `tpi:tapdir`'s listing → CAT's colours |
| `MSG_BYTE(m)` | 2169 | one character of a `SEND_MSG` text → one byte |
| `SEND_MSG(msg, msg1, st, forceDisplay=False)` | 2193 | a bare status, or `81h` and a message |
| `SEND_MSG2(msg, st, expandKeywords=True, colour=False)` | 2253 | `86h`: long text in pages, "Scroll? (Y/n)" between them |
| `PROMPT_EACH(prompts)` | 2764 | `86h`: one Y/N question after another, one exchange |
| `ListMenu(List, hdr1, hdr2, action, chosen, folders=False)` | 3483 | `86h`: pick one of a list, 16 to a page |
| `xchr(m)` | 3878 | a character of a card name as the 2068 lists it |
| `xstr(s)` | 3886 | a name as the 2068 lists it |
| `BUILD_FIT(s, n)` | 4565 | the build stamp in `n` characters |
| `SEND_MSG_PROMPT_YN(prompt, echo=True, lower=False)` | 5378 | `86h` or `88h`: one question, one key |

## The answer on the wire

What the ROM does with the first byte it reads after a command
([PROTOCOL.md §5.3](../../PROTOCOL.md#53-the-answer-a-status)): `00h` is
"no answer", Report J; `01h` is OK; `02h`–`7Fh` is a report, by
`STATUS_TO_REPORT` with A = status − 1; `81h`, `86h` and `88h`
start a response function. **Every response function then reads one more
byte, its own status, which becomes the command's result** when the
function ends. So every answer built here starts with two bytes: the
function code, then the status.

| Function | Bytes, in order | The ROM | Built by |
|---|---|---|---|
| status | `st` | `C_END`: 1 = OK, else the report | `SEND_MSG` (VERBOSE off), `CH_REPLY` |
| `81h` PRINT STRING | `81h`, `st`, text, `00h` | prints the text on the main screen, then `st` is the result | `SEND_MSG` (VERBOSE on, or forced) |
| `86h` PRINT STRING WITH LOOP | `86h`, `st`, then pages | each page is text ending `00h`: the ROM prints it, waits for a key, waits for READY, OUTs the key, as typed; then, whatever the key, `N` included, waits for READY and reads the next page (ROM 2.3, #227; ROM 2.2 upper-cased the key and left the loop on `N`). `03h` instead of `00h` ends the loop with no key, so after `N` the Pico sends an echo and `03h` | `SEND_MSG2`, `ListMenu`, `PROMPT_EACH`, `SEND_MSG_PROMPT_YN` |
| `88h` | as `86h` | `86h` on the lower screen (`LOWER_LOOP`, [../rom/exrom-fdd.md](../rom/exrom-fdd.md)) | `SEND_MSG_PROMPT_YN(lower=True)` |

`82h`–`85h` and `87h` exist in the ROM and are unused by the firmware.

The text rules, which the builders all keep
([PROTOCOL.md §5.4](../../PROTOCOL.md#54-the-answer-a-response-function-status--80)):

- The ROM reads each character **with no ready-wait**: it prints it with
  `RST 10` and reads the next. So the first bytes of an answer must be in
  TX **before** READY — an empty TX reads as `00h`, which ends the text
  (or, as the first byte, is Report J) — and the rest must keep up. That
  is what `CMD_SEND` is for: it puts the first four bytes in, says READY,
  and feeds the rest (by DMA where there is a channel).
- `00h` ends a string or a page. Inside an `86h` loop, `03h` ends the loop.
  Nothing else does: ROM 2.3's reader (`PS_READ`,
  [../rom/exrom-fdd.md](../rom/exrom-fdd.md#ps_read), #228) prints bytes of
  `80h` and above (block graphics, UDGs, keyword tokens), which ROM 2.2's
  took for the end.
- Control codes 16–23 (INK, PAPER, FLASH, BRIGHT, INVERSE, OVER, AT, TAB)
  take the next byte or two as their value, and the reader passes those
  straight to `RST 10h`, so a `00h` or `03h` value (INK 0, PAPER 3) is a
  value, not an end. ROM 2.2 tested them too, so those values could not be
  sent. So far `SEND_MSG2`'s colour codes are the firmware's only use of
  either; it still sends `?` for bytes of `80h` and above.
- `0Dh` is a new line; `08h` moves back one column.
- Codes 124 (`|`) and 126 (`~`) print as the TS2068 keywords STICK and
  FREE, with their spaces, always. 123 (`{`, ON ERR), 125 (`}`, SOUND) and
  127 (©, RESET) are keyword tokens too
  ([ERROR_TRAPPING.md](../../rom-analysis/ERROR_TRAPPING.md)), but HOME's
  print routine (063Bh) prints them as keywords only while FLAGS bit 4
  (`IY+1`) is clear. The editor sets that bit from its mode on every key
  (1683h: set in L mode), and it is set at start-up; when a command's answer
  prints it is set, so they print as the characters `{`, `}` and ©, one
  column each (ZEsarUX: FLAGS = 10h at a typed `SAVE "tpi:…"`, and `PRINT
  CHR$ 123;CHR$ 125;CHR$ 127;CHR$ 124;CHR$ 126` shows `{}© STICK FREE`;
  #173). So the firmware counts only 124 and 126 as keywords, and maps
  `\*` to 127 for ©. In practice names and help text never carry 123–126:
  `catalog.screen_name` turns them into `?` first.
- Keys come back **upper case** (`GET_KEY_AND_SEND` 0471h → `SEND_KEY`
  1C40h); the builders compare with 78 (`N`), 89 (`Y`) and so on.

The Y register through an answer. When the handler starts, the Z80's last
OUT (the end of the command body) has dropped Y to BUSY and the ROM is
polling 0Fh. The builder puts the first bytes into TX and says READY
(`MQ_READY`, through `CMD_SEND`); the ROM reads the rest blind. At a page's
`00h` the ROM waits for a key and then for READY; its OUT of the key drops
Y to BUSY again (auto-busy), `CMD_KEY` returns, and the builder puts the
next page's first bytes into TX and says READY once more. After the last
byte the builder waits for TX to empty (`CMD_DRAIN`); `PROCESS_CMD`'s tail
then stages the pre-load and says IDLE
([tspico-dispatch.md](tspico-dispatch.md)). When the user answers `N`, the
ROM has left its loop and reads nothing more: the builder sends nothing,
calls `MQ_READY` (so the tail's status reads are not left at BUSY), and
returns. In the single-port firmware READY was a `40h` byte in TX
interleaved with the text; each builder's "DUAL-PORT MIGRATION" comment
records the `wrt(0x40)`s it lost.

A BREAK at any key wait (the ROM's `KEYWAIT`) is a port-0Fh write;
`CMD_KEY` and `CMD_RX_FLUSH` raise `CmdAbort` and `PROCESS_CMD` ends the
command ([tspico-bus.md](tspico-bus.md#command-io-that-never-blocks)).
After a builder that waits for keys has returned, nothing more may be sent
for that command: the ROM has finished its function and will read the next
byte as a status (the comments at 3488 and 5381).

## Names and listings on a 32-column screen

### `shorten_filename(nom, l)`

`nom` if it is at most `l` characters; otherwise the name cut in the
middle, keeping the extension (from the last `.`), with `>` where the cut
is:

```text
l < 1: ""
e  = length of the extension with its dot (0 if none, or if e > l - 1)
k  = l - 1 - e          # room for the stem, less the '>'
k1 = k - k//2           # from the front
k2 = k//2               # from the end of the stem
nom[:k1] + ">" + nom[j-k2:]
```

`shorten_filename("averylongname.tap", 12)` is `"aver>ame.tap"`. `>` cannot
be part of a FAT name, so a shortened name is never mistaken for a real
one *(inferred as the reason for the choice)*. Callers: the folder listings
(`LIST_DIR_FILES` 1701, 1717, 1728; `CATALOG_TEXT` 2666, 2694), the
disk-command messages (2888, 2917, 3142), `IDIR` (3469), `public_path` and
`public_fname` (3904, 3920).

The result is never longer than `l`, and exactly `l` when `nom` is
longer. An "extension" with no room for the `>` in front of it is
shortened as part of the name: callers shorten paths too, and a path whose
last `.` is in a long folder name (`/TAP/GAMES/A.VERYLONGFOLDERNAME…`) has
one. Before #168 `k` went negative there and the slices returned more than
`l` characters — 73 for a 46-character path shortened to 27. A name the old
code shortened correctly comes out the same
([`commands_hosttest.py`](../../../src/test/commands_hosttest.py) sweeps
`l` from 0 to 33).

### `DIR_HEADER(sd_stat, path=None)`

The 128-character header of a folder listing, four rows of 32:

| Row | Text |
|---|---|
| 1 | `Path:` and the current folder, padded to 27 (`public_path(27)` unless `path` is given) |
| 2 | `sd_stat` (`"SD: <size>; free: <free>"` from `catalog.space_pair`, or `"SD: card error"`), cut and padded to 32 |
| 3 | `File Name                   Size` |
| 4 | 32 dashes |

The rows are not separated: on a 32-column screen each fills a line and
the next starts on the following one. The fixed layout is what
`CAT_COLOUR` (and the tests of `dirinfo` and `tpi:info`) rely on. Callers:
`DIR_FILES` (1645, with `"SD: card error"`), `LIST_DIR_FILES` (1739), and
`CATALOG_TEXT` (2694, with the catalogued folder as `path`)
([tspico-files.md](tspico-files.md), [tspico-disk.md](tspico-disk.md)).

### `CAT_COLOUR(text)`

Turns a plain listing (`DIR_HEADER`'s four rows and then 32-character
entry rows, as `DIR_FILES` and `CATALOG_TEXT` build them) into the one CAT
shows, chosen 2026-10-02:

- rows 1–2 (path, card line) on the blue bar: `PAPER 1`, `INK 7`;
- row 3 (column titles) on cyan: `PAPER 5`, `INK 9` (contrast);
- row 4 (the dashes) dropped;
- a folder row (it starts with `<`): `NORMAL_`, `INK 1` (blue), its first
  22 characters, and `folder` right-aligned in 10 for its size;
- a numbered row (`nnn `): the number on a cyan chip, then `NORMAL_` and
  the rest;
- a continuation row (four spaces): `NORMAL_` and the row;
- anything else ends the rows; it and whatever follows go out after
  `NORMAL_`, as they are.

Text that does not start with `Path:` or is shorter than 128 characters
(a TAP's block list, "Directory is empty") is returned unchanged. Every
row starts by setting its own colours, so a "Scroll?" prompt in the middle
changes nothing; and no row ends with a code after its 32nd character,
which would hide the line's end from `SEND_MSG2`'s column count. Colour 8
(`NORMAL_`, "transparent": the screen's own) and 9 ("contrast") are the
only values used beyond 1, 5 and 7, so none is `00h` or `03h` (see the
text rules). Send the result with `SEND_MSG2(…, colour=True)`; without
`colour` the codes are stripped. Callers: `DIR` (2569), `CATALOG` (2635),
`CDIR` (4303), `ZX_TPI`'s listing (7125).

`lista` and `dirinfo.tap` keep the plain text; the colour is added only on
the way out.

### `TAPDIR_COLOUR(text, headers)`

`tpi:tapdir`'s listing in the same colours (agreed 2026-10-02). `text` is
`TAPDIR`'s: four 32-character header rows (`File:` …, the pointer and
append line, the titles, the dashes), then 32-character block rows whose
first character is `>` (the block `LOAD ""` reads next) or a space and
whose next two are the block number. `headers` is true for the `CODE 1`
view, in which every row is a program.

- rows 1–2 on the blue bar, row 3 on cyan, row 4 dropped;
- the `>` row: all of it on yellow (`PAPER 6`, `INK 9`);
- any other block row: the marker, the number on a cyan chip, then the
  rest with `PAPER 8` and `INK 1` (blue) for a header block, `INK 8` for
  a data block. In the `CODE 1` view a row is a header unless
  `Data block` appears in columns 4–14; in the default view, when columns
  18–19 read ` Y` (`TAPDIR`'s "header?" column);
- the first row that is not a block row (e.g. `<empty file>`) ends the
  rows and goes out, with the rest, after `NORMAL_`.

Text that does not start with `File:` or is under 128 characters is
returned unchanged. One caller, `TAPDIR` (3787)
([tspico-commands.md](tspico-commands.md)).

## Answers: a status or a message

### `MSG_BYTE(m)`

The byte `SEND_MSG` sends for one character of its text: the code itself
for printable ASCII (32–127) and for `0Dh`, `3Fh` (`?`) for anything else.
`m` is a one-character `str` or an int.

Why (the docstring; 2026-09-30 audit): `SEND_MSG` used to pass each
character straight to `MQ.put()`. Since #79 its messages carry raw names
from the card ("Copied %s", "Erased %s"), and a name can hold non-ASCII
characters. MicroPython's `put()` takes a `str` as a buffer, so `é` went
out as two bytes, `C3h A9h`, its UTF-8 — both ≥ `80h`, which ends the
ROM's string early; and `CMD_PUT` had made room for one word, so a
two-word `put()` into a FIFO with one free slot blocked. Control codes are
replaced too, since `00h` would end the string — all but `0Dh`: the ROM
prints it as a new line, `SEND_MSG` sends one between `msg` and `msg1`,
and many messages build their lines with `chr(13)` (`tpi:zx48`,
`tpi:info`, the `romupdate` refusal). Replacing it as well (#107) printed
every one of those line breaks as `?`.

So colour codes cannot be sent through `SEND_MSG`; `SEND_MSG2` has its own
rules. `|` and `~` (124, 126) pass, and print as STICK and FREE.

### `SEND_MSG(msg, msg1, st, forceDisplay=False)`

A command's answer when it is one status, or one message and a status.

`msg` and `msg1` are the message's two parts (`str`, or anything whose
items `MSG_BYTE` takes); `msg1` may be empty. `st` is the status, an int
1–127 (the `_n_X_…` constants; annotated `int` since #181). With
`forceDisplay`, the message is shown even with VERBOSE off; passing the
object `NO_CARD_MSG` as `msg` forces it too (an identity test, `is`).

1. If `TSP.VERBOSE` or forced, the `81h` answer is built in RAM:
   `81h`, `st`, `0Dh`, the bytes of `msg`, then (if `msg1`) `0Dh` and the
   bytes of `msg1`, then `00h`. `CMD_SEND(ob, True)`: the first four bytes
   into TX, READY, the rest as the ROM reads it (all of it by DMA where a
   channel is free). The ROM prints the text on the main screen, starting
   on a new line, and takes `st` as the command's result.
2. Otherwise only `st`: `CMD_PUT(st)` and `MQ_READY()`. The message is not
   sent and not logged.
3. `CMD_DRAIN()`: wait until the ROM has read everything.

Returns `None`. Raises `CmdAbort` (BREAK, or a Z80 that stopped reading)
from `CMD_PUT`, `CMD_SEND` or `CMD_DRAIN`. Reads `TSP.VERBOSE`.

Why `MQ_READY` is required in the short path: the PIO dropped Y to BUSY on
the Z80's last OUT, the end of the command body; without READY the Z80
never reads the status and gives Report J. The comment at 2210–2214 notes
that it was once described as redundant and the audit tried removing it.

Callers: 72 sites in `tspico.py` — most handlers end with it — and
external commands through `extcmd.py`. The forced ones: `NO_CARD_REPLY`
(through `NO_CARD_MSG`), `LOAD "tpi:"` when several files match (6099:
that message says what to do), and `extcmd`'s `tpi:list` (89). The
`romupdate` refusal and the other mount errors go through `LOAD_TPI`'s
message ([tspico-files.md](tspico-files.md)).

Beware:

- It is the last thing a command sends. After it, the ROM reads the next
  byte as the next command's pre-load; `PROCESS_CMD`'s tail stages that.
  A handler must call one answer builder, once.
- The status of an `81h` answer comes **after** the code, not before; a
  machine-code client reading the answer must read two bytes before the
  text.

### `SEND_MSG2(msg, st, expandKeywords=True, colour=False)`

Long text as an `86h` loop: pages of a screen or less, with a
"`(nn%) Scroll? (Y/n)`" prompt between them. `msg` is a `str`; `st` the
status (the command's result); `expandKeywords` counts `|` and `~` at the
width the ROM prints them (STICK, FREE); `colour` lets INK and PAPER codes
through (see below). Returns `None`; raises `CmdAbort`.

**The header.** A page buffer `ob` gets `86h`, `st`, `0Dh` and `0Dh` (a
blank line, not counted). `CMD_RX_FLUSH()` empties RX of stray keys — a
BREAK among them raises — before anything is sent.

**The characters.** For each character of `msg`, a column count `c` and a
line count `l` are kept, and the byte written is:

| Character | Written | Column count |
|---|---|---|
| `0Dh` (CR), or CR LF | `0Dh` (the LF skipped) | `c = 32`: the line is full |
| `0Ah` (LF) alone | `0Dh` | `c = 32` |
| `08h` (backspace) | `08h` | one back (to 31 of the line above at column 0); dropped at the very start |
| `10h`–`15h` (INK … OVER) and a value in `ATTR_VALUES`, with `colour` | both bytes | none |
| `10h`–`15h` otherwise | nothing (the value byte is skipped too) | none |
| any other code below 32 | `?` | +1 |
| 128 and above | `?` (63) | +1 |
| 124 `\|`, 126 `~`, with `expandKeywords` | the code | +7 (" STICK "), +6 (" FREE ") |
| 125, 127, and 124/126 without `expandKeywords` | the code | +1 |
| `\` followed by `*` | 127 (©), the `*` skipped | +1 |
| anything else | the code | +1 |

Any of the six attribute codes is kept with a value RST 10h accepts
(`ATTR_VALUES`, [tspico-state.md](tspico-state.md)), 0 and 3 included:
ROM 2.3's reader takes value bytes as values (#228). A value RST 10h would
answer with Report K is dropped with its code. Until #228 the reader took a
`00h` value for the end of the page and a `03h` for the end of the loop, so
only INK and PAPER 1, 2, 4–9 were kept. AT and TAB (`16h`, `17h`) are not in that range: they become `?`
and their values print as characters. `colour=True` is passed only with
text the firmware built with those codes (the `CAT_COLOUR` listings,
`TAPDIR_COLOUR`, `tpi:info`, `DIR`'s other listings); a card's names
reach here through `xstr`, which has already turned every code below 32
into `?`.

The keyword widths: 124 is STICK and 126 FREE. Until the 2026-09-30 audit
the two widths were swapped (the original comments had 124 as FREE), so
each one in a listing put the count a column out.

**A full line.** When `c` reaches 32 *or passes it* (a keyword that starts
at column 26–31 jumps over 32), `l` goes up by one. Past 32, the overflow
is carried (`c -= 32`): the ROM has wrapped the keyword onto the next line
itself, and no CR is written. Exactly 32: `c = 0`, and if the character
was a CR (the line ended by itself), nothing more — except that a CR at
the very start of `msg` does not count as a line; if the line filled up
with a printable character, a CR, LF or CR LF that follows in `msg` is
skipped and `0Dh` written in its place, so a 32-character line followed
by its own line break gives one line, not a blank one. Before the audit
the test was `c == 32`: a keyword that jumped over 32 was never counted,
`c` never reset, and the rest of the message got no prompt at all.

**The prompt.** When `l` reaches the page length `ll` (21 to start with)
and what is left is more than will fit — more than 34 characters, or more
than one line break — the page ends: `(nn%) ` (`i * 100 // n`, how far
through `msg` this is), `Scroll? (Y/n)`, `00h`. `CMD_SEND(ob, True)`: the
first bytes in TX, READY, the rest as the ROM prints. The ROM prints the
prompt and waits for a key. `CMD_KEY()` returns it (Y has gone BUSY with
the Z80's OUT); the tests below are on `KEY_UP(ch)`, so `n` is `N` and `y`
is `Y`:

| Key | Effect |
|---|---|
| `N` or `n` | the ROM waits for READY and reads on (#227): a new page holding the key as typed, then out of the loop to the end below, which adds `03h`. The echo stands where ROM 2.2 printed its own `N` |
| `0` | next page 10 lines |
| `1`–`9` | next page that many lines |
| anything else (`Y`, ENTER …) | next page 21 lines |

The next page starts with 19 × (`08h`, `20h`, `08h`) — back, space, back,
once for each character of `(nn%) Scroll? (Y/n)` — which erases the
prompt, so the text carries on where the prompt was. The prompt was
printed after a full line, so it is on a line of its own and the erase
leaves the cursor at that line's start.

Why "more than 34 characters or more than one line break" (audit §4; host
check 2026-10-03): the screen can still scroll a line or two without
losing the top; counting characters alone let a tail of short lines (help
text, a listing ending in one-word rows) scroll the page off unread — 21
lines and 12 short ones printed 34 lines with no prompt. An earlier rule
that skipped the prompt for any message under 500 characters is gone too:
it changed nothing for one-screen text and suppressed the prompt for many
short lines, exactly when it was needed.

**The end.** `03h` (`LOOP_END`) into the page, `CMD_SEND(ob, True)`,
`CMD_DRAIN()`, then any keys typed during the output are read from RX and
dropped (an unbounded `while MQ.rx_fifo()`, which ends because nothing
keeps writing).

Callers, with their flags:

| Caller | `expandKeywords` | `colour` |
|---|---|---|
| DIR (2569, 2604), CATALOG (2635), CDIR (4303) — listings through CAT_COLOUR | `False` (2604: `True`) | `True` |
| DISK_COPY (2819), GETHELP (4560) | `False` | `False` |
| TAPDIR (3789), GETINFO (4663) | `True` | `True` |
| GETLOG (4789) | `True` | `False` |

Beware:

- One call is the whole answer, and it ends with a key wait or `03h`;
  nothing may follow it.
- The page length counts lines of 32 columns, so a code the counter does
  not know the width of puts every following line out. A new control code
  in text sent here needs a row in the table above.
- `ROM_VERSION` no longer changes anything here. It used to switch to a
  pre-1.2 protocol with no `03h` (every page prompted, the last one said
  "--- End of list (N to exit) ---"); a stale `"1.0"` left in an old
  `config.ini` then broke multi-page listings on every current ROM, all of
  which end the loop on `03h` (EXROM 06F5h). The audit removed the branch;
  [`cmd_io_hosttest.py`](../../../src/test/cmd_io_hosttest.py) runs a
  listing with `ROM_VERSION` `"1.0"` to show it is ignored.

## Questions and menus

The three builders in this section use an `86h` loop for something other
than paging: each page is a question, the key is the answer, and the
**echo of the answer starts the next page**, so the 2068 shows the key
the user pressed after the question. Each builds its pages in a `CmdOut`
and sends one with `send()` wherever it then waits for a key — the bytes
in TX, READY, the rest as the ROM prints. Each first empties RX with
`CMD_RX_FLUSH` (a BREAK there raises).

### `PROMPT_EACH(prompts)`

Asks each string of `prompts` in turn, in one `86h` exchange, and returns
the list of the indexes answered `Y`. Used by `DISK_ERASE` (2917) for
`ERASE` with a pattern: "Erase NAME (Y/N)?" for each match, then the
chosen ones are erased in a second `SD_CALL` after the exchange
([tspico-disk.md](tspico-disk.md)).

1. `86h`, status `1`.
2. For each prompt: the echo of the previous key (from the second prompt
   on; a key outside 32–126 is echoed as `Y`), `0Dh`, the prompt, `00h`;
   `send()`; `CMD_KEY()`. The test is on `KEY_UP(ch)`:
   - `Y`: the index is chosen.
   - anything else, `N` included: skipped, and the next prompt is asked.
     The ROM keeps its loop going after `N` (#227), so `N` means "not this
     one", as a user expects; with ROM 2.2 it ended the whole exchange.
3. After the last: the echo of the last key, `03h`; `send()`;
   `CMD_DRAIN()`.

The status of the exchange is always 1; the caller answers the erase
itself afterwards. The ROM sends keys as typed, and the echo shows the key
as it came.

An empty `prompts` returns `[]` before anything is queued: an exchange
needs a question, so nothing is sent and the caller still owes the Z80
its answer. Before #167 it reached the closing echo with no key and
`32 <= None` raised `TypeError` (Report J). `DISK_ERASE` never passes one:
`DISK_ERASE_MATCHES` answers "No match" (Report F) first
([`disk_cmds_hosttest.py`](../../../src/test/disk_cmds_hosttest.py)).

### `ListMenu(List, hdr1, hdr2, action, chosen, folders=False)`

A menu: the strings of `List` sixteen to a page, each with a key, and the
user picks one. Returns its index, or `-1` for none. Used by `IDIR`
(3471, "Mount file") and `CDIR` (4293, "Change to dir", with `folders`)
([tspico-commands.md](tspico-commands.md)).

Arguments: `hdr1` is the top line (the path), `hdr2` the column titles,
`action` the verb of the prompt, `chosen` the line printed before the choice
("Mounting: "), `folders` true to show the entries in blue.

**A page** (each a page of an `86h` loop; the first starts `86h`, status
`1`, later ones with the echo of the key that led to them):

```text
0Dh 0Dh
[blue bar] hdr1, padded/cut to 32
[cyan]     hdr2 padded to 24, "p of n" right-aligned in 8
[normal]   for each of up to 16 entries:
           [cyan chip] key [normal] space [blue if folders] entry 0Dh
           0Dh for each empty slot, so the page is always 16 lines
the position bar: 32 characters, '-' before this page,
           '=' on cyan for this page, '-' after it, each part
           proportional to the list (rounded)
0Dh
"<action> (0..<last key>), (B)ack" 0Dh "or (F)orward a page, (N)=quit?"
00h
```

The keys are `0123456789QWERTY` — the top row of the keyboard, so sixteen
choices sit under one hand; `LISTMENU_CHOICES` maps their codes to 0–15
([tspico-state.md](tspico-state.md#listmenu_choices)). `send()`, then
`CMD_KEY()`; the table is on `k = KEY_UP(ch)`, so lower-case letters (the
ROM sends keys as typed) work as their capitals:

| Key | Effect |
|---|---|
| `N` or `n` | the ROM reads on (#227): the key as typed, then the end below (`03h`), and `-1` |
| `B` (66) | back a page (to the first page from the first) and redraw |
| a choice key, on an entry that exists | the echo, then 32 × (`08h 20h 08h`), `0Dh`, 32 × (`08h 20h 08h`) — erasing the two prompt lines — and the choice is made |
| a choice key past the end of this page | as F |
| anything else (F …) | forward a page if there is one, else redraw this one; the echo is `F` (46h) whatever the key |

After a choice: `chosen`, `0Dh`, the entry, `0Dh`, `03h`; `send()`;
`CMD_DRAIN()`; RX emptied; return the index (`-1` after `N`, which leaves
`sel` at `-1`). The echoes are `ch`, the key as it came.

**An empty list** gets one page that says so: `86h`, `1`, `0Dh 0Dh`,
`hdr1` on the bar, `0Dh`, `(no items available)`, `03h` — no key wait —
and `-1`. Before this guard an empty list skipped the page loop and sent
only the final `03h`: the Z80 read it as the command's status, Report F
(`SAVE "tpi:cd"` in a folder with no subfolders). `IDIR` and `CDIR` take
`-1` as "cancelled".

Beware:

- Nothing may be sent after it returns (the comment at 3488): the
  exchange is over. `IDIR` therefore mounts the chosen file without
  reporting errors to the 2068 ("Can't set or show error now").
- The entries are printed as they are, so the caller must make them
  32-column safe (`IDIR` passes `"%03d " + shorten_filename(xstr(f), 26)`).
- The colours (blue bar `PAPER 1 INK 7`, cyan `PAPER 5 INK 9`, blue ink
  `INK 1`) are sent with `CmdOut` a byte at a time; none is `00h` or `03h`.

### `SEND_MSG_PROMPT_YN(prompt, echo=True, lower=False)`

One question, one key: returns the key's code. With `lower`, the question
is asked on the lower screen with function `88h`, so it does not write
over the picture. `88h` belongs to the ROM's disk module
([../rom/exrom-fdd.md](../rom/exrom-fdd.md)); pass it only for a command
that module sent: `tpi:fopen`'s "Replace NAME? (Y/N)" before `SAVE "f:x"
SCREEN$` overwrites a file (3109), kept to one line.

1. `88h` if `lower` else `86h`; status `1`; `0Dh` unless `lower` (the
   lower screen starts clear).
2. `CMD_RX_FLUSH()`.
3. The prompt, `00h`; `send()`; `CMD_KEY()`.
4. Any key, `N` included (the ROM reads on after it, #227): the echo (if
   `echo`; the key as typed, or `Y` for one outside 32–127), a `0Dh` if `lower` (so what the ROM prints next,
   "Start tape…", starts on its own line), `03h`; `send()`; `CMD_DRAIN()`;
   RX emptied; return `KEY_UP(ch)`, the key in upper case, so a caller's
   test for 89 (`Y`) holds whatever case was typed.

The status is always 1. The callers act on the key: `GETLOG`'s "Clear the
log file (y/N)?" (4688) and `RM`'s "Remove NAME (y/N)?" (5490) go on only
for 89 (`Y`), and the question is the whole answer — a refusal reaches only
the log. `tpi:fopen` records anything but `Y` as a refusal that `SAVE_TS`
turns into Report D at the header. All callers use `echo=True`.

Beware: like the other builders it ends the exchange; the comment at the
top says "this cannot be followed by another SEND_MSG* call". The RX
drain runs before anything is sent (`CMD_RX_FLUSH`), as the comments here
(5399–5401) and in `ListMenu` (3503–3506) say.

## Card names as the 2068 shows them

### `xchr(m)`

`catalog.screen_name(m)`: the character as the 2068 lists it — itself, or
`?` for one it cannot print or type back (below space, above `~`, or in
`catalog.UNSHOWABLE`; [catalog.md](catalog.md)). `|` and `~` used to
become " STICK " and " FREE ", what the 2068 prints for them, but nobody
could type those back into `LOAD "tpi:…"`; now they are `?`, which
`LOAD_TPI` takes as a wildcard for one such character. One caller, `xstr`.

### `xstr(s)`

`"".join(xchr(m) for m in s)`: a name as the 2068 lists it. Every name from
the card that is printed goes through it: the disk-command messages (2666,
2694, 2888, 2917, 3142), `IDIR`'s menu (3469), `public_path` and
`public_fname` (3900, 3916). Because of it, the text `SEND_MSG2` gets from
a listing has no control codes and no `|` or `~`.

### `BUILD_FIT(s, n)`

The build stamp in at most `n` characters. `s` is `BUILD_VERSION`, "commit
(branch)" ([tspico-state.md](tspico-state.md#build_version)). If it fits,
or is not of that shape, it is cut to `n`. Otherwise the commit is kept
whole and the branch cut to fit with `..`: `"abc1234 (long-bra..)"`; if
not even one branch character fits, the commit alone, cut to `n`. `..`
rather than `~` because `~` prints as FREE. One caller, `GETINFO` (4616),
which gives it 22 columns after the 10-column label.

## Where comments and the code disagree

None known. #181 brought the last ones into line with the code: Y "kept
at READY for the entire session" (the PIO drops it on every Z80 OUT), the
`st: bytes` annotations (an int), `SEND_MSG2`'s inline-wrt history (pages
are built in RAM and sent with `CMD_SEND`) and the RX drain's place
(before READY).
