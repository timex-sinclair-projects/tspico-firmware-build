# The v3 card (RP2350B): the hardware behind TS/board.py.
#
# Phase 4 of the v3 port plan (docs/v3-board-layer-proposal.md). The card has
# no memory chips: the tsbus C module serves the 2068's ROM and DOCK from SRAM
# and answers ports 0Eh/0Fh from core 1 (docs/reference/firmware/tsbus.md).
# The SD card has its own SPI pins, so SD never takes the bus; the LED is on
# the XL9555 expander; core 1 belongs to tsbus. Same names as board_v2.py.

import os
import time
import tsbus
from machine import Pin, SPI, I2C, Timer

NAME = "v3"
LABEL = "V3"        # tpi:info's Board line (6 columns at most)
PIO_MQ = False      # MQ is tsbus.MQ(): tspico_io must not touch PIO0 SM0
SLOTS = False       # the Pico writes the slots itself (write_slot), not the Z80
SD_SLOTS = True     # tpi:boot and tpi:dock take MEM 3: a slot file on the SD card
HAS_MODEM = True    # the TS2050's 8251 at 73h/77h, bridged to the ESP32-C3 (modem_start)
HAS_JOYSTICK = True # the DE-9 socket, answered as a Kempston interface at 1Fh (joystick)
HAS_SPEECH = True   # the SP0256-AL2 on core 1, out of the audio jack (speech_start)
HAS_CORE1 = False   # core 1 runs tsbus; background() runs on core 0

# The slots (phase 5, docs/v3-slots-proposal.md): v2's two chips of sixteen
# 32K slots, as files. Fnn.bin is flash slot nn, kept; Snn.bin is SRAM slot
# nn, deleted at every boot (v2's SRAM loses its contents at power-off). A
# missing file is an empty slot. A ROM slot is HOME (16K) then EXROM (16K).
SLOTS_DIR = "/slots"
SLOT_SIZE = 32768
MEM_SRAM, MEM_FLASH, MEM_SD = 1, 2, 3   # ROM_SM's two-bit memory codes

# MEM 3 (phase 6): slot nn read from /slots/Fnn.bin on the SD card, the same
# files as the flash slots, so v3-slots.zip unzips straight onto a card. If
# the card or the file isn't there, flash slot nn stands in. The caller has
# the card mounted on /sd while a MEM 3 slot is read (tspico.SD_SLOTS_CALL);
# nothing here mounts it. An SD dock is read-only, as a flash one.
SD_SLOTS_DIR = "/sd/slots"

# The last fallback for the boot ROM, when neither the boot slot nor flash
# slot 1 has a file: the 2068 is never released into an empty ROM.
ROM_FILE = "/rom/TSPICO-23.ROM"

_SD_CS = 37
_SD_SCK, _SD_MOSI, _SD_MISO = 38, 39, 32

_IOX_ADDR = 0x20
_IOX_IN1 = 1            # input port 1: the joystick, nBUSAK_L, SD_CD
_IOX_OUT0 = 2
_IOX_OUT0_SAFE = 0xA0   # no bus request, no NMI, OLED in reset, ESP32 off, LED off, SD socket off
_X_WIFI_EN = 0x08       # bit 3: the ESP32-C3's EN, high = powered and running
_X_WIFI_DL = 0x10       # bit 4: high pulls the ESP32's IO9 low, so it boots into download mode
_X_NLED = 0x20          # bit 5, active low
_X_SD_PWR = 0x40        # bit 6: SD_PWR_EN, high = the socket powered (proto2's U32; unconnected on proto1)
_X_SD_CD = 0x80         # port 1 bit 7: low = a card in (the TF-01A's switch closes to GND; R38 pulls it up)
_IOX_INT = 35           # nIOX_INT: the expander pulls it low when an input changes (R8 pulls it up)

# A card the switch has only just seen is left alone this long before the
# first SPI clock, so it is seated and powered before its lines are driven.
SD_SETTLE_MS = 250
# The socket's power switch (#262): after it turns on, this long before the
# first clock (VDD is up in about 120 us; the SD spec asks for 1 ms). After
# it turns off, this long before it turns on again: U32 discharges VDD through
# about 150 ohm into 10 uF, a time constant of 1.5 ms.
SD_ON_MS = 2
SD_OFF_MS = 10
_sd_off_at = None       # ticks_ms when the socket was last switched off; None: not since boot

_i2c = None             # I2C(0), shared by the LED and the card-detect read
_cd_since = None        # ticks_ms when the switch was first seen closed; None: no card


def _iox():
    global _i2c
    if _i2c is None:
        _i2c = I2C(0)               # the board's defaults: SCL 25, SDA 24
    return _i2c

# Port 0 is shared: the LED, the ESP32's EN and IO9, and on proto2 the SD
# socket's power (#262) each own bits of the one output register. _out0 is
# what was last written, starting from the value board_init.c writes at
# power-up; _port0 changes only the bits it is given. The LED changes its
# bit from soft timer callbacks, which run on core 0 between bytecodes:
# never inside an I2C write and never inside another callback. So a callback
# always starts from the newest _out0 and can't undo another bit; the worst a
# change from the main thread can do is write the LED's bit as it was one
# edge before, until the LED's next edge (10 ms) writes it again. _out0_buf
# is the one buffer every write uses, so the byte written is always a whole
# value of _out0.
_out0 = _IOX_OUT0_SAFE
_out0_buf = bytearray(1)


def _port0(mask, bits):
    """Set port 0's bits in mask to those of bits, the others unchanged, and
    write the register if that changed it. False if the expander didn't
    answer (the shadow keeps the new value)."""
    global _out0
    new = (_out0 & ~mask) | (bits & mask)
    if new == _out0:
        return True
    _out0 = new
    _out0_buf[0] = new
    try:
        _iox().writeto_mem(_IOX_ADDR, _IOX_OUT0, _out0_buf)
    except OSError:
        return False
    return True


def modem_power(on):
    """The ESP32-C3 on (EN high: it boots, about a second to Zimodem's
    banner) or off (EN low: held in reset, its WiFi silent). It draws up to
    about 350 mA in WiFi bursts from the 2068's 5 V rail, so it is off unless
    something needs it. False if the expander didn't answer."""
    return _port0(_X_WIFI_EN, _X_WIFI_EN if on else 0)


# The modem (docs/v3-modem-proposal.md, step 4): tsbus answers the 8251 from
# boot; the ESP32 is powered only when a program uses it. Core 1 says what
# it saw (tsbus.modem_poll); the idle loop does the powering, here, since the
# expander is I2C. The line comes up when Zimodem prints READY. (core 1 sees
# it: tsbus.modem_poll bit 3, #300), which took about 1 s on proto1
# (2026-10-12) and over 2 s with a WiFi join (2026-10-14). MODEM_BOOT_MS:
# the fallback, from EN high, for a Zimodem that never says it.
MODEM_BOOT_MS = 8000
MODEM_MODES = ("2050", "hayes", "off")
_m_mode = "off"          # what modem_start set up
_m_baud = 300
_m_idle_ms = 600_000
_m_powered = False       # the ESP32's EN is high
_m_up = False            # ... and Zimodem said READY., or MODEM_BOOT_MS passed
_m_power_at = 0          # ticks_ms when it was powered
_m_last = 0              # ticks_ms of the last 8251 use, or off-hook


def modem_start(mode, baud=None, idle_min=None):
    """The modem in `mode` ("2050", "hayes" or "off"), received characters
    paced at `baud` (0: none), the ESP32 off after `idle_min` minutes unused.
    Off: 73h/77h unanswered and the ESP32 off. Otherwise the 8251 is set up
    as at power-up (tsbus.modem); the ESP32 stays as it was."""
    global _m_mode, _m_baud, _m_idle_ms
    if baud is not None:
        _m_baud = baud
    if idle_min is not None:
        _m_idle_ms = idle_min * 60_000
    _m_mode = mode
    tsbus.modem_pace(_m_baud)
    if mode == "off":
        tsbus.modem(False)
        _modem_off()
        return
    tsbus.modem_mode(0 if mode == "hayes" else 1)
    tsbus.modem(True)


def _modem_off():
    global _m_powered, _m_up
    tsbus.modem_line(False)
    modem_power(False)
    _m_powered = _m_up = False


def modem_service():
    """Every idle pass of the dispatcher, while the modem is on: power the
    ESP32 when a program writes to the 8251; note the line is up once core 1
    has seen Zimodem's READY. (bit 3), or tell tsbus so MODEM_BOOT_MS after
    power-up if it hasn't; power it off after the idle time with no 8251 use
    (a terminal polling its status counts) and on-hook."""
    global _m_powered, _m_up, _m_power_at, _m_last
    if _m_mode == "off":
        return
    f = tsbus.modem_poll()
    now = time.ticks_ms()
    if f & 6:
        _m_last = now
    if not _m_powered:
        if f & 1:
            modem_power(True)
            _m_powered = True
            _m_power_at = _m_last = now
        return
    if not _m_up:
        if f & 8:
            _m_up = True                 # core 1 saw READY. and brought it up
        elif time.ticks_diff(now, _m_power_at) >= MODEM_BOOT_MS:
            tsbus.modem_line(True)
            _m_up = True
    if not f & 2 and time.ticks_diff(now, _m_last) > _m_idle_ms:
        _modem_off()


_M_STATES = ("on-hook", "off-hook", "dialling", "connected", "no carrier", "hanging up")


def modem_status():
    """(mode, ESP32 "off"/"starting"/"on", line state, calls, connects, Hayes
    flow control on) for tpi:modem."""
    s = tsbus.stats()
    esp = "on" if _m_up else ("starting" if _m_powered else "off")
    st = s["m_state"]
    line = _M_STATES[st] if _m_mode == "2050" and st < len(_M_STATES) else "-"
    return _m_mode, esp, line, s["m_dials"], s["m_connects"], bool(s.get("m_flow"))


def modem_flow(on):
    """Hayes mode: the card pauses Zimodem with XOFF when its receive ring is
    half full and resumes it with XON (tsbus.modem_flow). For a program that
    has sent Zimodem ATF1 and dials with X (ATDTX); not saved, and off again
    after any modem_start."""
    tsbus.modem_flow(on)


def esp_boot(download):
    """Restart the ESP32-C3: into its ROM's serial loader (download True:
    IO9 held low as it leaves reset), to install Zimodem through
    tsbus.esp_relay; or normally. The modem's idle logic is told the ESP32 is
    on but not up, so it neither switches it off nor sends to it."""
    global _m_powered, _m_up, _m_power_at, _m_last
    tsbus.modem_line(False)
    modem_power(False)
    modem_download(download)
    time.sleep_ms(50)
    modem_power(True)
    _m_powered, _m_up = True, False
    _m_power_at = _m_last = time.ticks_ms()


def modem_download(on):
    """IO9 held low (on) or released, read by the ESP32 as it leaves reset:
    low boots its ROM's serial downloader (to install Zimodem) instead of
    the firmware. Takes effect at the next modem_power(True)."""
    return _port0(_X_WIFI_DL, _X_WIFI_DL if on else 0)

# WiFi downloads (tpi:wifi, tpi:net; docs/v3-wifi-archive-proposal.md):
# core 0 borrows UART0 from tsbus for one command and talks to Zimodem itself.
# AT&G"url" fetches a file; stream mode (ATS45=3) sends "[ 0 size ]" and the
# bytes, with no checksum and no flow control, so they are collected into
# RAM and written to the SD card after (writing while receiving lost bytes).
# Proved by src/test/wifi_get_harness.py on board 1 (2026-11-08): under the
# firmware's own heap, cold and warm, byte-exact.
ESP_BOOT_MS = 8000       # EN high to Zimodem's READY. (2.8-3 s with a WiFi join)
ESP_JOIN_MS = 10000      # READY. to an address (ATI2 not 0.0.0.0)
ESP_FIRST_MS = 15000     # AT&G to the "[ 0 size ]" header (3-5 s seen)
ESP_IDLE_MS = 4000       # a stall in the data that ends a fetch


class WifiError(Exception):
    """A fetch or join that failed; str() is the message for the 2068."""


def _esp_wait(u, want, ms, buf):
    """Read UART0 into buf until `want` or ERROR is in it, or ms pass; the
    bytes read. Only the last len(buf) are kept: the ESP32's ROM prints
    ~280 bytes before Zimodem's READY."""
    n, t0 = 0, time.ticks_ms()
    mv = memoryview(buf)
    half = len(buf) // 2
    while time.ticks_diff(time.ticks_ms(), t0) < ms:
        if n == len(buf):
            mv[:half] = mv[half:]
            n = half
        k = u.readinto(mv[n:])
        if k:
            n += k
            got = bytes(mv[:n])
            if want in got or b"ERROR" in got:
                return got
        else:
            time.sleep_ms(5)
    return bytes(mv[:n])


def _esp_cmd(u, line, ms=1500):
    """Send one AT line; the reply, through OK or ERROR."""
    u.read()
    u.write(line + b"\r")
    return _esp_wait(u, b"OK\r\n", ms, bytearray(128))


def _esp_address(u, join_ms):
    """Zimodem's address (ATI2) once it is on WiFi, or None after join_ms."""
    t0 = time.ticks_ms()
    while True:
        r = _esp_cmd(u, b"ATI2")
        for ln in r.split(b"\r\n"):
            if ln.count(b".") == 3 and ln != b"0.0.0.0":
                return ln.decode()
        if time.ticks_diff(time.ticks_ms(), t0) >= join_ms:
            return None
        time.sleep_ms(500)


def _esp_open():
    """UART0 from tsbus, the ESP32 on and answering; the UART. A modem call
    in progress (2050 mode off-hook) is refused, since UART0 carries it."""
    global _m_up
    if _m_mode == "2050" and tsbus.stats()["m_state"]:
        raise WifiError("Modem in use")
    from machine import UART
    tsbus.modem(False)                    # core 1 leaves UART0 and its DMA alone
    u = UART(0, 115200, tx=Pin(44), rx=Pin(45), timeout=0, rxbuf=4096)
    try:
        if not _m_powered:
            esp_boot(False)
            if b"READY." not in _esp_wait(u, b"READY.", ESP_BOOT_MS, bytearray(256)):
                raise WifiError("No answer from the ESP32")
            tsbus.modem_line(True)        # up: the modem needn't wait MODEM_BOOT_MS
            _m_up = True
        _esp_cmd(u, b"ATE0")
    except BaseException:
        _esp_close(u)
        raise
    return u


def _esp_close(u):
    """Zimodem back as a program expects it (echo on, no stream mode), UART0
    back to tsbus, and the modem's idle clock restarted."""
    global _m_last
    time.sleep_ms(200)                    # the end of a cut-short stream
    _esp_cmd(u, b"ATS45=0")
    _esp_cmd(u, b"ATE1")
    u.deinit()
    _m_last = time.ticks_ms()
    modem_start(_m_mode)                  # "off": the ESP32 off again


def wifi_get(url, buf):
    """Fetch url (https://...) into buf with Zimodem's AT&G; its length.
    WifiError if the ESP32 isn't on WiFi, the fetch fails, or the file is
    bigger than buf (nothing is fetched past it)."""
    u = _esp_open()
    try:
        if _esp_address(u, ESP_JOIN_MS) is None:
            raise WifiError("Not on WiFi")
        if b"OK" not in _esp_cmd(u, b"ATS45=3"):
            raise WifiError("No answer from the ESP32")
        small = bytearray(256)
        for tries in range(3):            # just after a cold boot the first
            u.read()                      # AT&G once answered ERROR (2026-11-08)
            u.write(b'AT&G"' + url.encode() + b'"\r')
            h = _esp_wait(u, b"]\r\n", ESP_FIRST_MS, small)
            i = h.find(b"]\r\n")
            if i >= 0 or b"ERROR" not in h:
                break
            time.sleep_ms(1000)
        if i < 0:
            raise WifiError("Download failed" if b"ERROR" in h else "No reply from the ESP32")
        size = int(h[h.index(b"[") + 1:i].split()[1])
        if size > len(buf):
            raise WifiError("Too big: %d bytes" % size)
        mv = memoryview(buf)
        n = len(h) - i - 3
        mv[:n] = h[i + 3:]
        last = time.ticks_ms()
        while n < size and time.ticks_diff(time.ticks_ms(), last) < ESP_IDLE_MS:
            k = u.readinto(mv[n:size])
            if k:
                n += k
                last = time.ticks_ms()
        if n < size:
            raise WifiError("Download cut short")
        return size
    finally:
        _esp_close(u)


def wifi_status():
    """Zimodem's address, or None if it isn't on WiFi (a short wait)."""
    u = _esp_open()
    try:
        return _esp_address(u, 2000)
    finally:
        _esp_close(u)


def wifi_join(ssid, password):
    """Join ssid and save it as Zimodem's default (ATW, AT&W); the address.
    WifiError if it doesn't join."""
    if '"' in ssid or '"' in password:
        raise WifiError('No " in a name or password')
    u = _esp_open()
    try:
        r = _esp_cmd(u, b'ATW"' + ("%s,%s" % (ssid, password)).encode() + b'"', 12000)
        if b"OK" not in r:                # 12 s + 3 s + a cold boot's 3 s: inside
            raise WifiError("Can't join " + ssid)   # the 2068's ~19.9 s wait
        ip = _esp_address(u, 3000)
        if ip is None:
            raise WifiError("Can't join " + ssid)
        _esp_cmd(u, b"AT&W")
        return ip
    finally:
        _esp_close(u)

# The joystick (phase 6): the DE-9's six switches are port 1's bits 0-5 (up,
# down, left, right, fire 1, fire 2), pulled up, low while pressed. The
# expander pulls nIOX_INT low when any input changes, so the port is read
# only then, in a soft IRQ handler: a scheduled callback, which runs between
# bytecodes, so never inside another I2C transfer (see _port0). tsbus answers
# 1Fh from the byte it is given; the 2068 never waits for I2C. Reading port
# 1 releases nIOX_INT; a read that failed leaves it low, which
# joystick_service sees from the idle loop.
_joy_pin = None          # Pin(_IOX_INT) while the joystick is answered
_joy_buf = bytearray(1)


def kempston_byte(p1):
    """Port 1 as the Kempston interface's byte, 000FUDLR, 1 = pressed: up
    bit 3, down 2, left 1, right 0, fire bit 4. Fire 2 is a second fire
    button: bit 5 is left 0, since games that look at the whole byte take
    bits 5-7 set for no interface at all."""
    j = ~p1 & 0x3F
    return (((j >> 3) & 1) | ((j >> 1) & 2) | ((j << 1) & 4) | ((j << 3) & 8)
            | (0x10 if j & 0x30 else 0))


def _joy_read(_pin=None):
    try:
        _iox().readfrom_mem_into(_IOX_ADDR, _IOX_IN1, _joy_buf)
    except OSError:
        return                  # nIOX_INT stays low; joystick_service tries again
    tsbus.kempston(kempston_byte(_joy_buf[0]))


def joystick(on):
    """Answer 1Fh as a Kempston joystick from the DE-9 (on), or leave 1Fh
    unanswered (off). On reads the switches straight away: a change before
    now left nIOX_INT low, with no edge to come."""
    global _joy_pin
    if on:
        _joy_pin = Pin(_IOX_INT, Pin.IN)
        _joy_pin.irq(_joy_read, Pin.IRQ_FALLING)
        _joy_read()
    else:
        if _joy_pin:
            _joy_pin.irq(None)
            _joy_pin = None
        tsbus.kempston(None)


def joystick_service():
    """From the idle loop: a read the IRQ handler couldn't finish (the
    expander didn't answer) leaves nIOX_INT low, with no edge to come; read
    again. So does a change of the SD card switch or nBUSAK_L, also port 1,
    when nothing else has read it: harmless, the same byte is set again."""
    if _joy_pin is not None and not _joy_pin.value():
        _joy_read()
# Speech (docs/v3-speech-proposal.md): the SP0256-AL2 emulated on core 1
# (tsbus, sp0256.c), out of the audio jack. Text becomes allophone numbers
# on core 0 (TS/speech.py); tsbus queues them, and the chip speaks them while
# the 2068 carries on.

def speech_start(volume, rate, ports=True):
    """Speech on: the chip at `rate` % of its speed (50-150; its pitch moves
    with it), at `volume` % (0-100), answering OUT 17 / IN 37 as David's Pico
    Speech Synth 2068 board does (`ports`), and /speech.txt's words added to
    the exception list. Returns how many words that was."""
    from TS import speech
    tsbus.speech(True, rate)
    tsbus.speech_volume(volume)
    tsbus.speech_ports(ports)
    return speech.load_exceptions()


def say(text):
    """Speak text (English, or allophone names in [brackets]) after whatever
    is queued; returns (allophones queued, allophones in the text). Empty
    text stops speech at once. ValueError for an unknown allophone name."""
    from TS import speech
    if not text.strip():
        tsbus.say(None)
        return 0, 0
    al = speech.allophones(text)
    return tsbus.say(al), len(al)


# The LED dimmer: D4 on R5 (100R) is far too bright at full current, so
# while it is on it is lit for the first LED_BRIGHTNESS % of every 10 ms
# (100 Hz). config.ini's LED_BRIGHTNESS sets it (led_brightness).
LED_PERIOD_US = 10_000
LED_BRIGHTNESS = 5


def early_init():
    """tsbus up: 250 MHz, the bus programs, core 1. The 2068 stays held in
    reset until start_memory. The safe pin state was set in C at start-up."""
    tsbus.start()


_served = None      # ((boot mem, slot), (dock mem, slot)) the 2068 is served now
_boot_stale = False  # write_slot rewrote the boot slot: tpi:boot loads it again

# The one block buffer: every slot passes through its first 32K (a ROM, each
# half of the dock, a RAM dock being saved), and LOAD and SAVE hold a data
# block in it (tspico_io.BLOCK, set from BLOCK_BUF by tspico.py). Allocated
# here, at import, while the heap is clean: once the firmware runs, the v3
# heap has no 64K block, a 32K one isn't certain either (hardware,
# 2026-10-10: tpi:dock failed with MemoryError building a 64K dock image),
# and a 35000-byte LOAD or SAVE failed for want of one after a 300-file
# folder had been listed (2026-11-06, #384: LOAD streamed from the file
# instead and ran dry, Report R; SAVE gave Report 6). 48K plus a little holds
# any block of the 2068's RAM: SAVE's flag, session bytes and parity (4)
# and LOAD's flag-less block (content + parity). The users never overlap:
# each takes it and is done with it inside one command.
BLOCK_SIZE = 49152 + 8
BLOCK_BUF = bytearray(BLOCK_SIZE)
_buf = memoryview(BLOCK_BUF)[:SLOT_SIZE]
_zeros = bytes(1024)                # for an empty half, without another 32K


def _keys(rom_sm, bank_sm):
    """The boot and dock (mem, slot) pairs of v2's two words."""
    return (rom_sm & 3, bank_sm & 15), ((rom_sm >> 2) & 3, (bank_sm >> 4) & 15)


def slot_path(mem, slot):
    """The file behind slot `slot` (0-15) of memory `mem` (MEM_FLASH,
    MEM_SRAM, MEM_SD: the SD card's file, not its flash stand-in)."""
    if mem == MEM_SD:
        return "%s/F%02d.bin" % (SD_SLOTS_DIR, slot)
    return "%s/%s%02d.bin" % (SLOTS_DIR, "S" if mem == MEM_SRAM else "F", slot)


def _slot_file(mem, slot):
    """The 32K file that serves slot `slot` of memory `mem`, or None. MEM_SD
    falls back to the flash slot of the same number."""
    for m in ((MEM_SD, MEM_FLASH) if mem == MEM_SD else (mem,)):
        path = slot_path(m, slot)
        try:
            if os.stat(path)[6] == SLOT_SIZE:
                return path
        except OSError:
            pass
    return None


def read_slot_into(mem, slot, buf):
    """Read a slot's 32K into buf (32K, a bytearray or memoryview), in
    place. Returns the file read, or None if the slot has no 32K file; buf
    is then untouched. For MEM_SD that may be the flash slot standing in."""
    path = _slot_file(mem, slot)
    if path is None:
        return None
    try:
        with open(path, "rb") as f:
            f.readinto(buf)
    except OSError:
        return None
    return path


def _stood_in(mem, slot, path):
    """A note when a MEM_SD slot was read from flash instead, else None."""
    if mem == MEM_SD and path and not path.startswith(SD_SLOTS_DIR):
        return "no SD slot %d: used flash slot %d" % (slot, slot)
    return None


def rom_slot_empty(mem, slot):
    """True if slot `slot` of memory `mem` has no 32K file (for MEM_SD,
    neither on the SD card nor in flash): tpi:boot refuses it, rather than
    boot_rom falling back to another ROM unasked."""
    return _slot_file(mem, slot) is None


def clear_sram_slots():
    """Delete every Snn.bin: the SRAM slots start empty, as v2's chip does."""
    try:
        names = os.listdir(SLOTS_DIR)
    except OSError:
        return
    for n in names:
        if n.startswith("S") and n.endswith(".bin"):
            try:
                os.remove(SLOTS_DIR + "/" + n)
            except OSError:
                pass


def boot_rom(rom_sm, bank_sm):
    """Read the ROM to boot into _buf; return a note if it isn't the one
    asked for, else None.

    The boot memory is rom_sm's bits 0-1 and the slot bank_sm's bits 0-3.
    If that slot has no 32K file: flash slot 1, then ROM_FILE."""
    mem, slot = rom_sm & 3, bank_sm & 15
    path = read_slot_into(mem, slot, _buf)
    if path:
        return _stood_in(mem, slot, path)
    want = "%s slot %d" % (("SRAM", "flash", "SD")[mem - 1], slot)
    if (mem, slot) != (MEM_FLASH, 1):
        if read_slot_into(MEM_FLASH, 1, _buf):
            return "no ROM in %s: booted flash slot 1" % want
        want += " or flash slot 1"
    with open(ROM_FILE, "rb") as f:
        f.readinto(_buf)
    return "no ROM in %s: booted %s" % (want, ROM_FILE)


def load_dock(rom_sm, bank_sm):
    """The dock slots into the DOCK image, a 32K half at a time through
    _buf (tsbus.load_at): the dock slot, then for an even slot the next one,
    as v2's 64K cartridge spans two slots numbered by the even one. A half
    with no file is zeros, as an empty v2 slot reads. The caller turns DOCK
    serving off around it if the 2068 is running. Returns a note if a MEM_SD
    half came from flash instead, else None."""
    mem, slot = (rom_sm >> 2) & 3, (bank_sm >> 4) & 15
    note = None
    for half, s in ((0, slot), (1, slot + 1 if slot % 2 == 0 else None)):
        base = half * SLOT_SIZE
        path = read_slot_into(mem, s, _buf) if s is not None else None
        if path:
            tsbus.load_at(tsbus.DOCK, base, _buf)
            note = note or _stood_in(mem, s, path)
        else:
            for off in range(0, SLOT_SIZE, len(_zeros)):
                tsbus.load_at(tsbus.DOCK, base + off, _zeros)
    return note


def save_ram_dock(dock):
    """Before a RAM dock (MEM_SRAM) is switched away: its image, with the
    Z80's writes in it, back to Snn (and Snn+1 for an even slot), so
    switching back finds the data, as v2's SRAM keeps it until power-off.
    A 32K half at a time through _buf; about 64K of flash writes."""
    mem, slot = dock
    if mem != MEM_SRAM:
        return
    try:
        os.mkdir(SLOTS_DIR)
    except OSError:
        pass
    for half, s in ((0, slot), (1, slot + 1 if slot % 2 == 0 else None)):
        if s is None:
            continue
        tsbus.read(tsbus.DOCK, _buf, half * SLOT_SIZE)
        with open(slot_path(mem, s), "wb") as f:
            f.write(_buf)


def _reads(served_mem, mem):
    """True if a slot served from served_mem may come from a file of mem:
    the same memory, or MEM_SD, whose flash slot stands in (_slot_file)."""
    return served_mem == mem or served_mem == MEM_SD


def write_slot(mem, slot, path):
    """tpi:blkrcv on the v3 card: write the image at path (MOUNT_FILE's
    /TMP/temp.bin) into slot `slot` of memory `mem`, through _buf. Up to 32K
    fills one slot, zero-padded; up to 64K (a .DCK image) fills an even slot
    and the next. If those slots are in the DOCK now, it is reloaded, live.
    A booted slot isn't touched: the 2068 runs from its SRAM copy, and the
    new ROM takes effect at the next boot or tpi:boot: _boot_stale is set,
    so map_slots(..., reboot=True) loads it again although the two words
    still name it. Returns what was written, for the message; ValueError if
    the image doesn't fit."""
    global _boot_stale
    size = os.stat(path)[6]
    if size == 0 or size > 2 * SLOT_SIZE:
        raise ValueError("an image of %d bytes" % size)
    pair = size > SLOT_SIZE
    if pair and (slot % 2 or slot > 14):
        raise ValueError("a 64K image needs an even slot")
    try:
        os.mkdir(SLOTS_DIR)
    except OSError:
        pass
    with open(path, "rb") as f:
        for s in ((slot, slot + 1) if pair else (slot,)):
            n = f.readinto(_buf) or 0
            mv = memoryview(_buf)
            while n < SLOT_SIZE:                    # zero-pad without another buffer
                k = min(len(_zeros), SLOT_SIZE - n)
                mv[n:n + k] = _zeros[:k]
                n += k
            with open(slot_path(mem, s), "wb") as out:
                out.write(_buf)
    written = (slot, slot + 1) if pair else (slot,)
    if _served is not None:
        boot, (dmem, dslot) = _served
        docked = (dslot, dslot + 1) if dslot % 2 == 0 else (dslot,)
        if _reads(dmem, mem) and any(s in docked for s in written):
            tsbus.dock(False)
            load_dock(dmem * 4, dslot * 16)
            tsbus.dock(True)
        if _reads(boot[0], mem) and boot[1] in written:
            _boot_stale = True
    what = "%s slot%s %s" % ("SRAM" if mem == MEM_SRAM else "Flash",
                             "s" if pair else "", "%d-%d" % (slot, slot + 1) if pair else str(slot))
    return what


def start_memory(rom_sm, bank_sm):
    """Clear the SRAM slots, load the boot ROM (HOME, EXROM) and the dock
    from the slot files (boot_rom, load_dock), and release the 2068 into
    them. Returns boot_rom's or load_dock's note, for the caller to log, or
    None."""
    global _served, _boot_stale
    clear_sram_slots()
    tsbus.hold(True)
    note = boot_rom(rom_sm, bank_sm)
    m = memoryview(_buf)
    tsbus.load(tsbus.HOME, m[:16384])
    tsbus.load(tsbus.EXROM, m[16384:])
    note = load_dock(rom_sm, bank_sm) or note
    tsbus.dock_writes((rom_sm >> 2) & 3 == MEM_SRAM)   # a flash dock is read-only, as v2's chip
    tsbus.exrom(True)
    tsbus.dock(True)
    tsbus.serve(True)
    tsbus.hold(False)
    _served = _keys(rom_sm, bank_sm)
    _boot_stale = False
    if note:
        print("[board] " + note)
    return note


def map_slots(rom_sm, bank_sm, reboot=False):
    """tpi:boot and tpi:dock: show the 2068 what the two words now say.

    Only what changed is loaded, through _buf. The dock first, live, as
    v2's tpi:dock: a RAM dock being left is saved back first
    (save_ram_dock), DOCK serving is off for the copy (a read sees an empty
    dock, never half the new one, as tsbus.switch does), and dock writes are
    stored for a RAM dock and ignored for a flash one (tsbus.dock_writes).
    Then the ROM, which tsbus.switch loads with the 2068 held for RESET_MS
    (200 ms), so it starts cleanly in the new ROM rather than running a mix
    of the two (docs/v3-slots-proposal.md, decision 2). Returns a note if
    the ROM fell back or a MEM_SD slot came from flash, else None; MEMBOOT
    refuses an empty slot first.

    reboot is tpi:boot's: it also reloads a boot slot that hasn't changed
    in the words but has on disk (write_slot set _boot_stale), as the
    loaders romupd3/dckupd3 promise. tpi:dock leaves it off, so writing the
    booted slot never resets the 2068 behind a dock change."""
    global _served, _boot_stale
    boot, dock = _keys(rom_sm, bank_sm)
    note = None
    if _served is None or dock != _served[1]:
        if _served is not None:
            save_ram_dock(_served[1])
        tsbus.dock(False)
        note = load_dock(rom_sm, bank_sm)
        tsbus.dock_writes(dock[0] == MEM_SRAM)
        tsbus.dock(True)
    if _served is None or boot != _served[0] or (reboot and _boot_stale):
        note = boot_rom(rom_sm, bank_sm) or note
        m = memoryview(_buf)
        tsbus.switch(home=m[:16384], exrom=m[16384:])
        _boot_stale = False
    _served = (boot, dock)
    return note


def make_mq():
    """tsbus.MQ(), with both queues emptied, as a new v2 state machine's
    FIFOs are. The status byte is left alone (ACTIVATE_MQ sets BUSY)."""
    mq = tsbus.MQ()
    while mq.rx_fifo():
        mq.get()
    while mq.tx_fifo():
        mq.exec("pull (noblock)")
    return mq


def restart_mq(MQ):
    """Nothing to restart: core 1 is always serving."""
    pass


def card_present():
    """The socket's detect switch: True with a card in, False without, None
    if the expander doesn't answer (then only a mount can tell)."""
    try:
        return not (_iox().readfrom_mem(_IOX_ADDR, _IOX_IN1, 1)[0] & _X_SD_CD)
    except OSError:
        return None


def sd_card_ready():
    """ACTIVATE_SD asks this before it touches an SD line. False: the switch
    says the socket is empty, so no SPI at all, and a socket left powered
    (the card pulled while it was mounted) is released and switched off.
    True: a card is in, and has been for SD_SETTLE_MS (it waits out the rest
    when the card is new), or the switch can't be read and the mount will
    find out; either way the socket is then powered (sd_power)."""
    global _cd_since
    p = card_present()
    if p is None:
        sd_power(True)
        return True
    if not p:
        _cd_since = None
        if _out0 & _X_SD_PWR:               # lines are driven only while it's on
            sd_power(False)
        return False
    now = time.ticks_ms()
    if _cd_since is None:
        _cd_since = now
    wait = SD_SETTLE_MS - time.ticks_diff(now, _cd_since)
    if wait > 0:
        time.sleep_ms(wait)
    sd_power(True)
    return True


def sd_power(on):
    """The SD socket's power switch, SD_PWR_EN (port 0 bit 6, #262). On: if
    it was off, it waits out the rest of SD_OFF_MS since it went off, turns
    on, and waits SD_ON_MS for VDD before returning. Off: the four SD lines
    are released first (_sd_lines_free), then the power goes, so no driven
    line ever meets an unpowered card (what killed the two cards of
    tspico-hardware #21). Nothing happens on proto1 (bit 6 isn't connected;
    its socket is always powered)."""
    global _sd_off_at
    if on:
        if _out0 & _X_SD_PWR:
            return
        if _sd_off_at is not None:
            wait = SD_OFF_MS - time.ticks_diff(time.ticks_ms(), _sd_off_at)
            if wait > 0:
                time.sleep_ms(wait)
        _port0(_X_SD_PWR, _X_SD_PWR)
        time.sleep_ms(SD_ON_MS)
    else:
        _sd_lines_free()
        if _out0 & _X_SD_PWR:
            _port0(_X_SD_PWR, 0)
            _sd_off_at = time.ticks_ms()


def _sd_power_off_at_import():
    """A soft reset starts _out0 again at _IOX_OUT0_SAFE (socket off) but
    leaves the expander as it was: with the socket powered if a card was
    mounted. The LED's next write would switch it off under whatever the
    SPI pins were left driving. So, once at import: if the expander says the
    socket is on, release the lines, then switch it off."""
    global _sd_off_at
    try:
        out = _iox().readfrom_mem(_IOX_ADDR, _IOX_OUT0, 1)[0]
        if out & _X_SD_PWR:
            _sd_lines_free()
            _out0_buf[0] = out & ~_X_SD_PWR
            _iox().writeto_mem(_IOX_ADDR, _IOX_OUT0, _out0_buf)
            _sd_off_at = time.ticks_ms()
    except OSError:
        pass                    # no expander answering: nothing to switch


def sd_take_bus():
    """The SD card has its own pins: the bus stays as it is. Returns MQ."""
    return tsbus.MQ()


def sd_cs():
    """The SD card's chip select, GPIO 37, driven high (deselected)."""
    return Pin(_SD_CS, Pin.OUT, value=1)


def sd_spi():
    """SPI0 on its own pins: SCK 38, MOSI 39, MISO 32."""
    return SPI(0, sck=Pin(_SD_SCK), mosi=Pin(_SD_MOSI), miso=Pin(_SD_MISO))


def sd_release_bus():
    """After the card is unmounted: the lines released, then the socket
    switched off (sd_power(False)), so every command powers the card for its
    own mount. ACTIVATE_SD powers it again (sd_card_ready)."""
    sd_power(False)


def _sd_lines_free():
    """Nothing drives the socket. CS, SCK, MOSI and MISO go back to plain
    inputs, no pulls (RP2350 erratum E9: a pull-down can latch the pad), as
    board_init.c leaves them at power-on. R34 holds CS high, so a card that
    is in stays deselected, and R35 holds MISO; SCK and MOSI float behind
    their 33R. On proto2 R34 and R35 are on the switched rail, so with the
    socket off they hold nothing up either. A card going in then meets no
    driven line, which could power it through its I/O pins before its VDD
    contact makes."""
    for p in (_SD_CS, _SD_SCK, _SD_MOSI, _SD_MISO):
        Pin(p, Pin.IN, pull=None)


_sd_power_off_at_import()


class ExpanderLED:
    """D4, on the XL9555's port 0 bit 5 (active low), with Pin's value, on,
    off and toggle, dimmed to LED_BRIGHTNESS %.

    While it is on, a periodic machine.Timer lights it every LED_PERIOD_US
    and a one-shot timer darkens it again after the on-time: two I2C writes
    (about 100 us each) per period, whatever the brightness; none while it
    is off (both timers stopped). At 100 % it is simply lit. The timers'
    callbacks are soft (scheduled on core 0), so a long C call there stretches
    a period: a flicker, not a fault. It changes only its own bit of port 0
    (_port0), so the ESP32's EN and IO9 stay as they were set."""

    def __init__(self):
        self._v = 0
        self._lit = False
        self._on_us = LED_PERIOD_US * LED_BRIGHTNESS // 100
        self._period = None
        self._off = None
        self._light_cb = self._light    # bound once: the callbacks allocate nothing
        self._dark_cb = self._dark

    def _write(self, lit):
        if lit != self._lit:
            self._lit = lit
            _port0(_X_NLED, 0 if lit else _X_NLED)   # no expander answering: the LED is cosmetic

    def _light(self, t):
        self._write(True)
        self._off.init(mode=Timer.ONE_SHOT, period=self._on_us, tick_hz=1_000_000, callback=self._dark_cb)

    def _dark(self, t):
        self._write(False)

    def _stop(self):
        for t in (self._period, self._off):
            if t is not None:
                t.deinit()
        self._period = self._off = None

    def _start(self):
        self._write(True)
        if self._on_us < LED_PERIOD_US:
            self._off = Timer()
            self._off.init(mode=Timer.ONE_SHOT, period=self._on_us, tick_hz=1_000_000, callback=self._dark_cb)
            self._period = Timer(mode=Timer.PERIODIC, period=LED_PERIOD_US, tick_hz=1_000_000, callback=self._light_cb)

    def brightness(self, pct):
        """The on-time as a percentage of the period, 1-100."""
        self._on_us = LED_PERIOD_US * pct // 100
        if self._v:
            self._stop()
            self._start()

    def value(self, v=None):
        if v is None:
            return self._v
        v = 1 if v else 0
        if v != self._v:
            self._v = v
            if v:
                self._start()
            else:
                self._stop()
                self._write(False)
        return None

    def on(self):
        self.value(1)

    def off(self):
        self.value(0)

    def toggle(self):
        self.value(not self._v)


def make_led():
    """The LED: D4 through the expander."""
    return ExpanderLED()


def led_brightness(led, pct):
    """config.ini's LED_BRIGHTNESS (1-100, %) for the LED make_led gave."""
    led.brightness(pct)


def background(fn, args):
    """Core 1 belongs to tsbus: run fn(*args) here, on core 0."""
    fn(*args)
