# Setting up Claude Code for this repo

A short onboarding for contributors who want to use
[Claude Code](https://claude.com/claude-code) to work on
TS-Pico firmware. Most of the recent work on this repo was driven
through Claude Code, and the workflow assumes a handful of pieces
are installed and authenticated. This doc gets you from "I just
installed Claude Code" to "I opened a PR against this repo."

If you want the firmware-side conventions Claude Code follows
*inside* a session (harness-first, byte-in-buffer-before-ready,
when-you're-stuck heuristics), see [`src/CLAUDE.md`](../src/CLAUDE.md).
This doc only covers the setup *around* that.

---

## 1. Install Claude Code

Follow the official installer at
[claude.com/claude-code](https://claude.com/claude-code). It pairs
with an Anthropic account — no separate API key required for
interactive use.

Once installed, run `claude` in any directory to start a session.

## 2. Authenticate the `gh` CLI

Claude Code uses the GitHub CLI (`gh`) for everything PR- and
issue-related — opening PRs, viewing issues, downloading CI
artifacts. It must be installed and authenticated:

```bash
# macOS
brew install gh

# then, once:
gh auth login
```

Choose **GitHub.com** → **HTTPS** → **browser-based auth** at the
prompts. Verify with:

```bash
gh repo view timex-sinclair-projects/tspico-firmware-build
```

You should see the repo summary. If you get an auth error, rerun
`gh auth login`.

## 3. Clone and orient

```bash
gh repo clone timex-sinclair-projects/tspico-firmware-build
cd tspico-firmware-build
claude
```

The first thing Claude Code reads is the project structure. The
repo splits into four top-level areas:

| Folder | What's in it |
|---|---|
| `README.md` | Project overview + deploy steps |
| `docs/` | Protocol, architecture, dev guides (including this one) |
| `archive/` | Historical reference material (Ryan's pre-merge sources) |
| `src/` | Everything that ends up on the Pico — firmware sources, flash content, the Z80 EXROM image |
| `SD card/` | Everything that ends up on the user's SD card — TAP library, `tpi:help` text |

When you work under `src/`, Claude Code auto-loads
[`src/CLAUDE.md`](../src/CLAUDE.md) for context on the firmware
conventions (PIO ↔ MicroPython "ready" contract, harness-first
debugging methodology, telemetry switch, etc.).

## 4. The workflow this repo follows

Every change goes through a branch + PR cycle:

1. **Branch off main:**
   ```bash
   git checkout main && git pull
   git checkout -b descriptive-name
   ```

2. **Make the change.** For firmware edits, that usually means
   `src/dev_tspico.py` (the dev override) — see the iteration loop
   in §6.

3. **Push the branch early.** GitHub Actions builds a `firmware.uf2`
   for every branch — you can download it from the Actions tab and
   flash it for hardware testing without waiting for PR review.

4. **Open a PR:**
   ```bash
   gh pr create --fill
   ```
   Use a Summary / Test plan structure in the body. Claude Code
   templates this automatically.

5. **Squash-merge** after the change is confirmed on hardware. The
   iteration commits ("try X", "revert", "try Y") get collapsed
   into a single landing commit on main.

6. **Cleanup:** GitHub auto-deletes the branch on merge if that
   setting's on; if not, run
   `git push origin --delete branch-name` and
   `git remote prune origin` to keep things tidy.

## 5. Permissions to allow

Claude Code asks before running each new shell command. Worth
allowlisting up front:

| Command | Why |
|---|---|
| `gh pr ...`, `gh issue ...`, `gh release ...` | PR/issue/release management |
| `git push`, `git push origin --delete`, `git remote prune` | Branch push + cleanup |
| `mpy-cross`, `./src/build-dev-mpy.sh` | Compiling the dev override |

Use the `/fewer-permission-prompts` skill to scan your transcripts
and allowlist common read-only commands automatically.

**Do not allowlist without thought:**
- `git push --force` / `--force-with-lease` (use deliberately, not by reflex)
- `git reset --hard`, `git clean -f`, `git checkout --` (destructive)
- Anything with `--no-verify` / `--no-gpg-sign` (bypasses hooks)

## 6. Common command chains

These are the patterns Claude Code uses on this repo over and over.

**"Open a PR for this fix"** — Claude Code chains:

```bash
git checkout -b branch-name
# ... edit ...
git add <files>
git commit -m "..."
git push -u origin branch-name
gh pr create --title "..." --body "..."
```

**"Cut a release"** — tag and push, the workflow does the rest:

```bash
git tag v1.5.2
git push --tags
```

`release.yml` then builds the firmware fresh, assembles the
`ts-pico-v1.5.2.zip` bundle (UF2 + `src/` + `SD card/`), and
publishes a GitHub Release with auto-generated notes.

**"Close an issue with context"** — `gh issue close N --comment
"..."` so future readers see *why* it closed, not just that it did.

**Iterating on `src/dev_tspico.py`** — the fast loop, no UF2 rebuild
needed:

```bash
./src/build-dev-mpy.sh         # writes src/dev_tspico.mpy
# upload src/dev_tspico.mpy to the Pico's flash root via Thonny
# reset the Pico, test on the TS-2068
```

The dev override loads automatically if `/dev_tspico.mpy` is
present on the Pico's flash root. To revert, delete the file.

## 7. What `src/CLAUDE.md` covers (and what it doesn't)

[`src/CLAUDE.md`](../src/CLAUDE.md) is the in-repo conventions doc
Claude Code auto-loads when you work under `src/`. It covers:

- The harness-first methodology and the two-phase capture rule
- The PIO ↔ MicroPython "ready" contract (byte-in-buffer-before-
  asserting-ready, V6 pre-load chain)
- Structural conventions (`src/TS/` vs Pico flash paths vs SD card)
- "When you're stuck" debugging heuristics
- The TLM telemetry switch

It does **not** cover:

- This doc — Claude Code setup, `gh` auth, the workflow around
  PRs and releases.
- [`docs/DEVELOPER_GUIDE.md`](DEVELOPER_GUIDE.md) — the broader
  contributor onboarding (Thonny, `mpy-cross`, deploy targets,
  the `/TS/` shadowing trap, common debugging recipes).
- [`docs/PROTOCOL.md`](PROTOCOL.md), [`GUSTAVO_PROTOCOL.md`](GUSTAVO_PROTOCOL.md),
  [`DUAL_PORT_DEVELOPMENT.md`](DUAL_PORT_DEVELOPMENT.md) — protocol
  and architecture deep dives.

Read in this order if you're new:

1. `README.md` — project shape
2. `docs/CLAUDE_CODE_SETUP.md` — this doc
3. `docs/DEVELOPER_GUIDE.md` — broader onboarding
4. `src/CLAUDE.md` — firmware conventions (Claude Code auto-loads
   this on its own once you're working under `src/`)
5. Protocol docs as needed

---

## Troubleshooting

**"gh: command not found"** — Install via your package manager
(`brew install gh`, `apt install gh`, etc.). Then `gh auth login`.

**"Permission denied (publickey)" on `git push`** — You may have
cloned via SSH. Either switch the remote to HTTPS
(`git remote set-url origin https://github.com/.../...`) or add an
SSH key on GitHub.

**"gh: not authenticated"** — Run `gh auth login` and follow the
browser prompts.

**Claude Code prompts for every command, slowly** — Run
`/fewer-permission-prompts` to scan your recent transcripts and
allowlist the read-only commands you use most.

**Pre-commit hook fails** — Investigate the failure rather than
bypassing with `--no-verify`. If the hook is broken, fix the hook.
