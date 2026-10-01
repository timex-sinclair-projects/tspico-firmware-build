# from https://github.com/mendenm
# with some tweaks to hold off initializing the card
#
# MicroPython driver for SD cards using SPI bus.
#
# Requires an SPI bus and a CS pin.  Provides readblocks and writeblocks
# methods so the device can be mounted as a filesystem.
#
# Example usage on pyboard:
#
#     import pyb, sdcard, os
#     sd = sdcard.SDCard(pyb.SPI(1), pyb.Pin.board.X5)
#     pyb.mount(sd, '/sd2')
#     os.listdir('/')
#
# Example usage on ESP8266:
#
#     import machine, sdcard, os
#     sd = sdcard.SDCard(machine.SPI(1), machine.Pin(15))
#     os.mount(sd, '/sd')
#     os.listdir('/')
#
# Note about the crc_function:
#     this is crc(seed: int, buf: buffer) -> int
#     If no crc16  function is provided, CRCs are not computed on data transfers.
#     If a crc16 is provided, the CRC  function of the SD card is enabled,
#     and data transfers both ways are protected by it
#

from micropython import const
import time
from errno import ETIMEDOUT, EIO, ENODEV, EINVAL

crc7_be_syndrome_table = (
    b"\x00\x12$6HZl~\x90\x82\xb4\xa6\xd8\xca\xfc\xee2 \x16\x04zh^L\xa2\xb0\x86\x94\xea\xf8"
    b"\xce\xdcdv@R,>\x08\x1a\xf4\xe6\xd0\xc2\xbc\xae\x98\x8aVDr`\x1e\x0c:(\xc6\xd4\xe2\xf0"
    b"\x8e\x9c\xaa\xb8\xc8\xda\xec\xfe\x80\x92\xa4\xb6XJ|n\x10\x024&\xfa\xe8\xde\xcc\xb2\xa0"
    b'\x96\x84jxN\\"0\x06\x14\xac\xbe\x88\x9a\xe4\xf6\xc0\xd2<.\x18\ntfPB\x9e\x8c\xba\xa8'
    b"\xd6\xc4\xf2\xe0\x0e\x1c*8FTbp\x82\x90\xa6\xb4\xca\xd8\xee\xfc\x12\x006$ZH~l\xb0\xa2"
    b"\x94\x86\xf8\xea\xdc\xce 2\x04\x16hzL^\xe6\xf4\xc2\xd0\xae\xbc\x8a\x98vdR@>,\x1a\x08"
    b"\xd4\xc6\xf0\xe2\x9c\x8e\xb8\xaaDV`r\x0c\x1e(:JXn|\x02\x10&4\xda\xc8\xfe\xec\x92\x80"
    b'\xb6\xa4xj\\N0"\x14\x06\xe8\xfa\xcc\xde\xa0\xb2\x84\x96.<\n\x18ftBP\xbe\xac\x9a\x88\xf6'
    b"\xe4\xd2\xc0\x1c\x0e8*TFpb\x8c\x9e\xa8\xba\xc4\xd6\xe0\xf2"
)


def crc7(buf) -> int:
    crc = 0
    for b in buf:
        crc = crc7_be_syndrome_table[crc ^ b]
    return crc


def gb(bigval, b0, bn):
    # get numbered bits from a buf_to_int from, for example, the CSD
    return (bigval >> b0) & ((1 << (1 + bn - b0)) - 1)


_CMD_TIMEOUT = const(50)

# How long ACMD41 may take to bring the card out of idle. The SD spec allows
# up to 1 s after power-up, and a cold card at boot really does take longer
# than the ~250 ms (50 x 5 ms) this loop used to allow -- the mount then
# failed with (110, 'card type', 'v2') while the same card mounted fine a few
# seconds later. MicroPython's stock driver allows 5 s; 1.5 s covers the spec
# with margin and costs a fast card nothing (it answers on the first tries).
_INIT_TIMEOUT_MS = const(1500)

# How long to keep trying CMD0 (reset into SPI idle). A card that is still
# finishing something from before a soft reboot, or not quite awake at
# power-up, can miss the first one entirely; MicroPython's stock driver
# retries it, and so must we.
_CMD0_TIMEOUT_MS = const(500)

# Longest a card may hold MISO low (busy) after a write block or STOP_TRAN
# before we call it an error. The SD spec's write timeout is 250 ms (SDSC) /
# 500 ms (SDHC/SDXC); 1 s leaves margin. It used to be `while busy: pass`,
# which hangs the Pico for good on a card that never lets go.
_BUSY_TIMEOUT_MS = const(1000)

_R1_IDLE_STATE = const(1 << 0)
# R1_ERASE_RESET = const(1 << 1)
_R1_ILLEGAL_COMMAND = const(1 << 2)
_R1_COM_CRC_ERROR = const(1 << 3)
# R1_ERASE_SEQUENCE_ERROR = const(1 << 4)
# R1_ADDRESS_ERROR = const(1 << 5)
# R1_PARAMETER_ERROR = const(1 << 6)
_TOKEN_CMD25 = const(0xFC)
_TOKEN_STOP_TRAN = const(0xFD)
_TOKEN_DATA = const(0xFE)
_HCS_BIT = const(1 << 30)  # for ACMD41


class SDCard:
    def __init__(self, spi, cs, baudrate=5_000_000, crc16_function=None):
        self.spi = spi
        self.cs = cs

        self.cmdbuf = bytearray(6)
        self.cmdbuf5 = memoryview(self.cmdbuf)[:5]  # for crc7 generation
        self.tokenbuf = bytearray(1)
        self.crcbuf = bytearray(2)
        self.crc16 = None  # during init
        self.recovered = None  # what _recover() found, for the caller to log
        # initialise the card
        self.init_card(baudrate)
        self.check_crcs(crc16_function)  # now set it up

    def check_crcs(self, crc16_function):
        self.crc16 = crc16_function
        result = self.cmd(
            59, 1 if crc16_function else 0, release=True
        )  # send CRC enable/disable command
        return result

    def init_spi(self, baudrate):
        try:
            master = self.spi.MASTER
        except AttributeError:
            # on ESP8266
            self.spi.init(baudrate=baudrate, phase=0, polarity=0)
        else:
            # on pyboard
            self.spi.init(master, baudrate=baudrate, phase=0, polarity=0)

    def _spiff(self):
        self.spi.write(b"\xff")

    def _wait_ready(self, ms=_BUSY_TIMEOUT_MS):
        """Clock the card (CS already low) until it stops holding MISO low.
        Returns how many busy bytes it saw (0 = ready at once), or -1 if it
        was still busy after `ms`."""
        tb = self.tokenbuf
        t0 = time.ticks_ms()
        n = 0
        while True:
            self.spi.readinto(tb, 0xFF)
            if tb[0] != 0x00:
                return n
            n += 1
            if time.ticks_diff(time.ticks_ms(), t0) >= ms:
                return -1

    def _recover(self):
        """Bring back a card that an interrupted session left inside a
        transfer, before CMD0.

        The card runs off the Pico's 3V3, so a Pico reset, reflash or Ctrl-C
        never power-cycles it. Cut off inside a multi-block write (CMD25) --
        by a Ctrl-C or reset during an SD access, or by writeblocks raising
        without STOP_TRAN, as it used to on "write fail" -- the card is still
        waiting for data, swallows CMD0 as data, and the driver reported
        "no SD card" on every warm boot until the power was pulled.
        Reproduced and fixed on hardware 2026-09-26 by stopping a write 100
        bytes into a block.

        1. 520 x 0xFF with CS low: completes a half-sent block (512 data +
           2 CRC + response). With CRC checks off -- this driver's default --
           the card writes that sector with the 0xFF filler; the sector was
           mid-rewrite anyway. On a card in any other state these are just
           clocks.
        2. Wait out busy, send STOP_TRAN (0xFD), wait out busy: ends a
           multi-block write. Idle cards ignore a lone 0xFD.
        3. CMD12 (STOP_TRANSMISSION): ends a multi-block read (CMD18) left
           streaming. Idle cards answer "illegal command" and carry on.
        Everything is bounded; a card that stays busy is left for CMD0's
        own retry loop to report.

        Sets self.recovered to a short description when the card was found
        mid-transfer, else None.
        """
        cs = self.cs
        spi = self.spi
        buf = bytearray(520)
        cs(0)
        spi.readinto(buf, 0xFF)
        seen = 0
        for b in buf:
            if b != 0xFF:
                seen += 1
        b1 = self._wait_ready()
        spi.write(b"\xfd\xff")                     # STOP_TRAN + the byte before busy
        b2 = self._wait_ready()                      # busy here = it WAS in CMD25
        spi.write(b"\x4c\x00\x00\x00\x00\x61")   # CMD12, CRC7 0x30
        spi.readinto(buf, 0xFF)                      # skip byte + R1 + busy
        b3 = self._wait_ready()
        cs(1)
        spi.write(b"\xff\xff")
        stuck = b1 < 0 or b2 < 0 or b3 < 0
        if seen or b1 or b2 or stuck:
            self.recovered = "card was mid-transfer (%d non-idle bytes, busy %d/%d%s)" % (
                seen, b1, b2, ", still busy" if stuck else "")

    def decode_cid(self):
        cid_int = self.CID
        cid_array = self.CIDBYTES
        _gb = gb  # just for local binding
        manid =    _gb(cid_int, 120, 127)
        revhi =    _gb(cid_int, 60, 63)
        revlo =    _gb(cid_int, 56, 59)
        serial =   _gb(cid_int, 24, 55)
        manyear =  _gb(cid_int, 12, 19)+2000
        manmonth = _gb(cid_int, 8, 11)
        appid = cid_array[1:3].decode('ascii')
        product = cid_array[3:8].decode('ascii')
        return {
            'mid' : manid,
            'oid' : appid,
            'product' : product,
            'revision' : f"{revhi}.{revlo}",
            'serial' : serial,
            'date' : f"{manyear:04d}/{manmonth:02d}"
        }

    def init_card(self, baudrate):
        # init CS pin
        self.cs.init(self.cs.OUT, value=1)

        # init SPI bus; use low data rate for initialisation
        self.init_spi(100000)

        # clock card at least 100 cycles with cs high (16 bytes = 128 cycles)
        # use explicit string here for small memory footprint
        self.spi.write(b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff")

        # A card left mid-transfer by the last session ignores CMD0.
        self._recover()

        # CMD0: init card; should return _R1_IDLE_STATE. cmd() RAISES when
        # the card doesn't answer (stock MicroPython's returns -1), so the
        # old "allow 5 attempts" loop gave up on the first unanswered CMD0
        # -- seen at boot as (110, 'command:', 0, 'arg:', 0) about 30 ms
        # in. A missed or garbled CMD0 is just a failed attempt: clock the
        # card with CS high so it can finish whatever it was doing, and
        # try again for up to _CMD0_TIMEOUT_MS.
        # (cmd()'s third argument is `final`, extra bytes to clock out --
        # not a CRC as in the stock driver; cmd() computes the CRC itself.
        # The old call passed 0x95 there and clocked 149 bytes for nothing.)
        t0 = time.ticks_ms()
        while True:
            try:
                if self.cmd(0, 0) == _R1_IDLE_STATE:
                    break
            except OSError:
                pass
            if time.ticks_diff(time.ticks_ms(), t0) >= _CMD0_TIMEOUT_MS:
                raise OSError(ENODEV, "no SD card")
            self.spi.write(b"\xff\xff\xff\xff\xff\xff\xff\xff\xff\xff")
            time.sleep_ms(5)

        # CMD8: determine card version
        r = self.cmd(8, 0x01AA, 4)  # probe version
        v2 = r == _R1_IDLE_STATE
        v1 = r == (_R1_IDLE_STATE | _R1_ILLEGAL_COMMAND)

        if not (v1 or v2):
            raise OSError(EIO, "couldn't determine SD card version")
        arg41 = _HCS_BIT if v2 else 0  # we support high capacity, on v2 cards
        t0 = time.ticks_ms()
        while True:  # loop on acmd41 until the card leaves idle
            try:
                self.cmd(55, 0)
                r = self.cmd(41, arg41)
            except OSError:
                r = -1  # no answer yet: still busy, same as "not ready"
            if r == 0:
                break
            if time.ticks_diff(time.ticks_ms(), t0) >= _INIT_TIMEOUT_MS:
                break
            time.sleep_ms(5)
        if r != 0:
            raise OSError(ETIMEDOUT, "card type", "v2" if v2 else "v1")

        # get the number of sectors
        # CMD9: response R2 (R1 byte + 16-byte block read)
        if self.cmd(9, 0, 0, False) != 0:
            raise OSError(EIO, "no CSD response")
        csd = bytearray(16)
        self.readinto(csd)
        self.CSD = csd_int = int.from_bytes(
            csd, "big"
        )  # convert 16-byte CSD to a giant integer for bit extraction
        _gb = gb  # just for local binding
        # use bit numbers from SD card spec v9.0.0, table 5.3.2
        vers = _gb(csd_int, 126, 127)
        if vers == 1:  # CSD version 2.0
            self.sectors = (_gb(csd_int, 48, 69) + 1) * 1024
            self.cdv = 1
        elif vers == 0x00:  # CSD version 1.0 (old, <=2GB)
            c_size = _gb(csd_int, 62, 73)
            c_size_mult = _gb(csd_int, 47, 49)
            read_bl_len = _gb(csd_int, 80, 83)
            capacity = (c_size + 1) * (2 ** (c_size_mult + 2)) * (2**read_bl_len)
            self.sectors = capacity // 512
            self.cdv = 512  # converts bytes to sectors
        else:
            raise OSError(EIO, "CSD format unknown")
        # print('sectors', self.sectors)

        # get the card identification (CID)
        try:
            if self.cmd(10, 0, 0, False) != 0:
                raise OSError("no CID response")
            cid = bytearray(16)
            self.readinto(cid)
            self.CIDBYTES = cid
            self.CID = int.from_bytes(
                cid, "big"
            )
        except Exception:
            # 0 = unknown. tspico.SD_NOTE_CARD treats it that way, never as a
            # different card (it identifies the card by this CID since #101).
            # Exception, not a bare except, so Ctrl-C from the host still works.
            self.CIDBYTES = bytearray(16)
            self.CID = 0

        # CMD16: set block length to 512 bytes. A card that has only just
        # left idle can still refuse the first one (seen at boot as "can't
        # set 512 block size"), so give it a few tries.
        for _ in range(3):
            if self.cmd(16, 512) == 0:
                break
            time.sleep_ms(5)
        else:
            raise OSError(EIO, "can't set 512 block size")

        # set to high data rate now that it's initialised
        self.init_spi(baudrate)

    def cmd(self, cmd, arg, final=0, release=True, skip1=False):
        cs = self.cs  # prebind
        w = self.spi.write
        r = self.spi.readinto
        tb = self.tokenbuf
        spiff = self._spiff

        cs(0)  # select chip

        # create and send the command
        buf = self.cmdbuf
        buf[0] = 0x40 | cmd
        buf[1] = arg >> 24
        buf[2] = arg >> 16
        buf[3] = arg >> 8
        buf[4] = arg
        buf[5] = crc7(self.cmdbuf5) | 1
        w(buf)

        if skip1:
            r(tb, 0xFF)

        # wait for the response (response[7] == 0)
        for i in range(_CMD_TIMEOUT):
            r(tb, 0xFF)
            response = tb[0]
            # print(f"response: {response:02x}")

            if not (response & 0x80):
                # this could be a big-endian integer that we are getting here
                # if final<0 then store the first byte to tokenbuf and discard the rest
                if response & _R1_COM_CRC_ERROR:
                    cs(1)
                    spiff()
                    raise OSError(EIO, f"CRC err on cmd: {cmd:02d}")
                if final < 0:
                    r(tb, 0xFF)
                    final = -1 - final
                for j in range(final):
                    spiff()
                if release:
                    cs(1)
                    spiff()
                return response
            else:
                if i > (_CMD_TIMEOUT // 2):
                    time.sleep_ms(1)  # very slow response, give it time

        # timeout
        cs(1)
        spiff()
        raise OSError(ETIMEDOUT, "command:", cmd, "arg:", arg)

    def readinto(self, buf):
        cs = self.cs
        spiff = self._spiff

        cs(0)

        # read until start byte (0xff)
        for i in range(_CMD_TIMEOUT):
            self.spi.readinto(self.tokenbuf, 0xFF)
            if self.tokenbuf[0] == _TOKEN_DATA:
                break
            if i > _CMD_TIMEOUT // 2:
                time.sleep_ms(1)  # if response is slow, wait longer

        else:
            cs(1)
            raise OSError(ETIMEDOUT, "read timeout")

        self.spi.readinto(buf, 0xFF)

        # read checksum
        ck = self.spi.read(2, 0xFF)
        if self.crc16:
            crc = self.crc16(self.crc16(0, buf), ck)
            if crc != 0:
                cs(1)
                spiff()
                raise OSError(EIO, f"bad data CRC: {crc:04x}")

        cs(1)
        spiff()

    def write(self, token, buf):
        cs = self.cs
        spiff = self._spiff
        r = self.spi.read
        w = self.spi.write

        cs(0)

        # send: start of block, data, checksum
        r(1, token)
        w(buf)
        if self.crc16:
            crc = self.crc16(0, buf)
            self.crcbuf[0] = crc >> 8
            self.crcbuf[1] = crc & 0xFF
            w(self.crcbuf)  # write checksum
        else:
            w(b"\xff\xff")
            # check the response
        if ((r(1, 0xFF)[0]) & 0x1F) != 0x05:
            cs(1)
            spiff()
            raise OSError(EIO, "write fail")

        # wait for write to finish
        if self._wait_ready() < 0:
            cs(1)
            spiff()
            raise OSError(ETIMEDOUT, "write busy")

        cs(1)
        spiff()

    def write_token(self, token):
        self.cs(0)
        # A card still busy with the last block takes the token as a clock
        # tick and never sees it -- after a refused block ("write fail")
        # STOP_TRAN was lost that way. Let it finish first.
        self._wait_ready()
        self.spi.read(1, token)
        self._spiff()
        # wait for write to finish
        ok = self._wait_ready() >= 0
        self.cs(1)
        self._spiff()
        if not ok:
            raise OSError(ETIMEDOUT, "write busy")

    @staticmethod
    def blocks(buf):
        nblocks, err = divmod(len(buf), 512)
        if not nblocks or err:
            raise OSError(EINVAL, "Buffer length is invalid")
        return nblocks

    def readblocks(self, block_num, buf):
        # workaround for shared bus, required for (at least) some Kingston
        # devices, ensure MOSI is high before starting transaction
        self._spiff()
        nblocks = self.blocks(buf)

        # CMD18: set read address for multiple blocks
        if self.cmd(18, block_num * self.cdv, release=False) != 0:
            # release the card
            self.cs(1)
            raise OSError(EIO)  # EIO
        mv = memoryview(buf)
        # Always end the read with CMD12, even when a block fails or a
        # Ctrl-C lands mid-way: a card left streaming ignores the next
        # command. On the error path the original exception wins.
        try:
            for offset in range(0, nblocks * 512, 512):
                self.readinto(mv[offset : offset + 512])
        except BaseException:
            try:
                self.cmd(12, 0, skip1=True)
            except OSError:
                pass
            raise

        if self.cmd(12, 0, skip1=True):
            raise OSError(EIO)  # EIO

    def writeblocks(self, block_num, buf):
        # workaround for shared bus, required for (at least) some Kingston
        # devices, ensure MOSI is high before starting transaction
        self._spiff()
        nblocks = self.blocks(buf)

        # CMD25: set write address for first block
        if self.cmd(25, block_num * self.cdv) != 0:
            raise OSError(EIO)  # EIO`
        # send the data. Always finish with STOP_TRAN -- also when a block
        # is refused ("write fail") or a Ctrl-C lands between blocks: a card
        # left inside CMD25 swallows every later command as data and looked
        # like "no SD card" until a power cycle. On the error path the
        # original exception wins.
        mv = memoryview(buf)
        try:
            for offset in range(0, nblocks * 512, 512):
                self.write(_TOKEN_CMD25, mv[offset : offset + 512])
        except BaseException:
            try:
                self.write_token(_TOKEN_STOP_TRAN)
            except OSError:
                pass
            raise
        self.write_token(_TOKEN_STOP_TRAN)

    def ioctl(self, op, arg):
        if op == 4:  # get number of blocks
            return self.sectors
        if op == 5:  # get block size in bytes
            return 512