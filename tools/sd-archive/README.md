# An SD card of the TS-2068 software archive

These scripts make a TS-Pico card out of the programs on timexsinclair.com's
TS-2068 software list. Each program page links a zip in the archive.org
collection. The scripts take the tapes out of the zips, give them short names
in category folders, and try every one on a TS-Pico in the emulator
(`tools/emu`). The card gets only the tapes that load and start. A catalog
says what each one is, how to load it, and why any tape was left out.

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
- For `publish.py` and `tap_folder.py --publish`: the `internetarchive` library
  and an account that can write the items (`ia configure`). If it came with
  `pipx install internetarchive`, the library is only in pipx's venv: run those
  two with that venv's Python, for example
  `"$(pipx environment --value PIPX_LOCAL_VENVS)/internetarchive/bin/python" publish.py …`.

## Run

```bash
cd tools/sd-archive
python3 fetch.py http://localhost/downloadable-software/downloadable-software-for-the-ts-2068/
python3 describe.py           # the site's descriptions, for the catalog
python3 plan.py
python3 loadtest.py           # ~45 min for ~1400 tapes, 12 workers
python3 followup.py           # ~15 min
python3 build_card.py ~/Desktop/sd-2068
python3 publish.py ~/Desktop/sd-2068    # to archive.org (--dry-run to check first)
python3 tap_folder.py ~/Desktop/sd-2068 ~/Desktop/taps-2068 --publish   # the WiFi folder (#401)
```

Every step reuses what's already done. The fetch keeps a zip it has already
downloaded only while it still matches archive.org (see `fetch.py` below). The
tests skip tapes that already have a result, so a stopped run picks up where it
left off. A tape from a zip that changed is a new tape to them, so it gets tested. To update the card when the list changes, run all
five steps again. Delete `results*.json` in the work folder to retest
everything, for example after a firmware change.

Then copy `OUTDIR/TAP` and `OUTDIR/help` to the card, or publish it. `OUTDIR-not-loading/`
holds the tapes that were left out, with the same catalog.

## What each step does

- **`fetch.py`** reads the list page and each program's page (cached in
  `detail/`), and downloads the zips four at a time. A program inside a
  collection has no link of its own, because the collection's zip brings it.
  - **Cached zips are checked.** Each zip in `zips/` (named
    `<10-hex>_<name>.zip`) is compared with the MD5 in its item's file list
    (`https://archive.org/metadata/ITEM/files`, the list `ia list -c name,md5`
    prints), and downloaded again when it differs. A new download must match
    that MD5 too. If a stale zip can't be downloaded again, it is deleted, so
    no card is built from it.
  - **Why:** archive.org replaces zips, for example to take personal data out.
    On 2026-11-07, 40 cached zips no longer matched, and the card published on
    2026-10-17 held the pre-fix copies of TAX84, Superfile and QED.
  - **Not checked:** a file served from inside another zip (the World of
    Spectrum mirror's) has no MD5 of its own. It is reused as it is, and the
    run says how many there were.
- **`describe.py`** reads every `computer_media` post from the same site's
  WordPress REST API (`/wp-json/wp/v2/computer_media`). The catalog's
  `summary` is the post's excerpt, and its `description` is the post's opening
  paragraph. A tape from a collection gets the collection's. Run it again after
  editing the site; `build_card.py` leaves both columns empty without it.
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
  tapes, and writes `catalog.csv`. It also adds the TS-Pico project's own tapes
  at the top of `TAP/`: `tour.tap` (the guided tour), `art.tap`, `multi.tap`,
  `hello.tap` and `library/alpha.tap` to `zulu.tap`, which the tour uses. They
  come from the repo's `SD card/TAP`, which `promo/demo/build.py` fills (see
  [`promo/demo/README.md`](../../promo/demo/README.md)). `tour.tap` gets a
  catalog row. The 2026-11-07 card was built without them, from a branch where
  `build_card.py` didn't add them yet, so they were copied in by hand.
  - **Left out:** `.DS_Store` and the Finder's duplicate copies (`help/cat 2.txt`,
    `alpha 2.tap`…) in `SD card/help` and `SD card/TAP`. `publish.py` skips them
    in the zip too.
- **`publish.py`** zips the card (`TAP/`, `help/`, `catalog.csv`) and uploads
  the zip and the catalog to the `timex-sinclair-software-archive` item on
  archive.org, beside the tapes they came from, replacing the old copies. The
  web updater links there. It needs `pip install internetarchive` and an
  account that can write the item (`ia configure`).
  - **No backups:** the upload sends `x-archive-keep-old-version: 0`, which is
    what `ia upload --no-backup` does. Without it, archive.org keeps each
    replaced card under `history/files/`, where it stays public, with any
    tapes later withdrawn for privacy.
  - **Checked:** after the upload it waits for the item's archive.org tasks to
    finish (up to 30 minutes), then stops with an error if any
    `history/files/TS-Pico SD Card*` is left. To check by hand:
    `ia list timex-sinclair-software-archive | grep history/`. To remove one:
    `ia delete timex-sinclair-software-archive --no-backup 'history/files/…'`.
  - **`--dry-run`** makes the zip, uploads nothing, and reports the old copies
    the item has now.
- **`tap_folder.py`** lays the card's archive tapes out as plain files for the
  v3 card's WiFi download (#401), at their card paths (`TAP/GAMES/name.tap`),
  with an `index.txt` in every folder for browsing, and one index of every tape,
  `tspico-taps.txt.gz`, for search. With `--publish` it uploads them to their
  own archive.org item, `tspico-2068-tapes`.
  - **Why plain files:** Zimodem's `AT&G` needs a reply with a Content-Length.
    A file in an item has one, and a tape inside a zip can't be fetched on its
    own (see `docs/v3-wifi-archive-proposal.md`).
  - **What goes in:** only the tapes on the card, so only those that load and
    start, with the pipeline's repairs. The tour and its demo tapes stay on the
    card. A tape over `--max-tap` (default 65536 bytes) is left out and listed.
  - **Folder indexes:** `TAP/index.txt` lists the groups. Each folder's index lists
    its subfolders (`name/ D title tapes`), then its tapes. It is split into
    8 KB parts (`index.txt`, `index2.txt`…) so a part always fits the card's
    32 KB download buffer; the header says `part 1 of 2`.
  - **The full index:** one line per tape, tab-separated: path, status (`L` `LOAD ""`,
    `R` then `RUN`, `C` `LOAD "" CODE`, `S` another way), title, year,
    publisher, size, and the `computer_media` post ID (from `describe.py`).
    A tape from a collection is titled `Collection: tape`.
  - **Rebuilds:** `--publish` compares each tape with the MD5 in the item's
    file list and uploads only what changed, then the index, all with
    `x-archive-keep-old-version: 0`, 50 at a time, waiting while the item has
    over 100 archive.org tasks queued (archive.org refuses uploads past a few
    hundred: "bucket_tasks_queued exceeds rationed amount"). Nothing replaced is kept under
    `history/`. A tape that has left the card is listed, not deleted.
    `--dry-run` reports and uploads nothing.

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

- **Workers:** each one is a ZEsarUX plus a pico_host, on free ports the OS
  picks (ZRCP and the bridge), so two runs can go at once in different work
  folders.
- **Underruns:** many sessions at once need `pico_host.py` from #151 or later.
  Before it, a firmware thread that fell behind left the 2068 reading 00h, and
  good tapes failed with Report R.
- **Reset:** between tapes the 2068 is reset with ZRCP `reset-cpu`.
  `hard-reset-cpu` doesn't reliably restart a program that's running.

## The index for downloads over WiFi

`net_index.py` writes the list a v3 card downloads to find tapes in the item
(see `docs/v3-wifi-archive-proposal.md`). It doesn't need the emulator, but it
does use `plan.json` and the `results*.json` files, if they're there, to mark
the tapes that were load-tested.

```bash
python3 net_index.py              # the item's file list, plus ZIPs not yet downloaded
python3 net_index.py --offline    # cached list and ZIPs only
python3 net_index.py --publish    # then upload tspico-net.txt(.gz) to the item
```

- **Which ZIPs:** every ZIP tagged `(TS2068)`, plus the ones the site's 2068
  list links (`plan.json`).
- **What's left out, and why:** the card can't download a ZIP bigger than
  `--max-zip` (32 KB, its RAM buffer). It can't use a ZIP with no `.tap`
  inside, a `.tap` that is really a TZX, or a URL too long for Zimodem's
  256-byte `AT` line. The script prints how many of each it left out.
- **Format:** one tab-separated line per tape, described at the top of the
  script. It gives the 8.3 name, the status (`L`, `R` or `C` tested and
  working, `X` tested and failing or damaged, `?` untested), the title, year
  and publisher, and the ZIP and the tape's entry in it.
- **The `.gz`:** the card downloads this copy, about 28 KB, and unzips it
  with MicroPython's `deflate`.
