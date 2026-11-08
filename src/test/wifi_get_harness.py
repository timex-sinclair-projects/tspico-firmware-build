# Harness: fetch a file over the v3 card's WiFi with the firmware's own
# state, the way tpi:net will (docs/v3-wifi-archive-proposal.md).
#
# Run on a v3 card after `pico-serial.py break` (the firmware stopped at the
# REPL, tsbus and core 1 still serving the 2068, the heap as the firmware
# left it):
#
#   python3 tools/pico-serial.py run --file src/test/wifi_get_harness.py --timeout 120
#
# What it tests, the part nothing has shown yet:
#   1. core 0 borrows UART0 from tsbus (tsbus.modem(False), machine.UART),
#      fetches with Zimodem's AT&G in stream mode (ATS45=3) into
#      board.BLOCK_BUF (48K, made at boot), and
#   2. hands it back (board.modem_start), with core 1's 8251 working after.
# Each file is checked against the item's MD5. Then softreset.

import time, gc, hashlib, binascii, tsbus
from machine import UART, Pin
from TS import board_v3 as board   # the modem state (_m_*) lives here; TS.board copies names

ITEM = "https://archive.org/download/tspico-2068-tapes/"
WANT = [("TAP/index.txt", 339, "95cc098464bf116d0762d0e10582801e"),
        ("TAP/GAMES/index.txt", 8117, "8a1941e739d5d51e5f79807b09b2489c"),
        ("TAP/ARCADE/ambush.tap", 7994, "d34164897ba9f89d7ef2b10e444fd131"),
        ("tspico-taps.txt.gz", 45999, "bf09e8f5b835106ed61457ff9b5f85f4")]


class WifiError(Exception):
    pass


def _wait(u, want, ms, buf):
    """Read into buf until `want` is in it or ms pass; the bytes read (the
    last len(buf) of them: the ESP32's ROM prints ~280 bytes before
    Zimodem's READY.)."""
    n, t0 = 0, time.ticks_ms()
    mv = memoryview(buf)
    half = len(buf) // 2
    while time.ticks_diff(time.ticks_ms(), t0) < ms:
        if n == len(buf):                   # keep the newer half
            mv[:half] = mv[half:]
            n = half
        k = u.readinto(mv[n:])
        if k:
            n += k
            if want in bytes(mv[:n]) or b"ERROR" in bytes(mv[:n]):
                break
        else:
            time.sleep_ms(5)
    return bytes(mv[:n])


def _cmd(u, line, ms=1500):
    u.read()
    u.write(line + b"\r")
    return _wait(u, b"OK\r\n", ms, bytearray(128))


def wifi_get(url, buf, boot_ms=8000, join_ms=10000, first_ms=15000, idle_ms=4000):
    """Fetch url into buf; its length. Raises WifiError."""
    if board._m_mode == "2050" and tsbus.stats()["m_state"]:
        raise WifiError("Modem in use")
    tsbus.modem(False)                     # core 1 leaves UART0 alone
    u = UART(0, 115200, tx=Pin(44), rx=Pin(45), timeout=0, rxbuf=4096)
    small = bytearray(256)
    try:
        if not board._m_powered:
            board.esp_boot(False)
            r = _wait(u, b"READY.", boot_ms, small)
            if b"READY." not in r:
                raise WifiError("No answer from the ESP32")
        t0 = time.ticks_ms()
        _cmd(u, b"ATE0")
        while True:                         # joined: ATI2 is its address
            r = _cmd(u, b"ATI2")
            if b"." in r and b"0.0.0.0" not in r:
                break
            if time.ticks_diff(time.ticks_ms(), t0) > join_ms:
                raise WifiError("Not on WiFi")
            time.sleep_ms(500)
        if b"OK" not in _cmd(u, b"ATS45=3"):
            raise WifiError("No answer from the ESP32")
        for tries in range(3):             # just after boot the first AT&G
            u.read()                       # can answer ERROR (2026-11-08)
            u.write(b'AT&G"' + url.encode() + b'"\r')
            h = _wait(u, b"]\r\n", first_ms, small)
            i = h.find(b"]\r\n")
            if i >= 0 or b"ERROR" not in h:
                break
            time.sleep_ms(1000)
        if i < 0:
            raise WifiError("Download failed" if b"ERROR" in h else "No reply")
        if tries:
            print("  (AT&G tries: %d)" % (tries + 1))
        f = h[h.index(b"[") + 1:i].split()
        size = int(f[1])
        if size > len(buf):
            raise WifiError("Too big: %d bytes" % size)
        mv = memoryview(buf)
        n = len(h) - i - 3
        mv[:n] = h[i + 3:]
        last = time.ticks_ms()
        while n < size and time.ticks_diff(time.ticks_ms(), last) < idle_ms:
            k = u.readinto(mv[n:size])
            if k:
                n += k
                last = time.ticks_ms()
        if n < size:
            raise WifiError("Download cut short: %d of %d" % (n, size))
        return size
    finally:
        time.sleep_ms(200)
        _cmd(u, b"ATS45=0")
        u.deinit()
        board._m_last = time.ticks_ms()
        board.modem_start(board._m_mode)   # UART0 back to tsbus


gc.collect()
print("free", gc.mem_free(), "mode", board._m_mode, "powered", board._m_powered, "up", board._m_up)
buf = board.BLOCK_BUF
ok = 0
for name, size, md5 in WANT:
    t0 = time.ticks_ms()
    try:
        n = wifi_get(ITEM + name, buf)
    except WifiError as e:
        print("FAIL", name, e)
        continue
    h = binascii.hexlify(hashlib.md5(memoryview(buf)[:n]).digest()).decode()
    good = n == size and h == md5
    ok += good
    print("OK  " if good else "FAIL", name, n, "bytes in", time.ticks_diff(time.ticks_ms(), t0), "ms, md5", h == md5)
print("passed", ok, "of", len(WANT))
s = tsbus.stats()
print("after: modem_poll", tsbus.modem_poll(), "m_state", s["m_state"], "mode", board._m_mode, "powered", board._m_powered)
