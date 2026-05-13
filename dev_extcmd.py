"""Dev-override copy of TS/extcmd.py.

If present on the Pico's flash root alongside dev_tspico.{py,mpy},
this file is loaded INSTEAD of the frozen TS.extcmd. Lets you iterate
on external-command handlers without rebuilding the UF2.

To revert to the frozen TS.extcmd, just delete /dev_extcmd.py from
flash (and ensure dev_tspico's import chain falls back correctly).

Why this exists: putting a /TS/extcmd.py on flash would shadow the
ENTIRE TS package — Python expects all TS.* imports to resolve to
the flash directory once /TS/ exists there. So fixes to TS/extcmd.py
in the repo can't be tested in isolation on the Pico without a full
UF2 rebuild. dev_extcmd.py sidesteps that limitation, paralleling
the dev_tspico.py pattern.
"""

from random import randint
import math

from TS.sdcard import *

# ─── Portable import for tspico helpers ────────────────────────────────────
# Picks up dev_tspico if it's loaded, falls back to TS.tspico otherwise.
# Same chain as the canonical TS/extcmd.py fix (see commit log).
# ──────────────────────────────────────────────────────────────────────────
try:
    from dev_tspico import ACTIVATE_MQ, ACTIVATE_SD, SEND_MSG, SEND_MSG2
except ImportError:
    from TS.tspico import ACTIVATE_MQ, ACTIVATE_SD, SEND_MSG, SEND_MSG2


def FACTORIAL(MQ: StateMachine, TSP, pre, cmd):
    """Compute n! and return as a TLV (type-length-value) response."""
    wrt = MQ.put

    type_res = 128       # 128-199 = "normal" custom response
                         # 200     = OK
                         # 201+    = error conditions
    length = 0

    SEND_MSG("Calculating Factorial...", "", 1)

    par1 = (pre[4] * 256) + pre[3]

    if par1 >= 33:
        type_res = 210
        msg = "Number too big!"
    else:
        msg = str(math.factorial(par1))

    length = len(msg)

    MQ.put(type_res)
    MQ.put(length)
    for el in msg:
        MQ.put(el)

    return


def RND_WORD(MQ: StateMachine, TSP, pre, cmd):
    """Pick a random word from /words.txt and send it back."""
    MQ.put(0x01)

    buf = bytearray(10)

    # Pick a random byte offset into the word list. 85878 is the
    # position of the last word in /words.txt.
    offset = randint(1, 85878)

    with open("/words.txt", "r") as f_in:
        f_in.seek(offset)
        f_in.readline()           # discard first (likely incomplete) word
        buf = f_in.readline()     # next whole word
        buf = buf[:-2]            # strip trailing \r\n

    for el in buf:
        MQ.put(el)

    return


EXT_SA_FUNCT = {
    "TPI:.FACT": FACTORIAL,
    "TPI:.RNDW": RND_WORD,
}
