"""Host-side test for MOVE / ERASE / FORMAT (and tpi:ren) -- CPython, no Pico.

Runs the REAL TS.tspico handlers the ROM's disk keywords turn into --
tpi:copy a|b, tpi:erase x, tpi:format x, tpi:cd x / tpi:cd -, tpi:ren a|b --
against a temporary directory standing in for the SD card (/sd/TAP), with
FAT's case-insensitive names. The SD/MQ switching and the message senders are
faked; what reaches SEND_MSG / SEND_MSG2 and what ends up on the "card" is
checked. PROMPT_EACH (ERASE's per-file Y/N) is checked byte by byte against
the ListMenu sequence the ROM's function-0x86 loop expects.

See docs/DISK_COMMANDS_SPEC.md §3.

Run:  python3 src/test/disk_cmds_hosttest.py
"""

import os
import shutil
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import process_cmd_hosttest as P                                # noqa: E402

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  PASS  " if cond else "  FAIL  ") + msg)


class CardOS:
    """os for tspico with /sd/TAP mapped onto a temp dir, case-insensitive like FAT."""

    def __init__(self, root):
        self.root = root
        self.cwd = "/sd/TAP"

    def real(self, p):
        assert p.startswith("/sd/TAP"), p
        cur = self.root
        for part in p[len("/sd/TAP"):].split("/"):
            if not part:
                continue
            hits = [n for n in os.listdir(cur) if n.lower() == part.lower()] \
                if os.path.isdir(cur) else []
            cur = os.path.join(cur, hits[0] if hits else part)
        return cur

    def stat(self, p):
        r = self.real(p)
        st = os.stat(r)
        return (0x4000 if os.path.isdir(r) else 0x8000, 0, 0, 0, 0, 0, st.st_size, 0, 0, 0)

    def ilistdir(self, p=None):
        r = self.real(p or self.cwd)
        for n in os.listdir(r):
            full = os.path.join(r, n)
            yield (n, 16384, 0, 0) if os.path.isdir(full) else (n, 32768, 0, os.path.getsize(full))

    def remove(self, p):
        os.remove(self.real(p))

    def rmdir(self, p):
        os.rmdir(self.real(p))

    def mkdir(self, p):
        os.mkdir(self.real(p))

    def rename(self, a, b):
        os.rename(self.real(a), self.real(b))

    def chdir(self, p):
        if not os.path.isdir(self.real(p)):
            raise OSError(2, "ENOENT")
        self.cwd = p

    def getcwd(self):
        return self.cwd


def on_card(root, *path, exact=False):
    """Is it there? Case-insensitive like FAT; exact=True also checks the case."""
    cur = root
    for part in path:
        hits = [n for n in os.listdir(cur) if (n == part if exact else n.lower() == part.lower())] \
            if os.path.isdir(cur) else []
        if not hits:
            return False
        cur = os.path.join(cur, hits[0])
    return True


def build_card(root):
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(os.path.join(root, "GAMES", "ARCADE"))
    os.makedirs(os.path.join(root, "EMPTY"))
    os.makedirs(os.path.join(root, "FULL"))
    for rel, data in (("ADVENT.TAP", b"A" * 700), ("CHESS.TAP", b"C" * 1500),
                      ("NOTES.BAK", b"n"), ("OLD.BAK", b"o"), ("KEEP.BAK", b"k"),
                      ("FULL/X.TAP", b"x"), ("GAMES/MANIC.TAP", b"m" * 10)):
        with open(os.path.join(root, *rel.split("/")), "wb") as f:
            f.write(data)


def setup(t, root):
    cos = CardOS(root)
    sent = []
    t.os = cos
    t.open = lambda p, mode="r": open(cos.real(p), mode)
    for n in ("ACTIVATE_SD", "DEACTIVATE_SD", "ACTIVATE_MQ"):
        setattr(t, n, lambda *a, **k: None)
    t.SEND_MSG2 = lambda msg, st, exp=True, colour=False: sent.append(("MSG2", msg, st))
    t.SEND_MSG = lambda msg, msg1, st, force=False: sent.append(("MSG", msg, msg1, st))
    t.led = types.SimpleNamespace(value=lambda *a: None, toggle=lambda: None)
    t.LOG = lambda *a: None
    t.busy = False
    t.dir_files_calls = 0

    def dir_files():
        t.dir_files_calls += 1
        return True
    t.DIR_FILES = dir_files
    t.mounted = []

    def mount(real, remounting=False):
        t.mounted.append(real)
        t.TSP.f_name = real
        return True
    t.MOUNT_FILE = mount
    t.GET_DIRS = lambda path="/sd/TAP": ["/TAP"]
    t.alldirs = ["/TAP", "/TAP/EMPTY", "/TAP/FULL", "/TAP/GAMES", "/TAP/GAMES/ARCADE"]
    t.TSP = types.SimpleNamespace(cur_path="/sd/TAP", f_name="", offset_tbl=[], tap_idx=0,
                                  append=False, VERBOSE=False, LOG_LEVEL=2)
    t.prev_path = None
    return sent


def call(t, sent, handler, cmd):
    del sent[:]
    handler(bytearray(10), "xxx" + cmd)
    return sent[-1] if sent else None


def test_copy(t, root):
    print("MOVE a TO b  (tpi:copy)")
    build_card(root)
    sent = setup(t, root)
    C = t.DISK_COPY
    r = call(t, sent, C, "tpi:copy advent.tap|advent2.tap")
    check(r[-1] == t._1_OK and on_card(root, "advent2.tap"), "file -> new name (%r)" % (r,))
    check(open(os.path.join(root, "advent2.tap"), "rb").read() == b"A" * 700, "  contents copied whole")
    check(on_card(root, "ADVENT.TAP"), "  source untouched")
    check(t.dir_files_calls >= 1, "  current dir listing refreshed")
    r = call(t, sent, C, "tpi:copy chess.tap|games")
    check(r[-1] == t._1_OK and on_card(root, "GAMES", "chess.tap"), "file -> a directory keeps its name")
    r = call(t, sent, C, "tpi:copy advent.tap|chess.tap")
    check(r[-1] == t._3_F_Invalid_file and open(os.path.join(root, "CHESS.TAP"), "rb").read() == b"C" * 1500,
          "existing target: Report F, not overwritten")
    r = call(t, sent, C, "tpi:copy nothere.tap|x.tap")
    check(r[-1] == t._3_F_Invalid_file, "missing source: Report F")
    r = call(t, sent, C, "tpi:copy games|x")
    check(r[-1] == t._4_Q_Parameter, "a directory as the source: Report Q")
    r = call(t, sent, C, "tpi:copy advent.tap|nodir/x.tap")
    check(r[-1] == t._3_F_Invalid_file and not on_card(root, "nodir"), "destination dir missing: Report F")
    r = call(t, sent, C, "tpi:copy *.bak|full")
    check(r[0] == "MSG2" and r[-1] == t._1_OK, "pattern -> dir: a listing")
    check(all(on_card(root, "FULL", n) for n in ("KEEP.BAK", "NOTES.BAK", "OLD.BAK")), "  every match copied")
    check("KEEP.BAK" in r[1] and "copied" in r[1] and len(r[1]) % 32 == 0, "  one 32-column row per file")
    r = call(t, sent, C, "tpi:copy *.bak|full")
    check(r[0] == "MSG2" and r[1].count("exists") == 3, "  again: each one 'exists', none overwritten")
    r = call(t, sent, C, "tpi:copy *.bak|advent.tap")
    check(r[-1] == t._4_Q_Parameter, "pattern to a file: Report Q")
    r = call(t, sent, C, "tpi:copy *.zzz|full")
    check(r[-1] == t._3_F_Invalid_file, "pattern with no match: Report F")
    r = call(t, sent, C, "tpi:copy ../x|y")
    check(r[-1] == t._3_F_Invalid_file, "above the root: Report F")
    r = call(t, sent, C, "tpi:copy advent.tap")
    check(r[-1] == t._4_Q_Parameter, "one name only: Report Q")
    r = call(t, sent, C, "tpi:copy /games/manic.tap /full")
    check(r[-1] == t._1_OK and on_card(root, "FULL", "MANIC.TAP", exact=True),
          "typed by hand with a space, absolute paths; the copy keeps the stored name")


def test_erase(t, root):
    print("ERASE  (tpi:erase)")
    build_card(root)
    sent = setup(t, root)
    E = t.DISK_ERASE
    r = call(t, sent, E, "tpi:erase notes.bak")
    check(r[-1] == t._1_OK and not on_card(root, "NOTES.BAK"), "a file: gone, no prompt")
    check(r[0] == "MSG", "  answered with SEND_MSG (silent unless VERBOSE)")
    r = call(t, sent, E, "tpi:erase nothere")
    check(r[-1] == t._3_F_Invalid_file, "missing: Report F")
    r = call(t, sent, E, "tpi:erase games")
    check(r[-1] == t._4_Q_Parameter and on_card(root, "GAMES"), "a directory without '/': Report Q, kept")
    r = call(t, sent, E, "tpi:erase full/")
    check(r[-1] == t._4_Q_Parameter and on_card(root, "FULL"), "non-empty directory: Report Q, kept")
    with open(os.path.join(root, "EMPTY", "dirinfo.tap"), "wb") as f:
        f.write(b"d")
    r = call(t, sent, E, "tpi:erase empty/")
    check(r[-1] == t._1_OK and not on_card(root, "EMPTY"), "empty directory (bar dirinfo.tap): removed")
    check("/TAP/EMPTY" not in t.alldirs, "  and dropped from alldirs")
    t.TSP.cur_path = "/sd/TAP/GAMES/ARCADE"
    r = call(t, sent, E, "tpi:erase /games/")
    check(r[-1] == t._4_Q_Parameter, "the current directory's parent: Report Q")
    t.TSP.cur_path = "/sd/TAP"
    t.TSP.f_name = "/sd/TAP/ADVENT.TAP"
    r = call(t, sent, E, "tpi:erase advent.tap")
    check(r[-1] == t._4_Q_Parameter and on_card(root, "ADVENT.TAP"), "the mounted file: Report Q, kept")
    t.TSP.f_name = ""

    asked = []

    def answers(ans):
        def prompt_each(prompts):
            asked[:] = prompts
            return ans
        return prompt_each

    t.PROMPT_EACH = answers([0, 2])                              # Y to KEEP, skip NOTES?, Y to OLD
    build_card(root)
    r = call(t, sent, E, "tpi:erase *.bak")
    check(asked == ["Erase /KEEP.BAK (Y/N)?", "Erase /NOTES.BAK (Y/N)?", "Erase /OLD.BAK (Y/N)?"],
          "pattern: one prompt per match, sorted (%r)" % asked)
    check(not on_card(root, "KEEP.BAK") and on_card(root, "NOTES.BAK") and not on_card(root, "OLD.BAK"),
          "  only the ones answered Y are erased")
    check(sent == [], "  nothing sent after the prompt exchange")
    t.PROMPT_EACH = answers([])
    r = call(t, sent, E, "tpi:erase *.zzz")
    check(r[-1] == t._3_F_Invalid_file, "pattern with no match: Report F, no prompt")


def test_prompt_each(t):
    print("PROMPT_EACH byte sequence")
    tx = []
    keys = []
    t.CMD_PUT = lambda b: tx.append(b if isinstance(b, int) else ord(b))
    t.MQ_READY = lambda: tx.append("READY")
    t.CMD_DRAIN = lambda: tx.append("DRAIN")
    t.CMD_KEY = lambda: keys.pop(0)
    t.MQ = types.SimpleNamespace(rx_fifo=lambda: 0, get=lambda: 0)

    def nr(seq):
        """The bytes alone (READY's exact place is CMD_SEND's business)."""
        return [b for b in seq if b != "READY"]

    def ready_after_data(seq):
        """Every READY has at least one byte queued since the last key."""
        since = 0
        for b in seq:
            if b == "READY":
                if not since:
                    return False
                since = 0
            elif b != "DRAIN":
                since += 1
        return True

    def run(k, prompts=("A?", "B?", "C?")):
        del tx[:]
        keys[:] = k
        return t.PROMPT_EACH(list(prompts))

    got = run([ord("Y"), ord(" "), ord("y")])
    check(got == [0, 2], "Y / other / y -> indexes 0 and 2 (%r)" % got)
    want = [0x86, 1, "READY", 0x0D, ord("A"), ord("?"), 0,
            ord("Y"), "READY", 0x0D, ord("B"), ord("?"), 0,
            ord(" "), "READY", 0x0D, ord("C"), ord("?"), 0,
            ord("y"), 0x03, "READY", "DRAIN"]
    check(nr(tx) == nr(want) and tx.count("READY") == 4 and ready_after_data(tx) and tx[-2:] == ["READY", "DRAIN"],
          "0x86, 1, then echo-prompt-0 per key, echo 0x03 at the end; a READY per page, after its data")
    got = run([ord("y"), ord("n"), ord("Y")])
    check(got == [0, 2] and nr(tx)[-3:] == [ord("Y"), 0x03, "DRAIN"] and tx.count("READY") == 4,
          "y / n / Y -> 0 and 2: N skips that one and the questions go on to 0x03 -- the ROM reads"
          " on after N (#227) (%r)" % got)
    check([b for b in tx if b in (ord("y"), ord("n"))] == [ord("y"), ord("n")],
          "  each key echoed as typed")
    try:
        got = run([], prompts=())
        ok = got == [] and tx == []
    except Exception as e:                                      # noqa: BLE001
        ok, got = False, e
    check(ok, "no prompts: [] and nothing sent -- not TypeError (#167) (%r, %r)" % (got, tx))

    print("SEND_MSG_PROMPT_YN on the lower screen (function 0x88)")
    def yn(k, lower):
        del tx[:]
        keys[:] = [k]
        return t.SEND_MSG_PROMPT_YN("Replace x? (Y/N)", lower=lower)
    got = yn(ord("y"), True)
    check(got == ord("Y") and nr(tx)[:3] == [0x88, 1, ord("R")] and ready_after_data(tx),
          "0x88, status, then the prompt at once -- no leading new line; READY after data (%r)" % tx[:5])
    k = tx.index(0)
    check(tx[k + 1:k + 5] == [ord("y"), 0x0D, 0x03, "READY"],  # (3 bytes: all in TX, then READY)
          "after the key: its echo, a new line for the ROM's next message, 0x03, READY (%r)" % tx[k + 1:])
    got = yn(ord("n"), True)
    k = tx.index(0)
    check(got == ord("N") and tx[k + 1:k + 5] == [ord("n"), 0x0D, 0x03, "READY"],
          "'n' comes back as N; the ROM reads on after N (#227), so its echo as typed, 0x0D, 0x03,"
          " READY (%r)" % tx[k + 1:])
    yn(ord("y"), False)
    check(nr(tx)[:3] == [0x86, 1, 0x0D] and ready_after_data(tx) and 0x0D not in tx[tx.index(0):],
          "main screen (0x86): the leading new line and echo as before, no extra one")


def test_format(t, root):
    print("FORMAT  (tpi:format)")
    build_card(root)
    sent = setup(t, root)
    F = t.DISK_FORMAT
    r = call(t, sent, F, "tpi:format new")
    check(r[-1] == t._1_OK and on_card(root, "new.tap") and os.path.getsize(os.path.join(root, "new.tap")) == 0,
          "name without .tap: empty new.tap")
    check(t.mounted and t.mounted[-1].upper() == "/SD/TAP/NEW.TAP" and t.TSP.append, "  mounted, append on")
    r = call(t, sent, F, "tpi:format games/level2.tap")
    check(r[-1] == t._1_OK and on_card(root, "GAMES", "level2.tap"), "in a subdirectory")
    t.mounted[:] = []
    r = call(t, sent, F, "tpi:format advent.tap")
    check(r[-1] == t._3_F_Invalid_file and os.path.getsize(os.path.join(root, "ADVENT.TAP")) == 700
          and not t.mounted, "existing file: Report F, not truncated, not mounted")
    r = call(t, sent, F, "tpi:format notes.txt")
    check(r[-1] == t._4_Q_Parameter and not on_card(root, "notes.txt"), "not a .tap: Report Q")
    r = call(t, sent, F, "tpi:format nodir/x.tap")
    check(r[-1] == t._3_F_Invalid_file, "missing directory: Report F")
    r = call(t, sent, F, "tpi:format tools/")
    check(r[-1] == t._1_OK and os.path.isdir(os.path.join(root, "tools")) and "/TAP/tools" in t.alldirs,
          "dir/: made, and added to alldirs")
    r = call(t, sent, F, "tpi:format tools/")
    check(r[-1] == t._3_F_Invalid_file, "dir/ again: Report F")
    r = call(t, sent, F, "tpi:format /")
    check(r[-1] == t._3_F_Invalid_file, "'/' : Report F (never touches the card itself)")


def test_cd_and_ren(t, root):
    print("MOVE TO (tpi:cd) and tpi:ren")
    build_card(root)
    sent = setup(t, root)
    st, _ = t.ChangeDir("games/arcade")
    check(st == t._1_OK and t.TSP.cur_path == "/sd/TAP/games/arcade", "cd a/b (%s)" % t.TSP.cur_path)
    st, _ = t.ChangeDir("-")
    check(st == t._1_OK and t.TSP.cur_path == "/sd/TAP", "cd - : back to where we were")
    st, _ = t.ChangeDir("-")
    check(st == t._1_OK and t.TSP.cur_path.upper() == "/SD/TAP/GAMES/ARCADE", "cd - again: toggles")
    st, _ = t.ChangeDir("../..")
    check(st == t._1_OK and t.TSP.cur_path == "/sd/TAP", "cd ../.. (resolved)")
    st, _ = t.ChangeDir("/games")
    check(st == t._1_OK and t.TSP.cur_path == "/sd/TAP/games", "cd /games (resolved from the root)")
    st, _ = t.ChangeDir("/")
    check(st == t._1_OK and t.TSP.cur_path == "/sd/TAP", "cd / still the root")
    st, _ = t.ChangeDir("nothere")
    check(st == t._3_F_Invalid_file and t.TSP.cur_path == "/sd/TAP", "cd to a missing dir: F, unchanged")
    t.prev_path = None
    st, _ = t.ChangeDir("-")
    check(st == t._3_F_Invalid_file, "cd - with no previous dir: F")

    R = t.DISK_REN
    r = call(t, sent, R, "tpi:ren advent.tap|adv.tap")
    check(r[-1] == t._1_OK and on_card(root, "adv.tap") and not on_card(root, "ADVENT.TAP"), "rename a file")
    r = call(t, sent, R, "tpi:ren adv.tap|games")
    check(r[-1] == t._1_OK and on_card(root, "GAMES", "adv.tap"), "rename into a directory moves it")
    r = call(t, sent, R, "tpi:ren chess.tap|old.bak")
    check(r[-1] == t._3_F_Invalid_file and on_card(root, "CHESS.TAP"), "onto an existing name: F, kept")
    r = call(t, sent, R, "tpi:ren games|games/arcade")
    check(r[-1] == t._4_Q_Parameter, "a directory into itself: Q")
    t.TSP.f_name = "/sd/TAP/CHESS.TAP"
    r = call(t, sent, R, "tpi:ren chess.tap|c.tap")
    check(r[-1] == t._4_Q_Parameter, "the mounted file: Q")


def test_native_open(t, root):
    print("SAVE / LOAD \"f:...\"  (tpi:fopen -> NATIVE_OPEN)")
    from TS import native as N
    build_card(root)
    sent = setup(t, root)
    flash = tempfile.mkdtemp(prefix="flash.")
    cos = t.os
    t.open = lambda p, mode="r": open(cos.real(p) if p.startswith("/sd/") else
                                      os.path.join(flash, os.path.basename(p)), mode)
    prompts = []
    t.SEND_MSG_PROMPT_YN = lambda msg, echo=True, lower=False: (prompts.append((msg, lower)), keys.pop(0))[1]
    keys = []

    def fopen(path, op, mod=0, session=0x4242):
        pre = bytearray(10)
        par1 = op | (mod << 8)
        pre[3], pre[4], pre[5], pre[6] = par1 & 0xFF, par1 >> 8, session & 0xFF, session >> 8
        del sent[:]
        t.NATIVE_OPEN(pre, "xxxtpi:fopen " + path)
        return sent[-1] if sent else None

    r = fopen("games/new.bas", 0)
    check(r[-1] == t._1_OK and t.TSP.native == dict(op=0, path="/sd/TAP/games/new.bas",
                                                    session=0x4242, refuse=False),
          "SAVE, new file: armed for the session (%r)" % (t.TSP.native,))
    keys[:] = [ord("Y")]
    r = fopen("advent.tap", 0)
    check(prompts[-1] == ("Replace advent.tap? (Y/N)", True) and t.TSP.native["refuse"] is False,
          "SAVE over a file: 'Replace advent.tap? (Y/N)' on the lower screen, Y -> armed to overwrite (%r)"
          % (prompts[-1],))
    with open(os.path.join(root, "averyveryverylongname.bas"), "wb") as f:
        f.write(b"x")
    keys[:] = [ord("Y")]
    fopen("averyveryverylongname.bas", 0)
    check(len(prompts[-1][0]) <= 31, "  a long name is cut so prompt + key fit one line (%r)" % (prompts[-1][0],))
    keys[:] = [ord("N")]
    fopen("advent.tap", 0)
    check(t.TSP.native["refuse"] is True, "  N -> armed to refuse (SAVE_TS gives Report D)")
    for path, st, what in (("games", t._4_Q_Parameter, "a directory"),
                           ("nodir/x.bas", t._3_F_Invalid_file, "no such directory"),
                           ("bad?name", t._3_F_Invalid_file, "a name FAT can't hold"),
                           ("", t._3_F_Invalid_file, "no name")):
        r = fopen(path, 0)
        check(r[-1] == st and t.TSP.native is None, "SAVE to %s: refused, nothing armed" % what)
    t.TSP.f_name = "/sd/TAP/CHESS.TAP"
    r = fopen("chess.tap", 0)
    check(r[-1] == t._4_Q_Parameter, "SAVE over the mounted file: Q")
    t.TSP.f_name = ""

    prog = bytes(range(200))
    with open(os.path.join(root, "prog.bas"), "wb") as f:
        f.write(bytes(N.plus3_header(0, len(prog), 10, len(prog))) + prog)
    with open(os.path.join(root, "pic.scr"), "wb") as f:
        f.write(bytes(6912))
    with open(os.path.join(root, "raw.bin"), "wb") as f:
        f.write(b"\x11" * 300)
    r = fopen("prog.bas", 1)
    tap = open(os.path.join(flash, "native.tap"), "rb").read()
    check(r[-1] == t._1_OK and t.TSP.native["op"] == 1 and t.TSP.native["totlen"] == len(tap),
          "LOAD a +3DOS program: armed with the one-shot tape")
    check(tap == N.as_tap(0, len(prog), 10, len(prog), prog, "prog"),
          "  the tape is exactly the header block + data block for it")
    r = fopen("pic.scr", 1, t.MOD_SCREEN)
    tap = open(os.path.join(flash, "native.tap"), "rb").read()
    check(r[-1] == t._1_OK and tap[3:4] == b"\x03" and N.fields_from_tape_header(tap[3:20])[1:3] == (6912, 16384),
          "LOAD ... SCREEN$ of a raw .scr: CODE 6912 at 16384")
    r = fopen("raw.bin", 1, t.MOD_CODE)
    tap = open(os.path.join(flash, "native.tap"), "rb").read()
    check(r[-1] == t._1_OK and N.fields_from_tape_header(tap[3:20])[:2] == (3, 300),
          "LOAD ... CODE of a headerless file: the whole file as CODE")
    for path, op, mod, st, what in (("raw.bin", 1, 0, t._3_F_Invalid_file, "headerless file as a program"),
                                    ("prog.bas", 1, t.MOD_CODE, t._4_Q_Parameter, "a program as CODE"),
                                    ("pic.scr", 3, 0, t._4_Q_Parameter, "MERGE of a screen"),
                                    ("raw.bin", 1, t.MOD_SCREEN, t._4_Q_Parameter, "SCREEN$ of 300 bytes"),
                                    ("nothere", 1, 0, t._3_F_Invalid_file, "a missing file")):
        r = fopen(path, op, mod)
        check(r[-1] == st and t.TSP.native is None, "LOAD %s: refused, nothing armed (%r)" % (what, r[1]))
    shutil.rmtree(flash, ignore_errors=True)


def test_channels(t, root):
    print("OPEN # channels: tpi:chopen / chwr / chrd / chclose")
    build_card(root)
    sent = setup(t, root)
    tx = []
    t.CMD_PUT = lambda b: tx.append(b)
    t.MQ_READY = lambda: tx.append("READY+IDLE")        # must not happen: see CH_READY
    real_ch_ready = t.CH_READY
    t.CH_READY = lambda: tx.append("READY")
    t.gc = types.SimpleNamespace(collect=lambda: None, mem_free=lambda: 0)
    t.CHANNELS.close_all()

    def cmd(handler, text, stream, par2=0):
        """Returns ("st", status) for a bare-status reply (CH_REPLY), else tx."""
        pre = bytearray(10)
        pre[3], pre[5], pre[6] = stream, par2 & 0xFF, par2 >> 8
        del sent[:]
        del tx[:]
        handler(pre, "xxx" + text)
        check(not sent, "  %s: nothing printed (a bare status)" % text.split()[0]) if sent else None
        return ("st", tx[0]) if len(tx) == 2 and tx[1] == "READY" else None

    r = cmd(t.CH_OPEN, "tpi:chopen w notes.txt", 4)
    check(r[-1] == t._1_OK and on_card(root, "notes.txt"), "chopen w: created (%r)" % (r,))
    cmd(t.CH_WRITE, "tpi:chwr " + (b"Hello\r" + bytes([0xF5]) + b"1\r").hex(), 4)
    cmd(t.CH_WRITE, "tpi:chwr " + b"end\r".hex(), 4)
    check(open(os.path.join(root, "notes.txt"), "rb").read() == b"Hello\nPRINT 1\nend\n",
          "chwr x2: text translated and appended on the card")
    r = cmd(t.CH_WRITE, "tpi:chwr zz", 4)
    check(r[-1] == t._5_C_Nonsense, "chwr with bad hex: C")
    cmd(t.CH_CLOSE, "tpi:chclose", 4)
    r = cmd(t.CH_OPEN, "tpi:chopen r notes.txt", 5)
    cmd(t.CH_READ, "tpi:chrd", 5, 6)
    data = bytes(b"Hello\r"[:6])
    x = 0
    for b in data:
        x ^= b
    check(tx == [1, 6, "READY"] + list(data) + [x],
          "chrd 6: status 1, count, READY, the bytes, their XOR (%r)" % (tx,))
    got = b""
    for _ in range(10):
        cmd(t.CH_READ, "tpi:chrd", 5, 255)
        if tx[0] != 1:
            break
        got += bytes(tx[3:3 + tx[1]])
    check(got == b"PRINT 1\rend\r" and tx == [t._7_8_EOF, "READY"],
          "then the rest, then status 7 (Report 8 End of file) (%r, %r)" % (got, tx))
    cmd(t.CH_READ, "tpi:chrd", 9, 10)
    check(tx == [t._10_J_Invalid_IO, "READY"], "chrd on a stream that isn't open: its status alone")
    r = cmd(t.CH_OPEN, "tpi:chopen r nothere.txt", 6)
    check(r[-1] == t._3_F_Invalid_file, "chopen r of a missing file: F")
    r = cmd(t.CH_OPEN, "tpi:chopen w nodir/x.txt", 6)
    check(r[-1] == t._3_F_Invalid_file, "chopen w into a missing dir: F")
    r = cmd(t.CH_OPEN, "tpi:chopen w games", 6)
    check(r[-1] == t._4_Q_Parameter, "chopen of a directory: Q")
    r = cmd(t.CH_OPEN, "tpi:chopen x notes.txt", 6)
    check(r[-1] == t._4_Q_Parameter, "chopen with a bad mode: Q")
    r = cmd(t.CH_OPEN, "tpi:chopen wb data.bin", 7)
    data = bytes(b for b in range(121) if b != 23)            # 23 is TAB
    cmd(t.CH_WRITE, "tpi:chwr " + data.hex(), 7)
    check(open(os.path.join(root, "data.bin"), "rb").read() == data, "binary: bytes as sent")
    r = cmd(t.CH_OPEN, "tpi:chopen u recs.dat", 8, 6)          # PMR2: the record length
    cmd(t.CH_WRITE, "tpi:chwr " + (bytes([23, 2, 0]) + b"two\r").hex(), 8)
    check(open(os.path.join(root, "recs.dat"), "rb").read() == b"      two   ",
          "chopen u with PMR2 = 6: TAB 2 writes record 2, padded (stage 2)")
    r = cmd(t.CH_OPEN, "tpi:chopen u recs.dat", 8, 255)
    check(r[-1] == t._4_Q_Parameter, "a record length over 254: Q")

    def listing(spec):
        """chopen r d:spec, then everything chrd serves: (status, text)."""
        r = cmd(t.CH_OPEN, "tpi:chopen r " + spec, 9)
        if r[-1] != t._1_OK:
            return r[-1], None
        got = b""
        while True:
            cmd(t.CH_READ, "tpi:chrd", 9, 255)
            if tx[0] != 1:
                return tx[0], got.decode()
            got += bytes(tx[3:3 + tx[1]])
    st, got = listing("d:")
    check(st == t._7_8_EOF and got.split("\r")[:4] == ["EMPTY/", "FULL/", "GAMES/", "ADVENT.TAP"],
          "d: -- dirs first with '/', then files, one a line, then end of file (%r)" % got)
    st, got = listing("d:*.bak")
    check(got == "KEEP.BAK\rNOTES.BAK\rOLD.BAK\r", "d:*.bak: the names CAT \"*.bak\" lists (%r)" % got)
    st, got = listing("d:games/*")
    check(got == "ARCADE/\rMANIC.TAP\r", "d:games/* -- a subdirectory's (%r)" % got)
    st, got = listing("d:*.zzz")
    check(st == t._7_8_EOF and got == "", "no match: opens, the first read is end of file")
    r = cmd(t.CH_OPEN, "tpi:chopen r d:nothere/*", 9)
    check(r[-1] == t._3_F_Invalid_file, "d: of a missing directory: F")
    r = cmd(t.CH_OPEN, "tpi:chopen w d:", 9)
    check(r[-1] == t._4_Q_Parameter, "d: with mode w: Q")
    r = cmd(t.CH_OPEN, "tpi:chopen r d:", 9, 10)
    check(r[-1] == t._4_Q_Parameter, "d: with a record length: Q")
    r = cmd(t.CH_CLOSE, "tpi:chclose", 12)
    check(r[-1] == t._1_OK, "chclose of a stream that isn't open: OK")
    t.CH_READY = real_ch_ready


def main():
    P.install_fakes()
    ext = types.ModuleType("dev_extcmd")
    ext.EXT_SA_FUNCT = {}
    sys.modules["dev_extcmd"] = ext
    import TS.tspico as t
    t.TLM_ENABLED = False
    real_prompt_each = t.PROMPT_EACH
    real_prompt_yn = t.SEND_MSG_PROMPT_YN
    root = tempfile.mkdtemp(prefix="disk_hosttest.")
    try:
        test_copy(t, root)
        test_erase(t, root)
        test_format(t, root)
        test_cd_and_ren(t, root)
        test_native_open(t, root)
        test_channels(t, root)
        t.PROMPT_EACH = real_prompt_each                          # test_erase stubs it
        t.SEND_MSG_PROMPT_YN = real_prompt_yn                     # test_native_open stubs it
        test_prompt_each(t)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    ok = all(results)
    print("\n%s (%d checks)" % ("ALL PASS" if ok else "FAILURES", len(results)))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
