---
layout: post
title: "The Manuals and the Programmer's Reference, on the Site"
lang: en
date: 2026-10-06 07:00:00 -0400
---

The TS-Pico's documentation now lives on this site, under
[Docs]({{ '/docs/' | relative_url }}) in the menu. There are three documents, each written for
a different reader.

**The [User Manual]({{ '/manual/user-manual.html' | relative_url }})** is for everyone with a
TS-Pico. It covers setting it up, loading and saving from the SD card, the disk commands
(CAT, MOVE, ERASE and FORMAT), `f:` files and `OPEN #` channels, and every `tpi:` command
with the messages it gives. It also covers the virtual printer, Spectrum mode, and updating
with the [web updater]({{ site.updater_url | relative_url }}).

**The [Programmer's Manual]({{ '/manual/programmers-manual.html' | relative_url }})** is a
tutorial for writing TS-2068 machine code that talks to the TS-Pico: the two ports, the
protocol, the ROM's BIOS table, and how to add a `tpi:` command of your own on the Pico. Its
examples assemble and run.

**The [Programmer's Reference]({{ '/reference/' | relative_url }})** is for anyone who wants to
change the platform. It explains the firmware and the ROM down to every function, variable,
PIO instruction and ROM routine: what each one does, why it exists, what it touches and what
will break if you change it. Each chapter follows one source file in order, so you can read
them side by side. The flows follow one operation, such as a LOAD, a SAVE or a BREAK, from the
BASIC keyword to the SD card and back. An index lists every symbol.

The reference is checked against the code. Every change to the firmware or the ROM updates its
chapter in the same pull request, and the project's tests fail until it does. Writing it turned
up two dozen places where the code didn't do what its comments or the manuals said, and most
of the fixes are in [TS-Pico 2.2]({% post_url 2026-10-06-ts-pico-2-2 %}).

The pages are built from the project's repository every time the site updates, so they always
match the current code on `main`. Each page links to its source file on GitHub. If something
reads wrong or is missing, open an
[issue on GitHub]({{ site.github_repo }}/issues).
