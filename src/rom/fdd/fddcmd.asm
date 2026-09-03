;******************************************************************************
;  fddcmd.asm — native disk-command extension for the TS-PICO EXROM
;
;  Assembled at $3000 and spliced into the EXROM (file offset $7000 of the
;  32K TSPICO.ROM) by tools/build-rom.py. See docs/FDD_COMMANDS_DESIGN.md.
;
;  This is the SKELETON that closes the build/pipeline gap: it establishes the
;  base address, the entry point the HOME-ROM hook will call, and the symbol
;  exports the build consumes. The command handlers themselves are stubs for
;  now — FDD_DISPATCH returns without acting, so a ROM built with this module
;  (but without the $25D6 hook wired in) behaves exactly like stock.
;
;  Assemble standalone (the build script does this for you):
;     sjasmplus --sym=fddcmd.sym src/rom/fdd/fddcmd.asm
;******************************************************************************

        DEVICE  NOSLOT64K          ; flat 64K, no paging model — we emit a slice

FDD_BASE        EQU $3000          ; keep in sync with tools/build-rom.py
        ORG     FDD_BASE

;------------------------------------------------------------------------------
; FDD_DISPATCH — entry point invoked by the HOME-ROM disk-token hook ($25D6).
;
; On entry (per §2 of the design doc): B = the BASIC token that was dispatched
;   $CF CAT   $D0 FORMAT   $D1 MOVE   $D2 ERASE
; and HOME is paged in. For now every command is a stub: we return with the
; carry flag CLEAR to mean "not handled — let the caller fall through to its
; normal path", so stock behaviour is preserved until the handlers land.
;------------------------------------------------------------------------------
FDD_DISPATCH:
        jp      FDD_MAIN

        db      "FDDCMD",0         ; signature — build.py locates/verifies this
FDD_VERSION:
        db      0                  ; format/version byte, bumped as this grows

FDD_MAIN:
        and     a                  ; CF = 0  -> "not handled"
        ret

FDD_END:

;------------------------------------------------------------------------------
; Emit exactly the module bytes ($3000..FDD_END) as a raw slice for the build.
;------------------------------------------------------------------------------
        SAVEBIN "fddcmd.bin", FDD_BASE, FDD_END-FDD_BASE
