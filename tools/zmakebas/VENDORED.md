# Vendored: zmakebas

`zmakebas` tokenizes a text-file Spectrum/Sinclair BASIC listing into a `.TAP`
file. We use it to compile the BASIC program sources under [`basic/`](../../basic/)
into the `.tap` files we ship (see [`basic/README.md`](../../basic/README.md)).

It is vendored (rather than cloned in CI) so the build is reproducible and works
offline. `zmakebas.c` is **public domain** ("Public domain by Russell Marks,
1998" — see the header of the source), so there are no license obligations on
carrying it here.

## Provenance

| | |
|---|---|
| Upstream | https://github.com/chris-y/zmakebas |
| Commit   | `787890f4c0fa144cb95755ff927e9fc057e40f0d` (2025-06-20) |
| Version  | 1.8.6 |

`chris-y/zmakebas` is Cat's Eye Technologies' fork of Russell Marks' original,
with later additions (ZX Spectrum `PEEK`/`VAL` tokens, ZX-Next `-3` mode, label
support, `err`/`on err` tokens for the TS-Pico's extended BASIC, etc.).

## What we kept

| File | Why |
|---|---|
| `zmakebas.c`          | The tokenizer source (the only file we compile). |
| `Makefile`            | Upstream build rules. We build the `zmakebas` target only — the default `all` target also builds an AmigaGuide doc via `rman`, which we don't have or need. |
| `zmakebas.1`          | man page — full reference for the input format and escapes. |
| `README.upstream.md`  | Upstream README, for provenance/reference. |

## Updating

To refresh against upstream:

```sh
git clone https://github.com/chris-y/zmakebas /tmp/zmakebas
cp /tmp/zmakebas/{zmakebas.c,Makefile,zmakebas.1} tools/zmakebas/
cp /tmp/zmakebas/README.md tools/zmakebas/README.upstream.md
# then update the Commit/Version rows above
```

## Building by hand

```sh
make -C tools/zmakebas zmakebas      # produces tools/zmakebas/zmakebas (gitignored)
```

You normally don't need to — `tools/build-basic.sh` builds it for you.
