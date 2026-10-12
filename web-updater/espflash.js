// The ESP32-C3's ROM serial loader, spoken from the browser: enough of
// Espressif's protocol (the one esptool speaks) to write Zimodem into the v3
// card's modem module and check it. The bytes go through the TS-Pico: the
// card's firmware joins its USB port to the ESP32's UART (tsbus.esp_relay)
// and holds the ESP32 in its loader. No stub is uploaded: the ROM's own
// commands are used, at the loader's 115200 baud, which the relay doesn't
// change. Compressed writes (FLASH_DEFL_*) keep that to about a minute for
// the 1.2 MB image; the ROM's MD5 of what it wrote is checked against the
// image's.
//
// The protocol (Espressif's "Serial Protocol" for the ESP32-C3 ROM):
//   a request is SLIP-framed: 00, op, size (u16), checksum (u32), data;
//   a reply is 01, op, size (u16), value (u32), data, whose last four bytes
//   are the status (0 = OK) and error code.
//
// No DOM here: web-updater/test/espflash.test.mjs drives it against a fake
// loader under Node, which has CompressionStream too.

const SLIP_END = 0xC0, SLIP_ESC = 0xDB, SLIP_ESC_END = 0xDC, SLIP_ESC_ESC = 0xDD

const OP = {
    SYNC: 0x08,
    SPI_SET_PARAMS: 0x0B,
    SPI_ATTACH: 0x0D,
    FLASH_DEFL_BEGIN: 0x10,
    FLASH_DEFL_DATA: 0x11,
    SPI_FLASH_MD5: 0x13,
}
export const FLASH_WRITE_SIZE = 0x400        // the ROM loader's block
const STATUS_LEN = 4                         // the ESP32-C3 ROM's (esptool's ESP32ROM); 2 is the ESP8266's and the stub's
const FLASH_SIZE = 4 * 1024 * 1024           // the ESP32-C3-WROOM-02's 4 MB
const ERASE_MS_PER_MB = 30000                // esptool's ERASE_REGION_TIMEOUT_PER_MB
const MD5_MS_PER_MB = 8000

export function slipEncode(bytes) {
    const out = [SLIP_END]
    for (const b of bytes) {
        if (b === SLIP_END) out.push(SLIP_ESC, SLIP_ESC_END)
        else if (b === SLIP_ESC) out.push(SLIP_ESC, SLIP_ESC_ESC)
        else out.push(b)
    }
    out.push(SLIP_END)
    return Uint8Array.from(out)
}

/** The checksum FLASH_DEFL_DATA carries: XOR of the block's bytes, from EFh. */
export function checksum(bytes) {
    let c = 0xEF
    for (const b of bytes) c ^= b
    return c
}

const u32 = (...words) => {
    const a = new Uint8Array(4 * words.length)
    const v = new DataView(a.buffer)
    words.forEach((w, i) => v.setUint32(4 * i, w >>> 0, true))
    return a
}

const concat = (...parts) => {
    const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0))
    let o = 0
    for (const p of parts) { out.set(p, o); o += p.length }
    return out
}

/** zlib-wrapped deflate, what the ROM's FLASH_DEFL_* inflate. */
export async function deflate(bytes) {
    const stream = new Blob([bytes]).stream().pipeThrough(new CompressionStream('deflate'))
    return new Uint8Array(await new Response(stream).arrayBuffer())
}

export class EspError extends Error {}

export class EspRomLoader {
    /** io: { write(Uint8Array) -> Promise, read(ms) -> Promise<Uint8Array | null> }
     *  (null when nothing came in `ms`). */
    constructor(io) {
        this.io = io
        this.frame = null           // a SLIP frame being read, or null between frames
        this.esc = false
        this.pending = []           // whole frames read but not yet wanted
        this.leftover = new Uint8Array(0)
    }

    /** The next whole SLIP frame, or null by `ms`. */
    async readFrame(ms) {
        if (this.pending.length) return this.pending.shift()
        const end = Date.now() + ms
        for (;;) {
            let data = this.leftover
            this.leftover = new Uint8Array(0)
            if (!data.length) {
                const left = end - Date.now()
                if (left <= 0) return null
                data = await this.io.read(left)
                if (!data) return null
            }
            for (let i = 0; i < data.length; i++) {
                const b = data[i]
                if (this.frame === null) {
                    if (b === SLIP_END) this.frame = []     // anything else between frames is noise
                    continue
                }
                if (this.esc) {
                    this.frame.push(b === SLIP_ESC_END ? SLIP_END : b === SLIP_ESC_ESC ? SLIP_ESC : b)
                    this.esc = false
                } else if (b === SLIP_ESC) {
                    this.esc = true
                } else if (b === SLIP_END) {
                    if (this.frame.length) {
                        const f = Uint8Array.from(this.frame)
                        this.frame = null
                        this.leftover = data.slice(i + 1)
                        return f
                    }                                       // C0 C0: still at a frame's start
                } else {
                    this.frame.push(b)
                }
            }
        }
    }

    /** Send a request and wait for its reply: { value, data } (data without
     *  the status bytes). EspError on a failed status, or none by `ms`. */
    async command(op, data = new Uint8Array(0), chk = 0, ms = 3000) {
        const head = new Uint8Array(8)
        const v = new DataView(head.buffer)
        v.setUint8(0, 0x00)
        v.setUint8(1, op)
        v.setUint16(2, data.length, true)
        v.setUint32(4, chk, true)
        await this.io.write(slipEncode(concat(head, data)))
        const end = Date.now() + ms
        for (;;) {
            const left = end - Date.now()
            const f = left > 0 ? await this.readFrame(left) : null
            if (!f) throw new EspError(`no reply to command ${op.toString(16)}h`)
            if (f.length < 8 || f[0] !== 0x01 || f[1] !== op) continue   // another command's echo
            const fv = new DataView(f.buffer, f.byteOffset, f.length)
            const size = fv.getUint16(2, true)
            const body = f.slice(8, 8 + size)
            // The ROM's replies end in four status bytes: status, error, 0, 0.
            if (body.length < STATUS_LEN) throw new EspError(`short reply to ${op.toString(16)}h`)
            const status = body[body.length - STATUS_LEN], error = body[body.length - STATUS_LEN + 1]
            if (status !== 0) throw new EspError(`command ${op.toString(16)}h failed: error ${error.toString(16)}h`)
            return { value: fv.getUint32(4, true), data: body.slice(0, body.length - STATUS_LEN) }
        }
    }

    /** Get the loader's attention: SYNC until it answers, then drop the
     *  extra replies it sends. */
    async sync(tries = 10) {
        const data = concat(Uint8Array.from([0x07, 0x07, 0x12, 0x20]), new Uint8Array(32).fill(0x55))
        for (let i = 0; i < tries; i++) {
            try {
                await this.command(OP.SYNC, data, 0, 200)
                for (;;) { if (!(await this.readFrame(150))) break }   // the other SYNC replies
                this.pending = []
                return
            } catch (e) {
                if (!(e instanceof EspError)) throw e
            }
        }
        throw new EspError('the ESP32 loader does not answer')
    }

    async attach() {
        await this.command(OP.SPI_ATTACH, new Uint8Array(8))
        // id, total size, block, sector, page, status mask: the 4 MB part.
        await this.command(OP.SPI_SET_PARAMS, u32(0, FLASH_SIZE, 64 * 1024, 4096, 256, 0xFFFF))
    }

    /** Write `image` at `offset`, compressed, then check the ROM's MD5 of it.
     *  progress(fraction) as blocks go. */
    async flash(image, offset = 0, progress = () => {}) {
        const comp = await deflate(image)
        const blocks = Math.ceil(comp.length / FLASH_WRITE_SIZE)
        const eraseSize = Math.ceil(image.length / FLASH_WRITE_SIZE) * FLASH_WRITE_SIZE
        // The ROM erases the whole region at BEGIN; the fifth word is
        // "encrypted" (0), which the ESP32-C3's ROM expects.
        await this.command(OP.FLASH_DEFL_BEGIN, u32(eraseSize, blocks, FLASH_WRITE_SIZE, offset, 0), 0,
            Math.max(3000, ERASE_MS_PER_MB * eraseSize / (1024 * 1024)))
        for (let seq = 0; seq < blocks; seq++) {
            const block = comp.slice(seq * FLASH_WRITE_SIZE, (seq + 1) * FLASH_WRITE_SIZE)
            await this.command(OP.FLASH_DEFL_DATA, concat(u32(block.length, seq, 0, 0), block),
                checksum(block), 10000)
            progress((seq + 1) / blocks)
        }
        const r = await this.command(OP.SPI_FLASH_MD5, u32(offset, image.length, 0, 0), 0,
            Math.max(3000, MD5_MS_PER_MB * image.length / (1024 * 1024)))
        const got = new TextDecoder().decode(r.data.slice(0, 32)).toLowerCase()
        const want = md5hex(image)
        if (got !== want) throw new EspError(`the written image's MD5 is ${got}, not ${want}`)
        return { compressed: comp.length, blocks, md5: want }
    }
}

// ---------------------------------------------------------------------------
// MD5 (RFC 1321): the ROM's only digest, and not in WebCrypto.
// ---------------------------------------------------------------------------
const MD5_S = [7, 12, 17, 22, 5, 9, 14, 20, 4, 11, 16, 23, 6, 10, 15, 21]
const MD5_K = Array.from({ length: 64 }, (_, i) => Math.floor(Math.abs(Math.sin(i + 1)) * 2 ** 32) >>> 0)

export function md5hex(bytes) {
    const n = bytes.length
    const padded = new Uint8Array(((n + 8) >> 6) + 1 << 6)
    padded.set(bytes)
    padded[n] = 0x80
    const pv = new DataView(padded.buffer)
    pv.setUint32(padded.length - 8, (n * 8) >>> 0, true)
    pv.setUint32(padded.length - 4, Math.floor(n / 2 ** 29) >>> 0, true)
    let a0 = 0x67452301, b0 = 0xefcdab89, c0 = 0x98badcfe, d0 = 0x10325476
    const m = new Uint32Array(16)
    for (let off = 0; off < padded.length; off += 64) {
        for (let i = 0; i < 16; i++) m[i] = pv.getUint32(off + 4 * i, true)
        let a = a0, b = b0, c = c0, d = d0
        for (let i = 0; i < 64; i++) {
            let f, g
            if (i < 16) { f = (b & c) | (~b & d); g = i }
            else if (i < 32) { f = (d & b) | (~d & c); g = (5 * i + 1) % 16 }
            else if (i < 48) { f = b ^ c ^ d; g = (3 * i + 5) % 16 }
            else { f = c ^ (b | ~d); g = (7 * i) % 16 }
            const s = MD5_S[(i >> 4) * 4 + (i & 3)]
            const t = (a + f + MD5_K[i] + m[g]) >>> 0
            a = d; d = c; c = b
            b = (b + ((t << s) | (t >>> (32 - s)))) >>> 0
        }
        a0 = (a0 + a) >>> 0; b0 = (b0 + b) >>> 0; c0 = (c0 + c) >>> 0; d0 = (d0 + d) >>> 0
    }
    const out = new Uint8Array(16)
    const ov = new DataView(out.buffer)
    ;[a0, b0, c0, d0].forEach((w, i) => ov.setUint32(4 * i, w, true))
    return Array.from(out, (b) => b.toString(16).padStart(2, '0')).join('')
}

/** A Web Serial port opened raw (bytes, not text) for the loader: the
 *  updater's usual transport decodes UTF-8, which would mangle replies. */
export class RawSerialIO {
    constructor(port) {
        this.port = port
        this.chunks = []
        this.waiter = null
    }

    async open() {
        await this.port.open({ baudRate: 115200 })
        this.writer = this.port.writable.getWriter()
        this.reader = this.port.readable.getReader()
        this.pump = (async () => {
            try {
                for (;;) {
                    const { value, done } = await this.reader.read()
                    if (done) break
                    if (value && value.length) {
                        this.chunks.push(value)
                        if (this.waiter) { this.waiter(); this.waiter = null }
                    }
                }
            } catch (_e) { /* closed */ }
        })()
    }

    async write(bytes) { await this.writer.write(bytes) }

    async read(ms) {
        if (!this.chunks.length) {
            await new Promise((resolve) => {
                const t = setTimeout(() => { this.waiter = null; resolve() }, ms)
                this.waiter = () => { clearTimeout(t); resolve() }
            })
        }
        return this.chunks.length ? this.chunks.shift() : null
    }

    async close() {
        try { await this.reader.cancel() } catch (_e) { /* gone */ }
        try { this.reader.releaseLock() } catch (_e) { /* gone */ }
        try { this.writer.releaseLock() } catch (_e) { /* gone */ }
        await this.pump
        try { await this.port.close() } catch (_e) { /* gone */ }
    }
}
