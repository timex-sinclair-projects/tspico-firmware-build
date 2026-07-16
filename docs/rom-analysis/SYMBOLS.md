# TS-PICO ROM symbol reference

Address → name/purpose for both ROMs. **All addresses are identical in v1.1 and
v1.5w** unless marked. File offset == Z80 address throughout.

Names in `CAPS` are ours (the ROM ships no symbols). Names in `backticks` come from
`docs/` or the TS2068 reference disassemblies. Confidence is flagged where it
matters.

"Genuine" means crc32 `bf44ec3f` (HOME) / `ae16233a` (EXROM) — **not** the
mislabelled `WJ-*.bin` images. See
[DIFF_HOME_vs_STOCK.md#baseline](DIFF_HOME_vs_STOCK.md#baseline).

## EXROM chunk 0 (`0x0000-0x1FFF`) — patched genuine EXROM

### TS-PICO additions in the genuine ROM's 1024-byte hole (`0x1800-0x1BFF`)

This gap was empty in the genuine EXROM. It now holds the core Pico driver.

| Addr | Name | Purpose |
|---|---|---|
| `0x1A54` | **`WAIT_PICO_READY`** (`WF_NPH`) | Poll status bit 6 up to `0xE2`=226 times. Carry set = timeout **or** BREAK. Returns `A=02h` on failure. |
| `0x1A61` | `WAIT_PICO_READY.fail` | Shared timeout/BREAK exit. Contains a dead `LD A,40h` + 5 NOPs — a patch remnant. |
| `0x1A6E` | `WAIT_PICO_READY.ready` | Success exit (`SCF`/`CCF` = carry clear). |
| `0x1A73` | `SESSION_SETUP` | Builds SESSION ID from `FRAMES`; parses `TPI:`/`NET:` prefix into `0x5DDB`. |
| `0x1B7E` | **`SEND_BYTE_CRC`** | `CALL 229D` then `XOR D; LD D,A` — send byte and fold it into the CRC in `D`. |
| `0x1BA0` | `BUILD_PREHEADER_B` | Emits the 10-byte `'B'` pre-header. |
| `0x1BF3` | **`STATUS_TO_REPORT`** | Status→BASIC report dispatcher. Entered with `A = status-1`. |
| `0x1BEE` | — | `PUSH AF; XOR A; POP AF` — a no-op remnant. |
| `0x1C23` | `STATUS_OK` | Success path (status 1). |
| `0x1C40` | **`SEND_KEY`** | `CALL 1A54` (wait ready) then `JP 229D` (send). Tail-call target of `0x0471`. |

### Report targets (all reached from `0x1BF3`)

| Addr | Report | | Addr | Report |
|---|---|---|---|---|
| `0x1C16` | 6 — Number too big | | `0x1C35` | C — Nonsense in BASIC |
| `0x1C18` | 8 — End of file | | `0x1C39` | F — Invalid file name |
| `0x1C1A` | 9 — STOP statement | | `0x1C3C` | Q — Parameter error |
| `0x1C1C` | A — Invalid argument | | `0x1C3E` | R — Tape loading error |
| `0x1C21` | **J — Invalid I/O device** ← where internal error 9 lands | | `0x00F8` | D — BREAK-CONT repeats |

### Status / BREAK / string primitives

| Addr | Name | Purpose |
|---|---|---|
| `0x0655` | **`READ_STATUS`** | `CALL 069F; JP NC,06AA; IN A,(0Fh); RET`. The **only** status read. |
| `0x069F` | `CHECK_BREAK` | Reads keyboard row `0xFE`. Carry clear = key down. |
| `0x06AA` | `BREAK_ABORT` | `POP BC; JP 1A61` — BREAK exits via the timeout path. |
| `0x02B9` | **`READ_STATUS_BYTE`** | `CALL 2298`; 0 or carry → `JP 192F` (err); `DEC A`; `RET Z` if OK, else `SCF; RET`. |
| `0x01C3` | `READ_STATUS_AND_OPEN` | `CALL 02B9; JP 04F1`. |
| `0x04F1` | `OPEN_MAIN_SCREEN` | `LD A,0FEh; CALL 0426` → HOME `0x1230`. Opens channel `0xFE`. |
| `0x045F` | **`PRINT_STRING_FROM_PICO`** | Reads bytes via `0x068E`→`0x2298` and prints until terminated. |
| `0x0471` | **`GET_KEY_AND_SEND`** | Wait for key release → wait for keypress → `JP 1C40` (wait ready, send key). |
| `0x0546` | `POLL_KEYPRESS` | Key-availability poll; returns Z when no key. |
| `0x0810` | `LOOP_EXIT_OK` | `CALL 05FA; POP AF; RET`. |
| `0x0813` | `LOOP_EXIT_ERR` | `POP AF; RET`. |
| `0x025E`, `0x026A` | `GET_STATUS_BIT_*` | Return 0/1 flags combined by the GET STATUS handler. |

### Cross-ROM machinery

| Addr | Name | Purpose |
|---|---|---|
| `0x03DD` | **`CALL_HOME`** | EXROM→HOME thunk. Convention: `PUSH IX; EXX; LD HL,<home_target>; JP 03DD`. |
| `0x0F99` | `CALL_B` | Genuine, byte-identical. A 15-byte `VIDMOD` dispatcher — **touches no ports**; jumps to the RAM-resident `CALL_BANK`. |
| `0x0F8A` | `GOTO_B` | Genuine. The no-return counterpart; used by `0x08DD`. |
| `0x08DD` | `GOTO_HOME` | Genuine bytes (tail of `BADBAS`), **reused by TS-PICO** as a no-return thunk. |
| `0x1299` | `BANK_ENABLE` | Genuine, **3 hunks modified**: HSR masks widened from chunk 0 to chunks 0+1. Copied to RAM `0x6499` at boot. |
| `0x0049` | `BOOT_MAP_16K` | `LD A,03h; OUT (0F4h),A` — maps chunks 0+1 = `0x0000-0x3FFF`. |

The 17 factored `CALL_HOME` sites, with the HOME target each passes:

| Site | → HOME | | Site | → HOME | | Site | → HOME |
|---|---|---|---|---|---|---|---|
| `0x02D7` | `0x0020` | | `0x03C1` | `0x02B0` (`F_K_SCAN`) | | `0x05F1` | `0x1FBB` |
| `0x02E0` | `0x2C70` | | `0x03CA` | `0x1BE5` | | `0x064C` | `0x12BB` |
| `0x0303` | `0x0018` | | `0x03ED` | `0x073F` | | `0x0685` | `0x174D` |
| `0x030C` | `0x0010` | | `0x0426` | `0x1230` | | `0x17BA` | `0x0A30` |
| `0x0373` | `0x1C51` | | `0x042F` | `0x2FAF` | | `0x2085` | `0x0A35` |
| `0x037C` | `0x1F23` | | | | | `0x220A` | `0x08A6` |

Eleven **unfactored** genuine inline sites survive at `0x033B`, `0x048C`, `0x0515`,
`0x061D`, `0x072A`, `0x075B`, `0x07A0`, `0x07D1`, `0x0838`, `0x086F`, `0x08BE`.

### Free space in chunk 0

Only **84 bytes** remain, in three runs: `0x138E-0x13CF` (66), `0x1FCE-0x1FD7`
(10), `0x1FE4-0x1FEB` (8). **Chunk 0 is effectively full — put new code in chunk 1.**

## EXROM chunk 1 (`0x2000-0x22AD`) — all-new TS-PICO code

### `0x2000-0x203E` — relocation landing pad (**not** an API table)

| Addr | Name | Notes |
|---|---|---|
| `0x2000` | → `BEEPER` | the only live entry; called from HOME `0x03F6` |
| `0x2009` | **`BREAK_KEY`** | **address-pinned** — genuine HOME's `CALL 2009` was copied verbatim into EXROM `0x17DC` |
| `0x201E-0x2026` | — | dead `OUT (0Fh)` strobe, unreachable |
| `0x203F` | **`BEEPER`** | relocated verbatim from genuine HOME `0x03F3` |
| `0x2003`, `0x2006`, `0x2027`, `0x202A`, `0x202D`, `0x2030`, `0x2033`, `0x2036`, `0x2039`, `0x203C` | — | `JP` self — **padding** that keeps `0x2009` at its required address |

The ten `JP`-self stubs **lock the machine hard if called** (no BREAK, no timeout).
They are padding, not unimplemented API slots.

### TPI BIOS table at `0x1840` — the real API

`JR`/`JP` table for HOME and user code; zero EXROM-internal references.

| Addr | Name | → | Purpose |
|---|---|---|---|
| `0x1840` | `G_MODE` | `0x1856` | get TP_MODE |
| `0x1842` | `S_MODE` | `0x1862` | set TP_MODE |
| `0x1844` | `G_VERS` | `0x1852` | version → `BC = 0x0015` (21) |
| `0x1846` | `TX_A` | `0x186D` → `JP 229D` | send byte |
| `0x1848` | `RX_A` | `0x186A` → `JP 2298` | receive byte |
| `0x184A` | `C_END` | `0x184F` | end command |
| `0x184C` | `WF_NPH` | `JP 1A54` | wait for ready — **the only way to see `A=02h`** |
| `0x184E` | `EWAIT` | `JP 2279` | wait + read status |

`0x1630` printer/COPY table: `1630→1781` (COPY), `1633→17C3`, `1636→17CD` (buffer
flush), `1639→1668` (LPRINT via Pico), `163C→180F`.

### FUNCTION dispatch chain

Entered from `0x228C` with **`A = status - 1`**.

| Addr | Test | Status | Function | Handler |
|---|---|---|---|---|
| `0x026F` | `CP 80h` | `0x81` | PRINT STRING IN MAIN SCREEN | `0x0274` |
| `0x2194` | `CP 81h` | `0x82` | PRINT STRING & RETURN A KEY | `0x2198` |
| `0x21A4` | `CP 82h` | `0x83` | PRINT CHARACTER | `0x21A8` |
| `0x21BA` | `CP 83h` | `0x84` | RETURN KEY | `0x21BE` |
| `0x21C7` | `CP 84h` | `0x85` | GET STATUS | `0x21CB` |
| `0x21DF` | `CP 85h` | `0x86` | **PRINT STRING WITH LOOP (Y/N)** | `0x21E3` |
| `0x21FD` | `CP 86h` | `0x87` | PRINT n CHARACTERS | `0x2201` |
| `0x2213` | `CP 86h` | — | **BUG: dup — unreachable; handler beeps** | `0x2216` (dead) |

### Driver and port helpers

| Addr | Name | Purpose |
|---|---|---|
| `0x2274` | **`PICO_TRANSACT`** | write → wait → read → dispatch. The canonical handshake. |
| `0x2294` | **`ERR_9`** | `LD A,09h; SCF; RET` — shared "comms aborted" exit. Surfaces as **Report J**, not Report 9 (the 9 is already in `status-1` form). |
| `0x2298` | **`TSPICO_READ_DATA`** | `IN A,(0Eh); AND A; RET` |
| `0x229D` | **`TSPICO_WRITE_DATA`** | `OUT (0Eh),A; AND A; RET` |
| `0x223E` | `SEND_DATA_BLOCK_D` | `'D'` (`0x44`) data-block sender. |
| `0x21E7` | **`YN_LOOP`** | The Y/N prompt loop. **v1.5w patch site.** |
| `0x22A1` | **`YN_LOOP_GUARD`** | **v1.5w only.** `CALL 1A54; JR C,22A9; JP 21E7` / `POP AF; LD A,09h; SCF; RET`. |

### Free space in chunk 1

`0x22A1-0x3FFF` in v1.1 (**7519 bytes**), `0x22AE-0x3FFF` in v1.5w (**7506 bytes**).
All `0xFF`. **This is where new code belongs** — appending here moves no existing
address, which is exactly how v1.5w was built.

## HOME ROM (`0x0000-0x3FFF`)

| Addr | Name | Purpose |
|---|---|---|
| `0x3CE3` | **`CALL_EXROM`** | HOME→EXROM thunk. Convention: `EXX; LD HL,<exrom_target>; JP 3CE3`. TS-PICO addition — `0xFF` filler in genuine. Pushes `0xFEFC` = bank `0xFE` (EXROM) + active-low chunk mask `0xFC` (chunks 0+1 = 16K). |
| `0x0A50` | `CALL_EXROM_HL` | Same, HL passed via sysvar `0x5DCD`. |
| `0x03FC` | `CALL_EXROM_RET` | Same but **returns** (used for `BEEPER`). |
| `0x040D` | `CALL_B` | Byte-identical copy of EXROM `0x0F99`. |
| `0x3CF8` | — | `LD (5DCD),HL; JP 04F8` — post-return handler, entered from `0x0A23`. |
| `0x3CDC-0x3CFD` | — | New TS-PICO code in former filler. |
| `0x0E0C` | `BOOT_MAP_16K` | `01` → `03`: the byte that makes the EXROM 16K. |
| `0x3D00-0x3FFF` | `CHARSET` | **Untouched — byte-identical to genuine.** |

**Ten HOME→EXROM call sites** (only two use the bare `JP 3CE3` pattern; the rest go
through the sibling thunks). Full table in
[DIFF_HOME_vs_STOCK.md](DIFF_HOME_vs_STOCK.md#every-homeexrom-call-site).

| Site | → EXROM | | Site | → EXROM |
|---|---|---|---|---|
| `0x0A06` | `0x1630` | | `0x0A2C` | `0x163C` |
| `0x254C` | `0x01AB` | | `0x0A4D` | `0x1633` |
| `0x2556` | `0x01CC` | | `0x04F5` | `0x1639` |
| `0x255F` | `0x1855` | | `0x04FB` | `0x1636` |
| `0x3CE0` | `0x1855` | | `0x03F9` | `0x2000` (returns) |

The EXROM side lands on a jump table at `0x1630` (zero-filled in genuine):
`1630→1781`, `1633→17C3`, `1636→17CD`, `1639→1668`, `163C→180F`.

### Genuine HOME routines the TS-PICO calls

| Addr | Stock name | Role here |
|---|---|---|
| `0x02B0` | **`F_K_SCAN`** | KEY-SCAN. Returns `DE=FFFF` when no key — the basis of `0x0471`'s release/press detection. |
| `0x03F3` | `BEEPER` | **Evicted** — overwritten by a thunk; relocated verbatim to EXROM `0x203F`. |
| `0x02E1` | `F_UD_K` | Keyboard update. |
| `0x1230` | — | Channel open (`0x04F1` passes `A=0xFE`). |
| `0x0008` | — | `RST 08` ERROR-1. |

## System variables

See [PROTOCOL_FROM_ROM.md](PROTOCOL_FROM_ROM.md#ts-pico-system-variables) for the
full table with evidence.

| Addr | Field | | Addr | Field |
|---|---|---|---|---|
| `0x5DCD`/`0x5DCE` | COMND/BLOCK LEN | | `0x5DD7` | PMR1 |
| `0x5DCF` | BANK (`0xFF`=HOME) | | `0x5DD9` | PMR2 |
| `0x5DD1` | SESSION ID | | `0x5DDB` | device flags (b7=TPI/NET, b6=NET) |
| `0x5DD3` | command-string addr | | `0x5D37` | unclassified |
| `0x5DD5` | command-string len | | | |

Stock sysvars in play: `0x5C74` `T-ADDR`, `0x5C78` `FRAMES`, `0x5C48` `BORDCR`,
`0x5C65` `STKEND`, `0x5C5D` `CH_ADD`, `0x5C5F` `X_PTR`, `0x5C3A` `ERR_NR`.

## Ports

| Port | Dir | Role |
|---|---|---|
| `0x0E` | in/out | TS-PICO data |
| `0x0F` | in | TS-PICO status (**bit 6 = READY**; bits 4/5 documented but never tested) |
| `0xF4` | in/out | HSR — chunk enable (`LD A,03h` = chunks 0+1) |
| `0xFF` | in/out | display / bank (bit 7 = EXROM vs DOCK) |
| `0xFE` | in/out | ULA keyboard/border |
| `0xF5`/`0xF6` | out/both | AY sound |
| `0xFB` | in/out | printer (TS-PICO addition vs genuine EXROM) |

> **Do not trust a naive `DB`/`D3` opcode scan.** `db 5d` is almost always the low
> byte of `LD (5Dxx),A` hitting a TS-PICO sysvar. The genuine sites are listed
> above.
