"""Host-side test for DRAIN_STDIN in TS/tspico_io.py -- CPython, no Pico.

The bug (hardware, 2026-09-28): send a TS-Pico running 2.0 600 bytes
of ordinary text, then Ctrl-C, and nothing comes back -- the port opens,
but no number of Ctrl-Cs gets a ">>> ", and only a reset recovers it.
(Found while chasing a similar-looking USB silence in the PR #74
web-updater tests; that one turned out NOT to be this -- see
docs/DEVELOPER_GUIDE.md.)

Why, in MicroPython v1.20's rp2 port (ports/rp2/mphalport.c): Ctrl-C is
spotted in tud_cdc_rx_cb, while it moves bytes from TinyUSB's 256-byte
CDC FIFO into the 512-byte stdin ring buffer (511 usable). When the ring
is full it stops and leaves the rest in TinyUSB, so a Ctrl-C queued behind
511 bytes of other text is never looked at. The firmware never reads
stdin, so the ring never empties by itself.

CdcModel below is that path, byte for byte in the parts that matter. The
test shows the wedge without the fix, then that DRAIN_STDIN at the idle
heartbeat lets the same Ctrl-C through, and pins the helper's other
promises: it stops at the first Z80 byte, it is bounded, and an empty
stdin costs nothing. It also checks both idle heartbeats in BOTH
TS/tspico.py and dev_tspico.py call it.

This models the C code; it does not run it. The hardware check is the
600-byte repro above, with the firmware from this branch.

Run:  python3 src/test/stdin_drain_hosttest.py
"""

import builtins
import os
import re
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)

CTRL_C = 0x03
TUSB_FIFO = 256         # CFG_TUD_CDC_RX_BUFSIZE, shared/tinyusb/tusb_config.h
RING = 512 - 1          # MICROPY_HW_STDIN_BUFFER_LEN; a ringbuf holds len-1


class CdcModel:
    """Host -> TinyUSB FIFO -> stdin ring, as MicroPython v1.20 rp2 does it."""

    def __init__(self):
        self.host = []          # bytes the host has written, not yet accepted
        self.fifo = []          # TinyUSB's CDC RX FIFO
        self.ring = []          # MicroPython's stdin_ringbuf
        self.pending = False    # cdc_itf_pending
        self.interrupt = False  # mp_sched_keyboard_interrupt() was called
        self.reads = 0

    def host_write(self, data):
        self.host.extend(data)
        self.usb_task()

    def usb_task(self):
        """tud_task: accept what fits (the rest is NAKed), then rx_cb."""
        while self.host and len(self.fifo) < TUSB_FIFO:
            self.fifo.append(self.host.pop(0))
        if self.fifo:
            self.rx_cb()

    def rx_cb(self):
        """tud_cdc_rx_cb: the only place Ctrl-C is noticed."""
        self.pending = False
        while self.fifo:
            if len(self.ring) >= RING:
                self.pending = True     # "needs attention later on for polling"
                return
            c = self.fifo.pop(0)
            if c == CTRL_C:
                self.interrupt = True
            else:
                self.ring.append(c)

    def poll_cdc_interfaces(self):
        if self.pending:
            self.rx_cb()

    def check_interrupt(self):
        """The VM raises a scheduled KeyboardInterrupt at its next check."""
        if self.interrupt:
            self.interrupt = False
            raise KeyboardInterrupt


class FakePoll:
    """select.poll on sys.stdin: mp_hal_stdio_poll, then the ipoll iterator."""

    def __init__(self, cdc):
        self.cdc = cdc

    def register(self, obj, flags):
        pass

    def ipoll(self, timeout=-1):
        self.cdc.usb_task()
        self.cdc.poll_cdc_interfaces()
        self.cdc.check_interrupt()
        return iter([(None, 1)] if self.cdc.ring else [])


class FakeStdinBuffer:
    def __init__(self, cdc):
        self.cdc = cdc

    def readinto(self, buf):
        """mp_hal_stdin_rx_chr for one byte (poll said there is one)."""
        buf[0] = self.cdc.ring.pop(0)
        self.cdc.reads += 1
        return 1


class FakeMQ:
    def __init__(self, rx=0):
        self.rx = rx

    def rx_fifo(self):
        return self.rx


def install_fakes():
    builtins.const = lambda x: x
    machine = types.ModuleType("machine")
    machine.Pin = lambda *a, **k: None
    machine.SPI = lambda *a, **k: None
    machine.freq = lambda *a, **k: None
    sys.modules["machine"] = machine
    rp2 = types.ModuleType("rp2")
    rp2.StateMachine = lambda *a, **k: None
    rp2.asm_pio = lambda *a, **k: (lambda f: f)
    rp2.PIO = types.SimpleNamespace(OUT_HIGH=0, OUT_LOW=1, SHIFT_RIGHT=2,
                                    SHIFT_LEFT=3, IN_HIGH=4)
    sys.modules["rp2"] = rp2
    utime = types.ModuleType("utime")
    utime.sleep = utime.sleep_ms = lambda *a: None
    sys.modules["utime"] = utime
    ts = types.ModuleType("TS")
    ts.__path__ = [os.path.join(SRC, "TS")]
    sys.modules["TS"] = ts
    sdc = types.ModuleType("TS.sdcard")
    sdc.SDCard = lambda *a, **k: None
    sys.modules["TS.sdcard"] = sdc


results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def wire(io, cdc):
    """Point the helper at the model, as its first call would at sys.stdin."""
    io.select = types.SimpleNamespace(poll=lambda: FakePoll(cdc), POLLIN=1)
    io.sys = types.SimpleNamespace(
        stdin=types.SimpleNamespace(buffer=FakeStdinBuffer(cdc)))
    io._stdin_ipoll = None
    io._stdin_readinto = None


def heartbeats(io, cdc, n, drain):
    """n passes of the idle heartbeat. Returns the pass Ctrl-C landed on."""
    for i in range(1, n + 1):
        try:
            cdc.usb_task()              # tud_task runs from the VM hook
            cdc.check_interrupt()
            if drain:
                io.DRAIN_STDIN(FakeMQ())
        except KeyboardInterrupt:
            return i
    return None


def junk(n):
    return (b"print('hello from host')\r\n" * (n // 26 + 1))[:n]


def main():
    install_fakes()
    sys.path.insert(0, SRC)
    import TS.tspico_io as io

    print("the wedge (no drain)")
    cdc = CdcModel()
    wire(io, cdc)
    cdc.host_write(junk(600))
    cdc.host_write(b"\x03" * 5 + b"\r\n")
    check(len(cdc.ring) == RING,
          "600 bytes of text fill the stdin ring (%d of %d)" % (len(cdc.ring), RING))
    check(heartbeats(io, cdc, 50, drain=False) is None,
          "the Ctrl-Cs behind them are never seen -- the reported symptom")

    cdc = CdcModel()
    cdc.host_write(junk(400) + b"\x03")
    check(heartbeats(io, cdc, 1, drain=False) == 1,
          "below the limit Ctrl-C still works without the drain (why it hid)")

    print("DRAIN_STDIN")
    cdc = CdcModel()
    wire(io, cdc)
    cdc.host_write(junk(600))
    cdc.host_write(b"\x03" * 5 + b"\r\n")
    landed = heartbeats(io, cdc, 50, drain=True)
    check(landed is not None and landed <= 2,
          "the same wedge: Ctrl-C lands at heartbeat %s" % landed)

    cdc = CdcModel()
    wire(io, cdc)
    cdc.host_write(junk(600))
    heartbeats(io, cdc, 3, drain=True)
    check(not cdc.ring and not cdc.fifo and not cdc.host,
          "text with no Ctrl-C is all dropped, leaving room for the next one")
    cdc.host_write(b"\x03")
    check(heartbeats(io, cdc, 1, drain=True) == 1,
          "... and a later Ctrl-C is seen straight away")

    cdc = CdcModel()
    wire(io, cdc)
    cdc.host_write(junk(100))
    check(io.DRAIN_STDIN(FakeMQ(rx=1)) == 0 and cdc.reads == 0 and len(cdc.ring) == 100,
          "a byte from the Z80 waiting: reads nothing, the pre-header comes first")

    cdc = CdcModel()
    wire(io, cdc)
    cdc.host_write(junk(300))
    check(io.DRAIN_STDIN(FakeMQ(), limit=64) == 64 and len(cdc.ring) == 236,
          "bounded: stops at the limit (64 of 300)")

    cdc = CdcModel()
    wire(io, cdc)
    check(io.DRAIN_STDIN(FakeMQ()) == 0 and cdc.reads == 0,
          "nothing waiting: returns 0 at once")

    print("the idle heartbeats call it")
    for name in ("TS/tspico.py", "dev_tspico.py"):
        src = open(os.path.join(SRC, name)).read()
        check(re.search(r"^\s+DRAIN_STDIN,", src, re.M) is not None,
              "%s: imports DRAIN_STDIN from TS.tspico_io" % name)
        for fn in ("TS2068_IO", "ZX48_IO"):
            start = src.index("\ndef %s(" % fn)
            end = src.find("\ndef ", start + 1)
            body = src[start:end if end > 0 else len(src)]
            beat = body[body.rindex("< 2_100_000:"):]
            beat = beat[:beat.index("ts = time.ticks_us()")]
            check("DRAIN_STDIN(MQ)" in beat,
                  "%s: %s drains stdin at its idle heartbeat" % (name, fn))

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
