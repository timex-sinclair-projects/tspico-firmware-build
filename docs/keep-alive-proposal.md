# Proposal: response function 89h, a keep-alive with a spinner

Status: **proposal, for the team's review** (revised 2026-11-16 for ROM 2.4 and the border idea). Nothing is built yet. Branch
`keep-alive-fn89`, based on main after #408.

## The problem

Every `tpi:` command has to answer inside the 2068's one ready-wait. After a
command's last byte the ROM sits in `WAIT_PICO_READY` (EXROM 1A54h,
[exrom-driver.md](reference/rom/exrom-driver.md#wait_pico_ready-1a54h)): 226
polls of the READY bit, each about 88 ms because it goes through
`CHECK_BREAK`. That comes to **~19.9 s**, and then the 2068 gives Report J.
Nothing the Pico can send restarts that count. The ROM prints Pico text only
after READY, inside a response function (status 80h and up), and when the
function ends the command is over. The one existing loop that prints and then
waits again is function 86h, and it waits for a key on every pass.

So work that may take longer than ~19.9 s must either be cut short or split
across commands. The motivating case is `tpi:net find` (#408, merged). The
first find fetches the 46 KB index (~10 s), unpacks it (2.9 s) and searches it
(2.9 s). To be safe, the firmware stops after 13 s (`NET_FIND_MS`) and tells the
user to type the find again. The firmware can't fix this by itself.

## What it looks like

```text
SAVE "tpi:net find chess"
                                  <- the screen as it was
Finding /                         <- the lower screen; the spinner turns
```

The spinner goes `- \ | /` about four times a second. When the work ends the
label is wiped, the answer (a listing, a message or a report) arrives as it
always has, and BREAK stops the work at any moment with Report D.

## The ROM side: function 89h

### The routine

It goes at the end of the disk module, after `CAT #n`: 3998h, where 1640 free
bytes (`FFh`) begin. In `fddcmd.asm`:

```text
KEEP_ALIVE:                       ; function 89h (A = 88h on entry)
        ld      a,STREAM_LOWER    ; FDh: the lower screen, as LOWER_LOOP
        call    OPEN_STREAM
        call    PS_READ           ; the text, up to 00h (the module's own reader)
        ld      a,$89
        call    TSPICO_WRITE_DATA ; the ack: the Z80's OUT drops READY (auto-busy)
        call    WAIT_PICO_READY   ; a new ~19.9 s; BREAK -> BRK_ABORT, Report D
        jr      c,.j
        call    TSPICO_READ_DATA  ; the next status, as C_END_TAIL reads it
        jr      z,.j              ; 00h: no answer
        dec     a
        ret     z                 ; 1: OK, A = 0
        jp      FN_CHAIN_HEAD     ; anything else: the chain again (89h included)
.j:     ld      a,$09             ; a timeout or no answer: J, as ERR_9
        scf
        ret
```

That is about 30 bytes. It needs three new `EQU`s, each checked by an
`ANCHORS` entry in `build-rom.py`: `WAIT_PICO_READY` (1A54h),
`TSPICO_WRITE_DATA` (229Dh) and `FN_CHAIN_HEAD` (026Fh). It differs from the brief I was given in three ways:

- **No status byte of its own.** Every other function reads one more byte
  (`READ_STATUS_BYTE`) as the command's result. A keep-alive has no result:
  the result is whatever comes after the last pass. On the wire a pass is
  `89h`, text, `00h`.
- **An ack byte.** After the text the Z80 sends `89h` on port 0Eh. That
  `OUT` is what drops READY: the PIO's auto-busy does it in hardware, as it
  does for the key in an 86h loop. Without the ack, the Pico would have to
  see the `00h` go and then drop READY itself, all within the few dozen
  T-states before the Z80 is back in its ready-wait. MicroPython can't
  promise that, and a READY left up would make the Z80 read an empty FIFO
  (`00h`, Report J). The ack also tells the firmware that the pass is over
  (see "Knowing the Z80 has read it" below).
- **It jumps back into the chain instead of calling it.** The chain is
  `CP` / `JP` all the way down (026Fh → 2194h → … → 2218h). So `JP
  FN_CHAIN_HEAD` with A = status − 1 runs any function, a plain report (it
  falls off the end with A unchanged), or 89h again, and the stack does not
  grow. A thousand passes cost no more stack than one. The return contract
  is the chain's own: A = 0 for OK, A = status − 1 for a report, A = 09h with
  carry for J. C_END_TAIL (227Fh), C_END2 and the BIOS callers see exactly
  what they see today.

A keep-alive may be followed by anything a command can answer with: `01h`,
a report, `81h` text, an `86h` listing or Y/N prompt, or `88h`.

### Hooking it into the chain

The chain's last link is the disk module's patch at 2213h: `CP 87h / JP
Z,3006h / RET`, with the `RET` at 2218h. After that, 2219h–221Eh is the old
dead beep handler (`PUSH AF / CALL BEEPER / POP AF / RET`). A scan of the
committed `TSPICO-23.ROM`'s EXROM (and, since, `TSPICO-24.ROM`'s) found no `JP`, `CALL` or `JR` to any
address from 2218h to 221Eh: the only way into those bytes is falling through
from 2213h. One new `build-rom.py` patch:

```text
name:   response function $89: the dead beep handler -> KEEP_ALIVE ($3998)
exrom   $2218   before  c9 f5 cd 3f 20 f1
                after   fe 88 ca 98 39 c9      ; CP 88h / JP Z,KEEP_ALIVE / RET
```

221Eh's `RET` stays. `FIXED_SYMS` gets `"KEEP_ALIVE": 0x3998`, so the build
fails if the module ever moves it, as for `PS_READ`. The chunk-1 chapter's
BEEPER callers lose 221Ah.

Why not a slot in the module's vector table, the way 88h goes through
`LOWER_VEC` (3006h)? The table is full: 3000h–3020h are eleven `JP`s and
`TAPE_MODE` starts at 3021h. A pinned symbol does the same job.

### The ROM's version

*Revised 2026-11-16.* When this proposal was first written, ROM 2.3 was only
with the beta testers, and the plan was to keep its name with a new CRC.
Since then ROM 2.4 has been released (#416, `TSPICO-24.ROM`, PEEK 101 = 36).
Every address above is the same in 2.4: the bytes at 2213h–221Eh, the 1640
free bytes from 3998h, and no jumps into 2218h–221Eh.

So this is **ROM 2.5**: version byte 25h (pre-header byte 2, `rom_id`) and
G_VERS 0025h. Users now have 2.4, so the firmware can't assume the new ROM.
It sends a keep-alive only when `rom_id` ≥ 25h. On a 2.4 ROM, 89h would
fall off the chain (Report D), so `KEEP_ALIVE()` does nothing there, and the
commands keep today's limits. `tpi:net find` keeps `NET_FIND_MS` and its
"find again" answer for 2.4 ROMs, and drops them on 2.5. The release is the
usual ROM bump: the image is renamed in every file that names it, and the
updaters offer the ROM step.

### The lower screen, not the main one

The spinner prints on the lower screen (stream FDh, channel K), like 88h:

- The main screen belongs to the program. A spinner there would land
  wherever the print position is, in the middle of the program's output, and
  move that position.
- In direct mode the report that ends the command clears the lower screen
  anyway. In a program, the firmware's last pass wipes the label (see below),
  so nothing is left behind.
- `LOWER_LOOP` already prints Pico text on the lower screen while a
  statement runs, so this is a path we've already tested.

`CHR$ 8` moves the print position back one column. The firmware already
relies on that on the main screen: `SEND_MSG2` erases with `08h 20h 08h`
(tspico.py 2753) and `ListMenu` does the same (4185). The lower screen is
the same print routine with TV_FLAG bit 0 set, but I haven't tried `CHR$ 8`
there. **The first build step checks it in ZEsarUX**: a pass of `"ab", 08h,
"c"` on the lower screen must show `ac`. If it doesn't, the spinner can
re-print the label each pass from `AT 0,0` (the lower screen's `AT` is
relative to it), which costs only a few more bytes per pass.

## The firmware side

### The helper

In `src/TS/tspico.py`, next to the command I/O helpers:

```python
KEEP_ALIVE_START("Finding")     # nothing on the wire yet
...                             # the slow work, which calls:
KEEP_ALIVE()                    # cheap, never blocks: call it as often as you like
...
SEND_MSG(...)                   # any answer ends the keep-alive first
```

- `KEEP_ALIVE_START(label)` notes the time and the label. Nothing is sent,
  so a command that finishes fast shows no spinner.
- `KEEP_ALIVE()` is the tick. If a pass is out, it looks at RX: the ack
  (`89h`) means the pass is over, a port-0Fh word (BREAK, or a SYNC) raises
  `CmdAbort(1)`, and no ack after `KA_ACK_MS` (2 s; the Z80 takes 88–180
  ms) raises `CmdAbort(3)`. If no pass is out, and at least `KA_DELAY_MS`
  (1 s) has passed since START and `KA_PERIOD_MS` (250 ms) since the last
  pass, it sends one. The first pass is `89h, label, " ", "-", 00h`. Each
  pass after that is `89h, 08h, next spinner char, 00h`: four bytes, so it
  fits the TX FIFO, goes in with `CMD_SEND` and is followed by READY. It
  doesn't wait for the Z80.
- `KEEP_ALIVE_END()` waits for any pass still out, up to `KA_ACK_MS`.
  If a label was printed, it sends one last pass that wipes it (`08h 20h
  08h` for each character) and waits for that ack. Then it clears its state.
  Afterwards Y is BUSY (from the last ack's auto-busy) and the Z80 is in
  `KEEP_ALIVE`'s ready-wait, waiting for a status: the same state a handler
  starts in. So any answer can follow.

The rules this keeps:

- **Data before READY.** Every pass is fully in TX (or, if it's longer than
  four bytes, its first four bytes and the DMA channel running, through
  `CMD_SEND`) before `MQ_READY`, as `CMD_SEND` always does.
- **Knowing the Z80 has read the bytes.** The ack. When the `89h` arrives in
  RX, the Z80 has read the whole pass, `00h` included. The PIO dropped Y
  when the Z80 sent it, so there's no race to drop READY. That gives the
  rule: never two passes in flight, and never an answer while one is
  in flight.
- **"Y/N prompt last."** A keep-alive can only come before the answer. After
  an 81h, 86h or 88h function has run, the command is over and the ROM reads
  nothing more, so no pass may follow. The prompts keep refusing before they
  ask (#291's `RM_CHECK`: after `SEND_MSG_PROMPT_YN` only the log hears
  the Pico): a keep-alive comes before the refusal checks, and the prompt is
  still the last thing sent.
- **No forgotten keep-alive.** Every answer builder (`SEND_MSG`,
  `SEND_STATUS`, `SEND_MSG2`, `PROMPT_EACH`, `ListMenu`,
  `SEND_MSG_PROMPT_YN`, `CH_REPLY`) and `FAIL_CMD` call `KEEP_ALIVE_END()`
  first. When none is running, that's one test. A handler that raises
  mid-work still answers correctly: `FAIL_CMD` ends the keep-alive before it
  sends the status. `PROCESS_CMD`'s `CmdAbort` path just drops the state,
  because the Z80 has gone.
- **Memory.** The state is a few module-level ints and a 4-byte
  `bytearray` made at import. No objects are kept between commands
  ([appendix/memory.md](reference/appendix/memory.md)).

### When the bus is free

On v3 the card has its own SPI pins (`board_v3.sd_take_bus` leaves the bus
as it is), so a pass can go out while the card is mounted, inside an
`SD_CALL`. On v2 the bus state machine is parked while the card has GPIO 2–4,
so there `KEEP_ALIVE()` does nothing while `sd_active` (a board flag says
which kind of board it is). v2 gets keep-alives only between SD phases. That
is enough for what v2 does: v2 has no WiFi, and its long operations are
single SD calls.

### Reaching code that doesn't know about the 2068

The WiFi code is in `board_v3.py`. A module-level hook, `board.busy = None`,
which `KEEP_ALIVE_START` sets to `KEEP_ALIVE` and `END` sets back to
`None`. The loops that wait call `if busy: busy()`: `wifi_get`'s
`readinto` loop, `_esp_wait`, `_esp_address`. The same goes for the slow
loops in `tspico.py`: `NET_INFLATE`'s `readinto` loop, `net.find`'s row loop
(every 64 rows), and `DISK_COPY_WORK`'s block loop.

### The UART

The v3 fetch has no flow control: Zimodem's stream mode, a 4 KB `rxbuf`,
~11.5 KB/s. So the fetch loop can't stop for long. The 4 KB buffer gives
about 350 ms of slack. The tick is safe there because it never waits for the
Z80:

- With no pass out, it costs a `ticks_ms()` and a compare.
- Sending a pass costs four `CMD_PUT`s into an empty FIFO and an `MQ_READY`:
  microseconds.
- Checking for the ack is an `rx_fifo()` test and, at most, one `get()`.
- The first pass, with the label, comes 1 s into the work, which may be
  mid-fetch. It is longer than four bytes, but `CMD_SEND` hands everything
  past the first four to the DMA channel (`CAN_STREAM()` is true on v3), so
  it doesn't wait either. The label stays short (≤ 12 characters).
- The one step that does wait, `KEEP_ALIVE_END`, runs after the last byte
  has arrived.

So a bigger `rxbuf` isn't needed. To prove it, the hardware pass fetches the
46 KB index with the spinner running and checks the result. A dropped byte
breaks the gzip CRC, which `NET_INFLATE` already reports as "Can't unpack
the index". If it ever fails, the fallback is to tick only between
`wifi_get` and the SD phases; each of those is well under 19.9 s.

## The first users

1. **`tpi:net find`'s first run.** One command fetches, unpacks and
   searches. `NET_FIND_MS` and the "Now SAVE "tpi:net find …" again" answer
   go.
2. **`tpi:net update`** (fetch + unpack ~13 s, close to the limit today)
   and **`tpi:net <n>`'s download** of a tape.
3. **The ESP32's slow starts.** A cold boot (`ESP_BOOT_MS` 8 s), a join
   (`ESP_JOIN_MS` 10 s) and the first byte of a fetch (`ESP_FIRST_MS` 15 s)
   can add up to more than 19.9 s. Today the code relies on them not doing
   so.
4. **Long COPYs on v3** (`DISK_COPY_WORK`'s loop, with the card mounted).
   On v2 a COPY stays one SD call, as today.
5. **SD mounts.** `ACTIVATE_SD`'s retries are capped by `SD_TRY_MS` (6 s),
   so a mount by itself fits. The keep-alive matters when a mount comes
   after other slow work in the same command. Nothing changes in
   `ACTIVATE_SD` itself.

A side benefit: BREAK now stops a long operation at the next tick (Report
D, the fetch closed, the card unmounted). Today the Z80 sends its BREAK
while waiting, and the firmware sees it only after the work is done.
`NET_INFLATE` must then not leave a half-written index behind, since the
next find would trust it. It writes to a temporary name and renames at the
end, or removes the file in a `finally` unless it finished.

## Tests

- **ROM, in the Z80 interpreter** (`src/test/rom_keepalive_hosttest.py`,
  like `rom_fn86_hosttest.py`, against the committed ROM image). A
  simulated Pico answers a command with: 89h passes then 01h (OK, stack
  depth unchanged after 1000 passes); passes then a report (A = status −
  1); passes then 81h text and an 86h page; a pass and then silence (J at
  ~19.9 s of polls); a pass and then 00h (J). It also checks that every
  pass's ack is `89h` and comes after the `00h`.
- **Firmware, in the simulated bus** (`cmd_io_hosttest.py`'s Z80 and PIO).
  Ticks while "working", then each answer builder. It checks: TX ends `[01]`,
  RX is empty, Y is `FF`, and no `put()` goes into a full TX. BREAK during
  a pass and during the gap between passes gives `CmdAbort(1)`. A Z80 that
  stops acking gives `CmdAbort(3)`. A fast command sends no pass.
- **ZEsarUX** (`tools/emu`, the real firmware behind the emulator): first
  `CHR$ 8` on the lower screen, then a test command (`tpi:` debug
  `kawait n`, n seconds of ticks, kept only if you want it) running 30 s
  and 60 s, with BREAK halfway.
- **A v3 card on a 2068.** `kawait 60`. A first `tpi:net find` with no index
  on the card, in direct mode and from a program line, so we can see that the
  label is wiped. BREAK during the fetch, then a find that must refetch.
  A long COPY.

## The reference

In the same PR, by the `CLAUDE.md` routine:

- `rom/exrom-fdd.md`: a `KEEP_ALIVE` entry and its map row, and the module's
  size in the opening.
- `rom/exrom-chunk1.md`: the chain table, the `FN_DEAD_BEEP` section (2218h is
  now the 89h link), and BEEPER's callers.
- `rom/overview.md` and `ROM_CHANGES.md`: the patch and the new CRC.
- `PROTOCOL.md` §5.4: an 89h row, and the 80h/89h–FFh row becomes 80h/8Ah–FFh.
  Also a §13 pitfall: "never two passes in flight; END before any answer".
- `firmware/tspico-bus.md`: the helpers. `tspico-messages.md`: the
  answer-on-the-wire table. `board-v3.md`: `busy`. And the NET entries.
- `flows/` for the net commands, if one follows `tpi:net`.
- `flash/manifest.json`: slot 1's CRC.

## An alternative from the review: the border (Gustavo, #409)

Gustavo suggested, on the PR, a change to the ROM's wait loop instead of a
spinner, at the point where it tests READY (bit 6 of the status). While the
2068 waits, the loop changes the border color: a steady color, alternating
colors, or two-tone bars like the tape loader's. The border could show three
states: waiting; still waiting after NN ms; and a timeout.

### What it does and doesn't do

- **It doesn't lift the limit.** The ready-wait still counts 226 polls, and
  only something the Pico sends can restart it. So 89h is still needed for
  any work longer than ~19.9 s. The border is a way to *show* the wait, not
  to extend it.
- **It shows on every command, with no firmware change.** Any wait longer
  than the threshold shows: a slow mount, a big listing, an ESP32 starting
  up. The spinner shows only where the firmware calls `KEEP_ALIVE()`.
- **Combined with 89h, it simplifies the keep-alive.** If the border says
  "busy", a pass needn't print anything: it is `89h, 00h`. Then the
  lower-screen `CHR$ 8` question, the label, the wiping pass and the
  choice of screen all go away. The program's screen is never touched.

### Where it would go

- **The poll.** 1A58h, `CALL RD_STATUS` (234Fh), becomes `CALL WAIT_POLL`,
  a new routine in the module. It does what RD_STATUS does (READ_STATUS, the
  READY test, the RECOVERED test), plus the border.
  - **The threshold** is a count of polls, about 88 ms each. B counts down
    from E2h (226); after 12 polls (B ≤ D6h, about 1 s) the border starts
    to change. Waits shorter than that, which is nearly all of them, show
    nothing, so fast commands don't flicker.
  - **The pattern** comes from B, one color step per poll. Colors are
    written with `OUT (FEh)`, bits 0–2, with bit 4 (the beeper) kept at 0,
    as the stock code does.
  - **READY** puts the border back from BORDCR (5C48h, bits 3–5) before
    returning.
- **The exits that must put the border back** (BORDCR, as the SAVE prompt's
  BREAK routine at 22AEh already does):
  - **READY**: in `WAIT_POLL` itself.
  - **Timeout**: `WAIT_PICO_READY_FAIL` (1A61h) starts with 7 dead bytes
    (`LD A,40h` and five `NOP`s); a `CALL` to the restore fits there.
  - **BREAK**: `BRK_ABORT` (231Eh): its `CALL 230Eh` at 2322h becomes a
    `CALL` to a restore that then jumps to 230Eh. Key prompts reach
    `BRK_ABORT` too, which is harmless: the border is BORDCR's there anyway.
  - **Report T**: inside `WAIT_POLL`, before its `RST 8`.
- **The other wait.** `BIOS_WF_NPH` (239Eh) is the wait for the BIOS
  callers, which include the disk keywords (CAT, COPY …, through
  `C_END2`). It needs the same treatment, or a disk keyword's wait shows
  nothing.

### Combining it with 89h

`KEEP_ALIVE` calls `WAIT_PICO_READY`, whose count starts again at 226 on
each pass, and the READY at each pass restores the border. With a pass
every 250 ms the border would never show. Two ways out:

1. **The firmware sends passes rarely.** One every 10 s (half the budget)
   is enough to keep the 2068 waiting. The border then shows for all but
   about a second after each pass.
2. **Keep the count across passes.** It lives in a spare byte of system
   RAM instead of B, so a keep-alive's wait carries on where the last one
   stopped. That needs a free byte the ROM owns (the TS-Pico's own 5DCxh
   bytes, [sysvars.md](reference/rom/sysvars.md)). It's neater but takes
   more bytes and more checks.

Option 1 needs no extra ROM. I'd start there.

### The timeout signal

A timeout ends in Report J at once, which clears the lower screen and
prints the report. A timeout color would show only for that moment, unless
the ROM leaves it on, and then the border would stay wrong until the next
CLS. The report already says what happened, so I'd leave the border
alone at a timeout. It's worth hearing what Gustavo had in mind for this
state.

### Testing it

The Z80-interpreter test gains port FEh: the border changes only after the
threshold, and every exit (READY, timeout, BREAK, T) leaves it at
BORDCR's color. In ZEsarUX and on a 2068, `kawait 60` with the border
watched, and a short command watched for flicker.

## Questions for you

1. **ROM 2.5**, with the firmware checking `rom_id` before it sends 89h:
   agreed?
2. **The spinner, the border, or both?** My suggestion is both together in
   the combined form: 89h with no text, a pass every 10 s, the border
   showing the wait. That way every slow command shows something, and the
   screen is never written to.
3. If there's a spinner: **the lower screen** (recommended), or the main
   screen?
4. A debug command (`kawait n`) for the tests: keep it in the firmware,
   or test-only?
