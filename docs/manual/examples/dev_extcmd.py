"""Example TS-Pico commands (programmer's manual, Part 2).

Copy this file to the root of the Pico's flash as /dev_extcmd.py and reset
the Pico (with the TS-2068 switched off). The firmware loads it instead of
its built-in TS/extcmd.py; delete it to go back.

    SAVE "tpi:.hello"            prints a greeting (a message answer)
    SAVE "tpi:.fact" CODE n,0    n! as a data answer: 1, count, digits, XOR
    SAVE "tpi:.lines name"       counts the lines in a text file on the SD card

Every handler gives exactly ONE answer, and never writes the 01h that
follows it: PROCESS_CMD adds that when the handler returns.
"""

import math

# The helpers live in the firmware module that is running: /dev_tspico.py if
# you have one on flash, otherwise the built-in TS.tspico. Import the module,
# not the names, so its MQ (which changes after SD card work) is always the
# live one.
try:
    import dev_tspico as tp
except ImportError:
    import TS.tspico as tp

from TS import catalog

# Status codes. tspico's own names (_1_OK and so on) are underscore const()s,
# which MicroPython builds into tspico and never stores on the module, so
# tp._1_OK works on a PC but fails on the Pico. Keep your own.
OK = 1                                          # 0 OK
F_BAD_NAME = 3                                  # F Invalid file name
NUM_TOO_BIG = 6                                 # 6 Number too big


def HELLO(MQ, TSP, pre, cmd):
    """A message answer: function 81h, printed by the ROM."""
    tp.SEND_MSG("Hello from the TS-Pico!", "", OK, True)


def FACT(MQ, TSP, pre, cmd):
    """A data answer the Z80 reads itself: 1, n, n bytes, XOR of the bytes.

    From BASIC the ROM reads the 1 and returns; the program then reads the
    rest with IN 14. An error is a plain status the ROM turns into a report.
    """
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
    tp.MQ_READY()                               # data in TX first, then READY
    for b in digits:
        tp.CMD_PUT(b)                           # waits while TX is full
    tp.CMD_PUT(x)


def LINES(MQ, TSP, pre, cmd):
    """SD card work, then a message: how many lines a text file has."""
    name = tp.getArgs(cmd).strip()
    real = catalog.resolve(TSP.cur_path, name) if name else None
    if real is None:
        tp.SEND_MSG("Usage: tpi:.lines <file>", "", F_BAD_NAME)
        return

    def count():                                # runs with the SD card active
        n = 0
        with open(real, "rb") as f:
            while True:
                block = f.read(512)
                if not block:
                    break
                n += block.count(b"\n")
        return n

    n = tp.SD_CALL(count)                       # gives the bus back afterwards
    if isinstance(n, tuple):                    # SD_CALL's (message, status)
        tp.SEND_MSG("Can't read " + name, "", n[1])
        return
    tp.SEND_MSG("%s: %d lines" % (name, n), "", OK, True)


EXT_SA_FUNCT = {
    "TPI:.HELLO": HELLO,
    "TPI:.FACT": FACT,
    "TPI:.LINES": LINES,
}
