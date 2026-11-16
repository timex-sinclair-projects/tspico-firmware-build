# Proposal: the folder listing as an index, rendered on the way out (#384)

Status: proposal, 2026-11-06. Nothing here is built yet.

## The problem, in one sentence

The heap does not fragment because listings are big. It fragments because
the listing's **kept** objects (one `str` per name in `files[]`, the 32-byte
rows, `lista`) are allocated in the same pass as its **garbage** (the
`ilistdir` tuples, lowered names, formatting), so they end up interleaved.
After the garbage is collected, the kept objects are spread across the
whole heap. Then the next big allocation, such as CAT's 12K colored copy,
the 64K DCK or a 35K LOAD, finds no single block large enough.

Every fix so far (#386–#394) has made the garbage smaller or collected it
sooner. This proposal removes the kept objects from the GC heap instead.

## What a listing really needs to keep

| kept today | why | size, 300 files |
|---|---|---|
| `files[]`, one `str` per name | `LOAD "tpi:n"`, the ZX48 mount, index numbers, `LOAD_TPI` by name | ~12K (40 B a name, measured: 5.3K for 132 names) |
| `dirs[]` | `MOVE TO` checks, `tpi:cd` | small |
| `lista`, the rendered text | CAT, `tpi:dir`, `CDIR`, the ZX reply | 9.7K in one block |
| `CAT_COLOUR`'s copy, per CAT | color | 12.1K in one block, transient |
| `listing_sig` | the freshness check | one int |

Only the names, their kinds and their sizes are information. Everything
else is a rendering of them.

## The design

### 1. A fixed arena, allocated once at boot

`catalog.Index`: one `bytearray` holding the names packed as UTF-8, plus an
`array('H')` of offsets into it, an `array('L')` of sizes and a `bytearray`
of kinds (folder, numbered file, other file). All four are allocated at
import, like v3's `BLOCK_BUF`, and never reallocated.

- Proposed capacity: 512 entries and 8K of names, about 11K in total.
  `/help`, with 132 names, packs into 1,109 bytes of names, so 8K holds
  about 900 names of that length. Today a 300-file folder keeps about 22K,
  scattered.
- **Nothing the listing keeps is allocated during the listing.** Its
  garbage is then just garbage: one collect afterwards and the heap is
  whole again. This is the real fix for the sieve, on both boards.
- On overflow, the first 512 entries are listed, and the CAT footer says
  "and N more: use CAT \"*.tap\" or a subfolder". No MemoryError path is
  left in the listing.

### 2. Sorted by the C sort, not by Python

Make one key string per entry, `kind + name.lower() + "\0" + name + "\0" +
size`, into a list allocated once at the counted length, and call
`list.sort()` with no `key=`. The comparisons run in C, with no Python call
per comparison. Then copy each key into the arena and drop it.

Measured on the v3 card, `/help` (132 files): the sort took **9 ms**, and
the index kept **2.2K, against 5.3K** for today's `files[]`. The pack loop
(118 ms in total) is the slow part and is the first thing to optimize (one
`split`, a `memoryview` copy).

Count first, then allocate: growing the key list by `append` failed for a
**2K** block in a broken-up REPL heap, and one 4.8K `bytearray` failed in
the same heap where many small objects still fit. So the arena must be
allocated at boot, not per listing.

### 3. Freshness without sorting

`LISTING_FRESHEN` runs on every CAT. Today it sorts the whole folder and
builds a tuple per entry, only to hash it. An order-free signature is the
sum of `hash((name, type, size))` over the entries as `ilistdir` yields
them: no list, no sort, nothing kept. Measured: 28 ms for the 132 card
entries, and that is all `ilistdir` time.

### 4. Render on the way out, a page at a time

`SEND_MSG2` already sends one page (21 lines), then waits for the Scroll?
key. So it doesn't need the whole message as a string; it needs rows. The
proposal: `SEND_MSG2` takes a row source (a generator over the index) and
fills one preallocated page buffer (about 1K, reused), with the colors
added as each row is written.

- The `lista` text goes, and so does the 12K colored copy.
- Large folders get their color back.
- The progress percentage becomes row / total.

The text callers (help, messages) keep passing a `str`, wrapped in a
one-row source.

The same renderer serves:

- **CAT / `tpi:dir` / `CDIR`**: rows from the index.
- **`CAT "*.tap"` / `CAT "folder"`** (`CATALOG_TEXT`): rows from a filter
  over a temporary index of that folder. The `index_of` cursor becomes a
  direct position.
- **The ZX48 `tpi:dir` reply**: the v4 ROM reads it in pieces as it goes.
  On v3, render it into `BLOCK_BUF`, which is idle during `tpi:dir`, so it
  needs no allocation. On v2 (no `BLOCK_BUF`), a transient buffer is safe
  once nothing kept is interleaved.
- **`dirinfo.tap`** (`DIRINFO_WRITE`): written from the index, with no
  second read of the folder.

### 5. Lookups without a `str` per name

- `LOAD "tpi:n"`: slice entry `n` out of the arena and decode it. That
  makes one short-lived `str`, for one command.
- `LOAD "tpi:name"`: a case-insensitive scan of the arena's bytes.
  `LOAD_TPI` already compares as it walks the entries.

### 6. Small ones on the way

- `LIST_DIR_FILES` calls `os.statvfs("")` three times; call it once.
- `ob = bytearray()` in `SEND_MSG2` grows by `append` for every byte.
  Preallocate the page buffer (point 4).
- `LIST_GC_EVERY`'s collect every 32 rows can go once nothing kept is
  allocated during the listing.

## v2 and v3

The same code runs on both boards. v2's SD card and bus share GPIO 2–4, so
v2 cannot read the card while sending to the 2068. The index is why that
doesn't matter: everything CAT sends is already in RAM. v3 could stream
straight from the card, but it gains nothing over the index and would need
a second code path.

## Order of work, one PR each, measured with memcheck

1. The arena and the C-sorted build, with `files[]` replaced by the index
   accessors (the largest change: about 30 lines in tspico.py use `files`).
2. The order-free freshness signature (small; it can go first).
3. `SEND_MSG2` taking rows; CAT and `CDIR` rendered from the index; `lista`
   gone, color back.
4. `CATALOG_TEXT` and the ZX reply on the same renderer; `dirinfo.tap` from
   the index.

## Not known yet

- Whether the 2068 is happy with pages built as they are sent. The page
  boundary is already where `CMD_SEND` hands over, so it should be, but it
  needs a hardware check.
- The arena capacity: the real largest folders on users' cards. The 1,328
  tapes on the archive card are spread over folders; the largest folder
  there should set the size.
- The pack loop's speed on v2 (RP2040, 125 MHz), which is slower than the
  v3 card.
- The 300-file numbers. The card in the v3 slot today has no MEMDIR folder,
  so these numbers come from `/help` (132 files). A synthetic 300-entry run
  in the REPL failed for lack of a free block, which shows the problem but
  is not a fair comparison.
