/*
 * megabank: the v3 card's shadow of the TS-2068 Megabank's owner table.
 * See megabank.h.
 */
#if U8251_ON_PICO
#include "pico.h"           // __not_in_flash_func: core 1 runs this from RAM
#endif
#include "megabank.h"

void MB_FN(mb_clear)(mb_shadow_t *s) {
    for (int c = 0; c < 8; c++) {
        s->own[c] = 0;
    }
    s->select = 0;
    s->owned = 0;
}

int MB_FN(mb_out)(mb_shadow_t *s, unsigned port, unsigned data) {
    if (port == MB_PORT_SELECT) {
        s->select = (uint8_t)data;
        return 0;
    }
    if (port != MB_PORT_DATA || s->select > 7) {
        return 0;   // not the board's, or not an owner register
    }
    unsigned c = s->select;
    s->own[c] = (uint8_t)data;
    uint8_t bit = (uint8_t)(1u << c);
    uint8_t owned = (data >= 1 && data <= 253) ? (s->owned | bit) : (s->owned & ~bit);
    if (owned == s->owned) {
        return 0;
    }
    s->owned = owned;
    return 1;
}
