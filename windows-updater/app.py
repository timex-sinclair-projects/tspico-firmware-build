"""TS-Pico Updater -- the window.

A tkinter front end for core.Updater: pick a channel, Connect, tick the
options, Start. The run happens on a worker thread; it reaches the window only
through the queue below, which the Tk loop drains every 50 ms.

    TS-Pico-Updater.exe [--channel main] [--base URL-or-folder]

--base points at another copy of the published /updater/ directory -- a local
web-updater/ with a channel built by build-payload.sh, for testing.
"""

import argparse
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import core

TITLES = {
    "connect": "Connect",
    "bootsel": "BOOTSEL mode",
    "wipe": "Erase the Pico",
    "rom": "Update the TS-2068 ROM",
    "firmware": "Install the firmware",
    "files": "Copy the files",
}
MARKS = {"pending": "○", "active": "●", "done": "✓", "skipped": "–", "error": "✗"}
COLOURS = {"pending": "#888", "active": "#1565c0", "done": "#2e7d32", "skipped": "#aaa", "error": "#c62828"}
LOG_COLOURS = {"ok": "#2e7d32", "warn": "#b26a00", "error": "#c62828"}
ROM_STEPS = (
    "1.  Fit the P10 jumper if your board has one, and leave it on.\n"
    "2.  Turn the TS-2068 on.\n"
    "3.  Type  OUT 244,3  and press ENTER — this switches to the Spectrum ROM.\n"
    "4.  Type  LOAD \"\"  (J, then SYMBOL SHIFT+P twice) and press ENTER.\n"
    "5.  Wait for DONE on the TV. This window follows along.\n"
    "6.  Then switch the TS-2068 off again before the firmware is installed.\n"
    "     You'll be asked to confirm."
)


class TkUi(core.Ui):
    """core.Ui for the worker thread: everything goes through a queue."""

    def __init__(self, app):
        self.app = app
        self.choices = queue.Queue()

    def _post(self, *msg):
        self.app.q.put(msg)

    def log(self, msg, kind=""): self._post("log", msg, kind)
    def stage(self, name, state, msg=None): self._post("stage", name, state, msg)
    def stage_msg(self, name, msg): self._post("stage_msg", name, msg)
    def progress(self, name, frac): self._post("progress", name, frac)
    def rom_steps(self, on): self._post("rom_steps", on)
    def rom_status(self, text, kind=""): self._post("rom_status", text, kind)
    def withdraw(self, name): self._post("actions", [])

    def offer(self, name, choices):
        while not self.choices.empty():
            self.choices.get_nowait()
        self._post("actions", choices)

    def take(self, timeout=None):
        try:
            if timeout == 0:
                return self.choices.get_nowait()
            return self.choices.get(timeout=timeout)
        except queue.Empty:
            return None

    def confirm(self, text):
        done = threading.Event()
        box = {}
        self._post("confirm", text, done, box)
        done.wait()
        return box["ok"]


class App:
    def __init__(self, root, base, want):
        self.root = root
        self.q = queue.Queue()
        self.ui = TkUi(self)
        self.up = core.Updater(self.ui, base)
        self.busy = False
        self.manifests = {}

        root.title("TS-Pico Updater")
        root.minsize(640, 600)
        outer = ttk.Frame(root, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="TS-Pico Updater", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Install or upgrade the TS-Pico firmware over USB.",
                  foreground="#555").pack(anchor="w", pady=(0, 8))

        top = ttk.Frame(outer)
        top.pack(fill="x")
        chf = ttk.LabelFrame(top, text="Install from", padding=8)
        chf.pack(side="left", fill="both", expand=True)
        self.ch = tk.StringVar(value=want)
        self.ch_buttons = {}
        for c, label in (("release", "Latest release"), ("main", "Latest main build (for testers)")):
            b = ttk.Radiobutton(chf, text=label, value=c, variable=self.ch,
                                command=lambda: self.load_channel(self.ch.get()))
            b.pack(anchor="w")
            self.ch_buttons[c] = b

        vf = ttk.LabelFrame(top, text="Versions", padding=8)
        vf.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.latest = ttk.Label(vf, text="Latest: …")
        self.latest.pack(anchor="w")
        self.installed = ttk.Label(vf, text="Installed: not connected")
        self.installed.pack(anchor="w")

        opts = ttk.Frame(outer, padding=(0, 8))
        opts.pack(fill="x")
        self.btn_connect = ttk.Button(opts, text="Connect to TS-Pico", command=self.connect)
        self.btn_connect.pack(side="left")
        self.opt_wipe = tk.BooleanVar(value=True)
        self.opt_rom = tk.BooleanVar(value=False)
        self.cb_wipe = ttk.Checkbutton(opts, text="Erase the Pico first", variable=self.opt_wipe,
                                       command=self.refresh)
        self.cb_wipe.pack(side="left", padx=(12, 0))
        self.cb_rom = ttk.Checkbutton(opts, text="Update the TS-2068 ROM", variable=self.opt_rom,
                                      command=self.refresh)
        self.cb_rom.pack(side="left", padx=(12, 0))
        self.btn_start = ttk.Button(opts, text="Start", command=self.start)
        self.btn_start.pack(side="right")

        self.hint = ttk.Label(outer, text="", wraplength=600, justify="left")
        self.hint.pack(fill="x", pady=(0, 6))

        sf = ttk.LabelFrame(outer, text="Steps", padding=8)
        sf.pack(fill="x")
        self.rows = {}
        for i, s in enumerate(core.STAGES):
            mark = tk.Label(sf, text=MARKS["pending"], fg=COLOURS["pending"], font=("Segoe UI", 12))
            mark.grid(row=i, column=0, sticky="nw", padx=(0, 6))
            ttk.Label(sf, text=TITLES[s], font=("Segoe UI", 10, "bold")).grid(row=i, column=1, sticky="nw")
            msg = ttk.Label(sf, text="", wraplength=430, justify="left")
            msg.grid(row=i, column=2, sticky="nw", padx=(10, 0))
            self.rows[s] = (mark, msg)
        sf.columnconfigure(2, weight=1)

        self.romf = ttk.LabelFrame(outer, text="On the TS-2068", padding=8)
        ttk.Label(self.romf, text=ROM_STEPS, justify="left", font=("Segoe UI", 10)).pack(anchor="w")
        self.rom_status = tk.Label(self.romf, text="", justify="left", wraplength=580,
                                   font=("Segoe UI", 10, "bold"))
        self.rom_status.pack(anchor="w", pady=(6, 0))

        self.actions = ttk.Frame(outer, padding=(0, 6))
        self.actions.pack(fill="x")
        self.bar = ttk.Progressbar(outer, maximum=1000)
        self.bar.pack(fill="x", pady=(0, 6))

        self.log = ScrolledText(outer, height=10, font=("Consolas", 9), state="disabled", wrap="word")
        self.log.pack(fill="both", expand=True)
        for k, c in LOG_COLOURS.items():
            self.log.tag_configure(k, foreground=c)

        self.set_stages_pending()
        self.refresh()
        root.after(50, self.pump)
        self.work(self.load_channels, want)

    # --- worker thread ------------------------------------------------------
    def work(self, fn, *args):
        def body():
            try:
                fn(*args)
            finally:
                self.q.put(("idle",))
        self.busy = True
        self.refresh()
        threading.Thread(target=body, daemon=True).start()

    def load_channels(self, want):
        for c in core.CHANNELS:
            try:
                m = core.Channel(c, self.up.base).load()
                self.manifests[c] = m
                self.q.put(("chlabel", c, "%s (%s, %s)" % (
                    "Latest release" if c == "release" else "Latest main build (for testers)",
                    m.get("fw_version", "?"), m.get("tag", ""))))
            except Exception as e:
                self.ui.log("Channel %s: not available (%s)" % (c, e), "warn")
                self.q.put(("chlabel", c, None))
        if want not in self.manifests:
            want = next((c for c in core.CHANNELS if c in self.manifests), None)
        if want:
            self._load_channel(want)
        else:
            self.ui.log("No channel could be loaded. Check the internet connection and restart.", "error")

    def _load_channel(self, c):
        try:
            m = self.up.load_channel(c)
        except Exception as e:
            self.ui.log("Could not load %s: %s" % (c, e), "error")
            return
        self.q.put(("channel", c, m))

    def load_channel(self, c):
        if not self.busy:
            self.work(self._load_channel, c)

    def connect(self):
        def body():
            try:
                inst = self.up.connect()
                self.q.put(("installed", inst))
            except Exception as e:
                self.up.close_port()
                self.ui.log("Connect failed: %s" % e, "error")
                self.ui.stage("connect", "error", "Couldn’t connect. Close any other program using the "
                              "Pico (Thonny) and try again — or, if it won’t connect at all, put it in "
                              "BOOTSEL mode by hand (hold BOOTSEL while plugging in USB) and press Start.")
        self.work(body)

    def start(self):
        m = self.up.manifest
        if self.busy or not m or not m.get("uf2"):
            return
        wipe, rom = self.opt_wipe.get(), self.opt_rom.get()
        if not self.up.port:
            if not core.find_drive():
                messagebox.showinfo("TS-Pico Updater", "Connect to the TS-Pico first — or put it in "
                                    "BOOTSEL mode by hand (hold BOOTSEL while plugging in USB, so the "
                                    "RPI-RP2 drive shows) and press Start again.")
                return
        if wipe and not messagebox.askokcancel(
                "TS-Pico Updater",
                "This erases everything on the Pico — firmware and files — and installs firmware %s. "
                "Nothing on the TS-2068, SD card or EXROM is touched%s\n\nContinue?" % (
                    m["fw_version"], " except the ROM update you asked for." if rom else ".")):
            return

        def body():
            text = self.up.downgrade_text(wipe)
            if text:
                self.ui.log("MicroPython downgrade ahead.", "warn")
                if not self.ui.confirm(text):
                    return
            self.q.put(("running",))
            if self.up.run(wipe, rom):
                self.q.put(("alldone", m["fw_version"]))
        self.work(body)

    # --- the Tk side --------------------------------------------------------
    def pump(self):
        try:
            while True:
                self.handle(*self.q.get_nowait())
        except queue.Empty:
            pass
        self.root.after(50, self.pump)

    def handle(self, kind, *a):
        if kind == "log":
            msg, k = a
            self.log.configure(state="normal")
            self.log.insert("end", msg + "\n", k or ())
            self.log.see("end")
            self.log.configure(state="disabled")
        elif kind == "stage":
            name, state, msg = a
            mark, label = self.rows[name]
            mark.configure(text=MARKS[state], fg=COLOURS[state])
            if msg is not None:
                label.configure(text=msg)
            if state != "active":
                self.bar["value"] = 0
        elif kind == "stage_msg":
            self.rows[a[0]][1].configure(text=a[1])
        elif kind == "progress":
            self.bar["value"] = int(min(1, a[1]) * 1000)
        elif kind == "rom_steps":
            if a[0]:
                self.romf.pack(fill="x", before=self.actions, pady=(6, 0))
            else:
                self.romf.pack_forget()
        elif kind == "rom_status":
            self.rom_status.configure(text=a[0], fg=LOG_COLOURS.get(a[1], "#1565c0"))
        elif kind == "actions":
            for w in self.actions.winfo_children():
                w.destroy()
            for label, value in a[0]:
                ttk.Button(self.actions, text=label,
                           command=lambda v=value: (self.ui.choices.put(v), self.handle("actions", []))
                           ).pack(side="left", padx=(0, 6))
        elif kind == "confirm":
            text, done, box = a
            box["ok"] = messagebox.askokcancel("TS-Pico Updater", text)
            done.set()
        elif kind == "chlabel":
            c, text = a
            if text:
                self.ch_buttons[c].configure(text=text, state="normal")
            else:
                self.ch_buttons[c].configure(state="disabled")
        elif kind == "channel":
            c, m = a
            self.ch.set(c)
            self.latest.configure(text="Latest: %s%s" % (
                m.get("fw_version", "?"), " (TS-2068 ROM %s)" % m["rom_version"] if m.get("rom_version") else ""))
            if self.up.installed and m.get("upgrade_uf2"):
                self.opt_rom.set(self.up.rom_behind())
        elif kind == "installed":
            inst = a[0]
            self.installed.configure(text="Installed: %s" % inst["fw"])
            m = self.up.manifest
            if m and m.get("upgrade_uf2"):
                self.opt_rom.set(self.up.rom_behind())
        elif kind == "running":
            self.set_stages_pending()
        elif kind == "alldone":
            self.installed.configure(text="Installed: %s" % a[0])
            messagebox.showinfo("TS-Pico Updater", "All done. The TS-Pico is on firmware %s.\n\n"
                                "You can unplug the USB cable and turn the TS-2068 on." % a[0])
        elif kind == "idle":
            self.busy = False
        self.refresh()

    def set_stages_pending(self):
        for s in core.STAGES:
            if s == "connect" and self.up.installed:
                continue                         # keep "Connected. Installed: ..."
            mark, label = self.rows[s]
            mark.configure(text=MARKS["pending"], fg=COLOURS["pending"])
            label.configure(text="")

    def refresh(self):
        m = self.up.manifest
        rom = self.opt_rom.get()
        if rom:
            self.opt_wipe.set(True)              # the upgrade UF2 needs an empty filesystem
        problem = ""
        if not m:
            problem = "No payload loaded yet."
        elif not m.get("uf2"):
            problem = "This channel has no firmware image. Pick the other channel."
        elif rom and not m.get("upgrade_uf2"):
            problem = ("This channel has no ROM updater (upgrade.uf2). Pick “Latest main build”, "
                       "or untick the ROM update.")
        idle = not self.busy
        self.btn_start.state(["!disabled"] if idle and not problem else ["disabled"])
        self.btn_connect.state(["!disabled"] if idle and not self.up.port else ["disabled"])
        self.btn_connect.configure(text="Connected" if self.up.port else "Connect to TS-Pico")
        self.cb_rom.state(["!disabled"] if idle and m and m.get("upgrade_uf2") else ["disabled"])
        self.cb_wipe.state(["!disabled"] if idle and not rom else ["disabled"])
        for c, b in self.ch_buttons.items():
            b.state(["!disabled"] if idle and c in self.manifests else ["disabled"])
        inst = self.up.installed
        if problem:
            text, colour = problem, "#b26a00"
        elif inst and inst["from1x"] and not rom:
            text, colour = ("This board is on %s. Its TS-2068 ROM can't talk to firmware %s — tick "
                            "“Update the TS-2068 ROM” or the 2068 won't work afterwards." % (
                                inst["fw"], m["fw_version"])), "#b26a00"
        elif not rom and self.up.rom_behind():
            text, colour = ("This board is on %s, so its TS-2068 ROM is probably older than ROM %s. "
                            "Tick “Update the TS-2068 ROM” to install it with the firmware." % (
                                inst["fw"], m.get("rom_version") or m["fw_version"])), "#b26a00"
        else:
            steps = []
            if self.opt_wipe.get():
                steps.append("erase the Pico")
            if rom:
                steps.append("update the TS-2068 ROM (you’ll type two commands on the 2068)")
            steps += ["install firmware %s" % m["fw_version"], "copy its files"]
            text, colour = ("Start will " + ", then ".join(steps) +
                            ". Keep the USB cable connected throughout."), "#333"
        self.hint.configure(text=text, foreground=colour)


def main():
    ap = argparse.ArgumentParser(description="TS-Pico Updater")
    ap.add_argument("--channel", choices=core.CHANNELS, default="release")
    ap.add_argument("--base", default=core.SITE,
                    help="the published /updater/ directory: a URL or a local folder")
    args = ap.parse_args()
    root = tk.Tk()
    App(root, args.base, args.channel)
    root.mainloop()


if __name__ == "__main__":
    main()
