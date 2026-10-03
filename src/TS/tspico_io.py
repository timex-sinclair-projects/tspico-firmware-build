import gc
import os
import select
import sys
import time
import utime

from rp2 import StateMachine, asm_pio, PIO
from machine import Pin, freq, SPI

from TS.sdcard import *
from TS import native

# ─── READ THIS BEFORE ADDING AN IMPORT TO THIS FILE ─────────────────────────
# tspico_io.py is built into TWO firmwares, not one:
#
#   * the TS-Pico firmware (src/manifest.py), which has every TS module, and
#   * the UPGRADE firmware (src/upgrade/manifest.py) -- the UF2 the web
#     updater writes to put a new ROM in flash slots 0 and 1. It freezes only
#     the few modules it needs: TS/__init__, tspico_io, sdcard and native.
#
# A module-level import added here that the upgrade firmware doesn't have
# makes the upgrade UF2 die at boot with ImportError, before it has selected
# a ROM: the 2068 just beeps, and nobody can update their ROM. That happened
# from #82 (`from TS import native`) until it was caught on hardware on
# 2026-10-01. So a new module-level `from TS ...` / `import TS....` here
# needs ALL of:
#
#   1. a freeze() line in src/upgrade/manifest.py;
#   2. the file added to the `cp ... $M/modules-upgrade/TS/` line in BOTH
#      .github/workflows/build.yml and .github/workflows/release.yml;
#   3. no imports of its own beyond what the upgrade firmware has.
#
# src/test/upgrade_hosttest.py checks 1 and 2 and fails CI if they're
# missing. An import inside a function (like SAVE_TS's lazy
# `from TS.tspico import TLM`) is fine, as long as the upgrade code never
# calls that function. See docs/DEVELOPER_GUIDE.md, "The upgrade UF2 is a
# second build of tspico_io.py".
# ─────────────────────────────────────────────────────────────────────────────

# ---------------------------------------------------------------------------
# Module-level state. (The core1 watchdog's kill / busy / dead flags went with
# it in issue #51; the last of them were removed by the 2026-09-30 audit, §3.)
# ---------------------------------------------------------------------------

log_entries = ""    # log messages collected during a transaction

# Cached "no file mounted" fallback handle.
#
# When LOAD "" is issued without a prior mount (no f_name set in TSP),
# LOAD_TS streams /assets/nofile.tap as a friendly "no file mounted"
# message. Opening that file inside LOAD_TS takes ~5ms on cold flash
# metadata — which is enough time for the Z80 to race through its
# data loop reading stale 0x00s before we've written a single byte,
# resulting in a Report J error.
#
# Solution: pre-open nofile.tap at boot (or first lazy access) and
# reuse the handle. The seek + readinto inside LOAD_TS is then sub-ms,
# and Pico writes the first content byte before Z80's read race
# overshoots.
#
# `OPEN_NOFILE_TAP()` is called once during TS2068_IO()'s setup phase
# in tspico.py. After that, LOAD_TS uses the cached handle directly.
_nofile_arch = None


# ---------------------------------------------------------------------------
# BREAK / SYNC support (issue #51). Proven on hardware by
# src/test/abort_harness.py with the 1.8b "sync" test ROM
# (src/rom/TSPICO-SYNC.ROM); see the TS-Pico BREAK abort proposal.
#
# A Z80 write to port 0Fh lands in the RX FIFO like any other write, but
# with A0 in bit 8: 0x100 | value. The 1.8b ROM writes 03h there to open
# every command (SYNC) and to report BREAK, then waits up to ~1 s for status
# READY (bit 6) + IDLE (bit 3). ROMs up to v1.7 never write to 0Fh, so none
# of this changes anything for them.
# ---------------------------------------------------------------------------
from array import array

PORT_0F = const(0x100)          # bit 8 of an RX word: the Z80 wrote port 0Fh
TX_DEPTH = const(4)             # TS_IO_DUAL's FIFOs are not joined

# LOAD streams file data through this, a chunk at a time. Reading one byte
# per readinto() call cost too much per byte on MicroPython v1.29: the ROMs
# read blind every ~43-47 us, and the log showed "TX ran dry" in 6914-byte
# blocks on both the 2068 and ZX48 paths (hardware, 2026-10-02). Made once,
# here, so the stream loops allocate nothing.
LOAD_CHUNK = const(256)
_LOAD_BUF = bytearray(LOAD_CHUNK)
_LOAD_MV = memoryview(_LOAD_BUF)


# ─── Fast exec: MQX(MQ, ) without the per-call assembler ───────────────
# MicroPython 1.20's StateMachine.exec() runs the Python-level PIO
# assembler (rp2.asm_pio_encode) on EVERY call, string or not: 9.6 ms a
# call on this Pico (measured 2026-09-27), against 18 us for writing the
# encoded instruction straight to the state machine's INSTR register --
# which is all pio_sm_exec() does. Every LPRINT / LLIST character is a
# whole transaction with a few execs, so a program listing crawled at
# ~30-40 ms a character and looked hung. MQ is always PIO0 SM0. The
# encoding depends on the loaded program's side-set configuration, so it
# is cached per (instruction, side-set). On the host (no machine.mem32)
# MQX falls back to MQX(MQ, ), so the simulated PIO still sees the text.
try:
    from machine import mem32 as _mem32
except ImportError:
    _mem32 = None
_SM0_EXECCTRL = const(0x502000CC)
_SM0_INSTR = const(0x502000D8)
_SM0_PINCTRL = const(0x502000DC)
_ENCODED = {}


def MQX(MQ, instr):
    """MQX(MQ, instr), ~500x faster on the Pico. Allocation-free once the
    instruction has been seen with this side-set configuration."""
    if _mem32 is None:
        MQ.exec(instr)
        return
    ss = (_mem32[_SM0_PINCTRL] >> 29) | (((_mem32[_SM0_EXECCTRL] >> 30) & 1) << 3)
    by_ss = _ENCODED.get(instr)
    if by_ss is None:
        by_ss = _ENCODED[instr] = {}
    code = by_ss.get(ss)
    if code is None:
        import rp2
        code = by_ss[ss] = rp2.asm_pio_encode(instr, ss & 7, ss >> 3)
    _mem32[_SM0_INSTR] = code


def MQ_STATUS(MQ, st):
    """Set what the Z80 reads on port 0Fh (the PIO's Y register).

        "idle"       0xFF  ready, no transaction open -- what firmware has
                           always shown, so older ROMs see no difference
        "mid"        0xF7  ready, transaction open (IDLE, bit 3, clear)
        "recovered"  0xFB  ready + idle, RECOVERED (bit 2, active low): this
                           Pico gave up on a transaction by itself. The 1.8b
                           ROM reports "T TS-Pico reset, try again"; its next
                           SYNC clears it. Older ROMs only test bit 6.

    mid/recovered take two exec()s; the moment in between reads as busy.
    No logging here: this runs on time-critical paths.
    """
    if st == "idle":
        MQX(MQ, "mov(y, invert(null))")
    elif st == "mid":
        MQX(MQ, "set(y, 8)")
        MQX(MQ, "mov(y, invert(y))")
    else:
        MQX(MQ, "set(y, 4)")
        MQX(MQ, "mov(y, invert(y))")


def RX_CAPTURE(MQ, raw, n, stall_ms):
    """Take a burst of n words from the Z80 into raw, an array('H') (the
    words are 9-bit). Returns:

        n          the whole burst arrived
        k, 0<=k<n  k words, then stall_ms of silence
        -k         word k-1 was a write to port 0Fh (SYNC or BREAK); the Z80
                   is now waiting for READY + IDLE

    The two-phase rule (src/CLAUDE.md): the loop does nothing per word but
    test the FIFO, get and store -- the Z80 writes every ~30 us and the FIFO
    holds 4. The 0Fh test and the clock run only when the FIFO is empty,
    which is exactly when the Z80 has paused or stopped; a 0Fh write is
    always the last thing it sends before it stops.
    """
    # No `rx = MQ.rx_fifo` here: storing a bound method allocates, and an
    # allocation can start a GC right as the Z80's burst begins -- the
    # 4-deep FIFO overflows and bytes go missing from the middle of the
    # pre-header ("Partial pre-header 8/10" -> RECOVERED -> Report T,
    # hardware 2026-09-27). Direct calls allocate nothing.
    got = 0
    while got < n:
        if MQ.rx_fifo():
            raw[got] = MQ.get()
            got += 1
        else:
            if got and raw[got - 1] & PORT_0F:
                return -got
            t0 = time.ticks_ms()
            while not MQ.rx_fifo():
                if time.ticks_diff(time.ticks_ms(), t0) >= stall_ms:
                    return got
    if raw[n - 1] & PORT_0F:
        return -n
    return n


_stdin_ipoll = None           # set up on first DRAIN_STDIN: poll(0) on sys.stdin
_stdin_readinto = None
_stdin_byte = bytearray(1)


def DRAIN_STDIN(MQ, limit=1024):
    """Throw away text the host sent to the running firmware, so a later
    Ctrl-C still reaches it. Returns the number of bytes dropped.

    MicroPython (rp2; v1.20, and still v1.29 in shared/tinyusb/
    mp_usbd_cdc.c) sees Ctrl-C only while moving USB bytes into its
    512-byte stdin ring buffer (tud_cdc_rx_cb). The firmware never
    reads stdin, so once 511 bytes of anything else have arrived -- a
    tool writing before its Ctrl-C landed, a terminal echoing telemetry
    back -- the buffer is full, every later byte waits in TinyUSB behind
    it, and Ctrl-C is never looked at. The Pico runs on but USB is deaf
    until a reset (hardware, 2026-09-28: 600 bytes, then no Ctrl-C ever
    got through). Polling stdin moves the waiting bytes along, and that
    is what spots a Ctrl-C: KeyboardInterrupt comes out of this call.

    Run it from the idle loop's heartbeat only. It allocates nothing (the
    bound methods are made once, ipoll reuses its tuple), and it stops at
    the first byte from the Z80: a pre-header arrives 30 us a byte into a
    4-deep FIFO.
    """
    global _stdin_ipoll, _stdin_readinto
    if _stdin_ipoll is None:
        p = select.poll()
        p.register(sys.stdin, select.POLLIN)
        _stdin_ipoll = p.ipoll
        _stdin_readinto = sys.stdin.buffer.readinto
    n = 0
    while n < limit and not MQ.rx_fifo():
        for _ in _stdin_ipoll(0):
            break
        else:
            return n                        # nothing waiting
        _stdin_readinto(_stdin_byte)
        n += 1
    return n


def MQ_TO_IDLE(MQ, recovered=False, status=True):
    """The one way back to a known state, whatever happened: TX and RX empty,
    exactly one 0x01 pre-load staged (the ROM reads it with no wait straight
    after the next pre-header), status idle -- or recovered.

    status=False leaves Y alone, so the caller decides when the Z80 may go
    on. After a SYNC the Z80 waits for IDLE: that is the moment to do slow
    work (logging, gc), before setting it -- never after.

    Bounded: the FIFOs are 4 deep, so a few passes are enough; spinning
    longer means the SM isn't draining, and this path must never hang.
    """
    for _ in range(64):
        if MQ.tx_fifo() == 0:
            break
        MQX(MQ, "pull (noblock)")
        MQX(MQ, "mov (osr, null)")
    for _ in range(64):
        if MQ.rx_fifo() == 0:
            break
        MQ.get()
    if MQ.tx_fifo() < TX_DEPTH:
        MQ.put(0x01)
    if status:
        MQ_STATUS(MQ, "recovered" if recovered else "idle")


def TX_ROOM(MQ, echo, stall_ms=3000):
    """LOAD's slow path. TX is full, so the Z80 hasn't read the last byte
    yet: wait for room, listening, instead of blocking in MQ.put(). Returns

        0   there is room
        1   a write to port 0Fh -- BREAK, or a new command's SYNC after a
            2068 reset. The Z80 has stopped reading and waits for IDLE.
        3   TX stayed full for stall_ms: the Z80 has gone away.

    (2 was "the watchdog fired"; the core1 watchdog was removed in #51.)

    Data bytes the Z80 writes meanwhile (the block-type echo it sends just
    before its data loop) are kept in echo, a bytearray(3) of [count, byte,
    byte] (see ECHO_KEEP) -- never a list: this runs while the Z80 is
    streaming, and a list append can allocate, and an allocation can start
    a GC that stops core0 for 15-25 ms. The Z80 reads a byte every 50 us
    from a 4-deep FIFO, so that pause is ~300 empty reads and Report R.
    """
    # Call MQ's methods directly -- never `txf = MQ.tx_fifo` here. Storing a
    # bound method allocates it (16 bytes), and this runs once per byte of a
    # LOAD: 32 bytes a call filled the heap every ~6.5 KB, and each GC froze
    # the Pico ~6 ms mid-block while the Z80 read ~110 empty bytes. Report R
    # on every block over ~6 KB (hardware, 2026-09-27). A direct call
    # allocates nothing.
    t0 = time.ticks_ms()
    while MQ.tx_fifo() >= TX_DEPTH:
        if MQ.rx_fifo():
            w = MQ.get()
            if w & PORT_0F:
                return 1
            ECHO_KEEP(echo, w)
        elif time.ticks_diff(time.ticks_ms(), t0) >= stall_ms:
            return 3
    return 0


def ECHO_KEEP(echo, w):
    """Keep the Z80's echo byte w in echo = bytearray(3): [count, block
    type, CRC]. Anything past the second is dropped, as before. No
    allocation (see TX_ROOM)."""
    n = echo[0]
    if n < 2:
        echo[n + 1] = w & 0xFF
        echo[0] = n + 1


def RX_WORD(MQ, stall_ms):
    """One word from the Z80, or -1 after stall_ms of silence -- never the
    unbounded wait of a bare MQ.get()."""
    if not MQ.rx_fifo():
        t0 = time.ticks_ms()
        while not MQ.rx_fifo():
            if time.ticks_diff(time.ticks_ms(), t0) >= stall_ms:
                return -1
    return MQ.get()


# RX_BLOCK's result codes
RXB_OK = const(0)       # all n bytes arrived
RXB_ABORT = const(1)    # a write to port 0Fh (BREAK / SYNC); the Z80 waits for IDLE
RXB_STALL = const(3)    # silence: first_ms before the first byte, stall_ms after


def RX_BLOCK(MQ, buf, n, first_ms, stall_ms):
    """Take a SAVE data block of n bytes from the Z80 into buf (a bytearray).
    Returns (code, words taken), code one of RXB_*.

    The Z80's SAVE loop OUTs a byte every ~43 us with no handshake and the RX
    FIFO holds 4, so the per-byte path is only: test the FIFO, get, store.
    The port-0Fh test, the watchdog flag and the clock run only when the FIFO
    is empty -- exactly when the Z80 has paused or stopped. A 0Fh write
    (0x100 | value) is always the last thing it sends before it stops, so it
    is the newest word then; `w` keeps it (buf only holds the low 8 bits).

    Allocation-free per byte: the bound methods are taken ONCE per call.
    Storing one per byte (as TX_ROOM once did) allocates 16 bytes each time,
    and the GCs that follow freeze the Pico mid-block -- see alloc_probe.py.
    """
    rx = MQ.rx_fifo
    get = MQ.get
    got = 0
    w = 0
    limit = first_ms
    while got < n:
        if rx():
            w = get()
            buf[got] = w & 0xFF
            got += 1
        else:
            if w & PORT_0F:
                return RXB_ABORT, got
            t0 = time.ticks_ms()
            while not rx():
                if time.ticks_diff(time.ticks_ms(), t0) >= limit:
                    return RXB_STALL, got
            limit = stall_ms
    if w & PORT_0F:
        return RXB_ABORT, got
    return RXB_OK, got


# The SAVE header block, as 9-bit words (bit 8 = a port-0Fh write).
_SAVE_HDR_RAW = array("H", bytes(42))


def OPEN_NOFILE_TAP():
    """Pre-open /assets/nofile.tap and cache the handle.

    Called once during boot from TS2068_IO(). LOAD_TS uses the cached
    handle (with seek + readinto) instead of paying the file-open cost
    inside the time-critical protocol response path.

    Idempotent: calling more than once just leaves the existing handle
    in place. Returns True on success, False if the file is missing
    (in which case the user needs to install /assets/ on the Pico).
    """
    global _nofile_arch
    if _nofile_arch is not None:
        return True
    try:
        _nofile_arch = open("/assets/nofile.tap", "rb")
        return True
    except OSError:
        # /assets/nofile.tap not installed on the Pico's flash. LOAD ""
        # without a mount will fail until the user copies the assets/
        # files into /assets/ via Thonny (per README "Deploy to the
        # Pico" §5).
        _nofile_arch = None
        return False


@asm_pio(                                       # Bank selection via A15..A18
    out_init=(PIO.OUT_LOW, ) * 4, 
    out_shiftdir=PIO.SHIFT_RIGHT,
    autopull=True,
    pull_thresh=8,
    )
def sel_bank():
    wrap_target()
    pull(noblock)
    mov(x, osr)
    wait (0, gpio, 13)
    jmp(pin, "low")
    out(null, 4)
    out(pins, 4)
    jmp("fin")
    label("low")
    out(pins, 4)
    label("fin")
    wait (1, gpio, 13)
    wrap()
    

@asm_pio(                                       # Control lines: /BE, A14_L, /U10_CE /U10_OE
    set_init=(PIO.OUT_HIGH, ) * 2,
    in_shiftdir=PIO.SHIFT_LEFT,
    out_init=(PIO.OUT_HIGH, ) * 2,
    out_shiftdir=PIO.SHIFT_RIGHT,
    autopull=True,
    pull_thresh=8,
    )
def set_ctrl():
    wrap_target()
    mov(pins, invert(null))
    mov(y, null)
    set(pins, 3)
    pull(noblock)
    mov(x, osr)
    wait (0, gpio, 13)
    nop()                  [2]
    jmp (pin, "low")
    out(null, 2)
    out(pins, 2)
    jmp("pass")
    label("low")
    in_(pins, 2)
    mov(y, isr)
    mov(isr, null)
    jmp(y_dec, "home")
    set(pins, 2)
    jmp("wait")
    label("home")
    jmp(y_dec, "pass")
    set(pins, 0)
    label("wait")
    nop()                  [10]
    out(pins, 2)
    label("pass")
    wait (1, gpio, 13)
    wrap()


@asm_pio(                                       # Control lines /U10_CE /U10_OE only; for DCK access with not ROM mapping
    out_init=(PIO.OUT_HIGH, ) * 2,
    out_shiftdir=PIO.SHIFT_RIGHT,
    autopull=True,
    pull_thresh=8,
    )
def set_dck():
    wrap_target()
    mov(pins, invert(null))
    pull(noblock)
    mov(x, osr)
    wait (0, gpio, 13)
    nop()                  [2]
    jmp (pin, "pass")
    out(null, 2)
    out(pins, 2)
    jmp("pass")
    label("pass")
    wait (1, gpio, 13)
    wrap()


@asm_pio(
    sideset_init=(PIO.OUT_HIGH),
    out_init=(PIO.OUT_LOW,) * 8,
    out_shiftdir=PIO.SHIFT_RIGHT,
    in_shiftdir=PIO.SHIFT_LEFT,
)
def TS_IO_DUAL():
    """Dual-port PIO state machine — implements Gustavo's TPI v2.4 protocol.

    Two virtual ports share the same 8-bit data bus:
      Port $0E (data, addr LSB=0):
        Z80 IN  : Pico drives a byte from the TX FIFO onto D0-D7
        Z80 OUT : Pico samples D0-D7 from the bus into the RX FIFO

      Port $0F (status, addr LSB=1):
        Z80 IN  : Pico drives the value of scratch register Y onto D0-D7
                  (Y is independent of the FIFO — it does NOT consume bytes)
        Z80 OUT : same as $0E (we don't differentiate writes by port; the
                  high bit of the 9-bit RX value tells Python which port)

    The Z80 ROM uses port $0F as a "ready/continue" flag. It polls $0F
    in a tight loop and checks BIT 6 of the value. If BIT 6 is set, the
    Z80 proceeds; otherwise it keeps polling (with a long timeout — see
    docs/PROTOCOL.md). MicroPython controls the ready flag like this:

        sm.exec("mov(y, invert(null))")   # Y = 0xFFFFFFFF (bit 6 set)
                                          # → port $0F reads as 0xFF
                                          # → Z80 sees "ready"

        sm.exec("set(y, 0)")               # Y = 0 → port $0F reads 0x00
                                          # → Z80 sees "not ready", waits

    For the standard LOAD path, Y is set to READY at startup and never
    changed. Pico paces the data flow via TX FIFO depth (4 bytes), and
    Z80 reads bytes at ~47µs each — far slower than MicroPython can
    `MQ.put()` them, so streams keep up naturally.

    *** WHY pull(noblock) AND NOT pull(block) ***

    pull(block) sounds appealing — it would make the SM stall until the
    TX FIFO has data, giving Pico unlimited time to respond. BUT the
    TS-Pico hardware does NOT route the SM's stall to the Z80 /WAIT line.
    A stalled SM means subsequent /PICOSEL transitions go undetected
    and the bus hangs.

    With pull(noblock), if the FIFO is empty when Z80 reads $0E, the SM
    drives the X register (= A0 bit, normally 0) onto the bus. So the
    Z80 reads 0x00 — which the Z80 ROM interprets as "Report J / Invalid
    I/O Device". This is actually USEFUL behavior: it forces us to keep
    the FIFO pre-loaded with the right bytes at the right time, which
    is the protocol contract anyway.

    Pin assignments (unchanged from single-port TS_IO):
      GPIO 2-9   = D0-D7        (out_base / in_base)
      GPIO 10    = A0           (bit 8 of in_(pins, 9) — port decode)
      GPIO 11    = R/W select   (jmp_pin: 1=Z80 OUT/write, 0=Z80 IN/read)
      GPIO 12    = U6 buffer enable (sideset, active LOW during transaction)
      GPIO 14    = /PICOSEL     (wait gpio, active LOW = bus cycle)

    Run at freq=30_000_000. The dual-port decode adds ~7 cycles to the
    read path vs. single-port; 30MHz keeps the total under the Z80's
    data setup window with margin. RP2040 PIO can run up to half the
    system clock (135MHz at 270MHz CPU), so 30MHz is conservative.

    Total: 19 instructions of 32 available.

    ABOUT PIO INSTRUCTIONS (helpful background for newcomers):
      - Every instruction also sets GPIO 12 via the `.side(0|1)` clause.
        sideset(1) = U6 buffer DISABLED (Pico off the bus, idle).
        sideset(0) = U6 buffer ENABLED  (Pico drives or reads the bus).
      - ISR = Input Shift Register, OSR = Output Shift Register.
        `in_(pins, N)` shifts N pins INTO ISR's low N bits (SHIFT_LEFT).
        `out(dst, N)` shifts N bits OUT of OSR's low N bits (SHIFT_RIGHT).
      - X and Y are scratch registers (32-bit).
      - `jmp(pin, "lbl")` jumps if jmp_pin (= GPIO 11) is HIGH.
      - `pull(noblock)` moves TX FIFO → OSR; if FIFO empty, copies X into OSR.
      - `push(noblock)` moves ISR → RX FIFO; if FIFO full, drops the value.
    """
    # ============================================================
    # IDLE STATE — wait for the Z80 to start a bus cycle on $0E or $0F
    # ============================================================
    # /PICOSEL is the chip-select line driven by the TS-Pico's address
    # decoder hardware. It goes LOW when the Z80 reads or writes either
    # of our two ports. While idle (waiting), sideset(1) keeps U6 OFF
    # so we don't fight the Z80 bus.
    wait(0, gpio, 14)       .side(1)      # block until /PICOSEL goes LOW

    # GPIO 11 is the R/W signal (high = Z80 is OUTting, low = Z80 INing).
    # Branch to the appropriate handler. The `.side(1)` here keeps U6
    # disabled for one more cycle while we decide which path to take.
    jmp(pin, "z80_out")     .side(1)      # GPIO 11 HIGH → Z80 OUT branch

    # ============================================================
    # Z80 IN — Pico drives data ONTO the bus
    # ============================================================
    # First we need to know which port: $0E (data) or $0F (status).
    # That's encoded in address bit 0 (A0), which the hardware routes to
    # GPIO 10. We sample 9 pins (GPIO 2..10 = D0..D7 + A0) into ISR.
    # From now on sideset(0) → U6 ENABLED → we own the bus.
    in_(pins, 9)            .side(0)      # ISR low 9 bits = D0..D7, A0

    # Now we want to extract just A0 (bit 8 of ISR). The trick: copy ISR
    # to OSR, then `out(null, 8)` discards the bottom 8 bits (D0-D7),
    # leaving A0 at OSR bit 0. Finally `out(x, 1)` moves that 1 bit into
    # the X scratch register.
    mov(osr, isr)           .side(0)      # OSR = ISR (so we can shift OSR out)
    mov(isr, null)          .side(0)      # clear ISR (good hygiene; it
                                          # gets re-used by Z80 OUT path)
    out(null, 8)            .side(0)      # discard D0-D7 from OSR (LSB end)
    out(x, 1)               .side(0)      # X = next bit out of OSR = A0

    # X = 0 means port $0E (data). X = 1 means port $0F (status).
    # `jmp(not_x, ...)` jumps if X is zero, so X=0 → take the FIFO path.
    jmp(not_x, "rd_data")   .side(0)      # X==0 → "rd_data" (FIFO read)

    # --- Port $0F (status) read: drive the Y register's value ---
    # Y is a 32-bit scratch register controlled from MicroPython via
    # sm.exec("mov(y, ...)"). We typically keep Y = 0xFFFFFFFF so port
    # $0F always reads 0xFF (which has bit 6 set = "ready").
    mov(osr, y)             .side(0)      # OSR = Y (shift source)
    out(pins, 8)            .side(0)      # drive low 8 bits of OSR onto D0-D7
    jmp("fin")              .side(0)      # done; jump to cycle-end

    # --- Port $0E (data) read: drive next byte from TX FIFO ---
    # pull(noblock): if TX has a byte, OSR = that byte. If TX is empty,
    # OSR = X register (= 0 for a $0E read, since X was just set to A0=0).
    # So an empty FIFO produces 0x00 on the bus, which the Z80 ROM
    # interprets as "Report J — Invalid I/O Device". That's the *correct*
    # behavior — it's the firmware's job to keep the FIFO populated.
    label("rd_data")
    pull(noblock)           .side(0)      # OSR = FIFO byte (or X=0 if empty)
    out(pins, 8)            .side(0)      # drive low 8 bits onto D0-D7
    jmp("fin")              .side(0)      # done

    # ============================================================
    # Z80 OUT — Pico captures the byte FROM the bus
    # ============================================================
    # Same sample-and-record pattern, but we just push to RX FIFO instead
    # of decoding A0 separately. The A0 bit ends up in bit 8 of the 9-bit
    # value that lands in RX, so MicroPython can check `(raw >> 8) & 1`
    # to know which port the Z80 wrote to (the BASIC command path uses
    # this to validate writes go to $0E rather than $0F).
    #
    # ─── Issue #14 (PIO auto-busy on Z80 OUT) ───────────────────────────
    # After every Z80 write, drop Y to 0. This signals BUSY on port $0F
    # bit 6 — telling the Z80 (per Gustavo's V5 protocol) "Pico received
    # your byte, hold off while I process it." MicroPython then calls
    # MQ_READY() when it has the response ready and the Z80's next
    # WAIT EXECUTION poll exits.
    #
    # Without this, Y stayed at whatever Python last set it to and the
    # Z80's bit-6 LEVEL check after sending data (e.g., a 0x86 scroll-
    # prompt keypress) was instantly satisfied, racing into stale or
    # empty TX FIFO. MicroPython is structurally too slow to win that
    # race; doing it in the PIO is single-cycle. See issue #14.
    #
    # Cost: +1 PIO instruction (was 19/32, now 20/32). Python-side
    # contract: anywhere Python wants Y=READY after a Z80 OUT, it must
    # explicitly call MQ_READY(). See ACTIVATE_MQ / PROCESS_CMD / LVM
    # SAVE / SEND_MSG2 scroll branch / ListMenu / SEND_MSG_PROMPT_YN
    # / ZX48_IO for the audit.
    # ────────────────────────────────────────────────────────────────────
    label("z80_out")
    nop()                   .side(0)      # padding cycle for bus settle
    in_(pins, 9)            .side(0) [2]  # sample D0-D7 + A0; [2] adds 2
                                          # extra cycles to ensure the
                                          # Z80's data is stable before
                                          # we latch it (bus setup time)
    push(noblock)           .side(0)      # ISR → RX FIFO (drops if full)
    mov(y, null)            .side(0)      # Y = 0 → $0F bit 6 = 0 (BUSY)
                                          # auto-asserted on every Z80 OUT
                                          # so the Z80's WAIT EXECUTION
                                          # poll blocks until Python is
                                          # ready and calls MQ_READY().

    # ============================================================
    # END OF CYCLE — wait for /PICOSEL to release, return to idle
    # ============================================================
    label("fin")
    wait(1, gpio, 14)       .side(0)      # block until /PICOSEL goes HIGH
    mov(null, osr)          .side(1)      # consume OSR (cleanup); sideset(1)
                                          # disables U6 again so we're off
                                          # the bus until the next cycle


def REWIND_ABORTED_SEARCH(TSP):
    """Put the tape back where a LOAD search started. Returns True if it moved.

    The user's only way out of a LOAD that cannot match is BREAK, and the
    Z80 never tells us about it -- its abort path writes nothing, and the
    whole EXROM holds exactly one `OUT ($0E),A`
    (docs/rom-analysis/BREAK_AND_ABORT.md). All we ever see is the transfer
    going quiet, and 3 seconds later the watchdog firing.

    By then the search has walked an arbitrary distance through the tape,
    so without this the next LOAD starts from wherever the abandoned search
    happened to stop -- which to the user looks like the tape position
    moved on its own. Rewinding to where the search began is the closest we
    can get to "leave it where they left it" with no signal to work from.

    Only rewinds a search in progress. An abort in the middle of a block
    the Z80 had already accepted is left alone: that position is where the
    user actually is.
    """
    if getattr(TSP, "ld_start", -1) < 0:
        return False
    TSP.offset = TSP.ld_start
    TSP.tap_idx = getattr(TSP, "ld_start_idx", 0)
    TSP.ld_start = -1
    TSP.ld_wrapped = False
    return True


def ENA_MQ_DUAL(MQ):
    """Re-create and activate the dual-port TS_IO_DUAL state machine.

    The bus state machine, rebuilt: what ZX48-mode handlers must use. Needed after ENA_SD(), which re-claims GPIO 2-4
    for SPI: the SM has to be rebuilt on the way back to the bus.

    In TS-2068 mode the main dispatcher does this via ACTIVATE_MQ() in
    tspico.py, but ZX48_IO never calls back into the dispatcher between
    transactions, so a ZX handler that touches the SD card has to
    restore the bus itself.

    Leaves Y = READY: the PIO drops Y to 0 on every Z80 OUT (issue #14
    auto-busy), and a fresh SM starts with Y undefined.
    """
    MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000, out_base=Pin(2, Pin.OUT),
                      in_base=Pin(2, Pin.IN), jmp_pin=Pin(11),
                      sideset_base=Pin(12, Pin.OUT))

    MQ.active(0)
    utime.sleep(0.01)
    MQ.active(1)
    MQX(MQ, "mov(y, invert(null))")

    return MQ


# ─── SD_MOUNT: the firmware's own mount, for the two SAVE writes ─────────
# tspico.py sets this to SAVE_MOUNT, which unmounts any stale /sd and goes
# through ACTIVATE_SD: up to 5 attempts 0.5 s apart while the card is
# believed present, and SD_NOTE_CARD's bookkeeping (a card that has come
# back or been swapped repairs the folder, the mount, append mode, the
# channels and the printer capture). Raises OSError when there is no card.
#
# Before this, SAVE_TS and SAVE_ZX were the last two callers of the bare
# mount below: ONE os.mount, none of the bookkeeping. Their final status
# has already gone out when they mount (#40), so a card that only came up
# on a second attempt meant "0 OK" on the 2068 and a file that was never
# written (2026-09-30 audit, §2 #21). tspico_io can't import tspico (it is
# imported BY it, and the upgrade UF2 freezes tspico_io without it), hence
# a hook. None -- the harnesses and host tests that load this module on its
# own -- keeps the old single mount.
# ─────────────────────────────────────────────────────────────────────────
SD_MOUNT = None


def ENA_SD(log_level=0):
    """Mount the SD card on /sd. Used by SAVE_TS and SAVE_ZX to write the
    captured TAP.

    With SD_MOUNT set (the firmware), that does the mount: retried, the
    card's state kept, OSError raised on failure. Both callers catch it as
    the write failure. Without it, one bare mount: returns the SPI object,
    or -99 if the mount failed.

    Note: this leaves the GPIO pins claimed by SPI; the caller is
    responsible for unmounting (or letting MOUNT_FILE / DEACTIVATE_SD
    handle it later in the dispatcher).

    log_level is the caller's TSP.LOG_LEVEL, for the error entry below.
    """

    if SD_MOUNT is not None:
        return SD_MOUNT()

    U3_CS       = Pin(28, Pin.OUT, Pin.PULL_UP)
    D0          = Pin(2,  Pin.IN)
    D1          = Pin(3,  Pin.IN)
    D2          = Pin(4,  Pin.IN)

    spi = SPI(0, sck=D0, mosi=D1, miso=D2)

    # ─── A failed mount is logged and NOT raised -- on purpose ─────────────
    # What this guard is for: carry on when the mount fails, and let the
    # caller's own write fail if there really is no card. Both callers wrap
    # ENA_SD() and the open()/write() after it in `try ... except Exception`,
    # log "SAVE write FAILED ..." and keep the dispatcher alive (SAVE_TS can't
    # report it to the 2068 any more: its final status went out before the
    # pin grab, see the RACE FIX comment there). Not raising also covers a
    # /sd that is somehow still mounted: os.mount() then fails with EPERM,
    # but the write still works on the existing mount, as it always has.
    #
    # What was broken: the log call used TSP.LOG_LEVEL, and there is no TSP
    # in this module -- every other function here gets TSP as a parameter;
    # ENA_SD never did. So the error path raised NameError instead of logging
    # and returning -99. The callers caught that as the write failure and
    # logged "name 'TSP' isn't defined", which hid the real cause (the
    # mount error). The `except:` was also bare, so it would have swallowed
    # KeyboardInterrupt (Ctrl-C from the host) as well. Now the caller
    # passes its log level in, the real error is logged, and only Exception
    # is caught. Found by the 2026-09-30 audit; see audit_fixes_hosttest.py.
    # SDCard() is inside the try because it talks to the card (init_card)
    # and is where a missing card actually fails -- before os.mount runs.
    # ─────────────────────────────────────────────────────────────────────
    try:
        sd = SDCard(spi, U3_CS)
        os.mount(sd, "/sd")
    except Exception as e:
        LOG_ADD("ERROR: Mounting SD Card failed in ENA_SD: %r" % (e,), 2, log_level)
        spi = -99

    return spi


def LOG_ADD(msg, level, log_level):
    """Buffer a timestamped log entry for later writing to /activity.log.

    Critical-path safe: we don't actually write to flash here (which
    would block for tens of ms), we just append to a string. The
    dispatcher writes log_entries to disk between Z80 transactions.

    Args:
        msg:       message text (no trailing newline needed).
        level:     this entry's severity (0=INFO, 1=WARN, 2=ERROR, 3=CRIT).
        log_level: TSP.LOG_LEVEL configured threshold. Entries below this
                   threshold are dropped (not buffered).
    """
    global log_entries

    if level < log_level:
        return

    # ticks_us() rolls over after ~71 minutes; that's fine for relative
    # timing within a session. (On Pico W this could be replaced with
    # an NTP-synced timestamp.)
    log_entries += "[" + str(time.ticks_us()) + "] "
    log_entries += msg + "\n"

    return


def LOAD_TS(pre, MQ, TSP):
    """Send one TAP block to the Z80 via Gustavo's TPI v2.4 protocol.

    Called by the main I/O dispatcher when the TS-2068 has issued a LOAD
    pre-header (BASIC LVM operation: LOAD "" CODE / LOAD "name" / etc.).

    PROTOCOL OVERVIEW (per docs/PROTOCOL.md and Gustavo's spec v2.4):

        Z80 has already OUT-ed the 10-byte pre-header (drained into pre[]
        by the main loop). It is now polling port $0F for the "continue"
        flag (D6=1) and will read port $0E for the status byte.

        Pico's job, in order:
          1. Status response
             - Initial status byte (0x01 = OK) was pre-loaded into TX FIFO
               by either the previous handler's tail or the boot pre-load.
               Z80's first IN $0E drains it.
             - Y is already 0xFFFFFFFF (READY) — Z80's $0F polls succeed.
          2. Data block response
             - Stream block_type + (blk_len-1) content bytes to TX.
             - Z80 reads them from $0E in a tight loop (~47µs/byte). The
               Pico keeps the 4-deep FIFO topped up; when it is full,
               TX_ROOM waits for room -- bounded, and listening for BREAK
               -- instead of a blocking MQ.put() (#51).
             - The flag/type byte is the FIRST byte Z80 reads in the data
               loop — Z80's CRC accumulator starts at block_type and XORs
               every byte read, so by the end the accumulator equals the
               file's CRC byte (which is the LAST byte of the stream).
          3. Echo phase
             - Z80 OUTs block_type ack (echo of what it expected to load)
             - Z80 OUTs its computed CRC (verification)
             - We drain both with MQ.get(); could verify but currently
               trust them.
          4. Final status + next-iteration pre-load
             - Two MQ.put(0x01) writes:
               * first 0x01 = this iteration's final status byte (Z80
                 reads it after polling $0F again)
               * second 0x01 = pre-load for the NEXT command's initial
                 status read. Stays in TX FIFO until the next LOAD/SAVE
                 starts.

    TIMING NOTE: this routine writes to TX much faster than the Z80 can
    read ($0E reads cap at ~47µs/byte due to Z80 ROM loop overhead). The
    per-byte streaming loop relies on MQ.put() blocking when the FIFO is
    full to pace the data flow — no software synchronization needed.

    The Z80 ROM has a long timeout on $0F polling (~20s per Gustavo's
    modification), so even slow file I/O is safe. The 88ms gap commonly
    seen between status read and ack OUT is normal Z80 ROM internal
    processing — not something Pico needs to manage.

    Args:
        pre[]: 10-byte pre-header that was just received from the Z80.
            pre[0] = expected block type (0x00 = header, 0xFF = data)
            pre[1] = TADDR (1 = LOAD)
            pre[2] = bank (0xFF = HOME)
            pre[3:5] = session ID (LE 16-bit)
            pre[5:7] = memory address (LE 16-bit)
            pre[7:9] = block length (LE 16-bit, BASIC's view)
            pre[9]   = pre-header CRC (XOR of pre[0..8])
        MQ:  TS_IO_DUAL state machine.
        TSP: PICO_STATUS instance. We read TSP.f_name, .totlen, .offset,
             .tap_idx and update .offset, .tap_idx after each block.

    Returns:
        (MQ, TSP, log_entries) — log_entries is appended to by LOG_ADD()
        and shown to the user later. MQ and TSP are returned for
        consistency with the dispatcher's expected calling convention.
    """
    global log_entries
    log_entries = ""

    # ---- LED on so user sees activity ----
    led = Pin(25, Pin.OUT)
    led.value(1)

    # ---- Choose source file ----
    # If no file is mounted (or total length is 0), fall back to the
    # cached /assets/nofile.tap handle (pre-opened at boot — see
    # OPEN_NOFILE_TAP() above). Opening a fresh file handle here would
    # cost ~5ms on cold flash metadata, during which the Z80 races
    # ahead reading stale 0x00s from an empty TX FIFO and ends up
    # reporting Report J — see docs/DUAL_PORT_DEVELOPMENT.md §8 for
    # the failure pattern.
    #
    # If TSP.f_name is set we open /TMP/temp.tap normally — its
    # metadata is hot from MOUNT_FILE's recent COPY_FILE, so the open
    # cost is sub-ms.
    global _nofile_arch
    if (not TSP.f_name) or TSP.totlen == 0:
        # Use the cached handle if we have one. If not, lazy-open and
        # cache (one-time slow path; subsequent calls are fast).
        if _nofile_arch is None:
            OPEN_NOFILE_TAP()
        if _nofile_arch is None:
            # /assets/nofile.tap genuinely isn't installed.
            #
            # Send Z80 a meaningful error response — TAPE LOADING ERROR
            # (status 2 → "Report R") rather than letting Z80 read stale
            # 0x00s and report Report J (which is more confusing because
            # it suggests an I/O hardware fault rather than a missing
            # file).
            #
            # We still emit the V6 pre-load chain so the next command
            # doesn't inherit an empty FIFO.
            LOG_ADD("ERROR: /assets/nofile.tap missing on Pico flash. "
                    "Copy assets/*.tap from the repo to /assets/ via Thonny.",
                    2, TSP.LOG_LEVEL)
            print("[LOAD_TS] ERROR: /assets/nofile.tap missing. "
                  "Copy assets/*.tap from repo to /assets/ via Thonny.")
            wrt = MQ.put
            wrt(0x02)        # tape error — Z80 will display "R Tape loading error"
            wrt(0x01)        # next-iter pre-load (so subsequent commands work)
            MQX(MQ, "mov(y, invert(null))")  # #14: Y → READY (PIO auto-busy)
            return MQ, TSP, log_entries
        arch = _nofile_arch
        local_fname = "/assets/nofile.tap"
        LOG_ADD("WARNING: no file mounted in LOAD_TS — using nofile.tap",
                1, TSP.LOG_LEVEL)
    else:
        local_fname = getattr(TSP, "load_file", None) or "/TMP/temp.tap"   # native one-shot tape, else the mount
        arch = open(local_fname, "rb")

    # ------------------------------------------------------------------
    # BOUNDED SEARCH. The Z80 drives the LOAD retry loop: it asks for a
    # header, compares the name ITSELF, and asks again on a mismatch. We
    # serve one block per call and wrap at EOF, so a LOAD that can never
    # match used to cycle the tape forever -- neither side counted laps.
    #
    # The user's only escape was BREAK, and the Pico is never told about
    # that: the EXROM's abort path (READ_STATUS $0655 -> $06AA -> $1A61)
    # writes nothing, and the whole EXROM contains exactly one
    # `OUT ($0E),A`. See docs/rom-analysis/BREAK_AND_ABORT.md. So the loop
    # has to be bounded HERE; there is no signal to wait for.
    #
    # One full lap is allowed deliberately -- a program that legitimately
    # needs to wrap around cannot rewind, because it does not speak TPI.
    # A second lap would just repeat the first, so we stop and say so.
    #
    # A data-block request means the Z80 accepted a header, which ends the
    # search. Everything else extends it.
    # ------------------------------------------------------------------
    ld_start = getattr(TSP, "ld_start", -1)      # getattr: a stale
    ld_wrapped = getattr(TSP, "ld_wrapped", False)  # dev_tspico may predate
                                                    # these fields
    if pre[0] == 0xFF:
        TSP.ld_start = -1                        # accepted -> search over
    elif ld_start < 0:
        TSP.ld_start = TSP.offset                # a search begins here
        TSP.ld_start_idx = TSP.tap_idx           # ... and at this block index
        TSP.ld_wrapped = False
    elif ld_wrapped and TSP.offset >= ld_start:
        # Back where we started, having been round once. Nothing matches.
        TSP.ld_start = -1
        TSP.ld_wrapped = False
        LOG_ADD("ERROR: LOAD found no matching block in a full pass of "
                "the TAP; stopping the search.", 2, TSP.LOG_LEVEL)
        # No TLM() here: unlike SAVE_TS, LOAD_TS never lazily imports it, so
        # a call would NameError at runtime. LOG_ADD already records this.
        # Inline rather than _close_if_local(): that helper is defined much
        # further down, so calling it here would NameError. Same rule --
        # never close the module-owned cached nofile handle.
        if arch is not _nofile_arch:
            arch.close()
        wrt = MQ.put
        wrt(0x07)        # status 7 -> Report 8 "End of file"
        wrt(0x01)        # next-iter pre-load, so the next command works
        MQX(MQ, "mov(y, invert(null))")          # Y -> READY
        return MQ, TSP, log_entries

    # ---- Read the TAP block prefix [len_lo, len_hi, type] ----
    # TAP file format (standard ZX/TS): each block is
    #   [len_lo][len_hi][block_type][content...][CRC byte]
    # where len = 1 + len(content) + 1 (i.e., includes type and CRC).
    # ---- At the end of the tape: wrap, as the block-type search below does ----
    # A LOAD can start exactly at the end: after a .ROM mount's updater has
    # read its four blocks, or after any TAP's last block. Nothing read there
    # is a block, and a zero length used to reach bytearray(-1) below: a
    # MemoryError that killed the firmware (hardware, 2026-09-30: LOAD "" with
    # FDDV14.ROM still mounted after the ROM update).
    arch_len = arch.seek(0, 2)
    if TSP.offset >= arch_len:
        TSP.offset = 0
        TSP.tap_idx = 0
        TSP.ld_wrapped = True

    arch.seek(TSP.offset)
    blk_info = bytearray(3)
    arch.readinto(blk_info)
    totbytes = blk_info[0] + 256 * blk_info[1]   # = block size including type+CRC

    # ---- Validate that the file's block type matches what Z80 wants ----
    # If not, advance to the next block in the TAP and try again. (LOAD
    # often skips header blocks looking for the data block whose name
    # matches the request, etc.)
    if pre[0] != blk_info[2]:
        LOG_ADD("WARNING: Wrong block type in LOAD_TS. Moving ahead 1 block.",
                1, TSP.LOG_LEVEL)
        TSP.offset += totbytes + 2
        TSP.tap_idx += 1
        if TSP.offset >= TSP.totlen:
            TSP.tap_idx = 0
            TSP.offset  = 0
            TSP.ld_wrapped = True          # one lap of the tape completed
            LOG_ADD("WARNING: EOF reached searching in LOAD_TS; rewinding.",
                    1, TSP.LOG_LEVEL)
        arch.seek(TSP.offset)
        arch.readinto(blk_info)
        totbytes = blk_info[0] + 256 * blk_info[1]
        # BLINK() used to be called here. It sleeps ~1 second, INSIDE a live
        # transaction, while the Z80 sits in WF_NPH. The protocol tolerates
        # it (the ready wait allows 19.9s) so it never broke anything, but
        # it throttled a block-type-mismatch search to about one block per
        # second -- which is most of why a non-matching LOAD felt like a
        # hang rather than a fast spin. It was a visual debug aid, not a
        # protocol step; BLINK's real job is the watchdog's "something went
        # wrong" signal. The LED is already driven by the dispatcher.

    # ---- A block that can't be one: Report R, not a crash ----
    # Shorter than type + CRC, or running past the end of the file: a
    # damaged TAP, or not a TAP at all.
    if totbytes < 2 or TSP.offset + 2 + totbytes > arch_len:
        LOG_ADD("ERROR: LOAD_TS: no TAP block at offset %d (length %d, file %d)"
                % (TSP.offset, totbytes, arch_len), 2, TSP.LOG_LEVEL)
        if arch is not _nofile_arch:
            arch.close()
        wrt = MQ.put
        wrt(0x02)        # status 2 -> Report R "Tape loading error"
        wrt(0x01)        # next-iter pre-load, so the next command works
        MQX(MQ, "mov(y, invert(null))")          # Y -> READY
        return MQ, TSP, log_entries

    # ---- Header block: read it whole, then serve it exactly as on the tape ----
    # (A header is ~20 bytes, so it is buffered and streamed from memory
    # below; data blocks are streamed straight from the file.)
    #
    # There used to be an "autorun patch" here, inherited from the v1.5
    # firmware (src/test/lvm_test.py: "v1.5 does this for non-autorun
    # progs"). For a BASIC header whose autorun line was 32768 or more --
    # the tape convention for "no autorun" -- it rewrote the line's high
    # byte to 28h, i.e. autorun at line 10240-10495. Its comment said such
    # tapes hit "Report L" on the 2068. It was removed on 2026-10-01 because:
    #
    #   * The ROM already handles "no autorun". The 2068's LOAD (EXROM 06C3:
    #     LD H,(IX+0Eh) / AND 0C0h / JR NZ) skips the autorun whenever either
    #     top bit of the line is set -- the same test as the Spectrum. Those
    #     bytes are identical in the genuine 2068 EXROM and in TS-Pico ROMs
    #     1.1, 1.5w, 2.0 and 2.1, and the 2068's own SAVE without LINE
    #     writes exactly 80h there (EXROM 0450). No ROM we have needs it.
    #   * The patch turned every non-autorun program into one that autoruns
    #     to a line that can't exist (BASIC lines stop at 9999).
    #   * Its CRC fix-up, `crc ^ 0x80 ^ new`, is only right when the old
    #     byte was exactly 80h. A header with 81h-FFh there (some tape tools
    #     write FFFFh for "no autorun") reached the Z80 with a bad checksum:
    #     Report R. load_ts_hosttest.py pins both cases.
    #
    # If a real tape ever turns up that the 2068 mis-loads without it, that
    # is a finding about that tape: record which one, and what the 2068
    # does, before putting anything back here.
    # The block goes out of RAM, read whole here while the Z80 waits for
    # READY: no file access once it streams. A LittleFS read can stall for a
    # few hundred us (a cache refill, a block boundary), longer than the
    # 4-deep TX FIFO covers at the Z80's ~47 us a byte -- "TX ran dry" 17
    # times in a 35795-byte block, read a chunk at a time, and the 2068 then
    # failed the LOAD (hardware, 2026-10-03). v1.29 has ~180 KB free; a block
    # the heap can't hold still streams from the file, a chunk at a time.
    hdr = None                                       # the block, in RAM
    if blk_info[2] == 0x00:                          # header block
        hdr = bytearray(totbytes - 1)
        arch.readinto(hdr)
    else:
        try:
            gc.collect()
            hdr = bytearray(totbytes - 1)
            arch.readinto(hdr)
        except MemoryError:
            hdr = None
            arch.seek(TSP.offset + 3)                # back to the content for the file path

    # ---- Collect garbage NOW, while the Z80 waits for READY ----
    # Issue #51: once READY is up the Z80 reads a byte every 50 us with no
    # handshake, and the 4-deep TX FIFO covers ~200 us. A GC that starts
    # mid-stream (any allocation on core0, or core0 waiting for the heap
    # lock while the watchdog's LOG_ADD collects on core1) stops core0 for
    # 15-25 ms with a full firmware heap: hundreds of empty reads, Report
    # R. Hardware, 2026-09-26: "LOAD watchdog fired with 15772 of 16096
    # bytes queued" on the 8th LOAD of a session. Here it costs nothing --
    # the Z80 is parked in WAIT_PICO_READY (the dispatcher doesn't say
    # READY for LOAD) -- and leaves the heap far from its next threshold.
    gc.collect()

    # ---- No watchdog (issue #51 stage 5) ----
    # This used to start a core1 WATCHDOG thread with a total-time budget.
    # Every wait below is bounded on its own now -- TX_ROOM gives up after
    # 3 s of the Z80 not reading, RX_WORD after 1 s of silence, and a BREAK
    # / SYNC (port-0Fh write) ends the LOAD at once -- which the abort
    # harness proved on hardware without any watchdog. Gone with it: the
    # "core1 busy" spawn failures, the ~1 s BLINK with the bus state
    # machine off, and a total-time budget that killed slow-but-live LOADs.

    wrt = MQ.put

    # ============================================================
    # Phase 1: stream the response (block_type + content + CRC)
    # ============================================================
    # Z80's data loop reads `flag + content + CRC` = `totbytes` bytes
    # via $0E. The flag (block_type) is the first byte and seeds Z80's
    # running CRC accumulator. When the FIFO is full the loop below waits
    # in TX_ROOM (bounded, listening for BREAK), paced by the Z80's reads.
    wrt(blk_info[2])                                  # block_type / flag

    # Helper: close `arch` ONLY if it was opened locally for this call
    # (i.e., it's NOT the cached _nofile_arch). The cached handle stays
    # open across calls — it's owned by the module, not by this function.
    def _close_if_local():
        if arch is not _nofile_arch:
            arch.close()

    # ─── Issue #51: never block in MQ.put() ─────────────────────────────
    # The Z80 reads a byte every ~30-47 us with no handshake. MQ.put()
    # used to pace this loop by blocking while the 4-deep TX FIFO was full
    # -- and when the Z80 stopped reading (BREAK), it blocked until the
    # 3 s watchdog fired. Now the loop only puts when there is room; when
    # TX is full it waits in TX_ROOM, which listens: a write to port 0Fh
    # is the 1.8b ROM's BREAK abort (or a new command's SYNC after a 2068
    # reset), and any data byte is the Z80's block-type echo, kept for
    # phase 2. Per byte on the fast path: read, one FIFO test, one put --
    # no more work than the old read + put + kill test.
    #
    # Older ROMs never write 0Fh; for them only the watchdog (2) can end
    # the loop early, exactly as before.
    # ────────────────────────────────────────────────────────────────────
    put = MQ.put
    txf = MQ.tx_fifo
    echo = bytearray(3) # [count, block type, CRC] -- see ECHO_KEEP; no allocation mid-stream
    why = 0             # 0 ok, 1 port-0Fh write, 2 watchdog, 3 stall (TX_ROOM's codes)
    sent = 1            # bytes queued for the Z80, flag included
    dry = 0             # times TX was found empty mid-stream (a near-miss:
    dry_at = -1         # the Z80 may have read 0x00) and the first byte
    # READY only once the flag and the first bytes are queued: the
    # dispatcher no longer says it for LOAD (see TS2068_IO). The first time
    # TX fills is the moment -- and the only place this is tested, so the
    # per-byte fast path is unchanged.
    primed = False
    t_ready = time.ticks_ms()   # reset when READY actually rises
    # Z80 read-rate profile (issue #51 diagnostic): ms after READY at every
    # 1024th byte queued. One AND per byte; the clock is read 1/1024 bytes.
    prof = array("I", bytes(4 * ((totbytes >> 10) + 1)))

    if hdr is not None:
        # Stream from RAM (the block, read whole above).
        for b in hdr:
            n = txf()
            if n >= TX_DEPTH:
                if not primed:
                    MQX(MQ, "mov(y, invert(null))")     # READY: data waiting
                    primed = True
                    t_ready = time.ticks_ms()
                why = TX_ROOM(MQ, echo)
                if why:
                    break
            elif not n and primed:
                dry += 1
                if dry_at < 0:
                    dry_at = sent
            put(b)
            sent += 1
    else:
        # Data block: from the file LOAD_CHUNK bytes at a time into _LOAD_BUF
        # (a block can be 14 KB+, too big to hold whole). The tail of the
        # block reads through a memoryview slice -- one small allocation a
        # block, not a byte.
        rd = arch.readinto
        buf = _LOAD_BUF
        left = totbytes - 1
        while left and not why:
            got = rd(buf) if left >= LOAD_CHUNK else rd(_LOAD_MV[:left])
            if not got:
                break                                   # the file ended early
            left -= got
            i = 0
            while i < got:
                n = txf()
                if n >= TX_DEPTH:
                    if not primed:
                        MQX(MQ, "mov(y, invert(null))")     # READY: data waiting
                        primed = True
                        t_ready = time.ticks_ms()
                    why = TX_ROOM(MQ, echo)
                    if why:
                        break
                elif not n and primed:
                    dry += 1
                    if dry_at < 0:
                        dry_at = sent
                put(buf[i])
                i += 1
                sent += 1
                if not sent & 0x3FF:
                    prof[sent >> 10] = time.ticks_diff(time.ticks_ms(), t_ready)
    if not primed:
        MQX(MQ, "mov(y, invert(null))")                 # a block shorter than TX

    # ============================================================
    # Phase 2: the Z80's echo (block_type ack + computed CRC)
    # ============================================================
    # The Z80 OUTs its block type before the data loop (usually already
    # collected above, while TX was full) and its computed CRC after it,
    # and only after the CRC checked out. Bounded, and listening for 0Fh:
    # a BREAK can also land in the ROM's ready-wait around the block.
    while not why and echo[0] < 2:
        w = RX_WORD(MQ, 1000)
        if w < 0:
            why = 3
        elif w & PORT_0F:
            why = 1
        else:
            ECHO_KEEP(echo, w)

    if totbytes >= 8192:
        # WARNING level (1), off by default: at ERROR it put a line in the log
        # after every large LOAD, and the log write that followed on core1
        # froze core0 during the next command (see TS2068_IO's SYNC branch).
        # Where the time went: ms per 1K block. Near 52 = the ROM loop's
        # 178 T-states/byte; far above it = the Z80 was slowed down.
        k = sent >> 10
        LOG_ADD("DIAG: LOAD %d bytes, %s; ms/KB after READY: %s"
                % (totbytes, "ok" if not why and echo[0] >= 2 else "why=%d" % why,
                   " ".join(str(prof[i] - prof[i - 1] if i > 1 else prof[1])
                            for i in range(1, k + 1))), 1, TSP.LOG_LEVEL)

    if dry:
        # TX ran empty after READY: each time the Z80 may have read 0x00.
        # Normally 0; anything else says where a Pico-side pause began.
        LOG_ADD("ERROR: LOAD TX ran dry %d times, first at byte %d of %d."
                % (dry, dry_at, totbytes), 2, TSP.LOG_LEVEL)

    if why:
        # BREAK (1) or silence (3). Bytes the Z80 had actually read
        # = queued minus what's still in TX; 0-4 means it was still in the
        # ready-wait before the data. Then: the search rewound if one was
        # in progress, and straight back to idle -- the 1.8b ROM is waiting
        # for READY + IDLE to raise Report D.
        read = max(0, sent - txf())
        rewound = REWIND_ABORTED_SEARCH(TSP)
        _close_if_local()
        MQ_TO_IDLE(MQ, recovered=(why != 1))
        LOG_ADD("INFO: LOAD %s after the Z80 read %d of %d bytes%s." % (
            "stopped by BREAK" if why == 1 else "stalled -> RECOVERED",
            read, totbytes, "; tape rewound to offset %d" % TSP.offset
            if rewound else ""), 1 if why == 1 else 2, TSP.LOG_LEVEL)
        return MQ, TSP, log_entries

    _close_if_local()
    blq_t = echo[1]                                   # block_type ack
    crc   = echo[2]                                   # Z80's computed CRC

    # ============================================================
    # Phase 3: final status + pre-load for the NEXT command
    # ============================================================
    # Z80 polls $0F (sees Y=ready), then reads $0E for the final status.
    # The first wrt(0x01) is what it reads. The second 0x01 stays in
    # the TX FIFO so the NEXT command's initial $0E status read finds
    # it already there. This is the chain that makes back-to-back LOADs
    # work (e.g., header block followed by data block).
    wrt(0x01)                                          # this iter's final status
    wrt(0x01)                                          # next iter's status pre-load
    # ─── Issue #14: PIO auto-busy compensation ──────────────────────
    # The PIO drops Y to 0 on every Z80 OUT (echo bytes, CRC bytes,
    # etc.). Without an explicit MQ_READY here, Y stays BUSY, the
    # Z80's $0F poll never sees ready, and the two pre-loaded 0x01
    # bytes sit in TX never to be read → Report J on next command.
    # ────────────────────────────────────────────────────────────────
    MQX(MQ, "mov(y, invert(null))")                    # Y = READY

    # ---- Advance TAP position for the next call ----
    TSP.tap_idx += 1
    TSP.offset  += totbytes + 2                       # 2 = the len_lo/len_hi prefix
    if TSP.f_name:
        if TSP.f_name[-4:].upper() == ".TAP":
            if TSP.totlen != 0 and TSP.offset >= TSP.totlen:
                TSP.tap_idx = 0
                TSP.offset  = 0
                TSP.ld_wrapped = True      # one lap of the tape completed
                LOG_ADD("INFO: reached end of TAP, rewinding.",
                        0, TSP.LOG_LEVEL)
    else:
        # nofile.tap fallback — wrap around when we run off the end
        if TSP.offset >= os.stat("/assets/nofile.tap")[6]:
            TSP.tap_idx = 0
            TSP.offset  = 0

    # NOTE: write no other status here (the old END_MSG helper did, and
    # was removed by the 2026-09-30 audit). The two wrt(0x01) writes above
    # already provided the final status and the next-iter pre-load.
    # Another would inject an EXTRA 0x01 status into TX, which the Z80
    # consumes as the first byte of the NEXT iteration's data-loop read
    # (where it expects the block_type 0xFF). The CRC accumulator gets
    # offset by one byte from the start, every subsequent byte XORs into
    # the wrong slot, and the final CRC check fails → "Report R - Tape
    # Loading Error" on the data block.
    # If verbose status messages are wanted later, they need a different
    # protocol layout (e.g., write 0x81 + msg BEFORE the pre-load 0x01,
    # making the verbose directive the final response instead of an
    # additional 0x01).

    return MQ, TSP, log_entries



def LOAD_SERVE(pre, MQ, TSP):
    """LOAD / VERIFY / MERGE: serve the mounted TAP -- or, when the fdd ROM has
    armed a native file with tpi:fopen (TSP.native, see NATIVE_OPEN in
    tspico.py), the one-shot tape made from it.

    The one-shot is a separate file (/TMP/native.tap) with its own position.
    Each call swaps it in, runs the unchanged LOAD_TS, and swaps the
    mounted file's state back, so nothing else ever sees the swap and the
    mount is exactly as it was afterwards. The pre-header's session (bytes 3-4)
    must match the one tpi:fopen was given; any other LOAD drops a stale arm.
    It is used up once the data block has been served, or once the search has
    given up (Report 8)."""

    nat = getattr(TSP, "native", None)
    if not nat or nat.get("op", 0) == 0:
        return LOAD_TS(pre, MQ, TSP)
    if (pre[3] | (pre[4] << 8)) != nat["session"]:
        TSP.native = None                                  # stale: that statement never loaded
        return LOAD_TS(pre, MQ, TSP)

    keep = (TSP.f_name, TSP.totlen, TSP.offset, TSP.tap_idx, getattr(TSP, "ld_start", -1),
            getattr(TSP, "ld_wrapped", False), getattr(TSP, "ld_start_idx", 0))
    TSP.f_name = nat["tap"]
    TSP.totlen = nat["totlen"]
    TSP.offset = nat.get("offset", 0)
    TSP.tap_idx = nat.get("tap_idx", 0)
    TSP.ld_start = nat.get("ld_start", -1)
    TSP.ld_wrapped = nat.get("ld_wrapped", False)
    TSP.ld_start_idx = nat.get("ld_start_idx", 0)
    TSP.load_file = nat["tap"]
    try:
        MQ, TSP, log_entries = LOAD_TS(pre, MQ, TSP)
    finally:
        nat["offset"], nat["tap_idx"] = TSP.offset, TSP.tap_idx
        nat["ld_start"], nat["ld_wrapped"] = TSP.ld_start, TSP.ld_wrapped
        nat["ld_start_idx"] = getattr(TSP, "ld_start_idx", 0)
        done = pre[0] == 0xFF or TSP.ld_start < 0
        (TSP.f_name, TSP.totlen, TSP.offset, TSP.tap_idx, TSP.ld_start,
         TSP.ld_wrapped, TSP.ld_start_idx) = keep
        TSP.load_file = None
        if done:
            TSP.native = None
    return MQ, TSP, log_entries

# ZX48 mode's time limits. The Spectrum ROM reads a LOAD byte every ~43 us
# and writes a SAVE byte every ~83 us, with ~1 ms pauses around a block's
# flag and CRC and ~1 s between a SAVE's two blocks. Nothing a live Z80
# does in the middle of a block is slower than ZX_STALL_MS.
ZX_STALL_MS = const(1000)       # a block the Z80 stopped reading or sending
ZX_BLOCK_GAP_MS = const(3000)   # SAVE: the ROM's ~1 s pause before the data block


def ZX_FLUSH_TX(MQ):
    """Empty TX: the tail of a block the ROM did not read to the end.
    Bounded, like MQ_TO_IDLE, whose first half this is -- ZX48 mode has no
    status pre-load, so the rest of it does not apply."""
    for _ in range(64):
        if MQ.tx_fifo() == 0:
            break
        MQX(MQ, "pull (noblock)")
        MQX(MQ, "mov (osr, null)")


def ZX_ROOM(MQ, stall_ms):
    """ZX48 LOAD's slow path: TX is full, so wait for room -- listening --
    instead of blocking in MQ.put(). Returns

        -1       there is room
        -2       TX stayed full for stall_ms: the Z80 stopped reading
        0..511   a word the Z80 wrote: it has left this block and sent its
                 next command ('L', 'S', ...), for ZX48_IO to dispatch

    The ROM reads a block in one DI loop with no way out, so it only stops
    early when it asked for fewer bytes than the block holds: LD-BYTES reads
    flag + the length it expects + CRC, whatever the block's own length.
    LOAD "name" does that with every block before the one it wants, then
    prints its name and asks for the next one. No allocation: see TX_ROOM.
    """
    t0 = time.ticks_ms()
    while MQ.tx_fifo() >= TX_DEPTH:
        if MQ.rx_fifo():
            return MQ.get()
        if time.ticks_diff(time.ticks_ms(), t0) >= stall_ms:
            return -2
    return -1


# ---- UPDATE mode: the original Spectrum ROM, no handshake ---------------------
#
# A board upgraded from 1.1 / 1.5 to this firmware still has its old TS-2068
# ROM, which can't talk to it. Every shipped flash image has the same Spectrum
# ROM in slot 0 (crc32 A8E12A24), and `OUT 244,3` switches to it whatever the
# 2068 ROM is -- so that ROM loads the updater. It has no handshake at all: its
# LD-BYTES sends 'L', waits a fixed ~0.94 ms and reads the flag, whatever is
# in TX. So UPDATE mode doesn't answer 'L': TX always holds the next bytes of
# the updater tape, kept as ONE stream (each block's flag, content and CRC,
# back to back), and the next block's flag is already queued behind the last
# block's CRC when the next 'L' comes. Proven on hardware with a v15w chip
# (src/test/zx_bootstrap_harness.py): BASIC, SCREEN$ and CODE loaded, TX
# never ran empty, each 'L' arrived exactly at its block's flag.

def TAPE_STREAM(path):
    """TAPE_STREAM_OF the .tap file at path."""
    with open(path, "rb") as f:
        return TAPE_STREAM_OF(f.read())


def TAPE_STREAM_OF(raw):
    """A .tap as one stream: each block's flag + content + CRC, the 2-byte
    lengths dropped. Returns (stream, starts), starts the offset of every
    block."""
    stream = bytearray()
    starts = []
    o = 0
    while o + 2 <= len(raw):
        n = raw[o] | (raw[o + 1] << 8)
        starts.append(len(stream))
        stream.extend(raw[o + 2:o + 2 + n])
        o += 2 + n
    return stream, starts


def ZX_ARM(MQ, stream):
    """Rewind the tape: empty TX and queue the stream's first bytes, so the
    flag is there when the ROM reads, 0.94 ms after its 'L'. Returns the
    stream position (bytes queued)."""
    ZX_FLUSH_TX(MQ)
    pos = 0
    while pos < len(stream) and pos < TX_DEPTH:
        MQ.put(stream[pos])
        pos += 1
    return pos


def ZX_STREAM(MQ, stream, pos, rewind_ms):
    """Keep TX fed from stream[pos:] until the Z80 writes a word; return
    (word, pos). Never blocks in MQ.put().

    The tape rewinds by itself (back to stream[0], armed):
      * once the Z80 has read the whole stream, so the next LOAD "" starts
        the tape again;
      * after rewind_ms without a read part-way through -- a LOAD that was
        stopped (BREAK between blocks, a reset), so the next one doesn't
        start in the middle of the tape.

    The per-byte path is a FIFO test and a put, as in the harness; the clock
    runs only while TX is full (the Z80 isn't reading).
    """
    n = len(stream)
    since = -1
    while True:
        k = MQ.tx_fifo()
        if k < TX_DEPTH and pos < n:
            MQ.put(stream[pos])
            pos += 1
            since = -1
            continue
        if MQ.rx_fifo():
            return MQ.get(), pos
        if pos >= n and k == 0:
            pos = ZX_ARM(MQ, stream)                    # the whole tape was read
            since = -1
        elif k and pos > TX_DEPTH:                     # bytes waiting, the Z80 not reading
            if since < 0:
                since = time.ticks_ms()
            elif time.ticks_diff(time.ticks_ms(), since) >= rewind_ms:
                pos = ZX_ARM(MQ, stream)                # stopped part-way
                since = -1


def LOAD_ZX(MQ, TSP):
    """Send one TAP block to the Spectrum ROM in ZX48 mode.

    ZX48 is a much simpler protocol than the TS-2068 LVM one that
    LOAD_TS implements. The customised Spectrum ROM (flash slot 0) has
    no pre-header, no status byte and no echo:

        Z80  -> OUT ($0E),'L'      (76; consumed by ZX48_IO's dispatch)
        Z80  -> polls $0F for READY (ZX v2 ROM; up to ~3.8 s, then Report R)
        Pico -> flag byte          (block type: 0x00 header, 0xFF data)
        Pico -> content bytes      (Z80 reads at ~43us each)
        Pico -> CRC byte

    So the response is exactly `totbytes` bytes: the TAP block minus
    its 2-byte length prefix. There is deliberately NO status byte and
    NO V6 pre-load chain here.

    Returns MQ, TSP, log_entries, nxt. nxt is the Z80's next command byte
    when it arrived in the middle of this block (see ZX_ROOM), else -1;
    ZX48_IO dispatches it next.

    No watchdog (issue #51, as LOAD_TS): the stream never blocks in
    MQ.put(). When TX is full it waits in ZX_ROOM, and gives up after
    ZX_STALL_MS or when the Z80 sends its next command. Either way the
    tape moves on past this block, as a real one would -- a LOAD "name"
    skips the blocks before its file this way. It used to wait 3 s for
    the watchdog on every skipped block, and then send the same block
    again, because the tape position only moved on a complete read.

    Bytes the ROM did not read are flushed from TX before the next block's
    flag goes in. The flag goes in before READY: the ROM reads $0E the
    instant READY rises. Y stays READY afterwards -- the Z80's reads don't
    touch it, and its next OUT drops it.
    """
    global log_entries
    log_entries = ""

    led = Pin(25, Pin.OUT)
    led.value(1)

    if not TSP.f_name or TSP.totlen == 0:
        local_fname = "/assets/nofile.tap"
        LOG_ADD("WARNING: no file mounted in LOAD_ZX", 1, TSP.LOG_LEVEL)
    else:
        local_fname = "/TMP/temp.tap"

    blk_info = bytearray(3)
    arch = open(local_fname, "rb")
    arch.seek(TSP.offset)
    arch.readinto(blk_info)
    totbytes = blk_info[0] + 256 * blk_info[1]

    ZX_FLUSH_TX(MQ)
    # Collect garbage now, while the ROM waits for READY: a GC in the middle
    # of the block stops core0 for 5-25 ms, and the Z80 reads 0x00 from an
    # empty TX every 43 us meanwhile (see LOAD_TS).
    gc.collect()

    put = MQ.put
    txf = MQ.tx_fifo
    rd = arch.readinto
    buf = _LOAD_BUF     # a chunk at a time, as LOAD_TS (LOAD_CHUNK), if not in RAM
    # The whole block into RAM first, as LOAD_TS does: no file access once
    # the ROM reads blind (ZX LOAD logged "TX ran dry" 9-10 times a block,
    # hardware 2026-10-02/03). A block the heap can't hold uses the file.
    whole = None
    try:
        whole = bytearray(totbytes - 1)
        rd(whole)
    except MemoryError:
        whole = None
    nxt = -1
    sent = 1
    dry = 0             # times TX ran empty mid-block: the Z80 may have read 0x00
    primed = False      # TX has been full once; only then does empty mean late

    put(blk_info[2])                        # the flag
    MQX(MQ, "mov(y, invert(null))")         # READY

    # totbytes counts flag + content + CRC; the flag is already queued.
    if whole is not None:
        for b in whole:
            n = txf()
            if n >= TX_DEPTH:
                primed = True
                nxt = ZX_ROOM(MQ, ZX_STALL_MS)
                if nxt != -1:
                    break
            elif not n and primed:
                dry += 1
            put(b)
            sent += 1
    left = 0 if whole is not None else totbytes - 1
    while left and nxt == -1:
        got = rd(buf) if left >= LOAD_CHUNK else rd(_LOAD_MV[:left])
        if not got:
            break                           # the file ended early
        left -= got
        i = 0
        while i < got:
            n = txf()
            if n >= TX_DEPTH:
                primed = True
                nxt = ZX_ROOM(MQ, ZX_STALL_MS)
                if nxt != -1:
                    break
            elif not n and primed:
                dry += 1
            put(buf[i])
            i += 1
            sent += 1
    arch.close()

    if nxt != -1:
        read = max(0, sent - txf())
        ZX_FLUSH_TX(MQ)
        LOG_ADD("INFO: ZX LOAD: the ROM read %d of %d bytes, then %s." % (
            read, totbytes, "stopped" if nxt == -2 else "sent 0x%02X" % (nxt & 0xFF)),
            0 if nxt >= 0 else 1, TSP.LOG_LEVEL)
        if nxt == -2:
            nxt = -1
    if dry:
        LOG_ADD("ERROR: ZX LOAD: TX ran dry %d times in a %d-byte block."
                % (dry, totbytes), 2, TSP.LOG_LEVEL)

    led.value(0)

    TSP.offset += totbytes + 2
    TSP.tap_idx += 1
    if TSP.offset >= TSP.totlen:
        TSP.offset = 0
        TSP.tap_idx = 0
        LOG_ADD("WARNING: reached end of offset table in LOAD_ZX, rewinding...", 1, TSP.LOG_LEVEL)

    return MQ, TSP, log_entries, nxt


def LOAD_ZX_C(MQ, TSP, buf_size):
    """ZX Spectrum LOAD in 'compatible' mode — stream the tape continuously.

    Where LOAD_ZX answers one 'L' with exactly one block, this reads up
    to buf_size of the TAP into memory and streams every block back to
    back, the Z80 pacing it: blocks the Spectrum ROM skips over (wrong
    name, wrong type) are consumed by its own LD-BYTES calls exactly as
    they would be off a tape running continuously. That is what makes
    hard-to-load TAPs work here and not in LOAD_ZX. It is memory-hungry
    and can OOM the Pico.

    Each buffered entry is rd_bytes[2:len+2] — flag + content + CRC, the
    TAP block minus its length prefix.

    Returns MQ, TSP, log_entries, nxt, as LOAD_ZX.

    No watchdog and no blocking MQ.put() (issue #51): when TX is full the
    stream waits in ZX_ROOM. Every LD-BYTES call opens with an 'L' and
    waits for READY, so an 'L' mid-stream gets READY and the tape runs on;
    any other byte is the Z80's next command, and ends the stream. So does
    ZX_STALL_MS without a read (BREAK between blocks, a reset). The bytes
    left in TX are flushed: the next 'L' would read them as its flag.
    """
    global log_entries
    log_entries = " "

    cur_buf = []

    if (TSP.offset >= TSP.totlen):
        return MQ, TSP, log_entries, -1

    size_rd = TSP.totlen - TSP.offset

    if (size_rd >= buf_size):
        size_rd = buf_size
    rd_bytes = bytearray(size_rd)

    if (not TSP.f_name or TSP.totlen == 0):
        local_fname = "/assets/nofile.tap"
        LOG_ADD("WARNING: no file mounted in LOAD_ZX_C", 1, TSP.LOG_LEVEL)
    else:
        local_fname = "/TMP/temp.tap"

    arch = open(local_fname, "rb")
    arch.seek(TSP.offset)

    try:
        arch.readinto(rd_bytes)
    except:
        LOG_ADD("ERROR: while reading file in LOAD_ZX_C!", 2, TSP.LOG_LEVEL)
        arch.close()
        return MQ, TSP, log_entries, -1

    arch.close()

    TSP.offset += len(rd_bytes)

    while (rd_bytes):
        long = rd_bytes[0] + (256*rd_bytes[1])

        if (long > len(rd_bytes)):
            TSP.offset -= len(rd_bytes)
            break
        hasta = long + 2

        cur_buf.append(rd_bytes[2:hasta])

        rd_bytes = rd_bytes[hasta:]

    del rd_bytes
    ZX_FLUSH_TX(MQ)
    gc.collect()                            # now, not mid-stream (see LOAD_ZX)

    put = MQ.put
    txf = MQ.tx_fifo
    led = Pin(25, Pin.OUT)
    nxt = -1

    # Stage the first byte before raising READY — see the same note in
    # LOAD_ZX. memoryview keeps this from copying the (large) buffer.
    if cur_buf and len(cur_buf[0]):
        put(cur_buf[0][0])
        MQX(MQ, "mov(y, invert(null))")
        cur_buf[0] = memoryview(cur_buf[0])[1:]

    for ar in cur_buf:
        led.value(1)
        for el in ar:
            if txf() >= TX_DEPTH:
                nxt = ZX_ROOM(MQ, ZX_STALL_MS)
                while nxt == 76:            # 'L': the ROM's next LD-BYTES
                    MQX(MQ, "mov(y, invert(null))")
                    nxt = ZX_ROOM(MQ, ZX_STALL_MS)
                if nxt != -1:
                    break
            put(el)
        led.value(0)
        if nxt != -1:
            break

    # The tail: let the Z80 read what is left, answering its 'L's the same
    # way. In compatible mode the whole buffer is streamed, so once the ROM
    # has found its file the rest is never read -- the old unbounded wait
    # here hung ZX48 mode until reset.
    t0 = time.ticks_ms()
    while nxt == -1 and txf():
        if MQ.rx_fifo():
            w = MQ.get()
            if w == 76:
                MQX(MQ, "mov(y, invert(null))")
                t0 = time.ticks_ms()
            else:
                nxt = w
        elif time.ticks_diff(time.ticks_ms(), t0) >= ZX_STALL_MS:
            nxt = -2

    if nxt != -1:
        LOG_ADD("INFO: LOAD_ZX_C: stream ended with %d bytes unread (%s)."
                % (txf(), "stopped" if nxt == -2 else "0x%02X" % (nxt & 0xFF)),
                1, TSP.LOG_LEVEL)
        ZX_FLUSH_TX(MQ)
        if nxt == -2:
            nxt = -1

    cur_buf = []

    return MQ, TSP, log_entries, nxt


def SAVE_NAME(hdr):
    """Extract the ZX filename from a SAVE header block and judge it.

    The 10-byte, space-padded name lives at hdr[4:14]. Returns a tuple:

        name -- printable rendering of the name with the ZX space padding
                stripped. Always safe to put in a log line or a TLM: any
                byte that isn't printable ASCII is shown as '?'.
        ok   -- True if every byte is in the FAT-safe allowlist
                (alphanumeric, '_' or '-'), i.e. usable as a filename.

    Built byte-by-byte on purpose, NOT via bytes.decode(). A TS-2068 name
    can legitimately carry bytes >= 0x80 (graphics characters, BASIC
    tokens), and decode() raises on those. SAVE_TS runs unguarded inside
    the dispatcher's main loop (no try/except around the call in
    tspico.py), so an exception here would take the whole loop down
    rather than produce an error report.

    NOTE -- this allowlist is stricter than the one the `SAVE "tpi:<name>"`
    create path uses in TS/tspico.py, which allows any printable character
    other than the eight FAT-reserved ones. Spaces, dots and parens are
    creatable that way but not via a plain SAVE. That divergence is known
    and left as-is for now; see docs/PROTOCOL.md section 7.
    """
    raw = hdr[4:14]

    # Trim the ZX space padding by index, so we never build a str out of
    # bytes we are about to reject anyway.
    lo, hi = 0, len(raw)
    while lo < hi and raw[lo] == 0x20:
        lo += 1
    while hi > lo and raw[hi - 1] == 0x20:
        hi -= 1

    name = ""
    ok = True
    for i in range(lo, hi):
        b = raw[i]
        if b < 0x20 or b >= 0x7F:
            name += "?"            # control byte, BASIC token or graphics char
            ok = False
            continue
        c = chr(b)
        name += c
        if not (c.isalpha() or c.isdigit() or c in "_-"):
            ok = False             # printable, but not FAT-safe here
    return name, ok


def REFUSE_SAVE(MQ, status, quiet_ms=500):
    """Refuse a SAVE at the post-header status read. Returns bytes drained.

    This is THE way to fail a SAVE. The Z80 has sent its header and is
    polling $0F waiting for the mid-phase status; whatever we write here
    is the verdict. An error status sends it down STATUS_TO_REPORT, which
    RST-8's with a BASIC report and aborts the SAVE *before* the data
    block is transmitted.

    The alternative -- writing 0x01 "OK" and bailing out -- is what the
    header-CRC and no-data paths used to do, and it is actively harmful:
    the Z80 takes OK at face value and streams the whole data block at a
    handler that has already returned. Nobody drains it, so the
    dispatcher's next pre-header read picks up data bytes and dispatches
    on garbage, and the trailing 0x01 is read as the final status, so the
    2068 prints "0 OK" for a transfer that never produced a file.

    Statuses in use (see docs/GUSTAVO_PROTOCOL.md section 8):
        0x02 -> Report R, tape loading error  (bad header CRC, no data)
        0x03 -> Report F, invalid file name   (name not in the allowlist)
        0x06 -> Report 6, number too big      (data block won't fit in RAM)
        0x08 -> Report A, invalid argument    (empty program, BLEN=0)

    Caller is responsible for returning.
    """
    MQ.put(status)
    MQX(MQ, "mov(y, invert(null))")   # Y -> READY so the Z80 reads our status
    return DRAIN_REFUSED_SAVE(MQ, quiet_ms)


def DRAIN_REFUSED_SAVE(MQ, quiet_ms=500):
    """Resync the RX FIFO after refusing a SAVE at the post-header status.

    Refusing works by writing an error status where the Z80 expects the
    mid-phase 0x01: its STATUS_TO_REPORT path RST-8's, shows the BASIC
    report and aborts BEFORE sending the data block. When that lands no
    data arrives at all, and this returns 0 once quiet_ms (500 ms) has
    passed with nothing in RX.

    This is the safety net for when it doesn't land -- the Z80 sends the
    data block anyway, and those bytes would otherwise sit in RX and be
    misread as the next command's pre-header. Drain until the bus has
    been quiet for `quiet_ms`.

    SAVE_ZX also uses it, for a different reason: ZX mode has no status
    byte to refuse with, so its empty-save guard cannot prevent the 64K
    flood and must simply swallow it to keep the FIFO in sync.

    Returns the number of bytes drained (0 = the abort took cleanly).
    """
    n = 0
    last = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), last) < quiet_ms:
        if MQ.rx_fifo() > 0:
            MQ.get()
            n += 1
            last = time.ticks_ms()
    return n


def SAVE_TS(MQ, TSP, pre=None):
    """Receive a Z80 SAVE transaction via Gustavo's TPI v2.4 protocol.

    Called by the main I/O dispatcher when the Z80 has issued a SAVE
    pre-header. The pre-header has already been drained by the dispatcher;
    this function handles the remaining two phases (HEADER block then
    DATA block), each of which is a Z80→Pico bulk transfer terminated
    by a Pico→Z80 status byte.

    PROTOCOL OVERVIEW (see docs/PROTOCOL.md for the full guide):

      Z80's SAVE flow has three Z80-write phases interleaved with three
      status reads back from the Pico:

         Phase 1 (already done by dispatcher):
           Z80 OUTs 10-byte pre-header to $0E
           Z80 reads $0E for status — pre-loaded 0x01 satisfies it
           Z80 polls $0F (Y=READY)

         Phase 2 (this function):
           Z80 OUTs 21-byte HEADER block:
             [0]      block_type   (0x00 for header)
             [1,2]    session ID   (TPI extension; not in TAP CRC)
             [3]      HDTYPE       (0=BASIC, 1=NUMARR, 2=CHARARR, 3=CODE)
             [4-13]   filename     (10 ASCII chars)
             [14,15]  BLEN         (size of the upcoming data block, LE)
             [16,17]  ADDR         (memory address / autorun, LE)
             [18,19]  HDVARS       (variable-area offset, LE)
             [20]     CRC          (XOR of [0]+[3..19], skips session)
           Pico writes 0x01 status — Z80's mid-phase status read.
           Z80 polls $0F (Y=READY).

         Phase 3 (this function):
           Z80 OUTs (BLEN+4)-byte DATA block:
             [0]              block_type   (0xFF for data)
             [1,2]            session ID
             [3..BLEN+2]      data bytes
             [BLEN+3]         CRC
           Pico writes 0x01 final status.
           Pico writes 0x01 pre-load for next command's status read.
           Pico saves the reconstructed TAP file to SD (slow — happens
           AFTER the status writes so Z80 doesn't time out).

    CRC FORMULA (important — non-obvious):
      The header / data block CRC is the XOR of the block_type byte and
      the content bytes, *skipping the 2 session-ID bytes* at positions
      [1] and [2]. The session ID is a TPI extension on top of the
      original ZX tape format; standard ZX TAP CRC doesn't include them.

    READY + ABORT (issue #51, stage 3):
      The dispatcher does NOT say READY after a SAVE pre-header any more:
      the Z80 streams the 21-byte header block the moment it sees READY,
      ~43 us a byte into a 4-deep FIFO, so READY is raised here, straight
      before the capture loop -- after the TLM print and gc.collect(). The
      header and data block are taken by RX_CAPTURE / RX_BLOCK, which end on
      a port-0Fh write (the 1.8b ROM's BREAK or SYNC) or on silence instead
      of blocking in MQ.get(). A BREAK discards the partial SAVE -- nothing
      is written; a stall sets TSP.save_recovered so the dispatcher answers
      RECOVERED (the 1.8b ROM's Report T). Either way the dispatcher's
      ACTIVATE_MQ + 0x01 re-arm afterwards is the single way back to idle.

    Args:
        MQ:  TS_IO_DUAL state machine.
        TSP: PICO_STATUS instance. We use TSP.f_name, .append, .cur_path,
             .VERBOSE, and .LOG_LEVEL; SAVE_TS sets TSP.save_recovered.
        pre: the pre-header, for the session check (bytes 3-4 are repeated
             as bytes 1-2 of both blocks; 0000 = not from BASIC, unchecked).

    Returns:
        (MQ, TSP, log_entries, saved) for the dispatcher's calling
        convention. `saved` is True only if a .tap actually reached the
        SD card, and is the dispatcher's cue to re-mount and refresh the
        directory listing.

        The dispatcher used to infer that with
        `save_aborted = "sd" not in os.listdir("/")` -- reading the mount
        table to guess whether a file had been written. That was already
        indirect, and it got wronger as this function grew refusal paths
        that return before ENA_SD: it happens to answer correctly for
        those only because they leave /sd unmounted. It answers WRONGLY
        for the case that matters most -- a write that fails after
        ENA_SD (card pulled, disk full), where /sd is mounted, no file
        exists, and the dispatcher would go on to mount a ghost.
    """
    global log_entries
    log_entries = ""

    from TS.tspico import TLM         # lazy import: tspico imports SAVE_TS, so a
                                      # module-level import here would be circular
    wrt = MQ.put
    TSP.save_recovered = False
    gc.collect()
    TLM("SAVE_TS enter", "f_name=%r append=%s" % (TSP.f_name, TSP.append))

    # ============================================================
    # Phase 2: receive the 21-byte HEADER block
    # ============================================================
    # READY here, not in the dispatcher: the Z80 sends all 21 bytes the
    # moment it sees it, and nothing may run between this and the capture.
    raw = _SAVE_HDR_RAW
    MQ_STATUS(MQ, "mid")
    got = RX_CAPTURE(MQ, raw, 21, 1000)
    if got != 21:
        if got < 0:
            LOG_ADD("INFO: SAVE stopped by BREAK in the header block "
                    "(%d of 21 bytes); nothing written." % (-got - 1),
                    1, TSP.LOG_LEVEL)
        else:
            TSP.save_recovered = True
            LOG_ADD("ERROR: SAVE header block stalled after %d of 21 bytes "
                    "-> RECOVERED." % got, 2, TSP.LOG_LEVEL)
        TLM("SAVE_TS EXIT header", "got=%d" % got)
        return MQ, TSP, log_entries, False
    hdr = bytearray(21)
    for i in range(21):
        hdr[i] = raw[i] & 0xFF
    TLM("SAVE_TS header read", "bytes=%s" % " ".join("%02X" % b for b in hdr))

    # SESSION CHECK. The pre-header's bytes 3-4 come back as bytes 1-2 of
    # the header block; a mismatch means the bytes are misaligned (a lost
    # or stray byte), so nothing after this can be trusted. 0000 means the
    # SAVE didn't come from BASIC and carries no session.
    if pre is not None and (pre[3] or pre[4]) and (hdr[1] != pre[3] or hdr[2] != pre[4]):
        _fl = REFUSE_SAVE(MQ, 0x02)          # -> Report R
        LOG_ADD("ERROR: SAVE refused: header session %02X%02X, pre-header "
                "%02X%02X; drained %d" % (hdr[2], hdr[1], pre[4], pre[3], _fl),
                2, TSP.LOG_LEVEL)
        return MQ, TSP, log_entries, False

    # Verify CRC: XOR of [0] + [3..19] should equal hdr[20].
    # (Skip session-ID bytes at [1] and [2] — TPI extension, not in CRC.)
    crc_calc = hdr[0]
    for i in range(3, 20):
        crc_calc ^= hdr[i]
    if crc_calc != hdr[20]:
        TLM("SAVE_TS EXIT header CRC fail", "got 0x%02X want 0x%02X" % (
            hdr[20], crc_calc))
        LOG_ADD("ERROR: Bad CRC on SAVE header (got 0x%02X, expected 0x%02X)" % (
            hdr[20], crc_calc), 2, TSP.LOG_LEVEL)
        # REFUSE. This used to write 0x01 0x01 -- "OK" -- on the theory
        # that the Z80 "will see CRC fail elsewhere". It won't: the Z80
        # computed its own CRC over the bytes it sent and is satisfied
        # with them. A bad CRC here means the bytes were corrupted or
        # dropped in transit, which only WE can see. Telling the Z80 OK
        # made it stream the entire data block at a handler that had
        # already returned -- undrained, so the dispatcher read data
        # bytes as the next pre-header -- and the second 0x01 became the
        # final status, so the 2068 printed "0 OK" for a save that never
        # wrote a file.
        _fl = REFUSE_SAVE(MQ, 0x02)      # -> Report R "Tape loading error"
        LOG_ADD("SAVE refused: bad header CRC, drained %d byte(s)" % _fl,
                2, TSP.LOG_LEVEL)
        TLM("SAVE_TS CRC refusal drained", "%d residual byte(s)" % _fl)
        return MQ, TSP, log_entries, False

    # NO SD CARD. The dispatcher looked for the card before this SAVE began
    # (SD_PROBE) and found none: refuse here, at the header, so the 2068 stops
    # before sending the data block and keeps the program -- Report J, "Invalid
    # I/O device". Put a card in and SAVE again.
    if getattr(TSP, "save_no_card", False):
        _fl = REFUSE_SAVE(MQ, 0x0A)          # -> Report J
        LOG_ADD("SAVE refused: no SD card, drained %d byte(s)" % _fl, 1, TSP.LOG_LEVEL)
        return MQ, TSP, log_entries, False

    # ------------------------------------------------------------------
    # FILENAME GUARD. The 10-byte ZX name is already in hand (hdr[4:14]),
    # so judge it HERE -- at the post-header status read -- rather than
    # after the whole transfer. Refusing at this point uses the same
    # mechanism as the empty-program guard below: write an error status
    # where the Z80 expects the mid-phase 0x01, its STATUS_TO_REPORT path
    # RST-8's (status 3 -> Report F "Invalid file name") and it aborts
    # BEFORE sending the data block.
    #
    # This check used to live at the END of the function. By then the V6
    # chain had ALREADY written the final status 0x01, so the Z80 had
    # printed "0 OK" -- the verdict arrived after the verdict had been
    # announced -- and the error was then reported via END_MSG(), which
    # that function's own docstring forbids from SAVE_TS. END_MSG's ~34
    # bytes overflowed the 4-deep TX FIFO that the Z80 had already
    # stopped reading; MQ.put() blocks when TX is full, and the WATCHDOG
    # was gone (dead=True by then), so the Pico wedged in the
    # dispatcher's main loop until reset. Reproducer: SAVE "bad file"
    # -- the interior space is not in the allowlist.
    #
    # Skipped when appending: in that mode the target is the mounted TAP
    # (TSP.f_name) and the header's name is never used.
    # ------------------------------------------------------------------
    # NATIVE SAVE: SAVE "f:<path>" through the fdd ROM armed TSP.native with
    # tpi:fopen for this statement's session. The header's name is a stand-in
    # then; the file is nat["path"]. A "Replace (Y/N)?" answered N refuses it
    # here, before the data block (Report D). Any other SAVE drops a stale arm.
    nat = getattr(TSP, "native", None)
    native_save = None
    if nat and nat.get("op") == 0:
        TSP.native = None
        if pre is not None and (pre[3] | (pre[4] << 8)) == nat["session"]:
            native_save = nat
    if native_save and native_save.get("refuse"):
        _fl = REFUSE_SAVE(MQ, 0x0B)          # -> Report D, the user said N
        LOG_ADD("INFO: SAVE to %s not replaced" % native_save["path"], 0, TSP.LOG_LEVEL)
        return MQ, TSP, log_entries, False

    save_name = None
    if not native_save and not (TSP.f_name and TSP.append):
        save_name, name_ok = SAVE_NAME(hdr)
        if not name_ok:
            TLM("SAVE_TS EXIT filename not allowed", "%r" % save_name)
            _fl = REFUSE_SAVE(MQ, 0x03)      # -> Report F "Invalid file name"
            LOG_ADD('ERROR: SAVE refused: filename "%s" not allowed, '
                    "drained %d byte(s)" % (save_name, _fl), 2, TSP.LOG_LEVEL)
            TLM("SAVE_TS filename refusal drained", "%d residual byte(s)" % _fl)
            return MQ, TSP, log_entries, False

    # Compute the upcoming data block's size from header[14:16] = BLEN.
    # The data block transmitted is BLEN+4 bytes (type + 2 session + N + CRC).
    blen = hdr[14] + 256 * hdr[15]
    TLM("SAVE_TS header ok", "BLEN=%d" % blen)

    # ------------------------------------------------------------------
    # EMPTY-PROGRAM GUARD. A blank SAVE has BLEN=0, but the Z80's SA-BYTES
    # send loop decrements DE *then* tests it, so DE=0 wraps to 0xFFFF and it
    # floods 65536 bytes onto the bus (the classic ZX "SAVE 0 = SAVE 64K" ROM
    # quirk). We can't fix the 2068 ROM, so refuse the save: send an error
    # status at THIS post-header status read so the Z80's STATUS_TO_REPORT path
    # RST-8's (Report A "Invalid argument") and aborts BEFORE sending the data
    # block. No 64K flood. A bounded drain resyncs the FIFO if the Z80 floods
    # anyway (abort worked -> ~0 bytes drained).
    # ------------------------------------------------------------------
    if blen == 0:
        TLM("SAVE_TS EXIT empty (BLEN=0), refusing")
        _fl = REFUSE_SAVE(MQ, 0x08)      # -> Report A "Invalid argument"
        LOG_ADD("SAVE refused: empty program (BLEN=0), drained %d flood bytes"
                % _fl, 2, TSP.LOG_LEVEL)
        TLM("SAVE_TS empty drained", "%d residual byte(s)" % _fl)
        return MQ, TSP, log_entries, False

    long = blen + 4

    # ------------------------------------------------------------------
    # BUFFER GUARD. BLEN is a 16-bit field, so a legitimate
    # SAVE "x" CODE 0,65535 asks us for a 65539-byte bytearray -- there
    # is no bound to apply here, only a request that may not fit the
    # MicroPython heap. Unguarded, a MemoryError propagates out of the
    # dispatcher into main.py and drops the Pico to a REPL. Worse, the
    # allocation happens BEFORE the mid-phase status is written, so the
    # Z80 would also sit in WAIT EXECUTION until its ~19.9s WF_NPH
    # timeout. Collect and retry once, then refuse properly.
    # ------------------------------------------------------------------
    try:
        blk = bytearray(long)
    except MemoryError:
        gc.collect()
        try:
            blk = bytearray(long)
        except MemoryError:
            TLM("SAVE_TS EXIT no memory", "need %d bytes" % long)
            _fl = REFUSE_SAVE(MQ, 0x06)  # -> Report 6 "Number too big"
            LOG_ADD("SAVE refused: cannot allocate %d bytes, drained %d"
                    % (long, _fl), 2, TSP.LOG_LEVEL)
            return MQ, TSP, log_entries, False

    # ============================================================
    # Phase 3 setup: spawn the watchdog BEFORE announcing READY.
    #
    # Order matters. The Z80 cannot send a data byte until it sees
    # Y=READY, so spawning first means the spawn (and its OSError
    # fallback) can never overlap an in-flight burst. Spawning after
    # the READY put the thread creation inside the window where bytes
    # are already arriving into a 4-deep RX FIFO.
    # ============================================================
    # No watchdog (stage 5): RX_BLOCK bounds silence on its own, and a
    # BREAK / SYNC ends the SAVE at once. See LOAD_TS.
    TLM("SAVE_TS header ok, waiting for data", "long=%d" % long)

    # ============================================================
    # Mid-status: Pico writes 0x01 between header and data phases.
    # Z80 reads it after polling $0F (Y=READY).
    # ============================================================
    wrt(0x01)
    # READY, transaction still open: the Z80 reads the 0x01 and streams the
    # data block straight away (no ready-wait before it), so the capture loop
    # must follow at once.
    MQ_STATUS(MQ, "mid")

    # The Z80 can take up to ~1 s to start the data block after reading the
    # status (it does internal processing), so the first byte gets 1 s;
    # after that, 1 s of silence mid-block means it has gone.
    why, got = RX_BLOCK(MQ, blk, long, 1000, 1000)

    if why == RXB_STALL and got == 0:
        TLM("SAVE_TS EXIT no data after 1s")
        # Refuse rather than write 0x01 0x01. If the Z80 aborted
        # (BREAK on a ROM without the 0Fh abort) it isn't reading and the
        # byte is harmless -- the dispatcher's ACTIVATE_MQ discards it. If
        # it was merely slow, claiming OK meant it went on to stream a data
        # block into a returned handler, jamming RX for the next command.
        _fl = REFUSE_SAVE(MQ, 0x02)  # -> Report R "Tape loading error"
        LOG_ADD("ERROR: SAVE_TS aborted (no data after 1s), drained %d"
                % _fl, 2, TSP.LOG_LEVEL)
        return MQ, TSP, log_entries, False

    if why:
        # BREAK (a port-0Fh write; the 1.8b ROM checks every 256 bytes) or
        # the Z80 went silent mid-block. The partial SAVE is discarded --
        # nothing is written to SD or flash. The Z80 is waiting for READY +
        # IDLE (BREAK) or has gone (stall); the dispatcher's re-arm after we
        # return is the way back, with RECOVERED for a stall.
        if why == RXB_ABORT:
            LOG_ADD("INFO: SAVE stopped by BREAK after the Z80 sent %d of %d "
                    "bytes; nothing written." % (max(0, got - 1), long),
                    1, TSP.LOG_LEVEL)
        else:
            TSP.save_recovered = True
            LOG_ADD("ERROR: SAVE data block stalled after %d of %d bytes -> "
                    "RECOVERED; nothing written." % (got, long), 2, TSP.LOG_LEVEL)
        TLM("SAVE_TS EXIT data", "why=%d got=%d/%d" % (why, got, long))
        return MQ, TSP, log_entries, False
    TLM("SAVE_TS data read done", "%d bytes" % long)

    # ============================================================
    # CRITICAL — write final status and next-iter pre-load IMMEDIATELY.
    #
    # Z80 reads $0E for the final status as soon as we've drained its
    # last data byte. If TX FIFO is empty when Z80 reads, it gets stale
    # 0x00 and reports "Report J / Invalid I/O Device". So we MUST do
    # these two writes BEFORE the slow file-save below.
    # ============================================================
    # DATA PARITY. XOR of the flag and the content (skipping the 2 session
    # bytes) must equal the last byte. The Z80 computed it over what it
    # sent, so a mismatch means bytes were lost or corrupted in transit --
    # only we can see that. Answer Report R and write nothing, instead of
    # "0 OK" over a file that won't LOAD. Runs after the capture, while the
    # Z80 waits for its final status (it allows ~20 s).
    par = blk[0]
    for i in range(3, long - 1):
        par ^= blk[i]
    if par != blk[long - 1]:
        wrt(0x02)    # final status -> Report R
        wrt(0x01)    # next command's pre-load
        MQ_STATUS(MQ, "idle")
        # Wait (bounded) for the Z80 to READ the 02 before returning: the
        # dispatcher's ACTIVATE_MQ rebuilds the SM, which throws an unread
        # TX FIFO away and stages its own 0x01 -- and the Z80 would print
        # "0 OK" for a SAVE that wrote nothing. Same wait as the success
        # path's before ENA_SD.
        _tw = time.ticks_ms()
        while MQ.tx_fifo() > 1:
            if time.ticks_diff(time.ticks_ms(), _tw) >= 300:
                break
        LOG_ADD("ERROR: SAVE data block parity %02X, expected %02X -> Report R; "
                "nothing written." % (blk[long - 1], par), 2, TSP.LOG_LEVEL)
        TLM("SAVE_TS EXIT data parity", "got %02X want %02X" % (blk[long - 1], par))
        return MQ, TSP, log_entries, False

    wrt(0x01)        # final status — Z80 reads this and reports "0 OK"
    wrt(0x01)        # SENTINEL — do not remove. Nominally the pre-load for
                     # the next command's status read, but the dispatcher's
                     # ACTIVATE_MQ() builds a fresh StateMachine and discards
                     # it, then re-arms with its own MQ.put(0x01). Its real
                     # job is downstream: the "wait until tx_fifo() <= 1"
                     # spin before ENA_SD uses it to tell "Z80 read the final
                     # status" (2 -> 1) from "TX was always empty". Delete it
                     # as redundant and that wait returns instantly, handing
                     # back the GPIO 2-4 pin-grab race that #40 fixed.
    MQX(MQ, "mov(y, invert(null))")  # #14: Y → READY (PIO auto-busy from data phase)

    totbytes = len(hdr) + long
    TLM("SAVE_TS final status sent", "%d bytes total, Y=READY" % totbytes)

    # ============================================================
    # Reconstruct a standard TAP file from the received bytes.
    #
    # The Z80 sent us blocks in TPI format (with 2 session-ID bytes
    # inserted between block_type and the content). Standard TAP file
    # format does NOT include session bytes. We rewrite each block's
    # length prefix to skip them by overwriting the session-ID slots
    # with the prefix length bytes.
    #
    # This produces a standard TAP that any other ZX-compatible loader
    # can read.
    # ============================================================
    l_hdr = len(hdr) - 2          # header content length (= 19)
    hdr[2] = hdr[0]               # save block_type
    hdr[0] = l_hdr & 0xFF         # write len_lo where session_lo was
    hdr[1] = (l_hdr >> 8) & 0xFF  # write len_hi where session_hi was

    l_blk = len(blk) - 2
    blk[2] = blk[0]
    blk[0] = l_blk & 0xFF
    blk[1] = (l_blk >> 8) & 0xFF

    # ============================================================
    # Determine target filename
    # ============================================================
    if native_save:
        filename = native_save["path"]
        mode = "wb"
        out, kind = native.to_file(hdr[3], hdr[14] | (hdr[15] << 8), hdr[16] | (hdr[17] << 8),
                                   hdr[18] | (hdr[19] << 8), blk[3:-1])
        hdr, blk = out, b""                  # written below as-is: one native file
        TSP.native_saved = True              # the dispatcher: no mount changes, just refresh
    elif TSP.f_name and TSP.append:
        filename = TSP.f_name
        mode = "ab"
    else:
        # save_name was extracted and validated at the post-header status
        # read (see the FILENAME GUARD above), so by here it is known to
        # be FAT-safe. An all-spaces / empty ZX name is legal and lands on
        # the traditional fallback.
        clean_fname = save_name or "noname"
        filename = TSP.cur_path + "/" + clean_fname + ".tap"
        mode = "wb"
        TSP.f_name = filename

    # NOTE: write no other status here either, for the same reason as in
    # LOAD_TS. The two wrt(0x01) writes earlier already handled the final
    # status + next-iter pre-load chain. Another would orphan a status byte
    # in TX that corrupts the next transaction.

    # ============================================================
    # Write the TAP to SD card. ENA_SD() switches GPIO 2-4 from PIO
    # to SPI mode for SD access. After the write completes, the main
    # dispatcher will switch back to PIO for the next Z80 transaction.
    # ============================================================
    # RACE FIX: wait for the Z80 to actually READ the final status BEFORE
    # ENA_SD hijacks GPIO 2-4. GPIO 2 = D0 = bit 0 of the status byte, so if
    # the Z80's status read lands after the pin grab, the 0x01 corrupts to 0x00
    # -> Report J. The two status bytes were staged as (final, pre-load); wait
    # until the Z80 has consumed the final one (tx_fifo drops to <=1). Bounded
    # so a missed read can't hang the save. This is what the clean harness does.
    _tw = time.ticks_ms()
    while MQ.tx_fifo() > 1:
        if time.ticks_diff(time.ticks_ms(), _tw) >= 300:
            TLM("SAVE_TS status-read wait TIMEOUT", "tx=%d" % MQ.tx_fifo())
            break
    TLM("SAVE_TS status read confirmed", "waited %dms tx=%d" % (
        time.ticks_diff(time.ticks_ms(), _tw), MQ.tx_fifo()))
    TLM("SAVE_TS write start", "%r mode=%s" % (filename, mode))

    # The write is guarded but the failure CANNOT be reported: the final
    # status went out before ENA_SD, by design (#40 -- ENA_SD grabs
    # GPIO 2-4, and GPIO 2 is D0, so a status read landing after the grab
    # corrupts 0x01 to 0x00 and gives Report J). So the 2068 has already
    # printed "0 OK" by the time we get here. That is an accepted
    # limitation of the protocol ordering, not an oversight -- but it is
    # no reason to also take the dispatcher down. ENA_SD swallows its own
    # mount failure, so a pulled card surfaces here as OSError from
    # open(); unguarded that reaches main.py and drops the Pico to a REPL.
    saved = True
    try:
        ENA_SD(TSP.LOG_LEVEL)
        if mode == "ab" and not TSP.append:
            # The mount found a different card (SD_NOTE_CARD -> SD_REVALIDATE
            # turned append off): the card was swapped during the transfer.
            # TSP.f_name belongs to the other card; never append to a file of
            # the same name on this one.
            raise OSError(19, "a different SD card is in; not appending to %s" % filename)
        with open(filename, mode) as f1:
            f1.write(hdr)
            f1.write(blk)
    except Exception as _e:
        saved = False
        LOG_ADD("ERROR: SAVE write FAILED for %s: %s" % (filename, _e),
                2, TSP.LOG_LEVEL)
        TLM("SAVE_TS write FAILED", "%r: %s" % (filename, _e))
        if mode == "wb" and not native_save:
            # We advertised this name to the dispatcher, which would try to
            # mount it. Nothing landed, so take it back.
            TSP.f_name = ""
        TSP.native_saved = False
    try:
        os.chdir(TSP.cur_path)
    except OSError as _e:
        LOG_ADD("ERROR: chdir to %s failed after save: %s" % (TSP.cur_path, _e),
                2, TSP.LOG_LEVEL)

    if saved:
        TLM("SAVE_TS write done", "%d bytes -> %r" % (totbytes, filename))

    hdr = None
    blk = None
    gc.collect()

    if saved:
        LOG_ADD("INFO: SAVE TS complete: %d bytes -> %s" % (
            totbytes, filename), 0, TSP.LOG_LEVEL)
    return MQ, TSP, log_entries, saved


def _xor(buf, start, end):
    x = 0
    for i in range(start, end):
        x ^= buf[i]
    return x


def SAVE_ZX(MQ, TSP):
    """Receive a SAVE from the Spectrum ROM in ZX48 mode and write a TAP.

    The Spectrum ROM's SA-BYTES sends, per block and with no handshake
    after the READY poll:

        OUT ($0E),'S'   (83)      then polls $0F for READY (ZX v2 ROM),
                                  then len_lo, len_hi, flag, content, CRC

    ZX48_IO consumed the header block's 'S' when it dispatched here, so
    this reads:

        21 bytes   len_lo, len_hi, flag, 17 header bytes, CRC
         1 byte    the 'S' that opens the data block, ~1 s later
      len+4 bytes  len_lo, len_hi, flag, content, CRC

    where len comes from the tape header's length field (hdr[14:16]).
    The two length fields are then rewritten into TAP form (block length
    = content + flag + CRC) and both blocks are written to a .tap on the
    SD card named after the header.

    The Z80 reads nothing back — SA-BYTES ends with EI/RET — so there is
    no status byte to send, and sending one would leave an orphan in TX.
    A SAVE that fails is logged and not written; there is no way to tell
    the Spectrum, except that a SAVE refused at the header never gets
    READY for its data block, and the ROM gives Report R after ~3.8 s.

    Returns MQ, TSP, log_entries, nxt, as LOAD_ZX.

    No watchdog (issue #51): every wait is RX_BLOCK or RX_WORD, bounded.
    Both blocks' parity is checked, and a header or data block that
    stops, or fails its check, writes nothing -- as SAVE_TS.

    DUAL-PORT MIGRATION (2026-09):
      - Was ending with ENA_MQ(), which rebuilt the OLD single-port
        TS_IO state machine at 15 MHz and handed it back to ZX48_IO as
        the session's SM. Now ENA_MQ_DUAL().
      - RX reads are masked to 8 bits (RX_BLOCK does it). The RX word is
        9 bits (bit 8 = A0), and an unmasked value >= 256 assigned into
        a bytearray raises and drops the Pico to the REPL.
    """
    global log_entries
    log_entries = ""

    def fail(why, drain):
        LOG_ADD("ERROR: ZX SAVE: %s; nothing saved." % why, 2, TSP.LOG_LEVEL)
        if drain:
            # Swallow the rest of what the ROM is sending -- including the
            # data block's 'S', which then never gets READY -- so none of
            # it is dispatched as a command.
            DRAIN_REFUSED_SAVE(MQ, 1500)
        return MQ, TSP, log_entries, -1

    hdr = bytearray(21)

    # READY: we are here and listening. The Z80's 'S' dropped Y (PIO
    # auto-busy), and the ZX v2 ROM polls $0F before sending.
    MQX(MQ, "mov(y, invert(null))")
    code, got = RX_BLOCK(MQ, hdr, 21, ZX_STALL_MS, ZX_STALL_MS)
    if code != RXB_OK:
        return fail("the header block stopped after %d of 21 bytes" % got, False)
    if hdr[0] != 17 or hdr[1] != 0 or hdr[2] != 0 or _xor(hdr, 2, 21):
        return fail("not a tape header (length %d, flag %d, parity %s)" % (
            hdr[0] + 256 * hdr[1], hdr[2], "bad" if _xor(hdr, 2, 21) else "ok"), True)

    n = hdr[14] + 256 * hdr[15]
    try:
        gc.collect()
        blk = bytearray(n + 4)
    except MemoryError:
        return fail("no room for a %d-byte block" % n, True)

    w = RX_WORD(MQ, ZX_BLOCK_GAP_MS)
    if w != 83:
        LOG_ADD("ERROR: ZX SAVE: no data block after the header (%s); nothing saved."
                % ("silence" if w < 0 else "got 0x%02X" % (w & 0xFF)), 2, TSP.LOG_LEVEL)
        return MQ, TSP, log_entries, w
    MQX(MQ, "mov(y, invert(null))")   # READY again for the data block's poll

    code, got = RX_BLOCK(MQ, blk, n + 4, ZX_STALL_MS, ZX_STALL_MS)
    if code != RXB_OK:
        return fail("the data block stopped after %d of %d bytes" % (got, n + 4), False)
    if blk[0] + 256 * blk[1] != n or _xor(blk, 2, n + 4):
        return fail("the data block failed its check (length %d of %d, parity %s)" % (
            blk[0] + 256 * blk[1], n, "bad" if _xor(blk, 2, n + 4) else "ok"), False)

    name, _ = SAVE_NAME(hdr)
    if not name or any(c in '?:*\\/|"<>' for c in name):
        return fail("%r is not a usable file name" % name, False)

    hdr[0] = 19                     # TAP block lengths: flag + content + CRC
    blk[0] = (n + 2) & 0xFF
    blk[1] = (n + 2) >> 8

    filename = name + ".tap"
    saved = False
    try:
        ENA_SD(TSP.LOG_LEVEL)
        # After the mount, not before: ZX48 mode has no card check ahead of
        # the SAVE (the 2068 dispatcher's SD_PROBE), so this mount is where a
        # returned or swapped card is noticed, and SD_REVALIDATE may move
        # TSP.cur_path to /TAP if this card doesn't have the old folder.
        filename = TSP.cur_path + "/" + filename
        with open(filename, "wb") as f1:
            f1.write(hdr)
            f1.write(blk)
        saved = True
        # The folder's listing (CAT, and the names LOAD "tpi:..." matches) is
        # now missing this file. Re-reading it here, with the card still
        # mounted, would keep the bus off the PIO for the length of a
        # directory scan while the Spectrum may already be sending its next
        # 'L' or 'S'. tspico re-reads it at the next point that uses it and
        # where the Z80 is waiting for READY: a tpi: command (PROCESS_CMD) or
        # a ZX LOAD "tpi:..." (ZX_TPI). Found on hardware 2026-10-02: a ZX
        # SAVE "q" was on the card, but CAT didn't list it until tpi:cd.
        TSP.listing_stale = True
    except Exception as e:
        LOG_ADD("ERROR: ZX SAVE: writing %s failed: %r" % (filename, e), 2, TSP.LOG_LEVEL)
    try:
        os.umount("/sd")
    except Exception:
        pass
    # ENA_SD() re-claimed GPIO 2-4 for SPI, so the bus SM has to be
    # rebuilt before ZX48_IO's loop reads the FIFO again.
    MQ = ENA_MQ_DUAL(MQ)

    if saved:
        LOG_ADD("INFO: ZX SAVE wrote %s (%d bytes)" % (filename, n), 0, TSP.LOG_LEVEL)

    return MQ, TSP, log_entries, -1
