#!/bin/sh
# Build Zimodem for the TS-Pico v3 card's ESP32-C3 (the TS2050 modem,
# docs/v3-modem-proposal.md). Needs PlatformIO (pip install platformio).
#
#   ./build.sh                 build, and write out/zimodem-v3.bin
#   ./build.sh upload PORT     build and flash through a USB-serial bridge
#
# out/zimodem-v3.bin is the bootloader, partition table, boot_app0 and the
# app merged into one image for flash address 0. It ends with the app, so
# writing it leaves Zimodem's SPIFFS (its WiFi settings and phonebook) as it
# was. CI (.github/workflows/zimodem.yml, release.yml) builds the same file;
# the web updater installs it through the card's own USB.
set -e
cd "$(dirname "$0")"

ZIMODEM_REPO=https://github.com/bozimmerman/Zimodem.git
ZIMODEM_REV=a24225cc1b6c219e6c0764a4e6b1a388356a1dd5   # 4.0.3, 2026-08-30
ZIMODEM_VERSION=4.0.3.1   # ours: 4.0.3 with the patches below (ATI says it)

[ -d Zimodem/.git ] || git clone -q "$ZIMODEM_REPO" Zimodem
git -C Zimodem cat-file -e "$ZIMODEM_REV^{commit}" 2>/dev/null || git -C Zimodem fetch -q origin
git -C Zimodem checkout -q --force "$ZIMODEM_REV"

# The C3 configuration reads DTR on IO5 and the pulse-dial line on IO7, which
# are unconnected on this card. Pull them up (inactive) so a floating input
# cannot hang up a connection.
perl -pi -e 's/pinMode\(pinDTR,INPUT\)/pinMode(pinDTR,INPUT_PULLUP)/; s/pinMode\(pinOTH,INPUT\)/pinMode(pinOTH,INPUT_PULLUP)/' \
    Zimodem/zimodem/zcommand.ino
grep -q 'pinMode(pinDTR,INPUT_PULLUP)' Zimodem/zimodem/zcommand.ino \
    || { echo "build.sh: the IO5/IO7 pull-up patch didn't apply" >&2; exit 1; }

# A phonebook dial (ATD<number>) uses only the modifiers saved with the entry
# and drops the dial's own. Add them: the card's 2050 mode dials ATDX<number>
# so the call obeys XON/XOFF (X is a connection's own flag; ATF1 sets only the
# serial side), which the card needs to pause Zimodem when its ring fills
# (#302). On a stock Zimodem the X is ignored, as before.
perl -pi -e 's/ZResult res = doDialStreamCommand\(0,vbuf,addrLen,false,phb->modifiers\);/String mods = String(phb->modifiers) + dmodifiers; ZResult res = doDialStreamCommand(0,vbuf,addrLen,false,mods.c_str());/' \
    Zimodem/zimodem/zcommand.ino
grep -q 'String mods = String(phb->modifiers) + dmodifiers;' Zimodem/zimodem/zcommand.ino \
    || { echo "build.sh: the phonebook-modifiers patch didn't apply" >&2; exit 1; }

# The version ATI reports, so the updaters can tell this build from 4.0.3.
perl -pi -e "s/#define ZIMODEM_VERSION \"4\.0\.3\"/#define ZIMODEM_VERSION \"$ZIMODEM_VERSION\"/" Zimodem/zimodem/zimodem.ino
grep -q "#define ZIMODEM_VERSION \"$ZIMODEM_VERSION\"" Zimodem/zimodem/zimodem.ino \
    || { echo "build.sh: the version patch didn't apply" >&2; exit 1; }

if [ "$1" = upload ]; then
    pio run -t upload --upload-port "${2:?usage: build.sh upload PORT}"
    exit 0
fi
pio run
B=.pio/build/tspico_c3
ESPTOOL="${ESPTOOL:-$(ls "$HOME"/.platformio/packages/tool-esptoolpy/esptool.py 2>/dev/null)}"
[ -n "$ESPTOOL" ] || { echo "build.sh: esptool.py not found; set ESPTOOL" >&2; exit 1; }
BOOT_APP0="$(ls "$HOME"/.platformio/packages/framework-arduinoespressif32/tools/partitions/boot_app0.bin)"
mkdir -p out
python3 "$ESPTOOL" --chip esp32c3 merge_bin -o out/zimodem-v3.bin \
    --flash_mode dio --flash_freq 80m --flash_size 4MB \
    0x0 "$B/bootloader.bin" 0x8000 "$B/partitions.bin" 0xe000 "$BOOT_APP0" 0x10000 "$B/firmware.bin"
echo "$ZIMODEM_VERSION" > out/zimodem-v3.version
ls -l out/zimodem-v3.bin
