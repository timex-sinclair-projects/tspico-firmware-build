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
import sys
import time
import urllib.request

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
STAGES = ("connect", "bootsel", "wipe", "rom", "firmware", "files")


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
# The RPI-RP2 drive
# ---------------------------------------------------------------------------
def _is_rp2(root):
    try:
        with open(os.path.join(root, "INFO_UF2.TXT"), "r", errors="replace") as f:
            return "RPI-RP2" in f.read()
    except OSError:
        return False


def find_drive():
    """The mounted RPI-RP2 drive's root, or None."""
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
            if _is_rp2(root):
                return root
        return None
    cands = ["/Volumes/RPI-RP2"]
    for base in ("/media", "/run/media"):
        try:
            for user in os.listdir(base):
                cands.append(os.path.join(base, user, "RPI-RP2"))
        except OSError:
            pass
    for c in cands:
        if _is_rp2(c):
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
        self.nuke = None                         # flash_nuke.uf2, from the bundle

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
        return rom_behind(self.installed, self.manifest)

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
            raw.exec("import sys,os")
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
        self.ui.stage_msg(name, "Waiting for the RPI-RP2 drive…")
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            d = find_drive()
            if d:
                return d
            time.sleep(0.5)
        raise RuntimeError("the RPI-RP2 drive didn't appear. Hold BOOTSEL on the Pico while "
                           "plugging in USB, then press Start again.")

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
        self.ui.stage("bootsel", "done", "In BOOTSEL mode — the RPI-RP2 drive is %s." % d)

    def wipe(self):
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
        self.ui.stage("firmware", "active", "Downloading firmware %s…" % m["fw_version"])
        data = self.channel.fetch(m["uf2"])
        self.copy_uf2("firmware", data, "firmware %s" % m["fw_version"], "firmware.uf2")
        self.ui.stage("firmware", "done", "Firmware %s installed." % m["fw_version"])

    def files(self):
        ui = self.ui
        ui.stage("files", "active", "")
        self.wait_port("files", 45)              # first boot after a wipe formats the filesystem
        ui.stage_msg("files", "Entering the REPL…")
        self.enter_raw()
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
        ui.stage("files", "done", "All %d files written and verified. The Pico restarted." % len(files))

    def verify_files(self):
        paths = ["/" + f["path"] for f in self.manifest["files"]]
        got = json.loads(self.raw.exec(
            "import json\nr={}\nfor p in %r:\n try: r[p]=os.stat(p)[6]\n except OSError: r[p]=-1\n"
            "print(json.dumps(r))" % paths))
        bad = 0
        for f in self.manifest["files"]:
            n = got.get("/" + f["path"], -1)
            if n < 0:
                self.ui.log("  ✗ missing: %s" % f["path"], "error"); bad += 1
            elif n != f["size"]:
                self.ui.log("  ✗ size mismatch: %s (device %d, expected %d)" % (f["path"], n, f["size"]),
                            "error"); bad += 1
        if not bad:
            self.ui.log("Verify passed: %d files match." % len(paths), "ok")
        return bad

    # --- the whole run -----------------------------------------------------
    def downgrade_text(self, wipe):
        """A warning before installing an older MicroPython than the Pico runs,
        or None. The older one can't read the newer one's filesystem, so its
        first boot formats the flash."""
        if not self.installed or not self.installed.get("mp"):
            return None
        target = self.manifest.get("mp_version")
        if not target:
            try:
                target = uf2_micropython(self.channel.fetch(self.manifest["uf2"]))
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

    def run(self, wipe, rom):
        current = "bootsel"
        try:
            self.enter_bootsel()
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
