/*
 * TS-Pico v3: the safe pin state, set before MicroPython starts anything.
 *
 * The same state as board_safe_init() in the bring-up firmware
 * (firmware/bringup/board.c in tspico-hardware): the three local-bus buffers
 * off, the bus requests deasserted, the 2068 left held in reset.
 */

#include "hardware/gpio.h"
#include "mpconfigboard.h"

#define PIN_MD0        0   // MD0-MD7 on GP0-GP7
#define PIN_NAEN_LO    8   // U1 /OE
#define PIN_NAEN_HI    9   // U2 /OE
#define PIN_NDATA_OE   10  // U3 /OE
#define PIN_BE_REQ     11
#define PIN_WAIT_REQ   12
#define PIN_Z80_A14    13  // GP13-GP22: inputs from U4 / U6
#define PIN_TAPE_IN    22
#define PIN_TAPE_OUT   23
#define PIN_RESET_HOLD 29
#define PIN_OLED_DC    34
#define PIN_NIOX_INT   35
#define PIN_SD_CS      37
#define PIN_OLED_CS    41
#define PIN_PSRAM_CS   47

static void out(uint pin, bool v) {
    gpio_init(pin);
    gpio_put(pin, v);
    gpio_set_dir(pin, GPIO_OUT);
}

static void in_nopull(uint pin) {
    gpio_init(pin);
    gpio_disable_pulls(pin);
}

void tspico_v3_safe_init(void) {
    // Local bus buffers off before anything else.
    out(PIN_NAEN_LO, 1);
    out(PIN_NAEN_HI, 1);
    out(PIN_NDATA_OE, 1);
    // No /BE, no /WAIT, tape out idle.
    out(PIN_BE_REQ, 0);
    out(PIN_WAIT_REQ, 0);
    out(PIN_TAPE_OUT, 0);
    // MD: plain inputs. No pulls: MD is only sampled while a buffer drives it,
    // and RP2350 erratum E9 can latch a pad with input and pull-down on.
    for (uint p = PIN_MD0; p < PIN_MD0 + 8; p++) {
        in_nopull(p);
    }
    for (uint p = PIN_Z80_A14; p <= PIN_TAPE_IN; p++) {
        in_nopull(p);
    }
    // RESET_HOLD floats, so R1 holds the 2068 in reset until tsbus lets go.
    in_nopull(PIN_RESET_HOLD);
    // The expander's /INT has its own 10k pull-up.
    in_nopull(PIN_NIOX_INT);
    // PSRAM is not fitted; keep its CS high anyway.
    gpio_init(PIN_PSRAM_CS);
    gpio_pull_up(PIN_PSRAM_CS);
    // SPI chip selects idle high.
    out(PIN_SD_CS, 1);
    out(PIN_OLED_CS, 1);
    out(PIN_OLED_DC, 0);
}
