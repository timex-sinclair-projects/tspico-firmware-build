"""Host-side test for command I/O (issue #51 stage 4) -- CPython, no Pico.

Runs the PRODUCTION TS.tspico.PROCESS_CMD, SEND_MSG and SEND_MSG2 against a
Z80 that follows the EXROM's command sequence: pre-load status read (no
wait), ready-wait, the body ('D', len, text, XOR), ready-wait, then the
reply -- a one-byte status, or an 0x86 print loop with "Scroll? (Y/n)" key
waits between pages. The simulated PIO is load_ts_hosttest's: 4-deep FIFOs,
A0 in bit 8 of every Z80 write, auto-busy, and a test FAILURE on any put()
into a full TX FIFO -- which blocks forever on a Pico.

What it pins:
  * a short command and a multi-page 0x86 listing still work (Y to page on,
    N to stop), ending with TX = [01], RX empty, status FF;
  * BREAK at a "Scroll?" prompt (the 1.8b ROM's 0Fh write from KEYWAIT):
    the handler stops at once -- no erase / next page into a TX nobody
    reads -- and the Z80 gets READY + IDLE for Report D. Before stage 4 the
    Pico hung here until reset;
  * the Z80 stopping reading mid-listing: RECOVERED after the stall, no hang;
  * BREAK / SYNC during the command body: straight back to idle, no hang;
  * READY for a command is said by PROCESS_CMD, not the dispatcher;
  * no scenario ever puts into a full TX FIFO (checked per scenario).

Run:  python3 src/test/cmd_io_hosttest.py
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import process_cmd_hosttest as P                                # noqa: E402
import load_ts_hosttest as L                                    # noqa: E402

READY, IDLE = L.READY, L.IDLE


class PIO(L.FakePIO):
    """Records a put() into a full TX FIFO before raising: PROCESS_CMD's
    `except Exception` swallows the raise (it is an AssertionError), so
    each scenario checks the flag itself.

    STRICT like the real Z80: the first read after a READY wait happens at
    once -- an empty TX reads as 00 (counted in empty_reads) instead of the
    base fake's patient wait. That is what caught READY-before-data in
    ListMenu (Commander crashed on tpi:cd once MQX made READY fast)."""
    blocked = False

    def __init__(self):
        L.FakePIO.__init__(self)
        self.empty_reads = 0
        self._after_ready = False

    def put(self, b):
        if isinstance(b, str):                  # rp2 takes a 1-char str as a buffer
            b = ord(b)
        if len(self.tx) >= 4:
            self.blocked = True
        return L.FakePIO.put(self, b)

    def pump(self):
        op = self.pending
        if self.script is not None and op is not None:
            if op[0] == "in" and self._after_ready:
                self._after_ready = False
                if self.tx:
                    self._advance(self.tx.pop(0))
                else:
                    self.empty_reads += 1
                    self._advance(0x00)
                return
            if op[0] == "wait" and (self.status() & op[1]) == op[1]:
                self._after_ready = True
            elif op[0] == "out":
                self._after_ready = False
        L.FakePIO.pump(self)

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


def z80_cmd(body, keys=(), break_at_prompt=None, stop_after=None, body_break_at=None):
    """The EXROM after the dispatcher has taken the command pre-header."""
    st = yield ("in",)                          # pre-load status, no wait
    if st != 0x01:
        return ("st%02X" % (st or 0),)
    r = yield from L.ready_wait()               # 2247h
    if r:
        return (r,)
    for i, b in enumerate(body):
        if body_break_at is not None and i == body_break_at:
            yield L.out(0x0F, 0x03)             # BRK_ABORT / SYNC
            yield ("wait", READY | IDLE, 3000)
            return ("D",)
        yield L.out(0x0E, b)
    r = yield from L.ready_wait()
    if r:
        return (r,)
    code = yield ("in",)
    if code != 0x86:                            # one-byte status reply
        return ("ok" if code == 0x01 else "st%02X" % code,)
    rc = yield ("in",)
    text = bytearray()
    prompts = 0
    while True:
        if stop_after is not None and len(text) >= stop_after:
            yield ("stop",)                     # the Z80 has gone
        c = yield ("in",)
        if c == 0x00:                           # end of page: key wait
            prompts += 1
            if break_at_prompt == prompts:
                yield L.out(0x0F, 0x03)         # KEYWAIT -> BRK_ABORT
                yield ("wait", READY | IDLE, 3000)
                return ("D", prompts, bytes(text))
            key = keys[prompts - 1] if prompts <= len(keys) else ord("Y")
            yield L.out(0x0E, key)
            if key == ord("N"):
                return ("N", prompts, bytes(text))
            r = yield from L.ready_wait()
            if r:
                return (r, prompts, bytes(text))
            continue
        if c == 0x03:                           # end of message
            return ("ok", prompts, bytes(text))
        text.append(c)


def z80_menu(body, key):
    """A command answered with ListMenu (tpi:cd): 0x86 page, key, echo."""
    st = yield ("in",)
    r = yield from L.ready_wait()
    if st != 0x01 or r:
        return ("start", st, r)
    for b in body:
        yield L.out(0x0E, b)
    r = yield from L.ready_wait()
    code = yield ("in",)
    if r or code != 0x86:
        return ("code", code, r)
    yield ("in",)                               # return code
    while True:
        c = yield ("in",)
        if c == 0x00:
            break
    yield L.out(0x0E, key)
    r = yield from L.ready_wait()
    text = bytearray()
    while True:
        c = yield ("in",)
        if c == 0x03:
            return ("ok", bytes(text))
        if c == 0x00:
            return ("page end instead of the echo", bytes(text))
        text.append(c)


def main():
    P.install_fakes()
    import TS.tspico as t
    import TS.tspico_io as tio
    t.TLM_ENABLED = False
    ft = L.FakeTime()
    t.time = ft
    tio.time = ft

    long_text = "".join("line %02d of the listing........\r" % i for i in range(1, 61))

    def handlers():
        def short(pre, cmd):
            t.SEND_MSG("done", "", t._1_OK)
        def listing(pre, cmd):
            t.SEND_MSG2(long_text, t._1_OK)
        def menu(pre, cmd):
            menu_result.append(t.ListMenu(["FIRST", "SECOND"], "hdr1", "hdr2", "hdr3",
                                          "Change to dir", "Changing to: "))
        def ask(pre, cmd):
            menu_result.append(t.SEND_MSG_PROMPT_YN("Sure? "))
        return {"TPI:SHORT": short, "TPI:LIST": listing, "TPI:MENU": menu, "TPI:ASK": ask}

    menu_result = []

    def run_script(text, script):
        pio = PIO()
        P.fresh(t, pio)
        t.TSP.ROM_VERSION = "1.7"
        pio.tx = [0x01]
        pio.y = 0
        tio.kill = False
        pio.run(script)
        t.PROCESS_CMD(P.make_pre(text), handlers(), {})
        pio.finish()
        return pio, (pio.result or ("no result",))

    def run(text, **kw):
        pio = PIO()
        P.fresh(t, pio)
        t.TSP.ROM_VERSION = "1.7"
        pio.tx = [0x01]                         # the previous command's pre-load
        pio.y = 0                               # pre-header OUTs dropped it
        tio.kill = False
        pio.run(z80_cmd(P.make_body(text), **kw))
        t.PROCESS_CMD(P.make_pre(text), handlers(), {})
        pio.finish()
        return pio, (pio.result or ("no result",))

    def idle(pio, st=0xFF):
        return (pio.tx == [0x01] and not pio.rx and pio.status() == st
                and not pio.blocked)

    try:
        print("a short command")
        pio, r = run(b"tpi:short")
        check(r[0] == "ok" and idle(pio), "status 01, then TX = [01], status FF (%s)" % (r,))

        print("a multi-page listing")
        pio, r = run(b"tpi:list")
        check(r[0] == "ok" and len(r) > 2 and r[1] >= 2 and b"line 60" in r[2] and idle(pio),
              "Y through the prompts to the end, all 60 lines, back to idle (%s)" % (r[:2],))
        pio, r = run(b"tpi:list", keys=(ord("N"),))
        check(r[0] == "N" and len(r) > 1 and r[1] == 1 and idle(pio),
              "N at the first prompt stops it, back to idle (%s)" % (r[0],))

        print("BREAK at a Scroll? prompt (1.8b KEYWAIT)")
        pio, r = run(b"tpi:list", break_at_prompt=2)
        check(r[0] == "D" and idle(pio),
              "the Z80 gets READY + IDLE and raises Report D; TX = [01] (%s)" % (r[0],))
        check(pio.dropped == 0, "no RX overflow (%d)" % pio.dropped)

        print("the Z80 stops reading mid-listing")
        pio, r = run(b"tpi:list", stop_after=200)
        check(idle(pio, 0xFB), "RECOVERED (FB) after the stall, one pre-load, no hang (tx=%r st=%02X)"
              % (pio.tx, pio.status()))

        print("BREAK / SYNC during the command body")
        pio, r = run(b"tpi:list", body_break_at=4)
        check(r[0] == "D" and idle(pio), "straight back to idle, no hang (%s)" % (r[0],))

        print("strict Z80: nothing read from an empty TX after READY")
        pio, r = run(b"tpi:list")
        check(pio.empty_reads == 0, "multi-page listing incl. Scroll? erase: 0 empty reads (%d)" % pio.empty_reads)
        del menu_result[:]
        pio, r = run_script(b"tpi:menu", z80_menu(P.make_body(b"tpi:menu"), ord("0")))
        check(r[0] == "ok" and pio.empty_reads == 0 and menu_result == [0] and idle(pio),
              "ListMenu (tpi:cd): page, key 0, echo -- 0 empty reads, FIRST chosen (%s, %d)"
              % (r[0], pio.empty_reads))
        del menu_result[:]
        pio, r = run_script(b"tpi:ask", z80_menu(P.make_body(b"tpi:ask"), ord("Y")))
        check(r[0] == "ok" and pio.empty_reads == 0 and menu_result == [ord("Y")] and idle(pio),
              "SEND_MSG_PROMPT_YN: prompt, Y, echo -- 0 empty reads (%s, %d)" % (r[0], pio.empty_reads))

        print("READY for a command comes from PROCESS_CMD")
        for name in ("TS/tspico.py", "dev_tspico.py"):
            src = open(os.path.join(SRC, name), encoding="utf-8").read().replace("\r", "")
            i = src.index("if not ((pre[0] == 0 or pre[0] == 255) and pre[1] < 10)")
            cond = src[i:src.index("MQ_READY()", i)]
            check("and pre[0] != 66" in cond,
                  "%s: the dispatcher skips READY for all 42h traffic (commands, printer)" % name)
            i = src.index("got = RX_CAPTURE(MQ, pre_raw, 10, 1000)")
            sync = src[i:src.index("if got != 10:", i)]
            check(sync.index("while busy and") < sync.index('MQ_STATUS(MQ, "idle")'),
                  "%s: after a SYNC, IDLE waits for a SAVE_LOG flash write to finish" % name)
            pc = src[src.index("def PROCESS_CMD("):src.index("def TS2068_IO(")]
            a = pc.index('MQ_STATUS(MQ, "mid")')
            check(pc[a:].split("\n")[1].strip().startswith("got = RX_CAPTURE(MQ, raw, long,"),
                  "%s: PROCESS_CMD says READY straight before the body capture" % name)
            for fn in ("SEND_MSG", "SEND_MSG2", "ListMenu", "SEND_MSG_PROMPT_YN"):
                body = src[src.index("def %s(" % fn):]
                body = body[:body.index("\ndef ", 5)]
                check("MQ.put" not in body.replace("wrt = CMD_PUT", "")
                      and "ch = MQ.get()" not in body,
                      "%s %s: no blocking MQ.put / key MQ.get" % (name, fn))

    except L.PutWouldBlock as e:
        check(False, str(e))

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
