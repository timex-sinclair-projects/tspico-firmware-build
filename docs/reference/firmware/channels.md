# channels.py — `OPEN #` channels: streams, records, text conversion

Source: [`src/TS/channels.py`](../../../src/TS/channels.py) (557 lines).

The Pico half of `OPEN #n,"f:name"`, `OPEN #n,"d:spec"`, `OPEN #n,"x:"`
(commands, #404) and, on the v3 card, `OPEN #n,"v:"` (speech). The ROM's
channel driver ([rom/exrom-fdd.md](../rom/exrom-fdd.md)) sends what BASIC
prints to a stream as raw 2068 bytes — tokens, control codes, CR — and asks
for bytes when BASIC reads. This module keeps one `Channel` per stream
number in a `Channels` table and does everything that is not I/O: the mode
rules, the position, TAB as a seek, fixed-length records, directory
listings and command answers held in memory, and the translation between 2068 text and the
UTF-8, LF-ended text a Mac or a PC writes. File access comes in from
outside as an object with four methods (`SD_FS` in
[tspico-disk.md](tspico-disk.md); a dictionary in the host test), so the
whole module runs and is tested on the host:
[`src/test/channels_hosttest.py`](../../../src/test/channels_hosttest.py).
The card is unmounted between commands, so no file stays open: every
operation opens, seeks to the saved position, reads or writes, and closes.
There is no block cache on the Pico: the spec's "Buffering" paragraph
(§4b, one 256-byte block per channel, written back when evicted) describes
an earlier design; the only buffers are the ROM's 64-byte output and
255-byte input buffers, and every `tpi:chwr` reaches the card at once.
The handlers that call it are `CH_OPEN`, `CH_WRITE`, `CH_READ` and
`CH_CLOSE` ([tspico-disk.md](tspico-disk.md)); the contract is
[DISK_COMMANDS_SPEC.md §4 and §4b](../../DISK_COMMANDS_SPEC.md), the
user's view [user-manual.md chapter 6](../../manual/user-manual.md), the
wire view [PROTOCOL.md §7](../../PROTOCOL.md) and
[programmers-manual.md chapter 6](../../manual/programmers-manual.md).

The header comment names the three stages: stage 1 (#83) sequential text
and binary files in modes `r`, `w`, `a`; stage 2 (#84, spec §4b) `TAB` as
the position, mode `u`, record files; stage 3 (spec §4) `d:` listings. A
fourth paragraph adds the speech channel (#375): write-only, no file, each
line spoken when its CR arrives, and never in need of the card. A fifth
adds the command channel (#404): each line printed to `x:` is a command
(`path`, `dir`, `mount`, `info`), and `INPUT #` reads its answer, plain
lines for a program rather than text laid out for the screen, held in
memory like a `d:` listing.

## Map of the file

| Lines | What |
|---|---|
| 29–50 | `TOKENS`, `EXTRA`, `POUND`, `keyword` — the 2068's keywords by code |
| 53–100 | `TextOut` — 2068 output bytes to text-file bytes |
| 103–160 | `LATIN1`, `UTF8`, `TextIn` — text-file bytes to 2068 input bytes |
| 163–182 | `utf8_len` |
| 185–210 | `Channel` — one stream's state |
| 213–228 | `ChannelError`, `MAX_RECLEN`, `parse_mode` |
| 231–550 | `Channels` — the table and every operation on it |
| 553–579 | `_split_cr`, `_one_line` |

## The keywords

| Name | Value | Meaning |
|---|---|---|
| `TOKENS` | a tuple of 91 strings, `"RND"` … `"COPY"` | the keywords for codes A5h–FFh, in the 2068's order: the Spectrum's A5h–FFh, with the Spectrum's `CAT`, `FORMAT`, `MOVE`, `ERASE`, `OPEN #`, `CLOSE #` at CFh–D4h |
| `EXTRA` | `{12: "DELETE", 123: "ON ERR", 124: "STICK", 125: "SOUND", 126: "FREE", 127: "RESET"}` | the 2068's six extra keywords at low codes; 123–127 are what its printer shows for `{`, `\|`, `}`, `~` and DEL |
| `POUND` | 96 | the 2068's pound sign (where ASCII has a backquote) |

### `keyword(code)`

The spelling of a token byte: `TOKENS[code - 0xA5]` for codes from A5h,
else `EXTRA.get(code)` (`None` for anything else). Called by
`TextOut.feed` only for codes it has already tested, so the `None` case is
never printed.

### `TextOut`

2068 output bytes → text-file bytes: UTF-8, LF line ends. One per
`Channel`, created in `Channel.__init__`; stateful, because a control
code's parameters can arrive in the next `tpi:chwr`. The rules (its
docstring): keywords are spelled out with spaces around them as LIST shows
them; the comma control (6) becomes spaces to the next 16-column stop; INK
… OVER (one parameter) and AT / TAB (two) are dropped with their
parameters; other control codes are dropped; block graphics and UDGs
become `?`.

`PARAMS = {16: 1, 17: 1, 18: 1, 19: 1, 20: 1, 21: 1, 22: 2, 23: 2}` — the
number of parameter bytes after each control code. 23 (TAB) never reaches
`TextOut` from `Channels.write`, which takes it as the seek escape first
(`PROTOCOL.md` §13, "Byte 23 in a channel write is always a TAB").

### `TextOut.__init__(self)`

`skip` (int, 0): parameter bytes still to drop. `col` (int, 0): the
column, for the comma control. `last` (str, `"\n"`): the last character
put, for the space before a keyword.

### `TextOut._put(self, out, s)`

Appends the UTF-8 of `s` to `out`, advancing `col` by one per character and
resetting it at `"\n"`, and records the last character.

### `TextOut.feed(self, data)`

Translates one chunk and returns `bytes`. For each byte: while `skip` is
set, drop it; 13 → `"\n"`; a code in `PARAMS` → set `skip`; 6 → `16 - col
% 16` spaces; `POUND` → `"£"`; 12, 123–127 or ≥ A5h → `keyword(b)` with a
leading space unless the last character was a space or newline, and a
trailing space; 32–122 → the character; ≥ 128 (below A5h) → `?`; anything
else (a control code without parameters) is dropped.

Pinned by `channels_hosttest.py`: a LIST line comes out as `  10 PRINT
"hi"; TAB 5` with LF; the comma control pads to column 16; AT and INK go
with their parameters, also when split across chunks; pound becomes UTF-8
and graphics `?`; code 123 is `ON ERR `.

Beware: 123–127 are spelled as keywords on the way out but kept as bytes on
the way in (`TextIn`), so text written with `PRINT #4;"a|b"` reads back as
`a STICK b`. That is what the 2068 itself prints for `|` (the note on
`UNSHOWABLE` in [catalog.md](catalog.md)); byte-for-byte round trips need
binary mode.

## Text from a Mac or a PC

| Name | Value | Meaning |
|---|---|---|
| `LATIN1` | `{0xA3: POUND, 0xA9: 127}` | a lone byte ≥ 80h that is not UTF-8 is Latin-1: £ → 96, © → 127 (the 2068's ©) |
| `UTF8` | `{"£".encode(): POUND, "©".encode(): 127}` | the two UTF-8 sequences with a 2068 character; any other valid sequence becomes `?` |

### `TextIn`

Text-file bytes → 2068 input bytes (its docstring): CR, LF or CRLF → CR
(13); TAB → space; ASCII 32–127 unchanged (so a program can look for
`CHR$ 124`, though the editor would print it as STICK); £ and © from UTF-8
or Latin-1 → 96 and 127; anything else ≥ 80h → `?`; other control bytes
dropped. Stateful across chunks for a CRLF split between them and for a
UTF-8 sequence cut at the end of one. The 2026-09-30 audit (§2 #20) found
the earlier version taking any byte ≥ 80h as the lead of a sequence, so
`b"x\xa3yz"` read as `x?z`, and dropping 123–127; now one such byte is
one Latin-1 character. One `TextIn` per `Channel`, replaced by a fresh one
on every seek and used once per record.

### `TextIn.__init__(self)`

`cr` (bool, False): the last byte was a CR, so a following LF is the same
line end. `pend` (bytes, empty): the tail of a UTF-8 sequence cut off by
the end of the previous chunk.

### `TextIn.feed(self, data)`

Prepends `pend`, clears it, and walks the bytes: 10 → 13 unless it follows
a CR; any other byte clears `cr`; 13 → 13 and sets `cr`; 32–127 → itself;
≥ 80h → `utf8_len`: −1 (cut off) keeps the rest in `pend` and stops, k > 0
maps the sequence through `UTF8` or to `?` (63), 0 maps the byte through
`LATIN1` or to `?`; 9 → 32; other control bytes dropped. Returns `bytes`,
never longer than its input. Pinned by the host test: LF, CRLF and CR all
become CR; a CRLF split across chunks is one CR; a UTF-8 pound split across
chunks is 96; `é` is `?` and tab a space; and by `audit_fixes_hosttest.py`
§2 #20: no byte dropped or swallowed.

### `utf8_len(data, i)`

The length of the UTF-8 sequence starting at `data[i]`: 2 for a lead byte
C2h–DFh, 3 for E0h–EFh, 4 for F0h–F4h, and each following byte must be a
continuation (10xxxxxx); 0 when the byte is a continuation byte, a never-lead
value (80h–C1h, F5h–FFh) or a continuation is wrong; −1 when the sequence
is valid so far but the chunk ends first.

## One stream

### `Channel`

The state of one open stream; a plain record of attributes, created by
`Channels.open`, `open_list`, `open_speech` and `open_command`, read and
written by the `Channels` methods.

### `Channel.__init__(self, path, mode, binary, pos, reclen)`

| Attribute | Type, initial | Meaning |
|---|---|---|
| path | str (None for `d:`, `v:` and `x:`) | the real file path |
| mode | `'r'`, `'w'`, `'a'` or `'u'` | after `parse_mode` |
| binary | bool | `b` in the mode: bytes pass through, padding is 0 |
| pos | int | the next byte of the file; a record file's current record starts here |
| reclen | int, 0 | 0 a stream; else the record length (1–`MAX_RECLEN`) |
| text_out | `TextOut` | the output translator |
| text_in | `TextIn` | the input translator, replaced on a seek |
| eof_cr | bool, False | a last line with no newline has had its CR supplied |
| last_raw | int, 10 | the last raw byte read, to know whether the file ended in a line end |
| tab | list or None, None | the TAB bytes still to come after a 23: a list collecting them across calls |
| fill | int or None, None | bytes written into the open record; None when no record is open |
| query | bool, False | `TAB 0` seen: the next read returns a count |
| mem | bytes, an answer, or None, None | a `d:` listing (the names) or an `x:` command's answer, not a file; an answer is bytes or anything with `len()` and `chunk(pos, n)` (`XDirText`) |
| count | int or None, None | … and how many names |
| say | function or None, None | a speech channel (`v:`): called with each line printed to it |
| line | bytearray, empty | … and the translated text so far, up to the next newline (speech and `x:`) |
| run | function or None, None | a command channel (`x:`): called with each line printed to it, returns the answer |

### `Channel.in_memory(self)`

True when the channel has no file behind it (`path` is None): a `d:`
listing, a `v:` speech channel or an `x:` command channel. Such a channel
is read and written with no card mounted (`Channels.in_memory`).

### `Channel.pad(self)`

The padding byte: `b"\0"` in binary mode, `b" "` in text mode. Used for
gaps written past the end of the file and for the unused rest of a record.

### `ChannelError`

`Exception(message, status)`: `status` is a one-letter report name, `"F"`,
`"Q"` or `"O"`, which `CH_CALL` turns into 3, 4 or 10 through `CH_STATUS`
([tspico-disk.md](tspico-disk.md); any other letter becomes Q). The
message reaches only the Pico's log: the channel commands answer with the
bare status.

| Name | Value | Meaning |
|---|---|---|
| `MAX_RECLEN` | 254 | the longest record: a record and its CR fit one 255-byte `tpi:chrd` reply, which is the ROM's `INMAX` buffer |

### `parse_mode(m)`

`"r"`, `"w"`, `"a"` or `"u"`, each with an optional `b`: returns `(mode,
binary)`. `None` or empty means `r`; case does not matter; every `b` is
removed; any other letter raises `ChannelError("Mode must be r, w, a or
u (+b)", "Q")`. The ROM sends `r` when the statement gives no mode.

## The table

### `Channels`

Open channels by stream number. `fs` provides the file access: `exists(p)`,
`size(p)`, `read(p, pos, n)` → bytes, `write(p, pos, data, truncate)`
(truncate: start the file empty). One instance, `CHANNELS`, lives in
`tspico.py` over `SD_FS` ([tspico-state.md](tspico-state.md),
[tspico-disk.md](tspico-disk.md)).

### `Channels.__init__(self, fs)`

`fs`: the file access. `table` (dict, empty): stream number → `Channel`.

### `Channels.open(self, stream, path, mode, reclen=0)`

Opens `path` on `stream`. `parse_mode`; a `reclen` below 0 or above
`MAX_RECLEN` raises `("Record length 1-254", "Q")` (the message says 1,
but 0 passes: it means a stream). Any entry the stream had is dropped
first, so a stream orphaned by NEW or a reset on the 2068 costs nothing.
`r`: the file must exist (`("Not found", "F")`), position 0. `w`:
`fs.write(path, 0, b"", True)` creates or empties it, position 0. `a` and
`u`: the file is created if missing; the position is the file's size for
`a` on an existing file, else 0. Stores the `Channel`. Does not check for
a directory: `CH_OPEN` does. Nothing stops one file being open on two
streams at once: the spec's rule (§4, "Open files": a second `OPEN #` of
the same file is Report F) is not in the code. Pinned by the host test: `w` writes and
truncates; `a` appends; `r` of a missing file F; a bad mode Q; re-opening a
stream replaces the stale entry; `u` creates a missing file; length 255 Q.

### `Channels.open_list(self, stream, names)`

`OPEN #n,"d:..."`: a read-only text stream over `names` joined with `"\n"`
and UTF-8 encoded into `mem`, `count = len(names)`. Reads come from `mem`
through the same text path, so a non-ASCII name arrives as `?` and each
name ends in a CR; `TAB 0` reads the count. Nothing is ever written to
such a channel (`_data` drops output to mode `r`). Pinned by `stage3`: one
name a line, a directory's with `/`; then end of file; `TAB 0` the count;
`TAB 8` from the second name; an empty listing reads end of file at once
and `TAB 0` says 0.

### `Channels.open_speech(self, stream, say)`

`OPEN #n,"v:"` on the v3 card (#375): a write-only channel with no file
(path `None`, mode `w`, so `read` says Q), and `say` (the firmware passes
`board.say`) kept in `ch.say`. Drops any stale entry for the stream first,
as `open` does. Called by `CH_OPEN` only after it checked that the board
has speech and the spec is `v:` alone.
Pinned by `channels_hosttest.py`'s `speech`: nothing said before a CR; a
line said at its CR; keywords spelled out; an empty line silent; two lines
in one write said apart; TAB ignored; `CLOSE` says the unfinished line,
and still closes with speech off; reading Q; an unknown allophone Q; a
stale file entry replaced.

### `Channels.open_command(self, stream, run)`

`OPEN #n,"x:"` (#404): a channel with no file (path `None`, mode `r`,
`mem` empty) and `run` kept in `ch.run` (the firmware passes `X_RUN`,
[tspico-disk.md](tspico-disk.md)). Each line printed to it is a command,
run at its CR by `_command`; `run(line)` gives the answer, which the next
`INPUT #` reads from its start through the ordinary text path (`read`:
each `\n` arrives as a CR). A new command replaces the answer; `run`
raises `ChannelError` for a command it does not know. The answer is
bytes, or anything with `len()` and `chunk(pos, n)`, so the dir listing is
made as it is read and never held in one piece. Drops any stale entry for
the stream first. Called by `CH_OPEN` once it checked the spec is `x:`
alone, with no record length.
Pinned by `channels_hosttest.py`'s `commands`: nothing to read before a
command (end of file); nothing run before a CR; the answer with LF → CR,
then end of file; spaces around a command dropped; a long answer read in
pieces through `chunk()`, never copied whole; a new command replaces an
answer read only in part; `PRINT #4` alone runs nothing; an unknown
command Q with the last answer gone; a keyword token spelled out (so not a
command, Q); TAB ignored; `CLOSE` closes it; a stale file entry replaced.

### `Channels.in_memory(self, stream)`

Is the stream open with no file behind it (`d:`, `v:`, `x:`)? True when it
has an entry and `Channel.in_memory` says so. `SD_NEEDED`, `CH_WRITE` and
`CH_READ` ask it, so writing to or reading from such a stream never mounts,
waits for, or needs the card.

### `Channels._command(self, ch, data)`

The bytes printed to an `x:` stream: through `text_out` (keywords spelled
out, control codes dropped, CR → `\n`) onto `ch.line`. For each complete
line: decoded and stripped; a blank one (`PRINT #4` alone) runs nothing.
Otherwise the last answer goes first (`mem` empty, `pos` 0, a fresh
`TextIn`, `eof_cr` false, `last_raw` 10), then `mem = ch.run(text)`. So if
`run` raises, nothing is left to read: an unknown command is Q on the
`PRINT`, and a following `INPUT #` is end of file, not the previous
answer. The ROM drops what it read ahead from the last answer on any
write to the stream (`CH_OUT`, R_FLAGS bit 2), so the two sides agree on
where the new answer starts.

### `Channels.write_text(self, stream, lines)`

`CAT #n` (#404): `lines` (strings of printable ASCII, from `SCREEN_LINES` in
`CH_CAT`) written into the file open on `stream` as if each had been
printed to it with a CR. Only a file opened to be written takes them: a
stream with no file (`d:`, `v:`, `x:`) or mode `r` is `("Not a file open
for writing", "Q")`; a stream that is not open is `_get`'s `O`. Each line
is encoded, a CR (13) appended, and the bytes go to `_data` in pieces of
512 or a little over, the last piece whatever is left, so a long listing
is neither one block in memory nor one card write a line. Going through
`_data` gives the same result as `PRINT #`: a text file gets LF line ends
(`TextOut`), a binary file the CRs, a record file one record a line, with
Q for a line longer than the record (*inferred:* the lines before it stay
written).
The lines hold no 23, so nothing is taken as a TAB. Pinned by
`channels_hosttest.py` (`cat_text`): LF lines at the file's position after
what was there; 100 lines in 7 writes of about 512 bytes; CRs kept in
binary; a record a line and Q for one too long; mode `r`, `d:` and `x:` Q;
a closed stream O.

### `Channels.speaking(self, stream)`

Is the stream open on speech? True when its entry has `say`. Not used by
the firmware since #404 (`SD_NEEDED` and `CH_WRITE` ask `in_memory`,
which covers speech); the host tests use it.

### `Channels._speak(self, ch, final=False)`

Says every complete line in `ch.line`: cuts at each `\n` (a CR, after
`TextOut`) and hands the text before it to `_say`, keeping the rest. With
`final` (at `close`), says what is left too if it is not blank. Why lines:
the rules turn text into sounds a phrase at a time, and the ROM's driver
sends a speech stream's bytes at each CR (`CH_OUT`, R_FLAGS bit 1), so a
line is normally one `tpi:chwr`; a line longer than the ROM's 64-byte
buffer arrives in pieces and is still said whole.

### `Channels._say(self, ch, text)`

One line to `ch.say`, decoded from UTF-8; a blank line says nothing (an
empty `board.say` would stop speech). A `ValueError` from the speech rules
(a `[NAME]` that is not an SP0256 allophone) becomes `("Not an allophone",
"Q")`. An `OSError` (speech never started) passes up for `CH_WRITE` to
answer J.

### `Channels._size(self, ch)`

The size: `len(ch.mem)` for a listing or an answer, else `fs.size(ch.path)`.

### `Channels._raw(self, ch, pos, n)`

`n` raw bytes at `pos`: `fs.read` for a file; a slice of `mem` when it is
`bytes` (a `d:` listing, a short `x:` answer); else `mem.chunk(pos, n)`,
an answer made as it is read (`XDirText`). Not slicing for those: a
slice object's `start` and `stop` are a MicroPython build option.

### `Channels._get(self, stream)`

The `Channel`, or `ChannelError("Stream not open", "O")` — Report J on
the 2068.

### `Channels._put(self, ch, pos, data)`

Writes `data` at `pos`; a gap past the end is filled with `ch.pad()` first,
so `fs.write` is always called at or inside the current size. It reads the
size from `fs`, never from `mem`: a listing never reaches it.

### `Channels._end_record(self, ch)`

Closes an open record: if `fill` is less than `reclen`, writes the padding
from `pos + fill` to the record's end; moves `pos` on by `reclen`; clears
`fill`. Does nothing when no record is open. This is the one write that
`Channels.close` can make, which is why `close_writes` exists.

### `Channels._seek(self, ch, n)`

`TAB n`. On a record file an open record is closed first. `n == 0` sets
`query` and leaves the position: the next read is a count. Otherwise
`query` is cleared and `pos = (n - 1) * (reclen or 1)`: record `n` of a
record file, byte `n` of a stream, both 1-based (spec §4b). A fresh
`TextIn`, `eof_cr` false and `last_raw` 10, so what was read ahead is
forgotten; the ROM does the same on its side (`CH_OUT` clears its input
buffer on a 23).

### `Channels._data(self, ch, data)`

Bytes to store (no TAB among them) at the channel's position. A command
channel (`x:`): to `_command`, before the mode test. Mode `r`:
dropped — INPUT #'s prompt items go to the stream too (spec §4b). A speech
channel: the bytes go through `text_out` (keywords spelled out, control
codes dropped, CR → `\n`) onto `ch.line`, and `_speak` says each line now
complete; nothing else applies. After
`TAB 0`: `("TAB 0 is only for reading", "Q")`. A stream: the bytes
(binary) or `text_out.feed(data)` (text) are written at `pos`, which
advances. A record file: `_split_cr` cuts the data at each CR; a CR opens
an empty record if none is open (`PRINT #4;TAB n` with no items) and ends
it with `_end_record`; other parts are translated, and a part that would
overrun the record raises `("Longer than the record", "Q")` with nothing
written — the ROM flushes at every CR on a record file, so the report
lands on the PRINT that made the record too long. The CR itself is never
stored in a record.

### `Channels.write(self, stream, data)`

What BASIC printed to the stream, with TAB as 23, low, high. Scans the
bytes: while `ch.tab` is collecting, the byte joins it and the second one
completes `n = lo | hi << 8` for `_seek` (on a speech or command channel
the TAB is dropped: there is no position); a 23 sends the run so far to
`_data` and starts collecting; any other byte joins the run; the final run
goes to `_data`. The TAB's bytes may arrive in later calls (pinned: `TAB
15` sent one byte per chunk). Called by `CH_WRITE`. Pinned by `stage2`:
`TAB 3;"carol"` pads records 1–2 and fills 3; a record written in two
chunks; after writing record 2 the next read is record 3; `TAB 0` then
data Q; longer than the record Q with the record untouched; a record left
open by `;` is padded at close; binary records pad with 0; on a `u` stream
a write after a read lands right after that line.

### `Channels.read(self, stream, n)`

Up to `n` bytes for the 2068, or `b""` at the end of the file (`CH_READ`
sends status 7, Report 8). Mode `w` or `a`: `("Opened for writing",
"Q")`. After `TAB 0`: the count as text and a CR — the number of names of a
listing, else `ceil(size / (reclen or 1))`: records, or bytes for a
stream. A record file: an open record is closed, then exactly one record —
`fs.read` of `reclen` bytes padded to `reclen` — translated by a fresh
`TextIn` unless binary, plus a CR; past the end, `b""`. A binary stream:
`min(n, size - pos)` raw bytes. A text stream: a loop that reads
`min(n, size - pos)` raw bytes, cuts a `u` stream's chunk at its first line
end (`_one_line`, so a PRINT after an INPUT lands right after the line),
advances `pos` by the raw length, remembers the last raw byte, and returns
`text_in.feed(raw)` if that is non-empty, else reads again; at the end, a
last line that had no newline gets one CR (`eof_cr`), then `b""`. The
output is never longer than `raw`, so never longer than `n`. Called by
`CH_READ`. Pinned: reading back in 4-byte chunks; a last line without a
newline ends in CR once; binary round-trips every byte but 23; a write
channel Q; a closed stream O; `u` reads one line at a time; `TAB 6` from
byte 6; `TAB 0` on a stream is the size; `r` with a record length reads
the padded gap record.

### `Channels.close(self, stream)`

Closes the stream; a stream that is not open is not an error. A record
file's open record is padded first (`_end_record`), and the entry leaves
the table only after that write succeeded: if `fs.write` raises (no card,
an SD error), the stream stays open, which matches the ROM's `CLOSE #`,
which reports the error before freeing its side of the channel, so the
statement can simply be repeated once the card is back (the docstring;
`CH_CLOSE` in [tspico-disk.md](tspico-disk.md)). A speech channel says
what is left of an unfinished line (`PRINT #4;"bye";` then `CLOSE #4`)
with `_speak(final=True)`; a `ChannelError` or `OSError` from that is
swallowed, because closing must still close.

### `Channels.close_writes(self, stream)`

Will `close(stream)` write to the file? True only for a record file with a
part-written record (`reclen` set and `fill` not None). The firmware asks
first because mounting the card costs ~0.1–0.3 s or fails with no card in,
and CLOSE # of anything else must work without one (the docstring; the
2026-09-30 audit, §1 item 3; `audit_fixes_hosttest.py` `test_ch_close`).

### `Channels.close_all(self)`

Empties the table. Called by `SD_REVALIDATE` ([tspico-files.md](tspico-files.md))
when a different card has been mounted: the paths belonged to the old
card. The 2068's records are not told; its next OPEN # of each stream
replaces the entry anyway.

## Helpers

### `_split_cr(data)`

`data` split around its CRs into a list of parts and `b"\r"` markers:
`[b"ab", b"\r", b"c"]`. Empty parts are not produced. Used by `_data` for
record files.

### `_one_line(raw)`

`raw` up to and including its first line end — LF, CR, or CR LF taken
together — or all of it when there is none. Used by `read` on a `u`
stream so that a read stops at the line end and the position is right for
a following write.
