import gc
import os
import _thread
import time
import utime

from rp2 import StateMachine, asm_pio, PIO
from machine import Pin, freq, SPI

from TS.sdcard import *

# ---------------------------------------------------------------------------
# Module-level globals shared between LOAD_TS / SAVE_TS / WATCHDOG / etc.
#
# These get initialized inside the various functions via `global` declarations,
# but the FIRST reference to (e.g.) `kill` inside the streaming loop of
# LOAD_TS happens RIGHT AFTER spawning the watchdog thread — and there's no
# guarantee the watchdog has run its `kill = False` line yet on core1. Without
# these module-level defaults, that first reference raises NameError.
#
# Initialize them here so the race is impossible:
# ---------------------------------------------------------------------------

kill = False        # set True by WATCHDOG to abort a hung transaction
busy = False        # core1 watchdog activity flag
dead = True         # True = no transaction in progress; False = active
tx_wait_ms = 0      # TX_ROOM: how long TX had been full when the watchdog fired
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
    rx = MQ.rx_fifo
    get = MQ.get
    got = 0
    while got < n:
        if rx():
            raw[got] = get()
            got += 1
        else:
            if got and raw[got - 1] & PORT_0F:
                return -got
            t0 = time.ticks_ms()
            while not rx():
                if time.ticks_diff(time.ticks_ms(), t0) >= stall_ms:
                    return got
    if raw[n - 1] & PORT_0F:
        return -n
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
        2   the watchdog fired
        3   TX stayed full for stall_ms: the Z80 has gone away. Bounded on
            its own, because START_WATCHDOG can fail ("core1 busy") and a
            wait that only the watchdog can end would then never end.

    Data bytes the Z80 writes meanwhile (the block-type echo it sends just
    before its data loop) are kept in echo, a bytearray(3) of [count, byte,
    byte] (see ECHO_KEEP) -- never a list: this runs while the Z80 is
    streaming, and a list append can allocate, and an allocation can start
    a GC that stops core0 for 15-25 ms. The Z80 reads a byte every 50 us
    from a 4-deep FIFO, so that pause is ~300 empty reads and Report R.
    """
    global tx_wait_ms
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
        elif kill:
            tx_wait_ms = time.ticks_diff(time.ticks_ms(), t0)
            return 2
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
RXB_KILL = const(2)     # the watchdog fired
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
                if kill:
                    return RXB_KILL, got
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

patch = const(b'\xf3\xaf\x11\xff\xff\xc31\r*]\\"_\\\x18C\xc3\xed\x11\xff\xff\xff\xff\xff*]\\~\xcd}\x00\xd0\xcdt\x00\x18\xf7\xff\xff\xff\xc3\x1a7\xff\xff\xff\xff\xff\xc5*a\\\xe5\xc3-\x13\xf5\xe5*x\\#"x\\|\xb5 \x03\xfd4@\xc5\xd5\xcd\xe1\x02\xd1\xc1\xe1\xf1\xfb\xc9\xe1n\xfdu\x00\xed{=\\\xc3T\x13\xff\xff\xff\xff\xff\xff\xff\xf5\xe5*\xb0\\|\xb5 \x01\xe9\xe1\xf1\xedE*]\\#"]\\~\xc9\xfe!\xd0\xfe\r\xc8\xfe\x0c\xc8\xfe\x10\xd8\xfe\x18?\xd8#\xfe\x168\x01#7"]\\\xc9\xbfRN\xc4INKEY\xa4P\xc9F\xcePOIN\xd4SCREEN\xa4ATT\xd2A\xd4TA\xc2VAL\xa4COD\xc5VA\xccLE\xceSI\xceCO\xd3TA\xceAS\xceAC\xd3AT\xceL\xceEX\xd0IN\xd4SQ\xd2SG\xceAB\xd3PEE\xcbI\xceUS\xd2STR\xa4CHR\xa4NO\xd4BI\xceO\xd2AN\xc4<\xbd>\xbd<\xbeLIN\xc5THE\xceT\xcfSTE\xd0DEF F\xceCA\xd4FORMA\xd4MOV\xc5ERAS\xc5OPEN \xa3CLOSE \xa3MERG\xc5VERIF\xd9BEE\xd0CIRCL\xc5IN\xcbPAPE\xd2FLAS\xc8BRIGH\xd4INVERS\xc5OVE\xd2OU\xd4LPRIN\xd4LLIS\xd4STO\xd0REA\xc4DAT\xc1RESTOR\xc5NE\xd7BORDE\xd2CONTINU\xc5DI\xcdRE\xcdFO\xd2GO T\xcfGO SU\xc2INPU\xd4LOA\xc4LIS\xd4LE\xd4PAUS\xc5NEX\xd4POK\xc5PRIN\xd4PLO\xd4RU\xceSAV\xc5RANDOMIZ\xc5I\xc6CL\xd3DRA\xd7CLEA\xd2RETUR\xceCOP\xd9DELET\xc5ON ER\xd2STIC\xcbSOUN\xc4FRE\xc5RESE\xd4BHY65TGVNJU74RFCMKI83EDX\x0eLO92WSZ \rP01QA\xe3\xc4\xe0\xe4\xb4\xbc\xbd\xbb\xaf\xb0\xb1\xc0\xa7\xa6\xbe\xad\xb2\xba\xe5\xa5\xc2\xe1\xb3\xb9\xc1\xb8~\xdc\xda\\\xb7{}\xd8\xbf\xae\xaa\xab\xdd\xde\xdf\x7f\xb5\xd6|\xd5]\xdb\xb6\xd9[\xd7\x0c\x07\x06\x04\x05\x08\n\x0b\t\x0f\xe2*?\xcd\xc8\xcc\xcb^\xac-+=.,;"\xc7<\xc3>\xc5/\xc9`\xc6:\xd0\xce\xa8\xca\xd3\xd4\xd1\xd2\xa9\xcf./\x11\xff\xff\x01\xfe\xfe\xedx/\xe6\x1f(\x0eg}\x14\xc0\xd6\x08\xcb<0\xfaS_ \xf4-\xcb\x008\xe6z<\xc8\xfe(\xc8\xfe\x19\xc8{ZW\xfe\x18\xc9\xcd\xb0\x02\xc0!\x00\\\xcb~ \x07#5+ \x026\xff}!\x04\\\xbd \xee\xcd\\\x03\xd0\xfd\xcb0\xae!\x00\\\xbe(.\xeb!\x04\\\xbe(\'\xcb~ \x04\xeb\xcb~\xc8_w#6\x05#:\t\\w#\xfdN\x07\xfdV\x01\xe5\xcdq\x03\xe1w2\x08\\\xfd\xcb\x01\xee\xc9#6\x05#:\x08\\\xfe\xce\xd05\xc0:\n\\w#~\xfe\x0c \xe2\xfd\xcb0\xee\xf5\x01 N\x0by\xb0 \xfb\xf1\x18\xd2B\x16\x00{\xfe\'\xd0\xfe\x18 \x03\xcbx\xc0!\'\x02\x19~7\xc9{\xfe:8/\r\xfa\x8d\x03(\x03\xc6O\xc9!\r\x02\x04(\x03!\'\x02\x16\x00\x19~\xc9!K\x02\xcb@(\xf4\xcbZ(\n\xfd\xcb0^\xc0\x04\xc0\xc6 \xc9\xc6\xa5\xc9\xfe0\xd8\r\xfa\xdb\x03 \x19!v\x02\xcbh(\xd3\xfe80\x07\xd6 \x04\xc8\xc6\x08\xc9\xd66\x04\xc8\xc6\xfe\xc9!R\x02\xfe9(\xba\xfe0(\xb6\xe6\x07\xc6\x80\x04\xc8\xee\x0f\xc9\x04\xc8\xcbh!R\x02 \xa4\xd6\x10\xfe"(\x06\xfe \xc0>_\xc9>@\xc9\xf3}\xcb=\xcb=/\xe6\x03O\x06\x00\xdd!\x0f\x04\xdd\t:H\\\xe68\x0f\x0f\x0f\xf6\x08\x00\x00\x00\x04\x0c\r \xfd\x0e?\x05\xc2\x14\x04\xee\x10\xd3\xfeDO\xcbg \tz\xb3(\tyM\x1b\xdd\xe9M\x0c\xdd\xe9\xfb\xc9\xef1\'\xc0\x034\xecl\x98\x1f\xf5\x04\xa1\x0f8!\x92\\~\xa7 ^#N#Fx\x17\x9f\xb9 T#\xbe Px\xc6<\xf2c\x04\xe2\xaa\x04\x06\xfa\x04\xd6\x0c0\xfb\xc6\x0c\xc5!\xac\x04\xcd\xc57\xcds7\xef\x048\xf1\x86w\xef\xc0\x0218\xcd\x1e\x1f\xfe\x0b0"\xef\xe0\x04\xe04\x80CU\x9f\x80\x01\x0545q\x038\xcd#\x1f\xc5\xcd#\x1f\xe1PYz\xb3\xc8\x1b\xc3\xf3\x03\xcf\n\x89\x02\xd0\x12\x86\x89\n\x97`u\x89\x12\xd5\x17\x1f\x89\x1b\x90A\x02\x89$\xd0S\xca\x89.\x9d6\xb1\x898\xffI>\x89C\xffjs\x89O\xa7\x00T\x89\\\x00\x00\x00\x89i\x14\xf6$\x89v\xf1\x10\x05\xcdT(:;\\\x87\xfa\xed\x1b\xe1\xd0\xe5\xcd\xaf/bk\r\xf8\t\xcb\xfe\xc9\xcd\t\n\xfe \xd2\xf0\x05\xfe\x0c \x07\xfd\xcb\x01f\xca\xf0\x05\xfe\x068i\xfe\x180e!"\x05_\x16\x00\x19^\x19\xe5\xc3\x1a\x06NW\x10)TSR7PO_^]\\[ZTS\x0c>"\xb9 \x11\xfd\xcb\x01N \t\x04\x0e\x02>\x19\xb8 \x03\x05\x0e!\xc3\x14\t:\x91\\\xf5\xfd6W\x01> \xcd\xf0\x05\xf12\x91\\\xc9\xfd\xcb\x01N\xc2#\n\x0e!\xcd\x90\x07\x05\xc3\x14\t\xcd\x1a\x06y==\xe6\x10\x18Z>?\x18l\x11\x9e\x052\x0f\\\x18\x0b\x11\x84\x05\x18\x03\x11\x9e\x052\x0e\\*Q\\s#r\xc9\x11\x00\x05\xcd\x97\x05*\x0e\\W}\xfe\x16\xda\xbb# )DJ>\x1f\x918\x0c\xc6\x02O\xfd\xcb\x01N \x16>\x16\x90\xda)\x1f<G\x04\xfd\xcb\x02F\xc2\x90\x07\xfd\xbe1\xda\xc1\x07\xc3\x14\t|\xcd\x1a\x06\x81=\xe6\x1f\xc8W\xfd\xcb\x01\xc6> \xcdv\x07\x15 \xf8\xc9\xcd;\x06\xfd\xcb\x01N \x1a\xfd\xcb\x02F \x08\xedC\x88\\"\x84\\\xc9\xedC\x8a\\\xedC\x82\\"\x86\\\xc9\xfdqE"\x80\\\xc9\xfd\xcb\x01N \x14\xedK\x88\\*\x84\\\xfd\xcb\x02F\xc8\xedK\x8a\\*\x86\\\xc9\xfdNE*\x80\\\xc9\xfe\x0c \x04>z\x18Q\xfe|(M\xfe~(I\xfe{8\n\xfe\x800\x06\xfd\xcb\x01f(;\xfe\x808=\xfe\x900&G\xcdm\x06\xcd\x1a\x06\x11\x92\\\x18G!\x92\\\xcds\x06\xcb\x18\x9f\xe6\x0fO\xcb\x18\x9f\xe6\xf0\xb1\x0e\x04w#\r \xfb\xc9\xd6\xa50\t\xc6\x15\xc5\xedK{\\\x18\x0b\xcdE\x07\xc3\x1a\x06\xc5\xedK6\\\xeb!;\\\xcb\x86\xfe  \x02\xcb\xc6&\x00o)))\t\xc1\xeby=>! \x0e\x05O\xfd\xcb\x01N(\x06\xd5\xcd#\n\xd1y\xb9\xd5\xcc\x90\x07\xd1\xc5\xe5:\x91\\\x06\xff\x1f8\x01\x04\x1f\x1f\x9fO>\x08\xa7\xfd\xcb\x01N(\x05\xfd\xcb0\xce7\xeb\x08\x1a\xa0\xae\xa9\x12\x088\x13\x14#= \xf2\xeb%\xfd\xcb\x01N\xcc\x10\x07\xe1\xc1\r#\xc9\x08> \x83_\x08\x18\xe6|\x0f\x0f\x0f\xe6\x03\xf6Xg\xed[\x8f\\~\xab\xa2\xab\xfd\xcbWv(\x08\xe6\xc7\xcbW \x02\xee8\xfd\xcbWf(\x08\xe6\xf8\xcbo \x02\xee\x07w\xc9\xe5&\x00\xe3\x18\n\x11\x98\x00\xfe[8\x02\xd6\x1f\xf5\xcd|\x078\t> \xfd\xcb\x01F\xccv\x07\x1a\xe6\x7f\xcdv\x07\x1a\x13\x870\xf5\xd1\xfeH(\x03\xfe\x82\xd8z\xfe\x03\xd8> \xd5\xd9\xd7\xd9\xd1\xc9\xf5\xeb<\xcb~#(\xfb= \xf8\xeb\xf1\xfe \xd8\x1a\xd6A\xc9\xfd\xcb\x01N\xc0\x11\x14\t\xd5x\xfd\xcb\x02F\xc2=\x08\xfd\xbe18\x1b\xc0\xfd\xcb\x02f(\x16\xfd^-\x1d(Z>\x00\xcd0\x12\xed{?\\\xfd\xcb\x02\xa6\xc9\xcf\x04\xfd5R E>\x18\x902\x8c\\*\x8f\\\xe5:\x91\\\xf5>\xfd\xcd0\x12\xaf\x113\x08\xcd?\x07\xfd\xcb\x02\xee!;\\\xcb\xde\xcb\xae\xd9\xcd\xcf\x11\xd9\xfe (E\xfe\xe2(A\xf6 \xfen(;>\xfe\xcd0\x12\xf12\x91\\\xe1"\x8f\\\xcd9\t\xfdF1\x04\x0e!\xc5\xcd\xd6\t|\x0f\x0f\x0f\xe6\x03\xf6Xg\x11\xe0Z\x1aN\x06 \xeb\x12q\x13#\x10\xfa\xc1\xc9\x80scroll\xbf\xcf\x0c\xfe\x028\x80\xfd\x861\xd6\x19\xd0\xedD\xc5G*\x8f\\\xe5*\x91\\\xe5\xcd\x88\x08x\xf5!k\\Fx<w!\x89\\\xbe8\x034\x06\x18\xcd;\t\xf1= \xe8\xe1\xfduW\xe1"\x8f\\\xedK\x88\\\xfd\xcb\x02\x86\xcd\x14\t\xfd\xcb\x02\xc6\xc1\xc9\xaf*\x8d\\\xfd\xcb\x02F(\x04g\xfdn\x0e"\x8f\\!\x91\\ \x02~\x0f\xae\xe6U\xaew\xc9\xcd\xea\x08!<\\\xcb\xae\xcb\xc6\xcd\x88\x08\xfdF1\xcd\x7f\t!\xc0Z:\x8d\\\x05\x18\x07\x0e +w\r \xfb\x10\xf7\xfd61\x02>\xfd\xcd0\x12*Q\\\x11\x00\x05\xa7s#r#\x11\x0e\x0c?8\xf6\x01!\x17\x18*!\x00\x00"}\\\xfd\xcb0\x86\xcd\xcf\x08>\xfe\xcd0\x12\xcd\x88\x08\x06\x18\xcd\x7f\t*Q\\\x11\x00\x05s#r\xfd6R\x01\x01!\x18!\x00[\xfd\xcb\x01N \x12x\xfd\xcb\x02F(\x05\xfd\x861\xd6\x18\xc5G\xcd\xd6\t\xc1>!\x91_\x16\x00\x19\xc3\xf3\x05\x06\x17\xcd\xd6\t\x0e\x08\xc5\xe5x\xe6\x07x \x0c\xeb!\xe0\xf8\x19\xeb\x01 \x00=\xed\xb0\xeb!\xe0\xff\x19\xebG\xe6\x07\x0f\x0f\x0fOx\x06\x00\xed\xb0\x06\x07\t\xe6\xf8 \xdb\xe1$\xc1\r \xcd\xcd\xc3\t!\xe0\xff\x19\xeb\xed\xb0\x06\x01\xc5\xcd\xd6\t\x0e\x08\xc5\xe5x\xe6\x07\x0f\x0f\x0fOx\x06\x00\rT]6\x00\x13\xed\xb0\x11\x01\x07\x19=\xe6\xf8G \xe5\xe1$\xc1\r \xdc\xcd\xc3\tbk\x13:\x8d\\\xfd\xcb\x02F(\x03:H\\w\x0b\xed\xb0\xc1\x0e!\xc9|\x0f\x0f\x0f=\xf6Pg\xebah)))))DM\xc9>\x18\x90W\x0f\x0f\x0f\xe6\xe0oz\xe6\x18\xf6@g\xc9\xf5\xc5\xd5\x01@\x9c\x0by\xb0 \xfb\xaf\xdb\xfe\xe6\x1f\xfe\x1f(\xf7\xcd\xa9\x08\xd1\xc1\xf1\xc9\xd9!0\x16\xc3\xe3<\xfd\xcb\x01N\xca\x1a\x06\xfe\x800T"\xcd]!9\x16\x184\xedS\xd7]\xc3\x14\n\xc3\xf9<"\xcd]!<\x16\xc3P\n\x00>\x04\xd3\xfb\xfb!\x00[\xfduF\xafGw#\x10\xfc\xfd\xcb0\x8e\x0e!\xc3\x14\t"\xcd]!3\x16\xe5!\xfe\xfe\xe5\xf5:\xc2\\\xa7*\xcd]\xc2d\n\xf1\xcdre\xf1\xcd2\xfd\xfe\xa5\xdas\n\xd6\xa5\xcdE\x07\xc9\xfe\x90\xd2&\nG\xf5\xcdm\x06\xf1\xc3a%\x00*=\\\xe5!\xe5\x0b\xe5\xeds=\\\xcd\xcf\x11\xf5\x16\x00\xfd^\xff!\xc8\x00\xcd\xf3\x03\xf1!\x8e\n\xe5\xfe\x0c \x0c\xfd\xcb0n \x06\xfd\xcb\x01^(5\xfe\x1801\xfe\x078-\xfe\x108:\x01\x02\x00W\xfe\x168\x0c\x03\xfd\xcb7~\xca\x84\x0b\xcd\xcf\x11_\xcd\xcf\x11\xd5*[\\\xfd\xcb\x07\x86\xcd\xbb\x12\xc1#p#q\x18\n\xfd\xcb\x07\x86*[\\\xcd\xb8\x12\x12\x13\xedS[\\\xc9_\x16\x00!\xff\n\x19^\x19\xe5*[\\\xc9\tfjP\xb5p~\xcf\xd4*I\\\xfd\xcb7n\xc2\xfd\x0b\xcd\xd6\x16\xcd$\x13z\xb3\xca\xfd\x0b\xe5#N#F!\n\x00\tDM\xcd\xbb\x1f\xcd\xfd\x0b*Q\\\xe3\xe5>\xff\xcd0\x12\xe1+\xfd5\x0f\xcd\xac\x15\xfd4\x0f*Y\\####"[\\\xe1\xcdH\x12\xc9\xfd\xcb7n \x08!I\\\xcd[\x16\x18m\xfd6\x00\x10\x18\x1d\xcd\x97\x0b\x18\x05~\xfe\r\xc8#"[\\\xc9\xcd\x97\x0b\x01\x01\x00\xc3P\x17\xcd\xcf\x11\xcd\xcf\x11\xe1\xe1\xe1"=\\\xfd\xcb\x00~\xc0\xf9\xc97\xcd\xfb\x0c\xedR\x19#\xc1\xd8\xc5DMbk#\x1a\xe6\xf0\xfe\x10 \t#\x1a\xd6\x17\xce\x00 \x01#\xa7\xedB\t\xeb8\xe6\xc9\xfd\xcb7n\xc0*I\\\xcd\xd6\x16\xeb\xcd$\x13!J\\\xcdh\x16\xcd\xe1\x14>\x00\xc30\x12\xfd\xcb7~(\xa8\xc3\xe7\n\xfd\xcb0f(\xa1\xfd6\x00\xff\x16\x00\xfd^\xfe!\x90\x1a\xcd\xf3\x03\xc3\x86\n\xe5\xcd\xf6\x0c+\xcdM\x17"[\\\xfd6\x07\x00\xe1\xc9\xfd\xcb\x02^\xc4\x83\x0c\xa7\xfd\xcb\x01n\xc8:\x08\\\xfd\xcb\x01\xae\xf5\xfd\xcb\x02n\xc4\xa9\x08\xf1\xfe 0R\xfe\x100-\xfe\x060\nG\xe6\x01Ox\x1f\xc6\x12\x18* \t!j\\>\x08\xaew\x18\x0e\xfe\x0e\xd8\xd6\r!A\\\xbew \x026\x00\xfd\xcb\x02\xde\xbf\xc9G\xe6\x07O>\x10\xcbX \x01<\xfdq\xd3\x11s\x0c\x18\x06:\r\\\x11\x0e\x0c*O\\##s#r7\xc9\xcd\x88\x08\xfd\xcb\x02\x9e\xfd\xcb\x02\xae*\x8a\\\xe5*=\\\xe5!\xcd\x0c\xe5\xeds=\\*\x82\\\xe57\xcd\xfb\x0c\xeb\xcd\xc9\x15\xeb\xcd-\x16*\x8a\\\xe3\xeb\xcd\x88\x08:\x8b\\\x928& \x06{\xfd\x96P0\x1e> \xd5\xcd\x00\x05\xd1\x18\xe9\x16\x00\xfd^\xfe!\x90\x1a\xcd\xf3\x03\xfd6\x00\xff\xed[\x8a\\\x18\x02\xd1\xe1\xe1"=\\\xc1\xd5\xcd\x14\t\xe1"\x82\\\xfd6&\x00\xc9*a\\+\xa7\xed[Y\\\xfd\xcb7n\xc8\xed[a\\\xd8*c\\\xc9~\xfe\x0e\x01\x06\x00\xccP\x17~#\xfe\r \xf1\xc9\xf3>\xff\xed[\xb2\\\xd9\xedK\xb4\\\xed[8\\*{\\\xd9G>\x07\xd3\xfe>?\xedG\x00\x00\x00\x00\x00\x00bk6\x02+\xbc \xfa\xa7\xedR\x19#0\x065(\x035(\xf3+\xd9\xedC\xb4\\\xedS8\\"{\\\xd9\x04(\x19"\xb4\\\x11\xaf>\x01\xa8\x00\xeb\xed\xb8\xeb#"{\\+\x01@\x00\xedC8\\"\xb2\\!\x00<"6\\!\x00b"\xc0\\+6>+\xf9++"=\\\xedV\x00\xfd!:\\!@h"O\\\x11\xaa\x11\x01\x15\x00\xeb\xed\xb0\xeb>82\x8d\\2\x8f\\2H\\!#\x05"\t\\\xfd5\xc6\xfd5\xca!\xc1\x11\x11\x10\\\x01\x0e\x00\xed\xb0\xaf\xd3\xff\xfd\xcb\x01\xce\xcd5\n\xfd61\x02\xcd\xa6\x08\xaf\xfd\xcb\x01\xe6\x11\x17\x11\xcd?\x07\xfd\xcb\x02\xee!\x0b\x0e\x11\x00`\x01\x1d\x00\xed\xb0\xcd\x00`!\xcee"\xcee!\xe7\x08\xcd\x15h>\x01\xd3\xf4\xdb\xff\xcb\xff\xd3\xff!\x00\x10\x11\x00b\x010\x06\xed\xb0\xcb\xbf\xd3\xff\xaf\xd3\xf4\xc9\xfd61\x02\xcd\xe1\x14\xcd?\x13>\x00\xcd0\x12\xcd\x82\n\xcd\'\x1a\xfd\xcb\x00~ \x12\xfd\xcb0f(D*Y\\\xcd\r\r\xfd6\x00\xff\x18\xdd*Y\\"]\\\xcdh\x17x\xb1\xc2X\x11\xdf\xfe\r(\xc0\xfd\xcb0F\xc4\xea\x08\xcd\xa9\x08>\x19\xfd\x96O2\x8c\\\xfd\xcb\x01\xfe\xfd6\x00\xff\xfd6\n\x01\xfd6|\x00\xcd\xd8\x1av\xfd~\x00\xfe\xff(3\xfd\xcb}~(-\xfd\xcb}\xf6<2\xbb\\\xfd6\x00\xff*E\\"\xb8\\:G\\2\xba\\*\xb6\\\xcb\xbc\xcb\xb4"B\\\xfd6\n\x01!\x8d\x0e\xe5\xc3\xb9\x1a>\x07\xd3\xf5>\xff\xd3\xf6\xfd\xcb\x02\x9e\xfd\xcb\x01\xae\xfd\xcb0N\xc4#\n::\\<\xf5!\x00\x00\xfdt7\xfdt&"\x0b\\!\x01\x00"\x16\\\xcd?\x13\xfd\xcb7\xae\xcd\xa9\x08\xfd\xcb\x02\xee\xf1G\xfe\n8\x02\xc6\x07\xcd\xea\x11> \xd7x\x11e\x0f\xcd?\x07\xaf\x11\x15\x11\xcd?\x07\xedKE\\\xcd\x88\x17>:\xd7\xfdN\r\x06\x00\xcd\x88\x17\xcd\xfd\x0b::\\<(\x1b\xfe\t(\x04\xfe\x15 \x03\xfd4\r\x01\x03\x00\x11p\\!D\\\xcb~(\x01\t\xed\xb8\xfd6\n\xff\xfd\xcb\x01\x9e\xfd\xcb\x02\x9e\xc32\x0e\x80O\xcbNEXT without FO\xd2Variable not foun\xe4Subscript wron\xe7Out of memor\xf9Out of scree\xeeNumber too bi\xe7RETURN without GOSU\xc2End of fil\xe5STOP statemen\xf4Invalid argumen\xf4In\xf3\x18F\xff\xff\xff\xff\xff*]\\"_\\\xe1n\xfdu\x00\xed{=\\!T\x13\xe5&\xff.\x00\xe5\xf5:\xc2\\\xa7\xfb(\x04\xf1\xcd2\xfd\xf1\xcdre\xff\xff\xff\x01\x05\xad\x07\x10\xf5\xf3:\xc2\\\xa7\x00(\x04\xf1\xc3n\xfa\xf1\xc3\xaeb>\x01\xd3\xf4\x18\x0b\xaf\xd3\xf4\xd3\xff\x11\xff\xff\xc31\r!O\x00\x11\x00`\x01\x0b\x00\xed\xb0\xc3\x00`\xc3s\x18\xe5!\x80\x1f\xcb\x7f(\x03!\x98\x0c\x08\x13\xdd+\xf3>\x02G\x10\xfe\xd3\xfe\xee\x0f\x06\xa4- \xf5\x05%\xf2~\x00\x06/\x10\xfe\xd3\xfe>\r\x067\x10\xfe\xd3\xfe\x01\x0e;\x08o\xc3\xad\x00z\xb3(\x0c\xddn\x00|\xadg>\x017\xc3\xcb\x00l\x18\xf4y\xcbx\x10\xfe0\x04\x06B\x10\xfe\xd3\xfe\x06> \xef\x05\xaf<\xcb\x15\xc2\xba\x00\x1b\xdd#\x061>\x7f\xdb\xfe\x1f\xd0z<\xc2\xa4\x00\x06;\x10\xfe\xc9\xf5:H\\\xe68\x0f\x0f\x0f\xd3\xfe>\x7f\xdb\xfe\x1f\xfb8\x02\xcf\x0c\xf1\xc9\xc3\xa0\x19\xf3>\x0f\xd3\xfe!\xe5\x00\xe5\xdb\xfe\x1f\xe6 \xf6\x02O\xbf\xc0\xcd\x8d\x010\xfa!\x15\x04\x10\xfe+|\xb5 \xf9\xcd\x89\x010\xeb\x06\x9c\xcd\x89\x010\xe4>\xc6\xb80\xe0$ \xf1\x06\xc9\xcd\x8d\x010\xd5x\xfe\xd40\xf4\xcd\x8d\x01\xd0y\xee\x03O&\x00\x06\xb0\x18\x1f\x08 \x070\x0f\xddu\x00\x18\x0f\xcb\x11\xad\xc0y\x1fO\x13\x18\x07\xdd~\x00\xad\xc0\xdd#\x1b\x08\x06\xb2.\x01\xcd\x89\x01\xd0>\xcb\xb8\xcb\x15\x06\xb0\xd2p\x01|\xadgz\xb3 \xca|\xfe\x01\xc9\xcd\x8d\x01\xd0>\x16= \xfd\xa7\x04\xc8>\x7f\xdb\xfe\x1f\xd0\xa9\xe6 (\xf3y/O\xe6\x07\xf6\x08\xd3\xfe7\xc9\xc3\x10\x02\x01\xe1\x19\x912t\\\xd9!O%\xc3\xdd\x08\xcd\x1d\x08=\xc3\xf6\x03\xcd\xb9\x02\xc3\xf1\x04\xc3\xdd\x03\xfd\xcb\x01~(f\xc3|\x1a:t\\\xa7(\x02\x0e"\xcd\xe2\x01\x18\x12\xdd\xe5\xd9!0\x00\x18\xdf\xd9!\x83$\xc3\xdd\x08\x00\x00\x00\xd5\xdd\xe1\x06\x0b> \x12\x13\x10\xfc\xdd6\x01\xff\xcd\x08\x02\x18\x12\xdd\xe5\xd9!\xaf/\x18\xb9!\xea\x01\xe5:t\\\xc3\xae\x01!\xf6\xff\x0b\t\x030\x0f:t\\\xa7 \x02\xcf\x0ex\xb1(\n\x01\n\x00\xdd\xe5\xe1#\xeb\xed\xb0\xcd=\x02\x18\x12\xdd\xe5\xd9!\x18\x00\x18\x84\xd9!\x08\x00\xc3\xdd\x08\x00\x00\x00\xfe\xe4\xc2\xf2\x02:t\\\xfe\x03\xca\xd9\x08\x18"\xcd\xc1\x03\x13z\xb3>\x01\xc8>\x00\xc9\x00\x00\x00\xaf\xc9\xfe\x80\xc2[\x1c\xcd\xb9\x02\xcd\xf1\x04\xc3_\x04\x00\x00\x00\xcd\xd7\x02\xcd\xe0\x02\xcb\xf90\x0b!\x00\x00:t\\=(\x16\xcf\x01\xc2\xd9\x08\xfd\xcb\x01~(\x18#~\xddw\x0b#~\xddw\x0c#\xddq\x0e>\x01\xcbq(\x01<\xddw\x00\xeb\x18\x12\xcdd\x18\xa7(\x02=\xc9<\xc9\'ki\x1c\x0c\x1c\x10\x1a\xcd\xd7\x02\xfe) \xc3\xcd\xd7\x02\x18\x12\xdd\xe5\xd9! \x00\xc3\xdd\x03\xdd\xe5\xd9!p,\xc3\xdd\x03\xfd\xcb\x01~\xc8\xeb\xc3\xc9\x04\xfe\xaa 8:t\\\xfe\x03\xca\xd9\x08\xcd\xd7\x02\x18\x12\xdd\xe5\xd9!\x18\x00\xc3\xdd\x03\xdd\xe5\xd9!\x10\x00\xc3\xdd\x03\xfd\xcb\x01~\xc8\xdd6\x0b\x00\xdd6\x0c\x1b!\x00@\xddu\r\xddt\x0e\xc3@\x04\xfe\xaf\xc2G\x04:t\\\xfe\x03\xca\xd9\x08\xdd\xe5\xd9! \x00\xe5.\x00&\xff\xe5!\x00\x00\xe5\xe5\xd9\xcd\x99\x0f\xd9!\xe7!\xe5.\x00&\xff\xe5!\x00\x00\xe5\xe5\xd9\xcd\x99\x0f\xdd\xe1  :t\\\xa7\xca\xd9\x08\xcds\x03\x18\x12\xdd\xe5\xd9!Q\x1c\xc3\xdd\x03\xdd\xe5\xd9!#\x1f\xc3\xdd\x03\x185\xdd\xe5\xdd\xe5\xcd\x92\x03\xdd\xe1\x18\n\xd9!X%\xc3\xdd\x08\x00\x00\x00\xd9!\x18\x00\xe5.\x00&\xff\xe5!\x00\x00\xe5\xe5\xd9\xcd\x99\x0f\xdd\xe1\xfe,( :t\\\xa7\xca\xd9\x08\xcds\x03\x18\x12\xdd\xe5\xd9!\xb0\x02\xc3\xdd\x03\xdd\xe5\xd9!\xe5\x1b\xc3\xdd\x03\x18*\xcd\xd7\x02\xcd\xca\x03\x18"\xe5!\x00\xff\xe5&\x00\xe5\xe5\xd9\xcd\x99\x0f\xdd\xe1\xc9\xdd\xe5\xd9!?\x07\xc3\xdd\x03>\xff2\xcf]\xc3\xc2\x1c\x00\xfd\xcb\x01~\xc8\xdd\xe5\xcd\r\x04\xdd\xe1\x18\x0e\xd9!\xdc<\xc3\xdd\x08>\t7\xc9\x00\x00\x00\xddq\x0b\xddp\x0c\xcd|\x03\x18\x12\xdd\xe5\xd9!0\x12\xc3\xdd\x03\xdd\xe5\xd9!\xaf/\xc3\xdd\x03\xddq\r\xddp\x0e`i\xdd6\x00\x03\xc3\xc9\x04\xfe\xca(\x0b\xfd\xcb\x01~\xc8\xdd6\x0e\x80\x18S:t\\\xa7\xc2\xd9\x08\x18"\xf5\x18\x03\xcd\xfa\x05\xcd\x8e\x068\x03\xc3\xf2\x06\xf1\xa7\xc9\x00\xcd\xc1\x03\x13z\xb3 \xf8\xcdF\x05(\xfb\xc3R\x1c\xcd\xd7\x02\xcd\xca\x03\xfd\xcb\x01~\xc8\xdd\xe5\xd9!#\x1f\xe5.\x00&\xff\xe5!\x00\x00\xe5\xe5\xd9\xcd\x99\x0f\xdd\xe1\xddq\r\xddp\x0e\xdd6\x00\x00*Y\\\xed[S\\7\xedR\xddu\x0b\xddt\x0c*K\\\xedR\xddu\x0f\xddt\x10\xeb:t\\\xa7\xcaQ\x08\xe5\x01\x11\x00\xdd\t\xdd\xe5\x11\x11\x00\xaf7\xcd\xfc\x00\xdd\xe10\xf2>\xfe\x18\x12\xe5!\x00\x00"\xd1]\xe1\xc9\xf5>\xfe\xcd&\x04\xf1\xc9\x00\xcd&\x04\xfd6R\x03\x0e\x80\xdd~\x00\xdd\xbe\xef \x02\x0e\xf6\xfe\x040\xc5\x11\xa8<\xc5\xdd\xe5\xd9!?\x07\xe5.\x00&\xff\xe5!\x00\x00\xe5\xe5\xd9\xcd\x99\x0f\xdd\xe1\xc1\xdd\xe5\xd1!\xf0\xff\x19\x06\n~< \x03y\x80O\x13\x1a\xbe# \x01\x0c\x18\x12\xfd\xcb\x01\xae\xfd\xcb\x01\xde\xcd\xc1\x03\xaf\xfd\xcb\x01n\x18\x0e\xcd\x0c\x03\x10\xe0\xcby\xc2\xd6\x04>\r\x18\x12\xc8:\x08\\\xe6\x7f\xfea\xd8\xfe{\xd0\xe6\xdf\xc9\x00\x00\x00\xcd\x0c\x03\xe1\xdd~\x00\xfe\x03(\x0c:t\\=\xca\xcc\x05\xfe\x02\xca\xe5\x06\xe5\xddn\xfa\xddf\xfb\xdd^\x0b\xddV\x0c|\xb5(\r\xedR8&(\x07\xdd~\x00\xfe\x03 \x1d\xe1|\xb5 \x06\xddn\r\xddf\x0e\xe5\xdd\xe1:t\\\xfe\x027 \x01\xa7>\xff\xcd\xfc\x00\xd8\xcf\x1a\xdd^\x0b\xddV\x0c\xe5|\xb5 \x06\x13\x13\x13\xeb\x18\x0c\xddn\xfa\xddf\xfb\xeb7\xedR8\x1d\x11\x05\x00\x19DM\x18\x12\xdd\xe5\xd9!\xbb\x1f\xc3\xdd\x03\xfd6R\xff\xc3\x0c\x03\x00\x00\xcd\xf1\x05\xe1\xdd~\x00\xa7(f|\xb5(\'+F+N+\x03\x03\x03\xdd"_\\\xdd\xe5\xd9!P\x17\xe5.\x00&\xff\xe5!\x00\x00\xe5\xe5\xd9\xcd\x99\x0f\xdd\xe1\xdd*_\\*Y\\+\xddN\x0b\xddF\x0c\xc5\x03\x03\x03\xdd~\xfd\xf5\x18\x12\xdd\xe5\xd9!\xbb\x12\xc3\xdd\x03\xcd\x9f\x06\xd2\xaa\x06\xdb\x0f\xc9\xcdL\x06#\xf1w\xd1#s#r#\xe5\xdd\xe17>\xff\xc3\xc6\x05\xeb*Y\\+\xdd"_\\\xddN\x0b\xddF\x0c\xc5\x18\x12\xdd\xe5\xd9!M\x17\xc3\xdd\x03\xcdd\x18\xa7\xc8\xfe\x80?\xc9\xcd\x85\x06\xc1\xe5\xc5\x18\x12\xcdV\x08\x1f\xd8>\xfe\xdb\xfe\x1f\xc9\xc1\xc3q\x1a\x00\x00\x00\xcdL\x06\xdd*_\\#\xddN\x0f\xddF\x10\t"K\\\xddf\x0e|\xe6\xc0 \n\xddn\r"B\\\xfd6\n\x00\xd1\xdd\xe17>\xff*S\\+"W\\\xc3\xc6\x05\xddN\x0b\xddF\x0c\xc5\x03\xcd\xe2\x01\x18\x12\xcam\x04\xfe\x03\xca\xbf\x1c\xc3b\x04\x00\x00\x00\x00\x00\x00\x006\x80\xeb\xd1\xe5\xe5\xdd\xe17>\xff\xcd\xc6\x05\xe1\xed[S\\~\xe6\xc0 -\x1a\x13\xbe# \x02\x1a\xbe\x1b+0\x1c\xe5\xeb\xdd\xe5\xd9! \x17\xe5.\x00&\xff\xe5!\x00\x00\xe5\xe5\xd9\xcd\x99\x0f\xdd\xe1\xe1\x18\xd8\xcd\x99\x07\x18\xce~O\xfe\x80\xc8\xe5*K\\~\xfe\x80(9\xb9(\x1c\xc5\xdd\xe5\xd9! \x17\xe5.\x00&\xff\xe5!\x00\x00\xe5\xe5\xd9\xcd\x99\x0f\xdd\xe1\xc1\xeb\x18\xdc\xe6\xe0\xfe\xa0 \x12\xd1\xd5\xe5#\x13\x1a\xbe \x06\x170\xf7\xe1\x18\x03\xe1\x18\xcc>\xff\xd1\xeb<7\xcd\x99\x07\x18\xb0 4\x08"_\\\xeb\xdd\xe5\xd9! \x17\xe5.\x00&\xff\xe5!\x00\x00\xe5\xe5\xd9\xcd\x99\x0f\xd9!P\x17\xe5.\x00&\xff\xe5!\x00\x00\xe5\xe5\xd9\xcd\x99\x0f\xdd\xe1\xeb*_\\\x08\x08\xd5\xdd\xe5\xd9! \x17\xe5.\x00&\xff\xe5!\x00\x00\xe5\xe5\xd9\xcd\x99\x0f\xdd\xe1"_\\*S\\\xe3\xc5\x088\x1b+\x18\x12\xc5\x06\x06\xc5\x06\x00>\x7f\x10\xfc\xc1\x10\xf6\xc1\xdb\xfe\xc9\x00\xcdL\x06#\x18\x17\x18\x12\xcd\xfa\x05\xf1\xc9>\x02\xcd\x0c\x19\xa7\xfb\xc9>\x01\xc3`\x18\xcdL\x06#\xc1\xd1\xedSS\\\xed[_\\\xc5\xd5\xeb\xed\xb0\xe1\xc1\xd5\xdd\xe5\xd9!P\x17\xe5.\x00&\xff\xe5!\x00\x00\xe5\xe5\xd9\xcd\x99\x0f\xdd\xe1\xd1\xc9\xe5>\xfd\x18\x12\xc5\x06\n\xcd\xf6\x07\x10\xfb\xc1\xc9\x00\x00\x00\x00\x00\x00\x00\x00\xcd&\x04\xaf\x11\x89<\xdd\xe5\xd9!?\x07\xe5.\x00&\xff\xe5!\x00\x00\xe5\xe5\xd9\xcd\x99\x0f\xdd\xe1\xfd\xcb\x02\xee\xcd\xaa\x08\xdd\xe5\x11\x11\x00\xaf\xcdh\x00\xdd\xe1\x062v\x10\xfd\xdd^\x0b\xddV\x0c>\xff\xdd\xe1\xc3h\x00\xf5\xc5\xd5\x01@\x9c\x0by\xb0 \xfb\xaf\xdb\xfe\xe6\x1f\xfe\x1f(\xf7\xdd\xe5\xd9!\xa9\x08\xe5.\x00&\xff\xe5!\x00\x00\xe5\xe5\xd9\xcd\x99\x0f\xdd\xe1\xd1\xc1\xf1\xc9\xd9!\xed\x1b\xe5.\x00&\xff\xe5\xd9\xcd\x8a\x0f\xc3\xbc\x01"\xbc\\\xcd\xf4\t*\xbc\\\x11\x08\x00\x19~\xfe\x01 \x13\xe5\xcdl\t\xe1#^#V\xd5\x06\x00#N\xc5\xfb\xcdre*\xbc\\#~\xfe\x02(\x06\xcdl\t\xc3\x9a\t+~\xfe\x01(2\xfe\x02 B\x11\x06\x00\x19N#F!@h\t\xeb!@h\xed\xb0\xcds\t*\xbc\\\x11\x05\x00\x19~\xfe\x00(R+N+V+^\xd5\x06\x00\xc5\xfb\xcdre\xcdl\t>\x802\xc6\\!\xc6\x18\xe5\x06\xff\x0e\x00\xc5\xcdre\xcf\x1b!@h\x11\x15\x00\x19"W\\#"S\\"K\\6\x80#"Y\\6\r#6\x80#"a\\"c\\"e\\\xaf2\xc6\\2\xc2\\\xc9\x16\xff\x1e\x80!/\x0e\xe5\xd5*\xbc\\\x11\x0c\x00\x19\x06\x00~\xfe\x80(2\xfe\x00((#F\x11\x14\x00\x19~\x0f8\x05###\x18\xe8#~\xd1\xbb8\x05\xd5##\x18\xdd\xd1\x11\x05\x00\xedR\xe5O\xc5\x13\x13\x19\x18\xcf\x11\x18\x00\x19\x18\xc9\xc1x\xfe\xff(\x04\x0eX\x18\x02\x0e\x00\xc5\xfb\xcdre*\xbc\\\xaf2\xbe\\2\x15c\x11\x08\x00\x19\x1e\xff\x16\x00\xd5\x11\x01\x00\xd5\xe5\x11\x04\x00\xd5\x11\x01\x00\xd5\xcd"g~\xfe\x01("6\x00\x1e\xff\x16\x00\xd5\x11\x00\x80\xd5*\xbc\\\xe5\x11\x08\x00\xd5\x11\x01\x00\xd5\xcd"g#~\xfe\x02(\x026\x00*\xbc\\\x11\r\x00\x19\x16\xc0\x1e\x00\xcd\\c\xcd\xd1\x0b\xd2\xd4\nG\xcb\xf8p\xcb\xb8#\x0e\xfe\xc5\x11\xe7\x08\xd5\x11\x00\x00\xd5\x11\x01\x00\xd5\xd5\xcd"g\x1e\xffW\xd5\x11\x00\x00\xd5\xe5\x11\x16\x00\xd5\x11\x01\x00\xd5\xcd"gV:\xe7\x08\xba\xc2\xc2\n\x0e\xfe\xc5\x11L\n\xd5\x11\x00\x00\xd5\x11\x01\x00\xd5\xd5\xcd"g\x1e\xffW\xd5\x11\x00\x00\xd5\xe5\x11\x16\x00\xd5\x11\x01\x00\xd5\xcd"gV:\xe7\x08\xba\xc2\xc2\n++\xcd\xdb\n\x11\x15\x00\x19\x18\x08z\xe6\xdfw+\xcd\x1f\x0c\x16\xc0\x1e\x01\xcd\\c\xc3L\n+6\x80\xcd\xfb\x0c\xc96\x02\xc5\x118\x00\xd5\xd5\x11\x10\x00\xd5\x11\x01\x00\xd5\xcd"g##~\xcb\xc7w\x11\x00\x00>\x01\x08\xe5\xeb\x11\x00 \x19\xeb\xe1\x06\xfe:\xbe\\O\xc5\x01\xe7\x08\xc5\xd5\x01\x01\x00\xc5\xc5\xcd"g:\xbe\\G\x0e\x00\xc5\xd5#\xe5\x01\x01\x00\xc5\xc5\xcd"gF+:\xe7\x08\xb8 e\x06\xfe:\xbe\\O\xc5\x01L\n\xc5\xd5\x01\x01\x00\xc5\xc5\xcd"g:\xbe\\G\x0e\x00\xc5\xd5#\xe5\x01\x01\x00\xc5\xc5\xcd"gF+:L\n\xb8 7\x08F\xfe\x01 \x04\xcb\xc8\x18*\xfe\x02 \x04\xcb\xd0\x18"\xfe\x03 \x04\xcb\xd8\x18\x1a\xfe\x04 \x04\xcb\xe0\x18\x12\xfe\x05 \x04\xcb\xe8\x18\n\xfe\x06 \x04\xcb\xf0\x18\x02\xcb\xf8p\x185\x08F\xfe\x01 \x04\xcb\x88\x18*\xfe\x02 \x04\xcb\x90\x18"\xfe\x03 \x04\xcb\x98\x18\x1a\xfe\x04 \x04\xcb\xa0\x18\x12\xfe\x05 \x04\xcb\xa8\x18\n\xfe\x06 \x04\xcb\xb0\x18\x02\xcb\xb8p<\xfe\x08\xc2\xf9\n\xc9:\xbe\\<2\xbe\\2\x15c\x16\xa0_\xcd\\c\x16\x80_\xcd\\c\x16@\x1e\x00\xcd\\c\xf5:\x00\xa0\x08>\x042\x00\xa0\x16\xa0\x1e\xc0\xcd\xadc\xcbS \x07\x082\x00\xa0\xf17\xc9\x082\x00\xa0\xf1=2\xbe\\2\x15c\x16\xc0\x1e\x04\xcd\\c\xa7\xc9+6\x01\x11\x15\x00\x19~\x1f8\x05\x11\x04\x00\x19\xc9\x0e\x08:\xbe\\+++V+^bkG\xe5\xc5\x01\x00\x00\xc5\xc5\xcd\xd0e\x11\x08\x00\x19\xc9\xaf2\xbe\\2\x15c\x16\xc0\x1e\x00\xcd\\c*\xbc\\\x11\x0c\x00\x19\xcd\xd1\x0b\xd2\xf5\x0c~\xe5\xfe\x80 \x05\x11\x18\x00\x19w\xcd\xd1\x0b!\xe9_\x1e\xffW\xd5\x11\x00\x00\xd5\xe5\x11\x16\x00\xd5\x11\x01\x00\xd5\xcd"g\x08~/+w\x08\x16\xff_\xd5\xe5\x11\x02\x00\xd5\x11\x01\x00\xd5\xd5\xcd"g\x1e\xffW\xd5\x11\x02\x00\xd5#\xe5\x11\x01\x00\xd5\xd5\xcd"g~+F\xb8 \x0f\xe1~\xfe\x02 \x04##\x18#\xcd\xdb\n\x18\x1eN\xe1##~\xb9(\x16\xe5\xeb!\xe9_\x01\x16\x00\xed\xb0\xe1+:\xbe\\\xcb\xffw\xcd\x1f\x0c#\x16\xc0\x1e\x01\xcd\\c\x11\x16\x00\xc3`\x0c6\x80\xcd\xfb\x0c\xc9\xaf2\xbe\\*\xbc\\\x11\x0c\x00\x19~\xfe\x80(y#~\xcb\x7f \x06\x11\x17\x00\x19\x18\xef"\xe9_+~\xfe\x02 \x08\x11\x17\x00\x19>\xff\x18\x05\x11\x17\x00\x19~2\xeb_#~\xfe\x80(.#~\xcb\x7f \x06\x11\x17\x00\x19\x18\xee+~\xfe\x02 \x06\x11\x17\x00\x19\x18\xe2\xeb\x01\x17\x00\t:\xeb_G~\xb80\xd52\xeb_\xedS\xe9_\x18\xcc:\xbe\\<2\xbe\\*\xe9_w\x1e\xffW\xd5^\x16\x00\xd5\x1e\x00\xd5\x1e\x01\xd5\xd5\xcd"g\xc3\xff\x0c\xaf2\xbe\\2\x15c\x16\xc0\x1e\x00\xcd\\c*\xbc\\\x11\r\x00\x19\x16\xa0\xcd\xd1\x0b\xd0^\xcd\\c\x16\xc0\x1e\x01\xcd\\c\x11\x18\x00\x19\x18\xeb\xc5\xd5\xe5\xf5*\xb4\\\xed[{\\\xa7\xedRDM\x03*{\\\xe5\x11@\x08\xa7\xedR\xeb\xe1\xedS{\\\xed\xb0!\x00\x009\x01\xc0\x97\t\xf3\xf9\x11\xc0\xf7!\x00`\x01@\x08\xed\xb0!\x00\x1d\x01\xc0\x97^#V#{\xb2(\x0f\xeb\t\xd5^#V\xeb\t\xebr+s\xe1\x18\xe9\xf12\xc2\\\xf5\xfb!\x00`\xafw#|\xfe{ \xf8\xf1\xf5\xe6\x7fG\xdb\xff\xe6\x80\xb0\xd3\xff\xe1\xd1\xc1\xf1\xc9\xf5\xc5\xd5\xe5\xdb\xff\xe6\x80\xd3\xff!\x00\x009\x11\xc0\x97\xa7\xedR\xf3\xf9!\xff\xff\x11?h\x01@\x08\xed\xb8!\x00\x1d\x01\xc0\x97^#V#{\xb2(\x10\xe5\xeb^#V\xeb\xa7\xedB\xebr+s\xe1\x18\xe8\xaf2\xc2\\\xfb!\xbf\xf7\x11\xff\xff\xe5\xedK{\\\xa7\xedBDM\x03\xe1\xed\xb8\x11@\x08*{\\\x19"{\\\xe1\xd1\xc1\xf1\xc9\xc5\xd5\xe5\xf5G:\xc2\\\xa7 T\xb0\xca=\x0f!\xc0\x12DM\x11@\x08\x19\xed[e\\\x19\xed[\xb2\\\xa7\xedR\xd2:\x0f!?h\x11\xca\x12\xd5\x11\x00\xff\xd5\x11\x00\x00\xd5\xd5\xcd\xd0e*e\\\xeb\xed\xb8\xf1\xf5\xcd\xb0\r\x01\xc0\x97*=\\\t"=\\*?\\\t"?\\*\xc0\\\t"\xc0\\\x18Px\xa7(\x10\xe6\x7fG\xdb\xff\xe6\x80\xb0\xd3\xffx2\xc2\\\x18<\xcd\'\x0e\x01\xc0\x97*=\\\xa7\xedB"=\\*?\\\xa7\xedB"?\\*\xc0\\\xa7\xedB"\xc0\\\x01\xc0\x12!@h\x11P\x17\xd5\x11\x00\xff\xd5\x11\x00\x00\xd5\xd5\xcd\xd0e\x18\x037\x18\x01\xa7\xf1\xe1\xd1\xc1\xc9\xedK]\\\xcdi%*]\\\xa7\xedB+}*e\\w#\xc1p#q#"e\\*]\\+\xcbG(\x0c=F+=\xfa}\x0fN+\xc5\x18\xf4\x06 \xa7\xc8N+=\xc5\x18\xea*e\\+~+"e\\fo\xe5\xc9\xf5:\xc2\\\xa7(\x04\xf1\xc32\xfd\xf1\xc3re\xf5:\xc2\\\xa7(\x04\xf1\xc3\x90\xfd\xf1\xc3\xd0e\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xdd!\x00\x00\xdd9\xc5\xf5\xc5\xd5\xe5\xdd^\x02\xddV\x03\xaf\xcb#\xcb\x12\x17!\r\x00\xcb%\xcb\x14\xa7\xedR0\x15!\x18\x00\xcb%\xcb\x14\xa7\xedR8\x0f\x06\xff\xcd\x05d\x06\xff\x18\n\x06\xfe\x0e\xfe\x18\x04\x06\xff\x0e\x00\xf5\xc5!\xff\x1f7\xedR\x06\xfe\xcd\x16c\xeb\xc1\xf1\xa7(\x1f\xddq\xfe\xddp\xff\xddn\x00\xddf\x01\xddt\x03\xddu\x02\xddr\x01\xdds\x00\xe1\xd1\xc1\xf1\xcdre\xddn\x00\xddf\x01\xe5\xddn\x04\xddf\x05\xddu\xfe\xddt\xff\xddn\x06\xddf\x07\xddu\x00\xddt\x01\xddq\x02\xddp\x03\xdds\x04\xddr\x05\xe1\xddu\x06\xddt\x07\xe1\xd1\xc1\xf1\xcd\xd0e\xc9\xf5\xe5\xdd\xe5!\x00\x009\xd5:\x15c_\x16\x00\x13\x13\xa7\xedR\xeb\xdd!\x00\x00\xdd\x19\xd1\xdd\xf9\xcd\x1ee\xc5\x06\xff\xcd\x05d\x06\xffy\xe6\xf8O\xcd\x99d\xc1*x\\#"x\\|\xb5 \x03\xfd4@\xc5\xd5\xcd\xe1\x02\xd1\xc1\xdd!\x00\x00\xdd9\xcdJe\xdd#\xdd\xf9\xdd\xe1\xe1\xf1\xfb\xc9\xf5\xe5*\xb0\\|\xb5 \x01\xe9\xe1\xf1\xedE\xff\xf5\xc5\xd5\xcd^d\xf5PG\xcd\x05d\xc5\xcdMd/BO\xcd\x99d^#V+\xeb\xc1\xf1G\xcd\x99d\xd1\xc1\xf1\xc9\xf5\xc5\xcd^d\xf5PG\xcd\x05d\xc5\xcdMd/BO\xcd\x99ds#r+\xc1\xf1\xcd\x99d\xc1\xf1\xc9\xf5\xc5\xe5b.\x00:\x00\xc0\xf5~\xf5>\x07\xd3\xf5\xdb\xf6G>\x0e\xd3\xf5\xdb\xf6O>\x07\xd3\xf5>@\xd3\xf6>\x0e\xd3\xf5\xaf\xd3\xf6>\x022\x00\xc0{w\xcb/\xcb/\xcb/\xcb/w>\x07\xd3\xf5x\xd3\xf6>\x0e\xd3\xf5y\xd3\xf6\xf1w\xf12\x00\xc0\xe1\xc1\xf1\xc9\xf5\xc5\xe5b.\x00:\x00\xc0\xf5~\xf5>\x07\xd3\xf5\xdb\xf6G>\x0e\xd3\xf5\xdb\xf6O\xc5>\x07\xd3\xf5>@\xd3\xf6>\x0e\xd3\xf5\xaf\xd3\xf6>\x022\x00\xc0~\xe6\x0fOc~\xcb\'\xcb\'\xcb\'\xcb\'\xb1_\xc1>\x07\xd3\xf5x\xd3\xf6>\x0e\xd3\xf5y\xd3\xf6\xf1w\xf12\x00\xc0\xe1\xc1\xf1\xc9\xf5\xd5x\xfe\xfe(.\xfe\xff(\x1d\xa7(\x1f\x16\x80X\xcd\\c\x16@\x1e\x80\xcd\xadc{/O\x16\xa0\x1e\xc0\xcd\xadcC\x18\x1d\x01\x00\x00\x18\x18\xdb\xf4/G\x0e\x00\x18\x10\xdb\xff\xe6\x80/\x07G\xdb\xf4/\xe6\x01\xb0G\x0e\x00\xd1\xf1\xc9\xc5|\x06\x05\xcb?\x10\xfc<G\xaf7\x17\x10\xfd\xc1\xc9\xc5\xd5\xcdMdO:\x15c\xa7(\nGX\xcd\x05d\xa1(#\x10\xf7\xdb\xf4/\xa1(\x18\r \x11\xdb\xff\xe6\x80W\xdb\xf4\xe6\x01\x0f\xa2(\x04>\xfe\x18\x08>\xff\x18\x04\xaf\x18\x01x\xd1\xc1\xc9\xf5\xc5\xd5\xe5`:\x15c\xa7(\x11\x16\x80\x1e\x00\xcd\\c\x16\xa0\xf5y/_\xf1\xcd\\cx\xa7 \x11y\xfe\xff(\x06\xdb\xff\xcb\xbf\xd3\xffy/\xd3\xf4\x18Ox\xfe\xfe \x1d\xdb\xff\x17\xcb\x19?\x1f\xd3\xff\xcb\x7f \x08\xdb\xf4\xcb\x87\xd3\xf4\x185\xdb\xf4\xcb\xc7\xd3\xf4\x18-\xdb\xf4/_y/\xb3/\xd3\xf4\xcbA \x0c\xdb\xff\xcb\xbf\xd3\xff\xdb\xf4\xcb\x87\xd3\xf4x\xfe\xff(\x0e\x16\x80X\xcd\\c\x16@y/_\xcd\\c\xe1\xd1\xc1\xf1\xc9\xf5\xc5\xd5\xdb\xff\x00\x00\xddw\x00\xdd#\xdb\xf4\xddw\x00\xdd#:\x15c\xa7(\rGX\xcd\x05d\xddq\x00\xdd#C\x10\xf4\xdd+\xd1\xc1\xf1\xc9\xf5\xc5\xd5\xdd~\x00\xd3\xff\xdd#\xdd~\x00\xd3\xf4\xdd#:\x15c\xa7(\x0bG\xddN\x00\xcd\x99d\xdd#\x10\xf6\xdd+\xd1\xc1\xf1\xc9\xdd!\x00\x00\xdd9\xddq\x00\xddp\x01\xddN\x02\xddF\x03\xcd\x99d\xc1\xdd\xe1\xdd\xe1\xdd\xe9\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xe3\xdd*\xcee\xdd+\xddt\x00\xdd+\xddu\x00\xe1\xe3\xdd+\xddt\x00\xdd+\xddu\x00\xdd"\xcee\xd5\xc5\xf5!\x00\x009T]:\x15cO\x06\x00\x03\x03\xa7\xedB\xf9\xdd!\x00\x00\xdd\x19\xeb\xddN\x08\xddF\x08>\x0e\x81O0\x01\x04\xed\xb0\xd5\xdd\xe1\xcd\x1ee\xdd!\x00\x00\xdd9\xddN\n\xddF\x0b\xcd\x99d\xf1\xc1\xd1\xe1\xdd\xe1\xdd\xe1\xdd\xe1\xcd\x8ce\xf5\xc5\xd5\xe5\xdd*\xcee\xddN\x00\xdd#\xddF\x00\xdd#\xdd"\xcee\xdd!\x00\x00\xdd9>\x08\x81O0\x01\x04\xdd\t\xdd\xe5\xe1+\xcdJe\xdd\xe5\xd1\xed\xb8\xeb#\xf9\xdd*\xcee\xddN\x00\xdd#\xddF\x00\xdd#\xdd"\xcee\xc5\xdd\xe1\xe1\xd1\xc1\xf1\xdd\xe5\xc9\xe5\xd5\xc5H\xddF\t\xcd\x99dBK\xdd^\x00\xddV\x01\xddn\x06\xddf\x07\x07\x0f8\x05\xed\xb0\t\x18\x05\xed\xb8\xa7\xedB\xddu\x06\xddt\x07\xc1\xe1\xe5\xc5\xddF\x08\xcd\x99dDM\xdd^\x04\xddV\x05\xddn\x00\xddf\x01\x07\x0f8\x05\xed\xb0\t\x18\x05\xed\xb8\xa7\xedB\xddu\x04\xddt\x05\xc1\xd1\xe1\xc9T]\xddN\x02\xddF\x03\xdd~\x00\x07\x0f8\x03\t\x18\x02\xedB\xcdMd/G\xeb\xcdMd/O\xa8(\x16y\xa0G\x0e\x007x\xcb\x11\xa1 \xfax\xcb\x11\xa1(\x04\xa8G\x18\xf6x\xc9\xf5\xc5\xd5\xe5!\x00\x009\x11\n\x00\x19\xeb:\x15cO\x06\x00!\x00\x009\xa7\xedB++\xe5\xdd\xe1\xdd\xf9\xcd\x1ee\xd5\xdd\xe1\xddn\x06\xddf\x07\xcd\xe8f\xf5\xddn\x04\xddf\x05\xcd\xe8fO\xf1G\xdd~\t\xddV\x08\xba \x05x\xa1G\x18\x0bx\xb1\xfe\xff -XB\xcd\x99d\xddF\tK\xcd\x99d\xddn\x06\xddf\x07\xdd^\x04\xddV\x05\xddN\x02\xddF\x03\xdd~\x00\x07\x0f8\x04\xed\xb0\x18R\xed\xb8\x18N!\xc0\\\xc5\x06\xff\xcd\x16c\xc1\x11\x00\x02\xa7\xedR\x11 \x00\x19\xeb!\x00\x009\x13\xa7\xedR0\x04>\x01\x18+\x1b\xeb\xf9\x13\xdd~\x00\xddu\x00\xddt\x01\xddn\x02\xddf\x03\xa7\xedR8\x05\xcd\x8cf\x18\xf6\x19\xeb\xcd\x8cf\xeb\xddn\x00\xddf\x01\x19\xf9\xaf\xdd!\x00\x00\xdd9\xcdJe\xdd#\xdd\xf9\xe1\xd1\xc1\xf1\xdd\xe1\xdd\xe3\xdd\xe1\xdd\xe3\xdd\xe1\xdd\xe3\xdd\xe1\xdd\xe3\xdd\xe1\xdd\xe3\xc9\xdd\xe1\xf5\xdb\xff\xcb\xff\xd3\xff>\x01\xd3\xf4\xf1\xe9\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xc3\x86\x17\xc3\xc7\x17\xc3\xd1\x17\xc3d\x16\xc3\x13\x18\xf5\xcdh\x18\xaaW\xf1\xa7\xc9\xf17\xc9\xf5>BW\xcdh\x18\xf12\xd9]\xcd?\x16:\xcf]\xcd?\x16\xa7\xc9\xf17\xc9\xf5:\xdb]\xa7(u>\x05\xcdK\x16\xda3\x1c\xf1\xe5\xcd?\x16\xfe\x800\x06>\x01.\x00\x18\x04>\x02.\x08\xcd?\x16:<\\\xe6\x10\xfd\xcb\x01f(\x02\xf6\x01\xfd\xcb0N(\x02\xf6\x02\xcd?\x16:\x8d\\\xcd?\x16&\x00}"\xcd]\xcd?\x16|\xcd?\x16z\xcdh\x18}\xa7(\x08*\xd7]\xcd\x1c\x19\x18\x03\xcd,\x18\xda\t\x1c\xa7\xc2\t\x1c\xe1:\xd9]\xfe\x05 \x01\xf1\xaf"\xcd]!5\n\x18\x07\xf1"\xcd]!\x1a\x06\xe5.\x00&\xff\xe5*\xcd]\xc3\xe4\x08\x07\x16CR%4ap>BW\xcdh\x18:t\\\xfe\xd8 \x04\xd6\xd4\x18\x0e\xfe\xdb \x04\xd6\xd6\x18\x06\xfe\xde \x02\xd6\xd8\xcd?\x16:\xcf]\xcd?\x16\xdb\xff\xe6?G\xe6\x07\xf5\x0e\xff(\x10x\x0f\x0f\x0f\xe6\x07!\xf3\x16\xd5_\x16\x00\x19\xd1Ny\xcd?\x16\xf1\xf5\xfe\x06 \x02>\x03\xcd?\x16! \x18\xfe\x03 \x02.@}\xcd?\x16|\xcd?\x16!\x00@"\xd3]\xf1!\x00\x1b(\x03!\x00;"\xcd]}\xcd?\x16|\xcd?\x16z\xcd?\x16\x16\x00!\x00@\xcd\x1c\x19\xc9:\xdb]\xa7(\x0c\xcd\xfb\x16\xda4\x1c\xa7\xc2\n\x1c\x18\x1f\xf3\x06\xb0!\x00@\xe5\xc5\xcd\xe0\x17\xc1\xe1$|\xe6\x07 \n}\xc6 o?\x9f\xe6\xf8\x84g\x10\xe7\xd9!0\n\xc3\xdd\x08\xdd\xe5\xd9!0\n\xc3\xdd\x03\xcd\xe0\x17\xd9!\x19\x06\xc3\xdd\x08\xf3!\x00[\x06\x08\xc5\xcd\xe0\x17\xc1\x10\xf9\x18\xd7x\xfe\x03\x9f\xe6\x02\xd3\xfbW\xcd\t 8\x05\xcd\xbe\x17\xcf\x0c\xdb\xfb\x87\xf80\xf0\x0e ^#\x06\x08\xcb\x12\xcb\x13\xcb\x1a\xdb\xfb\x1f0\xfbz\xd3\xfb\x10\xf0\r \xe9\xc9\xf5\xe5\xd6\x90o&\x00\xc5\xedK{\\)))\t\xc1"\xd7]\xe1\xf1\xc3d\x16\x0e\x0e\xcdd\x18\xa7\xca\x14\x04=\xc2\x16\x04\xcdd\x1a\xda\x14\x04\xc9\x18\x14\x18\x1c\x18\x0c\x18 \x18\x1a\x18\x03\xc3d\x1a\xc3Q\x19\x01\x12\x00\xc9\xf5:\xdb]\x06\x00O\xf1\xc9\xaf2\xdb]\xc9\xdb\x0e\xa7\xc9\xd3\x0e\xa7\xc9\xf1!\xe5\x00\xc3k\x00\xf5:\xdb]\xa7(\xf2\xf1!\xe5\x00\xe5\xf5\xf3o\xa7 \x04\x0e\x01\x18\n\xfe\xff \x04\x0e\x03\x188\x0e\t\xcdh\x18\xd5:t\\\xcd\x98\x19:\xcf]\xcd\x98\x19\xed[\xd1]\xcd\x90\x19\xdd\xe5\xd1\xcd\x90\x19\xd1\xcd\x82\x19\xcdh\x18\x0c\xcdd\x18\xa7\xca2\x1c= S\x0c\xcdd\x1a\xda2\x1c\xf1g\xcdh\x18\xedS\xcd]\xed[\xd1]\xcdu\x19|\xa7\xc4\xe8\x04\xed[\xcd]\xdd~\x00\xcdh\x18\xacg\xdd#\x1bz\xb3 \xf1|\xcdh\x18\x0c\xcdd\x1a\xda3\x1c\xcdd\x18\xa7\xca3\x1c=\xc4o\x02\xfb \x0c7\xc9\x0c|\xcdh\x18\r\xc9\xe1\xe1\xe1\xe1\xa7\xc8\xc3\n\x1c\xcdd\x18\xa7(H=\xcdd\x1a8B\xc0>DW\xcdh\x18:\xcd]\xcd\xa5\x1b:\xce]\xcd\xa5\x1b~\xcd\xa5\x1b#\xe5*\xcd]+"\xcd]|\xb5\xe1 \xeez\xcdh\x18\xcdd\x1a\xdaj\x19\x0e\x0e\xcdd\x18\xa7\xcaj\x19=\xc8\xcdo\x02\xa7 \x02\xa7\xc9>\t7\xc9\xf1\x14\x08\x15\xc3\xff\x00{\xcdh\x18\xcd\x8d\x19z\xcdh\x18\x18\x0b{\xcdh\x18\xcd\x8d\x19z\xcdh\x18\xado\xc9{\xcdh\x18\xcd\x8d\x19z\xcdh\x18\x18\xf0\xc3\x16\x19\xf5:\xdb]\xa7(\xc7\xf1!\xe5\x00\xe5\xf3\xd5\xf5\xe1\xcb\xb5\xe5o\xa7 \x04\x0e\x05\x18\n\xfe\xff \x04\x0e\x07\x18\x02\x0e\n\xf1\x08}g\xcdh\x18:t\\\xcd\x8a\x19:\xcf]\xcd\x8a\x19\xed[\xd1]\xcd\x82\x19$\xcc\xe8\x04%\xdd\xe5\xd1\xcd\x82\x19\xd1\xcdu\x19}\xcdh\x18\x0c\xcdd\x18\xa7\xca3\x1c= Y\xcdd\x1a\xda3\x1c\xcd\x0c\x19\xcdd\x18o\x08 40?\xddu\x00\x08|\xadg\xdd#\x1bz\xb3 \xe9\xcdd\x18\xac\xa7\xc2\x15\x08<\xcd\x0c\x19\xcdd\x1a\xda3\x1c\xcdd\x18\xa7\xca3\x1c=\xc4o\x027\xfb \x01\xc9?\xc9\xcb\x10\xad\xc0\xcb@(\x02\xbf7\x08\x18\xb8\x08\xdd~\x00\xad(\xbe\xc9\xe1\xc3P\x1c\xe1\xd1\xd1\xe1\x01\x11\x00\xc3\xd5\x01\xf5\xc5\x06\xe2\xcdU\x06\xcbw \x08\x10\xf7\xc1\xf1>\x027\xc9\xc1\xf17?\xc9\xe5\xd5*x\\#|\xb5(\xfb"\xd1]*e\\+F+N+V+^x\xa7 \xc4y\xfe\x19\xd2A\x1c:t\\\xa7(\x05\xfe\x02\xd2\\\x1ay\xfe\x130\xae\xa7(\xab\xfe\x058\xa7\xd5\xd5\xe1"\xd3]\xedC\xd5]\x06_x\xa6\xfeT \x94#x\xa6\xfeP \x8d#x\xa6\xfeI \x86#>:\xbe\xc2[\x1ay\xfe\x07\xda[\x1a:t\\\xa7\xc2\xb2\x1b\xe5\xafgo"\xd7]"\xd9]\xcd\x03\x03\xfe\xaf(\x11\xcdD\x1b(*\xc3Z\x1a\xcd\xd7\x02\xcd\xca\x03\xc3|\x03\xcd\x02\x1b\xedC\xd7]\xcd\x03\x03\xfe,\xc2:\x1c\xcd\x02\x1b\xedC\xd9]\xcd\x03\x03\xcdD\x1b \xd6\xfd\xcb\x01~\xca\x9b\x1b\xe1\xedK\xd5]#\x06_x\xa6\xfeT(\x0c\xfeS(\'\x18n\xfe\r\xc8\xfe:\xc9#x\xa6\xfeA a#x\xa6\xfeP Z#x\xa6\xfeE S>\x08\xb9 N\xcd_\x18\x18-#x\xa6\xfeD B#x\xa6\xfeC ;#x\xa6\xfeA 4#x\xa6\xfeR -#x\xa6\xfeD &>\n\xb9 !>\x01\xcd`\x18\xcd/\x04\x18\x01\xe1\xd1\xc36\x1c\xcdh\x18\x18\x03\xcdh\x18\xaaW\xc9\xe1\xe1\xe1\xe1\xc3P\x1c\xcd/\x04y\xb7(\xf4\xedC\xcd]A\x0e\r>BW\xcdh\x18:t\\\xcd\xa5\x1b:\xcf]\xcd\xa5\x1b*\xd7]}\xcd\xa5\x1b|\xcd\xa5\x1b*\xd9]}\xcd\xa5\x1b|\xcd\xa5\x1bx\xcd\xa5\x1b:\xce]\xcd\xa5\x1b\xcd\xa5\x1b\x16\x00\xe1*\xd3]\xcd\x1c\x19\xda\x08\x1c\xa7\xca6\x1c\xf5\xaf\xf1\xd1\xe1\xfb=(B=(:=(:=(0=(\x0f=(\x0e=(\x0f=(\n=(\x0e\xc3\xf8\x00\xcf\x05\xcf\x07\xcf\x08\xcf\t\xe1\xe1\xe1\xcf\x12\xd1\xe1\xaf\xc9\xe1\xe1\xe1\xd1\xe1\x18\x06\xfd\xcb\x01~(\xef\xfb\xc3\xd9\x08\xc3(\x02\xcf\x19\xcf\x1a\xcdd\x1a\xda\xac\x1b\xc3h\x18\xfe\x81 \x0b\xcd\xb9\x02\xcd\xf1\x04\xcd_\x04\x18\x1d\xfe\x82 \x12\xcd\xb9\x02\xf5\xcdw\x1c\xf1\xc9\xcd\xf1\x04\xcdd\x18\xc3\xfa\x05\xfe\x83 \t\xcd\xb9\x02\xf5\xcdq\x04\xf1\xc9\xfe\x84 \x14\xcd\xb9\x02\xf5\xe5\xcd^\x02o\xcdj\x02\x87\xb5\xcdh\x18\xe1\xf1\xc9\xfe\x85\xc0\xcd\xc3\x01\xf5\xcd_\x04\xda\x13\x08\xcdq\x04\xe6_\xfeN\xc2\xac\x1c\xc3\x10\x08\xf17\xc9!\xd6\x1c\x11\x00[\x01)\x00\xed\xb0\xcd\x00[!\xea^\xc3\xea\x08\xaf\xcd\x05[\xc9\x11\x0b[\xc3\xed\x03\x80\r\r\x7f 2023 Timex Pico Interfac\xe5\x002bMbrb\xabb\xb8b\xcdb\xd3b\xdcb\xfbb\x1ac c$c*c5c>cDcHcNcWc\x17d\x1ed(dadedmd\x9fd\xacd\xb3d\x0ee\x16e2e:e\\efe\xcee\x85e\xd3e\xede\xf9e\x1ef-f:fBfPfffrf\x80f\x94f\xc0f\xfdf\x03g0gOgPgZgvg}g\xa7g\xdcg\xe3g\xf6g\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x95\x17\x13($&9\t\xa6\x08?\x07f\x05T\x05:\x05\xb0\x02\x10\x00\xed\x11\xcf\x11l<e<^<N<\xfd;\xf5;\xd0;\xc5;\x9e;.;\xdf:\xca:\xbb:V6\xd35n5\x894h4\xd33\xce3\xa11\x931`1\xf90\xe90\xe60Y0\xc0/\xaf/\xbd.t.p.p,\xf2)\xe5)\xb6)\xd7(\x8e(T(\x10(\xdb&y&`&>&5&\x03&\x1d$\xde#\x80#k"+"~!Y!U!\x1d \t \xeb\x1f\xd4\x1f\xbb\x1f\x99\x1f9\x1f6\x1f#\x1f\x1e\x1f\xf1\x1e\xe4\x1e\xd4\x1e\xca\x1e\x82\x1e\x97\x1dU\x1dY\x1cx\x1c\xd8\x1a\'\x1a\x88\x17P\x17 \x17\xf0\x16\xd6\x16\r\x16\xd0%\xcc%\xd4%\xc8%e\x14*\x14\xbe\x13\x9f\x13T\x13\xbb\x120\x12\xe1\x111\r\x1d\r\r\rJ\n#\n\xea\x08\xa9\x08\x88\x08\x10\x07\xb2\x05\x00\x05\x02\n6\x04\xf3\x03\xe1\x02\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff!g\xcfeqe\x99d^d\x05d\xff\xff\xff\xff\xff\xff\xff\xff\xe5\x00\xa3\x0eQ\x08\xe5\x06\xcc\x05\xab\x01\x8d\x01\x89\x01\xfc\x00h\x00')

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


@asm_pio(                                # This routine adapted from https://github.com/keyvin/docnotes/blob/master/z80/Python/z80io.py
    sideset_init=(PIO.OUT_HIGH),
    out_init=(PIO.OUT_LOW,) * 8, 
    out_shiftdir=PIO.SHIFT_RIGHT,
    in_shiftdir=PIO.SHIFT_LEFT,
    )
def TS_IO():
    wait (0, gpio, 14)      .side(1)     # We first wait for GPIO14=/PICOSEL to be low, then
    jmp(pin, "rd")          .side(1)     # ...if GPIO11=1 then it's a READ
    pull(noblock)           .side(0)
    out(pins, 8)            .side(0)     # if not, simply send all 8 bits
    jmp("fin")              .side(0)     # and JUMP to the end of the PIO program
    label("rd")                          # If it's a WRite, ...
    nop()                   .side(0)
    in_(pins, 9)            .side(0) [2] # we sample D0..D7 and A0. Notice the extra 2 cycles for sync
    push(noblock)           .side(0)
    label("fin")
    wait (1, gpio, 14)      .side(0)
    mov(null, osr)          .side(1)


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


def REARM_AFTER_LOAD_ABORT(MQ, TSP):
    """Re-prime TX so the command AFTER an aborted LOAD isn't Report J.

    LOAD_TS's normal exit ends with the V6 chain: two MQ.put(0x01) writes
    (this iteration's final status, then the pre-load the NEXT command's
    initial $0E status read consumes) followed by Y = READY. The abort
    paths never reach it. The watchdog has just drained both FIFOs, so TX
    comes back empty and Y is left wherever the partial Z80 OUTs dropped
    it — the next command's status read finds nothing and the dispatcher
    answers Report J.

    docs/PROTOCOL.md §7 states the rule this restores: "if LOAD_TS returns
    without writing the trailing two 0x01s, the next LOAD will hang or fail
    with Report J. The pre-load chain is load-bearing; honor it in any new
    handler." SAVE_TS gets away with the same shape only because the
    dispatcher calls ACTIVATE_MQ() after it and re-arms with its own
    MQ.put(0x01); nothing at all runs after LOAD_TS returns.

    ONE 0x01 here, not two. The pair on the normal path exists because the
    Z80 is still listening and consumes the first as this transaction's
    final status. After an abort there is no Z80 waiting — it has already
    reported and gone back to BASIC — so a second byte would sit in TX and
    be read as the first byte of the next command's response. That is the
    one-byte CRC shift that surfaces as Report R. Same shape as the
    dispatcher's own body-read-timeout recovery in tspico.py: one pre-load,
    then restore Y.

    The symptom this fixes, from Ryan on #48: VERIFY makes the Z80 abandon
    the transfer mid-block as soon as the comparison fails (a Program block
    covers the variables area, so verifying a running program against its
    own earlier SAVE always mismatches). Reporting R there is correct — but
    every command after it answered J until something re-primed the chain,
    which is why "a few tpi:nop calls would clear up the queue".

    Call AFTER ABORT_TX, never before: ABORT_TX waits for core1 to finish
    draining and re-activating the SM, and anything staged earlier is eaten
    by the watchdog's pull(noblock) cleanup loop. (If ABORT_TX hit its 3s
    bail-out, core1 may still be bouncing the SM and this write can be
    lost — no worse than the nothing that was written before.)
    """
    # Issue #51: through MQ_TO_IDLE, not a bare MQ.put(0x01). This assumed
    # the watchdog's cleanup had emptied TX -- but ABORT_TX stops waiting for
    # that cleanup after 3 s, and a put() into a still-full TX blocks forever,
    # the very hang the watchdog exists to prevent. MQ_TO_IDLE empties TX and
    # RX first, stages exactly one 0x01 (the rule above) and sets Y = READY
    # (idle), and it can't block.
    MQ_TO_IDLE(MQ)
    LOG_ADD("INFO: LOAD aborted; TX re-armed for the next command.",
            0, TSP.LOG_LEVEL)


def ABORT_TX(log_level, what="LOAD_TS"):
    """Abort an in-flight LVM transaction.

    Called from LOAD_TS / SAVE_TS when the watchdog has flagged the
    transaction as hung (kill = True). Logs the error, sets `dead = True`
    so the watchdog knows we're aborting, then waits for the watchdog to
    finish its FIFO-clear cleanup (busy goes False).

    The watchdog itself does the actual TX/RX FIFO drain; this function
    just signals it and waits. Do NOT write status bytes before calling
    this: the watchdog's cleanup loop is pumping `pull(noblock)` through
    TX the whole time it waits for `dead`, so anything staged beforehand
    is discarded. The dispatcher re-arms TX after we return.

    Waiting matters for more than tidiness. The watchdog's cleanup ends
    with MQ.active(0) -> BLINK() -> MQ.active(1), and BLINK blocks for
    ~1 second. Returning early means core0 races ahead into the
    dispatcher's ACTIVATE_MQ + status pre-load while core1 is still
    bouncing the very same hardware state machine underneath it.

    Args:
        log_level: TSP.LOG_LEVEL.
        what:      handler name for the log line.
    """
    global dead
    global busy

    LOG_ADD("ERROR: %s failed!" % what, 2, log_level)
    dead = True

    # Spin until the watchdog thread on core1 finishes its cleanup.
    # The watchdog drains FIFOs, deactivates/reactivates the SM, then
    # sets busy = False. We can't proceed to send a response until then
    # because the bus state is unsafe during cleanup.
    #
    # Bounded: if the thread died before clearing `busy` (it never should,
    # but an unhandled exception on core1 leaves no trace on core0), an
    # unbounded spin here wedges the dispatcher forever. BLINK alone is
    # ~1s, so give it 3s and then carry on.
    _t = time.ticks_ms()
    while busy:
        if time.ticks_diff(time.ticks_ms(), _t) >= 3000:
            LOG_ADD("ERROR: ABORT_TX gave up waiting for core1 cleanup",
                    2, log_level)
            busy = False
            break

    return


def STOP_WATCHDOG(log_level):
    """End a transaction's watchdog WITHOUT its cleanup, for a transaction
    that ended itself -- e.g. on a BREAK (issue #51) -- and will put the bus
    right with MQ_TO_IDLE. Sets `dead` so WATCHDOG's poll loop exits before
    its timeout, then waits (bounded) for core1 to let go.

    Unlike ABORT_TX, nothing here is an error and nothing waits for the
    watchdog's FIFO flush and ~1 s BLINK: a BREAK should be answered as fast
    as the Z80 asks. If the watchdog had already timed out and is mid-
    cleanup, the wait below simply lets it finish first.
    """
    global dead, busy

    dead = True
    _t = time.ticks_ms()
    while busy:
        if time.ticks_diff(time.ticks_ms(), _t) >= 3000:
            LOG_ADD("ERROR: STOP_WATCHDOG gave up waiting for core1",
                    2, log_level)
            busy = False
            break


def BLINK():
    """Blink the onboard LED 10 times for a fixed interval.

    Used as a visual signal during boot or when an error condition is
    detected. Blocking — caller is paused for ~1 second.
    """
    led = Pin(25, Pin.OUT)
    led.value(1)

    for i in range(10):
        utime.sleep(.1)
        led.toggle()

    led.value(0)

    return




def ENA_MQ_DUAL(MQ):
    """Re-create and activate the dual-port TS_IO_DUAL state machine.

    The dual-port counterpart of ENA_MQ() above, and the one ZX48-mode
    handlers must use. Needed after ENA_SD(), which re-claims GPIO 2-4
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


def ENA_MQ(MQ):
    """Re-create and activate the (legacy single-port) TS_IO state machine.

    NOTE: This is the OLD single-port version using `TS_IO` at 15MHz.

    *** UNUSED as of the 2026-09 ZX48 migration — do not call it. ***
    SAVE_ZX was its last caller; on the dual-port bus it silently
    replaced the session's SM with one that doesn't decode $0E from $0F.
    Use ENA_MQ_DUAL() below, or ACTIVATE_MQ() in tspico.py. Kept only so
    the single-port program has a working reference implementation.
    """
    MQ = StateMachine(0, TS_IO, freq=15_000_000, out_base=Pin(2, Pin.OUT),
                      in_base=Pin(2, Pin.IN), jmp_pin=Pin(11),
                      sideset_base=Pin(12, Pin.OUT))

    MQ.active(1)

    return MQ


def ENA_MQ_DUAL(MQ):
    """Re-create and activate the dual-port TS_IO_DUAL state machine.

    The dual-port counterpart of ENA_MQ() above, and the one ZX48-mode
    handlers must use. Needed after ENA_SD(), which re-claims GPIO 2-4
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


def ENA_SD():
    """Mount the SD card on /sd. Used by SAVE_TS to write the captured TAP.

    Note: this leaves the GPIO pins claimed by SPI; the caller is
    responsible for unmounting (or letting MOUNT_FILE / DEACTIVATE_SD
    handle it later in the dispatcher). New code should prefer the
    explicit ACTIVATE_SD / DEACTIVATE_SD pair in tspico.py.
    """
    
    U3_CS       = Pin(28, Pin.OUT, Pin.PULL_UP)
    D0          = Pin(2,  Pin.IN)
    D1          = Pin(3,  Pin.IN)
    D2          = Pin(4,  Pin.IN)

    spi = SPI(0, sck=D0, mosi=D1, miso=D2)
    sd = SDCard(spi, U3_CS)

    try:
        os.mount(sd, "/sd")
    except:
        LOG_ADD("ERROR: Mounting SD Card failed in ENA_SD!", 2, TSP.LOG_LEVEL)
        spi = -99
        pass
    
    return spi


def END_MSG(MQ, verbose, msg, msg1, st: bytes):
    """Send a single status response (optionally with a verbose string)
    back to the Z80, then wait for the FIFO to drain.

    !!!  WARNING — DO NOT call this from LOAD_TS or SAVE_TS  !!!
    Those handlers already write their own MQ.put(0x01) × 2 (final
    status + next-iter pre-load) per the V6 pattern. END_MSG would
    inject a THIRD status byte that gets orphaned in TX, then consumed
    by the next iteration's data-loop reads → CRC mismatch → "Report R
    Tape Loading Error". See docs/PROTOCOL.md §7 pitfalls.

    This function is appropriate for simpler "result" responses (e.g.,
    verbose feedback strings printed to the TS-2068 screen via the
    PRINT_STRING directive 0x81) where the protocol doesn't already
    chain a pre-load.

    Layout depending on `verbose`:
        VERBOSE = True (TS-2068 will display the message on screen):
            byte 0 = 0x81 (PRINT_STRING function code; this byte
                            simultaneously serves as the "final status"
                            from Z80's POV — values >= 0x80 are
                            interpreted as function codes, not errors)
            byte 1 = `st`  (return code: 1 = OK, else error code)
            byte 2 = 0x0D  (newline)
            bytes 3.. = `msg` ASCII characters
            optional 0x0D + `msg1` ASCII characters
            terminator = 0x00

        VERBOSE = False (silent OK):
            byte 0 = `st`  (just the status code)

    Args:
        MQ:      TS_IO_DUAL state machine.
        verbose: TSP.VERBOSE — whether to send the message text.
        msg:     primary message string (ignored if verbose=False).
        msg1:    optional secondary message string (e.g., a filename).
        st:      status byte (1 = OK, 2-9 = various Z80 BASIC reports).

    Blocks until the Z80 has drained every byte from TX FIFO.
    """
    wrt = MQ.put

    if verbose:
        # Verbose response: tells Z80 BASIC ROM "print the following
        # string on screen, then handle the trailing return code".
        wrt(0x81)               # PRINT_STRING function code (>=0x80 means
                                # "extended response — read more bytes")
        wrt(st)                 # actual return code (used after string is shown)
        wrt(0x0D)               # leading newline so message starts on its own line
        for m in msg:
            wrt(m)              # primary message text
        if msg1:
            wrt(0x0D)           # second-line separator
            for m in msg1:
                wrt(m)
        wrt(0x00)               # NULL terminator — tells Z80 ROM "string done"
    else:
        # Silent response: just one status byte.
        wrt(st)

    # Block until Z80 has drained every byte we put. This guarantees
    # the response has been fully consumed before our caller returns
    # (and possibly disturbs the FIFO state).
    while(MQ.tx_fifo() != 0):
        pass

    return


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
             - Z80 reads them from $0E in a tight loop (~47µs/byte). Pico's
               MQ.put() blocks when the 4-deep FIFO fills, so streaming
               paces itself naturally.
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
    global dead, kill, busy
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
        local_fname = "/TMP/temp.tap"
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

    # ---- Header-only: optionally patch the autorun byte ----
    # For non-autorun BASIC programs, the original Spectrum tape header
    # has hdvars high byte ≥ 0x80 indicating an autorun line. Some
    # programs were tape-saved with autorun enabled but don't actually
    # have an autorun line; loading them on TS-2068 hits "Report L".
    # This patches the autorun-line bytes back to a safe value.
    hdr = None
    if blk_info[2] == 0x00:                          # header block
        hdr = bytearray(totbytes - 1)
        arch.readinto(hdr)
        if hdr[0] == 0x00 and hdr[14] >= 0x80:       # BASIC w/ autorun bit set
            hdr[14] = 0x28
            hdr[17] = hdr[17] ^ 0x80 ^ hdr[14]       # fix CRC after the patch

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

    # ---- Spawn watchdog so a misbehaving Z80 doesn't lock the loop ----
    dead = False
    # Budget scaled to the block. Hardware 2026-09-26: the Z80 read TS-Pico
    # Commander's 16,096-byte block at ~190 us/byte -- still reading when a
    # flat 3 s budget killed it ~220 bytes from the end (Report R). TX_ROOM
    # and RX_WORD bound real silence on their own; this only has to outlast
    # a slow but live Z80: 3 s + 1 s per 4K.
    START_WATCHDOG(3 + totbytes // 4096, MQ, TSP)

    wrt = MQ.put

    # ============================================================
    # Phase 1: stream the response (block_type + content + CRC)
    # ============================================================
    # Z80's data loop reads `flag + content + CRC` = `totbytes` bytes
    # via $0E. The flag (block_type) is the first byte and seeds Z80's
    # running CRC accumulator. MQ.put() blocks if FIFO is full, paced
    # by Z80 reads — no manual synchronization needed.
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
        # Header block: stream from the in-memory buffer (already loaded).
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
        # Data block: stream from file byte-by-byte (avoid allocating a
        # potentially huge buffer for ~14KB+ data blocks).
        el = bytearray(1)
        rd = arch.readinto
        for _ in range(totbytes - 1):
            rd(el)
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
            put(el[0])
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
        # Where the time went: ms per 1K block. Near 52 = the ROM loop's
        # 178 T-states/byte; far above it = the Z80 was slowed down.
        k = sent >> 10
        LOG_ADD("DIAG: LOAD %d bytes, %s; ms/KB after READY: %s"
                % (totbytes, "ok" if not why and echo[0] >= 2 else "why=%d" % why,
                   " ".join(str(prof[i] - prof[i - 1] if i > 1 else prof[1])
                            for i in range(1, k + 1))), 2, TSP.LOG_LEVEL)

    if dry:
        # TX ran empty after READY: each time the Z80 may have read 0x00.
        # Normally 0; anything else says where a Pico-side pause began.
        LOG_ADD("ERROR: LOAD TX ran dry %d times, first at byte %d of %d."
                % (dry, dry_at, totbytes), 2, TSP.LOG_LEVEL)

    if why == 2:
        # The watchdog fired: its own cleanup path, as before. How far we'd
        # got says why: a handful of bytes queued means the Z80 stopped at
        # the very start (it didn't like the flag), not mid-block.
        # Timing says which: TX full for most of the 3 s = the Z80 stopped
        # reading early; TX full only briefly = it was still reading, slowly.
        LOG_ADD("ERROR: LOAD watchdog fired with %d of %d bytes queued, "
                "%d ms after READY; TX full for the last %d ms; dry %d."
                % (sent, totbytes, time.ticks_diff(time.ticks_ms(), t_ready),
                   tx_wait_ms, dry), 2, TSP.LOG_LEVEL)
        ABORT_TX(TSP.LOG_LEVEL)
        if REWIND_ABORTED_SEARCH(TSP):
            LOG_ADD("INFO: LOAD aborted mid-search; tape rewound to "
                    "offset %d." % TSP.offset, 0, TSP.LOG_LEVEL)
        _close_if_local()
        REARM_AFTER_LOAD_ABORT(MQ, TSP)
        return MQ, TSP, log_entries

    if why:
        # BREAK (1) or silence (3). Bytes the Z80 had actually read =
        # queued minus what's still in TX; 0-4 means it was still in the
        # ready-wait before the data. Then: watchdog off, the search
        # rewound if one was in progress, and straight back to idle --
        # the 1.8b ROM is waiting for READY + IDLE to raise Report D.
        read = max(0, sent - txf())
        STOP_WATCHDOG(TSP.LOG_LEVEL)
        rewound = REWIND_ABORTED_SEARCH(TSP)
        _close_if_local()
        MQ_TO_IDLE(MQ, recovered=(why == 3))
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

    # NOTE: do NOT call END_MSG() here. The two wrt(0x01) writes above
    # already provided the final status and the next-iter pre-load.
    # END_MSG would inject an EXTRA 0x01 status into TX, which the Z80
    # consumes as the first byte of the NEXT iteration's data-loop read
    # (where it expects the block_type 0xFF). The CRC accumulator gets
    # offset by one byte from the start, every subsequent byte XORs into
    # the wrong slot, and the final CRC check fails → "Report R - Tape
    # Loading Error" on the data block.
    # If verbose status messages are wanted later, they need a different
    # protocol layout (e.g., write 0x81 + msg BEFORE the pre-load 0x01,
    # making the verbose directive the final response instead of an
    # additional 0x01).

    dead = True
    return MQ, TSP, log_entries


def LOAD_ZX(MQ, TSP):
    """Send one TAP block to the Spectrum ROM in ZX48 mode.

    ZX48 is a much simpler protocol than the TS-2068 LVM one that
    LOAD_TS implements. The customised Spectrum ROM (flash slot 0) has
    no status port, no pre-header and no echo phase:

        Z80  -> OUT ($0E),'L'      (76; consumed by ZX48_IO's dispatch)
        Pico -> flag byte          (block type: 0x00 header, 0xFF data)
        Pico -> content bytes      (Z80 reads at ~43us each)
        Pico -> CRC byte
        Z80  -> nothing            (its SA/LD-RET just returns)

    So the response is exactly `totbytes` bytes: the TAP block minus
    its 2-byte length prefix. There is deliberately NO status byte and
    NO V6 pre-load chain here — any extra byte stays in TX and the next
    'L' reads it as that block's flag byte.

    DUAL-PORT MIGRATION (2026-09):
      - The single-port version wrote 0x40 ("continue") ahead of the
        flag byte, which the Z80 read off the shared FIFO. Under
        dual-port that flag lives on $0F (scratch Y), so the write is
        gone. NOTE: Ricardo's newer Spectrum ROM ("nuevo LD") polls
        $0E for 0x40 before the first byte and is therefore NOT
        compatible with this firmware — the ROM in flash slot 0 of
        Pico-v15w.rom is. See docs/rom-analysis/.
      - Off-by-one fix: this streamed flag + totbytes bytes, one more
        than the Z80 reads. The extra byte (the next block's length-low)
        stayed in TX and poisoned the following transaction; the
        "TX FIFO not empty after ZX mode" cleanup in ZX48_IO was
        papering over exactly that.
      - Y is left READY on exit. The PIO drops Y to 0 on every Z80 OUT
        (issue #14 auto-busy), including the 'L' that got us here, so a
        future ROM that polls $0F would otherwise stall.
    """
    global dead
    global kill
    global busy
    
    global log_entries
    log_entries = ""
    
    led = Pin(25, Pin.OUT)
    led.value(1)
   
    totbytes = 0
    
    blk_info = bytearray(3)
    el = bytearray(1)

    if (not TSP.f_name or TSP.totlen == 0):
        local_fname = "/assets/nofile.tap"
        LOG_ADD("WARNING: no file mounted in LOAD_ZX", 1, TSP.LOG_LEVEL)
    else:    
        local_fname = "/TMP/temp.tap"

    arch = open(local_fname, "rb")
    arch.seek(TSP.offset)

    arch.readinto(blk_info)
    totbytes = blk_info[0] + 256 * blk_info[1]
    
    dead = False
    # totbytes counts flag + content + CRC. The flag is sent below, so
    # the file loop streams the remaining totbytes-1 bytes. Sending
    # totbytes here is the off-by-one described in the docstring.
    r = range(totbytes - 1)

    START_WATCHDOG(3, MQ, TSP)

    wrt = MQ.put
    # Dual-port: 0x40 continue flag is on port $0F (scratch Y).
    wrt(blk_info[2])

    # Stage the flag byte FIRST, then raise READY. A ROM patched to poll
    # $0F after its 'L' reads $0E the instant the poll succeeds, so the
    # byte has to be in TX before Y goes high. Harmless with the current
    # ROM, which ignores $0F and just waits ~1ms.
    MQX(MQ, "mov(y, invert(null))")

    for i in r:
        arch.readinto(el)
        wrt(el[0])

        if kill:
            ABORT_TX(TSP.LOG_LEVEL)
            arch.close()

            return MQ, TSP, log_entries

    arch.close()

    # Y = READY. Nothing else to send: the Z80 has read its CRC byte and
    # returns without a status read.
    MQX(MQ, "mov(y, invert(null))")
    led.value(0)

    TSP.offset += totbytes + 2
    TSP.tap_idx += 1
    
    if (TSP.offset >= TSP.totlen):
        TSP.offset = 0
        TSP.tap_idx  = 0
        
        LOG_ADD("WARNING: reached end of offset table in LOAD_ZX, rewinding...", 1, TSP.LOG_LEVEL)
    
    dead = True
   
    return MQ, TSP, log_entries


def LOAD_ZX_C(MQ, TSP, buf_size):
    """ZX Spectrum LOAD in 'compatible' mode — stream the tape continuously.

    Where LOAD_ZX answers one 'L' with exactly one block, this reads up
    to buf_size of the TAP into memory and streams every block back to
    back. MQ.put() blocks on a full TX FIFO, so the Z80 paces it: blocks
    the Spectrum ROM skips over (wrong name, wrong type) are consumed by
    its own LD-BYTES calls exactly as they would be off a tape running
    continuously. That is what makes hard-to-load TAPs work here and not
    in LOAD_ZX. It is memory-hungry and can OOM the Pico.

    Each buffered entry is rd_bytes[2:len+2] — flag + content + CRC, the
    TAP block minus its length prefix — so no per-call byte accounting
    is needed and the LOAD_ZX off-by-one never applied here.

    DUAL-PORT MIGRATION (2026-09): the 0x40 continue byte is gone (it
    lives on $0F now), the end-of-stream wait is bounded instead of
    spinning forever, and Y is left READY. See LOAD_ZX for the full
    protocol notes.
    """
    global log_entries
    log_entries = " "
    
    cur_buf = []
    
    if (TSP.offset >= TSP.totlen):
        return MQ, TSP, log_entries
    
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
        return MQ, TSP, log_entries
        
    arch.close()
    
    TSP.offset += len(rd_bytes)
    
    while (rd_bytes):
        gc.collect()
        long = rd_bytes[0] + (256*rd_bytes[1])
        
        if (long > len(rd_bytes)):
            TSP.offset -= len(rd_bytes)
            break
        hasta = long + 2

        cur_buf.append(rd_bytes[2:hasta])
        gc.collect()

        rd_bytes = rd_bytes[hasta:]
        gc.collect()
        
    del rd_bytes
    gc.collect()
    
    wrt = MQ.put
    led = Pin(25, Pin.OUT)

    # Stage the first byte before raising READY — see the same note in
    # LOAD_ZX. memoryview keeps this from copying the (large) buffer.
    if cur_buf and len(cur_buf[0]):
        MQ.put(cur_buf[0][0])
        MQX(MQ, "mov(y, invert(null))")
        cur_buf[0] = memoryview(cur_buf[0])[1:]

    for ar in cur_buf:

        led.value(1)
        # Dual-port: 0x40 (= 64) continue flag is on port $0F (scratch Y).
        # MQ.put(64) removed — just stream data bytes.

        for el in ar:
            MQ.put(el)

        led.value(0)

    # Wait for the Z80 to drain what's left, but bounded: in compatible
    # mode we stream the whole tape, so if the Spectrum ROM found its
    # file and stopped asking, the tail never gets read and the old
    # unbounded spin here hung ZX48 mode until reset. After the timeout
    # we drop the remainder — leaving it in TX would make the next 'L'
    # read a stale byte as its flag.
    _tw = time.ticks_ms()
    while MQ.tx_fifo() != 0:
        if time.ticks_diff(time.ticks_ms(), _tw) >= 2000:
            LOG_ADD("WARNING: LOAD_ZX_C timed out with %d bytes unread; "
                    "discarding tail." % MQ.tx_fifo(), 1, TSP.LOG_LEVEL)
            while MQ.tx_fifo() != 0:
                MQX(MQ, "pull (noblock)")
                MQX(MQ, "mov (osr, null)")
            break

    MQX(MQ, "mov(y, invert(null))")                   # Y = READY

    cur_buf = []

    return MQ, TSP, log_entries


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


def _WAIT_CORE1(log_level, timeout_ms=3000):
    """Wait (bounded) for the core1 watchdog to release `busy`.

    Same rationale as ABORT_TX's wait, for the paths that end a
    transaction without an abort handshake. Bounded because an
    unbounded spin on a cross-core flag wedges the dispatcher if the
    thread ever dies without clearing it.
    """
    global busy
    _t = time.ticks_ms()
    while busy:
        if time.ticks_diff(time.ticks_ms(), _t) >= timeout_ms:
            LOG_ADD("ERROR: timed out waiting for core1 watchdog", 2, log_level)
            busy = False
            break
    return


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

    Caller is responsible for `dead = True` and for returning.
    """
    MQ.put(status)
    MQX(MQ, "mov(y, invert(null))")   # Y -> READY so the Z80 reads our status
    return DRAIN_REFUSED_SAVE(MQ, quiet_ms)


def DRAIN_REFUSED_SAVE(MQ, quiet_ms=500):
    """Resync the RX FIFO after refusing a SAVE at the post-header status.

    Refusing works by writing an error status where the Z80 expects the
    mid-phase 0x01: its STATUS_TO_REPORT path RST-8's, shows the BASIC
    report and aborts BEFORE sending the data block. When that lands no
    data arrives at all and this returns 0 almost immediately.

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
    global busy, dead, kill
    global log_entries
    log_entries = ""

    from TS.tspico import TLM         # lazy import: tspico imports SAVE_TS, so a
                                      # module-level import here would be circular
    dead = False
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
        dead = True
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
        dead = True
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
        dead = True
        _fl = REFUSE_SAVE(MQ, 0x02)      # -> Report R "Tape loading error"
        LOG_ADD("SAVE refused: bad header CRC, drained %d byte(s)" % _fl,
                2, TSP.LOG_LEVEL)
        TLM("SAVE_TS CRC refusal drained", "%d residual byte(s)" % _fl)
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
    save_name = None
    if not (TSP.f_name and TSP.append):
        save_name, name_ok = SAVE_NAME(hdr)
        if not name_ok:
            TLM("SAVE_TS EXIT filename not allowed", "%r" % save_name)
            dead = True
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
        dead = True
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
            dead = True
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
    # 3 s + 1 s per 4K: the Z80 SAVEs at ~43 us/byte, and RX_BLOCK bounds
    # real silence on its own (see LOAD_TS for why a flat budget failed).
    _wd = START_WATCHDOG(3 + long // 4096, MQ, TSP)
    TLM("SAVE_TS watchdog spawned", "ok=%s long=%d, waiting for data" % (
        _wd, long))

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

    if why == RXB_KILL:
        TLM("SAVE_TS EXIT killed by watchdog", "at byte %d/%d" % (got, long))
        # No status bytes here: the watchdog is pumping pull(noblock)
        # through TX while it waits for `dead`, so anything staged now
        # is discarded. ABORT_TX sets `dead` and waits for core1 to
        # finish bouncing the SM (its BLINK alone is ~1s) before we
        # let the dispatcher touch it. This is what LOAD_TS does.
        ABORT_TX(TSP.LOG_LEVEL, "SAVE_TS")
        return MQ, TSP, log_entries, False

    if why == RXB_STALL and got == 0:
        TLM("SAVE_TS EXIT no data after 1s")
        # Refuse rather than write 0x01 0x01. If the Z80 aborted
        # (BREAK on a ROM without the 0Fh abort) it isn't reading and the
        # byte is harmless -- the dispatcher's ACTIVATE_MQ discards it. If
        # it was merely slow, claiming OK meant it went on to stream a data
        # block into a returned handler, jamming RX for the next command.
        dead = True
        _fl = REFUSE_SAVE(MQ, 0x02)  # -> Report R "Tape loading error"
        LOG_ADD("ERROR: SAVE_TS aborted (no data after 1s), drained %d"
                % _fl, 2, TSP.LOG_LEVEL)
        _WAIT_CORE1(TSP.LOG_LEVEL)
        return MQ, TSP, log_entries, False

    if why:
        # BREAK (a port-0Fh write; the 1.8b ROM checks every 256 bytes) or
        # the Z80 went silent mid-block. The partial SAVE is discarded --
        # nothing is written to SD or flash. The Z80 is waiting for READY +
        # IDLE (BREAK) or has gone (stall); the dispatcher's re-arm after we
        # return is the way back, with RECOVERED for a stall.
        STOP_WATCHDOG(TSP.LOG_LEVEL)
        dead = True
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
        dead = True
        # Wait (bounded) for the Z80 to READ the 02 before returning: the
        # dispatcher's ACTIVATE_MQ rebuilds the SM, which throws an unread
        # TX FIFO away and stages its own 0x01 -- and the Z80 would print
        # "0 OK" for a SAVE that wrote nothing. Same wait as the success
        # path's before ENA_SD.
        _tw = time.ticks_ms()
        while MQ.tx_fifo() > 1:
            if time.ticks_diff(time.ticks_ms(), _tw) >= 300:
                break
        _WAIT_CORE1(TSP.LOG_LEVEL)
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

    dead = True
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
    if TSP.f_name and TSP.append:
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

    # NOTE: do NOT call END_MSG() here either, for the same reason as in
    # LOAD_TS. The two wrt(0x01) writes earlier already handled the final
    # status + next-iter pre-load chain. An extra END_MSG would orphan a
    # status byte in TX that corrupts the next transaction.

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
        ENA_SD()
        with open(filename, mode) as f1:
            f1.write(hdr)
            f1.write(blk)
    except Exception as _e:
        saved = False
        LOG_ADD("ERROR: SAVE write FAILED for %s: %s" % (filename, _e),
                2, TSP.LOG_LEVEL)
        TLM("SAVE_TS write FAILED", "%r: %s" % (filename, _e))
        if mode == "wb":
            # We advertised this name to the dispatcher, which would try to
            # mount it. Nothing landed, so take it back.
            TSP.f_name = ""
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


def SAVE_ZX(MQ, TSP):
    """Receive a SAVE from the Spectrum ROM in ZX48 mode and write a TAP.

    The Spectrum ROM's SA-BYTES sends, per block and with no handshake:

        OUT ($0E),'S'   (83)      then len_lo, len_hi, flag,
                                  content bytes, CRC byte

    ZX48_IO consumed the header block's 'S' when it dispatched here, so
    this reads:

        21 bytes   len_lo, len_hi, flag, 17 header bytes, CRC
         1 byte    the 'S' that opens the data block  (discarded)
      len+4 bytes  len_lo, len_hi, flag, content, CRC

    where len comes from the tape header's length field (hdr[14:16]).
    The two length fields are then rewritten into TAP form (block length
    = content + flag + CRC) and both blocks are appended to a .tap on the
    SD card named after the header.

    The Z80 reads nothing back — SA-BYTES ends with EI/RET — so there is
    no status byte to send, and sending one would leave an orphan in TX.

    DUAL-PORT MIGRATION (2026-09):
      - Was ending with ENA_MQ(), which rebuilt the OLD single-port
        TS_IO state machine at 15 MHz and handed it back to ZX48_IO as
        the session's SM: after one ZX SAVE the bus stopped decoding
        $0E/$0F apart for the rest of the session. Now ENA_MQ_DUAL().
      - RX reads are masked to 8 bits like SAVE_TS. The RX word is 9
        bits (bit 8 = A0), and an unmasked value >= 256 assigned into a
        bytearray raises and drops the Pico to the REPL.
    """
    global kill
    global dead
    global busy
    
    global log_entries
    log_entries = ""
    
    dead = False
    
    r1 = range(21)
    crc_h = 0
    ant = 0
    wrt = MQ.put
    
    hdr = bytearray(21)
    
    START_WATCHDOG(5, MQ, TSP)

    # Raise READY: we are in the handler and listening. The Z80's 'S'
    # dropped Y (PIO auto-busy), and a ROM patched to poll $0F after 'S'
    # waits here instead of guessing with a ~1ms delay — which is not
    # long enough to cover ZX48_IO's dispatch plus this thread spawn.
    MQX(MQ, "mov(y, invert(null))")

    for i in r1:
        hdr[i] = MQ.get() & 0xFF

    long = (256*hdr[15]) + hdr[14] + 4
    r2 = range(long)

    blk = bytearray(long)

    MQ.get()                     # the 'S' that opens the data block
    MQX(MQ, "mov(y, invert(null))")   # READY again for the data block's poll

    for i in r2:
        blk[i] = MQ.get() & 0xFF
        if kill:
            LOG_ADD("ERROR: SAVE_ZX failed! " + str(MQ.tx_fifo()) + " " + str(MQ.rx_fifo()), 2, TSP.LOG_LEVEL)
            dead = True
            blk = []
            
            return MQ, TSP, log_entries

    dead = True
    
    while(MQ.rx_fifo() != 0):
        fff = MQ.get()

    hdr[0] = 19
    
    l_blk = len(blk) - 2
    
    blk1 = int (l_blk / 256)
    blk0 = l_blk - (blk1 * 256)
    
    blk[0] = blk0
    blk[1] = blk1
    
    filename = hdr[4:14].decode()
    filename = filename.strip() + ".tap"
    filename = TSP.cur_path + "/" + filename
    
    ENA_SD()
    
    with open(filename, 'wb') as f1:
        f1.write(hdr)
        
    with open(filename, 'ab') as f1:
        f1.write(blk)
        
    hdr = []
    blk = []
    
    while(MQ.tx_fifo() != 0):
        pass
    
    while(MQ.rx_fifo() != 0):
        fff = MQ.get()
        
    os.umount("/sd")
    # ENA_SD() re-claimed GPIO 2-4 for SPI, so the bus SM has to be
    # rebuilt before ZX48_IO's loop reads the FIFO again. DUAL-PORT: this
    # was ENA_MQ(), which rebuilt the single-port TS_IO SM at 15 MHz.
    MQ = ENA_MQ_DUAL(MQ)

    LOG_ADD("INFO: Finished SAVE ZX successfully " + str(MQ.tx_fifo()) + " " + str(MQ.rx_fifo()), 0, TSP.LOG_LEVEL)

    return MQ, TSP, log_entries


def CORE1_BUSY():
    """True while this module's WATCHDOG thread still owns core1.

    THERE ARE TWO SEPARATE `busy` VARIABLES AND THEY ARE EASY TO CONFUSE.
    tspico.py imports only named symbols from this module, and `busy` is
    not one of them, so its own `global busy` binds a DIFFERENT
    module-level variable -- the one its SAVE_LOG / BLINK_LED / CHK_STATUS
    threads set. A `while busy:` in tspico.py therefore does NOT wait for
    the LVM watchdog here, however much it reads like it does.

    That matters because core1 is one resource: _thread.start_new_thread
    raises OSError "core1 in use" if ANY of those threads is still
    running. Code that wants to know whether it is safe to spawn has to
    consult both flags -- its own `busy` and this function.

    NOTE the three `while busy:` waits in tspico.py's main LVM loop are
    subject to exactly this, and are deliberately NOT changed here: they
    are unbounded spins, so making them wait on something that can
    actually be True would convert a no-op into a potential hang. They are
    left as-is until someone can test that on hardware. START_WATCHDOG()
    tolerating a failed spawn is what actually protects those paths today.
    """
    return busy


def START_WATCHDOG(secs, MQ, TSP):
    """Spawn the core1 WATCHDOG for an LVM transaction. Returns True if it ran.

    ALWAYS use this instead of calling _thread.start_new_thread(WATCHDOG,
    ...) directly. An unguarded spawn is the nastiest failure mode in this
    firmware: if core1 is still finishing a previous watchdog's cleanup
    -- which ends with a ~1 second BLINK() -- the call raises OSError
    "core1 in use", and with no handler it propagates out of TS2068_IO
    into main.py, which has no try/except either. The Pico drops to a
    REPL and the user sees "locked up, LED stopped blinking". tspico.py
    guards its SAVE_LOG spawn for exactly this reason; the LVM handlers
    did not.

    Losing the watchdog for one transaction is a far smaller problem than
    losing the dispatcher, so a failed spawn is logged and the caller
    proceeds unguarded. We deliberately do NOT retry-with-sleep: by the
    time a caller needs the watchdog the Z80 may be moments from
    streaming, and the RX FIFO is only 4 deep -- a few ms of sleep here
    would drop bytes, trading a rare hang for routine corruption.

    `kill` is cleared HERE, on core0, before the thread starts. WATCHDOG
    clears it too, but on core1 -- and the caller's drain loop reads
    `kill` as soon as this returns. Clearing it on the spawning core
    removes that race instead of documenting it (see WATCHDOG's own
    comment about the window).
    """
    global kill

    kill = False
    try:
        _thread.start_new_thread(WATCHDOG, (secs, MQ, TSP))
        return True
    except OSError:
        LOG_ADD("WARNING: core1 busy, running without a watchdog",
                1, TSP.LOG_LEVEL)
        return False


def WATCHDOG(secs, MQ, TSP):
    """Background timeout watcher for LVM transactions. Runs on core1.

    Spawned by LOAD_TS / SAVE_TS via _thread.start_new_thread() right
    before the bulk transfer begins. Its job is to detect when a
    transaction has hung (e.g., user pressed BREAK, Z80 crashed, bus
    glitch) and force-clean the FIFOs so the system can continue.

    PROTOCOL between this thread (core1) and the main handler (core0):

        Main handler                          WATCHDOG thread
        ─────────────                          ───────────────
        sets dead = False
        spawns WATCHDOG(secs, MQ, TSP)
                                               sets kill = False
                                               sets busy = True
                                               loops checking:
                                                 - secs elapsed?  → cleanup
                                                 - dead == True?   → exit cleanly
        ... does work ...
        sets dead = True (= "I'm done")
                                               notices dead, breaks loop
                                               sets busy = False
                                               returns
        observes busy == False
        proceeds to next transaction

    If the main handler doesn't set dead = True within `secs` seconds:
      1. Log the abort.
      2. Drain the PIO state machine's TX FIFO (pull noblock; clear OSR).
      3. Drain the RX FIFO.
      4. Bounce the SM (active off → BLINK warning → active on).
      5. Set kill = True so the main handler's `if kill:` checks fire.
      6. Wait for main handler to acknowledge (sets dead = True).
      7. Set busy = False to release the dispatcher.

    Args:
        secs: timeout in seconds (typically 3 for LOAD, 5 for SAVE).
        MQ:   TS_IO_DUAL state machine.
        TSP:  PICO_STATUS for log level access.
    """
    global kill, dead, busy

    led = Pin(25, Pin.OUT)

    # Initialize the cross-thread flags. Doing this here (rather than
    # at module level) ensures every transaction starts with a clean
    # state. Note: there's a small race window where the main handler
    # could reference `kill` BEFORE this line executes — that's why we
    # also initialize them at module level (see top of file).
    kill = False
    busy = True

    LOG_ADD("INFO: Starting watchdog...", 0, TSP.LOG_LEVEL)
    secs = secs * 1_000_000     # convert to microseconds for ticks_us
    led.value(1)
    t_init = time.ticks_us()

    # Polling loop: tight check, no sleep. We need to react quickly
    # when `dead` flips True so the dispatcher can resume promptly.
    while (time.ticks_us() - t_init) < secs:
        if dead:
            break

    # Two exit paths from the loop above:
    #   (a) `dead` went True before timeout → normal completion, skip cleanup.
    #   (b) `secs` elapsed with dead still False → transaction hung; clean up.
    if not dead:
        LOG_ADD("ERROR: Abnormal termination. Clearing TX/RX FIFO....",
                2, TSP.LOG_LEVEL)

        # Pump PIO instructions to drain whatever's stuck in the SM
        # internals (OSR, ISR, FIFOs). The kill = True flag tells the
        # main handler to abort its current loop iteration.
        while not dead:
            MQX(MQ, "pull (noblock)")     # drain TX FIFO into OSR
            MQX(MQ, "mov (osr, null)")    # discard OSR contents
            MQX(MQ, "mov (isr, null)")    # clear ISR
            MQX(MQ, "push (noblock)")     # push (nothing) to RX
            kill = True                   # signal main handler

        # Drain Python-side FIFOs.
        while MQ.rx_fifo() != 0:
            MQ.get()
        while MQ.tx_fifo() != 0:
            MQX(MQ, "pull (noblock)")
            MQX(MQ, "set (osr, null)")

        # Bounce the SM to flush any latched state, then BLINK to give
        # the user a visual indication something went wrong.
        MQ.active(0)
        LOG_ADD("INFO: TX/RX FIFO successfully cleared. Operation finished",
                0, TSP.LOG_LEVEL)
        BLINK()
        MQ.active(1)
        LOG_ADD("INFO: Ending watchdog. Operation ended normally",
                0, TSP.LOG_LEVEL)

    # Always reset flags before exiting so the next transaction starts clean.
    kill = False
    busy = False

    led.value(0)