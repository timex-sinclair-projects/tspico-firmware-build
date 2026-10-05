"""The two machines the tapes are tried on, built on tools/emu/session.py:

  TSPico  ZEsarUX on the TS-Pico ROM with the real firmware behind it
          (tools/emu/pico_host.py), the tape on its card: LOAD "tpi:name", LOAD "".
  Stock   ZEsarUX on its own TS-2068 ROM, no TS-Pico, the tape loaded
          from its virtual deck (ZRCP smartload): what a real 2068 would do.

run_parallel() runs jobs on several of them at once, each with its own ports.
"""

import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time

import common as C

sys.path.insert(0, C.EMU_DIR)
import session as S                                            # noqa: E402

RUN = 0xF7
STOCK_ROMS = [os.environ.get("TS2068_ROM", ""),
              "/Applications/zesarux.app/Contents/Resources/ts2068.rom",
              os.path.join(os.path.dirname(S.EMU), "..", "zesarux", "src", "ts2068.rom")]


def free_port():
    """A TCP port nothing is listening on, so runs in other work folders
    (or other sessions) don't collide."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def emu_dir(*p):
    return C.work("emu", *p)


class Machine(S.Session):
    """A ZEsarUX on ZRCP port `port` (no pkill of other sessions, unlike Session)."""

    def start_emu(self, port, rom, env):
        self.port = port
        os.makedirs(emu_dir(), exist_ok=True)       # ZEsarUX runs from here, never from its src/
        self.emu = subprocess.Popen(
            [S.EMU, "--machine", "TS2068", "--romfile", rom, "--enable-remoteprotocol",
             "--remoteprotocol-port", str(port), "--noconfigfile", "--vo", "null", "--ao", "null"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, cwd=emu_dir())
        self.s = None
        t0 = time.time()
        while self.s is None:
            try:
                self.s = socket.create_connection(("localhost", port), timeout=2)
            except OSError:
                assert time.time() - t0 < 30, "ZEsarUX didn't open ZRCP"
                time.sleep(0.3)
        self.cmd("")
        self.wait_editor()

    def type_line(self, *parts):
        """Enter a line and return at once (run() waits for a report, which a
        program that starts running never gives)."""
        line = b"".join(bytes([p]) if isinstance(p, int) else p.encode("latin-1") for p in parts)
        self.wait_editor()
        for k in range(0, len(line), 10):
            self.cmd("send-keys-ascii 120 " + " ".join(["97"] * min(10, len(line) - k)))
        t0 = time.time()
        while True:
            el = int.from_bytes(self.peek(S.E_LINE, 2), "little")
            cur = self.peek(el, len(line) + 1)
            if cur[-1] == 0x0D and all(b != 0x0D for b in cur[:-1]):
                break
            assert time.time() - t0 < 20, "typing failed"
            time.sleep(0.2)
        self.poke(el, line)
        self.cmd("poke %d 255" % S.ERR_NR)
        self.key(129)

    def result(self, shot):
        time.sleep(1)
        scr = self.text()
        self.screenshot(shot)
        return dict(err=self.peek(S.ERR_NR, 1)[0], screen=scr, rtape="Tape loading error" in scr)

    def close(self):
        for p in (self.emu, getattr(self, "host", None)):
            if p is None:
                continue
            try:
                p.terminate()
                p.wait(5)
            except Exception:                   # noqa: BLE001
                p.kill()


class TSPico(Machine):
    def __init__(self, k):
        self.root, self.log = emu_dir("root%d" % k), emu_dir("host%d.out" % k)
        seed = emu_dir("seed%d" % k)
        for d in (self.root, seed):
            shutil.rmtree(d, ignore_errors=True)
        os.makedirs(os.path.join(seed, "TAP"))
        bridge = "127.0.0.1:%d" % free_port()
        self.host = subprocess.Popen(
            [sys.executable, "-u", os.path.join(C.EMU_DIR, "pico_host.py"), "--root", self.root, "--sd", seed,
             "--tcp", bridge, "--unix", ""], stdout=open(self.log, "w"), stderr=subprocess.STDOUT)
        t0 = time.time()
        while "listening" not in open(self.log).read():
            assert time.time() - t0 < 30, "pico_host didn't start: see " + self.log
            time.sleep(0.2)
        time.sleep(1.5)
        self.start_emu(free_port(), S.ROM, dict(os.environ, TSPICO_BRIDGE="tcp:" + bridge))

    def served(self, off):
        with open(self.log, errors="replace") as f:
            f.seek(off)
            tail = f.read()
        return len(re.findall(r"LVM LOAD exit: tap_idx=\d+", tail)), "Traceback" in tail

    def test(self, job):
        """job: id, tap, name; code: LOAD "" CODE; run: then RUN."""
        sd = os.path.join(self.root, "sd", "TAP")
        for f in os.listdir(sd):
            if f.lower().endswith(".tap"):
                os.remove(os.path.join(sd, f))
        shutil.copy(job["tap"], os.path.join(sd, job["name"]))
        nblocks = len(C.blocks(C.read(job["tap"])))
        r = dict(id=job["id"], name=job["name"], blocks=nblocks)
        # reset-cpu, not hard-reset-cpu: the latter doesn't always restart a
        # 2068 that's running a program. F4h/FFh back to the HOME bank first.
        self.cmd("write-port 244 0")
        self.cmd("write-port 255 0")
        self.cmd("reset-cpu")
        time.sleep(1.5)
        self.wait_editor()
        t = self.run(S.LOAD, '"tpi:%s"' % job["name"], timeout=30)
        if "0 OK" not in t:
            r.update(status="MOUNTFAIL", screen=t)
            return r
        off = os.path.getsize(self.log)
        self.type_line(*((S.LOAD, '""', S.CODE) if job.get("code") else (S.LOAD, '""')))
        # Watch the firmware serve blocks until it goes quiet; press ENTER /
        # SPACE to get past "press a key" between parts.
        t0 = last = time.time()
        served, keys, exc = 0, 0, False
        while time.time() - t0 < 75:
            time.sleep(0.5)
            n, exc = self.served(off)
            if n != served:
                served, last = n, time.time()
            idle = time.time() - last
            if exc or (served >= nblocks and idle > 4) or (job.get("code") and served >= 2 and idle > 3):
                break
            if idle > 5:
                if keys == 4:
                    break
                self.key((129, 32)[keys % 2])
                keys += 1
                last = time.time()
        served, exc = self.served(off)
        r.update(self.result(emu_dir("shots", job["id"] + ".bmp")), served=served, keys=keys, traceback=exc)
        if job.get("run"):
            self.type_line(RUN)
            time.sleep(8)
            after = self.result(emu_dir("shots", job["id"] + "-run.bmp"))
            r.update(run_err=after["err"], run_screen=after["screen"])
        return r


class Stock(Machine):
    """A stock 2068. A fresh one per tape: smartload works from the editor."""

    def __init__(self, k):
        rom = next((p for p in STOCK_ROMS if p and os.path.exists(p)), None)
        assert rom, "no stock ts2068.rom: set TS2068_ROM"
        self.host = None
        self.start_emu(free_port(), rom, dict(os.environ, TSPICO_BRIDGE="tcp:127.0.0.1:9"))  # no TS-Pico

    def test(self, job):
        self.cmd("smartload " + job["tap"])
        t0 = time.time()
        while "LOAD" in self.text() or time.time() - t0 < 3:   # smartload types LOAD "" itself
            if time.time() - t0 > 15:
                break
            time.sleep(0.5)
        self.cmd("poke %d 255" % S.ERR_NR)
        last, stable, keys, t0 = None, 0, 0, time.time()
        while time.time() - t0 < 60 and self.peek(S.ERR_NR, 1)[0] == 0xFF:
            time.sleep(1)
            t = self.text()
            stable = stable + 1 if t == last else 0
            last = t
            if stable >= 4:
                if keys == 4:
                    break
                self.key((129, 32)[keys % 2])
                keys, stable = keys + 1, 0
        return dict(self.result(emu_dir("shots", job["id"] + "-stock.bmp")), id=job["id"], keys=keys)


def run_parallel(make, jobs, outname, workers=8, fresh=False):
    """Run jobs (dicts with an id) on `workers` machines from make(k); results
    are saved in the work folder as outname, and ids already there skipped, so
    an interrupted run picks up where it stopped. fresh: a new machine per job."""
    os.makedirs(emu_dir("shots"), exist_ok=True)
    out = C.load(outname, [])
    done = {r["id"] for r in out}
    q = queue.Queue()
    for j in jobs:
        if j["id"] not in done:
            q.put(j)
    total, lock, stop = q.qsize(), threading.Lock(), threading.Event()
    print("%s: %d to do (%d already done)" % (outname, total, len(done)), flush=True)

    def worker(k):
        m = None
        while True:
            try:
                job = q.get_nowait()
            except queue.Empty:
                break
            for attempt in range(2):            # a machine that went wrong: a new one, once
                try:
                    if m is None:
                        m = make(k)
                    job_result = m.test(job)
                    break
                except Exception as e:          # noqa: BLE001
                    job_result = dict(id=job["id"], status="ERROR", error=repr(e)[:300])
                    if m:
                        m.close()
                    m = None
            if fresh and m:
                m.close()
                m = None
            with lock:
                out.append(job_result)
                n = len(out) - len(done)
                if n % 25 == 0 or n == total:
                    print("  %d/%d" % (n, total), flush=True)
        if m:
            m.close()

    def saver():
        while not stop.wait(20):
            with lock:
                C.save(outname, out)
    threading.Thread(target=saver, daemon=True).start()
    ts = [threading.Thread(target=worker, args=(k,)) for k in range(workers)]
    for t in ts:
        t.start()
        time.sleep(2)
    for t in ts:
        t.join()
    stop.set()
    C.save(outname, out)
    return {r["id"]: r for r in out}
