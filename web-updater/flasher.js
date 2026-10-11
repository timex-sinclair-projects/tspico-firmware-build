/*
 * TS-Pico Web Updater — writing to a Pico in BOOTSEL mode.
 *
 * Two ways in, one interface (wipe / writeUf2 / reboot):
 *
 *   UsbBootsel    WebUSB + PICOBOOT (vendor/picoflash). Erases, writes,
 *                 verifies and reboots with no drive and no drag. Needs the
 *                 bootloader's vendor interface to be openable: fine on macOS,
 *                 ChromeOS and Android; Linux needs picotool's udev rule; an
 *                 RP2040 on Windows needs WinUSB bound to it (Zadig), because
 *                 its boot ROM has no Microsoft OS descriptors.
 *
 *   DriveBootsel  File System Access API on the RPI-RP2 drive. The user picks
 *                 the drive once; we write the UF2 onto it, as a drag would.
 *                 Works on any desktop Chrome/Edge with no driver. Wiping
 *                 means writing flash_nuke.uf2.
 *
 * The page prefers UsbBootsel and falls back to DriveBootsel when it can't be
 * opened.
 */

import { Picoboot } from './vendor/picoflash/picoboot.js'
import { uf2ToFlashBuffer } from './vendor/picoflash/uf2.js'

const FLASH_BASE = 0x10000000
// Each chip's flash, and the UF2 family its boot ROM takes. The v3 card is an
// RP2350B with 16 MB (GD25Q128E); the TS-Pico 2.x a Raspberry Pi Pico, an
// RP2040 with 2 MB.
const FLASH_SIZE = { RP2040: 2 * 1024 * 1024, RP2350: 16 * 1024 * 1024 }
const FAMILY = { RP2040: 0xE48BFF56, RP2350: 0xE48BFF59 }   // RP2350: Arm, secure
const SECTOR = 4096
const ERASE_CHUNK = 64 * 1024            // one PICOBOOT erase per 64K block: well inside its timeout
const WRITE_CHUNK = 16 * 1024
const UF2_FLAG_FAMILY = 0x00002000

export const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/** The chip a UF2 is built for ('RP2040', 'RP2350'), or null if it names a
 *  family neither boot ROM takes, or none. */
export function uf2Chip(bytes) {
    if (bytes.length < 512) return null
    const v = new DataView(bytes.buffer, bytes.byteOffset, 512)
    if (!(v.getUint32(8, true) & UF2_FLAG_FAMILY)) return null
    const fam = v.getUint32(28, true)
    return Object.keys(FAMILY).find((c) => FAMILY[c] === fam) || null
}

/** Check a UF2 is for this chip before either path writes it: an RP2040
 *  image on the v3 card, or the reverse, leaves a board that doesn't start. */
export function checkUf2(bytes, name, chip = 'RP2040') {
    if (bytes.length < 512 || bytes.length % 512) {
        throw new Error(`${name} is not a UF2 (size ${bytes.length})`)
    }
    const v = new DataView(bytes.buffer, bytes.byteOffset, 512)
    if (v.getUint32(0, true) !== 0x0A324655 || v.getUint32(4, true) !== 0x9E5D5157) {
        throw new Error(`${name} is not a UF2 (bad magic)`)
    }
    if ((v.getUint32(8, true) & UF2_FLAG_FAMILY) && v.getUint32(28, true) !== FAMILY[chip]) {
        throw new Error(`${name} is not an ${chip} UF2`)
    }
}

// ---------------------------------------------------------------------------
// WebUSB / PICOBOOT
// ---------------------------------------------------------------------------
export class UsbBootsel {
    static supported() {
        return typeof navigator.usb !== 'undefined'
    }

    /** Ask for the device (needs a click). Throws if the user cancels or it
     *  can't be opened -- the caller falls back to the drive. */
    static async request() {
        const pb = await Picoboot.requestDevice()
        return await UsbBootsel.open(pb)
    }

    /** A BOOTSEL Pico this page already has permission for, or null. Polls
     *  up to `ms` for it to appear (a reboot into BOOTSEL takes a second or
     *  two). No click needed. */
    static async find(ms = 0) {
        const end = Date.now() + ms
        do {
            const list = await Picoboot.getDevices()
            if (list.length) {
                try { return await UsbBootsel.open(list[0]) } catch (_e) { /* still enumerating */ }
            }
            if (Date.now() >= end) break
            await sleep(500)
        } while (true)
        return null
    }

    static async open(pb) {
        const conn = await pb.connect()
        await conn.setExclusiveAccess(1)     // keep the OS off the drive while we write
        await conn.exitXip()
        return new UsbBootsel(pb, conn)
    }

    constructor(pb, conn) {
        this.pb = pb
        this.conn = conn
        this.kind = 'usb'
        // The boot ROM's USB product ID says which chip: 0003 RP2040, 000F RP2350.
        this.chip = pb.target && pb.target.type === 'RP2350' ? 'RP2350' : 'RP2040'
    }

    describe() {
        return `USB bootloader (${this.pb.getInfo()})`
    }

    /** Erase the whole flash: what flash_nuke does, firmware and filesystem.
     *  The page never wipes a v3 card: its ROM slots live in that filesystem. */
    async wipe(progress = () => {}) {
        const size = FLASH_SIZE[this.chip]
        for (let off = 0; off < size; off += ERASE_CHUNK) {
            await this.conn.flashErase(FLASH_BASE + off, ERASE_CHUNK)
            progress((off + ERASE_CHUNK) / size)
        }
    }

    /** Erase what the image covers, write it, read it back. */
    async writeUf2(bytes, name, progress = () => {}) {
        checkUf2(bytes, name, this.chip)
        const { address, data } = uf2ToFlashBuffer(bytes)
        if (address < FLASH_BASE || address % SECTOR || address + data.length > FLASH_BASE + FLASH_SIZE[this.chip]) {
            throw new Error(`${name} doesn't fit the Pico's flash (0x${address.toString(16)}, ${data.length} bytes)`)
        }
        // Pad to whole sectors with 0xFF: the erase is by sector and the
        // padding reads back as erased flash.
        const len = Math.ceil(data.length / SECTOR) * SECTOR
        const img = new Uint8Array(len).fill(0xFF)
        img.set(data)
        const total = 3 * len                // erase, write, read back
        let done = 0
        const tick = (n) => progress((done += n) / total)
        for (let off = 0; off < len; off += ERASE_CHUNK) {
            const n = Math.min(ERASE_CHUNK, len - off)
            await this.conn.flashErase(address + off, n)
            tick(n)
        }
        for (let off = 0; off < len; off += WRITE_CHUNK) {
            const chunk = img.subarray(off, off + WRITE_CHUNK)
            await this.conn.flashWrite(address + off, chunk)
            tick(chunk.length)
        }
        for (let off = 0; off < len; off += WRITE_CHUNK) {
            const back = await this.conn.flashRead(address + off, Math.min(WRITE_CHUNK, len - off))
            const want = img.subarray(off, off + back.length)
            for (let i = 0; i < want.length; i++) {
                if (back[i] !== want[i]) {
                    throw new Error(`${name}: verify failed at 0x${(address + off + i).toString(16)}`)
                }
            }
            tick(back.length)
        }
    }

    /** Boot what's in flash. The device drops off USB. */
    async reboot() {
        try { await this.conn.reboot(100) } catch (_e) { /* it may go before it answers */ }
        await this.close()
    }

    async close() {
        try { await this.pb.disconnect() } catch (_e) { /* gone already */ }
    }
}

// ---------------------------------------------------------------------------
// File System Access API: the RPI-RP2 drive (RP2040), or RP2350
// ---------------------------------------------------------------------------
export class DriveBootsel {
    static supported() {
        return typeof window.showDirectoryPicker === 'function'
    }

    /** Ask the user to pick the boot drive (needs a click). */
    static async pick() {
        const dir = await window.showDirectoryPicker({ id: 'rpi-rp2', mode: 'readwrite' })
        const d = new DriveBootsel(dir)
        if (!(await d.present())) {
            throw new Error(`"${dir.name}" isn't the RPI-RP2 or RP2350 drive (no INFO_UF2.TXT naming one)`)
        }
        return d
    }

    constructor(dir) {
        this.dir = dir
        this.kind = 'drive'
        this.chip = 'RP2040'                // set by present() from INFO_UF2.TXT
    }

    describe() {
        return `the ${this.dir.name} drive`
    }

    /** Is the drive mounted and a Pico boot ROM? The handle is by path, so
     *  it keeps working after the drive goes away and comes back. */
    async present() {
        try {
            const f = await (await this.dir.getFileHandle('INFO_UF2.TXT')).getFile()
            const text = await f.text()
            if (/RP2350/.test(text)) { this.chip = 'RP2350'; return true }
            if (/RPI-RP2/.test(text)) { this.chip = 'RP2040'; return true }
            return false
        } catch (_e) {
            return false
        }
    }

    /** Wait for the drive to come back, e.g. after flash_nuke or a
     *  machine.bootloader(). */
    async waitPresent(ms) {
        const end = Date.now() + ms
        while (Date.now() < end) {
            if (await this.present()) return true
            await sleep(700)
        }
        return false
    }

    async waitGone(ms) {
        const end = Date.now() + ms
        while (Date.now() < end) {
            if (!(await this.present())) return true
            await sleep(300)
        }
        return false
    }

    /** Write a UF2 onto the drive. The Pico acts on the blocks as they land
     *  and reboots on the last one, so the tail of the write -- Chrome's
     *  close/rename of its temp file -- can fail because the drive has gone.
     *  That's success, and the drive vanishing is how we know. */
    async writeUf2(bytes, name, progress = () => {}) {
        checkUf2(bytes, name, this.chip)
        progress(0.05)
        let err = null
        try {
            const fh = await this.dir.getFileHandle(name, { create: true })
            const w = await fh.createWritable()
            await w.write(bytes)
            progress(0.6)
            await w.close()
        } catch (e) {
            err = e
        }
        if (!(await this.waitGone(15000))) {
            throw err || new Error(`wrote ${name} but the Pico didn't reboot`)
        }
        progress(1)
    }

    /** flash_nuke.uf2: erases everything, then comes back as RPI-RP2. RP2040
     *  only: the page never wipes a v3 card. */
    async wipe(nukeBytes, progress = () => {}) {
        if (this.chip !== 'RP2040') throw new Error('no flash_nuke for the ' + this.chip)
        await this.writeUf2(nukeBytes, 'flash_nuke.uf2', (f) => progress(f * 0.5))
        if (!(await this.waitPresent(60000))) {
            throw new Error('the RPI-RP2 drive did not come back after the wipe')
        }
        progress(1)
    }

    async reboot() { /* a UF2 write reboots by itself */ }
    async close() {}
}
