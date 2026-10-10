/*
 * TS-Pico v3 pin map, shared by the board's safe start-up (board_init.c) and
 * the tsbus module. From firmware/bringup/board.h in tspico-hardware, which
 * follows the schematic netlist (docs/v3-architecture.md section 7 there).
 */
#ifndef TSPICO_V3_PINS_H
#define TSPICO_V3_PINS_H

#define PIN_MD0        0   // MD0-MD7 on GP0-GP7
#define PIN_NAEN_LO    8   // U1 /OE: A7..A0 onto MD
#define PIN_NAEN_HI    9   // U2 /OE: A15..A8 onto MD
#define PIN_NDATA_OE   10  // U3 /OE: MD onto the Z80's data bus
#define PIN_BE_REQ     11  // /BE through the 74LVC06
#define PIN_WAIT_REQ   12  // /WAIT through the 74LVC06
#define PIN_Z80_A14    13  // GP13-GP22: inputs from U4 / U6
#define PIN_NMEMRD     15  // /MREQ ORed with /RD
#define PIN_NIORD      17  // /IORQ ORed with /RD
#define PIN_NIOWR      18  // /IORQ ORed with /WR
#define PIN_TAPE_IN    22
#define PIN_TAPE_OUT   23
#define PIN_I2C_SDA    24
#define PIN_I2C_SCL    25
#define PIN_RESET_HOLD 29  // high (or floating, R1) holds the 2068 in reset
#define PIN_OLED_DC    34
#define PIN_NIOX_INT   35
#define PIN_SD_CS      37
#define PIN_OLED_CS    41
#define PIN_PSRAM_CS   47

// XL9555 expander on I2C0 (PCA9555 registers). Port 0 outputs, port 1 inputs.
#define IOX_ADDR 0x20
#define IOX_OUT0 2
#define IOX_POL1 5
#define IOX_CFG0 6
#define IOX_CFG1 7
#define X_BUSRQ     (1u << 0)
#define X_NMI_REQ   (1u << 1)
#define X_NOLED_RST (1u << 2)
#define X_WIFI_EN   (1u << 3)
#define X_WIFI_DL   (1u << 4)
#define X_NLED      (1u << 5)
// No bus request, no NMI, OLED in reset, ESP32 off, normal ESP32 boot, LED
// off. Bits 6-7 are spare and stay inputs.
#define IOX_OUT0_SAFE (X_NLED | 0xc0)

#endif
