# The Pico half of the issue-#254 stress test (the 2068 half is st254.asm).
#
# Run at the REPL of a v3 card flashed with the TSBUS_DIAG build, firmware
# stopped (pico-serial.py break), after the 2068 has loaded st254.tap:
#
#     python3 tools/pico-serial.py run --file src/test/st254/stress.py --timeout 400
#
# It holds the status port at 00h and waits for the 2068's first heartbeat
# (RUN 100), then puts the card through timed phases. Per phase it reports
#
#   - what the 2068 saw: heartbeats (65536 reads each) and the reads that
#     weren't 00h, by value -- the 2068 sends each one back with OUT (0Eh);
#   - what core 1 saw (tsbus.diag): INs to 0Eh/0Fh, those whose strobe had
#     ended before the handler started ("gone") or before it drove the bus
#     ("missed"), the shortest time from handler entry to the strobe's end,
#     the longest core 1 loop pass, and a histogram of entry-to-end times.
#
#   - how long the reply took to reach MD after core 1 wrote it to io_drive
#     (drive_max, a histogram, and "never" within 1 us).
#
# If the 2068 sees bad reads in a phase where core 1 reports no gone/missed
# and normal times, core 1 answered in time and the fault is downstream of
# it (PIO, U3, the bus); if gone/missed or the gap spike with them, core 1
# was late or stalled. A slow drive with on-time entry points at the write
# from core 1 to PIO0 being held up.

import gc, machine, os, time, tsbus
from TS import board
from TS.sdcard import SDCard

PHASE_S = 8
CYC_NS = 4                      # tsbus runs core 1 at 250 MHz

# 0: wait for the 2068's heartbeat first (RUN 100); 1: start at once, for
# the bus-latency columns alone, the 2068 left at its prompt.
NO_2068 = 0

# 1: give core 1 high bus priority too (tsbus gives it to DMA only), to see
# whether that changes the flash phases. The stress test sets this line.
PRIO = 0
BUSCTRL_PRIORITY = 0x40068000   # BUSCTRL_BASE: bus_priority
PRIO_PROC1 = 0x10

mq = tsbus.MQ()
buf = bytearray(4096)
for i in range(len(buf)):
    buf[i] = i & 0xFF


def drain(acc):
    while mq.rx_fifo():
        w = mq.get()
        if w >> 8:
            acc[0] += 1         # OUT (0Fh): a heartbeat
        else:
            acc[1] += 1         # OUT (0Eh),value: a bad read
            v = w & 0xFF
            acc[2][v] = acc[2].get(v, 0) + 1


def quiet():
    mq.status(0)
    while mq.tx_fifo():
        mq.exec("pull (noblock)")


# ---- the phases: each a function doing one unit of work ----------------

def p_idle():
    time.sleep_ms(20)


def p_flash_write():
    with open("/TMP/st254.bin", "ab") as f:
        f.write(buf)
    if os.stat("/TMP/st254.bin")[6] >= 256 * 1024:
        os.remove("/TMP/st254.bin")


def p_flash_erase():
    with open("/TMP/st254e.bin", "wb") as f:
        f.write(buf)
    os.remove("/TMP/st254e.bin")


def p_flash_read():
    with open("/TMP/st254r.bin", "rb") as f:
        while f.readinto(buf):
            pass


def p_gc():
    junk = [bytearray(256) for _ in range(64)]
    del junk
    gc.collect()


_sd = [False]


def sd_on():
    if not _sd[0]:
        board.sd_take_bus()
        os.mount(SDCard(board.sd_spi(), board.sd_cs()), "/sd")
        _sd[0] = True


def sd_off():
    if _sd[0]:
        os.umount("/sd")
        board.sd_release_bus()
        _sd[0] = False


def p_sd_read():
    sd_on()
    with open("/sd/st254.tmp", "rb") as f:
        while f.readinto(buf):
            pass


def p_sd_write():
    sd_on()
    with open("/sd/st254w.tmp", "wb") as f:
        for _ in range(4):
            f.write(buf)


def p_sd_mount():
    sd_on()
    sd_off()


def p_mixed():
    p_flash_write()
    p_gc()
    p_sd_read()


# Anything that touches flash last: on the first runs the 2068 crashed in
# the first phase that did (a write, then a read).
PHASES = [
    ("idle", p_idle),
    ("gc", p_gc),
    ("sd mount/unmount", p_sd_mount),
    ("sd read", p_sd_read),
    ("sd write", p_sd_write),
    ("idle again", p_idle),
    ("flash read", p_flash_read),
    ("flash erase", p_flash_erase),
    ("flash write", p_flash_write),
    ("mixed", p_mixed),
]


# ---- set up --------------------------------------------------------------

try:
    os.umount("/sd")                      # the firmware's, if it was stopped mid-command
except OSError:
    pass

for name in ("/TMP/st254.bin", "/TMP/st254e.bin"):
    try:
        os.remove(name)
    except OSError:
        pass
with open("/TMP/st254r.bin", "wb") as f:
    for _ in range(16):
        f.write(buf)
sd_on()
with open("/sd/st254.tmp", "wb") as f:
    for _ in range(16):
        f.write(buf)
sd_off()
quiet()
while mq.rx_fifo():
    mq.get()
tsbus.diag_reset()
if PRIO:
    machine.mem32[BUSCTRL_PRIORITY] |= PRIO_PROC1
else:
    machine.mem32[BUSCTRL_PRIORITY] &= ~PRIO_PROC1
print("bus priority: %03Xh" % machine.mem32[BUSCTRL_PRIORITY])

print("waiting for the 2068: RUN 100" if not NO_2068 else "not waiting for the 2068")
acc = [0, 0, {}]
t0 = time.ticks_ms()
while not NO_2068 and acc[0] == 0 and acc[1] == 0:
    drain(acc)
    if time.ticks_diff(time.ticks_ms(), t0) > 180000:
        raise SystemExit("no heartbeat from the 2068 in 3 minutes")
    time.sleep_ms(10)
print("the 2068 is reading; phases of %d s" % PHASE_S)

results = []
for n, (name, fn) in enumerate(PHASES):
    acc = [0, 0, {}]
    quiet()
    drain([0, 0, {}])                     # anything from before this phase
    tsbus.diag_phase(n)
    ops = 0
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < PHASE_S * 1000:
        fn()
        ops += 1
        drain(acc)
    sd_off()
    drain(acc)
    tsbus.diag_phase(15)                  # between phases
    results.append((name, ops, acc))
    print("  %-17s done" % name)

for name in ("/TMP/st254.bin", "/TMP/st254r.bin"):
    try:
        os.remove(name)
    except OSError:
        pass
try:
    sd_on()
    for name in ("/sd/st254.tmp", "/sd/st254w.tmp"):
        try:
            os.remove(name)
        except OSError:
            pass
finally:
    sd_off()

# ---- report --------------------------------------------------------------

print()
print("phase              ops   hb  bad  | INs     gone missed min_ns gap_us | drive_max_ns never | bus read max ns: PIO0  APB  SRAM")
for n, (name, ops, acc) in enumerate(results):
    (ins, gone, missed, min_left, max_gap, hist, dmax, never, dhist,
     pio_rd, apb_rd, ram_rd) = tsbus.diag(n)
    print("%-17s %5d %4d %4d  | %7d %4d %6d %6d %6d | %11d %5d | %20d %4d %5d" % (
        name, ops, acc[0], acc[1], ins, gone, missed,
        min_left * CYC_NS if ins else -1, max_gap * CYC_NS // 1000,
        dmax * CYC_NS, never, pio_rd * CYC_NS, apb_rd * CYC_NS, ram_rd * CYC_NS))
    if acc[2]:
        vals = sorted(acc[2].items(), key=lambda kv: -kv[1])[:8]
        print("    bad values: " + ", ".join("%02Xh x%d" % kv for kv in vals))
    if ins:
        print("    entry-to-end, 256 ns buckets: " + " ".join(str(h) for h in hist))
        print("    drive, 32 ns buckets:         " + " ".join(str(h) for h in dhist))
print()
print("stats:", tsbus.stats())
