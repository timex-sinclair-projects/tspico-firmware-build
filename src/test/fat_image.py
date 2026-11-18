"""FAT volumes in memory for the label tests (catalog.read_label/write_label).

Dev is a block device as the SD driver is one: readblocks/writeblocks of
512-byte blocks, sparse (an unwritten block reads as zeros). fat16() and
fat32() lay out a volume the way newfs_msdos and SD Card Formatter do: a
boot sector with the extended signature 29h and "NO NAME" in BS_VolLab, the
FATs, an empty root folder. fat32() puts it behind an MBR, with the backup
boot sector at 6 and a root folder of two one-sector clusters, so a label
can land in the second. Checked against images newfs_msdos made and
fsck_msdos passed (2026-10-29).
"""

import struct


class Dev:
    def __init__(self):
        self.blocks = {}
        self.writes = []

    def readblocks(self, n, buf):
        buf[:] = self.blocks.get(n, bytes(512))

    def writeblocks(self, n, buf):
        self.writes.append(n)
        self.blocks[n] = bytes(buf)

    def get(self, n):
        return bytearray(self.blocks.get(n, bytes(512)))

    def put(self, n, data):
        self.blocks[n] = bytes(data).ljust(512, b"\0")


def _boot(spc, rsvd, fatsz16, root_ents, total, fat32, fatsz32=0, hidden=0):
    b = bytearray(512)
    b[0:3] = b"\xEB\x58\x90" if fat32 else b"\xEB\x3C\x90"
    b[3:11] = b"MSDOS5.0"
    struct.pack_into("<HBHBHHBHHHII", b, 11, 512, spc, rsvd, 2, root_ents, 0, 0xF8,
                     fatsz16, 63, 255, hidden, total)
    if fat32:
        struct.pack_into("<IHHIHH", b, 36, fatsz32, 0, 0, 2, 1, 6)
        b[66] = 0x29
        struct.pack_into("<I", b, 67, 0x1234ABCD)
        b[71:82] = b"NO NAME    "
        b[82:90] = b"FAT32   "
    else:
        b[38] = 0x29
        struct.pack_into("<I", b, 39, 0x1234ABCD)
        b[43:54] = b"NO NAME    "
        b[54:62] = b"FAT16   "
    b[510:512] = b"\x55\xAA"
    return b


def fat16(dev=None, total=81920, root_ents=512):
    """A FAT16 volume from sector 0 (no MBR). Returns (dev, root sector)."""
    dev = dev or Dev()
    fatsz = (total // 4 * 2 + 511) // 512
    dev.put(0, _boot(4, 1, fatsz, root_ents, total, False))
    for k in range(2):
        dev.put(1 + k * fatsz, b"\xF8\xFF\xFF\xFF")
    return dev, 1 + 2 * fatsz


def fat32(dev=None, start=2048, total=614400):
    """A FAT32 volume in the MBR's first partition. Returns (dev, the two
    root-folder sectors, the partition's first sector)."""
    dev = dev or Dev()
    mbr = bytearray(512)
    struct.pack_into("<B3sB3sII", mbr, 446, 0, b"\0\0\0", 0x0C, b"\0\0\0", start, total)
    mbr[510:512] = b"\x55\xAA"
    dev.put(0, mbr)
    rsvd, fatsz = 32, (total * 4 + 511) // 512
    boot = _boot(1, rsvd, 0, 0, total, True, fatsz, start)
    dev.put(start, boot)
    dev.put(start + 6, boot)
    fat = bytearray(512)
    struct.pack_into("<IIII", fat, 0, 0x0FFFFFF8, 0x0FFFFFFF, 3, 0x0FFFFFFF)   # root: 2 -> 3
    for k in range(2):
        dev.put(start + rsvd + k * fatsz, fat)
    data = start + rsvd + 2 * fatsz
    return dev, (data, data + 1), start


def entry(name, attr=0x20, first=None):
    """A 32-byte folder entry: an 8.3 name ("README  TXT") or a label."""
    e = bytearray(32)
    e[0:11] = name.encode().ljust(11)[:11]
    if first is not None:
        e[0] = first
    e[11] = attr
    return e


def lfn():
    """A long-name entry: attribute 0Fh, which has the label bit (08h) set."""
    e = bytearray(b"\xFF" * 32)
    e[0], e[11], e[12], e[26], e[27] = 0x41, 0x0F, 0, 0, 0
    return e


def fill(dev, sector, entries):
    """Write entries into a root-folder sector, from its first slot."""
    buf = dev.get(sector)
    for i, e in enumerate(entries):
        buf[i * 32:i * 32 + 32] = e
    dev.put(sector, buf)


def entries(dev, sector):
    buf = dev.get(sector)
    return [bytes(buf[i:i + 32]) for i in range(0, 512, 32)]
