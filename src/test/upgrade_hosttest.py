"""End-to-end host test of the upgrade UF2 -- CPython, no hardware.

Two halves of the real code, joined:

  * the Pico: src/upgrade/upgrade.py's serve() (the upgrade UF2's loop),
    with tspico_io's streaming, on load_ts_hosttest's fake time;
  * the 2068: first a Z80 that follows the ORIGINAL Spectrum ROM's LD-BYTES
    (to load the tape), then the real src/upgrade/updater.bin running in
    z80core, on updater_hosttest's model of the 2068's banking and the
    SST39SF040 flash chip.

The PIO between them has 4-deep FIFOs and auto-busy. The Z80 is patient: an
IN from an empty TX, or an OUT into a full RX, waits for the Pico instead of
going wrong -- updater_hosttest checks the Z80's own cadence, and the
hardware harness proved the Pico keeps up.

The payload is built fresh by tools/build-upgrade.py.

What it pins:
  * the tape reaches the Spectrum ROM whole, blocks in order, as the loader
    and the updater's CODE block (at 6000h);
  * the updater's 'I' stops the tape; its 'R's get the manifest's ROMs; the
    flash ends up with the TS-2068 ROM in slot 1 and ZX v3 in slot 0;
  * the web page's lines: waiting, tape, updater, status P/E/W/V... D;
  * a failure (P10 not fitted): X 2, the tape re-armed, LOAD "" works again;
  * the upgrade UF2 is self-contained: every TS / upgrade module that its
    frozen modules import is frozen too (src/upgrade/manifest.py) and staged
    by both workflows. The rest of this test imports the modules from the
    full source tree, so it can't see a module that is missing from the
    UF2 -- which is how #82's `from TS import native` in tspico_io shipped
    an upgrade UF2 that died with ImportError at boot.

Run:  python3 src/test/upgrade_hosttest.py
"""

import ast
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.dirname(HERE)
REPO = os.path.dirname(SRC)
sys.path.insert(0, HERE)
from sync_io_hosttest import install_fakes, FakeTime            # noqa: E402
import load_ts_hosttest as L                                    # noqa: E402
import updater_hosttest as U                                    # noqa: E402
from z80core import Z80, Halted                                # noqa: E402

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


class Done(Exception):
    pass


class Bus:
    """TS_IO_DUAL between the Pico code and a Z80 -- a script first, then
    z80core. Each FIFO call from the Pico side lets the Z80 run a little."""

    def __init__(self):
        self.tx, self.rx = [], []
        self.y = 0xFFFFFFFF
        self.script = None
        self.pending = None
        self.result = None
        self.cpu = None

    # ---- the Pico's side (the StateMachine API tspico_io uses) -----------
    def tx_fifo(self):
        self.pump()
        return len(self.tx)

    def rx_fifo(self):
        self.pump()
        return min(len(self.rx), 4)

    def get(self):
        for _ in range(1000000):
            if self.rx:
                return self.rx.pop(0)
            self.pump()
        raise AssertionError("get() on an RX FIFO that never filled")

    def put(self, b):
        if len(self.tx) >= 4:
            raise L.PutWouldBlock("put() into a full TX FIFO")
        self.tx.append(b & 0xFF)
        self.pump()

    def exec(self, s):
        t = s.replace(" ", "")
        if t == "mov(y,invert(null))":
            self.y = 0xFFFFFFFF
        elif t == "pull(noblock)":
            if self.tx:
                self.tx.pop(0)
        elif t != "mov(osr,null)":
            raise AssertionError("exec %r" % s)

    # ---- the Z80's side -----------------------------------------------------
    def z80_out(self, port, v):
        self.rx.append(v | (0x100 if port == 0x0F else 0))
        self.y = 0

    def pump(self):
        if self.script is not None:
            op = self.pending
            if op[0] == "out":
                if len(self.rx) < 4:
                    self.z80_out(op[1], op[2])
                    self._advance(None)
            elif op[0] == "in":
                if self.tx:
                    self._advance(self.tx.pop(0))
            elif op[0] == "ready":             # ZX v3's WAIT_RDY: ~3.8 s, then Report R
                if self.y & 0x40:
                    self._advance(None)
                elif len(op) > 1 and op[1] <= 0:
                    raise Done("v3 timed out waiting for READY")
                else:
                    self.pending = ("ready", (op[1] if len(op) > 1 else 20000) - 1)
            elif op[0] == "idle":
                self.pending = ("idle", op[1] - 1) if op[1] > 1 else None
                if self.pending is None:
                    self._advance(None)
            return
        if self.cpu is None:
            return
        cpu = self.cpu
        for _ in range(40):
            if cpu.pc == U.BASIC_RET:
                raise Done("basic")
            op = cpu.read(cpu.pc)
            if op == 0xDB and cpu.read(cpu.pc + 1) == 0x0E and not self.tx:
                return                          # IN (0Eh) waits for the Pico
            if op == 0xD3 and cpu.read(cpu.pc + 1) in (0x0E, 0x0F) and len(self.rx) >= 4:
                return                          # OUT waits for room
            try:
                cpu.step()
            except Halted:
                raise Done("halt")

    def run(self, gen):
        self.script = gen
        self._advance(None)

    def _advance(self, v):
        try:
            self.pending = self.script.send(v)
        except StopIteration as e:
            self.result, self.script, self.pending = e.value, None, None


def ld_bytes(n, v3=False):
    """The original ROM's LD-BYTES: 'L', then flag + n + CRC, no handshake.
    ZX v3's waits for READY after the 'L'."""
    yield ("idle", 20)
    yield ("out", 0x0E, 0x4C)
    if v3:
        yield ("ready",)
    flag = yield ("in",)
    h, data = flag, bytearray()
    for _ in range(n):
        b = yield ("in",)
        h ^= b
        data.append(b)
    crc = yield ("in",)
    return flag, bytes(data), crc == h


def z80_load_updater(tape, v3=False):
    """LOAD "" of the updater tape: the loader (header + program), then its
    LOAD ""CODE (header + code). Lengths as the ROM would ask."""
    yield ("idle", 200)
    got = []
    o = 0
    while o < len(tape):
        n = tape[o] | tape[o + 1] << 8
        got.append((yield from ld_bytes(n - 2, v3)))
        o += n + 2
    return got


def attach_cpu(bus, code, flash_image, we=True):
    """The updater, loaded and started, on updater_hosttest's machine model."""
    flash = U.Flash(flash_image, we=we)
    ram = bytearray(0x10000)
    ram[0x6000:0x6000 + len(code)] = code
    st = {"hsr": 0x03}

    def chip(a):
        if st["hsr"] >> (a >> 13) & 1:
            return a
        return 0x8000 + a if a < 0x4000 else None

    def read(a):
        c = chip(a)
        return ram[a] if c is None else flash.read(c, cpu.t)

    def write(a, v):
        c = chip(a)
        if c is None:
            ram[a] = v
        else:
            flash.write(c, v, cpu.t)

    def port_in(port):
        p = port & 0xFF
        if p == 0x0F:
            return bus.y & 0xFF
        if p == 0x0E:
            return bus.tx.pop(0) if bus.tx else 0
        return 0xFF

    def port_out(port, v):
        p = port & 0xFF
        if p == 0xF4:
            st["hsr"] = v
        elif p in (0x0E, 0x0F):
            bus.z80_out(p, v)

    cpu = Z80(read, write, port_in, port_out)
    cpu.sp = 0xFF40
    cpu.push(U.BASIC_RET)
    cpu.pc = 0x6000
    bus.cpu = cpu
    return flash, st


def check_frozen_closure():
    """The upgrade UF2 has only what src/upgrade/manifest.py freezes. Every
    import of a TS.* / upgrade* module in those files must resolve to another
    frozen file, and CI must stage each frozen TS file (build.yml and
    release.yml copy them into ports/rp2/modules-upgrade/TS/)."""

    print("the upgrade UF2's frozen modules import only each other")
    import re
    man = open(os.path.join(SRC, "upgrade", "manifest.py")).read()
    files = re.findall(r'freeze\("\$\(PORT_DIR\)/modules-upgrade", "([^"]+)"\)', man)
    mods = {f[:-3].replace("/", ".").replace(".__init__", "") for f in files}
    ours = lambda m: m == "TS" or m.startswith("TS.") or m.startswith("upgrade")
    for f in files:
        if f == "upgrade_data.py":
            continue                                    # generated: data only
        path = os.path.join(SRC, f) if f.startswith("TS/") else os.path.join(SRC, "upgrade", f)
        tree = ast.parse(open(path).read())
        need = set()
        # Only imports that run when the module is imported: walk everything
        # except function bodies. A lazy import inside a function (tspico_io's
        # SAVE_TS does `from TS.tspico import TLM`) only runs if the upgrade
        # code calls that function, which it doesn't; the import that killed
        # the boot was a module-level one.
        todo = list(tree.body)
        nodes = []
        while todo:
            node = todo.pop()
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            nodes.append(node)
            todo.extend(ast.iter_child_nodes(node))
        for node in nodes:
            if isinstance(node, ast.Import):
                need |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                need.add(node.module)
                if node.module == "TS":                 # from TS import native
                    need |= {"TS." + a.name for a in node.names}
        missing = sorted(m for m in need if ours(m) and m not in mods)
        check(not missing, "%s: everything it imports is frozen (missing: %s)" % (f, missing or "none"))
    for wf in ("build.yml", "release.yml"):
        y = open(os.path.join(REPO, ".github", "workflows", wf)).read()
        line = [l for l in y.splitlines() if "modules-upgrade/TS/" in l and l.strip().startswith("cp ")]
        staged = set(re.findall(r"src/(TS/\w+\.py)", line[0])) if len(line) == 1 else set()
        want = {f for f in files if f.startswith("TS/")}
        check(staged == want, "%s stages exactly the frozen TS files (%s)" % (wf, sorted(staged ^ want) or "ok"))


def main():
    check_frozen_closure()
    install_fakes()
    sys.path.insert(0, SRC)
    sys.path.insert(0, os.path.join(SRC, "upgrade"))
    import TS.tspico_io as tio
    tio.time = FakeTime()
    import upgrade
    upgrade.time = tio.time

    tmp = tempfile.mkdtemp()
    subprocess.run([sys.executable, os.path.join(REPO, "tools", "build-upgrade.py"), tmp],
                   check=True, stdout=subprocess.DEVNULL)
    spec = importlib.util.spec_from_file_location("upgrade_data", os.path.join(tmp, "upgrade_data.py"))
    data = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(data)
    code = open(os.path.join(SRC, "upgrade", "updater.bin"), "rb").read()

    rom = lambda *p: open(os.path.join(REPO, *p), "rb").read()
    base = bytearray(bytes((i * 7 + 3) & 0xFF for i in range(0x80000)))
    base[0:0x8000] = rom("ROMs", "TSPICO-ZX48-V2.BIN") + bytes(0x4000)
    base[0x8000:0x10000] = rom("ROMs", "TSPICO-15w-home") + rom("ROMs", "TSPICO-15w-exrom")
    base = bytes(base)

    def session(we=True, v3=False):
        """LOAD "" the tape, then run the updater against serve()."""
        bus = Bus()
        box = {}

        def z80():
            got = yield from z80_load_updater(data.TAPE, v3)
            box["tape"] = got
            box["flash"], box["st"] = attach_cpu(bus, code, base, we=we)
            yield ("idle", 5)
            return got

        bus.run(z80())
        out = io.StringIO()
        end = None
        try:
            with contextlib.redirect_stdout(out):
                upgrade.serve(bus, data)
        except Done as e:
            end = str(e)
        lines = [json.loads(l[4:]) for l in out.getvalue().splitlines() if l.startswith("UPG ")]
        return end, box, lines, bus

    print("a normal upgrade")
    end, box, lines, bus = session()
    tape = box.get("tape") or []
    check(len(tape) == 4 and all(ok for _, _, ok in tape) and tape[3][1] == code,
          "the Spectrum ROM got the tape: loader, then the updater's CODE block, CRCs right")
    fl = box["flash"]
    check(end == "halt" and bytes(fl.m[0x8000:0x10000]) == data.IMG1
          and bytes(fl.m[0:0x4000]) == data.IMG0,
          "slot 1 = the manifest's TS-2068 ROM, slot 0 = ZX v3 (%s)" % end)
    check(fl.m[0x4000:0x8000] == base[0x4000:0x8000] and fl.m[0x10000:] == base[0x10000:],
          "nothing else in the flash changed")
    ev = [l["event"] for l in lines]
    st = [(l["code"], l["arg"]) for l in lines if l["event"] == "status"]
    check(ev[:3] == ["waiting", "tape", "updater"] and st[0] == ("P", 1) and st[-1] == ("D", 0)
          and len([s for s in st if s[0] == "W"]) == 192,
          "web page lines: waiting, tape, updater, P 1 ... 192 W ... D (%s ...)" % ev[:4])

    print("a board that already has ZX v3 in slot 0 (it waits for READY after 'L')")
    end, box, lines, bus = session(v3=True)
    tape = box.get("tape") or []
    check(len(tape) == 4 and all(ok for _, _, ok in tape) and end == "halt"
          and bytes(box["flash"].m[0x8000:0x10000]) == data.IMG1,
          "READY comes up after each 'L': the tape loads and the upgrade completes (%s)" % end)

    print("P10 not fitted")
    end, box, lines, bus = session(we=False)
    st = [(l["code"], l["arg"]) for l in lines if l["event"] == "status"]
    check(end == "basic" and st[-1] == ("X", 2) and bytes(box["flash"].m) == base,
          "X 2, back to BASIC, the flash unchanged (%s, %s)" % (end, st[-1:]))
    stream, starts = tio.TAPE_STREAM_OF(data.TAPE)
    check(bus.tx == list(stream[:4]), "the tape is re-armed for LOAD \"\" (TX %s)" % bus.tx)

    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
