# v3: download 2068 programs from the archive over WiFi (proposal)

Status: proposal, 2026-11-06; revised 2026-11-08 for the plain-TAP folder
(#401). No firmware yet.

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
2. **Fetch plain files.** `AT&G` refuses any reply without a
   Content-Length (`proto_http.ino:470`), and archive.org's unzip service
   and metadata API always answer chunked. Plain files in an item come with
   a length. The tapes are now plain `.tap` files in their own item (see
   "The folder" below), so the Pico saves what it receives and unzips
   nothing. Whole ZIPs work too (the spike unzipped them with MicroPython's
   built-in `deflate`), but the folder made that unnecessary.
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
  URLs are shorter (about 165). The folder's tape paths are 34 characters
  at most (see "The folder").
- `example.com` gave `ERROR` over both http and https. We didn't look into
  why, and archive.org was unaffected.

### C. A custom ESP32 firmware that does both

This means adding an archive mode to Zimodem itself, so the ESP32 does the
fetch and the parsing and hands the Pico finished files. It needs more C++
on the ESP32 and gains nothing over B: the Pico has more RAM free than the C3
does once TLS is running, and it already writes the SD card.

## The folder: `tspico-2068-tapes` (#401)

The metadata JSON (552 KB) is too big for either chip to hold, and the
ZIPs hide most of the tested tapes: about 560 of them sit in collection ZIPs
over 32 KB, many of them big only because they also hold WAV recordings.
Zimodem sends no `Range` header and archive.org's unzip service is chunked,
so nothing on the card reaches a tape inside a big ZIP.

So the tapes themselves went up as plain files, in an item of their own:
[`tspico-2068-tapes`](https://archive.org/details/tspico-2068-tapes)
("TS-Pico WiFi tapes: TS-2068 programs as plain TAP files"), published
2026-11-07 by `tools/sd-archive/tap_folder.py` (#402, #403). The script's
docstring is the format's definition; in short:

- **The tapes:** 2,300, the SD card's archive tapes, at their card paths
  (`TAP/GAMES/name.tap`, `TAP/COLLECT/<collection>/name.tap`), with the
  pipeline's repairs and conversions. Every one loads and starts:
  1,353 `LOAD ""`, 484 `LOAD ""` then `RUN`, 444 `LOAD "" CODE`, 19 another
  way. 34 tapes over 64 KB (`--max-tap 65536`) were left out.
- **Browsing:** every folder has an `index.txt`: a `#tspico-dir` header,
  then its subfolders (`name/ D title tapes`) and its tapes
  (`name.tap status title year publisher size post`), tab-separated.
  A folder's index is split into parts of at most 8 KB (`index2.txt`...),
  97 parts in 94 folders. Browsing starts at `TAP/index.txt` (339 bytes,
  ten categories).
- **Search:** `tspico-taps.txt.gz`, one line per tape with its full path,
  221 KB, 46 KB gzipped.
- **URLs:** `https://archive.org/download/tspico-2068-tapes/TAP/...`. The
  longest tape path is 34 characters, so every `AT&G` line is far under
  Zimodem's 256-byte limit, and nothing needs percent-encoding.
- **Content-Length:** checked from the host 2026-11-08. The top index, a
  tape and the `.gz` each come back 302 to `ia600909.us.archive.org`, then
  200 with a `content-length`.

What this means for the card:

- **No unzip and no central-directory walk.** A download is one `AT&G`
  and a file write.
- **The buffer has to be 64 KB, or the card skips the big tapes.** 127
  tapes are over 32 KB (the largest is 63,635 bytes), and the bytes still
  arrive with no flow control, so a tape has to fit in RAM before it's
  written. board_v3's 32 KB slot buffer isn't enough; the 48 KB boot
  `BLOCK_BUF` (#392) isn't either. Either the firmware takes a 64 KB
  buffer while the heap is clean, or `tpi:net` refuses tapes over what it
  has and says so (the size is in the index line, so it can refuse before
  asking for it).
- **The full index needs the same buffer.** At 46 KB gzipped it doesn't
  fit in 32 KB. Browsing doesn't need it: every folder index part fits
  in 8 KB.

The ZIP index this proposal first built (`net_index.py`, 2026-11-07) is
retired: it reached 967 tapes, a third of them untested, against the
folder's 2,300 tested ones. Its findings are kept under "The ZIP index"
below.

## On the 2068

Lead with a keyword where we can, and fall back to a `tpi:` command where we
can't (the manual's rule). A first cut:

- `SAVE "tpi:wifi ssid,password"`: passes the credentials to Zimodem
  (`ATW`, `AT&W`). It only needs running once.
- `SAVE "tpi:net"`: lists `TAP/index.txt`, the categories, numbered, like
  `tpi:dir` does. `SAVE "tpi:net 5"` opens entry 5: a folder lists its own
  index (each 8 KB part in turn), a tape downloads.
- `SAVE "tpi:net find word"`: searches the full index (downloaded once to
  the SD card) and prints numbered matches.
- A tape downloads into `/TAP/NET/` under its 8.3 name. If that name
  exists, the Y/N prompt asks before overwriting; the refusal comes first,
  as with `tpi:rm`. Then it mounts the tape, so `LOAD ""` runs it, the same
  two-step load as SD files. The index line's status says which `LOAD` to
  use.
- `SAVE "tpi:net update"`: downloads the full index again.

A menu program, a BASIC TAP in `/assets`, could come later on top of the
same commands.

## Decisions (David, 2026-11-07)

1. **Zimodem fetches (option B).** No second ESP32 image.
2. **Every 2068 ZIP** in the item, tested or not, minus what the device
   can't fetch. *Superseded* by David's direction for #401: the card fetches
   from the plain-TAP folder, which holds the load-tested tapes only.
3. **Downloads go to `/TAP/NET/`.** An existing name is asked about first
   (Y/N), not overwritten silently.
4. **v3 only.** The v2 manual doesn't mention it.

## The ZIP index (2026-11-07, retired)

`tools/sd-archive/net_index.py` built it from the item's file list and the
ZIPs themselves. It was never published, and it was removed when the folder
replaced it; it's in this PR's history (commit 89ded57). It downloaded the small ones the SD-card pipeline didn't
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

That's what showed the gap the folder closes: about 560 tested tapes in
collection ZIPs over 32 KB.

## Steps

1. **Hardware spike:** done, 2026-11-06 (above).
2. **The folder:** published 2026-11-07 (#402, #403). Left: a v3 card
   downloads from it byte-exact (#401's last box).
3. **Firmware:** the core-0 ESP transfer in `tsbus` (into a RAM buffer,
   `ATS45=3`, 64 KB or a stated limit), the write to SD, and `tpi:wifi`
   and `tpi:net`. The same PR updates the reference chapters
   (`docs/reference/`).
4. **Manual:** a WiFi section in the v3 manual's modem chapter.
