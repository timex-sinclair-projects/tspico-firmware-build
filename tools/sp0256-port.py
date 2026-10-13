#!/usr/bin/env python3
"""Generate the SP0256 core for tsbus from MAME, and the AL2 ROM table.

    python3 tools/sp0256-port.py MAME_SP0256_CPP AL2_BIN

MAME_SP0256_CPP is MAME's src/devices/sound/sp0256.cpp (BSD-3-Clause,
Joseph Zbiciak and Tim Lindner); AL2_BIN is the SP0256-AL2 ROM as
spatula-city.org/~im14u2c/sp0256-al2/ offers it (al2.bin, 2048 bytes).
Writes src/tsbus/sp0256_mame.inc and src/tsbus/sp0256_al2.inc.

The core is MAME's code (lines 182-1150: the limiter, the 12-pole filter,
its register decode, the data-format tables, getb and the microsequencer),
turned from a C++ class into plain C mechanically: the class members become
fields of an sp0256_t (s->...) and the filter's of an lpc12_t (f->...), the
one lambda a function, LOG calls dropped. Two changes beyond that:
- Core 1 never reads flash (docs/reference/firmware/tsbus.md): every
  function is wrapped in SP0256_RAM(), the tables are placed in RAM by
  name (SP0256_DATA), and the ROM is read through sp0256_rom() from a 2 KB table
  instead of MAME's 64 KB address space.
- Nothing else. src/test/sp0256_hosttest.py checks the result sample for
  sample against reference renderings.
"""
import hashlib
import os
import re
import sys

src = open(sys.argv[1]).read().split("\n")
assert src[0].startswith("// license:BSD-3-Clause"), "not MAME's sp0256.cpp"
core = "\n".join(src[181:1150])          # lines 182-1150: limit .. micro

LPC = ["rpt", "cnt", "per", "rng", "amp", "f_coef", "b_coef", "z_data", "r", "interp"]


def lpc_members(body):
    for m in LPC:
        body = re.sub(r"(?<![\w.>])%s\b" % m, "f->" + m, body)
    return body


def cut(text, start_pat):
    """The function starting at start_pat, to its closing brace at column 0."""
    i = text.index(start_pat)
    j = text.index("\n}\n", i) + 3
    return text[i:j], text[:i] + "@@" + start_pat + "@@" + text[j:]


limit, core = cut(core, "inline int16_t sp0256_device::lpc12_t::limit(int16_t s)")
update, core = cut(core, "inline int sp0256_device::lpc12_t::update(")
regdec, core = cut(core, "inline void sp0256_device::lpc12_t::regdec()")

limit = limit.replace("inline int16_t sp0256_device::lpc12_t::limit(int16_t s)",
                      "static inline int16_t lpc12_limit(int16_t s)")
update = update.replace("inline int sp0256_device::lpc12_t::update(int num_samp, int16_t *out, uint32_t *optr)",
                        "static int lpc12_update(lpc12_t *f, int num_samp, int16_t *out, uint32_t *optr)")
update = lpc_members(update)
update = update.replace("const bool bit(f->rng & 1);", "const bool bit = (f->rng & 1);")
update = update.replace("limit(samp)", "lpc12_limit((int16_t)samp)")
update = re.sub(r"\bint\((f->[a-z_]+\[j\](?:\[\d\])?)\)", r"(int)(\1)", update)
regdec = regdec.replace("inline void sp0256_device::lpc12_t::regdec()", "static void lpc12_regdec(lpc12_t *f)")
regdec = regdec.replace("static constexpr int16_t qtbl[128] =", "static const int16_t qtbl[128] =")
regdec = regdec.replace("static constexpr int stage_map[6] = { 0, 1, 2, 3, 4, 5 };", "static const int stage_map[6] = { 0, 1, 2, 3, 4, 5 };")
regdec = regdec.replace("auto IQ = [] (uint8_t x) { return (x & 0x80) ? qtbl[0x7F & -x] : -qtbl[x]; };", "")
regdec = lpc_members(regdec)
regdec = regdec.replace("IQ(f->r[", "lpc12_iq(qtbl, f->r[")

core = core.replace("@@inline int16_t sp0256_device::lpc12_t::limit(int16_t s)@@", limit)
core = core.replace("@@inline int sp0256_device::lpc12_t::update(@@", update)
core = core.replace("@@inline void sp0256_device::lpc12_t::regdec()@@",
                    "static inline int16_t lpc12_iq(const int16_t *qtbl, uint8_t x)\n{\n"
                    "\treturn (x & 0x80) ? qtbl[0x7F & -x] : -qtbl[x];\n}\n\n" + regdec)
# bitrevbuff isn't used (MAME's own note); drop it.
core = re.sub(r"/\* =+ \*/\n/\*  BITREVBUFF.*?\n}\n", "", core, flags=re.S)
core = core.replace("uint32_t sp0256_device::getb(int len)", "static uint32_t sp0256_getb(sp0256_t *s, int len)")
core = core.replace("void sp0256_device::micro()", "static void sp0256_micro(sp0256_t *s)")
core = core.replace("getb(", "sp0256_getb(s, ").replace("static uint32_t sp0256_sp0256_getb(s, sp0256_t *s, int len)", "static uint32_t sp0256_getb(sp0256_t *s, int len)")
core = core.replace("m_filt.regdec();", "lpc12_regdec(&s->filt);")
core = core.replace("m_filt.", "s->filt.")
core = re.sub(r"\bm_drq_cb\(1\);", "", core)
core = core.replace("SET_SBY(1);", "s->sby_line = 1;")
core = re.sub(r"\bm_(\w+)", r"s->\1", core)
core = core.replace("assert(", "SP0256_ASSERT(")
core = core.replace("s->rom[idx0 & 0xffff]", "sp0256_rom(s, idx0)").replace("s->rom[idx1 & 0xffff]", "sp0256_rom(s, idx1)")
assert "s->rom[" not in core
# LOG(...) calls span lines: drop them
core = re.sub(r"\bLOG(FIFO)?\((?:[^;]|\n)*?\);", "", core)
# Core 1 must never read flash: functions go in RAM (SP0256_RAM, which the
# firmware build defines as __not_in_flash_func), and the tables lose their
# const so they land in .data, in RAM.
for fn in ("lpc12_limit", "lpc12_update", "lpc12_iq", "lpc12_regdec", "bitrev32", "bitrev8", "sp0256_getb", "sp0256_micro"):
    core = re.sub(r"(\n(?:static )?(?:inline )?(?:int16_t|int|void|uint32_t|uint8_t) )%s\(" % fn, r"\1SP0256_RAM(%s)(" % fn, core)
# Not const isn't enough: GCC puts tables nothing writes in .rodata anyway
# (in flash), so they're placed in RAM by name (SP0256_DATA).
core = core.replace("static const int16_t qtbl[128]", "static int16_t SP0256_DATA qtbl[128]")
core = core.replace("static const int stage_map[6]", "static int SP0256_DATA stage_map[6]")
core = core.replace("static const uint16_t sp0256_datafmt[]", "static uint16_t SP0256_DATA sp0256_datafmt[]")
core = core.replace("static const int16_t sp0256_df_idx[16 * 8]", "static int16_t SP0256_DATA sp0256_df_idx[16 * 8]")
for t in ("qtbl[128]", "stage_map[6]", "sp0256_datafmt[]", "sp0256_df_idx[16 * 8]"):
    assert "SP0256_DATA " + t in core, t
core = core.replace("static inline int16_t SP0256_RAM(lpc12_iq)(const int16_t *qtbl, uint8_t x)", "static inline int16_t SP0256_RAM(lpc12_iq)(int16_t *qtbl, uint8_t x)")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "tsbus")
with open(os.path.join(OUT, "sp0256_mame.inc"), "w") as f:
    f.write("// license:BSD-3-Clause\n// copyright-holders:Joseph Zbiciak,Tim Lindner\n"
            "// Generated by tools/sp0256-port.py from MAME's src/devices/sound/sp0256.cpp\n"
            "// (lines 182-1150). Don't edit: change the tool and regenerate.\n\n")
    f.write(core.strip() + "\n")

rom = open(sys.argv[2], "rb").read()
assert len(rom) == 2048, len(rom)
rev = bytes(int("{:08b}".format(b)[::-1], 2) for b in rom)
assert hashlib.sha1(rev).hexdigest() == "e60fcb5fa16ff3f3b69d36c7a6e955744d3feafc", "not the AL2 ROM"
with open(os.path.join(OUT, "sp0256_al2.inc"), "w") as f:
    f.write("// The General Instrument SP0256-AL2 ROM, 2048 bytes at 1000h, in MAME's bit\n"
            "// order (each byte of al2.bin bit-reversed; SHA-1 e60fcb5f...).\n"
            "// Copyright Microchip Technology Inc. Microchip retains the intellectual\n"
            "// property rights to the algorithms and data it contains; distributed as\n"
            "// Microchip allowed in 2007, acknowledging its ownership (see NOTICE).\n"
            "// Generated by tools/sp0256-port.py.\n")
    for k in range(0, 2048, 16):
        f.write("    " + ", ".join("0x%02x" % b for b in rev[k:k + 16]) + ",\n")
print("wrote sp0256_mame.inc, sp0256_al2.inc")
