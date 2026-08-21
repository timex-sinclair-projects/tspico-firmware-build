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
basic/SD/picotest.bas            ->  SD card/picotest.tap             (SD: /picotest.tap)
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

## Multiple programs in one TAP (multi-program tapes)

A `.tap` is just a sequence of tape files laid end to end, so one delivery TAP
can hold **several** BASIC programs in a fixed order (e.g. an autostarting menu
followed by the programs it loads — the way Ryan's `picotest.tap` is built).

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

Several BASIC programs predate this pipeline and are still committed as binary
`.tap` files. zmakebas is **one-way** — it can't recover source from a `.tap` —
so each stays committed until its original `.bas` source is added here.

Add each program's source at the path the convention maps to its committed TAP:

| Add source at | Builds to (the committed TAP it replaces) |
|---|---|
| `basic/assets/nofile.bas`          | `src/assets/nofile.tap`        |
| `basic/assets/rompatch.bas`        | `src/assets/rompatch.tap`      |
| `basic/assets/romupdate.bas`       | `src/assets/romupdate.tap`     |
| `basic/assets/dckupdate.bas`       | `src/assets/dckupdate.tap`     |
| `basic/SD/TAP/test/factorial.bas`  | `SD card/TAP/test/factorial.tap` |
| `basic/SD/TAP/test/RND WORDS.bas`  | `SD card/TAP/test/RND WORDS.tap` |
| `basic/SD/TAP/picotest.bas`        | `SD card/TAP/picotest.tap` — **multi-program** (14 tape files: `tspicotest` autostarting at line 1, then `test1`…`test12`); author as one source with a `#! zmakebas` directive per program (see [Multiple programs in one TAP](#multiple-programs-in-one-tap-multi-program-tapes)) |

To migrate one (do this **per program**, as its source lands):

1. Add the `.bas` at the mapped path above, with a `#! zmakebas` directive for
   its options (autostart line, `-n` name, etc.).
2. Build and confirm the generated `.tap` loads correctly — compare against the
   old committed one before deleting it.
3. Stop tracking the binary and let the build own it:

   ```sh
   git rm --cached "src/assets/nofile.tap"        # untrack, keep on disk
   echo "/src/assets/nofile.tap" >> .gitignore    # ignore the now-generated file
   ```

   Once **all four** `src/assets/*.tap` are BASIC-generated, a single
   `/src/assets/*.tap` line can replace those four per-file entries.

Until a program is migrated this way, leave its committed `.tap` in place — the
firmware build needs it.
