# Memory: keeping the heap whole

The firmware is Python on a small heap, and most of what it does for the
2068 needs one big piece of it at a time: a 64K DOCK image, a 35K LOAD or
SAVE block, a 300-file folder's listing. The total free memory is rarely the
problem. The problem is where the free memory is: a heap with 76K free in
two pieces of 38K can't give one buffer of 40K. This appendix is the set of
rules that came out of issue #384 (PRs #386–#398), with the bug or the
measurement behind each, and how to measure a change of your own.

Read it before you add a module variable, a cache, a buffer, or anything
that keeps something between two commands.

## The two heaps

| | v2 (RP2040) | v3 card (RP2350B) |
|---|---|---|
| GC heap | 234K in all, about 182K free with the firmware running, and a 168K largest block after three rounds of the 300-file folder and a 64K DOCK (`memcheck --dck`, 2026-11-07) | 172K in all, about 76K free with the firmware running; the top 256K of SRAM is `tsbus`'s images ([board-v3.md](../firmware/board-v3.md#memmapsection_extra_post_platform_endincl)) |
| LOAD/SAVE block | a new `bytearray` per block | `BLOCK_BUF`, 48K, made at import ([board.md](../firmware/board.md)) |
| a 64K DOCK stream | `BLKRCV` in 32K pieces (#376) | `BLOCK_BUF` |

v3 is the tight one. Measure there first, then on v2.

## How the heap behaves

These are the facts the rules rest on. They are MicroPython's GC as the heap
maps in #384 showed it.

- **The heap is 16-byte blocks, and nothing ever moves.** An object stays at
  the address it was given until it is freed. There is no compaction, so a
  collection can free memory but can't join two free pieces that have a
  live object between them.
- **Garbage is not reused until a collection.** The GC collects when an
  allocation finds no room, or when the code calls `gc.collect()`. Until
  then, new objects go into the free space after the last thing allocated.
  *(inferred from the heap maps: MicroPython keeps a "first free" position
  that a collection moves back to the bottom of the heap.)*
- **So a kept object made right after garbage ends up in the middle of the
  free memory.** The garbage before it is collected; the object stays where
  it is, and the free space is cut in two around it. This is the whole
  mechanism of #384's fragmentation: not big objects, but small kept ones
  interleaved with garbage. The heap map after a 300-file `MOVE TO` on the
  v3 card (2026-11-07) showed a 200-block cluster of them (the listing's
  signature tuple, its header string, the `DirText`, and the SD card
  driver with its buffers) splitting 66K of free memory into 35K and 29K.
- **Total free memory says little. The largest free block is the number
  that matters.** `gc.mem_free()` counts every free block wherever it is.
  [`LARGEST_BLOCK`](../firmware/tspico-commands.md) finds the biggest
  `bytearray` that can be had now, by trying sizes.
- **A small int is not an object.** An int up to 2^30 − 1 is stored in the
  reference itself and costs nothing on the heap. A bigger one, and every
  float, is an object. *(inferred: the RP2 ports' object representation.)*
  That is why `LISTING_SIG` masks its sum with `& 0x3FFFFFFF`.
- **Any allocation can start a collection.** When it finds no room, it
  collects first, so a line that allocates can take milliseconds. A
  collection took 4.3 ms on the v3 card with the firmware's heap.
- **Frozen code lives in flash, not the heap.** Everything under
  `src/TS/` is frozen into the UF2. A `/dev_tspico.py` or `.mpy` override
  ([boot.md](../firmware/boot.md)) is loaded at boot into the heap and
  changes its whole layout *(inferred: MicroPython keeps imported bytecode
  in RAM)*, so never measure memory with an override in place.

## The rules

### 1. A buffer that is needed again is made once, at import

Make it while the heap is clean, before anything has been through it, and
keep it for the life of the firmware. Examples:
[`BLOCK_BUF`](../firmware/board.md#block_buf) on v3 (48K) and
[`INDEX`](../firmware/tspico-state.md#index) (`catalog.Index`, about 11K).

Why: once the firmware has run a few commands, a big block may not exist at
all. On v3, `tpi:dock` failed with `MemoryError` building a 64K image
(2026-10-10). A 35000-byte LOAD failed for want of one after a 300-file
folder had been listed (2026-11-06): LOAD streamed from the file instead,
ran dry, and gave Report R; SAVE gave Report 6.

Size it from what it must hold, and say in its entry what happens when that
isn't enough (the index lists what fits and says "and n more").

### 2. What a command keeps is made after a collection

If a command does a lot of work and then keeps a little, make the little
after a `gc.collect()`, not as you go. Hold the results in locals that
aren't objects (small ints) until then, or in objects you will drop.

Why: rule 3 of "How the heap behaves". [`LIST_DIR_FILES`](../firmware/tspico-files.md#list_dir_files)
reads the folder twice and fills the index, then collects, then makes the
signature tuple, the free-space tuple, the header and the `DirText`. Made
as they came, those few hundred bytes split the heap; made after the
collection, they went into the small holes low in the heap, and the largest
block after a 300-file listing went from 28.7K to 66.5K (#398).

### 3. Nothing is kept between commands that isn't needed then

A module variable, a `TSP` field, a class attribute or a local of the
service loop's frame lives as long as it points at something. Anything it
points at stays where it was made. When a command is done with an object, set
the variable to `None` (or `""`) so the next collection frees it.

Why: `SD_DEV`, the SD card driver, was made new by every mount and the last
one was kept between commands, with its buffers, wherever that mount had put
it. Its only readers run while the card is mounted. `DEACTIVATE_SD` now
drops it (#398).

When you add a global, its entry in the reference must say how big it gets,
when it is made and when it is dropped (the Conventions, in the
[README](../README.md#conventions)).

### 4. Many small kept things go into one packed buffer

A list of 300 `str`s is 300 objects spread over the heap, each about 40
bytes for a short name. The same names packed into one `bytearray`, with an
`array('H')` of offsets and an `array('L')` of sizes, are three objects,
made once (rule 1). The callers see a sequence that decodes one name when
asked: [`catalog.View`](../firmware/catalog.md#view). The old `files[]` kept 5.3K
for 132 names; the index keeps 2.2K for the same folder (#396).

Make the arrays from a list or a `bytearray` (`array("H", [0] * n)`):
MicroPython's `array` has no `*`.

### 5. Count first, then allocate once at the full length

Growing an object (`append` to a list, `+=` on `bytes` or `str`,
`bytes(generator)`) reallocates it as it grows, and each step leaves the
old copy behind as garbage. Find the length first, then make the object
once: `keys = [None] * count` in `Index.fill`, `bytearray(n)` then a
slice assignment in [`ZX_PIECES`](../firmware/tspico-dispatch.md#zx_piecestext).

Why: `NEW_TAPBLK` built `dirinfo.tap`'s block by concatenation, about 9.7K
for 300 files, and was where a big folder ran out of memory on v2. The ZX48
`tpi:dir` reply was built by `bytes(generator)`, a byte at a time. Growing
the sort keys by `append` failed for a 2K block in a broken-up heap
(a REPL test, 2026-11-06, #384).

### 6. Don't build big text you can make as it is read

If the consumer reads a message one character or one row at a time, give it
an object that makes the characters as they are read, instead of the whole
string. `SEND_MSG2` reads a message only through `len(msg)`, `msg[i]` and
`msg.count(...)`, so [`DirText` and `DirColour`](../firmware/tspico-messages.md)
stand in for the listing and its colored copy: each row is made when it is
sent, with a one-row cache. Before #397, a 300-file CAT kept a 9.7K `str`
and needed a second, 12.1K block for the color, which the v3 heap often
couldn't give (CAT fell back to plain text).

The same holds for a channel's answer. `channels.Channels` reads an `x:`
answer through `len()` and `chunk(pos, n)` only, so `dir` answers with
[`XDirText`](../firmware/tspico-files.md#xdirtext), which builds just the
rows a `tpi:chrd` asks for (at most 255 bytes), not the ~10K a 300-file
listing would be in one piece (#404). The answer is kept in the channel
until the next command printed to it, `CLOSE #`, or the stream's next
`OPEN #` (rule 3: a stream BASIC forgot, after NEW or a reset, keeps its
answer until then); an `XDirText` holds only the index it reads from,
which is kept anyway (rule 1).

### 7. Slice with a `memoryview`, not a copy

`text[i:j]` on `bytes`, `bytearray` or `str` makes a new object.
`memoryview(text)[i:j]` doesn't: it is a view of the same memory, and
assigning it into a buffer copies the bytes straight across.
`Index.name` and `ZX_PIECES` work this way.

### 8. Sort plain strings, with no `key=`

`list.sort(key=f)` calls `f` once per item, and makes and keeps the key
objects, so the sort holds two objects per item. Make one string per entry
that sorts the way you want, and sort the list with no `key=`, so the
comparisons run in C. Check whether the list is already in order first,
since `os.ilistdir` often returns it sorted. `Index.fill` does both (#394,
#396).

### 9. No allocation where time matters

A loop with a deadline must not allocate at all: any allocation can start a
collection (milliseconds), and the PIO FIFOs hold four words. The
two-phase rule for bus capture is in [`src/CLAUDE.md`](../../../src/CLAUDE.md)
("The two-phase capture rule"). Collect where the Z80 is waiting for READY
(Y BUSY), as `DIR_FILES`, `ZX_TPI` and the LOAD and SAVE paths do, never
inside a transfer.

### 10. Catch `MemoryError` only where there is a fallback

Catch it around an allocation that can fail and has something sensible to
do instead, and say what in the log: `DIR_FILES` leaves a listing that
says "Too many files to list here" and MOVE TO still works. Don't catch it
broadly: an uncaught one reaches the service loop, which logs it as an
unexpected error and stops the firmware after three in a minute.

## Measuring a change

Measure before and after, on the v3 card first. A change that "should" use
less memory has been wrong before.

- `SAVE "tpi:meminfo tag"` ([`MEMINFO`](../firmware/tspico-commands.md#meminfopre-cmd))
  collects, then prints one `MEM` line to the USB console and
  `/activity.log`: free, allocated, the largest block, and the sizes of what
  the firmware keeps (files, folders, the listing, the mounted tape's
  table). Add the word `map` for `micropython.mem_info(1)`'s heap map.
- [`tools/memcheck.py`](../../../tools/memcheck.py) puts a test program on
  the card, has the 2068 run it (three rounds of the 300-file folder, the
  biggest folder, the root, a mount, a LOAD, a SAVE, a DOCK, a close and
  speech, each followed by a `tpi:meminfo`) and writes a table and the heap
  maps' summaries. `--dck` is the #372 check: a 64K DOCK streamed round
  after round. `--out DIR` keeps the run for a comparison. The number to
  compare is the lowest largest block in each round.
- **Naming what is in a heap map.** The map has one letter per block (`h`
  any object, `=` the rest of one, `T` tuple, `L` list, `D` dict, `S` str or
  bytes, `A` bytearray, `M` module, `B` code, `F` float, `.` free), with
  addresses from the start of the heap. To find which objects split a free
  run, run the real command on the 2068 first, then `tools/pico-serial.py
  break` (the firmware's objects stay in the heap), print `id()` of the
  globals and `TSP` fields in one REPL run, then in a second run
  `gc.collect()` and `micropython.mem_info(1)`. The heap's start address is
  the one that puts each `T` id on a `T` and each `S` id on an `S`
  (0x20015FC0 in the v3 build of 2026-11-07 *(varies with the build)*); an
  object's block is `(id - start) // 16`. Don't re-run the command in the
  REPL to reproduce the heap: the REPL's own objects change the layout.

## A checklist for a change that allocates

- Does it keep anything after the command ends? If so, how big, and is it
  made after a collection (rule 2)? Does its entry say so (rule 3)?
- Does it need one block bigger than a few K? Then it is made at import
  (rule 1), or it can fail with `MemoryError` and fall back (rule 10).
- Does anything grow in a loop (rule 5), get copied by slicing (rule 7) or
  sorted with `key=` (rule 8)?
- Does it run inside a bus transfer (rule 9)?
- What did `memcheck` say before and after?
