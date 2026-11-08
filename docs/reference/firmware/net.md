# The archive over WiFi (`net.py`)

Source: [`src/TS/net.py`](../../../src/TS/net.py), frozen into the v3 card's
build only (`src/boards/TSPICO_V3/manifest.py`). It is the text side of
`tpi:net`: the item's URLs, a folder index read into entries, the list kept
between commands, and the search. The fetching is board_v3's `wifi_get`
([board.md](board.md#wifi_geturl-buf)); the commands are `NET` and its
helpers in `tspico.py`
([tspico-commands.md](tspico-commands.md#netpre-cmd)). The design is
[docs/v3-wifi-archive-proposal.md](../../v3-wifi-archive-proposal.md).

The tapes are plain files in the `tspico-2068-tapes` item on archive.org
(#401), laid out by `tools/sd-archive/tap_folder.py`, whose docstring
defines the formats read here:

- `TAP/.../index.txt`, `index2.txt`…: a folder's index in parts of at most
  8 KB. A `#tspico-dir` header, whose sixth field is "part *k* of *n*",
  then `name/ D title tapes` for a subfolder and `name.tap status title
  year publisher size post` for a tape.
- `tspico-taps.txt.gz`: every tape, `path status title year publisher size
  post`, with the path from `TAP/`.

All are tab-separated UTF-8. The 2068 is sent ASCII only (`row`).

`NET` imports the module after a `gc.collect()`, the first time a
`tpi:net` runs; it stays loaded (memory.md rule 2). It holds no state
between commands except on flash (`LIST_PATH`).

## Constants

| Name | Line | Value |
|---|---|---|
| `ITEM` | 19 | `https://archive.org/download/tspico-2068-tapes/`: every URL starts here |
| `ROOT` | 20 | `"TAP"`: the top folder, the categories' index |
| `FULL` | 21 | `"tspico-taps.txt"`: the full index's name in the item (fetched as `FULL + ".gz"`) |
| `FULL_WBITS` | 22 | 12: the `.gz`'s window, 4 KB, as `tap_folder.py`'s `GZ_WBITS`; `NET_INFLATE` allocates it, and 32 KB didn't fit under the running firmware |
| `FULL_PATH` | 23 | `/sd/tspico-taps.txt`: the gunzipped copy on the card, outside `/TAP`, so no listing shows it |
| `LIST_PATH` | 24 | `/TMP/net.txt`: the last list, on the Pico's flash |
| `SAVE_DIR` | 25 | `/sd/TAP/NET`: where downloads go (David, 2026-11-07) |
| `MAX_FIND` | 26 | 99: the most matches `find` keeps; three digits for the 2068's numbers |

## Functions

### `part_url(folder, part)`

The URL of a folder's index part: `index.txt` for part 1, `index2.txt`…
after.

### `tape_url(path)`

`ITEM + path`. The item's paths are 8.3 names with no spaces, so nothing is
quoted, and the longest `AT&G` line is far under Zimodem's 256 bytes.

### `parent(folder)`

The folder above, or `ROOT` at (or above) the top: `tpi:net ..`.

### `parse_part(text, folder)`

One index part's text as `(parts, entries)`. `parts` comes from the header
("part 1 of 2"), 1 if it has none. An entry is `("D", path, title, count)`
for a subfolder (its trailing `/` dropped) or `("T", path, status, title,
size)` for a tape, with `path` the folder plus the name. A line too short
for a tape is skipped.

### `find(f, words, limit=MAX_FIND)`

The tapes in the full index (an open text file, read a line at a time)
whose path and title hold every word, in any case: `(entries, matched)`.
Entries stop at `limit`, the count doesn't. The header and short lines are
skipped. A line that doesn't hold every word somewhere is skipped before
it is split: most lines, and the search of 2,300 takes about 3 s on the card.

### `save_listing(where, part, parts, rows, path=None)`

Keeps a list for `tpi:net <number>`, `more` and `..`: a `#` line with
`where` (a folder, or "find *words*"), `part` and `parts`, then one
tab-joined line per entry. On flash, not in RAM: rule 3, nothing kept
between commands. It is written after the fetch, never during it. `path`
None means `LIST_PATH`, read at the call, so a test can move it.

### `load_listing(path=None)`

`(where, part, parts, rows)` of the kept list, or `None` if there is none
or its header is short.

### `name_of(entry)`

The last part of an entry's path: a tape's file name, or a folder's.

### `row(i, entry, width=32)`

One list line, after its number: a folder as "*NAME*/ *title* (*count*)",
a tape as its name without `.tap` padded to 8, its status letter and its
title. Cut to `width - 4` (the number and its space take 4), and anything
outside printable ASCII becomes `?`, so `SEND_MSG2` gets nothing it would
read as a 2068 keyword or control code. `i` isn't used.

### `HOW`, `how(status)`

How a tape loads, from its index status letter, for `NET_GET`'s answer:
L `LOAD ""`, R `LOAD "", then RUN`, C `LOAD "" CODE`, S (an ECM picture)
"load it with ecmvpico.tap". An unknown letter: `LOAD ""`.

`wifi_net_hosttest.py` checks `parse_part`, `row`, `parent`, `part_url`
and `find` directly, and the rest through `tpi:net`.
