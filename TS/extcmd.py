"""User-extensible TPI command handlers.

To add a new TPI:.SOMECMD command, write a function here following the
pattern below and add it to EXT_SA_FUNCT at the bottom.

Each handler is called by PROCESS_CMD (in tspico.py) when the Z80 has
issued a "TPI:.XXX" BASIC command. PROCESS_CMD has already drained the
pre-header and command body; your handler just produces the response.

PROTOCOL CONTRACT (see docs/PROTOCOL.md for full details):
    - You DO NOT need to write a "next-iter pre-load" 0x01 at the end —
      PROCESS_CMD's tail does that for you after your handler returns.
    - You SHOULD NOT write a 0x40 byte for $0F continue — port $0F is
      decoupled from the FIFO in dual-port; the Y register handles it,
      and a 0x40 in TX would orphan and corrupt subsequent reads.
    - Z80 expects ONE response status byte (0x01 = OK, 2-9 = error
      reports). For verbose / multi-byte responses, use a function code
      (0x80-0xFF) as your "status" — see SEND_MSG / SEND_MSG2 for how.
"""

from random import randint
import math

from TS.sdcard import *

from tspico import ACTIVATE_MQ, ACTIVATE_SD, SEND_MSG, SEND_MSG2


def FACTORIAL(MQ: StateMachine, TSP, pre, cmd):
    """Compute n! and return as a TLV (type-length-value) response.

    Demonstrates a custom user-defined function-code response format.
    Note: the Z80 ROM has to know how to interpret type_res values in
    the 128-199 range — that's outside the standard protocol.
    """
    wrt = MQ.put

    type_res = 128       # 128-199 = "normal" custom response
                         # 200     = OK
                         # 201+    = error conditions
    length = 0

    # Send an interim message to the user while we compute (verbose only).
    SEND_MSG("Calculating Factorial...", "", 1)

    par1 = (pre[4] * 256) + pre[3]

    if par1 >= 33:
        # TS-2068 can't safely handle factorial values over 33!
        type_res = 210
        msg = "Number too big!"
    else:
        msg = str(math.factorial(par1))

    length = len(msg)

    # Send the result as a Type-Length-Value triple.
    MQ.put(type_res)
    MQ.put(length)
    for el in msg:
        MQ.put(el)

    return


def RND_WORD(MQ: StateMachine, TSP, pre, cmd):
    """Pick a random word from /words.txt and send it back.

    Demonstrates the simplest response shape: one status byte, then a
    stream of ASCII characters. The Z80 ROM will need a corresponding
    handler for whatever response code we send.
    """
    # Status byte (Z80 reads this first as the command result).
    # Dual-port: no wrt(0x40) — port $0F continue is handled by the Y
    # register, which is at READY for the whole session. Writing 0x40
    # here would leave an orphan byte in TX FIFO that corrupts
    # subsequent reads.
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


# Register your handlers here. The dictionary key is the EXACT command
# string the user types after "LOAD" or "SAVE" on the TS-2068, e.g.:
#     SAVE "TPI:.FACT", CODE 5, 0
EXT_SA_FUNCT = {
    "TPI:.FACT": FACTORIAL,
    "TPI:.RNDW": RND_WORD,
}
