# The archive's tapes over WiFi, on the v3 card: tpi:net's indexes and its
# listing (docs/v3-wifi-archive-proposal.md). The fetching is
# board_v3.wifi_get; this module is the text: the item's URLs, a folder
# index read into rows, the listing kept between commands, and search.
#
# The item is tspico-2068-tapes on archive.org (#401), made by
# tools/sd-archive/tap_folder.py, whose docstring defines the formats:
#
#   TAP/.../index.txt, index2.txt...  a folder's index in parts of at most
#       8 KB: a "#tspico-dir" header ("part 1 of 2" in its sixth field),
#       then "name/ D title tapes" for a subfolder and
#       "name.tap status title year publisher size post" for a tape
#   tspico-taps.txt.gz  every tape: "path status title year publisher size
#       post", path from TAP/
#
# All of it is tab-separated UTF-8. The 2068 sees ASCII only (MSG_BYTE
# turns the rest into '?').

ITEM = "https://archive.org/download/tspico-2068-tapes/"
ROOT = "TAP"
FULL = "tspico-taps.txt"          # the full index, gunzipped
FULL_PATH = "/sd/" + FULL          # on the card, outside /TAP: no listing shows it
LIST_PATH = "/TMP/net.txt"         # the last listing, on the Pico's flash
SAVE_DIR = "/sd/TAP/NET"           # where downloads go
MAX_FIND = 99                      # matches tpi:net find lists


def part_url(folder, part):
    """The URL of a folder's index part (1, 2...)."""
    return ITEM + folder + ("/index.txt" if part == 1 else "/index%d.txt" % part)


def tape_url(path):
    return ITEM + path


def parent(folder):
    """The folder above, or ROOT at the top."""
    i = folder.rfind("/")
    return folder[:i] if i > 0 and folder != ROOT else ROOT


def parse_part(text, folder):
    """(parts, entries) from one index part's text. An entry is
    ("D", path, title, count) or ("T", path, status, title, size)."""
    parts, rows = 1, []
    for ln in text.split("\n"):
        if not ln:
            continue
        f = ln.split("\t")
        if ln[0] == "#":
            if len(f) > 5 and f[5].startswith("part "):
                parts = int(f[5].split()[-1])
            continue
        if f[1] == "D":
            rows.append(("D", folder + "/" + f[0].rstrip("/"), f[2], f[3]))
        elif len(f) >= 6:
            rows.append(("T", folder + "/" + f[0], f[1], f[2], f[5]))
    return parts, rows


def find(f, words, limit=MAX_FIND):
    """Tapes in the full index (an open text file) whose path and title hold
    every word (any case): (entries, matched). Entries stop at limit."""
    words = [w.lower() for w in words]
    rows, n = [], 0
    for ln in f:
        t = ln.rstrip("\n").split("\t")
        if len(t) < 6 or ln[0] == "#":
            continue
        hay = (t[0] + " " + t[2]).lower()
        if all(w in hay for w in words):
            n += 1
            if len(rows) < limit:
                rows.append(("T", t[0], t[1], t[2], t[5]))
    return rows, n


def save_listing(where, part, parts, rows, path=None):
    """Keep the listing on flash, for tpi:net <number>, more and .."""
    with open(path or LIST_PATH, "w") as f:
        f.write("#\t%s\t%d\t%d\n" % (where, part, parts))
        for r in rows:
            f.write("\t".join(r) + "\n")


def load_listing(path=None):
    """(where, part, parts, rows) of the last listing, or None."""
    try:
        f = open(path or LIST_PATH)
    except OSError:
        return None
    with f:
        h = f.readline().rstrip("\n").split("\t")
        rows = [tuple(ln.rstrip("\n").split("\t")) for ln in f if ln.strip()]
    if len(h) < 4:
        return None
    return h[1], int(h[2]), int(h[3]), rows


def name_of(entry):
    """A tape's file name, or a folder's, from its path."""
    return entry[1].rsplit("/", 1)[-1]


def row(i, entry, width=32):
    """One listing line, after the number: a folder as NAME/ title (tapes),
    a tape as name, its status letter and title. width counts the number."""
    if entry[0] == "D":
        s = "%s/ %s (%s)" % (name_of(entry), entry[2], entry[3])
    else:
        s = "%-8s %s %s" % (name_of(entry)[:-4], entry[2], entry[3])
    return "".join(c if " " <= c <= "~" else "?" for c in s[:width - 4])


HOW = {"L": 'LOAD ""', "R": 'LOAD "", then RUN', "C": 'LOAD "" CODE',
       "S": "load it with ecmvpico.tap"}   # an ECM picture


def how(status):
    """How a tape is loaded, from its status letter."""
    return HOW.get(status, 'LOAD ""')
