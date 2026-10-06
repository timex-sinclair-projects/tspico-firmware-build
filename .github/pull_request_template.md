## What and why

<!-- What changed, and why. Link the issue it fixes. -->

## Checklist

For a change under `src/`, `flash/`, the ROM build tools or the workflows
(skip what does not apply):

- [ ] The matching chapter in [`docs/reference/`](../docs/reference/README.md) says the new behaviour: entries added, changed or removed
- [ ] The flows and appendices the stamp table lists for each changed source re-read, and fixed where they changed
- [ ] Line numbers the chapters cite moved with the code (`reference_hosttest.py --relines <source>`, checked, before re-stamping)
- [ ] Stamps refreshed (`python3 src/test/reference_hosttest.py --stamp`) **only** for chapters I re-read; the index regenerated (`--index`); the test prints `ALL PASS`
- [ ] A fixed `reference-followup` issue: the chapters that cite it updated
- [ ] `docs/PROTOCOL.md` and the manuals updated if the wire protocol or what users see changed
- [ ] Tested on hardware, or said why not

The full routine is in [`src/CLAUDE.md`](../src/CLAUDE.md), "Keeping docs/reference/ current".
