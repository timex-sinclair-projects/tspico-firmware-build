"""Generate a small TAP file for LOAD/VERIFY/SAVE testing.

Program contents:
    10 PRINT "test"
    20 GO TO 10

The program is set to NOT auto-run (HDVARS high byte = 0x80) so after
LOAD the TS-2068 sits at the BASIC ready prompt with the program in
memory but not executing — perfect for VERIFY testing.

Run from the repo root:
    python3 test/make_test_tap.py

Output: test/test.tap (45 bytes total). Copy to SD card as /TAP/test.tap
or wherever your test harness expects it.

TAP file structure (one block per line below):
    [len_lo][len_hi]  — 16-bit length of next block (LE)
    [type=0x00][...header content (17 bytes)...][CRC]    ← header block
    [len_lo][len_hi]  — 16-bit length of next block (LE)
    [type=0xFF][...program bytes...][CRC]                ← data block

Header content layout (17 bytes after type byte, per ZX Spectrum spec):
    [0]    HDTYPE         (0x00 = BASIC PROGRAM)
    [1-10] filename       (10 ASCII chars, space-padded)
    [11,12] BLEN          (LE 16-bit) data block size in bytes
    [13,14] PARAM1        (LE 16-bit) for BASIC: autorun line number
                          (>= 0x8000 means NO autorun)
    [15,16] PARAM2        (LE 16-bit) for BASIC: variable area offset
                          (= BLEN means no variables)

CRC byte is XOR of all preceding block bytes (block_type + content).
This is the *standard ZX TAP CRC* — no session-ID skipping (those are
TPI-protocol-specific additions during SAVE, not part of the TAP file).
"""

import struct


# ----------------------------------------------------------------------------
# Encode the BASIC program
# ----------------------------------------------------------------------------
# ZX Spectrum BASIC program format (per line):
#     [line_hi][line_lo]    — line number, BIG-endian (line 10 = 00 0A)
#     [len_lo][len_hi]      — body length (LE), includes the trailing EOL
#     [body bytes...][0x0D] — body + EOL
#
# Tokens:
#     PRINT = 0xF5
#     GO TO = 0xEC
# Chars are stored as ASCII. After a numeric literal in source code, BASIC
# stores the rendered digits THEN a number marker (0x0E) + 5-byte binary
# value (so it doesn't have to re-parse).
# ----------------------------------------------------------------------------

prog = bytearray()

# Line 10:  PRINT "test"
#   F5 (PRINT) + 22 (") + 74 65 73 74 ("test") + 22 (") + 0D (EOL) = 8 bytes
line_10 = bytes([0xF5, 0x22, 0x74, 0x65, 0x73, 0x74, 0x22, 0x0D])
prog += bytes([0x00, 0x0A])                              # line 10 (BE)
prog += struct.pack("<H", len(line_10))                  # body length (LE)
prog += line_10

# Line 20:  GO TO 10
#   EC (GO TO) + 31 30 ("10") + 0E 00 00 0A 00 00 (number marker + 16-bit 10
#   stored as 5 bytes) + 0D (EOL) = 10 bytes
line_20 = bytes([0xEC, 0x31, 0x30,
                 0x0E, 0x00, 0x00, 0x0A, 0x00, 0x00,
                 0x0D])
prog += bytes([0x00, 0x14])                              # line 20 (BE)
prog += struct.pack("<H", len(line_20))                  # body length (LE)
prog += line_20

BLEN = len(prog)
print("BASIC program: %d bytes" % BLEN)
print("hex: " + " ".join("%02X" % b for b in prog))


# ----------------------------------------------------------------------------
# Build the header block (19 bytes total: 1 type + 17 content + 1 CRC)
# ----------------------------------------------------------------------------
NAME       = b"test      "        # 10 chars, space-padded
HDTYPE     = 0x00                  # BASIC PROGRAM
AUTORUN    = 0x8000                # >= 0x8000 means NO autorun
VARS_OFFS  = BLEN                  # no variables → vars start after program

assert len(NAME) == 10, "filename must be 10 chars"

header_content = bytearray()
header_content.append(HDTYPE)
header_content += NAME
header_content += struct.pack("<H", BLEN)
header_content += struct.pack("<H", AUTORUN)
header_content += struct.pack("<H", VARS_OFFS)
assert len(header_content) == 17

# Header block = [type 0x00] + content + CRC
hdr_block = bytearray()
hdr_block.append(0x00)             # block_type = header
hdr_block += header_content
crc = 0
for b in hdr_block:
    crc ^= b
hdr_block.append(crc)
assert len(hdr_block) == 19


# ----------------------------------------------------------------------------
# Build the data block (BLEN+2 bytes total: 1 type + program + 1 CRC)
# ----------------------------------------------------------------------------
data_block = bytearray()
data_block.append(0xFF)            # block_type = data
data_block += prog
crc = 0
for b in data_block:
    crc ^= b
data_block.append(crc)
assert len(data_block) == BLEN + 2


# ----------------------------------------------------------------------------
# Write the TAP file
# ----------------------------------------------------------------------------
out_path = "test/test.tap"
with open(out_path, "wb") as f:
    f.write(struct.pack("<H", len(hdr_block)))
    f.write(hdr_block)
    f.write(struct.pack("<H", len(data_block)))
    f.write(data_block)

import os
sz = os.path.getsize(out_path)
print()
print("Wrote %s (%d bytes)" % (out_path, sz))
print("  Header block: %d bytes" % len(hdr_block))
print("    name='%s', BLEN=%d, AUTORUN=0x%04X (no autorun), VARS=%d" % (
    NAME.decode().rstrip(), BLEN, AUTORUN, VARS_OFFS))
print("    CRC=0x%02X" % hdr_block[-1])
print("  Data block: %d bytes (CRC=0x%02X)" % (len(data_block), data_block[-1]))
print()
print("To use:")
print("  1. Copy %s to your SD card as /TAP/test.tap" % out_path)
print("  2. In the protocol observer (V7), change SD_TAP_PATH to")
print("     '/sd/TAP/test.tap'")
print("  3. On TS-2068:")
print("       LOAD \"\"       # loads the program (no autorun)")
print("       VERIFY \"\"     # should succeed — program hasn't run")
