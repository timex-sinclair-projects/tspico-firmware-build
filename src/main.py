import time, utime, sys

from gc import mem_free, collect
from machine import freq, Pin

# ---------------- TELEMETRY SWITCH ----------------
# "TELEMETRY" in /config.ini: true = full TLM event logging on USB serial
# (development boards, tools/pico-serial.py watch); false or missing =
# silent, which releases ship (2026-09-30 audit, §4: main.py used to force
# it on for everyone). Read here, before TS2068_IO, so the first events of
# boot already follow it.
#
# We import the TS.tspico module here (BEFORE pulling TS2068_IO out of
# it) so we can poke the flag onto the module object directly. Setting
# it before any TLM() call ensures the very first events of boot are
# subject to the chosen setting.
#
# At runtime you can also toggle this from the REPL:
#       import TS.tspico                  # if using the frozen module
#       TS.tspico.TLM_ENABLED = True
#   or
#       import dev_tspico                 # if using the dev override
#       dev_tspico.TLM_ENABLED = True
import TS.tspico


def _telemetry():
    try:
        import json
        with open("/config.ini") as f:
            return json.load(f).get("TELEMETRY") is True
    except Exception:
        return False


TS.tspico.TLM_ENABLED = _telemetry()

# Dev override: if /dev_tspico.{py,mpy} is present on flash, use that
# instead of the frozen TS.tspico. Lets you iterate on a single file
# without rebuilding the UF2. To revert, just delete /dev_tspico.* from
# flash. A .mpy (no parsing, ~80% less RAM at import; build-dev-mpy.sh or CI)
# is used only with no .py beside it: MicroPython imports .py first (#175).
#
# CRITICAL: when the dev override loads, the TLM_ENABLED flag we set
# above is on TS.tspico, NOT dev_tspico. We must mirror it onto the
# module that's actually running, otherwise diagnostic prints are
# silently dropped. (Easy mistake — caught during stage-9 testing.)
try:
    from dev_tspico import TS2068_IO
    import dev_tspico
    dev_tspico.TLM_ENABLED = TS.tspico.TLM_ENABLED
    print("[DEV] Using /dev_tspico override (TLM=%s)" % dev_tspico.TLM_ENABLED)
except ImportError:
    from TS.tspico import TS2068_IO
    print("[DEV] Using frozen TS.tspico (TLM=%s)" % TS.tspico.TLM_ENABLED)
except ValueError as e:
    # A /dev_tspico.mpy compiled for another MicroPython: "incompatible .mpy
    # file". Every MicroPython upgrade changes the bytecode version (v1.20
    # wrote mpy 6.1), and before this a leftover override stopped main.py
    # before the TS-Pico started. Run the frozen firmware instead.
    from TS.tspico import TS2068_IO
    print("[DEV] /dev_tspico ignored (%s); using frozen TS.tspico" % e)

U6_EN = Pin(12, Pin.OUT, Pin.PULL_UP)
WAIT = Pin(14, Pin.OUT, Pin.PULL_DOWN)     # TS_IO_DUAL waits on GPIO 14 as /PICOSEL (the name is unverified: hardware.md)
U10_ENA = Pin(19, Pin.OUT, Pin.PULL_UP)
U13_ENA = Pin(20, Pin.OUT, Pin.PULL_UP)
BE = Pin(21, Pin.OUT, Pin.PULL_UP)
ROSCS = Pin(26, Pin.IN, Pin.PULL_DOWN)
U10_WE = Pin(27, Pin.OUT, Pin.PULL_UP)
 
U6_EN.value(1)
WAIT.value(1)
U10_ENA.value(1)
U13_ENA.value(1)
BE.value(1)
U10_WE.value(1)

freq(270_000_000)
print(freq())

log_msg = ""

# utime.sleep(.5)

# ---------------- BELT-AND-SUSPENDERS TOP-LEVEL HANDLER ----------------
# Wrap TS2068_IO() so any unhandled exception gets logged to
# /activity.log instead of dropping the Pico to a REPL with no
# diagnostic trace persisted to flash.
#
# Without this wrapper, an OSError out of _thread.start_new_thread (or
# any other unhandled exception in TS2068_IO) would propagate to here,
# Python prints a traceback to USB serial and exits. From the user's
# perspective the Pico "locks up" — LED stops blinking, 2068 gets J on
# the next command, and the only diagnostic is whatever was already on
# the USB serial console (often nothing if telemetry was off).
#
# With this wrapper, the exception is captured to /activity.log along
# with a timestamp, then we BREAK the outer while loop so we don't
# infinite-loop on the same exception. The Pico will be quiescent but
# the post-mortem will be on flash, retrievable via Thonny.
# ───────────────────────────────────────────────────────────────────────

while True:

    collect()

    try:
        TS2068_IO()

    except Exception as err:

        try:
            with open("/activity.log", "a") as log:
                log_msg = "[%d] FATAL ERROR in TS2068_IO:\n" % time.ticks_us()
                log.write(log_msg)
                sys.print_exception(err, log)
        except:
            # If we can't even write to flash, dump to USB serial as
            # last resort and break the loop.
            pass

        # Also print to USB serial for live debugging when attached.
        print("\n[FATAL] TS2068_IO raised %r — see /activity.log" % err)
        sys.print_exception(err)

        break
        
