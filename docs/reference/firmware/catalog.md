# catalog.py — names, wildcards, paths, listings

Source: [`src/TS/catalog.py`](../../../src/TS/catalog.py) (544 lines).

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
[tspico-commands.md](tspico-commands.md); `LIST_DIR_FILES` also takes
`card_line`, and `CARD_LABEL` ([tspico-bus.md](tspico-bus.md)) takes
`read_label`.

The file's end is not pure: `read_label` and `write_label` read and write
the card's raw sectors, through a block device the caller hands in (the SD
driver, `SD_DEV` in `tspico.py`), because MicroPython gives Python no way
to the FAT volume label.

## Map of the file

| Lines | What |
|---|---|
| 10–22 | `ROOT`, `DIR_EXT`, `BLK_TYPES`, `UNSHOWABLE` |
| 25–70 | `screen_name`, `match_shown`, `has_wild`, `match` — names and wildcards |
| 73–133 | `resolve`, `public`, `split_arg`, `split_pair` — paths and arguments |
| 136–174 | `select`, `basename`, `parent`, `within` |
| 177–246 | `size_text`, `space_pair`, `counts`, `dir_rows` — the directory listing's text |
| 249–313 | `tap_table`, `tap_header_rows` — a TAP's blocks and their listing |
| 316–354 | `LIST_TEXT_MAX`, `LIST_HEX_MAX`, `is_text`, `list_text` — LIST "name" |
| 357–383 | the label's comment, `LABEL_MAX`, `LABEL_BAD`, `label_clean` |
| 386–528 | `_u16`, `_u32`, `_is_vbr`, `_Fat`, `read_label`, `write_label` — the label in the card's sectors |
| 531–544 | `card_line` — CAT's card line |

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

`"a.tap|b.tap"` → `("a.tap", "b.tap")`. The ROM joins COPY's and MOVE's two names
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
else to the second, with its size (`item[3]`). With a pattern there is
no third group: matching directories come first, then every matching file,
in name order. Shared by `CATALOG_TEXT`
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
`CAT_COLOUR` recognizes the rows by their first characters (`<`, three
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

## LIST "name": a file as the 2068 shows it

| Name | Value | Meaning |
|---|---|---|
| `LIST_TEXT_MAX` | 8192 | the most of a text file `LIST "x"` shows |
| `LIST_HEX_MAX` | 2048 | the most of any other file: 256 rows of the hex dump. Also how much `DISK_LIST_WORK` reads first, to decide which the file is |

### `is_text(data)`

True if every byte of `data` is TAB, LF, CR, or 32 and up but not 127 (DEL).
Bytes from 80h up pass (UTF-8 or Latin-1 text), and `list_text` shows them
as `?`. Pinned: CR, LF and TAB are text; a 0 byte and 127 are not; é in
UTF-8 is.

### `list_text(data, size, text=None)`

`LIST "name"`'s text, from the first bytes of the file (`data`) and the
file's `size`. `text` says which form (default `is_text(data)`; the caller
passes what it decided on the first `LIST_HEX_MAX` bytes, so text that
turns binary further on still lists as text).

- **Text:** TAB becomes two spaces, CR and LF stay (`SEND_MSG2` breaks
  lines at them), every other character goes through `screen_name`, so
  what the 2068 can't show is `?`.
- **Anything else:** a hex dump, 8 bytes a row in 30 columns, CR-ended:
  the offset in four hex digits, the 16 hex digits, the bytes as
  characters (`.` for anything outside 32–126 or in `UNSHOWABLE`), as in
  `0000 4142434445464748 ABCDEFGH`; a short last row is padded so its
  characters line up.

When `data` is shorter than `size`, a last line `(the first N of M
bytes)`, after a blank one. Pinned: line ends kept, TAB as two spaces, `|`
as `?`; a binary row's layout and a short last row's padding; `|` and `~`
as `.` in a row; the "first N of M" line; with `text=True` a control code
is `?`.

## The card's label

MicroPython's `VfsFat` doesn't give Python the volume label: FatFs has
`f_getlabel` and `f_setlabel`, but the port compiles them only for mkfs
(the comment at 357–366). So these work in the card's raw 512-byte sectors
through `readblocks` and `writeblocks`, and `write_label` needs the card
unmounted, because FatFs keeps a sector of the root folder cached. The
label is in two places: a root-folder entry with attribute 08h, which
Windows and macOS show, and the boot sector's `BS_VolLab`, which DOS
showed. `read_label` reads the entry; `write_label` writes both, as FatFs
does. Pinned against FAT16 and FAT32 images built by
[`src/test/fat_image.py`](../../../src/test/fat_image.py), laid out like
images `newfs_msdos` made and `fsck_msdos` passed (*the real images were
checked by hand, 2026-10-29; the test uses the fakes*).

| Name | Value | Meaning |
|---|---|---|
| `LABEL_MAX` | 11 | a FAT label's length |
| `LABEL_BAD` | `"*+,./:;<=>?[\]\|` | characters FatFs's `f_setlabel` refuses |

### `label_clean(name)`

The label FAT would store for `name`: trailing spaces off, upper case. None
if it is longer than `LABEL_MAX`, starts with a space, or holds a
character below a space, above `~`, in `LABEL_BAD` or in `UNSHOWABLE` (the
2068 couldn't show it in CAT's card line). `""` is no label. Used by
`LABEL_SET`. Pinned: `games` → `GAMES`; `Games 2  ` → `GAMES 2`; `""`
and 11 characters pass; 12 characters, a leading space, `.`, `:`, `*`,
`|`, `é` and TAB are None.

### `_u32(b, i)`

The little-endian 32-bit number at `b[i]`. `_u16` (two bytes) is the same,
at line 386 (`native.py` has its own, [native.md](native.md)).

### `_is_vbr(b)`

True if sector `b` is a FAT boot sector with 512-byte sectors: the 55h AAh
signature, a jump (EBh, E9h or E8h) first, 512 bytes per sector, a power
of two sectors per cluster, one or two FATs and some reserved sectors.
FatFs's `check_fs`, simplified (inferred from the FatFs source; the
checks were chosen to take the cards `newfs_msdos` and SD Card Formatter
make).

### `_Fat`

The FAT volume on `dev`, found as FatFs finds it: sector 0 if it is a boot
sector, else the first of the MBR's four partitions whose first sector is
one. `OSError(19, "No FAT volume")` if neither.

### `_Fat.__init__(self, dev)`

Reads sector 0 and, through the MBR if need be, the boot sector. Keeps
`dev`, `start` (the volume's first sector), `boot` (its boot sector),
`spc` (sectors per cluster), `fat` (the first FAT's sector) and `fat32`
(the 16-bit FAT size is 0). FAT32: `data` (cluster 2's sector),
`root_clus`, the label at 71 and the extended signature at 66 in the boot
sector, `backup` (the backup boot sector, from offset 50). FAT12/16:
`root` (the fixed root folder's first sector) and `root_secs`, the label
at 43 and the signature at 38, `backup` 0.

### `_Fat.read(self, n)`

Sector `n` as a new 512-byte `bytearray`.

### `_Fat.root_sectors(self)`

Every root-folder sector, in order: the fixed area on FAT12/16; on FAT32
each cluster of the root's chain, read from the FAT, until an end mark
(0FFFFFF7h and up) or a cluster below 2. At most 65 536 clusters, so a
loop in a damaged chain ends.

### `_Fat.find(self)`

`(lab, free)`, each `(sector, offset, buf)` or `(None, None, None)`: the
label entry and the first free one. An entry is the label if its
attribute has 08h and is not a long-name piece (0Fh in the low six bits),
and its first byte is neither 0 nor E5h. A free entry is a deleted one
(E5h) or the first 0, where the search stops. `buf` is the sector as read,
for the caller to change and write back. Pinned (through `read_label`): a
long-name entry and a deleted label are not the label.

### `read_label(dev)`

The card's label, `""` for none; `OSError` if there is no FAT volume. A
first byte of 05h is E5h (FAT's escape for a name that starts with E5h);
anything outside 32–126 is `?`; trailing spaces go. Used by `CARD_LABEL`.

### `write_label(dev, name)`

Gives the card the label `name`, already in `label_clean`'s form; `""`
takes it off. `OSError` if there is no FAT volume.

- **A name:** a new entry, the name padded to 11 and attribute 08h, with
  no date, goes over the old label entry or else into the first free one;
  none free is `ValueError("Root folder full")` (FAT12/16's fixed root
  folder can fill; on FAT32 a full root folder's chain is not extended).
- **`""`:** the label entry, if there is one, is marked deleted (E5h).

Then, if the boot sector has the extended signature 29h, `BS_VolLab` is
the name padded to 11, or `NO NAME    `, and on FAT32 the backup boot
sector the same, if it is one. Used by `DISK_LABEL_WORK`, with the card
unmounted. Pinned: FAT16 (no MBR) — the label goes in a deleted slot with
the other entries untouched, and into the boot sector; a second label
replaces the first, leaving one entry; `""` deletes it and the boot
sector says `NO NAME`; a full root folder is ValueError with nothing
written, but one holding a label takes the new one in its place. FAT32
behind an MBR — the label goes in the root's second cluster when the first
is full; the boot sector and its backup follow, the MBR is untouched, and
only those three sectors are written. No FAT volume: OSError (from
`read_label`).

## CAT's card line

### `card_line(label, total, free)`

The line CAT and `tpi:dir` show over the listing, at most 32 characters:
`SD: 240 MB; free: 236 MB`, with the label in place of `SD` when the card
has one. A long label tries `L: 240 MB, 236 MB free`, then `L 240 MB, 236
MB free`, then `L: 236 MB free`, and the last cut to 32. The sizes come
from `space_pair`. Used by `LIST_DIR_FILES`. Pinned: no label; a label in
place of `SD`; two 11-character labels with large sizes still fit 32
columns.
