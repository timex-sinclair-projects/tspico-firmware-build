"""PROD-TRACE harness — runs a FAITHFUL COPY of production's SAVE_TS + WATCHDOG
with telemetry at every phase, from Thonny (no UF2 rebuild).

Why: the production ~20s SAVE hang lives entirely inside SAVE_TS, which has no
TLM() calls, so it's a black box in the normal firmware log. The telemetry we
captured showed tx=2 (Z80 never read the final status) and rx=4 (RX FIFO full
of undrained bytes) when the dispatcher resumed -- a framing desync or early
exit. This harness copies the REAL SAVE_TS (tspico_io.py:991-1208) and WATCHDOG
(tspico_io.py:1302-1404) verbatim, only inserting TLM() calls, so we can see
which exit path it takes and with what values.

The copies below are line-for-line faithful to production; the ONLY additions
are TLM(...) calls and the WRITE_TARGET branch. If production changes, re-copy.

Usage (Thonny):
  1. Set CONFIG below (WRITE_TARGET; "flash" isolates the transfer from SD).
  2. Run this file. Reset the TS-2068.
  3. On the 2068: type a small program, then  SAVE "test"
  4. Read the TLM log. The last line before it hangs = where SAVE_TS dies.
  5. Ctrl-C to stop.
"""

import os
import time
import gc
import _thread
from machine import Pin, SPI, freq
from rp2 import StateMachine

freq(270_000_000)

from TS.tspico_io import TS_IO_DUAL, set_ctrl, sel_bank, ENA_SD

HARNESS_VERSION = "save_harness_prodtrace v1 (2026-07-21)"

# ===========================================================================
# CONFIG
# ===========================================================================
WRITE_TARGET = "flash"       # "flash" (isolate transfer) | "sd" (real ENA_SD)
FLASH_DIR    = "/TMP"
CUR_PATH     = "/sd/TAP"     # production TSP.cur_path default
MOUNTED_TAP  = None          # TSP.f_name; None => create-new
APPEND       = False         # TSP.append

# FIX under test: an empty program sends BLEN=0 in the header, but the Z80's
# SA-BYTES send loop decrements DE *then* tests it, so DE=0 wraps to 0xFFFF and
# it floods 65536 data bytes (the classic ZX "SAVE 0 = SAVE 64K" ROM quirk).
# An empty save should be REFUSED, not ingested. So when we see BLEN==0 in the
# header we send an ERROR status at the post-header status read -- the Z80's
# STATUS_TO_REPORT path RST-8's, shows a Report, and ABORTS before it sends the
# data block, so there is no 64K flood at all.
#
# BLEN0_STATUS is the status byte sent for an empty save -> which BASIC Report:
#   0x04 -> Report Q "Parameter error"      0x08 -> Report A "Invalid argument"
#   0x05 -> Report C "Nonsense in BASIC"    0x00 -> Report J "Invalid I/O device"
# (0x00 is the most reliable abort -- direct path, no FUNCTION-chain -- but the
# least apt wording. 0x08 "Invalid argument" reads best; try it first.)
BLEN0_STATUS = 0x08

# ===========================================================================
# Production-format telemetry
# ===========================================================================
_tlm_last = [0]

def TLM(msg, extra=""):
    global MQ
    now = time.ticks_us()
    dt = time.ticks_diff(now, _tlm_last[0]) if _tlm_last[0] else 0
    _tlm_last[0] = now
    try:
        tx = MQ.tx_fifo(); rx = MQ.rx_fifo()
    except Exception:
        tx = "?"; rx = "?"
    line = "[TLM %d dt=%d tx=%s rx=%s] %s" % (now, dt, tx, rx, msg)
    if extra:
        line += ": " + extra
    print(line)

def LOG_ADD(msg, level, log_level):
    TLM("LOG", msg)

def BLINK():
    pass

# ===========================================================================
# Cross-thread flags — the SAME globals SAVE_TS and WATCHDOG share in
# production (tspico_io.py module globals). The kill-race suspect lives here.
# ===========================================================================
kill = False
dead = False
busy = False
log_entries = ""

class TSP_STUB:
    def __init__(self):
        self.f_name = MOUNTED_TAP if MOUNTED_TAP else []
        self.append = APPEND
        self.cur_path = CUR_PATH
        self.VERBOSE = True
        self.LOG_LEVEL = 2

TSP = TSP_STUB()

# ===========================================================================
# Hardware bring-up (same as the proven observers)
# ===========================================================================
print("=" * 64)
print(HARNESS_VERSION)
print("  WRITE_TARGET=%s  MOUNTED_TAP=%r  APPEND=%s" % (
    WRITE_TARGET, MOUNTED_TAP, APPEND))
print("=" * 64)

U6_EN   = Pin(12, Pin.OUT, Pin.PULL_UP)
WAIT    = Pin(14, Pin.OUT, Pin.PULL_DOWN)
U10_ENA = Pin(19, Pin.OUT, Pin.PULL_UP)
U13_ENA = Pin(20, Pin.OUT, Pin.PULL_UP)
BE      = Pin(21, Pin.OUT, Pin.PULL_UP)
ROSCS   = Pin(26, Pin.IN,  Pin.PULL_DOWN)
U10_WE  = Pin(27, Pin.OUT, Pin.PULL_UP)
for _p in (U6_EN, WAIT, U10_ENA, U13_ENA, BE, U10_WE):
    _p.value(1)

rom_sm = StateMachine(4, set_ctrl, freq=150_000_000,
                      in_base=Pin(0, Pin.IN), jmp_pin=Pin(26),
                      set_base=Pin(21, Pin.OUT), out_base=Pin(19, Pin.OUT))
rom_sm.active(1)
bank_sm = StateMachine(5, sel_bank, freq=150_000_000,
                       jmp_pin=Pin(26), out_base=Pin(15, Pin.OUT))
bank_sm.active(1)
rom_sm.put(0x0A)
bank_sm.put(0x01)

MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000,
                  out_base=Pin(2, Pin.OUT), in_base=Pin(2, Pin.IN),
                  jmp_pin=Pin(11), sideset_base=Pin(12, Pin.OUT))
MQ.active(1)
MQ.exec("mov(y, invert(null))")

def MQ_READY():
    MQ.exec("mov(y, invert(null))")

def make_mq():
    global MQ
    MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000,
                      out_base=Pin(2, Pin.OUT), in_base=Pin(2, Pin.IN),
                      jmp_pin=Pin(11), sideset_base=Pin(12, Pin.OUT))
    MQ.active(1)

def sd_handback():
    """Equivalent to the dispatcher's DEACTIVATE_SD + ACTIVATE_MQ after an
    ENA_SD-based SD write, so the bus returns to the PIO."""
    try:
        os.umount("/sd")
    except Exception:
        pass
    Pin(28, Pin.OUT, Pin.PULL_UP).value(1)
    for gp in (2, 3, 4):
        Pin(gp, Pin.OUT).value(0)
    make_mq()

# boot-noise flush + rolling preload
_n = 0
_last = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), _last) < 300:
    if MQ.rx_fifo() > 0:
        MQ.get(); _n += 1; _last = time.ticks_ms()
MQ.put(0x01)
MQ_READY()
TLM("boot complete", "flushed %d, preload 0x01, Y=READY" % _n)


# ===========================================================================
# WATCHDOG — faithful copy of tspico_io.py:1302-1404, + TLM.
# ===========================================================================
def WATCHDOG(secs, MQ, TSP):
    global kill, dead, busy
    led = Pin(25, Pin.OUT)
    kill = False
    busy = True
    TLM("WD start", "secs=%d dead=%s kill=%s" % (secs, dead, kill))
    secs = secs * 1_000_000
    led.value(1)
    t_init = time.ticks_us()
    while (time.ticks_us() - t_init) < secs:      # tight poll, no sleep
        if dead:
            break
    if not dead:
        TLM("WD TIMEOUT — abnormal termination, clearing FIFOs")
        while not dead:
            MQ.exec("pull (noblock)")
            MQ.exec("mov (osr, null)")
            MQ.exec("mov (isr, null)")
            MQ.exec("push (noblock)")
            kill = True
        while MQ.rx_fifo() != 0:
            MQ.get()
        while MQ.tx_fifo() != 0:
            MQ.exec("pull (noblock)")
            MQ.exec("set (osr, null)")
        MQ.active(0)
        BLINK()
        MQ.active(1)
        TLM("WD bounced SM, done")
    else:
        TLM("WD normal exit", "dead=True observed")
    kill = False
    busy = False
    led.value(0)


# ===========================================================================
# SAVE_TS — faithful copy of tspico_io.py:991-1208, + TLM at every phase.
# ===========================================================================
def SAVE_TS(MQ, TSP):
    global busy, dead, kill
    global log_entries
    log_entries = ""

    # Capture entry state, but do NOT print here — a print between the
    # dispatcher's MQ_READY and this header read sits inside the Z80's tight
    # 18C4/18D2 handshake window and can desync it. Fold it into the
    # header-read-done line, which is AFTER the read.
    _enter = "dead=%s kill=%s busy=%s f_name=%r append=%s" % (
        dead, kill, busy, TSP.f_name, TSP.append)
    dead = False
    wrt = MQ.put
    gc.collect()

    # ---- Phase 2: 21-byte HEADER block ----
    _t0 = time.ticks_us()
    hdr = bytearray(21)
    for i in range(21):
        hdr[i] = MQ.get() & 0xFF
    TLM("header read done", "%dus  enter[%s]  bytes=%s" % (
        time.ticks_diff(time.ticks_us(), _t0), _enter,
        " ".join("%02X" % b for b in hdr)))

    crc_calc = hdr[0]
    for i in range(3, 20):
        crc_calc ^= hdr[i]
    if crc_calc != hdr[20]:
        TLM("EXIT: header CRC FAIL", "got=0x%02X want=0x%02X" % (hdr[20], crc_calc))
        wrt(0x01)
        wrt(0x01)
        MQ.exec("mov(y, invert(null))")
        dead = True
        return MQ, TSP, log_entries

    blen = hdr[14] + 256 * hdr[15]
    _nm = "".join(chr(c) if 32 <= c < 127 else "." for c in hdr[4:14])
    TLM("header CRC ok", "BLEN=%d name='%s'" % (blen, _nm))

    if blen == 0:
        # Empty program. Refuse it: send an ERROR status at the post-header
        # status read so the Z80 RST-8's (Report) and ABORTS before sending the
        # 64K flood (DE=0 wrap). No data phase at all in the good case.
        TLM("EMPTY save (BLEN=0): refusing", "status 0x%02X" % BLEN0_STATUS)
        wrt(BLEN0_STATUS)
        MQ.exec("mov(y, invert(null))")   # Y ready so the Z80 reads our status
        dead = True
        # Safety net: if the abort didn't take and the Z80 floods anyway, drain
        # until the bus goes quiet so the FIFO resyncs. Abort working => ~0 bytes.
        _fl = 0
        _last = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), _last) < 500:
            if MQ.rx_fifo() > 0:
                MQ.get()
                _fl += 1
                _last = time.ticks_ms()
        TLM("empty-save refused", "drained %d residual byte(s)" % _fl)
        return MQ, TSP, log_entries

    long = blen + 4
    blk  = bytearray(long)

    wrt(0x01)
    MQ.exec("mov(y, invert(null))")
    TLM("mid-status sent, Y=READY")

    # ---- Phase 3: DATA block ----
    _thread.start_new_thread(WATCHDOG, (5, MQ, TSP))
    TLM("watchdog spawned", "waiting <=1s for first data byte  kill=%s" % kill)

    t_init = time.ticks_us()
    while MQ.rx_fifo() == 0:
        if time.ticks_diff(time.ticks_us(), t_init) >= 1_000_000:
            TLM("EXIT: no data after 1s (abort)")
            wrt(0x01)
            wrt(0x01)
            MQ.exec("mov(y, invert(null))")
            dead = True
            while busy:
                pass
            return MQ, TSP, log_entries

    _t0 = time.ticks_us()
    for i in range(long):
        blk[i] = MQ.get() & 0xFF
        if kill:
            TLM("EXIT: killed by watchdog", "at byte %d/%d" % (i, long))
            wrt(0x01)
            wrt(0x01)
            MQ.exec("mov(y, invert(null))")
            dead = True
            return MQ, TSP, log_entries
    TLM("data read done", "%dus  %d bytes  crc_byte=0x%02X" % (
        time.ticks_diff(time.ticks_us(), _t0), long, blk[long - 1]))

    # ---- final status + preload (BEFORE the slow SD write) ----
    wrt(0x01)
    wrt(0x01)
    MQ.exec("mov(y, invert(null))")
    dead = True
    totbytes = len(hdr) + long
    TLM("final status+preload sent, Y=READY, dead=True")

    # ---- reconstruct TAP (in-place session strip) ----
    l_hdr = len(hdr) - 2
    hdr[2] = hdr[0]
    hdr[0] = l_hdr & 0xFF
    hdr[1] = (l_hdr >> 8) & 0xFF
    l_blk = len(blk) - 2
    blk[2] = blk[0]
    blk[0] = l_blk & 0xFF
    blk[1] = (l_blk >> 8) & 0xFF

    # ---- filename ----
    if TSP.f_name and TSP.append:
        filename = TSP.f_name
        mode = "ab"
    else:
        filename = hdr[4:14].decode().strip()
        clean_fname = "".join(c for c in filename
                              if c.isalpha() or c.isdigit() or c in "_-")
        if clean_fname != filename:
            TLM("EXIT: filename not allowed", repr(filename))
            return MQ, TSP, log_entries
        if not clean_fname:
            clean_fname = "noname"
        filename = TSP.cur_path + "/" + clean_fname + ".tap"
        mode = "wb"
        TSP.f_name = filename
    TLM("target chosen", "filename=%r mode=%s" % (filename, mode))

    # ---- write ----
    try:
        if WRITE_TARGET == "sd":
            TLM("ENA_SD + write (real production path)")
            ENA_SD()
            with open(filename, mode) as f1:
                f1.write(hdr)
                f1.write(blk)
            os.chdir(TSP.cur_path)
        else:
            fn = FLASH_DIR + "/" + filename.rsplit("/", 1)[-1]
            try:
                os.mkdir(FLASH_DIR)
            except OSError:
                pass
            with open(fn, mode) as f1:
                f1.write(hdr)
                f1.write(blk)
            filename = fn
        TLM("WRITE OK", "%d bytes -> %s" % (totbytes, filename))
    except Exception as e:
        TLM("WRITE FAILED", repr(e))

    return MQ, TSP, log_entries


# ===========================================================================
# Main loop — read pre-header, dispatch SAVE to the traced SAVE_TS.
# ===========================================================================
pre = bytearray(10)
print("=" * 64)
print('READY. On the TS-2068: type a program, then  SAVE "test"')
print("Ctrl-C to stop.")
print("=" * 64)

gc.collect()
try:
    while True:
        if MQ.rx_fifo() == 0:
            # Keep the status pre-load alive during idle: if something on the
            # 2068 side read $0E while idle and ate the pre-load, replenish it
            # so the next SAVE's pre-header status read (18C4) still gets 0x01.
            if MQ.tx_fifo() == 0:
                MQ.put(0x01)
            continue
        for i in range(10):
            pre[i] = MQ.get()
        MQ_READY()
        # ONE print here (we still want the pre-header if SAVE_TS then blocks),
        # but nothing else in the tight window before the header read.
        TLM("pre-header", " ".join("%02X" % b for b in pre))

        if pre[0] == 0x00 and pre[1] == 0x00:
            SAVE_TS(MQ, TSP)
            # dispatcher-equivalent hand-back after SAVE_TS
            if WRITE_TARGET == "sd":
                sd_handback()
            MQ.put(0x01)
            MQ_READY()
            TLM("post-SAVE handback done, preload+ready")
        else:
            TLM("non-SAVE pre-header, ignoring")
            MQ.put(0x01)
            MQ_READY()
except KeyboardInterrupt:
    pass

MQ.active(0)
print("stopped.")
