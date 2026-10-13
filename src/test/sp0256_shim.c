// A flat interface to one sp0256_t, for sp0256_hosttest.py (ctypes).
#include "sp0256.h"

static sp0256_t chip;

void shim_init(void) { sp0256_init(&chip, sp0256_al2); }
int shim_ald(int n) { return sp0256_ald(&chip, (uint8_t)n); }
int shim_lrq(void) { return sp0256_lrq(&chip); }
int shim_sample(void) { return sp0256_sample(&chip); }
int shim_idle(void) { return sp0256_idle(&chip); }
const uint8_t *shim_rom(void) { return sp0256_al2; }

// Speak `n` allophones as a program on the chip would (each loaded when LRQ
// allows), until the chip is idle: the samples into out (at most max).
// Returns how many.
int shim_say(const int *al, int n, int16_t *out, int max) {
    int next = 0, k = 0;
    sp0256_init(&chip, sp0256_al2);
    while (k < max) {
        if (next < n && sp0256_lrq(&chip)) {
            sp0256_ald(&chip, (uint8_t)al[next++]);
        }
        out[k++] = sp0256_sample(&chip);
        if (next >= n && sp0256_idle(&chip)) {
            break;
        }
    }
    return k;
}
