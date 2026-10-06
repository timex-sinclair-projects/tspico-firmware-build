# native.py — +3DOS headers for `f:` files

Source: [`src/TS/native.py`](../../../src/TS/native.py) (146 lines).

A native file is one program, screen, code block or array stored on its
own on the SD card, not inside a TAP, written by `SAVE "f:name"` and read
by `LOAD`, `VERIFY` and `MERGE "f:name"`. Everything except a screen
carries the 128-byte +3DOS header — the Spectrum +3 / esxDOS / NextZXOS
convention, chosen because every other tool on a card already reads and
writes it — whose fields are the tape header's; a screen is the raw 6912
bytes every emulator reads (spec [§4a, "File format"](../../DISK_COMMANDS_SPEC.md)).
This module is pure: it lays bytes out and reads them back, with no SD,
PIO or TS-Pico globals, so it is tested on the host
([`src/test/native_hosttest.py`](../../../src/test/native_hosttest.py)).
`NATIVE_LOAD_PREP` in [tspico-disk.md](tspico-disk.md) uses it to turn a
file into the one-shot tape that `LOAD_TS` serves, and `SAVE_TS` in
[tspico_io.md](tspico_io.md) uses `to_file` to turn the SAVE it received
into the file. The user's view is [user-manual.md chapter 5](../../manual/user-manual.md).

## Map of the file

| Lines | What |
|---|---|
| 11–16 | `SIG`, `HDR_LEN`, `SCREEN_LEN`, `SCREEN_ADDR`, the four types |
| 19–26 | `_u16`, `_put16` |
| 28–65 | `plus3_header`, `parse_plus3`, `is_screen` — the +3DOS header |
| 68–95 | `tape_header`, `fields_from_tape_header`, `tap_block` — the tape side |
| 98–146 | `to_file`, `describe`, `headerless_code`, `as_tap`, `tape_name` — file ↔ tape |

## Constants

| Name | Value | Meaning |
|---|---|---|
| `SIG` | `b"PLUS3DOS\x1a"` | the header's first nine bytes: the signature and a soft end-of-file |
| `HDR_LEN` | 128 | the header's length; the data starts there |
| `SCREEN_LEN` | 6912 | a SCREEN$ block: 6144 bytes of pixels and 768 of attributes |
| `SCREEN_ADDR` | 16384 | where a screen loads |
| `T_PROGRAM` | 0 | the tape header's type byte for a BASIC program |
| `T_NUMARR` | 1 | a numeric array |
| `T_CHARARR` | 2 | a character array |
| `T_CODE` | 3 | bytes (CODE, and a screen) |

## Helpers

### `_u16(b, i)`

The little-endian 16-bit value at `b[i]`.

### `_put16(b, i, v)`

Stores `v` little-endian at `b[i]`, `b[i + 1]`.

## The +3DOS header

### `plus3_header(typ, length, param1, param2)`

The 128-byte header for a data block of `length` bytes, as a `bytearray`:

| Bytes | Value |
|---|---|
| 0–8 | `SIG` |
| 9 | issue 1 |
| 10 | version 0 |
| 11–14 | the total file length, header included (`128 + length`), little-endian |
| 15 | `typ`, the tape header's type byte |
| 16–17 | `length` |
| 18–19 | `param1` |
| 20–21 | `param2` |
| 22–126 | zero: the spare byte of the +3 BASIC header and the reserved bytes |
| 127 | the checksum: the sum of bytes 0–126, low byte |

Bytes 15–22 are the "+3 BASIC header", the tape header's fields in +3DOS
order. The spec notes that the issue and version bytes "can mark a file as
2068"; the code writes 1 and 0, so a 2068 `.bas` is not marked, although
it may hold tokens (`ON ERR`, `STICK` …) no Spectrum has. Pinned by the
host test: signature and soft EOF; issue and version; the length includes
the header; type, length, param1 (LINE), param2 (the variables offset);
spare and reserved zero; the checksum.

### `parse_plus3(b)`

`(type, length, param1, param2)` from a header, or `None` when `b` is
shorter than 128 bytes, does not start with `SIG`, or its checksum is
wrong. Pinned: a round trip; a bad checksum, no signature and a short
header are all `None`.

### `is_screen(typ, length, param1)`

A SCREEN$ block: CODE, 6912 bytes, at 16384. Such a block is stored raw,
with no header. 6912 bytes saved from anywhere else are an ordinary +3DOS
file (pinned).

## The tape side

### `tape_header(typ, name, length, param1, param2)`

The 17-byte tape header, without the flag and checksum: the type, the name
in 10 bytes (a `str` is UTF-8 encoded; padded with spaces and cut to 10),
then `length`, `param1`, `param2` little-endian. The two parameters mean
what the 2068's SAVE put there — for a program the autostart LINE and the
start of the variables, for CODE the address and 32768 — and this module
only carries them. Pinned: the name is space-padded.

### `fields_from_tape_header(h)`

`(type, length, param1, param2)` from a 17-byte tape header: bytes 0,
11–12, 13–14, 15–16. No firmware caller; the tests use it to read the
one-shot tape back.

### `tap_block(flag, payload)`

One TAP block: the two-byte length (`len(payload) + 2`, little-endian),
the flag, the payload, and the XOR of the flag and every payload byte.
`NATIVE_LOAD_PREP` uses it for the header block only; it streams the data
block itself so the file never has to fit in RAM.

## File ↔ tape

### `to_file(typ, length, param1, param2, data)`

`(bytes to write, kind)` for a SAVE: a screen (`is_screen`) is `data` as
it is, kind `"screen"`; anything else is `plus3_header(...)` followed by
`data`, kind `"plus3"`. Called once by `SAVE_TS` with the fields of the
header block the 2068 sent and the data block's payload. Pinned: CODE is
header + data; `CODE 16384,6912` is raw; 6912 bytes elsewhere keep the
header.

### `describe(raw_head, size)`

What a native file holds, from its first 128 bytes and its size:
`(type, length, param1, param2, data_offset)`. A valid +3DOS header gives
its fields with offset 128, unless `128 + length` exceeds the file, which
is `None` (a truncated file). Without a header, a file of exactly 6912
bytes is a screen: `(T_CODE, 6912, 16384, 32768, 0)`. Anything else is
`None`, and the caller decides: `NATIVE_LOAD_PREP` takes it whole for
`LOAD ... CODE` and refuses it otherwise. Pinned: an array; a truncated
file `None`; raw 6912 a screen; raw 5000 `None`.

### `headerless_code(size, addr=32768)`

The fields for a headerless file loaded as CODE: `(T_CODE, size, addr,
32768, 0)`, the whole file at `addr`. `NATIVE_LOAD_PREP` leaves `addr` at
its default: the Pico cannot see whether the statement gave an address,
and when it did the ROM loads there whatever the header says (spec §4a).

### `as_tap(typ, length, param1, param2, data, name)`

The two TAP blocks — `tap_block(0x00, tape_header(...))` then
`tap_block(0xFF, data)` — that stand for a native file on a one-shot
tape, so the stock LOAD / VERIFY / MERGE code can read it. No firmware
caller: `NATIVE_LOAD_PREP` builds the same bytes by streaming, and
`disk_cmds_hosttest.py` checks that its tape equals `as_tap(...)`. Pinned
here: the header block is 19 bytes with flag 00 and the name as given, the
data block flag FF with the checksum.

### `tape_name(path)`

The 10-character tape name shown for a native file: the base name, the
extension dropped (a dot at the start is kept), cut to 10. The name in the
one-shot tape's header, which the 2068 prints as `Program: advent` while
it loads; the ROM asks for `""`, so it never has to match. Pinned:
`/sd/TAP/games/advent.bas` → `advent`; a long name cut to 10.
