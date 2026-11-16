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
    stage3(err)
    speech(err)
    commands(err)
    cat_text(err)

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


def stage3(err):
    print("stage 3: d: listings")
    ch = C.Channels(MemFS())
    ch.open_list(4, ["GAMES/", "adv.tap", "ch\u00e9.bas"])
    got = b""
    while True:
        d = ch.read(4, 7)
        if not d:
            break
        got += d
    check(got == b"GAMES/\radv.tap\rch?.bas\r", "one name a line, a dir's with '/', non-ASCII as '?' (%r)" % got)
    check(ch.read(4, 255) == b"", "then end of file (Report 8)")
    ch.write(4, tab(0))
    check(ch.read(4, 255) == b"3\r", "TAB 0: the number of names")
    ch.write(4, tab(8) + b"P?")
    check(ch.read(4, 255) == b"adv.tap\rch?.bas\r", "TAB 8: from the second name; prompt text dropped")
    ch.open_list(5, [])
    check(ch.read(5, 255) == b"", "no names: the first read is end of file")
    ch.write(5, tab(0))
    check(ch.read(5, 255) == b"0\r", "  and TAB 0 says 0")


def speech(err):
    print("speech: v: channels (#375)")
    said = []

    def say(text):
        if "[NOPE]" in text:
            raise ValueError("NOPE")             # as speech.allophones does
        if "OFF" in text:
            raise OSError("speech is off")       # as tsbus.say does when it never started
        said.append(text)
        return len(text), len(text)
    ch = C.Channels(MemFS())
    ch.open_speech(4, say)
    check(ch.speaking(4) and not ch.speaking(5), "speaking(): the v: stream, no other")
    ch.write(4, b"HELLO")
    check(said == [], "no CR yet: nothing said")
    ch.write(4, b" THERE\r")
    check(said == ["HELLO THERE"], "a CR says the line (%r)" % said)
    ch.write(4, b"\xf5 2\r\r")                  # PRINT, a keyword token; then an empty line
    check(said[1:] == ["PRINT  2"], "keywords are spelt out; an empty line says nothing (%r)" % said[1:])
    ch.write(4, b"ONE\rTWO\r")
    check(said[2:] == ["ONE", "TWO"], "two lines in one chwr: two sayings (%r)" % said[2:])
    ch.write(4, tab(9) + b"BYE")
    ch.close(4)
    check(said[4:] == ["BYE"] and not ch.speaking(4), "TAB ignored; CLOSE says the unfinished line")
    ch.open_speech(4, say)
    check(err(lambda: ch.read(4, 10)) == "Q", "v: can't be read: Q")
    check(err(lambda: ch.write(4, b"[NOPE]\r")) == "Q", "an unknown allophone name: Q")
    ch.write(4, b"SPEECH OFF")
    ch.close(4)
    check(not ch.speaking(4), "CLOSE closes even when speech is off")
    ch.open(5, "/sd/TAP/w.txt", "w")
    ch.open_speech(5, say)
    check(ch.speaking(5) and ch.table[5].path is None, "v: replaces a stale file entry on the stream")
    ch.close_all()



class Lazy:
    """An answer with only len() and chunk(), as XDirText is."""

    def __init__(self, data):
        self.data = data
        self.slices = 0

    def __len__(self):
        return len(self.data)

    def chunk(self, pos, n):
        self.slices += 1
        return self.data[pos:pos + n]


def commands(err):
    print("commands: x: channels (#404)")
    ran = []
    big = Lazy(b"2\n1\n" + b"".join(b"row %02d\n" % i for i in range(40)))

    def run(line):
        ran.append(line)
        if line == "path":
            return b"/games\n"
        if line == "dir":
            return big
        if line == "none":
            return b"\n"
        raise C.ChannelError("Not an x: command", "Q")
    ch = C.Channels(MemFS())
    ch.open_command(4, run)
    check(ch.in_memory(4) and not ch.in_memory(5), "in_memory(): the x: stream, no other")
    check(ch.read(4, 255) == b"", "nothing asked yet: end of data (Report 8)")
    ch.write(4, b"pa")
    check(ran == [], "no CR yet: nothing run")
    ch.write(4, b"th\r")
    check(ran == ["path"], "a CR runs the line (%r)" % ran)
    check(ch.read(4, 255) == b"/games\r", "the answer, LF -> CR")
    check(ch.read(4, 255) == b"", "then end of data")
    ch.write(4, b"  path  \r")
    check(ran[-1] == "path" and ch.read(4, 255) == b"/games\r", "spaces around the command go; asked again, read again")
    ch.write(4, b"dir\r")
    first = ch.read(4, 10)
    check(first == b"2\r1\rrow 00", "a long answer comes in pieces (%r)" % first)
    rest = b""
    while True:
        d = ch.read(4, 255)
        if not d:
            break
        rest += d
    check(first + rest == big.data.replace(b"\n", b"\r"), "... all of it, read through chunk()")
    check(big.slices >= 2, "the answer was read in pieces, never copied whole (%d pieces)" % big.slices)
    ch.write(4, b"dir\r")
    ch.read(4, 20)
    ch.write(4, b"path\r")
    check(ch.read(4, 255) == b"/games\r", "a new command replaces an answer read only in part")
    ch.write(4, b"none\r")
    check(ch.read(4, 255) == b"\r" and ch.read(4, 255) == b"", "an empty line is one CR, then the end")
    ch.write(4, b"\r\r")
    check(ran[-1] == "none", "PRINT #4 alone runs nothing")
    check(err(lambda: ch.write(4, b"bogus\r")) == "Q", "an unknown command: Q")
    check(ch.read(4, 255) == b"", "... and the last answer is gone")
    check(err(lambda: ch.write(4, b"\xf5\r")) == "Q" and ran[-1] == "PRINT",
          "a keyword token is spelt out, as on any text channel (%r): not a command, Q" % ran[-1])
    ch.write(4, tab(3) + b"path\r")
    check(ran[-1] == "path" and ch.read(4, 255) == b"/games\r", "TAB ignored")
    ch.close(4)
    check(not ch.in_memory(4) and 4 not in ch.table, "CLOSE closes it")
    ch.open(5, "/sd/TAP/w.txt", "w")
    check(not ch.in_memory(5), "a file stream is not in memory")
    ch.open_command(5, run)
    check(ch.in_memory(5) and ch.table[5].path is None, "x: replaces a stale file entry on the stream")
    ch.open_list(6, ["a/", "b"])
    check(ch.in_memory(6), "a d: listing is in memory too")
    ch.close_all()



def cat_text(err):
    print("write_text: CAT #s into a file (#404)")
    fs = MemFS()
    writes = []
    real = fs.write
    fs.write = lambda p, pos, data, t: writes.append(len(data)) or real(p, pos, data, t)
    ch = C.Channels(fs)
    ch.open(4, "/sd/TAP/cat.txt", "w")
    ch.write(4, b"Before\r")
    ch.write_text(4, ["Path:/TAP", "", "000 a.tap   1 kB"])
    ch.write(4, b"After\r")
    check(bytes(fs.files["/sd/TAP/cat.txt"]) == b"Before\nPath:/TAP\n\n000 a.tap   1 kB\nAfter\n",
          "text file: each line with LF, at the file's position (%r)" % bytes(fs.files["/sd/TAP/cat.txt"]))
    del writes[:]
    ch.write_text(4, ["%031d" % i for i in range(100)])
    check(len(writes) == 7 and max(writes) <= 512 + 32, "100 lines: 7 writes of about 512 bytes (%r)" % writes)
    ch.open(5, "/sd/TAP/cat.bin", "wb")
    ch.write_text(5, ["ab", "c"])
    check(bytes(fs.files["/sd/TAP/cat.bin"]) == b"ab\rc\r", "binary file: the CRs as they are")
    ch.open(6, "/sd/TAP/cat.rec", "w", 8)
    ch.write_text(6, ["one", "two"])
    check(bytes(fs.files["/sd/TAP/cat.rec"]) == b"one     two     ", "record file: a record a line")
    check(err(lambda: ch.write_text(6, ["longer than 8"])) == "Q", "  a line too long: Q")
    ch.open(7, "/sd/TAP/cat.txt", "r")
    check(err(lambda: ch.write_text(7, ["x"])) == "Q", "a file opened to be read: Q")
    ch.open_list(8, ["a"])
    check(err(lambda: ch.write_text(8, ["x"])) == "Q", "a d: listing: Q")
    ch.open_command(9, lambda line: b"")
    check(err(lambda: ch.write_text(9, ["x"])) == "Q", "an x: stream: Q")
    check(err(lambda: ch.write_text(10, ["x"])) == "O", "a stream that isn't open: O")
    ch.close_all()


if __name__ == "__main__":
    sys.exit(main())
