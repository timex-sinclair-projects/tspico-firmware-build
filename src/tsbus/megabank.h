/*
 * megabank: the v3 card's shadow of the TS-2068 Megabank's owner table
 * (github.com/timex-sinclair-projects/TS-2068-Megabank, docs/spec.md,
 * "Sharing the bus").
 *
 * The Megabank is a RAM card that answers the memory cycles of any 8K chunk
 * one of its expansion banks owns, pulling /BE. /BE switches off the 2068's
 * own memory but not this card, so the card must stop serving those chunks
 * too, or a DOCK chunk would have two drivers. The card follows the board's
 * register writes the way it follows ports F4h and FFh: OUT (FDh) selects a
 * register, OUT (FCh) writes it, and registers 00h-07h are OWN0-OWN7, the
 * owner of chunk 0-7: an expansion bank 1-253, or 0, FEh or FFh for none.
 * The card yields any chunk owned by a bank 1-253, whichever board (if any)
 * has that bank. With no Megabank nothing writes FDh/FCh and nothing changes.
 *
 * Plain C, so the same file runs on core 1 and in a host test
 * (src/test/megabank_hosttest.py, through ctypes).
 */
#ifndef MEGABANK_H
#define MEGABANK_H

#include <stdint.h>

#ifndef MB_FN
#ifdef __not_in_flash_func
#define MB_FN(f) __not_in_flash_func(f)   // core 1 never runs from flash
#else
#define MB_FN(f) f
#endif
#endif

#define MB_PORT_DATA   0xFC   // reads or writes the selected register
#define MB_PORT_SELECT 0xFD   // selects a register

typedef struct {
    uint8_t select;   // the register the last OUT (FDh) selected
    uint8_t own[8];   // OWN0-OWN7 as last written
    uint8_t owned;    // bit c set: chunk c is owned by an expansion bank 1-253
} mb_shadow_t;

// Power-up or reset: no chunk owned (the board clears its owner table).
void mb_clear(mb_shadow_t *s);

// An OUT the card saw, by the port's low byte. Returns 1 if the owned set
// changed (the chunk table needs rewriting), else 0.
int mb_out(mb_shadow_t *s, unsigned port, unsigned data);

#endif
