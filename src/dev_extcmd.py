"""External TPI commands: add your own without touching tspico.py.

Each entry in EXT_SA_FUNCT maps a command word -- upper case, with its
"TPI:" and, by convention, a leading dot -- to a handler:

    def HANDLER(MQ, TSP, pre, cmd):

called by PROCESS_CMD (tspico.py) after it has read and checked the command.
`pre` is the 10-byte pre-header (PARAMS(pre) gives the CODE numbers), `cmd`
is "D.." + the command text (getArgs(cmd) gives the text after the command
word). `MQ` is the port state machine at the time of the call; use the
helpers below instead, because SD card work replaces it.

THE CONTRACT (docs/PROTOCOL.md):
  * give exactly ONE answer: a status byte, a message (SEND_MSG with force,
    function 81h), scrolling text (SEND_MSG2, 86h), or data in a format your
    2068 program reads -- and put the first bytes in the FIFO BEFORE saying
    READY (MQ_READY);
  * never write the 01h "pre-load" at the end: PROCESS_CMD's tail does;
  * queue bytes with CMD_PUT, which waits while the FIFO is full and turns a
    BREAK into CmdAbort (never catch that);
  * do SD card work inside SD_CALL, before the answer.

/dev_extcmd.py on the Pico's flash, if present, is loaded instead of this
module, so commands can be tried without rebuilding the UF2. The repo keeps
src/dev_extcmd.py identical to this file (src/test/dev_sync_hosttest.py).

The two examples:
    SAVE "tpi:.fact" CODE n,0   n! (n = 0..32) as a data answer: status 1,
                                count, digits, XOR of the digits; BASIC reads
                                it with IN 14 after the SAVE. n > 32: Report 6.
    SAVE "tpi:.rndw"            a random word from /words.txt on the flash,
                                printed by the ROM (a message answer).
"""

import math
from random import randint

# The helpers live in the firmware module that is running: /dev_tspico if
# there is one on flash, otherwise the frozen TS.tspico. Import the module,
# not the names, so its MQ (rebuilt after SD card work) is always the live one.
try:
    import dev_tspico as tp
except ImportError:
    import TS.tspico as tp

# Status codes. tspico's _1_OK etc. are underscore const()s, which MicroPython
# inlines and never stores on the module: they work on a PC and raise
# AttributeError on the Pico. So handlers keep their own.
OK = 1                                          # 0 OK
F_BAD_NAME = 3                                  # F Invalid file name
NUM_TOO_BIG = 6                                 # 6 Number too big


def FACTORIAL(MQ, TSP, pre, cmd):
    """n! as a data answer: 1, count, digits, XOR -- the tpi:chrd format."""
    n, _ = tp.PARAMS(pre)
    if n > 32:                                  # 33! has 37 digits: keep it short
        tp.CMD_PUT(NUM_TOO_BIG)                 # Report 6 Number too big
        tp.MQ_READY()
        return
    digits = str(math.factorial(n)).encode()
    x = 0
    for b in digits:
        x ^= b
    tp.CMD_PUT(1)                               # status: data follows
    tp.CMD_PUT(len(digits))                     # the count
    tp.MQ_READY()                               # data in the FIFO first, then READY
    for b in digits:
        tp.CMD_PUT(b)                           # waits while the FIFO is full
    tp.CMD_PUT(x)


WORDS = "/words.txt"                            # one word a line, CR LF


def RND_WORD(MQ, TSP, pre, cmd):
    """A random word from /words.txt, as a message the ROM prints."""
    try:
        with open(WORDS, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(randint(0, max(0, size - 64)))
            f.readline()                        # skip the (likely partial) line
            word = f.readline().strip().decode() or "the"
    except OSError:
        tp.SEND_MSG("No %s on the Pico" % WORDS, "", F_BAD_NAME)
        return
    tp.SEND_MSG(word, "", OK, True)


EXT_SA_FUNCT = {
    "TPI:.FACT": FACTORIAL,
    "TPI:.RNDW": RND_WORD,
}
