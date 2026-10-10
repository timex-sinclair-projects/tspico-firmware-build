/*
 * TS-Pico v3: the safe pin state, set before MicroPython starts anything.
 *
 * The same state as board_safe_init() in the bring-up firmware
 * (firmware/bringup/board.c in tspico-hardware): the three local-bus buffers
 * off, the bus requests deasserted, the 2068 left held in reset, and the
 * expander's outputs at their safe values.
 */

#include "hardware/gpio.h"
#include "hardware/i2c.h"
#include "mpconfigboard.h"
#include "tspico_v3_pins.h"

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
    // The SD socket: nothing drives it until the firmware has seen a card
    // on the detect switch (board_v3.sd_card_ready). A driven line can power
    // a card through its I/O pins before its VDD contact makes. Plain
    // inputs: R34 holds CS high (the card deselected), R35 holds MISO, SCK
    // and MOSI float behind their 33R. No pulls (E9, above).
    in_nopull(PIN_SD_CS);
    in_nopull(PIN_SD_SCK);
    in_nopull(PIN_SD_MOSI);
    in_nopull(PIN_SD_MISO);
    // The OLED's chip select idles high.
    out(PIN_OLED_CS, 1);
    out(PIN_OLED_DC, 0);

    // The XL9555's port 0 drives /BUSRQ and /NMI (through the 74LVC06), the
    // OLED reset, the ESP32's EN and IO9, and the LED. It powers up as inputs
    // with output register FFh. Output register first, then direction, so the
    // outputs come up safe (as iox_init() in the bring-up). If the expander
    // does not answer, carry on: the request lines are pulled low on the board.
    i2c_init(i2c0, 400 * 1000);
    gpio_set_function(PIN_I2C_SDA, GPIO_FUNC_I2C);
    gpio_set_function(PIN_I2C_SCL, GPIO_FUNC_I2C);
    gpio_disable_pulls(PIN_I2C_SDA);    // R6/R7 are the pull-ups
    gpio_disable_pulls(PIN_I2C_SCL);
    const uint8_t regs[][2] = {
        {IOX_OUT0, IOX_OUT0_SAFE}, {IOX_POL1, 0x00}, {IOX_CFG1, 0xff}, {IOX_CFG0, 0xc0},
    };
    for (unsigned i = 0; i < sizeof regs / sizeof regs[0]; i++) {
        if (i2c_write_timeout_us(i2c0, IOX_ADDR, regs[i], 2, false, 10000) != 2) {
            break;
        }
    }
}
