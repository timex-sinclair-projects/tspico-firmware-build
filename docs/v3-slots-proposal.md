# Phase 5: slots on the v3 card (proposal)

Phase 5 of the v3 port plan (tspico-hardware `docs/v3-firmware-port-plan.md`)
brings the v3 card to parity with v2. This note covers its first and largest
part: **slots**. Today on the v3 card `tpi:boot`, `tpi:dock` and `tpi:blkrcv`
refuse with Report F (`NO_SLOTS`), the 2068 boots `/rom/TSPICO-23.ROM`, the
dock is empty, and so ZX48 mode can't run (the Spectrum ROM lives in slot 0).
Phase 4's design is [v3-board-layer-proposal.md](v3-board-layer-proposal.md).

## What v2 does

The v2 board has two 512K memory chips, each **16 slots of 32K**: the flash,
which keeps its contents, and the SRAM, which loses them at power-off
([flash/README.md](../flash/README.md),
[docs/reference/hardware.md](reference/hardware.md)).

- A **ROM** slot is a HOME ROM (16K) and an EXROM (16K). A **DOCK** cartridge
  is 64K, **two consecutive slots** numbered by the even one. The Spectrum
  ROM in slot 0 doubles as a dock: ZX48 mode's `OUT 244,3` maps the dock's
  first 16K over the ROM area.
- Two words pick what the 2068 sees: `ROM_SM` (flash or SRAM, for the boot
  ROM and for the dock) and `bank_sm` (the boot slot and the dock slot,
  4 bits each). `config.ini` keeps `ROM_SLOT`, `DCK_SLOT` and `ROM_SM`.
  A `tpi:boot` to anything but flash slot 1 is used for **one** power-on,
  then slot 1 comes back (`LOAD_CONFIG`), so a bad ROM can be escaped with
  a power cycle.
- `tpi:boot CODE m,s` switches the ROM under the **running** 2068 (the manual
  says to follow it with `NEW` or a reset). `tpi:dock CODE m,s` switches the
  dock live. `tpi:dock` isn't saved: it lasts until power-off.
- **Images get into a slot** through the Z80. Mounting a `.ROM`, `.BIN` or
  `.DCK` serves an updater tape (`romupdate.tap`, `dckupdate.tap`). Its
  BASIC asks for the memory and slot, guards against the booted slot
  ("never rewrite the slot you booted from"), then erases and programs the
  flash chip with SST39SF040 command sequences, or writes the SRAM. The
  Pico streams the image with `tpi:blkrcv`.

## What the v3 card has

No memory chips. `tsbus` serves three 64K SRAM images, `HOME`, `EXROM` and
`DOCK`, and `tsbus.switch(home=, exrom=, dock=)` replaces them:
- a ROM change holds the 2068 for 200 ms and releases it into the new ROM;
- a DOCK change is live.

Both were checked on proto1 ([reference/firmware/tsbus.md](reference/firmware/tsbus.md)).
Z80 writes to the dock are stored in the DOCK image. The flash filesystem is
about 14 MB. There is no PSRAM on the prototype.

## Proposal

### Slots are files

`/slots/F00.bin` … `/slots/F15.bin` are the flash slots, 32K each. The
numbering stays: `tpi:boot CODE 2,1`, `ROM_SLOT`, `DCK_SLOT` and existing
BASIC keep working, and a v2.2 flash image converts slot for slot.

**SRAM slots** (`MEM 1`) are `/slots/S00.bin` … `S15.bin`, and the firmware
**deletes them at boot**. That is the same "lost at power-off" as v2's
chip. The SRAM can't hold them: 16 × 32K is more than the RP2350B has left
after `tsbus`'s images. (Decision 1.)

A missing slot file reads as an empty slot: v2's erased or zero-filled
flash. The firmware never boots one (below).

### Booting

`board_v3.start_memory(rom_sm, bank_sm)` takes the boot memory and slot from
the words it is already given:
1. load the ROM slot's file, its first 16K into `HOME` and its second into
   `EXROM`;
2. load the dock (below);
3. serve, and release the 2068.

The one-shot boot is `LOAD_CONFIG`'s, unchanged.

If the boot slot's file is missing or isn't 32K, the firmware falls back to
**flash slot 1**, and logs it. If that's missing too, it falls back to
`/rom/TSPICO-23.ROM`, today's `ROM_FILE`. Phase 5's installer writes slot 1,
after which `/rom/` can go. The 2068 is never released into an empty ROM:
that would be a hang, on a machine with no way to fix it but USB.

### The dock

The `DOCK` image is 64K: the dock slot's file, then, for an even slot, the
next slot's file. That is v2's "two consecutive slots numbered by the even
one". A half with no file is mirrored from the other half, or is zeros if
neither exists. Slot 0 is the 16K Spectrum ROM, zero-filled to 32K as in
the 512K image, so the dock reads the Spectrum ROM at 0000h–3FFFh, which is
what ZX48 mode needs. Its upper 32K is slot 1, as two consecutive slots
would give on v2; ZX48 mode never maps it.

### `tpi:boot` and `tpi:dock`

These are the same commands, refusals and `config.ini` handling as v2.
`board_v3.map_slots(rom_sm, bank_sm)` compares the new words with what is
loaded:
- **The ROM changed:** `tsbus.switch(home=, exrom=)`. The 2068 is held
  200 ms and starts cleanly in the new ROM. That's a **behaviour change**
  from v2, which switches under the running Z80. (Decision 2.)
- **Only the dock changed:** `tsbus.switch(dock=)`, live, as v2.

`NO_SLOTS` goes, and with it `board.SLOTS`.

### Writing an image into a slot (`tpi:blkrcv` on v3)

The flash chip and its command sequences don't exist on v3, so the Pico
writes the slot file itself, from the image `MOUNT_FILE` already copied to
`/TMP/temp.bin` (`DCK_IMAGE` already makes a full 64K of a `.DCK`).

- Writing **the booted slot's file is safe** on v3: the 2068 runs from the
  SRAM image, not the file. The new ROM takes effect at the next boot or
  `tpi:boot`. v2's guard can relax on v3 to a warning.
- **How the user asks for it** is decision 3. Either keep the updater-tape
  workflow (mount, `LOAD ""`, answer the questions) with a small v3 updater
  tape that ends in `tpi:blkrcv`, or have one direct command.
- **Emulating the SST39SF040** for third-party Z80 flash tools (the port
  plan's decision 4) is left out of phase 5.

### Getting the slots onto the card

`tools/build-flash.py` gains `--slots DIR`. It writes `F00.bin` …
`F15.bin` from the manifest and a base image, which is where the third-party
ROMs and cartridges in slots 2, 3, 8–15 come from, as for the 512K image.
They go onto the card with `pico-serial.py put` for now. The web updater's
v3 support (phase 5, step 5) does it for users later.

### ZX48 on the v3 card

With slot 0 in the dock, `tpi:zx48` and `OUT 244,3` need nothing new on the
v3 side. ZX48_IO already runs on `tsbus.MQ()`, and the deep-queue host test
covers its streaming (#243). The phase 4 command list's ZX48 rows get run on
the card.

## Order of work

1. **Slot files and booting.** `start_memory` and the dock from `/slots`,
   with the fallbacks. Also `build-flash.py --slots`, and the slots put on
   the card. On the card: boot from F01, a missing slot, the one-shot.
2. **`tpi:boot` and `tpi:dock`.** `map_slots` through `tsbus.switch`, and
   `NO_SLOTS` gone. On the card: switch ROMs both ways; a live dock
   (a cartridge in F08–F15, if the base image has one); SRAM slots cleared
   at boot.
3. **ZX48 on the card.** The phase 4 ZX48 rows on proto1.
4. **Writing slots.** Decision 3's flow, then on the card: write a ROM into
   a spare slot, boot it, write the booted slot.

Each step is its own PR, with host tests in the style of
`board_v3_hosttest.py`: fake files, a fake `tsbus` recording `load` and
`switch`. Each updates the reference.

## Decisions

1. **SRAM slots:** files deleted at boot (proposed), or no SRAM slots on v3
   (`MEM 1` refused)?
2. **`tpi:boot` on v3:** a 200 ms reset into the new ROM (proposed, since a
   ROM swapped under a running Z80 runs a mix of the two), or emulate v2's
   live switch?
3. **Writing a slot:** a v3 updater tape that keeps romupdate's questions
   and ends in `tpi:blkrcv`, or one direct command
   (`SAVE "tpi:blkrcv" CODE m,s` with the image mounted)?
4. **The fallback ROM:** slot 1, then `/rom/TSPICO-23.ROM` (proposed), or
   refuse to boot and hold the 2068 with an error blink?
