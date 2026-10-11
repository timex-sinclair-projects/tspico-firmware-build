# bustest: bus integrity on the v3 card

Written to find out why **Sinistar** (jon0x0/ts2068, `arcade-ports/sinistar`, a
64K AROS cartridge) crashed within seconds on the v3 card. It turned out to
be a fault in that 2068: Sinistar crashed on the v2.2 board with the same
machine, and ran flawlessly on a second 2068 with the v3 card. Every test
here passed on the v3 card. They're kept as a bus and RAM check for the
card and for a 2068.

## The harness

`bustest.asm` runs on the 2068 and checks every byte it reads against a
cartridge whose content is a function of the address (`make_dck.py`:
`f(addr) = lo ^ hi ^ 5Ah`, with a `LD A,D0h+c / RET` stub in each chunk). It
fills RAM in chunks 4, 6, 7 with `~f` and `LD A,50h+c` stubs, so any byte
says which bank answered. Its own code, stack, IM2 table and variables live
in chunk 5 (B000h-BFFFh), the one chunk it never switches.

Each iteration:

- **Picks a random HSR** over chunks 0-4, 6, 7.
- **Checks the bank straight after the `OUT (F4h)`**, with one of two
  probes:
  - `JP (HL)` into a stub (type 2). This is an opcode fetch from the new
    mapping 4 T-states later.
  - `LD A,(HL)` (type 1).
- **Every 64th iteration, does an `LDIR`** of 256 bytes from a chunk, all of
  them checked (type 5).
- **Checks the stack** (type 6): a random word pushed and popped, and a
  `CALL` that checks its own return address.
- **Checks RAM** (type 7): a 256-byte pattern, one byte checked and
  rewritten, all of it every 64th iteration, and a scratch byte written and
  read back.
- **Scans the keyboard:** 8 INs from port FEh.
- **Writes a screen byte and AY register 14.**

An IM2 interrupt every frame does what Sinistar's does. It switches to
HSR 10h, checks a dock byte (type 3) and a RAM byte (type 4), writes to the
AY, then switches the HSR back.

`DOCKRUN` (`sjasmplus -DDOCKRUN`) builds the same test to run from the
cartridge, as Sinistar does: its code is put into the dock image at 9100h
and chunk 4 stays DOCK, so nearly every opcode fetch comes from the card.

Build and run (the v3 card's slot files for flash slots 8-9 shown):

```
sjasmplus bustest.asm                      # bustest.bin, RAM-resident
sjasmplus -DDOCKRUN bustest.asm            # bustestd.bin (stub) + bustestd_dock.bin
python3 make_dck.py OUT [bustestd_dock.bin]   # (bustest|bustestd).dck, F08/F09 or D08/D09.bin
zmakebas -n bustest -a 10 -o loader.tap bustest.bas   # then append the CODE block at 45568
```

On the 2068: `LOAD "tpi:bustest.tap"`, `LOAD ""`, dock the cartridge, then
`RUN 100` for the normal display or `RUN 200` for ECM (DECR 2, Sinistar's
mode). A run is 16 x 65536 iterations, 6 to 11 minutes. The report gives
the error count by type and the first 12 errors (type, HSR, address,
expected, got, iteration).

## What it found (2026-10-11)

All runs on the v3 card: 0 errors.

- **Firmware:** main's, plus a hardware bank-path build that was tried and
  dropped.
- **Variants:** RAM-resident and dock-resident, normal and ECM display, with
  and without INs.
- **Volume:** millions of iterations, and 18,000-40,000 interrupts per run.

Sinistar's crashes, caught with `tsbus.diag_trap` in the diag build, were
in-game state corruption:

- One `RET` through a saved stack returned to 8908h instead of 890Ah. The
  low byte of the stack word read back as 08h instead of 0Ah, D1 lost.
- Others ended in HALT with interrupts off, or in a RAM loop.

## TSRun, headless (`tsrun/`)

Sinistar run in TSRun (the web player's emulator) under Node, to see where
its interrupts land. Copy TSRun's `*.js` and `roms/` to a scratch
directory, add `package.json` containing `{"type":"module"}`, and patch
`machine.js` in two places:

- **Export `memRead`.**
- **Add the hooks to `endRasterFrame`:** call
  `globalThis.__irqHook?.(m, "before")` before the interrupt, and count taken
  interrupts in `globalThis.__irqTaken`.
  - For `hold.mjs`, also hold /INT for `globalThis.__intHold` T-states: step
    one instruction at a time and take the interrupt at the first boundary
    with IFF1 set.
  - Add `globalThis.__jitter()` T-states to `runFrame`'s frame end.

`irqlog.mjs FRAMES DCK OUT` logs each frame's PC, SP, IFF1, HALT, HSR and
stack word. `hold.mjs FRAMES P J SEED DCK` runs with /INT held for P
T-states and the frame end jittered by up to J T-states.

Findings:

- **Dock chunk 3:** Sinistar never takes an interrupt while it is mapped
  (0 of 1,303 such frame ends).
- **Swapped stack:** it does take interrupts with SP swapped into its data
  (793 frames), and that is harmless there.
- **Perturbed timing:** no crash in 7,000 frames with /INT held 0-128
  T-states and up to 2,000 T-states of jitter. The demo returns to the
  title screen's DI wait loop at F8C0h about every 75 s, which isn't a hang.

## ramtest: the 2068's own RAM

`ramtest.asm` (loader `ramtest.bas`) runs March C- with eight data
backgrounds, plus an address-in-data pass, over 5F00h-FFFFh, forever.
Interrupts are off and the display is in ECM, Sinistar's conditions. The
report goes on the screen between passes. On the 2068 used for the
Sinistar tests it ran 37 passes with 0 errors (2026-10-11): the RAM is
sound.

Sinistar crashed on the v2.2 board as well, with the same 2068. On a second
2068 with the v3 card it ran flawlessly (2026-10-11). The fault was in the
first 2068, and it's pattern-sensitive: it corrupted Sinistar's state, D1 of
a stack byte included, but passed this RAM test and the bus tests. The v3
card and the game are fine.
