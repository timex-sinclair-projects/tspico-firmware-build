"""TS-Pico Updater -- the window.

A tkinter front end for core.Updater: Connect, Start. A v2 board is always
erased and gets the ROM update (the firmware needs its matching ROM); the v3
card never is (core.Updater.run). The only option is the v3 card's modem. The run happens on a worker thread; it reaches the window only
through the queue below, which the Tk loop drains every 50 ms.

    TS-Pico-Updater.exe [--channel main] [--base URL-or-folder]

--channel main installs the latest main build instead of the release, for
testing; the window offers no choice. --base points at another copy of the published /updater/ directory -- a local
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
    "modem": "Modem firmware",
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

        root.title("TS-Pico Updater")
        root.minsize(640, 600)
        outer = ttk.Frame(root, padding=12)
        outer.pack(fill="both", expand=True)

        ttk.Label(outer, text="TS-Pico Updater", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Install or upgrade the TS-Pico firmware over USB.",
                  foreground="#555").pack(anchor="w", pady=(0, 8))

        top = ttk.Frame(outer)
        top.pack(fill="x")
        vf = ttk.LabelFrame(top, text="Versions", padding=8)
        vf.pack(side="left", fill="both", expand=True)
        self.latest = ttk.Label(vf, text="Latest: …")
        self.latest.pack(anchor="w")
        self.installed = ttk.Label(vf, text="Installed: not connected")
        self.installed.pack(anchor="w")

        opts = ttk.Frame(outer, padding=(0, 8))
        opts.pack(fill="x")
        self.btn_connect = ttk.Button(opts, text="Connect to TS-Pico", command=self.connect)
        self.btn_connect.pack(side="left")
        # The v3 card's modem: shown once a v3 card is known and the channel
        # has Zimodem for it (refresh).
        self.opt_modem = tk.BooleanVar(value=True)
        self.cb_modem = ttk.Checkbutton(opts, text="Modem firmware", variable=self.opt_modem,
                                        command=self.refresh)
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
        self.work(self._load_channel, want)

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

    def _load_channel(self, c):
        try:
            m = self.up.load_channel(c)
        except Exception as e:
            self.ui.log("Could not load %s: %s. Check the internet connection and restart." % (c, e),
                        "error")
            return
        self.q.put(("channel", c, m))

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
        if self.busy or not m:
            return
        if not self.up.port:
            d = core.find_drive()
            if not d:
                messagebox.showinfo("TS-Pico Updater", "Connect to the TS-Pico first — or put it in "
                                    "BOOTSEL mode by hand (hold BOOTSEL while plugging in USB, so the "
                                    "RPI-RP2 drive shows, or RP2350 on the v3 card) and press Start again.")
                return
            if core.drive_chip(d) == "RP2350":
                self.up.board = "v3"
                self.refresh()
        if not self.up.image()[0]:
            return
        wipe = rom = not self.up.v3
        modem = self.opt_modem.get()
        if wipe and not messagebox.askokcancel(
                "TS-Pico Updater",
                "This erases everything on the Pico — firmware and files — and installs firmware %s. "
                "Nothing on the TS-2068, SD card or EXROM is touched, except that the TS-2068 ROM is "
                "updated.\n\nContinue?" % m["fw_version"]):
            return

        def body():
            text = self.up.downgrade_text(wipe)
            if text:
                self.ui.log("MicroPython downgrade ahead.", "warn")
                if not self.ui.confirm(text):
                    return
            self.q.put(("running",))
            if self.up.run(wipe, rom, modem):
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
        elif kind == "channel":
            c, m = a
            self.latest.configure(text="Latest: %s%s" % (
                m.get("fw_version", "?"), " (TS-2068 ROM %s)" % m["rom_version"] if m.get("rom_version") else ""))
        elif kind == "installed":
            inst = a[0]
            self.installed.configure(text="Installed: %s" % inst["fw"])
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
        v3 = self.up.v3                          # its ROM slots are files: never wiped, no ROM step
        problem = ""
        if not m:
            problem = "No payload loaded yet."
        elif v3 and not m.get("v3"):
            problem = "This release has nothing for the v3 card."
        elif not v3 and not m.get("uf2"):
            problem = "This release has no firmware image."
        elif not v3 and not m.get("upgrade_uf2"):
            problem = "This release has no ROM updater (upgrade.uf2)."
        idle = not self.busy
        zim = v3 and bool(self.up.zimodem())
        if zim and not self.cb_modem.winfo_manager():
            self.cb_modem.pack(side="left", padx=(12, 0), after=self.btn_connect)
        elif not zim:
            self.cb_modem.pack_forget()
        self.cb_modem.state(["!disabled"] if idle else ["disabled"])
        self.btn_start.state(["!disabled"] if idle and not problem else ["disabled"])
        self.btn_connect.state(["!disabled"] if idle and not self.up.port else ["disabled"])
        self.btn_connect.configure(text="Connected" if self.up.port else "Connect to TS-Pico")
        if problem:
            text, colour = problem, "#b26a00"
        elif v3:
            text, colour = ("Start will install firmware %s for the v3 card, then copy its files and "
                            "its ROM slots. Slots 0 and 1 (the Spectrum and TS-Pico ROMs) are always "
                            "replaced; your own ROMs and cartridges in the other slots are kept. "
                            "Nothing is erased.%s Keep the USB cable connected throughout." % (
                                m["fw_version"],
                                " Then it checks the Zimodem on the card's WiFi modem module and "
                                "installs %s if it's missing or older; its WiFi and phonebook "
                                "settings are kept." % (self.up.zimodem().get("version") or "this release's")
                                if zim and self.opt_modem.get() else "")), "#333"
        else:
            text, colour = ("Start will erase the Pico, then update the TS-2068 ROM (you’ll type two "
                            "commands on the 2068), then install firmware %s, then copy its files. "
                            "Keep the USB cable connected throughout." % m["fw_version"]), "#333"
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
