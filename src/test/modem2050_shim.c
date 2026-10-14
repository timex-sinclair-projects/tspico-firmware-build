/* modem2050_hosttest.py's view of src/tsbus/modem2050.c with the 8251: one
 * of each, small rings, accessors. Time is in ms (tick_ms 1). */
#include <string.h>
#include "modem2050.h"

static u8251_t u;
static m2050_t m;
static uint8_t urx[16], utx[16], lrx[64], ltx[64];

void shim_init(int mode) {
    u8251_init(&u, urx, sizeof urx, utx, sizeof utx);
    m2050_init(&m, (uint8_t)mode, 1, lrx, sizeof lrx, ltx, sizeof ltx);
}
void shim_control(int b) { u8251_control(&u, (uint8_t)b); }
void shim_data_out(int b) { u8251_data_out(&u, (uint8_t)b); }
int shim_status(void) { return u8251_status(&u); }
int shim_data_in(void) { return u8251_data_in(&u); }
/* one core-1 pass: the modem, then the 8251 (no pacing) */
void shim_poll(unsigned now) { m2050_poll(&m, &u, now); u8251_poll(&u, now); }
/* Zimodem sends a byte; -1 if the ring is full */
int shim_line_rx(int b) {
    if (m.lrx_head - m.lrx_tail >= sizeof lrx) return -1;
    lrx[m.lrx_head++ & (sizeof lrx - 1)] = (uint8_t)b;
    return 0;
}
/* Zimodem takes a byte; -1 if none */
int shim_line_tx(void) {
    if (m.ltx_tail == m.ltx_head) return -1;
    return ltx[m.ltx_tail++ & (sizeof ltx - 1)];
}
int shim_get(const char *k) {
    if (!strcmp(k, "state")) return m.state;
    if (!strcmp(k, "dials")) return (int)m.dials;
    if (!strcmp(k, "connects")) return (int)m.connects;
    if (!strcmp(k, "carrier_lost")) return (int)m.carrier_lost;
    if (!strcmp(k, "xoff_sent")) return m.xoff_sent;
    if (!strcmp(k, "lrx_level")) return (int)(m.lrx_head - m.lrx_tail);
    if (!strcmp(k, "flow")) return m.flow;
    return -999;
}
const char *shim_number(void) { return m.number; }
/* tsbus.modem_flow: core 0's request, taken on the next pass */
void shim_flow(int on) { m.flow_want = on ? 1 : 0; }
