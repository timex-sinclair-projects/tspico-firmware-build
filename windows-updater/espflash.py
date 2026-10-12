"""The v3 card's modem: a client for the ESP32-C3 ROM's serial loader.

The same protocol as the web updater's espflash.js, for the Windows exe:
the card's relay (tsbus.esp_relay) joins its USB serial port to the ESP32's
UART with the ESP32 in its ROM loader, and this talks to the loader through
it. Only what a Zimodem write needs: SYNC, SPI_ATTACH, SPI_SET_PARAMS,
FLASH_DEFL_BEGIN/DATA and SPI_FLASH_MD5. No stub is uploaded: the ROM's own
commands at 115200, deflated, write the 1.1 MB image in about a minute.

A request is SLIP-framed: 00, op, length (16-bit), checksum (32-bit, only
for data blocks), data. A reply is 01, op, length, value (32-bit), data,
then 4 status bytes (status, error, 0, 0) on the C3's ROM. esptool's
espressif/loader.py is the reference.

io is anything with write(bytes) and read(timeout) -> bytes (b"" by timeout);
core.py passes the card's serial port, test/core_test.py a fake loader.
"""

import hashlib
import struct
import time
import zlib

SLIP_END, SLIP_ESC, SLIP_ESC_END, SLIP_ESC_ESC = 0xC0, 0xDB, 0xDC, 0xDD
SYNC, SPI_SET_PARAMS, SPI_ATTACH = 0x08, 0x0B, 0x0D
FLASH_DEFL_BEGIN, FLASH_DEFL_DATA, SPI_FLASH_MD5 = 0x10, 0x11, 0x13
FLASH_WRITE_SIZE = 0x400            # the ROM loader's block
STATUS_LEN = 4                      # the ESP32-C3 ROM's; 2 is the ESP8266's and the stub's
FLASH_SIZE = 4 * 1024 * 1024        # the ESP32-C3-WROOM-02's 4 MB
ERASE_S_PER_MB = 30.0               # esptool's ERASE_REGION_TIMEOUT_PER_MB
MD5_S_PER_MB = 8.0


class EspError(Exception):
    """The loader refused a command, or didn't answer."""


def slip_encode(data):
    out = bytearray([SLIP_END])
    for b in data:
        if b == SLIP_END:
            out += bytes([SLIP_ESC, SLIP_ESC_END])
        elif b == SLIP_ESC:
            out += bytes([SLIP_ESC, SLIP_ESC_ESC])
        else:
            out.append(b)
    out.append(SLIP_END)
    return bytes(out)


def checksum(data):
    """The data blocks' checksum: XOR of the bytes, seeded with EFh."""
    c = 0xEF
    for b in data:
        c ^= b
    return c


class EspRomLoader:
    def __init__(self, io):
        self.io = io
        self.frame = None           # a SLIP frame being read, or None between frames
        self.esc = False
        self.pending = []           # whole frames read but not yet wanted
        self.leftover = b""

    def read_frame(self, timeout):
        """The next whole SLIP frame, or None by timeout (seconds)."""
        if self.pending:
            return self.pending.pop(0)
        end = time.monotonic() + timeout
        while True:
            data, self.leftover = self.leftover, b""
            if not data:
                left = end - time.monotonic()
                if left <= 0:
                    return None
                data = self.io.read(left)
                if not data:
                    continue
            for i, b in enumerate(data):
                if self.frame is None:
                    if b == SLIP_END:
                        self.frame = bytearray()          # anything else between frames is noise
                    continue
                if self.esc:
                    self.frame.append(SLIP_END if b == SLIP_ESC_END else SLIP_ESC if b == SLIP_ESC_ESC else b)
                    self.esc = False
                elif b == SLIP_ESC:
                    self.esc = True
                elif b == SLIP_END:
                    if self.frame:                        # C0 C0: still at a frame's start
                        f, self.frame = bytes(self.frame), None
                        self.leftover = data[i + 1:]
                        return f
                else:
                    self.frame.append(b)

    def command(self, op, data=b"", chk=0, timeout=3.0):
        """Send a request and wait for its reply: (value, data without the
        status bytes). Replies to other commands (a late SYNC's) are skipped."""
        self.io.write(slip_encode(struct.pack("<BBHI", 0, op, len(data), chk) + data))
        end = time.monotonic() + timeout
        while True:
            left = end - time.monotonic()
            f = self.read_frame(left) if left > 0 else None
            if f is None:
                raise EspError("no reply to command %02Xh" % op)
            if len(f) < 8 or f[0] != 0x01 or f[1] != op:
                continue
            size, value = struct.unpack_from("<HI", f, 2)
            body = f[8:8 + size]
            if len(body) < STATUS_LEN:
                raise EspError("short reply to %02Xh" % op)
            status, error = body[-STATUS_LEN], body[-STATUS_LEN + 1]
            if status:
                raise EspError("command %02Xh failed: error %02Xh" % (op, error))
            return value, body[:-STATUS_LEN]

    def sync(self, tries=10):
        """Get the loader's attention: SYNC until it answers, then drop the
        other replies the ROM sends to each SYNC."""
        data = bytes([0x07, 0x07, 0x12, 0x20]) + b"\x55" * 32
        for _ in range(tries):
            try:
                self.command(SYNC, data, 0, 0.2)
            except EspError:
                continue
            while self.read_frame(0.15) is not None:
                pass
            self.pending = []
            return
        raise EspError("the ESP32 loader does not answer")

    def attach(self):
        self.command(SPI_ATTACH, bytes(8))
        self.command(SPI_SET_PARAMS, struct.pack("<6I", 0, FLASH_SIZE, 64 * 1024, 4096, 256, 0xFFFF))

    def flash(self, image, offset=0, progress=None):
        """Write image at offset, deflated, then check the ROM's MD5 of what
        it wrote. Only the image's own blocks are erased: Zimodem's SPIFFS
        (WiFi, phonebook) further up stays. Returns (compressed, blocks, md5)."""
        comp = zlib.compress(bytes(image), 9)
        blocks = (len(comp) + FLASH_WRITE_SIZE - 1) // FLASH_WRITE_SIZE
        erase = (len(image) + FLASH_WRITE_SIZE - 1) // FLASH_WRITE_SIZE * FLASH_WRITE_SIZE
        mb = 1024 * 1024
        # The C3's ROM takes a fifth word, the encrypted flag.
        self.command(FLASH_DEFL_BEGIN, struct.pack("<5I", erase, blocks, FLASH_WRITE_SIZE, offset, 0), 0,
                     max(3.0, ERASE_S_PER_MB * erase / mb))
        for seq in range(blocks):
            block = comp[seq * FLASH_WRITE_SIZE:(seq + 1) * FLASH_WRITE_SIZE]
            self.command(FLASH_DEFL_DATA, struct.pack("<4I", len(block), seq, 0, 0) + block,
                         checksum(block), 10.0)
            if progress:
                progress((seq + 1) / blocks)
        _, r = self.command(SPI_FLASH_MD5, struct.pack("<4I", offset, len(image), 0, 0), 0,
                            max(3.0, MD5_S_PER_MB * len(image) / mb))
        got = r[:32].decode(errors="replace").lower()
        want = hashlib.md5(bytes(image)).hexdigest()
        if got != want:
            raise EspError("the written image's MD5 is %s, not %s" % (got, want))
        return len(comp), blocks, want
