# catalog.py — names, wildcards, paths, listings

Source: [`src/TS/catalog.py`](../../../src/TS/catalog.py) (313 lines).

The pure half of `CAT` / `SAVE "tpi:dir <arg>"`, and of every other
command that takes a path: pattern matching, path resolution inside the
card's public root, TAP block tables and the text of the listings. Nothing
here touches the SD card, the PIO or the TS-Pico globals; `tspico.py` does
the I/O with the card active and hands the results in. That split keeps
every rule testable on the host
([`src/test/catalog_hosttest.py`](../../../src/test/catalog_hosttest.py);
the layouts are also read by `screen_colour_hosttest.py` and the dirinfo
tests, which is why they stay plain text). The contract is
[DISK_COMMANDS_SPEC.md §2 and §3](../../DISK_COMMANDS_SPEC.md); the
user's view is [user-manual.md chapter 3](../../manual/user-manual.md).

Callers outside [tspico-disk.md](tspico-disk.md): `LIST_DIR_FILES`
(`screen_name`, `size_text`, `space_pair`, `DIR_EXT`), `OFF_TABLE`
(`tap_table`), `TAPDIR` (`tap_header_rows`), `xchr` (`screen_name`),
`GETINFO` (`space_pair`), `ChangeDir` (`resolve`), `LOAD_TPI` (`has_wild`,
`match_shown`), `RM_CHECK` (`resolve`, `ROOT`, `within`) — all in
[tspico-files.md](tspico-files.md) and
[tspico-commands.md](tspico-commands.md).

## Map of the file

| Lines | What |
|---|---|
| 10–22 | `ROOT`, `DIR_EXT`, `BLK_TYPES`, `UNSHOWABLE` |
| 25–70 | `screen_name`, `match_shown`, `has_wild`, `match` — names and wildcards |
| 73–133 | `resolve`, `public`, `split_arg`, `split_pair` — paths and arguments |
| 136–174 | `select`, `basename`, `parent`, `within` |
| 177–246 | `size_text`, `space_pair`, `counts`, `dir_rows` — the directory listing's text |
| 249–313 | `tap_table`, `tap_header_rows` — a TAP's blocks and their listing |

## Constants

| Name | Value | Meaning |
|---|---|---|
| `ROOT` | `"/sd/TAP"` | the real directory that is `/` to the user. Every public path is resolved under it and never above it |
| `DIR_EXT` | `('TAP', 'TZX', 'DCK', 'ROM', 'BIN')` | the extensions a plain listing numbers, and `DIR_FILES` indexes into `files` and `dirinfo.tap`; compared against a name's last three characters, upper-cased |
| `BLK_TYPES` | `('Program', 'Num. array', 'Char array', 'Code block')` | the tape header's type byte 0–3, as the TAP listing names it |
| `UNSHOWABLE` | `"{\|}~\x7f"` | characters a Mac or PC name may hold that the 2068 cannot show as themselves or type back: its character printer (HOME 063Bh) prints `\|` and `~` as the STICK and FREE keywords always, `{`, `}` and 7Fh as ON ERR, SOUND and RESET unless FLAGS bit 4 is set, and none of the five is on its keyboard (the comment at line 17) |

## Names and wildcards

### `screen_name(s)`

`s` as the 2068 lists it: every character below `" "`, above `"~"` or in
`UNSHOWABLE` becomes `?`. `LOAD "tpi:..."` then takes that `?` as a
wildcard (`LOAD_TPI`), and `?` cannot be part of a FAT name, so it never
collides with a real one. Used by `dir_rows`, `xstr`/`xchr` in `tspico.py`,
and `match_shown`. Pinned: `{a}|b~c\x7fé.tap` → `?a??b?c??.tap`; `GAME
(1).TAP` unchanged.

### `match_shown(name, pat)`

Does `pat` match `name` as the 2068 lists it? `match(screen_name(name),
pat, False)`: case-insensitive, `*` any run, and `?` only a character the
2068 cannot show — which is what a `?` in a listing stands for — so
`?game?.tap` finds `{game}.tap` and not `(game).tap`. Used by `LOAD_TPI`
to mount by a wildcarded name typed from a listing. Pinned by the
"match_shown" checks.

### `has_wild(s)`

`*` or `?` in `s`. Used by `split_arg` and `LOAD_TPI`.

### `match(name, pat, any_q=True)`

A case-insensitive glob. `*` matches any run, including none; `?` matches
one character when `any_q` is true, and only a literal `?` when it is
false (for `match_shown`). The loop walks `name` with one backtrack point:
a `*` records its position and the name position, and on a mismatch the
match resumes one character further into the name; trailing `*`s are
skipped; the pattern must be used up. Pinned: `*` is case-insensitive;
`*` alone matches the empty name, an empty pattern does not; `?` is
exactly one; several `*`; `*.c` wants the last dot.

## Paths and arguments

### `resolve(cur, arg)`

The real path for a public path argument, or `None` if it leaves the
root. `cur` is the real current directory (`TSP.cur_path`); it must be
`ROOT` or below it, else `None` (unless `arg` is absolute). A leading `/`
starts at the public root; `.` and empty components are ignored; `..` pops
one component and gives `None` at the root. The result is `ROOT` joined
with the components, with no check that it exists and no case change.
Used by every path-taking handler; the 2026-09-30 audit made `ChangeDir`
go through it as well (`audit_fixes_hosttest.py` items 4/5). Pinned: `""`
is the current directory; relative; `..` up; `..` above the root refused;
`/UTILS` from the root; `/` alone; `a/./b//c`; a `cur` outside the root
refused.

### `public(real)`

The public form of a real path: `"/sd/TAP/GAMES"` → `"/GAMES"`, `ROOT` →
`"/"`. Assumes `real` starts with `ROOT`.

### `split_arg(arg)`

`"games/*.tap"` → `("games", "*.tap")`: the directory part and the last
component, which is the pattern only when it holds a wildcard — otherwise
`(arg, None)`. The directory part is `''` for the current directory and
`'/'` for a pattern at the root. `arg` is stripped first. Pinned: a bare
pattern, dir + pattern, root + pattern, a plain name, spaces stripped.

### `split_pair(arg)`

`"a.tap|b.tap"` → `("a.tap", "b.tap")`. The ROM joins MOVE's two names
with `|`, which FAT names cannot contain; typed by hand, `SAVE "tpi:copy a
b"` with a single space works too (exactly two words). Either half is `''`
when missing: with no `|` and not two words, the whole stripped text is
the first half. Used by `DISK_COPY` and `DISK_REN`.

## Selecting entries

### `select(items, pat)`

What CAT lists from a directory's `os.ilistdir()` items, in its order:
`[(name, is_dir, size)]` — directories, then files, then (bare listing
only) the files `DIR` cannot index. Items are sorted case-insensitively.
`dirinfo.tap` is never listed; dot names only when the pattern starts with
a dot; with a pattern, a non-match is dropped. A directory (type 16384)
goes to the first group with size 0; with no pattern a file whose last
three characters are not in `DIR_EXT` goes to the third group; everything
else to the second, with its size (`item[3]`). With a pattern every match
is therefore in the second group, in name order. Shared by `CATALOG_TEXT`
and `DIR_NAMES` (`OPEN #n,"d:..."`), so both show the same entries.

### `basename(path)`

The text after the last `/` (the whole string if there is none).

### `parent(path)`

The text before the last `/`, or `ROOT` when that is empty. For a path
with no `/` it would return all but the last character; every caller
passes a real path under `ROOT`.

### `within(path, top)`

True if `path` is `top` or somewhere below it, case-insensitively as FAT:
equal, or starting with `top + '/'`. Used to protect the current directory
and the mounted file.

## The directory listing's text

### `size_text(size)`

A file's size for the listing's 10-character column: below 1024 `"%d B"`;
below 10 kB `"%.1f kB"`; below 1 MB whole kB, rounded; from 1 MB `"%.1f
MB"` (1 kB = 1024). The docstring records why: it used to be `"%.2f kB" %
(size >> 10)`, the shift dropped the fraction first, and every size read
`.00 kB` (2026-09-30 audit §4; changed 2026-10-02). The Commander reads
only the index and the name from `dirinfo.tap`'s rows, so the size text is
free to change within its column. Pinned: `900 B`, `1023 B`, `2.5 kB`,
`47 kB`, `48 kB`, `16 kB`, `1.2 MB`, `4096.0 MB`; every one fits 10
characters.

### `space_pair(total, free)`

`("240 MB", "236 MB")` for a card or flash of `total` bytes with `free`
left. The unit comes from the total, so both read alike: GB with one
decimal from 1 GB, whole MB from 10 MB, MB with one decimal from 1 MB,
whole kB below. The CAT header used to give GB to four places whatever the
size, so the 256 MB cards the boards ship with read `SD: 0.2346GB` (the
docstring; audit "to do", #120). Used by `LIST_DIR_FILES` for the `SD:`
line and by `GETINFO` for flash and card.

### `counts(nf, nd)`

`"3 files, 1 dir"`, with the plurals right. The second header line of a
filtered or other-directory listing. Pinned: `counts(1, 1) == "1 file, 1
dir"`.

### `dir_rows(entries, index_of, shorten)`

The listing rows, 32 characters each and no CR (the screen wraps), for
`entries = [(name, is_dir, size)]` already sorted and filtered by `select`.
`index_of(name)` is the number `LOAD "tpi:n"` uses for the file, or `None`
when it has none (another directory, or a type `DIR` does not index);
`shorten` is `tspico.shorten_filename`, so names are cut the same way
everywhere (the middle replaced by `>`). Every name goes through
`screen_name`. A directory: `"<%-21s       0 B"` of the name shortened to
20 plus `>` — 1 + 21 + 10. A file: `"%s %-18s%10s"` — a three-digit index
or three spaces, a space, the name shortened to 18, `size_text` in 10. The
caller (`CATALOG_TEXT`) puts `DIR_HEADER`'s four rows in front;
`CAT_COLOUR` recognises the rows by their first characters (`<`, three
digits, four spaces). Pinned: dirs, indexed and unindexed files; every row
32 characters; `{x}.TAP` shown as `?x?.TAP`.

## A TAP's blocks

### `tap_table(f)`

The block table of the TAP file open in `f` (binary, seekable): the shape
`OFF_TABLE` has always built for the mounted file, one entry per block,
`[offset, length, " Y"/" N", name]`. The file is read 14 bytes at a time:
`length` is the TAP's two-byte count (payload plus flag and checksum); a
block whose flag byte is 0 and whose 14 bytes are all there is a header
(`" Y"`), its name the 10 bytes after the type, each kept as it is when
32–127 and `?` otherwise, and its type `BLK_TYPES[type]` (an invalid type
gives `??????????` and `undefined`); any other block is `" N"` and takes
as its name the type of the last header seen, or `Code block` when there
has been none. The next offset is `offset + length + 2`; the loop stops
when fewer than two bytes remain, and does not check that a block's
declared length fits the file.

The comment on the name explains the choice: the 2068 wrote it, so its
bytes are sent as they are and `|` shows as STICK exactly as it does
elsewhere on the 2068; only what `SEND_MSG2` cannot carry — control codes,
and 80h and above, which would end the ROM's string — becomes `?`. That is
the opposite of `screen_name`, which is for names typed on a Mac or PC.
Used by `OFF_TABLE` (`TSP.offset_tbl`) and `CATALOG_TEXT` for an unmounted
TAP. Pinned: five blocks with the right offsets, names and lengths (a
300-byte code block is 302); an empty file is `[]`; a header name's bytes
kept with 80h+ as `?`.

### `tap_header_rows(tbl, cur_idx=None, idx1=0, idx2=None, orphans=False)`

`TAPDIR`'s header listing rows (`CODE 1,n`) for any block table, returned
as a flat list of pieces, four per row, 32 characters a row. A row is
produced for each header; for the block at `cur_idx`, the tape position,
marked `>` instead of a space (`None` when the table is not the mounted
file's); and, with `orphans`, for each data block that has no header in
front of it (a loader, headerless code), which `TAPDIR` shows only when
the tape is positioned on one. The pieces: the mark; `"%02d "` the index;
for a header followed by a block, that block's name field (the type set
from this header) in 10 and its length in 5, or `(no data)` and 0 for a
header at the end; for a data block `"Data block"` and its length; then
the name in 10 — the header's file name, `Data block`'s type, or
`headerless` for an orphan when `orphans` is set. `idx1`–`idx2` limit the
range. The length shown for a header's row is the data block's TAP length,
two more than its payload. Used by `TAPDIR` and `CATALOG_TEXT`
(`orphans=True`). Pinned: headers only by default; `orphans=True` shows
the headerless block, named so; the position is marked, even on a data
block; every row is 32 characters.
