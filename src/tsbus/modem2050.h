/*
 * modem2050: what stands between the 8251 (usart8251.c) and the line, the
 * ESP32-C3 running Zimodem (docs/v3-modem-proposal.md).
 *
 * Two modes:
 * - Hayes: every byte both ways, DSR held at 1, so a program talks to
 *   Zimodem directly.
 * - 2050: Zimodem made to look like a Timex TS2050 to unmodified software
 *   (MTERM, the BASIC dialers; docs/ts2050-software-notes.md). DTR is the
 *   hook: pulses on it dial a number, sent to Zimodem as ATD<number> (its
 *   phonebook maps the number to a host); Zimodem's result lines are read
 *   here and never reach the 2068; DSR is the connection.
 *
 * Plain C with no hardware, like usart8251.c: core 1 calls m2050_poll once a
 * loop pass (never from the IN handler), and src/test/modem2050_hosttest.py
 * drives it through ctypes. It moves at most M2050_BURST bytes each way a
 * pass, so a pass stays short.
 *
 * The rings: the line's (lrx written by DMA, the caller advancing lrx_head;
 * ltx read by DMA, the caller advancing ltx_tail) and the 8251's (this
 * advances usart's rx_head and tx_tail, as usart8251.h's "caller").
 */
#ifndef MODEM2050_H
#define MODEM2050_H

#include <stdint.h>
#include "usart8251.h"

#define M2050_HAYES 0
#define M2050_2050  1

// 2050 mode's states.
#define M2050_ONHOOK    0   // DTR off: idle, DSR 0
#define M2050_OFFHOOK   1   // DTR on: counting dial pulses
#define M2050_DIALING   2   // ATD sent, waiting for Zimodem's result
#define M2050_CONNECTED 3   // DSR 1: data both ways
#define M2050_DEAD      4   // the call failed or the far end went: DSR 0 until on-hook
#define M2050_HANGUP    5   // on-hook from connected: +++ and ATH under way

// Times, in ms (MTERM's own, at 3.528 MHz: break 58 ms, make 47.5 ms,
// 832 ms between digits; the notes, section 2.8).
#define M2050_BREAK_MAX_MS  200    // a DTR break shorter than this is a dial pulse
#define M2050_DIGIT_MS      300    // DTR on this long after pulses ends a digit
#define M2050_NUMBER_MS     1500   // ... and this long ends the number
#define M2050_ONHOOK_MS     400    // DTR off this long is on-hook
#define M2050_GUARD_MS      1100   // Zimodem's +++ guard time is over 900 ms
#define M2050_SETTLE_MS     3500   // data held back after CONNECT (MTERM/T reads none for about 2.8 s)

#define M2050_BURST 16             // bytes moved each way a pass, at most

typedef struct {
    // Set by m2050_init.
    uint8_t mode;
    uint32_t tick_ms;              // ticks of `now` in a millisecond

    // The line's rings.
    uint8_t *lrx;
    uint32_t lrx_size, lrx_head, lrx_tail;    // lrx_head: the caller's
    uint8_t *ltx;
    uint32_t ltx_size, ltx_head, ltx_tail;    // ltx_tail: the caller's

    // 2050 mode.
    volatile uint8_t state;
    uint8_t dtr;                   // DTR as last seen
    uint32_t dtr_at;               // when it last changed
    uint8_t pulses;                // in the digit being dialled
    char number[24];               // the digits so far
    uint8_t ndigits;
    char line[24];                 // a result line being read
    uint8_t nline;
    uint8_t match;                 // characters of "NO CARRIER" held back
    uint8_t swallow_lf;            // the LF after CONNECT's CR
    uint32_t connected_at;         // when CONNECT came
    uint8_t hang_phase;
    uint32_t hang_at, last_tx_at;
    uint8_t xoff_sent;

    // Hayes mode's flow control: off unless the program turns it on
    // (tsbus.modem_flow, after sending Zimodem ATF1). flow_want is core 0's
    // request; m2050_poll copies it into flow on core 1.
    volatile uint8_t flow_want;
    uint8_t flow;

    // Counters.
    uint32_t dials, connects, carrier_lost, rx_lost;
} m2050_t;

void m2050_init(m2050_t *m, uint8_t mode, uint32_t tick_ms,
    uint8_t *lrx, uint32_t lrx_size, uint8_t *ltx, uint32_t ltx_size);
void m2050_poll(m2050_t *m, u8251_t *u, uint32_t now);

#endif
