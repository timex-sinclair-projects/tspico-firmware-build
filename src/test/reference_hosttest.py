"""docs/reference/ -- the programmer's reference -- must cover the code it describes.

The reference (docs/reference/README.md) explains every top-level function,
class, method and module variable of the firmware, every tpi: command, and
every label of the ROM sources. This test fails CI when:

  1. a symbol in the code has no entry in the reference (COVERAGE), or
  2. a source file changed since the reference was last checked against it
     (STAMPS: the table in docs/reference/README.md records a hash of each
     source; re-read the matching chapter, fix what changed, then re-stamp).

What counts as an entry: a Markdown heading (## or deeper) or the first cell
of a table row, anywhere under docs/reference/ except README.md and
appendix/, holding the symbol's name in backticks: `ACTIVATE_MQ()`,
`PICO_STATUS.__init__`, `files`, `tpi:cd`, `WAIT_PICO_READY`. A trailing
"(...)" is ignored, so `RX_CAPTURE(MQ, raw, n, stall_ms, ready=None)` names
RX_CAPTURE. Command names compare case-insensitively.

Run:  python3 src/test/reference_hosttest.py            # check (CI)
      python3 src/test/reference_hosttest.py --missing  # only what is uncovered
      python3 src/test/reference_hosttest.py --list     # the whole inventory
      python3 src/test/reference_hosttest.py --stamp    # fresh rows for the stamp table
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
    "src/rom/TSPICO-21.ROM",
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
    """{name: first file documenting it}; names as written, plus lower-case."""
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
                    found.setdefault(name, rel)
                    found.setdefault(name.lower(), rel)
    return found


def stamps():
    """{source: hash} from README.md's table."""
    out = {}
    if not os.path.exists(README):
        return out
    for line in read(os.path.relpath(README, ROOT)).splitlines():
        m = STAMP_ROW_RE.match(line)
        if m:
            out[m.group(1).strip()] = m.group(2)
    return out


INDEX = os.path.join(REF, "appendix", "index.md")


def index_text(inv, found):
    """appendix/index.md: every symbol, where it is, where it is explained."""
    lines = [
        "# Symbol index",
        "",
        "Every symbol the reference covers, in source order within each file: the",
        "line it is defined on today, and the chapter that explains it. Generated by",
        "`python3 src/test/reference_hosttest.py --index`; do not edit by hand, and",
        "regenerate it when a line number moves (the test checks that it is current).",
        "",
    ]
    last = None
    for rel, kind, name, line in inv:
        if rel != last:
            lines += ["", "## `%s`" % rel, "", "| Symbol | Kind | Line | Explained in |", "|---|---|---|---|"]
            last = rel
        key = name.lower() if kind == "command" else name
        where = found.get(key)
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

    if "--stamp" in argv:
        for rel in STAMPED:
            print("| `%s` | `%s` |" % (rel, stamp(rel)))
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
    extra = [r for r in have if r not in STAMPED]
    for rel in extra:
        fails += 1
        print("  FAIL  stamp %s: not a source this test knows (add it to STAMPED or drop the row)" % rel)

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
              "re-read its chapter, fix what the change affects, then paste the row from\n"
              "    python3 src/test/reference_hosttest.py --stamp\n"
              "into the stamp table in docs/reference/README.md." % fails)
        return 1
    print("\nALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
