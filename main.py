import time, utime, sys

from gc import mem_free, collect
from machine import freq, Pin

# ---------------- TELEMETRY SWITCH ----------------
# Edit this single line to control firmware-wide diagnostic prints.
# True  = full TLM event logging on USB serial (useful for development)
# False = silent (recommended for production / end-user installs)
#
# We import the TS.tspico module here (BEFORE pulling TS2068_IO out of
# it) so we can poke the flag onto the module object directly. Setting
# it before any TLM() call ensures the very first events of boot are
# subject to the chosen setting.
#
# At runtime you can also toggle this from the REPL:
#       import TS.tspico
#       TS.tspico.TLM_ENABLED = True
import TS.tspico
TS.tspico.TLM_ENABLED = True

# Dev override: if /dev_tspico.py is present on flash, use that instead
# of the frozen TS.tspico. Lets you iterate on a single file without
# rebuilding the UF2. To revert, just delete /dev_tspico.py from flash.
# /dev_tspico.py is a renamed copy of TS/tspico.py. It still imports
# `from TS.tspico_io import ...` etc — those resolve to the frozen
# modules because no /TS/ folder shadows them.
try:
    from dev_tspico import TS2068_IO
    print("[DEV] Using /dev_tspico.py override")
except ImportError:
    from TS.tspico import TS2068_IO

U6_EN = Pin(12, Pin.OUT, Pin.PULL_UP)
WAIT = Pin(14, Pin.OUT, Pin.PULL_DOWN)
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

while True:
    
    collect()
    TS2068_IO()
    
#     try:
#         TS2068_IO()
#         
#     except Exception as err:
#         
#         try:
#             close("activity.log")
#         except:
#             pass
#         
#         with open("/activity.log", "a") as log:
#             
#             log_msg += "[" + str(time.ticks_us()) + "] "
#             log_msg += "FATAL ERROR!!!:"
#             
#             log.write(log_msg)
#             sys.print_exception(err, log)
#             
#         break        
        
