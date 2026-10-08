/*
 * TS-Pico Web Updater — application glue.
 *
 * One guided run takes a TS-Pico from whatever it has (1.1, 1.5, 2.x, or a
 * blank/wiped Pico) to the chosen build:
 *
 *   1. Connect   Web Serial -> raw REPL; read the installed version.
 *   2. BOOTSEL   machine.bootloader(), then the bootloader over WebUSB
 *                (PICOBOOT) or, failing that, the RPI-RP2 drive (File System
 *                Access API). See flasher.js.
 *   3. Wipe      erase all 2 MB (WebUSB) or write flash_nuke.uf2 (drive).
 *   4. ROM       boards behind the channel's ROM (romBehind): write upgrade.uf2, reboot, and
 *                follow its "UPG {json}" lines while the user runs the updater
 *                on the 2068 (OUT 244,3, LOAD ""). Then back to BOOTSEL.
 *   5. Firmware  write firmware.uf2 and reboot.
 *   6. Files     Web Serial again: main.py, config.ini, words.txt, assets/,
 *                verify, reboot.
 *
 * Everything is fetched same-origin from a channel directory (release/ or
 * main/), built by build-payload.sh and published by pages.yml.
 */

import { WebSerial } from './vendor/transports.js'
import { MpRawMode } from './vendor/rawmode.js'
import { sizeFmt, splitPath, setReporter } from './vendor/utils.js'
import { UsbBootsel, DriveBootsel, sleep } from './flasher.js'

// ---------------------------------------------------------------------------
// DOM helpers
// ---------------------------------------------------------------------------
const $ = (id) => document.getElementById(id)
const show = (el, on = true) => { el.hidden = !on }
const enable = (el, on = true) => { el.disabled = !on }

function log(msg, kind = '') {
    const line = document.createElement('div')
    line.className = 'log-line' + (kind ? ' log-' + kind : '')
    line.textContent = `[${new Date().toLocaleTimeString()}] ${msg}`
    const out = $('log')
    out.appendChild(line)
    out.scrollTop = out.scrollHeight
}

setReporter((title, err) => log(`${title}: ${err && err.message ? err.message : err}`, 'warn'))

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const CHANNELS = ['release', 'main']
// ?via=drive: always write through the RPI-RP2 drive, never WebUSB -- to test
// that route, or when WebUSB half-works on a machine.
const DRIVE_ONLY = new URLSearchParams(location.search).get('via') === 'drive'
const PICO_VID = 0x2E8A
const ROM_BLOCKS = { 1: 128, 0: 64 }        // updater.asm: slot 1 is 32K, slot 0 the low 16K
const ROM_FAIL = {
    1: 'The updater got no answer from the TS-Pico.',
    2: 'The flash can\'t be written: fit the P10 jumper, then type LOAD "" on the 2068 again.',
    3: 'The data kept arriving wrong. Type LOAD "" on the 2068 to try again.',
    4: 'A flash write didn\'t take. Type LOAD "" on the 2068 to try again.',
}

let channel = 'release'
let manifest = null
let serial = null        // WebSerial transport, open
let raw = null           // MpRawMode, while in the raw REPL
let boot = null          // UsbBootsel | DriveBootsel, while the Pico is in BOOTSEL
let installed = null     // { fw, ver, from1x, mp } once read
let running = false

// ---------------------------------------------------------------------------
// Stages: each <li class="stage" id="st-..."> has .msg, .actions and a
// progress bar. The run marks them active/done/skipped/error as it goes.
// ---------------------------------------------------------------------------
const STAGES = ['connect', 'bootsel', 'wipe', 'rom', 'firmware', 'files']

function stage(name) { return $('st-' + name) }

function setStage(name, state, msg) {
    const el = stage(name)
    el.dataset.state = state
    if (msg !== undefined) el.querySelector('.msg').textContent = msg
    if (state !== 'active') {
        el.querySelector('.actions').replaceChildren()
        show(el.querySelector('.progress'), false)
    }
}

function stageMsg(name, msg) {
    stage(name).querySelector('.msg').textContent = msg
}

function stageProgress(name, frac) {
    const bar = stage(name).querySelector('.progress')
    show(bar, true)
    bar.firstElementChild.style.width = Math.round(Math.min(1, frac) * 100) + '%'
}

/** Show buttons in a stage and wait for one. Resolves with the chosen value
 *  inside the click's user activation, so the caller may open a browser
 *  picker (WebUSB, Web Serial, directory) straight away. */
function ask(name, choices) {
    const box = stage(name).querySelector('.actions')
    return new Promise((resolve) => {
        box.replaceChildren(...choices.map((c, i) => {
            const b = document.createElement('button')
            b.textContent = c.label
            if (i === 0) b.className = 'primary'
            b.addEventListener('click', () => { box.replaceChildren(); resolve(c.value) })
            return b
        }))
    })
}

class Stop extends Error {}                 // the user chose to stop; not a failure

// ---------------------------------------------------------------------------
// Channel + manifest
// ---------------------------------------------------------------------------
async function fetchManifest(ch) {
    const resp = await fetch(`${ch}/manifest.json`, { cache: 'no-store' })
    if (!resp.ok) throw new Error('HTTP ' + resp.status)
    return await resp.json()
}

async function loadChannel(ch) {
    channel = ch
    try { localStorage.setItem('tspico-channel', ch) } catch (_e) { /* private mode */ }
    for (const c of CHANNELS) $('ch-' + c).checked = (c === ch)
    try {
        manifest = await fetchManifest(ch)
    } catch (err) {
        manifest = null
        log(`Could not load ${ch}/manifest.json: ${err.message}`, 'error')
        $('latest-version').textContent = 'unavailable'
        refreshPlan()
        return
    }
    const m = manifest
    const total = m.files.reduce((n, f) => n + (f.size || 0), 0)
    $('latest-version').textContent = `${m.fw_version || '?'}` +
        (m.rom_version ? ` (TS-2068 ROM ${m.rom_version})` : '')
    const src = $('latest-source')
    src.textContent = m.tag || ''
    if (m.source_url) src.href = m.source_url; else src.removeAttribute('href')
    $('payload-summary').textContent = `${m.files.length} files, ${sizeFmt(total)}` +
        (m.uf2 ? '' : ' — no firmware image in this channel')

    setLink('dl-uf2', m.uf2 && `${ch}/${m.uf2}`)
    setLink('dl-uf2-zip', m.uf2_zip && `${ch}/${m.uf2_zip}`)
    setLink('dl-upgrade', m.upgrade_uf2 && `${ch}/${m.upgrade_uf2}`)
    setLink('sdcard-link', m.sdcard && m.sdcard.path && `${ch}/${m.sdcard.path}`)
    $('sdcard-note').textContent = m.sdcard ? `(${m.sdcard.files} files, ${sizeFmt(m.sdcard.size)})` : ''
    log(`Loaded ${ch} channel: firmware ${m.fw_version || '?'} (${m.tag}), ${m.files.length} files` +
        (m.upgrade_uf2 ? ', ROM updater included.' : ', no ROM updater.'))
    // Already connected: the new channel's ROM decides the ROM step afresh.
    if (installed && !running) $('opt-rom').checked = !!m.upgrade_uf2 && romBehind()
    refreshPlan()
}

function setLink(id, href) {
    const a = $(id)
    if (href) { a.href = href; a.classList.remove('disabled') }
    else { a.removeAttribute('href'); a.classList.add('disabled') }
}

// ---------------------------------------------------------------------------
// The plan: what the run will do, from the options and what we know
// ---------------------------------------------------------------------------
function majorOf(v) {
    const n = parseFloat(String(v))
    return Number.isFinite(n) ? n : null
}

// "2.1.2" -> [2, 1]: the major.minor that firmware and ROM share from 2.0 on.
function verOf(v) {
    const m = /^(\d+)\.(\d+)/.exec(String(v || ''))
    return m ? [Number(m[1]), Number(m[2])] : null
}

// Does this board need the ROM step? The ROM can't be read over USB, so the
// installed firmware's major.minor stands for it. Anything older than the
// channel's ROM needs it, and so does a board whose version is unknown (a
// wiped Pico): in practice every board out there still has 1.1's ROM. Only a
// board already on the channel's major.minor skips it.
function romBehind() {
    if (!installed || !manifest) return false
    const want = verOf(manifest.rom_version || manifest.fw_version)
    if (!want) return installed.from1x
    const have = installed.ver
    if (!have) return true
    return have[0] < want[0] || (have[0] === want[0] && have[1] < want[1])
}

function refreshPlan() {
    const m = manifest
    const wantRom = $('opt-rom').checked
    const hint = $('plan-hint')
    let problem = ''
    if (!m) problem = 'No payload loaded for this channel.'
    else if (!m.uf2) problem = 'This channel has no firmware image. Pick the other channel, or use “Do it by hand”.'
    else if (wantRom && !m.upgrade_uf2) problem = 'This channel has no ROM updater (upgrade.uf2). ' +
        'Pick “Latest main build”, or untick the ROM update.'
    enable($('btn-start'), !problem && !running)
    enable($('opt-rom'), !!(m && m.upgrade_uf2) && !running)
    enable($('opt-wipe'), !running && !wantRom)
    if (wantRom) $('opt-wipe').checked = true   // the upgrade UF2 needs an empty filesystem

    hint.className = 'hint'
    if (problem) {
        hint.classList.add('warn'); hint.textContent = problem
    } else if (installed && installed.from1x && !wantRom) {
        hint.classList.add('warn')
        hint.textContent = `This board is on ${installed.fw}. Its TS-2068 ROM can't talk to ` +
            `firmware ${m.fw_version} — tick “Update the TS-2068 ROM” or the 2068 won't work afterwards.`
    } else if (!wantRom && romBehind()) {
        hint.classList.add('warn')
        hint.textContent = `This board is on ${installed.fw}, so its TS-2068 ROM is probably older ` +
            `than ROM ${m.rom_version || m.fw_version}. Tick “Update the TS-2068 ROM” to install it ` +
            `with the firmware.`
    } else {
        hint.textContent = planText()
    }
    show(hint, true)
    // Only stages that haven't run yet follow the options.
    const plan = (name, on, off) => {
        if (['pending', 'skipped', undefined].includes(stage(name).dataset.state)) {
            setStage(name, on ? 'pending' : 'skipped', on ? '' : off)
        }
    }
    plan('rom', wantRom, 'Not needed.')
    plan('wipe', $('opt-wipe').checked, 'Keeping what’s on the Pico.')
}

function planText() {
    const steps = []
    if ($('opt-wipe').checked) steps.push('erase the Pico')
    if ($('opt-rom').checked) steps.push('update the TS-2068 ROM (you’ll type two commands on the 2068)')
    steps.push(`install firmware ${manifest.fw_version}`, 'copy its files')
    return 'Start will ' + steps.join(', then ') + '. Keep the USB cable connected throughout.'
}

// ---------------------------------------------------------------------------
// Serial: connect, raw REPL, reconnect after a reboot
// ---------------------------------------------------------------------------
async function openSerial(port) {
    const t = new WebSerial()
    t.port = port
    const pi = port.getInfo()
    t.info = { vid: (pi.usbVendorId || 0).toString(16), pid: (pi.usbProductId || 0).toString(16) }
    await t.connect()
    t.onDisconnect(() => {
        if (serial === t) {
            serial = null
            raw = null
            log('Serial port closed (the Pico rebooted or was unplugged).')
            if (!running) showConnected(false)
        }
    })
    return t
}

async function closeSerial() {
    const t = serial
    serial = null
    raw = null
    if (t) { try { await t.disconnect() } catch (_e) { /* gone */ } }
}

/** Wait for a Pico running MicroPython to show up on a serial port we
 *  already have permission for (Chrome remembers it across reboots), and
 *  open it. Asks for a click only if there's none. */
async function reconnectSerial(name, ms = 30000) {
    const end = Date.now() + ms
    stageMsg(name, 'Waiting for the Pico to come back on USB…')
    while (Date.now() < end) {
        const ports = (await navigator.serial.getPorts())
            .filter((p) => p.getInfo().usbVendorId === PICO_VID)
        for (const p of ports) {
            try {
                serial = await openSerial(p)
                log('Serial reconnected.')
                return serial
            } catch (_e) { /* still enumerating, or not ours */ }
        }
        await sleep(700)
    }
    stageMsg(name, 'Click Connect and pick the Pico (“Board in FS mode” / “USB Serial Device”).')
    await ask(name, [{ label: 'Connect to TS-Pico', value: true }])
    serial = new WebSerial()
    await serial.requestAccess()
    const t = await openSerial(serial.port)
    serial = t
    return serial
}

async function enterRaw() {
    if (raw) return raw
    raw = await MpRawMode.begin(serial)      // Ctrl-C the firmware, Ctrl-A raw REPL
    return raw
}

/** Run code that resets the board: no reply will come. */
async function execNoReply(code) {
    await enterRaw()
    try {
        await raw.port.readUntil('>', 1000).catch(() => {})
        await raw.port.write(code)
        await raw.port.write('\x04')
        await sleep(400)
    } catch (_e) { /* expected: the port drops */ }
    await closeSerial()
}

async function readInstalled() {
    const info = await raw.getDeviceInfo()
    log(`Device: ${info.machine} — ${info.version}`)
    if (!/rp2|pico/i.test(info.machine + ' ' + info.sysname)) {
        log('Warning: this does not look like an RP2040/Pico.', 'warn')
    }
    // The running firmware's own FW_VERSION (2.0 on) wins: Ctrl-C leaves its
    // module loaded, and config.ini can hold a stale one (a 2.0 board may
    // still say "1.00"). 1.x has no such constant, so fall back to
    // config.ini: 1.5 wrote FW_VERSION there, 1.1's has none.
    let code = ''
    try {
        code = (await raw.exec("import sys\nm=sys.modules.get('TS.tspico') or sys.modules.get('dev_tspico')\n" +
            "print(getattr(m,'FW_VERSION','') if m else '')")).trim()
    } catch (_e) { /* no firmware module */ }
    let cfg = null
    try { cfg = JSON.parse(new TextDecoder().decode(await raw.readFile('/config.ini'))) } catch (_e) { /* none */ }
    let fw, major
    // config.ini's FW_VERSION is only a guess (1.5 wrote it; a board can
    // keep a stale one), so only the running module's version counts as known.
    let known = false
    if (code) {
        known = true
        fw = code
        major = majorOf(code)
    } else if (cfg) {
        fw = cfg.FW_VERSION || '1.1 (no version in config.ini)'
        major = majorOf(cfg.FW_VERSION || '1.1')
    } else {
        fw = 'unknown (no firmware running, no config.ini)'
        major = null
    }
    return { fw, ver: known ? verOf(code) : null, from1x: major !== null && major < 2, mp: info.release || null }
}

async function connect() {
    enable($('btn-connect'), false)
    try {
        // A Pico port this site already has permission for needs no picker.
        const known = (await navigator.serial.getPorts())
            .filter((p) => p.getInfo().usbVendorId === PICO_VID)
        let port
        if (known.length === 1) {
            port = known[0]
            setStage('connect', 'active', 'Opening the TS-Pico’s serial port…')
        } else {
            setStage('connect', 'active', 'Pick the TS-Pico in the browser’s port list…')
            const t = new WebSerial()
            await t.requestAccess()
            port = t.port
        }
        try {
            serial = await openSerial(port)
        } catch (_e) {
            await sleep(1500)               // just rebooted, or another tab just let go
            serial = await openSerial(port)
        }
        stageMsg('connect', 'Stopping the firmware and reading its version…')
        await enterRaw()
        installed = await readInstalled()
        $('installed-version').textContent = installed.fw
        if (manifest && manifest.upgrade_uf2) $('opt-rom').checked = romBehind()
        setStage('connect', 'done', `Connected. Installed: ${installed.fw}.`)
        showConnected(true)
    } catch (err) {
        log('Connect failed: ' + err.message, 'error')
        setStage('connect', 'error', 'Couldn’t connect. Close any other program using the Pico ' +
            '(Thonny, another tab) and try again — or, if it won’t connect at all, put it in BOOTSEL ' +
            'mode by hand (below) and press Start.')
        await closeSerial()
    } finally {
        enable($('btn-connect'), !serial)
        refreshPlan()
    }
}

function showConnected(on) {
    $('btn-connect').textContent = on ? 'Connected' : 'Connect to TS-Pico'
    enable($('btn-connect'), !on && !running)
}

// ---------------------------------------------------------------------------
// BOOTSEL
// ---------------------------------------------------------------------------
async function enterBootsel() {
    setStage('bootsel', 'active', '')
    if (serial) {
        stageMsg('bootsel', 'Rebooting the Pico into BOOTSEL mode…')
        log('machine.bootloader()')
        await execNoReply('import machine\nmachine.bootloader()')
    }
    boot = await getBootsel('bootsel')
    setStage('bootsel', 'done', `In BOOTSEL mode — using ${boot.describe()}.`)
}

/** A handle on the Pico's bootloader: the same kind as last time if we had
 *  one (no picker needed), else WebUSB, else the drive. */
async function getBootsel(name) {
    if (boot && boot.kind === 'usb') {
        const b = await UsbBootsel.find(20000)
        if (b) return b
    }
    if (boot && boot.kind === 'drive') {
        stageMsg(name, 'Waiting for the RPI-RP2 drive…')
        if (await boot.waitPresent(20000)) return boot
    }
    if (UsbBootsel.supported() && !DRIVE_ONLY) {
        const b = await UsbBootsel.find(3000)
        if (b) return b
    }
    // First time: needs a click for the browser's picker.
    return await pickBootsel(name)
}

async function pickBootsel(name) {
    const usb = UsbBootsel.supported() && !DRIVE_ONLY
    const drive = DriveBootsel.supported()
    for (;;) {
        const choices = []
        if (usb) choices.push({ label: 'Allow USB access', value: 'usb' })
        if (drive) choices.push({ label: 'Use the RPI-RP2 drive', value: 'drive' })
        choices.push({ label: 'Stop', value: 'stop' })
        stageMsg(name, usb
            ? 'The Pico is in BOOTSEL mode. Click “Allow USB access” and pick “RP2 Boot” in the list.'
            : 'The Pico is in BOOTSEL mode. Click “Use the RPI-RP2 drive”. Chrome then asks you to ' +
              '“select where this site can save changes”: choose the RPI-RP2 drive itself — on a Mac ' +
              'under Locations, on Windows under This PC — not a folder, click Select, and allow editing.')
        const how = await ask(name, choices)
        if (how === 'stop') throw new Stop()
        try {
            if (how === 'usb') {
                const b = await UsbBootsel.request()
                log(`Using ${b.describe()}.`)
                return b
            }
            const d = await DriveBootsel.pick()
            log(`Using ${d.describe()}.`)
            return d
        } catch (err) {
            if (err.name === 'NotFoundError' || err.name === 'AbortError') {
                log('Nothing picked.', 'warn')
                continue
            }
            log(`${how === 'usb' ? 'USB' : 'Drive'} access failed: ${err.message}`, 'error')
            if (how === 'usb') {
                log('On Windows the Pico’s bootloader has no WebUSB driver unless you ' +
                    'installed WinUSB for “RP2 Boot” (Zadig). On Linux it needs picotool’s ' +
                    'udev rule. The RPI-RP2 drive works everywhere — use that.', 'warn')
            }
        }
    }
}

async function fetchBytes(path) {
    const resp = await fetch(path, { cache: 'no-store' })
    if (!resp.ok) throw new Error(`${path}: HTTP ${resp.status}`)
    return new Uint8Array(await resp.arrayBuffer())
}

async function writeImage(name, path, label) {
    setStage(name, 'active', `Downloading ${label}…`)
    const bytes = await fetchBytes(path)
    stageMsg(name, `Writing ${label} (${sizeFmt(bytes.length)}) via ${boot.describe()}…`)
    await boot.writeUf2(bytes, path.split('/').pop(), (f) => stageProgress(name, f))
    log(`Wrote ${label}.`, 'ok')
}

// ---------------------------------------------------------------------------
// The TS-2068 ROM update, driven from the 2068 and watched over serial
// ---------------------------------------------------------------------------
async function romUpdate() {
    await writeImage('rom', `${channel}/${manifest.upgrade_uf2}`, 'the ROM updater')
    await boot.reboot()
    await reconnectSerial('rom')

    const box = $('rom-steps')
    show(box, true)
    stage('rom').querySelector('.msg').after(box)
    stageMsg('rom', 'Now on the TS-2068 (the TS-Pico stays plugged into it and into USB):')
    stageProgress('rom', 0)

    let slot1Done = false
    let writing = false                     // the updater is running: never interrupt the Pico now
    let lastEvent = Date.now()
    let resolveDone, rejectDone
    const done = new Promise((res, rej) => { resolveDone = res; rejectDone = rej })
    const status = (text, kind = '') => {
        const s = $('rom-status')
        s.textContent = text
        s.className = 'hint ' + kind
    }
    status('Waiting for LOAD "" on the 2068…')

    const fmt = (ev) => Object.entries(ev).map(([k, v]) => `${k}=${v}`).join(' ')
    let phase = 1
    const onUpg = (ev) => {
        lastEvent = Date.now()
        if (ev.event !== 'status' || ev.code !== 'W') log('2068: ' + fmt(ev))
        switch (ev.event) {
            case 'waiting': status('Waiting for LOAD "" on the 2068…'); break
            case 'tape':
                writing = false
                status(ev.note ? 'The updater stopped; the tape rewound. Type LOAD "" again.'
                    : 'Loading the updater from the TS-Pico…')
                break
            case 'ignored': status('That went to the TS-2068 ROM, not the Spectrum ROM. ' +
                'Type OUT 244,3 first, then LOAD "".', 'warn'); break
            case 'updater':
                writing = true
                withdraw()                  // continuing now would interrupt it
                status('The updater is running. Don’t turn anything off.')
                break
            case 'status':
                if (ev.code === 'P') {
                    phase = ev.arg
                    status(phase === 1 ? 'Writing the TS-2068 ROM (slot 1)…' : 'Writing the ZX Spectrum ROM (slot 0)…')
                } else if (ev.code === 'W') {
                    const before = phase === 1 ? 0 : ROM_BLOCKS[1]
                    stageProgress('rom', (before + ev.arg + 1) / (ROM_BLOCKS[1] + ROM_BLOCKS[0]))
                } else if (ev.code === 'V') {
                    if (phase === 1) slot1Done = true
                    log(`Slot ${phase} verified.`, 'ok')
                } else if (ev.code === 'D') {
                    writing = false
                    stageProgress('rom', 1)
                    status('Both ROMs written and verified. The 2068 says DONE.', 'ok')
                    resolveDone('done')
                } else if (ev.code === 'X') {
                    writing = false
                    status((ROM_FAIL[ev.arg] || `The update failed (reason ${ev.arg}).`) +
                        (slot1Done ? ' (The TS-2068 ROM is already new; you can also continue without the ZX ROM.)' : ''),
                    'warn')
                }
                break
        }
    }

    let buf = ''
    serial.onReceive((data) => {
        buf += data
        let nl
        while ((nl = buf.indexOf('\n')) >= 0) {
            const line = buf.slice(0, nl).trim()
            buf = buf.slice(nl + 1)
            if (!line.startsWith('UPG ')) continue
            let ev
            try { ev = JSON.parse(line.slice(4)) } catch (_e) { continue }
            onUpg(ev)
        }
    })

    // An escape hatch for when the serial events don't arrive but the 2068
    // shows DONE -- offered only while the updater isn't writing, because
    // continuing interrupts the Pico, and the updater needs it until DONE.
    let offered = false
    const withdraw = () => {
        stage('rom').querySelector('.actions').replaceChildren()
        offered = false
    }
    const watch = setInterval(() => {
        if (!serial) {
            rejectDone(new Error('The Pico disconnected during the ROM update. Plug it back in and press ' +
                'Start again (untick Erase if the ROM part finished).'))
            return
        }
        if (!offered && !writing && Date.now() - lastEvent > 45000) {
            offered = true
            ask('rom', [
                { label: 'The 2068 says DONE — continue', value: 'done' },
                { label: 'Stop', value: 'stop' },
            ]).then(resolveDone)
        }
    }, 1000)

    let how
    try { how = await done } finally { clearInterval(watch) }
    serial.onReceive(() => {})
    show(box, false)
    if (how === 'stop') throw new Stop()
    setStage('rom', 'done', slot1Done || how === 'done' ? 'TS-2068 ROM updated.' : 'Done.')

    // Back to BOOTSEL for the real firmware -- a hard reset of the Pico, so with
    // the 2068 off: a reset while the 2068 runs leaves the SD card unreadable
    // until it loses power, and the ROM chip is live under a running 2068.
    stageMsg('firmware', 'Switch the TS-2068 off now. The USB cable keeps the Pico powered, and ' +
        'the Pico is about to restart.')
    if (await ask('firmware', [
        { label: 'The 2068 is off — continue', value: 'go' },
        { label: 'Stop', value: 'stop' },
    ]) === 'stop') throw new Stop()
    stageMsg('firmware', 'Rebooting the Pico into BOOTSEL mode…')
    await execNoReply('import machine\nmachine.bootloader()')
    boot = await getBootsel('firmware')
}

// ---------------------------------------------------------------------------
// Files: upload, verify, reboot
// ---------------------------------------------------------------------------
async function uploadFiles() {
    setStage('files', 'active', '')
    await reconnectSerial('files', 45000)    // first boot after a wipe formats the filesystem
    stageMsg('files', 'Entering the REPL…')
    await enterRaw()

    const files = manifest.files
    const totalBytes = files.reduce((n, f) => n + (f.size || 0), 0)
    let doneBytes = 0
    for (let i = 0; i < files.length; i++) {
        const f = files[i]
        stageMsg('files', `Writing ${f.path} (${i + 1}/${files.length})…`)
        const data = await fetchBytes(`${channel}/pico/${f.path}`)
        const [dir] = splitPath('/' + f.path)
        if (dir) await raw.makePath('/' + dir)
        await raw.writeFile('/' + f.path, data)
        log(`  ✓ ${f.path} (${sizeFmt(data.byteLength)})`, 'ok')
        doneBytes += f.size || 0
        stageProgress('files', totalBytes ? doneBytes / totalBytes : (i + 1) / files.length)
    }

    stageMsg('files', 'Verifying…')
    const bad = await verifyFiles()
    if (bad) throw new Error(`${bad} file(s) didn’t verify — see the log`)

    stageMsg('files', 'Restarting the firmware…')
    await execNoReply('import machine\nmachine.reset()')
    setStage('files', 'done', `All ${files.length} files written and verified. The Pico restarted.`)
}

async function verifyFiles() {
    const onDevice = new Map()
    flatten(await raw.walkFs(), onDevice)
    let bad = 0
    for (const f of manifest.files) {
        const got = onDevice.get('/' + f.path)
        if (got === undefined) { log(`  ✗ missing: ${f.path}`, 'error'); bad++ }
        else if (got !== f.size) { log(`  ✗ size mismatch: ${f.path} (device ${got}, expected ${f.size})`, 'error'); bad++ }
    }
    if (!bad) log(`Verify passed: ${manifest.files.length} files match.`, 'ok')
    return bad
}

function flatten(nodes, map) {
    for (const n of nodes) {
        if ('content' in n) flatten(n.content, map)
        else map.set(n.path, n.size)
    }
}

// ---------------------------------------------------------------------------
// The run
// ---------------------------------------------------------------------------
/** "1.29.0" -> [1, 29, 0]; compare two such. */
function verCmp(a, b) {
    const pa = String(a).split('.').map(Number), pb = String(b).split('.').map(Number)
    for (let i = 0; i < 3; i++) {
        const d = (pa[i] || 0) - (pb[i] || 0)
        if (d) return d
    }
    return 0
}

/** The MicroPython release in a UF2 ("1.20.0"), or null: for a channel whose
 *  manifest predates mp_version. The version string sits in the image; UF2
 *  blocks carry 256 bytes each, so join their payloads before searching. */
function uf2MicroPython(bytes) {
    const n = Math.floor(bytes.length / 512)
    const pay = new Uint8Array(n * 256)
    for (let i = 0; i < n; i++) pay.set(bytes.subarray(i * 512 + 32, i * 512 + 32 + 256), i * 256)
    const text = new TextDecoder('latin1').decode(pay)
    const m = /MicroPython v(\d+\.\d+\.\d+)/.exec(text)
    return m ? m[1] : null
}

/** Before installing an older MicroPython than the Pico runs: say what
 *  happens and ask. A newer MicroPython (v1.29, from firmware 2.x on main)
 *  writes the Pico's filesystem in a format an older one (v1.20, the 2.1
 *  release and before) can't read, and the older one's first boot then
 *  formats the flash. The files step writes this channel's files back, but
 *  anything else -- the activity log, files the user added -- is gone, and
 *  "keep what's on the Pico" can't be honoured. */
async function downgradeOk(wipe) {
    if (!installed || !installed.mp) return true
    let target = manifest.mp_version
    if (!target) {
        try { target = uf2MicroPython(await fetchBytes(`${channel}/${manifest.uf2}`)) } catch (_e) { target = null }
    }
    if (!target || verCmp(target, installed.mp) >= 0) return true
    log(`MicroPython downgrade: the Pico has v${installed.mp}, this firmware is built on v${target}.`, 'warn')
    return confirm(`This Pico runs MicroPython v${installed.mp}; firmware ${manifest.fw_version} is ` +
        `built on v${target}, an older one. That older MicroPython can't read the newer one's ` +
        `filesystem, so its first boot erases the Pico's files — the activity log and anything ` +
        `you added included. The updater then writes this firmware's own files again.` +
        (wipe ? '' : '\n\n“Keep what’s on the Pico” can’t be honoured for this install.') +
        '\n\nContinue?')
}

async function start() {
    if (running || !manifest || !manifest.uf2) return
    const wipe = $('opt-wipe').checked
    const rom = $('opt-rom').checked
    if (!serial && !confirm('The Pico isn’t connected over serial. Continue only if it’s already ' +
        'in BOOTSEL mode (the RPI-RP2 drive is showing). Otherwise click Cancel and Connect first.')) return
    if (wipe && !confirm('This erases everything on the Pico — firmware and files — and installs ' +
        `firmware ${manifest.fw_version}. Nothing on the TS-2068, SD card or EXROM is touched` +
        (rom ? ' except the ROM update you asked for.' : '.') + '\n\nContinue?')) return
    if (!(await downgradeOk(wipe))) return

    running = true
    setRunning(true)
    let current = 'bootsel'
    try {
        await enterBootsel()

        if (wipe) {
            current = 'wipe'
            setStage('wipe', 'active', 'Erasing the Pico’s flash…')
            if (boot.kind === 'usb') {
                await boot.wipe((f) => stageProgress('wipe', f))
            } else {
                await boot.wipe(await fetchBytes('flash_nuke.uf2'), (f) => stageProgress('wipe', f))
            }
            setStage('wipe', 'done', 'Erased.')
            log('Flash erased.', 'ok')
        }

        if (rom) {
            current = 'rom'
            await romUpdate()
        }

        current = 'firmware'
        await writeImage('firmware', `${channel}/${manifest.uf2}`, `firmware ${manifest.fw_version}`)
        await boot.reboot()
        setStage('firmware', 'done', `Firmware ${manifest.fw_version} installed.`)

        current = 'files'
        await uploadFiles()

        $('installed-version').textContent = manifest.fw_version
        log('All done.', 'ok')
        show($('done'), true)
    } catch (err) {
        if (err instanceof Stop) {
            setStage(current, 'error', 'Stopped.')
            log('Stopped.', 'warn')
        } else {
            setStage(current, 'error', err.message)
            log(`${current}: ${err.message}`, 'error')
            log('You can press Start again: every step can be repeated, and a Pico stuck in ' +
                'BOOTSEL mode is always recoverable.', 'warn')
        }
        if (boot && boot.close) await boot.close()
    } finally {
        running = false
        setRunning(false)
    }
}

function setRunning(on) {
    enable($('btn-start'), !on)
    enable($('opt-wipe'), !on)
    for (const c of CHANNELS) enable($('ch-' + c), !on)
    showConnected(!!serial)
    if (on) {
        show($('done'), false)
        for (const s of STAGES) {
            if (s !== 'connect') setStage(s, 'pending', '')
        }
    }
    refreshPlan()
}

// The software library lives in the archive.org item its tapes came from
// (tools/sd-archive/publish.py). Its downloads send no CORS header, so the
// page only links them; the metadata API does, so the note shows the zip's
// current size and date.
async function libraryNote() {
    const name = decodeURIComponent($('library-link').href.split('/').pop())
    try {
        const r = await fetch('https://archive.org/metadata/timex-sinclair-software-archive/files')
        const f = (await r.json()).result.find((x) => x.name === name)
        if (f) {
            $('library-note').textContent = `(${sizeFmt(+f.size)}, ` +
                `${new Date(f.mtime * 1000).toISOString().slice(0, 10)})`
        }
    } catch (_e) { /* the links work without it */ }
}

// ---------------------------------------------------------------------------
async function init() {
    libraryNote()
    // Windows: WebUSB can't open RP2 Boot and the drive picker won't take
    // RPI-RP2, so the firmware steps fail. Point at windows-updater/.
    if (/Windows/.test(navigator.userAgent)) show($('windows-note'), true)
    if (typeof navigator.serial === 'undefined') {
        show($('unsupported'), true)
        show($('main'), false)
        return
    }
    $('btn-connect').addEventListener('click', connect)
    $('btn-start').addEventListener('click', start)
    $('opt-wipe').addEventListener('change', refreshPlan)
    $('opt-rom').addEventListener('change', refreshPlan)
    for (const c of CHANNELS) {
        $('ch-' + c).addEventListener('change', () => loadChannel(c))
    }
    const how = []
    if (UsbBootsel.supported() && !DRIVE_ONLY) how.push('USB (WebUSB)')
    if (DriveBootsel.supported()) how.push('the RPI-RP2 drive')
    log(`This browser can write firmware via ${how.join(' or ') || 'nothing (use Do it by hand)'}.`)

    // Channel: ?channel=main, else the last one used, else release. A channel
    // that isn't published is disabled.
    let want = new URLSearchParams(location.search).get('channel')
    if (!want) { try { want = localStorage.getItem('tspico-channel') } catch (_e) { /* private mode */ } }
    for (const c of CHANNELS) {
        try {
            const m = await fetchManifest(c)
            $('ch-' + c + '-label').textContent = m.tag ? `(${m.fw_version}, ${m.tag})` : ''
        } catch (_e) {
            enable($('ch-' + c), false)
            $('ch-' + c + '-label').textContent = '(not published)'
            if (want === c) want = null
        }
    }
    if (!CHANNELS.includes(want) || $('ch-' + want).disabled) {
        want = CHANNELS.find((c) => !$('ch-' + c).disabled) || 'release'
    }
    await loadChannel(want)
}

init()
