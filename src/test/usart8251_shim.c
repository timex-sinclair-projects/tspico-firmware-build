/* usart8251_hosttest.py's view of src/tsbus/usart8251.c: one instance, its
 * rings, and accessors, so the test doesn't depend on the struct's layout. */
#include <string.h>
#include "usart8251.h"

static u8251_t u;
static uint8_t rx[64], tx[16];          /* small rings, to reach full quickly */

void shim_init(void) { u8251_init(&u, rx, sizeof rx, tx, sizeof tx); }
void shim_control(int b) { u8251_control(&u, (uint8_t)b); }
void shim_data_out(int b) { u8251_data_out(&u, (uint8_t)b); }
void shim_poll(unsigned now) { u8251_poll(&u, now); }
int shim_status(void) { return u8251_status(&u); }
int shim_data_in(void) { return u8251_data_in(&u); }
void shim_set(unsigned pace, int dsr) { u.pace = pace; u.dsr = (uint8_t)dsr; }
/* the line sends a byte (DMA into the receive ring) */
void shim_line_rx(int b) { rx[u.rx_head & (sizeof rx - 1)] = (uint8_t)b; u.rx_head++; }
/* the line takes a byte from the transmit ring (DMA out); -1 if empty */
int shim_line_tx(void) {
    if (u.tx_tail == u.tx_head) return -1;
    return tx[u.tx_tail++ & (sizeof tx - 1)];
}
int shim_get(const char *k) {
    if (!strcmp(k, "expect_mode")) return u.expect_mode;
    if (!strcmp(k, "mode")) return u.mode;
    if (!strcmp(k, "cmd")) return u.cmd;
    if (!strcmp(k, "mask")) return u.mask;
    if (!strcmp(k, "rx_chars")) return (int)u.rx_chars;
    if (!strcmp(k, "tx_chars")) return (int)u.tx_chars;
    if (!strcmp(k, "tx_dropped")) return (int)u.tx_dropped;
    if (!strcmp(k, "rx_lost")) return (int)u.rx_lost;
    return -999;
}
