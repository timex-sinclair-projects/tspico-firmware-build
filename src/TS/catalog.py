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


def size_text(size):
    """Size column, exactly as LIST_DIR_FILES has always shown it."""

    if size >= 1024:
        return "%.2f kB" % (size >> 10)
    return "%d B" % size


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
