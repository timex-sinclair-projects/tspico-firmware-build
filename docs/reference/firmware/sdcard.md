# src/TS/sdcard.py — the SPI SD driver and its recovery

Source: [`src/TS/sdcard.py`](../../../src/TS/sdcard.py). Part of the
[programmer's reference](../README.md).

The driver talks to the micro SD card over SPI and presents it to
MicroPython as a block device. `ACTIVATE_SD` ([tspico-bus.md](tspico-bus.md))
and `ENA_SD` ([tspico_io.md](tspico_io.md)) build an `SDCard` and hand it to
`os.mount(sd, "/sd")`; from then on the C-level FAT filesystem calls
`readblocks`, `writeblocks` and `ioctl`, and nothing else in the firmware
calls the driver except its constructor and, in `ACTIVATE_SD`, the two
attributes `recovered` and `CID`. The header names the origin, the mendenm
fork of MicroPython's `sdcard.py`, and lists the TS-Pico changes: CMD0
retries (#61), `_recover()` for a card left mid-transfer (#66), bounded busy
waits (#66), and the CID kept as the card's identity (#101, #107). The
header does not list the fifth change, the 100 ms read-token wait (#131).

The card's SPI lines are GPIO 2 (SCK), GPIO 3 (MOSI) and GPIO 4 (MISO),
the pins that are D0–D2 of the 2068 data bus through U6; chip select is
GPIO 28 (`U3_CS`, `Pin.PULL_UP`). `ACTIVATE_SD` builds the bus through the
board layer ([board.md](board.md)), on v2 as
`SPI(0, sck=Pin(2), mosi=Pin(3), miso=Pin(4))`, and holds U6 off (GPIO 12
high) first, so the card is only ever used while the bus state machine is
parked ([flows/sd-handover.md](../flows/sd-handover.md)); `DEACTIVATE_SD`
drives GPIO 2–4 low and CS high afterwards ([tspico-bus.md](tspico-bus.md)).
The card module runs off the Pico's 3V3 rail with a 4K7 pull-up on nCS
([DEVELOPER_GUIDE.md §3](../../DEVELOPER_GUIDE.md), from the schematic), so a
Pico reset, a UF2 flash or a Ctrl-C never power-cycles it: that is what
`_recover` is for, and why `ACTIVATE_SD` budgets its attempts with
`SD_TRY_MS`.

What the driver does and does not do: SPI mode 0 at 100 kHz for the
start-up sequence and 5 MHz afterwards (the `baudrate` default; both callers
pass none; the 5 MHz clock was kept by the 2026-09-30 audit, §5); a CRC-7 on
every command frame, computed by `crc7`; no CRC-16 on data, because both
callers leave `crc16_function` at `None`, so `check_crcs` sends CMD59 with
0, the two CRC bytes after each read are discarded and 0xFFFF is sent after
each write. Every read is a CMD18 and every write a CMD25, also for a single
block; CMD17, CMD24 and CMD58 are never sent.

## Map

| Lines | What |
|---|---|
| 1–29 | the header: origin, the TS-Pico changes, the `crc_function` note |
| 31–33 | imports: `const`, `time`, and `ETIMEDOUT` (110), `EIO` (5), `ENODEV` (19), `EINVAL` (22) from `errno` |
| 35–57 | `crc7_be_syndrome_table`, `crc7`, `gb` |
| 60–81 | the five timeouts |
| 83–93 | the R1 bits, the three data tokens, `_HCS_BIT` |
| 96–109 | `SDCard`, `SDCard.__init__` |
| 111–129 | `check_crcs`, `init_spi`, `_spiff` |
| 131–194 | `_wait_ready`, `_recover` |
| 196–215 | `decode_cid` |
| 217–330 | `init_card`: the start-up sequence |
| 332–383 | `cmd`: one command frame and its R1 |
| 385–470 | `readinto`, `write`, `write_token`: one data block each way |
| 472–531 | `blocks`, `readblocks`, `writeblocks`: the block-device interface |
| 533–537 | `ioctl` |

## The command set

| Command | Sent by | Argument | What the driver does with the answer |
|---|---|---|---|
| CMD0 GO_IDLE_STATE | `init_card` | 0 | repeats until R1 == `_R1_IDLE_STATE`, for up to `_CMD0_TIMEOUT_MS` |
| CMD8 SEND_IF_COND | `init_card` | `0x01AA`, 4 trailing bytes clocked out unread | R1 idle: a v2 card; idle + illegal: v1; anything else: "couldn't determine SD card version" |
| CMD55 APP_CMD | `init_card` | 0 | the prefix of every ACMD41; its R1 is ignored |
| ACMD41 SD_SEND_OP_COND | `init_card` | `_HCS_BIT` on a v2 card, 0 on v1 | repeated until R1 == 0, for up to `_INIT_TIMEOUT_MS` |
| CMD9 SEND_CSD | `init_card` | 0, CS kept low | R1 must be 0; then `readinto` takes the 16-byte CSD: card size, `cdv` |
| CMD10 SEND_CID | `init_card` | 0, CS kept low | R1 must be 0; then `readinto` takes the 16-byte CID; any failure gives CID 0 |
| CMD16 SET_BLOCKLEN | `init_card` | 512 | R1 must be 0; three tries |
| CMD59 CRC_ON_OFF | `check_crcs` | 1 or 0 | R1 returned, unchecked |
| CMD18 READ_MULTIPLE_BLOCK | `readblocks` | `block_num * cdv`, CS kept low | R1 must be 0; then one `readinto` per 512 bytes |
| CMD12 STOP_TRANSMISSION | `readblocks`, `_recover` | 0, one stuff byte skipped | ends a CMD18; in `_recover` sent raw and unanswered |
| CMD25 WRITE_MULTIPLE_BLOCK | `writeblocks` | `block_num * cdv` | R1 must be 0; then one `write` per 512 bytes, then `write_token(STOP_TRAN)` |

## What it raises

Every failure is an `OSError`; `ACTIVATE_SD` prints each one as `attempt
n/5 failed: …` and `SD_CALL` turns one inside a command into "SD card
error", Report F ([tspico-bus.md](tspico-bus.md)).

| Raised by | Error |
|---|---|
| `init_card` | `OSError(ENODEV, "no SD card")`: no answer to CMD0 within `_CMD0_TIMEOUT_MS` |
| `init_card` | `OSError(EIO, "couldn't determine SD card version")`: CMD8's R1 is neither v1's nor v2's |
| `init_card` | `OSError(ETIMEDOUT, "card type", "v2" or "v1")`: the card never left idle within `_INIT_TIMEOUT_MS` |
| `init_card` | `OSError(EIO, "no CSD response")`, `OSError(EIO, "CSD format unknown")` |
| `init_card` | `OSError(EIO, "can't set 512 block size")`: CMD16 refused three times |
| `cmd` | `OSError(EIO, "CRC err on cmd: NN")`: the card's R1 has `_R1_COM_CRC_ERROR` set |
| `cmd` | `OSError(ETIMEDOUT, "command:", cmd, "arg:", arg)`: no R1 within `_CMD_TIMEOUT` polls |
| `readinto` | `OSError(ETIMEDOUT, "read timeout")`: no data token within `_READ_TOKEN_MS`; `OSError(EIO, "bad data CRC: …")` only with a `crc16_function` |
| `write` | `OSError(EIO, "write fail")`: the data response is not "accepted"; `OSError(ETIMEDOUT, "write busy")` |
| `write_token` | `OSError(ETIMEDOUT, "write busy")` |
| `blocks` | `OSError(EINVAL, "Buffer length is invalid")` |
| `readblocks`, `writeblocks` | `OSError(EIO)` with no text: CMD18, CMD25 or the final CMD12 refused |

The errno numbers appear in the logs as the comments quote them:
`(110, 'card type', 'v2')`, `OSError(19, 'no SD card')`,
`[Errno 5] EIO: write fail`.

## `crc7_be_syndrome_table`

The CRC-7 lookup table, a `bytes` of 256 entries, kept as a literal with the
escapes Python chose. Entry `i` is the CRC-7 of the single byte `i`, already
shifted one bit left ("be": the 7 bits sit in bits 1–7, bit 0 free for the
end bit). `crc7` is its only reader; `cmd` ORs 1 into the result to form the
frame's last byte. Checked against the SD standard values: the table gives
0x95 for CMD0 with argument 0, 0x87 for CMD8 with `0x01AA`, and 0x61 for
CMD12 with 0, the byte `_recover` sends by hand (its comment says "CRC7
0x30", the 7-bit value before the shift).

## `crc7(buf)`

Folds every byte of `buf` through the table: `crc = table[crc ^ b]`,
starting from 0. Returns the shifted CRC-7 (0–254, even). Called by `cmd`
on `cmdbuf5`, the first five bytes of the frame. Pure, no state.

## `gb(bigval, b0, bn)`

Returns bits `b0`..`bn` inclusive of an integer: `(bigval >> b0) &
((1 << (1 + bn - b0)) - 1)`. `init_card` uses it on the 128-bit CSD with the
bit numbers of the SD spec's table (the comment cites "SD card spec v9.0.0,
table 5.3.2"), and `decode_cid` on the CID; both bind it to a local first
("just for local binding", a MicroPython habit that saves a global lookup).

## The timeouts

Each one bounds a wait that used to be unbounded or too short, and each has
a host test in CI that pins it.

| Constant | Value | Bounds | Why that value | Pinned by |
|---|---|---|---|---|
| `_CMD_TIMEOUT` | 50 | the number of response bytes `cmd` reads while waiting for an R1 (bit 7 clear); after 25 of them each poll sleeps 1 ms, so about 25 ms plus byte times | inherited from the origin; not in the header's list of changes | the fakes in `sdcard_init_hosttest.py` charge 25 ms for a command nobody answers, which is this wait |
| `_READ_TOKEN_MS` | 100 | `readinto`'s wait for the `_TOKEN_DATA` byte, after 25 polls without a sleep | the SD spec's read access time limit; it was ~24 ms, so a slow card's read could fail with "read timeout" where the spec says it is fine (audit §4, fixed in #131) | `sd_recover_hosttest.py`: "read whose data never arrives: timeout raised AND CMD12 sent" |
| `_INIT_TIMEOUT_MS` | 1500 | the ACMD41 loop in `init_card` | the spec allows a card 1 s after power-up to leave idle; the old loop allowed ~250 ms (50 × 5 ms) and a cold card at boot failed with `(110, 'card type', 'v2')` while the same card mounted a few seconds later; MicroPython's stock driver allows 5 s (#60) | `sdcard_init_hosttest.py`: at least 1 s; a card ready after 900 ms mounts; one that never leaves idle gives ETIMEDOUT at ~1.5 s |
| `_CMD0_TIMEOUT_MS` | 500 | how long `init_card` keeps retrying CMD0 | a card still finishing something from before a soft reboot, or not yet awake, misses the first CMD0; the stock driver retries it; the old loop gave up on the first unanswered one (#61) | `sdcard_init_hosttest.py`: three ignored CMD0s still mount; a card that never answers gives "no SD card" at ~0.5 s |
| `_BUSY_TIMEOUT_MS` | 1000 | `_wait_ready`'s default: how long a card may hold MISO low after a block or STOP_TRAN | the spec's write timeout is 250 ms (SDSC) / 500 ms (SDHC/SDXC); 1 s leaves margin; it used to be `while busy: pass`, which hung the Pico for good on a card that never let go (#66) | `sd_recover_hosttest.py`: a write that never leaves busy raises within 3 × `_BUSY_TIMEOUT_MS`; a card stuck busy at init fails in under 4 s |

The three `_wait_ready` calls in `_recover` are why a card that is in but
not answering costs ~4 s per mount attempt, and why `ACTIVATE_SD` stops
starting attempts after `SD_TRY_MS` (6 s): five such attempts ran past the
2068's ~19.9 s READY wait and gave Report J (hardware, 2026-10-02;
[tspico-bus.md](tspico-bus.md)).

## The R1 bits

An R1 is the one-byte answer to every command here; `cmd` recognises it by
bit 7 being clear. Only three bits are named; the four that are commented
out (erase reset, erase sequence error, address error, parameter error) are
never tested.

| Constant | Bit | Where it matters |
|---|---|---|
| `_R1_IDLE_STATE` | `1 << 0` | CMD0 succeeds when R1 equals it; CMD8's R1 equals it on a v2 card; ACMD41 is repeated until R1 is 0, i.e. until this bit clears |
| `_R1_ILLEGAL_COMMAND` | `1 << 2` | a v1 card answers CMD8 with idle + illegal (`0x05`); `init_card` takes that as v1 |
| `_R1_COM_CRC_ERROR` | `1 << 3` | set in any R1, `cmd` releases the card and raises `EIO, "CRC err on cmd"` |

## The data tokens and `_HCS_BIT`

| Constant | Value | Use |
|---|---|---|
| `_TOKEN_CMD25` | `0xFC` | the start token `write` puts before each 512-byte block of a CMD25 |
| `_TOKEN_STOP_TRAN` | `0xFD` | ends a CMD25; `write_token` sends it after the last block, and on every error path; `_recover` sends it raw |
| `_TOKEN_DATA` | `0xFE` | the start token the card puts before a block it sends; `readinto` waits for it (CSD, CID, every CMD18 block) |
| `_HCS_BIT` | `1 << 30` | ACMD41's argument on a v2 card: the host supports high capacity (SDHC/SDXC) |

## `SDCard`

The block device. Its state, all set in `__init__` and `init_card`:

| Attribute | Type | Set by | Meaning |
|---|---|---|---|
| `spi`, `cs` | `machine.SPI`, `machine.Pin` | `__init__` | the bus and chip select the caller built |
| `cmdbuf`, `cmdbuf5` | `bytearray(6)`, a memoryview of its first 5 bytes | `__init__` | the command frame; `cmdbuf5` is what `crc7` reads |
| `tokenbuf` | `bytearray(1)` | `__init__` | one-byte scratch for every response and token poll |
| `crcbuf` | `bytearray(2)` | `__init__` | the CRC-16 sent after a block, only with a `crc16_function` |
| `crc16` | callable or `None` | `__init__` (`None` during init), `check_crcs` | the data CRC function; `None` in the firmware |
| `recovered` | `str` or `None` | `__init__` (`None`), `_recover` | what `_recover` found; `ACTIVATE_SD` prints and logs it |
| `CSD` | int | `init_card` | the 16-byte CSD as a big-endian integer |
| `sectors` | int | `init_card` | the card's size in 512-byte blocks; `ioctl(4)` returns it |
| `cdv` | 1 or 512 | `init_card` | block-to-address factor: 1 on a CSD 2.0 card (block addressing), 512 on CSD 1.0 (byte addressing) |
| `CIDBYTES`, `CID` | `bytearray(16)`, int | `init_card` | the CID, or 16 zero bytes and 0 when CMD10 failed; `TSP.sd_cid` is this `CID` |

The methods MicroPython's filesystem calls are `readblocks(block_num,
buf)`, `writeblocks(block_num, buf)` and `ioctl(op, arg)`, the two-argument
"simple" block interface, which the C-level `VfsFat` accepts (audit §3: the
SD card uses `VfsFat`; the frozen `_boot_fat.py` was never part of it).

## `SDCard.__init__(self, spi, cs, baudrate=5_000_000, crc16_function=None)`

Stores the bus and CS, allocates the four buffers, sets `crc16 = None` for
the duration of the start-up and `recovered = None`, then runs
`init_card(baudrate)` and `check_crcs(crc16_function)`, in that order:
CMD59 is sent at the final SPI speed, after the card is up. Raises whatever
`init_card` raises. Its two callers, `ACTIVATE_SD` (`tspico.py`) and
`ENA_SD` (`tspico_io.py`, used without the `SD_MOUNT` hook only by the
harnesses), both call `SDCard(spi, U3_CS)` with the defaults.

## `SDCard.check_crcs(self, crc16_function)`

Sets `self.crc16` and sends CMD59 with argument 1 (CRC on) or 0 (off),
releasing CS. Returns the R1 unchecked. With `None`, the firmware's case,
the card is told not to check data CRCs, `readinto` ignores the two bytes
after each block and `write` sends `0xFFFF` for them. The header's note:
with a `crc(seed, buf) -> int` function both directions are protected.
Nothing in the repo supplies one.

## `SDCard.init_spi(self, baudrate)`

Re-initialises the SPI bus at `baudrate`, phase 0, polarity 0. It tries
`self.spi.MASTER` first (the pyboard form, `spi.init(master, baudrate=…)`)
and on `AttributeError` uses the keyword-only form (the ESP8266 form, as the
comments say). The rp2 port's `machine.SPI` has no `MASTER` attribute, so
the second form is the one that runs on the Pico (inferred; the tests' fake
SPIs have no `MASTER` either and take that path). Called twice by
`init_card`: at 100000 before CMD0 and at `baudrate` after CMD16.

## `SDCard._spiff(self)`

Writes one `0xFF` byte: eight clocks with MOSI high, with CS in whatever
state it is. `cmd`, `readinto`, `write` and `write_token` call it right
after raising CS, the clocks a card needs after deselect to finish its
response; `readblocks` and `writeblocks` call it before their command "to
ensure MOSI is high before starting transaction", a workaround the comment
attributes to some Kingston cards on a shared bus. The audit (§5) kept that
leading byte: GPIO 2–4 are shared with the Z80 bus, so MOSI's level before
a transaction is not otherwise known.

## `SDCard._wait_ready(self, ms=_BUSY_TIMEOUT_MS)`

With CS already low, reads one byte at a time (MOSI high) until the card
stops answering `0x00`. Returns how many busy bytes it saw, 0 when the
first byte was not `0x00`, or -1 when `ms` has passed. The clock is only
consulted after a busy byte, so a ready card costs one byte and no
`ticks_ms` call. Callers: `_recover` (three times), `write` (after the data
response), `write_token` (before and after the token). Added with #66: the
origin's `while busy: pass` had no bound.

## `SDCard._recover(self)`

Brings back a card that the previous session left inside a transfer,
before `init_card` sends CMD0. The docstring is the specification; the
steps as coded:

1. CS low. Read 520 bytes with MOSI high (`spi.readinto(buf, 0xFF)`): a
   half-sent CMD25 block gets its remaining data, two CRC bytes and the
   response slot filled, and with CRC checks off the card writes that
   sector with the `0xFF` filler. Count the bytes that were not `0xFF` as
   `seen` (an idle card returns only `0xFF`; a card still streaming a CMD18
   read returns data).
2. `b1 = _wait_ready()`: wait out the busy that follows a block.
3. Write `FD FF`: STOP_TRAN and the byte before busy. `b2 = _wait_ready()`;
   a busy here means the card was inside a CMD25. An idle card ignores a
   lone `0xFD`.
4. Write the CMD12 frame by hand, `4C 00 00 00 00 61`, then read 520 bytes
   (skip byte, R1, busy) and `b3 = _wait_ready()`. This ends a CMD18 left
   streaming; an idle card answers "illegal command" and carries on. The
   answer is not examined, which is why `cmd` is not used here: `cmd` would
   raise on a card that is busy swallowing data.
5. CS high, two `0xFF`.
6. `stuck = b1 < 0 or b2 < 0 or b3 < 0`. When `seen`, `b1`, `b2` or `stuck`
   is non-zero, `self.recovered` becomes
   `"card was mid-transfer (%d non-idle bytes, busy %d/%d%s)"` with
   `", still busy"` appended when stuck; otherwise it stays `None`.

Why: the card runs off the Pico's 3V3, so a reset, reflash or Ctrl-C during
an SD access, or `writeblocks` raising on "write fail" without STOP_TRAN as
it used to, left the card waiting for data; it swallowed CMD0 as data and
the driver reported "no SD card" on every warm boot until the power was
pulled. Reproduced and fixed on hardware 2026-09-26 by stopping a write 100
bytes into a block (#66; [DEVELOPER_GUIDE.md §3](../../DEVELOPER_GUIDE.md),
"If the SD card won't mount after a soft reboot"). Everything is bounded: a
card that stays busy costs three `_BUSY_TIMEOUT_MS` and is then left for
CMD0's own retry loop to report as "no SD card".

Pinned by `sd_recover_hosttest.py`, whose byte-level fake card is left in
each state: 100 bytes into a block (block finished, one STOP_TRAN, mounts,
`recovered` says "mid-transfer"); between blocks of a CMD25 (the "write
fail" case); streaming a CMD18 (one CMD12, mounts); stuck busy ("no SD card"
in under 4 s); and an idle card, which is left alone, `recovered` is `None`
and no STOP_TRAN is consumed.

Beware: a hard reset of the Pico (every UF2 flash, `machine.reset()`)
reliably leaves the card holding MISO low for good; this sequence does not
reach it, CMD0 gets no reply, and only reseating the card or a power cycle
clears it (DEVELOPER_GUIDE §3, reproduced 2026-09-30; the cause is not
known). The user manual's advice follows from that
([user-manual.md 2.6](../../manual/user-manual.md)).

## `SDCard.decode_cid(self)`

Returns the CID as a dict: `mid` (bits 120–127, the manufacturer), `oid`
(bytes 1–2 as ASCII), `product` (bytes 3–7 as ASCII), `revision` as
`"hi.lo"` (bits 60–63 and 56–59), `serial` (bits 24–55), `date` as
`"YYYY/MM"` (year bits 12–19 plus 2000, month bits 8–11). Reads `CID` and
`CIDBYTES`. No caller in the firmware (`grep` finds none outside this file):
it is a REPL convenience. With a CID of 0 it returns zeros and NUL strings;
a card with non-ASCII bytes in its name would make `.decode('ascii')`
raise.

## `SDCard.init_card(self, baudrate)`

The start-up sequence, run once per `SDCard`, so once per mount attempt:

1. `cs.init(cs.OUT, value=1)`: CS high.
2. `init_spi(100000)`: the low rate the spec requires for initialisation.
3. Sixteen `0xFF` bytes with CS high: 128 clocks, more than the 74 the card
   needs to wake. The literal string is spelled out "for small memory
   footprint".
4. `_recover()` (above).
5. CMD0 until R1 == `_R1_IDLE_STATE`. `cmd(0, 0)` raising `OSError` (no
   answer) counts as a failed attempt, not an error: the loop clocks ten
   `0xFF` with CS high so the card can finish what it was doing, sleeps
   5 ms and tries again, and gives up with `ENODEV, "no SD card"` after
   `_CMD0_TIMEOUT_MS`. The comment records the two bugs this replaced:
   `cmd` raises where the stock driver returned -1, so the old "allow 5
   attempts" loop died on the first unanswered CMD0 (seen at boot as
   `(110, 'command:', 0, 'arg:', 0)` about 30 ms in), and the old call
   passed `0x95` as `cmd`'s third argument, which is `final`, extra bytes
   to clock out, not the CRC it is in the stock driver, so every CMD0
   clocked 149 bytes for nothing. `sdcard_init_hosttest.py` pins both: three
   ignored CMD0s still mount, and `final` is always 0.
6. CMD8 with `0x01AA` and `final=4`: the four bytes of the R7 answer (the
   voltage range and echo) are clocked out and discarded. R1 idle means a
   v2 card; idle + illegal means v1 (the comment: "determine card
   version"); anything else raises `EIO`.
7. CMD55 then ACMD41, with `_HCS_BIT` for a v2 card, until R1 is 0. An
   `OSError` from either (no answer yet) is treated as "not ready", `r =
   -1`; 5 ms between tries; `_INIT_TIMEOUT_MS` in all, then
   `ETIMEDOUT, "card type", "v2"/"v1"`. Pinned: a card that ignores its
   first four CMD55s still mounts.
8. CMD9 with `release=False`, so CS stays low for the data that follows;
   `readinto` takes the 16-byte CSD. Bits 126–127 give the CSD version:
   1 (CSD 2.0, SDHC/SDXC) sets `sectors = (C_SIZE + 1) * 1024` from bits
   48–69 and `cdv = 1`; 0 (CSD 1.0, cards up to 2 GB) computes the capacity
   from `c_size` (62–73), `c_size_mult` (47–49) and `read_bl_len` (80–83)
   as `(c_size + 1) * 2**(c_size_mult + 2) * 2**read_bl_len`, sets
   `sectors = capacity // 512` and `cdv = 512`, since such a card is
   addressed in bytes. Any other version raises `EIO, "CSD format
   unknown"`. The capacity class is never read from the OCR (no CMD58).
9. CMD10, inside `try … except Exception`: the 16-byte CID into `CIDBYTES`
   and `CID`. Any failure, including a non-zero R1 (raised as a plain
   `OSError("no CID response")` and caught at once), leaves `CIDBYTES` as
   sixteen zero bytes and `CID = 0`. 0 means "unknown": `SD_NOTE_CARD`
   never takes it as a different card and never lets it replace a CID it
   knows (#107, audit §2 #13; the CID has been the card's identity since
   #101, and before that fix one failed CMD10 looked like a card swap and
   closed every channel). `Exception`, not a bare `except`, so a Ctrl-C from
   the host still gets through.
10. CMD16 with 512, up to three tries 5 ms apart: a card that has only just
    left idle can refuse the first one (seen at boot as "can't set 512
    block size", #60). All three refused raises `EIO`. Pinned: one refusal
    mounts, nine are reported.
11. `init_spi(baudrate)`: 5 MHz from here on.

Reads nothing but the card; writes `CSD`, `sectors`, `cdv`, `CIDBYTES`,
`CID`, and `recovered` through `_recover`. Takes about 0.7 s of card work
at boot on a healthy card (DEVELOPER_GUIDE §3's figure for the whole boot
mount). Interrupting it, or any later access, with Ctrl-C is what leaves
the card in the state `_recover` repairs.

## `SDCard.cmd(self, cmd, arg, final=0, release=True, skip1=False)`

Sends one command frame and returns its R1.

1. CS low.
2. Builds the six bytes in `cmdbuf`: `0x40 | cmd`, the 32-bit argument
   big-endian, and `crc7(cmdbuf5) | 1`. Every frame carries a correct CRC-7,
   so the card's own CRC check can stay on for commands.
3. With `skip1`, reads and discards one byte first: CMD12 answers with a
   stuff byte before its R1.
4. Polls up to `_CMD_TIMEOUT` bytes for one with bit 7 clear; after the
   first half, 1 ms of sleep per poll ("very slow response, give it time").
5. On the response: `_R1_COM_CRC_ERROR` set releases the card and raises
   `EIO, "CRC err on cmd: NN"`. A negative `final` reads one more byte into
   `tokenbuf` and sets `final = -1 - final` (the comment: for a response
   that is a big-endian integer); no caller in the firmware uses that
   form. Then `final` bytes are clocked out and dropped; with `release`, CS
   goes high and one `0xFF` follows. Returns the R1.
6. No response: CS high, one `0xFF`, `ETIMEDOUT, "command:", cmd, "arg:",
   arg`.

`release=False` is how CMD9, CMD10 and CMD18 keep CS low for the data block
that follows. `arg` must fit 32 bits: `cmdbuf[1] = arg >> 24` would raise
`ValueError` otherwise, which `block_num * cdv` never reaches on a card this
driver accepts.

## `SDCard.readinto(self, buf)`

Takes one data block of `len(buf)` bytes from the card, CS low throughout.

1. Polls for `_TOKEN_DATA`: the first 25 polls (`_CMD_TIMEOUT // 2`) back to
   back, then the clock starts and each further poll sleeps 1 ms, up to
   `_READ_TOKEN_MS`; then CS high and `ETIMEDOUT, "read timeout"`. This is
   the one error exit that does not clock a `0xFF` after raising CS.
2. `spi.readinto(buf, 0xFF)`: the block.
3. Two CRC bytes, read and, with `crc16` set, checked: `crc16(crc16(0, buf),
   ck)` must be 0, else CS high, `0xFF`, `EIO, "bad data CRC"`. Without
   `crc16` they are dropped.
4. CS high, one `0xFF`.

Callers: `init_card` for the CSD and CID (16 bytes each) and `readblocks`
for each 512-byte slice of its buffer. The wait was lengthened from ~24 ms
to the spec's 100 ms by #131 (audit §4, "data-token wait").

## `SDCard.write(self, token, buf)`

Sends one data block inside a CMD25:

1. CS low. `spi.read(1, token)` sends the token while reading a byte that
   is dropped; `spi.write(buf)` sends the data; then the CRC, computed when
   `crc16` is set, else `FF FF`.
2. Reads the data response; its low five bits must be `0x05`, "data
   accepted". Otherwise CS high, `0xFF`, `EIO, "write fail"`. No STOP_TRAN
   is sent here; `writeblocks`'s `except` does that.
3. `_wait_ready()` for the card to program the block; -1 gives CS high,
   `0xFF`, `ETIMEDOUT, "write busy"`.
4. CS high, one `0xFF`.

Only `writeblocks` calls it, always with `_TOKEN_CMD25`. The "write fail"
path is the one that used to strand the card (see `writeblocks`), and the
field failure of 2026-09-26 (`EIO: write fail` raised from inside
`os.ilistdir()`, FatFs flushing a sector `os.remove("dirinfo.tap")` had
dirtied) is why `DIR_FILES` now wraps all its SD work ([tspico-files.md](tspico-files.md)).

## `SDCard.write_token(self, token)`

Sends a lone token, in practice `_TOKEN_STOP_TRAN`, and waits for the card
to finish:

1. CS low, then `_wait_ready()` first: a card still busy with the last
   block takes the token as a clock tick and never sees it, which is how
   STOP_TRAN was lost after a refused block. The result of this first wait
   is not checked; the token is sent either way.
2. `spi.read(1, token)`, one `0xFF` (the byte before busy).
3. `_wait_ready()` again; CS high; one `0xFF`; -1 from the wait raises
   `ETIMEDOUT, "write busy"` after CS is released.

Called by `writeblocks` on its normal path and in its `except`.

## `SDCard.blocks(buf)`

A `staticmethod`: `divmod(len(buf), 512)` must give at least one block and
no remainder, else `EINVAL, "Buffer length is invalid"`. Returns the block
count. Both block methods call it before touching the card.

## `SDCard.readblocks(self, block_num, buf)`

The filesystem's read: `len(buf)` bytes from block `block_num` on.

1. `_spiff()` (the MOSI-high workaround), `blocks(buf)`.
2. CMD18 with `block_num * cdv`, `release=False`. A non-zero R1 raises CS and
   raises `OSError(EIO)`.
3. For each 512-byte slice of a `memoryview` of `buf`, `readinto`.
4. `cmd(12, 0, skip1=True)` ends the stream; a non-zero R1 is `OSError(EIO)`.

The loop is inside `try … except BaseException`: on any exception, a
block that timed out or a Ctrl-C landing mid-way, CMD12 is still sent (its
own `OSError` swallowed) and the original exception re-raised, because a
card left streaming ignores the next command. Pinned by
`sd_recover_hosttest.py`: a two-block read gives the data and exactly one
CMD12; a read whose data never arrives raises and still sends CMD12, and
the fake card is idle afterwards. MicroPython calls this from `os.mount`'s
filesystem driver; no Python code in the firmware does.

## `SDCard.writeblocks(self, block_num, buf)`

The filesystem's write.

1. `_spiff()`, `blocks(buf)`.
2. CMD25 with `block_num * cdv` (CS released after the R1; `write`
   reselects per block). A non-zero R1 is `OSError(EIO)`.
3. For each 512-byte slice, `write(_TOKEN_CMD25, slice)`.
4. `write_token(_TOKEN_STOP_TRAN)`.

Step 3 is inside `try … except BaseException`: when a block is refused
("write fail") or a Ctrl-C lands between blocks, STOP_TRAN is sent anyway
(its `OSError` swallowed) and the original exception re-raised. Before #66
the exception left the card inside the CMD25, where it swallowed every
later command, CMD0 included, as data, and the TS-Pico said "no SD card"
until a power cycle. Pinned by `sd_recover_hosttest.py`: a refused second
block raises `EIO` and sends one STOP_TRAN, the card is idle and the next
command works; a card that never leaves busy raises `ETIMEDOUT` within
3 s, one `_BUSY_TIMEOUT_MS` in `write` and two in the `except`'s
`write_token`, instead of hanging.

Beware: the same card state can be produced from outside the driver, by a
Pico reset during a write (`_recover`) or by a Ctrl-C from the host, which
is why `tools/pico-serial.py`'s docstring says never to `break` while the
Pico may be mid-SD access.

## `SDCard.ioctl(self, op, arg)`

The block-device control call: `op` 4 returns `sectors` (the block count),
`op` 5 returns 512 (the block size). Every other `op` (1 init, 2 deinit, 3
sync, 6 erase) falls through and returns `None`, which MicroPython takes as
"not supported". Only the filesystem driver calls it; `tpi:info`'s SD card
line comes from `os.statvfs` on the mounted filesystem, not from here
([tspico-commands.md](tspico-commands.md)).

## How it differs from the driver it came from

As the code and its comments say, not from a diff against the origin:

- `cmd` raises `OSError` when the card does not answer; the stock driver
  returns -1. The CMD0 loop had to change with it (#61).
- `cmd`'s third parameter is `final`, bytes to clock out after the
  response, and the CRC is computed; in the stock driver that position is
  the CRC byte (the `0x95` the old call passed here).
- ACMD41 gets 1.5 s, not the stock 5 s, and CMD16 three tries (#60).
- `_recover` before CMD0, STOP_TRAN and CMD12 on every exit of
  `writeblocks` and `readblocks`, and every busy wait bounded (#66).
- The data-token wait is the spec's 100 ms (#131); the audit measured
  ~24 ms before and noted that micropython-lib's driver waits ~100 ms.
- The CID is read and kept (`CIDBYTES`, `CID`, `decode_cid`), with 0 for
  "unknown" (#101, #107).
- No `crc16` function is wired in; the `crc_function` note in the header
  describes a capability the firmware does not use.

The header's old line about "hold off initializing", which the audit listed
as describing a change that does not exist (§3, stale comments), was
replaced by the current list in #123.
