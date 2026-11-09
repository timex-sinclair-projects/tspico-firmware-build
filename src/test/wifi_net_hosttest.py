#!/usr/bin/env python3
"""Host test: the v3 card's WiFi downloads (board_v3.wifi_get/wifi_join/
wifi_status, TS/net.py, and tspico's tpi:wifi and tpi:net).

A fake Zimodem answers behind machine.UART: it boots (the ROM's text, then
READY.) when the expander's EN bit goes high, and answers ATE, ATS45, ATI2,
ATW, AT&W and AT&G in stream mode. board_v3_hosttest's fakes stand in for
tsbus, the expander and the pins; the SD card is a temp folder.

    python3 src/test/wifi_net_hosttest.py
"""

import gzip
import io
import os
import shutil
import sys
import tempfile
import types
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..")))
sys.path.insert(0, HERE)

import board_v3_hosttest as BV

FAILS = []


def check(ok, what):
    print(("  PASS  " if ok else "  FAIL  ") + what)
    if not ok:
        FAILS.append(what)


ITEM = "https://archive.org/download/tspico-2068-tapes/"
ROOT_IDX = ("#tspico-dir\t1\t2026-11-07\tTAP\tTS-2068 programs\tpart 1 of 1\ttapes 3\n"
            "GAMES/\tD\tGames\t3\n")
GAMES1 = ("#tspico-dir\t1\t2026-11-07\tTAP/GAMES\tGames\tpart 1 of 2\ttapes 3\n"
          "CATS1/\tD\tCards\t1\n"
          "21.tap\tL\t21\t198x\t\t2087\t56278\n"
          "xadom.tap\tR\tXadom été\t1984\tSomeone\t3000\t7\n")
GAMES2 = ("#tspico-dir\t1\t2026-11-07\tTAP/GAMES\tGames\tpart 2 of 2\ttapes 3\n"
          "zz.tap\tC\tZed\t1985\t\t60000\t9\n")
FULL = ("#tspico-taps\t1\t2026-11-07\ttapes 3\tmax-tap 65536\n"
        "TAP/GAMES/21.tap\tL\t21\t198x\t\t2087\t56278\n"
        "TAP/GAMES/xadom.tap\tR\tXadom\t1984\tSomeone\t3000\t7\n"
        "TAP/ARCADE/ambush.tap\tL\tAmbush\t1983\tBews, Michael\t7994\t8\n")
T21 = bytes((i * 7) & 0xFF for i in range(2087))
TZZ = bytes((i * 11 + (i >> 8)) & 0xFF for i in range(60000))      # over 48K: needs the PSRAM
XADOM = bytes((i * 3 + 1) & 0xFF for i in range(3000))


class Zim:
    """The ESP32 running Zimodem, as far as board_v3 uses it."""

    def __init__(self):
        self.files = {}
        self.ip = "192.168.1.9"
        self.password = "secret"
        self.errors = 0          # AT&G answers ERROR this many times first
        self.cut = None          # AT&G sends only this many bytes of the file
        self.booted = False
        self.lines = []
        self.saved = 0
        self.boots = 0
        self.s45 = 0
        self.echo = True


Z = Zim()


class FakeUART:
    def __init__(self, n, baud, tx=None, rx=None, timeout=0, rxbuf=0):
        BV.CALLS.append(("UART", n, baud, tx.n, rx.n))
        self.q = bytearray()
        self.pending = b""
        self.live = True

    def _power(self):
        if not BV.OUT0[0] & 0x08:
            Z.booted = False
            return
        if not Z.booted:
            Z.booted, Z.boots, Z.echo, Z.s45 = True, Z.boots + 1, True, 0
            self.q += b"ESP-ROM:esp32c3-api1-20210207\r\n" + b"load:0x3fcd5810,len:0x438\r\n" * 10
            self.q += b"\r\nZimodem ESP32 Firmware v4.0.3.2\r\n"
            if Z.ip != "0.0.0.0":
                self.q += b"CONNECTED TO home (%s)\r\n" % Z.ip.encode()
            self.q += b"READY.\r\n"

    def read(self):
        self._power()
        d = bytes(self.q)
        del self.q[:]
        return d or None

    def readinto(self, mv):
        self._power()
        k = min(len(mv), len(self.q), 700)
        mv[:k] = self.q[:k]
        del self.q[:k]
        return k

    def write(self, b):
        assert self.live
        self._power()
        self.pending += bytes(b)
        while b"\r" in self.pending:
            ln, _, self.pending = self.pending.partition(b"\r")
            self.line(ln)

    def deinit(self):
        BV.CALLS.append(("UART-deinit",))
        self.live = False

    def line(self, ln):
        Z.lines.append(ln)
        if not Z.booted:
            return
        q = self.q
        if Z.echo:
            q += ln + b"\r\n"
        ok, err = b"OK\r\n", b"ERROR\r\n"
        if ln in (b"ATE0", b"ATE1"):
            Z.echo = ln == b"ATE1"
            q += ok
        elif ln.startswith(b"ATS45="):
            Z.s45 = int(ln[6:])
            q += ok
        elif ln == b"ATI2":
            q += Z.ip.encode() + b"\r\n" + ok
        elif ln.startswith(b'ATW"'):
            ssid, _, pw = ln[4:-1].decode().partition(",")
            if pw == Z.password:
                Z.ip = "192.168.1.9"
                q += ok
            else:
                Z.ip = "0.0.0.0"
                q += err
        elif ln == b"AT&W":
            Z.saved += 1
            q += ok
        elif ln.startswith(b'AT&G"'):
            url = ln[5:-1].decode()
            assert Z.s45 == 3, "stream mode first"
            if Z.errors:
                Z.errors -= 1
                q += err
            elif url in Z.files:
                d = Z.files[url]
                q += b"[ 0 %d ]\r\n" % len(d) + (d if Z.cut is None else d[:Z.cut])
            else:
                q += err
        else:
            q += err


def gz12(data):
    """gzip with a 4K window, as tap_folder.py's gz_index makes the full index."""
    c = zlib.compressobj(9, zlib.DEFLATED, 16 + 12)
    return c.compress(data) + c.flush()


def fake_deflate():
    m = types.ModuleType("deflate")
    m.RAW, m.ZLIB, m.GZIP, m.AUTO = 0, 1, 2, 3

    class DeflateIO:
        def __init__(self, stream, fmt, wbits):
            assert fmt == m.GZIP and wbits <= 12, "a 4K window: no 32K block on the card's heap"
            self.data = io.BytesIO(zlib.decompress(stream.read(), 16 + wbits))  # fails on a bigger window

        def readinto(self, b):
            d = self.data.read(len(b))
            b[:len(d)] = d
            return len(d)
    m.DeflateIO = DeflateIO
    return m


class SdOS:
    """os for tspico with /sd mapped onto a temp dir."""

    def __init__(self, root):
        self.root, self.cwd = root, "/sd/TAP"

    def real(self, p):
        assert p.startswith("/sd"), p
        return os.path.join(self.root, *[x for x in p[3:].split("/") if x])

    def stat(self, p):
        r = self.real(p)
        st = os.stat(r)
        return (0x4000 if os.path.isdir(r) else 0x8000, 0, 0, 0, 0, 0, st.st_size, 0, 0, 0)

    def mkdir(self, p):
        os.mkdir(self.real(p))

    def remove(self, p):
        os.remove(self.real(p))

    def chdir(self, p):
        self.cwd = p

    def getcwd(self):
        return self.cwd


def main():
    import sync_io_hosttest as S
    S.install_fakes()
    m = sys.modules["machine"]
    m.Pin, m.I2C, m.Timer, m.UART = BV.FakePin, BV.FakeI2C, BV.FakeTimer, FakeUART
    m.SPI = lambda bus, **k: "spi"
    sys.modules["tsbus"] = BV.fake_tsbus()
    sys.modules["deflate"] = fake_deflate()
    mp = types.ModuleType("micropython")
    mp.const = lambda x: x
    sys.modules["micropython"] = mp

    from TS import board
    import TS.board_v3 as b3
    from TS import net
    class TickClock(BV.Clock):                 # time moves on every look, as on the card:
        def ticks_ms(self):                    # the receive loop polls without sleeping
            self.ms += 1
            return self.ms
    clock = TickClock()
    b3.time = clock
    real_power = b3.modem_power

    def power(on):                             # EN low resets the ESP32
        if not on:
            Z.booted = False
        return real_power(on)
    b3.modem_power = power

    Z.files = {ITEM + "TAP/index.txt": ROOT_IDX.encode(),
               ITEM + "TAP/GAMES/index.txt": GAMES1.encode(),
               ITEM + "TAP/GAMES/index2.txt": GAMES2.encode(),
               ITEM + "TAP/GAMES/21.tap": T21,
               ITEM + "TAP/GAMES/xadom.tap": XADOM,
               ITEM + "TAP/GAMES/zz.tap": TZZ,
               ITEM + "tspico-taps.txt.gz": gz12(FULL.encode())}
    buf = bytearray(49160)

    print("wifi_get, the ESP32 off (cold)")
    board.modem_start("2050", 300, 10)
    BV.take()
    n = board.wifi_get(ITEM + "TAP/GAMES/21.tap", buf)
    got = BV.take()
    check(n == len(T21) and bytes(buf[:n]) == T21, "the file, byte-exact (%d bytes)" % n)
    check(Z.boots == 1 and b3._m_powered and b3._m_up, "the ESP32 powered and booted once, the line up")
    check(("modem", False) in got and got.index(("modem", False)) < got.index(("UART", 0, 115200, 44, 45)),
          "tsbus lets go of UART0 before it is opened")
    check(("modem_line", True) in got, "  the line raised once READY. came")
    check(got[-1] == ("modem", True) and ("UART-deinit",) in got,
          "UART0 handed back: deinit, then modem_start (%r)" % (got[-3:],))
    check(Z.lines[-2:] == [b"ATS45=0", b"ATE1"], "Zimodem left as a program expects it: ATS45=0, ATE1")

    print("wifi_get, the ESP32 on (warm)")
    del Z.lines[:]
    n = board.wifi_get(ITEM + "TAP/GAMES/xadom.tap", buf)
    check(bytes(buf[:n]) == XADOM and Z.boots == 1, "fetched without a boot")
    check(Z.lines[:3] == [b"ATE0", b"ATI2", b"ATS45=3"], "ATE0, ATI2, ATS45=3 first (%r)" % Z.lines[:3])

    print("wifi_get, an ERROR just after boot")
    Z.errors = 2
    n = board.wifi_get(ITEM + "TAP/GAMES/21.tap", buf)
    check(bytes(buf[:n]) == T21 and Z.errors == 0, "retried: the third AT&G gets it")
    Z.errors = 3
    try:
        board.wifi_get(ITEM + "TAP/GAMES/21.tap", buf)
        check(False, "three ERRORs: WifiError")
    except board.WifiError as e:
        check(str(e) == "Download failed", "three ERRORs: WifiError Download failed (%s)" % e)
    Z.errors = 0

    print("wifi_get's other failures")
    for setup, want in ((lambda: setattr(Z, "ip", "0.0.0.0"), "Not on WiFi"),
                        (lambda: setattr(Z, "cut", 1000), "Download cut short"),
                        (lambda: None, "Too big: 3000 bytes")):
        Z.ip, Z.cut = "192.168.1.9", None
        setup()
        BV.take()
        try:
            board.wifi_get(ITEM + "TAP/GAMES/xadom.tap", buf if want != "Too big: 3000 bytes" else bytearray(2000))
            check(False, want)
        except board.WifiError as e:
            got = BV.take()
            check(str(e) == want and got[-1] == ("modem", True), "%s, and UART0 handed back (%s)" % (want, e))
    Z.ip, Z.cut = "192.168.1.9", None
    BV.STATE[0] = 3
    BV.take()
    try:
        board.wifi_get(ITEM + "TAP/index.txt", buf)
        check(False, "a call in progress: refused")
    except board.WifiError as e:
        check(str(e) == "Modem in use" and BV.take() == [], "a call in progress: Modem in use, UART0 not touched")
    BV.STATE[0] = 0
    board.modem_start("off")
    check(not b3._m_powered and not BV.OUT0[0] & 0x08, "modem off: the ESP32 off")
    board.wifi_get(ITEM + "TAP/index.txt", buf)
    check(Z.boots == 2 and not BV.OUT0[0] & 0x08, "modem off: booted for the fetch, off again after")
    board.modem_start("2050")

    print("wifi_join and wifi_status")
    check(board.wifi_status() == "192.168.1.9", "wifi_status: the address")
    saved = Z.saved
    check(board.wifi_join("home", "secret") == "192.168.1.9" and Z.saved == saved + 1, "joined, then AT&W")
    for ssid, pw, want in (("home", "wrong", "Can't join home"), ('ho"me', "x", 'No " in a name or password')):
        try:
            board.wifi_join(ssid, pw)
            check(False, want)
        except board.WifiError as e:
            check(str(e) == want and Z.saved == saved + 1, "%s, nothing saved" % want)
    check(board.wifi_status() is None, "wifi_status after a failed join: None")
    Z.ip = "192.168.1.9"

    print("net.py")
    parts, rows = net.parse_part(GAMES1, "TAP/GAMES")
    check(parts == 2 and rows[0] == ("D", "TAP/GAMES/CATS1", "Cards", "1")
          and rows[1] == ("T", "TAP/GAMES/21.tap", "L", "21", "2087"), "parse_part: parts, a folder and a tape")
    check(net.row(1, rows[0]) == "CATS1/ Cards (1)" and net.row(2, rows[1]) == "21       L 21",
          "rows: a folder, a tape (%r, %r)" % (net.row(1, rows[0]), net.row(2, rows[1])))
    check(net.row(3, rows[2]) == "xadom    R Xadom ?t?", "non-ASCII shown as ? (%r)" % net.row(3, rows[2]))
    check(net.parent("TAP/GAMES/CATS1") == "TAP/GAMES" and net.parent("TAP") == "TAP", "parent")
    check(net.part_url("TAP/GAMES", 2) == ITEM + "TAP/GAMES/index2.txt", "part_url")
    found, k = net.find(io.StringIO(FULL), ["games", "XAD"])
    check(k == 1 and found[0][1] == "TAP/GAMES/xadom.tap", "find: any case, in the path or title")
    found, k = net.find(io.StringIO(FULL), ["a"], limit=1)
    check(k == 3 and len(found) == 1, "find: every word; limit")

    print("tpi:net and tpi:wifi")
    import TS.tspico as t
    d = tempfile.mkdtemp(prefix="wifi_net.")
    os.makedirs(os.path.join(d, "TAP"))
    sd = SdOS(d)
    t.os = sd
    t.open = lambda p, mode="r": open(sd.real(p), mode)
    for name in ("ACTIVATE_SD", "DEACTIVATE_SD", "ACTIVATE_MQ"):
        setattr(t, name, lambda *a, **k: None)
    sent = []
    t.SEND_MSG = lambda msg, msg1, st, force=False: sent.append(("MSG", msg, msg1, st))
    t.SEND_MSG2 = lambda msg, st, exp=True, colour=False: sent.append(("MSG2", msg, st))
    answer = [89]
    t.SEND_MSG_PROMPT_YN = lambda p, echo=True, lower=False: sent.append(("YN", p)) or answer[0]
    t.TLM = lambda *a, **k: None
    t.LOG = lambda *a: None
    t.DIR_FILES = lambda: True
    t.time = clock
    t.TSP = types.SimpleNamespace(cur_path="/sd/TAP", f_name="", sd_present=True, VERBOSE=False)
    net.LIST_PATH = os.path.join(d, "net.txt")
    board.BLOCK_BUF = b3.BLOCK_BUF = bytearray(49160)

    def pre(a=0, b=0):
        return bytes((0, 0, 0, a & 0xFF, a >> 8, b & 0xFF, b >> 8, 0, 0, 0))

    def run(text, a=0, b=0, handler=None):
        del sent[:]
        (handler or t.NET)(pre(a, b), "D.." + text)
        return list(sent)

    def text_of(s):
        return "".join(c for c in s if " " <= c <= "~" or c == "\r")

    got = run("tpi:net")
    check(len(got) == 1 and got[0][0] == "MSG2" and "Net: /TAP" in got[0][1] and "001" in got[0][1]
          and "GAMES/ Games (3)" in got[0][1], "tpi:net: the categories, numbered (%r)" % text_of(got[0][1]))
    got = run("tpi:net 1")
    check(got[0][0] == "MSG2" and "Net: /TAP/GAMES  1 of 2" in got[0][1] and "Part 1 of 2: tpi:net more" in got[0][1],
          "tpi:net 1: the folder, part 1 of 2 (%r)" % text_of(got[0][1]))
    got = run("tpi:net more")
    check("zz       C Zed" in got[0][1] and "tpi:net more" not in got[0][1], "tpi:net more: part 2, no more")
    got = run("tpi:net more")
    check(got == [("MSG", "NET: No more in this folder", "", t._4_Q_Parameter)], "and again: Report Q")
    got = run("tpi:net 1")
    check(got[0] == ("MSG", "NET: Too big for the card: zz.tap", "60000 bytes, 49160 at most", t._6_6_Num2Big),
          "no PSRAM: a tape over 48K refused before any fetch (%r)" % (got,))
    check(not os.path.exists(os.path.join(d, "TAP", "NET", "zz.tap")), "  nothing saved")
    run("tpi:net more")                                  # back to part 2
    board.PSRAM_HEAP = True
    got = run("tpi:net 1")
    board.PSRAM_HEAP = False
    check(got == [("MSG", "Saved /TAP/NET/zz.tap", 'MOVE TO "/net", LOAD "tpi:zz.tap", then LOAD "" CODE', t._1_OK)],
          "with the PSRAM: the 60000-byte tape fetched into a buffer of its own (%r)" % (got,))
    with open(os.path.join(d, "TAP", "NET", "zz.tap"), "rb") as f:
        check(f.read() == TZZ, "  /TAP/NET/zz.tap byte-exact")
    check(len(board.BLOCK_BUF) == 49160, "  BLOCK_BUF left as it was")
    run("tpi:net ..")
    got = run("tpi:net 1")
    check("1 of 2" in got[0][1], "tpi:net ..: back up, then GAMES again")
    got = run("tpi:net 2")
    saved = os.path.join(d, "TAP", "NET", "21.tap")
    check(got == [("MSG", "Saved /TAP/NET/21.tap", 'MOVE TO "/net", LOAD "tpi:21.tap", then LOAD ""', t._1_OK)],
          "tpi:net 2: a tape saved, how to load it (%r)" % (got,))
    with open(saved, "rb") as f:
        check(f.read() == T21, "  /TAP/NET/21.tap byte-exact, the folder made")
    with open(saved, "wb") as f:
        f.write(b"old")
    answer[0] = 78
    got = run("tpi:net 2")
    check(got == [("YN", 'Replace "21.tap" (y/N)?')], "there already: asked, and the prompt is the answer")
    with open(saved, "rb") as f:
        check(f.read() == b"old", "  N: kept")
    answer[0] = 89
    run("tpi:net 2")
    with open(saved, "rb") as f:
        check(f.read() == T21, "  Y: replaced")
    with open(saved, "wb") as f:
        f.write(b"old")
    got = run("tpi:net 2", 255, 0)
    with open(saved, "rb") as f:
        check(got[0][0] == "MSG" and got[0][3] == t._1_OK and f.read() == T21, "CODE 255,0: replaced, no prompt")
    got = run("tpi:net 9")
    check(got == [("MSG", "NET: Number out of range 1-3", "", t._6_6_Num2Big)], "a number past the list: Report 6")
    got = run("tpi:net 2", 1, 0)
    check(got[0][3] == t._8_A_Invalid_arg, "CODE 1,0: Report A")
    t.NET_FIND_MS, keep = -1, t.NET_FIND_MS              # the fetch took all the time there was
    got = run("tpi:net find xad")
    check(got == [("MSG", "NET: Archive index downloaded", 'Now SAVE "tpi:net find xad" again', t._1_OK)],
          "a first find out of time: the index fetched, find again (%r)" % (got,))
    t.NET_FIND_MS = keep
    os.remove(os.path.join(d, "tspico-taps.txt"))
    Z.files[ITEM + "tspico-taps.txt.gz"] = b"\x1f\x8b not gzip"                    # can't be unpacked
    got = run("tpi:net find xad")
    check(got == [("MSG", "NET: Can't unpack the index", "", t._3_F_Invalid_file)]
          and not os.path.exists(os.path.join(d, "tspico-taps.txt"))
          and not os.path.exists(os.path.join(d, "tspico-taps.txt.gz")),
          "an index that won't unpack: Report F, nothing left on the card (%r)" % (got,))
    Z.files[ITEM + "tspico-taps.txt.gz"] = gz12(FULL.encode())
    got = run("tpi:net find xad")
    check(got[0][0] == "MSG2" and "Net: find xad (1)" in got[0][1] and "xadom    R Xadom" in got[0][1],
          "tpi:net find: the full index fetched, one match (%r)" % text_of(got[0][1]))
    check(os.path.exists(os.path.join(d, "tspico-taps.txt")) and not os.path.exists(os.path.join(d, "tspico-taps.txt.gz")),
          "  the index gunzipped onto the card, the .gz gone")
    del Z.files[ITEM + "tspico-taps.txt.gz"]                 # found on the card: not fetched again
    got = run("tpi:net find zzz")
    check(got == [("MSG", "NET: Nothing found", "", t._1_OK)], "nothing found, from the card's copy")
    got = run("tpi:net 1")
    check(got == [("MSG", "NET: Number out of range 1-0", "", t._6_6_Num2Big)], "  and its empty list")
    got = run("tpi:net find a")
    got = run("tpi:net 1")
    check(got[0][1] == "Saved /TAP/NET/21.tap" or got[0][0] == "YN", "a find's match downloads (%r)" % (got,))
    got = run("tpi:net update")
    check(got == [("MSG", "Download failed", "", t._10_J_Invalid_IO)], "update, the file gone: Report J, shown")
    Z.ip = "0.0.0.0"
    got = run("tpi:net")
    check(got == [("MSG", "Not on WiFi", 'SAVE "tpi:wifi name,password"', t._10_J_Invalid_IO)],
          "not on WiFi: Report J and how to join (%r)" % (got,))
    got = run("tpi:wifi", handler=t.WIFI)
    check(got == [("MSG", "WiFi: not on a network", 'SAVE "tpi:wifi name,password"', t._1_OK)], "tpi:wifi: not on")
    got = run("tpi:wifi home,secret", handler=t.WIFI)
    check(got == [("MSG", "WiFi: joined home", "Address 192.168.1.9", t._1_OK)], "tpi:wifi home,secret: joined")
    got = run("tpi:wifi", handler=t.WIFI)
    check(got == [("MSG", "WiFi: on, address 192.168.1.9", "", t._1_OK)], "tpi:wifi: the address")
    got = run("tpi:wifi home,nope", handler=t.WIFI)
    check(got == [("MSG", "Can't join home", "", t._10_J_Invalid_IO)] and "nope" not in repr(got),
          "a wrong password: Report J, the password not shown")
    got = run("tpi:wifi home", handler=t.WIFI)
    check(got[0][3] == t._8_A_Invalid_arg, "no comma: Report A")
    check("TPI:WIFI" in t.SD_FREE and "TPI:NET" not in t.SD_FREE, "tpi:wifi needs no card; tpi:net does")
    t.board.HAS_MODEM = False
    check(run("tpi:net") == [("MSG", "No WiFi on this board", "", t._3_F_Invalid_file)]
          and run("tpi:wifi", handler=t.WIFI) == [("MSG", "No WiFi on this board", "", t._3_F_Invalid_file)],
          "v2: No WiFi on this board, Report F")
    t.board.HAS_MODEM = True
    shutil.rmtree(d)

    print()
    if FAILS:
        print("%d FAILED" % len(FAILS))
        return 1
    print("ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
