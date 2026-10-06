---
layout: page
title: Documentation
lang: en
description: The TS-Pico user manual, the programmer's manual and the programmer's reference.
---

Everything here is published from the project's repository as it is on `main`, so it follows
the firmware and the ROM as they change.

## For TS-Pico owners

**[User Manual]({{ '/manual/user-manual.html' | relative_url }})** — setting up the TS-Pico,
loading and saving from the SD card, the disk commands (CAT, MOVE, ERASE, FORMAT), `f:` files
and `OPEN #` channels, every `tpi:` command, the printer, Spectrum mode, and updating with the
[web updater]({{ site.updater_url | relative_url }}).

## For programmers

**[Programmer's Manual]({{ '/manual/programmers-manual.html' | relative_url }})** — machine
code for the TS-2068 that talks to the TS-Pico: the ports and the protocol, the ROM's BIOS
table, and new `tpi:` commands for the Pico, with worked examples.

**[Programmer's Reference]({{ '/reference/' | relative_url }})** — the firmware and the ROM
explained function by function: what each routine, variable, PIO program and ROM label does,
why it exists and what it touches. It is checked against the source on every change, so it is
the place to start before changing the platform.

The source, the release notes and the issue tracker are on
[GitHub]({{ site.github_repo }}).
