# channels.py -- the Pico side of OPEN #n,"f:name" channels (DISK_COMMANDS_SPEC.md §4).
#
# Stage 1: sequential text and binary files. The fdd ROM's channel driver sends
# what BASIC prints to the stream (raw 2068 bytes: tokens, control codes, CR)
# and asks for bytes when BASIC reads it (INPUT #, INKEY$ #). This module keeps
# one entry per stream and does the text translation both ways.
#
# The card is unmounted between commands (its pins are shared with the 2068
# link), so no file stays open: every operation opens the file, seeks to the
# saved position, reads or writes, and closes it. File access is passed in
# (`fs`), so all of this is tested on the host (src/test/channels_hosttest.py).

# The TS-2068 keywords: $A5-$FF as the Spectrum's, and six more at low codes.
TOKENS = (
    "RND", "INKEY$", "PI", "FN", "POINT", "SCREEN$", "ATTR", "AT", "TAB",
    "VAL$", "CODE", "VAL", "LEN", "SIN", "COS", "TAN", "ASN", "ACS", "ATN",
    "LN", "EXP", "INT", "SQR", "SGN", "ABS", "PEEK", "IN", "USR", "STR$",
    "CHR$", "NOT", "BIN", "OR", "AND", "<=", ">=", "<>", "LINE", "THEN", "TO",
    "STEP", "DEF FN", "CAT", "FORMAT", "MOVE", "ERASE", "OPEN #", "CLOSE #",
    "MERGE", "VERIFY", "BEEP", "CIRCLE", "INK", "PAPER", "FLASH", "BRIGHT",
    "INVERSE", "OVER", "OUT", "LPRINT", "LLIST", "STOP", "READ", "DATA",
    "RESTORE", "NEW", "BORDER", "CONTINUE", "DIM", "REM", "FOR", "GO TO",
    "GO SUB", "INPUT", "LOAD", "LIST", "LET", "PAUSE", "NEXT", "POKE", "PRINT",
    "PLOT", "RUN", "SAVE", "RANDOMIZE", "IF", "CLS", "DRAW", "CLEAR", "RETURN",
    "COPY")
EXTRA = {12: "DELETE", 123: "ON ERR", 124: "STICK", 125: "SOUND", 126: "FREE",
         127: "RESET"}
POUND = 96                                          # the 2068's pound sign


def keyword(code):
    if code >= 0xA5:
        return TOKENS[code - 0xA5]
    return EXTRA.get(code)


class TextOut:
    """2068 output bytes -> text-file bytes (UTF-8, LF line ends).

    Keywords are spelt out with spaces around them as LIST shows them; the
    comma control (6) becomes spaces to the next 16-column stop; INK..OVER (one
    parameter) and AT / TAB (two) are dropped with their parameters; other
    control codes and graphics are dropped (graphics become '?').
    Stateful: a control code's parameters can arrive in the next chunk."""

    PARAMS = {16: 1, 17: 1, 18: 1, 19: 1, 20: 1, 21: 1, 22: 2, 23: 2}

    def __init__(self):
        self.skip = 0
        self.col = 0
        self.last = "\n"

    def _put(self, out, s):
        for ch in s:
            if ch == "\n":
                self.col = 0
            else:
                self.col += 1
            self.last = ch
        out.extend(s.encode())

    def feed(self, data):
        out = bytearray()
        for b in data:
            if self.skip:
                self.skip -= 1
                continue
            if b == 13:
                self._put(out, "\n")
            elif b in self.PARAMS:
                self.skip = self.PARAMS[b]
            elif b == 6:
                self._put(out, " " * (16 - self.col % 16))
            elif b == POUND:
                self._put(out, "£")
            elif b == 12 or b >= 123 and b <= 127 or b >= 0xA5:
                lead = "" if self.last in (" ", "\n") else " "
                self._put(out, lead + keyword(b) + " ")
            elif 32 <= b < 123:
                self._put(out, chr(b))
            elif b >= 128:
                self._put(out, "?")                  # block graphics, UDGs
            # anything else (<32): dropped
        return bytes(out)


class TextIn:
    """Text-file bytes -> 2068 input bytes: CR, LF or CRLF -> CR (13), pound
    -> 96, ASCII 32-122 as-is, anything else '?'. Stateful across chunks for a
    CRLF split between them and for UTF-8 sequences."""

    def __init__(self):
        self.cr = False
        self.pend = b""

    def feed(self, data):
        data = self.pend + bytes(data)
        self.pend = b""
        out = bytearray()
        i = 0
        n = len(data)
        while i < n:
            b = data[i]
            if b == 10:
                if not self.cr:
                    out.append(13)
                self.cr = False
                i += 1
                continue
            self.cr = False
            if b == 13:
                out.append(13)
                self.cr = True
            elif 32 <= b < 123:
                out.append(b)
            elif b >= 0x80:                          # a UTF-8 sequence: whole, or keep for later
                k = 2 if b < 0xE0 else 3 if b < 0xF0 else 4
                if i + k > n:
                    self.pend = data[i:]
                    break
                out.append(POUND if data[i:i + k] == "£".encode() else 63)
                i += k
                continue
            elif b == 9:
                out.append(32)
            # other control bytes: dropped
            i += 1
        return bytes(out)


class Channel:
    def __init__(self, path, mode, binary, pos):
        self.path = path
        self.mode = mode                             # 'r', 'w' or 'a'
        self.binary = binary
        self.pos = pos                               # the next byte of the file
        self.text_out = TextOut()
        self.text_in = TextIn()
        self.eof_cr = False                          # a last line without a newline got its CR
        self.last_raw = 10


class ChannelError(Exception):
    """(message, status) -- status is the firmware's report code name."""


def parse_mode(m):
    """"r", "w", "a" with an optional "b" (binary): (mode, binary)."""

    m = (m or "r").lower()
    binary = "b" in m
    m = m.replace("b", "")
    if m not in ("r", "w", "a"):
        raise ChannelError("Mode must be r, w or a (+b)", "Q")
    return m, binary


class Channels:
    """Open channels by stream number. fs gives the file access:
       fs.exists(path), fs.size(path), fs.read(path, pos, n) -> bytes,
       fs.write(path, pos, data, truncate) (truncate: start the file empty)."""

    def __init__(self, fs):
        self.fs = fs
        self.table = {}

    def open(self, stream, path, mode):
        m, binary = parse_mode(mode)
        self.table.pop(stream, None)                 # a stale entry (NEW, reset) goes
        if m == "r":
            if not self.fs.exists(path):
                raise ChannelError("Not found", "F")
            pos = 0
        elif m == "w":
            self.fs.write(path, 0, b"", True)
            pos = 0
        else:
            pos = self.fs.size(path) if self.fs.exists(path) else 0
            if pos == 0:
                self.fs.write(path, 0, b"", True)
        self.table[stream] = Channel(path, m, binary, pos)

    def _get(self, stream):
        ch = self.table.get(stream)
        if ch is None:
            raise ChannelError("Stream not open", "O")
        return ch

    def write(self, stream, data):
        ch = self._get(stream)
        if ch.mode == "r":
            return                                   # INPUT #'s prompt items: dropped
        out = bytes(data) if ch.binary else ch.text_out.feed(data)
        if out:
            self.fs.write(ch.path, ch.pos, out, False)
            ch.pos += len(out)

    def read(self, stream, n):
        """Up to n bytes for the 2068, or b"" at the end of the file."""

        ch = self._get(stream)
        if ch.mode != "r":
            raise ChannelError("Opened for writing", "Q")
        size = self.fs.size(ch.path)
        if ch.binary:
            data = self.fs.read(ch.path, ch.pos, min(n, max(0, size - ch.pos)))
            ch.pos += len(data)
            return data
        while True:
            if ch.pos >= size:
                if not ch.eof_cr and ch.last_raw not in (10, 13):
                    ch.eof_cr = True
                    return b"\r"                     # finish a last line that has no newline
                return b""
            raw = self.fs.read(ch.path, ch.pos, min(n, size - ch.pos))
            if not raw:
                return b""
            ch.pos += len(raw)
            ch.last_raw = raw[-1]
            out = ch.text_in.feed(raw)               # never longer than raw
            if out:
                return out

    def close(self, stream):
        """Close it; closing a stream that isn't open is not an error."""

        self.table.pop(stream, None)

    def close_all(self):
        self.table.clear()
