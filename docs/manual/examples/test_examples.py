"""Run the manual's machine-code examples against a simulated TS-Pico.

The Z80 code runs in the firmware repo's host Z80 interpreter
(src/test/z80core.py). The Pico is a model of firmware 2.0 as the Z80 sees it:
the two ports, auto-BUSY after every OUT, SYNC, the pre-load 01h, the
pre-header and body (XOR checked), READY / IDLE, and the answers of the
commands the examples use. The channel commands use the firmware's own
channels.py and catalog.py; tpi:.fact is the dev_extcmd.py handler from this
folder, run unchanged.

Not simulated: the ROM (RST 10h prints into a list, CHAN_OPEN returns, RST 8
stops the run and records the report), the BIOS thunk (bios.asm), timing
beyond T-state counts, the 4-deep FIFOs.

Run:  python3 docs/manual/examples/test_examples.py
"""

import os
import subprocess
import sys
import types
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = sys.argv[1] if len(sys.argv) > 1 else os.path.normpath(
    os.path.join(HERE, "..", "..", ".."))           # docs/manual/examples -> the repo
sys.path.insert(0, os.path.join(REPO, "src", "test"))
sys.path.insert(0, os.path.join(REPO, "src"))
from z80core import Z80                                          # noqa: E402

sys.modules.setdefault("micropython", types.SimpleNamespace(const=lambda x: x))
from TS import catalog, channels                                 # noqa: E402

FAILS = []


def check(cond, msg):
    print(("  ok    " if cond else "  FAIL  ") + msg)
    if not cond:
        FAILS.append(msg)


def build(name):
    subprocess.run(["sjasmplus", "--nologo", "--msg=war", "--raw=%s.bin" % name,
                    "--sym=%s.sym" % name, "%s.asm" % name], cwd=HERE, check=True)
    syms = {}
    for line in open(os.path.join(HERE, name + ".sym")):
        k, _, v = line.partition(": EQU ")
        if v:
            syms[k.strip()] = int(v, 16)
    return open(os.path.join(HERE, name + ".bin"), "rb").read(), syms


# ---------------------------------------------------------------------------
# The Pico
# ---------------------------------------------------------------------------

class MemFS:
    """channels.py's file access, on a dict of real paths -> bytearray."""

    def __init__(self, files):
        self.files = {k: bytearray(v) for k, v in files.items()}

    def exists(self, p):
        return p in self.files

    def size(self, p):
        return len(self.files[p])

    def read(self, p, pos, n):
        return bytes(self.files[p][pos:pos + n])

    def write(self, p, pos, data, truncate):
        if truncate or p not in self.files:
            self.files[p] = bytearray()
        f = self.files[p]
        f[pos:pos + len(data)] = data


class Pico:
    IDLE, MID = 0xFF, 0xF7

    def __init__(self, files=None, verbose=False):
        self.fs = MemFS(files or {})
        self.ch = channels.Channels(self.fs)
        self.cur = catalog.ROOT
        self.verbose = verbose
        self.tx = deque([1])                     # the boot pre-load
        self.y = self.IDLE
        self.state = "idle"
        self.buf = []
        self.co = None
        self.tail = False
        self.underruns = 0
        self.commands = []
        self.keys_seen = []
        self.syncs = 0
        self.stray = 0

    # -- helpers the handlers use (same names as the firmware's) --
    def put(self, b):
        self.tx.append(b & 0xFF)

    def ready(self, y=None):
        self.y = self.IDLE if y is None else y

    def send_msg(self, msg, msg1, st, force=False):
        if self.verbose or force:
            for b in (0x81, st, 0x0D):
                self.put(b)
            self.ready()
            for c in msg.encode():
                self.put(c)
            if msg1:
                self.put(0x0D)
                for c in msg1.encode():
                    self.put(c)
            self.put(0)
        else:
            self.put(st)
            self.ready()

    # -- the ports --
    def port_in(self, port):
        if port == 0x0F:
            return self.y
        if not self.tx:
            self.underruns += 1
            v = 0
        else:
            v = self.tx.popleft()
        self.maybe_tail()
        return v

    def port_out(self, port, v):
        self.y = 0                               # auto-BUSY
        if port == 0x0F:                         # SYNC / abort
            self.syncs += 1
            self.tx.clear()
            self.tx.append(1)
            self.buf, self.co, self.tail = [], None, False
            self.state = "pre"
            self.y = self.IDLE
            return
        if self.state == "pre":
            self.buf.append(v)
            if len(self.buf) == 10:
                self.pre = self.buf
                self.need = self.pre[7] + 256 * self.pre[8] + 4
                self.buf = []
                self.state = "body"
                self.y = self.MID
        elif self.state == "body":
            self.buf.append(v)
            if len(self.buf) == self.need:
                self.process(self.buf)
        elif self.state == "key":
            self.keys_seen.append(v)
            self.step(v)
        else:
            self.stray += 1

    def maybe_tail(self):
        if self.tail and not self.tx:
            self.tx.append(1)                    # PROCESS_CMD's tail
            self.y = self.IDLE
            self.tail = False
            self.state = "idle"

    def process(self, body):
        x = 0
        for b in body[:-1]:
            x ^= b
        if x != body[-1] or body[0] != 0x44:
            self.put(2)                          # Report R
            self.ready()
            self.finish()
            return
        text = bytes(body[3:-1]).decode()
        cmd = "D.." + text
        word = text.split(" ")[0].upper()
        self.commands.append(text)
        h = HANDLERS.get(word) or EXT.get(word)
        if h is None:
            self.send_msg("Unrecognized command: " + word, "", 5)
            self.finish()
            return
        r = h(self, self.pre, cmd) if h in HANDLERS.values() else h(None, self, self.pre, cmd)
        if isinstance(r, types.GeneratorType):
            self.co = r
            self.step(None)
        else:
            self.finish()

    def step(self, key):
        try:
            if key is None:
                next(self.co)
            else:
                self.co.send(key)
            self.state = "key"
        except StopIteration:
            self.co = None
            self.finish()

    def finish(self):
        self.tail = True
        self.state = "tail"
        self.maybe_tail()


def params(pre):
    return pre[3] | pre[4] << 8, pre[5] | pre[6] << 8


def args(cmd):
    sp = cmd[7:].find(" ")
    return cmd[sp + 8:] if sp >= 0 else ""


# firmware handlers, as the Z80 sees them (tspico.py PATH, SEND_MSG2, CH_*)

def h_path(p, pre, cmd):
    p.send_msg("Current working dir is: ", catalog.public(p.cur), 1, True)


def h_dir(p, pre, cmd):
    lines = ["File %02d.tap" % i for i in range(30)]
    for b in (0x86, 1, 0x0D, 0x0D):
        p.put(b)
    p.ready()
    for l in lines[:21]:
        for c in l.encode():
            p.put(c)
        p.put(0x0D)
    for c in b"Scroll? (Y/n)":
        p.put(c)
    p.put(0)
    k = yield                                    # CMD_KEY
    if k == 78:
        p.ready()
        return
    for i in range(19):
        p.put(8), p.put(32), p.put(8)
        if not i:
            p.ready()
    for l in lines[21:]:
        for c in l.encode():
            p.put(c)
        p.put(0x0D)
    p.put(3)


CH_ST = {"F": 3, "Q": 4, "O": 10}


def ch_call(fn, *a):
    try:
        return fn(*a), 1
    except channels.ChannelError as e:
        return e.args[0], CH_ST.get(e.args[1], 4)


def ch_reply(p, st):
    p.put(st)
    p.ready(Pico.MID)                            # CH_READY: not idle yet


def h_chopen(p, pre, cmd):
    stream, reclen = params(pre)
    stream &= 0xFF
    arg = args(cmd).strip()
    k = arg.find(" ")
    mode, path = (arg[:k], arg[k + 1:].strip()) if k > 0 else ("r", arg)
    if path[:2].lower() == "d:":
        where, pat = catalog.split_arg(path[2:].strip())
        real = catalog.resolve(p.cur, where)
        if real is None or (real != catalog.ROOT and
                            not any(n.startswith(real + "/") for n in p.fs.files)):
            ch_reply(p, 3)                       # DIR_NAMES: "Not found", F
            return
        ents = [(n[len(real) + 1:], 0x8000, 0, len(v)) for n, v in p.fs.files.items()
                if n.startswith(real + "/") and "/" not in n[len(real) + 1:]]
        names = [n for n, d, _ in catalog.select(ents, pat)]
        _, st = ch_call(p.ch.open_list, stream, names)
        ch_reply(p, st)
        return
    real = catalog.resolve(p.cur, path) if path else None
    if real is None or real == catalog.ROOT:
        ch_reply(p, 3)
        return
    _, st = ch_call(p.ch.open, stream, real, mode, reclen)
    ch_reply(p, st)


def h_chwr(p, pre, cmd):
    hx = args(cmd).strip()
    try:
        data = bytes(int(hx[i:i + 2], 16) for i in range(0, len(hx), 2))
    except ValueError:
        ch_reply(p, 5)
        return
    _, st = ch_call(p.ch.write, params(pre)[0] & 0xFF, data)
    ch_reply(p, st)


def h_chrd(p, pre, cmd):
    par1, par2 = params(pre)
    data, st = ch_call(p.ch.read, par1 & 0xFF, max(1, min(255, par2 or 255)))
    if st != 1 or not data:
        p.put(st if st != 1 else 7)
        p.ready(Pico.MID)
        return
    x = 0
    for b in data:
        x ^= b
    p.put(1)
    p.put(len(data))
    p.ready(Pico.MID)
    for b in data:
        p.put(b)
    p.put(x)


def h_chclose(p, pre, cmd):
    p.ch.close(params(pre)[0] & 0xFF)
    ch_reply(p, 1)


HANDLERS = {"TPI:PATH": h_path, "TPI:DIR": h_dir, "TPI:CHOPEN": h_chopen,
            "TPI:CHWR": h_chwr, "TPI:CHRD": h_chrd, "TPI:CHCLOSE": h_chclose}

# dev_extcmd.py, run unchanged: its `tp` module is this simulation
_P = {}
tp = types.ModuleType("dev_tspico")
tp.CMD_PUT = lambda b: _P["p"].put(b)
tp.MQ_READY = lambda: _P["p"].ready()
tp.PARAMS = params
tp.getArgs = args
tp.SEND_MSG = lambda m, m1, st, force=False: _P["p"].send_msg(m, m1, st, force)
sys.modules["dev_tspico"] = tp
sys.path.insert(0, HERE)
import dev_extcmd                                                # noqa: E402
EXT = dev_extcmd.EXT_SA_FUNCT


# ---------------------------------------------------------------------------
# The machine
# ---------------------------------------------------------------------------

BASIC_RET = 0x2D2B                               # anywhere in the ROM will do


def run(name, pico, pokes=None, keys=(), limit_t=400_000_000):
    image, syms = build(name)
    mem = bytearray(65536)
    mem[60000:60000 + len(image)] = image
    for addr, val in (pokes or {}).items():
        if isinstance(val, (bytes, bytearray)):
            mem[addr:addr + len(val)] = val
        else:
            mem[addr] = val
    _P["p"] = pico
    out = {"text": bytearray(), "report": None, "keys": list(keys), "rom": []}

    def port_in(port):
        p = port & 0xFF
        if p in (0x0E, 0x0F):
            return pico.port_in(p)
        return 0xFF                              # no keys held down

    def port_out(port, v):
        p = port & 0xFF
        if p in (0x0E, 0x0F):
            pico.port_out(p, v)

    cpu = Z80(lambda a: mem[a], lambda a, v: mem.__setitem__(a, v) if a >= 0x4000 else None,
              port_in, port_out)

    def ret():
        cpu.pc = cpu.pop()

    def hook(a):
        if a == 0x0010:                          # RST 10h: print A
            out["text"].append(cpu.a)
            ret()
        elif a == 0x1230:                        # CHAN_OPEN
            ret()
        elif a == 0x0008:                        # RST 8: the report byte follows
            out["report"] = mem[cpu.pop()]
            raise StopIteration
        elif a == syms["GETKEY"]:
            cpu.a = out["keys"].pop(0)
            ret()
        elif a < 0x4000 and a != BASIC_RET:
            out["rom"].append(a)
            raise StopIteration

    cpu.fetch_hook = hook
    cpu.sp = 0xFF00
    cpu.push(BASIC_RET)
    cpu.pc = 60000
    try:
        while cpu.t < limit_t and cpu.pc != BASIC_RET:
            cpu.step()
    except StopIteration:
        pass
    out["bc"] = cpu.b << 8 | cpu.c
    out["returned"] = cpu.pc == BASIC_RET
    out["sp_ok"] = cpu.sp == 0xFF00
    out["t"] = cpu.t
    out["mem"] = mem
    out["syms"] = syms
    return out


def link_ok(pico, what):
    check(pico.underruns == 0, "%s: never read an empty FIFO" % what)
    check(pico.stray == 0, "%s: no stray bytes" % what)
    check(list(pico.tx) == [1] and pico.y == Pico.IDLE,
          "%s: link left idle with one pre-load (tx=%r y=%02X)" % (what, list(pico.tx), pico.y))


def poke_word(d, addr, v):
    d[addr], d[addr + 1] = v & 0xFF, v >> 8


def poke_text(d, len_addr, text_addr, text, word=False):
    d[len_addr] = len(text)
    if word:
        d[len_addr + 1] = 0
    d[text_addr] = text


def main():
    print("picocmd: tpi:path (an 81h message)")
    p = Pico()
    pk = {}
    poke_text(pk, 60010, 60012, b"tpi:path", word=True)
    r = run("picocmd", p, pk)
    check(r["returned"] and r["bc"] == 0, "returns 0 = OK (bc=%d)" % r["bc"])
    check(r["text"] == b"\rCurrent working dir is: \r/", "printed the message (%r)" % bytes(r["text"]))
    link_ok(p, "path")

    print("picocmd: tpi:dir, two pages, Y at the prompt")
    p = Pico()
    poke_text(pk, 60010, 60012, b"tpi:dir", word=True)
    r = run("picocmd", p, pk, keys=[ord("Y")])
    check(r["returned"] and r["bc"] == 0, "returns 0 = OK")
    check(b"File 29.tap" in r["text"] and p.keys_seen == [ord("Y")], "both pages printed, key sent")
    link_ok(p, "dir Y")

    print("picocmd: tpi:dir, N at the prompt")
    p = Pico()
    r = run("picocmd", p, pk, keys=[ord("N")])
    check(r["returned"] and r["bc"] == 0, "returns 0 = OK")
    check(b"File 20.tap" in r["text"] and b"File 21.tap" not in r["text"], "stopped after page 1")
    link_ok(p, "dir N")

    print("picocmd: an unknown command, both entries")
    p = Pico()
    poke_text(pk, 60010, 60012, b"tpi:nosuch", word=True)
    r = run("picocmd", p, pk)
    check(r["bc"] == 0x0B + 1 and "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"[r["bc"]] == "C",
          "USR 60000 gives the code of Report C (%d)" % r["bc"])
    link_ok(p, "unknown")
    p = Pico()
    r = run_at("picocmd", p, pk, 60003)
    check(r["report"] == 0x0B, "USR 60003 raises Report C (%r)" % r["report"])

    print("picocmd: the Pico doesn't answer")
    p = Pico()
    p.port_out = lambda port, v: setattr(p, "y", 0)          # dead: always BUSY
    poke_text(pk, 60010, 60012, b"tpi:path", word=True)
    r = run("picocmd", p, pk, limit_t=200_000_000)
    check(r["returned"] and r["bc"] == 0x12 + 1, "gives Report J (%d) after %.1f s"
          % (r["bc"], r["t"] / 3.528e6))

    data = bytes((i * 7 + 3) & 0xFF for i in range(700))       # every byte value, 23 too
    print("loadfile: a 700-byte binary file")
    p = Pico({catalog.ROOT + "/GAMES/data.bin": data})
    p.cur = catalog.ROOT + "/GAMES"
    pk = {}
    poke_word(pk, 60003, 32768)
    poke_word(pk, 60005, 16384)
    poke_text(pk, 60007, 60008, b"data.bin")
    r = run("loadfile", p, pk)
    check(r["returned"] and r["bc"] == 700, "returns 700 (%d)" % r["bc"])
    check(bytes(r["mem"][32768:32768 + 700]) == data, "the bytes arrived intact")
    check(r["mem"][32768 + 700] == 0, "nothing written past the end")
    check([c.split()[0] for c in p.commands] == ["tpi:chopen"] + ["tpi:chrd"] * 4 + ["tpi:chclose"],
          "chopen, 3 reads + the end-of-file read, chclose (%s)" % [c[:10] for c in p.commands])
    check(p.ch.table == {}, "channel closed")
    link_ok(p, "loadfile")

    print("loadfile: stops at the limit")
    p = Pico({catalog.ROOT + "/data.bin": data})
    poke_word(pk, 60005, 300)
    r = run("loadfile", p, pk)
    check(r["bc"] == 300 and r["mem"][32768 + 300] == 0, "reads exactly 300 (%d)" % r["bc"])
    check(p.ch.table == {}, "channel closed")

    print("loadfile: no such file")
    p = Pico({})
    r = run("loadfile", p, pk)
    check(r["report"] == 0x0E, "Report F (%r)" % r["report"])
    link_ok(p, "no file")

    print("loadfile: a byte lost on the way")
    p = Pico({catalog.ROOT + "/data.bin": data})
    orig = h_chrd

    def lossy(pp, pre, cmd):
        orig(pp, pre, cmd)
        pp.tx.remove(pp.tx[5])
        pp.put(0)
    HANDLERS["TPI:CHRD"] = lossy
    poke_word(pk, 60005, 16384)
    r = run("loadfile", p, pk)
    HANDLERS["TPI:CHRD"] = orig
    check(r["report"] == 0x1A, "Report R (%r)" % r["report"])
    check(p.ch.table == {}, "channel still closed after the error")

    print("logline: append two lines, one longer than a chunk")
    p = Pico({catalog.ROOT + "/log.txt": b"first\n"})
    pk = {}
    long = b"The quick brown fox jumps over the lazy dog. " * 3
    poke_text(pk, 60003, 60004, b"log.txt")
    poke_text(pk, 60036, 60037, long)
    r = run("logline", p, pk)
    check(r["returned"] and r["report"] is None, "returns without an error")
    check(bytes(p.fs.files[catalog.ROOT + "/log.txt"]) == b"first\n" + long + b"\n",
          "file is 'first' + the line + LF")
    link_ok(p, "logline")
    poke_text(pk, 60036, 60037, b"")
    r = run("logline", p, pk)
    check(bytes(p.fs.files[catalog.ROOT + "/log.txt"]).endswith(long + b"\n\n"), "an empty line")
    p = Pico({})
    poke_text(pk, 60003, 60004, b"new.txt")
    poke_text(pk, 60036, 60037, b"hello")
    r = run("logline", p, pk)
    check(bytes(p.fs.files.get(catalog.ROOT + "/new.txt", b"?")) == b"hello\n", "makes a new file")

    print("countdir")
    files = {catalog.ROOT + "/%s" % n: b"x" for n in
             ["a.tap", "b.TAP", "c.tap", "notes.txt", "d.tzx"] + ["g%02d.tap" % i for i in range(9)]}
    p = Pico(files)
    pk = {}
    poke_text(pk, 60003, 60004, b"*.tap")
    r = run("countdir", p, pk)
    check(r["returned"] and r["bc"] == 12, "12 .tap files (%d)" % r["bc"])
    check(p.ch.table == {}, "channel closed")
    link_ok(p, "countdir")
    poke_text(pk, 60003, 60004, b"")
    p = Pico(files)
    r = run("countdir", p, pk)
    check(r["bc"] == 14, "no pattern: all 14 (%d)" % r["bc"])
    poke_text(pk, 60003, 60004, b"nodir/*")
    p = Pico(files)
    r = run("countdir", p, pk)
    check(r["report"] == 0x0E, "a folder that isn't there: F (%r)" % r["report"])

    print("fact")
    import math
    for n in (0, 5, 20, 32):
        p = Pico()
        r = run("fact", p, {60003: n})
        check(r["text"] == str(math.factorial(n)).encode() + b"\r", "%d! = %s" % (n, bytes(r["text"][:-1]).decode()))
        link_ok(p, "fact %d" % n)
    p = Pico()
    r = run("fact", p, {60003: 33})
    check(r["report"] == 0x05, "33: Report 6 (%r)" % r["report"])
    link_ok(p, "fact 33")

    print()
    print("%d FAILED" % len(FAILS) if FAILS else "all passed")
    return 1 if FAILS else 0


def run_at(name, pico, pokes, entry):
    """run(), entered at another address (patch a JP at 60000)."""
    patched = dict(pokes)
    patched[60000] = bytes([0xC3, entry & 0xFF, entry >> 8])     # pokes go in after the image
    return run(name, pico, patched)


if __name__ == "__main__":
    sys.exit(main())
