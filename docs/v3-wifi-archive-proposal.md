# v3: download 2068 programs from the archive over WiFi (proposal)

Status: proposal, 2026-11-06. Nothing built yet.

The idea: the v3 card's ESP32-C3 joins the home WiFi, reaches the
Timex/Sinclair software archive on archive.org, and the user picks a program
from the 2068 and saves its TAP to the SD card. Then they `LOAD` it as usual.

## What TSRun does (and doesn't)

[TSRun](https://github.com/josef-jelinek/TSRun) is a TS 2068 emulator that
runs in a web browser. It isn't device firmware: the browser supplies WiFi,
TLS and redirects. Its archive browser (`tsarchive.js`, about 210 lines) is
what's useful here. It shows the archive can be reached with three plain
HTTPS GETs and no unzip code. TSRun has no license file, so we reuse the
method, not the code.

| Step | URL | Notes |
|------|-----|-------|
| Index | `https://archive.org/metadata/timex-sinclair-software-archive/files` | 552 KB of JSON, 1,895 files, 1,791 original ZIPs (1,189 tagged `(TS2068)`). Chunked. |
| ZIP contents | `https://archive.org/download/<item>/<zip>/` (trailing slash) | 302 to `ia6xxxxx.us.archive.org/view_archive.php?archive=...`, an HTML table. Undocumented, scraped. |
| One TAP | `https://archive.org/download/<item>/<zip>/<member>` | 302 to the same `view_archive.php` with `&file=`. archive.org unzips the file itself. |

Each path segment is percent-encoded on its own (spaces and parentheses
too). archive.org won't unpack an encoded `/`. All three responses come back
chunked over HTTP/1.1, and two of them redirect.

## Where the code runs: three options

### A. A second ESP32 image (the original design idea)

The ESP32's partition table already has two 1.9 MB app slots
(`min_spiffs.csv`, `esp32/zimodem/platformio.ini`), so Zimodem could sit in
`ota_0` and an archive app in `ota_1`, with `otadata` choosing which one
boots.

- The switch has to come from the running image. We'd patch Zimodem to add
  an `AT` command that boots the other slot, and the archive app would need
  its own way back. Or the card could rewrite `otadata` through the ROM
  loader, the same way the updaters install Zimodem now.
- Zimodem's own update command, `AT&U`, writes the *other* OTA slot, which
  would wipe the archive app (that's how Arduino's `Update` works). The
  updaters would have to rewrite both slots every time.
- There'd be two WiFi setups, two images to build in CI, two to put through
  the web updater and the Windows exe, and the modem would be gone while the
  archive app runs.

### B. Zimodem fetches, the Pico does the rest (recommended)

Zimodem already has an HTTPS client. `AT&G"https://..."` streams a URL to
the serial line after a `[ channel length ]` header
(`zcommand.ino doWebStream`, `proto_http.ino doWebGetStream`). It follows
302s, uses TLS, keeps the WiFi credentials the modem already uses
(`ATW"ssid,pass"`, saved with `AT&W`), and paces its output with the flow
control we already set up (#303).

That puts all the archive logic in MicroPython on core 0, which already
owns the SD card, the `tpi:` commands and the 2068's messages:

1. **One ESP32 image, no switching.** The modem keeps working, and the
   updaters don't change.
2. **Fetch whole ZIPs and unzip on the Pico.** `AT&G` refuses any reply
   without a Content-Length (`proto_http.ino:470`), and archive.org's unzip
   service and metadata API always answer chunked. Plain files in the item,
   whole ZIPs included, come with a length. MicroPython's built-in `deflate`
   unzips them.
3. **New firmware:** a core-0 path to the ESP UART that sends an `AT` line
   and collects the response, with core 1's modem logic held off. That's the
   pattern `tsbus.esp_relay` already follows. Ours carries bytes to a buffer
   instead of to USB.

### Hardware spike, 2026-11-06 (board 1, Zimodem 4.0.3.1, home WiFi)

Run from the REPL with the firmware stopped, the Pico on UART0 directly.

| Fetch | Result |
|-------|--------|
| `AT&G"https://archive.org/robots.txt"` | OK: `[ 0 238 46 ]` header, then the body. TLS works. |
| A member through the unzip service (`.../x.zip/128 colors.tap`) | `ERROR` after about 3 s: the reply is chunked. |
| `AT&G"https://archive.org/metadata/<item>/files"` | `ERROR`: chunked. |
| Whole ZIP, 580 bytes | OK, byte-exact. Zimodem followed the 302 to `ia601601.us.archive.org`. |
| Whole ZIP, 35,676 bytes, default mode | OK, byte-exact, checksum `215` matches. About 13 s to the first byte: Zimodem saves the file to its own flash (110 KB free) before sending it. |
| The same, `ATS45=3` (stream, no checksum) | OK, byte-exact, about 5 s to the first byte and 2.4 s of data. No size limit. |
| Unzip on the Pico (`deflate.DeflateIO`, raw, 15-bit window) | 78,936-byte TAP in 975 ms. ZIP CRC and MD5 match archive.org's copy. |

**End to end, 2026-11-07 (same board):** a REPL prototype of `tpi:net get`
did the whole path. Zimodem fetched *Quetzalcoatl* (Virgin Games, 1984), a
14,719-byte ZIP, in stream mode into RAM in 6.7 s. The Pico inflated the TAP
inside it (38,198 bytes, CRC ok), and the TAP was copied to the SD card.
David ran `LOAD "tpi:quetzal.tap"` and `LOAD ""` on the 2068, and the game
runs.

The prototype wrote to the Pico's flash first because the SD card wouldn't
initialize (`card type v2`). It was stuck from before the test, the known
state after a replug or a hard reset, and reseating it fixed that. The
firmware will write straight to SD.

What we learned:

- **Stream mode (`ATS45=3`) is the one to use.** The ZIP's own CRC32 does
  the checking, and Zimodem's flash isn't a size limit.
- **The Pico mustn't write flash while receiving.** Writing each 4 KB to
  LittleFS as it came in lost 2.8 KB of the 35 KB ZIP: the line has no flow
  control here and the write stalls the loop. Collecting into RAM first
  worked. The firmware will need a RAM buffer (or XON/XOFF, #303) and a size
  cap. A soft reset leaves 164 KB free, but with the firmware stopped mid-run
  the heap was too fragmented for a 38 KB buffer, so the buffer has to be
  allocated early or in pieces (see #384).
- **The `AT` command line is at most 256 bytes** (`MAX_COMMAND_SIZE`), and
  TOSEC names are long. One QWIK 1040 member URL was 314 bytes. Whole-ZIP
  URLs are shorter (about 165), but the index should give each file a short
  URL anyway (see below).
- `example.com` gave `ERROR` over both http and https. We didn't look into
  why, and archive.org was unaffected.

### C. A custom ESP32 firmware that does both

This means adding an archive mode to Zimodem itself, so the ESP32 does the
fetch and the parsing and hands the Pico finished files. It needs more C++
on the ESP32 and gains nothing over B: the Pico has more RAM free than the C3
does once TLS is running, and it already writes the SD card.

## The index: publish our own

The metadata JSON (552 KB) is too big for either chip to hold, and the
listing page is an undocumented HTML scrape. But we own the
`timex-sinclair-software-archive` item (`tools/sd-archive/publish.py`
uploads to it). So we publish a small index next to the ZIPs.

Suggested format: a text file with one line per tape, holding the title,
year, publisher, the ZIP's name and size, the member path and its size, and
a "tested" mark. It covers every ZIP tagged `(TS2068)` (David's choice,
2026-11-07), not just the load-tested ones. The host tool that builds it
reads the member lists from the ZIPs in `~/tspico-archive-work`, or
downloads them, and takes the titles and categories from the SD card
catalog where a tape is on it. With names only, the list would be about
70 KB, which fits on the SD card and takes about 7 s to download. The device downloads
it once (and again on a refresh command) and searches it locally. That also
means:

- **No HTML parsing on the device.** The index names the ZIP and the member
  inside it.
- **It downloads through Zimodem.** A plain file in the item comes with a
  Content-Length, unlike the metadata API. The index should be one file of
  known size, small enough for RAM, or split by first letter.
- **Short URLs.** Under the 256-byte `AT` limit, `/download/<item>/<zip>`
  goes through archive.org's `ia6xxxxx` redirect. An index line could also
  carry the direct `ia` path, but those hosts move, so the redirect is
  safer.
- **What the device can't fetch is left out.** The index leaves out ZIPs
  with no `.tap`, `.tzx` or `.dck` inside (the WAV-only and image ZIPs),
  and ZIPs too big for the RAM buffer. The sizes are in the metadata, and
  the largest 2068 ZIPs are 260 MB WAV collections. A ZIP with several
  tapes gets one line per tape.
- **Untested is marked, not hidden.** The 1,328 tapes the SD-card pipeline
  load-tested carry the mark. The rest are listed too, so `tpi:net` can
  show which is which.
- **Categories and real titles** instead of TOSEC filenames.

TSRun's way of getting one TAP (archive.org's unzip service) is out for
Zimodem, because its replies are chunked. Fetching the whole ZIP and
inflating it on the Pico works (see the spike). Most 2068 ZIPs are a few
KB. The index should leave out the huge ones, such as the 260 MB WAV
collections.

## On the 2068

Lead with a keyword where we can, and fall back to a `tpi:` command where we
can't (the manual's rule). A first cut:

- `SAVE "tpi:wifi ssid,password"`: passes the credentials to Zimodem
  (`ATW`, `AT&W`). It only needs running once.
- `SAVE "tpi:net word"`: searches the index and prints numbered matches,
  like `tpi:dir` does.
- `SAVE "tpi:net get 12"`: downloads match 12 into `/TAP/NET/` under an 8.3
  name. If that name exists, the Y/N prompt asks before overwriting; the
  refusal comes first, as with `tpi:rm`. Then it mounts the tape, so `LOAD ""` runs it. That's the same two-step load
  as SD files.
- `SAVE "tpi:net update"`: downloads the index again.

A menu program, a BASIC TAP in `/assets`, could come later on top of the
same commands.

## Decisions (David, 2026-11-07)

1. **Zimodem fetches (option B).** No second ESP32 image.
2. **Every 2068 ZIP** in the item, tested or not, minus what the device
   can't fetch (see the index).
3. **Downloads go to `/TAP/NET/`.** An existing name is asked about first
   (Y/N), not overwritten silently.
4. **v3 only.** The v2 manual doesn't mention it.

## The index, built (2026-11-07)

`tools/sd-archive/net_index.py` builds it from the item's file list and the
ZIPs themselves. It downloaded the small ones the SD-card pipeline didn't
already have.

- **Coverage:** 1,217 ZIPs looked at (the 1,189 tagged `(TS2068)`, plus 28
  from the site's 2068 list without the tag). They yield **967 tapes from
  902 ZIPs.** By status: 337 L, 163 R, 32 X, 435 untested.
- **Left out:** 265 ZIPs over 32 KB, 37 ZIPs with no `.tap`, and 16 TZXs
  named `.tap`.
- **Size and URLs:** the index is 105 KB, and 27.9 KB gzipped. The longest
  `AT&G` line is 178 bytes, because only what HTTP needs is percent-encoded
  (archive.org accepts unencoded parentheses and commas).
- **Entries:** each line names the tape by its entry in the ZIP's central
  directory, not by its local header. Some ZIPs store sizes after the data
  (flag bit 3), so their local headers give no length.

On the card (board 1, bare REPL), the 27.9 KB `.gz` gunzipped to flash in
1.3 s. A search for "scramble" read all 967 lines in 0.26 s. Fetching
*Circuit Board Scramble* by its index line took 9.7 s, and its TAP came out
through the central directory with a good CRC (a flag-bit-3 ZIP). The tape
is now in `/TAP/NET/` on the card.

**The gap is the collections.** About 560 of the 1,328 load-tested tapes
are inside ZIPs over 32 KB: user-group library tapes (CATUG, ISTUG,
SINCUS…), most of them big because they also hold WAV recordings. Neither a
bigger RAM buffer nor Zimodem reaches them. Zimodem sends no `Range`
header, and archive.org's unzip service is chunked. The way to reach them
is to put the tapes themselves in the item, as plain `.tap` files (they'd
get a Content-Length), and point the index at those. That would publish
more copies of tapes already in the item and in the SD card ZIP, so it's
David's call.
David's direction (2026-11-07): a clean folder of plain TAP files plus an
index, as a project of its own,
[#401](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/401).

## Steps

1. **Hardware spike:** done, 2026-11-06 (above). B works with whole ZIPs.
2. **Index:** `tools/sd-archive/net_index.py` (built and tested on the card,
   2026-11-07). It goes into the item once David agrees; then fetch the
   published `.gz` with `AT&G` once, to check archive.org serves it with a
   length.
3. **Firmware:** the core-0 ESP transfer in `tsbus` (into RAM, `ATS45=3`),
   ZIP inflate to SD, and `tpi:wifi` and `tpi:net`. The same PR updates the
   reference chapters (`docs/reference/`).
4. **Manual:** a WiFi section in the v3 manual's modem chapter.
