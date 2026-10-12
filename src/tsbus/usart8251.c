/*
 * usart8251: the TS2050's Intel 8251A, as the 2068's software sees it. See
 * usart8251.h for who calls what, and the Intel 8251A datasheet (205222-002)
 * for the chip.
 *
 * What is the chip's and what isn't:
 * - The mode byte / command state machine is the datasheet's: after an
 *   internal reset (command bit 6) the next control write is the mode byte,
 *   then every one is a command. A mode byte with baud factor 00 (sync mode,
 *   not supported) is ignored, so the datasheet's reset preamble (00h three
 *   times, then 40h) ends in "expecting a mode byte" from any state. At
 *   power-up the datasheet leaves the chip's state undefined (a mode byte,
 *   a sync character or a command); this one starts taking commands, with
 *   mode 4Fh (8N1, x64) and everything off. So a program that reset the chip
 *   before the modem came up carries on, and the BASIC "Modem" dialer, which
 *   never resets it, has its first OUT 119,31 taken as the off-hook command
 *   it means.
 * - The status bits are the datasheet's status register: TxRDY is "room to
 *   write", whatever CTS or TxEN say; RxRDY is held clear while RxE is off;
 *   TxEMPTY stays set while the transmitter is disabled.
 * - There is no wire: the line is a byte stream (Zimodem, 8N1). The mode
 *   byte only sets the character length, which masks the bytes both ways;
 *   parity, stop bits and PE/FE don't exist. OE is set when the receive
 *   ring overflows, and cleared, as on the chip, by ER or a reset.
 * - Received characters are paced: one becomes RxRDY no sooner than `pace`
 *   after the last, so a program sees a 300-baud line as a 2050 gave it.
 * - What comes and goes on the line, and DSR, are modem2050.c's.
 */
#if U8251_ON_PICO
#include "pico.h"           // __not_in_flash_func: core 1 runs this from RAM
#endif
#include "usart8251.h"

// Program order is enough between the loop and the IN handler: they run on
// the same core, so a compiler barrier keeps the stores in order.
#define BARRIER() __asm volatile ("" ::: "memory")

// Every status bit but RxRDY, which u8251_status adds when it is read.
static void U8251_FN(update_status)(u8251_t *u) {
    uint8_t s = 0;
    if (u->tx_head - u->tx_tail < u->tx_size) {
        s |= U8251_TXRDY;
    }
    if (!(u->cmd & U8251_C_TXEN) || u->tx_head == u->tx_tail) {
        s |= U8251_TXEMPTY;
    }
    if (u->overrun) {
        s |= U8251_OE;
    }
    if (u->dsr) {
        s |= U8251_DSR;
    }
    u->status = s;
}

void u8251_init(u8251_t *u, uint8_t *rx_buf, uint32_t rx_size, uint8_t *tx_buf, uint32_t tx_size) {
    *u = (u8251_t){0};
    u->rx_buf = rx_buf;
    u->rx_size = rx_size;
    u->tx_buf = tx_buf;
    u->tx_size = tx_size;
    u->mode = 0x4f;              // power-up: taking commands, 8N1 (see above)
    u->mask = 0xff;
    update_status(u);
}

void U8251_FN(u8251_control)(u8251_t *u, uint8_t b) {
    if (u->expect_mode) {
        if (b & 0x03) {          // async: x1, x16 or x64
            u->mode = b;
            u->mask = (uint8_t)((1u << (5 + ((b >> 2) & 3))) - 1);
            u->expect_mode = 0;
        }                        // sync mode (00): not supported, ignored
    } else if (b & U8251_C_IR) {
        u->expect_mode = 1;      // internal reset: the next write is a mode byte
        u->cmd = 0;
        u->hold_full = 0;
        u->overrun = 0;
    } else {
        if (b & U8251_C_ER) {
            u->overrun = 0;
        }
        u->cmd = b & (uint8_t)~(U8251_C_ER | U8251_C_IR);
    }
    update_status(u);
}

void U8251_FN(u8251_data_out)(u8251_t *u, uint8_t b) {
    if ((u->cmd & U8251_C_TXEN) && u->tx_head - u->tx_tail < u->tx_size) {
        u->tx_buf[u->tx_head & (u->tx_size - 1)] = b & u->mask;
        u->tx_head++;
        u->tx_chars++;
    } else {
        u->tx_dropped++;
    }
    update_status(u);
}

void U8251_FN(u8251_poll)(u8251_t *u, uint32_t now) {
    uint32_t level = u->rx_head - u->rx_tail;
    if (level > u->rx_size) {                 // the writer lapped us: those are gone
        u->rx_lost += level - u->rx_size;
        u->rx_tail = u->rx_head - u->rx_size;
        u->overrun = 1;
        level = u->rx_size;
    }
    if (!u->hold_full && level && (u->cmd & U8251_C_RXE)
        && (u->pace == 0 || now - u->last_release >= u->pace || u->rx_chars == 0)) {
        u->hold = u->rx_buf[u->rx_tail & (u->rx_size - 1)] & u->mask;
        u->rx_tail++;
        BARRIER();               // the character before the flag
        u->hold_full = 1;
        u->last_release = now;
    }
    update_status(u);
}

uint8_t U8251_FN(u8251_status)(u8251_t *u) {
    uint8_t s = u->status;
    if (u->hold_full && (u->cmd & U8251_C_RXE)) {
        s |= U8251_RXRDY;
    }
    return s;
}

uint8_t U8251_FN(u8251_data_in)(u8251_t *u) {
    uint8_t b = u->hold;
    if (u->hold_full) {
        u->hold_full = 0;
        u->rx_chars++;
    }
    return b;
}
