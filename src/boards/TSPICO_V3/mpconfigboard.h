// TS-Pico v3 (proto1). Pin map: firmware/bringup/board.h in tspico-hardware,
// docs/v3-architecture.md section 7 there.

#define MICROPY_HW_BOARD_NAME "TS-Pico v3"

// U22 (APS6404L) is not fitted on proto1: images live in SRAM.
#define MICROPY_HW_ENABLE_PSRAM (0)

// Default pins for the peripherals, set to what each is wired to on the
// board. The port's defaults (UART0 on GP0/1, UART1 GP4/5, I2C1 GP6/7, SPI1
// GP8-11) would put a peripheral created without pins on MD0-MD7 or the
// buffer enables.
#define MICROPY_HW_UART0_TX  (44)   // ESP32-C3
#define MICROPY_HW_UART0_RX  (45)
#define MICROPY_HW_UART0_CTS (-1)
#define MICROPY_HW_UART0_RTS (-1)
#define MICROPY_HW_UART1_TX  (36)   // spare pad; nothing on the board
#define MICROPY_HW_UART1_RX  (41)   // OLED_CS: pass pins to use UART1
#define MICROPY_HW_UART1_CTS (-1)
#define MICROPY_HW_UART1_RTS (-1)

#define MICROPY_HW_I2C0_SCL  (25)   // XL9555 expander
#define MICROPY_HW_I2C0_SDA  (24)
#define MICROPY_HW_I2C1_SCL  (43)   // J3, for an I2C OLED
#define MICROPY_HW_I2C1_SDA  (42)

#define MICROPY_HW_SPI0_SCK  (38)   // microSD
#define MICROPY_HW_SPI0_MOSI (39)
#define MICROPY_HW_SPI0_MISO (32)
#define MICROPY_HW_SPI1_SCK  (42)   // J3, SPI OLED (write-only)
#define MICROPY_HW_SPI1_MOSI (43)
#define MICROPY_HW_SPI1_MISO (40)   // spare pad

// The local-bus buffers' enables (GP8-GP10) have no pull-ups and the pads
// reset with pull-downs, so the buffers are on until firmware turns them off.
// This runs right after the clock is set, before anything else touches a pin.
void tspico_v3_safe_init(void);
#define MICROPY_BOARD_STARTUP() tspico_v3_safe_init()
