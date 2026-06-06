/*
 * SPDX-FileCopyrightText: 2024 Volodymyr Shymanskyy
 * SPDX-License-Identifier: MIT
 *
 * The software is provided "as is", without any warranties or guarantees (explicit or implied).
 * This includes no assurances about being fit for any specific purpose.
 *
 * ---------------------------------------------------------------------------
 * Vendored from ViperIDE (https://github.com/vshymanskyy/ViperIDE),
 * src/utils.js, trimmed for the TS-Pico Web Updater. Only the helpers that
 * transports.js / rawmode.js depend on are kept; the toastr/analytics/peerjs
 * UI machinery from upstream is removed and `report()` is reduced to a console
 * log plus an optional app-supplied hook (see setReporter below).
 * ---------------------------------------------------------------------------
 */

export function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms))
}

export class Mutex {
    constructor() {
        this._lock = Promise.resolve()
    }

    acquire() {
        let release
        const lock = new Promise(resolve => release = resolve)
        const acquire = this._lock.then(() => release)
        this._lock = this._lock.then(() => lock)
        return acquire
    }
}

export function splitPath(path) {
    const parts = path.split('/').filter(part => part !== '')
    const filename = parts.pop()
    const directoryPath = parts.join('/')
    return [ directoryPath, filename ]
}

export function sizeFmt(size, places=1) {
    if (size == null) { return "unknown" }
    const suffixes = ['B', 'KiB', 'MiB', 'GiB', 'TiB']
    let i = 0
    while (size > 1024 && i < suffixes.length - 1) {
        i++
        size /= 1024
    }
    if (i === 0) {
        return `${size}${suffixes[i]}`
    } else {
        return `${(size).toFixed(places)}${suffixes[i]}`
    }
}

/*
 * Error reporting. Upstream routed this through toastr + analytics; here we
 * just log to the console and forward to an optional app-supplied reporter so
 * the updater UI can surface the message however it likes.
 */
let _reporter = null
export function setReporter(fn) { _reporter = fn }

export function report(title, err) {
    console.error(title, err, err && err.stack)
    if (_reporter) {
        try { _reporter(title, err) } catch (_e) { /* ignore reporter failures */ }
    }
}
