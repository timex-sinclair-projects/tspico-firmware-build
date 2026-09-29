# native.py -- native SD files for SAVE / LOAD "f:name" (DISK_COMMANDS_SPEC.md §4a).
#
# A native file is one program, screen, code block or array stored on its own,
# not inside a TAP. Everything except a screen carries the 128-byte +3DOS header
# (the Spectrum +3 / esxDOS / NextZXOS convention), whose fields are the tape
# header's; a screen is the raw 6912 bytes every tool reads.
#
# Pure: no SD, PIO or TS-Pico globals, so it is tested on the host
# (src/test/native_hosttest.py). tspico does the I/O.

SIG = b"PLUS3DOS\x1a"
HDR_LEN = 128
SCREEN_LEN = 6912
SCREEN_ADDR = 16384

T_PROGRAM, T_NUMARR, T_CHARARR, T_CODE = 0, 1, 2, 3


def _u16(b, i):
    return b[i] | (b[i + 1] << 8)


def _put16(b, i, v):
    b[i] = v & 0xFF
    b[i + 1] = (v >> 8) & 0xFF


def plus3_header(typ, length, param1, param2):
    """The 128-byte +3DOS header for a data block of `length` bytes.

    Layout: 'PLUS3DOS' 0x1A, issue 1, version 0, total file length (4 bytes,
    header included), then the +3 BASIC header -- type, length, param1,
    param2 (the tape header's fields) and a spare byte -- zeros, and a
    checksum of bytes 0-126 in byte 127."""

    h = bytearray(HDR_LEN)
    h[0:9] = SIG
    h[9] = 1
    h[10] = 0
    total = HDR_LEN + length
    for i in range(4):
        h[11 + i] = (total >> (8 * i)) & 0xFF
    h[15] = typ
    _put16(h, 16, length)
    _put16(h, 18, param1)
    _put16(h, 20, param2)
    h[127] = sum(h[:127]) & 0xFF
    return h


def parse_plus3(b):
    """(type, length, param1, param2) from a +3DOS header, or None if b does
    not start with a valid one (signature and checksum)."""

    if len(b) < HDR_LEN or bytes(b[0:9]) != SIG:
        return None
    if (sum(b[:127]) & 0xFF) != b[127]:
        return None
    return b[15], _u16(b, 16), _u16(b, 18), _u16(b, 20)


def is_screen(typ, length, param1):
    """A SCREEN$ block: CODE, 6912 bytes at 16384. Stored raw, with no header."""

    return typ == T_CODE and length == SCREEN_LEN and param1 == SCREEN_ADDR


def tape_header(typ, name, length, param1, param2):
    """The 17-byte ZX tape header (without flag and checksum)."""

    h = bytearray(17)
    h[0] = typ
    n = name.encode() if isinstance(name, str) else bytes(name)
    n = (n + b" " * 10)[:10]
    h[1:11] = n
    _put16(h, 11, length)
    _put16(h, 13, param1)
    _put16(h, 15, param2)
    return h


def fields_from_tape_header(h):
    """(type, length, param1, param2) from a 17-byte tape header."""

    return h[0], _u16(h, 11), _u16(h, 13), _u16(h, 15)


def tap_block(flag, payload):
    """One TAP block: 2-byte length, flag, payload, XOR checksum."""

    x = flag
    for b in payload:
        x ^= b
    n = len(payload) + 2
    return bytes([n & 0xFF, n >> 8, flag]) + bytes(payload) + bytes([x])


def to_file(typ, length, param1, param2, data):
    """(bytes to write, kind) for a SAVE: raw for a screen, else header + data.
    kind is 'screen' or 'plus3'."""

    if is_screen(typ, length, param1):
        return bytes(data), "screen"
    return bytes(plus3_header(typ, length, param1, param2)) + bytes(data), "plus3"


def describe(raw_head, size):
    """What a native file holds, from its first 128 bytes and its size:
    (type, length, param1, param2, data_offset) or None if it is neither a
    +3DOS file nor a raw screen. A headerless file of any other size is None:
    the caller decides (LOAD ... CODE with an address can still take it)."""

    p = parse_plus3(raw_head)
    if p is not None:
        typ, length, p1, p2 = p
        if HDR_LEN + length > size:
            return None                                 # truncated file
        return typ, length, p1, p2, HDR_LEN
    if size == SCREEN_LEN:
        return T_CODE, SCREEN_LEN, SCREEN_ADDR, 32768, 0
    return None


def headerless_code(size, addr=32768):
    """Fields for a headerless file loaded as CODE: the whole file at addr."""

    return T_CODE, size, addr, 32768, 0


def as_tap(typ, length, param1, param2, data, name):
    """The two TAP blocks (header + data) that stand for a native file on a
    one-shot tape, so the stock LOAD / VERIFY / MERGE code can read it."""

    return tap_block(0x00, tape_header(typ, name, length, param1, param2)) + \
        tap_block(0xFF, data)


def tape_name(path):
    """The 10-character tape name shown for a native file: its base name,
    extension dropped, cut to 10."""

    base = path[path.rfind('/') + 1:]
    k = base.rfind('.')
    if k > 0:
        base = base[:k]
    return base[:10]
