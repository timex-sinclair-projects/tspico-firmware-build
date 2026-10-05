# Handoff plan: finishing the TS-Pico programmer's reference

**Delete this file before the PR is opened.** It lives at the repo root, not
under `docs/reference/`, because the coverage test counts every `.md` under
`docs/reference/` (except `README.md` and `appendix/`) as a chapter.

Written 2026-10-05 by the session that started the work, for the session
that finishes it. Everything is in the git worktree on branch
`claude/ts-pico-programmer-reference-9f9a8e`, uncommitted. Read sections 0
and 1 completely before doing anything.

---

## 0. Where things stand

### Done

| Piece | Where | State |
|---|---|---|
| The rule | [`CLAUDE.md`](CLAUDE.md) (new, root) and the section "Keeping docs/reference/ current" in [`src/CLAUDE.md`](src/CLAUDE.md) | done |
| The coverage test | [`src/test/reference_hosttest.py`](src/test/reference_hosttest.py); added to the host-test step of `.github/workflows/build.yml` | done; run it with no args, `--missing`, `--list`, `--stamp`, `--index` |
| The index and conventions | [`docs/reference/README.md`](docs/reference/README.md) — the chapter map, the entry format, the six things an entry says, the stamp table | done; the stamp table's rows are correct for the sources as they are now, except `.github/workflows/build.yml`, which this branch changed (re-stamp it at the end) |
| ROM 2.1 listings | `docs/rom-analysis/disasm/tspico-21-exrom.labelled.asm`, `tspico-21-exrom-symbols.sym` (generated), `tspico-21-home.asm`/`.sym`; produced by the extended [`tools/romdisasm.sh`](tools/romdisasm.sh) | done; the ROM chapters cite these |
| Pointers | `README.md`, `docs/DEVELOPER_GUIDE.md` §12 (and a v3→v4 fix at its upgrade-UF2 table), `docs/PROTOCOL.md` §15, `docs/rom-analysis/README.md` | done |
| Editor-written pages | `docs/reference/overview.md`, `appendix/ports-and-status.md`, `appendix/glossary.md`, `appendix/index.md` (generated) | done |
| Chapters written by authors, **not yet reviewed** | `hardware.md`, `firmware/pio.md`, `firmware/tspico_io.md`, `firmware/tspico-state.md`, `firmware/tspico-dispatch.md`, `firmware/tspico-files.md`, `firmware/tspico-disk.md`, `firmware/sdcard.md`, `firmware/channels.md`, `firmware/catalog.md`, `firmware/native.md`, `firmware/printer.md`, `firmware/extcmd.md`, `firmware/upgrade.md`, `rom/exrom-sync.md` | 11,000 lines; coverage complete for their sources (see the snapshot below) |

### Not done

Chapters still to write (the README's table names them; the test's
`--missing` output shows what each must cover):

| Chapter | Uncovered symbols it must cover (snapshot) |
|---|---|
| `firmware/tspico-bus.md` | 46 functions/classes of `src/TS/tspico.py` (list in §2) |
| `firmware/tspico-messages.md` | 13 functions of `tspico.py` |
| `firmware/tspico-commands.md` | 31 handlers + all 48 `tpi:` command words |
| `firmware/boot.md` | `_telemetry`, `log_msg` of `src/main.py`, plus the non-symbol substance (config.ini, manifests, build, flash image) |
| `rom/overview.md`, `rom/sysvars.md`, `rom/home.md` | no inventory symbols; substance only |
| `rom/exrom-driver.md`, `rom/exrom-chunk1.md` | 65 of the 68 curated names in `docs/rom-analysis/tspico-exrom-symbols.sym` |
| `rom/exrom-fdd.md` | 151 labels/EQUs of `src/rom/fdd/fddcmd.asm` |
| `rom/zx48.md` | 22 labels/EQUs of `src/rom/patches/tspico-zx48-v3.asm` |
| `flows/*.md` (9 files) | no inventory symbols; see §4 |

Then: the review pass (§3), the flows (§4), the finish (§5), the PR (§6).

Snapshot of the test at handoff: `python3 src/test/reference_hosttest.py --missing`
prints 366 of 847 uncovered: 126 in `src/TS/tspico.py`, 2 in `src/main.py`,
151 in `fddcmd.asm`, 65 in the curated symbol file, 22 in `tspico-zx48-v3.asm`.

### Loose ends left by authors who were stopped mid-task

- `firmware/tspico-state.md`: the author was about to add the fourth use of
  `_5_C_Nonsense` (`tpi:chwr` with bad hex) to the status-constants table.
  Check the row and add it if missing.
- `hardware.md`: the author was about to change the DMA table's first
  cells from backticked names (`RxDMA`, `_ring`, `STREAM_DMA`) to plain text,
  because the test counts any backticked token in a table row's first cell
  as an entry and those symbols belong to `tspico_io.md`. Do that.
- `firmware/tspico-dispatch.md` is complete; `tspico-messages.md` was never
  started.
- `firmware/tspico-files.md` is complete; `tspico-commands.md` was never
  started.
- `firmware/extcmd.md` exists (246 lines) and covers extcmd.py;
  `boot.md` was never started.
- `rom/exrom-sync.md` is complete; `exrom-fdd.md` and `zx48.md` were never
  started. The author noted one correction to carry into `exrom-sync.md`:
  it asserted that PROTOCOL.md's ~43 µs SAVE cadence "includes STEP",
  which nothing states; find and fix that sentence.

---

## 1. Ground rules

1. **Read first:** `docs/reference/README.md` (all of it), the "Ground
   rules for AI agents" at the end of `src/CLAUDE.md`, the root
   `CLAUDE.md`, and one finished chapter end to end as the model of depth
   and voice: `docs/reference/firmware/upgrade.md`.
2. **Facts come from the code.** Read every line of the source range a
   chapter covers (`sed -n 'a,bp' file | tr -d '\r'`; the firmware `.py`
   files are CRLF). Design docs supply reasons and history, cited by
   relative link. Where a comment, a doc and the code disagree, say so;
   the code wins. Mark inferences *(inferred)* and hardware-only facts
   *(unverified)*. Never invent timings or bug histories.
3. **The entry format** (what the test looks for): a heading `##`–`######`
   or a table row whose first cell holds the symbol's name in backticks.
   A trailing `(…)` is ignored, so show signatures. Methods are
   `Class.method`. Command words are `tpi:xxx`, case-insensitive. **Quirk:**
   any backticked token in a heading or in a table row's first cell counts,
   so a chapter that merely *mentions* another chapter's symbol must not
   put it in backticks in those positions (plain text, or not in the first
   cell). The first chapter found (alphabetical path order) wins the
   index, so a stray mention mis-files the symbol in `appendix/index.md`.
4. **Ownership.** Each symbol belongs to one chapter (§2 lists the
   remaining ones; the README's table lists them all). Other chapters link.
5. **Source order** within a chapter; a `## Map` at the top; the chapter
   opens with a title, a `Source:` link line and a paragraph of scope.
6. **Environment.** Work only in the worktree
   `/Users/david/Documents/github/tspico-firmware-build/.claude/worktrees/hopeful-franklin-53fa54`.
   Don't `cd` to the main checkout. Quote grep patterns in zsh (brackets
   and parentheses glob). Markdown is LF. Don't commit until §6; never
   push to `main`; the PR needs the user's explicit OK (repo rule).
7. **Pace.** The first session fanned out eleven subagents at once and hit
   session rate limits twice; most authors were cut off mid-write. Write
   chapters yourself one at a time, or run at most two or three subagents
   concurrently, and have each write its file in parts (append as it goes)
   so an interruption loses little. A chapter of 1,000 lines is normal;
   write it in three or four appends.
8. **Check as you go.** After each chapter:
   `python3 src/test/reference_hosttest.py --missing | grep '<source>'`
   until nothing is printed for the chapter's symbols.

---

## 2. The remaining chapters, with their briefs

Each brief: the file, what it owns, the source ranges to read in full,
the docs for the "why", and the points that must be covered. Line numbers
are those of the sources at handoff (`--list` prints current ones).

### 2.1 `docs/reference/firmware/tspico-bus.md` (part 2 of tspico.py)

**Owns** (source order): `DEACTIVATE_SD`, `ACTIVATE_MQ`, `MQ_READY`,
`CmdAbort`, `CMD_PUT`, `CMD_SEND`, `CmdOut` (+ `CmdOut.__init__`,
`CmdOut.__call__`, `CmdOut.send`), `CMD_KEY`, `CMD_DRAIN`, `PRELOAD_READ`,
`CMD_RX_FLUSH`, `CMD_FLUSH`, `MQ_BUSY`, `ACTIVATE_SD`, `SAVE_MOUNT`,
`SD_NOTE_CARD`, `SD_REVALIDATE`, `LISTING_SIG`, `LISTING_FRESHEN`,
`LISTING_CHECK`, `REFRESH_LISTING`, `SD_PROBE`, `BLINK_ERROR`, `BLINK_LED`,
`SD_CALL`, `SD_NEEDED`, `NO_CARD_REPLY`, `REFRESH_IF`, `CH_READY`,
`CH_REPLY`, `CH_CALL`.
**Read:** `src/TS/tspico.py` 690–1340, 2669–2730, 3228–3262; grep each
name for callers. `tspico-state.md` already documents every module
variable (link, don't re-enter) — read it so the two chapters agree.
**Docs:** PROTOCOL.md §3, §13; DEVELOPER_GUIDE.md §7, §8;
DUAL_PORT_DEVELOPMENT.md §6–8; AUDIT-2026-09-30.md; SD_ROBUSTNESS_PROPOSAL.md;
tests `sd_state_hosttest.py`, `sd_recover_hosttest.py`, `sd_mount_hosttest.py`,
`cmd_io_hosttest.py`, `audit_fixes_hosttest.py`.
**Must cover:** who owns the bus and how it changes hands (the shared GPIO
2–4, NULL_SM parking, the clamp, the U6 enable, the Y register through the
handover, why ACTIVATE_MQ must not pre-load a status); the command I/O
helpers' contract with PROCESS_CMD (what CMD_PUT/CMD_SEND/CmdOut buffer,
when bytes reach the FIFO, `_CMD_ECHO`, CMD_STALL_MS/KEY_WAIT_MS,
CmdAbort: who raises it, who catches it, why it is a BaseException); the
SD card's state (sd_present, sd_cid, sd_listing_ok, listing_stale,
SD_TRY_MS, the retry policy, what a changed card triggers, SD_NEEDED's
rule and NO_CARD_REPLY's answer); the LED thread on core 1 (busy/dead).

### 2.2 `docs/reference/firmware/tspico-messages.md` (part 4)

**Owns:** `shorten_filename`, `DIR_HEADER`, `CAT_COLOUR`, `TAPDIR_COLOUR`,
`MSG_BYTE`, `SEND_MSG`, `SEND_MSG2`, `PROMPT_EACH`, `ListMenu`, `xchr`,
`xstr`, `BUILD_FIT`, `SEND_MSG_PROMPT_YN`.
**Read:** `tspico.py` 1507–1600, 2145–2470, 2729–2767, 3447–3642,
3848–3862, 4507–4520, 5262–5332. The colour constants, LISTMENU_CHOICES,
the FN_* codes and STR_END/LOOP_END are in `tspico-state.md`: link.
**Docs:** PROTOCOL.md §5.3–5.4 (the text rules, the keys), §13;
rom-analysis/PROTOCOL_FROM_ROM.md (function requests, status−1);
ROM_CHANGES.md (function 88h); programmers-manual.md ch 12;
tests `screen_colour_hosttest.py`, `commands_hosttest.py`, `process_cmd_hosttest.py`.
**Must cover:** how an 81h string and an 86h loop are built byte by byte
(MSG_BYTE's mapping, the 00h/03h terminators, bytes ≥ 80h, 32-column
wrapping, the Scroll? prompt and its keys 1–9/0, the backspace trick that
erases the prompt, line endings CR/LF/CRLF, keyword expansion of ~ and
FREE/STICK, colour codes and which values are forbidden and why); the Y
register and the FIFO at each step (where READY is said relative to the
first bytes); the ROM function each helper uses (link
`../rom/exrom-chunk1.md`); the prompts and what may follow them (nothing);
ListMenu's keys, paging and the page indicator; the colour helpers for CAT
and tapdir.

### 2.3 `docs/reference/firmware/tspico-commands.md` (part 6)

**Owns:** one table with a row per key of `SA_funct` (48 rows, first cell
`tpi:xxx`: the handler, the BASIC form(s), the CODE options in brief) —
`tpi:append tpi:blkrcv tpi:cd tpi:close tpi:dir tpi:copy tpi:erase
tpi:format tpi:ren tpi:fopen tpi:chopen tpi:chwr tpi:chrd tpi:chclose
tpi:ffw tpi:help tpi:idir tpi:info tpi:log tpi:loglevel tpi:md tpi:boot
tpi:memboot tpi:dock tpi:memdock tpi:nop tpi:path tpi:rew tpi:rm
tpi:newtap tpi:tapdir tpi:verbose tpi:zx48 tpi:autolf tpi:autopg tpi:bmp
tpi:clprint tpi:config tpi:delete tpi:freset tpi:getconfig tpi:list
tpi:meminfo tpi:noautolf tpi:noautopg tpi:opprint tpi:prnsz tpi:stop` —
then one entry per handler in source order: `DIR`, `IDIR`, `PATH`,
`TAPDIR`, `NEW_TAP`, `SA_NOT_IMP`, `APPEND`, `BLKRCV`, `CDIR`, `FWD`,
`GETHELP`, `GETINFO`, `GETLOG`, `LOGLEVEL`, `MDIR`, `MEMBOOT`, `MEMDOCK`,
`REW`, `BAD_CODE`, `BAD_ARG`, `RM`, `RM_CHECK`, `UNMOUNT`, `VERB_TOGGLE`,
`ZX48`, `NOP`, `PRN_OPEN`, `PRN_CLOSE`, `PRN_FLAG`, `PRN_SIZE`, `PRN_BMP`.
(The disk/channel handlers the table points at — DISK_*, NATIVE_OPEN,
CH_* — are in `tspico-disk.md`: link from the rows.)
**Read:** `tspico.py` 2505–2580, 3414–3446, 3643–3830, 3895–4120,
4205–4718, 4798–5260 (MEMBOOT/getBoot/getDock/BOOT_SLOT_CLASH/MEMDOCK are
in `tspico-files.md` except MEMBOOT/MEMDOCK themselves — check that
chapter's map to avoid a double entry), 5333–5567, 5666–5745, and the
SA_funct table at ~6170–6220.
**Docs:** user-manual.md ch 3, 4, 7, 8, 10, App A, App D (verify every
option against the code; say where the manual and the code differ);
PROTOCOL.md §5, §11, §13; AUDIT-2026-09-30.md; flash/README.md;
tests `commands_hosttest.py`, `boot_slot_guard_hosttest.py`, `catalog_hosttest.py`.
**Per handler:** BASIC syntax, every CODE n,m option and argument form,
the interactive forms, the answer (bare status / 81h / 86h / Y–N prompt:
name the helper) and whether VERBOSE changes it, every report and its
condition, the bus/SD state it needs (SD_CALL? ACTIVATE_SD itself?), the
state it changes (TSP fields, caches, config.ini, flash files), beware.

### 2.4 `docs/reference/firmware/boot.md`

**Owns:** every symbol of `src/main.py` (the 8 pin variables as a table,
`_telemetry`, `log_msg`).
**Substance (no symbols):** `src/config.ini` (every key, type, default,
who reads it — LOAD_CONFIG in `tspico-dispatch.md`, `_telemetry` — and
what writes it); `src/manifest.py` and `TS/buildinfo.py`
(`tools/gen-buildinfo.py`: COMMIT/BRANCH/DIRTY, how BUILD_VERSION shows);
the dev overrides (`dev_tspico.py`, `dev_extcmd.py`, `build-dev-mpy.sh`,
the `.mpy` preference, `dev_sync_hosttest.py`, the /TS/ shadowing trap
of DEVELOPER_GUIDE §6); the UF2 build in `build.yml` and `release.yml`
step by step (MicroPython version and board, module staging and
freezing, the two UF2s and `modules-upgrade`, artifacts, the host tests,
the ROM and flash checks, release assets, the Pages chain); the flash
image (`flash/README.md`, `flash/manifest.json`, `tools/build-flash.py`:
16 slots of 32K, 64K DCK pages, crc checks, `--slot` overrides, the base
image); `tools/pico-serial.py` in brief; the Pico's flash filesystem at
runtime (/main.py, /config.ini, /assets/*.tap, /activity.log,
/words.txt, /dev_*, temp.tap, temp.bin) and who creates each.
**Read:** `src/main.py`, `src/config.ini`, `src/manifest.py`,
`src/build-dev-mpy.sh`, `tools/gen-buildinfo.py`, `tools/build-flash.py`,
`flash/README.md`, `flash/manifest.json`, both workflows, root `README.md`,
`tspico.py` LOAD_CONFIG (4719–4797). Link `upgrade.md` for the upgrade
UF2 rather than re-describing it.

### 2.5 `docs/reference/rom/overview.md`, `rom/sysvars.md`, `rom/home.md`

No inventory symbols; completeness is the measure. Use headings or table
rows with backticked names for every routine, hook and variable so the
index and cross-links work — but only for things these chapters own
(HOME addresses, system variables); EXROM routine names belong to the
EXROM chapters (plain text or links here).
**Read in full:** every `docs/rom-analysis/*.md`; `docs/ROM_CHANGES.md`;
`tools/build-rom.py` (PATCHES, ANCHORS, rebase, main); `tools/build-rom.sh`;
`tools/romdiff.py` (header, EXPECT_CRC); `tools/romdisasm.sh`;
`src/rom/fdd/README.md`; `src/rom/patches/tspico-sync.asm` (the HOME
sites); `flash/manifest.json`; `src/test/rom_sync_hosttest.py`,
`rom_cend_hosttest.py`, `rom_zx48_hosttest.py` (headers). For every HOME
address, read `docs/rom-analysis/disasm/tspico-21-home.asm` around it
(`grep -n ';0f12'` — the comment column holds lower-case hex addresses).
For sysvars, grep both 2.1 listings for `(5d` and `(65c` references and
read `fddcmd.asm`'s EQU block.
**overview.md must cover:** the images and lineage with sizes and crc32s
(TSPICO.ROM v1.7 09D4CA63; TSPICO-SYNC.ROM 2.0 crc in build-rom.py's
BASE_ROM_CRC 56bd89a4; TSPICO-21.ROM E813BF90; ZX v2 B3D40C73, v4
083655BF; ROMs/ for 1.1, 1.5w, genuine with their md5/crc; which ships in
which flash slot); the 32K file layout (HOME at 0, EXROM at 4000h, file
offset == Z80 address); the 16K EXROM across chunks 0+1 and the proof; the
TS2068 banking primer (ports F4h/FFh, HSR, chunks, DOCK vs EXROM); the
thunks 3CE3h, 0A50h, 03FCh, 03DDh, 08DDh with register conventions, the
pushed bank constants (FEFCh, FF00h), CALL_B/GOTO_B and BANK_ENABLE in RAM
at 6499h, the bank stack at 65CEh and why 2.1 needed H_TRAP; version
bytes (PEEK 101, G_VERS, banner, FDD_VERSION); the build: every PATCH
(bank, address, before, after, why) and every ANCHOR of build-rom.py,
`--verify`/`--rebase`, BASE_ROM_CRC, build-rom.sh, the CI check that the
slot-1 ROM equals a fresh build; how to read the listings (which file is
which, status−1, the linear-sweep caveat, the generated symbol file); a
one-table guide to `docs/rom-analysis/`; the two ports' I/O sites by
address; a pointer to `../hardware.md`.
**sysvars.md must cover:** every TS-Pico sysvar at 5Dxxh (PROTOCOL_FROM_ROM
"TS-PICO system variables", SYMBOLS.md; address, size, name, meaning,
writers, readers, initial value); the stock sysvars the Pico code uses
(FRAMES, ERR_SP, ERR_NR, X_PTR, CH_ADD, CURCHL, STRMS, CHANS, PROG,
T_ADDR, FLAGS, MODE, the header area, 65CEh, 6499h, 5CCBh, and whatever
`fddcmd.asm`'s EQUs name); TPMODE 5DDBh and its bits; the ZX ROM's
variables used by v3/v4 (link `zx48.md`). Tables by area, one row per
variable, a paragraph per group.
**home.md must cover:** every HOME hunk vs the genuine ROM —
DIFF_HOME_vs_STOCK's ten (tape and printer hooks, the 16K banking change,
the thunks, 3CDCh–3CFDh), 2.0's 0065h and 0F12h–0F1Fh, 2.1's 1946h,
25D6h–25E3h, 1488h–14C6h (trampolines, H_TRAP at 14B2h), 145Eh, 1438h,
13A5h, 03F3h, 041Ch — each with address, genuine bytes, TS-Pico bytes
(quote the listing), what the hook does, which EXROM routine it reaches
and how, which BASIC statement passes through it; the HOME side of the
protocol (the report printer and Report T, the syntax-table change for
bare CAT/FORMAT/MOVE/ERASE, OPEN #/CLOSE # routing, the BEEPER thunk and
DI); the HOME layout map (0000h–3CDBh, 3CDCh–3CFDh, 3D00h–3FFFh).

### 2.6 `docs/reference/rom/exrom-driver.md` and `rom/exrom-chunk1.md`

**Own all 68 names** in `docs/rom-analysis/tspico-exrom-symbols.sym`
(`--missing | grep exrom-symbols` must print nothing). Three are already
covered elsewhere (by `exrom-sync.md`'s EQU table, presumably); the test
tolerates duplicates, but keep these two chapters the home of every name.
**Ground truth:** `docs/rom-analysis/disasm/tspico-21-exrom.labelled.asm`.
Read in full 0000h–0100h, 03D0h–0420h, 0640h–06C0h, 1800h–1C80h,
2000h–22AEh, and the routine around every other curated address.
**Docs:** rom-analysis SYMBOLS.md, PROTOCOL_FROM_ROM.md,
DIFF_EXROM_vs_STOCK.md, ERROR_TRAPPING.md, BREAK_AND_ABORT.md,
MEMORY_MAP.md, REVIEW_ROM_V17_SAVE_BREAK.md, DIFF_V11_vs_V15W.md;
ROM_CHANGES.md (the 2.0/2.1 patch sites inside these regions: CALL
SYNC_WRITE at 189Ah/1998h/1BAAh/1651h/16F6h; 06AAh; 18FDh; 19EFh; 0479h;
1A58h; 184Ch/184Fh; 01D2h; 2213h); PROTOCOL.md §4–6, §9;
GUSTAVO_PROTOCOL.md and LOW-LEVEL-PROTOCOL-V5.TXT (intent only);
programmers-manual.md ch 3, 8, App B; `tools/wf_nph_timing.py`.
**exrom-driver.md (1800h–1BFFh + the BIOS table):** READ_STATUS 0655h and
CHECK_BREAK 069Fh as the driver uses them; WAIT_PICO_READY (226 polls,
88 ms each through the keyboard scan, ~19.9 s, the fail/ready exits, the
dead LD A,40h, 2.0's RD_STATUS at 1A58h); SESSION_SETUP (session id from
FRAMES, TPI:/NET: parsing into 5DDBh, the 5–31 character gate, the exit
to SAVE-ETC 01D5h, 2.1's F_HOOK at 01D2h, SESSION_NAMED 1AACh);
SEND_BYTE_CRC; BUILD_PREHEADER_B (the ten bytes and the sysvar behind
each); STATUS_TO_REPORT and every report target (status−1 dispatch,
internal error 9 → J, each target's address and code); STATUS_OK;
SEND_KEY; the PUSH AF/XOR A/POP AF remnant; the BIOS table entry by entry
(G_MODE, S_MODE, G_VERS, TX_A, RX_A, C_END, WF_NPH: contract, target, the
2.0/2.1 changes); the banner 1C6Ch; anything else in the region. Entry and
exit registers for every routine; the wire bytes and the firmware function
on the other end (link `../firmware/…`); sysvars (link `sysvars.md`).
**exrom-chunk1.md (2000h–22ADh and the chunk-0 paths):** the relocated
BEEPER at 2000h and the 2000h–203Eh landing pad; accessors 2298h/229Dh;
the function chain (READ_STATUS, DEC A, the CP chain: each function
81h–88h, loop bodies, key waits and 2.0's KEYWAIT, the string reader's
00h/03h stops, the 86h loop at 21E6h, the dead second CP 86h made 88h →
LOWER_LOOP); the status→report tail; C_END 2279h/227Fh and WF_NPH's
pieces; YN_LOOP_GUARD 22A1h; the v1.7 SAVE-BREAK change; then the chunk-0
tape and printer paths that call the driver (the header pre-header at
189Ah, the block loops at 1998h/19EFh with STEP, the SAVE loop at 18FDh,
the XOR, the search/retry as the Z80 does it — link LOAD_TS/SAVE_TS) and
the printer sites 1651h/16F6h, as paths with the stock routine names and
addresses. Use status−1 explicitly at every CP.

### 2.7 `docs/reference/rom/exrom-fdd.md` and `rom/zx48.md`

**Own** every global label and EQU of `src/rom/fdd/fddcmd.asm` (151
uncovered) and `src/rom/patches/tspico-zx48-v3.asm` (22). Local labels
(`.name`) are explained within their parent routine. EQUs for ports,
constants, stock routines and variables go in tables, one row each.
**Read in full:** the two sources; the 2.1 listing at 3000h–376Ch;
`src/rom/fdd/README.md`; ROM_CHANGES.md; FDD_COMMANDS_DESIGN.md;
DISK_COMMANDS_SPEC.md; rom-analysis PATCH_ZX48_HANDSHAKE.md,
BREAK_AND_ABORT.md, ERROR_TRAPPING.md; PROTOCOL.md §7, §9, §10;
`tools/build-rom.py` PATCHES/ANCHORS; tests `rom_zx48_hosttest.py`,
`rom_cend_hosttest.py`, `zx48_tpi_hosttest.py`, `zx48_io_hosttest.py`;
the firmware side for links: `tspico-disk.md` (written), `tspico-dispatch.md`
(ZX_TPI, ZX48_IO), `tspico_io.md` (LOAD_ZX, LOAD_ZX_C, SAVE_ZX, ZX_STREAM).
**exrom-fdd.md:** constants and EQUs (FDD_BASE, FDD_VERSION, every
HOME/EXROM/RAM address named); the vector table (each *_VEC: the patch
site that reaches it, its target); GUARDED, JP_HL and H_TRAP (the
bank-stack leak, DI/EI discipline); FDD_MAIN and the two passes (FLAGS
bit 7); token dispatch; FDD_CAT/FDD_ONE_ARG/FDD_MOVE and the string
helpers (NONSENSE, TOO_LONG, SKIP_SPACES, NEXT_CHAR, AT_END, EXPT_STR_END,
RUNTIME, HC_EXPT_STR, POP_STR, NOT_EMPTY, BUILD_START, HC_TEST_ROOM,
SEND_PREFIX, SEND_ONE, SEND_TAIL, COPY_CSTR); TPI_SEND and SESSION_NAMED
(the 64-char argument); F_HOOK, PEEK_NAME, SEND_FOPEN (the f: test, the
session id, the hand-built pre-header and body, TXX/TX_STR, how the name
is edited for SAVE vs LOAD, the jump to SAVE-ETC); WF_FAIL/C_FAIL/C_END2
(J/D/T; why a timeout is J); LOWER_LOOP (88h); the channel code
(CH_OPEN_HOOK, OPEN_SYNTAX, STRMS_NC/STRMS_HL, CH_CLOSE_HOOK, the HC_*
helpers, CH_OUT, CH_IN, CH_FLUSH, CH_FETCH, CH_STATUS, CH_SEND, HEXDIG,
STRLEN, the record layout offset by offset); the CMD_* strings and what
the Pico answers (link `tspico-disk.md`); MODE_R, FDD_END, G_BEEP.
**zx48.md:** the lineage (stock 48K → ZX v2 per PATCH_ZX48_HANDSHAKE.md →
v3 → v4); EQU tables (ports, the v2/stock routines and variables:
WAIT_RDY, STK_FETCH, CHAN_OPEN, PR_STRING, BREAK_KEY, SET_STK, T_ADDR,
CH_ADD, X_PTR, ERR_SP, ERR_D, ERR_J, NEW_CODE, ZXV); every patch site
(address, before, after, why); WAIT_RDY_V3 (the D-register bug, ~3.8 s);
TPI_CHK, TPI_TXT, TPI_CMD (the whole 'T' exchange: op with bit 7 in v4,
TPI_OUT/TPI_DLY's ~50 µs cadence and the 4-deep FIFO, the ~30 s READY wait
with BREAK_KEY, the status byte, the message/pieces reply, the workspace
and PR_STRING), TPI_ERR (raising a report by hand, four steps), TPI_END,
the banner byte; the firmware side as links; how ZX48 mode is entered and
left (tpi:zx48, the DOCK slot, OUT 244,3; user manual ch 9).

---

## 3. The review pass (every chapter, including the fifteen already written)

Do this after §2, before the flows, chapter by chapter:

1. **Coverage quirks.** Run `python3 src/test/reference_hosttest.py --index`
   and read `appendix/index.md`: every symbol's "Explained in" column must
   name the chapter that owns it. A symbol filed under the wrong chapter
   means a stray backticked mention in a heading or a first table cell
   there; make that mention plain text. Also grep for duplicate entries
   across chapters (`grep -rn '^### `NAME' docs/reference`).
2. **Spot-check accuracy.** For each chapter pick five entries (include
   the longest) and compare every claim with the source. Fix what is
   wrong. Depth is the point; if an entry only paraphrases the code's
   comment, deepen it from the code.
3. **Dead links.** Write a ten-line script: for every `](...)` relative
   link in `docs/reference/**/*.md`, check the target file exists and, if
   it has a `#anchor`, that a heading producing that anchor exists
   (GitHub's slug rule: lower-case, spaces → `-`, punctuation dropped,
   backticks dropped). Fix every broken one. The chapters were written in
   parallel against planned file names, so expect some.
4. **Agreement between chapters.** The same fact stated in two chapters
   must match (slot sizes are 32K; the SM numbers; the clocks; the status
   values). `overview.md` and `appendix/*` were written by the editor
   before the chapters and should be re-read against them.
5. **Known disagreements** are now logged in `REFERENCE-FOLLOWUPS.md` at the
   repo root (add each new one there as chapters are written; the user
   decides each). Originally: reported by authors — make sure each is stated
   in the chapter (code wins) and list them in the PR description as
   follow-ups, not fixed in code by this PR:
   - `updater.asm` line 5 and `upgrade.py` line 4 name `tools/build-upgrade.sh`;
     the script is `tools/build-upgrade.py`.
   - `updater.asm` `VARS equ 7600h` is dead; the variables live in the code
     block (line 569's comment).
   - `updater.asm` line 214 "and return, carry set": the carry is
     `status`'s and nobody reads it.
   - `src/upgrade/main.py` names GPIO 14 `WAIT` while `TS_IO_DUAL` waits on
     it as /PICOSEL; GPIO 19/20 are `U10_ENA`/`U13_ENA` in main.py but
     `set_ctrl`'s header says /U10_CE and /U10_OE. `hardware.md` discusses
     both; it marks the resolution *(unverified)*.
   - `PICO_STATUS.__init__`'s comment says `bank_sm`'s default is
     "0001 0000"; the code computes 1.
   - `TS_IO_DUAL`'s docstring says PIO runs "up to half the system clock";
     ROM/BANK run at 150 MHz on a 270 MHz CPU, so the comment is wrong and
     the code right.
   - `src/upgrade/manifest.py`'s comment says the page leaves the
     filesystem empty "after flash_nuke"; over WebUSB it erases through
     PICOBOOT (same effect).
   - The `tpi:chwr` bad-hex path uses `_5_C_Nonsense` (fourth use).

---

## 4. The flows (`docs/reference/flows/`, nine files)

Each flow follows one operation from the BASIC keyword to the SD card and
back, as a numbered sequence. Each step names the side (2068 or Pico), the
ROM routine with its address or the firmware function, what goes over the
wire, the state of the TX/RX FIFOs and the Y register after the step, and
what can go wrong there and which report results. Build them from the
chapters (link each step's entry) and from the code; 150–400 lines each.
No inventory symbols; headings describe the step, not a symbol, so put
symbol names in links or plain text, not alone in backticks in headings.

| File | Follows |
|---|---|
| `flows/boot.md` | power-on: `main.py` → `TS2068_IO` setup (pins, SMs, SD, config, nofile.tap, pre-load) on the Pico; the 2068's boot through the HOME ROM, the EXROM init, the banner, TPMODE; both sides at the first prompt |
| `flows/command.md` | `SAVE "tpi:dir"`: SAVE-ETC → SESSION_SETUP → SYNC_WRITE → BUILD_PREHEADER_B → the body → the ROM's wait; RX_CAPTURE/RX_DMA → PROCESS_CMD → SA_funct → DIR → SEND_MSG2 → the 86h loop with keys → C_END → the tail. Then the variants: a bare status, a 81h message, a Y/N prompt, a mount (`LOAD "tpi:name"`), an external command, a command needing the card with no card |
| `flows/load.md` | `LOAD ""`: LD-BYTES hook → the pre-header → LOAD_SERVE/LOAD_TS → the search through the offset table → the header block → the data block by STREAM_DMA → the echoes and XOR → final status; VERIFY/MERGE; headerless LOAD; nofile.tap; the retry bound; what each failure reports (R, J, T, D) |
| `flows/save.md` | `SAVE "name"`: SA-BYTES hook → header pre-header → SAVE_TS (the mid status, the refusals F/A) → the ~1 s pause → the data block via RX_BLOCK → the SD write → the pre-load; APPEND and NEWTAP; `f:` SAVE through F_HOOK and `tpi:fopen` and the 88h prompt |
| `flows/channels.md` | `OPEN #4,"f:log.txt","a"` → OPEN_SYNTAX → CH_OPEN_HOOK → `tpi:chopen` → CH_OPEN; `PRINT #4` → CH_OUT → CH_FLUSH → `tpi:chwr` → CH_WRITE; `INPUT #4` → CH_IN → CH_FETCH → `tpi:chrd` → CH_READ data phase; TAB; `CLOSE #4`; the `d:` listing; the IDLE-before-SYNC rule |
| `flows/printer.md` | `LPRINT "x"` with `tpi:picopt`: the 1651h hook → one transaction per character → PRINT_IO → TextCapture → PRINT_FLUSH to /sd/VLPRINT; `COPY` → 16F6h → the body → write_bmp |
| `flows/sd-handover.md` | the bus between MQ and SPI: ACTIVATE_SD (NULL_SM, U6 off, SPI, mount, SD_NOTE_CARD/SD_REVALIDATE) → work → DEACTIVATE_SD (clamp) → ACTIVATE_MQ (rebuild TS_IO_DUAL, Y) — as SD_CALL wraps it, at boot, after a SAVE, and in the ZX48 handlers (ENA_SD/ENA_MQ_DUAL); the no-card paths; the wedged-card recovery |
| `flows/break-and-recovery.md` | SYNC at the start of a transaction (SYNC_WRITE/SYNC_WAIT ↔ RX_CAPTURE/MQ_TO_IDLE); BREAK in a ready wait (BRK_ABORT), in a block loop (STEP), in a key wait (KEYWAIT) ↔ CmdAbort/RXB_ABORT/TX_ROOM; the Pico giving up (stall clocks, RECOVERED, Report T); the BIOS contract |
| `flows/zx48.md` | `SAVE "tpi:zx48"` → ZX48 → the DOCK switch and OUT 244,3 → ZX48_IO's loop → `LOAD ""` through LOAD_ZX/LOAD_ZX_C → `LOAD "tpi:name"` through TPI_CMD and ZX_TPI → `SAVE "tpi:dir"` (v4 pieces) → SAVE_ZX → leaving the mode |

---

## 5. Finishing

1. `python3 src/test/reference_hosttest.py --missing` → nothing.
2. Fix `docs/reference/README.md`'s table if any chapter name changed.
3. Re-stamp only what this branch changed: `.github/workflows/build.yml`
   (the test line was added). Everything else was documented against the
   current sources, so the existing rows stand. `python3 src/test/reference_hosttest.py --stamp`
   prints all rows; replace that one.
4. `python3 src/test/reference_hosttest.py --index`, then the test with no
   arguments → `ALL PASS`.
5. Run the rest of CI locally: every `python3 src/test/*_hosttest.py` line
   in `.github/workflows/build.yml`'s "Run host-side tests" step,
   `python3 tools/build-flash.py check flash/manifest.json`,
   `python3 docs/manual/examples/test_examples.py`,
   `python3 docs/manual/examples/test_extcmd_host.py`,
   `python3 tools/build-rom.py --verify`. All must pass (none of them
   should be affected; `dev_sync_hosttest.py` would catch an accidental
   edit of a firmware file).
6. Delete this file.
7. Update the memory note `programmers-reference.md` in the project's
   memory directory (state, branch, what is left).

## 6. Commit, push, PR (repo rules in `src/CLAUDE.md`, "GitHub workflow")

- One commit (or a few logical ones) on the branch; end the message with
  the attribution line the session's system reminder gives. Include the
  generated listings and symbol file under `docs/rom-analysis/disasm/`.
- `git push -u origin claude/ts-pico-programmer-reference-9f9a8e` so CI
  runs the new test alongside the others.
- **Open the PR only after the user says so.** The description explains
  why (the reference, the rule, the test, the stamps), lists the
  follow-ups from §3.5, and ends with the generated-with line from the
  system reminder. Squash merge, delete branch, when the user says so.
