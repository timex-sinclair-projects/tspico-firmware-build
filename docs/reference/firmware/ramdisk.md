# ramdisk.py — the TS-2068 Megabank's RAM disk: the file system behind `r:`

Source: [`src/TS/ramdisk.py`](../../../src/TS/ramdisk.py) (530 lines). The v3
card only: frozen by [`src/boards/TSPICO_V3/manifest.py`](../../../src/boards/TSPICO_V3/manifest.py),
imported by `tspico.py`'s `RD_START` when an `r:` command first runs
([tspico-disk.md](tspico-disk.md#the-megabanks-ram-disk-r-names)).

The Megabank board (the TS-2068-Megabank repository's `docs/spec.md`, "The
RAM disk") is up to 4 MB of battery-backed RAM that answers only the Z80's
bus cycles: the TS-Pico can't reach it. So the RAM disk is split. This
module owns the file system (the superblock, the directory, allocation,
compaction, names, the listing) and decides what to copy where; the ROM's
mover, response function 89h ([PROTOCOL.md §6.3](../../PROTOCOL.md)), does
each copy, one operation at a time. The directory and the data are on the
board, so they survive power-off with its battery; this module keeps a cache
of the directory and nothing else. Nothing here touches the bus: the mover is
handed in as `Disk.mv` (`RD_MOVER` on the card, a model board in
[`src/test/ramdisk_hosttest.py`](../../../src/test/ramdisk_hosttest.py)), so
every rule is tested on the host. On a real board,
[`basic/SD/TAP/test/mbdisk.bas`](../../../basic/SD/TAP/test/mbdisk.bas) runs
each command and records its report, for `tools/hwcheck.py --megabank`.

**The layout.** Pages are the board's 8K pages counted from BASE, 0 to
SIZE × 8 − 1. The RAM disk is pages `first`..`last`, where `last` is always
the board's last page, so the banks below stay free for programs (and for
ZXDesk's first bank, which the spec reserves). Page `last` holds the
metadata: the superblock at 0000h, `STAGE` at 0100h, the directory at
0400h–1FFFh. Pages `first`..`last − 1` hold the data, in 1K clusters
counted from 0 at `first`. A 64K RAM disk is 8 pages: 56 clusters of data.

**The superblock** (`SB_LEN` bytes at page `last`, 0000h):

| Bytes | Field |
|---|---|
| 0–3 | `MAGIC`, "TSRD" |
| 4 | `VERSION`, 1 |
| 5 | log₂ of the cluster size: 10 |
| 6–7 | `first` page |
| 8–9 | `last` page: must be the board's last page, or the RAM disk is not this board's |
| 10–13 | the generation: one more for every directory change |
| 14–15 | the high-water: directory slots 0 to high − 1 are read |
| 16–29 | 0 |
| 30–31 | the 16-bit sum of bytes 0–29 |

**A directory entry** (`ENTRY` bytes; slot *s* at page `last`, 0400h + 32*s*):

| Bytes | Field |
|---|---|
| 0 | `USED`, 46h ('F'): a file; anything else is a free slot |
| 1–17 | the file's 17-byte tape header: type, name (10, space-padded), length, parameter 1, parameter 2 |
| 18–19 | its first cluster |
| 20–21 | its length: the data block's |
| 22 | the data block's flag byte (FFh from SAVE) |
| 23–26 | the generation it was written at |
| 27–30 | 0 |
| 31 | the XOR of bytes 0–30, XOR A5h |

**Why it survives a power cut.** An entry is written in one op 5, and the
mover writes in order, so its check byte is the last byte to land: an entry
cut short fails its check, and that file is lost, no other. A file's data
goes to the board before its entry; a replaced file's old entry is cleared
only after the new entry is in and the superblock (whose high-water may have
had to grow to reach the new slot) says so. A cut between those two leaves
two entries of one name, and `Disk.mount` keeps the newer by its generation.
There is no allocation bitmap, though the spec drew one: which clusters are
used follows from the entries, so there is nothing to disagree with them.
Compaction is the exception: a file moved down over itself is lost if the
power fails mid-move (`Disk.compact`).

**Caching.** Every command reads the superblock (op 7, then op 4 of
`SB_LEN` bytes: ~3 ms of transfer) and reads the directory again only if the
generation changed, high-water × 32 bytes. That covers a reset, a power
cycle and a second TS-Pico. The generation in the superblock is written
after every change; the generations in the entries only break ties.

## Map of the file

| Lines | What |
|---|---|
| 1–56 | the layout, in a comment |
| 58–73 | `MAGIC` … `TYPES`: the layout's constants, the status codes, the type names |
| 76–85 | `RdError` |
| 88–127 | `w16`, `r16`, `r32`, `w32`, `sum16`, `tape_name`, `check_name`, `clusters` |
| 130–176 | `Entry` |
| 179–183 | `renamed` |
| 186–514 | `Disk`: the board and the superblock (218–286), geometry and allocation (288–347), directory writes (350–371), the operations (374–486), text (488–514) |
| 517–530 | `parse_size` |

## Constants

| Name | Value | Meaning |
|---|---|---|
| `MAGIC` | `b"TSRD"` | the superblock's first four bytes |
| `VERSION` | 1 | the format version in byte 4; another version is not mounted |
| `SB_LEN` | 32 | the superblock's length, and the bytes every command reads |
| `STAGE` | 0100h | where a SAVE's header block goes on page `last` so the firmware can read it: the mover has no 2068 → Pico operation, so the header is copied to the board (op 1) and read back (op 4) |
| `DIR_OFF` | 0400h | the directory's offset in page `last` (0020h–03FFh are free; the spec's `tpi:ram alloc` records could go there) |
| `ENTRY` | 32 | a directory entry's length |
| `SLOTS` | 224 | (2000h − `DIR_OFF`) / `ENTRY`: the most files a RAM disk holds |
| `PAGE` | 8192 | a board page |
| `CLUSTER` | 1024 | the allocation unit (the spec's 1K) |
| `PER_PAGE` | 8 | clusters in a page |
| `USED` | 46h | an entry's byte 0 when it is a file |
| `OK`, `R_TAPE`, `F_NAME`, `Q_PARAM`, `J_IO` | 1, 2, 3, 4, 10 | the firmware's status codes ([PROTOCOL.md §5.3](../../PROTOCOL.md)) this module raises: OK, R Tape loading error, F Invalid file name, Q Parameter error, J Invalid I/O device. No board, no RAM disk and the write-protect switch are J; a full disk or directory is Q |
| `TYPES` | `("Program", "Num array", "Chr array", "Bytes")` | the header's type byte 0–3, as the listing shows it |

## Errors

### `RdError`

The one exception: `args` = (status, message). Every refusal in this module
and every refused mover operation (`RD_MOVER._st`) raises it; `RD_RUN`
turns it into the command's answer.

### `RdError.status`

`args[0]`, the status the command answers with.

### `RdError.msg`

`args[1]`, the text shown with it (always for an error; `RD_RUN` forces it).

## Helpers

### `w16(v)`

Two bytes, little-endian.

### `r16(b, i)`

The little-endian word at `b[i]`.

### `r32(b, i)`

The little-endian 32-bit value at `b[i]`.

### `w32(v)`

Four bytes, little-endian.

### `sum16(b, n)`

The sum of `b[0:n]`, modulo 65536: the superblock's check.

### `tape_name(name)`

`name` as a tape header holds it: its first 10 bytes, padded with spaces.

### `check_name(name)`

Raises `RdError(F_NAME)` unless `name` is 1–10 printable ASCII characters
(the tape rules, so a file moves between tape, the card and the RAM disk
unchanged); returns it.

### `clusters(length)`

The clusters `length` bytes take, rounded up; 0 for 0.

## `Entry`

### `Entry`

One file: its slot, its tape header (17 bytes), first cluster, length, flag
byte and generation. `__slots__`, so an entry is small: 224 of them is the
most a cache holds.

### `Entry.__init__(self, slot, hdr, first, length, flag, gen)`

Stores the fields; `hdr` as `bytes`.

### `Entry.name`

The header's name field, decoded, trailing spaces stripped.

### `Entry.kind`

The header's type byte (0 program, 1 number array, 2 character array, 3 bytes).

### `Entry.size`

Its clusters (`clusters(length)`).

### `Entry.pack(self)`

The 32-byte entry, check byte last.

### `Entry.parse(b, slot)`

An `Entry` from 32 bytes, or `None` for a free slot or one that fails its
check (a write cut short).

### `renamed(hdr, name)`

A header with its name field replaced by `tape_name(name)`. Every entry's
header carries the entry's own name, so `LOAD "r:x"` after `MOVE` or `COPY`
loads a header whose name is x.

## `Disk`

### `Disk`

The RAM disk on one board. `tspico.py` keeps one in `RD` for the firmware's
lifetime and sets `mv` to a fresh `RD_MOVER` for every command. The mover's
calls (all raise `RdError` on a refusal):

| Call | Op | Does |
|---|---|---|
| `mv.info()` | 7 | (found, BASE, SIZE, STATUS, VERSION) |
| `mv.read(n, page, off)` | 4 | n bytes from the board |
| `mv.write(data, page, off)` | 5 | bytes to the board |
| `mv.move(n, page, off, page2, off2)` | 6 | board to board; the runs must not overlap |
| `mv.copy_in(addr, n, page, off)` | 1 | 2068 memory to the board |
| `mv.copy_out(addr, n, page, off)` | 2 | the board to 2068 memory |
| `mv.compare(addr, n, page, off)` | 3 | `True` if they are the same |

### `Disk.__init__(self)`

Nothing known: no board, not formatted, `entries` `None` (not read).
Fields: `mv`; `found`, `pages`, `base`, `wp` (the write-protect switch,
STATUS bit 0), `low` (battery low, bit 1), `version` from op 7; `formatted`,
`first`, `last`, `gen`, `high` from the superblock; `entries` (slot →
`Entry`) and `cache_gen`, the generation they were read at; `confirm`, the
FORMAT or ERASE waiting to be repeated (`RD_CONFIRMED`). Memory: the
entries, at most 224 small objects, made when the directory is read and
replaced when it changes.

### `Disk.probe(self)`

Op 7. Raises `RdError(J_IO, "No Megabank board")` if the mover found none
(ID/IDCOMP not A5h/5Ah); otherwise sets `base`, `pages` (SIZE × 8),
`version`, `wp`, `low`.

### `Disk.mount(self, need=True)`

`probe`, then the superblock (op 4). It is good if the magic, version,
cluster size and sum hold, `last` is this board's last page, `first` is
below it and the high-water is at most `SLOTS`. Not good: `formatted` is
false, the cache is dropped, and with `need` it raises `RdError(J_IO, 'No
RAM disk: FORMAT "r:" makes one')`. Good: `first`, `last`, `gen`, `high`;
if the cache was read at this generation it stands, otherwise the directory's
first `high` slots are read in one op 4 and parsed. Of two entries with one
name the newer generation wins (the leftover of a replace cut short).

### `Disk.superblock(self)`

The `SB_LEN` bytes for the current fields, sum last.

### `Disk.commit(self)`

A directory change is complete: the generation goes up by one and the
superblock is written (op 5). The cache is now at that generation.

### `Disk.writable(self)`

Raises `RdError(J_IO, "The board is write-protected")` when the switch is
on. The board drops the writes anyway; refusing first keeps the directory
and the cache in step and gives the reason. Every writing operation calls
it before its first write.

### `Disk.nclusters`

Data clusters: (`last` − `first`) × 8.

### `Disk.loc(self, c)`

Cluster `c` as (page, offset).

### `Disk.files(self)`

The entries sorted by name: the listing's order.

### `Disk.find(self, name)`

The entry of that name, or `None`. Names compare exactly, as a tape's do.

### `Disk.get(self, name)`

`find`, or `RdError(F_NAME, "Not found: r:name")`.

### `Disk.used(self)`

Clusters in use.

### `Disk.free(self)`

Clusters free (K, since a cluster is 1K).

### `Disk.alloc(self, length)`

The first cluster of the first free run that holds `length` bytes, or
`None`. A file of 8K or more starts on a page boundary, so a program can map
its pages straight into a chunk (the spec's `LOAD "r:icons"`, then page the
icons in by number).

### `Disk.free_slot(self)`

The lowest free directory slot, or `RdError(Q_PARAM)`: the directory is
full. Writers call it before copying any data, so a full directory costs no
copy.

### `Disk.place(self, length)`

`alloc`; if that fails and enough clusters are free, `compact` and `alloc`
again; then `RdError(Q_PARAM, "The RAM disk is full")`. An empty file takes
cluster 0 and no space.

### `Disk.write_entry(self, e)`

Writes `e` to its slot (op 5, 32 bytes), puts it in the cache, and raises
`high` if the slot is at or above it. The superblock is not written: the
caller commits.

### `Disk.clear_entry(self, e)`

Writes 0 to the slot's byte 0 (op 5, 1 byte) and drops it from the cache.

### `Disk.add(self, name, hdr, length, flag, c)`

The data is at cluster `c`: enter it as `name` (its header renamed), commit;
then, if a file of that name was there, clear its entry and commit again.
Two commits, so that the new entry is reachable (high-water) before the
old one goes. Returns the new entry.

### `Disk.format(self, npages)`

A new, empty RAM disk of `npages` pages at the top of the board: `first` =
`pages` − `npages`, high-water 0, one commit. The old directory's bytes stay
on the board but are never read (a slot below the high-water is always one
written since). The generation carries on from the old RAM disk's, if there
was one, so another TS-Pico's cache can't match it by chance. Refused when
write-protected, or for fewer than 2 pages or more than the board.

### `Disk.save_header(self, addr)`

A SAVE's header block: 17 bytes from 2068 memory at `addr` to `STAGE` (op
1) and back to the Pico (op 4). Returns the header.

### `Disk.save_data(self, name, hdr, addr, length, flag)`

A SAVE's data block: a slot first, then `place`, the data from `addr` (op
1, one operation however many pages it crosses), then `add`.

### `Disk.header_loc(self, e)`

Where `e`'s tape header is on the board: inside its entry (page `last`,
`DIR_OFF` + 32 × slot + 1). LOAD copies it from there to the 2068 (op 2),
so no header is stored twice.

### `Disk.put(self, name, hdr, data, flag=0xFF)`

A whole file from the TS-Pico (COPY from the card, op 5).

### `Disk.fetch(self, e)`

A file's data to the TS-Pico (COPY to the card, op 4).

### `Disk.erase(self, e)`

Clears `e`'s entry and commits. Its clusters are free from then on.

### `Disk.rename(self, e, name)`

A new entry with the new name in a free slot, commit, then the old entry
cleared and commit: the same order as `add`, so a cut leaves one name or
the other. Refused if another file has the name.

### `Disk.duplicate(self, e, name)`

COPY on the board: a new run, op 6 from the old one, `add`.

### `Disk.compact(self)`

Slides every file down, in cluster order, to close the gaps, keeping big
files on page boundaries. Each file moves in pieces no longer than the
distance it moves (op 6 doesn't handle overlapping runs), and its entry is
rewritten when its data is in place; one commit at the end. A file moving
over its own old place is lost if the power fails mid-move; the others are
not. `place` calls it when free space is there but in pieces.

### `Disk.listing(self)`

CAT `"r:"`'s text: "RAM disk *n*K, *f* files, *k*K free", then a row a file,
by name: the name (10), the type (9) and the length (6), within 32 columns.
Lines end in CR.

### `Disk.report(self)`

`SAVE "tpi:ram"`'s text: the board (size, banks, version, battery,
write-protect) and the RAM disk (size, pages, files, free) or that there is
none.

### `parse_size(arg, pages)`

FORMAT `"r:size"`'s size, in pages: a number of K (a trailing K allowed), a
multiple of 8; empty, half the board (`pages` // 2, at least 2). Otherwise
`RdError(Q_PARAM)`.
