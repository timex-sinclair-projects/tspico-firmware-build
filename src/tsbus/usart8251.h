/*
 * usart8251: the Intel 8251A the Timex TS2050 modem put at ports 73h (data)
 * and 77h (status, mode and command), as the 2068's software drives it
 * (docs/v3-modem-proposal.md, docs/ts2050-software-notes.md).
 *
 * No hardware here, so the same file runs on core 1 and in a host test
 * (src/test/usart8251_hosttest.py, through ctypes). The caller owns the two
 * rings' storage and the time: `now` is any free-running 32-bit counter,
 * core 1's cycle counter on the card.
 *
 * Who calls what, on the card:
 *   u8251_status, u8251_data_in   core 1's IN handler (an interrupt)
 *   u8251_control, u8251_data_out core 1's loop, for OUTs (io_snoop)
 *   u8251_poll                    core 1's loop, every pass
 * No locks: the IN handler interrupts the loop on the same core, and masking
 * it (hardware, 2026-10-12) made INs late, read as a floating bus. What the
 * two share is only the received character: the loop sets `hold`, then
 * `hold_full`, and only while it is clear; the handler clears it, only
 * while it is set. RxRDY is worked out from it when 77h is read, never kept,
 * so a status byte can't lag a read. The rest of `status` is the loop's.
 */
#ifndef USART8251_H
#define USART8251_H

#include <stdint.h>

#ifndef U8251_FN
#ifdef __not_in_flash_func
#define U8251_FN(f) __not_in_flash_func(f)   // core 1 never runs from flash
#else
#define U8251_FN(f) f
#endif
#endif

// Status bits (IN 77h).
#define U8251_TXRDY   0x01
#define U8251_RXRDY   0x02
#define U8251_TXEMPTY 0x04
#define U8251_PE      0x08
#define U8251_OE      0x10
#define U8251_FE      0x20
#define U8251_BRKDET  0x40
#define U8251_DSR     0x80

// Command bits (OUT 77h after the mode byte).
#define U8251_C_TXEN  0x01
#define U8251_C_DTR   0x02
#define U8251_C_RXE   0x04
#define U8251_C_SBRK  0x08
#define U8251_C_ER    0x10
#define U8251_C_RTS   0x20
#define U8251_C_IR    0x40
#define U8251_C_EH    0x80

#define U8251_XON  0x11
#define U8251_XOFF 0x13

typedef struct {
    // Set by the caller.
    uint32_t pace;          // ticks of `now` between received characters; 0: none
    uint8_t dsr;            // what status bit 7 shows (Hayes mode: 1)
    uint8_t flow;           // send XOFF/XON to the line as the receive ring fills/drains

    // The chip.
    uint8_t expect_mode;    // the next control write is a mode byte (after any reset)
    uint8_t mode;           // the last mode byte
    volatile uint8_t cmd;   // the last command, less ER and IR
    uint8_t mask;           // the character length's bits: 1Fh .. FFh
    volatile uint8_t hold;      // the received character IN 73h returns
    volatile uint8_t hold_full; // ... is there: RxRDY (with RxE)
    uint8_t overrun;        // OE: the receive ring overflowed
    volatile uint8_t status;// IN 77h's bits but RxRDY, kept current by every loop call

    // Receive ring: the line's bytes, written by DMA on the card. The caller
    // advances rx_head; rx_tail is ours. rx_size is a power of two.
    uint8_t *rx_buf;
    uint32_t rx_size;
    uint32_t rx_head, rx_tail;
    uint32_t last_release;  // `now` when the last character became RxRDY
    uint8_t xoff_sent;

    // Transmit ring: the 2068's bytes for the line. tx_head is ours; the
    // caller advances tx_tail as they go out. tx_size is a power of two.
    uint8_t *tx_buf;
    uint32_t tx_size;
    uint32_t tx_head, tx_tail;

    // Counters.
    volatile uint32_t rx_chars; // characters the 2068 read (the IN handler counts)
    uint32_t tx_chars;      // characters it wrote that went into the ring
    uint32_t tx_dropped;    // writes with TxEN off or the ring full
    uint32_t rx_lost;       // bytes lost to a full receive ring
} u8251_t;

void u8251_init(u8251_t *u, uint8_t *rx_buf, uint32_t rx_size, uint8_t *tx_buf, uint32_t tx_size);
void u8251_control(u8251_t *u, uint8_t b);
void u8251_data_out(u8251_t *u, uint8_t b);
void u8251_poll(u8251_t *u, uint32_t now);
uint8_t u8251_status(u8251_t *u);
uint8_t u8251_data_in(u8251_t *u);

#endif
