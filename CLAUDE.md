# TS-Pico firmware build — orientation

Read [`src/CLAUDE.md`](src/CLAUDE.md) first: the working style, the
harness-first rule, the GitHub workflow and the gotchas. This file adds the
one rule that spans the whole repo.

## The programmer's reference is part of the code

[`docs/reference/`](docs/reference/README.md) explains the firmware and the
ROM down to every function, variable, PIO instruction and ROM routine: what
each does, why it exists, what it touches. It is only worth having while it
is true, so:

- **A change under `src/` (the firmware, `config.ini`, the ROM sources and
  images, the upgrade payload), under `flash/`, in a build tool the
  reference lists, or in the CI workflows changes the matching chapter in
  the same PR.** A new function, variable, `tpi:` command or ROM label gets
  a new entry. Changed behaviour: the entry says the new behaviour and, if
  the reason changed, the new reason. A removed symbol: its entry goes.
  The flows and appendices the stamp row lists for that source get the
  same re-read: they follow operations across files, so a change in one
  file can make a flow wrong without touching any entry.
- **A fix for a `reference-followup` issue updates the chapters that cite
  it.** The caveat and the issue link go; the entry says the new behaviour.
- **Then re-stamp and re-index.** `python3 src/test/reference_hosttest.py`
  fails CI until every symbol has an entry, every changed source has a fresh
  row in the stamp table in `docs/reference/README.md` (`--stamp` prints
  the rows) and `docs/reference/appendix/index.md` is regenerated
  (`--index`).
- **A new stamp is a claim that you re-read the chapter against the
  change.** Don't paste a new hash over a chapter you didn't check. If you
  can't say what a change means for the explanation, say so in the PR.
- The entry format and the voice are in the README's "Conventions": entries
  in source order, facts from the code, inferences marked.

This binds AI agents as much as people. An agent that edits firmware and
reports "done" without touching `docs/reference/` has not finished.
