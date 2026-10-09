/*
 * TS-Pico v3: RP2350B (QFN80), 12 MHz crystal, GD25Q128E 16 MB QSPI flash.
 * APS6404L PSRAM footprint on QMI CS1 (GP47), not fitted on proto1.
 *
 * The pico-sdk board header. A copy of firmware/bringup/boards/tspico_v3.h in
 * the tspico-hardware repo, which phase 1's bus test was built with; keep the
 * two the same.
 */
#ifndef _BOARDS_TSPICO_V3_H
#define _BOARDS_TSPICO_V3_H

#define TSPICO_V3

// RP2350B: 48 GPIOs
#define PICO_RP2350A 0

#define PICO_BOOT_STAGE2_CHOOSE_W25Q080 1

#ifndef PICO_FLASH_SPI_CLKDIV
#define PICO_FLASH_SPI_CLKDIV 2
#endif

#ifndef PICO_FLASH_SIZE_BYTES
#define PICO_FLASH_SIZE_BYTES (16 * 1024 * 1024)
#endif

#ifndef PICO_XOSC_STARTUP_DELAY_MULTIPLIER
#define PICO_XOSC_STARTUP_DELAY_MULTIPLIER 64
#endif

#ifndef PICO_RP2350_A2_SUPPORTED
#define PICO_RP2350_A2_SUPPORTED 1
#endif

#endif
