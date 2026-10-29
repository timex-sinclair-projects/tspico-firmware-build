# catalog.py -- the pure half of CAT / SAVE "tpi:dir <arg>".
#
# Pattern matching, path resolution, TAP block tables and listing text. Nothing
# here touches the SD card, the PIO or the TS-Pico globals: tspico.py does the
# I/O (with the SD activated) and hands the results in. That keeps every rule
# testable on the host (src/test/catalog_hosttest.py).
#
# See docs/DISK_COMMANDS_SPEC.md §2.

ROOT = "/sd/TAP"                                    # public "/" on the SD card

DIR_EXT = ('TAP', 'TZX', 'DCK', 'ROM', 'BIN')      # what a plain listing shows (and indexes)

BLK_TYPES = ('Program', 'Num. array', 'Char array', 'Code block')


# Characters a name from a Mac or PC may hold that the 2068 can't show as
# themselves or type back: its character printer (HOME 063Bh) prints |
# and ~ as the STICK and FREE keywords always, and { } and 7Fh as ON ERR,
# SOUND and RESET unless FLAGS bit 4 happens to be set; none of the five
# is on its keyboard, nor is anything above 7Fh or below 20h.
UNSHOWABLE = "{|}~\x7f"


def screen_name(s):
    """s as the 2068 lists it: every character it can't print or type
    becomes '?', which LOAD "tpi:..." then takes as a wildcard (LOAD_TPI).
    '?' can't be part of a FAT name, so it never collides with a real one."""
    return "".join("?" if (c < " " or c > "~" or c in UNSHOWABLE) else c for c in s)


def match_shown(name, pat):
    """Does pat match name as the 2068 lists it (screen_name)? Case-
    insensitive; '*' matches any run, but '?' only a character the 2068
    can't show -- which is what a '?' in a listing stands for -- so
    "?game?.tap" finds {game}.tap and not (game).tap. A '?' can't be part of
    a FAT name, so this never shadows a real one."""
    return match(screen_name(name), pat, False)


def has_wild(s):
    return '*' in s or '?' in s


def match(name, pat, any_q=True):
    """Case-insensitive glob: '*' matches any run (including none), '?' one
    char -- or, with any_q False, only a literal '?' (see match_shown)."""

    n = name.upper()
    p = pat.upper()
    i = j = 0
    star = -1
    mark = 0
    while i < len(n):
        if j < len(p) and ((any_q and p[j] == '?') or p[j] == n[i]):
            i += 1
            j += 1
        elif j < len(p) and p[j] == '*':
            star = j
            mark = i
            j += 1
        elif star >= 0:
            j = star + 1
            mark += 1
            i = mark
        else:
            return False
    while j < len(p) and p[j] == '*':
        j += 1
    return j == len(p)


def resolve(cur, arg):
    """Real path for a public path argument, or None if it leaves the root.

    cur is the real current directory (TSP.cur_path, e.g. "/sd/TAP/GAMES").
    A leading '/' starts at the public root. '.' and '..' are honoured but
    '..' never climbs above the root.
    """

    if arg.startswith('/'):
        parts = []
    else:
        if not (cur == ROOT or cur.startswith(ROOT + '/')):
            return None
        parts = [p for p in cur[len(ROOT):].split('/') if p]
    for p in arg.split('/'):
        if p == '' or p == '.':
            continue
        if p == '..':
            if not parts:
                return None
            parts.pop()
        else:
            parts.append(p)
    return ROOT + ''.join('/' + p for p in parts)


def public(real):
    """Public form of a real path: "/sd/TAP/GAMES" -> "/GAMES"."""

    p = real[len(ROOT):]
    return p if p else '/'


def split_arg(arg):
    """Split "games/*.tap" into ("games", "*.tap"). The pattern is None when
    the last component has no wildcard, and the directory part is '' for the
    current directory."""

    arg = arg.strip()
    k = arg.rfind('/')
    last = arg[k + 1:]
    if not has_wild(last):
        return arg, None
    if k < 0:
        return '', last
    return (arg[:k] if k > 0 else '/'), last


def split_pair(arg):
    """ "a.tap|b.tap" -> ("a.tap", "b.tap"). The ROM joins COPY's and MOVE's names with
    '|', which FAT names can't contain; typed by hand (SAVE "tpi:copy a b") a
    single space works too. Either half is '' when missing."""

    if '|' in arg:
        a, b = arg.split('|', 1)
    else:
        parts = arg.split()
        if len(parts) != 2:
            return arg.strip(), ''
        a, b = parts
    return a.strip(), b.strip()


def select(items, pat):
    """What CAT lists from a directory's os.ilistdir() items, in its order:
    [(name, is_dir, size)] -- directories, then files, then (bare listing
    only) the files DIR can't index. dirinfo.tap is never listed; dot names
    only when the pattern starts with a dot. Shared by CAT and OPEN #n,"d:...".
    """

    dirs_l, files_l, other_l = [], [], []
    for item in sorted(items, key=lambda it: it[0].lower()):
        name = item[0]
        if name == "dirinfo.tap":
            continue
        if pat is None:
            if name[0] == '.':
                continue
        elif not match(name, pat) or (name[0] == '.' and pat[0] != '.'):
            continue
        if item[1] == 16384:
            dirs_l.append((name, True, 0))
        elif pat is None and name[-3:].upper() not in DIR_EXT:
            other_l.append((name, False, item[3]))
        else:
            files_l.append((name, False, item[3]))
    return dirs_l + files_l + other_l


def basename(path):
    return path[path.rfind('/') + 1:]


def parent(path):
    return path[:path.rfind('/')] or ROOT


def within(path, top):
    """True if path is top or somewhere below it (case-insensitive, as FAT)."""

    p, t = path.upper(), top.upper()
    return p == t or p.startswith(t + '/')


def size_text(size):
    """A file's size for the listing's 10-character column: "52 B",
    "2.5 kB", "47 kB", "1.2 MB" (1 kB = 1024 bytes). Whole kB from 10 kB,
    one decimal below 10 kB and from 1 MB.

    It used to be "%.2f kB" % (size >> 10): the shift dropped the fraction
    first, so every size read ".00 kB" (2026-09-30 audit, §4; changed
    2026-10-02). The Commander reads only the index and the name from
    dirinfo.tap's rows (tc, lines 71 and 1114), so the size text is free to
    change within its column."""

    if size < 1024:
        return "%d B" % size
    if size < 10 << 10:
        return "%.1f kB" % (size / 1024)
    if size < 1 << 20:
        return "%d kB" % int(size / 1024 + 0.5)
    return "%.1f MB" % (size / (1 << 20))


def space_pair(total, free):
    """("240 MB", "236 MB") for a card or flash of `total` bytes with `free`
    left. The unit comes from the total, so both read alike: kB below 1 MB,
    MB with one decimal below 10 MB, whole MB below 1 GB, GB with one
    decimal above (the board takes cards up to 16 GB). The CAT header used
    to give GB to four places whatever the size, so the 256 MB cards the
    boards ship with read "SD: 0.2346GB"."""

    if total >= 1 << 30:
        div, fmt, unit = 1 << 30, "%.1f", "GB"
    elif total >= 10 << 20:
        div, fmt, unit = 1 << 20, "%d", "MB"
    elif total >= 1 << 20:
        div, fmt, unit = 1 << 20, "%.1f", "MB"
    else:
        div, fmt, unit = 1 << 10, "%d", "kB"

    def one(n):
        v = n / div
        if fmt == "%d":
            v = int(v + 0.5)
        return (fmt % v) + " " + unit
    return one(total), one(free)


def counts(nf, nd):
    """ "3 files, 1 dir" """

    return "%d file%s, %d dir%s" % (nf, "" if nf == 1 else "s", nd, "" if nd == 1 else "s")


def dir_rows(entries, index_of, shorten):
    """Listing rows (32 chars each, no CR -- the screen wraps) for
    entries = [(name, is_dir, size), ...] already sorted and filtered.

    index_of(name) gives the number LOAD "tpi:n" uses for that file, or None
    when it has none (another directory, or a type DIR doesn't index).
    shorten is tspico's shorten_filename, so names are cut the same way.
    """

    L = []
    for name, is_dir, size in entries:
        nom = screen_name(name)
        if is_dir:
            L.append("<%-21s       0 B" % (shorten(nom, 20) + ">"))
        else:
            i = index_of(name)
            idx = "%03d" % i if i is not None else "   "
            L.append("%s %-18s%10s" % (idx, shorten(nom, 18), size_text(size)))
    return L


def tap_table(f):
    """Block table of the TAP file open in f (binary, seekable).

    The shape OFF_TABLE has always built for the mounted file, one entry per
    block: [offset, length, " Y"/" N" (header?), name]. A header's name is its
    10-character filename; a data block's is the type of the header before it,
    or 'Code block' when there is none.
    """

    f.seek(0, 2)
    fsize = f.tell()
    tbl = []
    offset = 0
    blk_type = 'Code block'
    buf = bytearray(14)
    while offset + 2 <= fsize:
        f.seek(offset)
        n = f.readinto(buf)
        long = buf[0] + 256 * buf[1]
        if n >= 14 and buf[2] == 0:
            hdr = " Y"
            try:
                # The 2068 wrote this name: send its bytes as they are, so it
                # looks as the 2068 shows it anywhere else (| as STICK...).
                # Only what SEND_MSG2 can't carry -- control codes, and 80h+
                # (which would end the ROM's string) -- becomes '?'.
                name = "".join(chr(b) if 32 <= b <= 127 else "?" for b in buf[4:14])
                blk_type = BLK_TYPES[buf[3]]
            except Exception:
                name = "??????????"
                blk_type = "undefined"
        else:
            hdr = " N"
            name = blk_type
        tbl.append([offset, long, hdr, name])
        offset += long + 2
    return tbl


def tap_header_rows(tbl, cur_idx=None, idx1=0, idx2=None, orphans=False):
    """TAPDIR's header listing rows (CODE 1,n) for any block table.

    cur_idx marks the tape position with '>' (None when the table is not the
    mounted file's). orphans=True also lists data blocks that have no header
    in front of them (loaders, headerless code); TAPDIR shows those only when
    the tape is positioned on one."""

    if idx2 is None:
        idx2 = len(tbl) - 1
    N = []
    for idx, el in enumerate(tbl):
        if idx < idx1 or idx > idx2:
            continue
        orphan = el[2] != " Y" and (idx == 0 or tbl[idx - 1][2] != " Y")
        if el[2] == " Y" or idx == cur_idx or (orphans and orphan):
            N.append(">" if idx == cur_idx else " ")
            N.append("%02d " % idx)
            if el[2] == " Y" and idx + 1 < len(tbl):
                N.append("%-10s  %5s " % (tbl[idx + 1][3], tbl[idx + 1][1]))
            elif el[2] == " Y":
                N.append("%-10s  %5s " % ("(no data)", 0))
            else:
                N.append("Data block  %5s " % el[1])
            N.append("%-10s" % ("headerless" if orphans and orphan else el[3]))
    return N


# --- LIST "name": a file as the 2068 shows it --------------------------------

LIST_TEXT_MAX = 8192                                # bytes of a text file LIST shows
LIST_HEX_MAX = 2048                                 # bytes of anything else (256 rows)


def is_text(data):
    """True if data reads as text: no control codes but TAB, LF and CR, and
    no DEL. Bytes from 80h up (UTF-8, Latin-1) pass; LIST shows them as '?'."""

    for b in data:
        if (b < 32 and b not in (9, 10, 13)) or b == 127:
            return False
    return True


def list_text(data, size, text=None):
    """LIST "name"'s text for the first bytes of a file (`data`) of `size`
    bytes. Text as itself, line ends kept and a TAB as two spaces, through
    screen_name; anything else as a hex dump, 8 bytes a row in 30 columns:
    "0000 0011223344556677 ..h.i..."  If `data` is not the whole file, a
    last line says how much of it this is. `text` says which (default:
    is_text(data)); a control code in text shows as '?'."""

    if text is None:
        text = is_text(data)
    if text:
        out = [c if c in "\r\n" else screen_name(c)
               for c in "".join(chr(b) for b in data).replace("\t", "  ")]
    else:
        out = []
        for i in range(0, len(data), 8):
            row = data[i:i + 8]
            out.append("%04X %-16s %s\r" % (
                i, "".join("%02X" % b for b in row),
                "".join(chr(b) if 32 <= b < 127 and chr(b) not in UNSHOWABLE else "." for b in row)))
    if len(data) < size:
        out.append("\r(the first %d of %d bytes)" % (len(data), size))
    return "".join(out)


# --- The card's label ----------------------------------------------------------
# MicroPython's VfsFat doesn't give Python the FAT volume label (FatFs has
# f_getlabel/f_setlabel, but only mkfs calls f_setlabel), so these read and
# write it in the raw sectors, through a block device handed in (readblocks/
# writeblocks of 512-byte blocks: the SD driver, or a test image). Writing
# needs the card unmounted: FatFs keeps a sector of the root folder cached.
#
# The label is a root-folder entry with attribute 08h, what Windows and macOS
# show. The boot sector has a copy (BS_VolLab) that DOS showed; FatFs's
# f_setlabel leaves it alone, and so does write_label: the boot sector is the
# one sector whose loss makes the card unmountable, and nothing reads it for
# the name. So a label change writes one sector, the one FatFs would.

LABEL_MAX = 11
LABEL_BAD = '"*+,./:;<=>?[\\]|'                     # FatFs's f_setlabel refuses these


def label_clean(name):
    """The label FAT would store for `name` (upper case, at most 11
    characters, no trailing spaces), or None if it can't be one. "" is no
    label."""

    name = name.rstrip(" ").upper()
    if len(name) > LABEL_MAX or name[:1] == " ":
        return None
    for c in name:
        if c < " " or c > "~" or c in LABEL_BAD or c in UNSHOWABLE:
            return None
    return name


def _u16(b, i):
    return b[i] | b[i + 1] << 8


def _u32(b, i):
    return b[i] | b[i + 1] << 8 | b[i + 2] << 16 | b[i + 3] << 24


def _is_vbr(b):
    """A FAT boot sector with 512-byte sectors (FatFs's check_fs, simplified)."""

    return (b[510] == 0x55 and b[511] == 0xAA and b[0] in (0xEB, 0xE9, 0xE8)
            and _u16(b, 11) == 512 and b[13] and not b[13] & (b[13] - 1)
            and b[16] in (1, 2) and _u16(b, 14))


class _Fat:
    """The geometry of the FAT volume on dev, found as FatFs finds it: the
    first sector, else the first of the MBR's four partitions that holds
    one. OSError if there is none."""

    def __init__(self, dev):
        self.dev = dev
        b = self.read(0)
        start = 0
        if not _is_vbr(b):
            if b[510] != 0x55 or b[511] != 0xAA:
                raise OSError(19, "No FAT volume")
            for k in range(4):
                lba = _u32(b, 446 + 16 * k + 8)
                if lba and _is_vbr(self.read(lba)):
                    start = lba
                    break
            else:
                raise OSError(19, "No FAT volume")
            b = self.read(start)
        self.start = start
        spc, rsvd, nfat = b[13], _u16(b, 14), b[16]
        fatsz = _u16(b, 22) or _u32(b, 36)
        self.spc = spc
        self.fat = start + rsvd
        self.fat32 = _u16(b, 22) == 0
        if self.fat32:
            self.data = self.fat + nfat * fatsz
            self.root_clus = _u32(b, 44)
        else:
            self.root = self.fat + nfat * fatsz
            self.root_secs = (_u16(b, 17) * 32 + 511) // 512

    def read(self, n):
        buf = bytearray(512)
        self.dev.readblocks(n, buf)
        return buf

    def root_sectors(self):
        """Every sector of the root folder, in order."""

        if not self.fat32:
            for i in range(self.root_secs):
                yield self.root + i
            return
        c = self.root_clus
        for _ in range(65536):                       # a loop in the chain ends it
            if c < 2 or c >= 0x0FFFFFF7:
                return
            for i in range(self.spc):
                yield self.data + (c - 2) * self.spc + i
            sec = self.read(self.fat + c * 4 // 512)
            c = _u32(sec, c * 4 % 512) & 0x0FFFFFFF

    def find(self):
        """(sector, offset, buf) of the label entry, then of the first free
        entry: (None, None, None) for one that isn't there."""

        lab = free = (None, None, None)
        for n in self.root_sectors():
            buf = self.read(n)
            for off in range(0, 512, 32):
                b0, attr = buf[off], buf[off + 11]
                if b0 == 0:
                    if free[0] is None:
                        free = (n, off, buf)
                    return lab, free
                if b0 == 0xE5:
                    if free[0] is None:
                        free = (n, off, buf)
                    continue
                if attr & 0x3F != 0x0F and attr & 0x08 and lab[0] is None:
                    lab = (n, off, buf)
        return lab, free


def read_label(dev):
    """The card's label ("" for none). OSError if there's no FAT volume."""

    fat = _Fat(dev)
    (n, off, buf), _ = fat.find()
    if n is None:
        return ""
    raw = bytearray(buf[off:off + 11])
    if raw[0] == 0x05:
        raw[0] = 0xE5
    return "".join(chr(b) if 32 <= b < 127 else "?" for b in raw).rstrip(" ")


def write_label(dev, name):
    """Give the card the label `name` (label_clean's form; "" takes it
    away). OSError if there's no FAT volume, ValueError if the root folder
    has no free entry for it. Writes the one root-folder sector that holds
    the entry, and nothing else."""

    fat = _Fat(dev)
    lab, free = fat.find()
    if name:
        raw = (name + " " * LABEL_MAX)[:LABEL_MAX].encode()
        n, off, buf = lab if lab[0] is not None else free
        if n is None:
            raise ValueError("Root folder full")
        entry = bytearray(32)
        entry[0:11] = raw
        entry[11] = 0x08
        buf[off:off + 32] = entry
        fat.dev.writeblocks(n, buf)
    else:
        n, off, buf = lab
        if n is not None:
            buf[off] = 0xE5
            fat.dev.writeblocks(n, buf)


def card_line(label, total, free):
    """CAT's card line, at most 32 characters: "SD: 240 MB; free: 236 MB",
    the label in place of "SD" when the card has one, shorter forms when a
    long label doesn't fit."""

    tot, fr = space_pair(total, free)
    who = label or "SD"
    for line in ("%s: %s; free: %s" % (who, tot, fr),
                 "%s: %s, %s free" % (who, tot, fr),
                 "%s %s, %s free" % (who, tot, fr),
                 "%s: %s free" % (who, fr)):
        if len(line) <= 32:
            return line
    return line[:32]
