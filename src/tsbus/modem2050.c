/*
 * modem2050: the TS2050's line, made of Zimodem. See modem2050.h.
 *
 * 2050 mode, step by step (the notes' section 2 for MTERM's side):
 * - DTR on from on-hook: off-hook. Zimodem gets ATE0V1X0F1 (no echo, word
 *   results, short CONNECT, XON/XOFF), so its results are known lines.
 * - A DTR break under M2050_BREAK_MAX_MS, then DTR back: one pulse. DTR on
 *   for M2050_DIGIT_MS after pulses: a digit (10 pulses are 0). On for
 *   M2050_NUMBER_MS after the last digit: ATDX<number>, dialing.
 * - Dialing, Zimodem's result line: CONNECT... connects (DSR 1); NO
 *   CARRIER, NO ANSWER, ERROR, BUSY or NO DIALTONE: dead (DSR stays 0).
 * - Connected: DSR at once, but the data held back for M2050_SETTLE_MS:
 *   Zimodem connects in milliseconds and a host's banner follows at once,
 *   while MTERM/T qualifies the carrier (1.84 s), redraws its screen, and
 *   drops what it reads meanwhile. On proto1 (2026-10-12) the banner never
 *   showed with no hold; with 2 s its first 25 characters (0.8 s at 300
 *   baud) were still lost, so about 2.8 s in all. 3.5 s leaves a margin.
 * - Then data both ways, except "NO CARRIER" followed by CR or LF, anywhere
 *   in a line: Zimodem printed it straight after a host's "> " prompt, with
 *   no line break before it (proto1). It is held back as it arrives and,
 *   with its line ending, is the far end gone (dead). Anything that only
 *   starts like it is passed on. So a host that sends the words NO CARRIER
 *   and a line ending ends the call: a fair price.
 * - DTR off for M2050_ONHOOK_MS: on-hook. From connected, Zimodem's escape:
 *   M2050_GUARD_MS with nothing sent, "+++", the guard again, then ATH.
 *   From dialing, ATH at once.
 * - DSR is 1 only while connected, and steady otherwise: MTERM counts DSR
 *   changes while on-hook as rings, and answers after four.
 * While not connected the 2068's bytes are dropped (MTERM sends nothing
 * on-hook anyway) and Zimodem's are read here.
 */
#if U8251_ON_PICO
#include "pico.h"           // __not_in_flash_func: core 1 runs this from RAM
#endif
#include "modem2050.h"

// Not const: const data goes to flash (.rodata), and core 1 must never read
// flash, which stalls while core 0 writes it (#254). These are copied to RAM
// at start-up (.data). For the same reason nothing here may become a call to
// strlen or memcpy, which the compiler makes of simple loops and which are
// in flash: put_line is given its length (STR), and every copy goes through
// a ring's masked index, which isn't a memcpy. Check the disassembly after a
// change (docs/reference/firmware/tsbus.md, "Placement").
static char no_carrier[] = "NO CARRIER";
#define NO_CARRIER_LEN 10
static char s_init[] = "ATE0V1X0F1\r";
static char s_ath[] = "ATH\r";
static char s_plus[] = "+++";
static char r_connect[] = "CONNECT";
static char r_answer[] = "NO ANSWER";
static char r_error[] = "ERROR";
static char r_busy[] = "BUSY";
static char r_dialtone[] = "NO DIALTONE";
// Volatile as well: gcc moves a static array that nothing writes or passes
// on into .rodata (flash) even when it isn't const, and this one is only
// read here (checked with arm-none-eabi-objdump -t: .data).
static volatile char s_ready[] = "READY.";
#define STR(s) (s), (sizeof (s) - 1)

static uint32_t U8251_FN(ms)(m2050_t *m, uint32_t n) {
    return n * m->tick_ms;
}

static int U8251_FN(starts)(const char *s, const char *p) {   // s begins with p
    while (*p) {
        if (*s++ != *p++) {
            return 0;
        }
    }
    return 1;
}

// n bytes for Zimodem, if there is room for all of them.
static void U8251_FN(put_line)(m2050_t *m, const char *s, uint32_t n, uint32_t now) {
    if (m->ltx_size - (m->ltx_head - m->ltx_tail) < n) {
        return;
    }
    for (uint32_t i = 0; i < n; i++) {
        m->ltx[m->ltx_head++ & (m->ltx_size - 1)] = (uint8_t)s[i];
    }
    m->last_tx_at = now;
}

static void U8251_FN(put_byte)(m2050_t *m, uint8_t b, uint32_t now) {
    if (m->ltx_head - m->ltx_tail < m->ltx_size) {
        m->ltx[m->ltx_head++ & (m->ltx_size - 1)] = b;
        m->last_tx_at = now;
    }
}

// A byte for the 2068 (the 8251's receive ring has room: checked by the caller).
static void U8251_FN(to_2068)(u8251_t *u, uint8_t b) {
    u->rx_buf[u->rx_head & (u->rx_size - 1)] = b;
    u->rx_head++;
}

void m2050_init(m2050_t *m, uint8_t mode, uint32_t tick_ms,
    uint8_t *lrx, uint32_t lrx_size, uint8_t *ltx, uint32_t ltx_size) {
    *m = (m2050_t){0};
    m->mode = mode;
    m->tick_ms = tick_ms;
    m->lrx = lrx;
    m->lrx_size = lrx_size;
    m->ltx = ltx;
    m->ltx_size = ltx_size;
    m->state = M2050_ONHOOK;
}

static void U8251_FN(go_onhook)(m2050_t *m, uint32_t now) {
    if (m->state == M2050_CONNECTED) {
        m->state = M2050_HANGUP;          // the escape, then ATH (m2050_poll)
        m->hang_phase = 0;
        if (m->xoff_sent) {
            put_byte(m, U8251_XON, now);  // don't leave Zimodem stopped
            m->xoff_sent = 0;
        }
        return;
    }
    if (m->state == M2050_DIALING) {
        put_line(m, STR(s_ath), now);        // a character aborts the dial; ATH makes sure
    }
    m->state = M2050_ONHOOK;
}

// DTR, in 2050 mode: the hook and the dial.
static void U8251_FN(follow_dtr)(m2050_t *m, u8251_t *u, uint32_t now) {
    uint8_t d = (u->cmd & U8251_C_DTR) ? 1 : 0;
    if (d != m->dtr) {
        uint32_t was = now - m->dtr_at;  // how long the old level lasted
        m->dtr = d;
        m->dtr_at = now;
        if (d) {
            if (m->state == M2050_ONHOOK) {
                m->state = M2050_OFFHOOK;
                m->pulses = 0;
                m->ndigits = 0;
                put_line(m, STR(s_init), now);
            } else if (m->state == M2050_OFFHOOK && was < ms(m, M2050_BREAK_MAX_MS)) {
                m->pulses++;
            }
        }
        return;
    }
    uint32_t held = now - m->dtr_at;
    if (!d) {
        if (m->state != M2050_ONHOOK && m->state != M2050_HANGUP && held > ms(m, M2050_ONHOOK_MS)) {
            go_onhook(m, now);
        }
        return;
    }
    if (m->state != M2050_OFFHOOK) {
        return;
    }
    if (m->pulses && held > ms(m, M2050_DIGIT_MS)) {
        if (m->pulses <= 10 && m->ndigits < sizeof m->number - 1) {
            m->number[m->ndigits++] = (char)('0' + m->pulses % 10);
        }
        m->pulses = 0;
    }
    if (!m->pulses && m->ndigits && held > ms(m, M2050_NUMBER_MS)) {
        if (m->ltx_size - (m->ltx_head - m->ltx_tail) < m->ndigits + 5u) {
            return;                       // the line is full: next pass
        }
        put_byte(m, 'A', now);            // ATDX<number>, a byte at a time (see above).
        put_byte(m, 'T', now);            // X: the call obeys the XOFF/XON below; our
        put_byte(m, 'D', now);            // Zimodem adds it to the phonebook entry's
        put_byte(m, 'X', now);            // modifiers, stock 4.0.3 ignores it (#302)
        for (uint32_t i = 0; i < m->ndigits; i++) {
            put_byte(m, (uint8_t)m->number[i], now);
        }
        put_byte(m, '\r', now);
        m->number[m->ndigits] = 0;
        m->state = M2050_DIALING;
        m->nline = 0;
        m->dials++;
    }
}

// A byte from Zimodem while not connected: result lines.
static void U8251_FN(read_result)(m2050_t *m, uint8_t c, uint32_t now) {
    if (c == '\r' || c == '\n') {
        if (m->nline && m->state == M2050_DIALING) {
            m->line[m->nline] = 0;
            if (starts(m->line, r_connect)) {
                m->state = M2050_CONNECTED;
                m->connects++;
                m->match = 0;
                m->swallow_lf = (c == '\r');
                m->connected_at = now;
            } else if (starts(m->line, no_carrier) || starts(m->line, r_answer)
                       || starts(m->line, r_error) || starts(m->line, r_busy)
                       || starts(m->line, r_dialtone)) {
                m->state = M2050_DEAD;
            }
        }
        m->nline = 0;
    } else if (m->nline < sizeof m->line - 1) {
        m->line[m->nline++] = (char)c;
    }
}

// A byte from Zimodem while connected: data, but for NO CARRIER.
static void U8251_FN(read_data)(m2050_t *m, u8251_t *u, uint8_t c) {
    if (m->swallow_lf) {
        m->swallow_lf = 0;
        if (c == '\n') {
            return;
        }
    }
    if (m->match < NO_CARRIER_LEN && c == (uint8_t)no_carrier[m->match]) {
        m->match++;                       // held back
        return;
    }
    if (m->match == NO_CARRIER_LEN && (c == '\r' || c == '\n')) {
        m->state = M2050_DEAD;            // the far end hung up
        m->carrier_lost++;
        m->match = 0;
        return;
    }
    for (uint32_t i = 0; i < m->match; i++) {
        to_2068(u, (uint8_t)no_carrier[i]); // a false start: what was held back
    }
    m->match = 0;
    if (c == (uint8_t)no_carrier[0]) {
        m->match = 1;                     // a new start
        return;
    }
    to_2068(u, c);
}

// While the line is down (Zimodem powered but not yet heard from), what has
// arrived is dropped, but looked through for the "READY." that ends
// Zimodem's start-up message (showInitMessage, after it has tried its
// WiFi): 1 when it has come, lrx_tail just after it, so what follows is
// kept (m2050_poll drops the line ending); else 0, everything dropped. So
// the line comes up the moment Zimodem listens, however long its WiFi join
// takes (#300).
int U8251_FN(m2050_wait_ready)(m2050_t *m) {
    while (m->lrx_tail != m->lrx_head) {
        char c = (char)m->lrx[m->lrx_tail++ & (m->lrx_size - 1)];
        if (c == s_ready[m->ready_match]) {
            if (++m->ready_match == sizeof s_ready - 1) {
                m->ready_match = 0;
                m->eol_swallow = 2;
                return 1;
            }
        } else {
            m->ready_match = c == s_ready[0];
        }
    }
    return 0;
}

void U8251_FN(m2050_poll)(m2050_t *m, u8251_t *u, uint32_t now) {
    uint32_t level = m->lrx_head - m->lrx_tail;
    if (level > m->lrx_size) {            // DMA lapped us: those are gone
        m->rx_lost += level - m->lrx_size;
        m->lrx_tail = m->lrx_head - m->lrx_size;
        u->overrun = 1;
    }
    // The line ending after Zimodem's READY. (m2050_wait_ready): dropped,
    // so a program's screen doesn't start with a blank line.
    while (m->eol_swallow && m->lrx_tail != m->lrx_head) {
        uint8_t c = m->lrx[m->lrx_tail & (m->lrx_size - 1)];
        if (c != '\r' && c != '\n') {
            m->eol_swallow = 0;
            break;
        }
        m->lrx_tail++;
        m->eol_swallow--;
    }
    int hayes = m->mode == M2050_HAYES;
    if (!hayes) {
        follow_dtr(m, u, now);
    }

    // Zimodem -> the 2068 (or the result reader). The 8251's ring must have
    // room for a held-back "NO CARRIER" and the byte after it.
    for (int n = 0; n < M2050_BURST && m->lrx_tail != m->lrx_head; n++) {
        if (u->rx_size - (u->rx_head - u->rx_tail) < NO_CARRIER_LEN + 1) {
            break;
        }
        if (!hayes && m->state == M2050_CONNECTED
            && now - m->connected_at < ms(m, M2050_SETTLE_MS)) {
            break;                        // CONNECT came less than M2050_SETTLE_MS ago
        }
        uint8_t c = m->lrx[m->lrx_tail++ & (m->lrx_size - 1)];
        if (hayes) {
            to_2068(u, c);
        } else if (m->state == M2050_CONNECTED) {
            read_data(m, u, c);
        } else {
            read_result(m, c, now);
        }
    }

    // The 2068 -> Zimodem: in Hayes mode always, in 2050 mode only while
    // connected; otherwise dropped, so TxRDY stays up.
    int pass = hayes || m->state == M2050_CONNECTED;
    for (int n = 0; n < M2050_BURST && u->tx_tail != u->tx_head; n++) {
        if (pass && m->ltx_head - m->ltx_tail >= m->ltx_size) {
            break;                        // the line is full: wait
        }
        uint8_t c = u->tx_buf[u->tx_tail++ & (u->tx_size - 1)];
        if (pass) {
            put_byte(m, c, now);
        }
    }

    // Flow control toward Zimodem: in 2050 mode while connected (ATF1 is in
    // its init, and it dials ATDX, which our Zimodem 4.0.3.1 keeps on a
    // phonebook dial); in Hayes mode only when the program has turned it on
    // (flow_want, tsbus.modem_flow) and set Zimodem up for it itself. Zimodem
    // obeys XOFF only with ATF1 and on a connection dialled with X (ATDTX);
    // otherwise XOFF and XON reach the host as data (#301, #302). Turning it
    // off in Hayes mode while Zimodem is stopped sends XON first.
    if (m->flow != m->flow_want) {
        if (hayes && !m->flow_want && m->xoff_sent) {
            put_byte(m, U8251_XON, now);
            m->xoff_sent = 0;
        }
        m->flow = m->flow_want;
    }
    if (hayes ? m->flow : m->state == M2050_CONNECTED) {
        level = m->lrx_head - m->lrx_tail;
        if (!m->xoff_sent && level > m->lrx_size / 2) {
            put_byte(m, U8251_XOFF, now);
            m->xoff_sent = 1;
        } else if (m->xoff_sent && level < m->lrx_size / 4) {
            put_byte(m, U8251_XON, now);
            m->xoff_sent = 0;
        }
    }

    // On-hook from connected: the guard, +++, the guard, ATH.
    if (m->state == M2050_HANGUP) {
        if (m->hang_phase == 0) {
            if (m->ltx_tail == m->ltx_head && now - m->last_tx_at > ms(m, M2050_GUARD_MS)) {
                put_line(m, STR(s_plus), now);
                m->hang_at = now;
                m->hang_phase = 1;
            }
        } else if (now - m->hang_at > ms(m, M2050_GUARD_MS + 100)) {
            put_line(m, STR(s_ath), now);
            m->state = M2050_ONHOOK;
            if (m->dtr) {                 // off-hook again already: a redial
                m->state = M2050_OFFHOOK;
                m->pulses = 0;
                m->ndigits = 0;
                put_line(m, STR(s_init), now);
            }
        }
    }

    u->dsr = (uint8_t)(hayes || m->state == M2050_CONNECTED);
}
