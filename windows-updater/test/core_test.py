"""Host test for core.py: a whole run against a fake Pico.

The fake speaks the raw REPL and runs the code it is sent with CPython over a
temporary directory standing in for the Pico's flash, so the version read,
the file copy and the verify run for real. The boot drive (RPI-RP2, or RP2350
for a fake v3 card) is another temporary directory: copying a UF2 onto it
"reboots" the fake into whatever that UF2 is (firmware, the ROM updater, the
flash eraser). The ROM updater replays a recorded run's UPG lines. On the
fake v3 card, the modem probe answers with the fake ESP32's Zimodem version,
and the relay hands the port to a fake ESP32-C3 ROM loader (FakeRom), which
checks every command as the ROM does and inflates the image into its flash;
espflash.py is also tested against it alone.

    python3 windows-updater/test/core_test.py
"""

import binascii
import io
import json
import os
import shutil
import struct
import sys
import tempfile
import types
import contextlib
import hashlib
import importlib
import random
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import core  # noqa: E402
import espflash  # noqa: E402

UPG = [
    {"event": "waiting"},
    {"event": "tape"},
    {"event": "updater"},
    {"event": "status", "code": "P", "arg": 1},
    *[{"event": "status", "code": "W", "arg": i} for i in range(128)],
    {"event": "status", "code": "V", "arg": 0},
    {"event": "status", "code": "P", "arg": 0},
    *[{"event": "status", "code": "W", "arg": i} for i in range(64)],
    {"event": "status", "code": "V", "arg": 0},
    {"event": "status", "code": "D", "arg": 0},
]


class FakeRom:
    """The ESP32-C3's ROM loader: SLIP in, every command checked as the ROM
    checks it, the blocks inflated into a model 4 MB flash, MD5 from it.
    Replies come back in random splits, so frames are reassembled across reads."""

    def __init__(self, deaf_syncs=2, bad_seq_at=-1):
        self.flash = bytearray(b"\x5A" * (4 * 1024 * 1024))
        self.out = bytearray()
        self.buf = bytearray()
        self.deaf = deaf_syncs                   # the first SYNCs go unanswered, as a waking loader's do
        self.bad_seq_at = bad_seq_at
        self.attached = False
        self.md5_done = False
        self.erase = 0

    def write(self, data, chunk=None):
        self.buf += data
        while True:
            s = self.buf.find(0xC0)
            e = self.buf.find(0xC0, s + 1) if s >= 0 else -1
            if s < 0 or e < 0:
                break
            raw, self.buf = bytes(self.buf[s + 1:e]), self.buf[e:]
            if not raw:
                continue
            f, i = bytearray(), 0
            while i < len(raw):
                if raw[i] == 0xDB:
                    i += 1
                    f.append(0xC0 if raw[i] == 0xDC else 0xDB)
                else:
                    f.append(raw[i])
                i += 1
            self.handle(bytes(f))

    def read(self, timeout=0):
        if not self.out:
            return b""
        n = random.randint(1, min(40, len(self.out)))
        d, self.out = bytes(self.out[:n]), self.out[n:]
        return d

    def reply(self, op, data=b"", status=0, error=0):
        body = data + bytes([status, error, 0, 0])
        self.out += espflash.slip_encode(struct.pack("<BBHI", 1, op, len(body), 0) + body)

    def handle(self, f):
        assert f[0] == 0, "a request starts 00"
        op, size, chk = struct.unpack_from("<BHI", f, 1)
        d = f[8:8 + size]
        assert len(d) == size, "the size field matches"
        if op == espflash.SYNC:
            if self.deaf > 0:
                self.deaf -= 1
                return
            for _ in range(8):                   # the ROM answers a SYNC several times
                self.reply(op)
        elif op == espflash.SPI_ATTACH:
            assert size == 8
            self.attached = True
            self.reply(op)
        elif op == espflash.SPI_SET_PARAMS:
            assert struct.unpack_from("<I", d, 4)[0] == 4 * 1024 * 1024
            self.reply(op)
        elif op == espflash.FLASH_DEFL_BEGIN:
            assert self.attached, "SPI_ATTACH before BEGIN"
            assert size == 20, "five words: the C3 ROM wants the encrypted flag"
            self.erase, self.blocks, self.bsize, self.offset, _ = struct.unpack("<5I", d)
            assert self.erase % espflash.FLASH_WRITE_SIZE == 0, "erase size in whole blocks"
            self.flash[self.offset:self.offset + self.erase] = b"\xFF" * self.erase
            self.comp, self.seq = bytearray(), 0
            self.reply(op)
        elif op == espflash.FLASH_DEFL_DATA:
            n, seq = struct.unpack_from("<II", d)
            block = d[16:16 + n]
            if espflash.checksum(block) != chk:
                return self.reply(op, b"", 1, 0x07)
            if seq != self.seq or seq == self.bad_seq_at:
                return self.reply(op, b"", 1, 0x09)
            assert n <= self.bsize
            self.comp += block
            self.seq += 1
            if self.seq == self.blocks:          # inflate into the flash
                img = zlib.decompress(bytes(self.comp))
                assert len(img) <= self.erase, "fits the erased region"
                self.flash[self.offset:self.offset + len(img)] = img
            self.reply(op)
        elif op == espflash.SPI_FLASH_MD5:
            a, n = struct.unpack_from("<II", d)
            self.md5_done = True
            self.reply(op, hashlib.md5(bytes(self.flash[a:a + n])).hexdigest().encode())
        else:
            self.reply(op, b"", 1, 0x05)


# A stand-in for zimodem-v3.bin: 300K that deflates to ~150 blocks, as code does.
_rng = random.Random(3068)
ZIMODEM = bytes(_rng.randrange(16) for _ in range(300 * 1024))


class Pico:
    """The board: its flash (a directory), what it's running, its USB face."""

    def __init__(self, root, fw="2.1.2", mp="1.20.0", v3=False, zimodem=None):
        self.v3 = v3
        self.zimodem = zimodem                   # the ESP32's Zimodem version, None: blank
        self.rom = None                          # the ESP32's loader, once the relay has run
        self.restarted = 0                       # soft resets that ran main.py
        self.flash = os.path.join(root, "flash")
        self.drive = os.path.join(root, "RP2350" if v3 else "RPI-RP2")
        os.makedirs(self.flash)
        os.makedirs(self.drive)
        self.fw, self.mp = fw, mp
        self.mode = "firmware"                   # firmware | upgrade | bootsel
        self.written = []                        # UF2 names, in order
        self.away = 0                            # polls the drive stays gone after a reboot
        with open(os.path.join(self.flash, "config.ini"), "w") as f:
            json.dump({"FW_VERSION": "1.00"}, f)  # stale, as on a real 2.x board
        with open(os.path.join(self.flash, "activity.log"), "w") as f:
            f.write("old")

    def bootsel(self):
        self.mode = "bootsel"
        with open(os.path.join(self.drive, "INFO_UF2.TXT"), "w") as f:
            f.write("UF2 Bootloader v1.0\nModel: Raspberry Pi RP2350\nBoard-ID: RP2350\n" if self.v3
                    else "UF2 Bootloader v3.0\nModel: Raspberry Pi RP2\nBoard-ID: RPI-RP2\n")

    def took(self, name):
        """A UF2 landed on the drive: boot into it."""
        self.written.append(name)
        self.away = 3
        for n in os.listdir(self.drive):
            os.remove(os.path.join(self.drive, n))
        if name == "flash_nuke.uf2":
            shutil.rmtree(self.flash)
            os.makedirs(self.flash)
            self.fw = None
            self.bootsel()
        elif name == "upgrade.uf2":
            self.mode, self.fw = "upgrade", None
        else:
            self.mode, self.fw, self.mp = "firmware", "2.2.1", "1.29.0"


def user_slot(flash):
    """A cartridge the user put in slot 2, and a stray /TS folder."""
    os.makedirs(os.path.join(flash, "slots"))
    with open(os.path.join(flash, "slots", "F02.bin"), "wb") as f:
        f.write(b"mine" * 8192)
    os.makedirs(os.path.join(flash, "TS", "sub"))
    with open(os.path.join(flash, "TS", "sub", "x.py"), "w") as f:
        f.write("x")


class FakePort:
    """core.Port's interface over the fake Pico."""

    def __init__(self, pico):
        if pico.mode == "bootsel":
            raise OSError("no such port")
        self.pico = pico
        self.out = b"UPG " + b"\nUPG ".join(json.dumps(e).encode() for e in UPG) + b"\n" \
            if pico.mode == "upgrade" else b"TLM ...\n"
        self.buf = b""
        self.raw = False
        self.code = b""
        self.ns = {}
        self.relay = None                        # the ESP32's loader, while the relay runs

    def close(self):
        pass

    def write(self, data, chunk=256):
        if self.pico.mode == "bootsel":
            raise core.Gone("gone")
        if self.relay:
            return self.relay.write(data)
        for c in data:
            b = bytes([c])
            if not self.raw:
                if b == b"\x03":
                    self.out += b"\r\nMicroPython\r\n>>> "
                elif b == b"\x01":
                    self.raw = True
                    self.out += b"raw REPL; CTRL-B to exit\r\n>"
                elif b == b"\x04":              # soft reset from the friendly REPL: main.py runs
                    self.pico.restarted += 1
            elif b == b"\x02":
                self.raw = False
                self.out += b">\r\nMicroPython\r\n>>> "
            elif b == b"\x04":
                self.run(self.code.decode())
                self.code = b""
            else:
                self.code += b
        if self.pico.mode == "bootsel":
            raise core.Gone("rebooted")

    def run(self, code):
        pico = self.pico
        if "esp_relay" in code:                  # the port is the ESP32's loader's now
            pico.rom = self.relay = FakeRom()
            self.out += b"OK"
            return
        if "ATI" in code:                        # the probe
            self.out += b"OK" + (pico.zimodem or "-").encode() + b"\r\n\x04\x04>"
            return
        out, err = io.StringIO(), ""
        fs = pico.flash

        def real(p):
            return os.path.join(fs, p.lstrip("/"))

        fake_os = types.SimpleNamespace(
            uname=lambda: types.SimpleNamespace(
                sysname="rp2", release=pico.mp,
                machine="TS-Pico v3 with RP2350" if pico.v3 else "Raspberry Pi Pico with RP2040"),
            mkdir=lambda p: os.mkdir(real(p)),
            stat=lambda p: os.stat(real(p)),
            listdir=lambda p: os.listdir(real(p)),
            rmdir=lambda p: os.rmdir(real(p)),
            remove=lambda p: os.remove(real(p)),
            chdir=lambda p: None,
        )
        mods = {}
        if pico.fw:
            mods["TS.tspico"] = types.SimpleNamespace(FW_VERSION=pico.fw)
        machine = types.SimpleNamespace(bootloader=pico.bootsel, reset=lambda: None)
        fake_sys = types.SimpleNamespace(modules=mods, path=["", ".frozen", "/lib"])

        def imp(name, *a, **k):
            return {"os": fake_os, "sys": fake_sys, "json": json, "binascii": binascii,
                    "machine": machine}[name]

        g = self.ns
        g["__builtins__"] = dict(__builtins__.__dict__ if hasattr(__builtins__, "__dict__")
                                 else __builtins__, __import__=imp,
                                 open=lambda p, m="r": open(real(p), m))
        try:
            with contextlib.redirect_stdout(out):
                exec(code, g)
        except Exception as e:
            err = "Traceback\n%s: %s\n" % (type(e).__name__, e)
        self.out += b"OK" + out.getvalue().encode() + b"\x04" + err.encode() + b"\x04>"

    def read_some(self):
        if self.pico.mode == "bootsel" and not self.out:
            raise core.Gone("gone")
        if self.relay and not self.out:
            d = self.relay.read()
            if d or not self.relay.md5_done:
                return d
            # The host has gone quiet: the relay ends, the ESP32 restarts.
            rom, self.relay = self.relay, None
            if bytes(rom.flash[:len(ZIMODEM)]) == ZIMODEM:
                self.pico.zimodem = "4.0.4"
            self.out += b"RELAY 1\r\n\x04\x04>"
        d, self.out = self.out[:64], self.out[64:]
        return d

    read_until = core.Port.read_until

    def flush_input(self):
        self.out = b""
        self.buf = b""


class TestUi(core.Ui):
    def __init__(self):
        self.lines, self.states, self.asked = [], {}, []
        self.pending = None

    def log(self, msg, kind=""):
        self.lines.append((kind, msg))

    def stage(self, name, state, msg=None):
        self.states[name] = (state, msg)

    def offer(self, name, choices):
        self.asked.append([c[0] for c in choices])
        self.pending = choices[0][1]

    def take(self, timeout=None):
        v, self.pending = self.pending, None
        return v


def uf2(family, blocks=2):
    """A UF2 whose blocks name a chip family."""
    blk = struct.pack("<IIIIIIII", 0x0A324655, 0x9E5D5157, 0x2000, 0x10000000, 256, 0, blocks, family)
    return (blk + bytes(512 - len(blk))) * blocks


SLOTS = {"slots/F00.bin": b"\x00" * 32768, "slots/F01.bin": b"\x01" * 32768,
         "slots/F02.bin": b"\x02" * 32768}


def channel_dir(root, v3_family=core.UF2_FAMILY["RP2350"]):
    """A published channel, as build-payload.sh lays it out."""
    ch = os.path.join(root, "site", "release")
    os.makedirs(os.path.join(ch, "pico", "assets"))
    os.makedirs(os.path.join(ch, "slots"))
    files = {"main.py": b"import TS\n", "config.ini": b'{"VERBOSE": 0}\n',
             "assets/nofile.tap": bytes(range(256)) * 9 + b"'\"\\\x00"}
    for p, d in files.items():
        with open(os.path.join(ch, "pico", p), "wb") as f:
            f.write(d)
    for n, d in (("firmware.uf2", uf2(core.UF2_FAMILY["RP2040"])),
                 ("upgrade.uf2", uf2(core.UF2_FAMILY["RP2040"])),
                 ("firmware-v3.uf2", uf2(v3_family))):
        with open(os.path.join(ch, n), "wb") as f:
            f.write(d)
    for p, d in SLOTS.items():
        with open(os.path.join(ch, p), "wb") as f:
            f.write(d)
    with open(os.path.join(ch, "zimodem-v3.bin"), "wb") as f:
        f.write(ZIMODEM)
    m = {"channel": "release", "tag": "v2.2.1", "fw_version": "2.2.1", "mp_version": "1.29.0",
         "rom_version": "2.2", "uf2": "firmware.uf2", "upgrade_uf2": "upgrade.uf2",
         "files": [{"path": p, "size": len(d)} for p, d in sorted(files.items())],
         "v3": {"uf2": "firmware-v3.uf2", "mp_version": "1.29.0",
                "slots": [{"file": p, "path": p, "slot": int(p[-6:-4]), "size": len(d),
                           "always": p[-6:-4] in ("00", "01")} for p, d in sorted(SLOTS.items())],
                "zimodem": {"file": "zimodem-v3.bin", "size": len(ZIMODEM), "version": "4.0.4"}}}
    with open(os.path.join(ch, "manifest.json"), "w") as f:
        json.dump(m, f)
    return os.path.join(root, "site"), files


def run(fw, wipe, rom, v3=False, by_hand=False, setup=None, zimodem=None, modem=True, **chan):
    """A whole run. by_hand: the Pico is already in BOOTSEL, no Connect.
    setup(flash) puts files on the fake's flash first."""
    importlib.reload(core)
    root = tempfile.mkdtemp()
    try:
        pico = Pico(root, fw=fw, v3=v3, zimodem=zimodem)
        if setup:
            setup(pico.flash)
        if by_hand:
            pico.bootsel()
        site, files = channel_dir(root, **chan)
        core.Port = lambda dev: FakePort(pico)
        core.pico_ports = lambda: [] if pico.mode == "bootsel" else ["COM7"]
        def find_drive():
            if pico.away:
                pico.away -= 1
                return None
            return pico.drive if pico.mode == "bootsel" else None
        core.find_drive = find_drive
        real_write = core.write_uf2

        def write_uf2(drive, data, name, progress=None):
            real_write(drive, data, name, progress)
            pico.took(name)
        core.write_uf2 = write_uf2
        ui = TestUi()
        up = core.Updater(ui, site)
        up.nuke = b"nuke"
        up.load_channel("release")
        inst = None if by_hand else up.connect()
        ok = up.run(wipe, rom, modem)
        if not ok and not chan:
            for k, line in ui.lines:
                print("   log:", k, line)

        def read(p):
            try:
                with open(os.path.join(pico.flash, p), "rb") as f:
                    return f.read()
            except OSError:
                return None
        pico.got = {p: read(p) for p in list(files) + list(SLOTS)}
        pico.ts_left = os.path.exists(os.path.join(pico.flash, "TS"))
        return ok, ui, pico, inst, up, all(pico.got[p] == d for p, d in files.items())
    finally:
        shutil.rmtree(root)


def check(name, cond):
    print("%s  %s" % ("PASS" if cond else "FAIL", name))
    return cond


def main():
    results = []

    # Unit: the version rules match app.js.
    results.append(check("ver_of", core.ver_of("2.2.1") == (2, 2) and core.ver_of("x") is None))
    results.append(check("major_of", core.major_of("1.1 (no version in config.ini)") == 1.1))
    results.append(check("ver_cmp", core.ver_cmp("1.20.0", "1.29.0") < 0 and core.ver_cmp("1.29", "1.29.0") == 0))
    results.append(check("ver_cmp: our Zimodem 4.0.3.1 is newer than 4.0.3",
                         core.ver_cmp("4.0.3", "4.0.3.1") < 0 and core.ver_cmp("4.0.3.1", "4.0.3.1") == 0))
    m = {"rom_version": "2.2", "fw_version": "2.2.1"}
    results.append(check("rom_behind: 2.1 board", core.rom_behind({"ver": (2, 1), "from1x": False}, m)))
    results.append(check("rom_behind: 2.2 board", not core.rom_behind({"ver": (2, 2), "from1x": False}, m)))
    results.append(check("rom_behind: unknown", core.rom_behind({"ver": None, "from1x": False}, m)))
    blk = bytearray(512 * 2)
    blk[32:32 + 22] = b"xxMicroPython v1.20.0 "
    results.append(check("uf2_micropython", core.uf2_micropython(bytes(blk)) == "1.20.0"))

    # A whole run: a 2.1.2 board, wipe + ROM + firmware + files.
    ok, ui, pico, inst, up, same = run("2.1.2", wipe=True, rom=True)
    results.append(check("installed version read from the running module", inst["fw"] == "2.1.2"))
    results.append(check("ROM step wanted for a 2.1 board", up.rom_behind()))
    results.append(check("full run succeeds", ok))
    results.append(check("UF2s in order", pico.written == ["flash_nuke.uf2", "upgrade.uf2", "firmware.uf2"]))
    results.append(check("files copied byte for byte", same))
    results.append(check("asked to switch the 2068 off", ["The 2068 is off — continue", "Stop"] in ui.asked))
    results.append(check("slots verified", sum("verified" in m for _, m in ui.lines) == 2))
    results.append(check("every stage done, the modem skipped",
                         all(ui.states[s][0] == "done" for s in core.STAGES if s != "modem")
                         and ui.states["modem"] == ("skipped", "Only on the v3 card.")))

    # No wipe, no ROM: old files stay.
    ok, ui, pico, inst, up, same = run("2.2.1", wipe=False, rom=False)
    results.append(check("firmware-only run succeeds", ok and same))
    results.append(check("firmware-only run writes one UF2", pico.written == ["firmware.uf2"]))

    # Unit: the boot drive and the UF2 family check.
    d = tempfile.mkdtemp()
    try:
        info = os.path.join(d, "INFO_UF2.TXT")
        with open(info, "w") as f:
            f.write("Board-ID: RP2350\n")
        a = core.drive_chip(d)
        with open(info, "w") as f:
            f.write("Board-ID: RPI-RP2\n")
        results.append(check("drive_chip", a == "RP2350" and core.drive_chip(d) == "RP2040"
                             and core.drive_chip(os.path.join(d, "nope")) is None))
    finally:
        shutil.rmtree(d)
    core.check_uf2(uf2(core.UF2_FAMILY["RP2350"]), "x", "RP2350")
    try:
        core.check_uf2(uf2(core.UF2_FAMILY["RP2040"]), "x", "RP2350")
        refused = False
    except RuntimeError:
        refused = True
    results.append(check("check_uf2 refuses the other chip's UF2", refused))

    # The v3 card: no wipe or ROM even if asked, its own UF2, the slots.
    ok, ui, pico, inst, up, same = run("2.3", wipe=True, rom=True, v3=True, setup=user_slot)
    results.append(check("v3: detected from os.uname", up.v3 and not up.rom_behind()))
    results.append(check("v3: run succeeds", ok and same))
    results.append(check("v3: only the v3 UF2", pico.written == ["firmware-v3.uf2"]))
    results.append(check("v3: wipe and ROM skipped", ui.states["wipe"][0] == "skipped"
                         and ui.states["rom"][0] == "skipped"))
    results.append(check("v3: slots 0 and 1 written", pico.got["slots/F00.bin"] == SLOTS["slots/F00.bin"]
                         and pico.got["slots/F01.bin"] == SLOTS["slots/F01.bin"]))
    results.append(check("v3: the user's slot 2 kept", pico.got["slots/F02.bin"] == b"mine" * 8192))
    results.append(check("v3: stray /TS removed", not pico.ts_left))

    # A v3 card in BOOTSEL by hand: known from the RP2350 drive; a missing slot is written.
    ok, ui, pico, inst, up, same = run(None, wipe=True, rom=False, v3=True, by_hand=True)
    results.append(check("v3 by hand: detected from the drive", ok and up.v3
                         and pico.written == ["firmware-v3.uf2"]))
    results.append(check("v3 by hand: a missing slot 2 is written",
                         pico.got["slots/F02.bin"] == SLOTS["slots/F02.bin"]))

    # A channel whose v3 image is an RP2040 build: refused before copying.
    ok, ui, pico, inst, up, same = run("2.3", wipe=False, rom=False, v3=True,
                                       v3_family=core.UF2_FAMILY["RP2040"])
    results.append(check("v3: an RP2040 image is refused", not ok and pico.written == []
                         and "not an RP2350 UF2" in (ui.states["firmware"][1] or "")))

    # The modem: a blank ESP32 gets Zimodem through the relay; a current one is
    # left alone; unticked, nothing is asked of it.
    ok, ui, pico, inst, up, same = run("2.3", wipe=False, rom=False, v3=True)
    results.append(check("v3 modem: blank ESP32 written, verified, checked",
                         ok and pico.zimodem == "4.0.4" and ui.states["modem"][0] == "done"
                         and pico.restarted == 1
                         and any("MD5" in m and "verified" in m for _, m in ui.lines)))
    results.append(check("v3 modem: only the image's blocks erased (the SPIFFS kept)",
                         pico.rom.erase == -(-len(ZIMODEM) // 1024) * 1024
                         and pico.rom.flash[pico.rom.erase] == 0x5A))
    ok, ui, pico, inst, up, same = run("2.3", wipe=False, rom=False, v3=True, zimodem="4.0.4")
    results.append(check("v3 modem: a current Zimodem is kept, the firmware restarted",
                         ok and pico.rom is None and pico.restarted == 1
                         and "already installed" in ui.states["modem"][1]))
    ok, ui, pico, inst, up, same = run("2.3", wipe=False, rom=False, v3=True, modem=False)
    results.append(check("v3 modem: unticked, skipped", ok and pico.rom is None
                         and ui.states["modem"] == ("skipped", "Not this time.")))

    # espflash.py alone, against the fake loader.
    class Io:
        def __init__(self, rom):
            self.rom = rom
        def write(self, d):
            self.rom.write(d)
        def read(self, timeout):
            return self.rom.read()

    rom = FakeRom(deaf_syncs=3)
    esp = espflash.EspRomLoader(Io(rom))
    esp.sync()
    esp.attach()
    steps = []
    comp, blocks, md5 = esp.flash(ZIMODEM, 0, steps.append)
    results.append(check("espflash: deaf SYNCs, then the image written and its MD5 matched",
                         bytes(rom.flash[:len(ZIMODEM)]) == ZIMODEM and steps[-1] == 1
                         and steps == sorted(steps) and md5 == hashlib.md5(ZIMODEM).hexdigest()))
    results.append(check("espflash: SLIP escapes C0 and DB",
                         espflash.slip_encode(bytes([1, 0xC0, 2, 0xDB, 3])) ==
                         bytes([0xC0, 1, 0xDB, 0xDC, 2, 0xDB, 0xDD, 3, 0xC0])))

    def fails(fn, what):
        try:
            fn()
        except espflash.EspError as e:
            return what in str(e)
        return False
    rom = FakeRom(deaf_syncs=0, bad_seq_at=0)
    esp = espflash.EspRomLoader(Io(rom))
    esp.sync()
    esp.attach()
    results.append(check("espflash: a refused block fails the write",
                         fails(lambda: esp.flash(ZIMODEM[:64 * 1024]), "11h failed")))
    rom = FakeRom(deaf_syncs=0)
    esp = espflash.EspRomLoader(Io(rom))
    esp.sync()
    esp.attach()
    real_handle = rom.handle

    def corrupt(f):                              # a byte goes bad after writing
        if f[1] == espflash.SPI_FLASH_MD5:
            rom.flash[3] ^= 0xFF
        real_handle(f)
    rom.handle = corrupt
    results.append(check("espflash: an MD5 that differs fails the write",
                         fails(lambda: esp.flash(ZIMODEM[:8 * 1024]), "MD5")))
    esp = espflash.EspRomLoader(types.SimpleNamespace(write=lambda d: None, read=lambda t: b""))
    results.append(check("espflash: no loader at all, sync gives up",
                         fails(lambda: esp.sync(3), "does not answer")))

    print("%d/%d passed" % (sum(results), len(results)))
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
