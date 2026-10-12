#!/usr/bin/env python3
"""Install Zimodem on the v3 card's ESP32-C3, through the card's own USB.

The ESP32-C3 modules come blank. This puts the ESP32 into its ROM's serial
loader, joins the card's USB port to its UART (tsbus.esp_relay, byte for
byte), and runs esptool through the card as if the ESP32 were plugged in
directly. Then it restarts the ESP32 normally, checks that Zimodem answers,
and restarts the TS-Pico firmware. The web updater does the same in the
browser; this is the developer's way, and how the relay was proven.

    pip install esptool pyserial
    python3 tools/zimodem-install.py [--port PORT] [--image zimodem-v3.bin]

The image defaults to esp32/zimodem/out/zimodem-v3.bin (esp32/zimodem/build.sh,
or the release's zimodem-v3.bin). Writing it leaves Zimodem's settings (WiFi,
phonebook) as they were. The 2068 can stay on: core 1 keeps serving it, but
the TS-Pico's commands answer nothing until the firmware restarts at the end.
"""

import argparse
import glob
import os
import subprocess
import sys
import time

import serial

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
IMAGE = os.path.join(REPO, "esp32", "zimodem", "out", "zimodem-v3.bin")

# Run on the card, in the raw REPL. The relay returns once the host has been
# quiet for 4 s after its first byte (esptool has finished), or sent nothing
# for 60 s.
RELAY = """
import tsbus, time, micropython
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
print('RELAY', r)
"""

# After the install: Zimodem's banner, read with the modem off.
CHECK = """
import tsbus, time
from machine import UART, Pin
from TS import board
tsbus.modem(False)
u = UART(0, 115200, tx=Pin(44), rx=Pin(45), timeout=50)
board.esp_boot(False)
time.sleep_ms(2500)
u.write(b'\\rATI\\r')
time.sleep_ms(800)
b = u.read() or b''
print('CHECK', b'Zimodem' in b, repr(b[-160:]))
u.deinit()
"""


def find_port(explicit):
    if explicit:
        return explicit
    ports = sorted(glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/ttyACM*"))
    if not ports:
        sys.exit("no TS-Pico serial port found; give --port")
    return ports[0]


class Port:
    """The card's serial port, read up to a token, keeping what comes after."""

    def __init__(self, name):
        self.s = serial.Serial(name, 115200, timeout=0.1)
        self.buf = b""

    def write(self, data):
        self.s.write(data)

    def until(self, token, timeout):
        end = time.monotonic() + timeout
        while token not in self.buf:
            if time.monotonic() > end:
                raise TimeoutError("waiting for %r, got %r" % (token, self.buf[-120:]))
            self.buf += self.s.read(self.s.in_waiting or 1)
        i = self.buf.index(token) + len(token)
        out, self.buf = self.buf[:i], self.buf[i:]
        return out

    def take(self):
        out, self.buf = self.buf + self.s.read(self.s.in_waiting or 1), b""
        return out

    def close(self):
        self.s.close()


def raw_repl(p):
    p.write(b"\r\x03\x03")
    p.until(b">>> ", 10)
    time.sleep(0.1)
    p.take()
    p.write(b"\r\x01")
    p.until(b"raw REPL; CTRL-B to exit\r\n>", 5)


def run_code(p, code, timeout):
    """Run code in the raw REPL; its output (it must end, unlike RELAY)."""
    p.write(code.encode() + b"\x04")
    p.until(b"OK", 5)
    out = p.until(b"\x04", timeout)[:-1]
    err = p.until(b"\x04", 5)[:-1]
    p.until(b">", 5)
    if err.strip():
        raise RuntimeError(err.decode(errors="replace"))
    return out.decode(errors="replace")


def restart_firmware(p):
    p.write(b"\x02")                            # out of the raw REPL
    time.sleep(0.2)
    p.write(b"\x04")                            # soft reset: the firmware starts again


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port")
    ap.add_argument("--image", default=IMAGE)
    ap.add_argument("--check", action="store_true", help="only check that Zimodem answers")
    args = ap.parse_args()
    if args.check:
        p = Port(find_port(args.port))
        raw_repl(p)
        try:
            print(run_code(p, CHECK, 15).strip())
        finally:
            restart_firmware(p)
            p.close()
        return 0
    if not os.path.exists(args.image):
        sys.exit("no image at %s: build it (esp32/zimodem/build.sh) or give --image" % args.image)
    port = find_port(args.port)

    print("Stopping the firmware and starting the relay on %s..." % port)
    p = Port(port)
    raw_repl(p)
    p.write(RELAY.encode() + b"\x04")
    p.until(b"OK", 5)
    time.sleep(0.5)
    print("ESP32 says: %r" % p.take()[-120:])   # the ROM loader's start-up text, if any
    p.close()

    print("Flashing %s (%d bytes) with esptool, through the card..." % (args.image, os.path.getsize(args.image)))
    cmd = [sys.executable, "-m", "esptool", "--chip", "esp32c3", "--port", port, "--baud", "115200",
           "--before", "no-reset", "--after", "no-reset", "write-flash", "0x0", args.image]
    rc = subprocess.call(cmd)

    print("Waiting for the relay to finish...")
    time.sleep(1)
    p = Port(port)
    try:
        out = p.until(b"\x04", 90)                 # the relay's output ends
        p.until(b"\x04", 5)                        # its errors, if any
        p.until(b">", 5)
        print([l for l in out.decode(errors="replace").splitlines() if "RELAY" in l] or out[-200:])
        if rc == 0:
            print("Checking Zimodem...")
            print(run_code(p, CHECK, 15).strip())
    finally:
        restart_firmware(p)
        p.close()
    print("esptool %s; the TS-Pico firmware is restarting." % ("succeeded" if rc == 0 else "FAILED (%d)" % rc))
    return rc


if __name__ == "__main__":
    sys.exit(main())
