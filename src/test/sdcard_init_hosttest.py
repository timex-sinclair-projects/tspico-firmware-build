"""Host-side test for TS/sdcard.py card start-up -- CPython, no Pico.

A cold SD card at boot took longer to leave idle (ACMD41) than the driver's
old ~250 ms budget (50 x 5 ms), so the boot-time mount failed with
(110, 'card type', 'v2') while the same card mounted fine at the REPL a few
seconds later. The driver now waits up to _INIT_TIMEOUT_MS (1500 ms,
covering the SD spec's 1 s) and retries CMD16 a few times.

This runs the REAL SDCard constructor and init_card with the command layer
simulated: a v2 SDHC card that stays idle for a set time after the first
ACMD41, then answers. Time is a virtual clock that each command and the
driver's sleep_ms() advance.

Run:  python3 src/test/sdcard_init_hosttest.py
"""

import importlib
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)


class Clock:
    def __init__(self):
        self.ms = 0

    def ticks_ms(self):
        return self.ms

    @staticmethod
    def ticks_diff(a, b):
        return a - b

    def sleep_ms(self, n):
        self.ms += n


def load_driver():
    mp = types.ModuleType("micropython")
    mp.const = lambda x: x
    sys.modules["micropython"] = mp
    ts = types.ModuleType("TS")
    ts.__path__ = [os.path.join(SRC, "TS")]
    sys.modules["TS"] = ts
    return importlib.import_module("TS.sdcard")


class FakeSPI:
    """An idle card at byte level: MISO is always 0xFF. (The command layer
    is simulated by overriding SDCard.cmd; _recover() talks raw SPI.)"""
    def init(self, *a, **k):
        pass

    def write(self, *a):
        pass

    def readinto(self, buf, w=0):
        for i in range(len(buf)):
            buf[i] = 0xFF

    def read(self, n, w=0):
        return bytes([0xFF]) * n


class FakePin:
    OUT = 1

    def init(self, *a, **k):
        pass

    def __call__(self, *a):
        pass


def make_card(sd, clock, ready_after_ms, cmd16_refusals=0, cmd0_silent=0, acmd_silent=0):
    """cmd0_silent / acmd_silent: how many CMD0 / CMD55 the card ignores
    first -- the driver's cmd() raises ETIMEDOUT for those, as it does on
    real hardware when no response byte ever arrives."""
    class Card(sd.SDCard):
        def __init__(self):
            self.acmd41_started = None
            self.acmd41_calls = 0
            self.cmd16_left = cmd16_refusals
            self.cmd0_left = cmd0_silent
            self.acmd_left = acmd_silent
            self.cmd0_finals = []
            self.pending = bytes(16)
            sd.SDCard.__init__(self, FakeSPI(), FakePin())

        def cmd(self, cmd, arg, final=0, release=True, skip1=False):
            clock.ms += 1                               # every command takes time
            if cmd == 0:
                self.cmd0_finals.append(final)
                if self.cmd0_left:
                    self.cmd0_left -= 1
                    clock.ms += 25                      # cmd()'s response wait
                    raise OSError(sd.ETIMEDOUT, "command:", 0, "arg:", 0)
                return 0x01
            if cmd == 55 and self.acmd_left:
                self.acmd_left -= 1
                clock.ms += 25
                raise OSError(sd.ETIMEDOUT, "command:", 55, "arg:", 0)
            if cmd in (8, 55):
                return 0x01                             # idle; CMD8 idle = v2 card
            if cmd == 41:
                self.acmd41_calls += 1
                if self.acmd41_started is None:
                    self.acmd41_started = clock.ms
                return 0 if clock.ms - self.acmd41_started >= ready_after_ms else 0x01
            if cmd == 9:
                self.pending = bytes([0x40] + [0] * 15)  # CSD version 2.0
                return 0
            if cmd == 10:
                self.pending = bytes(16)                 # CID
                return 0
            if cmd == 16:
                if self.cmd16_left:
                    self.cmd16_left -= 1
                    return 0x04                          # refused
                return 0
            if cmd == 59:
                return 0
            raise AssertionError("unexpected CMD%d" % cmd)

        def readinto(self, buf):
            buf[:] = self.pending

    return Card


results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def attempt(sd, clock, **kw):
    clock.ms = 0
    try:
        return make_card(sd, clock, **kw)(), None
    except OSError as e:
        return None, e


def main():
    sd = load_driver()
    clock = Clock()
    sd.time = clock

    print("ACMD41 start-up budget")
    check(sd._INIT_TIMEOUT_MS >= 1000,
          "_INIT_TIMEOUT_MS = %d ms, at least the SD spec's 1 s" % sd._INIT_TIMEOUT_MS)
    c, e = attempt(sd, clock, ready_after_ms=5)
    check(c is not None and c.acmd41_calls <= 3,
          "fast card: mounts within the first ACMD41 tries (%s)" % (c.acmd41_calls if c else repr(e)))
    c, e = attempt(sd, clock, ready_after_ms=900)
    check(c is not None,
          "cold card that leaves idle after 900 ms: mounts -- the old ~250 ms budget failed it%s"
          % ("" if c else ": %r" % (e,)))
    c, e = attempt(sd, clock, ready_after_ms=10_000)
    check(e is not None and e.args[0] == sd.ETIMEDOUT and 1500 <= clock.ms <= 1600,
          "card that never leaves idle: ETIMEDOUT after ~1.5 s, no hang (%r at %d ms)" % (e, clock.ms))

    print("CMD0 (reset into SPI idle)")
    c, e = attempt(sd, clock, ready_after_ms=5, cmd0_silent=3)
    check(c is not None, "card ignores the first 3 CMD0s (soft reboot / just powered): mounts%s"
          % ("" if c else ": %r -- the old driver gave up on the first" % (e,)))
    c, e = attempt(sd, clock, ready_after_ms=5, cmd0_silent=10_000)
    check(e is not None and e.args[0] == sd.ENODEV and 500 <= clock.ms <= 600,
          "card that never answers CMD0: 'no SD card' after ~0.5 s (%r at %d ms)" % (e, clock.ms))
    c, e = attempt(sd, clock, ready_after_ms=5)
    check(c is not None and set(c.cmd0_finals) == {0},
          "CMD0 no longer clocks out 149 stray bytes (final=%s)" % (sorted(set(c.cmd0_finals)) if c else "?"))
    c, e = attempt(sd, clock, ready_after_ms=300, acmd_silent=4)
    check(c is not None, "no answer to the first ACMD41s counts as 'not ready yet': mounts%s"
          % ("" if c else ": %r" % (e,)))

    print("CMD16")
    c, e = attempt(sd, clock, ready_after_ms=5, cmd16_refusals=1)
    check(c is not None, "refuses the first CMD16, accepts the next: mounts%s"
          % ("" if c else ": %r" % (e,)))
    c, e = attempt(sd, clock, ready_after_ms=5, cmd16_refusals=9)
    check(e is not None and "512 block size" in str(e),
          "refuses CMD16 every time: still reported (%r)" % (e,))

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
