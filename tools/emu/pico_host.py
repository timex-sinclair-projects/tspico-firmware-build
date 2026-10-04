#!/usr/bin/env python3
"""Run the REAL TS-Pico firmware on this computer, as the device behind a
TS-2068 emulated by ZEsarUX (issue #35).

ZEsarUX, patched (the `tspico-device` branch: 16K EXROM, and a hook on ports
0Eh/0Fh), sends every Z80 access to those ports over a Unix socket as a
2-byte frame [op, value] and waits for a 1-byte reply:

    op 0  OUT (0Eh),A    data to the Pico          reply ignored
    op 1  IN  A,(0Eh)    data from the Pico        reply = the byte
    op 2  IN  A,(0Fh)    the status byte           reply = the byte
    op 3  OUT (0Fh),A    SYNC / BREAK              reply ignored

This process answers those frames with a model of the bus state machine
(BusModel), and runs the firmware's own main loop, `TS.tspico.TS2068_IO()`,
unmodified, on a thread, under stand-ins for the MicroPython modules it uses
(rp2, machine, utime, micropython, the SD driver). The Pico's flash and the
SD card are folders under --root: `/config.ini`, `/assets`, `/TMP`, ... and
`/sd/...`.

What the model keeps from the hardware: the 9-bit RX words (bit 8 = a write
to 0Fh), the status byte driven by the firmware's `exec("mov(y, ...)")`, BUSY
after every Z80 write (the PIO's auto-busy), a 4-word TX FIFO as the firmware
sees it, and an empty FIFO reading as 00h. What it doesn't: timing. Every
port access is a socket round trip, so nothing here can show a FIFO running
dry or overflowing because the Pico was late -- that needs the hardware.

Usage (normally via tools/emu/session.py):
    python3 tools/emu/pico_host.py --root /tmp/tspico-root [--sd "SD card"]
"""

import argparse
import builtins
import os as _os
import queue
import shutil
import socket
import sys
import threading
import time as _time
import types

REPO = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
SRC = _os.path.join(REPO, "src")
SOCK = _os.environ.get("TSPICO_BRIDGE_SOCK", "/tmp/tspico_bridge.sock")

OP_OUT_DATA, OP_IN_DATA, OP_IN_STATUS, OP_OUT_STATUS = 0, 1, 2, 3
PORT_0F = 0x100


# ---- the bus state machine (PIO0 SM0, TS_IO_DUAL), as a model --------------

class BusModel:
    """What the firmware sees as `MQ` (an rp2.StateMachine running
    TS_IO_DUAL), driven from the other side by the emulator's port frames."""

    def __init__(self):
        self.rx = queue.Queue()         # words the Z80 wrote: v, or 0x100|v for port 0Fh
        self.tx = queue.Queue()         # bytes for the Z80's IN (0Eh)
        self.y = 0                      # the status byte the Z80 reads on 0Fh
        self.underruns = 0              # IN (0Eh) with nothing queued: read as 00h

    # -- the firmware's side (rp2.StateMachine) --
    def get(self):
        return self.rx.get()

    def put(self, b):
        if isinstance(b, (bytes, bytearray, memoryview)):
            for x in bytes(b):
                self.tx.put(x)
        elif isinstance(b, str):
            for x in b.encode():
                self.tx.put(x)
        else:
            self.tx.put(b & 0xFF)

    def rx_fifo(self):
        n = self.rx.qsize()
        if not n:
            _time.sleep(0)              # let the frame thread run: the firmware polls this
        return min(n, 4)

    def tx_fifo(self):
        n = self.tx.qsize()
        if n:
            _time.sleep(0)
        return min(n, 4)

    def active(self, *a):
        return None

    def restart(self):
        pass

    def exec(self, instr):
        t = instr.replace(" ", "")
        if t == "mov(y,invert(null))":
            self.y = 0xFFFFFFFF
        elif t.startswith("set(y,"):
            self.y = int(t[6:-1])
        elif t == "mov(y,invert(y))":
            self.y = ~self.y & 0xFFFFFFFF
        elif t in ("mov(y,null)",):
            self.y = 0
        elif t == "pull(noblock)":
            try:
                self.tx.get_nowait()
            except queue.Empty:
                pass
        # mov(osr,null) and anything else: no visible effect

    def reset_fifos(self):
        """A new StateMachine(0, ...) clears both FIFOs (pio_sm_init); Y stays."""
        for q in (self.rx, self.tx):
            while True:
                try:
                    q.get_nowait()
                except queue.Empty:
                    break

    # -- the emulator's side --
    def frame(self, op, v):
        if op == OP_OUT_DATA:
            self.rx.put(v)
            self.y = 0                  # auto-busy: every Z80 OUT drops READY
            return 0
        if op == OP_OUT_STATUS:
            self.rx.put(PORT_0F | v)
            self.y = 0
            return 0
        if op == OP_IN_STATUS:
            return self.y & 0xFF
        try:
            return self.tx.get_nowait()
        except queue.Empty:
            self.underruns += 1
            return 0x00                 # PIO pull(noblock) of an empty FIFO


BUS = BusModel()


# ---- a host folder as the Pico's flash + the SD card -------------------------

class HostFS:
    """MicroPython's `os` on a host folder: absolute paths ("/config.ini",
    "/sd/TAP/x.tap") live under root, relative ones under the current
    directory, which is tracked here as a Pico path."""

    def __init__(self, root):
        self.root = _os.path.abspath(root)
        self.cwd = "/"

    def pico(self, p):
        p = str(p)
        if not p.startswith("/"):
            p = (self.cwd.rstrip("/") + "/" + p) if p else self.cwd
        parts = []
        for part in p.split("/"):
            if part in ("", "."):
                continue
            if part == "..":
                if parts:
                    parts.pop()
                continue
            parts.append(part)
        return "/" + "/".join(parts)

    def host(self, p):
        return _os.path.join(self.root, self.pico(p).lstrip("/"))

    # the os functions the firmware uses
    def stat(self, p):
        st = _os.stat(self.host(p))
        mode = 0x4000 if _os.path.isdir(self.host(p)) else 0x8000
        return (mode, 0, 0, 0, 0, 0, st.st_size, int(st.st_atime), int(st.st_mtime), int(st.st_ctime))

    def ilistdir(self, p=""):
        h = self.host(p)
        for n in sorted(_os.listdir(h)):
            full = _os.path.join(h, n)
            if _os.path.isdir(full):
                yield (n, 0x4000, 0, 0)
            else:
                yield (n, 0x8000, 0, _os.path.getsize(full))

    def listdir(self, p=""):
        return sorted(_os.listdir(self.host(p)))

    def mkdir(self, p):
        _os.mkdir(self.host(p))

    def rmdir(self, p):
        _os.rmdir(self.host(p))

    def remove(self, p):
        _os.remove(self.host(p))

    def rename(self, a, b):
        _os.rename(self.host(a), self.host(b))

    def chdir(self, p):
        new = self.pico(p)
        if not _os.path.isdir(self.host(new)):
            raise OSError(2, "ENOENT")
        self.cwd = new

    def getcwd(self):
        return self.cwd

    def statvfs(self, p=""):
        return (4096, 4096, 61440, 57000, 57000, 0, 0, 0, 0, 255)     # a 240 MB card

    def mount(self, dev, p):
        if getattr(dev, "absent", False):
            raise OSError(19, "ENODEV")

    def umount(self, p):
        pass

    def sync(self):
        pass

    def uname(self):
        return ("rp2", "rp2", "1.29.0", "v1.29.0 (host)", "Raspberry Pi Pico (emulated)")

    def open(self, p, mode="r", *a, **k):
        return builtins.open(self.host(p), mode, *a, **k)

    def as_module(self):
        m = types.ModuleType("os")
        for name in ("stat", "ilistdir", "listdir", "mkdir", "rmdir", "remove", "rename",
                     "chdir", "getcwd", "statvfs", "mount", "umount", "sync", "uname"):
            setattr(m, name, getattr(self, name))
        m.sep = "/"
        return m


# ---- MicroPython stand-ins ---------------------------------------------------

def _mod(name, **attrs):
    m = types.ModuleType(name)
    m.__dict__.update(attrs)
    sys.modules[name] = m
    return m


def micropython_env(fs):
    def ident(*a, **k):
        if len(a) == 1 and callable(a[0]) and not k:
            return a[0]
        return lambda f: f

    class Pin:
        IN = OUT = PULL_UP = PULL_DOWN = 0

        def __init__(self, *a, **k):
            self.v = k.get("value", 0)

        def value(self, *a):
            if a:
                self.v = a[0]
            return self.v

        def on(self):
            self.v = 1

        def off(self):
            self.v = 0

        def toggle(self):
            self.v ^= 1

    class Other:                       # the ROM / BANK state machines, NULL_SM
        def __init__(self, *a, **k):
            pass

        def active(self, *a):
            pass

        def put(self, *a):
            pass

        def get(self, *a):
            return 0

        def exec(self, *a):
            pass

        def restart(self):
            pass

        def rx_fifo(self):
            return 0

        def tx_fifo(self):
            return 0

    def StateMachine(n, prog=None, *a, **k):
        if n == 0 and getattr(prog, "__name__", "") == "TS_IO_DUAL":
            BUS.reset_fifos()
            return BUS
        return Other()

    class PIOMeta(type):
        def __getattr__(cls, name):
            return 0

    class PIO(metaclass=PIOMeta):
        pass

    class SPI:
        def __init__(self, *a, **k):
            pass

    builtins.const = lambda x: x                       # a MicroPython builtin
    t = _time
    ticks = dict(ticks_ms=lambda: int(t.monotonic() * 1000),
                 ticks_us=lambda: int(t.monotonic() * 1_000_000),
                 ticks_diff=lambda a, b: a - b,
                 ticks_add=lambda a, b: a + b,
                 sleep=t.sleep, sleep_ms=lambda ms: t.sleep(ms / 1000),
                 sleep_us=lambda us: t.sleep(us / 1_000_000),
                 time=t.time, localtime=t.localtime, monotonic=t.monotonic)
    _mod("utime", **ticks)
    mp_time = _mod("mp_time", **ticks)
    _mod("micropython", const=lambda x: x, native=ident, viper=ident,
         mem_info=lambda *a: None, alloc_emergency_exception_buf=lambda n: None,
         schedule=lambda fn, arg: fn(arg))
    _mod("rp2", StateMachine=StateMachine, asm_pio=ident, PIO=PIO)   # no DMA: the firmware's polling paths
    _mod("machine", Pin=Pin, SPI=SPI, freq=lambda *a: 270_000_000, reset=lambda: _os._exit(3))
    import gc
    if not hasattr(gc, "mem_free"):
        gc.mem_free = lambda: 180_000

    class SDCard:
        CID = 0x5A5A
        absent = False

        def __init__(self, *a, **k):
            pass

    sd = _mod("TS.sdcard", SDCard=SDCard)
    sd.__all__ = ["SDCard"]
    return mp_time


def install_firmware(fs):
    mp_time = micropython_env(fs)
    os_mod = fs.as_module()
    sys.path.insert(0, SRC)
    import TS                                          # noqa: F401  (the package, for TS.sdcard)
    sys.modules["TS"].sdcard = sys.modules["TS.sdcard"]
    import json, array, math, random, struct, select, traceback, gc   # noqa: F401  (stdlib that uses the real os)
    real_os = sys.modules.get("os")
    sys.modules["os"] = os_mod                         # only while the firmware imports
    try:
        import TS.tspico as fw
        import TS.tspico_io as io
        import TS.catalog, TS.native, TS.channels, TS.printer   # noqa: F401
    finally:
        sys.modules["os"] = real_os
    for name, m in list(sys.modules.items()):
        if name.startswith("TS.") and isinstance(m, types.ModuleType) and name != "TS.sdcard":
            if hasattr(m, "os"):
                m.os = os_mod
            if hasattr(m, "time"):
                m.time = mp_time
            m.open = fs.open
            m.bytearray = MPBytearray
    sel = types.ModuleType("select")                   # DRAIN_STDIN: nothing on stdin, ever
    sel.POLLIN = 1

    class Poll:
        def register(self, *a):
            pass

        def ipoll(self, *a):
            return ()
    sel.poll = Poll
    io.select = sel
    fw.machine = sys.modules["machine"]

    class MPSys(types.ModuleType):
        """sys as the Pico reports it: MicroPython 1.29 (tpi:info shows it)."""
        implementation = types.SimpleNamespace(name="micropython", version=(1, 29, 0, ""),
                                               _machine="Raspberry Pi Pico (emulated)")

        def __getattr__(self, name):
            return getattr(sys, name)
    fw.sys = MPSys("sys")
    # extcmd looks for /dev_tspico.py first: that is this same firmware.
    sys.modules["dev_tspico"] = fw
    return fw


class MPBytearray(bytearray):
    """MicroPython's bytearray takes a str where CPython wants bytes
    (`blk += "abc"`, `.extend("abc")`): the firmware relies on it."""

    @staticmethod
    def _b(x):
        return x.encode() if isinstance(x, str) else x

    def __iadd__(self, other):
        return MPBytearray(bytearray.__add__(self, self._b(other)))

    def __add__(self, other):
        return MPBytearray(bytearray.__add__(self, self._b(other)))

    def extend(self, other):
        bytearray.extend(self, self._b(other))


def build_root(root, sd_src):
    """The Pico's flash and the card: config.ini (telemetry on), words.txt,
    assets/ from src/, and the SD card from --sd (the repo's "SD card")."""
    _os.makedirs(root, exist_ok=True)
    for name in ("config.ini", "words.txt"):
        src = _os.path.join(SRC, name)
        if _os.path.exists(src) and not _os.path.exists(_os.path.join(root, name)):
            shutil.copy(src, _os.path.join(root, name))
    a_src, a_dst = _os.path.join(SRC, "assets"), _os.path.join(root, "assets")
    if _os.path.isdir(a_src) and not _os.path.isdir(a_dst):
        shutil.copytree(a_src, a_dst)
    sd = _os.path.join(root, "sd")
    if not _os.path.isdir(sd):
        shutil.copytree(sd_src, sd)
    import json
    p = _os.path.join(root, "config.ini")
    try:
        cfg = json.load(open(p))
        cfg["TELEMETRY"] = True
        json.dump(cfg, open(p, "w"))
    except Exception:
        pass


# ---- the socket the emulator connects to ----------------------------------------

def serve():
    if _os.path.exists(SOCK):
        _os.unlink(SOCK)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCK)
    srv.listen(1)
    print("[pico_host] listening on", SOCK, flush=True)
    while True:
        conn, _ = srv.accept()
        print("[pico_host] emulator connected", flush=True)
        try:
            while True:
                hdr = b""
                while len(hdr) < 2:
                    chunk = conn.recv(2 - len(hdr))
                    if not chunk:
                        raise ConnectionError
                    hdr += chunk
                conn.sendall(bytes([BUS.frame(hdr[0], hdr[1]) & 0xFF]))
        except (ConnectionError, OSError):
            print("[pico_host] emulator disconnected (underruns: %d)" % BUS.underruns, flush=True)
        finally:
            conn.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/tmp/tspico-root", help="the Pico's flash; the card is <root>/sd")
    ap.add_argument("--sd", default=_os.path.join(REPO, "SD card"), help="seeds <root>/sd the first time")
    args = ap.parse_args()
    build_root(args.root, args.sd)
    sys.setswitchinterval(0.0002)
    fs = HostFS(args.root)
    fw = install_firmware(fs)
    fw.TLM_ENABLED = True

    def firmware():
        try:
            fw.TS2068_IO()
        except BaseException as e:            # noqa: BLE001
            import traceback
            traceback.print_exc()
            print("[pico_host] firmware stopped:", repr(e), flush=True)
    threading.Thread(target=firmware, daemon=True).start()
    serve()


if __name__ == "__main__":
    main()
