/*
 * SPDX-FileCopyrightText: 2024 Volodymyr Shymanskyy
 * SPDX-License-Identifier: MIT
 *
 * The software is provided "as is", without any warranties or guarantees (explicit or implied).
 * This includes no assurances about being fit for any specific purpose.
 *
 * ---------------------------------------------------------------------------
 * Vendored from ViperIDE (https://github.com/vshymanskyy/ViperIDE),
 * src/transports.js, trimmed for the TS-Pico Web Updater. Only the abstract
 * `Transport` base class and the `WebSerial` USB-CDC transport are kept; the
 * Bluetooth (WebBluetooth), WebSocket (WebSocketREPL) and WebRTC
 * (WebRTCTransport) classes from upstream — and the `peerjs` import they
 * needed — are removed. The TS-Pico is a USB-attached Pico, so WebSerial is
 * the only transport the updater uses.
 * ---------------------------------------------------------------------------
 */

import { sleep, Mutex, report } from './utils.js'

export class Transport {
    constructor() {
        if (this.constructor === Transport) {
            throw new Error("Cannot instantiate abstract class Transport")
        }
        this.mutex = new Mutex()
        this.inTransaction = false
        this.receivedData = ''
        this.activityCallback = () => {}
        this.receiveCallback = () => {}
        this.disconnectCallback = () => {}
        this.writeChunk = 128
        this.emit = false
        this.info = {}
    }

    async requestAccess() {
        throw new Error("Method 'requestAccess()' must be implemented.")
    }

    async connect() {
        throw new Error("Method 'connect()' must be implemented.")
    }

    async getInfo() {
        return this.info
    }

    async disconnect() {
        throw new Error("Method 'disconnect()' must be implemented.")
    }

    async write(data) {
        const encoder = new TextEncoder()
        const value = encoder.encode(data)
        try {
            let offset = 0
            while (offset < value.byteLength) {
                const chunk = value.slice(offset, offset + this.writeChunk)
                await this.writeBytes(chunk)
                this.activityCallback()
                offset += this.writeChunk
            }
        } catch (err) {
            report("Write error", err)
        }
    }

    onActivity(callback) {
        this.activityCallback = callback
    }

    onReceive(callback) {
        this.receiveCallback = callback
    }

    onDisconnect(callback) {
        this.disconnectCallback = callback
    }

    /*
     * Transaction API
     */

    async startTransaction() {
        const release = await this.mutex.acquire()
        this.prevRecvCbk = this.receiveCallback
        this.inTransaction = true
        this.receivedData = ''
        this.receiveCallback = (data) => {
            this.receivedData += data
            if (this.emit && this.prevRecvCbk) { this.prevRecvCbk(data) }
        }

        return () => {
            if (this.prevRecvCbk) {
                this.receiveCallback = this.prevRecvCbk
                this.receiveCallback(this.receivedData)
            }
            this.receivedData = null
            this.inTransaction = false

            release()
        }
    }

    async flushInput() {
        if (!this.inTransaction) {
            throw new Error('Not in transaction')
        }
        this.receivedData = ''
    }

    async readExactly(n, timeout=5000) {
        if (!this.inTransaction) {
            throw new Error('Not in transaction')
        }
        let endTime = Date.now() + timeout
        while (timeout <= 0 || (Date.now() < endTime)) {
            if (this.receivedData.length >= n) {
                const res = this.receivedData.substring(0, n)
                this.receivedData = this.receivedData.substring(n)
                return res
            }
            const prev_avail = this.receivedData.length
            await sleep(10)
            if (this.receivedData.length > prev_avail) {
                endTime = Date.now() + timeout
            }
        }
        throw new Error('Timeout')
    }

    async readUntil(ending, timeout=5000) {
        if (!this.inTransaction) {
            throw new Error('Not in transaction')
        }
        let endTime = Date.now() + timeout
        while (timeout <= 0 || (Date.now() < endTime)) {
            const idx = this.receivedData.indexOf(ending) + ending.length
            if (idx >= ending.length) {
                const res = this.receivedData.substring(0, idx)
                this.receivedData = this.receivedData.substring(idx)
                return res
            }
            const prev_avail = this.receivedData.length
            await sleep(10)
            if (this.receivedData.length > prev_avail) {
                endTime = Date.now() + timeout
            }
        }
        throw new Error('Timeout reached before finding the ending sequence')
    }
}

/*
 * USB / Serial
 */

export class WebSerial extends Transport {
    constructor(serial=null) {
        super()
        this.port = null
        this.reader = null
        this.writer = null
        if (serial) {
            this.serial = serial
        } else {
            if (typeof navigator.serial === 'undefined') {
                throw new Error('WebSerial not available')
            }
            this.serial = navigator.serial
        }
    }

    async requestAccess() {
        this.port = await this.serial.requestPort()
        try {
            const pi = this.port.getInfo()
            this.info = {
                vid: pi.usbVendorId.toString(16).padStart(4, '0'),
                pid: pi.usbProductId.toString(16).padStart(4, '0'),
            }
        } catch (err) {
            report("Error", err)
        }
    }

    async connect() {
        await this.port.open({ baudRate: 115200 })

        const decoderStream = new TextDecoderStream()
        this.readableStreamClosed = this.port.readable.pipeTo(decoderStream.writable)
        this.reader = decoderStream.readable.getReader()
        this.writer = this.port.writable.getWriter()

        const processStream = async () => {
            while (true) {
                const { value, done } = await this.reader.read()
                if (done) {
                    this.reader.releaseLock()
                    break
                }
                this.receiveCallback(value)
                this.activityCallback()
            }
            this.disconnectCallback()
        }
        processStream()
    }

    async disconnect() {
        if (this.reader) {
            await this.reader.cancel()
            await this.readableStreamClosed.catch(() => {})
        }
        if (this.writer) {
            try { this.writer.releaseLock() } catch (_e) { /* ignore */ }
        }
        if (this.port) {
            try { await this.port.close() } catch (_e) { /* ignore */ }
        }
    }

    async writeBytes(data) {
        await this.writer.write(data)
    }
}
