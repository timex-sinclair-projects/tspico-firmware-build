// Host test for espflash.js, the web updater's ESP32-C3 ROM-loader client
// (the v3 card's modem: Zimodem written through the card's relay). A fake
// loader decodes the SLIP frames, checks every command the way the ROM
// does (checksums, block order, the BEGIN words), inflates the blocks with
// Node's zlib into a model 4 MB flash, and answers MD5 from it. Replies come
// back in random splits, so frames are reassembled across reads.
//
//   node web-updater/test/espflash.test.mjs [zimodem-v3.bin]
//
// With no argument it uses esp32/zimodem/out/zimodem-v3.bin if it exists,
// else 300K of patterned bytes.
import { readFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { createHash } from 'node:crypto'
import { inflateSync } from 'node:zlib'
import assert from 'node:assert/strict'
import { EspRomLoader, EspError, slipEncode, checksum, md5hex, FLASH_WRITE_SIZE } from '../espflash.js'

const here = dirname(fileURLToPath(import.meta.url))
let failed = 0
async function check(what, fn) {
    try { await fn(); console.log('  ok   ' + what) } catch (e) { failed++; console.log('  FAIL ' + what + ': ' + e.message) }
}

class FakeRom {
    constructor({ deafSyncs = 2, badSeqAt = -1 } = {}) {
        this.flash = new Uint8Array(4 * 1024 * 1024).fill(0x5A)
        this.out = []                   // reply bytes, handed out in random splits
        this.buf = []
        this.deaf = deafSyncs           // the first SYNCs go unanswered, as a waking loader's do
        this.badSeqAt = badSeqAt
        this.ops = []
    }
    // io
    async write(bytes) {
        for (const b of bytes) this.buf.push(b)
        for (;;) {
            const s = this.buf.indexOf(0xC0), e = this.buf.indexOf(0xC0, s + 1)
            if (s < 0 || e < 0) break
            const raw = this.buf.slice(s + 1, e); this.buf = this.buf.slice(e)
            if (!raw.length) continue
            const f = []
            for (let i = 0; i < raw.length; i++) {
                if (raw[i] === 0xDB) { f.push(raw[++i] === 0xDC ? 0xC0 : 0xDB) } else f.push(raw[i])
            }
            this.handle(Uint8Array.from(f))
        }
    }
    async read(_ms) {
        if (!this.out.length) return null
        const n = 1 + Math.floor(Math.random() * Math.min(40, this.out.length))
        return Uint8Array.from(this.out.splice(0, n))
    }
    reply(op, data = [], status = 0, error = 0, value = 0) {
        const body = [...data, status, error, 0, 0]
        const head = [0x01, op, body.length & 0xFF, body.length >> 8, value & 0xFF, (value >> 8) & 0xFF, (value >> 16) & 0xFF, value >>> 24]
        this.out.push(...slipEncode(Uint8Array.from([...head, ...body])))
    }
    handle(f) {
        assert.equal(f[0], 0x00, 'a request starts 00')
        const op = f[1], size = f[2] | (f[3] << 8)
        const chk = (f[4] | (f[5] << 8) | (f[6] << 16) | (f[7] << 24)) >>> 0
        const d = f.slice(8, 8 + size), v = new DataView(d.buffer, d.byteOffset, d.length)
        assert.equal(d.length, size, 'the size field matches')
        this.ops.push(op)
        switch (op) {
        case 0x08:                                          // SYNC
            if (this.deaf > 0) { this.deaf--; return }
            for (let i = 0; i < 8; i++) this.reply(op)      // the ROM answers a SYNC several times
            return
        case 0x0D: assert.equal(size, 8); this.attached = true; return this.reply(op)
        case 0x0B: assert.equal(v.getUint32(4, true), 4 * 1024 * 1024); return this.reply(op)
        case 0x10: {                                        // FLASH_DEFL_BEGIN
            assert.ok(this.attached, 'SPI_ATTACH before BEGIN')
            assert.equal(size, 20, 'five words: the C3 ROM wants the encrypted flag')
            this.erase = v.getUint32(0, true); this.blocks = v.getUint32(4, true)
            this.bsize = v.getUint32(8, true); this.offset = v.getUint32(12, true)
            assert.equal(this.erase % FLASH_WRITE_SIZE, 0, 'erase size in whole blocks')
            this.flash.fill(0xFF, this.offset, this.offset + this.erase)
            this.comp = []; this.seq = 0
            return this.reply(op)
        }
        case 0x11: {                                        // FLASH_DEFL_DATA
            const len = v.getUint32(0, true), seq = v.getUint32(4, true)
            const block = d.slice(16, 16 + len)
            if (checksum(block) !== chk) return this.reply(op, [], 1, 0x07)
            if (seq !== this.seq || seq === this.badSeqAt) return this.reply(op, [], 1, 0x09)
            assert.ok(len <= this.bsize)
            this.comp.push(...block); this.seq++
            if (this.seq === this.blocks) {                 // inflate into the flash
                const img = inflateSync(Uint8Array.from(this.comp))
                assert.ok(img.length <= this.erase, 'fits the erased region')
                this.flash.set(img, this.offset)
            }
            return this.reply(op)
        }
        case 0x13: {                                        // SPI_FLASH_MD5
            const a = v.getUint32(0, true), n = v.getUint32(4, true)
            const hex = createHash('md5').update(this.flash.subarray(a, a + n)).digest('hex')
            return this.reply(op, [...new TextEncoder().encode(hex)])
        }
        default:
            return this.reply(op, [], 1, 0x05)
        }
    }
}

const imgPath = process.argv[2] || join(here, '..', '..', 'esp32', 'zimodem', 'out', 'zimodem-v3.bin')
const image = existsSync(imgPath) ? new Uint8Array(readFileSync(imgPath))
    : Uint8Array.from({ length: 300 * 1024 }, (_, i) => (i * 7 + (i >> 9)) & 0xFF)
console.log('image: %s (%d bytes)', existsSync(imgPath) ? imgPath : 'patterned', image.length)

await check('md5hex matches node:crypto at every padding edge', async () => {
    for (const n of [0, 1, 55, 56, 63, 64, 65, 119, 120, 1000, 100000]) {
        const b = Uint8Array.from({ length: n }, (_, i) => (i * 31) & 0xFF)
        assert.equal(md5hex(b), createHash('md5').update(b).digest('hex'), `length ${n}`)
    }
})

await check('SLIP escapes C0 and DB', async () => {
    assert.deepEqual([...slipEncode(Uint8Array.from([1, 0xC0, 2, 0xDB, 3]))],
        [0xC0, 1, 0xDB, 0xDC, 2, 0xDB, 0xDD, 3, 0xC0])
})

await check('sync through deaf first tries, attach, write, MD5 verified', async () => {
    const rom = new FakeRom({ deafSyncs: 3 })
    const esp = new EspRomLoader(rom)
    await esp.sync()
    await esp.attach()
    let last = 0
    const r = await esp.flash(image, 0, (f) => { assert.ok(f >= last); last = f })
    assert.equal(last, 1, 'progress reaches 1')
    assert.deepEqual(rom.flash.subarray(0, image.length), image, 'the flash holds the image')
    assert.equal(rom.flash[image.length + 1], image.length % 1024 ? 0xFF : 0x5A, 'erased to the block, no further')
    assert.equal(rom.flash[rom.erase + 10], 0x5A, 'nothing past the erased region touched (Zimodem\'s SPIFFS)')
    console.log('       %d bytes, %d compressed in %d blocks', image.length, r.compressed, r.blocks)
})

await check('a refused block is an EspError', async () => {
    const rom = new FakeRom({ deafSyncs: 0, badSeqAt: 2 })
    const esp = new EspRomLoader(rom)
    await esp.sync(); await esp.attach()
    await assert.rejects(esp.flash(image), EspError)          // block 2: the patterned image has only 3
})

await check('an MD5 that differs is an EspError', async () => {
    const rom = new FakeRom({ deafSyncs: 0 })
    const esp = new EspRomLoader(rom)
    await esp.sync(); await esp.attach()
    const orig = rom.handle.bind(rom)
    rom.handle = (f) => { if (f[1] === 0x13) rom.flash[3] ^= 0xFF; orig(f) }   // a byte goes bad after writing
    await assert.rejects(esp.flash(image.slice(0, 8 * 1024)), /MD5/)
})

await check('no loader at all: sync gives up', async () => {
    const esp = new EspRomLoader({ write: async () => {}, read: async () => null })
    await assert.rejects(esp.sync(3), /does not answer/)
})

console.log(failed ? `\n${failed} FAILED` : '\nALL PASS')
process.exit(failed ? 1 : 0)
