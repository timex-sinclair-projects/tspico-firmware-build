#!/usr/bin/env python3
"""Step 2: take the tapes out of the zips, drop duplicates, and give each a
folder and a short name.

    python3 tools/sd-archive/plan.py

A zip's .tap files are used; with none, its .tzx (tzxtap), else its .wav
(tzxwav, then tzxtap). A ".tap" that is really a TZX is converted, and zero
padding after the last block is dropped. Writes taps/<sha>.tap, plan.json and
skipped.json in the work folder. Needs tzxtools (pip install tzxtools).
"""

import collections
import hashlib
import os
import re
import shutil
import subprocess
import unicodedata
import urllib.parse
import zipfile

import common as C

# Category folder from the page's tags, first match wins.
FOLDERS = [
    ("COLLECT", {"Collection", "Magazine"}),
    ("ARCADE", {"Arcade"}),
    ("GAMES", {"Game", "Card Game", "Chess", "Text Adventure", "Strategy", "Gambling", "Dice",
               "Simulation", "Entertainment", "Artificial Intelligence"}),
    ("EDUCATE", {"Education", "Teaching", "Tutorial", "Mathematics", "Science", "Astronomy",
                 "Spanish", "French", "Weather"}),
    ("MUSIC", {"Music", "Sound", "Speech", "Speech Synthesis", "Speech Recognition"}),
    ("HOME", {"Home", "Finance", "Business", "Tax", "Stocks", "Database", "Spreadsheet", "Calendar",
              "Clock", "Holiday", "Word Processor", "Desktop Publishing", "Hobby", "Resource Management"}),
    ("GRAPHICS", {"Graphics", "Art", "Animation", "Clip Art", "3D", "User Defined Graphics", "Font",
                  "Banner", "Photography"}),
    ("UTILITY", {"Utility", "Programming", "Machine Language", "Renumber", "Compiler",
                 "Forth (programming language)", "Pascal (programming language)", "Tape",
                 "Tape Directory", "Header", "ROM", "RAM", "DOS", "Disk Drive Systems", "64 Column",
                 "Terminal", "Modem", "BBS", "Ham Radio", "Electronics", "Engineering", "Joystick",
                 "Printer", "Emulation"}),
    ("DEMOS", {"Demo"}),
]
UNTAGGED = {"Dam Buster": "ARCADE", "DROP-OUT": "ARCADE", "Night Gunner": "ARCADE", "Penetrator": "ARCADE",
            "Simple Roulette": "GAMES", "WUMPUS": "GAMES", "DevPac": "UTILITY", "Zeus Disassembler": "UTILITY",
            "MTerm II": "UTILITY", "SpectraTERM 1.0": "UTILITY", "Spectrum Emulator Code": "UTILITY",
            "Print and Copy IBM": "UTILITY", "SuperCheck": "UTILITY", "Multi-Draw 2068": "GRAPHICS",
            "Random Colors": "GRAPHICS", "Notes": "HOME", "Omnicalc 2": "HOME", "Tasword II": "HOME"}

# A zip with three or more tapes gets its own subfolder, named from the zip.
SUBFOLDERS = [
    (r"Byte Power - Issue (\d+)", r"BPOWER\1"),
    (r"CATS Library Tape (\d+)", r"CATS\1"),
    (r"CATUG Tape [\d.]+ 0*(\d+)", r"CATUG\1"),
    (r"ISTUG Public Domain Library (\d+)", r"ISTUG\1"),
    (r"LIST LIB (\d+)", r"LIST\1"),
    (r"ListLib_(\d+)\.(\d+)", r"LIST\1\2"),
    (r"SINCUS Exchange Tape (\d+)", r"SINC\1"),
    (r"Timex Sinclair Public Domain Library Tape (\d+)", r"TSPD\1"),
    (r"TS2068 Club Library Tape", "FWCLUB"),
    (r"TS2068 Computer Programs", "IMREPGMS"),
    (r"(?i)zxzine ?(\d+)", r"ZXZINE\1"),
    (r"Banner Designer", "BANNERDS"),
    (r"BBSs", "BBS"),
    (r"Electronics Pgms", "ELECTRON"),
    (r"Entry", "ENTRY"),
    (r"HOT Z Disassembler", "HOTZ"),
    (r"Machine Code Tutor", "MCTUTOR"),
    (r"VU-Calc 80 Col", "VUCALC80"),
    (r"(?i)ecmview", "ECMVIEW"),
    (r"MiscPgms", "MISCPGMS"),
]

STOP = {"the", "a", "an", "of", "and", "for", "to", "in", "ts", "2068", "ts2068", "tape", "side",
        "program", "programs", "by", "with", "version", "v"}


def folder_for(it):
    tags = {t.strip() for t in it["tags"].split(",") if t.strip()}
    for f, s in FOLDERS:
        if tags & s:
            return f
    return UNTAGGED.get(it["title"], "MISC")


def words(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s)
    s = re.sub(r"\.(tap|tzx|wav)$", "", s, flags=re.I)
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    w = [x.lower() for x in re.split(r"[^A-Za-z0-9]+", s) if x]
    return [x for x in w if x not in STOP] or w or ["prog"]


def short(s, n=8, keepnum=False):
    """An n-letter name: 'Capitalization Master' -> 'capimast'. keepnum keeps a
    trailing number: 'CATS Library Tape 8' -> 'catslib8'."""
    w = words(s)
    while len(w) > 1 and w[0].isdigit():        # leading track numbers ("05-ON ERROR")
        w = w[1:]
    num = ""
    if keepnum:
        nums = [x for x in w if x.isdigit() and len(x.lstrip("0") or "0") <= 3]
        if nums:
            w = [x for x in w if not x.isdigit()] or ["n"]
            num = nums[-1].lstrip("0") or "0"
    n -= len(num)
    j = "".join(w)
    if len(j) <= n:
        return j + num
    if len(w) == 1:
        return j[:n] + num
    out = w[0][:max(n - 3 * (len(w) - 1), 4)]  # the first word gets the most
    for x in w[1:]:
        room = n - len(out)
        if room <= 0:
            break
        out += x[:min(room, 4 if x.isalpha() else len(x))]
    return out[:n] + num


def subfolder(zipname):
    base = zipname.split("(")[0]
    for pat, rep in SUBFOLDERS:
        m = re.search(pat, zipname)
        if m:
            return m.expand(rep)
    return short(base, 8, True).upper()


def tzx_to_tap(data, tag):
    p, out = C.work("conv", tag + ".tzx"), C.work("conv", tag + ".tap")
    with open(p, "wb") as f:
        f.write(data)
    r = subprocess.run(["tzxtap", p, "-i", "-o", out], capture_output=True)
    return C.read(out) if r.returncode == 0 and os.path.exists(out) else None


def wav_to_tap(data, tag):
    p, tz = C.work("conv", tag + ".wav"), C.work("conv", tag + "_w.tzx")
    with open(p, "wb") as f:
        f.write(data)
    r = subprocess.run(["tzxwav", p, "-o", tz], capture_output=True)
    os.remove(p)
    if r.returncode or not os.path.exists(tz):
        return None
    return tzx_to_tap(C.read(tz), tag + "_w")


def clean_tap(d, tag):
    """(tap bytes or None, what was done)."""
    if d.startswith(b"ZXTape!"):
        c = tzx_to_tap(d, tag)
        return (c, "tzx-named-tap") if c else (None, "a TZX named .tap that tzxtap can't convert")
    i = 0
    while i + 2 <= len(d):
        ln = d[i] | d[i + 1] << 8
        if ln == 0:
            return (d[:i], "trailing zeros dropped") if not d[i:].strip(b"\x00") else (d, "")
        i += 2 + ln
    return d, ""


def members(z):
    return [n for n in z.namelist() if "__MACOSX" not in n and not os.path.basename(n).startswith("._")
            and not n.endswith("/")]


def tapes_in(z, tag):
    """[(member, tap bytes)], and where they came from: tap / tzx / wav."""
    mem = members(z)
    taps = [n for n in mem if n.lower().endswith(".tap")]
    # The firmware writes its own dirinfo.tap; LarKen-disk (lkdos/) copies
    # are fragments of a tape that's also there whole.
    taps = [n for n in taps if os.path.basename(n).lower() != "dirinfo.tap"]
    if any("/lkdos/" not in n.lower() for n in taps):
        taps = [n for n in taps if "/lkdos/" not in n.lower()]
    if taps:
        return [(n, z.read(n)) for n in taps], "tap"
    for ext, conv in ((".tzx", tzx_to_tap), (".wav", wav_to_tap)):
        got = []
        for k, n in enumerate(x for x in mem if x.lower().endswith(ext)):
            d = conv(z.read(n), "%s_%d" % (tag, k))
            if d:
                got.append((n, d))
        if got:
            return got, ext[1:]
    return [], ""


def main():
    items = C.load("items.json")
    urlmap = C.load("urlmap.json")
    shutil.rmtree(C.work("conv"), ignore_errors=True)
    os.makedirs(C.work("conv"))
    os.makedirs(C.work("taps"), exist_ok=True)
    plan, seen, skipped, used = [], {}, [], {}

    def uniq(folder, base, n=8):
        s = used.setdefault(folder, set())
        name, k = base, 1
        while name in s:
            k += 1
            name = base[:n - len(str(k))] + str(k)
        s.add(name)
        return name

    for it in sorted(items, key=lambda x: x["title"].lower()):
        for url in it["downloads"]:
            u = C.zip_url(url)
            zp = urlmap.get(u)
            if not zp or not os.path.exists(zp):
                skipped.append((it["title"], "not downloaded"))
                continue
            zipname = urllib.parse.unquote(u.rsplit("/", 1)[1])
            z = zipfile.ZipFile(zp)
            got, src = tapes_in(z, hashlib.md5(zp.encode()).hexdigest()[:8])
            if not got:
                exts = sorted({os.path.splitext(n)[1].lower() for n in members(z)})
                skipped.append((it["title"], "no tape (%s)" % " ".join(exts)))
                continue
            folder = folder_for(it)
            got.sort(key=lambda x: x[0].lower())
            if len(got) > 2:
                folder += "/" + uniq(folder, subfolder(zipname))
            for k, (n, d) in enumerate(got):
                d, how = clean_tap(d, hashlib.md5((zp + n).encode()).hexdigest()[:8])
                if not d:
                    skipped.append((it["title"] + " / " + n, how))
                    continue
                h = hashlib.sha1(d).hexdigest()
                if h in seen:
                    seen[h]["also"].append(it["title"])
                    continue
                if len(got) == 1:
                    base = short(it["title"])
                elif len(got) == 2:             # two parts: their own names, else title + 1/2
                    fb = [short(os.path.basename(x[0])) for x in got]
                    base = fb[k] if fb[0] != fb[1] else short(it["title"], 7) + str(k + 1)
                else:
                    base = short(os.path.basename(n))
                with open(C.tap_path(h), "wb") as f:
                    f.write(d)
                e = dict(title=it["title"], page=it["page"], tags=it["tags"], member=n, zip=zipname,
                         url=u, zip_file=zp, src="tzx" if how == "tzx-named-tap" else src, fix=how,
                         folder=folder, name=uniq(folder, base) + ".tap", sha1=h, also=[])
                seen[h] = e
                plan.append(e)

    C.save("plan.json", plan)
    C.save("skipped.json", skipped)
    print(len(plan), "tapes;", len(skipped), "skipped")
    print(dict(collections.Counter(e["folder"].split("/")[0] for e in plan)))
    print(dict(collections.Counter(s[1].split(" (")[0] for s in skipped)))


if __name__ == "__main__":
    main()
