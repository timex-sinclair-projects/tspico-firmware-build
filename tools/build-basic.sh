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

# ── Compile each .bas ──────────────────────────────────────────────────
count=0
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

  # Options directive (first match wins). POSIX bracket class (not \s) so this
  # works on both BSD (local) and GNU (CI) sed.
  opts="$(sed -n 's/^#![[:space:]]*zmakebas[[:space:]]*//p' "$bas" | head -n1)"
  [ -z "$opts" ] && opts="-n $name"

  mkdir -p "$(dirname "$out")"
  if [ "$VERBOSE" = 1 ]; then
    echo "==> $ZMK $opts -o \"$out\" \"$bas\""
  else
    echo "==> basic/$rel -> $disp"
  fi
  # shellcheck disable=SC2086  # $opts is intentionally word-split
  eval "\"\$ZMK\" $opts -o \"\$out\" \"\$bas\""
  count=$((count + 1))
done < <(find "$SRC_DIR" -type f -name '*.bas' -print0 | sort -z)

echo "Built $count BASIC program(s)."
