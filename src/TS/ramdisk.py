# ramdisk.py -- the TS-2068 Megabank's RAM disk: the file system behind "r:".
#
# The Megabank board (TS-2068-Megabank, docs/spec.md: "The RAM disk") is up to
# 4 MB of battery-backed RAM that only the Z80 can reach. So the file system
# lives here, on the v3 card, and every byte moves through the ROM's mover
# (response function 89h, PROTOCOL.md 6.3): this module decides what to copy
# where, and an object with the mover's operations (`mv`, below) does it. The
# directory and the data are on the board, so they survive power-off with the
# board's battery; this module keeps only a cache of the directory.
#
# Pages are the board's 8K pages, counted from BASE: 0 to SIZE * 8 - 1. The
# RAM disk is the pages first..last, at the top of the board (last is always
# the board's last page), so the banks below it stay free for programs.
#
#   page last, 0000h  the superblock (SB_LEN bytes):
#       0-3   "TSRD"           4  format version (1)    5  log2 cluster size (10)
#       6-7   first page       8-9  last page          10-13  generation
#      14-15  directory high-water: slots 0..high-1 are read
#      16-29  0                 30-31  the 16-bit sum of bytes 0-29
#   page last, 0100h  STAGE: a SAVE's 17-byte header, copied in from the 2068
#                     so the firmware can read it (the mover has no 2068 -> Pico
#                     operation)
#   page last, 0400h  the directory: SLOTS entries of 32 bytes
#   pages first..last-1  the data, in 1K clusters (cluster c is page
#                     first + c // 8, offset (c % 8) * 1K)
#
# A directory entry:
#    0      'F' (46h): a file. Anything else: a free slot
#    1-17   the file's 17-byte tape header: type, name (10), length, p1, p2
#   18-19   its first cluster      20-21  its length (the data block's)
#   22      the data block's flag byte (FFh from SAVE)
#   23-26   the generation it was written at (two entries of one name, after a
#           power cut between writing the new one and clearing the old: the
#           newer wins)
#   27-30   0                      31  XOR of bytes 0-30, XOR A5h
#
# The entry is written in one operation and its check byte is the last byte
# written, so a write cut short by a power cut leaves an entry that fails its
# check: that file is lost, no other is. A file's data is written before its
# entry, and the old entry is cleared only after the new one is in and the
# superblock says so (its high-water may have to grow to reach the new slot),
# so a cut during a SAVE loses at most the file being written. There is no allocation
# bitmap: which clusters are in use follows from the entries, so nothing can
# disagree with them.
#
# Files are contiguous. One of 8K or more starts on a page boundary, so a
# program can map a file's pages straight into a chunk. When free space is
# there but in pieces, `compact` slides the files down (op 6), in pieces no
# longer than the distance moved, so a piece never overlaps its source.
#
# Caching: every command reads the superblock (op 4, SB_LEN bytes) and reads the
# directory again only if the generation has changed. Every directory change
# raises it. That covers a reset, a power cycle and a second TS-Pico.
#
# No bus code here: `mv` is the mover (tspico.py's RD_MOVER on the card, a
# model in src/test/ramdisk_hosttest.py), so all of this is tested on the host.

MAGIC = b"TSRD"
VERSION = 1
SB_LEN = 32
STAGE = 0x100
DIR_OFF = 0x400
ENTRY = 32
SLOTS = (0x2000 - DIR_OFF) // ENTRY          # 224
PAGE = 8192
CLUSTER = 1024
PER_PAGE = PAGE // CLUSTER                   # 8
USED = 0x46                                  # 'F'

# The firmware's status codes (PROTOCOL.md 5.3)
OK, R_TAPE, F_NAME, Q_PARAM, J_IO = 1, 2, 3, 4, 10

TYPES = ("Program", "Num array", "Chr array", "Bytes")


class RdError(Exception):
    """A refusal: args = (status, message)."""

    @property
    def status(self):
        return self.args[0]

    @property
    def msg(self):
        return self.args[1]


def w16(v):
    return bytes((v & 0xFF, v >> 8 & 0xFF))


def r16(b, i):
    return b[i] | b[i + 1] << 8


def r32(b, i):
    return b[i] | b[i + 1] << 8 | b[i + 2] << 16 | b[i + 3] << 24


def w32(v):
    return bytes((v & 0xFF, v >> 8 & 0xFF, v >> 16 & 0xFF, v >> 24 & 0xFF))


def sum16(b, n):
    s = 0
    for i in range(n):
        s += b[i]
    return s & 0xFFFF


def tape_name(name):
    """A name as a tape header holds it: 10 bytes, padded with spaces."""
    b = name.encode()[:10]
    return b + b" " * (10 - len(b))


def check_name(name):
    if not 1 <= len(name) <= 10:
        raise RdError(F_NAME, "A name is 1-10 characters")
    for c in name:
        if not 32 <= ord(c) < 127:
            raise RdError(F_NAME, "A name is 1-10 characters")
    return name


def clusters(length):
    return (length + CLUSTER - 1) // CLUSTER


class Entry:
    __slots__ = ("slot", "hdr", "first", "length", "flag", "gen")

    def __init__(self, slot, hdr, first, length, flag, gen):
        self.slot = slot
        self.hdr = bytes(hdr)
        self.first = first
        self.length = length
        self.flag = flag
        self.gen = gen

    @property
    def name(self):
        return bytes(self.hdr[1:11]).decode().rstrip(" ")

    @property
    def kind(self):
        return self.hdr[0]

    @property
    def size(self):                         # clusters
        return clusters(self.length)

    def pack(self):
        b = bytearray(ENTRY)
        b[0] = USED
        b[1:18] = self.hdr
        b[18:20] = w16(self.first)
        b[20:22] = w16(self.length)
        b[22] = self.flag
        b[23:27] = w32(self.gen)
        x = 0xA5
        for i in range(31):
            x ^= b[i]
        b[31] = x
        return bytes(b)

    @staticmethod
    def parse(b, slot):
        if b[0] != USED:
            return None
        x = 0xA5
        for i in range(31):
            x ^= b[i]
        if x != b[31]:
            return None
        return Entry(slot, b[1:18], r16(b, 18), r16(b, 20), b[22], r32(b, 23))


def renamed(hdr, name):
    """A tape header with its name field replaced."""
    h = bytearray(hdr)
    h[1:11] = tape_name(name)
    return bytes(h)


class Disk:
    """The RAM disk on one board, through the mover `mv`:

    mv.info()                      -> (found, BASE, SIZE, STATUS, VERSION)
    mv.read(n, page, off)          -> bytes          (op 4)
    mv.write(data, page, off)                        (op 5)
    mv.move(n, page, off, page2, off2)               (op 6)
    mv.copy_in(addr, n, page, off)                   (op 1: 2068 -> board)
    mv.copy_out(addr, n, page, off)                  (op 2: board -> 2068)
    mv.compare(addr, n, page, off) -> True if equal  (op 3)

    A refused or failed operation raises RdError from the mover itself.
    One Disk lives for the firmware's lifetime; `mv` is set per command."""

    def __init__(self):
        self.mv = None
        self.found = False
        self.pages = 0          # on the board
        self.base = 0
        self.wp = False         # the write-protect switch
        self.low = False        # battery low
        self.version = 0
        self.formatted = False
        self.first = self.last = 0
        self.gen = 0
        self.high = 0
        self.entries = None     # slot -> Entry, or None: not read
        self.cache_gen = None
        self.confirm = None     # (what, gen): a FORMAT or ERASE waiting to be repeated

    # ── the board and the superblock ─────────────────────────────────────

    def probe(self):
        found, base, size, status, version = self.mv.info()
        self.found = bool(found)
        if not self.found:
            self.pages = 0
            raise RdError(J_IO, "No Megabank board")
        self.base, self.pages, self.version = base, size * 8, version
        self.wp, self.low = bool(status & 1), bool(status & 2)

    def mount(self, need=True):
        """The board, the superblock, and the directory if it changed. With
        need, an unformatted RAM disk is an error."""
        self.probe()
        last = self.pages - 1
        sb = self.mv.read(SB_LEN, last, 0)
        ok = (sb[0:4] == MAGIC and sb[4] == VERSION and sb[5] == 10
              and r16(sb, 30) == sum16(sb, 30) and r16(sb, 8) == last
              and r16(sb, 6) < last and r16(sb, 14) <= SLOTS)
        self.formatted = ok
        if not ok:
            self.entries = None
            self.cache_gen = None
            if need:
                raise RdError(J_IO, 'No RAM disk: FORMAT "r:" makes one')
            return
        self.first, self.last = r16(sb, 6), last
        self.gen, self.high = r32(sb, 10), r16(sb, 14)
        if self.entries is not None and self.cache_gen == self.gen:
            return
        self.entries = {}
        if self.high:
            raw = self.mv.read(self.high * ENTRY, last, DIR_OFF)
            names = {}
            for s in range(self.high):
                e = Entry.parse(raw[s * ENTRY:(s + 1) * ENTRY], s)
                if e is None:
                    continue
                o = names.get(e.name)
                if o is not None:                   # a cut SAVE's leftover
                    if o.gen >= e.gen:
                        continue
                    del self.entries[o.slot]
                names[e.name] = e
                self.entries[s] = e
        self.cache_gen = self.gen

    def superblock(self):
        b = bytearray(SB_LEN)
        b[0:4] = MAGIC
        b[4] = VERSION
        b[5] = 10
        b[6:8] = w16(self.first)
        b[8:10] = w16(self.last)
        b[10:14] = w32(self.gen)
        b[14:16] = w16(self.high)
        b[30:32] = w16(sum16(b, 30))
        return bytes(b)

    def commit(self):
        """A directory change is complete: raise the generation."""
        self.gen = (self.gen + 1) & 0xFFFFFFFF
        self.mv.write(self.superblock(), self.last, 0)
        self.cache_gen = self.gen

    def writable(self):
        if self.wp:
            raise RdError(J_IO, "The board is write-protected")

    # ── geometry ─────────────────────────────────────────────────────────

    @property
    def nclusters(self):
        return (self.last - self.first) * PER_PAGE

    def loc(self, c):
        return self.first + c // PER_PAGE, (c % PER_PAGE) * CLUSTER

    def files(self):
        return sorted(self.entries.values(), key=lambda e: e.name)

    def find(self, name):
        for e in self.entries.values():
            if e.name == name:
                return e
        return None

    def get(self, name):
        e = self.find(name)
        if e is None:
            raise RdError(F_NAME, "Not found: r:%s" % name)
        return e

    def used(self):
        return sum(e.size for e in self.entries.values())

    def free(self):
        return self.nclusters - self.used()

    def alloc(self, length):
        """The first cluster of a free run for length bytes, or None. A file
        of 8K or more starts on a page boundary."""
        k = clusters(length)
        align = PER_PAGE if length >= PAGE else 1
        runs = sorted((e.first, e.first + e.size) for e in self.entries.values() if e.size)
        pos = 0
        for a, b in runs + [(self.nclusters, self.nclusters)]:
            p = (pos + align - 1) // align * align
            if p + k <= a:
                return p
            pos = max(pos, b)
        return None

    def free_slot(self):
        for s in range(SLOTS):
            if s not in self.entries:
                return s
        raise RdError(Q_PARAM, "The RAM disk's directory is full")

    def place(self, length):
        """alloc, compacting first if the space is there but in pieces."""
        if length == 0:
            return 0
        c = self.alloc(length)
        if c is None and self.free() >= clusters(length):
            self.compact()
            c = self.alloc(length)
        if c is None:
            raise RdError(Q_PARAM, "The RAM disk is full")
        return c

    # ── directory writes ─────────────────────────────────────────────────

    def write_entry(self, e):
        self.mv.write(e.pack(), self.last, DIR_OFF + e.slot * ENTRY)
        self.entries[e.slot] = e
        if e.slot >= self.high:
            self.high = e.slot + 1

    def clear_entry(self, e):
        self.mv.write(b"\x00", self.last, DIR_OFF + e.slot * ENTRY)
        self.entries.pop(e.slot, None)

    def add(self, name, hdr, length, flag, c):
        """The data is on the board at cluster c: enter it as name, replacing
        any file of that name (the new entry first, then the old one goes)."""
        old = self.find(name)
        e = Entry(self.free_slot(), renamed(hdr, name), c, length, flag, (self.gen + 1) & 0xFFFFFFFF)
        self.write_entry(e)
        self.commit()                   # the new entry counts (its slot may raise high) ...
        if old is not None:
            self.clear_entry(old)       # ... before the old one goes
            self.commit()
        return e

    # ── operations ───────────────────────────────────────────────────────

    def format(self, npages):
        """A new, empty RAM disk of npages pages at the top of the board."""
        self.writable()
        if not 2 <= npages <= self.pages:
            raise RdError(Q_PARAM, "Size: 16K to %dK, in 8K steps" % (self.pages * 8))
        old_gen = self.gen if self.formatted else 0
        self.last = self.pages - 1
        self.first = self.pages - npages
        self.gen = old_gen
        self.high = 0
        self.entries = {}
        self.formatted = True
        self.commit()

    def save_header(self, addr):
        """A SAVE's header block: copy it in to STAGE, read it back."""
        self.writable()
        self.mv.copy_in(addr, 17, self.last, STAGE)
        return bytes(self.mv.read(17, self.last, STAGE))

    def save_data(self, name, hdr, addr, length, flag):
        """A SAVE's data block, from 2068 memory at addr."""
        self.writable()
        self.free_slot()                            # fail before copying
        c = self.place(length)
        if length:
            p, o = self.loc(c)
            self.mv.copy_in(addr, length, p, o)
        return self.add(name, hdr, length, flag, c)

    def header_loc(self, e):
        """Where e's tape header is on the board: inside its entry."""
        return self.last, DIR_OFF + e.slot * ENTRY + 1

    def put(self, name, hdr, data, flag=0xFF):
        """A whole file from the TS-Pico (COPY to "r:", a restore)."""
        self.writable()
        self.free_slot()
        c = self.place(len(data))
        if data:
            p, o = self.loc(c)
            self.mv.write(data, p, o)
        return self.add(name, hdr, len(data), flag, c)

    def fetch(self, e):
        """A file's data, to the TS-Pico (COPY from "r:")."""
        if not e.length:
            return b""
        p, o = self.loc(e.first)
        return self.mv.read(e.length, p, o)

    def erase(self, e):
        self.writable()
        self.clear_entry(e)
        self.commit()

    def rename(self, e, name):
        self.writable()
        check_name(name)
        o = self.find(name)
        if o is not None and o is not e:
            raise RdError(F_NAME, "r:%s exists" % name)
        n = Entry(self.free_slot(), renamed(e.hdr, name), e.first, e.length, e.flag,
                  (self.gen + 1) & 0xFFFFFFFF)
        self.write_entry(n)
        self.commit()
        self.clear_entry(e)
        self.commit()

    def duplicate(self, e, name):
        """COPY "r:a" TO "r:b": on the board (op 6)."""
        self.writable()
        check_name(name)
        self.free_slot()
        c = self.place(e.length)
        if e.length:
            p, o = self.loc(e.first)
            p2, o2 = self.loc(c)
            self.mv.move(e.length, p, o, p2, o2)
        return self.add(name, e.hdr, e.length, e.flag, c)

    def compact(self):
        """Slide every file down, in order, to close the gaps. Each move is in
        pieces no longer than the distance, so no piece overlaps its source;
        a file's entry is rewritten once its data is in place."""
        self.writable()
        pos = 0
        moved = False
        for e in sorted(self.entries.values(), key=lambda e: e.first):
            if not e.size:
                continue
            if e.length >= PAGE:
                pos = (pos + PER_PAGE - 1) // PER_PAGE * PER_PAGE
            if e.first > pos:
                dist = (e.first - pos) * CLUSTER
                done = 0
                while done < e.length:
                    n = min(dist, e.length - done, 0xFFFF)
                    sp, so = self.loc(e.first)
                    dp, do = self.loc(pos)
                    # page:offset + done, as a page and offset again
                    sp, so = sp + (so + done) // PAGE, (so + done) % PAGE
                    dp, do = dp + (do + done) // PAGE, (do + done) % PAGE
                    self.mv.move(n, sp, so, dp, do)
                    done += n
                e.first = pos
                self.write_entry(e)
                moved = True
            pos = e.first + e.size
        if moved:
            self.commit()

    # ── text ─────────────────────────────────────────────────────────────

    def listing(self):
        fs = self.files()
        free = self.free() * CLUSTER // 1024
        lines = ["RAM disk %dK, %d file%s, %dK free" % (
            (self.last - self.first + 1) * 8, len(fs), "" if len(fs) == 1 else "s", free)]
        for e in fs:
            t = TYPES[e.kind] if e.kind < 4 else "Type %d" % e.kind
            lines.append("%-10s %-9s %6d" % (e.name, t, e.length))
        return "\r".join(lines) + "\r"

    def report(self):
        """SAVE "tpi:ram": the board and the RAM disk."""
        if not self.found:
            return "No Megabank board\r"
        lines = ["Megabank: %dK, banks %d-%d" % (self.pages * 8, self.base,
                                                   self.base + self.pages // 8 - 1),
                 "Board version %d" % self.version,
                 "Battery: %s" % ("LOW" if self.low else "OK"),
                 "Write-protect: %s" % ("ON" if self.wp else "off")]
        if self.formatted:
            n = len(self.entries)
            lines.append("RAM disk: %dK, pages %d-%d" % ((self.last - self.first + 1) * 8,
                                                         self.first, self.last))
            lines.append("%d file%s, %dK free" % (n, "" if n == 1 else "s", self.free()))
        else:
            lines.append('No RAM disk: FORMAT "r:" makes one')
        return "\r".join(lines) + "\r"


def parse_size(arg, pages):
    """FORMAT "r:[size]": size in K (a multiple of 8), or K followed by K;
    none: half the board. Returns pages."""
    s = arg.strip().upper()
    if s.endswith("K"):
        s = s[:-1]
    if not s:
        return max(2, pages // 2)
    if not s.isdigit():
        raise RdError(Q_PARAM, 'FORMAT "r:" or "r:size", size in K')
    k = int(s)
    if k % 8:
        raise RdError(Q_PARAM, "Size: a multiple of 8K")
    return k // 8
