// Sinistar with a held /INT (P T-states) and frame jitter (J). A crash: the
// game's interrupts stop for 120 frames after it has started, or the PC sits
// in the ROM area (chunk 0 HOME) at a frame boundary.
import fs from "node:fs";
import {createMachine, resetMachine, runFrame, insertDock} from "./machine.js";
const [frames, P, J, seed0] = [+process.argv[2], +process.argv[3], +process.argv[4], +process.argv[5] || 1];
let seed = seed0;
const rnd = () => (seed = (seed * 1103515245 + 12345) & 0x7fffffff) / 0x7fffffff;
const m = createMachine(new Uint8Array(8).fill(0x1f));
m.homeRom.set(fs.readFileSync("roms/ts2068-0.rom"));
m.exRom.set(fs.readFileSync("roms/ts2068-1.rom"));
insertDock(m, new Uint8Array(fs.readFileSync(process.argv[6] || "sinistar.dck")));
resetMachine(m);
globalThis.__intHold = P;
globalThis.__jitter = () => (J ? Math.floor(rnd() * J) : 0);
let last = 0, lastTaken = 0, crashed = -1, why = "";
for (let f = 0; f < frames; f++) {
    runFrame(m);
    const t = globalThis.__irqTaken || 0;
    if (t !== lastTaken) { lastTaken = t; last = f; }
    if (f > 1400) {
        if (f - last > 120) { crashed = f; why = "no interrupts for 120 frames"; break; }
        if (m.cpu.pc < 0x4000 && !(m.portF4 & 1)) { crashed = f; why = "PC in ROM"; break; }
    }
}
console.log(`P=${P} J=${J} seed=${seed0} -> ${crashed < 0 ? "ok, " + frames + " frames" : "CRASH at frame " + crashed + " (" + why + ") pc " + m.cpu.pc.toString(16)}  late irqs ${globalThis.__irqLate || 0}`);
