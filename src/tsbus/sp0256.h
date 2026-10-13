/*
 * sp0256: the General Instrument SP0256-AL2 speech chip, emulated from its
 * ROM, for the v3 card's speech (docs/v3-speech-proposal.md).
 *
 * The chip itself is MAME's SP0256 core (BSD-3-Clause, Joseph Zbiciak and
 * Tim Lindner), turned into plain C by tools/sp0256-port.py
 * (sp0256_mame.inc); the AL2's ROM is sp0256_al2.inc (Microchip's; see
 * NOTICE). This file and sp0256.c are the interface around them.
 *
 * No hardware here, so the same code runs on core 1 and in a host test
 * (src/test/sp0256_hosttest.py, through ctypes). One sample per call, at the
 * chip's 10 kHz (its 3.12 MHz crystal divided by 312).
 *
 * The chip's own interface: an allophone number is loaded (ALD) while LRQ
 * says it can take one; the chip takes it when it finishes the one it is
 * speaking, and LRQ comes back. So a speaker keeps one allophone queued
 * ahead, as a program on the real chip does.
 */
#ifndef SP0256_H
#define SP0256_H

#include <stdbool.h>
#include <stdint.h>

#ifndef SP0256_RAM
#if U8251_ON_PICO
#include "pico.h"
#define SP0256_RAM(f) __not_in_flash_func(f)   // core 1 never runs from flash
#else
#define SP0256_RAM(f) f
#endif
#endif

#define SP0256_RATE   10000         // samples a second, on a 3.12 MHz crystal
#define SP0256_ROM_AT 0x1000        // where the AL2's ROM sits in the chip's address space
#define SP0256_ROM_N  2048

// Tables core 1 reads: in RAM by name. Without this GCC puts a table that
// nothing writes in .rodata, in flash, even when it isn't const.
#ifndef SP0256_DATA
#if U8251_ON_PICO
#define SP0256_DATA __attribute__((section(".data.sp0256")))
#else
#define SP0256_DATA
#endif
#endif

typedef struct {
    int       rpt, cnt;             // repeat counter, period down-counter
    uint32_t  per, rng;             // period, noise generator
    int       amp;
    int16_t   f_coef[6];
    int16_t   b_coef[6];
    int16_t   z_data[6][2];         // the filter stages' delays
    uint8_t   r[16];                // the encoded register set
    int       interp;
} lpc12_t;

typedef struct {
    uint8_t  *rom;                  // SP0256_ROM_N bytes, MAME's bit order
    int       sby_line;             // standby: nothing to say
    int       silent;
    lpc12_t   filt;                 // the 12-pole filter
    int       lrq;                  // load request: 1 = an allophone can be loaded
    int       ald;                  // the loaded allophone's address
    int       pc;                   // the microsequencer's PC, in bits
    int       stack;
    int       fifo_sel;             // executing from the FIFO (the SPB640's; unused here)
    int       halted;
    uint32_t  mode;
    uint32_t  page;
    uint32_t  fifo_head, fifo_tail, fifo_bitp;
    uint16_t  fifo[64];
} sp0256_t;

// Reset, with the ROM at `rom` (SP0256_ROM_N bytes; sp0256_al2 for the AL2).
void sp0256_init(sp0256_t *s, uint8_t *rom);
// Stop speaking at once: silence from the next sample, ready for an
// allophone. Field stores only, for core 1 (sp0256_init uses memset).
void sp0256_stop(sp0256_t *s);
// Load allophone n (0-63 on the AL2). False if the chip can't take one now
// (LRQ busy): the load is dropped, as the chip drops it.
bool sp0256_ald(sp0256_t *s, uint8_t n);
// The chip can take an allophone (LRQ).
bool sp0256_lrq(sp0256_t *s);
// The next sample: MAME's HIGH_QUALITY limiter (-8192..8191), shifted left
// 2, so -32768..32764. Speech peaks near 6000.
int16_t sp0256_sample(sp0256_t *s);
// Nothing loaded and nothing left to say.
bool sp0256_idle(sp0256_t *s);

extern uint8_t sp0256_al2[SP0256_ROM_N];

#endif
