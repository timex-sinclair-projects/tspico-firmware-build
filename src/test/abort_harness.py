"""BREAK / SYNC harness -- a clean-room Pico side for the 1.8b "sync" test ROM.

Why this exists
---------------
Issue #51: when the user presses BREAK mid-transaction the 2068 stops talking
and the Pico is left mid-transaction, so the next command often fails with
Report J. The 1.8b test ROM (src/rom/TSPICO-SYNC.ROM, built from
src/rom/patches/tspico-sync.asm) now tells the Pico, by writing a control
byte to port 0Fh. This harness proves the Pico side of that, in isolation,
before any of it goes near production (src/CLAUDE.md, harness-first):

  1. a Z80 write to 0Fh is seen, at any point, as bit 8 of the RX word;
  2. one return-to-idle routine gets the Pico back to a known state;
  3. the new status values (0xFF idle, 0xF7 ready mid-transaction, 0xFB
     recovered) reach the ROM;
  4. the LOAD send loop never blocks in MQ.put(), so it can hear an abort;
  5. the SAVE drain and the 0x86 key wait hear an abort too.

What the ROM does (see tspico-sync.asm)
---------------------------------------
  OUT (0Fh),03h    SYNC before the first byte of every LOAD / SAVE-header /
                   TPI: command / LPRINT / COPY, and the BREAK abort. Then it
                   waits up to ~1 s for status READY (bit 6) + IDLE (bit 3).
  status bit 2     RECOVERED, active low. Seen while the ROM waits for READY,
                   it raises "T TS-Pico reset, try again".
  BREAK            checked every 256 bytes of a LOAD or SAVE block, in the
                   key waits (0x86 prompts), and in every ready-wait.

Status values (Y register -> port 0Fh)
---------------------------------------
  0xFF  idle       ready, no transaction open, not recovered (== old firmware)
  0xF7  mid        ready, transaction open (IDLE clear): SYNC_WAIT keeps
                   waiting, so a SYNC can't race a phase's READY
  0xFB  recovered  ready + idle, RECOVERED low: this Pico gave up on a
                   transaction on its own (stall). Cleared by the next SYNC.
  0x00  busy       set by the PIO itself on every Z80 write (issue #14)

The harness answers
-------------------
  LOAD ""           a synthetic BASIC program: one REM line, LOAD_PROG_LEN
                    bytes -- long enough to press BREAK in the middle.
  SAVE "x" ...      any SAVE; the data is received, checked and discarded
                    (a partial SAVE after BREAK must never be written). The
                    session ID (pre-header bytes 3-4) must repeat in both
                    blocks. If the data block doesn't open with FF + session,
                    the SAVE was abandoned after its header -- v1.7 and
                    earlier don't tell the Pico -- and those bytes are kept as
                    the start of the next command, so it isn't swallowed.
  SAVE "tpi:..."    any TPI command gets PAGES pages of 0x86 paged output, so
                    BREAK can be tried at the "Scroll?" key wait.

Structure: all hardware actions are inside boot()/main(). The protocol engine
(Link, Harness) only uses an MQ-like object, so it runs unchanged on CPython
against a simulated Z80 (src/test/abort_harness_hosttest.py) and against the
ZEsarUX bridge.

Usage on a Pico
---------------
  1. Flash TSPICO-SYNC.ROM into a spare slot (e.g. with romupdate) and set
     ROM_SLOT below to that slot.
  2. Copy this file to the Pico (Thonny) and run it. Power on the TS-2068.
  3. Try: LOAD ""  (BREAK during the block),  SAVE "t" CODE 0,40000  (BREAK
     during the block),  SAVE "tpi:dir"  (BREAK at "Scroll?"), and each one
     again without BREAK. After every BREAK the next command must work first
     time.
  4. With ROM_SLOT = 1 (shipping v1.7, no SYNC): SAVE "t", hold BREAK so it
     stops after "Bytes:"/"Program:", then LOAD "" -- the log should show
     [stale] and the LOAD should work first time.
  5. Watch the USB serial log. Ctrl-C prints a summary.
"""

import time
import gc
from array import array

HARNESS_VERSION = "abort_harness v2 (2026-09-26)"

# ===========================================================================
# CONFIG -- edit these, then re-run.
# ===========================================================================

ROM_SLOT = 1            # flash slot holding TSPICO-SYNC.ROM (1 = shipping v1.7)
DCK_SLOT = 0

STALL_MS = 1500         # silence inside a transaction that counts as a stall
SAVE_DATA_START_MS = 3000   # the Z80 can take ~1 s before a SAVE data block
KEY_WAIT_MS = 120000    # how long a 0x86 "Scroll?" prompt waits for a key

LOAD_PROG_LEN = 16000   # bytes in the synthetic REM line served by LOAD ""
PAGES = 4               # 0x86 pages served for any TPI: command

VERBOSE = True

# ===========================================================================
# Protocol constants
# ===========================================================================

PORT_BIT = 0x100        # A0 lands in bit 8 of every RX word: set = port 0Fh
ABORT_BYTE = 0x03       # what the ROM writes to 0Fh (SYNC and BREAK abort)
TX_DEPTH = 4            # TS_IO_DUAL FIFOs are not joined: 4 words each way

ST_IDLE, ST_MID, ST_RECOVERED = "idle", "mid", "recovered"


# MicroPython note: these exceptions carry their data in args -- no custom
# __init__ (MicroPython can't call Exception.__init__) and no instance
# attributes. Read them with got() / detail() / e.args[0].

class Abort(Exception):
    """The Z80 wrote to port 0Fh (SYNC or BREAK) in the middle of something.
    args[0] = words received up to and including that write."""


class Stall(Exception):
    """The Z80 went quiet mid-transaction with no abort (reset, old ROM, or
    bytes the PIO dropped). args[0] = words received before the silence;
    args[1], if present, says why."""


class Mismatch(Stall):
    """Bytes that can't belong to this transaction (session ID disagrees):
    give up on it as recovered, like a stall."""


class NotOurs(Exception):
    """A SAVE's data block didn't open with FF + this statement's session ID.
    With v1.7 and earlier (no SYNC) that means the SAVE was abandoned after
    its header -- a BREAK in the ready-wait -- and these bytes are the start
    of the user's next command. args[0] = that command's 10-byte pre-header."""


def got(e):
    return e.args[0] if e.args else 0


def detail(e):
    return e.args[1] if len(e.args) > 1 else ""


# ===========================================================================
# Link -- the MQ transport with abort detection. Nothing here blocks forever.
# ===========================================================================

class Link:
    def __init__(self, mq, ticks_ms, ticks_diff):
        self.mq = mq
        self.ticks_ms = ticks_ms
        self.ticks_diff = ticks_diff
        self.status = None

    # ---- status (Y register) ----------------------------------------------
    def set_status(self, st):
        ex = self.mq.exec
        if st == ST_IDLE:
            ex("mov(y, invert(null))")          # 0xFF
        elif st == ST_MID:
            ex("set(y, 8)")                     # transient 0x08 = busy
            ex("mov(y, invert(y))")             # 0xF7
        else:
            ex("set(y, 4)")                     # transient 0x04 = busy
            ex("mov(y, invert(y))")             # 0xFB
        self.status = st

    # ---- receive ------------------------------------------------------------
    def get(self, stall_ms):
        """One byte from the Z80. Raises Abort on a port-0Fh write, Stall if
        nothing arrives for stall_ms."""
        mq = self.mq
        if not mq.rx_fifo():
            t0 = self.ticks_ms()
            while not mq.rx_fifo():
                if self.ticks_diff(self.ticks_ms(), t0) >= stall_ms:
                    raise Stall(0)
        w = mq.get()
        if w & PORT_BIT:
            raise Abort(1)
        return w

    # THE TWO-PHASE RULE (src/CLAUDE.md): the Z80 writes a byte every
    # ~30-40 us and the RX FIFO holds 4, so the loop that takes a burst may do
    # nothing per byte but test the FIFO, get() and store. Everything else --
    # the abort test, the clock -- happens only when the FIFO is empty, which
    # is exactly when the Z80 has paused or stopped. A port-0Fh write is
    # always the last thing the Z80 sends before it stops, so it is always
    # the newest word when the FIFO runs dry.

    def drain(self, raw, n, stall_ms, first_ms=None):
        """Fill raw[0:n] (an array('H'): words are 9-bit) from the Z80."""
        rx = self.mq.rx_fifo
        get = self.mq.get
        got = 0
        limit = stall_ms if first_ms is None else first_ms
        while got < n:
            if rx():
                raw[got] = get()
                got += 1
            else:
                if got and raw[got - 1] & 0x100:
                    raise Abort(got)
                ticks, diff = self.ticks_ms, self.ticks_diff
                t0 = ticks()
                while not rx():
                    if diff(ticks(), t0) >= limit:
                        raise Stall(got)
                limit = stall_ms
        if raw[n - 1] & 0x100:
            raise Abort(n)
        return n

    def drain_xor(self, n, stall_ms, first_ms=None):
        """Take n bytes without storing them and return their XOR. Data bytes
        are 0-255, so a port-0Fh word (0x100 | value) shows up as bit 8 of
        the running XOR: the abort test costs nothing per byte."""
        rx = self.mq.rx_fifo
        get = self.mq.get
        p = 0
        got = 0
        limit = stall_ms if first_ms is None else first_ms
        while got < n:
            if rx():
                p ^= get()
                got += 1
            else:
                if p & 0x100:
                    raise Abort(got)
                ticks, diff = self.ticks_ms, self.ticks_diff
                t0 = ticks()
                while not rx():
                    if diff(ticks(), t0) >= limit:
                        raise Stall(got)
                limit = stall_ms
        if p & 0x100:
            raise Abort(n)
        return p

    # ---- send ---------------------------------------------------------------
    def send(self, b, echo):
        """Queue one byte for the Z80 without ever blocking in MQ.put(). While
        the TX FIFO is full, listen: a port-0Fh write aborts, and any data
        byte the Z80 writes meanwhile is appended to `echo`."""
        mq = self.mq
        if mq.tx_fifo() >= TX_DEPTH:
            t0 = self.ticks_ms()
            while mq.tx_fifo() >= TX_DEPTH:
                if mq.rx_fifo():
                    w = mq.get()
                    if w & PORT_BIT:
                        raise Abort()
                    echo.append(w)
                elif self.ticks_diff(self.ticks_ms(), t0) >= STALL_MS:
                    raise Stall()
        mq.put(b)

    def tx_wait(self, echo):
        """The LOAD loop's slow path: TX is full, so the Z80 hasn't read yet.
        Listen until there is room, as send() does."""
        mq = self.mq
        t0 = self.ticks_ms()
        while mq.tx_fifo() >= TX_DEPTH:
            if mq.rx_fifo():
                w = mq.get()
                if w & PORT_BIT:
                    raise Abort()
                echo.append(w)
            elif self.ticks_diff(self.ticks_ms(), t0) >= STALL_MS:
                raise Stall()

    def wait_tx_empty(self, echo):
        """Wait until the Z80 has read everything queued, listening as send()."""
        mq = self.mq
        t0 = self.ticks_ms()
        while mq.tx_fifo():
            if mq.rx_fifo():
                w = mq.get()
                if w & PORT_BIT:
                    raise Abort()
                echo.append(w)
            elif self.ticks_diff(self.ticks_ms(), t0) >= STALL_MS:
                raise Stall()

    # ---- the one way back to idle ------------------------------------------
    def to_idle(self, recovered=False):
        """Known state for the next command, whatever happened: TX and RX
        empty, exactly one 0x01 pre-load staged (the ROM reads it with no
        wait straight after the next pre-header), status idle or recovered."""
        mq = self.mq
        n = 0
        while mq.tx_fifo() and n < 64:
            mq.exec("pull(noblock)")            # TX FIFO -> OSR, discarded
            n += 1
        while mq.rx_fifo():
            mq.get()
        mq.put(0x01)
        self.set_status(ST_RECOVERED if recovered else ST_IDLE)


# ===========================================================================
# Harness -- dispatch + the three transaction types
# ===========================================================================

def xor_all(buf, start, end, seed=0):
    for i in range(start, end):
        seed ^= buf[i]
    return seed


def make_program(n):
    """A one-line BASIC program: 10 REM AAAA...ZZZZ... (n bytes in total)."""
    body = n - 6                                # line no, length, REM, CR
    prog = bytearray(n)
    prog[0], prog[1] = 0x00, 0x0A               # line 10
    prog[2], prog[3] = (body + 2) & 0xFF, (body + 2) >> 8
    prog[4] = 0xEA                              # REM
    for i in range(body):
        prog[5 + i] = 0x41 + (i % 26)
    prog[n - 1] = 0x0D
    return prog


def make_header(name, prog_len):
    """17-byte ZX/TS header content for a BASIC program, no autorun."""
    h = bytearray(17)
    h[0] = 0x00                                 # program
    nm = (name + " " * 10)[:10]
    for i in range(10):
        h[1 + i] = ord(nm[i])
    h[11], h[12] = prog_len & 0xFF, prog_len >> 8
    h[13], h[14] = 0x00, 0x80                   # autorun >= 32768: none
    h[15], h[16] = prog_len & 0xFF, prog_len >> 8
    return h


class Harness:
    def __init__(self, mq, ticks_ms=None, ticks_diff=None, log=print):
        self.link = Link(mq, ticks_ms or time.ticks_ms,
                         ticks_diff or time.ticks_diff)
        self.log = log if VERBOSE else (lambda *a: None)
        self.pre = bytearray(10)
        self.raw = array("H", [0] * 32)         # burst capture, 9-bit words
        self.rest = array("H", [0] * 8)
        self.header = make_header("breaktest", LOAD_PROG_LEN)
        self.program = make_program(LOAD_PROG_LEN)
        self.header_parity = xor_all(self.header, 0, len(self.header), 0x00)
        self.program_parity = xor_all(self.program, 0, len(self.program), 0xFF)
        self.stats = {"sync": 0, "load": 0, "save": 0, "cmd": 0,
                      "abort": 0, "stall": 0, "error": 0, "other": 0,
                      "stale": 0, "mismatch": 0}
        self.events = []        # (kind, detail) -- for the host test

    def start(self):
        self.link.to_idle()

    def _event(self, kind, detail=""):
        self.events.append((kind, detail))
        self.log("[%s] %s" % (kind, detail))

    # ---- one command --------------------------------------------------------
    def serve_once(self, idle_ms=None):
        """Handle one command, or one stray SYNC. Returns False if nothing
        arrived within idle_ms (None = wait forever)."""
        link, mq = self.link, self.link.mq
        rx = mq.rx_fifo
        raw = self.raw
        if not rx():
            t0 = link.ticks_ms()
            while not rx():
                if idle_ms is not None and link.ticks_diff(link.ticks_ms(), t0) >= idle_ms:
                    return False
        self.what = "pre-header"
        try:
            # Straight into the tight capture: the first byte is not taken on
            # its own, because the Z80 sends the other nine right behind it.
            try:
                link.drain(raw, 10, STALL_MS)
            except Abort as a:
                if got(a) == 1:
                    # A lone port-0Fh write: SYNC (the ROM then waits for
                    # READY + IDLE before it sends anything else).
                    self.stats["sync"] += 1
                    link.to_idle()
                    self._event("sync", "0Fh <- %02X" % (raw[0] & 0xFF))
                    return True
                raise
            pre = self.pre
            for i in range(10):
                pre[i] = raw[i]
            while True:
                try:
                    self.dispatch()
                    break
                except NotOurs as e:
                    # save() already took the whole of this next pre-header
                    # (and made sure its 0x01 status is waiting); serve it.
                    self.stats["stale"] += 1
                    self._event("stale", "SAVE abandoned after its header; "
                                "%s opens the next command" % " ".join("%02X" % b for b in e.args[0]))
                    for i in range(10):
                        pre[i] = e.args[0][i]
                    self.what = "pre-header"
        except Abort as a:
            self.stats["abort"] += 1
            link.to_idle()
            self._event("abort", self.what)
        except Mismatch as e:
            self.stats["mismatch"] += 1
            link.to_idle(recovered=True)
            self._event("mismatch", "%s: %s -> RECOVERED" % (self.what, detail(e)))
        except Stall as e:
            self.stats["stall"] += 1
            evidence = ""
            if self.what == "pre-header":
                n = got(e)
                evidence = ": got %d/10 [%s]" % (n, " ".join(
                    "%03X" % raw[i] for i in range(n)))
            elif got(e):
                evidence = ": %d bytes then silence" % got(e)
            link.to_idle(recovered=True)
            self._event("stall", "%s%s -> RECOVERED" % (self.what, evidence))
        except Exception as e:                  # never leave the bus in a mess
            self.stats["error"] += 1
            link.to_idle(recovered=True)
            self._event("error", "%s: %r" % (self.what, e))
        return True

    def dispatch(self):
        pre, link = self.pre, self.link
        if pre[0] == 0x00 and pre[1] == 0x00:
            self.what = "save"
            self.save()
        elif pre[0] in (0x00, 0xFF) and 0 < pre[1] < 10:
            self.what = "load"
            self.load()
        elif pre[0] == 0x42:
            self.what = "cmd"
            self.command()
        else:
            self.stats["other"] += 1
            link.to_idle()
            self._event("other", " ".join("%02X" % b for b in pre))

    # ---- LOAD ---------------------------------------------------------------
    def load(self):
        """Serve the synthetic tape: header block for pre[0]=00, data block
        for pre[0]=FF. Wire: [flag][content][parity] out; the Z80 writes one
        byte before the block and one after (the 'echo')."""
        link, mq = self.link, self.link.mq
        if self.pre[0] == 0x00:
            flag, body, parity = 0x00, self.header, self.header_parity
        else:
            flag, body, parity = 0xFF, self.program, self.program_parity
        echo = []
        put = mq.put
        txf = mq.tx_fifo
        depth = TX_DEPTH                        # local: no global lookup per byte
        # The Z80 reads the pre-load status (already in TX) with no wait, then
        # waits for READY. Queue the start of the block BEFORE saying READY.
        put(flag)
        n = len(body)
        i = 0
        while i < n and txf() < depth:
            put(body[i])
            i += 1
        link.set_status(ST_MID)
        # The Z80 reads a byte every ~30-40 us with no handshake: an empty TX
        # FIFO hands it 0x00. Per byte: one FIFO test, one put -- the slow
        # path (TX full) is where we listen for an abort.
        while i < n:
            if txf() < depth:
                put(body[i])
                i += 1
            else:
                link.tx_wait(echo)
        if txf() >= depth:
            link.tx_wait(echo)
        put(parity)
        link.wait_tx_empty(echo)
        while len(echo) < 2:
            echo.append(link.get(STALL_MS))
        # Final status + next command's pre-load, then idle.
        put(0x01)
        put(0x01)
        link.set_status(ST_IDLE)
        self.stats["load"] += 1
        self._event("load", "%s block %d bytes, echo %s" % (
            "header" if flag == 0 else "data", n + 2,
            " ".join("%02X" % e for e in echo)))

    # ---- SAVE ---------------------------------------------------------------
    def save(self):
        """Header block (21) then data block (BLEN+4), received and checked,
        never written anywhere.

        Session ID: bytes 3-4 of the pre-header, repeated as bytes 1-2 of both
        blocks (FRAMES-derived, one per BASIC statement; 0000 = not from BASIC,
        so not checked). The header's copy must match, or the bytes are
        misaligned. The data block's first three bytes are read on their own
        and must be FF + the session: if not, this SAVE was abandoned and
        they belong to the next command (see NotOurs)."""
        link, mq = self.link, self.link.mq
        raw = self.raw
        s_lo, s_hi = self.pre[3], self.pre[4]
        check_session = s_lo or s_hi
        link.set_status(ST_MID)
        link.drain(raw, 21, STALL_MS, first_ms=STALL_MS)
        if check_session and (raw[1] != s_lo or raw[2] != s_hi):
            raise Mismatch(21, "header block session %02X%02X, pre-header %02X%02X" % (
                raw[2], raw[1], s_hi, s_lo))
        hcrc_ok = xor_all(raw, 3, 20, seed=raw[0]) == raw[20]
        blen = raw[14] | (raw[15] << 8)
        name = "".join(chr(c) if 32 <= c < 127 else "?" for c in raw[4:14])
        mq.put(0x01)                            # header-block status
        link.set_status(ST_MID)                 # data block still to come

        link.drain(raw, 3, STALL_MS, first_ms=SAVE_DATA_START_MS)
        if raw[0] != 0xFF or (check_session and (raw[1] != s_lo or raw[2] != s_hi)):
            # Not our data block: the first three bytes of the next command's
            # pre-header, with seven more right behind. Its status is read
            # with no wait after the tenth, so stage the 0x01 now if TX is
            # empty (with v1.7 the header-block status is usually still
            # there, unread), then take the rest before doing anything else.
            if not mq.tx_fifo():
                mq.put(0x01)
            head = [raw[0], raw[1], raw[2]]
            link.drain(self.rest, 7, STALL_MS)
            raise NotOurs(head + [self.rest[i] for i in range(7)])

        # Content + parity: BLEN+1 bytes, XORed on the fly and not stored.
        # The parity seeds with the flag (FF) and skips the session bytes, so
        # XOR(content) ^ parity == FF for a good block.
        p = link.drain_xor(blen + 1, STALL_MS)
        dcrc_ok = p == 0xFF
        mq.put(0x01)                            # final status
        mq.put(0x01)                            # next command's pre-load
        link.set_status(ST_IDLE)
        self.stats["save"] += 1
        self._event("save", "%r BLEN=%d hdrCRC=%s dataCRC=%s session=%02X%02X (discarded)" % (
            name, blen, hcrc_ok, dcrc_ok, s_hi, s_lo))

    # ---- TPI: command -> 0x86 pages ----------------------------------------
    def command(self):
        """Any 'B' command: read its body, then PAGES pages of 0x86 output
        with a "Scroll? (Y/n)" key wait between pages."""
        link = self.link
        # ROM 223Eh: reads the pre-load status (no wait), then WAIT_PICO_READY
        # at 2247h before it sends the 'D' body -- so say READY first.
        link.set_status(ST_MID)
        # Body = 'D', len lo, len hi, text, XOR of all of those (ROM 224Dh-
        # 2274h). Production reads len+3 and leaves the checksum byte for
        # SEND_MSG2's RX flush; read it here, or its late arrival drops the
        # status back to busy after we have said READY.
        n = self.pre[7] + 256 * self.pre[8]
        body = array("H", [0] * (n + 4))
        link.drain(body, n + 4, STALL_MS)
        sum_ok = xor_all(body, 0, n + 3) == body[n + 3]
        cmd = "".join(chr(c) if 32 <= c < 127 else "?" for c in body[3:n + 3]).strip()
        if not sum_ok:
            # As production's FAIL_CMD: one status byte (02 -> Report R), then
            # the next command's pre-load.
            link.mq.put(0x02)
            link.mq.put(0x01)
            link.set_status(ST_IDLE)
            self.stats["cmd"] += 1
            self._event("cmd", "%r bad checksum -> Report R" % cmd)
            return
        echo = []
        send = link.send
        send(0x86, echo)                        # PRINT_STRING_WITH_LOOP
        send(0x01, echo)                        # return code: 01 = OK (02B9h
                                                # quietly gives up on 00)
        send(0x0D, echo)
        link.set_status(ST_MID)
        prompt = b"Scroll? (Y/n)"
        for page in range(1, PAGES + 1):
            for line in range(1, 5):
                text = "page %d/%d line %d: %s" % (page, PAGES, line, cmd)
                for ch in text[:31]:
                    send(ord(ch), echo)
                send(0x0D, echo)
            if page == PAGES:
                break
            for ch in prompt:
                send(ch, echo)
            send(0x00, echo)                    # end of this page
            link.wait_tx_empty(echo)
            del echo[:]
            link.set_status(ST_MID)
            key = link.get(KEY_WAIT_MS)         # the Z80's SEND_KEY
            if key == 0x4E:                     # 'N'
                link.mq.put(0x01)               # next command's pre-load
                link.set_status(ST_IDLE)
                self.stats["cmd"] += 1
                self._event("cmd", "%r stopped with N at page %d" % (cmd, page))
                return
            link.set_status(ST_MID)
            for _ in range(len(prompt)):        # erase the prompt (new ROM)
                send(0x08, echo)
                send(0x20, echo)
                send(0x08, echo)
        send(0x03, echo)                        # end of message (new ROM)
        link.wait_tx_empty(echo)
        link.mq.put(0x01)                       # next command's pre-load
        link.set_status(ST_IDLE)
        self.stats["cmd"] += 1
        self._event("cmd", "%r all %d pages" % (cmd, PAGES))

    def summary(self):
        s = self.stats
        return ("SYNCs %(sync)d  LOADs %(load)d  SAVEs %(save)d  cmds %(cmd)d  "
                "aborts %(abort)d  stalls %(stall)d  stale SAVEs %(stale)d  "
                "session mismatches %(mismatch)d  errors %(error)d  other %(other)d" % s)


# ===========================================================================
# Pico hardware -- only runs on the device
# ===========================================================================

# ---------------------------------------------------------------------------
# PIO programs. The harness prefers the firmware's own copies (TS.tspico_io),
# but not every UF2 freezes that module, so it carries exact copies of the
# three it needs. abort_harness_hosttest.py checks they still match
# src/TS/tspico_io.py instruction for instruction.
# ---------------------------------------------------------------------------

try:
    from rp2 import asm_pio, PIO
except ImportError:                             # CPython (host test)
    asm_pio = None

if asm_pio is not None:
    @asm_pio(out_init=(PIO.OUT_LOW,) * 4, out_shiftdir=PIO.SHIFT_RIGHT,
             autopull=True, pull_thresh=8)
    def SEL_BANK():                             # bank selection via A15..A18
        wrap_target()
        pull(noblock)
        mov(x, osr)
        wait(0, gpio, 13)
        jmp(pin, "low")
        out(null, 4)
        out(pins, 4)
        jmp("fin")
        label("low")
        out(pins, 4)
        label("fin")
        wait(1, gpio, 13)
        wrap()

    @asm_pio(set_init=(PIO.OUT_HIGH,) * 2, in_shiftdir=PIO.SHIFT_LEFT,
             out_init=(PIO.OUT_HIGH,) * 2, out_shiftdir=PIO.SHIFT_RIGHT,
             autopull=True, pull_thresh=8)
    def SET_CTRL():                             # /BE, A14_L, /U10_CE, /U10_OE
        wrap_target()
        mov(pins, invert(null))
        mov(y, null)
        set(pins, 3)
        pull(noblock)
        mov(x, osr)
        wait(0, gpio, 13)
        nop()                  [2]
        jmp(pin, "low")
        out(null, 2)
        out(pins, 2)
        jmp("pass")
        label("low")
        in_(pins, 2)
        mov(y, isr)
        mov(isr, null)
        jmp(y_dec, "home")
        set(pins, 2)
        jmp("wait")
        label("home")
        jmp(y_dec, "pass")
        set(pins, 0)
        label("wait")
        nop()                  [10]
        out(pins, 2)
        label("pass")
        wait(1, gpio, 13)
        wrap()

    @asm_pio(sideset_init=(PIO.OUT_HIGH), out_init=(PIO.OUT_LOW,) * 8,
             out_shiftdir=PIO.SHIFT_RIGHT, in_shiftdir=PIO.SHIFT_LEFT)
    def TS_IO_DUAL_COPY():                      # dual-port $0E / $0F with auto-busy
        wait(0, gpio, 14)       .side(1)
        jmp(pin, "z80_out")     .side(1)
        in_(pins, 9)            .side(0)
        mov(osr, isr)           .side(0)
        mov(isr, null)          .side(0)
        out(null, 8)            .side(0)
        out(x, 1)               .side(0)
        jmp(not_x, "rd_data")   .side(0)
        mov(osr, y)             .side(0)
        out(pins, 8)            .side(0)
        jmp("fin")              .side(0)
        label("rd_data")
        pull(noblock)           .side(0)
        out(pins, 8)            .side(0)
        jmp("fin")              .side(0)
        label("z80_out")
        nop()                   .side(0)
        in_(pins, 9)            .side(0) [2]
        push(noblock)           .side(0)
        mov(y, null)            .side(0)
        label("fin")
        wait(1, gpio, 14)       .side(0)
        mov(null, osr)          .side(1)


def boot():
    from machine import Pin, freq
    from rp2 import StateMachine
    try:
        from TS.tspico_io import TS_IO_DUAL, set_ctrl, sel_bank
        pio_src = "TS.tspico_io"
    except ImportError:
        TS_IO_DUAL, set_ctrl, sel_bank = TS_IO_DUAL_COPY, SET_CTRL, SEL_BANK
        pio_src = "harness copies (no TS.tspico_io in this firmware)"

    freq(270_000_000)
    print("=" * 64)
    print(HARNESS_VERSION)
    print("  PIO programs from %s" % pio_src)
    print("  ROM_SLOT=%d  LOAD_PROG_LEN=%d  PAGES=%d" % (
        ROM_SLOT, LOAD_PROG_LEN, PAGES))
    print("=" * 64)
    for n in (12, 19, 20, 21, 27):
        Pin(n, Pin.OUT, Pin.PULL_UP).value(1)
    Pin(14, Pin.OUT, Pin.PULL_DOWN).value(1)
    Pin(26, Pin.IN, Pin.PULL_DOWN)
    rom_sm = StateMachine(4, set_ctrl, freq=150_000_000,
                          in_base=Pin(0, Pin.IN), jmp_pin=Pin(26),
                          set_base=Pin(21, Pin.OUT), out_base=Pin(19, Pin.OUT))
    rom_sm.active(1)
    bank_sm = StateMachine(5, sel_bank, freq=150_000_000,
                           jmp_pin=Pin(26), out_base=Pin(15, Pin.OUT))
    bank_sm.active(1)
    rom_sm.put(0x0A)                            # DCK and ROM from flash
    bank_sm.put(DCK_SLOT * 16 + ROM_SLOT)
    mq = StateMachine(0, TS_IO_DUAL, freq=30_000_000,
                      out_base=Pin(2, Pin.OUT), in_base=Pin(2, Pin.IN),
                      jmp_pin=Pin(11), sideset_base=Pin(12, Pin.OUT))
    mq.active(1)
    mq.exec("mov(y, invert(null))")
    t0 = time.ticks_ms()                        # boot noise
    while time.ticks_diff(time.ticks_ms(), t0) < 300:
        if mq.rx_fifo():
            mq.get()
            t0 = time.ticks_ms()
    print("[boot] ROM slot %d, MQ up" % ROM_SLOT)
    return mq


def main():
    mq = boot()
    h = Harness(mq)
    h.start()
    print('READY. Try LOAD "", SAVE "t" CODE 0,40000, SAVE "tpi:dir" -- with and')
    print("without BREAK. After every BREAK the next command must work first time.")
    gc.collect()
    try:
        while True:
            h.serve_once()
            gc.collect()
    except KeyboardInterrupt:
        pass
    print("")
    print("SUMMARY  " + h.summary())
    mq.active(0)


if __name__ == "__main__":
    main()
