# Zimodem for the v3 card's modem

The v3 card's ESP32-C3-WROOM-02 runs [Zimodem](https://github.com/bozimmerman/Zimodem)
(Bo Zimmerman's WiFi Hayes modem firmware) as the line behind the TS2050
modem the card emulates at ports 73h/77h
([docs/v3-modem-proposal.md](../../docs/v3-modem-proposal.md)). The modules
come blank; the web updater installs this build through the card's own USB.

- `build.sh` fetches Zimodem at a pinned commit (4.0.3) and patches it:
  - the C3 configuration's unconnected DTR (IO5) and pulse-dial (IO7)
    inputs pull up;
  - a phonebook dial (`ATD1234`) keeps the dial's own modifiers as well as
    the entry's. The card's 2050 mode dials `ATDX1234`, so the call obeys
    XON/XOFF and the card can pause Zimodem when its ring fills (#302);
  - the version becomes **4.0.3.1**, which `ATI` reports, so the updaters
    (which compare four parts) install it over a stock 4.0.3.

  Then it builds it with PlatformIO, and merges the bootloader, partition table,
  `boot_app0` and the app into `out/zimodem-v3.bin`, one image for flash
  address 0. The image ends with the app, so writing it leaves Zimodem's
  SPIFFS, with the user's WiFi settings and phonebook, as it was.
- `platformio.ini`: the ESP32-C3 at 4 MB, `min_spiffs.csv` (two OTA app
  slots and SPIFFS), USB CDC off (the module's USB pins aren't wired), and
  `CORE_DEBUG_LEVEL=0`, so the ESP32 core prints no log lines on UART0: it is
  the 2068's line, and in a call a log line would reach the 2068 as text.

CI: `.github/workflows/zimodem.yml` builds it when this folder changes (the
`tspico-zimodem` artifact), `release.yml` attaches `zimodem-v3.bin` to each
release, and `pages.yml` puts it in the updater channels (`v3.zimodem` in
`manifest.json`).

To build by hand: `pip install platformio`, then `./build.sh`. To flash
through a USB-serial bridge (tspico-hardware's `firmware/bringup`
`esp_bridge.uf2`): `./build.sh upload PORT`.
