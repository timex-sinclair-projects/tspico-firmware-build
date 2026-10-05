# An SD card of the TS-2068 software archive

These scripts make a TS-Pico card out of the programs on timexsinclair.com's
TS-2068 software list. Each program page links a zip in the archive.org
collection. The scripts take the tapes out of the zips, give them short names
in category folders, and try every one on a TS-Pico in the emulator
(`tools/emu`). The card gets only the tapes that load and start. A catalog
says how to load each one, and why any tape was left out.

```
fetch.py PAGE ─▶ plan.py ─▶ loadtest.py ─▶ followup.py ─▶ build_card.py OUTDIR
 pages, zips      tapes,      LOAD "" on      CODE / RUN /     the card +
                  names       the TS-Pico     TZX / stock      catalog.csv
```

## Needs

- ZEsarUX from the `zesarux-tspico` fork, as `$ZESARUX`. See
  [`tools/emu/README.md`](../emu/README.md). The stock-2068 check uses ZEsarUX's
  own `ts2068.rom`, which it looks for in `/Applications/zesarux.app`, then in the
  lab clone. Set `$TS2068_ROM` to use another copy.
- Python 3.10 or later, with `tzxtools` (`pip install tzxtools`) for `tzxtap`
  and `tzxwav`.
- About 5 GB in the work folder, `$TSPICO_ARCHIVE_WORK` (default
  `~/tspico-archive-work`). The zips go there, plus everything the scripts
  make. None of it goes in the repo.

## Run

```bash
cd tools/sd-archive
python3 fetch.py http://localhost/downloadable-software/downloadable-software-for-the-ts-2068/
python3 plan.py
python3 loadtest.py           # ~45 min for ~1400 tapes, 12 workers
python3 followup.py           # ~15 min
python3 build_card.py ~/Desktop/sd-2068
```

Every step reuses what's already done. The fetch keeps zips it has already
downloaded. The tests skip tapes that already have a result, so a stopped run
picks up where it left off. To update the card when the list changes, run all
five steps again. Delete `results*.json` in the work folder to retest
everything, for example after a firmware change.

Then copy `OUTDIR/TAP` and `OUTDIR/help` to the card. `OUTDIR-not-loading/`
holds the tapes that were left out, with the same catalog.

## What each step does

- **`fetch.py`** reads the list page and each program's page (cached in
  `detail/`), and downloads the zips four at a time. A program inside a
  collection has no link of its own, because the collection's zip brings it.
- **`plan.py`** takes each zip's `.tap` files, or converts its `.tzx` or `.wav`
  when there's no `.tap`. It also converts a `.tap` that is really a TZX, and
  drops zero padding after the last block. It removes identical tapes. It
  leaves out `dirinfo.tap`, because the firmware writes its own, and LarKen
  `lkdos/` fragments when the zip has the whole tape too.
  - **Folder:** the program's tags decide its folder (`ARCADE`, `GAMES`,
    `HOME`…). A zip with three or more tapes gets a subfolder (`COLLECT/CATS8`,
    `BPOWER5`…).
  - **Name:** the title, cut to 8 characters (`capimast.tap`).
- **`loadtest.py`** runs each tape: `LOAD "tpi:name"`, then `LOAD ""`. It reads
  the firmware's telemetry for each block served, and presses ENTER or SPACE
  at "press a key" prompts. It records the report, the screen, and a screenshot
  in `emu/shots/`.
- **`followup.py`** takes a second look:
  - Tapes with no BASIC program are tried with `LOAD "" CODE`.
  - Damaged tapes are retried from the same file's TZX or WAV in the zip.
  - Programs that stop with a report are tried again with RUN.
  - Everything still failing is loaded on a stock 2068 (ZRCP `smartload`). If
    the stock 2068 fails the same way, the tape is at fault, not the TS-Pico.
- **`build_card.py`** decides each tape's verdict (`verdict()`), copies the
  tapes, and writes `catalog.csv`.

## Verdicts

`common.classify()` sorts each `LOAD ""` result:

| Result | Meaning | On the card? |
| --- | --- | --- |
| OK | every block loaded | yes |
| PARTIAL | running, and the rest of the tape loads when the program asks for it (a menu, the next part) | yes |
| LOADED-ERR | stopped with a report (`2 Variable not found`…) | only if RUN starts it |
| LOOP | the program loaded, then kept asking for a file the tape doesn't have | no |
| R-TAPE, T-RESET | damaged tape (Report R; the firmware says T for some damage) | no |

Tapes with any block that has a bad checksum or is cut short stay off the
card, even when the first part loads.

## The emulator, in parallel

- **Workers:** each one is a ZEsarUX plus a pico_host. ZRCP uses port
  10100+k, the bridge 20700+k, and the stock 2068s 10300+k.
- **`fast_host.py`:** this is `tools/emu/pico_host.py` with its bus model
  patched. When several sessions share the CPU, the firmware thread falls
  behind, and the 2068 reads 00h from an empty queue. Good tapes then fail with
  Report R. With the patch, an `IN (0Eh)` waits up to 50 ms for its byte, and
  the firmware's idle poll sleeps instead of spinning a core.
- **Reset:** between tapes the 2068 is reset with ZRCP `reset-cpu`.
  `hard-reset-cpu` doesn't reliably restart a program that's running.
