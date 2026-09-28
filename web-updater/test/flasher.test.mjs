// Host test for flasher.js's WebUSB path: run the real UF2s through
// UsbBootsel against a fake PICOBOOT connection that models the flash
// (erase -> 0xFF, write only clears bits, read back), and check the result
// matches what the UF2 says. Also checks wipe covers all 2 MB and that
// checkUf2 rejects non-UF2 / non-RP2040 input.
//
//   node web-updater/test/flasher.test.mjs [firmware.uf2 ...]
//
// With no arguments it uses any UF2 found in the generated release/ and main/
// payload channels (run build-payload.sh first).
import { readFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import assert from 'node:assert/strict'
import { UsbBootsel, checkUf2 } from '../flasher.js'

const here = dirname(fileURLToPath(import.meta.url))
const BASE = 0x10000000, SIZE = 2 * 1024 * 1024

class FakeConn {
    constructor() { this.flash = new Uint8Array(SIZE).fill(0x5A); this.log = [] }
    range(addr, n) {
        assert.ok(addr >= BASE && addr + n <= BASE + SIZE, `out of range 0x${addr.toString(16)}+${n}`)
        return addr - BASE
    }
    async flashErase(addr, n) {
        assert.equal(addr % 4096, 0); assert.equal(n % 4096, 0)
        this.flash.fill(0xFF, this.range(addr, n), this.range(addr, n) + n); this.log.push('E')
    }
    async flashWrite(addr, buf) {
        assert.equal(addr % 256, 0)
        const o = this.range(addr, buf.length)
        for (let i = 0; i < buf.length; i++) this.flash[o + i] &= buf[i]   // NOR: only 1 -> 0
        this.log.push('W')
    }
    async flashRead(addr, n) { const o = this.range(addr, n); this.log.push('R'); return this.flash.slice(o, o + n) }
    async reboot() {}
}

function expected(uf2) {
    const out = new Map()
    for (let off = 0; off < uf2.length; off += 512) {
        const v = new DataView(uf2.buffer, uf2.byteOffset + off, 512)
        const addr = v.getUint32(12, true), n = v.getUint32(16, true)
        out.set(addr, uf2.subarray(off + 32, off + 32 + n))
    }
    return out
}

let files = process.argv.slice(2)
if (!files.length) {
    files = []
    for (const ch of ['release', 'main']) for (const f of ['firmware.uf2', 'upgrade.uf2']) {
        const p = join(here, '..', ch, f)
        if (existsSync(p)) files.push(p)
    }
}

let n = 0
const ok = (msg) => { n++; console.log('ok', n, msg) }

// wipe
{
    const c = new FakeConn(); const u = new UsbBootsel({ getInfo: () => 'fake' }, c)
    let last = 0
    await u.wipe((f) => { assert.ok(f >= last); last = f })
    assert.ok(c.flash.every((b) => b === 0xFF)); assert.equal(last, 1)
    ok('wipe erases all 2 MB, progress reaches 1')
}

for (const path of files) {
    const uf2 = new Uint8Array(readFileSync(path))
    checkUf2(uf2, path)
    const c = new FakeConn(); const u = new UsbBootsel({ getInfo: () => 'fake' }, c)
    let last = 0
    await u.writeUf2(uf2, path, (f) => { assert.ok(f >= last && f <= 1.0000001); last = f })
    for (const [addr, data] of expected(uf2)) {
        const o = addr - BASE
        assert.deepEqual(c.flash.subarray(o, o + data.length), data, `block at 0x${addr.toString(16)}`)
    }
    assert.ok(Math.abs(last - 1) < 1e-9, `progress ends at ${last}`)
    ok(`${path.split('/').slice(-2).join('/')}: every UF2 block lands in flash, verified, progress 0..1`)
}

// flash_nuke.uf2 runs from RAM: the WebUSB path erases instead, and refuses
// to "write" a RAM image into flash.
{
    const nuke = new Uint8Array(readFileSync(join(here, '..', 'flash_nuke.uf2')))
    checkUf2(nuke, 'flash_nuke.uf2')
    const u = new UsbBootsel({ getInfo: () => 'fake' }, new FakeConn())
    await assert.rejects(u.writeUf2(nuke, 'flash_nuke.uf2'), /doesn't fit/)
    ok('a RAM-only UF2 (flash_nuke) is refused, not written to flash')
}

// Verify catches a flash that doesn't take a write.
{
    if (!files.length) throw new Error('no firmware UF2 to test: run build-payload.sh with one first')
    const uf2 = new Uint8Array(readFileSync(files[files.length - 1]))
    const c = new FakeConn(); c.flashWrite = async () => {}             // writes silently fail
    const u = new UsbBootsel({ getInfo: () => 'fake' }, c)
    await assert.rejects(u.writeUf2(uf2, 'x.uf2'), /verify failed/)
    ok('a write that does not take fails the verify')
}

// checkUf2 rejects junk and other families.
{
    assert.throws(() => checkUf2(new Uint8Array(100), 'x'), /not a UF2/)
    assert.throws(() => checkUf2(new Uint8Array(512), 'x'), /bad magic/)
    const uf2 = new Uint8Array(readFileSync(join(here, '..', 'flash_nuke.uf2'))).slice(0, 512)
    const v = new DataView(uf2.buffer)
    v.setUint32(8, v.getUint32(8, true) | 0x2000, true); v.setUint32(28, 0xE48BFF59, true)   // RP2350
    assert.throws(() => checkUf2(uf2, 'x'), /not an RP2040/)
    ok('checkUf2 rejects short, non-UF2 and non-RP2040 files')
}
console.log(`all ${n} passed`)
