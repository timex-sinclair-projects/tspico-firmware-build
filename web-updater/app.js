/*
 * TS-Pico Web Updater — application glue.
 *
 * Drives the vendored ViperIDE WebSerial transport + MpRawMode to push a
 * release payload (main.py, config.ini, words.txt, assets/*.tap, help/*.txt)
 * onto a TS-Pico over USB, preserving subfolders. See README.md for the
 * deployment model (payload + manifest.json published same-origin).
 *
 * Prototype for https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/26
 */

import { WebSerial } from './vendor/transports.js'
import { MpRawMode } from './vendor/rawmode.js'
import { sleep, sizeFmt, splitPath, setReporter } from './vendor/utils.js'

// ---------------------------------------------------------------------------
// Small DOM helpers
// ---------------------------------------------------------------------------
const $ = (id) => document.getElementById(id)
const show = (el, on = true) => { el.hidden = !on }
const enable = (el, on = true) => { el.disabled = !on }

function log(msg, kind = '') {
    const line = document.createElement('div')
    line.className = 'log-line' + (kind ? ' log-' + kind : '')
    const ts = new Date().toLocaleTimeString()
    line.textContent = `[${ts}] ${msg}`
    const out = $('log')
    out.appendChild(line)
    out.scrollTop = out.scrollHeight
}

function setStatus(text, kind = '') {
    const s = $('status')
    s.textContent = text
    s.className = 'status ' + kind
}

// Route library-level errors (utils.report) into our log.
setReporter((title, err) => log(`${title}: ${err && err.message ? err.message : err}`, 'warn'))

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let port = null      // WebSerial transport
let raw = null       // MpRawMode (held open while connected)
let manifest = null  // parsed manifest.json
let busy = false

// ---------------------------------------------------------------------------
// Manifest loading (same-origin: published next to this page)
// ---------------------------------------------------------------------------
async function loadManifest() {
    try {
        const resp = await fetch('manifest.json', { cache: 'no-store' })
        if (!resp.ok) throw new Error('HTTP ' + resp.status)
        manifest = await resp.json()
    } catch (err) {
        log('Could not load manifest.json — is the payload published? ' + err.message, 'error')
        $('latest-version').textContent = 'unavailable'
        return
    }
    const total = manifest.files.reduce((n, f) => n + (f.size || 0), 0)
    $('latest-version').textContent =
        `${manifest.fw_version || '?'}` + (manifest.tag ? ` (release ${manifest.tag})` : '')
    $('payload-summary').textContent =
        `${manifest.files.length} files, ${sizeFmt(total)}`

    // UF2 download button (Step 1). The firmware image ships with real releases;
    // a locally-built test payload may not include it.
    const a = $('uf2-link')
    if (manifest.uf2) {
        a.href = manifest.uf2
        a.classList.remove('disabled')
        $('uf2-note').textContent = ''
    } else {
        a.removeAttribute('href')
        a.classList.add('disabled')
        $('uf2-note').textContent = 'Firmware image not in this payload (included in published releases).'
    }

    // Zipped UF2 fallback (Step 1). Some Windows setups block or quarantine a
    // raw .uf2 download (antivirus / SmartScreen); the .zip sidesteps that. Only
    // present when the payload includes the firmware image.
    const az = $('uf2-zip-link')
    if (manifest.uf2_zip) {
        az.href = manifest.uf2_zip
        az.classList.remove('disabled')
    } else {
        az.removeAttribute('href')
        az.classList.add('disabled')
    }

    // SD card bundle (Step 3, software testers only). Built from the repo's
    // "SD card/" folder by build-payload.sh; absent from payloads that don't
    // include it. This is a plain same-origin download — the SD content goes on
    // a physical card, not over the serial link.
    const sd = $('sdcard-link')
    if (manifest.sdcard && manifest.sdcard.path) {
        sd.href = manifest.sdcard.path
        sd.classList.remove('disabled')
        const bits = []
        if (manifest.sdcard.files) bits.push(`${manifest.sdcard.files} files`)
        if (manifest.sdcard.size) bits.push(sizeFmt(manifest.sdcard.size))
        $('sdcard-note').textContent = bits.length ? `(${bits.join(', ')})` : ''
    } else {
        sd.removeAttribute('href')
        sd.classList.add('disabled')
        $('sdcard-note').textContent = 'SD card bundle not in this payload (included in published releases).'
    }
    log(`Loaded manifest: firmware ${manifest.fw_version || '?'}, ${manifest.files.length} files.`)
}

// ---------------------------------------------------------------------------
// Connect / disconnect
// ---------------------------------------------------------------------------
async function connect() {
    if (busy) return
    busy = true
    enable($('btn-connect'), false)
    try {
        setStatus('Requesting serial port…')
        port = new WebSerial()
        await port.requestAccess()        // user picks the Pico in the browser dialog
        port.onDisconnect(onPortLost)
        await port.connect()              // open at 115200
        log(`Port opened (VID:${port.info.vid} PID:${port.info.pid}). Entering raw REPL…`)

        setStatus('Connecting to MicroPython…')
        raw = await MpRawMode.begin(port) // Ctrl-C interrupt + Ctrl-A raw REPL

        const info = await raw.getDeviceInfo()
        log(`Device: ${info.machine} — ${info.version}`)
        const looksLikePico = /rp2|pico/i.test(info.machine + ' ' + info.sysname)
        if (!looksLikePico) {
            log('Warning: this does not look like an RP2040/Pico. Proceed with caution.', 'warn')
        }

        // Read installed firmware version from /config.ini on the device.
        let installed = 'unknown'
        try {
            const bytes = await raw.readFile('/config.ini')
            const cfg = JSON.parse(new TextDecoder().decode(bytes))
            installed = cfg.FW_VERSION || 'unknown'
        } catch (_e) {
            log('No readable /config.ini on device (fresh flash?).', 'warn')
        }
        $('installed-version').textContent = installed
        updateFwHint(installed)

        setStatus('Connected', 'ok')
        show($('connected-panel'), true)
        enable($('btn-update'), !!manifest)
        enable($('btn-verify'), !!manifest)
        enable($('btn-reboot'), true)
        enable($('btn-bootloader'), true)
        enable($('btn-disconnect'), true)
        $('btn-connect').textContent = 'Connected'
    } catch (err) {
        log('Connect failed: ' + err.message, 'error')
        setStatus('Connect failed', 'error')
        await safeDisconnect()
        enable($('btn-connect'), true)
    } finally {
        busy = false
    }
}

function onPortLost() {
    log('Serial port closed / device disconnected.', 'warn')
    resetUiToDisconnected()
}

async function safeDisconnect() {
    try { if (raw && raw.end) await raw.end() } catch (_e) { /* ignore */ }
    try { if (port) await port.disconnect() } catch (_e) { /* ignore */ }
    raw = null
    port = null
}

async function disconnect() {
    await safeDisconnect()
    log('Disconnected.')
    resetUiToDisconnected()
}

function resetUiToDisconnected() {
    raw = null
    port = null
    show($('connected-panel'), false)
    enable($('btn-connect'), true)
    $('btn-connect').textContent = 'Connect to TS-Pico'
    enable($('btn-update'), false)
    enable($('btn-verify'), false)
    enable($('btn-reboot'), false)
    enable($('btn-bootloader'), false)
    enable($('btn-disconnect'), false)
    $('installed-version').textContent = 'connect in Step 3 to read'
    show($('fw-hint'), false)
    setStatus('Not connected')
}

// ---------------------------------------------------------------------------
// Update: write every manifest file to the device flash
// ---------------------------------------------------------------------------
async function update() {
    if (busy || !raw || !manifest) return
    busy = true
    setControlsDuringTransfer(true)
    const files = manifest.files
    const totalBytes = files.reduce((n, f) => n + (f.size || 0), 0)
    let doneBytes = 0
    let failed = 0

    setProgress(0)
    log(`Starting update: ${files.length} files, ${sizeFmt(totalBytes)}.`)
    try {
        for (let i = 0; i < files.length; i++) {
            const f = files[i]
            const dest = '/' + f.path
            setStatus(`Writing ${f.path} (${i + 1}/${files.length})`)
            try {
                const resp = await fetch('pico/' + f.path, { cache: 'no-store' })
                if (!resp.ok) throw new Error('fetch HTTP ' + resp.status)
                const data = new Uint8Array(await resp.arrayBuffer())

                const [dir] = splitPath(dest)
                if (dir) await raw.makePath('/' + dir)
                await raw.writeFile(dest, data)

                log(`  ✓ ${f.path} (${sizeFmt(data.byteLength)})`, 'ok')
            } catch (err) {
                failed++
                log(`  ✗ ${f.path}: ${err.message}`, 'error')
            }
            doneBytes += f.size || 0
            setProgress(totalBytes ? doneBytes / totalBytes : (i + 1) / files.length)
        }
        if (failed === 0) {
            setStatus('Update complete', 'ok')
            log('Update complete. Run Verify, then Reboot.', 'ok')
        } else {
            setStatus(`Update finished with ${failed} error(s)`, 'error')
            log(`Update finished with ${failed} failed file(s).`, 'error')
        }
    } finally {
        setControlsDuringTransfer(false)
        busy = false
    }
}

// ---------------------------------------------------------------------------
// Verify: walk the device FS and compare names/sizes against the manifest
// ---------------------------------------------------------------------------
async function verify() {
    if (busy || !raw || !manifest) return
    busy = true
    setControlsDuringTransfer(true)
    setStatus('Verifying…')
    try {
        const tree = await raw.walkFs()
        const onDevice = new Map()
        flatten(tree, onDevice)

        let ok = 0, mismatch = 0, missing = 0
        for (const f of manifest.files) {
            const key = '/' + f.path
            if (!onDevice.has(key)) {
                log(`  ✗ missing: ${f.path}`, 'error'); missing++
            } else if (onDevice.get(key) !== f.size) {
                log(`  ✗ size mismatch: ${f.path} (device ${onDevice.get(key)}, expected ${f.size})`, 'error')
                mismatch++
            } else {
                ok++
            }
        }
        if (mismatch === 0 && missing === 0) {
            setStatus(`Verified ✓ all ${ok} files match`, 'ok')
            log(`Verify passed: ${ok}/${manifest.files.length} files match.`, 'ok')
        } else {
            setStatus(`Verify found problems (${missing} missing, ${mismatch} mismatched)`, 'error')
        }
    } catch (err) {
        log('Verify failed: ' + err.message, 'error')
        setStatus('Verify failed', 'error')
    } finally {
        setControlsDuringTransfer(false)
        busy = false
    }
}

// Flatten walkFs() tree into a Map<fullpath, size> for files only.
function flatten(nodes, map) {
    for (const n of nodes) {
        if ('content' in n) {
            flatten(n.content, map)
        } else {
            map.set(n.path, n.size)
        }
    }
}

// ---------------------------------------------------------------------------
// Reboot / bootloader (fire-and-forget: device drops serial on reset)
// ---------------------------------------------------------------------------
async function fireAndForget(code, note) {
    if (!raw) return
    log(note)
    try {
        // Send a bare exec without waiting for the OK that will never come —
        // the board resets mid-command.
        await raw.port.readUntil('>', 1000).catch(() => {})
        await raw.port.write(code)
        await raw.port.write('\x04')        // Ctrl-D: execute
        await sleep(400)
    } catch (_e) { /* expected: serial drops */ }
    await safeDisconnect()
    resetUiToDisconnected()
}

async function reboot() {
    if (busy) return
    await fireAndForget('import machine\nmachine.reset()',
        'Rebooting Pico (machine.reset())…')
    log('Pico is rebooting. It will reconnect as a serial device shortly.', 'ok')
}

async function bootloader() {
    if (busy) return
    if (!confirm('Reboot the Pico into BOOTSEL (UF2 flashing) mode?\n\n' +
        'An RPI-RP2 drive will appear. Drag firmware.uf2 onto it, then ' +
        'reconnect here to copy the files.')) return
    await fireAndForget('import machine\nmachine.bootloader()',
        'Entering BOOTSEL mode (machine.bootloader())…')
    log('Pico should now appear as the RPI-RP2 drive. Drop firmware.uf2 on it.', 'ok')
}

// ---------------------------------------------------------------------------
// UI plumbing
// ---------------------------------------------------------------------------
function updateFwHint(installed) {
    const hint = $('fw-hint')
    const latest = manifest && manifest.fw_version
    hint.className = 'hint'
    if (!latest) {
        show(hint, false); return
    }
    if (installed === 'unknown') {
        hint.classList.add('warn')
        hint.textContent = `Couldn't read the installed firmware version. ` +
            `If this is a fresh Pico, do Step 2 first, then upload files in Step 3.`
    } else if (String(installed) === String(latest)) {
        hint.classList.add('ok')
        hint.textContent = `✓ Firmware is already up to date (${installed}). ` +
            `You can skip Step 2 — just upload the files in Step 3.`
    } else {
        hint.classList.add('warn')
        hint.textContent = `Installed firmware is ${installed}, latest is ${latest}. ` +
            `Do Step 2 to flash the new firmware before uploading files.`
    }
    show(hint, true)
}

function setProgress(frac) {
    const pct = Math.round(frac * 100)
    $('progress-bar').style.width = pct + '%'
    $('progress-pct').textContent = pct + '%'
}

function setControlsDuringTransfer(active) {
    show($('progress-wrap'), active)
    enable($('btn-update'), !active)
    enable($('btn-verify'), !active)
    enable($('btn-reboot'), !active)
    enable($('btn-bootloader'), !active)
    enable($('btn-disconnect'), !active)
}

function init() {
    // Browser support gate.
    if (typeof navigator.serial === 'undefined') {
        show($('unsupported'), true)
        show($('main'), false)
        return
    }
    $('btn-connect').addEventListener('click', connect)
    $('btn-disconnect').addEventListener('click', disconnect)
    $('btn-update').addEventListener('click', update)
    $('btn-verify').addEventListener('click', verify)
    $('btn-reboot').addEventListener('click', reboot)
    $('btn-bootloader').addEventListener('click', bootloader)
    loadManifest()
}

init()
