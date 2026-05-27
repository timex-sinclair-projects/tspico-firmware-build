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
    """Pick a random word from /words.txt and send it back.

    DUAL-PORT MIGRATION FIX:

      Previous implementation wrote `MQ.put(0x01)` then the word chars
      raw — i.e., it sent the "OK, no further output" status byte but
      then sent more bytes anyway. That violates the spec contract,
      where the Z80 reads ONE status byte and then either stops (for
      0x01-0x09 codes) or follows a function-code protocol (for
      0x80-0xFF codes).

      In practice the 2068's ROM kept reading past 0x01 and consumed
      the word chars — which "worked" for displaying the word but
      also drained the V6 pre-load byte placed by PROCESS_CMD's tail.
      So the NEXT command's pre-header phase found TX empty, read
      0x00, and reported J. Then BASIC's recovery sent stray bytes
      that kept the main loop's idle `ts` updating, preventing the
      heartbeat from firing — Pico appeared "halted."

      Fix: use the documented 0x81 (PRINT_STRING) protocol per spec
      p.5:
          27: 0x81  function code (PRINT_STRING)
          28: 0x01  status code (no error)
          29+: characters (printable ASCII)
          34:  0x00 end of string

      Z80 reads exactly that sequence, stops at 0x00, V6 pre-load is
      preserved, next command works normally.
    """
    # Pick a random byte offset into the word list. 85878 is the
    # position of the last word in /words.txt.
    offset = randint(1, 85878)

    with open("/words.txt", "r") as f_in:
        f_in.seek(offset)
        f_in.readline()           # discard first (likely incomplete) word
        buf = f_in.readline()     # next whole word
        buf = buf[:-2]            # strip trailing \r\n

    # Standard PRINT_STRING protocol (spec p.5).
    MQ.put(0x81)                  # function code: PRINT_STRING
    MQ.put(0x01)                  # status: no error
    for el in buf:
        MQ.put(el)                # word characters
    MQ.put(0x00)                  # end-of-string terminator

    return


EXT_SA_FUNCT = {
    "TPI:.FACT": FACTORIAL,
    "TPI:.RNDW": RND_WORD,
}
