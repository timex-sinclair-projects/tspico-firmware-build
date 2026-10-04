#!/usr/bin/env python3
"""A TS-2068 + TS-Pico session with no hardware (issue #35): ZEsarUX running
the TS-Pico ROM, the real firmware behind it (tools/emu/pico_host.py), and a
ZRCP client to type BASIC, read the screen and save screenshots.

    from session import Session, SAVE, CAT, LOAD
    with Session() as s:
        s.run(CAT)                              # CAT
        print(s.text())                         # the screen, as text (ZEsarUX OCR)
        s.screenshot("cat.bmp")
        s.run(SAVE, '"tpi:info"')

Needs the patched ZEsarUX (branch `tspico-device`: 16K EXROM and the port
0Eh/0Fh bridge); its binary from $ZESARUX, else the lab's build. Each line is
typed as a placeholder and then written into the edit line already
tokenised (the 2068's keyword entry is too fiddly to type over ZRCP).
"""

import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
EMU = os.environ.get("ZESARUX", os.path.expanduser(
    "~/Documents/github/zesarux-tspico-lab/work/zesarux-tspico"))
ROM = os.path.join(REPO, "src", "rom", "TSPICO-21.ROM")
SOCK = os.environ.get("TSPICO_BRIDGE_SOCK", "/tmp/tspico_bridge.sock")

# BASIC tokens
SAVE, LOAD, CAT, CODE, LPRINT, MOVE, PRINT, TO, OUT = 0xF8, 0xEF, 0xCF, 0xAF, 0xE0, 0xD1, 0xF5, 0xCC, 0xDF
E_LINE, ERR_NR = 23641, 23610


def tap_block(flag, body):
    """One TAP block: length, flag, body, XOR checksum."""
    data = bytes([flag]) + bytes(body)
    x = 0
    for b in data:
        x ^= b
    data += bytes([x])
    return bytes([len(data) & 0xFF, len(data) >> 8]) + data


def basic_tap(name, lines, autorun=0x8000):
    """A TAP holding a BASIC program: lines = [(number, tokenised bytes)]."""
    prog = b"".join(bytes([n >> 8, n & 0xFF]) + bytes([(len(t) + 1) & 0xFF, (len(t) + 1) >> 8])
                    + t + b"\x0d" for n, t in lines)
    hdr = bytes([0]) + name.encode().ljust(10)[:10] + bytes(
        [len(prog) & 0xFF, len(prog) >> 8, autorun & 0xFF, autorun >> 8, len(prog) & 0xFF, len(prog) >> 8])
    return tap_block(0x00, hdr) + tap_block(0xFF, prog)


class Session:
    def __init__(self, root="/tmp/tspico-root", fresh=True, port=10000, log="/tmp/pico_host.out",
                 sd=os.path.join(REPO, "SD card")):
        # Stale ones from a session that died would take the socket and the
        # ZRCP port: stop them first.
        subprocess.run(["pkill", "-f", os.path.basename(EMU)], stderr=subprocess.DEVNULL)
        subprocess.run(["pkill", "-f", "tools/emu/pico_host.py"], stderr=subprocess.DEVNULL)
        time.sleep(0.5)
        if fresh and os.path.isdir(root):
            import shutil
            shutil.rmtree(root)
        self.port = port
        self.host = subprocess.Popen(
            [sys.executable, "-u", os.path.join(HERE, "pico_host.py"), "--root", root, "--sd", sd],
            stdout=open(log, "w"), stderr=subprocess.STDOUT)
        t0 = time.time()
        while "listening" not in open(log).read():
            assert time.time() - t0 < 20, "pico_host didn't start: see " + log
            time.sleep(0.2)
        time.sleep(1.5)                       # its boot-noise flush, before the first command
        self.emu = subprocess.Popen(
            [EMU, "--machine", "TS2068", "--romfile", ROM, "--enable-remoteprotocol",
             "--remoteprotocol-port", str(port), "--noconfigfile", "--vo", "null", "--ao", "null"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.s = None
        t0 = time.time()
        while self.s is None:
            try:
                self.s = socket.create_connection(("localhost", port), timeout=2)
            except OSError:
                assert time.time() - t0 < 20, "ZEsarUX didn't open ZRCP"
                time.sleep(0.3)
        self.cmd("")
        self.wait_editor()

    # ---- ZRCP ----
    def cmd(self, c, timeout=60):
        """One ZRCP command; its reply, up to the next prompt."""
        self.s.settimeout(0.05)
        try:
            while self.s.recv(65536):
                pass
        except OSError:
            pass
        self.s.settimeout(timeout)
        self.s.sendall((c + "\n").encode())
        buf = b""
        while b"command>" not in buf:
            buf += self.s.recv(65536)
        return buf.decode(errors="replace").replace("command>", "").strip()

    def peek(self, addr, n):
        toks = [t for t in self.cmd("read-memory %d %d" % (addr, n)).split()
                if len(t) == 2 * n and all(c in "0123456789ABCDEFabcdef" for c in t)]
        return bytes.fromhex(toks[0])

    def poke(self, addr, data):
        for i in range(0, len(data), 64):
            self.cmd("write-memory %d %s" % (addr + i, " ".join(str(b) for b in data[i:i + 64])))

    def key(self, code, hold=0.12):
        self.cmd("send-keys-event %d 1" % code)
        time.sleep(hold)
        self.cmd("send-keys-event %d 0" % code)

    # ---- the 2068 ----
    def text(self):
        """The screen as text (ZEsarUX's OCR of the 2068 character set)."""
        return "\n".join(l.rstrip() for l in self.cmd("get-ocr").splitlines())

    def wait_editor(self, timeout=30):
        """Past the copyright screen or a report: the K cursor alone on the
        bottom line (pressing ENTER until it's there)."""
        t0 = time.time()
        while time.time() - t0 < timeout:
            lines = [l for l in self.text().splitlines() if l.strip()]
            if lines and lines[-1].strip() == "K":
                return
            self.key(129)                       # ENTER
            time.sleep(0.6)
        raise AssertionError("the editor never came up:\n" + self.text())

    def run(self, *parts, wait=None, until=None, timeout=60):
        """Enter one immediate line given as tokens (ints) and text (str),
        e.g. run(SAVE, '"tpi:info"'). Waits until a report is printed (or
        `until` text appears), then returns the screen text."""
        line = b"".join(bytes([p]) if isinstance(p, int) else p.encode("latin-1") for p in parts)
        self.wait_editor()
        for k in range(0, len(line), 10):       # placeholder 'a's; ZRCP takes ~20 keys a command
            self.cmd("send-keys-ascii 120 " + " ".join(["97"] * min(10, len(line) - k)))
        t0 = time.time()
        while True:
            el = int.from_bytes(self.peek(E_LINE, 2), "little")
            cur = self.peek(el, len(line) + 1)
            if cur[-1] == 0x0D and all(b != 0x0D for b in cur[:-1]):
                break
            assert time.time() - t0 < 20, "typing the placeholder failed: " + cur.hex()
            time.sleep(0.2)
        self.poke(el, line)
        self.cmd("poke %d 255" % ERR_NR)
        self.key(129)                          # ENTER
        t0 = time.time()
        while time.time() - t0 < timeout:
            time.sleep(0.5)
            t = self.text()
            if until is not None:
                if until in t:
                    return t
            elif self.peek(ERR_NR, 1)[0] != 0xFF or ", 0:1" in t:
                return t
        return self.text()

    def screenshot(self, path):
        """The emulated screen to a file (.bmp / .scr / .pbm, by its name)."""
        return self.cmd("save-screen " + os.path.abspath(path))

    def close(self):
        for p in (self.emu, self.host):
            try:
                p.terminate()
                p.wait(5)
            except Exception:
                p.kill()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


if __name__ == "__main__":
    with Session() as s:
        print(s.run(CAT))
        s.screenshot("/tmp/tspico-cat.bmp")
