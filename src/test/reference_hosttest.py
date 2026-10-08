"""docs/reference/ -- the programmer's reference -- must cover the code it describes.

The reference (docs/reference/README.md) explains every top-level function,
class, method and module variable of the firmware, every tpi: command, and
every label of the ROM sources. This test fails CI when:

  1. a symbol in the code has no entry in the reference (COVERAGE), or
  2. a source file changed since the reference was last checked against it
     (STAMPS: the table in docs/reference/README.md records a hash of each
     source; re-read the chapters, flows and appendices its row lists, fix
     what changed, then re-stamp), or
  3. a flow or appendix is not listed against any source in that table
     (FLOWS: they cut across the sources, so the table says which sources
     each one follows; appendix/index.md and appendix/glossary.md exempt).

The index links each symbol to an entry in its own source's chapters (the
stamp table's Chapter cell) when there is one, so a name that two sources
share points at the right one.

What counts as an entry: a Markdown heading (## or deeper) or the first cell
of a table row, anywhere under docs/reference/ except README.md and
appendix/, holding the symbol's name in backticks: `ACTIVATE_MQ()`,
`PICO_STATUS.__init__`, `files`, `tpi:cd`, `WAIT_PICO_READY`. A trailing
"(...)" is ignored, so `RX_CAPTURE(MQ, raw, n, stall_ms, ready=None)` names
RX_CAPTURE. Command names compare case-insensitively.

Run:  python3 src/test/reference_hosttest.py            # check (CI)
      python3 src/test/reference_hosttest.py --missing  # only what is uncovered
      python3 src/test/reference_hosttest.py --list     # the whole inventory
      python3 src/test/reference_hosttest.py --stamp    # every stamp row with its current hash
      python3 src/test/reference_hosttest.py --relines SRC...  # line numbers in SRC's chapters
                        # that moved since SRC was stamped (--apply writes them)
      python3 src/test/reference_hosttest.py --index    # regenerate appendix/index.md

The rule itself is in CLAUDE.md ("Keeping docs/reference/ current").
"""

import ast
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
REF = os.path.join(ROOT, "docs", "reference")
README = os.path.join(REF, "README.md")

# Python sources whose top-level symbols the reference must cover.
# dev_tspico.py / dev_extcmd.py are byte-for-byte copies (dev_sync_hosttest),
# TS/buildinfo.py is generated and TS/__init__.py is empty.
FIRMWARE = (
    "src/main.py",
    "src/TS/tspico.py",
    "src/TS/tspico_io.py",
    "src/TS/sdcard.py",
    "src/TS/channels.py",
    "src/TS/catalog.py",
    "src/TS/extcmd.py",
    "src/TS/native.py",
    "src/TS/printer.py",
    "src/upgrade/main.py",
    "src/upgrade/upgrade.py",
)

# Z80 sources: every global label and EQU must have an entry.
ROM_ASM = (
    "src/rom/fdd/fddcmd.asm",
    "src/rom/patches/tspico-sync.asm",
    "src/rom/patches/tspico-zx48-v3.asm",
    "src/upgrade/updater.asm",
)
# The curated names of the ROM's own (binary-only) routines.
ROM_SYMS = "docs/rom-analysis/tspico-exrom-symbols.sym"

# Everything the reference describes, hashed in README.md's stamp table.
STAMPED = FIRMWARE + ROM_ASM + (
    ROM_SYMS,
    "src/config.ini",
    "src/manifest.py",
    "src/upgrade/manifest.py",
    "src/upgrade/loader.bas",
    "src/rom/TSPICO.ROM",
    "src/rom/TSPICO-SYNC.ROM",
    "src/rom/TSPICO-23.ROM",
    "src/rom/TSPICO-ZX48-V4.BIN",
    "flash/manifest.json",
    "tools/build-rom.py",
    "tools/build-flash.py",
    "tools/build-upgrade.py",
    "tools/gen-buildinfo.py",
    ".github/workflows/build.yml",
    ".github/workflows/release.yml",
)

# Where the SA_funct / EXT_SA_FUNCT command tables live.
COMMAND_TABLES = (("src/TS/tspico.py", "SA_funct"), ("src/TS/extcmd.py", "EXT_SA_FUNCT"))


def read(rel, binary=False):
    with open(os.path.join(ROOT, rel), "rb") as f:
        data = f.read()
    if binary:
        return data
    return data.replace(b"\r\n", b"\n").decode("utf-8", "replace")


def stamp(rel):
    """12 hex digits of sha256 over the LF-normalised file (ROM images raw)."""
    binary = rel.endswith((".ROM", ".BIN", ".bin", ".rom"))
    data = read(rel, binary=True)
    if not binary:
        data = data.replace(b"\r\n", b"\n")
    return hashlib.sha256(data).hexdigest()[:12]


# ---------------------------------------------------------------------------
# The inventory
# ---------------------------------------------------------------------------

def py_symbols(rel):
    """(kind, name) for every top-level def/class, method, module variable
    and `global` name in a Python module."""
    tree = ast.parse(read(rel), filename=rel)
    out = []

    def targets(node):
        if isinstance(node, ast.Name):
            yield node.id
        elif isinstance(node, (ast.Tuple, ast.List)):
            for e in node.elts:
                yield from targets(e)

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out.append(("function", node.name, node.lineno))
        elif isinstance(node, ast.ClassDef):
            out.append(("class", node.name, node.lineno))
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out.append(("method", "%s.%s" % (node.name, sub.name), sub.lineno))
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                for name in targets(t):
                    out.append(("variable", name, node.lineno))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            for name in targets(node.target):
                out.append(("variable", name, node.lineno))
    for node in ast.walk(tree):
        if isinstance(node, ast.Global):
            for name in node.names:
                out.append(("variable", name, node.lineno))
    seen = set()
    uniq = []
    for kind, name, line in out:            # first occurrence wins
        if (kind, name) not in seen:
            seen.add((kind, name))
            uniq.append((kind, name, line))
    return uniq


def commands():
    """The tpi: command words of SA_funct and EXT_SA_FUNCT, lower-case."""
    out = []
    for rel, table in COMMAND_TABLES:
        tree = ast.parse(read(rel), filename=rel)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Dict):
                continue
            if not any(isinstance(t, ast.Name) and t.id == table for t in node.targets):
                continue
            for key in node.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    out.append((rel, key.value.lower(), key.lineno))
    return out


LABEL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):")
EQU_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\s+equ\b", re.IGNORECASE)
SYM_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*):\s*equ\b", re.IGNORECASE)


def asm_symbols(rel):
    """Global labels and EQU names of an sjasmplus source (not .local ones)."""
    out = {}
    for n, line in enumerate(read(rel).splitlines(), 1):
        m = LABEL_RE.match(line) or EQU_RE.match(line)
        if m and m.group(1) not in out:
            out[m.group(1)] = n
    return list(out.items())


def curated_symbols():
    out = []
    for n, line in enumerate(read(ROM_SYMS).splitlines(), 1):
        m = SYM_RE.match(line)
        if m:
            out.append((m.group(1), n))
    return out


def inventory():
    """[(group, kind, name, line)] -- group is the source file."""
    inv = []
    for rel in FIRMWARE:
        for kind, name, line in py_symbols(rel):
            inv.append((rel, kind, name, line))
    for rel, word, line in commands():
        inv.append((rel, "command", word, line))
    for rel in ROM_ASM:
        for name, line in asm_symbols(rel):
            inv.append((rel, "label", name, line))
    for name, line in curated_symbols():
        inv.append((ROM_SYMS, "label", name, line))
    return inv


# ---------------------------------------------------------------------------
# The reference
# ---------------------------------------------------------------------------

HEADING_RE = re.compile(r"^#{2,6}\s+(.*)$")
ROW_RE = re.compile(r"^\|([^|]*)\|")
TICK_RE = re.compile(r"`([^`]+)`")
STAMP_ROW_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{12})`\s*\|")


def entry_name(token):
    """`RX_CAPTURE(MQ, raw)` -> RX_CAPTURE; `tpi:cd` -> tpi:cd."""
    token = token.strip()
    token = re.sub(r"\(.*\)$", "", token).strip()
    return token


def reference_files():
    out = []
    for dirpath, dirnames, filenames in os.walk(REF):
        if os.path.basename(dirpath) == "appendix":
            continue
        for fn in sorted(filenames):
            if not fn.endswith(".md"):
                continue
            rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
            if rel == os.path.relpath(README, ROOT):
                continue
            out.append(rel)
    return sorted(out)


def entries():
    """{name: [files documenting it, in order]}; names as written, plus lower-case."""
    found = {}
    in_code = False
    for rel in reference_files():
        for line in read(rel).splitlines():
            if line.startswith("```"):
                in_code = not in_code
                continue
            if in_code:
                continue
            m = HEADING_RE.match(line)
            cell = None
            if m:
                cell = m.group(1)
            else:
                r = ROW_RE.match(line)
                if r:
                    cell = r.group(1)
            if cell is None:
                continue
            for tok in TICK_RE.findall(cell):
                name = entry_name(tok)
                if name:
                    for k in (name, name.lower()):
                        if rel not in found.setdefault(k, []):
                            found[k].append(rel)
    return found


LINK_RE = re.compile(r"\]\(([^)#]+\.md)\)")
# Never tied to a source: the generated index, and the glossary.
UNSTAMPED_DOCS = ("docs/reference/appendix/index.md", "docs/reference/appendix/glossary.md")


def stamp_rows():
    """{source: (hash, line)} from README.md's table."""
    out = {}
    if not os.path.exists(README):
        return out
    for line in read(os.path.relpath(README, ROOT)).splitlines():
        m = STAMP_ROW_RE.match(line)
        if m:
            out[m.group(1).strip()] = (m.group(2), line)
    return out


def stamps():
    """{source: hash} from README.md's table."""
    return {rel: h for rel, (h, line) in stamp_rows().items()}


def row_docs(line):
    """The chapters, flows and appendices a stamp row names, relative to ROOT."""
    return [os.path.normpath(os.path.join("docs/reference", t)) for t in LINK_RE.findall(line)]


def cross_cutting_docs():
    """flows/*.md and appendix/*.md, which the stamp table must list."""
    out = []
    for sub in ("flows", "appendix"):
        d = os.path.join(REF, sub)
        if not os.path.isdir(d):
            continue
        for fn in sorted(os.listdir(d)):
            rel = os.path.relpath(os.path.join(d, fn), ROOT)
            if fn.endswith(".md") and rel not in UNSTAMPED_DOCS:
                out.append(rel)
    return out


# ---------------------------------------------------------------------------
# Line numbers in the prose (--relines)
#
# The chapters cite their source by line ("the comment at 4710-4728",
# "TS2068_IO's outer loop (6394)"). The index's numbers are regenerated, but
# these are prose: a change that adds lines above them leaves them pointing
# at the wrong code and fails nothing. --relines finds the version of a
# source its stamp was made against in git history (or --since REV), maps
# every old line to its new one (difflib), and lists each number in the
# row's chapters that would move. It cannot tell a line number from a value
# (128, a GPIO pin, another file's line), so it only proposes: check the
# list, then --apply writes it. Run it BEFORE re-stamping, while the stamp
# still names the old version.
# ---------------------------------------------------------------------------

# A line number in prose: 2-5 digits, not part of a word, a hex address
# (3000h, $3000, 0x3000), a decimal (4.4), a path, or a number with a unit
# ("6000 ms", "512 bytes"); "#L123" is a line link and is matched. Inline code
# (`WAIT_CORE1(3000, ...)`) is skipped whole: numbers there are values. So is
# a "(...)" that names another source ("(tspico_io 2399, 2417)", "tspico_io's
# SAVE paths (2747, 2890)"): those are its lines, not this one's.
LINE_REF_RE = re.compile(r"(?:(?<=#L)|(?<![\w.#/$\\`-]))(\d{2,5})"
                         r"(?![\w%`]|\.\d|\s?(?:ms|µs|s\b|bytes|KB|MHz|kHz|Hz|baud|columns|lines\b|bits))")
# Numbers that are values, not lines, whatever range they fall in (and the
# years this project has dates in).
NOT_LINES = {"1024", "1536", "2040", "2048", "2068", "4096", "6912", "8192", "15104", "16384", "32768", "65536",
             "2024", "2025", "2026", "2027"}


def git(*args):
    import subprocess
    r = subprocess.run(("git", "-C", ROOT) + args, capture_output=True)
    return r.stdout if r.returncode == 0 else None


def stamped_version(rel, want):
    """The text of rel at the newest commit whose content has stamp `want`."""
    for rev in (git("log", "--format=%H", "--", rel) or b"").decode().split():
        data = git("show", "%s:%s" % (rev, rel))
        if data is not None and hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()[:12] == want:
            return data.replace(b"\r\n", b"\n").decode("utf-8", "replace")
    return None


def line_map(old_text, new_text):
    """{old line: (new line, exact)} for every line that moved."""
    import difflib
    old, new = old_text.split("\n"), new_text.split("\n")
    out = {}
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, old, new, autojunk=False).get_opcodes():
        for k in range(i1, i2):
            if tag == "equal":
                n, exact = j1 + (k - i1), True
            else:                                   # changed or deleted: the start of what replaced it
                n, exact = min(j1 + (k - i1), max(j2 - 1, j1)), False
            if n != k or not exact:
                out[k + 1] = (n + 1, exact)
    return out


def other_sources(rel):
    """Stems of the other code sources: "(tspico_io 2399, 2417)" cites them."""
    stems = {os.path.splitext(os.path.basename(r))[0] for r in FIRMWARE + ROM_ASM}
    stems.discard(os.path.splitext(os.path.basename(rel))[0])
    return stems


def foreign_spans(line, others):
    """(start, end) of each "(...)" that cites another source's lines: one
    that starts with its name ("(tspico_io 2399"), or that follows it named
    as a file -- `tspico_io`'s, tspico_io.py -- within 40 characters. (A
    bare `native` is as likely a field as native.py.)"""
    spans = []
    for m in re.finditer(r"\(([^()]*)\)", line):
        head = m.group(1).split(" ", 1)[0].strip("`'")
        before = line[max(0, m.start() - 40):m.start()]
        if any(head in (o, o + ".py", o + ".asm") for o in others) or any(
                re.search(r"`%s`'s|\b%s\.(py|asm)\b" % (re.escape(o), re.escape(o)), before) for o in others):
            spans.append((m.start(), m.end()))
    return spans


def remap_lines(doc, moves, old_len, apply, others=()):
    """doc's line numbers through moves: [(line, old, new, exact, context)]; writes if apply."""
    text = read(doc)
    changes, out, in_code = [], [], False
    for no, line in enumerate(text.split("\n"), 1):
        if line.startswith("```"):
            in_code = not in_code
        if in_code or line.startswith("```"):
            out.append(line)
            continue

        def sub(m, base=0, spans=()):
            v = m.group(1)
            at = base + m.start()
            if (v in NOT_LINES or int(v) > old_len or int(v) not in moves
                    or any(a <= at < b for a, b in spans)):
                return m.group(0)
            new, exact = moves[int(v)]
            changes.append((no, v, str(new), exact, line.strip()[:110]))
            return str(new)
        spans = foreign_spans(line, others)
        parts, done, pos = line.split("`"), [], 0  # even parts are prose; odd ones are code spans
        for i, x in enumerate(parts):
            done.append(LINE_REF_RE.sub(lambda m, b=pos: sub(m, b, spans), x) if i % 2 == 0 else x)
            pos += len(x) + 1
        out.append("`".join(done))
    if apply and changes:
        with open(os.path.join(ROOT, doc), "w") as f:
            f.write("\n".join(out))
    return changes


def relines(sources, since=None, apply=False):
    """--relines: the line numbers in each source's chapters that moved."""
    rows = stamp_rows()
    total = 0
    for rel in sources:
        if rel not in rows:
            print("%s: no stamp row" % rel)
            return 1
        h, line = rows[rel]
        if since:
            old = git("show", "%s:%s" % (since, rel))
            old = old.replace(b"\r\n", b"\n").decode("utf-8", "replace") if old is not None else None
        else:
            old = stamped_version(rel, h)
        if old is None:
            print("%s: no version stamped %s in git history (give --since REV)" % (rel, h))
            return 1
        moves = line_map(old, read(rel))
        for doc in row_docs(line.split("|")[3]):         # the Chapter cell, not the flows
            for no, a, b, exact, ctx in remap_lines(doc, moves, old.count("\n") + 1, apply,
                                                    other_sources(rel)):
                total += 1
                print("%s:%d  %s -> %s%s  | %s" % (doc, no, a, b, "" if exact else "  (changed line)", ctx))
    print("\n%d number(s) %s" % (total, "moved" if apply else
          "would move. Check each is a line of that source, then --apply (or fix by hand)"))
    return 0


INDEX = os.path.join(REF, "appendix", "index.md")


def explained_in(files, chapters):
    """The entry the index links: one in the symbol's own chapters (the stamp
    table's Chapter cell for its source) if there is one, else the first.
    Names are not unique across sources -- src/main.py and the upgrade's
    main.py share their pin names, fddcmd.asm's BEEPER is not the EXROM's
    -- so the source decides, not the alphabet."""
    if not files:
        return None
    for f in files:
        if f in chapters:
            return f
    return files[0]


def index_text(inv, found):
    """appendix/index.md: every symbol, where it is, where it is explained."""
    lines = [
        "# Symbol index",
        "",
        "Every symbol the reference covers, in source order within each file: the",
        "line it is defined on today, and the chapter that explains it (one for its",
        "own source where there is one: names repeat across files). Generated by",
        "`python3 src/test/reference_hosttest.py --index`; do not edit by hand, and",
        "regenerate it when a line number moves (the test checks that it is current).",
        "",
    ]
    own = {src: row_docs(line.split("|")[3]) for src, (h, line) in stamp_rows().items()}
    last = None
    for rel, kind, name, line in inv:
        if rel != last:
            lines += ["", "## `%s`" % rel, "", "| Symbol | Kind | Line | Explained in |", "|---|---|---|---|"]
            last = rel
        key = name.lower() if kind == "command" else name
        where = explained_in(found.get(key), own.get(rel, ()))
        if where:
            doc = os.path.relpath(where, "docs/reference")
            where = "[%s](../%s)" % (doc, doc)
        else:
            where = "*(no entry)*"
        src = "[%d](../../../%s#L%d)" % (line, rel, line)
        lines.append("| `%s` | %s | %s | %s |" % (name, kind, src, where))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------

def main(argv):
    inv = inventory()

    if "--list" in argv:
        for rel, kind, name, line in inv:
            print("%-32s %-9s %-40s %d" % (rel, kind, name, line))
        print("\n%d symbols" % len(inv))
        return 0

    if "--index" in argv:
        with open(INDEX, "w") as f:
            f.write(index_text(inv, entries()))
        print("wrote %s" % os.path.relpath(INDEX, ROOT))
        return 0

    if "--relines" in argv:
        args = [x for x in argv[argv.index("--relines") + 1:] if x != "--apply"]
        since = None
        if "--since" in args:
            i = args.index("--since")
            since = args[i + 1]
            args = args[:i] + args[i + 2:]
        return relines(args, since, "--apply" in argv)

    if "--stamp" in argv:
        rows = stamp_rows()
        for rel in STAMPED:
            h = stamp(rel)
            if rel in rows:
                old, line = rows[rel]
                print(line.replace("`%s`" % old, "`%s`" % h, 1))
            else:
                print("| `%s` | `%s` | *(chapter)* | *(flows)* |" % (rel, h))
        return 0

    found = entries()
    missing = []
    for rel, kind, name, line in inv:
        key = name.lower() if kind == "command" else name
        if key not in found:
            missing.append((rel, kind, name))

    if "--missing" in argv:
        for rel, kind, name in missing:
            print("%-32s %-9s %s" % (rel, kind, name))
        print("\n%d of %d uncovered" % (len(missing), len(inv)))
        return 0 if not missing else 1

    fails = 0
    by_file = {}
    for rel, kind, name in missing:
        by_file.setdefault(rel, []).append(name)
    for rel in [r for r in dict.fromkeys(x[0] for x in inv)]:
        names = by_file.get(rel, [])
        total = sum(1 for x in inv if x[0] == rel)
        ok = not names
        print(("  PASS  " if ok else "  FAIL  ") + "%s: %d of %d symbols have an entry" %
              (rel, total - len(names), total))
        if not ok:
            fails += 1
            for n in names:
                print("          missing: %s" % n)

    rows = stamp_rows()
    have = stamps()
    for rel in STAMPED:
        want = stamp(rel)
        got = have.get(rel)
        if got == want:
            print("  PASS  stamp %s" % rel)
        elif got is None:
            fails += 1
            print("  FAIL  stamp %s: no row in docs/reference/README.md" % rel)
        else:
            fails += 1
            print("  FAIL  stamp %s: the file changed since the reference was checked "
                  "against it (stamped %s, now %s)" % (rel, got, want))
            for doc in row_docs(rows[rel][1]):
                print("          re-read: %s" % doc)
    extra = [r for r in have if r not in STAMPED]
    for rel in extra:
        fails += 1
        print("  FAIL  stamp %s: not a source this test knows (add it to STAMPED or drop the row)" % rel)

    listed = set()
    for h, line in rows.values():
        listed.update(row_docs(line))
    for doc in cross_cutting_docs():
        if doc in listed:
            print("  PASS  %s is listed against its sources" % doc)
        else:
            fails += 1
            print("  FAIL  %s: no stamp row lists it; add it to the \"Flows and appendices\" "
                  "cell of each source it follows" % doc)
    for doc in sorted(listed):
        if not os.path.exists(os.path.join(ROOT, doc)):
            fails += 1
            print("  FAIL  the stamp table links %s, which does not exist" % doc)

    want = index_text(inv, found)
    try:
        got = read(os.path.relpath(INDEX, ROOT))
    except OSError:
        got = None
    if got == want:
        print("  PASS  appendix/index.md is current")
    else:
        fails += 1
        print("  FAIL  appendix/index.md is out of date: python3 src/test/reference_hosttest.py --index")

    if fails:
        print("\n%d problem(s). Each uncovered symbol needs an entry in docs/reference/ "
              "(a heading or table row naming it in backticks). For a changed source, "
              "re-read the chapters, flows and appendices its row lists, fix what the change affects (first\n"
              "    python3 src/test/reference_hosttest.py --relines SOURCE\n"
              "lists the line numbers in its chapters the change moved), then paste its row from\n"
              "    python3 src/test/reference_hosttest.py --stamp\n"
              "into the stamp table in docs/reference/README.md." % fails)
        return 1
    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
