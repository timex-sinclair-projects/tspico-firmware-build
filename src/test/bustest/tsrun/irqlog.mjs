// Headless TSRun: stock ROMs, Sinistar in the dock, N frames, a log of every
// frame-end interrupt (PC, SP, IFF1, HSR) and the stack top.
import fs from "node:fs";
import {createMachine, resetMachine, runFrame, insertDock, memRead} from "./machine.js";
const frames = +process.argv[2] || 3000;
const m = createMachine(new Uint8Array(8).fill(0xff));
m.homeRom.set(fs.readFileSync("roms/ts2068-0.rom"));
m.exRom.set(fs.readFileSync("roms/ts2068-1.rom"));
const err = insertDock(m, new Uint8Array(fs.readFileSync(process.argv[3])));
if (err) { console.error(err); process.exit(1); }
resetMachine(m);
const rows = [];
globalThis.__irqHook = (mm, when) => {
    const c = mm.cpu;
    const sp = c.sp, lo = memRead(mm, sp), hi = memRead(mm, (sp + 1) & 0xffff);
    rows.push([c.pc, sp, c.iff1 ? 1 : 0, c.halted ? 1 : 0, mm.portF4, (hi << 8) | lo]);
};
for (let f = 0; f < frames; f++) runFrame(m);
const out = rows.map(r => r.map(v => v.toString(16)).join(" ")).join("\n");
fs.writeFileSync(process.argv[4] || "irq.log", out + "\n");
console.log("frames", frames, "rows", rows.length, "final pc", m.cpu.pc.toString(16));
