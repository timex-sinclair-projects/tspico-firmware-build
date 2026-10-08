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

import builtins
import os
import re
import types
import tempfile
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


def z80_cmd(body, keys=(), break_at_prompt=None, stop_after=None, body_break_at=None, rom23=False):
    """The EXROM after the dispatcher has taken the command pre-header.
    rom23: ROM 2.3's $86 (#227, #228) -- after N it waits for READY and reads
    on like any key, and a control code's value bytes are never a terminator."""
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
            if key == ord("N") and not rom23:
                return ("N", prompts, bytes(text))
            r = yield from L.ready_wait()
            if r:
                return (r, prompts, bytes(text))
            continue
        if c == 0x03:                           # end of message
            return ("ok", prompts, bytes(text))
        text.append(c)
        if rom23 and 0x10 <= c <= 0x17:         # PS_READ: the value bytes, whatever they are
            for _ in range(2 if c >= 0x16 else 1):
                text.append((yield ("in",)))


def z80_blkrcv(body, read_n=0, break_first=False):
    """romupdate.bas: SAVE "tpi:blkrcv" (status), then -- after its PRINTs and
    the erase -- the DI write loop reads read_n bytes blind. break_first: the
    user BREAKs before the USR, so nothing is ever read (1.8b/2.x ROMs write
    0Fh for BREAK, and the next command's SYNC does the same)."""
    st = yield ("in",)
    if st != 0x01:
        return ("st%02X" % (st or 0),)
    r = yield from L.ready_wait()
    if r:
        return (r,)
    for b in body:
        yield L.out(0x0E, b)
    r = yield from L.ready_wait()
    if r:
        return (r,)
    code = yield ("in",)
    if code != 0x01:
        return ("st%02X" % code,)
    if break_first:
        yield L.out(0x0F, 0x03)
        yield ("wait", READY | IDLE, 3000)
        return ("D",)
    data = bytearray()
    for _ in range(read_n):
        data.append((yield ("in",)))
    return ("ok", bytes(data))


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
            menu_result.append(t.ListMenu(["FIRST", "SECOND"], "hdr1", "hdr2",
                                          "Change to dir", "Changing to: "))
        def ask(pre, cmd):
            menu_result.append(t.SEND_MSG_PROMPT_YN("Sure? "))
        def keywords(pre, cmd):
            t.SEND_MSG2(kw_text[0], t._1_OK)
        def coloured(pre, cmd):
            t.SEND_MSG2(kw_text[0], t._1_OK, colour=True)
        return {"TPI:SHORT": short, "TPI:LIST": listing, "TPI:MENU": menu, "TPI:ASK": ask,
                "TPI:KW": keywords, "TPI:COL": coloured}

    kw_text = [""]

    menu_result = []

    def pre_for(text, rom_id):
        pre = P.make_pre(text)
        pre[2] = rom_id                         # FFh: ROM 2.2 and earlier; 23h: ROM 2.3
        return pre

    def run_script(text, script, rom_id=0xFF):
        pio = PIO()
        P.fresh(t, pio)
        t.TSP.ROM_VERSION = "1.7"
        pio.tx = [0x01]
        pio.y = 0
        tio.kill = False
        pio.run(script)
        t.PROCESS_CMD(pre_for(text, rom_id), handlers(), {})
        pio.finish()
        return pio, (pio.result or ("no result",))

    def run(text, rom="1.7", **kw):
        pio = PIO()
        P.fresh(t, pio)
        t.TSP.ROM_VERSION = rom
        pio.tx = [0x01]                         # the previous command's pre-load
        pio.y = 0                               # pre-header OUTs dropped it
        tio.kill = False
        pio.run(z80_cmd(P.make_body(text), **kw))
        t.PROCESS_CMD(pre_for(text, 0x23 if kw.get("rom23") else 0xFF), handlers(), {})
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

        print("ROM 2.3: keys as typed, the Pico ends the loop after N (#227)")
        pio, r = run(b"tpi:list", keys=(ord("n"),), rom23=True)
        check(r[0] == "ok" and len(r) > 2 and r[1] == 1 and r[2].endswith(b"Scroll? (Y/n)n")
              and pio.empty_reads == 0 and idle(pio),
              "'n' at the first prompt: the echo 'n' and 0x03 end it, back to idle (%s)" % (r[:2],))
        pio, r = run(b"tpi:list", keys=(ord("y"), ord("5")), rom23=True)
        check(r[0] == "ok" and len(r) > 2 and b"line 60" in r[2] and idle(pio),
              "lower-case 'y' pages on like 'Y' (%s)" % (r[:2],))
        pio, r = run(b"tpi:list", keys=(ord("N"),))
        check(r[0] == "N" and 0x03 not in pio.tx and idle(pio),
              "ROM 2.2 (pre-header byte 2 FFh): N still sends nothing more (%s)" % (r[0],))

        print("ROM 2.3: colour values 0 and 3 (#228)")
        kw_text[0] = "\x10\x00black \x11\x03magenta \x12\x01flash\x10\x08\x11\x08\x12\x00"
        pio, r = run(b"tpi:col", rom23=True)
        check(r[0] == "ok" and len(r) > 2 and r[2] == b"\r\r\x10\x00black \x11\x03magenta \x12\x01flash"
              b"\x10\x08\x11\x08\x12\x00" and idle(pio),
              "INK 0, PAPER 3, FLASH 1 and FLASH 0 sent with their values (%r)" % (r[2:] or r,))
        pio, r = run(b"tpi:col")
        check(r[0] == "ok" and len(r) > 2 and r[2] == b"\r\rblack magenta flash\x10\x08\x11\x08",
              "ROM 2.2: the same text without the codes it can't take (%r)" % (r[2:] or r,))
        kw_text[0] = "\x10\x0cbad"
        pio, r = run(b"tpi:col", rom23=True)
        check(r[0] == "ok" and len(r) > 2 and r[2] == b"\r\rbad",
              "ROM 2.3: INK 12, a value RST 10h refuses (Report K), is still dropped (%r)" % (r[2:] or r,))

        print("ROM_VERSION is not a protocol switch (audit 2026-09-30)")
        pio, r = run(b"tpi:list", rom="1.0")
        check(r[0] == "ok" and len(r) > 2 and r[1] >= 2 and b"line 60" in r[2] and idle(pio),
              "a stale \"1.0\" in config.ini: the same listing, same prompts, ends on 03 (%s)" % (r[:2],))

        print("keyword widths: | is STICK (7), ~ is FREE (6)")
        kw_text[0] = "xxxx||||" * 3
        pio, r = run(b"tpi:kw")
        check(r[0] == "ok" and len(r) > 2 and r[2] == b"\r\r" + b"xxxx||||\r" * 3,       # \r\r: SEND_MSG2's opening blank line
              "4 + 4x7 = 32 columns: a line break after each group (%r)" % (r[2:] or r,))
        kw_text[0] = "xx~~~~~" * 2
        pio, r = run(b"tpi:kw")
        check(r[0] == "ok" and len(r) > 2 and r[2] == b"\r\r" + b"xx~~~~~\r" * 2,
              "2 + 5x6 = 32 columns: a line break after each group (%r)" % (r[2:] or r,))
        kw_text[0] = "".join("%02d .......................|\r" % i for i in range(1, 31))  # 26 + 7 = 33
        pio, r = run(b"tpi:kw")
        check(r[0] == "ok" and len(r) > 1 and r[1] == 2,
              "26 chars + STICK straddles column 32: every line is two on screen, so 60 lines"
              " prompt twice (%s prompts)" % (r[1] if len(r) > 1 else r,))

        print("RX flushes before a reply hear BREAK (audit §4)")
        saved_mq = t.MQ
        words = [0x41, 0x103]
        t.MQ = types.SimpleNamespace(rx_fifo=lambda: len(words), get=lambda: words.pop(0))
        try:
            t.CMD_RX_FLUSH()
            raised = None
        except t.CmdAbort as e:
            raised = e.args[0]
        check(raised == 1 and not words, "a stray key, then BREAK's 0Fh write: CmdAbort(1), not swallowed")
        words[:] = [0x41, 0x42]
        t.CMD_RX_FLUSH()
        check(not words, "stray keys alone: just emptied")
        t.MQ = saved_mq
        src = open(os.path.join(SRC, "TS", "tspico.py"), encoding="utf-8").read().replace("\r", "")
        for fn in ("SEND_MSG2", "PROMPT_EACH", "ListMenu", "SEND_MSG_PROMPT_YN"):
            body = src[src.index("def %s(" % fn):]
            body = body[:body.index("\ndef ", 5)]
            head = body[:body.index("CMD_KEY()") if "CMD_KEY()" in body else len(body)]
            check("CMD_RX_FLUSH()" in head and "while MQ.rx_fifo() != 0:" not in head.split("CMD_RX_FLUSH()")[0],
                  "%s empties RX with CMD_RX_FLUSH, not a plain drain" % fn)
        pc = src[src.index("def PROCESS_CMD("):src.index("def TS2068_IO(")]
        tail = pc[pc.index("finally:"):]
        check(tail.index("RXD.arm(MQ)") < tail.index('MQ_STATUS(MQ, "recovered" if cmd_abort == 3 else "idle")'),
              "PROCESS_CMD's tail arms the pre-header's DMA channel before it says IDLE")
        loop = src[src.index("def TS2068_IO("):]
        z = loop.index("ZX48_IO(pre)")
        check("rxd.stop()" in loop[z - 200:z], "the channel is stopped before ZX48_IO reads RX by hand")

        print("a page that ends with short lines still prompts (audit §4, n > i + 34)")
        kw_text[0] = "".join("%02d a long line of help text....\r" % i for i in range(1, 22)) + "x\r" * 12
        pio, r = run(b"tpi:kw")
        check(r[0] == "ok" and len(r) > 1 and r[1] == 1,
              "21 lines, then 12 one-character lines (24 characters): a prompt, not 33 lines in a"
              " row (%s prompts)" % (r[1] if len(r) > 1 else r,))
        kw_text[0] = "".join("%02d a long line of help text....\r" % i for i in range(1, 22)) + "the end"
        pio, r = run(b"tpi:kw")
        check(r[0] == "ok" and len(r) > 1 and r[1] == 0,
              "21 lines and a short last one: no prompt just for that (%s prompts)" % (r[1] if len(r) > 1 else r,))

        print("tpi:blkrcv: the ROM-update stream (audit 2026-09-30)")
        image = bytes((i * 37 + 11) & 0xFF for i in range(1000))
        real_open, real_os = getattr(t, "open", builtins.open), t.os

        def blkrcv_run(script):
            pio = PIO()
            P.fresh(t, pio)
            t.TSP.ROM_VERSION = "2.1"
            t.TSP.f_name = "/sd/TAP/NEW.ROM"
            t.getDock = lambda: (2, 4)
            t.BOOT_SLOT_CLASH = lambda *a: None
            t.BLINK_ERROR = lambda *a: None
            t.led = types.SimpleNamespace(value=lambda *a: None)
            img = tempfile.NamedTemporaryFile(suffix=".bin", delete=False)
            img.write(image)
            img.close()
            t.open = lambda path, mode="r": real_open(img.name if path == "/TMP/temp.bin" else path, mode)
            t.os = types.SimpleNamespace(stat=lambda path: (0,) * 6 + (len(image),))
            pio.tx = [0x01]
            pio.y = 0
            tio.kill = False
            pio.run(script)
            try:
                t.PROCESS_CMD(P.make_pre(b"tpi:blkrcv"), {"TPI:BLKRCV": t.BLKRCV}, {})
            finally:
                t.open, t.os = real_open, real_os
            pio.finish()
            return pio, (pio.result or ("no result",))

        pio, r = blkrcv_run(z80_blkrcv(P.make_body(b"tpi:blkrcv"), read_n=len(image)))
        check(r[0] == "ok" and len(r) > 1 and r[1] == image and idle(pio),
              "the updater's blind read loop gets all %d bytes, in order; back to idle (%s)"
              % (len(image), r[0]))
        pio, r = blkrcv_run(z80_blkrcv(P.make_body(b"tpi:blkrcv"), break_first=True))
        check(r[0] == "D" and not pio.blocked and idle(pio),
              "BREAK before the write loop starts: Report D, back to idle, no put() into a"
              " full FIFO (blocked=%s, %s)" % (pio.blocked, r[0]))

        print("BREAK at a Scroll? prompt (1.8b KEYWAIT)")
        pio, r = run(b"tpi:list", break_at_prompt=2)
        check(r[0] == "D" and idle(pio),
              "the Z80 gets READY + IDLE and raises Report D; TX = [01] (%s)" % (r[0],))
        check(pio.dropped == 0, "no RX overflow (%d)" % pio.dropped)

        print("the Z80 stops reading mid-listing")
        check(t.CMD_STALL_MS >= 60000,
              "the output stall limit is long (%d ms): the Z80 waits for the user at the ROM's scroll? prompt"
              % t.CMD_STALL_MS)
        stall, t.CMD_STALL_MS = t.CMD_STALL_MS, 3000   # exercise the path quickly
        pio, r = run(b"tpi:list", stop_after=200)
        t.CMD_STALL_MS = stall
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
        del menu_result[:]
        pio, r = run_script(b"tpi:menu", z80_menu(P.make_body(b"tpi:menu"), ord("n")), rom_id=0x23)
        check(r == ("ok", b"n") and pio.empty_reads == 0 and menu_result == [-1] and idle(pio),
              "ROM 2.3 ListMenu: 'n' -> -1, its echo and 0x03 end the loop (%s, %r)" % (r, menu_result))
        del menu_result[:]
        pio, r = run_script(b"tpi:ask", z80_menu(P.make_body(b"tpi:ask"), ord("y")), rom_id=0x23)
        check(r == ("ok", b"y") and menu_result == [ord("Y")] and idle(pio),
              "ROM 2.3 SEND_MSG_PROMPT_YN: 'y' echoed as typed, returned as Y (%s, %r)" % (r, menu_result))

        print("the pre-header capture allocates nothing")
        import ast
        io_src = open(os.path.join(SRC, "TS", "tspico_io.py"), encoding="utf-8").read().replace("\r", "")
        fn = [n for n in ast.parse(io_src).body if isinstance(n, ast.FunctionDef) and n.name == "RX_CAPTURE"][0]
        bad = [n.lineno for n in ast.walk(fn) if isinstance(n, ast.Assign) and isinstance(n.value, ast.Attribute)]
        check(not bad, "RX_CAPTURE stores no bound methods (%s)" % bad)

        print("unknown pre-headers go back to a known state (audit 2026-09-30)")
        for name in ("TS/tspico.py", "dev_tspico.py"):
            src = open(os.path.join(SRC, name), encoding="utf-8").read().replace("\r", "")
            loop = src[src.index("def TS2068_IO("):src.index("def ZX48_IO(")]
            i = loop.index('LOG("Unrecognized command! " + str(list(pre)), 1)')
            # the branch ends at the next else: at its own depth (whatever the indent)
            branch = loop[i:i + re.search(r"\n {8,}else:", loop[i:]).start()]
            check("MQ_TO_IDLE(MQ, recovered=True)" in branch and "MQ.active(0)" not in branch
                  and "BLINK_ERROR()" not in branch,
                  "%s: an unrecognised pre-header -> MQ_TO_IDLE (one 0x01 staged), no SM restart"
                  " or 1 s blink" % name)
            check(not re.search(r"^\s*elif pre\[0\] == 65:", loop, re.M) and "def PROCESS_ASM(" not in src,
                  "%s: no 'A' (41h) branch: it falls into the unrecognised path" % name)

        print("READY for a command comes from PROCESS_CMD")
        for name in ("TS/tspico.py", "dev_tspico.py"):
            src = open(os.path.join(SRC, name), encoding="utf-8").read().replace("\r", "")
            i = src.index("if pre[0] not in (PRE_HEADER, PRE_DATA, PRE_CMD):")
            cond = src[i:src.index("MQ_READY()", i)]
            check("66" in cond,
                  "%s: the dispatcher skips READY for all 42h traffic (commands, printer)" % name)
            i = src.index("got = RX_CAPTURE(MQ, pre_raw, 10, 1000)")
            sync = src[i:src.index("if got != 10:", i)]
            check(sync.index("while busy and") < sync.index('MQ_STATUS(MQ, "idle")'),
                  "%s: after a SYNC, IDLE waits for a SAVE_LOG flash write to finish" % name)
            code = [l.strip() for l in src[i:src.index("if pre[0] == PRE_HEADER and pre[1] == 0:", i)].split("\n")
                    if l.strip() and not l.strip().startswith("#")]
            walks = [k for k, l in enumerate(code) if "gc.collect()" in l or
                     ("gc.mem_free()" in l and not (k and code[k - 1] == "if TSP.LOG_LEVEL == 0:"))]
            check(not walks, "%s: no heap walk (gc.collect / gc.mem_free) on every SYNC / transaction %s"
                  % (name, [code[k] for k in walks]))
            pc = src[src.index("def PROCESS_CMD("):src.index("def TS2068_IO(")]
            check('got = RX_CAPTURE(MQ, raw, long, BODY_READ_TIMEOUT_MS, "mid")' in pc
                  and 'MQ_STATUS(MQ, "mid")\n    got = RX_CAPTURE' not in pc,
                  "%s: PROCESS_CMD's body capture says READY itself, once it is listening" % name)
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
