# Flow: how the bus passes between the Z80 and the SD card

GPIO 2, 3 and 4 are both D0–D2 of the 2068's data bus (through the U6
buffer) and the SD card's SPI clock, MOSI and MISO. Only one side can have
them at a time. Whenever the Pico touches the card it takes the pins away
from the Z80, and while it does, the Z80 must be somewhere that does not
need the Pico: in a ready-wait, polling a port nobody answers. This flow
follows one handover from the Z80 to the card and back, says where it
happens and why each step is there, and covers the cases where the card is
missing or stuck.

Notation: **MQ** is the bus state machine (PIO0 SM 0); **TX**/**RX** its
FIFOs; **Y** the status the Z80 reads on port 0Fh.

## The two states

| | MQ state (normal) | SD state |
|---|---|---|
| state machine 0 runs | `TS_IO_DUAL`, 30 MHz | `NULL_SM`, parked (started and stopped) |
| GPIO 2–4 | the PIO's | `SPI(0)` |
| GPIO 12 (U6 enable) | the PIO's side-set: U6 on only during a Z80 cycle on 0Eh/0Fh | output 1: U6 off, the Pico off the 2068's bus |
| `sd_active` | `False` | `True` |
| what the Z80 can do | anything | nothing useful: its reads of 0Eh/0Fh are not answered by the Pico |

([../firmware/tspico-bus.md](../firmware/tspico-bus.md#the-bus-and-how-it-changes-hands))

## One handover

| # | Step | Code | Effect | Why |
|---|---|---|---|---|
| 0 | **Precondition**: the Z80 is in a ready-wait | — | it is polling 0Fh for READY, ~88 ms a poll, ~19.9 s before it gives up | the only safe moment: it will not read data or send until it sees READY. Mid-block the Z80 reads blind and the card must not be touched |
| 1 | Save the pre-load if one is pending | `PRELOAD_READ()` (≤ 100 ms), and `MQ.put(0x01)` afterwards if it was not read | | rebuilding the state machine empties TX; a pre-load lost here is Report J or a misread later ([../firmware/tspico-bus.md](../firmware/tspico-bus.md#preload_readms100)) |
| 2 | Park the bus program | `ACTIVATE_SD`: `StateMachine(0, NULL_SM)`, `active(1)`, `active(0)`; `sd_active = True` | TX and RX gone; no PIO drives D0–D7 or U6 | nothing may drive the shared pins while SPI uses them |
| 3 | U6 off | `Pin(12, OUT, value=1)` | the 2068's data bus is isolated from GPIO 2–9 | since #61; before, the bus could fight the card |
| 4 | Mount | `SPI(0, sck=2, mosi=3, miso=4)`, `SDCard(spi, U3_CS)`, `os.mount(sd, "/sd")`, up to 5 tries 0.5 s apart while the card is believed present, 1 when it is known missing, none started after 6 s | | a cold card refuses at first; the 6 s budget keeps the worst case inside the Z80's ~19.9 s |
| 5 | Note the card | `SD_NOTE_CARD(CID)` → `SD_REVALIDATE` when it is back or different | the folder, the mount, append, the channels fixed for the new card | ([../firmware/tspico-bus.md](../firmware/tspico-bus.md#sd_note_cardcid)) |
| 6 | **The work** | the handler's file operations | | keep it short: the Z80's budget is shared with everything else in the transaction |
| 7 | Unmount, CS high, clamp | `DEACTIVATE_SD`: `os.umount`, U3_CS = 1, GPIO 2–4 driven low | | a defined level until the PIO takes the pins (whether the clamp is still needed with U6 is an open question, audit §4) |
| 8 | Bus program back | `ACTIVATE_MQ`: `StateMachine(0, TS_IO_DUAL, 30 MHz, …)`, `active(1)`, `MQ_BUSY()` | **TX [], RX [], Y `00`** | Y must be BUSY: a fresh state machine keeps the old Y, and a READY now would let the Z80 read an empty TX as 00h (Report J) ([../firmware/tspico-bus.md](../firmware/tspico-bus.md#activate_mq)) |
| 9 | The answer, then READY | `CMD_PUT`/`CMD_SEND`/`SEND_MSG` …, which say READY after the first bytes are in TX | TX [answer…], Y `FF` or `F7` | data first, then READY |

Steps 2–5 are `ACTIVATE_SD`, 7–8 `DEACTIVATE_SD` + `ACTIVATE_MQ`. Most
handlers get all of it from **`SD_CALL(fn, *args)`**, which runs `fn` with
the card and always gives the pins back in a `finally`, turning an SD error
into ("SD card error", F) and a missing card into the no-card answer (J)
([../firmware/tspico-bus.md](../firmware/tspico-bus.md#sd_callfn-args)).
`SD_PROBE`, `LISTING_CHECK` and `REFRESH_LISTING` are the same shape.

**If a handler raises with the card in hand**, `PROCESS_CMD`'s `except`
calls `FAIL_CMD`, which sees `sd_active` still `True` and does steps 7–8
before it answers J. Without that the Pico would `put()` into the parked
state machine — nothing reaches the Z80, and after four words `put()`
blocks for good ([../firmware/tspico-dispatch.md](../firmware/tspico-dispatch.md#fail_cmdstatus)).

## Where it happens

| When | Who | The Z80 is in |
|---|---|---|
| boot | `TS2068_IO`: `ACTIVATE_SD(tries=5)` while core 1 blinks the LED, then 7–8 and the boot pre-load ([boot.md](boot.md)) | nothing yet: no Z80 transaction can start before the bus program runs |
| a command | the handler, via `SD_CALL` or by hand (`MOUNT_FILE`, `ChangeDir`, `GETHELP` …); the card gate's `SD_PROBE` | PICO_TRANSACT's ready-wait after the body ([command.md](command.md)) |
| `LOAD "tpi:name"` | `MOUNT_FILE`: the file copied from the card to `/TMP/temp.tap` on the Pico's flash | the same; this can take seconds |
| a SAVE | the dispatcher's `SD_PROBE` at the header (with `PRELOAD_READ` around it); `SAVE_TS`'s write through `SAVE_MOUNT` before the final status; the re-mount after it ([save.md](save.md)) | the header's ready-wait; the final status's ready-wait |
| LOAD | **never**: `LOAD_TS` streams from the copy on the Pico's flash, because the Z80 reads the block blind and the card cannot be touched then ([load.md](load.md)) | — |
| printing | `PRINT_FLUSH` when the text buffer is full or another transaction arrives; `COPY_BMP` | a printer transaction's ready-wait |
| a channel command | `CH_CALL` → `SD_CALL` for each `tpi:chwr`, `tpi:chrd` … (open, seek, write or read, close) | `CH_SEND`'s WF_NPH ([channels.md](channels.md)) |
| ZX48 mode | `SAVE_ZX` mounts with `ENA_SD` → `SAVE_MOUNT` and gives the bus back with `ENA_MQ_DUAL`, which rebuilds `TS_IO_DUAL` and **says READY** itself because `ZX48_IO` never returns to the dispatcher between transfers; `ZX_TPI` uses the usual `ACTIVATE_SD` … `ACTIVATE_MQ` and says READY with its reply ([../firmware/tspico_io.md](../firmware/tspico_io.md#ena_mq_dualmq)) | the Spectrum ROM's ready-wait after `'S'` or `'T'` |

## No card, and a stuck card

- **No card at all**: each mount attempt fails after ~0.5 s (`CMD0`'s
  timeout). `ACTIVATE_SD` raises `OSError(19)`; `sd_present` goes `False`;
  the wrappers give the pins back. A command that needs the card answers
  "No SD card…" (J); the next such command probes once more, so putting a
  card in is all it takes ([command.md](command.md#no-card)).
- **A card left mid-transfer** by an interrupted session (a Ctrl-C, a reset
  or a reflash during an SD access — the card is powered from the Pico's
  3V3 and keeps waiting for data): the driver's `_recover` finishes the
  block with `FFh`, sends STOP_TRAN and CMD12, waits out the busy, and
  `CMD0` then works; `recovered` says so and the log records it
  ([../firmware/sdcard.md](../firmware/sdcard.md#sdcard_recoverself)).
- **A card holding MISO low** (seen after every hard reset of the Pico,
  cause unknown): `_recover`'s three busy waits cost ~3 s, then `CMD0`
  fails; `SD_TRY_MS` stops new attempts after 6 s, so a command answers
  within ~8.5 s, inside the Z80's ~19.9 s, instead of the 20 s five
  attempts took (hardware, 2026-10-02). Only reseating the card clears it.
- **A card swapped between commands**: noticed at the next mount by its
  CID (`SD_NOTE_CARD`); a swap to a card with an unreadable CID is noticed
  only if a command saw the slot empty in between. `LISTING_FRESHEN`
  catches a folder that changed on the same card (a file added on a Mac).

## What goes wrong, and where

| Mistake | Result |
|---|---|
| touching the card while the Z80 reads blind (mid-block) | the Z80 reads floating bytes: R |
| `ACTIVATE_MQ` saying READY, or a handler saying READY before its data | the Z80 reads 00h: J |
| an SD access that takes longer than ~19.9 s | the Z80 gives up (J) and the Pico answers nobody; the next SYNC recovers |
| forgetting to hand back (`DEACTIVATE_SD` + `ACTIVATE_MQ`) | the Pico is deaf to the 2068 until `FAIL_CMD` or the restart loop rebuilds the bus |
| losing the pre-load to a rebuild | the next read of 0Eh is 00h: J |

## Where to read more

- [../firmware/tspico-bus.md](../firmware/tspico-bus.md) — every function in the handover.
- [../firmware/sdcard.md](../firmware/sdcard.md) — the driver and its recovery.
- [../hardware.md](../hardware.md) — the pins and U6.
- [DUAL_PORT_DEVELOPMENT.md §1, §8](../../DUAL_PORT_DEVELOPMENT.md) — the history of the handover bugs.
