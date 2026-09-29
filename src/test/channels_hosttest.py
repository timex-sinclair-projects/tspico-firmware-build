"""Host-side test for TS/channels.py -- OPEN # channels, stage 1 (sequential).

Text translation both ways (keywords, line ends, the comma control, dropped
control codes and their parameters, the pound sign, chunk boundaries), binary
pass-through, the r / w / a rules, and the errors. CPython, no Pico: the file
system is a dict.

Run:  python3 src/test/channels_hosttest.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from TS import channels as C                                    # noqa: E402

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


class MemFS:
    def __init__(self):
        self.files = {}

    def exists(self, p):
        return p in self.files

    def size(self, p):
        return len(self.files[p])

    def read(self, p, pos, n):
        return bytes(self.files[p][pos:pos + n])

    def write(self, p, pos, data, truncate):
        f = bytearray() if truncate else self.files.setdefault(p, bytearray())
        f[pos:pos + len(data)] = data
        self.files[p] = f


def main():
    print("text out (2068 -> file)")
    t = C.TextOut()
    listing = b"  10" + bytes([0xF5]) + b'"hi";' + bytes([0xAD]) + b"5" + b"\r"
    check(t.feed(listing) == b'  10 PRINT "hi"; TAB 5\n', "a LIST line: keywords spelt out, CR -> LF (%r)"
          % C.TextOut().feed(listing))
    t = C.TextOut()
    check(t.feed(b"A" + bytes([6]) + b"B\r") == b"A" + b" " * 15 + b"B\n", "comma control: spaces to column 16")
    t = C.TextOut()
    check(t.feed(bytes([22, 5, 3]) + b"X" + bytes([16, 2]) + b"Y\r") == b"XY\n",
          "AT and INK dropped with their parameters")
    t = C.TextOut()
    a = t.feed(b"P" + bytes([22, 5]))
    b = t.feed(bytes([3]) + b"Q\r")
    check(a + b == b"PQ\n", "a control code's parameters split across chunks")
    t = C.TextOut()
    check(t.feed(bytes([96, 0x80, 0x90]) + b"\r") == "£??\n".encode(), "pound -> UTF-8 pound, graphics -> ?")
    t = C.TextOut()
    check(t.feed(b"x" + bytes([123, 0x80 | 0x7F & 0xEC]) + b"\r")[:1] == b"x", "extended tokens don't crash")
    check(C.TextOut().feed(bytes([123]) + b"\r") == b"ON ERR \n", "ON ERR (123) spelt out")

    print("text in (file -> 2068)")
    ti = C.TextIn()
    check(ti.feed(b"one\ntwo\r\nthree\rfour") == b"one\rtwo\rthree\rfour", "LF, CRLF and CR all become CR")
    ti = C.TextIn()
    check(ti.feed(b"a\r") + ti.feed(b"\nb") == b"a\rb", "CRLF split across chunks: one CR")
    ti = C.TextIn()
    pound = "£".encode()
    check(ti.feed(b"x" + pound[:1]) + ti.feed(pound[1:] + b"y") == bytes([ord("x"), 96, ord("y")]),
          "UTF-8 pound split across chunks -> 96")
    check(C.TextIn().feed("é\t".encode()) == b"? ", "other UTF-8 -> ?, tab -> space")

    print("channels")
    fs = MemFS()
    ch = C.Channels(fs)
    ch.open(4, "/sd/TAP/notes.txt", "w")
    ch.write(4, b"Hello" + bytes([13]))
    ch.write(4, bytes([0xF5]) + b"2" + bytes([13]))
    ch.close(4)
    check(bytes(fs.files["/sd/TAP/notes.txt"]) == b"Hello\nPRINT 2\n", "w: text written, keywords spelt out")
    ch.open(4, "/sd/TAP/notes.txt", "a")
    ch.write(4, b"more\r")
    check(bytes(fs.files["/sd/TAP/notes.txt"]).endswith(b"PRINT 2\nmore\n"), "a: appended")
    ch.open(5, "/sd/TAP/notes.txt", "r")
    got = b""
    while True:
        d = ch.read(5, 4)
        if not d:
            break
        check(len(d) <= 4, "  read never returns more than asked (%d)" % len(d)) if len(d) > 4 else None
        got += d
    check(got == b"Hello\rPRINT 2\rmore\r", "r: read back in small chunks, CR line ends (%r)" % got)
    fs.files["/sd/TAP/last.txt"] = bytearray(b"a\nno newline")
    ch.open(6, "/sd/TAP/last.txt", "r")
    got = b""
    while True:
        d = ch.read(6, 255)
        if not d:
            break
        got += d
    check(got == b"a\rno newline\r", "a last line without a newline still ends in CR, once (%r)" % got)
    ch.open(7, "/sd/TAP/bin.dat", "wb")
    ch.write(7, bytes(range(256)))
    ch.open(7, "/sd/TAP/bin.dat", "rb")
    check(ch.read(7, 255) + ch.read(7, 255) == bytes(range(256)) and ch.read(7, 255) == b"",
          "binary: every byte both ways, then end of file")
    ch.open(8, "/sd/TAP/notes.txt", "w")
    check(bytes(fs.files["/sd/TAP/notes.txt"]) == b"", "w truncates an existing file")

    def err(f):
        try:
            f()
        except C.ChannelError as e:
            return e.args[1]
        return None
    check(err(lambda: ch.open(4, "/sd/TAP/nothere", "r")) == "F", "r of a missing file: F")
    check(err(lambda: ch.open(4, "/sd/TAP/x", "q")) == "Q", "a bad mode: Q")
    ch.open(4, "/sd/TAP/last.txt", "r")
    check(err(lambda: ch.write(4, b"x")) == "Q", "writing a read channel: Q")
    ch.open(4, "/sd/TAP/w.txt", "w")
    check(err(lambda: ch.read(4, 1)) == "Q", "reading a write channel: Q")
    ch.close(4)
    check(err(lambda: ch.read(4, 1)) == "O", "a closed stream: O")
    ch.close(4)
    check(True, "closing a stream that isn't open is fine")
    ch.open(9, "/sd/TAP/w.txt", "w")
    ch.open(9, "/sd/TAP/last.txt", "r")
    check(ch.table[9].mode == "r", "re-opening a stream replaces the stale entry")
    ch.close_all()
    check(ch.table == {}, "close_all")

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
