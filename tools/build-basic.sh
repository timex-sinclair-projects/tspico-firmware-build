#!/usr/bin/env bash
#
# Compile the tracked BASIC program sources under basic/ into .tap files
# using the vendored zmakebas (tools/zmakebas/).
#
# The .tap outputs are generated, NOT committed. Edit the .bas sources; never
# edit a .tap by hand. The generated TAPs flow into the release bundle and the
# web-updater payload from wherever they land in the delivery tree.
#
# Usage:
#   ./tools/build-basic.sh          # build everything
#   ./tools/build-basic.sh -v       # verbose (echo each zmakebas command)
#
# ── Where a program lands: directory convention ────────────────────────
# The first path component under basic/ selects the delivery target; the rest
# of the path is mirrored verbatim:
#
#   basic/SD/<rest>      ->  "SD card/<rest>"     (the SD card filesystem root)
#   basic/<rest>         ->  "src/<rest>"         (the Pico flash filesystem root)
#
# So, for example:
#
#   basic/SD/TAP/test/factorial.bas  ->  "SD card/TAP/test/factorial.tap"
#                                        (= /TAP/test/factorial.tap on the SD card)
#   basic/assets/nofile.bas          ->  "src/assets/nofile.tap"
#                                        (= /assets/nofile.tap on the Pico)
#
# `SD/` is the only special prefix (it maps to the "SD card" repo folder, which
# has a space in its name). Everything else maps under src/, the Pico-flash side.
#
# ── Per-program zmakebas options: the #! directive ─────────────────────
# zmakebas treats lines starting with '#' as comments, so an options directive
# at the top of a .bas is invisible to the tokenizer:
#
#   #! zmakebas -a 10 -n factorial
#
# The script always appends `-o <output> <input>`, so the directive carries
# only the extras (autostart line `-a`, the 10-char Spectrum filename `-n`,
# `-l` for labels, `-3` for ZX-Next, etc. — see tools/zmakebas/zmakebas.1).
# Default if absent: `-n <basename>`.
#
# ── Appending a pre-built tape block: the #! append directive ──────────
# zmakebas only emits BASIC programs, so a program that pulls in a machine-code
# block (`LOAD ""CODE 32600`) needs that CODE tape file laid down right after
# it on the tape. A second directive names one:
#
#   #! zmakebas -n romupdate -a 1
#   #! append romupdate_code.tap
#
# The path is relative to the .bas's own directory (the block is a tracked
# binary input, so it lives beside its source under basic/). Several `#! append`
# lines append in order, and in a multi-program tape each program carries its
# own — the directive belongs to whichever `#! zmakebas` block it follows.
#
set -euo pipefail

VERBOSE=0
[ "${1:-}" = "-v" ] && VERBOSE=1

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
SRC_DIR="$ROOT/basic"
ZMK_DIR="$HERE/zmakebas"
ZMK="$ZMK_DIR/zmakebas"

# ── Build the tokenizer (once) ─────────────────────────────────────────
# Build only the `zmakebas` target; the Makefile's default `all` also
# builds an AmigaGuide doc via `rman`, which we don't ship.
if [ ! -x "$ZMK" ] || [ "$ZMK_DIR/zmakebas.c" -nt "$ZMK" ]; then
  echo "==> Building zmakebas"
  make -C "$ZMK_DIR" zmakebas >/dev/null
fi

if [ ! -d "$SRC_DIR" ]; then
  echo "No basic/ directory at $SRC_DIR — nothing to build."
  exit 0
fi

# ── Emit one program to stdout ─────────────────────────────────────────
# Tokenize one source (or one segment of a multi-program source), then
# concatenate any tape blocks its `#! append` directives name.
#   $1 the .bas (or segment) to tokenize
#   $2 the directory relative `#! append` paths resolve against
#   $3 the `-n` name to fall back on when there's no options directive
emit_program() {
  local seg="$1" srcdir="$2" defname="$3"
  local opts blob

  # Options directive (first match wins). POSIX bracket class (not \s) so this
  # works on both BSD (local) and GNU (CI) sed.
  opts="$(sed -n 's/^#![[:space:]]*zmakebas[[:space:]]*//p' "$seg" | head -n1)"
  [ -z "$opts" ] && opts="-n $defname"
  [ "$VERBOSE" = 1 ] && echo "    $ZMK $opts -o - \"$seg\"" >&2
  # shellcheck disable=SC2086  # $opts is intentionally word-split
  eval "\"\$ZMK\" $opts -o - \"\$seg\""

  # `#! append <file>` — a pre-built tape block (a CODE header plus its data,
  # which zmakebas can't produce) concatenated after this program.
  while IFS= read -r blob; do
    blob="${blob%"${blob##*[![:space:]]}"}"       # strip trailing whitespace
    [ -z "$blob" ] && continue
    case "$blob" in /*) ;; *) blob="$srcdir/$blob" ;; esac
    if [ ! -f "$blob" ]; then
      echo "ERROR: $seg: '#! append' target not found: $blob" >&2
      exit 1
    fi
    [ "$VERBOSE" = 1 ] && echo "    append $blob" >&2
    cat "$blob"
  done < <(sed -n 's/^#![[:space:]]*append[[:space:]]*//p' "$seg")

  return 0
}

# ── Compile each .bas ──────────────────────────────────────────────────
# A source file normally holds ONE program -> one tape file. A file may also
# hold SEVERAL programs, each introduced by its own `#! zmakebas` directive;
# those are tokenized separately and concatenated, in source order, into one
# multi-program .tap. (A TAP is just a sequence of tape files, so a multi-program
# tape is the per-program tapes laid end to end.) See basic/README.md.
files=0
progs=0
# -print0 / read -d '' so paths with spaces (e.g. "RND WORDS.bas") survive.
while IFS= read -r -d '' bas; do
  rel="${bas#"$SRC_DIR"/}"            # e.g. SD/TAP/test/factorial.bas  or  assets/nofile.bas
  name="$(basename "${rel%.bas}")"

  # Map source path -> delivery path by its first component.
  if [ "${rel%%/*}" = "SD" ]; then
    dest="SD card/${rel#SD/}"         # SD card side
  else
    dest="src/$rel"                   # Pico flash side
  fi
  out="$ROOT/${dest%.bas}.tap"
  disp="${dest%.bas}.tap"
  mkdir -p "$(dirname "$out")"

  # How many `#! zmakebas` directives does this source carry? 0 or 1 -> a single
  # program; 2+ -> a multi-program tape. `|| true` so grep's "no match -> exit 1"
  # doesn't trip `set -e`.
  ndir="$(grep -cE '^#![[:space:]]*zmakebas' "$bas" || true)"

  if [ "${ndir:-0}" -ge 2 ]; then
    # ── Multi-program tape: split on each directive, tokenize, concatenate ──
    echo "==> basic/$rel -> $disp ($ndir programs)"
    tmp="$(mktemp -d)"
    # Each `#! zmakebas` line starts a new segment; awk keeps each segment file
    # open and appends to it, so 0001.bas, 0002.bas, ... come out in order. Lines
    # before the first directive (file-level comments) are dropped — zmakebas
    # would ignore them anyway.
    awk -v dir="$tmp" '
      /^#![[:space:]]*zmakebas/ { seg++ }
      seg>0 { print > (dir "/" sprintf("%04d", seg) ".bas") }
    ' "$bas"
    first=1
    for seg in "$tmp"/*.bas; do
      # Per-program options and `#! append` blocks ride on that program's own
      # segment; emit_program picks them up.
      if [ "$first" = 1 ]; then
        emit_program "$seg" "$(dirname "$bas")" "$name" > "$out"   # first: create
        first=0
      else
        emit_program "$seg" "$(dirname "$bas")" "$name" >> "$out"  # rest: append
      fi
      progs=$((progs + 1))
    done
    rm -rf "$tmp"
  else
    # ── Single program: one tape file from the whole source ──
    echo "==> basic/$rel -> $disp"
    emit_program "$bas" "$(dirname "$bas")" "$name" > "$out"
    progs=$((progs + 1))
  fi
  files=$((files + 1))
done < <(find "$SRC_DIR" -type f -name '*.bas' -print0 | sort -z)

echo "Built $progs BASIC program(s) into $files .tap file(s)."
