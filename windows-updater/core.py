"""TS-Pico Updater -- the engine, without a window.

The same guided run as the web updater (web-updater/app.js), for machines
where the browser can't reach the Pico's boot ROM: Windows has no WebUSB
driver for "RP2 Boot", and Chrome won't hand a page the RPI-RP2 drive.
A native program can do both the plain way -- pyserial for the MicroPython
REPL, an ordinary file copy onto the RPI-RP2 drive for each UF2.

   1. Connect   serial -> Ctrl-C the firmware -> raw REPL; read the version.
   2. BOOTSEL   machine.bootloader(), then wait for the RPI-RP2 drive.
   3. Wipe      copy flash_nuke.uf2; the Pico erases and comes back.
   4. ROM       boards behind the channel's ROM: copy upgrade.uf2, follow its
                "UPG {json}" lines while the user runs the updater on the 2068
                (OUT 244,3, LOAD ""), then back to BOOTSEL.
   5. Firmware  copy firmware.uf2.
   6. Files     serial again: main.py, config.ini, words.txt, assets/,
                verify, machine.reset().
   7. Modem     the v3 card only: Zimodem on its ESP32-C3, checked over the
                raw REPL and, if missing or older, written through the
                card's relay (tsbus.esp_relay) with espflash.py.

The v3 card (RP2350B) skips 3 and 4: its ROMs are slot files on the same
flash as the firmware, so a wipe would erase the user's slots, and the ROM
step is a file copy. Step 5 copies the manifest's v3.uf2 onto the RP2350
drive; step 6 also writes /slots (0 and 1 always, the others only where the
card has none).

Everything comes from the same published channel directories the web page
uses (release/ and main/ under the site's /updater/), so this program never
needs rebuilding for a new firmware release.

The window (app.py) talks to the run only through the Ui class below, so
the run can be driven by a test with a fake Pico (test/core_test.py).
"""

import base64
import json
import os
import re
import string
import struct
import sys
import time
import urllib.request

import espflash

SITE = "https://timex-sinclair-projects.github.io/tspico-firmware-build/updater/"
CHANNELS = ("release", "main")
PICO_VID = 0x2E8A
ROM_BLOCKS = {1: 128, 0: 64}        # updater.asm: slot 1 is 32K, slot 0 the low 16K
ROM_FAIL = {
    1: "The updater got no answer from the TS-Pico.",
    2: 'The flash can\'t be written: fit the P10 jumper, then type LOAD "" on the 2068 again.',
    3: 'The data kept arriving wrong. Type LOAD "" on the 2068 to try again.',
    4: 'A flash write didn\'t take. Type LOAD "" on the 2068 to try again.',
}
STAGES = ("connect", "bootsel", "wipe", "rom", "firmware", "files", "modem")
UF2_FAMILY = {"RP2040": 0xE48BFF56, "RP2350": 0xE48BFF59}   # RP2350: Arm, secure
UF2_FLAG_FAMILY = 0x00002000
# Python that removes /TS if it's there: a /TS left on the flash shadows the
# frozen modules and stops the firmware starting. A v2 board is wiped instead;
# a v3 card never is. Prints 1 if it removed one.
RMTREE = """import os
def _rm(p):
 try:
  m = os.stat(p)[0]
 except OSError:
  return 0
 if m & 0x4000:
  for n in os.listdir(p):
   _rm(p + '/' + n)
  os.rmdir(p)
 else:
  os.remove(p)
 return 1
print(_rm('/TS'))"""
# The raw REPL's first code. The firmware may have left the current directory
# on the SD card, and `import os` looks in it first (os, like time, is
# extensible): a card that was busy when the firmware was stopped fails the
# import (EIO, ETIMEDOUT). Import os with '' off the path, then start from the
# flash's root. The web updater's vendor/rawmode.js does the same.
RAW_START = """import sys
c = '' in sys.path
if c: sys.path.remove('')
import os
if c: sys.path.insert(0, '')
os.chdir('/')
del c"""
# Python for the v3 card: the modem off, the ESP32 restarted into Zimodem, and
# the version ATI reports ("4.0.3"), or "-" if nothing answers like Zimodem.
ESP_PROBE = """import tsbus, time
from machine import UART, Pin
from TS import board
tsbus.modem(False)
u = UART(0, 115200, tx=Pin(44), rx=Pin(45), timeout=50, rxbuf=2048)
board.esp_boot(False)
time.sleep_ms(3000)
u.read()
u.write(b'\\rATI\\r')
time.sleep_ms(800)
b = u.read() or b''
u.deinit()
i = b.find(b'Firmware v')
print(b[i + 10:b.find(b'\\r', i)].decode() if i >= 0 else '-')"""
# Python for the v3 card: the ESP32 into its ROM loader and USB joined to its
# UART until the host has been quiet for 4 s (tsbus.esp_relay). Ctrl-C off
# meanwhile: 03h is just data.
ESP_RELAY = """import tsbus, time, micropython
from TS import board
tsbus.modem(False)
board.esp_boot(True)
time.sleep_ms(300)
micropython.kbd_intr(-1)
try:
    r = tsbus.esp_relay(60000, 4000)
finally:
    micropython.kbd_intr(3)
    board.esp_boot(False)
print('RELAY', r)"""


class Stop(Exception):
    """The user chose to stop; not a failure."""


def resource(name):
    """A file the exe carries (PyInstaller unpacks it to sys._MEIPASS); run
    from the repo, the web updater's copy."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, name)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web-updater", name)


# ---------------------------------------------------------------------------
# Versions -- the same rules as app.js
# ---------------------------------------------------------------------------
def ver_of(v):
    """"2.1.2" -> (2, 1): the major.minor firmware and ROM share from 2.0 on."""
    m = re.match(r"^(\d+)\.(\d+)", str(v or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def major_of(v):
    """parseFloat("1.1 (no version...)") -> 1.1; None when it isn't a number."""
    m = re.match(r"^\s*(\d+(?:\.\d+)?)", str(v or ""))
    return float(m.group(1)) if m else None


def ver_cmp(a, b):
    """"1.29.0" vs "1.20.0": <0, 0 or >0."""
    pa = [int(x) for x in re.findall(r"\d+", str(a))[:3]] + [0, 0, 0]
    pb = [int(x) for x in re.findall(r"\d+", str(b))[:3]] + [0, 0, 0]
    for x, y in zip(pa[:3], pb[:3]):
        if x != y:
            return x - y
    return 0


def rom_behind(installed, manifest):
    """Does this board need the ROM step? The ROM can't be read over USB, so
    the installed firmware's major.minor stands for it; an unknown version
    (a wiped Pico) counts as behind -- every board out there has 1.1's ROM."""
    if not installed or not manifest:
        return False
    want = ver_of(manifest.get("rom_version") or manifest.get("fw_version"))
    if not want:
        return installed["from1x"]
    have = installed["ver"]
    if not have:
        return True
    return have < want


def uf2_micropython(data):
    """The MicroPython release inside a UF2 ("1.20.0"), or None. UF2 blocks
    carry 256 payload bytes each, so join them before searching."""
    pay = b"".join(data[i + 32:i + 288] for i in range(0, len(data) - 511, 512))
    m = re.search(rb"MicroPython v(\d+\.\d+\.\d+)", pay)
    return m.group(1).decode() if m else None


def check_uf2(data, name, chip="RP2040"):
    """Refuse a UF2 built for the other chip before copying it: an RP2040
    image on the v3 card, or the reverse, leaves a board that doesn't start."""
    if len(data) < 512 or len(data) % 512:
        raise RuntimeError("%s is not a UF2 (size %d)" % (name, len(data)))
    magic0, magic1, flags = struct.unpack_from("<III", data, 0)
    if magic0 != 0x0A324655 or magic1 != 0x9E5D5157:
        raise RuntimeError("%s is not a UF2 (bad magic)" % name)
    if flags & UF2_FLAG_FAMILY and struct.unpack_from("<I", data, 28)[0] != UF2_FAMILY[chip]:
        raise RuntimeError("%s is not an %s UF2" % (name, chip))


# ---------------------------------------------------------------------------
# The channel: manifest + payload, from the site or a local directory
# ---------------------------------------------------------------------------
class Channel:
    def __init__(self, name, base=SITE):
        self.name = name
        self.base = base if base.endswith(("/", os.sep)) else base + "/"
        self.manifest = None

    def _get(self, rel):
        if self.base.startswith(("http://", "https://")):
            url = self.base + rel
            req = urllib.request.Request(url, headers={"Cache-Control": "no-cache"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read()
        with open(os.path.join(self.base, *rel.split("/")), "rb") as f:
            return f.read()

    def load(self):
        self.manifest = json.loads(self._get(self.name + "/manifest.json"))
        return self.manifest

    def fetch(self, rel):
        return self._get(self.name + "/" + rel)


# ---------------------------------------------------------------------------
# Serial + the MicroPython raw REPL
# ---------------------------------------------------------------------------
def pico_ports():
    from serial.tools import list_ports
    return sorted(p.device for p in list_ports.comports() if p.vid == PICO_VID)


class Gone(Exception):
    """The serial port went away (the Pico rebooted or was unplugged)."""


class Port:
    """A Pico's USB serial port, opened with DTR on: MicroPython's USB CDC
    only sends to a host that has asserted DTR."""

    def __init__(self, device):
        import serial
        self.device = device
        self.s = serial.Serial(device, 115200, timeout=0.05, write_timeout=5)
        self.s.dtr = True
        self.buf = b""

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass

    def write(self, data, chunk=256):
        """In chunks with a breath between: the raw REPL reads from a small
        USB buffer, as pyboard.py does it."""
        try:
            for i in range(0, len(data), chunk):
                self.s.write(data[i:i + chunk])
                if len(data) > chunk:
                    time.sleep(0.01)
        except Exception as e:
            raise Gone(str(e)) from e

    def read_some(self):
        try:
            n = self.s.in_waiting
            return self.s.read(n or 1)
        except Exception as e:
            raise Gone(str(e)) from e

    def read_until(self, token, timeout=5.0):
        end = time.monotonic() + timeout
        while token not in self.buf:
            if time.monotonic() > end:
                raise TimeoutError("timed out waiting for %r (got %r)" % (token, self.buf[-80:]))
            self.buf += self.read_some()
        i = self.buf.index(token) + len(token)
        out, self.buf = self.buf[:i], self.buf[i:]
        return out

    def flush_input(self):
        time.sleep(0.1)
        try:
            self.s.reset_input_buffer()
        except Exception as e:
            raise Gone(str(e)) from e
        self.buf = b""


class _LoaderIO:
    """The card's port as espflash.py's io: the relay passes bytes both ways."""

    def __init__(self, port):
        self.port = port

    def write(self, data):
        # Whole frames at once: Port.write's pauses are for the raw REPL's
        # small buffer, and would add half a minute over a Zimodem write.
        self.port.write(data, chunk=len(data) or 1)

    def read(self, timeout):
        p = self.port
        if p.buf:
            data, p.buf = p.buf, b""
            return data
        end = time.monotonic() + timeout
        while True:
            data = p.read_some()
            if data or time.monotonic() >= end:
                return data


class RawRepl:
    """MicroPython's raw REPL (Ctrl-A): send code + Ctrl-D, get OK, stdout,
    Ctrl-D, stderr, Ctrl-D, '>'."""

    def __init__(self, port):
        self.port = port

    def enter(self, timeout=20.0):
        p = self.port
        end = time.monotonic() + timeout
        while True:                              # Ctrl-C until the firmware lets go
            p.write(b"\r\x03")
            try:
                p.read_until(b">>> ", 0.5)
                break
            except TimeoutError:
                if time.monotonic() > end:
                    raise TimeoutError("the Pico doesn't answer Ctrl-C")
        p.flush_input()
        p.write(b"\r\x01")
        p.read_until(b"raw REPL; CTRL-B to exit\r\n")
        p.read_until(b">")

    def exec(self, code, timeout=10.0):
        p = self.port
        if isinstance(code, str):
            code = code.encode()
        p.write(code)
        p.write(b"\x04")
        p.read_until(b"OK", timeout)
        out = p.read_until(b"\x04", timeout)[:-1]
        err = p.read_until(b"\x04", timeout)[:-1]
        p.read_until(b">", timeout)
        if err:
            raise RuntimeError(err.decode(errors="replace").strip())
        return out.decode(errors="replace")

    def exec_no_reply(self, code):
        """Code that resets the board: no reply will come."""
        try:
            self.port.write(code.encode() + b"\x04")
            time.sleep(0.4)
        except Gone:
            pass

    def restart_firmware(self):
        """Out of the raw REPL (Ctrl-B), then a soft reset (Ctrl-D) from the
        friendly one, which runs main.py: a soft reset inside the raw REPL
        comes back to the raw REPL, and the firmware never starts."""
        try:
            self.port.write(b"\x02")
            time.sleep(0.2)
            self.port.write(b"\x04")
            time.sleep(0.4)
        except Gone:
            pass

    def write_file(self, path, data, chunk=1024, progress=None):
        self.exec("import binascii\nf=open(%r,'wb')\nw=f.write\na=binascii.a2b_base64" % path)
        try:
            for i in range(0, len(data), chunk):
                b64 = base64.b64encode(data[i:i + chunk]).decode()
                self.exec("w(a(%r))" % b64)
                if progress:
                    progress(min(len(data), i + chunk))
        finally:
            self.exec("f.close()")

    def make_dirs(self, path):
        self.exec(
            "import os\np=''\nfor d in %r.split('/'):\n"
            " if not d: continue\n p+='/'+d\n"
            " try: os.mkdir(p)\n except OSError as e:\n"
            "  if e.args[0] not in (17,20): raise\n" % path)


# ---------------------------------------------------------------------------
# The boot drive: RPI-RP2 on a Pico, RP2350 on the v3 card
# ---------------------------------------------------------------------------
def drive_chip(root):
    """"RP2040" or "RP2350" by the drive's INFO_UF2.TXT, or None if it isn't
    a boot drive."""
    try:
        with open(os.path.join(root, "INFO_UF2.TXT"), "r", errors="replace") as f:
            text = f.read()
    except OSError:
        return None
    if "RP2350" in text:
        return "RP2350"
    if "RPI-RP2" in text:
        return "RP2040"
    return None


def find_drive():
    """The mounted boot drive's root, or None."""
    if os.name == "nt":
        import ctypes
        k32 = ctypes.windll.kernel32
        k32.SetErrorMode(0x0001)                 # SEM_FAILCRITICALERRORS: no "insert a disk" box
        mask = k32.GetLogicalDrives()
        for i, letter in enumerate(string.ascii_uppercase):
            if not mask & (1 << i):
                continue
            root = letter + ":\\"
            if k32.GetDriveTypeW(root) != 2:      # DRIVE_REMOVABLE
                continue
            if drive_chip(root):
                return root
        return None
    cands = ["/Volumes/RPI-RP2", "/Volumes/RP2350"]
    for base in ("/media", "/run/media"):
        try:
            for user in os.listdir(base):
                cands += [os.path.join(base, user, n) for n in ("RPI-RP2", "RP2350")]
        except OSError:
            pass
    for c in cands:
        if drive_chip(c):
            return c
    return None


def write_uf2(drive, data, name, progress=None):
    """Copy a UF2 onto the drive, as a drag would. The Pico reboots on the last
    block, so an error closing the file afterwards is expected."""
    path = os.path.join(drive, name)
    written = 0
    try:
        with open(path, "wb", buffering=0) as f:
            for i in range(0, len(data), 32 * 1024):
                written += f.write(data[i:i + 32 * 1024])
                if progress:
                    progress(written / len(data))
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
    except OSError:
        if written < len(data):
            raise


# ---------------------------------------------------------------------------
# What the run needs from a window
# ---------------------------------------------------------------------------
class Ui:
    def log(self, msg, kind=""): print(msg)
    def stage(self, name, state, msg=None): pass
    def stage_msg(self, name, msg): pass
    def progress(self, name, frac): pass
    def rom_steps(self, on): pass
    def rom_status(self, text, kind=""): pass
    def offer(self, name, choices): """Show buttons [(label, value)]; don't wait."""
    def withdraw(self, name): pass
    def take(self, timeout=None): """The value of the button pressed, or None by timeout."""
    def confirm(self, text): return True

    def ask(self, name, choices):
        self.offer(name, choices)
        v = self.take(None)
        self.withdraw(name)
        return v


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------
class Updater:
    def __init__(self, ui, base=SITE):
        self.ui = ui
        self.base = base
        self.channel = None
        self.port = None
        self.raw = None
        self.installed = None
        self.board = None                        # "v2" (RP2040) or "v3" (RP2350B), once known
        self.nuke = None                         # flash_nuke.uf2, from the bundle

    @property
    def v3(self):
        return self.board == "v3"

    # --- channel -----------------------------------------------------------
    def load_channel(self, name):
        ch = Channel(name, self.base)
        ch.load()
        self.channel = ch
        m = ch.manifest
        self.ui.log("Loaded %s channel: firmware %s (%s), %d files%s" % (
            name, m.get("fw_version", "?"), m.get("tag", ""), len(m["files"]),
            ", ROM updater included." if m.get("upgrade_uf2") else ", no ROM updater."))
        return m

    @property
    def manifest(self):
        return self.channel.manifest if self.channel else None

    def rom_behind(self):
        return not self.v3 and rom_behind(self.installed, self.manifest)

    def image(self):
        """(path in the channel, MicroPython release or None) of the firmware
        for this board."""
        m = self.manifest
        if self.v3:
            v3 = m.get("v3") or {}
            return v3.get("uf2"), v3.get("mp_version")
        return m.get("uf2"), m.get("mp_version")

    # --- serial ------------------------------------------------------------
    def open_port(self, device):
        last = None
        for _ in range(6):                       # Windows may refuse a port that just appeared
            try:
                self.port = Port(device)
                return self.port
            except Exception as e:
                last = e
                time.sleep(0.5)
        raise RuntimeError("can't open %s: %s" % (device, last))

    def close_port(self):
        if self.port:
            self.port.close()
        self.port = None
        self.raw = None

    def wait_port(self, name, timeout=30.0):
        self.ui.stage_msg(name, "Waiting for the Pico to come back on USB…")
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            ports = pico_ports()
            if ports:
                time.sleep(0.5)
                return self.open_port(ports[0])
            time.sleep(0.5)
        raise RuntimeError("the Pico didn't come back on USB as a serial port")

    def enter_raw(self):
        if not self.raw:
            raw = RawRepl(self.port)
            raw.enter()
            raw.exec(RAW_START)
            self.raw = raw
        return self.raw

    def connect(self):
        """Find the Pico's serial port, stop the firmware, read its version."""
        self.ui.stage("connect", "active", "Looking for the TS-Pico…")
        ports = pico_ports()
        if not ports:
            raise RuntimeError("no TS-Pico serial port. Check the cable, close Thonny, "
                               "or put the Pico in BOOTSEL mode by hand and press Start.")
        if len(ports) > 1:
            self.ui.log("More than one Pico: using %s." % ports[0], "warn")
        self.open_port(ports[0])
        self.ui.log("Opened %s." % ports[0])
        self.ui.stage_msg("connect", "Stopping the firmware and reading its version…")
        self.enter_raw()
        self.installed = self.read_installed()
        self.ui.stage("connect", "done", "Connected. Installed: %s." % self.installed["fw"])
        return self.installed

    def read_installed(self):
        raw = self.raw
        info = json.loads(raw.exec(
            "import json\nu=os.uname()\nprint(json.dumps([u.sysname,u.release,u.machine]))"))
        self.ui.log("Device: %s — MicroPython %s" % (info[2], info[1]))
        if not re.search(r"rp2|pico", info[2] + " " + info[0], re.I):
            self.ui.log("Warning: this does not look like an RP2040/Pico.", "warn")
        # "TS-Pico v3 with RP2350" on the v3 card; "... with RP2040" on a Pico.
        self.board = "v3" if "RP2350" in info[2].upper() else "v2"
        if self.v3:
            self.ui.log("This is a TS-Pico v3 card (RP2350B).")
        # The running firmware's FW_VERSION (2.0 on) wins: Ctrl-C leaves its
        # module loaded, and config.ini can hold a stale one. 1.x has none,
        # so fall back to config.ini: 1.5 wrote FW_VERSION there, 1.1 didn't.
        code = ""
        try:
            code = raw.exec("m=sys.modules.get('TS.tspico') or sys.modules.get('dev_tspico')\n"
                            "print(getattr(m,'FW_VERSION','') if m else '')").strip()
        except RuntimeError:
            pass
        cfg = None
        try:
            cfg = json.loads(raw.exec("print(open('/config.ini').read())"))
        except (RuntimeError, ValueError):
            pass
        if code:
            fw, major, known = code, major_of(code), True
        elif cfg is not None:
            fw = cfg.get("FW_VERSION") or "1.1 (no version in config.ini)"
            major, known = major_of(cfg.get("FW_VERSION") or "1.1"), False
        else:
            fw, major, known = "unknown (no firmware running, no config.ini)", None, False
        return {"fw": fw, "ver": ver_of(code) if known else None,
                "from1x": major is not None and major < 2, "mp": info[1] or None}

    def bootloader(self):
        """machine.bootloader() over the raw REPL; the port drops."""
        self.enter_raw()
        self.ui.log("machine.bootloader()")
        self.raw.exec_no_reply("import machine\nmachine.bootloader()")
        self.close_port()

    # --- drive -------------------------------------------------------------
    def wait_drive(self, name, timeout=30.0):
        self.ui.stage_msg(name, "Waiting for the boot drive (RPI-RP2, or RP2350 on the v3 card)…")
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            d = find_drive()
            if d:
                return d
            time.sleep(0.5)
        raise RuntimeError("the boot drive (RPI-RP2, or RP2350 on the v3 card) didn't appear. "
                           "Hold BOOTSEL while plugging in USB, then press Start again.")

    def wait_drive_gone(self, timeout=20.0):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if not find_drive():
                return True
            time.sleep(0.3)
        return False

    def copy_uf2(self, name, data, label, fname, comes_back=False):
        """Copy a UF2 and see the Pico take it: the drive goes away. One that
        comes_back (the flash eraser) reboots into BOOTSEL again, and may do it
        before a poll sees the drive gone."""
        drive = self.wait_drive(name)
        self.ui.stage_msg(name, "Writing %s (%d KB) to %s…" % (label, len(data) // 1024, drive))
        write_uf2(drive, data, fname, lambda f: self.ui.progress(name, f))
        if not self.wait_drive_gone(10 if comes_back else 20) and not comes_back:
            raise RuntimeError("the Pico didn't restart after %s was copied" % label)
        self.ui.log("Wrote %s." % label, "ok")

    # --- stages ------------------------------------------------------------
    def enter_bootsel(self):
        self.ui.stage("bootsel", "active", "")
        if self.port:
            self.ui.stage_msg("bootsel", "Rebooting the Pico into BOOTSEL mode…")
            self.bootloader()
        d = self.wait_drive("bootsel")
        # A board put in BOOTSEL by hand wasn't known until now.
        if drive_chip(d) == "RP2350" and not self.v3:
            self.board = "v3"
            self.ui.log("This is a TS-Pico v3 card (RP2350B): no erase and no ROM update; "
                        "its ROM slots are files.")
        elif not self.board:
            self.board = "v2"
        self.ui.stage("bootsel", "done", "In BOOTSEL mode — the boot drive is %s." % d)

    def wipe(self):
        if self.v3:                              # flash_nuke is RP2040-only, and would take the slots
            raise RuntimeError("the v3 card is never erased")
        self.ui.stage("wipe", "active", "Erasing the Pico’s flash…")
        if self.nuke is None:
            with open(resource("flash_nuke.uf2"), "rb") as f:
                self.nuke = f.read()
        self.copy_uf2("wipe", self.nuke, "the flash eraser", "flash_nuke.uf2", comes_back=True)
        # flash_nuke erases everything, then comes back as RPI-RP2.
        self.wait_drive("wipe", 60)
        self.ui.stage("wipe", "done", "Erased.")
        self.ui.log("Flash erased.", "ok")

    def rom_update(self):
        ui = self.ui
        ui.stage("rom", "active", "Downloading the ROM updater…")
        data = self.channel.fetch(self.manifest["upgrade_uf2"])
        self.copy_uf2("rom", data, "the ROM updater", "upgrade.uf2")
        self.wait_port("rom")
        ui.stage_msg("rom", "Now on the TS-2068 (the TS-Pico stays plugged into it and into USB):")
        ui.rom_steps(True)
        ui.progress("rom", 0)
        ui.rom_status('Waiting for LOAD "" on the 2068…')

        st = {"phase": 1, "slot1": False, "writing": False, "last": time.monotonic(), "done": None}

        def on_upg(ev):
            st["last"] = time.monotonic()
            e = ev.get("event")
            if e != "status" or ev.get("code") != "W":
                ui.log("2068: " + " ".join("%s=%s" % kv for kv in ev.items()))
            if e == "waiting":
                ui.rom_status('Waiting for LOAD "" on the 2068…')
            elif e == "tape":
                st["writing"] = False
                ui.rom_status('The updater stopped; the tape rewound. Type LOAD "" again.'
                              if ev.get("note") else "Loading the updater from the TS-Pico…")
            elif e == "ignored":
                ui.rom_status('That went to the TS-2068 ROM, not the Spectrum ROM. '
                              'Type OUT 244,3 first, then LOAD "".', "warn")
            elif e == "updater":
                st["writing"] = True
                ui.withdraw("rom")               # continuing now would interrupt it
                ui.rom_status("The updater is running. Don’t turn anything off.")
            elif e == "status":
                code, arg = ev.get("code"), ev.get("arg")
                if code == "P":
                    st["phase"] = arg
                    ui.rom_status("Writing the TS-2068 ROM (slot 1)…" if arg == 1
                                  else "Writing the ZX Spectrum ROM (slot 0)…")
                elif code == "W":
                    before = 0 if st["phase"] == 1 else ROM_BLOCKS[1]
                    ui.progress("rom", (before + arg + 1) / (ROM_BLOCKS[1] + ROM_BLOCKS[0]))
                elif code == "V":
                    if st["phase"] == 1:
                        st["slot1"] = True
                    ui.log("Slot %s verified." % st["phase"], "ok")
                elif code == "D":
                    st["writing"] = False
                    ui.progress("rom", 1)
                    ui.rom_status("Both ROMs written and verified. The 2068 says DONE.", "ok")
                    st["done"] = "done"
                elif code == "X":
                    st["writing"] = False
                    ui.rom_status(ROM_FAIL.get(arg, "The update failed (reason %s)." % arg) +
                                  (" (The TS-2068 ROM is already new; you can also continue "
                                   "without the ZX ROM.)" if st["slot1"] else ""), "warn")

        # An escape hatch for when the serial lines don't arrive but the 2068
        # shows DONE -- offered only while the updater isn't writing, because
        # continuing interrupts the Pico, and the updater needs it until DONE.
        offered = False
        line = b""
        while st["done"] is None:
            try:
                chunk = self.port.read_some()
            except Gone:
                self.close_port()
                raise RuntimeError("The Pico disconnected during the ROM update. Plug it back in "
                                   "and press Start again (untick Erase if the ROM part finished).")
            line += chunk
            while b"\n" in line:
                one, line = line.split(b"\n", 1)
                one = one.strip().decode(errors="replace")
                if one.startswith("UPG "):
                    try:
                        on_upg(json.loads(one[4:]))
                    except ValueError:
                        pass
            if st["writing"] and offered:
                offered = False
            if not offered and not st["writing"] and time.monotonic() - st["last"] > 45:
                offered = True
                ui.offer("rom", [("The 2068 says DONE — continue", "done"), ("Stop", "stop")])
            if offered:
                v = ui.take(0)
                if v:
                    ui.withdraw("rom")
                    st["done"] = v
        ui.withdraw("rom")
        ui.rom_steps(False)
        if st["done"] == "stop":
            raise Stop()
        ui.stage("rom", "done", "TS-2068 ROM updated.")

        # Back to BOOTSEL for the real firmware -- a hard reset of the Pico, so
        # with the 2068 off: a reset while the 2068 runs leaves the SD card
        # unreadable until it loses power, and the ROM chip is live under it.
        ui.stage_msg("firmware", "Switch the TS-2068 off now. The USB cable keeps the Pico "
                                 "powered, and the Pico is about to restart.")
        if ui.ask("firmware", [("The 2068 is off — continue", "go"), ("Stop", "stop")]) == "stop":
            raise Stop()
        ui.stage_msg("firmware", "Rebooting the Pico into BOOTSEL mode…")
        self.bootloader()

    def firmware(self):
        m = self.manifest
        uf2, _ = self.image()
        if not uf2:
            raise RuntimeError("this channel has nothing for the v3 card yet — pick "
                               "“Latest main build”" if self.v3 else "this channel has no firmware image")
        label = "firmware %s%s" % (m["fw_version"], " for the v3 card" if self.v3 else "")
        self.ui.stage("firmware", "active", "Downloading %s…" % label)
        data = self.channel.fetch(uf2)
        check_uf2(data, uf2, "RP2350" if self.v3 else "RP2040")
        self.copy_uf2("firmware", data, label, uf2.rsplit("/", 1)[-1])
        self.ui.stage("firmware", "done", "Firmware %s installed." % m["fw_version"])

    def slots(self):
        return (self.manifest.get("v3") or {}).get("slots") or [] if self.v3 else []

    def sizes(self, paths):
        """{path: size, or -1 if missing} on the Pico."""
        return json.loads(self.raw.exec(
            "import json\nr={}\nfor p in %r:\n try: r[p]=os.stat(p)[6]\n except OSError: r[p]=-1\n"
            "print(json.dumps(r))" % list(paths)))

    def upload_slots(self):
        """The v3 card's slot files: 0 and 1 always (our ROMs, new with each
        release), the others only where the card has no such file, so a ROM or
        cartridge the user put in a slot is never overwritten."""
        slots = self.slots()
        self.raw.make_dirs("/slots")
        have = self.sizes("/" + s["path"] for s in slots)
        todo = [s for s in slots if s.get("always") or have["/" + s["path"]] < 0]
        for s in slots:
            if s not in todo:
                self.ui.log("  · %s: already on the card, kept" % s["path"])
        for i, s in enumerate(todo):
            self.ui.stage_msg("files", "Writing ROM slot %s (%d/%d)…" % (s["slot"], i + 1, len(todo)))
            data = self.channel.fetch(s["file"])
            self.raw.write_file("/" + s["path"], data)
            self.ui.log("  ✓ %s (%d bytes)" % (s["path"], len(data)), "ok")
        return len(todo)

    def files(self):
        ui = self.ui
        ui.stage("files", "active", "")
        self.wait_port("files", 45)              # first boot after a wipe formats the filesystem
        ui.stage_msg("files", "Entering the REPL…")
        self.enter_raw()
        slots = 0
        if self.v3:
            ui.stage_msg("files", "Checking for stray files…")
            if self.raw.exec(RMTREE).strip() == "1":
                ui.log("Removed a stray /TS folder.", "warn")
            slots = self.upload_slots()
        files = self.manifest["files"]
        total = sum(f.get("size", 0) for f in files) or 1
        done = 0
        for i, f in enumerate(files):
            path = f["path"]
            ui.stage_msg("files", "Writing %s (%d/%d)…" % (path, i + 1, len(files)))
            data = self.channel.fetch("pico/" + path)
            if "/" in path:
                self.raw.make_dirs("/" + path.rsplit("/", 1)[0])
            self.raw.write_file("/" + path, data,
                                progress=lambda n, d=done: ui.progress("files", (d + n) / total))
            ui.log("  ✓ %s (%d bytes)" % (path, len(data)), "ok")
            done += f.get("size", len(data))
        ui.stage_msg("files", "Verifying…")
        bad = self.verify_files()
        if bad:
            raise RuntimeError("%d file(s) didn’t verify — see the log" % bad)
        ui.stage_msg("files", "Restarting the firmware…")
        self.raw.exec_no_reply("import machine\nmachine.reset()")
        self.close_port()
        ui.stage("files", "done", "All %d files%s written and verified. The Pico restarted." % (
            len(files), " and %d ROM slot(s)" % slots if self.v3 else ""))

    def verify_files(self):
        files = self.manifest["files"]
        want = files + self.slots()              # kept slots are 32K too
        got = self.sizes("/" + f["path"] for f in want)
        bad = 0
        for f in want:
            n = got.get("/" + f["path"], -1)
            if n < 0:
                self.ui.log("  ✗ missing: %s" % f["path"], "error"); bad += 1
            elif n != f["size"]:
                self.ui.log("  ✗ size mismatch: %s (device %d, expected %d)" % (f["path"], n, f["size"]),
                            "error"); bad += 1
        if not bad:
            self.ui.log("Verify passed: %d files%s match." % (
                len(files), " and %d ROM slots" % (len(want) - len(files)) if len(want) > len(files) else ""),
                "ok")
        return bad

    # --- the modem ---------------------------------------------------------
    def zimodem(self):
        """The channel's Zimodem for the v3 card ({file, size, version}), or None."""
        return (self.manifest.get("v3") or {}).get("zimodem") if self.manifest else None

    def esp_version(self):
        return self.enter_raw().exec(ESP_PROBE, 15).strip()

    def install_modem(self):
        """Zimodem on the v3 card's ESP32-C3: checked, and written when it is
        missing or older than the channel's. The card runs the relay; this end
        talks to the ESP32's ROM loader through it (espflash.py). Only the
        image's own area is written, so Zimodem's WiFi and phonebook stay."""
        ui, z = self.ui, self.zimodem()
        ui.stage("modem", "active", "")
        self.wait_port("modem", 45)
        ui.stage_msg("modem", "Checking the modem module…")
        have = self.esp_version()
        ui.log("The modem module has no Zimodem." if have == "-" else
               "The modem module has Zimodem %s." % have)
        if have != "-" and z.get("version") and ver_cmp(have, z["version"]) >= 0:
            self.raw.restart_firmware()
            self.close_port()
            ui.stage("modem", "done", "Zimodem %s is already installed." % have)
            return
        ui.stage_msg("modem", "Downloading Zimodem %s…" % z.get("version", ""))
        image = self.channel.fetch(z["file"])

        # The relay runs until this end has been quiet for 4 s; meanwhile the
        # port carries the loader's SLIP frames, byte for byte.
        ui.stage_msg("modem", "Starting the modem module’s loader…")
        p = self.port
        p.write(ESP_RELAY.encode() + b"\x04")
        p.read_until(b"OK", 5)
        esp = espflash.EspRomLoader(_LoaderIO(p))
        esp.sync()
        esp.attach()
        ui.stage_msg("modem", "Writing Zimodem %s (%d KB)…" % (z.get("version", ""), len(image) // 1024))
        _, blocks, md5 = esp.flash(image, 0, lambda f: ui.progress("modem", f))
        ui.log("  ✓ zimodem: %d bytes, %d blocks, MD5 %s verified" % (len(image), blocks, md5), "ok")

        # The relay ends 4 s after the last byte, and the raw REPL carries on.
        ui.stage_msg("modem", "Checking it starts…")
        p.buf = b""
        p.read_until(b"\x04", 15)                    # the relay's output: "RELAY n"
        err = p.read_until(b"\x04", 5)[:-1]
        p.read_until(b">", 5)
        if err.strip():
            raise RuntimeError(err.decode(errors="replace").strip())
        now = self.esp_version()
        if now == "-":
            raise RuntimeError("Zimodem was written but doesn’t answer")
        self.raw.restart_firmware()
        self.close_port()
        ui.stage("modem", "done", "Zimodem %s installed and checked." % now)

    # --- the whole run -----------------------------------------------------
    def downgrade_text(self, wipe):
        """A warning before installing an older MicroPython than the Pico runs,
        or None. The older one can't read the newer one's filesystem, so its
        first boot formats the flash."""
        if not self.installed or not self.installed.get("mp"):
            return None
        uf2, target = self.image()
        if not target and uf2:
            try:
                target = uf2_micropython(self.channel.fetch(uf2))
            except Exception:
                target = None
        if not target or ver_cmp(target, self.installed["mp"]) >= 0:
            return None
        return ("This Pico runs MicroPython v%s; firmware %s is built on v%s, an older one. "
                "That older MicroPython can't read the newer one's filesystem, so its first boot "
                "erases the Pico's files — the activity log and anything you added included. "
                "The updater then writes this firmware's own files again.%s\n\nContinue?" % (
                    self.installed["mp"], self.manifest["fw_version"], target,
                    "" if wipe else "\n\n“Keep what’s on the Pico” can’t be honoured for this install."))

    def run(self, wipe, rom, modem=True):
        current = "bootsel"
        try:
            self.enter_bootsel()
            if self.v3:
                wipe = rom = False
                self.ui.stage("wipe", "skipped", "Never on the v3 card: it would erase your ROM slots.")
                self.ui.stage("rom", "skipped", "Not on the v3 card: its ROMs are slot files, "
                                                "copied with the files.")
            if wipe:
                current = "wipe"
                self.wipe()
            if rom:
                current = "rom"
                self.rom_update()
            current = "firmware"
            self.firmware()
            current = "files"
            self.files()
            z = self.zimodem() if self.v3 else None
            if self.v3 and z and modem:
                current = "modem"
                self.install_modem()
            else:
                self.ui.stage("modem", "skipped", "Only on the v3 card." if not self.v3 else
                              "This channel has no modem firmware." if not z else "Not this time.")
            self.ui.log("All done.", "ok")
            return True
        except Stop:
            self.ui.stage(current, "error", "Stopped.")
            self.ui.log("Stopped.", "warn")
        except Exception as e:
            self.ui.stage(current, "error", str(e))
            self.ui.log("%s: %s" % (current, e), "error")
            self.ui.log("You can press Start again: every step can be repeated, and a Pico stuck "
                        "in BOOTSEL mode is always recoverable.", "warn")
        finally:
            self.close_port()
        return False
