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


def has_wild(s):
    return '*' in s or '?' in s


def match(name, pat):
    """Case-insensitive glob: '*' matches any run (including none), '?' one char."""

    n = name.upper()
    p = pat.upper()
    i = j = 0
    star = -1
    mark = 0
    while i < len(n):
        if j < len(p) and (p[j] == '?' or p[j] == n[i]):
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
    """ "a.tap|b.tap" -> ("a.tap", "b.tap"). The ROM joins MOVE's two names with
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
        nom = name.replace("~", "?")
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
                name_raw = bytes(buf[4:14]).decode()
                name = ''.join(' ' if (ord(c) <= 30 or ord(c) >= 127) else c for c in name_raw)
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
