"""TS-Pico upgrade firmware: the Pico side of the ROM update.

This is not the TS-Pico firmware. It is a separate UF2 (see src/upgrade/
main.py and tools/build-upgrade.sh) that the web updater writes before the
real firmware, for a board coming from 1.1 / 1.5 whose TS-2068 ROM can't
talk to the current firmware. It does two things:

1. Serve the updater tape to the ORIGINAL slot-0 Spectrum ROM, which every
   shipped flash image has. The user types OUT 244,3 on the 2068 (the
   Spectrum ROM, whatever the 2068 ROM is) and LOAD "". That ROM has no
   handshake -- 'L', a fixed ~0.94 ms, then it reads -- so TX always holds
   the tape as one stream (tspico_io's TAPE_STREAM_OF / ZX_ARM /
   ZX_STREAM, proven on a v15w board). READY goes up at each 'L' too, so a
   board that already has ZX v3 in slot 0 (which waits for it) can run the
   upgrade again. (ZX v2 can't: its WAIT_RDY bug breaks every LOAD.)

2. Answer the updater (src/upgrade/updater.asm) once it runs. Its requests
   are a port-0Fh write (the tape never has one) plus arguments on 0Eh; the
   reply is queued and then READY is raised:

       'I'              -> 'T','P', version, 0        (the tape stops)
       'R' image,block  -> 256 bytes + their XOR      image 1: slot 1, 0: slot 0
       'S' code,arg     -> 0                          progress

Everything it learns goes to the USB serial port as one line per event,
"UPG {json}", for the web page: waiting, tape, updater, each status (P
phase, E erased, W block written, V verified, D done, X failed) and
anything it ignored.

`data` is the generated upgrade_data module: TAPE (the updater .tap), IMG1
(the TS-2068 ROM for slot 1, 32K) and IMG0 (the ZX ROM for slot 0, 16K).

This UF2 has only the modules src/upgrade/manifest.py freezes. It imports
TS.tspico_io, which is shared with the TS-Pico firmware, so whatever
tspico_io imports when it loads has to be frozen here too. #82's
`from TS import native` wasn't, and until 2026-10-01 this UF2 died at boot
with ImportError. src/test/upgrade_hosttest.py now checks this, and
docs/DEVELOPER_GUIDE.md ("The upgrade UF2 is a second build of
tspico_io.py") has the rules.
"""
import gc
import json
import time

from TS.tspico_io import (MQX, TAPE_STREAM_OF, ZX_ARM, ZX_STREAM, ZX_FLUSH_TX,
                          ZX_ROOM, RX_WORD, TX_DEPTH, PORT_0F)

VERSION = 1
REWIND_MS = 5000        # a LOAD stopped part-way: rewind the tape after this
STATUS_NAMES = {"P": "phase", "E": "erased", "W": "written", "V": "verified",
                "D": "done", "X": "failed"}


def report(event, **kw):
    """One line for the web page."""
    kw["event"] = event
    print("UPG " + json.dumps(kw))


def reply(MQ, data):
    """Queue data for the Z80: the first bytes go in before READY (it reads
    the instant it sees it), the rest as it reads (~44 us a byte). False if
    it stopped reading."""
    ZX_FLUSH_TX(MQ)
    n = len(data)
    i = 0
    while i < n and MQ.tx_fifo() < TX_DEPTH:
        MQ.put(data[i])
        i += 1
    MQX(MQ, "mov(y, invert(null))")         # READY
    while i < n:
        if ZX_ROOM(MQ, 1000) != -1:
            ZX_FLUSH_TX(MQ)
            return False
        MQ.put(data[i])
        i += 1
    return True


def drained(MQ, ms):
    """Wait (bounded) for the Z80 to read what's left in TX."""
    t0 = time.ticks_ms()
    while MQ.tx_fifo() and time.ticks_diff(time.ticks_ms(), t0) < ms:
        pass
    return not MQ.tx_fifo()


def serve(MQ, data):
    """Run the update, forever: the Pico has nothing else to do until the web
    page writes the real firmware."""
    images = {0: data.IMG0, 1: data.IMG1}
    stream, starts = TAPE_STREAM_OF(data.TAPE)
    blk = bytearray(257)
    service = False                         # the updater is running
    report("waiting", say='On the 2068: OUT 244,3, then LOAD ""')
    gc.collect()
    pos = ZX_ARM(MQ, stream)
    loading = False
    while True:
        if service:
            while not MQ.rx_fifo():
                pass
            w = MQ.get()
        else:
            w, pos = ZX_STREAM(MQ, stream, pos, REWIND_MS)

        if not w & PORT_0F:
            if w == 0x4C:                   # the Spectrum ROM's LD-BYTES
                # Its bytes are already queued. The original ROM just reads;
                # ZX v3 (a board upgraded before) polls READY first -- raise it.
                MQX(MQ, "mov(y, invert(null))")
                if service:                 # a reset, and LOAD "" again
                    service = False
                    pos = ZX_ARM(MQ, stream)
                    report("tape", note="the updater stopped; tape rewound")
                elif not loading:
                    loading = True
                    report("tape")
                continue
            if service:
                continue                    # a stray byte: the updater only writes 0Fh first
            # An old TS-2068 ROM's command: swallow the burst, rewind the tape.
            t0 = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), t0) < 50:
                if MQ.rx_fifo():
                    MQ.get()
                    t0 = time.ticks_ms()
            pos = ZX_ARM(MQ, stream)
            loading = False
            report("ignored", byte=w & 0xFF, say='That was the TS-2068 ROM: type OUT 244,3 first')
            continue

        c = w & 0xFF
        if c == 0x49:                                           # 'I'
            service = True
            loading = False
            reply(MQ, bytes((0x54, 0x50, VERSION, 0)))
            report("updater")
        elif c == 0x52:                                         # 'R'
            img = RX_WORD(MQ, 100)
            b = RX_WORD(MQ, 100)
            if img < 0 or b < 0:
                continue                    # it times out and asks again
            src = images.get(img & 0xFF)
            off = (b & 0xFF) * 256
            if src is None or off + 256 > len(src):
                report("bad-request", image=img & 0xFF, block=b & 0xFF)
                continue
            x = 0
            for i in range(256):
                v = src[off + i]
                blk[i] = v
                x ^= v
            blk[256] = x
            reply(MQ, blk)
        elif c == 0x53:                                         # 'S'
            code = RX_WORD(MQ, 100)
            arg = RX_WORD(MQ, 100)
            if code < 0 or arg < 0:
                continue
            code = chr(code & 0xFF)
            reply(MQ, b"\x00")
            report("status", code=code, what=STATUS_NAMES.get(code, "?"), arg=arg & 0xFF)
            if code == "X":                 # back to BASIC: LOAD "" tries again
                drained(MQ, 200)
                service = False
                pos = ZX_ARM(MQ, stream)
        elif not service:
            ZX_FLUSH_TX(MQ)                 # a 0Fh write that isn't ours (a 1.8b SYNC)
            pos = ZX_ARM(MQ, stream)
