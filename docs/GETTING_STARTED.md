# Getting started

A short orientation for new contributors. Covers both:

- **Hand-coders** — editing files in your editor of choice, building
  + uploading to the Pico, opening PRs through the usual git
  workflow.
- **Claude-assisted coders** — using
  [Claude Code](https://claude.com/claude-code) to drive edits,
  builds, PRs, and releases.

Most of the setup is the same either way; the two paths diverge in
how you spend a typical working hour. Read §§1–4 first regardless,
then jump to the section that matches your path.

---

## 1. What is TS-Pico?

A Raspberry-Pi-Pico-based storage interface for the Timex Sinclair
TS-2068. Two firmware halves talk to each other: a modified TS-2068
EXROM (Z80 side, owned by Gustavo) and MicroPython running on the
Pico (this repo, Pico-side lead: Ricardo). The protocol between
them is called TPI.

Background reading (in order, when you're ready):
[`GUSTAVO_PROTOCOL.md`](GUSTAVO_PROTOCOL.md) →
[`PROTOCOL.md`](PROTOCOL.md) →
[`DUAL_PORT_DEVELOPMENT.md`](DUAL_PORT_DEVELOPMENT.md).

## 2. Tools you'll need

| Tool | Why | Path |
|---|---|---|
| `gh` CLI | PRs, issues, release artifacts | both |
| Thonny | Editor / file-transfer to the Pico over USB | both |
| `mpy-cross` v1.20.* | Pre-compile `src/dev_tspico.py` to `.mpy` | both |
| Claude Code | AI-assisted editing | Claude path only |

```bash
# macOS
brew install gh thonny
pip install --user mpy-cross==1.20.*

# Authenticate gh once
gh auth login    # GitHub.com → HTTPS → browser-based

# Verify
gh repo view timex-sinclair-projects/tspico-firmware-build
mpy-cross --version    # should report mpy v6.1 for MP 1.20.0
```

For Claude Code: install per
[claude.com/claude-code](https://claude.com/claude-code), then run
`claude` in your repo directory.

## 3. Clone and orient

```bash
gh repo clone timex-sinclair-projects/tspico-firmware-build
cd tspico-firmware-build
```

Four top-level areas:

| Folder | What's in it |
|---|---|
| `README.md` | Project overview + deploy steps |
| `docs/` | Protocol, architecture, dev guides (this file lives here) |
| `archive/` | Historical reference material |
| `src/` | Everything that ends up on the Pico — firmware sources, flash content, the Z80 EXROM image |
| `SD card/` | Everything that ends up on the user's SD card — TAP library, `tpi:help` text |

The split between `src/` and `SD card/` is the deploy boundary.
File goes on the Pico's flash? It's under `src/`. File goes on the
SD card? It's under `SD card/`.

[`src/CLAUDE.md`](../src/CLAUDE.md) holds the firmware-side
conventions (PIO ↔ MicroPython "ready" contract, harness-first
debugging, byte-in-buffer-before-asserting-ready). Claude Code
auto-loads it when you work under `src/`; read it manually if
you're hand-coding.

## 4. The workflow

Every change goes through a branch + PR cycle, regardless of which
path you're on:

1. **Branch off `main`:**
   ```bash
   git checkout main && git pull
   git checkout -b descriptive-name
   ```

2. **Make the change.** For firmware tweaks the usual file is
   `src/dev_tspico.py` (the dev override) — see §6 for the
   iteration loop.

3. **Push early.** Every branch push triggers `build.yml`, which
   produces a `firmware.uf2` artifact on the Actions tab. You can
   flash that to the Pico without waiting for review.

4. **Open a PR** with a Summary / Test plan body. Reference the
   issue it closes if any.

5. **Squash-merge** after the change is confirmed on hardware. The
   per-iteration commits collapse into a single landing commit on
   `main`.

6. **Cleanup.** If the repo's auto-delete-on-merge isn't on, delete
   the branch by hand and `git remote prune origin`.

Releases: `git tag vX.Y.Z && git push --tags`. `release.yml` builds
the firmware fresh, assembles the bundle (UF2 + `src/` + `SD card/`),
and publishes a GitHub Release.

---

## 5. Hand-coder path

You'll spend most of your time in:

- **Your editor** (VS Code, Vim, Emacs, whatever) editing
  `src/dev_tspico.py` and the files under `src/TS/`.
- **A terminal** for `git`, `gh`, and `./src/build-dev-mpy.sh`.
- **Thonny** for uploading `.mpy` files to the Pico and watching
  the REPL.

Read [`docs/DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) next — it's
the comprehensive hand-coder onboarding. It covers:

- Host setup details (Thonny, mpy-cross version matching)
- Getting the Pico into a known state (flashing the UF2)
- Deploy targets (Pico flash, EXROM, SD card)
- The `.mpy` build flow and why it's mandatory for `dev_tspico.py`
- The dev-override pattern (`/dev_tspico.mpy` shadowing
  `TS.tspico`)
- The `/TS/` shadowing trap (the one gotcha that wastes the most
  time)
- The PIO ↔ MicroPython ready contract
- Harness-first methodology for protocol bugs
- Common debugging recipes

Read [`src/CLAUDE.md`](../src/CLAUDE.md) too. Despite the name, the
conventions there apply to all contributors — not just the
Claude-Code workflow.

## 6. Claude-assisted path

Once Claude Code is installed and `gh` is authenticated (§2), `cd`
into the repo and run `claude`. Claude reads `README.md` and the
auto-loaded `src/CLAUDE.md` for context.

### Permissions worth allowlisting up front

Claude Code asks before running each new shell command. Allowlist
these early to avoid prompt fatigue:

| Command | Why |
|---|---|
| `gh pr ...`, `gh issue ...`, `gh release ...` | PR/issue/release management |
| `git push`, `git push origin --delete`, `git remote prune` | Branch push + cleanup |
| `mpy-cross`, `./src/build-dev-mpy.sh` | Compiling the dev override |

Use the `/fewer-permission-prompts` skill to scan your transcripts
and allowlist common read-only commands automatically.

**Don't allowlist without thought:**

- `git push --force` / `--force-with-lease` (use deliberately)
- `git reset --hard`, `git clean -f`, `git checkout --`
  (destructive)
- Anything with `--no-verify` / `--no-gpg-sign` (bypasses hooks)

### Iteration loop

The fast loop, no UF2 rebuild needed:

```bash
./src/build-dev-mpy.sh         # writes src/dev_tspico.mpy
# upload src/dev_tspico.mpy to the Pico's flash root via Thonny
# reset the Pico, test on the TS-2068
```

The dev override loads automatically if `/dev_tspico.mpy` is
present on the Pico's flash root. To revert: delete the file.

### Useful Claude Code skills

- `/code-review` — review the current diff
- `/verify` — manually verify a change behaves
- `/fewer-permission-prompts` — autoscan and allowlist
- `/init` — initialize a `CLAUDE.md` (we already have one)

---

## 7. Multi-session coordination

If two or more Claude Code sessions are working on this repo at the
same time (or two hand-coders, or one of each), the failure modes
are real. We hit several of them coordinating the SD-card reorg
(PR #29) with the web-updater work (PR #28). What follows is
practical advice from that experience.

### Pick distinct concerns per session

The single most useful rule. If session A is working on the
firmware (`src/TS/`, `src/dev_tspico.py`) and session B is working
on the web updater (`web-updater/`), they will rarely collide. If
both are touching `release.yml`, they will collide every time.

When you assign work to a session, name the **files** it owns.
Sessions don't see each other's intent — only commits that have
already landed.

### Start every session with a sync

Each session has its own working tree and its own idea of `main`'s
state. Before any new branch:

```bash
git checkout main
git fetch origin
git pull
```

A session that branches from a stale `main` will produce a PR with
a diff that confuses reviewers and conflicts with what's already
on `main`. We hit this when one session's working tree had files
from another session's open PR — the new branch silently inherited
those files, and the PR claimed credit for them.

If you're switching to a different session for a task, do a `git
status` first to confirm the working tree is clean. Stash or
commit anything in flight before you change focus.

### Tell each session what the other is doing

At the top of a session, give Claude a one-sentence prime:

> "Another session is working on the web-updater (`web-updater/`,
> PR #28). Don't touch those files; if you need to coordinate,
> leave a comment on the PR."

Sessions can't see each other directly but they *can* read GitHub
state (open PRs, recent commits) and the comments on those PRs.
Using the PR's comment thread as the shared bulletin board scales
better than telling the user to relay messages between sessions.

### When concerns overlap, decide who lands first

If both sessions must touch the same file, pick a landing order:

- **First session lands.** Its PR merges to `main`.
- **Second session rebases** onto the new `main` and re-applies
  its changes.

In our case the SD-card reorg PR #29 landed first; the web-updater
PR #28 then had to rebase and update `web-updater/build-payload.sh`
(which referenced the moved `src/help/` path). The PR-comment
hand-off ([example](https://github.com/timex-sinclair-projects/tspico-firmware-build/pull/28))
made the second rebase mechanical: the comment listed exactly what
changed and what fixes were needed.

### When a session creates a PR, write a coordination comment

If your PR will affect another session's open work, post a comment
on that other PR explaining:

1. What changed on `main` after your PR lands
2. What lines or files the other PR will need to update
3. The mechanical rebase steps (`git fetch`, `git rebase`, then…)

This costs you two minutes and saves the other session 30.

### Don't trust the working tree to reflect remote state

In the SD-card reorg, a session created a new branch via
`git checkout -b new-branch`. The session assumed it was branching
off `main`. It was actually branching off another session's open
PR branch, because the working tree had been left there. The
mistake wasn't caught until commit time, when the PR diff included
the other session's commits.

Defensive pattern:

```bash
git fetch origin
git checkout origin/main -B new-branch
# ↑ explicitly checkout origin/main as the base for the new branch
```

Or check the base after creating the branch:

```bash
git log --oneline origin/main..HEAD
# empty = you're correctly based on main; any commits = you inherited from elsewhere
```

### Use `.gitignore` to keep cross-session noise out

If one session generates files the other shouldn't commit (a
build output, an editor file, a payload directory), get them into
`.gitignore` early. Files that aren't gitignored but aren't yet
tracked are minefields when two sessions are active — each session
sees them as "untracked, presumably yours."

### Symptoms that mean you've crossed streams

- Your PR's diff contains commits or files you didn't write.
- `git status` shows files modified that you haven't touched in
  this session.
- `gh pr view` shows your PR has more commits than your session
  created.
- A workflow CI run fails on `main` after your merge because a
  file the other session deleted is referenced by code yours
  added.

When you see one of these, stop and reconcile before pushing
further. Soft-reset to the right base
(`git reset --soft origin/main`) and re-stage only what's yours.

---

## 8. Troubleshooting

**"gh: command not found"** — Install via your package manager
(`brew install gh`, `apt install gh`). Then `gh auth login`.

**"Permission denied (publickey)" on `git push`** — You cloned via
SSH but haven't added a key. Either add an SSH key on GitHub, or
switch the remote to HTTPS:
`git remote set-url origin https://github.com/.../...`.

**"gh: not authenticated"** — `gh auth login`, follow browser
prompts.

**Claude Code prompts for every command, slowly** —
`/fewer-permission-prompts` to scan recent transcripts and
allowlist read-only commands.

**Pre-commit hook fails** — Investigate the failure rather than
bypassing with `--no-verify`. If the hook is broken, fix the
hook.

**`MemoryError` at boot when loading dev_tspico** — You uploaded
the `.py` instead of the `.mpy`. The Pico's parser runs out of
memory on `dev_tspico.py` directly; you must build the `.mpy` with
`./src/build-dev-mpy.sh` and upload that.

**Boot says it loaded the frozen TS.tspico, not your dev override**
— You forgot to upload `dev_tspico.mpy` to the Pico's flash root,
OR there's both a `.py` and a `.mpy` and the import order isn't
what you want. Delete both, upload only the `.mpy`.

**Tests passed but real-hardware test fails** — Read
[`docs/DUAL_PORT_DEVELOPMENT.md`](DUAL_PORT_DEVELOPMENT.md) §4–5
on the harness-first methodology. Most wire-level bugs reproduce
in a harness if you build the right one; intermittent symptoms
are usually structural (PIO ↔ MicroPython contract) rather than
flaky hardware.
