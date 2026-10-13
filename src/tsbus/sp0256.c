/*
 * sp0256: the SP0256-AL2 emulated from its ROM. See sp0256.h.
 *
 * The chip's code is MAME's, unchanged but for its form
 * (tools/sp0256-port.py makes sp0256_mame.inc from MAME's sp0256.cpp); this
 * file is MAME's constants, the ROM table, and MAME's ald_w and
 * sound_stream_update reduced to one sample at a time.
 */
#include <string.h>

#include "sp0256.h"

// MAME's constants (sp0256.cpp, lines 33-43).
#define CLOCK_DIVIDER (6*4*13)
#define HIGH_QUALITY
#define SCBUF_SIZE   (4096)             /* Must be power of 2               */
#define SCBUF_MASK   (SCBUF_SIZE - 1)
#define PER_PAUSE    (64)               /* Equiv timing period for pauses.  */
#define PER_NOISE    (64)               /* Equiv timing period for noise.   */
#define FIFO_ADDR    (0x1800 << 3)      /* SP0256 address of SPB260 speech FIFO.   */

#ifndef SP0256_ASSERT
#define SP0256_ASSERT(x) ((void)0)
#endif

// The AL2's ROM. Not const: core 1 reads it, so it must be in RAM.
uint8_t sp0256_al2[SP0256_ROM_N] = {
#include "sp0256_al2.inc"
};

// MAME reads the ROM from a 64K address space; the AL2's code and data are
// all at 1000h-17FFh, and the rest read 0 there (an empty region).
static inline uint8_t SP0256_RAM(sp0256_rom)(sp0256_t *s, int idx) {
    idx &= 0xffff;
    return (idx >= SP0256_ROM_AT && idx < SP0256_ROM_AT + SP0256_ROM_N) ? s->rom[idx - SP0256_ROM_AT] : 0;
}

#include "sp0256_mame.inc"

void sp0256_init(sp0256_t *s, uint8_t *rom) {
    memset(s, 0, sizeof *s);            // MAME's device_start and device_reset
    s->rom = rom;
    s->filt.rng = 1;
    s->filt.rpt = -1;
    s->halted = 1;
    s->lrq = 1;
    s->page = 0x1000 << 3;
    s->silent = 1;
    s->sby_line = 1;
}

bool SP0256_RAM(sp0256_ald)(sp0256_t *s, uint8_t n) {
    if (!s->lrq) {                      // MAME's ald_w: dropped while busy
        return false;
    }
    s->lrq = 0;
    s->ald = n << 4;
    s->sby_line = 0;
    return true;
}

bool SP0256_RAM(sp0256_lrq)(sp0256_t *s) {
    return s->lrq != 0;
}

int16_t SP0256_RAM(sp0256_sample)(sp0256_t *s) {
    // MAME's sound_stream_update, one sample at a time: run the
    // microsequencer when the repeat count runs out, then one sample of the
    // filter, or silence.
    int16_t out = 0;
    uint32_t head = 0;
    if (s->filt.rpt <= 0) {
        sp0256_micro(s);
    }
    if (s->silent && s->filt.rpt <= 0) {
        return 0;
    }
    lpc12_update(&s->filt, 1, &out, &head);
    return out;
}

bool SP0256_RAM(sp0256_idle)(sp0256_t *s) {
    return s->halted && s->lrq && s->filt.rpt <= 0;
}
