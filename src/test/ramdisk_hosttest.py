"""Host-side test for TS/ramdisk.py, the Megabank RAM disk's file system.

CPython, no Pico, no ROM. A model board (a bytearray of SIZE * 64K) and a
model mover with the ROM's operations and refusals (PROTOCOL.md 6.3: a page
past the board or an offset of 2000h or more is reply 4). The 2068's memory is
a second bytearray, for ops 1-3.

What it pins down: FORMAT's geometry; SAVE/LOAD through the header in the
directory entry; replacing a file; a file of 8K or more on a page boundary;
erase, rename, duplicate; compaction when free space is in pieces (and the
data intact after it); the generation counter (a second firmware sees a
change; an unchanged one doesn't re-read the directory); a cut-off entry
write and a leftover duplicate after a power cut; a corrupt superblock;
write-protect; a full disk and a full directory; no board.

Run:  python3 src/test/ramdisk_hosttest.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
from TS import ramdisk as rd                                    # noqa: E402

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


class Board:
    def __init__(self, banks=8, wp=False, present=True):
        self.mem = bytearray(banks * 65536)
        self.size = banks
        self.wp = wp
        self.present = present
        self.z80 = bytearray(65536)
        self.ops = []           # (op, n)
        self.cut = None         # an op 5 cut short after this many bytes

    @property
    def pages(self):
        return self.size * 8


class Mover:
    """The ROM's mover over Board, with its range checks."""

    def __init__(self, b):
        self.b = b

    def _at(self, n, page, off):
        if not self.b.present:
            raise rd.RdError(rd.J_IO, "no board (3)")
        if off >= 0x2000 or page * 8192 + off + n > self.b.pages * 8192:
            raise rd.RdError(rd.J_IO, "out of range (4)")
        return page * 8192 + off

    def info(self):
        self.b.ops.append((7, 0))
        if not self.b.present:
            return (0, 0, 0, 0, 0)
        return (1, 1, self.b.size, 1 if self.b.wp else 0, 1)

    def read(self, n, page, off):
        self.b.ops.append((4, n))
        a = self._at(n, page, off)
        return bytes(self.b.mem[a:a + n])

    def write(self, data, page, off):
        self.b.ops.append((5, len(data)))
        a = self._at(len(data), page, off)
        if self.b.wp:
            return                      # the switch drops the writes
        n = len(data)
        if self.b.cut is not None:
            n = min(n, self.b.cut)
            self.b.cut = None
            self.b.mem[a:a + n] = data[:n]
            raise PowerCut()
        self.b.mem[a:a + n] = data

    def move(self, n, page, off, page2, off2):
        self.b.ops.append((6, n))
        a = self._at(n, page, off)
        d = self._at(n, page2, off2)
        assert not (a < d < a + n or d < a < d + n), "op 6 with overlapping runs"
        self.b.mem[d:d + n] = self.b.mem[a:a + n]

    def copy_in(self, addr, n, page, off):
        self.b.ops.append((1, n))
        a = self._at(n, page, off)
        self.b.mem[a:a + n] = self.b.z80[addr:addr + n]

    def copy_out(self, addr, n, page, off):
        self.b.ops.append((2, n))
        a = self._at(n, page, off)
        self.b.z80[addr:addr + n] = self.b.mem[a:a + n]

    def compare(self, addr, n, page, off):
        self.b.ops.append((3, n))
        a = self._at(n, page, off)
        return self.b.z80[addr:addr + n] == self.b.mem[a:a + n]


class PowerCut(Exception):
    pass


def disk(b):
    d = rd.Disk()
    d.mv = Mover(b)
    return d


def header(kind, name, length, p1=0, p2=0x8000):
    return bytes([kind]) + rd.tape_name(name) + rd.w16(length) + rd.w16(p1) + rd.w16(p2)


def save(d, name, data, kind=3, addr=0x8000):
    """As tpi:rblk does: the header block, then the data block."""
    b = d.mv.b
    hdr = header(kind, name, len(data), addr)
    b.z80[0x6000:0x6011] = hdr
    d.mount()
    got = d.save_header(0x6000)
    assert got == hdr
    b.z80[addr:addr + len(data)] = data
    d.mount()
    return d.save_data(name, got, addr, len(data), 0xFF)


def load(d, name, addr=0x9000):
    b = d.mv.b
    d.mount()
    e = d.get(name)
    p, o = d.header_loc(e)
    d.mv.copy_out(0x6000, 17, p, o)
    hdr = bytes(b.z80[0x6000:0x6011])
    p, o = d.loc(e.first)
    if e.length:
        d.mv.copy_out(addr, e.length, p, o)
    return hdr, bytes(b.z80[addr:addr + e.length])


def pat(n, seed):
    return bytes((i * 7 + seed + (i >> 8)) & 0xFF for i in range(n))


def refused(fn, status):
    try:
        fn()
    except rd.RdError as e:
        return e.status == status
    return False


def block(b, d, stream):
    """The slot's ROM block, as the ROM would copy it (op 2)."""
    p, o = d.block_loc(stream)
    a = p * 8192 + o
    return b.mem[a:a + rd.BLOCK_LEN]


def rom_write(b, d, stream, data):
    """What the ROM does for PRINT #: each byte at the position, through the
    window; past the extent it asks the firmware to grow (tpi:rchgrow), and
    it writes the length and position back to the slot."""
    blk = block(b, d, stream)
    sp, so, ext, ln, pos = (rd.r16(blk, i) for i in (0, 2, 4, 6, 8))
    for c in data:
        if pos >= ext:
            d.grow(stream, pos + 1)
            blk = block(b, d, stream)
            sp, so, ext = rd.r16(blk, 0), rd.r16(blk, 2), rd.r16(blk, 4)
        a = sp * 8192 + so + pos
        b.mem[a] = c
        pos += 1
        ln = max(ln, pos)
        p, o = d.block_loc(stream)
        q = p * 8192 + o + 6
        b.mem[q:q + 4] = rd.w16(ln) + rd.w16(pos)


def rom_read(b, d, stream):
    blk = block(b, d, stream)
    sp, so, ln = rd.r16(blk, 0), rd.r16(blk, 2), rd.r16(blk, 6)
    a = sp * 8192 + so
    return bytes(b.mem[a:a + ln])


def channels():
    print("Channels (r: streams)")
    b = Board(banks=8)
    d = disk(b)
    d.mount(need=False)
    d.format(32)
    d.mount()
    sl = d.open_stream(4, "log", "w", False, 0)
    blk = block(b, d, 4)
    e = d.find("log")
    check(e is not None and e.length == 0 and e.kind == 3, "OPEN w: the file is made, empty, a CODE file")
    check(rd.r16(blk, 4) == 8 * 1024 and rd.r16(blk, 6) == 0 and rd.r16(blk, 8) == 0
          and rd.r16(blk, 10) == d.last and blk[14] == ord("w"),
          "its block: 8K reserved, length 0, position 0, the slot's page, mode w")
    p, o = d.loc(sl.first)
    check((rd.r16(blk, 0), rd.r16(blk, 2)) == (p, o), "the block's start is the file's first cluster")
    data = pat(20000, 5)
    rom_write(b, d, 4, data)
    check(d.slots[4].ext * 1024 >= 20000, "writing past the extent grows it (%d clusters)" % d.slots[4].ext)
    check(refused(lambda: d.erase(d.find("log")), rd.F_NAME), "ERASE of an open file: F")
    check(refused(lambda: save(d, "log", b"x"), rd.F_NAME), "SAVE over an open file: F")
    check(refused(lambda: d.rename(d.find("log"), "log2"), rd.F_NAME), "MOVE of an open file: F")
    check(refused(lambda: d.open_stream(5, "log", "a", False, 0), rd.F_NAME),
          "a second OPEN for writing: F")
    r = d.open_stream(5, "log", "r", False, 0)
    check(r.length == 20000, "a second stream may read it, at its current length")
    d.close(5)
    check(refused(lambda: d.format(32), rd.F_NAME), "FORMAT while a stream is open: F")
    check("log        Bytes      20000" in d.listing(), "CAT shows the open file's current length")
    d.close(4)
    e = d.find("log")
    check(e.length == 20000 and rd.r16(e.hdr, 11) == 20000 and 4 not in d.slots,
          "CLOSE: the length into the entry and its header; the slot is free")
    check(load(d, "log")[1] == data, "LOAD \"r:log\" CODE gives the bytes written")
    check(d.free() == d.nclusters - rd.clusters(20000), "CLOSE gave the unused room back")

    # a, u
    sl = d.open_stream(4, "log", "a", False, 0)
    check(sl.pos == 20000 and rd.r16(block(b, d, 4), 8) == 20000, "OPEN a: the position is the end")
    rom_write(b, d, 4, b"tail")
    d.close(4)
    check(load(d, "log")[1] == data + b"tail", "append")
    sl = d.open_stream(4, "log", "u", False, 30)
    check(sl.pos == 0 and block(b, d, 4)[12] == 30, "OPEN u with records: position 0, record length 30")
    rom_write(b, d, 4, b"HEAD")
    d.close(4)
    check(load(d, "log")[1] == b"HEAD" + data[4:] + b"tail", "update in place")
    check(refused(lambda: d.open_stream(4, "none", "r", False, 0), rd.F_NAME), "OPEN r of a missing file: F")
    check(refused(lambda: d.open_stream(4, "x", "w", False, 255), rd.Q_PARAM), "a record of 255: Q")

    # w empties
    d.open_stream(4, "log", "w", False, 0)
    rom_write(b, d, 4, b"new")
    d.close(4)
    check(load(d, "log")[1] == b"new", "OPEN w empties an existing file")

    # the mask: NEW / reset
    d.open_stream(3, "kept", "w", False, 0)
    rom_write(b, d, 3, b"0123456789")
    d.open_stream(6, "gone", "w", False, 0)
    rom_write(b, d, 6, b"abc")
    d.sync(1 << 3)
    check(3 in d.slots and 6 not in d.slots and load(d, "gone")[1] == b"abc",
          "the mask: stream 6 no longer open (NEW): closed with its length")
    d2 = disk(b)                                      # another firmware, or a restart
    d2.mount()
    check(3 in d2.slots and d2.slots[3].mode == "w", "the slots are on the board: a restart finds them")
    d2.sync(0)
    check(not d2.slots and load(d2, "kept")[1] == b"0123456789", "mask 0 (a reset): every slot closed")
    d.mount()

    # growth that has to move
    d.format(16)
    d.mount()
    save(d, "a", pat(1000, 1))
    save(d, "b", pat(1000, 2))
    d.open_stream(4, "a", "a", False, 0)
    check(d.slots[4].ext == 1, "OPEN a with a file right after: no room to reserve")
    rom_write(b, d, 4, pat(3000, 3))
    d.close(4)
    check(load(d, "a")[1] == pat(1000, 1) + pat(3000, 3) and load(d, "b")[1] == pat(1000, 2),
          "growth moved the file (op 6, no overlap) and kept both files")

    # compaction goes round an open file
    d.format(16)
    d.mount()
    for i in range(6):
        save(d, "f%d" % i, pat(1024, i))
    d.open_stream(4, "f3", "r", False, 0)
    for i in (0, 2, 4):
        d.erase(d.find("f%d" % i))
    f3 = d.find("f3").first
    save(d, "big", pat(3 * 1024, 9))
    check(d.find("f3").first == f3 and load(d, "f3")[1] == pat(1024, 3) and load(d, "big")[1] == pat(3072, 9)
          and load(d, "f1")[1] == pat(1024, 1) and load(d, "f5")[1] == pat(1024, 5),
          "compaction moves the others round an open file")
    d.close(4)

    # listing
    d.open_list(5, ["f1", "big", "f3"])
    sl = d.slots[5]
    check(sl.reclen == 10 and sl.entry is None and rom_read(b, d, 5) == b"f1" + bytes(8) + b"big" + bytes(7)
          + b"f3" + bytes(8), "a listing: 10-byte records padded with 0, no entry")
    used = d.used()
    d.close(5)
    check(d.used() == used - 1, "its clusters are free when it closes")

    # write-protect, garbage slots
    b.wp = True
    d.mount()
    check(refused(lambda: d.open_stream(4, "wp", "w", False, 0), rd.J_IO), "write-protected: OPEN w is J")
    check(d.open_stream(4, "f1", "r", False, 0).length == 1024, "but reading is fine")
    b.wp = False
    d.close(4)
    b2 = Board(banks=8)
    d3 = disk(b2)
    d3.mount(need=False)
    d3.format(32)
    p, o = d3.last, rd.SLOT_OFF
    b2.mem[p * 8192 + o:p * 8192 + o + 64] = bytes([0x4F]) * 64        # an old RAM disk's leftovers
    d4 = disk(b2)
    d4.mount()
    check(not d4.slots, "slot bytes that make no sense are free slots")


def main():
    print("Format")
    b = Board(banks=8)                      # 512K: 64 pages
    d = disk(b)
    check(refused(d.mount, rd.J_IO), "an unformatted board: J, 'No RAM disk'")
    d.mount(need=False)
    check(not d.formatted, "mount(need=False) says not formatted")
    d.format(rd.parse_size("", d.pages))
    check((d.first, d.last) == (32, 63), "FORMAT \"r:\": half the board, at the top (pages 32-63)")
    check(d.nclusters == 31 * 8, "31 data pages, 248 clusters")
    check(rd.parse_size("64", 64) == 8 and rd.parse_size("64k", 64) == 8, "a size in K")
    check(refused(lambda: rd.parse_size("12", 64), rd.Q_PARAM), "a size not a multiple of 8K: Q")
    check(refused(lambda: d.format(65), rd.Q_PARAM), "bigger than the board: Q")
    d2 = disk(b)
    d2.mount()
    check(d2.formatted and d2.files() == [], "a second firmware finds it, empty")

    print("SAVE and LOAD")
    data = pat(3000, 1)
    e = save(d, "prog", data, kind=0)
    hdr, got = load(d, "prog")
    check(got == data, "the data comes back")
    check(hdr[0] == 0 and hdr[1:11] == b"prog      " and rd.r16(hdr, 11) == 3000,
          "the header comes back from the directory entry")
    check(e.first == 0 and e.size == 3, "3000 bytes: 3 clusters from cluster 0")
    big = pat(20000, 2)
    e2 = save(d, "icons", big)
    check(e2.first % 8 == 0 and e2.first == 8, "20000 bytes start on a page boundary (cluster 8)")
    small = pat(500, 3)
    e3 = save(d, "tiny", small)
    check(e3.first == 3, "a small file fills the gap before it (cluster 3)")
    check(load(d, "icons")[1] == big and load(d, "tiny")[1] == small, "both come back")
    empty = save(d, "nil", b"")
    check(empty.size == 0 and load(d, "nil")[1] == b"", "an empty file")
    check(refused(lambda: d.get("nofile"), rd.F_NAME), "LOAD of a missing name: F")

    print("Replace, erase, rename, duplicate")
    gen = d.gen
    new = pat(1500, 9)
    save(d, "prog", new, kind=0)
    check(load(d, "prog")[1] == new and len([f for f in d.files() if f.name == "prog"]) == 1,
          "SAVE over a name replaces it; one entry")
    check(d.gen == gen + 2, "a replace: two commits (the new entry, then the old one cleared)")
    d.mount()
    d.rename(d.get("tiny"), "small")
    check(d.find("tiny") is None and load(d, "small")[1] == small, "rename")
    hdr, _ = load(d, "small")
    check(hdr[1:11] == b"small     ", "rename rewrites the header's name too")
    check(refused(lambda: d.rename(d.get("small"), "icons"), rd.F_NAME), "rename onto a name: F")
    d.duplicate(d.get("icons"), "icons2")
    check(load(d, "icons2")[1] == big and load(d, "icons")[1] == big, "COPY on the board (op 6)")
    d.erase(d.get("icons2"))
    check(d.find("icons2") is None, "erase")
    d3 = disk(b)
    d3.mount()
    check(sorted(f.name for f in d3.files()) == ["icons", "nil", "prog", "small"],
          "another firmware reads the same directory")

    print("The generation counter")
    n = len(b.ops)
    d3.mount()
    check([o for o, _ in b.ops[n:]] == [7, 4] and b.ops[-1][1] == rd.SB_LEN,
          "unchanged: op 7 and the superblock only")
    save(d, "x", b"abc")
    n = len(b.ops)
    d3.mount()
    check(len(b.ops) - n == 3 and d3.find("x") is not None, "changed elsewhere: the directory again")

    print("Compaction")
    b = Board(banks=8)
    d = disk(b)
    d.mount(need=False)
    d.format(4)                             # 3 data pages: 24 clusters
    files = {}
    for i in range(6):
        files["f%d" % i] = pat(4000, i)     # 4 clusters each: 24
        save(d, "f%d" % i, files["f%d" % i])
    check(refused(lambda: save(d, "more", b"z"), rd.Q_PARAM), "a full disk: Q")
    for k in ("f1", "f3"):
        d.erase(d.get(k))
        del files[k]
    want = pat(8192, 77)                    # 8 clusters, page-aligned: no free page
    check(d.alloc(len(want)) is None and d.free() == 8, "8 clusters free, in pieces")
    save(d, "page", want)
    files["page"] = want
    check(all(load(d, k)[1] == v for k, v in files.items()), "after compaction every file is intact")
    check(d.get("page").first % 8 == 0, "the new file is on a page boundary")
    d4 = disk(b)
    d4.mount()
    check(all(d4.get(k).first == d.get(k).first for k in files), "the moves are in the directory")

    print("Power cuts")
    b = Board(banks=8)
    d = disk(b)
    d.mount(need=False)
    d.format(8)
    save(d, "keep", pat(2000, 5))
    save(d, "victim", pat(2000, 6))
    b.z80[0x8000:0x8000 + 1000] = pat(1000, 7)
    d.mount()
    b.cut = 20                              # the new entry, cut after 20 bytes
    try:
        d.save_data("new", header(3, "new", 1000), 0x8000, 1000, 0xFF)
        check(False, "the cut raises")
    except PowerCut:
        pass
    d5 = disk(b)
    d5.mount()
    check(d5.find("new") is None and load(d5, "keep")[1] == pat(2000, 5),
          "an entry cut short: that file is lost, no other")
    # A cut between the new entry and clearing the old: two of one name.
    e = d5.get("victim")
    dup = rd.Entry(d5.free_slot(), e.hdr, e.first, 100, 0xFF, d5.gen + 5)
    d5.write_entry(dup)
    d5.mv.write(d5.superblock(), d5.last, 0)  # committed; the old one not yet cleared
    d6 = disk(b)
    d6.mount()
    check(len([f for f in d6.files() if f.name == "victim"]) == 1 and d6.get("victim").length == 100,
          "two entries of one name: the newer wins")

    print("A corrupt superblock")
    b.mem[63 * 8192 + 3] ^= 0xFF
    d7 = disk(b)
    check(refused(d7.mount, rd.J_IO), "a bad magic: no RAM disk (J)")
    b.mem[63 * 8192 + 3] ^= 0xFF
    b.mem[63 * 8192 + 12] ^= 1                # the generation: the sum no longer matches
    check(refused(disk(b).mount, rd.J_IO), "a bad sum: no RAM disk")
    b.mem[63 * 8192 + 12] ^= 1
    check(disk(b).mount() is None, "put back: it mounts")

    print("Write-protect, a full directory, no board")
    b.wp = True
    d8 = disk(b)
    d8.mount()
    check(d8.wp and refused(lambda: d8.save_data("w", header(3, "w", 1), 0x8000, 1, 0xFF), rd.J_IO),
          "write-protected: SAVE refused (J), before any write")
    check(refused(lambda: d8.erase(d8.get("keep")), rd.J_IO), "and ERASE")
    check(load(d8, "keep")[1] == pat(2000, 5), "LOAD still works")
    b.wp = False
    b = Board(banks=8)
    d = disk(b)
    d.mount(need=False)
    d.format(64)
    for i in range(rd.SLOTS):
        d.put("n%d" % i, header(3, "n%d" % i, 0), b"")
    check(d.high == rd.SLOTS and refused(lambda: d.put("one", header(3, "one", 0), b""), rd.Q_PARAM),
          "%d files: the directory is full (Q)" % rd.SLOTS)
    d9 = disk(Board(present=False))
    check(refused(d9.mount, rd.J_IO), "no board: J")
    check("No Megabank board" in d9.report(), "tpi:ram says so")

    channels()

    print("Text")
    b = Board(banks=8)
    d = disk(b)
    d.mount(need=False)
    check("No RAM disk" in d.report(), "tpi:ram, unformatted")
    d.format(32)
    save(d, "prog", pat(100, 1), kind=0)
    save(d, "scr", pat(6912, 2))
    lst = d.listing()
    check(lst.startswith("RAM disk 256K, 2 files, 240K free\r"), "CAT's first line")
    check("prog       Program      100\r" in lst and "scr        Bytes       6912\r" in lst, "a row a file")
    rep = d.report()
    check("Megabank: 512K, banks 1-8" in rep and "RAM disk: 256K, pages 32-63" in rep, "tpi:ram")

    ok = sum(results)
    print("%d/%d passed" % (ok, len(results)))
    return 0 if ok == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
