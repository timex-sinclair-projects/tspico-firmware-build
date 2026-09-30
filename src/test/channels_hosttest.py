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
    every = bytes(b for b in range(256) if b != 23)   # 23 is TAB, as on the screen
    ch.open(7, "/sd/TAP/bin.dat", "wb")
    ch.write(7, every)
    ch.open(7, "/sd/TAP/bin.dat", "rb")
    check(ch.read(7, 255) + ch.read(7, 255) == every and ch.read(7, 255) == b"",
          "binary: every byte but 23 (TAB) both ways, then end of file")
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
    before = bytes(fs.files["/sd/TAP/last.txt"])
    check(err(lambda: ch.write(4, b"P?")) is None and bytes(fs.files["/sd/TAP/last.txt"]) == before,
          "output to a read channel (INPUT #'s prompt) is dropped")
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

    stage2(err)

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


def tab(n):
    return bytes([23, n & 0xFF, n >> 8])


def stage2(err):
    print("stage 2: records (TAB n = record n)")
    fs = MemFS()
    ch = C.Channels(fs)
    p = "/sd/TAP/people.dat"
    ch.open(4, p, "u", 10)
    check(fs.files[p] == b"", "u creates a missing file")
    ch.write(4, tab(3) + b"carol\r")
    check(bytes(fs.files[p]) == b" " * 20 + b"carol     ",
          "PRINT #4;TAB 3;\"carol\": records 1-2 padded, 3 = carol + spaces (%r)" % bytes(fs.files[p]))
    ch.write(4, tab(1) + b"al")
    ch.write(4, b"ice\r")
    check(bytes(fs.files[p])[:10] == b"alice     ", "a record written in two chunks (PRINT ...;)")
    ch.write(4, tab(2))
    ch.write(4, b"bob\r")
    check(ch.read(4, 255) == b"carol     \r", "the next read after writing record 2 is record 3, then CR")
    ch.write(4, tab(1))
    check(ch.read(4, 255) == b"alice     \r", "INPUT #4;TAB 1;a$: exactly record 1 and CR")
    check(ch.read(4, 255) == b"bob       \r", "then sequentially record 2")
    ch.read(4, 255)
    check(ch.read(4, 255) == b"", "past the last record: end of file")
    ch.write(4, tab(0))
    check(ch.read(4, 255) == b"3\r", "INPUT #4;TAB 0;n: the record count")
    ch.write(4, tab(0))
    check(err(lambda: ch.write(4, b"x")) == "Q", "PRINT #4;TAB 0;...: Q")
    ch.write(4, tab(2))
    check(err(lambda: ch.write(4, b"12345678901")) == "Q", "longer than the record: Q, nothing cut off")
    check(bytes(fs.files[p])[10:20] == b"bob       ", "  and record 2 is untouched")
    ch.write(4, tab(5) + b"eve;")
    ch.close(4)
    check(len(fs.files[p]) == 50 and bytes(fs.files[p])[40:] == b"eve;      ",
          "a record left open by ';' is padded at CLOSE; the gap is padding (%d)" % len(fs.files[p]))
    ch.open(5, p, "r", 10)
    ch.write(5, tab(4))
    check(ch.read(5, 255) == b"          \r", "r with a record length: TAB 4 reads the padded gap record")
    ch.write(5, b"P?")
    check(bytes(fs.files[p])[:5] == b"alice", "r: prompt text is still dropped")
    ch.open(6, "/sd/TAP/rec.bin", "ub", 4)
    ch.write(6, tab(2) + bytes([1, 2]) + b"\r")
    check(bytes(fs.files["/sd/TAP/rec.bin"]) == bytes(4) + bytes([1, 2, 0, 0]), "binary records pad with 0")
    check(err(lambda: ch.open(7, p, "u", 255)) == "Q", "record length 255: Q (254 is the most)")

    print("stage 2: streams (TAB n = byte n)")
    q = "/sd/TAP/s.txt"
    fs.files[q] = bytearray(b"line one\nline two\nline three\n")
    ch.open(4, q, "u")
    check(ch.read(4, 255) == b"line one\r", "u reads one line at a time")
    ch.write(4, b"LINE TWO\r")
    check(bytes(fs.files[q]) == b"line one\nLINE TWO\nline three\n",
          "a write after INPUT # lands right after that line (%r)" % bytes(fs.files[q]))
    ch.write(4, tab(6))
    check(ch.read(4, 255) == b"one\r", "TAB 6: from byte 6 of the file")
    ch.write(4, tab(0))
    check(ch.read(4, 255) == b"%d\r" % len(fs.files[q]), "TAB 0 on a stream: the size in bytes")
    ch.open(5, q, "r")
    ch.write(5, tab(10))
    check(ch.read(5, 255) == b"LINE TWO\rline three\r", "r: TAB 10 seeks, then reads ahead as before")
    ch.write(5, tab(1) + b"P?")
    check(ch.read(5, 4) == b"line", "TAB 1 then prompt text on r: back to the start, prompt dropped")
    t = C.Channels(fs)
    t.open(3, q, "u")
    t.write(3, bytes([23]))
    t.write(3, bytes([15]))
    t.write(3, bytes([0]))
    check(t.read(3, 255) == b"TWO\r", "TAB 15 sent one byte per chunk")


if __name__ == "__main__":
    sys.exit(main())
