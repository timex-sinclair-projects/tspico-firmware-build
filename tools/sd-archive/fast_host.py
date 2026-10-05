#!/usr/bin/env python3
"""tools/emu/pico_host.py for many sessions at once: same arguments, two changes.

pico_host answers the 2068's IN (0Eh) with whatever the firmware has queued,
or 00h (an underrun) when it has nothing yet. With several sessions sharing
the CPU the firmware thread falls behind mid-block, the 2068 reads 00h bytes,
and good tapes fail with Report R. Here an IN waits up to 50 ms for its byte
(a Pico that keeps up), and the firmware's idle poll sleeps instead of
spinning a core. Not for anything timing-related -- nor is pico_host.
"""

import queue
import sys
import time

import common as C

sys.path.insert(0, C.EMU_DIR)
import pico_host as P                                          # noqa: E402

_frame = P.BusModel._frame


def frame(self, op, v):
    if op != P.OP_IN_DATA:
        return _frame(self, op, v)
    try:
        return self.tx.get(timeout=0.05)
    except queue.Empty:
        self.underruns += 1
        return 0x00


def rx_fifo(self):
    n = self.rx.qsize()
    if not n:
        time.sleep(0.0005)
    return min(n, 4)


P.BusModel._frame = frame
P.BusModel.rx_fifo = rx_fifo

if __name__ == "__main__":
    P.main()
