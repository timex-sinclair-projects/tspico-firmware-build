# BASIC programs

This is where the **source** for the BASIC programs we ship lives — tracked,
diffable, reviewable. The `.tap` files that actually get delivered are
**generated** from these sources at build time by
[`zmakebas`](../tools/zmakebas/) and are **not** committed.

```
basic/**/*.bas   ──zmakebas──▶   <delivery>/**/*.tap   (gitignored)
```

Edit the `.bas`. Never edit a generated `.tap` by hand.

## Where a program lands: directory convention

The folder a `.bas` lives in under `basic/` determines where its `.tap` is
written. The **first** path component picks the delivery target; the rest of
the path is mirrored verbatim:

| Source under `basic/` | Built to (repo) | On the device |
|---|---|---|
| `basic/SD/<rest>` | `SD card/<rest>` | `/<rest>` on the **SD card** |
| `basic/<rest>`    | `src/<rest>`     | `/<rest>` on the **Pico** flash |

Examples:

```
basic/SD/TAP/test/factorial.bas  ->  SD card/TAP/test/factorial.tap   (SD: /TAP/test/factorial.tap)
basic/SD/readme.bas              ->  SD card/readme.tap               (SD: /readme.tap)
basic/assets/nofile.bas          ->  src/assets/nofile.tap            (Pico: /assets/nofile.tap)
```

`SD/` is the only special prefix — it maps to the repo's `SD card/` folder
(which has a space in its name, so we keep it out of `basic/`). Everything else
maps under `src/`, the Pico-flash side.

## Build

```sh
./tools/build-basic.sh        # build every program
./tools/build-basic.sh -v     # verbose: show each zmakebas invocation
```

This builds the vendored `zmakebas` if needed, then compiles each
`basic/**/*.bas` to its mapped destination (see the convention above).

CI runs this automatically:

- **build.yml** builds the programs on every push/PR as a smoke test — a `.bas`
  that won't tokenize fails the build.
- **release.yml** and **pages.yml** build them before assembling the release
  bundle and the web-updater payload, so the generated `.tap`s ride along inside
  `src/assets/` and `SD card/TAP/` without being in git.

## Adding a program

1. Drop `yourprog.bas` in the folder that maps to its destination (see the
   convention above) — e.g. `basic/assets/` for a Pico-flash asset, or
   `basic/SD/TAP/test/` for an SD-card test program.
2. Put a build directive on the first line so the tokenizer gets the right
   options:

   ```
   #! zmakebas -a 10 -n yourprog
   ```

   The script always appends `-o <output> <input>`; the directive carries the
   extras. Common options (full list in [`zmakebas.1`](../tools/zmakebas/zmakebas.1)):

   | Option | Meaning |
   |---|---|
   | `-a <line>` | Auto-start: program RUNs from this line on LOAD. |
   | `-n <name>` | The ≤10-char filename stored in the TAP header. Defaults to the source basename. |
   | `-l`        | Enable labels (`@label` line refs instead of hard line numbers). |
   | `-i <n>`    | Line-number increment when using `-l`. |
   | `-3`        | ZX-Next / `.3dos` dialect. |

   With no directive, the default is `-n <basename>`.
3. Build, and the `.tap` appears at the destination its folder maps to.

## Programs with a CODE block: the `#! append` directive

zmakebas only emits BASIC programs. A program that pulls in a machine-code
block — `romupdate.bas` does `LOAD ""CODE 32600` — needs that CODE tape file
sitting right behind it on the tape. Name it with a second directive:

```
#! zmakebas -n romupdate -a 1
#! append romupdate_code.tap
```

The build tokenizes the program, then concatenates the named file onto the
`.tap`. The path is relative to the `.bas`'s own directory, so the block lives
beside its source — it's a **tracked binary input**, not a build output:

```
basic/assets/romupdate.bas         <- source (tracked)
basic/assets/romupdate_code.tap    <- CODE block (tracked binary input)
        │
        └──build──▶  src/assets/romupdate.tap   (generated, gitignored)
```

Several `#! append` lines append in order. In a multi-program tape each
program carries its own — a directive belongs to whichever `#! zmakebas` block
it follows. A missing target fails the build rather than emitting a short TAP.

Assembling those CODE blocks is out of scope for this pipeline; they're
hand-built artifacts checked in as-is.

## Multiple programs in one TAP (multi-program tapes)

A `.tap` is just a sequence of tape files laid end to end, so one delivery TAP
can hold **several** BASIC programs in a fixed order (e.g. an autostarting menu
followed by the programs it loads — the way `nofile.tap` is built).

To author one, put **more than one** `#! zmakebas` directive in a single source
file. Each directive starts a new program; the lines below it (up to the next
directive or end of file) are that program's listing. The build tokenizes each
program separately and concatenates them — **in top-to-bottom source order** —
into the one `.tap` the file maps to. Per-program options ride on each program's
own directive, exactly as for a single program.

```
#! zmakebas -n loader -a 10        <- program 1: "loader", autostarts at line 10
10 print "menu..."
...

#! zmakebas -n data1               <- program 2: "data1", no autostart
10 rem ...

#! zmakebas -n data2               <- program 3: "data2", no autostart
10 rem ...
```

The file's path maps to its destination exactly as usual — nothing special; a
multi-program source is still one `.bas` → one `.tap`. The only difference is
that the `.tap` now contains three tape files instead of one. A source with a
single directive (the common case) is unchanged. See
[`SD/TAP/demo/multi.bas`](SD/TAP/demo/multi.bas) for a working example.

Notes:
- The sequence is literally the order the directives appear — reorder the
  blocks to reorder the tape.
- Lines before the *first* directive are file-level comments (dropped); give
  each actual program its own `#! zmakebas` line.
- This is build-time concatenation only. zmakebas remains one-way, so a TAP that
  was authored elsewhere as multiple files still needs each program's source
  recovered before it can be migrated here.

## Source format (zmakebas)

Plain text, one BASIC line per line, real line numbers (or `@labels` with `-l`).
Lines starting with `#` are comments. Tokens are spelled out in lower case
(`print`, `goto`, `rem`, …). Non-ASCII Spectrum characters and control codes use
backslash escapes — e.g. `\a`..`\u` for UDGs, block graphics, colour controls.
See [`tools/zmakebas/zmakebas.1`](../tools/zmakebas/zmakebas.1) for the full
escape table, and [`SD/TAP/demo/hello.bas`](SD/TAP/demo/hello.bas) for a minimal
working example.

## Migrating existing committed TAPs

Every BASIC program the firmware and the SD card image need is now built from
source here: `src/assets/` (`nofile`, `romupdate`, `dckupdate`, and the v3
card's `romupd3`, `dckupd3`, which have no CODE block: the Pico writes the
slot itself) and the test
programs, the last two of which (`factorial`, `RND WORDS`) were rewritten for
the fixed `tpi:.fact` / `tpi:.rndw` examples. (`rompatch.tap`, a v1.2-era ROM
patch, was retired with `tpi:rompatch`.) zmakebas is **one-way** -- it can't
recover source from a `.tap` -- so if another committed binary turns up, keep
it until its source is added.

To migrate one:

1. Add the `.bas` at the path that maps to its `.tap`, with a `#! zmakebas` directive for
   its options (autostart line, `-n` name, etc.).
2. Build and confirm the generated `.tap` loads correctly — compare against the
   old committed one before deleting it.
3. Stop tracking the binary and let the build own it:

   ```sh
   git rm --cached "SD card/TAP/test/factorial.tap"        # untrack, keep on disk
   echo "/SD card/TAP/test/factorial.tap" >> .gitignore    # ignore the now-generated file
   ```

Until a program is migrated this way, leave its committed `.tap` in place — the
firmware build needs it.
