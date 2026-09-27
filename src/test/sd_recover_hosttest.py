"""Host-side test: SD card left mid-transfer by an interrupted session.

WHY (hardware, 2026-09-26)
The SD module runs off the Pico's 3V3, so a Pico reset, reflash or Ctrl-C
never power-cycles the card. Cut off inside a multi-block write (CMD25) --
a Ctrl-C or reset during an SD access, or writeblocks raising on "write
fail" without sending STOP_TRAN -- the card keeps waiting for data and
swallows CMD0 as data: every warm boot then reported "no SD card" until the
power was pulled. Reproduced on hardware by stopping a write 100 bytes
into a block; recovered by finishing the block, STOP_TRAN, busy wait, CMD0.

This runs the REAL SDCard driver against a byte-level fake card that can be
left in each stranded state, and checks:
  - init recovers a card left mid-block, waiting for a data token, or
    streaming a multi-block read, and says so in sd.recovered;
  - an idle card (cold boot) is left alone, sd.recovered is None;
  - a card stuck busy fails init in bounded time instead of hanging;
  - writeblocks sends STOP_TRAN when a block is refused, so the NEXT
    command works without a power cycle;
  - a write that never leaves busy raises instead of hanging;
  - readblocks sends CMD12 when a block read fails.

Run:  python3 src/test/sd_recover_hosttest.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sdcard_init_hosttest as base                              # noqa: E402

BLOCK = 512 + 2            # data + CRC after the start token


class Clock(base.Clock):
    def __init__(self):
        self.ms = 0.0


class Card:
    """Byte-level SPI-mode card. MOSI bytes go in via xfer(), MISO comes out."""

    def __init__(self, clock):
        self.clock = clock
        self.cs_low = False
        self.state = "idle"
        self.left = 0            # bytes still to receive in the current block
        self.busy = 0            # MISO-low bytes still to give
        self.after_busy = None
        self.stuck_busy = False
        self.fail_block = None   # refuse this committed block (0-based)
        self.never_ready = False # hold busy forever after the next block
        self.blocks = 0
        self.stop_trans = 0
        self.cmd12s = 0
        self.stream_pos = 0
        self.bad_stream = False  # a read that never produces a data token
        self.junk_blocks = 0     # half-sent blocks completed with filler

    def xfer(self, m):
        self.clock.ms += 0.02                     # a byte at 400 kHz
        if not self.cs_low:
            return 0xFF
        if self.stuck_busy:
            return 0x00
        if self.busy:
            self.busy -= 1
            if not self.busy and self.after_busy:
                self.state, self.after_busy = self.after_busy, None
            return 0x00
        st = self.state
        if st == "mid_block":
            self.left -= 1
            if self.left == 0:
                self.state = "resp"
            return 0xFF
        if st == "resp":
            k = self.blocks
            self.blocks += 1
            if self.never_ready:
                self.stuck_busy = True
                return 0x05
            self.busy, self.after_busy = 3, "wait_token"
            return 0x0D if k == self.fail_block else 0x05
        if st == "wait_token":
            if m == 0xFC:
                self.state, self.left = "mid_block", BLOCK
            elif m == 0xFD:
                self.stop_trans += 1
                self.state = "stop_skip"          # one byte, then busy
            return 0xFF
        if st == "stop_skip":
            self.busy, self.after_busy = 2, "idle"
            return 0xFF
        if st == "streaming":
            if m == 0x4C:                         # CMD12 seen on MOSI
                self.cmd12s += 1
                self.state = "idle"
                return 0xFF
            if self.bad_stream:
                return 0xFF
            p = self.stream_pos % (1 + BLOCK + 1)
            self.stream_pos += 1
            return 0xFE if p == 0 else (0x5A if p <= BLOCK else 0xFF)
        return 0xFF                               # idle


class FakeSPI:
    def __init__(self, card):
        self.card = card

    def init(self, *a, **k):
        pass

    def write(self, data):
        for b in bytes(data):
            self.card.xfer(b)

    def readinto(self, buf, w=0):
        for i in range(len(buf)):
            buf[i] = self.card.xfer(w)

    def read(self, n, w=0):
        b = bytearray(n)
        self.readinto(b, w)
        return b


class FakePin:
    OUT = 1

    def __init__(self, card):
        self.card = card

    def init(self, mode, value=1):
        self.card.cs_low = not value

    def __call__(self, v):
        self.card.cs_low = not v


def make(sd, card):
    """SDCard whose command layer is simulated (as in sdcard_init_hosttest)
    but whose data path and _recover() run byte-level against `card`."""
    class SD(sd.SDCard):
        def cmd(self, cmd, arg, final=0, release=True, skip1=False):
            card.clock.ms += 1
            if cmd == 12 and card.state == "streaming":
                card.cmd12s += 1                  # accepted mid-stream, as on a real card
                card.state = "idle"
                return 0
            if card.state != "idle" or card.stuck_busy:
                card.clock.ms += 25
                raise OSError(sd.ETIMEDOUT, "command:", cmd, "arg:", arg)
            card.cs_low = not release
            if cmd == 25:
                card.state = "wait_token"
                card.cs_low = True
                return 0
            if cmd == 18:
                card.state, card.stream_pos = "streaming", 0
                card.cs_low = True
                return 0
            if cmd == 12:
                card.cmd12s += 1
                return 0
            if cmd in (0, 8, 55):
                return 0x01
            if cmd == 41:
                return 0
            if cmd == 9:
                self._pending = bytes([0x40] + [0] * 15)
                return 0
            if cmd == 10:
                self._pending = bytes(16)
                return 0
            if cmd in (16, 59):
                return 0
            raise AssertionError("unexpected CMD%d" % cmd)

        def readinto(self, buf):
            if card.state == "streaming":
                return sd.SDCard.readinto(self, buf)
            buf[:] = self._pending

    return SD(FakeSPI(card), FakePin(card))


results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def main():
    sd = base.load_driver()
    clock = Clock()
    sd.time = clock

    def boot(setup):
        clock.ms = 0.0
        card = Card(clock)
        setup(card)
        try:
            return card, make(sd, card), None
        except OSError as e:
            return card, None, e

    print("init on a healthy card (cold boot)")
    card, s, e = boot(lambda c: None)
    check(s is not None and s.recovered is None and card.stop_trans == 0,
          "idle card: mounts, nothing to recover, no STOP_TRAN consumed (%r)" % (e,))

    print("init on a card left mid-transfer (warm boot)")
    def mid_block(c):
        c.state, c.left = "mid_block", BLOCK - 100     # 100 bytes of a block sent
    card, s, e = boot(mid_block)
    check(s is not None and card.state == "idle" and card.stop_trans == 1,
          "stopped 100 bytes into a block: block finished, STOP_TRAN, mounts (%r)" % (e,))
    check(s is not None and s.recovered and "mid-transfer" in s.recovered,
          "sd.recovered says so: %r" % (s.recovered if s else None))

    card, s, e = boot(lambda c: setattr(c, "state", "wait_token"))
    check(s is not None and card.stop_trans == 1 and s.recovered,
          "left inside CMD25 between blocks (the 'write fail' case): mounts (%r, %r)"
          % (e, s.recovered if s else None))

    card, s, e = boot(lambda c: setattr(c, "state", "streaming"))
    check(s is not None and card.cmd12s >= 1 and s.recovered,
          "left streaming a CMD18 read: CMD12 ends it, mounts (%r)" % (e,))

    card, s, e = boot(lambda c: setattr(c, "stuck_busy", True))
    check(e is not None and e.args[0] == sd.ENODEV and clock.ms < 4000,
          "card that never leaves busy: 'no SD card' in bounded time, no hang (%r at %d ms)"
          % (e, clock.ms))

    print("writeblocks / readblocks clean up")
    card, s, e = boot(lambda c: None)
    card.fail_block = 1
    try:
        s.writeblocks(100, bytearray(512 * 4))
        err = None
    except OSError as x:
        err = x
    check(err is not None and "write fail" in str(err) and card.stop_trans == 1 and card.state == "idle",
          "2nd block refused: EIO raised AND STOP_TRAN sent -- card back to idle (%r)" % (err,))
    ok = True
    try:
        s.cmd(16, 512)
    except OSError:
        ok = False
    check(ok, "the next command works without a power cycle")

    card, s, e = boot(lambda c: None)
    card.never_ready = True
    t = clock.ms
    try:
        s.writeblocks(100, bytearray(512))
        err = None
    except OSError as x:
        err = x
    check(err is not None and err.args[0] == sd.ETIMEDOUT and clock.ms - t < 3500,
          "write that never leaves busy: ETIMEDOUT within 3 x _BUSY_TIMEOUT_MS, no hang (%r, %d ms)" % (err, clock.ms - t))

    card, s, e = boot(lambda c: None)
    buf = bytearray(512 * 2)
    s.readblocks(0, buf)
    check(bytes(buf) == b"\x5a" * 1024 and card.cmd12s == 1,
          "normal 2-block read: data right, one CMD12")
    card, s, e = boot(lambda c: None)
    card.bad_stream = True
    try:
        s.readblocks(0, buf)
        err = None
    except OSError as x:
        err = x
    check(err is not None and card.cmd12s == 1 and card.state == "idle",
          "read whose data never arrives: timeout raised AND CMD12 sent (%r)" % (err,))

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
