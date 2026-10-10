#!/usr/bin/env python3
"""Talk to the TS-Pico's USB serial console directly -- no Thonny needed.

Built for AI agents (and anyone at a shell) to monitor telemetry and use the
MicroPython REPL themselves instead of asking a human to copy/paste from
Thonny. Standard library only; macOS (/dev/cu.usbmodem*) and Linux
(/dev/ttyACM*).

Usage:
    python3 tools/pico-serial.py watch [--seconds N]   # passive, timestamped
    python3 tools/pico-serial.py break                 # Ctrl-C -> REPL
    python3 tools/pico-serial.py run "import os; print(os.listdir('/'))"
    python3 tools/pico-serial.py run --file snippet.py # multi-line (paste mode)
    python3 tools/pico-serial.py softreset             # Ctrl-D: rerun main.py
    python3 tools/pico-serial.py put local.py /remote.py   # copy a file onto the Pico
    python3 tools/pico-serial.py get /activity.log out.log # copy one off it
    python3 tools/pico-serial.py put --sd game.tap /TAP/game.tap  # onto the SD card
    python3 tools/pico-serial.py get --sd /TAP/game.tap game.tap  # off it
    python3 tools/pico-serial.py run --sd "print(os.listdir('/sd/TAP'))"
    python3 tools/pico-serial.py flash --branch my-branch   # CI UF2 -> Pico
    python3 tools/pico-serial.py flash --v3 --branch main   # the v3 card's UF2
    python3 tools/pico-serial.py flash path/to/firmware.uf2

`--sd` (put, get, run) mounts the SD card at /sd first, the way the
firmware's ACTIVATE_SD does (through TS.board, so on the v2 board and the v3
card alike), and unmounts it after; a put/get path gets /sd in front. Like
put and get it needs the REPL: `break` first, `softreset` after. The firmware
re-reads the card's folder at its next command.

`watch` opens the port READ-ONLY and never writes, so it cannot disturb the
running firmware; it reattaches if the Pico is unplugged and comes back.
Plugging USB into a Pico the 2068 is already powering does not reset it.

`flash` needs no buttons: it drops the firmware to the REPL and calls
machine.bootloader(), which reboots the chip into BOOTSEL (the RPI-RP2 drive
on a v2 board's RP2040, RP2350 on the v3 card), then copies the UF2 and waits
for the board to reboot into it. If the drive is already mounted it just
copies. It refuses a UF2 built for the other chip: a v2 build on the v3 card,
or the reverse, would leave a board that doesn't come up. A v3 card running
the bring-up firmware (no REPL) or hung needs BOOTSEL by hand. With
--branch/--run it downloads the `tspico-firmware-uf2` artifact (`--upgrade`:
`tspico-upgrade-uf2`; `--v3`: `tspico-v3-firmware-uf2`) from a successful
build.yml run via `gh`. `--branch B` takes the run for B's CURRENT
head commit on GitHub, so it never flashes an older build; `--run N` refuses
anything that isn't a finished, successful firmware build (a Pages deploy run
on the same commit has an id that looks just the same).

`put` and `get` move files over the REPL (base64, so any content), with the
firmware stopped at `>>>` -- `break` first.

`break`, `run`, `put`, `get`, `softreset` and `flash` WRITE to the port. `break` stops the firmware
(the 2068 has no TS-Pico until `softreset` or a power cycle) -- never send it
while the Pico may be mid-SD access: see "If the SD card won't mount after a
soft reboot" in docs/DEVELOPER_GUIDE.md. `run` assumes the REPL is at `>>>`.

Every command refuses to start if another process (usually Thonny) holds the
port: two readers split the output between them, and Thonny interrupts the
firmware when it connects.
"""

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tty

PROMPT = b">>> "


def find_port(explicit):
    if explicit:
        return explicit
    ports = sorted(glob.glob("/dev/cu.usbmodem*") + glob.glob("/dev/ttyACM*"))
    return ports[0] if ports else None


def holders(port):
    """PIDs + commands of other processes with the port open (needs lsof)."""
    try:
        out = subprocess.run(["lsof", "-t", port], capture_output=True, text=True).stdout
    except FileNotFoundError:
        return []
    res = []
    for pid in out.split():
        if int(pid) == os.getpid():
            continue
        cmd = subprocess.run(["ps", "-o", "command=", "-p", pid],
                             capture_output=True, text=True).stdout.strip()
        res.append("%s %s" % (pid, cmd[:80]))
    return res


def open_port(port, write):
    busy = holders(port)
    if busy:
        sys.exit("%s is already open by:\n  %s\nDisconnect Thonny (or stop the "
                 "other reader) first." % (port, "\n  ".join(busy)))
    flags = (os.O_RDWR if write else os.O_RDONLY) | os.O_NOCTTY | os.O_NONBLOCK
    fd = os.open(port, flags)
    tty.setraw(fd)
    return fd


def read_until(fd, seconds, until=None):
    out = b""
    end = time.time() + seconds
    while time.time() < end:
        try:
            b = os.read(fd, 8192)
        except BlockingIOError:
            b = b""
        if b:
            out += b
            if until and out.endswith(until):
                break
        else:
            time.sleep(0.03)
    return out


def write_all(fd, data):
    """Write in small chunks, draining the Pico's echo in between. The port
    is non-blocking, and the Pico echoes every pasted character: one big
    os.write() fills both directions and fails with EAGAIN (a paste-mode
    script of ~1 KB was enough)."""
    for i in range(0, len(data), 64):
        chunk = data[i:i + 64]
        while chunk:
            try:
                n = os.write(fd, chunk)
                chunk = chunk[n:]
            except BlockingIOError:
                n = 0
            read_until(fd, 0.02)                   # drain echo; discarded
    return len(data)


def emit(data):
    sys.stdout.write(data.decode("utf-8", "replace").replace("\r\n", "\n"))
    sys.stdout.flush()


def cmd_watch(args):
    stamp = lambda: time.strftime("%H:%M:%S")
    print("[watch start %s]" % stamp(), flush=True)
    end = time.time() + args.seconds
    fd, buf = None, b""
    while time.time() < end:
        if fd is None:
            port = find_port(args.port)
            if not port:
                time.sleep(0.1)
                continue
            fd = open_port(port, write=False)
            print("[%s attached %s]" % (stamp(), port), flush=True)
        try:
            b = os.read(fd, 4096)
        except BlockingIOError:
            b = b""
        except OSError as e:                        # unplugged
            print("[%s port gone: %s]" % (stamp(), e), flush=True)
            os.close(fd)
            fd = None
            continue
        if not b:
            time.sleep(0.02)
            continue
        buf += b
        while b"\n" in buf:
            line, buf = buf.split(b"\n", 1)
            print("%s %s" % (stamp(), line.decode("utf-8", "replace").rstrip("\r")),
                  flush=True)
    print("[watch end %s]" % stamp())


def with_port(args, fn):
    port = find_port(args.port)
    if not port:
        sys.exit("no Pico serial port found")
    fd = open_port(port, write=True)
    try:
        fn(fd)
    finally:
        os.close(fd)


def cmd_break(args):
    def go(fd):
        os.write(fd, b"\x03")
        time.sleep(0.3)
        os.write(fd, b"\x03")
        emit(read_until(fd, args.timeout, PROMPT))
        print()
    with_port(args, go)


def cmd_run(args):
    code = open(args.file).read() if args.file else args.code
    if code is None:
        sys.exit("run: give CODE or --file")

    def go(fd):
        read_until(fd, 0.2)                          # discard stale output
        if "\n" in code.strip():
            # Paste mode: Ctrl-E, the text, Ctrl-D. Handles blocks and
            # indentation that the line-by-line REPL would mangle.
            os.write(fd, b"\x05")
            read_until(fd, 1, b"=== ")
            write_all(fd, code.replace("\r\n", "\n").replace("\n", "\r").encode())
            write_all(fd, b"\x04")
        else:
            write_all(fd, code.encode() + b"\r")
        emit(read_until(fd, args.timeout, PROMPT))
        print()
    with_port(args, on_sd(args, go))


def _repl_line(fd, line, timeout=5):
    """One line at the friendly REPL; returns its output up to the prompt."""
    write_all(fd, line.encode() + b"\r")
    return read_until(fd, timeout, PROMPT)


# --sd: the SD card mounted at /sd as ACTIVATE_SD mounts it, through
# TS.board, so the same lines work on the v2 board and the v3 card. The
# firmware must be stopped (break) first: it unmounts the card after every
# command, so /sd is free at the REPL. A leftover mount is dropped first.
SD_MOUNT = ("import os\r"
            "from TS import board\r"
            "from TS.sdcard import SDCard\r"
            "exec('try:\\n os.umount(\\'/sd\\')\\nexcept OSError:\\n pass')\r"
            "_sd_mq = board.sd_take_bus(); os.mount(SDCard(board.sd_spi(), board.sd_cs()), '/sd')")
SD_UNMOUNT = "os.umount('/sd'); board.sd_release_bus(); del _sd_mq"


def sd_path(p):
    """A path on the card: /sd in front unless it is there already."""
    p = p if p.startswith("/") else "/" + p
    return p if p == "/sd" or p.startswith("/sd/") else "/sd" + p


def sd_mount(fd):
    out = b""
    for line in SD_MOUNT.split("\r"):
        out += _repl_line(fd, line, 10)
    if b"Traceback" in out:                          # not "Error": the guard line says OSError
        sys.exit("SD mount failed:\n" + out.decode("utf-8", "replace"))


def sd_unmount(fd):
    out = _repl_line(fd, SD_UNMOUNT)
    if b"Traceback" in out:
        print("SD unmount: " + out.decode("utf-8", "replace"))


def on_sd(args, go):
    """Run go(fd) with the card mounted if --sd was given."""
    if not getattr(args, "sd", False):
        return go

    def wrapped(fd):
        read_until(fd, 0.2)
        sd_mount(fd)
        try:
            go(fd)
        finally:
            sd_unmount(fd)
    return wrapped


def cmd_put(args):
    import base64
    data = open(args.local, "rb").read()
    remote = sd_path(args.remote) if args.sd else args.remote

    def go(fd):
        read_until(fd, 0.2)
        out = _repl_line(fd, "import binascii; _f = open(%r, 'wb')" % remote)
        if b"Error" in out:
            sys.exit(out.decode("utf-8", "replace"))
        for i in range(0, len(data), 384):
            chunk = base64.b64encode(data[i:i + 384]).decode()
            out = _repl_line(fd, "_f.write(binascii.a2b_base64(%r))" % chunk)
            if b"Error" in out:
                _repl_line(fd, "_f.close()")
                sys.exit(out.decode("utf-8", "replace"))
        _repl_line(fd, "_f.close(); del _f")
        out = _repl_line(fd, "import os; print(os.stat(%r)[6])" % remote)
        size = out.decode("utf-8", "replace").split("\n")
        ok = any(l.strip() == str(len(data)) for l in size)
        print("%s -> %s: %d bytes%s" % (args.local, remote, len(data),
                                        "" if ok else "  SIZE MISMATCH: %r" % out))
        if not ok:
            sys.exit(1)
    with_port(args, on_sd(args, go))


def cmd_get(args):
    import base64

    remote = sd_path(args.remote) if args.sd else args.remote

    def go(fd):
        read_until(fd, 0.2)
        out = _repl_line(fd, "import os; print(os.stat(%r)[6])" % remote)
        try:
            size = int(out.decode().split("\n")[-2].strip())
        except (ValueError, IndexError):
            sys.exit(out.decode("utf-8", "replace"))
        _repl_line(fd, "import binascii; _f = open(%r, 'rb')" % remote)
        data = b""
        while len(data) < size:
            out = _repl_line(fd, "print(binascii.b2a_base64(_f.read(384)).decode().strip())", 10)
            lines = [l.strip() for l in out.decode("utf-8", "replace").split("\n")]
            b64 = lines[-2] if len(lines) >= 2 else ""
            chunk = base64.b64decode(b64) if b64 else b""
            if not chunk:
                break
            data += chunk
        _repl_line(fd, "_f.close(); del _f")
        open(args.local, "wb").write(data)
        print("%s -> %s: %d bytes%s" % (remote, args.local, len(data),
                                        "" if len(data) == size else "  SHORT (expected %d)" % size))
    with_port(args, on_sd(args, go))


def cmd_softreset(args):
    def go(fd):
        os.write(fd, b"\x04")
        emit(read_until(fd, args.timeout))
        print()
    with_port(args, go)


BOOT_DRIVES = ("RPI-RP2", "RP2350")             # the BOOTSEL drives' volume names


def rp2_drive():
    for name in BOOT_DRIVES:
        for d in ["/Volumes/" + name] + glob.glob("/media/*/" + name) + \
                glob.glob("/run/media/*/" + name):
            if os.path.isdir(d):
                return d
    return None


# UF2 family IDs (the field at offset 28 of each 512-byte block, when flag
# 0x2000 is set). A picotool-built RP2350 UF2 also carries ABSOLUTE blocks.
UF2_MAGIC = b"UF2\n\x57\x51\x5d\x9e"            # magic 0A324655h, 9E5D5157h
UF2_FAMILIES = {0xE48BFF56: "RP2040", 0xE48BFF59: "RP2350", 0xE48BFF5A: "RP2350",
                0xE48BFF5B: "RP2350"}


def uf2_chip(path):
    """The chip a UF2 is built for ("RP2040", "RP2350"), or None if unknown."""
    with open(path, "rb") as f:
        data = f.read()
    chips = set()
    for off in range(0, len(data) - 511, 512):
        if data[off:off + 8] != UF2_MAGIC:
            continue
        flags = int.from_bytes(data[off + 8:off + 12], "little")
        if flags & 0x2000:
            chips.add(UF2_FAMILIES.get(int.from_bytes(data[off + 28:off + 32], "little")))
    chips.discard(None)
    return chips.pop() if len(chips) == 1 else None


def drive_chip(drive):
    """The chip behind a BOOTSEL drive, from its INFO_UF2.TXT Board-ID."""
    try:
        with open(os.path.join(drive, "INFO_UF2.TXT")) as f:
            info = f.read()
    except OSError:
        return None
    if "Board-ID: RPI-RP2" in info:
        return "RP2040"
    if "Board-ID: RP2350" in info:
        return "RP2350"
    return None


BUILD_WORKFLOW = "build.yml"                 # the workflow that makes the UF2s
BUILD_WORKFLOW_NAME = "Build TS-Pico Firmware"   # its `name:`, as gh reports it


def gh_json(*args):
    return json.loads(subprocess.run(["gh"] + list(args), capture_output=True,
                                     text=True, check=True).stdout)


def branch_head(branch):
    """The commit the branch points at on GitHub right now."""
    sha = subprocess.run(["gh", "api", "repos/{owner}/{repo}/commits/" + branch, "--jq", ".sha"],
                         capture_output=True, text=True)
    if sha.returncode != 0 or not sha.stdout.strip():
        sys.exit("can't find branch %r on GitHub: %s" % (branch, sha.stderr.strip()))
    return sha.stdout.strip()


def ci_run_for_branch(branch):
    """The build.yml run for the branch's CURRENT head commit.

    Not `gh run list --branch B --limit 1`: on 2026-10-01 that returned a
    months-old run first for `main`, and `flash --branch main` put a build
    from #70 on the Pico instead of the one just merged. Runs are found by
    the head commit instead, so what gets flashed is always the code the
    branch has now -- or nothing, with a message saying why.
    """
    sha = branch_head(branch)
    runs = gh_json("run", "list", "--commit", sha, "--workflow", BUILD_WORKFLOW,
                   "--json", "databaseId,status,conclusion,headSha,createdAt")
    if not runs:
        sys.exit("no %s run for %s (%s) yet -- has CI started? Or pass --run"
                 % (BUILD_WORKFLOW, branch, sha[:7]))
    runs.sort(key=lambda r: r["createdAt"], reverse=True)
    ok = [r for r in runs if r["status"] == "completed" and r["conclusion"] == "success"]
    if not ok:
        r = runs[0]
        sys.exit("the %s run for %s (%s) is %s/%s -- wait for it, or pass --run"
                 % (BUILD_WORKFLOW, branch, sha[:7], r["status"], r["conclusion"] or "-"))
    return ok[0]


def check_run(run_id):
    """A --run id must be a finished, successful FIRMWARE build. Other
    workflows (Pages, release) run on the same commits and have ids that
    look just the same -- an easy one to mix up, and their artifacts don't
    include the UF2s."""
    r = gh_json("run", "view", str(run_id), "--json",
                "workflowName,status,conclusion,headSha,headBranch")
    if r["workflowName"] != BUILD_WORKFLOW_NAME:
        sys.exit("run %s is %r, not the firmware build (%r)"
                 % (run_id, r["workflowName"], BUILD_WORKFLOW_NAME))
    if r["status"] != "completed" or r["conclusion"] != "success":
        sys.exit("run %s is %s/%s -- only a successful build can be flashed"
                 % (run_id, r["status"], r["conclusion"] or "-"))
    return r


def ci_uf2(branch, run_id, dest, artifact="tspico-firmware-uf2"):
    """Download a UF2 artifact (tspico-firmware-uf2, or tspico-upgrade-uf2
    for the upgrade firmware); return the .uf2 path."""
    if run_id is None:
        r = ci_run_for_branch(branch)
        run_id = r["databaseId"]
    else:
        r = check_run(run_id)
    print("CI run %s (%s%s)" % (run_id, r["headSha"][:7],
                                ", " + r["headBranch"] if r.get("headBranch") else ""))
    subprocess.run(["gh", "run", "download", str(run_id), "-n", artifact,
                    "-D", dest], check=True)
    found = glob.glob(os.path.join(dest, "**", "*.uf2"), recursive=True)
    if not found:
        sys.exit("artifact had no .uf2")
    return found[0]


def cmd_flash(args):
    if bool(args.uf2) + bool(args.branch) + bool(args.run) != 1:
        sys.exit("flash: give exactly one of UF2, --branch, --run")
    tmp = tempfile.mkdtemp(prefix="tspico-uf2-")
    try:
        artifact = ("tspico-v3-firmware-uf2" if args.v3 else
                    "tspico-upgrade-uf2" if args.upgrade else "tspico-firmware-uf2")
        flash(args, args.uf2 or ci_uf2(args.branch, args.run, tmp, artifact))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def flash(args, uf2):
    drive = rp2_drive()
    if not drive:
        print("Putting the Pico into BOOTSEL via machine.bootloader() ...")
        def go(fd):
            os.write(fd, b"\x03")
            time.sleep(0.3)
            os.write(fd, b"\x03")
            read_until(fd, 3, PROMPT)
            os.write(fd, b"import machine; machine.bootloader()\r")
            time.sleep(0.5)
        try:
            with_port(args, go)
        except OSError:
            pass                                     # port vanished mid-write: expected
        end = time.time() + args.timeout
        while not drive and time.time() < end:
            time.sleep(0.25)
            drive = rp2_drive()
        if not drive:
            sys.exit("no BOOTSEL drive (%s) appeared -- use BOOTSEL + reset by hand, then rerun"
                     % " or ".join(BOOT_DRIVES))

    # The mount point exists before macOS has finished mounting it: copying
    # straight away can fail with EACCES. Wait for the bootloader's own
    # INFO_UF2.TXT, then retry the copy briefly.
    end = time.time() + args.timeout
    while not os.path.exists(os.path.join(drive, "INFO_UF2.TXT")) and time.time() < end:
        time.sleep(0.25)
    want, have = uf2_chip(uf2), drive_chip(drive)
    if want and have and want != have:
        hint = ("" if args.uf2 else
                " Use --v3 for the v3 card." if have == "RP2350" else " Leave out --v3 for a v2 board.")
        sys.exit("%s is built for the %s, but the board in BOOTSEL is an %s -- not copied"
                 " (it stays in BOOTSEL).%s" % (uf2, want, have, hint))
    print("Copying %s -> %s" % (uf2, drive))
    while True:
        try:
            shutil.copyfile(uf2, os.path.join(drive, os.path.basename(uf2)))
            break
        except PermissionError:
            if time.time() >= end:
                raise
            time.sleep(0.5)
    end = time.time() + args.timeout
    while rp2_drive() and time.time() < end:         # unmounts when it reboots
        time.sleep(0.25)
    while not find_port(args.port) and time.time() < end:
        time.sleep(0.25)
    print("Pico rebooted into the new firmware" if find_port(args.port)
          else "Copied; serial port not back yet")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--port", help="serial device (default: first usbmodem/ttyACM)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    w = sub.add_parser("watch", help="passive, read-only, timestamped capture")
    w.add_argument("--seconds", type=float, default=600)
    w.set_defaults(fn=cmd_watch)

    b = sub.add_parser("break", help="Ctrl-C the firmware to the REPL")
    b.add_argument("--timeout", type=float, default=3)
    b.set_defaults(fn=cmd_break)

    r = sub.add_parser("run", help="run Python at the REPL, print its output")
    r.add_argument("code", nargs="?")
    r.add_argument("--file", help="multi-line snippet, sent in paste mode")
    r.add_argument("--timeout", type=float, default=5)
    r.add_argument("--sd", action="store_true", help="with the SD card mounted at /sd")
    r.set_defaults(fn=cmd_run)

    s = sub.add_parser("softreset", help="Ctrl-D: soft reboot, rerun main.py")
    s.add_argument("--timeout", type=float, default=3,
                   help="seconds of boot output to show")
    s.set_defaults(fn=cmd_softreset)

    p = sub.add_parser("put", help="copy a local file onto the Pico (REPL at >>>)")
    p.add_argument("local")
    p.add_argument("remote")
    p.add_argument("--sd", action="store_true", help="REMOTE is on the SD card (/sd added)")
    p.set_defaults(fn=cmd_put)

    g = sub.add_parser("get", help="copy a file off the Pico (REPL at >>>)")
    g.add_argument("remote")
    g.add_argument("local")
    g.add_argument("--sd", action="store_true", help="REMOTE is on the SD card (/sd added)")
    g.set_defaults(fn=cmd_get)

    f = sub.add_parser("flash", help="put the Pico in BOOTSEL and copy a UF2")
    f.add_argument("uf2", nargs="?", help="local .uf2 file")
    f.add_argument("--branch", help="the CI build of this branch's current head commit")
    f.add_argument("--run", help="a specific CI run id")
    g2 = f.add_mutually_exclusive_group()
    g2.add_argument("--upgrade", action="store_true",
                    help="the upgrade UF2 (src/upgrade/) instead of the firmware")
    g2.add_argument("--v3", action="store_true",
                    help="the v3 card's UF2 (board TSPICO_V3) instead of the v2 firmware")
    f.add_argument("--timeout", type=float, default=30)
    f.set_defaults(fn=cmd_flash)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
