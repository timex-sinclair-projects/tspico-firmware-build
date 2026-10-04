# The TS-Pico emulator bridge, version 1

How a TS-2068 emulator talks to `pico_host` (`tools/emu/pico_host.py`, or the
standalone `pico_host` binary), which runs the real TS-Pico firmware. This is
the one thing an emulator has to implement to get a TS-Pico. ZEsarUX does it
(`tools/emu/zesarux-tspico.patch`); FUSE and TSRun are next (issue #35).

## 1. What the emulator does

On a TS-2068 (and only then), every Z80 I/O access whose **low address byte** is
`0Eh` or `0Fh` goes to the bridge instead of the emulated bus. The TS-Pico board
decodes only the low byte, so `OUT (0Eh),A`, `OUT (C),A` with C = 0Eh and any
B, and so on, all count. Other ports are untouched. ZX48 mode needs nothing
more: the Spectrum ROM uses the same two ports.

For each access the emulator sends one **frame** and, before the Z80 instruction
completes, waits for one reply byte:

| Op | Z80 access | Value sent | Reply |
|----|-----------|------------|-------|
| 0 | `OUT (0Eh)` | the byte written | ignored (0) |
| 1 | `IN (0Eh)` | 0 | the byte the Z80 reads |
| 2 | `IN (0Fh)` | 0 | the status byte the Z80 reads |
| 3 | `OUT (0Fh)` | the byte written | ignored (0) |
| 4 | *HELLO* (no Z80 access) | the bridge version the emulator speaks: `1` | the version `pico_host` speaks: `1` |

A frame is two bytes, `[op, value]`; the reply is one byte. Exchanges are
strictly one at a time: the Z80 stops at the access until the reply comes, so
the order of frames is exactly the order of the Z80's port accesses.

- **HELLO** is optional, and if sent comes first. An emulator that skips it gets
  version-1 behaviour; future versions will be told apart by it.
- **No connection:** run as if the TS-Pico weren't plugged in. `IN (0Fh)` reads
  `FFh` and `IN (0Eh)` reads `00h`, so the ROM's commands fail with a report
  instead of hanging. Try connecting once, at the first access to `0Eh`/`0Fh`,
  and again after a reset of the emulated machine. Reconnecting on every access
  would stall the emulator.
- **Lost connection:** fall back to "not plugged in" until the next reset.

## 2. Transport

`pico_host` listens on both:

- **TCP `127.0.0.1:2068`** (`--tcp HOST:PORT`, or `--tcp ""` to turn it off).
  Use this one where you can: it works the same on macOS, Linux and Windows,
  and in a browser it can be bridged to a WebSocket. Set `TCP_NODELAY`, because
  every frame is a round trip.
- **Unix socket `/tmp/tspico_bridge.sock`** (`--unix PATH`, or `$TSPICO_BRIDGE_SOCK`),
  on macOS and Linux. The ZEsarUX patch in this repo uses it today.

The emulator connects as the client. One emulator at a time; a second connection
waits until the first closes.

An emulator should let the user choose, for example with an environment variable
`TSPICO_BRIDGE`, which takes `tcp:HOST:PORT` or `unix:PATH`. The default is
`tcp:127.0.0.1:2068`.

## 3. What `pico_host` does with them (for reference)

This is the model of the TS-Pico's bus state machine, `TS_IO_DUAL`, the firmware
runs against. An emulator needs none of it, but it explains the replies:

- **Writes** (ops 0 and 3) go into a receive queue as 9-bit words. A write to
  `0Fh` sets bit 8, which is how the firmware tells SYNC and BREAK from data.
  Every write also sets the status byte to `00h` ("busy"), as the board's PIO
  does.
- **The status byte** (op 2) is what the firmware last set it to: `FFh` ready +
  idle, `F7h` ready with a command open, `FBh` "TS-Pico reset, try again",
  `00h` busy. See `docs/PROTOCOL.md` §3.
- **Reads of `0Eh`** (op 1) take the next byte the firmware has queued. With
  nothing queued they read `00h`, as the real FIFO does. `pico_host` counts these
  "underruns" and prints the count when the emulator disconnects.

## 4. Timing: what the bridge doesn't model

Every port access is a round trip, and nothing runs against the 2068's bus
clock. The firmware's timing-critical paths (DMA, the 4-deep FIFOs, the ROMs'
blind reads) therefore behave as they would on hardware with infinite slack.
The bridge shows whether the ROM and the firmware agree. It can't show a FIFO
running dry or overflowing because the Pico was late: that needs the real
board.

## 5. Versions

| Version | Change |
|---------|--------|
| 1 | Ops 0-3 (as in the June 2026 ZEsarUX patch), op 4 HELLO, TCP alongside the Unix socket. |
