# Open questions for the team

Catch-all for low-traffic "we should think about this someday" items.
**For anything with a real decision path, open a GitHub issue instead** —
issues notify the team, support discussion threads, are linkable from
PRs, and have a real status field that doesn't drift.

This file is for items that aren't quite issue-worthy yet (vague hunches,
half-formed ideas, things waiting for more data before they can be
articulated as a concrete question).

Add new entries at the top. When something graduates to a GitHub issue,
remove it from here and link the issue.

---

## Open

*(none currently)*

---

## Graduated to GitHub issues

- **Should we implement true CRC verification on incoming messages?** —
  [#2](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/2)
- **Write developer onboarding guide (env setup, mpy generation, etc.)** —
  [#6](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/6)
- **SEND_MSG2 intermittent failure / TX FIFO underflow / blank-screen
  keypress wait** (originally filed here as "blank-screen-then-keypress-wait
  for short messages"; investigation showed it's the same race that makes
  `tpi:help border` hang under the buffer-prebuild refactor) —
  [#7](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/7)
- **Extension command (extcmd) protocol incompatible with dual-port V6
  pre-load chain** — design analysis in
  [`docs/EXTCMD_PROTOCOL.md`](EXTCMD_PROTOCOL.md), tracker at
  [#8](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/8)
- **ZX48 exit-by-byte unreachable: `OUT 10,100` doesn't reach the Pico
  (port `$0A` not routed through PICOSEL)** —
  [#9](https://github.com/timex-sinclair-projects/tspico-firmware-build/issues/9)

---

## Resolved

*(none yet)*
