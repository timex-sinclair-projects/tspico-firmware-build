"""SAVE harness — a clean-room Pico-side implementation of the TS-Pico SAVE
protocol, built from the ROM disassembly (EXROM `l1879h`, the SA-BYTES
replacement) rather than from the production firmware.

Purpose
-------
The production SAVE path does not work end-to-end. This harness reimplements
JUST the SAVE side of the TPI protocol, cleanly and instrumented, so we can:
  1. Prove the SAVE wire protocol works in isolation (write reconstructed
     .tap blocks to Pico flash, no SD pin-sharing in the way), and
  2. Turn any stall into EVIDENCE (which phase, how many bytes, timestamps)
     instead of a silent hang.

It boots the TS-2068 (ROM_SM/BANK_SM), speaks the dual-port protocol
(TS_IO_DUAL on SM0), and handles a normal `SAVE "name"` of any kind
(BASIC / CODE / DATA / SCREEN$ — all identical on the wire; only the header
type byte and payload differ, which we write verbatim).

The wire protocol, from the ROM (verified byte-exact on the host against
make_test_tap.py's known-good output)
-----------------------------------------------------------------------
A normal SAVE makes the Z80 call `l1879h` twice — header block, then data
block:

  HEADER call (flag=0x00):
    pre-header(10) -> [status read, no wait] -> WF_NPH -> header block(21)
                   -> WF_NPH -> [status read]
  DATA call (flag=0xFF), NO pre-header (ROM `jr l18d8h` at 0x1896):
    data block(BLEN+4) -> WF_NPH -> [status read]

  pre-header(10) = [00][TADDR][BANK][sLo][sHi][aLo][aHi][lenLo][lenHi][crc]
                   crc = XOR(bytes 0..8);   TADDR==0 => SAVE
  block(N)       = [flag][sLo][sHi][content...][parity]
                   parity seeds with flag and XORs content, but NOT the two
                   session bytes -> equals the standard ZX tape checksum, so
                   a valid .tap block is [flag][content][parity] with the
                   session stripped.

  Header content (17 bytes at wire[3:20]):
    [3]HDTYPE [4:14]name(10) [14:16]BLEN [16:18]ADDR [18:20]HDVARS
  BLEN (data payload length) is read from the header block, indices 14/15.

Status / readiness handshake (the subtle part)
----------------------------------------------
TS_IO_DUAL auto-sets Y=BUSY (`mov(y, null)`) on EVERY Z80 write, and there is
no hardware /WAIT — readiness is purely the Y register polled in software by
the ROM's WF_NPH loop. Consequences this harness respects:
  * The pre-header status read (ROM 0x18C4) has NO WF_NPH before it, so the
    0x01 for it must already be in TX (pre-loaded). We keep a rolling
    pre-load: boot loads one 0x01, and each SAVE's tail loads the next.
  * The header-block and data-block status reads (ROM 0x1911) ARE gated by a
    preceding WF_NPH, so their 0x01 can be staged after we finish draining.
  * After each receive phase we MUST re-assert MQ_READY(), because the bytes
    we just received left Y=BUSY. WF_NPH's first poll costs ~88 ms, which is
    ample time for that.

Deliberate differences from production (the suspected bugs)
----------------------------------------------------------
  * NO per-byte work in the drain. Production does `hdr[i] = MQ.get() & 0xFF`
    on every byte of the 21-byte blast (tspico_io.py:1060). During a SAVE all
    writes are to port $0E (A0=0 -> bit 8 clear -> value already 0..255), so
    the mask is unnecessary AND it is exactly the per-byte work the two-phase
    rule forbids. We store raw into a bytearray, matching the proven
    pre-header read (`pre[i] = MQ.get()`). This is the leading 9/21-stall
    suspect.
  * Bounded, instrumented waits. Every phase has an inter-byte stall timeout;
    a stall returns the partial count instead of blocking forever.

Usage
-----
  1. Copy this file to the Pico (Thonny), set the CONFIG block below.
  2. Run it. Power on / reset the TS-2068 (it boots via the TS-Pico EXROM).
  3. On the TS-2068:  type a program, then  SAVE "test"
  4. Watch the USB serial log. Ctrl-C in Thonny prints a summary.

To test append: set MOUNTED_TAP to an existing .tap path and APPEND=True.
To test real SD create/append: set WRITE_TARGET="sd".
"""

import os
import time
import gc
from machine import Pin, SPI, freq
from rp2 import StateMachine, asm_pio, PIO

# The PIO transport programs ARE the hardware definition (not SAVE logic), so
# we use the canonical ones, exactly as the sanctioned harness template does.
from TS.tspico_io import TS_IO_DUAL, set_ctrl, sel_bank
from TS.sdcard import SDCard

# NOTE ON STRUCTURE: all hardware *actions* live inside boot()/run()/main() so
# this module can be imported (with the machine/rp2/TS.* modules mocked) and
# its SAVE logic host-tested without a Pico. Thonny "Run" executes the file as
# __main__, so main() still fires on device. See test/save_harness_hosttest.py.

HARNESS_VERSION = "save_harness v1 (2026-07-21)"

# ===========================================================================
# CONFIG — edit these, then re-run.
# ===========================================================================

# Where the reconstructed .tap is written.
#   "flash" — Pico internal flash (FLASH_DIR). Isolates the wire protocol from
#             the SD SPI/PIO pin-sharing. Use this first.
#   "sd"    — real SD card create/append at SD_DIR (includes the pin handoff).
WRITE_TARGET = "flash"

FLASH_DIR = "/TMP"          # flash target dir (created if missing)
SD_DIR    = "/sd/TAP"       # SD target dir (must exist on the card)

# Mount state driving the create-new vs. append decision.
#   MOUNTED_TAP = None            -> no tap mounted; each SAVE creates a new
#                                    <name>.tap from the header's filename.
#   MOUNTED_TAP = "/TMP/foo.tap"  -> that tap is "mounted".
#   APPEND = True                 -> when a tap is mounted, SAVE appends to it.
# Combinations:
#   None + False  : every SAVE creates <name>.tap (overwrites by name).
#   None + True   : first SAVE creates+mounts <name>.tap; later SAVEs append.
#   path + True   : every SAVE appends to `path`.
MOUNTED_TAP = None
APPEND      = False

# Diagnostics
VERBOSE          = True     # per-transaction logging over USB serial
STALL_MS         = 3000     # inter-byte silence that counts as a stall (ms)
VERIFY_DATA_CRC  = True     # production does NOT; we check it for diagnostics

# ===========================================================================
# Local NULL_SM (parks SM0 with no pin claims so SPI can take GPIO 2-4).
# Defined here to avoid importing the 200 KB TS.tspico module.
# ===========================================================================

@asm_pio(autopull=True, pull_thresh=8)
def NULL_SM():
    nop()


# ===========================================================================
# State-machine handles + control. The main dual-port I/O SM (MQ) is a module
# global because the SD path recreates it (see sd_mount / sd_restore).
# ===========================================================================

MQ = None
rom_sm = None
bank_sm = None

def make_mq():
    global MQ
    MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000,
                      out_base=Pin(2, Pin.OUT), in_base=Pin(2, Pin.IN),
                      jmp_pin=Pin(11), sideset_base=Pin(12, Pin.OUT))
    MQ.active(1)

def mq_ready():
    # Y = 0xFFFFFFFF -> port $0F reads 0xFF -> bit 6 set -> Z80 sees "ready".
    MQ.exec("mov(y, invert(null))")

def mq_busy():
    MQ.exec("set(y, 0)")


def boot():
    """Bring up the hardware: ROM/BANK SMs (so the 2068 boots), the dual-port
    SM, Y=READY, boot-noise flush, and the first rolling status pre-load."""
    global rom_sm, bank_sm
    freq(270_000_000)

    print("=" * 64)
    print(HARNESS_VERSION)
    print("  WRITE_TARGET=%s  MOUNTED_TAP=%r  APPEND=%s" % (
        WRITE_TARGET, MOUNTED_TAP, APPEND))
    print("=" * 64)

    u6_en   = Pin(12, Pin.OUT, Pin.PULL_UP)
    wait    = Pin(14, Pin.OUT, Pin.PULL_DOWN)
    u10_ena = Pin(19, Pin.OUT, Pin.PULL_UP)
    u13_ena = Pin(20, Pin.OUT, Pin.PULL_UP)
    be      = Pin(21, Pin.OUT, Pin.PULL_UP)
    Pin(26, Pin.IN, Pin.PULL_DOWN)             # ROSCS (ROM_SM jmp_pin, input)
    u10_we  = Pin(27, Pin.OUT, Pin.PULL_UP)
    for _p in (u6_en, wait, u10_ena, u13_ena, be, u10_we):
        _p.value(1)

    # ROM_SM / BANK_SM must run before the Z80 fetches its first instruction or
    # the TS-2068 can't see the cartridge ROM and won't boot.
    rom_sm = StateMachine(4, set_ctrl, freq=150_000_000,
                          in_base=Pin(0, Pin.IN), jmp_pin=Pin(26),
                          set_base=Pin(21, Pin.OUT), out_base=Pin(19, Pin.OUT))
    rom_sm.active(1)
    bank_sm = StateMachine(5, sel_bank, freq=150_000_000,
                           jmp_pin=Pin(26), out_base=Pin(15, Pin.OUT))
    bank_sm.active(1)
    rom_sm.put(0x0A)        # both DCK and ROM mapped to flash
    bank_sm.put(0x01)       # DCK_SLOT=0 + ROM_SLOT=1 (TS-Pico ROM)
    print("[boot] ROM_SM/BANK_SM running (TS-2068 can boot)")

    make_mq()
    mq_ready()
    print("[boot] MQ (TS_IO_DUAL) active, Y=READY")

    flush_rx(300)
    MQ.put(0x01)          # rolling pre-load: status for the FIRST pre-header read
    mq_ready()
    print("[boot] flushed boot noise, pre-loaded 0x01, Y=READY")


# ===========================================================================
# SD pin-sharing handoff (only used when WRITE_TARGET == "sd").
# GPIO 2/3/4 are shared between the PIO data bus and SPI0 (SCK/MOSI/MISO);
# GPIO 28 is the SD /CS. Order matters: park SM -> SPI; and on the way back,
# clamp 2-4 LOW before the PIO reclaims them (the "Report D" fix).
# ===========================================================================

def sd_mount():
    global MQ
    MQ = StateMachine(0, NULL_SM, freq=15_000_000)   # release GPIO 2-9
    MQ.active(1)
    MQ.active(0)
    U3_CS = Pin(28, Pin.OUT, Pin.PULL_UP)
    D0 = Pin(2, Pin.IN)
    D1 = Pin(3, Pin.IN)
    D2 = Pin(4, Pin.IN)
    spi = SPI(0, sck=D0, mosi=D1, miso=D2)
    sd = SDCard(spi, U3_CS)
    os.mount(sd, "/sd")

def sd_restore():
    try:
        os.umount("/sd")
    except Exception:
        pass
    Pin(28, Pin.OUT, Pin.PULL_UP).value(1)
    for gp in (2, 3, 4):
        Pin(gp, Pin.OUT).value(0)        # clamp low before PIO reclaims them
    make_mq()                            # rebuild the dual-port SM


# ===========================================================================
# Helpers
# ===========================================================================

def xor_all(buf, start, end, seed=0):
    c = seed
    for i in range(start, end):
        c ^= buf[i]
    return c

def wait_tx_drained(timeout_ms=500):
    """Block until the Z80 has read our staged TX bytes (or timeout). Used
    before touching the SM for SD, so the Z80 gets its status first."""
    t0 = time.ticks_ms()
    while MQ.tx_fifo() > 0:
        if time.ticks_diff(time.ticks_ms(), t0) >= timeout_ms:
            return False
    return True

def flush_rx(quiet_ms=200):
    """Drain stray RX bytes until the FIFO stays empty for quiet_ms."""
    n = 0
    last = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), last) < quiet_ms:
        if MQ.rx_fifo() > 0:
            MQ.get()
            n += 1
            last = time.ticks_ms()
    return n


# ---------------------------------------------------------------------------
# The two-phase drain. PHASE 1 is this tight loop with NO per-byte time calls
# on the fast path; the stall timer is only consulted when the FIFO is empty.
# Returns the number of bytes actually received (== n on success).
# ---------------------------------------------------------------------------

def drain_phase(buf, n, stall_ms):
    rx = MQ.rx_fifo
    get = MQ.get
    got = 0
    waiting = False
    t_wait = 0
    while got < n:
        if rx():
            buf[got] = get()      # raw 9-bit; port-$0E writes -> bit8=0 -> 0..255
            got += 1
            waiting = False
        else:
            if not waiting:
                waiting = True
                t_wait = time.ticks_ms()
            elif time.ticks_diff(time.ticks_ms(), t_wait) >= stall_ms:
                return got
    return got


# ---------------------------------------------------------------------------
# TAP reconstruction + write. In-place buffer reuse (session-strip) matching
# the ROM's own framing, verified byte-exact on the host.
# ---------------------------------------------------------------------------

_current_tap = MOUNTED_TAP     # runtime mount state (updated on create)

def base_dir():
    return SD_DIR if WRITE_TARGET == "sd" else FLASH_DIR

def sanitize(raw):
    # raw is a bytes/bytearray slice (the 10 space-padded ZX filename bytes).
    # Build the string by hand rather than bytes.decode(errors=...), which
    # MicroPython does not reliably support.
    s = ""
    for c in raw:
        if 0x20 <= c < 0x7F:
            s += chr(c)
    s = s.rstrip()                    # ZX names are space-padded to 10
    out = ""
    for ch in s:
        if ch.isalpha() or ch.isdigit() or ch in "_-":
            out += ch
        elif ch == " ":
            out += "_"
        # else: drop
    return out or "noname"

def frame_header_inplace(hdr):
    """hdr is the 21-byte wire header. Rewrite in place to a framed .tap block:
    [len_lo][len_hi][flag][17 content][crc], length = 19."""
    l_hdr = len(hdr) - 2              # 19
    hdr[2] = hdr[0]                   # relocate flag (0x00) to content position
    hdr[0] = l_hdr & 0xFF
    hdr[1] = (l_hdr >> 8) & 0xFF
    return l_hdr

def frame_data_inplace(blk, long):
    """blk[0:long] is the wire data block (long == BLEN+4). Rewrite in place to
    [len_lo][len_hi][flag][BLEN data][crc], length = BLEN+2."""
    l_blk = long - 2                  # BLEN+2
    blk[2] = blk[0]                   # relocate flag (0xFF)
    blk[0] = l_blk & 0xFF
    blk[1] = (l_blk >> 8) & 0xFF
    return l_blk

def choose_target(save_name):
    """Return (path, mode). Implements create-new-if-unmounted /
    append-if-mounted using the config + runtime mount state."""
    global _current_tap
    if _current_tap and APPEND:
        return _current_tap, "ab"
    path = base_dir() + "/" + save_name + ".tap"
    _current_tap = path               # this file is now the mounted tap
    return path, "wb"

def ensure_dir(path):
    d = path.rsplit("/", 1)[0]
    if not d:
        return
    parts = d.split("/")
    cur = ""
    for p in parts:
        if not p:
            continue
        cur += "/" + p
        try:
            os.mkdir(cur)
        except OSError:
            pass                      # already exists

def write_tap(hdr, blk, long, save_name):
    """Reconstruct + write both framed blocks. Returns (path, mode, nbytes)."""
    frame_header_inplace(hdr)                 # 21 bytes -> framed 19-content
    frame_data_inplace(blk, long)             # long bytes -> framed (BLEN+2)-content
    path, mode = choose_target(save_name)
    hdr_bytes = bytes(hdr)                    # 21 bytes total on disk
    data_view = memoryview(blk)[0:long]       # long bytes total on disk

    if WRITE_TARGET == "sd":
        sd_mount()
        try:
            ensure_dir(path)
            with open(path, mode) as f:
                f.write(hdr_bytes)
                f.write(data_view)
            sz = os.stat(path)[6]
        finally:
            sd_restore()
    else:
        ensure_dir(path)
        with open(path, mode) as f:
            f.write(hdr_bytes)
            f.write(data_view)
        sz = os.stat(path)[6]
    return path, mode, sz


# ===========================================================================
# SAVE transaction handler. Called after the dispatcher has confirmed a SAVE
# pre-header. Returns a dict describing what happened (for logging).
# ===========================================================================

HDTYPES = {0: "BASIC", 1: "NUM-ARRAY", 2: "CHAR-ARRAY", 3: "CODE/SCREEN$"}

hdr_buf = bytearray(21)
DATA_MAX = 65540
blk_buf  = bytearray(DATA_MAX)

def handle_save(pre, T0):
    ev = {"ok": False}

    # --- PHASE 1: header block (21 bytes). Z80 has already cleared WF_NPH
    #     (we set READY after the pre-header). ---
    got = drain_phase(hdr_buf, 21, STALL_MS)
    ev["hdr_got"] = got
    ev["t_hdr"] = time.ticks_diff(time.ticks_us(), T0)
    if got != 21:
        ev["stall"] = "header block: %d/21 bytes" % got
        return ev

    # header CRC = XOR(hdr[0], hdr[3..19]) — session bytes [1],[2] excluded.
    hcrc = xor_all(hdr_buf, 3, 20, seed=hdr_buf[0])
    ev["hdr_crc_ok"] = (hcrc == hdr_buf[20])
    save_name = sanitize(hdr_buf[4:14])
    blen = hdr_buf[14] | (hdr_buf[15] << 8)
    long = blen + 4
    ev.update({"hdtype": hdr_buf[3], "name": save_name, "blen": blen,
               "addr": hdr_buf[16] | (hdr_buf[17] << 8)})

    if long > DATA_MAX:
        ev["stall"] = "BLEN %d exceeds buffer" % blen
        return ev

    # Stage the header-block status (Z80 reads it at ROM 0x1911) and re-assert
    # READY for the WF_NPH at 0x190B. The 21 writes left Y=BUSY.
    MQ.put(0x01)
    mq_ready()

    # --- PHASE 2: data block (BLEN+4 bytes), NO pre-header. ---
    got = drain_phase(blk_buf, long, STALL_MS)
    ev["data_got"] = got
    ev["t_data"] = time.ticks_diff(time.ticks_us(), T0)
    if got != long:
        ev["stall"] = "data block: %d/%d bytes" % (got, long)
        return ev

    if VERIFY_DATA_CRC:
        dcrc = xor_all(blk_buf, 3, long - 1, seed=blk_buf[0])
        ev["data_crc_ok"] = (dcrc == blk_buf[long - 1])

    # Final status (Z80 reads at 0x1911 after its data-block WF_NPH). For flash
    # we can also stage the next-command pre-load now (SM stays up). For SD we
    # must let the Z80 read the final status BEFORE we tear down the SM, then
    # re-load the pre-load after rebuilding it.
    if WRITE_TARGET == "sd":
        MQ.put(0x01)                 # final status only
        mq_ready()
        wait_tx_drained()            # ensure Z80 consumed it before SM teardown
    else:
        MQ.put(0x01)                 # final status
        MQ.put(0x01)                 # next-command pre-load
        mq_ready()

    # --- Reconstruct + write ---
    try:
        path, mode, sz = write_tap(hdr_buf, blk_buf, long, save_name)
        ev.update({"ok": True, "path": path, "mode": mode, "size": sz})
    except Exception as e:
        ev["write_error"] = repr(e)

    if WRITE_TARGET == "sd":
        # SM was rebuilt by sd_restore(); seed the next-command pre-load now.
        MQ.put(0x01)
        mq_ready()

    return ev


# ===========================================================================
# Main dispatch loop.
# ===========================================================================

pre_buf = bytearray(10)
stats = {"saves": 0, "stalls": 0, "other": 0}

def log_event(ev):
    if not VERBOSE:
        return
    if ev.get("ok"):
        print("[SAVE ok] name=%r type=%s(%d) BLEN=%d  -> %s (%s) %d bytes  "
              "hdrCRC=%s dataCRC=%s" % (
                  ev["name"], HDTYPES.get(ev["hdtype"], "?"), ev["hdtype"],
                  ev["blen"], ev["path"], ev["mode"], ev["size"],
                  ev.get("hdr_crc_ok"), ev.get("data_crc_ok", "n/a")))
    elif "stall" in ev:
        print("[SAVE STALL] %s   (hdr@%sus data@%sus)  hdr_got=%s data_got=%s"
              % (ev["stall"], ev.get("t_hdr"), ev.get("t_data"),
                 ev.get("hdr_got"), ev.get("data_got")))
        # dump the partial bytes we did receive — the evidence.
        if ev.get("hdr_got"):
            g = ev["hdr_got"]
            print("   header  partial (%d): %s" % (
                g, " ".join("%02X" % hdr_buf[i] for i in range(g))))
        if ev.get("data_got"):
            g = min(ev["data_got"], 48)
            print("   data    first %d: %s" % (
                g, " ".join("%02X" % blk_buf[i] for i in range(g))))
    elif "write_error" in ev:
        print("[SAVE write FAILED] name=%r  %s" % (
            ev.get("name"), ev["write_error"]))

def resync():
    """After a stall or an unknown command, get back to a clean idle: drain
    stray RX, restore the rolling pre-load, assert READY. (Cannot rescue a
    truly frozen Z80 — that needs a 2068 reset — but recovers from a Report J
    that dropped the Z80 back to BASIC.)"""
    flush_rx(150)
    # Drain any stale TX so the next rolling pre-load isn't orphaned. Every
    # status byte is 0x01, so this only guards the byte *count*, not the value.
    try:
        while MQ.tx_fifo() > 0:
            MQ.exec("pull(noblock)")     # TX FIFO -> OSR (discarded next cycle)
    except Exception:
        pass
    MQ.put(0x01)
    mq_ready()

def run():
    print("=" * 64)
    print('READY.  On the TS-2068: type a program, then  SAVE "name"')
    print("Ctrl-C in Thonny for a summary.")
    print("=" * 64)

    T0 = time.ticks_us()
    gc.collect()
    try:
        while True:
            if MQ.rx_fifo() == 0:
                continue

            # PHASE 0 — pre-header (10 bytes), tight. Matches the production
            # dispatcher's read exactly (no mask, no per-byte work).
            got = drain_phase(pre_buf, 10, STALL_MS)
            if got != 10:
                stats["stalls"] += 1
                print("[PRE STALL] pre-header %d/10: %s" % (
                    got, " ".join("%02X" % pre_buf[i] for i in range(got))))
                resync()
                continue
            # The pre-header status read (ROM 0x18C4) had no WF_NPH; its 0x01
            # came from the rolling pre-load. Re-assert READY for the WF_NPH
            # at 0x18D2.
            mq_ready()

            if pre_buf[0] == 0x00 and pre_buf[1] == 0x00:
                # SAVE.
                ev = handle_save(pre_buf, T0)
                log_event(ev)
                if ev.get("ok"):
                    stats["saves"] += 1
                    # flash + sd paths both already staged the next pre-load.
                else:
                    stats["stalls"] += 1 if "stall" in ev else 0
                    resync()
            else:
                stats["other"] += 1
                if VERBOSE:
                    print("[skip] non-SAVE pre-header: %s" % (
                        " ".join("%02X" % b for b in pre_buf)))
                # This harness only answers SAVE; let the Z80 error out + reset.
                resync()

    except KeyboardInterrupt:
        pass

    print("")
    print("=" * 64)
    print("SUMMARY  %s" % HARNESS_VERSION)
    print("  SAVEs completed : %d" % stats["saves"])
    print("  stalls          : %d" % stats["stalls"])
    print("  non-SAVE frames : %d" % stats["other"])
    print("  mounted tap now : %r" % _current_tap)
    print("=" * 64)
    MQ.active(0)
    print("MQ deactivated. ROM_SM/BANK_SM left running (2068 keeps its ROM).")


def main():
    boot()
    run()


if __name__ == "__main__":
    main()
