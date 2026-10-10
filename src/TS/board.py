# The board the firmware runs on: every hardware touch goes through here.
#
# Two boards share one source tree (phase 4 of the v3 port plan;
# docs/v3-board-layer-proposal.md): the v2 TS-Pico (RP2040, the bus in PIO
# state machines) and the v3 card (RP2350B, the bus in the tsbus C module).
# The choice is made at run time: only the v3 build has tsbus. Both
# implementations export the same names; see board_v2.py.

# Not just `import tsbus`: on a host, src/tsbus/ (the C module's sources)
# imports as an empty namespace package. The real module has MQ.
try:
    from tsbus import MQ as _tsbus_mq
except ImportError:
    _tsbus_mq = None

if _tsbus_mq is not None:
    from TS.board_v3 import *
else:
    from TS.board_v2 import *
