#################################
# DATE: 2026/04/15              #
# FIRMWARE VERSION: 1.5         #
# ROM: 1.5W                     #
#################################

#############
# CHANGELOG #
#############

# - BIG NEWS: Implement Flash update, both to the SRAM and/or the Flash memory
# - Cleared TMP directory on the Pico Flash at startup (lines 1582-1586)
# - Option for sorting DIR
# - ROMPATCH command for patching default ROM to v1.2 from any previous version
# - Added logging function to 'activity.log' w/4 levels: INFO, WARNING, ERROR and CRITICAL. Notice CRITIAL not always means error,
#   but something that needs to be logged in any case
# - LOAD routine now validates block type, to avoid error on LOAD "" CODE for a BASIC pgm for instance
# - Implemented append newly SAVEd file to currently mounted TAP
# - Fixed small errors on mounting file and tap_idx references. Now mounting an already mounted file (remounting?)
#   behaves correctly, i.e. goes to the first block of the TAP
# - New, proper MOUNT_FILE() routine
# - LOAD now caches all files on internal Flash, and streams each byte (David's optimization)
# - Fixed LOADing non-existent filename from .TAP
# - Fixed special characters and trailing spaces in filename SAVE
# - New SAVE cmds: "tpi:blkrcv [CODE n,m], "tpi:getlog" [CODE n, 0], "tpi:gethelp", "tpi:getinfo", "tpi:verbose", "tpi:append"
# - Incorrect commands now show description of error (if verbose=enabled)
# - Incorporated some try..except blocks in troublesome, failing parts
# - Two consecutives LOAD "" with no file mounted is now properly handled
# - TAP loop around now works 
# - Nonexistent/nonworking SD Card is now reported on the log and the TS-Pico is halted
# - Small cleanup here and there 
# - Added reporting append status in tapdir header
# - Verbose options: CODE 1,0 - Display state; CODE 0,1 - Set OFF; CODE 1,1 - Set ON
# - Append options: CODE 1,0 - Display state; CODE 0,1 - Set OFF; CODE 1,1 - Set ON
# - Added SAVE "tpi:loglevel" - Display log level; CODE n,1 - Set level to n
# - tpi:rm will attempt to remove a dirinfo.tap file to make a dir empty so it can be removed
# - tpi:rm can also remove a file. A global dictionary isdir[name] stores if a name is a dir 
# - tpi:md gets the option CODE 1,0 to also change to the new directory
# - tpi:ffw/rew get an option to move by header with CODE n,1
# - Added optional parameter to SEND_MSG to force the display rather than temporarily
#   enabling TSP.VERBOSE.
# - Have tpi:zx48 always show its info message, and fix/add info to it
# - In MOUNT_FILE, compute offsets for the code block of romupdate.tap in buf[]
#   for the length patches rather than hard-coded offsets for when they change.
# - Have memdock and memboot report their setting if no CODE option is given
# - Added reporting memdock and memboot settings in getinfo
# - Modify SEND_MSG2 to also handle a short message rather than having to check
#   the length and instead use SEND_MSG.
# - Reworked SEND_MSG2 to print by character rather than 640 or 672 chars at a 
#   time so it can handle un-padded rows with newlines as well as backspaces. 
#   Allow 2 more lines displayed before getting the scroll prompt. 
#   After a 'y' keypress, use backspaces and spaces to erase the scroll message 
#   so we can continue on the line after the last content seamlessly. This dodges
#   the problem with printing a line starting with a space as the first line of 
#   the next screen. 
# - Change the DIR file listing stored in lista for showing the directory to
#   always show the file extension and shorten the base name to do so rather
#   than just truncate the name.
# - Added config.ini setting ZX_TAPE_COMPAT for selecting the regular (false, 
#   default) or compatible (true) tape load routines.
# - Added CODE option to tpi:zx48 to override the ZX_TAPE_COMPAT setting with
#   CODE 0,1 for regular and CODE 1,1 for compatible.
# - Check each config.ini paramater separately so we don't default all if one is
#   not present. This allow us to default only new parameters.
# - Remove showing "/sd" from the path name of the file in tapdir to be consistent.
# - Add command to erase LOG file (SAVE "tpi:getlog"CODE 0,255).
# - Convert msg bytearray to string that getlog sends to SEND_MSG2
# - Add feature to SEND_MSG2 scroll prompt of pressing keys 1 thru 9 to only
#   scroll by that many lines, with 0 scrolling by 10 lines.
# - Add function public_fname() similar to public_path() to print the full file
#   name
# - Added mounted tap info to getinfo of block number, file name and block type
# - Re-ordered some lines of getinfo for better grouping or related values
# - When truncating file names for DIR_FILES, indicate this with a '>' at the
#   end or before the dot of the file extension.
# - Add new tpi:ts2040 and tpi:picopt to gethelp (handled in ROM like tape and sdcard)
# - Fix getDock() not computing location and slot values without using int(), 
#   which had resulted in errors when this produced a float value.
# - Move DIR, TAPDIR, and PATH commands from LOAD to SAVE. LOAD is strictly for
#   mounting files by name or index, so LD_funct and EXT_LD_FUNCT were removed.
#   The previous LOAD commands now can have CODE parameters.
# - DIR: Add option of CODE nn,1: Show the full name for file index nn
# - TAPDIR: Add options of CODE n,0: Show n blocks before and after current
#   point; CODE n,1: Show n files around the current point (0=all); CODE n,2 is
#   like CODE n,0 but a tpi:tapdir is shown after; likewise, CODE n,3 is for files.
# - PATH: Add option of CODE 1,0 to show the full path of the mounted file.
# - LOGLEVEL: add labeling of level type when printing the level value: INFO,
#   WARNING, ERRORS, CRITICAL
# - Parse cmd for the first space rather than assuming it is at the 7th
#   character for commands that have a file name argument (cd, md, rm) because
#   they are all two letter commands. Now, they can be other lengths, the
#   SA_funct entry doesn't have to contain a space, and commands no longer also
#   match words with more characters (e.g., tpi:dirt would work for tpi:dir).
# - Add option to cd of CODE 2,0 to print the new path after changing (this is
#   what md uses if given the CODE 1,0 option to cd to the new directory)
# - Handle PC (CR/LF) and Linux (LF) end of line markers in SEND_MSG2 in addition 
#   to the existing Timex (CR) line endings. This allows us to print content from
#   other text files loaded onto the Pico or from the SD card regardless of source 
#   platform. 
# - Added individual command help by naming the command in "tpi:gethelp command".
#   This looks for files in the /TS/help folder on the Pico flash of the command
#   name given with a .txt extension and prints the contents of the file. You 
#   could add files with other names to just print reminder text for other stuff
#   like even BASIC commands. SEND_MSG2 handling all line endings helps here.
# - Fix mistake of chaining to CDIR() rather than DIR() from md
# - Fix bug in LOAD_CONFIG where the ROM_SLOT setting from config.ini would get 
#   overwritten by the default.
# - Add loglevel to getinfo screen
# - Reverse the order of some CODE option arguments to be a general format of
#   the operation number being first and the operation value being second: 
#   append, dir, ffw, rew, getlog, loglevel, verbose, and zx48.
# - Removed toggle options for append and verbose
# - Add confirmation prompt to tpi:rm unless CODE 255,0 is given
# - Add BAD_CODE() helper and reports to more commands of invlaid code values
# - Fix bug in TS2068_IO causing DIR_FILES to make a listing of the root 
#   directory after a SAVE since the current directory had not been set since 
#   mounting the SD.
# - Fix mounting of new tap file when none was mounted for older tspico_io.py version.
# - Add list of commands that have specific help to end of "tpi:gethelp" text
# - Add a FIFO check to ZX48_IO upon return from Spectrum mode to clear the
#   queue which may not be empty.
# - Tweak some error status codes so the BASIC error makes more sense now that
#   the ROM is reporting different codes.
# - Add status code constants to help know what error reports they make
# - Tweak and update the gethelp text
# - Update messages that rompatch and zx48 show 
# - Allow "\*" in a SEND_MSG2 string to produce the copyright symbol, and filter
#   out codes > 127 since they will usually fail. The print routine we have in
#   the EXROM is limited. Also, ignore a leading CR (0x0D) in the message as far
#   as counting as a scroll line. This allows a separator line at the start to
#   separate short outputs but not cause the scroll to happen with that blank
#   line at the top. 
# - Add a leading CR to the beginning of gethelp command help file text to
#   visually separate each from text before.
# - Changed index loading to not use a leading special character and just be a
#   number (LOAD "tpi:nnn"). Currently, you have to give 3 digits to avoid the
#   two-character tpi command ROM bug.
# - Add tpi:tap to give the name of a new tap file to create and mount with
#   append mode on. MOUNT_FILE/tapdir/ffw/rew handle an empty file now.
# - Add optional parameter to SEND_MSG2 to not expand keywords (only affects
#   FREE and STICK for now)
# - Added an interactive DIR with CODE 3,0 that pages through files (not dirs),
#   letting you press a key to mount a file.
# - Added an interactive CD by adding a space (SAVE "tpi:cd "). Until the
#   two-letter tpi command bug is fixed, you have to do this space hack or make
#   a new command for it.
# - Added option to give "on" or "off" as an argument to tpi:verbose and
#   tpi:append (SAVE "tpi:verbose on"). Also added giving the log level number
#   as an argument to loglevel (SAVE "tpi:loglevel 2") and "clear" as an
#   argument to getlog (SAVE "tpi:getlog clear").
# - Broke out the part of CD that checks the new name and does the change into a
#   separate routine so it can be called by the interactive CD routine.
# - Changed findArgs to getArgs and have it return the arg string instead.
# - Moved the command help files all to the SD card in an /sd/help folder.
# - Extended the zx48 compatible loader option to be able to give a custom
#   buffer size by giving the value as >= 16384 on the CODE 1,* option. CODE 1,1
#   uses the default buffer size.
# - Move flushing RX queue up before sending codes to the ROM in SEND_MSG2 and
#   other places the 0x86 ROM function is used.
# - Add utility function isTapMounted() and check in some places that were
#   showing an empty tap when a non-tap file was mounted.
# - Have BLKRCV use small buffers to avoid a large allocation.
# - CDIR: add CODE 1,2 and 1,3 to chain to DIR CODE 2,0 and 3,0
# - GETLOG: add a try/except around reading the log file in case the file is too
#   large to allocate the buffer. Need to figure out a longer term fix.
# - MDIR: Have CODE 1,0 chain to CDIR CODE 2,0 rather than PATH CODE 1,0
# - Removed TPI:TEST command
# - External SAVE commands: Pass MQ and TSP to functions along with pre and cmd,
#   and try to import the EXT_SA_FUNCT from /TS/extcmd.py to bring in any
#   external commands defined. Also updated that file with sample commands.
# - Renumber error constant names because ROM error code bug had been reporting
#   them off by one when using SEND_MSG with verbose on. Also add a workaround.
# - Added utility functions: WAIT_TX_RECEIVED, EMPTY_TX_FIFO, and EMPTY_RX_FIFO
# - Rename tpi:tap to tpi:newtap
# - Swapped FFW/REW CODE 2,n and 1,n so that 1,n is 0,n with another tapdir, and
#   2,n is move by file with 3,n being 2,n with another tapdir. 0,n remains as-is
# - Improve error handling for GETHELP, MDIR, RM, VERBOSE, APPEND
# - Shorten some command names: getinfo->info, gethelp->help, getlog->log,
#   memboot->boot, memdock->dock
# - Have the LOG() function add the prefix of "INFO:","WARNING:","ERROR:", or
#   "CRITICAL:" to the message based on the log level parameter.
# - Change gethelp to not list external help files by default. You have to give
#   the command "tpi:gethelp ?"
# - ZX48: change CODE so that first is non-zero to suppress the help text, and
#   the second is 0 for default load routine, 1 for normal, 2 for compatible,
#   and 16384 or greater for compatible with a custom buffer size.
# - NOP: Added CODE 1,* to flush RX queue, and CODE *,1 to flush TX queue
# - Added back tpi:memboot and tpi:memdock as aliases for tpi:boot and tpi:dock
# - Unified the interactive CD and DIR menu code to a generic ListMenu() function
# - Improve handling with MOUNT_FILE calls in ROMPATCH and PROCESS_CMD
# - Replace some patterns with dir_exists() and file_exists() calls
# - Fix OFF_TABLE() to look at the size of temp.tap and not TSP.totlen since it
#   looks at that file and not TSP.f_name, which can be not the same file when
#   dck/romupdate.tap are used when TSP.f_name points to a .dck or .rom file.
# - Add a call to OFF_TABLE() when using dck/romupdate.tap as the temp.tap file
#   for a .dck or .rom load so that when .tap operations access temp.tap, they
#   have the correct information.
# - Add storing the previously mounted file name and tpi:path CODE 1,1 to
#   display it.
# - Add storing previous memdock setting and tpi:dock CODE 0,1 to display it as
#   well as CODE 0,2 to swap to it, storing the current one as the previous.
# - Removed storing the previously mounted file name and tpi:path CODE 1,1 to
#   display it.
# - Removed error code workaround in SEND_MSG since ROM 1.5 fixes the problem.
# - Fix: add global MQ to WAIT_TX_RECEIVED
# - Move init code for talking to the ROM down into loop for ListMenu to reduce
#   the delay between it and the sending of the message.
# - Fix dock code 0,2 not swapping to prev dock slot
# - Add a timeout in TS2068_IO for incomplete commands
# - If a .tap fails to load, set TSP.f_name to empty rather than previos name.
# - Change DCK_IMAGE to use small buffers rather than two 8K ones
# - Fix ffw/rew errors with an empty tap file.
# - Add shorten_filename utility function for new long name shortening in the
#   middle of the name but not including the extension.
# - Incorporate Ricardo's mod for interactive list of 16 rather than 10 items.
# - Trying to just use direct writes in ListMenu rather than building a big
#   string to avoid the ROM timing out.
# - Move tpi:dir CODE 3,0 out to tpi:idir and change tpi:cd CODE 1,3 to 1,1 to
#   chain to tpi:idir.
# - Add tpi:dir CODE 2,n to start the list at file n instead of 0
# - Add a confirmation prompt for clearing the log, and make the CODE 255,0
#   an option for "tpi:log clear" to bypass the confirmation rather than it
#   being an alias for clear.
# - Adjust the logic after SAVE_TS is called to handle the case of the save
#   being aborted.
# - Adjust use of function 0x86 for extra 0x40 code with 1.5W ROM 
# - Tweaking the logic after SAVE_TS is called to handle the case of the save
#   being aborted.
# - Have GETHELP list any external commands available
# - Add Ricardo's global path interactive CD feature as CODE 0,1 option. Adjust
#   it and ChangeDir so it works from any directory, includes /TAP, and updates
#   the directory list when they are made or removed in tpi:md and tpi:rm.
# - Change ffw/rew CODE 1,x and 3,x to chain to tapdir with CODE x,255
# - Add: `global MQ` to ACTIVATE_SD
# - Adjust the logic in SEND_MSG_PROMPT_YN after getting the character
# - More attempts to adjust the logic after SAVE_TS is called to handle the case
#   of the save being aborted, but finding other issues making it difficult.
# - Found that ENA_SD() in tspico_io.py was leaving MQ active after activating
#   the SD card, confusing checks of both after SAVE_TS. Adjusted logic to only
#   check if the SD is mounted and only then try re/mounting and updating the
#   directory, otherwise skip and just make sure MQ is active after all that.
# - Have tpi:rm return Invalid Argument error if a name is not given instead of
#   Invalid Filename, so that is only returned if the file wasn't found.
# - Have tpi:md report End of File error if the dir exists but change to it if
#   CODE 1,0 was given and return no error. If the name exists as a file, return
#   error Invalid Filename. If no name is given, return Invalid Argument error.
# - Fix handling of newlines after a full 32 character line in SEND_MSG2.
# - Fix tpi:idir to handle an empty directory 
# - Fix dirinfo.tap not getting char(126) "FREE" replaced with "?"
# - Remove the 2 second sleep from DIR
# - Add turning on the LED for other DIR forms, interactive DIR and interactive
#   CD where the pico is busy.
# - Have GETHELP no have SEND_MSG2 expand keywords (really just ~/FREE) to
#   preserve column alignment in help files that might use ~.
# - Move try/except around first call to GET_DIRS into the function as it is
#   used in other places, and set return empty on error.
# - For tpi:help, check for /sd/help only in one place, and if not found, return
#   error Q instead of F. Also make a help topic not found log as a warning.
# - Have tpi:md not call DIR_FILES if it's going to chain to CD
# - Tweak the UI for the interactive commands to be more clear
# - Typos, have GET_DIRS add the root path to the list, Make bottom bar in
#   ListMenu a page incicator by showing '=' where the list is with the whole
#   line as the full content and other pages as '-', have interactive CD not
#   show ".." when at the "root" /TAP dir.
# - Add a gc.collect after most init and before calling GET_DIRS and the main loop.
# - Remove ACTIVATE_MQ calls after calls to MOUNT_FILE since it does that.
# - Have COPY_FILE return success bool
# - Re-work MOUNT_FILE to not corrupt TSP fields if mount fails and to try to
#   remount the current file on failures that may have overwritten temp.tap or
#   temp.bin. So you have to pass in the filename rather than set TSP.f_name.
# - Change log_entries to be a list of strings
# - Change DIR_FILES to build the dir msg from a string array
# - public_path and public_fname can optionally shorten to a given length
# - Split out upgrade functions into separete tspico_upgrade.py
# - Optimize string construction using the % operator rather than +
# - Make ListMenu choices dictioniary and loglevel strings global to not re-create
# - In BLKRCV, use a memoryview on the buffer
# - In MDIR, fix message var name error and avoid calling GET_DIRS by just
#   appending the new path to alldirs and re-sorting.
# - Construct large SEND_MSG2 strings from making a string array rather than
#   multiple appends. Move extra leading newlines from strings to function.
# - Optimize SEND_MSG2 to do fewer checks normally for special characters
# - Optimize ListMenu to write strings as is goes rather than make a big page
#   string to write at once.
# - Change 'b' to 'B' and 'Kb' to 'kB' in memory sizes
# - Change named constants for STATUS to const() class and start name with underscore.
# - Change isdir dictionary to a dirs_upper list of dir names
# - Move gc.collect at loop bottom to only when SAVE_LOG is called
# - Add clearing RX/TX queues at bottom of loop and report if not empty
# - Try tightening DIR_FILES by del big vars when done with them, make nom a
#   bytearray(32) to not reallocate a string for each dir entry that we
#   ultimately format to 32 chars anyway.
# - Tweak header for tapdir. Fix printing } as ? in SEND_MSG2.
# - In MOUNT_FILE when remounting, restore the offset and index

# TO DO:
#=======
# - Debug LPRINT, LLIST, etc
# - LOAD and SAVE config.ini
# - GUI
# - Primary support for TZX, SNA and Z80 files
# - Test NMI routine to SAVE snapshots
# - Test "RST 8"-like ROM replacement with TS 2068 and/or Spectrum ROMs
#   for adding new, different OS versions that would also take advantage
#   of the TS-Pico hardware.
# - Add descriptive of each slot in the Flash in config.ini
# - "Golden commands" for Assembler
# - Dedicated SPI for the SD Card
# - Test special "update" firmware
# - Add support for choosing the code paths for DCK+ROM or DCK only
# - Add command to eject SD card and mark ejected so ACTIVATE_SD returns false
#   so routines can handle it and bail or they could look at the SD flag ahead
#   of that. 


import utime
import _thread
import time
import gc
import os
import sys
import json

from micropython import const
from rp2 import StateMachine, asm_pio, PIO
from machine import Pin, freq, SPI

from TS.sdcard import *

# ─── DUAL-PORT MIGRATION (Ryan's tspico.py -> dual-port) ───────────────
# Three things changed from Ryan's original single-port import:
#
#   1. Module path:  `tspico_io` -> `TS.tspico_io`
#      Always pull from the frozen module (baked into the UF2 by
#      manifest.py). A root-level /tspico_io.py (Ricardo's older one)
#      would shadow the frozen one and silently pull in stale single-
#      port code; using the explicit TS. prefix defeats that risk.
#
#   2. PIO program:  `TS_IO` -> `TS_IO_DUAL`
#      The single-port PIO is gone in the dual-port architecture.
#      TS_IO_DUAL decodes the A0 address bit (GPIO 10) to route Z80
#      reads of $0E (data) vs $0F (status) into separate handling.
#      The Z80's $0F polls are answered by the Y register (set to
#      0xFFFFFFFF = always ready) instead of by interleaving 0x40
#      bytes into the TX FIFO.
#
#   3. Added import: `OPEN_NOFILE_TAP`
#      Pre-opens /assets/nofile.tap at boot so LOAD "" (no prior
#      mount) doesn't pay file-open latency in the hot path. Without
#      this, opening the file takes 1-5ms during which the Z80 reads
#      stale TX bytes and reports Report J.
#
# See docs/DUAL_PORT_DEVELOPMENT.md §7 for the full migration narrative.
# ───────────────────────────────────────────────────────────────────────
from TS.tspico_io import (
    sel_bank, set_ctrl, set_dck,
    TS_IO_DUAL,                          # was: TS_IO (single-port)
    LOAD_TS, LOAD_SERVE, LOAD_ZX, LOAD_ZX_C,
    SAVE_TS, SAVE_ZX,
    OPEN_NOFILE_TAP,                     # added: cached nofile handle
    RX_CAPTURE, MQ_TO_IDLE, MQ_STATUS,   # issue #51: SYNC / BREAK abort
    RX_DMA,                              # the pre-header by DMA (v1.29)
    STREAM_DMA,                          # blind sends by DMA (v1.29)
    TX_ROOM, RX_WORD, PORT_0F, TX_DEPTH, # issue #51 stage 4: command I/O
    RX_BLOCK, RXB_ABORT, RXB_OK,         # printer bodies, ZX tpi:
    ZX_FLUSH_TX, ZX_ROOM, ZX_STALL_MS,   # ZX48 mode (issue #51 stage 6)
    MQX,                                 # fast MQ.exec (9.6 ms -> 18 us)
    DRAIN_STDIN,                         # keep Ctrl-C reachable over USB
)
from TS.printer import TextCapture, next_name, write_bmp, VLPRINT, VSCREEN
from TS import catalog
from TS import native
from TS import channels
from TS import tspico_io                                                # SD_MOUNT: set below SAVE_MOUNT
from array import array

# ─── Virtual printer: LPRINT / LLIST -> .TXT, COPY -> .BMP ──────────────
# (TS/printer.py; the 2068 sends printer output here while TPMODE bit 0 is
# set -- SAVE "tpi:picopt".) Text is buffered in RAM and written to the SD
# card only while the Z80 is parked in a READY wait: see PRINT_FLUSH.
PRT = TextCapture()
prn_path = None             # the open /sd/VLPRINT capture; None: next char opens one
bmp_size = (512, 384)       # SAVE "tpi:bmp" CODE x,y
PRINT_FLUSH_AT = 4096       # buffered text that forces a flush mid-printout

#####################
# SERVICE FUNCTIONS #
#####################

@asm_pio(
    autopull=True,
    pull_thresh=8,
)
def NULL_SM():
    nop()

#######################
# MODULE-LEVEL CACHES #
#######################

# ListMenu key-to-index mapping: 0-9 (ASCII 48-57), Q-Y (ASCII 81,87,69,82,84,89)
# Created once at module load instead of every ListMenu() call
LISTMENU_CHOICES = {
    48: 0, 49: 1, 50: 2, 51: 3, 52: 4, 53: 5, 54: 6, 55: 7, 56: 8, 57: 9,  # 0-9
    81: 10, 87: 11, 69: 12, 82: 13, 84: 14, 89: 15  # Q W E R T Y
}

# Log level labels - shared by LOG() and LOGLEVEL()
LOG_LABELS = ("INFO", "WARNING", "ERROR", "CRITICAL","SPECIAL")

# True from ACTIVATE_SD (which parks MQ on NULL_SM and hands GPIO 2-4 to
# SPI) until the next ACTIVATE_MQ. FAIL_CMD reads it: a handler that raised
# while the card had the bus would otherwise leave the Z80 talking to a
# parked state machine for the rest of the session.
sd_active = False

# The directory before the last successful change: MOVE TO "" (tpi:cd -) goes
# back to it. One level, like cd -.
prev_path = None

# The caches DIR_FILES / GET_DIRS fill for the current card. Empty until a card
# has been read: with no card at boot they stay so, and the commands that list
# or index them are refused until a card is in (SD_NEEDED).
files = []
files_upper = []
dirs = []
dirs_upper = []
lista = ""
alldirs = []
sd_space = None                                                                # (total, free) bytes, as the last listing read them

# ─── Colour in SEND_MSG2 (the CAT listing and tpi:info, 2026-10-02) ─────
# The 2068 prints INK (10h) and PAPER (11h) followed by a value. The ROM's
# string reader stops on 00h and 03h, so values 0 (black) and 3 (magenta)
# can't be sent, nor any 0 that would switch INVERSE, BRIGHT or FLASH off.
# What is used: colours 1, 2, 4-7; 8 ("transparent": the colour already on
# screen, i.e. the user's own colours on a fresh line) to go back to normal;
# and INK 9 ("contrast": black or white to suit the paper). Only messages
# sent with SEND_MSG2(..., colour=True) keep these; in any other text they
# are dropped, as before.
INK_ = "\x10"
PAPER_ = "\x11"
NORMAL_ = PAPER_ + "\x08" + INK_ + "\x08"

RXD = None          # TS2068_IO's RxDMA (the pre-header by DMA), for PROCESS_CMD's tail

# What a command that needs the card answers when there is none: always
# shown (SEND_MSG forces it), with Report J -- "Invalid I/O device" is the
# report that means the device isn't there.
NO_CARD_MSG = "No SD card. Insert one and\rtry again."                 # 37 chars wrapped mid-word at 32

# ─── Protocol bytes by name (issue #16) ─────────────────────────────────
# The ROM function codes, the bytes that end a string or a loop, and the
# first byte of a pre-header, as docs/PROTOCOL.md names them. Each use
# site also says the number in its comment (0x86 ...): that's how many
# people know these. See PROTOCOL.md §5 for each function's exchange.
#
# ROM function codes: a reply's first byte, in place of a status, picks
# what the Z80 does with the bytes after it.
FN_PRINT_STRING = const(0x81)       # print the text up to STR_END (main screen)
FN_PRINT_STRING_KEY = const(0x82)   # print, then wait for a key and send it back (unused)
FN_PRINT_CHAR = const(0x83)         # print one character (unused)
FN_RETURN_KEY = const(0x84)         # wait for a key and send it back (unused)
FN_GET_STATUS = const(0x85)         # the Z80 sends a keyboard/aux mask (unused)
FN_PRINT_LOOP = const(0x86)         # pages of text, a key between them, LOOP_END ends it
FN_PRINT_LOOP_LOWER = const(0x88)   # FN_PRINT_LOOP on the lower screen (ROM 2.1 only)
# Inside those replies:
STR_END = const(0x00)               # FN_PRINT_STRING: the end of the text. FN_PRINT_LOOP:
                                    # the end of a page -- the Z80 waits for a key
LOOP_END = const(0x03)              # FN_PRINT_LOOP: the end of the loop (no key wait)
# The first byte of a pre-header (pre[0]):
PRE_HEADER = const(0x00)            # a tape header block: LOAD / SAVE
PRE_DATA = const(0xFF)              # a tape data block: LOAD / SAVE
PRE_CMD = const(0x42)               # 'B': a tpi: command, or the printer (pre[1] 4-6)

# Status codes returned to the 2068 - each maps to a BASIC error
_1_OK = const(1)
_2_R_Tape_load = const(2)
_3_F_Invalid_file = const(3)
_4_Q_Parameter = const(4)
_5_C_Nonsense = const(5)
_6_6_Num2Big = const(6)
_7_8_EOF = const(7)
_8_A_Invalid_arg = const(8)
_9_9_STOP = const(9)
_10_J_Invalid_IO = const(10)
_11_D_Break = const(11)


# ─── DUAL-PORT MIGRATION: optional telemetry (stage 9) ────────────────────
# Comprehensive event logging for diagnosis. Each TLM() call prints an
# event with timestamp (microseconds since boot), delta from previous
# TLM call, and TX/RX FIFO occupancy. Frozen-module overhead is
# negligible when the flag is False.
#
# DEFAULT: TLM_ENABLED = False — Ryan's preferred experience (no
# telemetry noise on a normal run, zero overhead in hot paths).
#
# TO ENABLE FOR A TESTING SESSION (pick one):
#
#   1. EASIEST — edit /main.py on the Pico's flash. Find the line:
#         TS.tspico.TLM_ENABLED = ...   (or `dev_tspico.TLM_ENABLED`)
#      and set it to True. Reboot. No UF2 rebuild needed.
#
#   2. AT THE REPL (transient — gone on reboot):
#         import dev_tspico
#         dev_tspico.TLM_ENABLED = True
#
#   3. EDIT THE DEFAULT BELOW to True, commit. Permanent for that copy.
#
# When False, both TLM() and TLM_RESET() return immediately with zero
# work — no string format, no FIFO read, no print, no timestamp track.
# This is the right setting for normal operation; flip to True only
# when you actively need the diagnostic stream.
# ─────────────────────────────────────────────────────────────────────────
TLM_ENABLED = False

# Build stamp — which build is actually on the Pico. Logged at LOAD_CONFIG
# entry, printed at import so it lands before TLM is enabled, and shown by
# tpi:info so it is readable from the 2068 as well as over USB.
#
# Generated, not hand-written: tools/gen-buildinfo.py writes TS/buildinfo.py
# from git before the frozen modules are staged, and manifest.py freezes it.
# It used to be a literal, which rotted -- it read "2026-05-27-J (inline-wrt
# SEND_MSG2 + suppress_scroll<500)" long after #104 and #106 had reworked both
# of those, so it described behaviour the firmware no longer had. A stamp has
# to come from the build or it will lie.
#
# Guarded, because a hand build that skips the generator must still run; it
# then reports "unknown". FW_VERSION below is the release number and is
# maintained by hand on purpose -- this is the commit underneath it.
try:
    from TS.buildinfo import COMMIT, BRANCH, DIRTY
    BUILD_VERSION = "%s%s (%s)" % (COMMIT, "+dirty" if DIRTY else "", BRANCH)
except ImportError:
    BUILD_VERSION = "unknown (no buildinfo)"

# The TS-Pico version: the firmware and its TS-2068 ROM share one number from
# 2.0 on. 2.1 is the release ROM: the disk-command build from tools/build-rom.py
# (PEEK 101 = 21h). tpi:info reports this, not the FW_VERSION an older
# config.ini may still hold.
FW_VERSION = "2.1"
# Self-labeling: when loaded as the frozen module __name__ == "TS.tspico";
# when loaded via the dev override __name__ == "dev_tspico". This file is
# kept byte-identical between the two locations so the stamp prints the
# correct label regardless of which copy actually loaded.
print("[%s] BUILD_VERSION =" % __name__, BUILD_VERSION)

_tlm_last = 0   # last TLM timestamp, microseconds


def TLM(action, detail=""):
    """Log one event to the REPL with timing and FIFO state.

    When TLM_ENABLED = False this returns immediately with zero work
    (no formatting, no FIFO read, no print) so it's safe to leave
    TLM() calls scattered through hot paths in production builds.
    """
    if not TLM_ENABLED:
        return

    global _tlm_last
    try:
        now = time.ticks_us()
    except:
        now = 0
    dt = time.ticks_diff(now, _tlm_last) if _tlm_last else 0           # ticks_us wraps every ~18 min
    _tlm_last = now

    try:
        tx = MQ.tx_fifo()
        rx = MQ.rx_fifo()
        fifo = "tx=%d rx=%d" % (tx, rx)
    except:
        fifo = "tx=? rx=?"

    if detail:
        print("[TLM %d dt=%d %s] %s: %s" % (now, dt, fifo, action, detail))
    else:
        print("[TLM %d dt=%d %s] %s" % (now, dt, fifo, action))


def TLM_RESET(tag=""):
    """Reset TLM timer at the start of a new operation.

    Also a no-op when TLM_ENABLED = False.
    """
    if not TLM_ENABLED:
        return

    global _tlm_last
    try:
        _tlm_last = time.ticks_us()
    except:
        _tlm_last = 0
    print("[TLM ===== %s =====]" % tag)


class PICO_STATUS():                                                            # Class for the object that holds TS-Pico's current status
    
    def __init__(self, init_values):                                            # init_values is a dictionary read at startup; read below
                                                                                # The variables that define current status of the TS-Pico are:
        self.append = False                                                     # whether or not append new SAVEd file to currently mounted TAP file
        self.bank_sm = 0                                                        # initial value for the BANK StateMachine
        self.cur_path = "/sd/TAP"                                               # string holding the current path
        self.f_name = []                                                        # string of current filename
        self.offset = 0                                                         # integer pointer to current position on a large TAP file
        self.offset_tbl = []                                                    # table of offsets for each segment in a .TAP file
        # LOAD search bookkeeping, used by LOAD_TS to bound the Z80's
        # retry loop. ld_start is the offset a search began at (-1 = no
        # search in progress); ld_wrapped records that the tape has been
        # round once since then. Together they let LOAD_TS stop after one
        # full pass instead of cycling forever -- there is no BREAK signal
        # from the Z80 to stop it (docs/rom-analysis/BREAK_AND_ABORT.md).
        self.ld_start = -1
        self.ld_start_idx = 0
        self.ld_wrapped = False
        self.tap_idx = 0                                                        # pointer to position of next block to be LOADed in the mounted TAP 
        self.totlen = 0                                                         # integer holding total length in bytes, of a large TAP file
        self.zx48 = False                                                       # boolean for ZX Spectrum compatibility mode
        
        # Should probably move these from try/except to "if x in init_values" 
        # See LOAD_CONFIG about there should be only one defaults definition.

        try:                                                                    # try to retrieve configuration values from init_values passed on startup
            self.DCK_SLOT = init_values["DCK_SLOT"]                             # What slot of Flash or SRAM contains the startup DCK image (0-15). default = 0 (Spectrum cartridge)
        except:                                                                 # if fail, assume hard-wired values
            self.DCK_SLOT = 0
        try:
            self.ROM_SLOT = init_values["ROM_SLOT"]                             # What slot of Flash or SRAM contains the startup ROM image (0-15). default = 1 (TS-Pico ROM)
        except:                                                                 # if fail, assume hard-wired values
            self.ROM_SLOT = 1
        try:
            self.ROM_SM = init_values["ROM_SM"]                                 # Bit pattern for Flash/SRAM activation during DCK/ROM access. Default = 0x0A, or 1010 meaning both assigned to Flash
        except:                                                                 # if fail, assume hard-wired values
            self.ROM_SM = 0x0A
        try:                                                                    # try to retrieve configuration values from init_values passed on startup
            self.LOG_LEVEL = init_values["LOG_LEVEL"]                           # Log level: 0 info, 1 warning, 2 errors, 3 critical. Default = 2 
        except:                                                                 # if fail, assume hard-wired values
            self.LOG_LEVEL = 2
        try:                                                                    # try to retrieve configuration values from init_values passed on startup
            self.VERBOSE = init_values["VERBOSE"]                               # Verbosity of status messages. Default = False, no verbosity. 
        except:                                                                 # if fail, assume hard-wired values
            self.VERBOSE = False
        self.FW_VERSION = FW_VERSION                                            # the code's own version, never config.ini's
        try:                                                                    # try to retrieve configuration values from init_values passed on startup
            self.ROM_VERSION = init_values["ROM_VERSION"]                       # Current ROM version.
        except:                                                                 # if fail, assume hard-wired values
            self.ROM_VERSION = FW_VERSION
        try:                                                                    # try to retrieve configuration values from init_values passed on startup
            self.ZX_TAPE_COMPAT = init_values["ZX_TAPE_COMPAT"]                 # boolean for ZX Spectrum "compatible" tape routine (True) or normal (False)
        except:                                                                 # if fail, assume hard-wired values
            self.ZX_TAPE_COMPAT = False

        self.bank_sm = (self.DCK_SLOT * 16) + self.ROM_SLOT                    # bit pattern to store slot of DCK/ROM. 4 bits each. Default 0001 0000
        # The SD card, as the last mount found it (ACTIVATE_SD / SD_NOTE_CARD).
        # sd_cid is the card's CID register (maker, product, serial number):
        # a different value on a later mount means a different card.
        self.sd_present = False
        self.sd_cid = None
        self.save_no_card = False                                               # the dispatcher's card check for this SAVE failed
        self.sd_listing_ok = False                                              # DIR_FILES read the current folder without errors
        self.listing_stale = False                                              # a ZX48 SAVE wrote into the folder: REFRESH_LISTING
        self.dck_prev_slot = self.DCK_SLOT
        # tpi:dock's "previous setting" starts as the setting itself. It was
        # always 2 (flash), but config.ini can put the DOCK in SRAM (ROM_SM
        # bits 2-3 = 1, as getDock reads them): then CODE 0,1 named the wrong
        # memory and CODE 0,2 swapped to a flash slot nobody had chosen.
        # (2026-09-30 audit, §2 #19.)
        self.dck_prev_mem  = (self.ROM_SM >> 2) & 3


# ─── DUAL-PORT MIGRATION: new helper DEACTIVATE_SD ─────────────────────
# In Ryan's single-port version, the SD-teardown logic lived inline at
# the top of ACTIVATE_MQ. The dual-port refactor splits it out:
#
#   1. Some boot paths (and the SAVE branch in TS2068_IO) need to call
#      ACTIVATE_MQ without first having mounted /sd; Ryan's old loop
#      `while True: try: umount; except: break` wasted ~10ms on every
#      such call retrying the unmount.
#   2. The dual-port protocol is sensitive to bus-handover timing.
#      Splitting teardown lets us do it deterministically: unmount
#      once, then clamp the SPI data lines LOW before the PIO reclaims
#      them. This eliminates the tri-state window where Z80 D6 could
#      float high — the original Report D root cause (see
#      docs/DUAL_PORT_DEVELOPMENT.md §1).
# ───────────────────────────────────────────────────────────────────────
def DEACTIVATE_SD():
    """Tear down SD card access and safe the shared bus lines."""
    TLM("DEACTIVATE_SD enter")
    try:
        os.umount("/sd")
        TLM("  /sd unmounted")
    except:
        TLM("  /sd already unmounted")

    U3_CS = Pin(28, Pin.OUT, Pin.PULL_UP)
    U3_CS.value(1)

    # GPIO 2-4 are the SD card's SPI lines (SCK/MOSI/MISO) and also D0-D2
    # of the 2068 bus. Leave them driven LOW, not floating, until the bus
    # state machine takes them back (ACTIVATE_MQ, straight after). Kept
    # as harmless; whether it's needed at all -- U6 keeps the 2068 off
    # these pins during SD use since #61 -- needs a scope (audit §4). It is
    # not the "Report D fix" this comment used to claim: that was about
    # D6, which is GPIO 8.
    for p in (2, 3, 4):
        Pin(p, Pin.OUT).value(0)
    TLM("DEACTIVATE_SD exit", "GPIO 2-4 clamped LOW, U3_CS=HIGH")
    return


# ─── DUAL-PORT MIGRATION: ACTIVATE_MQ rewritten ────────────────────────
# Five changes from Ryan's single-port version:
#
#   1. PIO program:  TS_IO       -> TS_IO_DUAL
#      Routes Z80 reads of $0E vs $0F into separate handling so the
#      Y register can answer status independently of the TX FIFO.
#
#   2. PIO clock:    15 MHz       -> 30 MHz
#      The dual-port decode adds ~7 instructions to the read path.
#      30 MHz keeps the total well within Z80's data setup window.
#      RP2040 PIO can run up to half the CPU clock (135 MHz at our
#      270 MHz setting) so 30 MHz is conservative.
#
#   3. Y stays BUSY after activation (it was set READY here at first)
#      The caller loads its reply into TX and then calls MQ_READY():
#      see the note in the body for the Report J race that READY-on-
#      activation caused.
#
#   4. SD teardown REMOVED
#      The old `while True: try: os.umount; except: break` loop and
#      the U3_CS write are gone — DEACTIVATE_SD() handles that now.
#      Callers must call DEACTIVATE_SD() FIRST, then ACTIVATE_MQ().
#      (Stage 4 updates TS2068_IO to do this in the right order.)
#
#   5. NO pre-load of 0x01 here  ← CRITICAL, easy mistake
#      ACTIVATE_MQ is called both at boot AND mid-command (after
#      SD operations in MOUNT_FILE etc.). At boot we need a pre-load
#      so the Z80's first status read finds 0x01. But mid-command,
#      the next thing in the call chain (SEND_MSG, etc.) writes its
#      own status — adding a pre-load HERE would put TWO 0x01s in
#      TX, the Z80 only reads one, and the second sits in TX and
#      gets misread later in the protocol (the orphan-byte family).
#      Boot-time pre-load goes in TS2068_IO() instead, ONCE.
#      (This was "Bug 1" in docs/DUAL_PORT_DEVELOPMENT.md §8.)
# ───────────────────────────────────────────────────────────────────────
def ACTIVATE_MQ():                                                                                # Re-enable TX/RX SM, after a SDCard access (DUAL-PORT)

    global MQ
    global sd_active

    TLM("ACTIVATE_MQ enter")
    sd_active = False
    MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000, out_base=Pin(2, Pin.OUT),
                      in_base=Pin(2, Pin.IN), jmp_pin=Pin(11),
                      sideset_base=Pin(12, Pin.OUT))

    MQ.active(1)                                                              # (an unused ready=False path, SM built but not started, was removed: audit §3)
    # A new StateMachine doesn't clear Y: it keeps whatever the last program
    # on state machine 0 left there, so "BUSY" below was never guaranteed --
    # a READY left over would let the Z80 read an empty TX as 00. Say it
    # (audit §4; ~18 us).
    MQ_BUSY()
    # ─── DUAL-PORT MIGRATION: Y stays at BUSY here ──────────────────
    # We INTENTIONALLY do NOT set Y=READY in this function. Caller
    # MUST load any response bytes into TX and then call MQ_READY()
    # to signal ready, in that order.
    #
    # The old behavior was:
    #     MQX(MQ, "mov(y, invert(null))")    # Y=READY immediately
    # which created a race: between this exec and the caller's
    # response-byte load, the Z80 (which has been polling $0F
    # throughout any preceding SD operation) sees ready, immediately
    # reads $0E, finds TX empty, gets 0x00 → Report J.
    #
    # The race was theoretical for handlers that respond instantly
    # (TPI:DIR, etc.) but became reliably reproducible for handlers
    # that do SD round-trips before responding (TPI:MD, TPI:RM,
    # MOUNT_FILE, NEW_TAP, GETHELP, ...). The 575ms SD window is
    # plenty of time for the Z80 to win the race against our
    # Python code path to SEND_MSG.
    #
    # Now: SM is active, Y=0 (BUSY), TX is empty. Caller does:
    #     ACTIVATE_MQ()
    #     # load response bytes via SEND_MSG() or MQ.put(...)
    #     MQ_READY()   # (or SEND_MSG calls this internally)
    # Z80 sees BUSY on $0F until we're ready; protocol races
    # eliminated.
    # ────────────────────────────────────────────────────────────────
    TLM("ACTIVATE_MQ exit", "SM active, Y=BUSY (TX FIFO empty)")

    return


# ─── DUAL-PORT MIGRATION: new helpers MQ_READY / MQ_BUSY ───────────────
# In Ryan's single-port code, "ready" was signalled by writing 0x40 to
# the TX FIFO — the byte had bit 6 set, and the Z80's WF_NPH polling
# loop tests bit 6 of $0F. Every handler interleaved `wrt(0x40)` and
# `wrt(0x01)` (data) bytes in TX with careful ordering.
#
# In dual-port, $0F is decoded SEPARATELY by the PIO and answered by
# the Y scratch register — NOT by the TX FIFO at all. So:
#
#   - "ready" means  set Y = 0xFFFFFFFF  (MQ_READY)
#   - "busy"  means  set Y = 0           (MQ_BUSY)
#
# Every `wrt(0x40)` or `MQ.put(0x40)` in Ryan's handlers becomes a
# `MQ_READY()` call (typically placed AFTER the data bytes are in TX,
# so Z80 sees "ready" on its next $0F poll and then reads the data via
# $0E). Stages 5-7 of this migration walk through each callsite.
#
# These functions deliberately have NO logging or TLM. They run in
# time-critical receive paths where a print() takes ~1-10ms — long
# enough for the 4-deep RX FIFO to overflow and lose Z80 bytes.
# ───────────────────────────────────────────────────────────────────────
def MQ_READY():
    """Signal 'ready' to Z80 — bit 6 set on $0F reads (Y = 0xFFFFFFFF).

    Per the V1.5 protocol (Gustavo's V5 doc), the Z80 polls $0F bit 6
    in WAIT EXECUTION before reading TX or writing RX, and only
    proceeds when it observes bit 6 = 1. MQ_READY asserts that.

    With the issue-#14 PIO auto-busy (`mov(y, null)` after every Z80
    OUT in TS_IO_DUAL), the contract is:

      - PIO drops Y to 0 (BUSY) on every Z80 write to $0E or $0F.
      - Python MUST call MQ_READY() when it has the response (TX
        bytes loaded, or no further input expected) and wants the
        Z80's next WAIT EXECUTION poll to proceed.

    Callers that legitimately need Y=READY after a Z80 OUT:
      - PROCESS_CMD tail (V6 pre-load 0x01 for next command)
      - LVM SAVE post-block status code
      - SEND_MSG / SEND_MSG2 / SEND_MSG_PROMPT_YN entry
      - ListMenu after keypress receipt
      - ZX48_IO echo path
      - extcmd handlers that return data
    """
    # invert(null) is the documented MicroPython PIO syntax for ~0.
    # The tilde form `~null` does NOT parse correctly via runtime
    # sm.exec() in MicroPython v1.20.0 — confirmed by REPL test. Nor in
    # v1.29: rp2.py's `null` is a plain number there too.
    MQX(MQ, "mov(y, invert(null))")


# ─── Issue #51 stage 4: command I/O that never blocks ──────────────────
# Command output (SEND_MSG, SEND_MSG2, ListMenu, SEND_MSG_PROMPT_YN) used
# MQ.put(), which blocks for good once the 4-deep TX FIFO is full and the
# Z80 has stopped reading -- and no watchdog covers commands. The 1.8b
# ROM's BREAK at a "Scroll? (Y/n)" or menu key wait arrives as a port-0Fh
# write (0x103): MQ.get() handed it back as a key, SEND_MSG2 took it for
# "next page" and wrote the erase + next page into a TX nobody read. The
# Pico hung until reset.
#
# Now every byte goes through CMD_PUT, which waits in TX_ROOM when TX is
# full and listens; key waits go through CMD_KEY. A BREAK, or a Z80 that
# stops reading, raises CmdAbort, which PROCESS_CMD catches: it empties
# both FIFOs and its finally-tail stages the one pre-load and says READY
# + IDLE -- what the 1.8b ROM's BRK_ABORT waits for before Report D.
#
# CmdAbort is a BaseException so a handler's `except Exception:` can't
# swallow it and carry on writing to a Z80 that has gone.
# ────────────────────────────────────────────────────────────────────────
class CmdAbort(BaseException):
    """args[0]: 1 = port-0Fh write (BREAK / SYNC), 3 = the Z80 stopped
    reading (TX stayed full), as TX_ROOM's codes."""


_CMD_ECHO = bytearray(3)            # TX_ROOM's scratch; stray keys land here
# How long command output waits on a Z80 that has stopped reading before
# giving up (RECOVERED). NOT short: the Z80 legitimately stops for as long
# as the user takes -- the ROM's own "scroll?" prompt, a slow listing --
# and 3 s killed tpi:idir / a mount-error reply on hardware (2026-09-27).
# A Z80 that has really gone, on the 1.8b ROM, says so at once: BREAK or
# the next command's SYNC is a port-0Fh write.
CMD_STALL_MS = 600_000
KEY_WAIT_MS = 86_400_000            # a key wait waits for the user, as the ROM
                                    # does (a day); BREAK ends it at once


def CMD_PUT(b):
    """MQ.put() for command output that never blocks. Raises CmdAbort."""
    if MQ.tx_fifo() >= TX_DEPTH:
        _CMD_ECHO[0] = 0
        why = TX_ROOM(MQ, _CMD_ECHO, CMD_STALL_MS)
        if why:
            raise CmdAbort(why)
    MQ.put(b)


def CMD_SEND(buf, ready):
    """Command output the ROM reads blind -- a message, a page of a listing:
    the first bytes into TX, READY (if `ready`), then the rest. Raises
    CmdAbort, as CMD_PUT.

    The ROM prints each character as it reads it, with no ready-wait
    (PROTOCOL.md, "Text rules"): RST 10 is slow, but a GC or a flash write
    on v1.29 can outlast the four characters in the FIFO, and the ROM then
    prints whatever it reads from an empty one. So the page is built in RAM
    first and, where there is DMA, a channel feeds the FIFO from it whatever
    core0 is doing (STREAM_DMA). Without DMA, CMD_PUT a byte at a time."""
    if tspico_io._DMA is not None:
        _CMD_ECHO[0] = 0                    # all of it by DMA, READY once it runs
        r = STREAM_DMA(MQ, buf, _CMD_ECHO, CMD_STALL_MS, MQ_READY if ready else False)
        if r is not None:
            if r[0]:
                raise CmdAbort(r[0])
            return
    n = len(buf)
    k = min(TX_DEPTH, n)
    for i in range(k):
        CMD_PUT(buf[i])
    if ready:
        MQ_READY()
    for i in range(k, n):
        CMD_PUT(buf[i])


class CmdOut:
    """A page of command output, built in RAM and sent with CMD_SEND:
    `wrt = CmdOut()`, then wrt(byte or str) as with CMD_PUT, and
    wrt.send() where the Pico would wait for the Z80 -- before a key read
    or the end. Nothing reaches TX before send(), and send() says READY
    once the first bytes are in (and, with DMA, the channel is running):
    data in TX first, then READY, as every handler must. For menus and
    prompts (ListMenu, PROMPT_EACH, SEND_MSG_PROMPT_YN), which the ROM
    prints a character at a time, blind -- as SEND_MSG2's pages."""

    def __init__(self):
        self.b = bytearray()

    def __call__(self, x):
        if isinstance(x, str):
            self.b.extend(x.encode())
        else:
            self.b.append(x)

    def send(self, ready=True):
        b = self.b
        self.b = bytearray()
        if b:
            CMD_SEND(b, ready)
        elif ready:
            MQ_READY()


def CMD_KEY():
    """The Z80's key at a prompt (its OUT $0E). A write to port 0Fh -- the
    1.8b ROM's BREAK at the key wait -- raises CmdAbort."""
    w = RX_WORD(MQ, KEY_WAIT_MS)
    if w < 0:
        raise CmdAbort(3)
    if w & PORT_0F:
        raise CmdAbort(1)
    return w & 0xFF


def CMD_DRAIN():
    """Wait until the Z80 has read everything queued -- bounded, and
    listening for BREAK, unlike the `while MQ.tx_fifo() != 0` spins it
    replaces. Raises CmdAbort."""
    t0 = time.ticks_ms()
    while MQ.tx_fifo():
        if MQ.rx_fifo() and MQ.get() & PORT_0F:
            raise CmdAbort(1)
        if time.ticks_diff(time.ticks_ms(), t0) >= CMD_STALL_MS:
            raise CmdAbort(3)


def PRELOAD_READ(ms=100):
    """Wait (bounded) for the Z80 to read the pre-load status the ROM reads
    with no wait straight after its pre-header. Call it before anything that
    rebuilds the bus state machine (an SD access: ACTIVATE_SD / ACTIVATE_MQ),
    which empties TX. True if it was read; if not, the caller puts 0x01
    back after the SD access."""
    t0 = time.ticks_ms()
    while MQ.tx_fifo() and time.ticks_diff(time.ticks_ms(), t0) < ms:
        pass
    return not MQ.tx_fifo()


def CMD_RX_FLUSH():
    """Empty RX before a reply that waits for keys -- but a write to port
    0Fh found there is BREAK (or the next command's SYNC): raise CmdAbort,
    as CMD_KEY would. A plain drain swallowed it, and the Z80, waiting in
    its abort for READY + IDLE, then got the listing's READY + IDLE, raised
    Report D, and left the Pico sending to nobody until the next command's
    SYNC ended it -- whose pre-header was then lost: Report T (audit §4,
    "RX flushes on entry")."""
    for _ in range(64):
        if not MQ.rx_fifo():
            return
        if MQ.get() & PORT_0F:
            raise CmdAbort(1)


def CMD_FLUSH():
    """Empty both FIFOs after a CmdAbort, bounded. No pre-load: the
    caller's tail stages the one 0x01."""
    for _ in range(64):
        if MQ.tx_fifo() == 0:
            break
        MQX(MQ, "pull (noblock)")
        MQX(MQ, "mov (osr, null)")
    for _ in range(64):
        if MQ.rx_fifo() == 0:
            break
        MQ.get()



def MQ_BUSY():
    """Signal 'not ready' to Z80 — bit 6 clear on $0F reads (Y = 0).

    With the issue-#14 PIO auto-busy it isn't needed: the PIO drops Y to
    0 on every Z80 OUT, and nothing calls this today. Kept for a path that
    must assert BUSY without an inbound write -- and for the open audit
    question (§4) of whether a fresh state machine's Y is reliably 0.
    """
    MQX(MQ, "set(y, 0)")


# ─── DUAL-PORT MIGRATION: retired single-port helpers ────────────────────
# Three helper functions are gone from the file at this point:
#
#   WAIT_TX_RECEIVED()  was:  while MQ.tx_fifo() != 0: pass
#   EMPTY_TX_FIFO()     was:  while MQ.tx_fifo() != 0: pull(noblock); mov(osr,null)
#   EMPTY_RX_FIFO()     was:  while MQ.rx_fifo() != 0: MQ.get()
#
# They were idiomatic single-port plumbing for the per-command "wait
# until Z80 has read everything, then drain RX of any echoes" cycle.
# In dual-port we either don't need them (Y register pacing handles
# most cases) or we inline them at the small number of remaining
# callsites — both for clarity and to avoid encouraging copy-paste of
# the old pattern.
#
# Every callsite has been migrated:
#   - SEND_MSG / SEND_MSG2 / SEND_MSG_PROMPT_YN tails  (stage 6)
#   - PRINT_IO / PROCESS_CMD tails  (stage 5)
#   - ListMenu tail  (stage 7)
#   - TS2068_IO unrecognized-cmd branch + bottom-of-loop  (stage 4)
#   - CHK_STATUS watchdog cleanup  (stage 7)
#   - ZX48_IO unrecognized-cmd + post-mode cleanup  (stage 7)
# ─────────────────────────────────────────────────────────────────────────


# ─── SD_TRY_MS: no new mount attempt once this long has gone ─────────────
# ACTIVATE_SD runs inside commands, while the 2068 waits ~19.9 s for READY.
# An empty slot fails an attempt in ~0.5 s (CMD0's 500 ms), so five tries
# fit in ~5 s -- the five are for a cold card that refuses at first. But a
# card that is in and not answering can hold MISO low: the driver's
# _recover() then waits out three 1 s busy timeouts before CMD0, ~4 s an
# attempt, and five of them (20 s, seen on hardware 2026-10-02 after a
# reflash) ran past the 2068's wait. It reported J, and the Pico went on
# to answer a command nobody was reading. With this budget the worst case
# is two such attempts, ~8.5 s; a fast-failing cold card still gets all
# five.
# ─────────────────────────────────────────────────────────────────────────
SD_TRY_MS = 6000


def ACTIVATE_SD(tries=None):                                                                    # Enable SD-Card access SM, after TX/RX operation

    """Mount the SD card on /sd and hand GPIO 2-4 to SPI. Returns the SPI.

    tries: mount attempts, 0.5 s apart. Default: 5 while the card is believed
    present (a cold card can refuse to start and be fine seconds later), 1
    once it is known to be missing -- with no card each attempt gives up
    after ~0.5 s, and every command would otherwise stall ~5 s. No attempt
    starts once SD_TRY_MS has gone, whatever `tries` says.

    Every mount goes through here, so this is where the card's state is
    kept: on success SD_NOTE_CARD records it and, when the card has just come
    back or is a different card, repairs the state that belonged to the old
    one. On failure TSP.sd_present goes False and OSError(19) is raised.
    """

    global MQ
    global sd_active

    TLM("ACTIVATE_SD enter")
    if tries is None:
        tries = 5 if TSP.sd_present else 1
    MQ = StateMachine(0, NULL_SM, freq=15_000_000)
    MQ.active(1)
    MQ.active(0)
    sd_active = True

    U3_CS       = Pin(28, Pin.OUT, Pin.PULL_UP)
    D0          = Pin(2,  Pin.IN)
    D1          = Pin(3,  Pin.IN)
    D2          = Pin(4,  Pin.IN)
    # GPIO 2-4 are also Z80 data lines D0-D2 through the U6 buffer. Hold
    # U6 off (GPIO 12 high, as main.py sets it at boot) so the bus can't
    # fight the SD card; ACTIVATE_MQ hands the pin back to the PIO.
    Pin(12, Pin.OUT, value=1)

    # A card can refuse to start up at boot and be perfectly happy a few
    # seconds later, so try the whole mount a few times before giving up.
    # Each failure is PRINTED with its reason: the log copy only reaches
    # /activity.log if logging itself is working, and the console used to
    # show nothing but "FAILED".
    err = None
    spi = sd = None
    t_start = time.ticks_ms()
    attempt = 0
    for attempt in range(1, tries + 1):
        if attempt > 1 and time.ticks_diff(time.ticks_ms(), t_start) >= SD_TRY_MS:
            attempt -= 1                                                       # the ones actually made
            print("[ACTIVATE_SD] giving up: %d ms on %d attempt(s)" % (
                time.ticks_diff(time.ticks_ms(), t_start), attempt))
            break
        try:
            spi = SPI(0, sck=D0, mosi=D1, miso=D2)
            sd = SDCard(spi, U3_CS)
            recovered = getattr(sd, "recovered", None)
            if recovered:
                # Left mid-transfer by an interrupted session (Ctrl-C or reset
                # during an SD access): the driver brought it back without a
                # power cycle. Worth knowing how often that happens.
                print("[ACTIVATE_SD] %s -- recovered" % recovered)
                LOG("SD card %s; recovered without a power cycle" % recovered, 1)
            os.mount(sd, "/sd")
            TLM("ACTIVATE_SD exit", "SD mounted at /sd (attempt %d)" % attempt)
            if attempt > 1:
                LOG("SD card mounted on attempt %d (before that: %s)" % (attempt, err), 1)
            break
        except Exception as e:
            err = e
            sd = None
            print("[ACTIVATE_SD] attempt %d/%d failed: %r" % (attempt, tries, e))
            if attempt < tries:
                time.sleep_ms(500)

    if sd is not None:
        SD_NOTE_CARD(getattr(sd, "CID", 0))                                    # may repair state; raises if it can't
        return spi

    # Raise rather than loop in BLINK_ERROR. This runs inside commands
    # (CD, MD, RM, NEWTAP, HELP, every MOUNT_FILE), and a card that wedges
    # mid-session -- often right after a failed write -- used to brick the
    # TS-Pico until power-cycle. Raised, it becomes that one command
    # failing: PROCESS_CMD's handler catches it and FAIL_CMD re-arms the
    # bus (sd_active is still True). At boot TS2068_IO carries on without a
    # card, and the next command that needs one tries again.
    if TSP.sd_present:                                                        # it was there: an error
        LOG(f"Mounting SD Card failed in ACTIVATE_SD after {attempt} attempts! {err}", 2)
        SAVE_LOG()
    elif TSP.sd_cid is None:                                                  # none since power-on
        LOG("SD card: not found (%s)" % err, 1)
    TSP.sd_present = False
    TLM("ACTIVATE_SD FAILED after %d attempt(s)" % attempt, repr(err))
    raise OSError(19, "SD card mount failed after %d attempts: %s" % (attempt, err))


def SAVE_MOUNT():                                                               # tspico_io.SD_MOUNT: the SAVE writes' mount

    """Mount the card for SAVE_TS / SAVE_ZX's write, through ACTIVATE_SD:
    retried, and the card's state kept. Raises OSError if it can't.

    Unmounts first: ENA_SD's bare mount carried on over a /sd left mounted
    (os.mount gives EPERM, the write used the old mount), and ACTIVATE_SD
    would count that EPERM as a missing card."""

    try:
        os.umount("/sd")
    except OSError:
        pass
    return ACTIVATE_SD()


tspico_io.SD_MOUNT = SAVE_MOUNT                                                 # 2026-09-30 audit, §2 #21


def SD_NOTE_CARD(cid):                                                         # ACTIVATE_SD: a card mounted

    """Record the mounted card. When it has just come back (or is the first
    card of the session) or is a different card, bring the state that
    assumed the old card up to date (SD_REVALIDATE). The card is mounted."""

    # ─── A CID of 0 means "couldn't read it", not "a different card" ──────
    # The driver (sdcard.py) sets CID = 0 when CMD10 fails. That fallback is
    # Ryan's, from when the CID was only informational. Since #101 the CID is
    # the card's identity, and a change in it makes SD_REVALIDATE drop
    # append mode, close every OPEN # channel and the printer capture. So one
    # failed CMD10 on the same card looked like a card swap, and two cards
    # that both failed looked like the same card. Now 0 is "unknown": it
    # never counts as a change, and it doesn't replace a CID we know. (Found
    # by the 2026-09-30 audit.) A real swap with an unreadable CID still
    # comes through the back/away path when the card was seen to be out.
    # ─────────────────────────────────────────────────────────────────────
    first = TSP.sd_cid is None
    back = not TSP.sd_present
    known = cid != 0
    changed = known and TSP.sd_cid not in (None, 0) and cid != TSP.sd_cid
    TSP.sd_present = True
    if known or first:
        TSP.sd_cid = cid
    if back or changed:
        if changed:
            LOG("SD card: a different card is in", 1)
        elif not first:
            LOG("SD card: back in", 0)
        SD_REVALIDATE(changed)


def SD_REVALIDATE(changed):                                                    # the card is new or back: fix the state

    """Bring everything that belongs to the card up to date. Runs with the
    card mounted, the first time one is seen and whenever it comes back:

      * no TAP folder (a freshly formatted card): make it;
      * the current folder: kept if the card has it, else the top (/TAP);
      * the mounted file: kept if the card has it, else unmounted;
      * a DIFFERENT card: append goes off (a save must never land in the
        other card's file), and open channels and the printer capture are
        dropped -- their files were on the other card;
      * the directory caches are rebuilt.

    If there is no TAP folder and one can't be made (a write-protected card),
    the card counts as missing: TSP.sd_present goes False and OSError(19) is
    raised."""

    global alldirs, prev_path, prn_path

    root = catalog.ROOT
    if not dir_exists(root):
        try:
            os.mkdir(root)
            LOG("SD card had no TAP folder: made one", 1)
        except OSError as e:
            TSP.sd_present = False
            LOG("SD card has no TAP folder and one can't be made: %s" % e, 2)
            raise OSError(19, "SD card has no TAP folder")
    if not dir_exists(TSP.cur_path):
        TSP.cur_path = root
    if prev_path and not dir_exists(prev_path):
        prev_path = None
    if TSP.f_name and TSP.f_name.startswith("/sd/") and not file_exists(TSP.f_name):
        LOG("SD card: %s isn't on this card; unmounted" % TSP.f_name, 1)
        FORGET_MOUNT()
    if changed:
        TSP.append = False
        CHANNELS.close_all()
        prn_path = None
    os.chdir(TSP.cur_path)
    TSP.sd_listing_ok = DIR_FILES()
    alldirs = GET_DIRS()


def LISTING_SIG(entries):                                                     # the folder's names, types and sizes, as one number

    """A fingerprint of a folder listing (os.ilistdir's entries, in
    LIST_DIR_FILES' order): name, type and size of each. Two listings with
    the same fingerprint list the same files."""
    return hash(tuple((e[0], e[1], e[3] if len(e) > 3 else 0) for e in entries))


def LISTING_FRESHEN():                                                        # re-read the folder if the card's copy changed

    """The card is mounted. Re-read the current folder (DIR_FILES: files,
    lista, dirinfo.tap) if what is on the card no longer matches the last
    listing. The Pico only noticed a card being swapped when a command found
    it missing or a different card; the SAME card, taken out, given a file
    on a Mac and put back between two commands, kept the old listing -- CAT
    didn't show the file and LOAD "tpi:" couldn't find it until a reboot
    (hardware, 2026-10-03). Reading the folder is cheap; rebuilding the
    listing (dirinfo.tap, free space) happens only when it changed."""
    try:
        os.chdir(TSP.cur_path)
        sig = LISTING_SIG(sorted(os.ilistdir(), key=lambda fname: fname[0].lower()))
    except OSError:
        return
    if sig != getattr(TSP, "listing_sig", None):
        LOG("The folder changed on the card: re-reading it", 0)
        TSP.sd_listing_ok = DIR_FILES()


def LISTING_CHECK():                                                         # mount, LISTING_FRESHEN, give the bus back

    """Mount the card, bring the listing up to date if the folder changed
    (LISTING_FRESHEN), and hand the bus back to the MQ (Y BUSY). False if
    there is no card."""
    ok = True
    try:
        ACTIVATE_SD()
        LISTING_FRESHEN()
    except OSError:
        ok = False
    finally:
        DEACTIVATE_SD()
        ACTIVATE_MQ()
    return ok


def REFRESH_LISTING():                                                         # re-read the folder after a ZX48 SAVE

    """Re-read the current folder's listing (files, lista) because a ZX48
    SAVE wrote a file into it (TSP.listing_stale, set by SAVE_ZX). Called
    where the Z80 is waiting for READY: the start of PROCESS_CMD, and
    ZX_TPI before it matches a name. With no card it does nothing -- the
    command's own card check answers. Leaves the bus with the MQ (Y BUSY),
    as every SD step inside a command does."""

    TSP.listing_stale = False
    try:
        ACTIVATE_SD()
        os.chdir(TSP.cur_path)
        TSP.sd_listing_ok = DIR_FILES()
    except OSError:
        pass
    finally:
        DEACTIVATE_SD()
        ACTIVATE_MQ()


def SD_PROBE(tries=None):                                                      # is there a card? (bus left with the MQ)

    """Mount and unmount the card, and give the bus back to the MQ (Y stays
    BUSY). True if a card is in; a card that has come back, or is a
    different one, is brought up to date on the way (SD_NOTE_CARD)."""

    ok = True
    try:
        ACTIVATE_SD(tries)
    except OSError:
        ok = False
    finally:
        DEACTIVATE_SD()
        ACTIVATE_MQ()
    return ok

def BLINK_ERROR():                                                             # An onboard LED-blinking routine. This for an error condition. Interval is fixed

    global led
    
    led.value(1)

    for i in range(10):
        utime.sleep(.1)
        led.toggle()
    
    led.value(0)
        
    return


def BLINK_LED(pause):                                                           # Another routine that ...well...blinks the onboard LED!
                                                                                # Runs on core1 during boot only (TS2068_IO starts it and
                                                                                # stops it with `dead = True`). COPY_FILE once used it too.
    global dead
    global busy
    global led
    
    busy = True
    
    utime.sleep(.2)
    
    while not dead:
        led.value(1)
        utime.sleep(pause)                                                      # 'pause' controls interval
        led.value(0)
        utime.sleep(pause)
        
    led.value(0)
    busy = False
    
    return    


def COPY_FILE(src_file, dst_file):                                                          # Copy the large .TAP file to Pico's internal flash
                                                                                             # best compatibility and performance
    global led

    # ─── No dead/busy handshake here any more ──────────────────────────────
    # This function used to set `dead = False` on entry, `dead = True` at the
    # end, and then spin on `while busy: pass`. That was a handshake with a
    # thread on core1 -- BLINK_LED or Ryan's CHK_STATUS watchdog -- which
    # blinked the LED during the copy: `dead = True` told it to stop, and
    # `while busy` waited for it to finish. Nothing starts such a thread
    # here any more (the LED is toggled inline below, and the watchdog was
    # removed in issue #51), so the handshake had nothing to talk to.
    #
    # What it did still do was wait on the ONE remaining user of `busy`,
    # SAVE_LOG on core1 -- and before the 2026-09-30 audit a SAVE_LOG whose
    # flash write failed left `busy` True for ever, so every LOAD "tpi:file"
    # mount then hung the Pico right here. The wait also never protected the
    # copy itself: it ran AFTER the copy had finished.
    #
    # Instead, wait (bounded) BEFORE writing to flash, so the copy doesn't
    # overlap a log write -- both cores stop while a flash sector is
    # programmed, and two writers to the flash filesystem from two cores is
    # asking for trouble. 3 s is far more than a log write takes, and well
    # inside the ~20 s the Z80 waits for a command's reply.
    # ─────────────────────────────────────────────────────────────────────
    WAIT_CORE1(3000, "COPY_FILE")

    try:
        buf = bytearray(512)
    except:
        return False
    bytes_rd = 0
    
    led.value(1)
    
    try:
        with open(src_file, 'rb') as file_in:
            with open(dst_file, 'wb') as file_out:
                
                bytes_rd = file_in.readinto(buf)
                i = 0
                while bytes_rd  > 0:
                    file_out.write(buf[:bytes_rd])
                    bytes_rd = file_in.readinto(buf)
                    
                    i += 1
                    if (i >= 15):
                        led.toggle()
                        i = 0
    except:
        return False
    finally:
        led.value(0)

    del buf                                                                             # OPTIMIZATION - CHECK!
    gc.collect()

    return True


def DCK_IMAGE():

    """ Generates a full 64kB image from a .DCK file """
                                                                                              # This will be used by the Flash write pgm
    gc.collect()
    header = bytearray(9)
    buff_size = 256
    rep = 8192 // buff_size
    empty = bytearray(buff_size)
    cur_chunk = bytearray(buff_size)
    
    LOG("Start processing DCK file", 0)
  
    f_in = open("/TMP/temp.bin", "rb")
    f_out = open("/TMP/temp_dck.bin", "wb")

    f_in.readinto(header)

    # DCK header byte 0 is the bank number:
    #     0: DOCK bank  - You set tpi:dock to this
    # 1-253: Reserved
    #   254: EXROM bank - We don't have a way to specify this unless you appended it to a 16K HOME block
    #   255: HOME bank  - You would set tpi:boot to this

    if header[0] != 0x00:
        LOG("Not a valid DOCK image; wrong header. Aborting...", 3)
        
        f_in.close()
        f_out.close()
        gc.collect()
        
        return False

    LOG("DCK header:" + str(header), 0)

    for el in range(1, 9):                                                              # Byte 0 is bank, bytes 1-8 are the 8x 8kb chunk types
        if (header[el] == 0x00 or header[el] == 0x01):                                  # Non-existent chunk type (8kb data is not in the file)
            for i in range(rep):
                f_out.write(empty)
        elif header[el] == 0x02 or header[el] == 0x03:                                  # Chunk data is in the file
            for i in range(rep):
                f_in.readinto(cur_chunk)
                f_out.write(cur_chunk)
        else:                                                                           # Invalid
            LOG("Not a valid DOCK image; wrong chunk type. Aborting...", 3)
            f_in.close()
            f_out.close()
            gc.collect()
            
            return False        

    # DCK files can have additional sections after this starting again with
    # another header. Technically, you could separate each chunk in a deparate
    # DCK section with its own header, but that is not done. More practically,
    # you could specify one DCK section for HOME bank to replace the HOME ROM
    # and another section for EXROM to replace the EXROM bank ROM.

    LOG("Image of DCK file generated succesfully", 0)
    
    f_in.close()
    f_out.close()
    
    os.remove("/TMP/temp.bin")
    os.rename("/TMP/temp_dck.bin", "/TMP/temp.bin")
    
    del empty
    del cur_chunk
    gc.collect()
    
    return True


def shorten_filename(nom, l):
    # Shorten a filename to fit in length l by removing characters from the
    # middle of the name before the file extension, replacing them with a '>'.
    size = len(nom)
    if size > l:
        j = nom.rfind('.')
        if j == -1:
            j = size
        e = size - j # length of ext with dot
        k = l - 1 - e
        k2 = k // 2
        k1 = k - k2
        return "%s>%s" % (nom[:k1], nom[j-k2:])
    return nom


def DIR_HEADER(sd_stat, path=None):                                                           # lista header: path, SD line, column titles (4 x 32 chars)
    if path is None:
        path = public_path(27)
    return "Path:%-27s%-32sFile Name                   Size--------------------------------" % (path, sd_stat[:32])


def CAT_COLOUR(text):                                                         # a plain listing -> the coloured one

    """The listing as CAT shows it (chosen 2026-10-02): the path and the
    card line on a blue bar, the column titles on cyan, the dashed line
    gone, folders in blue with "folder" for their size, and each index
    number on a cyan chip. `text` is DIR_HEADER's four 32-character rows
    and then 32-character entry rows, as DIR_FILES and CATALOG_TEXT build
    them (and as dirinfo and tpi:info's tests read them: those keep the
    plain text). Anything else -- a TAP's block list, "Directory is empty"
    -- goes through as it is. Send the result with SEND_MSG2(colour=True).

    Every row starts by setting its own colours, so a "Scroll?" prompt in
    the middle changes nothing, and none ends with a code between its 32nd
    character and the next row (SEND_MSG2 would then not see the line's
    end)."""

    if not text.startswith("Path:") or len(text) < 128:
        return text
    out = [PAPER_ + "\x01" + INK_ + "\x07" + text[0:64],                 # path + card line
           PAPER_ + "\x05" + INK_ + "\x09" + text[64:96]]                # column titles
    rest = text[128:]                                                      # [96:128] is the dashes
    while len(rest) >= 32:
        row = rest[:32]
        if row[0] == "<":
            out.append(NORMAL_ + INK_ + "\x01" + row[:22] + "%10s" % "folder")
        elif row[:3].isdigit() and row[3] == " ":
            out.append(PAPER_ + "\x05" + INK_ + "\x09" + row[:3] + NORMAL_ + row[3:])
        elif row[:4] == "    ":
            out.append(NORMAL_ + row)
        else:
            break
        rest = rest[32:]
    out.append(NORMAL_ + rest)
    return "".join(out)


def TAPDIR_COLOUR(text, headers):                                             # CAT "" as CAT shows a folder

    """tpi:tapdir's listing in CAT's colours (agreed 2026-10-02): the file and
    pointer lines on the blue bar, the column titles on cyan, the dashed
    line gone, block numbers on cyan chips, headers in blue, and the block
    LOAD "" reads next (marked '>') on a yellow row. `text` is TAPDIR's: four
    32-character header rows, then 32-character block rows (both views);
    anything after them ("<empty file>") goes through as it is. `headers`:
    the CODE 1 view, where every row is a program (bar its orphans).
    Send with SEND_MSG2(colour=True); every row sets its own colours."""

    if not text.startswith("File:") or len(text) < 128:
        return text
    out = [PAPER_ + "\x01" + INK_ + "\x07" + text[0:64],
           PAPER_ + "\x05" + INK_ + "\x09" + text[64:96]]
    rest = text[128:]
    while len(rest) >= 32 and rest[0] in " >" and rest[1:3].isdigit():
        row = rest[:32]
        if row[0] == ">":
            out.append(PAPER_ + "\x06" + INK_ + "\x09" + row)
        else:
            hdr = ("Data block" not in row[4:15]) if headers else row[18:20] == " Y"
            out.append(NORMAL_ + row[0] + PAPER_ + "\x05" + INK_ + "\x09" + row[1:3]
                       + PAPER_ + "\x08" + INK_ + ("\x01" if hdr else "\x08") + row[3:])
        rest = rest[32:]
    out.append(NORMAL_ + rest)
    return "".join(out)


def DIR_FILES():                                                                             # Get all files and directories from current path
    """
    Rebuild files[], lista and dirinfo.tap for the current directory.

    Returns True on success. On an SD card error (OSError) it logs an ERROR
    with the reason, leaves an empty listing that says so, and returns False
    instead of raising.

    Any FatFs call can reach the card here, not just the dirinfo.tap write.
    The field failure (activity.log, 2026-09-26) was EIO from
    sdcard.writeblocks raised inside os.ilistdir(): FatFs flushing the
    sector that os.remove("dirinfo.tap") had dirtied. Uncaught, that took
    TS2068_IO down at boot with a FATAL and the 2068 got no TS-Pico at all,
    not even LOAD from the flash assets.
    """

    global files
    global dirs
    global lista
    global sd_space
    global files_upper
    global dirs_upper

    try:
        LIST_DIR_FILES()
        return True
    except OSError as e:
        LOG("DIR_FILES: SD card error, directory listing skipped: %s" % e, 2)

    files = []
    dirs = []
    files_upper = []
    dirs_upper = []
    sd_space = None
    lista = DIR_HEADER("SD: card error") + "SD card error: reseat the card\r"   # it recovers without a power cycle since #66/#101

    try:
        os.remove("dirinfo.tap")                                                             # a half-written one would LOAD as garbage
    except:
        pass

    return False


def LIST_DIR_FILES():                                                                        # DIR_FILES without the error handling; raises OSError on SD errors
    
    global files
    global dirs
    global lista
    global sd_space
    global files_upper
    global dirs_upper
    
    files = []
    dirs = []
    files_upper = []
    dirs_upper = []
    lista = ""
    L = []
    header = ""
    
    dirinfo = []
    tap_blk = []
    tap_hdr = []
    num_dirs = 0
    num_files = 0
    
    ext = catalog.DIR_EXT                                                                     # extensions to be included
    starts = ['.']                                                                            # first characters of files to be excluded
    
    ordered = True                                                                            # In the future, this could be controlled by an option

    # dirinfo.tap is the synthetic TAP this function writes at the end (the
    # listing in a form the Commander LOADs). It is left out of the listing
    # by name below. It used to be deleted here first, a FAT write on every
    # listing -- the write #62 traced field EIO errors to. (2026-09-30
    # audit, §3.)

    if ordered:
        listing = sorted(os.ilistdir(), key=lambda fname: fname[0].lower())
    else:
        listing = [item for item in os.ilistdir()]
    TSP.listing_sig = LISTING_SIG(listing)                                    # what LISTING_FRESHEN compares
    
    nom = bytearray(32)
    
    for archs in listing:
        if archs[1] == 16384:
            dirs.append(archs[0])
            dirs_upper.append(archs[0].upper())
            nom = shorten_filename(catalog.screen_name(archs[0]), 20)
            dirinfo.append("%-32s" %  nom)
            L.append("<%-21s       0 B" % (nom + ">"))

    num_dirs = len(dirinfo)
    i = 0
    
    for archs in listing:
        if archs[1] == 32768:
            if (archs[0][-3:].upper() not in ext) or (archs[0][0] in starts) or archs[0] == "dirinfo.tap":
                continue
            files.append(archs[0])
            files_upper.append(archs[0].upper())
            
            size_txt = catalog.size_text(int(archs[3]))

            nom = "%03d %-18s%10s" % (i, shorten_filename(catalog.screen_name(archs[0]), 18), size_txt)
            L.append(nom)
            dirinfo.append(nom)

            i += 1

    # Then every other file, without an index: LOAD "tpi:n" only counts the
    # types above, and files[] / dirinfo.tap keep exactly those (spec §2).
    for archs in listing:
        if archs[1] == 32768 and archs[0][-3:].upper() not in ext \
                and archs[0][0] not in starts and archs[0] != "dirinfo.tap":
            L.append("    %-18s%10s" % (shorten_filename(catalog.screen_name(archs[0]), 18),
                                        catalog.size_text(int(archs[3]))))
    
    del listing

    sd_block = os.statvfs("")[0]
    sd_tot   = os.statvfs("")[2]
    sd_free  = os.statvfs("")[3]
    sd_space = (sd_tot * sd_block, sd_free * sd_block)
    sd_stat  = "SD: %s; free: %s" % catalog.space_pair(*sd_space)

    header = DIR_HEADER(sd_stat)
    
    if not L:
        lista = header + "%s\r" % "Directory is empty"
    else:
        lista = header + "".join(L)
    del L

    num_files = len(files)
    
    dirinfo.insert(0, "%-32s" % num_dirs)
    dirinfo.insert(1, "%-32s" % num_files)
    
    tap_blk = (NEW_TAPBLK(dirinfo, 32))
    del dirinfo
    long = len(tap_blk) - 4                                        # this is the pure data blk size stored in header; it's the block minus the first 4 bytes
    tap_hdr = NEW_HDR(2, "dirinfo", long)                             # generate header for each block, with parameters
    
    with open("dirinfo.tap", "wb") as f_out:
        f_out.write(tap_hdr)                                          # now write the header
        f_out.write(tap_blk)                                           # and then the block

    # gc.collect()
    return


def LOG(msg, level):                                                                    # Adds a timestamped new entry to log_entries
    
    global log_entries
    global log_to_serial
    global TSP
    
    if 0 <= level <= 4:
        m = "%s:%s" % (LOG_LABELS[level], msg)
    else:
        m = msg

    if log_to_serial:                                                                    # If enabled, send log msg to console instead of logfile
        print(m)
    
    # ─── LOG must work before TSP exists ──────────────────────────────────
    # TSP (the PICO_STATUS object holding LOG_LEVEL) is created in TS2068_IO
    # only AFTER LOAD_CONFIG has read config.ini -- and LOAD_CONFIG itself
    # calls LOG when config.ini is missing or unreadable, or holds a bad
    # ROM_SM. So LOG has to cope with TSP not existing yet.
    #
    # The old guard, `if TSP.LOG_LEVEL:`, was meant to do exactly that (its
    # comment said "TSP is not initialized at startup, so this check is
    # required"), but it reads TSP to make the check, so it raised NameError
    # instead. The result: a missing or corrupt config.ini -- e.g. a power
    # cut while LOAD_CONFIG rewrites it, which it does on every boot from a
    # non-default slot -- crashed the boot, and the TS-Pico never came up.
    # Found by the 2026-09-30 audit; see src/test/audit_fixes_hosttest.py.
    #
    # globals().get() looks TSP up without raising. Until it exists there is
    # no log level to filter by, so every message is kept: these are the few
    # boot messages that explain why the defaults were used, which is what
    # someone reading /activity.log after a bad boot needs to see.
    # ─────────────────────────────────────────────────────────────────────
    tsp = globals().get("TSP")
    if tsp is not None and tsp.LOG_LEVEL:                                                # LOG_LEVEL 0 = keep everything
        if level < tsp.LOG_LEVEL:
            return
    
    log_entries.append("[%d]%s\n" % (time.ticks_us(), m))                                    # on Pico W, timestamp can be replaced by local time provided by ntp
    
    return


def MOUNT_FILE(f_name, remounting=False):                                                    # Mount file from a LOAD "tpi:..." command 
                                                                                             # and performs actions according to file type
    TLM("MOUNT_FILE enter", "f_name=%r remounting=%s" % (f_name, remounting))
    """
    Mount the given file f_name, and remounting the current file if the new
    mount fails. The remounting input is mainly for internal use when
    recursively calling to re-mount to avoid further recursive calls.
    """
    
    global TSP
    global led

    # (It used to set U3_CS high here; DEACTIVATE_SD and the SD driver's
    # init_card already leave the card deselected.)

    # Save info in case of remount
    offset = TSP.offset
    idx    = TSP.tap_idx
    append = TSP.append

    # Don't remove in case we know we can't mount the new file, and we overwrite
    # these anyway.
    # try:
    #     os.remove("/TMP/temp.tap")
    #     os.remove("/TMP/temp.bin")
    # except:
    #     pass
    
    msg = "File %s mounted correctly" % f_name
    err_level = 0
    remount = False # True=trigger remount of previous file if error
    
    ACTIVATE_SD()
    led.value(1)
    
    totlen = os.stat(f_name)[6]
    
    if f_name[-4:].upper() in [".BIN", ".DCK", ".ROM"]:
        
        if not COPY_FILE(f_name, "/TMP/temp.bin"):

            remount = True
            msg = "Copying file %s" % f_name
            err_level = 2
        else:

            if f_name[-4:].upper() == ".DCK":
            
                if DCK_IMAGE():
                    if not COPY_FILE("/assets/dckupdate.tap", "/TMP/temp.tap"):       # was /TS/dckupdate.tap; moved to /assets/ during dual-port migration to avoid frozen-package shadow
                        # The trick here and with romupdate.tap is that we copy this to 
                        # temp.tap but don't change the TSP.f_name, and the next non-tpi
                        # LOAD"" will pull from temp.tap.
                        err_level = 2
                        msg = "Copying dckupdate.tap"
                        remount = True
                else:
                    remount = True
                    err_level = 2
                    msg = "Creating DCK image for %s. See logfile for details" % f_name
                    
            else:
                
                len_hi = int(totlen / 256)
                len_lo = totlen - (len_hi * 256)

                try:
                    with open("/assets/romupdate.tap", "rb") as f_in:                 # was /TS/romupdate.tap; same move as dckupdate.tap above
                        buf = bytearray(f_in.read())
                    
                    # Parse the romupdate.tap file blocks to get the offset of block 3
                    # where the machine code is. As long as the MC doesn't change those
                    # offsets, and they are in block 3 of the .tap, you can change the 
                    # BASIC program and not change this code.
                    x = 0
                    for i in range(2):
                        l = buf[x] + 256 * buf[x+1] # length of block
                        x += l + 2 

                    x += 104 # offset to first length location
                    buf[x]   = len_lo                                            # We update the TAP file ML routine, with the length of the block
                    buf[x+1] = len_hi                                            # to be written to the Flash/SRAM
                    # LOG("Patching romupdate at %d and %d" % (x, x+1), 2)

                    x += 200 # offset to second length location
                    buf[x]   = len_lo                                            # Same to the second part of the ML routine (Update LOWER block)
                    buf[x+1] = len_hi
                    # LOG("Patching romupdate at %d and %d" % (x, x+1), 2)
                    remount = True # if writing fails, try a remount
                    with open("/TMP/temp.tap", "wb") as f_out:                            # And we update the seudo TAP
                        f_out.write(buf)
                except:
                    err_level = 2
                    msg = "Copying romupdate.tap"
        
    elif f_name[-4:].upper() == ".TAP":
        
        s = os.stat(f_name)
        if s[6] != 0: # An empty .tap is OK, otherwise check it
            with open(f_name, "rb") as f_check:
                
                # ─── Compare bytes, not decoded text ───────────────────────────
                # The first 7 bytes are raw TAP data. They used to be compared
                # with `file_type.decode() == "ZXTape!"`, and .decode() raises
                # UnicodeError on bytes that aren't valid UTF-8 -- e.g. a TAP
                # whose first block is headerless (flag FFh at byte 2), or a
                # header name with a byte >= 80h -- so mounting such a TAP
                # failed with an exception instead of mounting. A TZX file
                # starts with the ASCII signature "ZXTape!", so comparing the
                # bytes needs no decoding at all. The "non-standard first block"
                # note is now an elif: a TZX's first byte ('Z' = 5Ah) is > 19 as
                # well, and that used to overwrite the TZX error message.
                # (2026-09-30 audit.)
                # ─────────────────────────────────────────────────────────────
                file_type = f_check.read(7)
                if file_type == b"ZXTape!":
                    msg = "Wrong file type while mounting: %s. It's a TZX file" % f_name
                    err_level = 2

                elif file_type[0] > 19:                                    # informational only
                    msg = "Non-standard first block while mounting file %s. Expected 19, read %d" % (f_name, file_type[0])
                
        if err_level < 2:    
            if not COPY_FILE(f_name, "/TMP/temp.tap"):
                err_level = 2
                msg = "Copying file %s" % f_name
                remount = True
        
    else:
        msg = "Wrong filename while mounting: %s" % f_name
        err_level = 2

    # ─── DUAL-PORT MIGRATION: pair with DEACTIVATE_SD ─────────────────────
    DEACTIVATE_SD()
    ACTIVATE_MQ()
    LOG(msg, err_level)
    
    if err_level > 1:
        LOG("Failed to mount: %s" % f_name, err_level)
        BLINK_ERROR()
        if remounting or not TSP.f_name:
            # Don't try remounting, but don't leave a bad file mounted
            UNMOUNT([],[])
        elif remount:
            # Try re-mounting the current file because temp.bin or temp.tap were
            # overwritten or an error occured writing them with the new file.
            if MOUNT_FILE(TSP.f_name, True):
                # Restore where we were
                TSP.offset = offset
                TSP.tap_idx = idx
                TSP.append = append
                err_level = 0
                LOG("Remounted: " + TSP.f_name, 0)
    else:
        try:
            totlen = os.stat("/TMP/temp.tap")[6]                                       # We mount this file as a regular TAP to perform Flash write
            TSP.f_name = f_name
            TSP.totlen = totlen
            TSP.append = False
            OFF_TABLE() # Makes TSP.offset_tbl from temp.tap and not TSP.f_name
        except:
            UNMOUNT([], [])
    
    led.value(0)
    
    return (err_level == 0)
        

def NEW_HDR(type_hdr: int, fname, long: int):                      # This routine returns a new TAP header with the required parameters: header type, file name, and length of data block
    
    if (long < 0 or long > 65535):                                 # Validate data block length
        LOG("Wrong block length in NEW_HDR", 2)
        return
    
    if (type_hdr > 3) or (type_hdr < 0):
        LOG("Wrong header type in NEW_HDR", 2)                     # Also validate header type 
        return
    
    hdr = bytearray.fromhex('00')                                  # We start building the bytearray that will form the header: start with 0x00, a type header (FF=data)
    hdr += type_hdr.to_bytes(1, 'little')                          # Next, the filename passed as parameter
    hdr += f"{fname:<10}"[:10]                                     # ...trimmed to 10 bytes and left-justified with blanks
    
    long_b = int(long/256)                                         # Now we calculate LSB and MSB of block length
    long_a = int(((long/256) - long_b) * 256)
    
    hdr += long_a.to_bytes(1, 'little') + long_b.to_bytes(1, 'little')   #... and add it to the header
    hdr += bytearray.fromhex('69c18080')                           # Next, four bytes of which the second indicates array letter; the rest are ignored    
                                                                   # As we always use the same variable name ('a'), this pattern never changes
    crc = 0                                                        # Now we calculate the CRC for the entire block
    for el in hdr:
        crc = crc ^ el
        
    hdr += crc.to_bytes(1, 'little')                               #... and append it to the end of the block
    
    hdr = bytearray.fromhex('1300') + hdr                          # Now we add the (fixed) length for the header
    
    return(hdr)                                                    # and return the header
    

def NEW_TAPBLK(items, maxsize: int):                               # This routine generates a data block for storing an array, with the parameters: array items, and max size of single item
    
    num_items = len(items)

    dims = [0] * 4                                                 # This will hold LSB and MSB for both dimension of the array

    dims[1] = int((num_items)/256)  
    dims[0] = int(((num_items/256) - dims[1]) * 256)

    dims[3] = int((maxsize)/256)
    dims[2] = int(((maxsize/256) - dims[3]) * 256)

    blk = bytearray.fromhex("FF02")                                # We start a new data block: FF for data, 02 for String array type

    for el in dims:
        blk += el.to_bytes(1, 'little')                            # Now, store each LSB/MSB in blk
        
    for el in items:                                               # Now onto the items themselves 
        blk += el
    
    crc = 0
    for el in blk:
        crc = crc ^ el                                             # calculate CRC
    
    blk += crc.to_bytes(1, 'little')                               # and store it at the end of the blk
    
    len_blk = len(blk)
    len2 = int((len_blk)/256)                                      # Now calculate blk length's LSB/MSB 
    len1 = int(((len_blk/256) - len2) * 256)
    
    blk = len2.to_bytes(1, 'little') + blk                         #...and store it on the blk's first two positions
    blk = len1.to_bytes(1, 'little') + blk

    return(blk)                                                    # and return the blk


def OFF_TABLE():                                                             # Builds an offset table of segments, from the current .TAP file
    
    global TSP
    
    arch = open("/TMP/temp.tap", "rb")
    TSP.offset_tbl = catalog.tap_table(arch)
    TSP.tap_idx = 0
    TSP.offset = 0
    
    arch.close()
    gc.collect()
    
    return


def PARAMS(pre):
    """Returns calculated CODE parameters from pre-header."""

    par1 = (pre[4] << 8) | pre[3]
    par2 = (pre[6] << 8) | pre[5]
        
    return par1, par2


def SAVE_LOG():                                                                         # Saves log_entries to the 'activity.log' file in flash

    # ─── Why `busy` exists, and why it is cleared in a `finally` ──────────
    # The idle loop runs SAVE_LOG on core1 (_thread.start_new_thread). Writing
    # to the Pico's flash stops BOTH cores while a sector is programmed, so a
    # log write must not overlap a LOAD or SAVE block, or the pre-header burst
    # after a SYNC: the Z80 keeps clocking bytes out and the 4-deep PIO FIFO
    # overflows. `busy` is how core0 knows a write is in progress; the main
    # loop waits for it to clear (WAIT_CORE1) before it starts a transfer.
    #
    # It used to be cleared only on the success path. If the write raised --
    # flash full, a filesystem error -- the thread died with `busy` still True,
    # and every `while busy: pass` waiting on it spun for ever: the next
    # LOAD "tpi:file" (COPY_FILE), SAVE or LOAD hung the Pico until a power
    # cycle, and the idle loop never tried to save the log again (it only
    # starts SAVE_LOG when `not busy`). Found by the 2026-09-30 audit;
    # reproduced in src/test/audit_fixes_hosttest.py. The `finally` makes
    # "busy is False once SAVE_LOG has finished" true on every path.
    #
    # `busy = True` is ALSO set by the idle loop just before it starts this
    # thread (see there); setting it again here covers the synchronous calls
    # from LOAD_CONFIG.
    # ─────────────────────────────────────────────────────────────────────

    global busy
    global log_entries

    busy = True

    try:
        with open("/activity.log", "a") as logfile:
            for e in log_entries:
                logfile.write(e)
            # writelines doesn't add newlines, but our log strings already have them.
    finally:
        # The entries are dropped even when the write failed. Keeping them
        # would mean retrying a write that will most likely fail again (a
        # full flash stays full) while log_entries grows without limit in
        # the Pico's ~150 KB heap -- the log is not worth running out of
        # memory for. The error itself can't be logged: that is the log.
        log_entries = []
        busy = False

    return


def WAIT_CORE1(limit_ms, who):                                                          # bounded wait for a SAVE_LOG on core1

    """Wait until core1 has finished writing the log (`busy` is False), but
    for at most limit_ms. True if core1 is idle, False if we gave up.

    Why wait at all: a flash write stops both cores (see SAVE_LOG), so a
    transfer that starts while one is in progress can lose bytes mid-block.
    Why bounded: `busy` is set and cleared by another core, and the old
    unbounded `while busy: pass` turned any way of it staying True into a
    hang that only a power cycle cleared. Giving up costs, at worst, one
    transfer that overlaps a write -- recoverable, and the 2068 reports it
    -- while waiting for ever costs the whole session.

    The limit is chosen by the caller from what the Z80 tolerates at that
    point. A normal log write takes a few tens of ms, so any limit here is
    many times what a healthy write needs.
    """

    if not busy:
        return True
    t = time.ticks_ms()
    while busy:
        if time.ticks_diff(time.ticks_ms(), t) >= limit_ms:
            LOG("%s: gave up waiting %d ms for the log write on core1" % (who, limit_ms), 2)
            return False
    return True


def CLEAR_LOG():                                                                         # Clear log_entries and the 'activity.log' file in flash
    
    global busy
    global log_entries
    
    busy = True
    ok = True

    try:
        with open("/activity.log", "w") as logfile:
            log_entries = []
        LOG("Log file was cleared", 0)
    except:
        LOG("OS error clearing log file", 2)
        ok = False

    busy = False

    return ok


def MSG_BYTE(m):                                                                         # one character of SEND_MSG text -> one byte

    """The byte to send for one character of a SEND_MSG message: printable
    ASCII as is, anything else as '?'.

    Why: SEND_MSG used to pass each character straight to MQ.put(). Since #79
    its messages carry raw names from the card ("Copied %s", "Erased %s"),
    and a name can have non-ASCII characters. MicroPython's put() takes a
    str as a buffer, so 'é' went out as TWO bytes (C3 A9, its UTF-8). Both
    are >= 80h, which ends the ROM's string early (the 0x81 reader stops on
    any byte >= 80h: EXROM 068E, CP 80h) -- and CMD_PUT only made room for
    one word, so a two-word put into a FIFO with one slot left blocked.
    SEND_MSG2 has always replaced these with '?'; this makes SEND_MSG agree.
    Control codes are replaced too (00h would end the string), except
    0Dh: the ROM prints it as a new line, SEND_MSG itself sends one
    between msg and msg1, and messages build their lines with chr(13) --
    tpi:zx48, tpi:info and the romupdate refusal among them. Replacing it
    (#107) printed every one of those line breaks as '?'. (2026-09-30
    audit.)"""

    o = m if isinstance(m, int) else ord(m)
    return o if 32 <= o <= 127 or o == 0x0D else 0x3F


def SEND_MSG(msg, msg1, st: bytes, forceDisplay=False):                                         # Sends one-line status message(s)
                                                                                                # back to the TS, once a command is finished
    global MQ
    global TSP

    wrt = CMD_PUT     # never blocks; BREAK raises CmdAbort (#51)

    if msg is NO_CARD_MSG:                                                    # the one error everyone must see
        forceDisplay = True

    # ─── DUAL-PORT MIGRATION ──────────────────────────────────────────────
    # The two `wrt(0x40)` "Read continue flag" writes in the single-port
    # version have been removed. The continue flag now lives on $0F via
    # the Y register (kept at READY for the entire session). A 0x40 in
    # the TX FIFO would have been consumed by the Z80's $0E read as if
    # it were data — orphaning the rest of the response by one byte.
    #
    # `MQ_READY()` after the data is loaded is REQUIRED: the PIO drops Y to
    # BUSY on every Z80 OUT (#14), so after the command's body Y is BUSY,
    # and without this the Z80 never sees READY and gives Report J. (It
    # was once described here as redundant; the 2026-09-30 audit tried
    # removing it.)
    # ─────────────────────────────────────────────────────────────────────
    if TSP.VERBOSE or forceDisplay:

        # ─── Issue #14: pre-fill TX, then MQ_READY, then stream body ───
        # PIO auto-busy left Y = 0 from the last Z80 OUT before this
        # call. The body for-loop would fill TX to 4 (FIFO depth) and
        # then deadlock — Z80 can't drain while Y is BUSY, wrt() blocks
        # on full FIFO. Put the first 3 header bytes in TX (satisfying
        # "byte in buffer before signaling ready"), THEN MQ_READY, then
        # the body loop is paced by Z80 reads.
        # ───────────────────────────────────────────────────────────────
        ob = bytearray()        # the whole message, then CMD_SEND
        put = ob.append
        put(FN_PRINT_STRING)    # 0x81 PRINT STRING — this IS the D-block status
        put(st)                 # Return code
        put(0x0D)               # Start with a newline
        for m in msg:           # The message
            put(MSG_BYTE(m))    # ~ and | still pass, as FREE and STICK
        if msg1:                # Write msg1
            put(0x0D)
            for m in msg1:
                put(MSG_BYTE(m))
        put(STR_END)            # 0x00: end of string
        CMD_SEND(ob, True)      # header in TX, READY, the rest as the Z80 reads

    else:

        wrt(st)                 # Return code (< 0x80) — IS the D-block status
        MQ_READY()              # one-byte status is in TX; signal ready

    TLM("SEND_MSG enter+loaded", "msg=%r msg1=%r st=%d verbose=%s force=%s" % (
        msg[:30] if isinstance(msg, str) else msg, msg1, st, TSP.VERBOSE, forceDisplay))

    CMD_DRAIN()
    TLM("SEND_MSG exit")
    return


def SEND_MSG2(msg, st: bytes, expandKeywords = True, colour = False):                                         # Sends a SCROLLING status message back to the TS,
                                                                                              # once a command is finished
    # msg: a string of the message (no bytearrays)
    # st:  report status

    global MQ
    global TSP
    
    global kill
    global dead

    TLM("SEND_MSG2 enter", "msg_len=%d st=%d expand=%s rom_ver=%s" % (
        len(msg), st, expandKeywords, TSP.ROM_VERSION))

    # ─── No old-ROM ("1.0") branch any more ────────────────────────────────
    # SEND_MSG2 used to switch protocols on TSP.ROM_VERSION: "1.0" meant a
    # pre-1.2 ROM whose 0x86 handler had no 0x03 end-of-loop byte, so pages
    # ended in 0x00, every page prompted, the last one said "--- End of list
    # (N to exit) ---" and a CR replaced the erase sequence. But ROM_VERSION
    # is not detected from the ROM: it is a string in config.ini. Every ROM
    # this firmware can run with (1.5w, 2.0, 2.1) ends the loop on 0x03
    # (EXROM 06F5, CP 03h), so a stale "1.0" left in an old config.ini
    # paired the old protocol with a new ROM, and multi-page listings broke
    # (no 0x03, so the 2068 never left the loop). Removed by the 2026-09-30
    # audit; cmd_io_hosttest.py runs a listing with ROM_VERSION "1.0" to
    # show it is ignored now. ROM_VERSION is still shown by tpi:info.
    # ─────────────────────────────────────────────────────────────────────
    end_char = LOOP_END                                # 0x03: end of the 0x86 loop

    scroll = "Scroll? (Y/n)"

    s = len(scroll) + 6
    n = len(msg)

    # ─── Inline-wrt SEND_MSG2 ──────────────────────────────────────────────
    # Confirmed by regression test: the buffer-prebuild + preload-then-
    # MQ_READY refactor caused `tpi:help border` to consistently fail,
    # even though both patterns place the same 4 header bytes in TX at
    # the moment Y=READY fires. The original inline-wrt pattern (bytes
    # go directly to TX as the per-char loop produces them) handles
    # border correctly, so we're back to that.
    #
    # The "Scroll? (Y/n)" prompt is gated on the line count alone (l == ll
    # below), so output that fits on one screen never prompts. An earlier
    # character threshold (no prompt under 500 chars) is gone: it changed
    # nothing for one-screen output and suppressed the prompt exactly when
    # it was needed, for many short lines (e.g. a long directory listing).
    # ─────────────────────────────────────────────────────────────────────

    # Each page is built in RAM, then sent by CMD_SEND: the 4 header bytes
    # into TX, READY -- so the Z80's first $0E read finds a real byte --
    # and the rest by DMA where there is one. The ROM reads it all blind.
    ob = bytearray()
    wrt = ob.append

    wrt(FN_PRINT_LOOP)  # 0x86 PRINT STRING WITH LOOP (this IS the D-block status)
    wrt(st)     # BASIC return code
    wrt(0x0D)   # Start on a new line
    wrt(0x0D)   # Start with a blank line we don't count

    CMD_RX_FLUSH()              # stray keystrokes (a BREAK among them raises CmdAbort)

    TLM("SEND_MSG2 inline-wrt start", "header+MQ_READY done")

    c = 0       # char count
    l = 0       # line count
    ll = 21     # initial line limit
    i = -1

    while i < n - 1:

        i += 1
        ch = ord(msg[i])

        if ch < 32:

            if ch == 0x0D:
                if i+1 < n and msg[i+1] == '\n':
                    i += 1
                c = 32

            elif ch == 0x0A:
                ch = 0x0D
                c = 32

            elif ch == 0x08:
                if l > 0 or c > 0:
                    if c == 0:
                        c = 31
                        l -= 1
                    else:
                        c -= 1
                else:
                    continue

            elif ch >= 0x10 and ch <= 0x15:
                # INK/PAPER and a value the ROM can take: kept, zero width,
                # in a message built with colour codes (see INK_). Any other
                # attribute code, and every one in other text, is dropped
                # with its value byte.
                if colour and ch <= 0x11 and i + 1 < n and ord(msg[i+1]) in (1, 2, 4, 5, 6, 7, 8, 9):
                    wrt(ch)
                    wrt(ord(msg[i+1]))
                i += 1
                continue

            else:
                ch = 0x3F   # '?'
                c += 1

        elif ch >= 124:

            if ch > 127:
                ch = 63
                c += 1
            elif expandKeywords:
                # The 2068 prints codes 124 and 126 as keywords, so the column
                # counter must advance by the printed width. 124 is STICK and
                # 126 is FREE: the ROM's keyword table runs ... DELETE, ON ERR
                # (123), STICK (124), SOUND (125), FREE (126), RESET (127)
                # (docs/rom-analysis/ERROR_TRAPPING.md; xchr() agrees). With
                # their spaces that is " STICK " = 7 and " FREE " = 6. These two
                # widths were swapped until the 2026-09-30 audit (Ryan's
                # comments had 124 as FREE), so each one in a listing put the
                # line count a column out.
                if ch == 124:
                    c += 7                               # " STICK "
                elif ch == 126:
                    c += 6                               # " FREE "
                else:
                    c += 1
            else:
                c += 1

        elif msg[i] == '\\':
            if i+1 < n and msg[i+1] == '*':
                ch = 127
                i += 1
            c += 1

        else:
            c += 1

        wrt(ch)

        # ─── A line is full at column 32 -- or past it ─────────────────────
        # This used to be `if c == 32:`. A keyword is 6 or 7 columns wide, so
        # one that starts at column 26-31 takes c from below 32 to above it
        # without ever equalling 32: that line was never counted, c was never
        # reset, and the rest of the message got no Scroll? prompt at all. The
        # ROM wraps the keyword onto the next line itself, so for c > 32 the
        # line is counted and the overflow carried over, and no CR is written
        # (the print position is already on the next line). Found together
        # with the width fix above (2026-09-30 audit).
        if c >= 32:

            l += 1

            if c > 32:
                c -= 32                              # the part of the keyword that wrapped
            else:
                c = 0

                if ch == 0x0D:
                    if i == 0 or (i == 1 and msg[1] == '\n'):
                        l -= 1
                else:
                    if i + 1 < n:
                        if msg[i+1] == '\r':
                            if i + 2 < n and msg[i+2] == '\n':
                                i += 1
                            i += 1
                        elif msg[i+1] == '\n':
                            i += 1
                    wrt(0x0D)

            # Prompt at the page's end unless what's left fits on the line or
            # two the screen can still scroll: under 34 characters AND at most
            # one line break. Characters alone let a tail of short lines (help
            # text, a listing ending in one-word rows) scroll the page off
            # unread: 21 lines + 12 short ones printed 34 with no prompt
            # (audit §4, "n > i + 34"; host check 2026-10-03).
            if l == ll and (n > i + 34 or msg.count("\r", i + 1) + msg.count("\n", i + 1)
                            - msg.count("\r\n", i + 1) > 1):
                # Scroll-prompt path (inline-wrt style).
                l = 0
                for m in "(%2d%%) " % ((i * 100) // n):
                    wrt(ord(m))
                for m in scroll:
                    wrt(ord(m))
                wrt(STR_END)    # 0x00: end of this page
                CMD_SEND(ob, True)
                # ─── Issue #14: 0x86 bit-6 ack (PIO auto-busy variant) ─
                # When the Z80 sends the keypress (its OUT $0E for the
                # 'Y'/'N'/digit), the PIO automatically drops Y to 0
                # via the `mov(y, null)` after `push(noblock)` in
                # TS_IO_DUAL's z80_out path. So as soon as MQ.get()
                # returns we're already in BUSY state — no MQ_BUSY()
                # call needed here, no race to win.
                #
                # All we have to do is re-assert MQ_READY() before
                # pushing the first byte of the next page. That fires
                # the Z80's wait_bit6 exit with real data ready.
                # ──────────────────────────────────────────────────────

                ch = CMD_KEY()      # BREAK at the prompt raises CmdAbort (#51)
                if ch == 78:    # 'N' → done. Z80 exits 0x86 without bit-6 check
                    MQ_READY()  # restore Y for downstream reads (V6 pre-load)
                    return
                if ch == 48:
                    ll = 10
                elif ch >= 49 and ch <= 57:
                    ll = ch - 48
                else:
                    ll = 21

                # READY only once the first erase bytes are in TX --
                # data in TX first, then READY: the Z80 reads TX the moment it sees
                # READY, and an empty TX reads as 00. The slow MQ.exec() used to hide
                # READY-before-data here (READY landed ~9.6 ms late); with MQX the
                # 2068 read 00 and Commander crashed on tpi:cd (hardware, 2026-09-27).
                # CMD_SEND keeps that order: the next page goes out with the
                # first bytes in TX before READY.
                ob = bytearray()
                wrt = ob.append
                for _eb in range(s):
                    wrt(0x08)
                    wrt(0x20)
                    wrt(0x08)

    wrt(end_char)
    CMD_SEND(ob, True)
    TLM("SEND_MSG2 end_char written", "0x%02X" % end_char)

    CMD_DRAIN()
    rx_drained = 0
    while MQ.rx_fifo() != 0:    # stray bytes (keys typed during output)
        MQ.get()
        rx_drained += 1
    TLM("SEND_MSG2 exit", "rx_drained=%d" % rx_drained)


def WALK(top):
    """ Walk directory tree yielding (path, [subdirs]) """
    
    subdirs = []
    
    for name, ftype, inode, *_ in os.ilistdir(top):
        if ftype == 0x4000: # DIR_TYPE
            subdirs.append(name)
            
    yield top, subdirs
    
    for dirname in subdirs:
        
        yield from WALK("%s/%s" % (top, dirname))


def GET_DIRS(path='/sd/TAP'):
    """ Get list of all directories recursively from path """
    
    paths = [path[3:]]
    
    try:
        for dirpath, dirnames in WALK(path):
            for dirname in dirnames:
                paths.append("%s/%s" % (dirpath[3:], dirname)) # Remove '/sd' prefix
        del dirnames
        paths.sort()
        LOG("Directories list succesfully updated", 0)
    except Exception as e:
        LOG(f"Unable to succesfully update directories list: {e}", 2)
    
    return paths


def DIR(pre, cmd):                                                                              # Directory listing

    # SAVE "tpi:dir"            - Normal directory of files
    # SAVE "tpi:dir"CODE 1,n    - Show long name for file n
    # SAVE "tpi:dir"CODE 2,0    - Show a dir of files with their index and whole names
    # SAVE "tpi:dir"CODE 2,n    - Show a dir of files starting at file n
    # SAVE "tpi:dir <arg>"      - CAT "<arg>": another directory, a pattern
    #                             ("*.tap", "games/b*") or a TAP's contents

    global lista
    global led
    global files

    par1, par2 = PARAMS(pre)

    TLM("DIR enter", "par1=%d par2=%d files=%d lista_len=%d" % (
        par1, par2, len(files), len(lista)))

    arg = getArgs(cmd).strip()
    if par1 == 0 and arg:
        CATALOG(arg)
        return

    if par1 == 0:
        # Regular listing. It is the one made when this card and folder were
        # last read, so look at the card first (one mount, ~0.2 s): a
        # different card is read afresh (SD_NOTE_CARD), a card that has
        # been taken out gets the no-card answer instead of its old files,
        # and a folder that changed on the card is re-read (LISTING_FRESHEN).
        if not LISTING_CHECK():
            NO_CARD_REPLY("TPI:DIR")
            return
        TLM("DIR par1=0 — regular listing via SEND_MSG2")
        led.value(1)
        SEND_MSG2(CAT_COLOUR(lista), 1, False, True)
        TLM("DIR SEND_MSG2 returned")
        led.value(0)

    elif par1 == 1 or par1 == 2:

        n = len(files)
        if par2 >= n:
            msg = "File index %d out of range 0-%d" % (par2, n)
            LOG(msg, 2)
            SEND_MSG(msg, "", _6_6_Num2Big)
            return
        
        if par1 == 1:
            # Long name of a file by index
            SEND_MSG("Path: %s" % public_path(), "File: %s" % files[par2], _1_OK, True)
            return

        # Index and full names of only files
        led.value(1)
        idx = par2
        # CAT's colours (2026-10-02): the path on the blue bar, the titles
        # on cyan, the dashed line gone, each number on a cyan chip.
        M = [PAPER_ + "\x01" + INK_ + "\x07" + "%-32s" % ("Path:%s" % public_path(27))]
        M.append(PAPER_ + "\x05" + INK_ + "\x09" + "  #  File Name         %3d files" % n)
        for f in range(par2, n):
            M.append(PAPER_ + "\x05" + INK_ + "\x09" + "%03d" % idx + NORMAL_ + " %s\r" % files[f])
            idx += 1
        M.append(NORMAL_)
        msg = "".join(M)
        SEND_MSG2(msg, 1, True, True)
        led.value(0)

    else:
        msg = BAD_CODE("DIR", par1, par2)
        LOG(msg, 2)
        SEND_MSG(msg, "", _8_A_Invalid_arg)
  
    return



def CATALOG(arg):                                                                               # CAT "arg" / SAVE "tpi:dir arg"

    """List what arg names: a directory, the files matching a pattern in the
    last path component, or the blocks of a TAP file. Bare DIR stays the
    cached lista; this reads the card, so it brackets the SD access itself.
    See docs/DISK_COMMANDS_SPEC.md §2."""

    TLM("CATALOG enter", "arg=%r" % arg)
    led.value(1)
    ACTIVATE_SD()
    try:
        msg, st = CATALOG_TEXT(arg)
    except OSError as e:
        LOG("CATALOG: SD card error: %s" % e, 2)
        msg, st = "SD card error", _3_F_Invalid_file
    finally:
        DEACTIVATE_SD()
        ACTIVATE_MQ()
    if st == _1_OK:
        SEND_MSG2(CAT_COLOUR(msg), _1_OK, False, True)
    else:
        LOG(msg, 1)
        SEND_MSG(msg, arg, st)
    led.value(0)


def CATALOG_TEXT(arg):                                                                          # CATALOG's listing, SD already active

    global TSP
    global files

    where, pat = catalog.split_arg(arg)
    real = catalog.resolve(TSP.cur_path, where)
    if real is None:
        return "Not found: %s" % arg, _3_F_Invalid_file
    try:
        mode = os.stat(real)[0]
    except OSError:
        return "Not found: %s" % arg, _3_F_Invalid_file
    is_dir = mode & 0x4000

    if pat is None and not is_dir:                                                              # one file: a TAP's blocks, else its entry
        name = real[real.rfind('/') + 1:]
        if name[-4:].upper() == '.TAP':
            if TSP.f_name.upper() == real.upper() and TSP.offset_tbl:
                tbl, cur = TSP.offset_tbl, TSP.tap_idx                                          # the mounted file: its live table and position
            else:
                with open(real, "rb") as f:
                    tbl = catalog.tap_table(f)
                cur = None
            N = ["File:%-27s" % shorten_filename(xstr(catalog.public(real)), 27)]
            N.append("%-32s" % ("%d blocks%s" % (len(tbl), ", mounted" if cur is not None else "")))
            N.append("Blk Type         Len  Name      ")
            N.append("--------------------------------")
            rows = catalog.tap_header_rows(tbl, cur, orphans=True)
            N.extend(rows if rows else ["%s\r" % "<empty file>"])
            return "".join(N), _1_OK
        parent = real[:real.rfind('/')]
        for item in os.ilistdir(parent):                                                        # the name as stored, not as typed
            if item[0].upper() == name.upper():
                name = item[0]
                break
        entries = [(name, False, os.stat(real)[6])]
        path = catalog.public(parent)
    else:
        if not is_dir:
            return "Not a directory: %s" % where, _3_F_Invalid_file
        entries = catalog.select(os.ilistdir(real), pat)                        # dirs, files, then DIR's unindexed
        if not entries:
            return ("No match for %s" % pat) if pat else ("Directory is empty"), _3_F_Invalid_file
        path = catalog.public(real)

    listed = real if is_dir else real[:real.rfind('/')]
    here = listed.upper() == TSP.cur_path.upper()
    upper = [f.upper() for f in files] if here else []
    index_of = lambda n: upper.index(n.upper()) if n.upper() in upper else None
    nf = sum(1 for e in entries if not e[1])
    line2 = (("%s: " % pat) if pat else "") + catalog.counts(nf, len(entries) - nf)
    header = DIR_HEADER(line2, shorten_filename(xstr(path), 27))
    return header + "".join(catalog.dir_rows(entries, index_of, shorten_filename)), _1_OK


# ─── MOVE / ERASE / FORMAT (docs/DISK_COMMANDS_SPEC.md §3) ─────────────────
# The ROM turns MOVE "a" TO "b", ERASE "x" and FORMAT "x" into tpi:copy a|b,
# tpi:erase x and tpi:format x; tpi:ren a|b has no keyword. Paths resolve like
# CAT's (catalog.resolve: '/' is the SD root, '..' never climbs above it).
# Nothing here overwrites: an existing target is Report F.

def SD_CALL(fn, *args):                                                       # run fn with the SD card, then hand it back

    """Run fn(*args) with the SD card active and always give the pins back to
    the MQ. An SD error becomes ("SD card error", Report F)."""

    try:
        ACTIVATE_SD()
        return fn(*args)
    except OSError as e:
        if not TSP.sd_present:                                                # the mount failed: no card
            return NO_CARD_MSG, _10_J_Invalid_IO
        LOG("SD card error: %s" % e, 2)
        return "SD card error", _3_F_Invalid_file
    finally:
        DEACTIVATE_SD()
        ACTIVATE_MQ()


# Commands that work without the SD card. Everything else in SA_funct needs
# it, and so do LOAD "tpi:name" (mount) and tpi:help <topic> (the help files
# are on the card). External commands decide for themselves.
SD_FREE = frozenset((
    "TPI:INFO", "TPI:VERBOSE", "TPI:LOGLEVEL", "TPI:LOG", "TPI:BOOT", "TPI:MEMBOOT",
    "TPI:DOCK", "TPI:MEMDOCK", "TPI:ZX48", "TPI:NOP", "TPI:PATH", "TPI:CLOSE",
    "TPI:TAPDIR", "TPI:FFW", "TPI:REW", "TPI:APPEND", "TPI:BLKRCV", "TPI:CHCLOSE",
    "TPI:AUTOLF", "TPI:NOAUTOLF", "TPI:AUTOPG", "TPI:NOAUTOPG", "TPI:BMP", "TPI:PRNSZ",
    "TPI:CONFIG", "TPI:DELETE", "TPI:FRESET", "TPI:GETCONFIG", "TPI:LIST",
    "TPI:MEMINFO", "TPI:STOP"))

# Commands the fdd ROM sends in the middle of a BASIC statement (OPEN #,
# PRINT #, INPUT #, SAVE/LOAD "f:"): a printed message would move the ROM's
# current channel, so these get the bare status (CH_REPLY does the same).
SD_QUIET = frozenset(("TPI:CHOPEN", "TPI:CHWR", "TPI:CHRD", "TPI:FOPEN"))


def SD_NEEDED(load_cmd, cmd_word, cmd_exec, SA_funct):                        # does this command need the card?

    if load_cmd:
        return True                                                           # LOAD "tpi:name": mount a file
    if cmd_word == "TPI:HELP":
        return cmd_exec.strip() != cmd_word                                   # a topic is a file on the card
    return cmd_word in SA_funct and cmd_word not in SD_FREE


def NO_CARD_REPLY(cmd_word):                                                  # the command's answer: no card

    LOG("%s: no SD card" % cmd_word, 1)
    if cmd_word in SD_QUIET:
        CH_REPLY(_10_J_Invalid_IO)
    else:
        SEND_MSG(NO_CARD_MSG, "", _10_J_Invalid_IO, True)


def REFRESH_IF(*dirs):                                                        # DIR_FILES if any dir is the current one

    if any(d.upper() == TSP.cur_path.upper() for d in dirs):
        os.chdir(TSP.cur_path)
        DIR_FILES()


def PROMPT_EACH(prompts):                                                     # one 0x86 exchange, one key per prompt

    """Ask each prompt in one function-0x86 exchange and return the indexes
    answered Y. Any other key skips that one. N ends the exchange -- the ROM
    stops its loop on N -- so nothing from there on is chosen. Same byte
    sequence as ListMenu: the echo of the last key starts the next string,
    READY goes up after it, and 0x03 ends the loop."""

    global MQ

    wrt = CmdOut()    # each page built in RAM, sent by CMD_SEND (DMA); BREAK raises CmdAbort
    CMD_RX_FLUSH()                                                            # stray keystrokes; a BREAK raises CmdAbort
    wrt(FN_PRINT_LOOP)                                                        # 0x86 PRINT STRING WITH LOOP -- the D-block status
    wrt(1)                                                                    # BASIC return code
    need_ready = True
    yes = []
    ch = None
    for i, p in enumerate(prompts):
        if ch is not None:
            wrt(ch if 32 <= ch < 127 else 89)                                 # echo the last answer
        wrt(0x0D)
        for m in p:
            wrt(m)
        wrt(STR_END)                                                          # 0x00: Z80 prints, waits for a key
        wrt.send()                                                            # data in TX first, then READY
        ch = CMD_KEY()                                                        # BREAK here raises CmdAbort
        if ch in (78, 110):                                                   # N: the ROM has left its loop
            MQ_READY()
            return yes
        if ch in (89, 121):
            yes.append(i)
        need_ready = True
    wrt(ch if 32 <= ch < 127 else 89)
    wrt(LOOP_END)                                                             # 0x03: end the loop
    wrt.send()
    CMD_DRAIN()
    return yes


def DISK_COPY(pre, cmd):                                                      # MOVE "a" TO "b" / SAVE "tpi:copy a|b"

    # SAVE "tpi:copy a|b"      - copy file a to b (b may be a directory)
    # SAVE "tpi:copy *.tap|d"  - copy the matching files into directory d

    TLM("DISK_COPY enter")
    a, b = catalog.split_pair(getArgs(cmd))
    if not a or not b:
        SEND_MSG("Copy needs a source and a destination", "", _4_Q_Parameter)
        return
    led.value(1)
    msg, st = SD_CALL(DISK_COPY_WORK, a, b)
    led.value(0)
    if st == _1_OK and isinstance(msg, list):
        SEND_MSG2("".join(msg), _1_OK, False)
    else:
        if st != _1_OK:
            LOG(msg, 1)
        SEND_MSG(msg, "", st)


def DISK_COPY_WORK(a, b):                                                     # DISK_COPY with the SD active

    cur = TSP.cur_path
    where, pat = catalog.split_arg(a)
    dst = catalog.resolve(cur, b)
    if dst is None:
        return "Not found: %s" % b, _3_F_Invalid_file
    dst_is_dir = dir_exists(dst)
    jobs = []
    if pat:
        src_dir = catalog.resolve(cur, where)
        if src_dir is None or not dir_exists(src_dir):
            return "Not found: %s" % a, _3_F_Invalid_file
        if not dst_is_dir:
            return "Copy them to a directory", _4_Q_Parameter
        for item in sorted(os.ilistdir(src_dir), key=lambda it: it[0].lower()):
            n = item[0]
            if item[1] == 16384 or n == "dirinfo.tap" or not catalog.match(n, pat) \
                    or (n[0] == '.' and pat[0] != '.'):
                continue
            jobs.append((src_dir + '/' + n, dst + '/' + n))
        if not jobs:
            return "No match for %s" % pat, _3_F_Invalid_file
    else:
        src = catalog.resolve(cur, a)
        if src is None or not (file_exists(src) or dir_exists(src)):
            return "Not found: %s" % a, _3_F_Invalid_file
        if dir_exists(src):
            return "Can't copy a directory", _4_Q_Parameter
        name = catalog.basename(src)
        for item in os.ilistdir(catalog.parent(src)):                         # the name as stored, not as typed
            if item[0].upper() == name.upper():
                name = item[0]
                break
        jobs.append((src, dst + '/' + name if dst_is_dir else dst))

    rows = []
    touched = []
    for s_, d_ in jobs:
        name = catalog.basename(s_)
        if s_.upper() == d_.upper():
            why = "same file"
        elif file_exists(d_) or dir_exists(d_):
            why = "exists"
        elif not dir_exists(catalog.parent(d_)):
            why = "no such dir"
        elif COPY_FILE(s_, d_):
            why = ""
            touched.append(catalog.parent(d_))
        else:
            why = "copy failed"
            try:
                os.remove(d_)                                                 # no half-copied file left behind
            except OSError:
                pass
        if pat is None:                                                       # one file: one answer
            REFRESH_IF(*touched)
            if why == "":
                return "Copied %s" % name, _1_OK
            if why == "copy failed":
                return "Copy failed: %s" % name, _4_Q_Parameter
            return "%s: %s" % (catalog.public(d_), why), _3_F_Invalid_file
        rows.append("%-32s" % ("%s %s" % (shorten_filename(xstr(name), 18),
                                          "copied" if why == "" else why))[:32])
    REFRESH_IF(*touched)
    return rows, _1_OK


def DISK_ERASE(pre, cmd):                                                     # ERASE "x" / SAVE "tpi:erase x"

    # SAVE "tpi:erase name"    - delete a file, no prompt (silent unless verbose)
    # SAVE "tpi:erase *.bak"   - delete matching files, Erase <name> (Y/N)? each:
    #                            Y erases, N stops, any other key skips
    # SAVE "tpi:erase dir/"    - remove an empty directory

    TLM("DISK_ERASE enter")
    arg = getArgs(cmd).strip()
    if not arg:
        SEND_MSG("Name required", "", _4_Q_Parameter)
        return
    where, pat = catalog.split_arg(arg)
    if pat is None:
        msg, st = SD_CALL(DISK_ERASE_ONE, arg)
        if st != _1_OK:
            LOG(msg, 1)
        SEND_MSG(msg, "", st)
        return
    found, st = SD_CALL(DISK_ERASE_MATCHES, where, pat)
    if st != _1_OK:
        SEND_MSG(found, "", st)
        return
    chosen = PROMPT_EACH(["Erase %s (Y/N)?" % shorten_filename(xstr(catalog.public(p)), 20)
                          for p in found])
    if chosen:                                                                # the exchange is over: now the card
        SD_CALL(DISK_ERASE_LIST, [found[i] for i in chosen])


def DISK_ERASE_ONE(arg):                                                      # one file, or an empty dir/

    cur = TSP.cur_path
    is_dir = arg.endswith('/')
    real = catalog.resolve(cur, arg.rstrip('/') if is_dir else arg)
    if real is None:
        return "Not found: %s" % arg, _3_F_Invalid_file
    if is_dir:
        if not dir_exists(real):
            return "Not found: %s" % arg, _3_F_Invalid_file
        if catalog.within(cur, real):
            return "Can't erase the current directory", _4_Q_Parameter
        try:
            os.remove(real + "/dirinfo.tap")                                  # DIR_FILES' own file doesn't count
        except OSError:
            pass
        try:
            os.rmdir(real)
        except OSError:
            return "Directory not empty", _4_Q_Parameter
        alldirs[:] = [d for d in alldirs if not catalog.within(d, real[3:])]
        REFRESH_IF(catalog.parent(real))
        return "Erased %s" % catalog.public(real), _1_OK
    if dir_exists(real):
        return 'A directory: ERASE "%s/"' % arg, _4_Q_Parameter
    if not file_exists(real):
        return "Not found: %s" % arg, _3_F_Invalid_file
    if TSP.f_name and TSP.f_name.upper() == real.upper():
        return "File is mounted", _4_Q_Parameter
    os.remove(real)
    REFRESH_IF(catalog.parent(real))
    return "Erased %s" % catalog.public(real), _1_OK


def DISK_ERASE_MATCHES(where, pat):                                           # the files a pattern names

    d = catalog.resolve(TSP.cur_path, where)
    if d is None or not dir_exists(d):
        return "Not found: %s" % where, _3_F_Invalid_file
    found = [d + '/' + it[0] for it in sorted(os.ilistdir(d), key=lambda it: it[0].lower())
             if it[1] != 16384 and it[0] != "dirinfo.tap" and catalog.match(it[0], pat)
             and (it[0][0] != '.' or pat[0] == '.')]
    if not found:
        return "No match for %s" % pat, _3_F_Invalid_file
    return found, _1_OK


def DISK_ERASE_LIST(paths):                                                   # after PROMPT_EACH: erase the chosen

    for p in paths:
        if TSP.f_name and TSP.f_name.upper() == p.upper():
            LOG("ERASE: %s is mounted, kept" % p, 1)
            continue
        try:
            os.remove(p)
            LOG("Erased %s" % p, 0)
        except OSError as e:
            LOG("ERASE: %s: %s" % (p, e), 2)
    REFRESH_IF(*[catalog.parent(p) for p in paths])
    return None, _1_OK


def DISK_FORMAT(pre, cmd):                                                    # FORMAT "x" / SAVE "tpi:format x"

    # SAVE "tpi:format name.tap" - create an empty .tap and mount it (".tap" may be left off)
    # SAVE "tpi:format dir/"     - make a directory
    # Never formats the card, and never overwrites.

    global TSP

    TLM("DISK_FORMAT enter")
    arg = getArgs(cmd).strip()
    if not arg:
        SEND_MSG("Name required", "", _4_Q_Parameter)
        return
    if arg.endswith('/'):
        msg, st = SD_CALL(DISK_MAKE_DIR, arg.rstrip('/'))
        SEND_MSG(msg, "", st)
        return
    base = catalog.basename(arg)
    if '.' not in base:
        arg += '.tap'
    elif base[base.rfind('.'):].upper() != '.TAP':
        SEND_MSG('FORMAT makes "x.tap" or "dir/"', "", _4_Q_Parameter)
        return
    real, st = SD_CALL(DISK_NEW_TAP, arg)
    if st != _1_OK:
        LOG(real, 1)
        SEND_MSG(real, "", st)
        return
    if not MOUNT_FILE(real):
        SEND_MSG("Made it, but can't mount it", "", _4_Q_Parameter)
        return
    TSP.append = True                                                         # SAVE adds to it, as tpi:newtap does
    SEND_MSG("New .tap mounted: ", public_fname(), _1_OK)


def DISK_NEW_TAP(name):                                                       # an empty .tap; its real path

    real = catalog.resolve(TSP.cur_path, name)
    if real is None:
        return "Not found: %s" % name, _3_F_Invalid_file
    base = catalog.basename(real)
    if not base or any(c < ' ' or c > '~' or c in ':*?\\|"<>' for c in base):
        return "Name not allowed: %s" % base, _3_F_Invalid_file
    if file_exists(real) or dir_exists(real):
        return "Already exists: %s" % catalog.public(real), _3_F_Invalid_file
    if not dir_exists(catalog.parent(real)):
        return "Not found: %s" % catalog.public(catalog.parent(real)), _3_F_Invalid_file
    with open(real, "wb"):
        pass
    REFRESH_IF(catalog.parent(real))
    return real, _1_OK


def DISK_MAKE_DIR(name):                                                      # FORMAT "dir/"

    real = catalog.resolve(TSP.cur_path, name)
    if real is None or real == catalog.ROOT:
        return "Not allowed: %s/" % name, _3_F_Invalid_file
    if file_exists(real) or dir_exists(real):
        return "Already exists: %s" % catalog.public(real), _3_F_Invalid_file
    if not dir_exists(catalog.parent(real)):
        return "Not found: %s" % catalog.public(catalog.parent(real)), _3_F_Invalid_file
    os.mkdir(real)
    try:
        alldirs.append(real[3:])
        alldirs.sort()
    except Exception:
        pass
    REFRESH_IF(catalog.parent(real))
    return "Made %s/" % catalog.public(real), _1_OK


def DISK_REN(pre, cmd):                                                       # SAVE "tpi:ren a|b" (no keyword)

    # SAVE "tpi:ren old|new"   - rename (or move, if new is a directory)
    # SAVE "tpi:ren old new"   - the same, typed with a space

    TLM("DISK_REN enter")
    a, b = catalog.split_pair(getArgs(cmd))
    if not a or not b:
        SEND_MSG("Rename needs two names", "", _4_Q_Parameter)
        return
    msg, st = SD_CALL(DISK_REN_WORK, a, b)
    SEND_MSG(msg, "", st)


def DISK_REN_WORK(a, b):

    global alldirs

    cur = TSP.cur_path
    src = catalog.resolve(cur, a)
    if src is None or not (file_exists(src) or dir_exists(src)):
        return "Not found: %s" % a, _3_F_Invalid_file
    is_dir = dir_exists(src)
    if is_dir and catalog.within(cur, src):
        return "Can't rename the current directory", _4_Q_Parameter
    if TSP.f_name and catalog.within(TSP.f_name, src):
        return "File is mounted", _4_Q_Parameter
    dst = catalog.resolve(cur, b)
    if dst is None:
        return "Not found: %s" % b, _3_F_Invalid_file
    if dir_exists(dst):
        dst = dst + '/' + catalog.basename(src)
    if file_exists(dst) or dir_exists(dst):
        return "Already exists: %s" % catalog.public(dst), _3_F_Invalid_file
    if not dir_exists(catalog.parent(dst)):
        return "Not found: %s" % b, _3_F_Invalid_file
    if is_dir and catalog.within(dst, src):
        return "Can't move a directory into itself", _4_Q_Parameter
    os.rename(src, dst)
    if is_dir:
        alldirs = GET_DIRS()
    REFRESH_IF(catalog.parent(src), catalog.parent(dst))
    return "Renamed to %s" % catalog.public(dst), _1_OK


# ─── Native SD files: SAVE / LOAD / VERIFY / MERGE "f:<path>" (spec §4a) ────
# The fdd ROM catches an "f:" name before the stock SAVE/LOAD code, sends
# tpi:fopen <path> with the operation, the statement's modifier token and its
# session, shortens the name, and lets the stock code carry on. This arms
# TSP.native for that session: SAVE_TS then writes the file instead of a .tap,
# and LOAD_TS serves the one-shot tape built here. Both are in tspico_io.py.

NATIVE_TAP = "/TMP/native.tap"
MOD_CODE, MOD_SCREEN, MOD_DATA, MOD_LINE = 0xAF, 0xAA, 0xE4, 0xCA
KIND = {native.T_PROGRAM: "a program", native.T_NUMARR: "an array",
        native.T_CHARARR: "an array", native.T_CODE: "bytes"}


def NATIVE_OPEN(pre, cmd):                                                     # tpi:fopen, from the fdd ROM

    # tpi:fopen <path>   PMR1 = operation (0 SAVE, 1 LOAD, 2 VERIFY, 3 MERGE)
    #                           + 256 * the token after the name (CODE, SCREEN$,
    #                           DATA, LINE) or 0
    #                    PMR2 = the statement's session id

    global TSP

    par1, par2 = PARAMS(pre)
    op, mod, session = par1 & 0xFF, par1 >> 8, par2
    path = getArgs(cmd).strip()
    TSP.native = None
    TLM("NATIVE_OPEN enter", "op=%d mod=%02X session=%04X path=%r" % (op, mod, session, path))
    if not path:
        SEND_MSG("Name required", "", _3_F_Invalid_file)
        return
    if op == 0:
        real, st = SD_CALL(NATIVE_SAVE_TARGET, path)
        if st != _1_OK:
            LOG(real, 1)
            SEND_MSG(real, "", st)
            return
        real, exists = real
        TSP.native = dict(op=0, path=real, session=session, refuse=False)
        if exists:                                                             # TOS: "Supersede (Y/N)?"
            ch = SEND_MSG_PROMPT_YN("Replace %s? (Y/N)"                        # lower screen: SCREEN$ must not save it
                                    % shorten_filename(xstr(catalog.basename(real)), 16), lower=True)    # 31 + the key echo = one line
            TSP.native["refuse"] = ch not in (89, 121)                         # SAVE_TS refuses it: Report D
            return
        SEND_MSG("Saving to %s" % catalog.public(real), "", _1_OK)
        return
    res, st = SD_CALL(NATIVE_LOAD_PREP, path, op, mod)
    if st != _1_OK:
        LOG(res, 1)
        SEND_MSG(res, "", st)
        return
    TSP.native = dict(op=op, session=session, tap=NATIVE_TAP, totlen=res)
    SEND_MSG("Loading %s" % path, "", _1_OK)


def NATIVE_SAVE_TARGET(path):                                                  # (real path, exists?) for a SAVE

    real = catalog.resolve(TSP.cur_path, path)
    if real is None or real == catalog.ROOT:
        return "Not allowed: %s" % path, _3_F_Invalid_file
    base = catalog.basename(real)
    if not base or any(c < ' ' or c > '~' or c in ':*?\\|"<>' for c in base):
        return "Name not allowed: %s" % base, _3_F_Invalid_file
    if dir_exists(real):
        return "A directory: %s" % path, _4_Q_Parameter
    if not dir_exists(catalog.parent(real)):
        return "Not found: %s" % catalog.public(catalog.parent(real)), _3_F_Invalid_file
    if TSP.f_name and TSP.f_name.upper() == real.upper():
        return "File is mounted", _4_Q_Parameter
    return (real, file_exists(real)), _1_OK


def NATIVE_LOAD_PREP(path, op, mod):                                           # the one-shot tape; its length

    real = catalog.resolve(TSP.cur_path, path)
    if real is None or not file_exists(real):
        return "Not found: %s" % path, _3_F_Invalid_file
    size = os.stat(real)[6]
    with open(real, "rb") as f:
        head = f.read(native.HDR_LEN)
        d = native.describe(head, size)
        if d is None:
            if mod == MOD_CODE:
                d = native.headerless_code(size)                               # LOAD "f:x.bin" CODE a: the whole file
            elif mod == MOD_SCREEN:
                return "Not a screen: %s" % path, _4_Q_Parameter
            else:
                return "Not a TS-Pico file: %s" % path, _3_F_Invalid_file
        typ, length, p1, p2, start = d
        if op == 3 or mod in (0, MOD_LINE):
            want = (native.T_PROGRAM,)
        elif mod in (MOD_CODE, MOD_SCREEN):
            want = (native.T_CODE,)
        else:
            want = (native.T_NUMARR, native.T_CHARARR)
        if typ not in want:
            return "%s holds %s" % (catalog.basename(real), KIND.get(typ, "data")), _4_Q_Parameter
        if mod == MOD_SCREEN and length != native.SCREEN_LEN:
            return "Not a screen: %s" % path, _4_Q_Parameter
        hdr_blk = native.tap_block(0x00, native.tape_header(typ, native.tape_name(real), length, p1, p2))
        f.seek(start)
        n = length + 2
        x = 0xFF
        buf = bytearray(512)
        with open(NATIVE_TAP, "wb") as out:                                    # Pico flash: LOAD_TS can't use the card
            out.write(hdr_blk)
            out.write(bytes([n & 0xFF, n >> 8, 0xFF]))
            left = length
            while left > 0:
                k = f.readinto(buf)
                if not k:
                    break
                k = min(k, left)
                for i in range(k):
                    x ^= buf[i]
                out.write(buf[:k])
                left -= k
            if left:
                return "Short file: %s" % path, _2_R_Tape_load
            out.write(bytes([x]))
    return len(hdr_blk) + n + 2, _1_OK


# ─── OPEN # channels, stage 1 (DISK_COMMANDS_SPEC.md §4) ────────────────────
# The fdd ROM's channel driver sends these through the Pico Interface BIOS,
# with the stream number in PMR1:
#   tpi:chopen <mode> <path>   open ("r" / "w" / "a", + "b" for binary)
#   tpi:chwr <hex>             write bytes (hex in the body: no data phase)
#   tpi:chrd                   read up to PMR2 bytes -- a raw data phase:
#                              status, count, the bytes, their XOR (see CH_READ)
#   tpi:chclose                close (not an error if it isn't open)
# No file stays open: the card is unmounted between commands. channels.py
# keeps each stream's path and position and does the text translation.

class SD_FS:
    """channels.py's file access, on the SD card (active while it runs)."""

    def exists(self, p):
        return file_exists(p)

    def size(self, p):
        return os.stat(p)[6]

    def read(self, p, pos, n):
        with open(p, "rb") as f:
            f.seek(pos)
            return f.read(n)

    def write(self, p, pos, data, truncate):
        if truncate:
            with open(p, "wb") as f:
                f.write(data)
            return
        mode = "ab" if pos >= self.size(p) else "r+b"
        with open(p, mode) as f:
            if mode == "r+b":
                f.seek(pos)
            f.write(data)


CHANNELS = channels.Channels(SD_FS())
CH_STATUS = {"F": _3_F_Invalid_file, "Q": _4_Q_Parameter, "O": _10_J_Invalid_IO}


def CH_READY():                                                               # ready, but not idle yet

    """READY without IDLE (0F7h). The fdd ROM's channel driver can send its next
    command the moment it has this one's answer -- CLOSE # flushes and closes
    back to back -- and it waits for IDLE before its SYNC. Plain MQ_READY says
    IDLE too, so that SYNC could land while PROCESS_CMD's tail was still
    draining and logging: the tail's own IDLE then let the pre-header go with
    nobody capturing it ("Partial pre-header 4/10", Report T; hardware,
    2026-09-29). The tail's IDLE is the one that counts."""

    MQ_STATUS(MQ, "mid")


def CH_REPLY(st):                                                             # a bare status: never prints

    """The channel driver runs inside PRINT # / INPUT #: a message printed now
    would move the ROM's current channel to the screen mid-statement. So the
    answer is the status byte alone, whatever VERBOSE says (C_END: 1 = ok)."""

    CMD_PUT(st)
    CH_READY()


def CH_CALL(fn, *args):                                                       # channel op with the SD active

    """(result, status): a ChannelError becomes its report, an SD error F."""

    def run():
        try:
            return fn(*args), _1_OK
        except channels.ChannelError as e:
            return e.args[0], CH_STATUS.get(e.args[1], _4_Q_Parameter)
    return SD_CALL(run)


def DIR_NAMES(arg):                                                           # OPEN #n,"d:arg": the names, SD active

    """The names CAT "arg" would list, one per entry, a directory's with '/'.
    A single file names itself; a directory that isn't there is F."""

    where, pat = catalog.split_arg(arg)
    real = catalog.resolve(TSP.cur_path, where)
    try:
        is_dir = real is not None and os.stat(real)[0] & 0x4000
    except OSError:
        real = None
    if real is None:
        raise channels.ChannelError("Not found", "F")
    if not is_dir:
        if pat is not None:
            raise channels.ChannelError("Not a directory", "F")
        return [catalog.basename(real)]
    return [n + ("/" if d else "") for n, d, _ in catalog.select(os.ilistdir(real), pat)]


def CH_OPEN(pre, cmd):                                                        # tpi:chopen <mode> <path>

    stream, reclen = PARAMS(pre)                                              # PMR2: record length, 0 = a stream
    stream &= 0xFF
    arg = getArgs(cmd).strip()
    k = arg.find(' ')
    mode, path = (arg[:k], arg[k + 1:].strip()) if k > 0 else ("r", arg)
    TLM("CH_OPEN", "stream=%d mode=%r path=%r reclen=%d" % (stream, mode, path, reclen))
    if path[:2].lower() == "d:":                                              # stage 3: a directory listing
        def op():
            if mode.lower() != "r" or reclen:
                raise channels.ChannelError("d: is read-only, no record length", "Q")
            CHANNELS.open_list(stream, DIR_NAMES(path[2:].strip()))
        msg, st = CH_CALL(op)
        if st != _1_OK:
            LOG("OPEN #%d %s: %s" % (stream, path, msg), 1)
        CH_REPLY(st)
        return
    real = catalog.resolve(TSP.cur_path, path) if path else None
    if real is None or real == catalog.ROOT:
        CH_REPLY(_3_F_Invalid_file)
        return

    def op():
        if dir_exists(real):
            raise channels.ChannelError("A directory", "Q")
        if not dir_exists(catalog.parent(real)):
            raise channels.ChannelError("Not found", "F")
        CHANNELS.open(stream, real, mode, reclen)
    msg, st = CH_CALL(op)
    if st != _1_OK:
        LOG("OPEN #%d %s: %s" % (stream, path, msg), 1)
    CH_REPLY(st)


def CH_WRITE(pre, cmd):                                                       # tpi:chwr <hex>

    stream = PARAMS(pre)[0] & 0xFF
    hx = getArgs(cmd).strip()
    try:
        data = bytes(int(hx[i:i + 2], 16) for i in range(0, len(hx), 2))
    except ValueError:
        CH_REPLY(_5_C_Nonsense)
        return
    msg, st = CH_CALL(CHANNELS.write, stream, data)
    CH_REPLY(st)


def CH_READ(pre, cmd):                                                        # tpi:chrd -- the data phase

    # The fdd ROM's driver reads, straight after the command body:
    #   status (1 = data follows; 7 = end of file -> Report 8; others -> their
    #   report), then for 1: the count n (1-255), n bytes, their XOR. It reads a
    #   byte every ~70 us with no handshake, as LOAD does at ~50 us, so the
    #   bytes are ready before READY and garbage is collected first.
    par1, par2 = PARAMS(pre)
    stream, n = par1 & 0xFF, max(1, min(255, par2 or 255))
    data, st = CH_CALL(CHANNELS.read, stream, n)
    wrt = CMD_PUT
    if st != _1_OK or not data:
        wrt(st if st != _1_OK else _7_8_EOF)
        CH_READY()
        return
    gc.collect()
    x = 0
    for b in data:
        x ^= b
    if tspico_io._DMA is not None:
        # All of it by DMA, CH_READY once the channel runs: the ROM reads it
        # blind (~70 us a byte), and a core0 pause longer than the FIFO's
        # ~280 us would hand it 00s. A port-0Fh write or a stall ends it.
        out = bytearray(len(data) + 3)
        out[0] = 1
        out[1] = len(data)
        out[2:-1] = data
        out[-1] = x
        _CMD_ECHO[0] = 0
        r = STREAM_DMA(MQ, out, _CMD_ECHO, CMD_STALL_MS, CH_READY)
        if r is not None:
            if r[0]:
                raise CmdAbort(r[0])
            return
    wrt(1)
    wrt(len(data))
    CH_READY()                                                                # data in TX first, then READY
    for b in data:
        wrt(b)
    wrt(x)


def CH_CLOSE(pre, cmd):                                                       # tpi:chclose

    # ─── Why CLOSE # sometimes needs the card, and sometimes doesn't ───────
    # When OPEN # channels arrived (#83), closing a stream only dropped it
    # from the table, so CH_CLOSE called CHANNELS.close() directly and
    # TPI:CHCLOSE was listed in SD_FREE (commands that never touch the card).
    #
    # Record files (#84) changed that: close() now PADS a part-written record
    # to its full length -- PRINT #4;TAB 2;"ab"; then CLOSE #4 -- and that is
    # a write to the file on the card. But the card is unmounted between
    # commands (DEACTIVATE_SD), and nothing here mounted it, so the padding
    # was written to a card that wasn't there: on hardware an OSError, the
    # 2068 got Report J, and the record stayed short. Found by the 2026-09-30
    # audit; see src/test/audit_fixes_hosttest.py.
    #
    # So: when close() is going to write, run it through CH_CALL, which
    # mounts the card, gives the pins back to the MQ afterwards, and turns a
    # missing card or an SD error into the right status. Otherwise close
    # without the card, as before -- CLOSE # of a read stream, or of a write
    # stream with nothing pending, must keep working with no card in. That
    # is also why TPI:CHCLOSE stays in SD_FREE: the dispatcher must not
    # refuse it up front just because the card is missing.
    # ─────────────────────────────────────────────────────────────────────
    stream = PARAMS(pre)[0] & 0xFF
    if not CHANNELS.close_writes(stream):
        CHANNELS.close(stream)                                                # bookkeeping only: no card needed
        CH_REPLY(_1_OK)
        return
    msg, st = CH_CALL(CHANNELS.close, stream)
    if st != _1_OK:
        # The padding couldn't be written (no card, or an SD error). The
        # stream stays open here, and that is deliberate: on an error status
        # the fdd ROM's CLOSE # reports it and stops BEFORE freeing its own
        # side of the channel (CH_CLOSE_HOOK -> CH_STATUS -> C_FAIL in
        # src/rom/fdd/fddcmd.asm), so BASIC still has the stream open as
        # well. Both sides agree, and CLOSE # can be repeated once the card
        # is back in, writing the padding then. (Channels.close only drops
        # the stream after the write succeeded.)
        LOG("CLOSE #%d: %s" % (stream, msg), 1)
    CH_REPLY(st)

def IDIR(pre, cmd):

    # SAVE "tpi:idir"   - Show an interactive dir list to pick a file to mount

    global files
    global TSP

    TLM("IDIR enter")
    if len(files) == 0:
        SEND_MSG("Directory is empty:", public_path(), _1_OK, True)
        return
    
    led.value(1)
    hdr1 = "Path:%s" % public_path(27)
    hdr2 = "   #  File Name"
    hdr3 = "  ------------------------------"
    List = []
    idx = 0
    for f in files:
        List.append("%03d %s" % (idx, shorten_filename(xstr(f), 26)))
        idx += 1
    isel = ListMenu(List, hdr1, hdr2, hdr3, 'Mount file', "Mounting: ")

    if isel >= 0:
        sel = files[isel]
        if not MOUNT_FILE('%s/%s' % (TSP.cur_path, sel)):
            pass # Can't set or show error now

    led.value(0)

    return


def ListMenu(List, hdr1, hdr2, hdr3, action, chosen, folders=False):

    # Given a list of strings, present them 16 at a time to pick from by
    # pressing keys 0-9,Q-Y or N to stop, B to go back a page or other key to go
    # forward a page. The index of the selection is returned, -1 for none.
    # You can't send a message after using this.
    
    global MQ

    nmax = 16
    nl = chr(13)
    n = len(List)
    idx = 0
    prompt1 = action + " (0.."
    prompt2 = "), (B)ack" + nl + "or (F)orward a page, (N)=quit?"
    letters = "0123456789QWERTY"

    # ─── DUAL-PORT MIGRATION ──────────────────────────────────────────────
    # Removed wrt(0x40) "Read continue" from the start of every loop
    # iteration -- the continue flag lives on $0F (the Y register) now.
    # Order (#70): stale keystrokes are drained BEFORE anything is said;
    # each reply goes into TX first, and only then MQ_READY -- see below.
    # (This note used to say the opposite: drain after READY, and Y kept
    # READY all session. 2026-09-30 audit, §3.)
    # ─────────────────────────────────────────────────────────────────────
    wrt = CmdOut()    # each page built in RAM, sent by CMD_SEND (DMA); BREAK raises CmdAbort

    def codes(s):     # colour codes, a byte at a time (CMD_PUT makes room for one)
        for c in s:
            wrt(ord(c))

    # CAT's colours (2026-10-02): the path on the blue bar, the titles and
    # page on cyan, hdr3's dashed line gone, each choice letter on a cyan
    # chip, folders in blue, the page's place in the list on cyan.
    BAR = PAPER_ + "\x01" + INK_ + "\x07"
    CYAN = PAPER_ + "\x05" + INK_ + "\x09"
    Init = True
    sel = -1
    pgs = (n - 1) // nmax + 1

    # READY is said below, once the first bytes of each reply are in TX --
    # data in TX first, then READY: the Z80 reads TX the moment it sees
    # READY, and an empty TX reads as 00. The slow MQ.exec() used to hide
    # READY-before-data here (READY landed ~9.6 ms late); with MQX the
    # 2068 read 00 and Commander crashed on tpi:cd (hardware, 2026-09-27).
    need_ready = True

    CMD_RX_FLUSH()                      # stray keystrokes; a BREAK raises CmdAbort

    # ─── DUAL-PORT MIGRATION: empty-list guard ──────────────────────────
    # Without this, an empty List skips the `while idx < n` loop entirely
    # and the function falls through to `wrt(0x03)` at the bottom — making
    # 0x03 the only byte the Z80 ever reads. Z80 interprets 0x03 as the
    # SAVE statement's final status → Report F (Invalid filename).
    #
    # Reproducer: `SAVE "tpi:cd"` (interactive CD) when current path has
    # no subdirectories. dirs = [] → List = [] → 0x03 only → F.
    #
    # Fix: write a proper PRINT_STRING_WITH_LOOP response saying "no
    # items available" and return -1 cleanly. The caller (CDIR/IDIR)
    # treats -1 as "user cancelled" and does nothing further. V6 chain
    # intact.
    # ────────────────────────────────────────────────────────────────────
    if n == 0:
        wrt(FN_PRINT_LOOP)              # 0x86 PRINT STRING WITH LOOP function code
        wrt(1)                          # status: no error
        wrt(0x0D)
        wrt(0x0D)
        codes(BAR)
        for m in ("%-32s" % hdr1)[:32]:
            wrt(m)
        codes(NORMAL_)
        wrt(0x0D)
        for m in "(no items available)":
            wrt(m)
        wrt(LOOP_END)                   # 0x03: end of loop (no scroll, no keypress)
        wrt.send()                      # data in TX first, then READY
        CMD_DRAIN()
        while MQ.rx_fifo() != 0:
            MQ.get()
        return -1

    while idx < n:
        i = 0
        # Write screen

        if Init:
            wrt(FN_PRINT_LOOP)  # 0x86 PRINT STRING WITH LOOP — this IS the D-block status
            wrt(1)      # BASIC return code
            Init = False
        else:
            wrt(ch)     # Show previous choice
        wrt(0x0D)
        wrt(0x0D)
        codes(BAR)
        for m in ("%-32s" % hdr1)[:32]:
            wrt(m)
        pg = "%d of %d" % (idx // nmax + 1, pgs)
        codes(CYAN)
        for m in ("%-24s%8s" % (hdr2, pg))[:32]:
            wrt(m)
        codes(NORMAL_)
        while i < nmax and idx + i < n:
            x = letters[i]
            codes(CYAN)
            wrt(x)
            codes(NORMAL_)
            wrt(0x20)
            if folders:
                codes(INK_ + "\x01")
            for m in List[idx+i]:
                wrt(m)
            if folders:
                codes(INK_ + "\x08")
            wrt(0x0D)
            i += 1
        j = i
        while i < nmax:
            wrt(0x0D)
            i += 1
        a = int(idx * 32 / n + 0.5)
        for k in range(a):
            wrt('-')
        w = int(j * 32 / n + 0.5)
        codes(CYAN)
        for k in range(w):
            wrt('=')
        codes(NORMAL_)
        for k in range(32 - a - w):
            wrt('-')
        wrt(0x0D)
        for m in prompt1:
            wrt(m)
        wrt(x)
        for m in prompt2:
            wrt(m)
            
        wrt(STR_END)    # 0x00: end of this string (Z80 displays + waits for key)
        wrt.send()      # the page into TX, READY, the rest as the Z80 reads it
        # ─── Issue #14: 0x86 bit-6 ack (PIO auto-busy variant) ────────
        # PIO drops Y to 0 automatically when the Z80 writes the
        # keypress (its OUT $0E). MQ.get() returns with us already in
        # BUSY state. Re-assert MQ_READY() before the next wrt for
        # both branches: the navigation paths fall through to the
        # next `while idx < n` iteration which redraws, and the
        # selection path writes the echo + erase bytes.
        # ──────────────────────────────────────────────────────────────
        ch = CMD_KEY()      # BREAK at the prompt raises CmdAbort (#51)
        if ch == 78:    # 'N' then done (ROM ended the loops)
            MQ_READY()  # restore Y for downstream reads
            return -1
        need_ready = True   # READY after the next reply's first byte
        if ch == 66: # B
            if idx >= nmax:
                idx -= nmax
            else:
                idx = 0
        elif ch in LISTMENU_CHOICES:
            j = idx + LISTMENU_CHOICES[ch]
            if j < n:
                wrt(ch)
                # Erase bottom two lines
                for b in range(32):
                    wrt(0x08)
                    wrt(0x20)
                    wrt(0x08)
                wrt(0x0D)
                for b in range(32):
                    wrt(0x08)
                    wrt(0x20)
                    wrt(0x08)
                # Choose it
                sel = j
                break
            else:
                ch = 0x46
        else:
            ch = 0x46
            if idx + i < n:
                idx += i
        # Back to top for next screenful

    if sel >= 0:
        for m in "%s\r%s\r" % (chosen, List[sel]):
            wrt(m)
            
    wrt(LOOP_END)       # 0x03: end string loop
    wrt.send()          # the echo, erase, choice and 0x03; then READY
    # ─── DUAL-PORT MIGRATION: inline tail drains ──────────────────────────
    CMD_DRAIN()
    while MQ.rx_fifo() != 0:
        MQ.get()

    return sel


def PATH(pre, cmd):                                                                             # Show current directory
    
    # SAVE "tpi:path"               - Show current path
    # SAVE "tpi:path"CODE 1,0       - Show current mounted file path

    global TSP
    
    TLM("PATH enter")
    par1, par2 = PARAMS(pre)

    if par1 == 0 and par2 == 0:
        SEND_MSG("Current working dir is: ", public_path(), _1_OK, True)
    elif par1 == 1 and par2 == 0:
        if TSP.f_name:
            SEND_MSG("Current mounted file is: ", public_fname(), _1_OK, True)
        else:
            SEND_MSG("No file mounted!", "", _1_OK, True)
    else:
        msg = BAD_CODE("PATH", par1, par2)
        LOG(msg, 1)
        SEND_MSG(msg, "", _8_A_Invalid_arg)
    
    return
    

def isTapMounted():
    """Check if a .TAP file is currently mounted."""
    global TSP

    return TSP.f_name and TSP.f_name[-4:].lower() == '.tap'


def TAPDIR(pre, cmd):                                                        # Display contents of currently mounted TAP file
    
    # SAVE "tpi:tapdir"             - Show the whole listing (CODE 0,0)
    # SAVE "tpi:tapdir"CODE 0,n     - Show a listing of only n blocks before and
    #                                 after the current position with n=0 to 
    #                                 show all blocks
    # SAVE "tpi:tapdir"CODE 1,n     - Show a listing of n headers before and 
    #                                 after the current position with n=0 to 
    #                                 all headers. If the current position is on
    #                                 a data block, it is also shown.
    # SAVE "tpi:tapdir"CODE x,255   - Show a screenfull around the current pos

    global TSP
    
    TLM("TAPDIR enter")
    par1, par2 = PARAMS(pre)

    if not isTapMounted():

        nom = " --  No .TAP file mounted!  --  "
        LOG("No file mounted in TAPDIR", 1)

    else:

        N = ["File:%-27s" % public_fname(27)]
        N.append("Pointer at block: %02d, Append:" % TSP.tap_idx)
        if TSP.append:
            N.append("on ")
        else:
            N.append("off")
        if par1 == 0:
            # N.appd(" #  Offset   Len  Hdr?   Desc.  ")
            N.append("Blk  Start   Len  Hdr?  Desc.   ")
        elif par1 == 1:
            # N.appd(" #  File         Len  Desc.     ")
            N.append("Blk Type         Len  Name      ")
        else:
            msg = BAD_CODE("TAPDIR", par1, par2)
            LOG(msg, 2)
            SEND_MSG(msg, "", _8_A_Invalid_arg)
            return
        N.append("--------------------------------")

        if not TSP.offset_tbl:

            N.append("%s\r" % "<empty file>")

        else:

            if par2 == 255:
                idx1 = max(0, TSP.tap_idx - 8 * (par1+1))
                idx2 = min(len(TSP.offset_tbl) - 1, idx1 + 17 * (par1+1))
            elif par2 > 0:
                idx1 = max(0, TSP.tap_idx - (par1+1)*par2)
                idx2 = min(len(TSP.offset_tbl) - 1, TSP.tap_idx + (par1+1)*par2)
            else:
                idx1 = 0
                idx2 = len(TSP.offset_tbl) - 1
            idx = 0

            if par1 == 0: # Block listing

                for el in TSP.offset_tbl:

                    if idx >= idx1 and idx <= idx2:
                        if idx == TSP.tap_idx:
                            N.append(">")
                        else:
                            N.append(" ")
                        N.append("%02d %6s  %5s %s  %-10s" % (idx, el[0], el[1], el[2], el[3])) # Index, offset, len, Hdr?, Desc.
                    
                    idx += 1
                
            else: # Header listing

                N.extend(catalog.tap_header_rows(TSP.offset_tbl, TSP.tap_idx, idx1, idx2))
                    
        nom = TAPDIR_COLOUR("".join(N), par1 == 1)

    SEND_MSG2(nom, _1_OK, True, True)

    return


def NEW_TAP(pre, cmd):

    # Create a new empty tap file of the given name and mount it.
    # SAVE "tpi:newtap name"       # 
    # SAVE "tpi:newtap name.tap"   # 

    global TSP
    
    TLM("NEW_TAP enter")
    arg = getArgs(cmd)
    if arg == "":
        msg = "Name required for new .tap file"
        LOG(msg, 1)
        SEND_MSG(msg, "", _3_F_Invalid_file, True)
        return
    # Remove a .tap extension
    jarg = arg.find('.')
    if jarg >= 0 and arg[jarg:].lower() == '.tap':
        filename = "%s" % arg[:jarg]
    else:
        filename = "%s" % arg
    # Make new .tap file name
    filename = filename.strip()
    # Check for invalid chars
    clean_fname = ''.join(l for l in filename if (l >= ' ' and l < chr(127) and (l not in r':*\/|"<>')))
    if clean_fname != filename:
        msg = 'Filename "%s" not allowed' % filename
        LOG(msg, 2)
        SEND_MSG(msg, "", _3_F_Invalid_file)
        return
    filename = "%s/%s.tap" % (TSP.cur_path, clean_fname)

    # Make new empty .tap file -- never over an existing one (FORMAT refuses too)
    def make():
        if file_exists(filename) or dir_exists(filename):
            return "File exists: ", _3_F_Invalid_file
        with open(filename, "w") as newfile:
            pass
        os.chdir(TSP.cur_path)
        DIR_FILES()
        return "", _1_OK

    msg, st = SD_CALL(make)
    if st != _1_OK:
        if msg == "SD card error":
            msg = "Can't create new file: "
        LOG(msg + filename, 1)
        SEND_MSG(msg, "%s.tap" % clean_fname, st)
        return
    LOG("New empty file:%s" % filename, 0)

    if not MOUNT_FILE(filename):
        msg = "Failed to mount new .tap file: "
        LOG(msg + filename, 2)
        st = _4_Q_Parameter
    else:
        # Set append on
        TSP.append = True
        msg = "New .tap file mounted: "
        LOG(msg + filename, 0)
        filename = public_fname()
        st = _1_OK

    # ACTIVATE_MQ()
    SEND_MSG(msg, filename, st)
    return


def SA_NOT_IMP(pre, cmd):                                                      # Output for not implemented SAVE Command 
    
    SEND_MSG("CMD OK, but not yet implemented", "", _5_C_Nonsense)

    return


def dir_exists(filename):                                                                              # Checks whether filename's directory exists or not
    try:
        return (os.stat(filename)[0] & 0x4000) != 0
    except OSError:
        return False
        
        
def file_exists(filename):                                                                             # Checks whether filename exists or not
    try:
        return (os.stat(filename)[0] & 0x4000) == 0
    except OSError:
        return False
    

def xchr(m):
    """A character of a Mac/PC name as the 2068 shows it: '?' for any it
    can't print as itself or type back (catalog.screen_name). | and ~ used
    to become " STICK " / " FREE " -- what the 2068 prints for them, but
    nothing anyone could type into LOAD "tpi:..."."""
    return catalog.screen_name(m)


def xstr(s):
    # Expand or replace chars in string

    return "".join(xchr(m) for m in s)


def public_path(n = 0):
    """
    Return the public version of the current path (without leading '/sd').
    If n is given, shorten to n chars by removing middle characters.
    """

    global TSP
    
    p = "/%s" % xstr(TSP.cur_path[4:])
    if n == 0:
        return p
    else:
        return shorten_filename(p, n)
    

def public_fname(n = 0):
    """
    Return public version of the current filename (without leading '/sd').
    If n is given, shorten to n chars by removing middle characters.
    """
    
    global TSP
    
    if TSP.f_name:
        f = xstr(TSP.f_name[3:])
        if n == 0:
            return f
        else:
            return shorten_filename(f, n)
    else:
        return ""
    
    
def APPEND(pre, cmd):                                                                                  # Start appending each newly SAVEd file to currently mounted TAP

    # Toggle the append mode for a mounted tap file
    # SAVE "tpi:append"         - Display append mode
    # SAVE "tpi:append"CODE 1,0 - Set append mode OFF
    # SAVE "tpi:append"CODE 1,1 - Set append mode ON
    # SAVE "tpi:append off"     - Set append mode OFF
    # SAVE "tpi:append on"      - Set append mode ON

    global TSP
    
    TLM("APPEND enter")
    par1, par2 = PARAMS(pre)
    arg = getArgs(cmd)
    arg = arg.lower()
    st = _1_OK
    msg2 = ""

    if arg != '':
        par1 = 1
        if arg == 'on':
            par2 = 1
        elif arg == 'off':
            par2 = 0
        else:
            msg = BAD_ARG("APPEND", arg)
            par2 = -1

    if par1 == 0 and par2 == 0:
        # Display
        if not isTapMounted():
            msg = "No .tap mounted"
        elif TSP.append:
            msg = "Append is ON"
        else:
            msg = "Append is OFF"

    elif par1 == 1:
        # Set
        if par2 < 0:
            st = _8_A_Invalid_arg
            LOG(msg, 2)
        elif par2 != 0:
            if isTapMounted():
                TSP.append = True
                msg = "Append new files to: "
                msg2 = public_fname()
                LOG(msg + msg2, 0)
            else:
                msg = "No .tap mounted. Append failed."
                LOG(msg, 2)
                st = _4_Q_Parameter
        else:
            TSP.append = False
            msg = "Append is OFF"
            LOG(msg, 0)
    else:
        msg = BAD_CODE("APPEND", par1, par2)
        LOG(msg, 2)
        st = _8_A_Invalid_arg

    SEND_MSG(msg, msg2, st, par1 == 0)
    return 


def BLKRCV(pre, cmd):                                                                                  # 'Internal' command to send block to be written to Flash

    global MQ
    global TSP
    global led

    TLM("BLKRCV enter")
    _BUFSZ = 256
    buf = bytearray(_BUFSZ)
    mv = memoryview(buf)  # Faster indexing than bytearray

    wrt = MQ.put

    status = _1_OK

    # The Z80 erases and writes the DOCK slot as soon as this returns OK.
    # If that slot is the one it boots from, stop here (MEMDOCK normally
    # refused it already): report Q, nothing streamed, nothing erased.
    mem, page = getDock()
    clash = BOOT_SLOT_CLASH(mem, page, TSP.f_name)
    if clash:
        LOG("BLKRCV: %s Command refused" % clash[0], 1)
        SEND_MSG(clash[0], clash[1], _4_Q_Parameter, True)
        return

    # ─── How the stream is read, and the one window where it can hang ──────
    # romupdate.bas / dckupdate.bas run `SAVE "tpi:blkrcv"` (line 280), then
    # PRINT, erase the slot (USR 32800/32600), and only THEN start the write
    # loop (USR 32870/32670). That loop runs with interrupts off and reads
    # port 0Eh blind -- no ready check -- a byte every ~33 us (117 T-states:
    # flash unlock + program, IN A,(0Eh), LD (HL),A, count) until done.
    #
    # So the stream is queued long before anything reads it. If BASIC never
    # gets to the USR -- BREAK during the PRINTs or the erase, or an error --
    # nothing ever reads it, and a plain MQ.put() on the full FIFO blocked
    # for ever: the Pico deaf even to the next command's SYNC, until a power
    # cycle. (2026-09-30 audit; #69 had moved every other output path to
    # CMD_PUT but not this one.)
    #
    # Fix: the first GATE bytes go through CMD_PUT, which waits for room
    # without blocking -- bounded, and raising CmdAbort on a port-0Fh write
    # (BREAK, or the next command's SYNC), so PROCESS_CMD tidies up and the
    # Pico stays alive. Once GATE bytes are in, the Z80 has consumed some of
    # them, i.e. its DI write loop is running and will read to the end on its
    # own; from there it is the same fast MQ.put() stream as always. The
    # per-byte loop is deliberately untouched: it has to keep up with a
    # reader that never waits, and CMD_PUT's extra check on every byte would
    # eat into that 33 us. (A reset in the middle of the write loop still
    # leaves the Pico in put() -- but that also leaves the slot half-written,
    # which needs the user's attention and a power cycle anyway.)
    # ──────────────────────────────────────────────────────────────────────
    GATE = 8                                # > the 4-deep FIFO + the status byte

    def stream(f, total):
        """Send `total` bytes of file f (from its current position)."""
        # By DMA where there is one: the whole image into RAM (a .DCK is 64K;
        # v1.29 has ~180K free), the gate as below, then the rest from RAM by
        # a DMA channel -- no file reads, GCs or USB interrupts can leave the
        # FIFO dry under the Z80's 33 us write loop, which would put 00s in
        # the flash. A Z80 that stops (reset mid-write) or a BREAK / SYNC now
        # ends it too: the loop never pauses once it has started, so 3 s of
        # no reads means it has gone.
        data = None
        if tspico_io._DMA is not None:
            try:
                gc.collect()
                data = bytearray(total)
            except MemoryError:
                data = None
        if data is not None:
            got = f.readinto(data)
            mvd = memoryview(data)[:got]
            # No gate: the channel starts now, seconds before the write loop
            # reads (BASIC prints and erases first), and BREAK / a stall end
            # it. The gate's late start cost ten empty reads -- 00s in the
            # flash (hardware, 2026-10-03). Up to CMD_STALL_MS for the first
            # read (the erase), then 3 s: the write loop never pauses.
            _CMD_ECHO[0] = 0
            r = STREAM_DMA(MQ, mvd, _CMD_ECHO, 3000, False, CMD_STALL_MS)
            if r is not None:
                TLM("BLKRCV streamed by DMA", "why=%d sent=%d of %d echo=%s rx=%d" % (
                    r[0], r[1], got, bytes(_CMD_ECHO).hex(), MQ.rx_fifo()))
                if r[0]:
                    raise CmdAbort(r[0])
                return
            gate = GATE                     # no channel free: the stream below, from RAM
            for i in range(got):
                if gate:
                    CMD_PUT(mvd[i])
                    gate -= 1
                else:
                    wrt(mvd[i])
            return
        gate = GATE
        left = total
        while left > 0:
            n = f.readinto(buf if left >= _BUFSZ else mv[:left])
            if not n:
                break
            i = 0
            while gate and i < n:           # until the Z80 is demonstrably reading
                CMD_PUT(mv[i])
                i += 1
                gate -= 1
            for j in range(i, n):           # the fast path, exactly as before
                wrt(mv[j])
            left -= n

    led.value(1)
    try:
        if TSP.f_name[-4:].upper() == ".DCK":

            # ─── DUAL-PORT MIGRATION: status + MQ_READY (was wrt(0x40); wrt(status)) ──
            wrt(status)
            MQ_READY()

            try:
                with open("/TMP/temp.bin", "rb") as file:
                    stream(file, 65536)     # DCK_IMAGE always writes the full 64K
            except Exception as e:
                print(f"ERROR! {e}")
                return

        elif TSP.f_name[-4:].upper() in [".BIN", ".ROM"]:

            file_len = os.stat("/TMP/temp.bin")[6]
            send_len = file_len

            par1, par2 = PARAMS(pre)

            if ((par1 + par2) > file_len):
                status = _3_F_Invalid_file
                BLINK_ERROR()

            # ─── DUAL-PORT MIGRATION: status + MQ_READY (was wrt(0x40); wrt(status)) ──
            wrt(status)
            MQ_READY()

            if (status == _1_OK):

                rd_offset = par2

                if (par1 != 0):
                    send_len = par1
                else:
                    send_len = file_len - rd_offset

                with open("/TMP/temp.bin", "rb") as file:
                    file.seek(rd_offset)
                    stream(file, send_len)
    finally:
        led.value(0)                        # also on the .DCK path, which used to leave it lit

    return

def ChangeDir(potential_new_path, SDactive = False):

    global TSP
    global MQ

    TLM("ChangeDir enter", "path=%r SDactive=%s" % (potential_new_path, SDactive))
    status = _1_OK
    if not SDactive:
        ACTIVATE_SD()
    global prev_path
    old_path = TSP.cur_path

    if potential_new_path == "-":                                                 # MOVE TO "": back where we were
        if prev_path and dir_exists(prev_path):
            new_path = prev_path
        else:
            new_path = TSP.cur_path
            status = _3_F_Invalid_file

    # ─── ".." below the root is left to catalog.resolve() ──────────────────
    # There used to be a branch here, from before catalog.resolve() existed
    # (#79), that handled ".." by hand: split cur_path on "/", drop the first
    # (empty) element and the last one, and join the rest. Dropping the empty
    # first element also dropped the leading "/", so from /sd/TAP/GAMES it
    # produced "sd/TAP" -- a RELATIVE path. os.chdir("sd/TAP") only lands in
    # the right place when MicroPython's current directory is the VFS root
    # "/", which is true only because DEACTIVATE_SD unmounts /sd between
    # commands; whenever the current directory was inside /sd (e.g. just after
    # SD_REVALIDATE chdir'd there), "cd .." failed with Report Q. This
    # branch ran BEFORE the catalog.resolve() branch below and so hid it,
    # even though resolve() handles ".." correctly and absolutely. Removed
    # by the 2026-09-30 audit; see src/test/audit_fixes_hosttest.py.
    #
    # ".." AT the root is still handled by the next branch: resolve() returns
    # None for a path that would climb above /sd/TAP, and "cd .." at the top
    # has always meant "stay at the top", not an error.
    # ─────────────────────────────────────────────────────────────────────
    elif (potential_new_path == ".." and TSP.cur_path.count("/") == 2) or potential_new_path == "/" or potential_new_path.lower() == "/tap":
        new_path = "/sd/TAP"
        
    elif potential_new_path[0:5].lower() == "/tap/":
        new_path = "/sd" + potential_new_path

    elif catalog.resolve(TSP.cur_path, potential_new_path) and \
            dir_exists(catalog.resolve(TSP.cur_path, potential_new_path)):             # "a/b", "../x", "/games", normalised
        new_path = catalog.resolve(TSP.cur_path, potential_new_path)

    # ─── No raw "cur_path + / + arg" fallback any more ─────────────────────
    # A last branch used to try the plain concatenation
    # "%s/%s" % (TSP.cur_path, arg) -- before #79 that was how any relative
    # name was found. Since catalog.resolve() handles every relative name,
    # the fallback was reached in exactly one case: resolve() had returned
    # None because the path climbs ABOVE /sd/TAP ("cd ../.." from one level
    # down). The fallback then chdir'd to "/sd/TAP/GAMES/../.." and left the
    # card root, which resolve() exists to prevent. Without it, such a path
    # is Report F like any other directory that can't be reached -- the same
    # answer CAT gives for it. Removed by the 2026-09-30 audit.
    # ─────────────────────────────────────────────────────────────────────
    else:
        # no changes bc it doesn't meet any of the tests above
        new_path = TSP.cur_path
        status = _3_F_Invalid_file

    if status == _1_OK:
    
        try:
            os.chdir(new_path)
            TSP.cur_path = os.getcwd()
        except:
            status = _4_Q_Parameter
        
    if status == _1_OK:
        if TSP.cur_path != old_path:
            prev_path = old_path
        message = "Changed dir to: %s" % potential_new_path
        LOG(message, 0)
        DIR_FILES()
        # gc.collect()
    else:
        message = "OS error changing to: %s" % potential_new_path
        LOG(message, 2)
            
    if not SDactive:
        # ─── DUAL-PORT MIGRATION: pair with DEACTIVATE_SD ─────────────────
        DEACTIVATE_SD()
        ACTIVATE_MQ()

    return status, message


def CDIR(pre, cmd):                                                                                            # Changes path to specified DIRectory
    
    # tpi:cd name
    # SAVE "tpi:cd name"            - Change current directory to name (can be . or .. as well)
    # SAVE "tpi:cd name" CODE 1,0   - Change dir and then do a tpi:dir
    # SAVE "tpi:cd name" CODE 1,1   - Change dir and then do a tpi:idir
    # SAVE "tpi:cd name" CODE 1,2   - Change dir and then do a tpi:dir CODE 2,0
    # SAVE "tpi:cd name" CODE 2,0   - Change dir and then display new path
    # SAVE "tpi:cd"                 - Interactive CD
    # SAVE "tpi:cd"CODE 0,1         - Interactive CD but use global dir list

    global lista
    global dirs
    global alldirs
    global led
    
    TLM("CDIR enter")
    status = _1_OK
    par1, par2 = PARAMS(pre)
 
    potential_new_path = getArgs(cmd)

    if potential_new_path == "":

        led.value(1)
        cwd = public_path(27)
        hdr1 = "Path:%s" % cwd
        hdr2 = "  Directory Name"
        hdr3 = "  ------------------------------"
        if par2 == 0:
            if cwd != '/TAP':
                List = ['..'] + dirs
            else:
                List = dirs
        else:
            List = alldirs
        isel = ListMenu(List, hdr1, hdr2, hdr3, "Change to dir", "Changing dir to: ", True)
        if isel >= 0:
            status, message = ChangeDir(List[isel])
        led.value(0)
        return

    status, message = ChangeDir(potential_new_path)

    if status == 1 and par1 == 1 and par2 <= 2:
        if par2 == 0:
            SEND_MSG2(CAT_COLOUR(lista), _1_OK, False, True)
        else:
            pre = 10 * [0]
            if par2 == 1:
                IDIR(pre,cmd)
            else:
                pre[3] = 2
                DIR(pre,cmd)
    else:
        SEND_MSG(message, "Current: %s" % public_path(), status, par1 == 2 and par2 == 0)

    return 


def FWD(pre, cmd):                                                                                     # Moves pointer to next block in TAP file; also can skip
                                                                                                       # 'CODE n,0' # of blocks or 'CODE n,1' files forward
    # SAVE "tpi:ffw"          - Move forward 1 block  (CODE 0,0)
    # SAVE "tpi:ffw" CODE 0,n - Move forward n blocks
    # SAVE "tpi:ffw" CODE 1,n - Move forward n blocks and do "tpi:tapdir"CODE 0,0
    # SAVE "tpi:ffw" CODE 2,n - Move forward n files
    # SAVE "tpi:ffw" CODE 3,n - Move forward n files  and do "tpi:tapdir"CODE 1,0

    global TSP
    
    TLM("FWD enter")
    par1, par2 = PARAMS(pre)
    st = _1_OK
    forth = max(par2,1)
    num_blks = len(TSP.offset_tbl)

    if not isTapMounted():
        msg = "No .tap file mounted"
        LOG(msg, 1)
        forth = 0

    elif TSP.tap_idx >= num_blks - 1:
        msg = "Can't FWD. Already at end."
        forth = 0

    elif par1 <= 1:

        # Move by block
        TSP.tap_idx += forth
        if TSP.tap_idx >= num_blks - 1:
            TSP.tap_idx = max(0, num_blks - 1)

    elif par1 <= 3:

        # Move by file
        i = TSP.tap_idx
        if TSP.offset_tbl[i][2][1] == 'Y':
            l = i
        else:
            l = -1
        i += 1
        h = forth
        while i < num_blks - 1 and h > 0:
            if TSP.offset_tbl[i][2][1] == 'Y':
                h -= 1
                l = i
            i += 1
        if h == 0 or l >= 0:
            i = l
        else:
            i = num_blks - 1
        TSP.tap_idx = i

    else:
        # Invalid option
        msg = BAD_CODE("FFW", par1, par2)
        LOG(msg, 2)
        st = _8_A_Invalid_arg

    if st == _1_OK and forth != 0:
            
        TSP.offset = TSP.offset_tbl[TSP.tap_idx][0]
        gc.collect()
        msg = "Moved ahead to block # %d" % TSP.tap_idx
        LOG(msg, 0)
        if par1 == 1 or par1 == 3:
            # Chain to TAPDIR
            pre = [0] * 10
            pre[5] = 255 # CODE 0,255
            if par1 == 3: # do TAPDIR by file as well
                pre[3] = 1 # CODE 1,255
            TAPDIR(pre, cmd)
            return

    SEND_MSG(msg, "", st)
    
    return 


def getArgs(cmd):

    """Return the string of arguments after the command word and a space."""
    sp = cmd[7:].find(' ')
    if sp >= 0:
        return cmd[sp+8:]
    else:
        return ""


def GETHELP(pre, cmd):                                                 # Shows TS-Pico command help

    # SAVE "tpi:help"            General help
    # SAVE "tpi:help <command>"  Get help on a specific command
    # SAVE "tpi:help ?"          List commands with specific help
    # For help on a specific command, a file with that name in lowercase and a
    # .txt extension needs to be present in the /sd/help folder containing the 
    # text. It can be broken into short lines with CR/LF, LF, or CR line endings.

    global TSP
    global EXT_SA_FUNCT
    
    HELP_DIR = "/sd/help"
    nl = chr(0x0D)
    arg = getArgs(cmd)
    arg = arg.lower()
    st = _1_OK
    lv = 2
    errm = "SD card help folder not found."

    if arg:

        ACTIVATE_SD()

        if not dir_exists(HELP_DIR):

            msg = errm
            st = _4_Q_Parameter

        else:

            if arg == "?":

                # List specific help file names
                listing = sorted(os.ilistdir(HELP_DIR), key=lambda fname: fname[0].lower())
                M = ['Commands for "tpi:help cmd":', nl, nl]
                l = 0
                for name in listing:
                    i = name[0].find('.')
                    if i > 0:
                        e = name[0][i:]
                        if e.lower() == '.txt':
                            hlp = name[0][:i]
                            if l + i + (l>0) > 32:
                                M.append("\r%s" % hlp)
                                l = i
                            elif l == 0:
                                M.append(hlp)
                                l = i
                            else:
                                M.append(" %s" % hlp)
                                l += i + 1
                        else:
                            pass
                    else:
                        pass
                msg = "".join(M)

            else:
        
                # Look for help file
                hname = "%s/%s.txt" % (HELP_DIR, arg)
                if file_exists(hname):
                    try:
                        with open(hname, 'rt') as help:
                            # Written on a Mac/PC: what the 2068 can't print
                            # as itself (| ~ { } ...) shows as '?' -- but keep
                            # line ends and \* (SEND_MSG2's (c)).
                            msg = "".join(c if c in "\r\n" else catalog.screen_name(c)
                                          for c in help.read())
                    except:
                        msg = "Failed to read help file: %s" % hname
                        st = _2_R_Tape_load
                else:
                    msg = 'Help for "%s" not found' % arg
                    st = _3_F_Invalid_file
                    lv = 1 # warning

        # ─── DUAL-PORT MIGRATION: pair with DEACTIVATE_SD ─────────────────
        DEACTIVATE_SD()
        ACTIVATE_MQ()

    else:
        #                  01234567890123456789012345678901
        M     = ['LOAD: mount a file']
        M.append('================================')
        M.append('"tpi:<filename>" Mount by name')
        M.append('"tpi:nnn"        Mount by index')
        M.append('')
        M.append('SAVE commands: [ ]-> optional')
        M.append('================================')
        M.append('"tpi:append"[CODE 1,0/1]')
        M.append('"tpi:append on/off"')
        M.append('"tpi:blkrcv"[CODE len,offset]')
        M.append('"tpi:cd <name>"[CODE 1/2,0]')
        M.append('"tpi:cd"[CODE 0,1]')
        M.append('"tpi:close"')
        M.append('"tpi:dir"[CODE 1/2,index]')
        M.append('"tpi:ffw"[CODE 0/1/2/3,n]')
        M.append('"tpi:help [command]"')
        M.append('"tpi:idir"')
        M.append('"tpi:info"')
        M.append('"tpi:log"[CODE 0,n]')
        M.append('"tpi:log clear"[CODE 255,0]')
        M.append('"tpi:loglevel"[CODE 1,n]')
        M.append('SAVE commands: [ ]-> optional')
        M.append('================================')
        M.append('"tpi:loglevel n"')
        M.append('"tpi:md <folder>"[CODE 1,0]')
        M.append('"tpi:boot"[CODE loc,slot]')
        M.append('"tpi:dock"[CODE loc,slot]')
        M.append('"tpi:dock"[CODE 0,1/2]')
        M.append('"tpi:newtap <name>[.tap]"')
        M.append('"tpi:nop"')
        M.append('"tpi:path"[CODE 1,0]')
        M.append('"tpi:rew"[CODE 0/1/2/3,n]')
        M.append('"tpi:rm <name>"[CODE 255,0]')
        M.append('"tpi:tapdir"[CODE 0/1,n]')
        M.append('"tpi:tape"    <=>   "tpi:sdcard"')
        M.append('"tpi:ts2040"  <=>   "tpi:picopt"')
        M.append('"tpi:verbose"[CODE 1,0/1]')
        M.append('"tpi:verbose on/off"')
        M.append('"tpi:zx48"[CODE 0/1,0/1/2/n]')
        M.append('SAVE commands: [ ]-> optional')
        M.append('================================')
        M.append('"tpi:copy <from> <to>"')
        M.append('"tpi:erase <name or pattern>"')
        M.append('"tpi:format <name.tap or dir/>"')
        M.append('"tpi:ren <old> <new>"')
        M.append('"tpi:opprint"  "tpi:clprint"')
        M.append('"tpi:autolf"   "tpi:noautolf"')
        M.append('"tpi:autopg"   "tpi:noautopg"')
        M.append('"tpi:prnsz"[CODE cols,lines]')
        M.append('"tpi:bmp"[CODE width,height]')
        M.append('')
        M.append('"tpi:help ?" to list help topics')
        M.append('from /help folder on the SD card')
        if EXT_SA_FUNCT:
            M.append('')
            M.append('')
            M.append('External commands loaded are:')
            for e in EXT_SA_FUNCT:
                M.append('  "%s"' % e)
            M.append('')
        msg = chr(13).join(M)
        
    if st != _1_OK:
        LOG(msg, lv)
    SEND_MSG2(msg, st, False)

    return


def BUILD_FIT(s, n):                                                          # "abc1234 (long-branch-name)" in n chars

    """The build stamp in n characters: the commit always, the branch cut
    with ".." when the whole won't fit. ("~" would print as FREE.)"""

    if len(s) <= n or not s.endswith(")") or " (" not in s:
        return s[:n]
    commit, branch = s[:-1].split(" (", 1)
    room = n - len(commit) - 5                                                # " (" + ".." + ")"
    if room < 1:
        return commit[:n]
    return "%s (%s..)" % (commit, branch[:room])


def GETINFO(pre, cmd):                                                 # Shows TS-Pico internal status

    global TSP
    global files
    global lista
    
    cop = chr(127)
    nl = chr(13)

    # Report the card as it is now, not as the last command left it: a card
    # taken out since then would still show. One mount (~0.2 s; a card that
    # has just been pulled costs the 5 tries once). A different card is read
    # afresh on the way, so the space line below is the new card's.
    SD_PROBE()

    fl_block = os.statvfs("")[0]
    fl_tot = os.statvfs("")[2]
    fl_free = os.statvfs("")[3]

    fl_free = fl_free * fl_block
    fl_tot = fl_tot * fl_block
    
    # The screen (chosen 2026-10-02 from the colour proposals): a cyan
    # " TS-Pico " badge on a blue strip, labels in blue, values in the
    # screen's own colours. With no SD card the strip and the card's "none"
    # turn red; nothing mounted is normal, not a warning. Colour codes: see
    # SEND_MSG2's `colour`.
    missing = not TSP.sd_present                                       # a TAP not mounted isn't an error
    bar = PAPER_ + "\x05" + INK_ + "\x09" + " TS-Pico " + PAPER_ + ("\x02" if missing else "\x01") + INK_ + "\x07"
    lab = lambda t: INK_ + "\x01" + "%-10s" % t + INK_ + "\x08"
    warn = INK_ + "\x02" + "none" + INK_ + "\x08"
    M     = [bar + "%-23s" % " interface status"]                  # 9 + 23: SEND_MSG2 ends the line
    M.append(NORMAL_ + INK_ + "\x01" + " %s 2023-2026 TS Pico Dev Team" % cop + INK_ + "\x08" + nl + nl)
    M.append(lab("Firmware") + "%-6s" % TSP.FW_VERSION + INK_ + "\x01" + "uPython " + INK_ + "\x08"
             + ".".join(str(v) for v in sys.implementation.version[:3]) + nl)
    M.append(lab("ROM") + "%s" % TSP.ROM_VERSION + nl)
    M.append(lab("Build") + BUILD_FIT(BUILD_VERSION, 22) + nl)        # 10 + 22: the 32-col line
    M.append(lab("Board") + "V2.2  " + INK_ + "\x01" + "Log level " + INK_ + "\x08" + "%d" % TSP.LOG_LEVEL + nl)
    M.append(lab("Free RAM") + "%d kB" % (gc.mem_free() >> 10) + nl)
    M.append(lab("Flash") + "%s, %s free" % catalog.space_pair(fl_tot, fl_free) + nl)
    if TSP.sd_present and sd_space:
        M.append(lab("SD card") + "%s, %s free" % catalog.space_pair(*sd_space) + nl)
    else:
        M.append(lab("SD card") + warn + nl)
    mem, page = getBoot()
    M.append(lab("Boot") + "%-6s" % ("%d,%d" % (mem, page)))
    mem, page = getDock()
    M.append(INK_ + "\x01" + "Dock " + INK_ + "\x08" + "%d,%d" % (mem, page) + nl)
    M.append(lab("Append") + "%-6s" % ("on" if TSP.append else "off")
             + INK_ + "\x01" + "Verbose " + INK_ + "\x08" + ("on" if TSP.VERBOSE else "off") + nl)

    if not TSP.f_name:
        M.append(lab("Mounted") + "none" + nl)
    else:
        M.append(lab("Mounted") + "%s" % public_fname() + nl)
        if isTapMounted():
            i = TSP.tap_idx
            val = "%02d" % i
            # A header is shown with the size of the data block after it,
            # offset_tbl[i+1]. A TAP can END with a header -- an append cut
            # short, or a header-only file -- and offset_tbl[i+1] then raised
            # IndexError, so tpi:info gave Report J instead of the status.
            # (2026-09-30 audit.) The tap_idx bound is belt and braces.
            if 0 <= i < len(TSP.offset_tbl):
                blk = TSP.offset_tbl[i]
                # One line of 22 after the label: the name came padded to 10,
                # and with "Code block" after it the line was 34 characters,
                # wrapping "ck" onto a line of its own (found in the emulator,
                # tools/emu, 2026-10-04). The name gives way, not the type.
                if blk[2] == " Y":
                    nxt = TSP.offset_tbl[i+1][3] if i + 1 < len(TSP.offset_tbl) else "no data"
                    what = blk[3].rstrip()
                else:
                    nxt = blk[3]
                    what = "Data block" if len(nxt) <= 7 else "Data"
                val += ":%s:%s" % (what[:max(1, 22 - len(val) - 2 - len(nxt))], nxt)
            else:
                val += ":<empty>"
            M.append(lab("Block") + val[:22] + nl)

    M.append(lab("Path") + "%s" % public_path() + nl)
    M.append(lab("Files") + "%d" % len(files) + nl)
    msg = "".join(M)
    SEND_MSG2(msg, _1_OK, True, True)

    return


def GETLOG(pre, cmd):                                                 # Shows the last nn bytes of the events log file 

    # SAVE "tpi:log"
    # SAVE "tpi:log"CODE 0,n     - Show n bytes of the end of the file
    # SAVE "tpi:log clear"       - Clear the log file (with prompt)
    # SAVE "tpi:log clear"CODE 255,0 - Clear the log file (no prompt)

    global TSP
    global led
    
    status = _1_OK
    par1, par2 = PARAMS(pre)
    arg = getArgs(cmd)

    if arg != '':

        if arg.lower() == 'clear':
            sent = False
            if par1 != 255 or par2 != 0:
                sent = True
                ch = SEND_MSG_PROMPT_YN('Clear the log file (y/N)?')
                if ch != 89: # 89='Y'
                    LOG("Log file not cleared", 0)
                    return
            if CLEAR_LOG():
                msg = "Log file was cleared"
                if not sent:
                    SEND_MSG(msg, "", _1_OK)
                return
            else:
                msg = "Couldn't clear log file"
                status = _4_Q_Parameter

        else:
            par1 = -1

    if par1 < 0:
        msg = BAD_ARG("LOG", arg)
        status = _8_A_Invalid_arg

    elif par1 != 0:
        msg = BAD_CODE("LOG", par1, par2)
        status = _8_A_Invalid_arg

    if status != _1_OK:
        LOG(msg, 2)
        SEND_MSG(msg, "", status)
        return
    
    led.value(1)

    log_fname = "/activity.log"
    file_seek = 0
    
    len_cmd = par2
    len_file = os.stat(log_fname)[6]
    
    if len_cmd != 0 and (len_cmd <= len_file):
        len_read = len_cmd
        file_seek = len_file - len_cmd
    else:    
        len_read = len_file

    # ─── Read first, then show -- and only the read is guarded ────────────
    # The whole requested part of the log is read into one buffer, and the
    # log is only trimmed to 64 KB at boot, so it can outgrow the heap during
    # a long session. Ryan wrapped this in a try/except for exactly that
    # ("in case the file is too large to allocate the buffer").
    #
    # That `except:` was bare, and SEND_MSG2 sat inside the try. Since #51,
    # BREAK at SEND_MSG2's "Scroll?" prompt raises CmdAbort -- deliberately a
    # BaseException, so that a handler's `except Exception:` can NOT swallow
    # it; PROCESS_CMD must see it to stop talking to a Z80 that has left the
    # command. A bare `except:` catches BaseException too, so GETLOG ate the
    # BREAK and then sent "Log file too large" to a 2068 that had stopped
    # listening. Found by the 2026-09-30 audit; see audit_fixes_hosttest.py.
    #
    # Now the try covers only reading the file (MemoryError for a log too big
    # to hold; OSError or a decode error for a damaged one), catches only
    # Exception, and SEND_MSG2 runs outside it, so CmdAbort propagates. The
    # finally turns the LED off on every path, including a BREAK.
    # ─────────────────────────────────────────────────────────────────────
    try:
        try:
            buf = bytearray(len_read)
            with open(log_fname, "r") as logfile:
                if file_seek:
                    logfile.seek(file_seek)
                logfile.readinto(buf)
            text = buf.decode('utf-8')                                # Convert bytes to string
        except MemoryError:
            text = None
            msg = "Log file too large"
        except Exception as e:                                        # OSError, UnicodeError: a damaged log
            text = None
            msg = "Couldn't read the log file"
            LOG("GETLOG: %s" % e, 2)
        buf = None                                                    # free it before SEND_MSG2 builds its output

        if text is None:
            LOG(msg, 2)
            SEND_MSG(msg, "", _4_Q_Parameter)
        else:
            SEND_MSG2(text, 1)                                        # CmdAbort (BREAK) passes straight through
    finally:
        led.value(0)

    return


def LOAD_CONFIG():

    TLM("LOAD_CONFIG enter", "build=" + BUILD_VERSION)
    init_values = {}
    defaulted = False
    
    try:
        with open("config.ini", "r") as f:                      # We first try to load config values from config.ini file
            init_values = json.load(f)
    except:                                                     # If fails, we load default hard-wired values
        LOG("Failed to load initial values from config.ini. Using default values instead", 1)

    # Define default values
    # NOTE: The problem is that the class also has default values.
    # We should have only one place for them. Perhaps a static method could 
    # return the default_values dictionary which could be passed into 
    # LOAD_CONFIG. The class constructor could do what this does to add any 
    # missing items from default_values.

    default_values = {}
    default_values["DCK_SLOT"] = 0                             # Slot in Flash for DCK image at startup
    default_values["ROM_SLOT"] = 1                             # Slot in Flash for ROM image at startup
    default_values["ROM_SM"] = 10                              # Flash/SRAM activation pattern bitmap for DCK access (MSB=10) and ROM access (LSB=10)
    default_values["LOG_LEVEL"] = 2                            # Only log errors and up
    default_values["VERBOSE"] = False                          # Disable verbosity on commands
    default_values["ZX_TAPE_COMPAT"] = False                   # Use regular tape load routine in zx48 mode
    default_values["TELEMETRY"] = False                        # TLM over USB serial (main.py reads it; developers set true)
    default_values["FW_VERSION"] = FW_VERSION
    default_values["ROM_VERSION"] = FW_VERSION                 # the ROM this firmware ships with
    # Fill any missing values with the default
    for key, value in default_values.items():
        if key not in init_values:
            init_values[key] = default_values[key]
            defaulted = True
        
    # ─── ROM_SM: only the four combinations tpi:boot / tpi:dock can set ────
    # ROM_SM = dock MEM * 4 + boot MEM, and both commands accept MEM 1 (SRAM)
    # or 2 (flash) only -- MEM 3 was refused by #91 -- so the valid values are
    # 5, 6, 9 and 10. The old test (<= 4, or 8 or 12) let through 7, 11, 13,
    # 14, 15 and anything over 15, and they were used for the current boot.
    # A value that isn't a number at all (e.g. "10" in quotes, from a
    # hand-edited config.ini) made the `<=` raise TypeError and stopped the
    # boot. `in` never raises, so anything else now falls back to the
    # default. (2026-09-30 audit.)
    # ─────────────────────────────────────────────────────────────────────
    if init_values["ROM_SM"] not in (5, 6, 9, 10):
        LOG("Incorrect initial ROM_SM value %r. Using default value of %d instead"
            % (init_values["ROM_SM"], default_values["ROM_SM"]), 2)
        init_values["ROM_SM"] = default_values["ROM_SM"]
        defaulted = True                                                # write the good value back

    return_ROM_SLOT = -1
    boot_mem = init_values["ROM_SM"] & 3                                # tpi:boot's MEM: 1 SRAM, 2 flash (the default)
    if init_values["ROM_SLOT"] != default_values["ROM_SLOT"] or boot_mem != 2:
                                                                        # If we started with a non-default boot slot, we use it on this run,
                                                                        # but reverse back to default hard-wired flash slot 1 for next boot
        return_ROM_SLOT = init_values["ROM_SLOT"]
        return_ROM_SM = init_values["ROM_SM"]
        init_values["ROM_SLOT"] = default_values["ROM_SLOT"]
        init_values["ROM_SM"] = (init_values["ROM_SM"] & 12) + 2
        defaulted = True

    if defaulted: # Save config
        try:
            with open("config.ini", "w") as f:
                json.dump(init_values, f)
        except:
            LOG("while updating config.ini!", 2)
            SAVE_LOG()
        
        if return_ROM_SLOT >= 0:
            init_values["ROM_SLOT"] = return_ROM_SLOT
            init_values["ROM_SM"] = return_ROM_SM
            
    SAVE_LOG()
    
    return init_values            


def LOGLEVEL(pre, cmd):

    TLM("LOGLEVEL enter")
    """Display or set the log level"""
    # SAVE "tpi:loglevel"           - Report log level (CODE 0,0)
    # SAVE "tpi:loglevel"CODE 1,n   - Set log level to n (n>=0)
    # SAVE "tpi:loglevel n"         - Set log level to n (n>=0)

    global TSP

    status = _1_OK
    viz = False
    par1, par2 = PARAMS(pre)
    arg = getArgs(cmd)
    arg = arg.lower()

    if arg != '':
        par1 = 1
        l = -1
        try:
            l = int(arg)
            par2 = l
        except:
            par2 = -1

    if par1 == 0:
        # Report current level
        if TSP.LOG_LEVEL <= 4:
            lbl = LOG_LABELS[TSP.LOG_LEVEL]
        else:
            lbl = ""
        msg = "LOG level is %d %s" % (TSP.LOG_LEVEL, lbl)
        viz = True
        
    elif par1 == 1:
        # Set level
        if par2 < 0:
            msg = BAD_ARG("LOGLEVEL", arg)
            status = _8_A_Invalid_arg
            LOG(msg, 2)
        elif par2 > 4:
            msg = "Bad log level: %d" % par2
            status = _8_A_Invalid_arg
            LOG(msg, 2)
        else:
            TSP.LOG_LEVEL = par2
            lbl = LOG_LABELS[TSP.LOG_LEVEL]
            msg = "LOG level set to %d %s" % (TSP.LOG_LEVEL, lbl)
            LOG(msg, 0)
    else:
        msg = BAD_CODE("LOGLEVEL", par1, par2)
        LOG(msg, 2)
        status = _8_A_Invalid_arg

    SEND_MSG(msg, "", status, viz)

    return 


def MDIR(pre, cmd):                                                                                         # MAKE DIRectory in the current path                         
    
    # Make a new directory
    # SAVE "tpi:md <name>"              - Create a directory
    # SAVE "tpi:md <name>" CODE 1,0     - Also change to the new directory

    global TSP
    global alldirs
    
    TLM("MDIR enter")
    name = cmd[10:]
    message = "Created dir: "
    status = _1_OK
    par1, par2 = PARAMS(pre)
    
    if not name:
        status = _8_A_Invalid_arg
        message = "MD: Filename required"
        LOG(message, 2)
    else:
        ACTIVATE_SD()
        os.chdir(TSP.cur_path)

        if dir_exists(name):
            message = 'MD: directory "%s" exists' % name
            LOG(message, 2)
            status = _7_8_EOF
        elif file_exists(name):
            message = 'MD: file "%s" exists' % name
            LOG(message,2)
            status = _3_F_Invalid_file
        else:
            try:
                os.mkdir(name)
                if par1 != 1 or par2 != 0:
                    DIR_FILES() # Update local dir list
                # Update alldirs w/o calling GET_DIRS()
                try:
                    alldirs.append("%s/%s" % (TSP.cur_path[3:], name))
                    alldirs.sort()
                    gc.collect()
                except:
                    pass

            except OSError:

                message = "MD: OS error creating: "
                LOG(message + name, 2)
                status = _4_Q_Parameter

        # ─── DUAL-PORT MIGRATION: pair with DEACTIVATE_SD ─────────────────
        DEACTIVATE_SD()
        ACTIVATE_MQ()

    if (status == _1_OK or status == _7_8_EOF) and par1 == 1 and par2 == 0:
        # Change to new DIR with show path option
        pre = [0] * 10
        pre[3] = 2 # CODE 2,0
        CDIR(pre, cmd)
    else:
        SEND_MSG(message, name, status)
            
    return 
                

def MEMBOOT(pre, cmd):                                           # Changes ROM slot to boot from; either SRAM or Flash
    
    # SAVE "tpi:boot"                # Report the boot setting
    # SAVE "tpi:boot"CODE mem,slot   # Set boot to mem,slot

    global TSP
    
    global BANK
    global ROM
    
    TLM("MEMBOOT enter")
    par1, par2 = PARAMS(pre)
    new = "MEM=%d, PAGE=%d" % (par1, par2)
    
    if par1 == 0 and par2 == 0:
        # Report setting
        mem, page = getBoot()
        SEND_MSG("BOOT is MEM=%d, PAGE=%d" % (mem, page), "", _1_OK, True)

    elif (par1 == 0 or par1 > 2 or par2 > 15):
        msg = "Wrong values, %s" % new
        SEND_MSG(msg, "OK values: MEM=1..2, PAGE=0..15", _8_A_Invalid_arg)
        LOG("BOOT: %s. Command ignored" % msg, 1) 
    else:            
        val1 = TSP.ROM_SM & 12
        TSP.ROM_SM = val1 + par1
        
        val1 = TSP.bank_sm & 240
        TSP.bank_sm = val1 + par2
        
        with open("config.ini", "r") as f:                                                    # As sometimes this change can hang the machine,
            init_values = json.load(f)                                                        # we modify the init values for next startup
                                                                                              # so changes will take effect next reboot
        init_values["ROM_SLOT"] = par2                                                        # both halves of the boot setting: LOAD_CONFIG
        init_values["ROM_SM"] = (init_values.get("ROM_SM", 10) & 12) + par1                   # uses them once, then puts back flash slot 1
        
        with open("config.ini", "w") as f:
            json.dump(init_values, f)
            
        msg = 'Change ROM to %s' % new
        SEND_MSG(msg, "", _1_OK)
        LOG(msg, 0)
        
        # Kept (audit §4): the ROM is switched under the running 2068 right
        # here, and SEND_MSG has only waited for TX to empty -- the Z80 is
        # still finishing the statement in the old ROM. 0.1 s is cheap next
        # to a crash, and nothing measured says it can go.
        utime.sleep(.100)
        
        ROM.put(TSP.ROM_SM)
        BANK.put(TSP.bank_sm)
        
#         WAIT_TX_RECEIVED()

    return 


def getBoot():
    """Get current boot memory and page settings."""
    global TSP

    val1 = TSP.ROM_SM & 12
    mem = TSP.ROM_SM - val1
    val1 = TSP.bank_sm & 240
    page = TSP.bank_sm - val1
    return mem, page


def getDock():
    """Get current dock memory and page settings."""
    global TSP

    val1 = TSP.ROM_SM & 3
    mem = (TSP.ROM_SM - val1) // 4
    val1 = TSP.bank_sm & 15
    page = (TSP.bank_sm - val1) // 16
    return mem, page


def BOOT_SLOT_CLASH(mem, page, f_name):
    """Would the ROM updater, writing f_name through DOCK mem,page, overwrite
    the slot the 2068 is running from? Returns the refusal (msg, msg1), or None.

    romupdate/dckupdate erase and write the DOCK slot from Z80 code; if that is
    the boot slot, the ROM vanishes under the running Z80 and both machines hang
    with the slot half-written. A .ROM/.BIN writes page `page`; a 64K .DCK
    writes `page` and `page`+1."""

    if not isinstance(f_name, str):         # nothing mounted: TSP.f_name is []
        return None                         # (MEMDOCK raised here -> Report J)
    ext = f_name[-4:].upper()
    if ext not in (".ROM", ".BIN", ".DCK"):
        return None
    bmem, bpage = getBoot()
    if mem != bmem:
        return None
    if bpage != page and not (ext == ".DCK" and bpage == page + 1):
        return None
    return ("Can't write %s slot %d:" % ("SRAM" if mem == 1 else "Flash", bpage),
            "the 2068 is running from it." + chr(13) + "Boot another slot first.")


def MEMDOCK(pre, cmd):                                                  # Changes DCK slot; either SRAM or Flash

    # SAVE "tpi:dock" CODE 0,0   - Display setting
    # SAVE "tpi:dock" CODE 0,1   - Display previous setting
    # SAVE "tpi:dock" CODE 0,2   - Swap to previous setting
    # SAVE "tpi:dock" CODE 1,m   - Assign SRAM page m to dock
    # SAVE "tpi:dock" CODE 2,m   - Assign flash page m to dock

    global TSP
    global BANK
    global ROM
    
    TLM("MEMDOCK enter")
    par1, par2 = PARAMS(pre)
    mem,  page = getDock()
    old = "MEM=%d, PAGE=%d" % (mem, page)
    new = "MEM=%d, PAGE=%d" % (par1, par2)

    if (par1 > 2 or par2 > 15):
        msg = "Wrong values, %s" % new
        SEND_MSG(msg, "OK values: MEM=1..2, PAGE=0..15", _8_A_Invalid_arg)
        LOG("DOCK: %s. Command ignored" % new, 1) 
    
    elif par1 == 0 and par2 == 0:
        # Report setting
        SEND_MSG("DOCK is %s" % old, "", _1_OK, True)

    elif par1 == 0 and par2 == 1:
        # Report previous setting
        mem  = TSP.dck_prev_mem
        page = TSP.dck_prev_slot
        SEND_MSG("DOCK was previously:", "  MEM=%d, PAGE=%d" % (mem, page), _1_OK, True)

    else:
        if par1 == 0:
            if par2 == 2:
                # Swap to previous setting
                par1 = TSP.dck_prev_mem
                par2 = TSP.dck_prev_slot
                msg2 = "Swapped with previous setting"
            else:
                msg = BAD_CODE("DOCK", par1, par2)
                LOG(msg, 2)
                SEND_MSG(msg, "", _8_A_Invalid_arg)
                return
        else:
            msg2 = ""

        # With a .ROM/.DCK mounted this is romupdate/dckupdate picking the
        # slot it is about to erase: refuse the booted one here, before the
        # DOCK moves. (BLKRCV checks again; plain DOCK use is unaffected.)
        clash = BOOT_SLOT_CLASH(par1, par2, TSP.f_name)
        if clash:
            LOG("DOCK: %s Command refused" % clash[0], 1)
            SEND_MSG(clash[0], clash[1], _4_Q_Parameter, True)
            return

        TSP.dck_prev_mem  = mem
        TSP.dck_prev_slot = page
        val1 = TSP.ROM_SM & 3
        TSP.ROM_SM = val1 + (par1 * 4)
        val1 = TSP.bank_sm & 15
        TSP.bank_sm = val1 + (par2 * 16)

        msg = "Change DOCK to %s" % new
        SEND_MSG(msg, msg2, _1_OK)
        LOG("%s. %s" % (msg, msg2), 0)
        
        ROM.put(TSP.ROM_SM)
        BANK.put(TSP.bank_sm)
        
    return 


def REMOVE_DIR(d):                                                        # Recursively remove a directory and all its contents
    
    try:
        if dir_exists(d):
            for f in os.ilistdir(d):
                if f[0] not in ('.', '..'):
                    REMOVE_DIR("/".join((d, f[0])))  # File or Dir
            os.rmdir(d)
        else:  # File
            os.remove(d)
        
    except:
        LOG("Could not remove directory %s" % d, 1)
        
    return


def REW(pre, cmd):                                                                                           # Moves pointer to previous block in TAP file; also 
                                                                                                             # can skip 'CODE n' # of blocks backwards
    # SAVE "tpi:rew"         - Rewind 1 block (CODE 0,0)
    # SAVE "tpi:rew"CODE 0,n - Rewind by n blocks
    # SAVE "tpi:rew"CODE 1,n - Rewind n blocks and do "tpi:tapdir"CODE 0,0
    # SAVE "tpi:rew"CODE 2,n - Rewind by n files
    # SAVE "tpi:rew"CODE 3,n - Rewind n files  and do "tpi:tapdir"CODE 1,0

    global TSP
    
    TLM("REW enter")
    par1, par2 = PARAMS(pre)
    back = max(par2,1)
    st = _1_OK

    if not isTapMounted():
        msg = "No .tap file mounted"
        LOG(msg, 1)
        back = 0

    elif TSP.tap_idx == 0:
        msg = "Can't REW. Already at start."
        back = 0

    elif par1 <= 1:

        # Move by block
        TSP.tap_idx -= back
        if TSP.tap_idx < 0:
            TSP.tap_idx = 0

    elif par1 <= 3:

        # Move by file

        i = TSP.tap_idx
        if TSP.offset_tbl[i][2][1] == 'Y':
            l = i
        else:
            l = -1
        i -= 1
        h = back
        while i >= 0 and h > 0:
            if TSP.offset_tbl[i][2][1] == 'Y': # block i is a header
                l = i # Mark as last seen header
                h -= 1 # Dec header count
            i -= 1 # dec block count
        if h == 0 or l >= 0:
            i = l
        else:
            i = 0
        TSP.tap_idx = i

    else:
        # Invalid
        msg = BAD_CODE("REW", par1, par2)
        LOG(msg, 1)
        st = _8_A_Invalid_arg

    if st == _1_OK and back != 0:
            
        TSP.offset = TSP.offset_tbl[TSP.tap_idx][0]
        gc.collect()
        msg = "Moved back to block # %d" % TSP.tap_idx 
        LOG(msg, 0)
        if par1 == 1 or par1 == 3:
            # Chain to TAPDIR
            pre = [0] * 10
            pre[5] = 255 # CODE 0,255
            if par1 == 3: # do TAPDIR by file as well
                pre[3] = 1 # CODE 1,255
            TAPDIR(pre, cmd)
            return
    
    SEND_MSG(msg, "", st)

    return

    
def ResolveIndexName(name):

    # name, found = ResolveIndexName(name)
    # If name is a file index reference, a number within the range of files, 
    # then resolve it to the actual name. If the name is not an index, the index
    # is not found, or the file is not found, the given name is returned as-is.

    global TSP
    global files

    # `0 <= index`: Python indexes from the end with a negative number, so
    # LOAD "tpi:-1" used to mount the LAST file in the folder (files[-1])
    # instead of saying there's no such file. (2026-09-30 audit.)
    try:
        index = int(name)
        if 0 <= index < len(files):
            return files[index], index
    except ValueError:
        pass

    return name, -1


def LOAD_TPI(name, only_tap=False, fresh=False):
    """LOAD "tpi:<name>": mount a file from the current folder. Returns
    (msg, name, status) for SEND_MSG -- or, in ZX48 mode, ZX_TPI.

    name is a file name (any case), a number from the listing, or
    dirinfo.tap. only_tap (ZX48 mode) refuses anything but a .tap: .ROM,
    .DCK and .BIN mount a TS-2068 updater program instead.
    """
    if name == "dirinfo.tap":
        if MOUNT_FILE("%s/dirinfo.tap" % TSP.cur_path):
            return "Mounting dir info: ", name, _1_OK
        msg = "Error mounting file: "
        LOG(msg + name, 2)
        return msg, name, _2_R_Tape_load

    name, idx = ResolveIndexName(name)
    if idx < 0 and name.upper() in files_upper:                                 # Is name a valid file?
        idx = files_upper.index(name.upper())
    if idx < 0 and catalog.has_wild(name):
        # The name as CAT showed it: '?' for a character the 2068 can't type
        # (catalog.screen_name), '*' for any run. Exactly one match mounts
        # it; several say so and point at the number.
        hits = [i for i, f in enumerate(files) if catalog.match_shown(f, name)]
        if len(hits) == 1:
            idx = hits[0]
        elif hits:
            msg = "%d files match: " % len(hits)
            LOG(msg + name, 1)
            return msg, name + chr(13) + 'Use LOAD "tpi:" with its number.', _3_F_Invalid_file
    if idx < 0 and not fresh:
        # Not in the listing: the folder may have changed on the card since
        # (LISTING_FRESHEN). Look once more before saying it isn't there.
        LISTING_CHECK()
        return LOAD_TPI(name, only_tap, True)
    if idx < 0:
        msg = "File does not exist: "
        LOG(msg + name, 2)
        return msg, name, _3_F_Invalid_file                                     # If none of the above, raise error
    if only_tap and files[idx][-4:].upper() != ".TAP":
        return "Only .tap files in ZX48 mode: ", files[idx], _4_Q_Parameter
    if MOUNT_FILE("%s/%s" % (TSP.cur_path, files[idx])):
        return "File mounted OK", name, _1_OK
    return "Error mounting file:", name, _4_Q_Parameter


def SEND_MSG_PROMPT_YN(prompt, echo = True, lower = False):

    # Prints prompt string, waits for a character and returns that char
    # Assumes MQ is active. This cannot be followed by another SEND_MSG* call.
    # lower=True: on the lower screen (response function 0x88), so the prompt
    # doesn't write over the picture. ONLY the fdd ROM has 0x88 -- pass it only
    # for a command that ROM sent (tpi:fopen). Keep such a prompt to one line.

    global MQ

    # ─── DUAL-PORT MIGRATION ──────────────────────────────────────────────
    # Removed: leading EMPTY_RX_FIFO(); three wrt(0x40) calls ("Read
    # continue", "Read continue to get char", "Start a new string");
    # and replaced WAIT_TX_RECEIVED() / EMPTY_RX_FIFO() at the tail
    # with inline drains.
    #
    # All three wrt(0x40)s were single-port "continue flag in TX" writes
    # that have no place in dual-port — the continue flag lives on $0F
    # via the Y register. A 0x40 left in TX would be consumed as data
    # by Z80's $0E read, orphaning the rest of the response.
    #
    # The EMPTY_RX_FIFO moved BELOW MQ_READY: at the original position
    # the Z80 hadn't been told to read yet, so RX had nothing to drain.
    # After MQ_READY the Z80 may dump stale keystrokes; we drain those.
    # ─────────────────────────────────────────────────────────────────────
    wrt = CmdOut()    # each page built in RAM, sent by CMD_SEND (DMA); BREAK raises CmdAbort
    wrt(FN_PRINT_LOOP_LOWER if lower else FN_PRINT_LOOP)   # 0x88 / 0x86 PRINT STRING WITH LOOP (0x88: lower screen) -- this IS the D-block status
    wrt(0x01)   # BASIC return code
    if not lower:
        wrt(0x0D)   # Start a new line (the lower screen starts clear)

    CMD_RX_FLUSH()              # stray keystrokes (a BREAK among them raises CmdAbort)

    for ch in prompt:
        wrt(ch)
    wrt(STR_END)        # 0x00: end string (Z80 prints + waits for key)
    wrt.send()  # into TX, READY, the rest as the Z80 reads it
    # ─── Issue #14: 0x86 bit-6 ack (PIO auto-busy variant) ───────────────
    # PIO drops Y to 0 automatically on the Z80's keypress OUT, so by
    # the time MQ.get() returns we're already BUSY. Re-assert MQ_READY()
    # before pushing the echo + 0x03 so the Z80's wait_bit6 exits with
    # real bytes ready to read.
    # ──────────────────────────────────────────────────────────────────────

    ch = CMD_KEY()      # BREAK at the prompt raises CmdAbort (#51)
    if ch == 78: # 'N' causes the ROM to end the string loop and any exchange
        MQ_READY()      # nothing more to send; restore Y for downstream reads
    else:
        # The echo and 0x03 first, THEN READY -- data in TX first, then READY: the Z80 reads TX the moment it sees
        # READY, and an empty TX reads as 00. The slow MQ.exec() used to hide
        # READY-before-data here (READY landed ~9.6 ms late); with MQX the
        # 2068 read 00 and Commander crashed on tpi:cd (hardware, 2026-09-27).
        if echo:
            if ch < 32 or ch > 127:
                wrt(89) # Y
            else:
                wrt(ch)
        if lower:
            wrt(0x0D)   # what the ROM prints next ("Start tape...") starts on its own line
        wrt(LOOP_END)   # 0x03: end the string loop
        wrt.send()      # echo and 0x03 in TX, then READY
        # Could add an option to not wrt(0x03) and let the caller do that after
        # writing some more text to indicate the result of the action.

        # ─── DUAL-PORT MIGRATION: inline drains ───────────────────────
        CMD_DRAIN()
        while MQ.rx_fifo() != 0:
            MQ.get()

    return ch

def BAD_CODE(command, par1, par2):
    """Return error message for invalid CODE parameters."""
    return "%s: Bad CODE %s,%s" % (command, par1, par2)


def BAD_ARG(command, arg):
    """Return error message for invalid argument."""
    return "%s: Bad argument: %s" % (command, arg)


def RM(pre, cmd):

    # Remove a file or an empty folder (the type decides which).
    # SAVE "tpi:rm <name>"            - Remove it, after a Y/N prompt
    # SAVE "tpi:rm <name>" CODE 255,0 - Remove it without asking
    # <name> is any file or folder: a name in the current folder, a path
    # (relative, or from / = the card's TAP folder), or a number from the
    # listing. The mounted file can't be removed: tpi:close it first.

    TLM("RM enter")
    par1, par2 = PARAMS(pre)
    name = getArgs(cmd).strip()
    if name:
        name, idx = ResolveIndexName(name)
    if not name:
        message = "RM: Filename required"
        LOG(message, 2)
        SEND_MSG(message, "", _8_A_Invalid_arg)
        return
    if (par1, par2) not in ((0, 0), (255, 0)):
        message = BAD_CODE("RM", par1, par2)
        LOG(message, 2)
        SEND_MSG(message, "", _8_A_Invalid_arg)
        return

    kind, st = SD_CALL(RM_CHECK, name)
    if st != _1_OK:                                                           # kind is the message
        LOG(kind, 1)
        SEND_MSG(kind, "", st)
        return
    arg = name.rstrip('/') + ('/' if kind == "dir" else "")

    if par1 == 0:
        ch = SEND_MSG_PROMPT_YN('Remove "%s" (y/N)?' % name)                  # the prompt is the answer:
        if ch != 89: # 89='Y'                                                 # the rest only reaches the log
            LOG("%s not removed from %s" % (name, TSP.cur_path), 0)
            return
        message, st = SD_CALL(DISK_ERASE_ONE, arg)
        LOG("RM: " + message, 0 if st == _1_OK else 2)
        return

    message, st = SD_CALL(DISK_ERASE_ONE, arg)
    LOG("RM: " + message, 0 if st == _1_OK else 2)
    SEND_MSG(message, "", st)


def RM_CHECK(name):                                                           # RM, before it asks: SD active

    """("file" or "dir", OK), or (message, status) if RM can't remove name."""

    real = catalog.resolve(TSP.cur_path, name.rstrip('/'))
    if real is None or real == catalog.ROOT:
        return "RM: Not found: %s" % name, _3_F_Invalid_file
    if dir_exists(real):
        if catalog.within(TSP.cur_path, real):
            return "RM: Can't remove the current directory", _4_Q_Parameter
        return "dir", _1_OK
    if not file_exists(real):
        return "RM: Not found: %s" % name, _3_F_Invalid_file
    if TSP.f_name and TSP.f_name.upper() == real.upper():
        return "RM: File is mounted; tpi:close it first", _4_Q_Parameter
    return "file", _1_OK


def UNMOUNT(pre, cmd):                                                                                       # Unmount currently mounted file 
    
    TLM("UNMOUNT enter")
    SEND_MSG("Unmounting file. ", "", _1_OK)
    FORGET_MOUNT()

    return


def FORGET_MOUNT():                                                            # no file mounted (UNMOUNT, a card without it)

    """Forget the mounted file and its flash copy. Sends nothing."""

    TSP.f_name = ""
    TSP.offset_tbl = []
    TSP.offset = 0
    TSP.tap_idx = 0
    TSP.append = False

    for tmp in ("/TMP/temp.bin", "/TMP/temp.tap"):                           # each on its own: one missing
        try:                                                                  # mustn't keep the other
            os.remove(tmp)
        except OSError:
            pass

    return


def VERB_TOGGLE(pre, cmd):                                                                               # Toggle commands verbosity ON/OFF 

    # Toggle, display, set, or clear the verbose state
    # SAVE "tpi:verbose"            - Display verbose state
    # SAVE "tpi:verbose"CODE 1,0    - Set off
    # SAVE "tpi:verbose"CODE 1,1    - Set on
    # SAVE "tpi:verbose on"         - Set on
    # SAVE "tpi:verbose off"        - Set off

    global TSP
    
    TLM("VERB_TOGGLE enter")
    par1, par2 = PARAMS(pre)
    arg = getArgs(cmd)
    arg = arg.lower()
    st = _1_OK

    if arg != '':
        par1 = 1
        if arg == 'on':
            par2 = 1
        elif arg == 'off':
            par2 = 0
        else:
            msg = BAD_ARG("VERBOSE", arg)
            par2 = -1
    
    if par1 == 0 and par2 == 0:
        # Display
        if TSP.VERBOSE:
            msg = "Verbose is enabled"
        else:    
            msg = "Verbose is disabled"
    elif par1 == 1:
        # Set
        if par2 < 0:
            st = _8_A_Invalid_arg
            LOG(msg, 2)
        else:
            TSP.VERBOSE = (par2 != 0)
            if TSP.VERBOSE:
                msg = "Verbose is now enabled"
            else:    
                msg = "Verbose is now disabled"
            LOG(msg, 0)
    else:
        msg = BAD_CODE("VERBOSE", par1, par2)
        LOG(msg, 2)
        st = _8_A_Invalid_arg
        
    SEND_MSG(msg, "", st, par1 == 0)
    return 


def ZX48(pre, cmd):                                                           # Changes to ZX Spectrum 48 compat mode 
    
    # Put Pico in ZX Spectrum communication mode
    # SAVE "tpi:zx48"           - put in ZX48 mode (with current tape compat mode)
    # SAVE "tpi:zx48"CODE 1,*   - Don't display help
    # SAVE "tpi:zx48"CODE *,0   - Use default tape load routine 
    # SAVE "tpi:zx48"CODE *,1   - Set normal tape load routine 
    # SAVE "tpi:zx48"CODE *,2   - Set compatible tape load routine 
    # SAVE "tpi:zx48"CODE *,bufsize - compatible load with buffer size spec. 
    #                               Size >= 16384

    global TSP
    
    TLM("ZX48 enter")
    par1, par2 = PARAMS(pre)
    nl = chr(13)

    if par1 > 1:
        msg = BAD_CODE("ZX48", par1, par2)
        LOG(msg, 2)
        SEND_MSG(msg, "", _8_A_Invalid_arg)
        return

    TSP.zx48 = True

    M = [nl, 'Changing TS-Pico to ZX48 mode.', nl]

    if par2 > 0:
        TSP.ZX_TAPE_COMPAT = par2 > 1
          
    if TSP.ZX_TAPE_COMPAT == True:
        M.append('(Compatible tape load mode)')
        if par2 >= 16384:
            M.append('\r(Buffer size = %d)' % par2)
    else:
        M.append('(Normal tape load mode)')
    M.append(nl)
    # One line each, with its own CR: the 2068's screen is 32 columns, and
    # these used to be joined with no separator, relying on every piece
    # being exactly 32 characters. Two weren't ("OUT 14,14to exit").
    M.append(nl.join((
        'Use OUT 244,3 to switch to the',
        'Spectrum ROM. To return to Timex',
        'mode, use OUT 244,0 then',
        'OUT 14,14 to exit ZX48 mode and',
        'resume normal TS-Pico operation.')))
    M.append(nl)
    msg = "".join(M)

    SEND_MSG(msg, "", _1_OK, par1 == 0)
            
    return 


def NOP(pre, cmd):
    TLM("NOP enter")
    """A 'no operation' command"""

    global MQ

    # ─── DUAL-PORT MIGRATION ──────────────────────────────────────────────
    # Was:  MQ.put(0x40); MQ.put(0x01)
    #       (single-port: 0x40 = continue flag in TX, 0x01 = OK status)
    # Now:  MQ.put(0x01); MQ_READY()
    #       The continue flag now lives on $0F via the Y register. The
    #       0x40 in TX would have been read as data by the Z80's $0E
    #       read and misinterpreted later (orphan-byte family bug).
    # ─────────────────────────────────────────────────────────────────────
    MQ.put(0x01)
    MQ_READY()

    return


##################################
# PRE HEADER PROCESSING ROUTINES #
##################################


def PRINT_FLUSH():
    """Append the buffered printer text to the capture file, opening the next
    numbered /VLPRINT/PRNnnnn.TXT if none is open.

    Touches the SD card, which takes the bus state machine away (ACTIVATE_SD
    parks MQ on NULL_SM, and a Z80 that starts a command meanwhile reads a
    floating bus). So ONLY call it while the Z80 is parked in a READY wait
    (~20 s): inside a printer transaction before its READY, inside a
    command, or after another command's pre-header before its handler says
    READY. Leaves MQ rebuilt, Y = BUSY, TX empty: callers stage statuses
    after it.
    """
    global prn_path
    if not PRT.buf:
        return
    try:
        ACTIVATE_SD()
        if prn_path is None:
            prn_path = next_name(VLPRINT, "PRN", "TXT")
        with open(prn_path, "ab") as f:
            f.write(PRT.buf)
        LOG("Printer: %d bytes -> %s" % (len(PRT.buf), prn_path), 0)
        PRT.buf = bytearray()
    except Exception as e:
        LOG("Printer flush failed, %d bytes kept: %s" % (len(PRT.buf), e), 2)
        if len(PRT.buf) > 32768:                    # no card: don't eat the heap
            PRT.buf = bytearray()
    finally:
        DEACTIVATE_SD()
        ACTIVATE_MQ()


def COPY_BMP(scr, mode, colour):
    """COPY's screen -> the next /VSCREEN/SCRnnnn.BMP, at the SAVE "tpi:bmp"
    size (default 512x384). Same SD rule as PRINT_FLUSH. True if written."""
    try:
        ACTIVATE_SD()
        path = next_name(VSCREEN, "SCR", "BMP")
        w0 = 512 if mode == 3 else 256
        sx = max(1, bmp_size[0] // w0)
        sy = max(1, bmp_size[1] // 192)
        with open(path, "wb") as f:
            w, h = write_bmp(f, scr, mode, colour, sx, sy)
        LOG("COPY: mode %d -> %s (%dx%d)" % (mode, path, w, h), 0)
        return True
    except Exception as e:
        LOG("COPY to BMP failed: %s" % e, 2)
        return False
    finally:
        DEACTIVATE_SD()
        ACTIVATE_MQ()


def PRINT_IO(pre):
    """One printer transaction: an LPRINT / LLIST character (pre[1] = 5) or
    COPY (pre[1] = 4 / 6). Gustavo's manual 2.26-2.27; wire format in
    TS/printer.py.

    Each character is its own transaction -- the dispatcher hands every one
    here, SYNC and all. (This used to loop reading the next pre-headers
    itself: on the 1.8b ROM the per-character SYNC misaligned it after the
    first character, and the first non-printer pre-header ended the loop and
    was swallowed, answered with "file closed OK".)

    No body: the Z80 read the pre-load status straight after the pre-header
    and waits for READY. A body (a character >= 80h's pattern, COPY's
    screen) goes through the ROM's 223Eh: READY, 'D' + len + data + XOR,
    READY, final status.
    """
    n = pre[7] | (pre[8] << 8)
    body = None
    ok = True
    if n:
        body = bytearray(n + 4)
        why, got = RX_BLOCK(MQ, body, n + 4, 1000, 1000, "mid")    # READY once listening
        if why:
            MQ_TO_IDLE(MQ, recovered=(why != RXB_ABORT))
            LOG("Printer body %s after %d of %d bytes" % (
                "stopped by BREAK" if why == RXB_ABORT else "stalled", got, n + 4), 1)
            return
        x = 0
        for i in range(n + 3):
            x ^= body[i]
        ok = x == body[n + 3] and body[0] == 0x44
    status = _1_OK
    if pre[1] == 5:
        PRT.feed(pre[3])
        if len(PRT.buf) >= PRINT_FLUSH_AT:
            PRINT_FLUSH()                           # the Z80 waits for READY
    elif not (ok and body is not None
              and COPY_BMP(memoryview(body)[3:n + 3], pre[4], pre[3])):
        status = _2_R_Tape_load
    if body is not None:
        MQ.put(status)                              # 223Eh's final status
    MQ.put(0x01)                                    # next command's pre-load
    MQ_STATUS(MQ, "idle")


def PRN_OPEN(pre, cmd):
    """SAVE "tpi:opprint": close any capture and start the next numbered one."""
    global prn_path
    PRINT_FLUSH()
    st = _1_OK
    try:
        ACTIVATE_SD()
        prn_path = next_name(VLPRINT, "PRN", "TXT")
        open(prn_path, "w").close()
        msg = "Printer capture: " + prn_path[3:]
    except Exception as e:
        prn_path = None
        msg, st = "Printer capture: SD error", _3_F_Invalid_file
        LOG("OPPRINT failed: %s" % e, 2)
    finally:
        DEACTIVATE_SD()
        ACTIVATE_MQ()
    PRT.col = PRT.line = 0
    SEND_MSG(msg, "", st)


def PRN_CLOSE(pre, cmd):
    """SAVE "tpi:clprint": write out and close the capture file. The next
    printed character opens a new one."""
    global prn_path
    PRINT_FLUSH()
    msg = "Printer capture closed: " + prn_path[3:] if prn_path else "No printer capture open"
    prn_path = None
    PRT.col = PRT.line = 0
    SEND_MSG(msg, "", _1_OK)


def PRN_FLAG(pre, cmd):
    """SAVE "tpi:autolf" / "noautolf" / "autopg" / "noautopg"."""
    word = cmd[7:].split(" ")[0].upper()
    on = not word.startswith("NO")
    if word.endswith("AUTOLF"):
        PRT.autolf = on
        msg = "Printer: CR+LF line ends " + ("on" if on else "off")
    else:
        PRT.autopg = on
        msg = "Printer: paging every %d lines %s" % (PRT.lines, "on" if on else "off")
    SEND_MSG(msg, "", _1_OK)


def PRN_SIZE(pre, cmd):
    """SAVE "tpi:prnsz" CODE cols,lines (or "tpi:prnsz cols lines"): page
    size for wrapping and AUTOPG. No parameters: report it."""
    cols, lines = PARAMS(pre)
    args = getArgs(cmd).replace(",", " ").split()
    try:
        if args:
            cols, lines = int(args[0]), int(args[1]) if len(args) > 1 else PRT.lines
        if cols or lines:
            if not (0 <= cols <= 255 and 0 <= lines <= 255):
                raise ValueError
            PRT.cols, PRT.lines = cols, lines
    except (ValueError, IndexError):
        SEND_MSG("Printer size: bad parameters", "", _4_Q_Parameter)
        return
    SEND_MSG("Printer size: %d columns, %d lines" % (PRT.cols, PRT.lines), "", _1_OK)


def PRN_BMP(pre, cmd):
    """SAVE "tpi:bmp" CODE x,y: COPY picture size -- 256/512/1024/2048 x
    192/384/768/1536 (hi-res screens 512/1024/2048/4096 wide). No
    parameters: report it."""
    global bmp_size
    x, y = PARAMS(pre)
    if x or y:
        if y == 1596:                               # as printed in the manual
            y = 1536
        if x not in (256, 512, 1024, 2048, 4096) or y not in (192, 384, 768, 1536):
            SEND_MSG("BMP size: use 256-4096 x 192-1536", "", _4_Q_Parameter)
            return
        bmp_size = (x, y)
    SEND_MSG("COPY picture: %dx%d" % bmp_size, "", _1_OK)

def FAIL_CMD(status):
    """Put TX into a known state and hand the Z80 exactly one status byte.

    Recovery path for PROCESS_CMD (issue #42). A handler may have written
    part of a response before it failed, so clear TX first: a partial
    response shifts every byte the Z80 reads after it, turning a clean
    error into a CRC mismatch a phase or two downstream -- the
    orphan-byte family described in src/CLAUDE.md.

    Deliberately NOT SEND_MSG. With TSP.VERBOSE on, SEND_MSG streams the
    message text and blocks in MQ.put() once TX fills. On this path we do
    not know the Z80 is still reading -- if it has already aborted,
    nothing drains TX and the Pico hangs, which is the exact failure this
    recovery exists to prevent. One byte always fits the 4-deep FIFO and
    can never block. The human-readable explanation goes to
    /activity.log, which is retrievable; a wedged Pico is not.
    """
    global MQ

    # The handler may have died with the card holding the bus: MQ parked on
    # NULL_SM, GPIO 2-4 on SPI. Anything put() there never reaches the Z80,
    # and nothing would ever rebuild the bus SM -- the TS-Pico goes deaf
    # for the rest of the session. Hand the bus back first, the same
    # DEACTIVATE_SD -> ACTIVATE_MQ pair every SD handler ends with (Y stays
    # BUSY until the MQ_READY below). Guarded: this is the recovery path.
    if sd_active:
        try:
            DEACTIVATE_SD()
            ACTIVATE_MQ()
        except Exception:
            pass

    # Both loops are bounded. The equivalent drains elsewhere in this
    # file spin freely, which is fine on a healthy path -- but this is
    # the recovery path, and an unbounded loop here would be the very
    # hang we are trying to prevent. The FIFOs are 4 deep; anything
    # past a few iterations means the SM is not draining and spinning
    # will not help.
    for _ in range(64):
        if MQ.tx_fifo() == 0:
            break
        MQX(MQ, "pull (noblock)")
        MQX(MQ, "mov (osr, null)")
    for _ in range(64):
        if MQ.rx_fifo() == 0:
            break
        MQ.get()

    MQ.put(status)
    MQ_READY()


def PROCESS_CMD(pre, SA_funct, EXT_SA_FUNCT):                                           # Processes 'B' (BASIC) commands sent by the TS
    
    global TSP
    global MQ
    global ROM
    global BANK
    
    global files
    global files_upper
    
    TSP.zx48 = False
    cur_fname = TSP.f_name
    
    wrt = MQ.put
    load_cmd = pre[1]

    # The body is 'D', len lo, len hi, the command text, then an XOR of
    # all of those (EXROM 224Dh-2274h, the same in v1.1 to v1.7): len+4
    # bytes. Reading len+3 left the checksum byte in RX. It landed after
    # the handler had set READY, dropped Y back to BUSY (PIO auto-busy),
    # and only the tail's RX drain disposed of it. Read it and check it.
    long = pre[7] + 256*pre[8] + 4
    rl = range(long)
    cmd = bytearray(long)           # sized to the body (was a fixed 100)

    # ─── DUAL-PORT MIGRATION: leading wrt(0x40); wrt(0x01) REMOVED ────
    # In single-port Ricardo's code, these two bytes served as:
    #   - wrt(0x40): "continue flag" — signal Pico is ready for body
    #   - wrt(0x01): pre-load of initial status for command body phase
    # Both are obsolete in dual-port:
    #   - The continue flag lives on $0F via the Y register (kept at
    #     READY for the entire session).
    #   - The initial status byte the Z80 just read at pre-header time
    #     was supplied by the PREVIOUS handler's V6 tail pre-load (or
    #     by the boot pre-load for the very first command).
    # Leaving them here would inject two orphan bytes that get misread
    # by subsequent Z80 reads — the classic orphan-byte family of bugs.
    #
    # The blocking-read loop below is the production-tight body drain;
    # same two-phase capture rule as the dispatcher's pre-header read.
    # ──────────────────────────────────────────────────────────────────
    #
    # ─── DUAL-PORT MIGRATION: body-read timeout (defensive) ───────────
    # Hard guard against a documented cascade where Z80 aborts mid-
    # command without sending the body bytes:
    #
    #   1. Some prior command consumed the V6 pre-load 0x01 (e.g., a
    #      stray IN 14 in BASIC, or an unknown source we haven't yet
    #      tracked down).
    #   2. Next SAVE "tpi:..." pre-header phase: Z80 reads $0E for
    #      status, gets 0x00 from empty TX → Report J.
    #   3. BASIC's ON ERR catches the J, aborts the SAVE statement.
    #   4. Z80 never sends the command body bytes that would normally
    #      follow the pre-header.
    #   5. But we already read all 10 pre-header bytes (that's why
    #      we're in PROCESS_CMD), so the dispatcher saw pre[0]=66 and
    #      called us. Now we're blocked in MQ.get() forever waiting
    #      for body bytes that aren't coming. Pico effectively hangs.
    #
    # Without this timeout, the only recovery is the TS-Pico reset
    # button. Symptom: LED stops blinking, Thonny REPL traceback at
    # this exact line.
    #
    # With this timeout: after 1 second of no byte arriving, we log
    # the timeout via TLM, drain any partial state, write a fresh V6
    # pre-load, and return. Main loop continues, ready for the next
    # command. picotest's BASIC ON ERR has already handled the J on
    # the 2068 side, so the user-visible behavior is just "that one
    # test failed" rather than "the Pico locked up."
    #
    # Same pattern would benefit the main-loop pre-header read (if
    # Z80 sends 1-9 bytes and stops, that read also hangs). Filed
    # in OPEN_QUESTIONS.md as belt-and-suspenders follow-up.
    # ──────────────────────────────────────────────────────────────────
    BODY_READ_TIMEOUT_MS = 1000   # tunable; 1 second is generous

    # Stage 4 (#51): READY here, not in the dispatcher -- the Z80 sends the
    # whole body the moment it sees it, ~35 us a byte into a 4-deep RX FIFO,
    # and the dispatcher said it before its own logging. RX_CAPTURE ends on
    # a port-0Fh write (BREAK / SYNC) or on silence instead of hanging.
    raw = array("H", bytes(2 * long))
    got = RX_CAPTURE(MQ, raw, long, BODY_READ_TIMEOUT_MS, "mid")   # READY once listening
    if got != long:
        MQ_TO_IDLE(MQ, status=False)            # empty FIFOs, one pre-load
        TLM("PROCESS_CMD body %s" % ("aborted (0Fh)" if got < 0 else "timeout"),
            "got=%d of %d: %s" % (got, long, " ".join("%03X" % raw[i] for i in range(abs(got)))))
        LOG("PROCESS_CMD body %s at byte %d/%d" % (
            "aborted by BREAK/SYNC" if got < 0 else "read timeout",
            -got - 1 if got < 0 else got, long), 1 if got < 0 else 2)
        MQ_STATUS(MQ, "idle" if got < 0 else "recovered")
        return
    for l in rl:
        cmd[l] = raw[l] & 0xFF

    # Now safe to TLM (Z80 is processing — no time pressure on Pico).
    TLM("PROCESS_CMD enter", "load_cmd=%d cmd_len=%d cmd=%r" % (
        load_cmd, long, bytes(cmd[:long])))

    # --- Issue #42: the V6 pre-load tail must ALWAYS run -----------------
    # Everything from the body decode through the command dispatch runs
    # inside a try/finally whose `finally` IS the tail at the bottom of
    # this function (drains + MQ.put(0x01) + MQ_READY).
    #
    # Before this, a handler that raised -- MOUNT_FILE's unguarded
    # os.stat() with no SD card is the easy one to hit -- propagated out
    # of PROCESS_CMD to the main loop, which logs it and `continue`s.
    # That skipped the tail, so the V6 pre-load was never written and the
    # NEXT command's pre-header phase read 0x00 from an empty TX FIFO and
    # reported J. The failure surfaced one command later than its cause,
    # which is the orphan-byte family's signature (see src/CLAUDE.md
    # "Symptom-to-cause mapping").
    #
    # `return` inside a `try` still runs its `finally`, so the early
    # return on an undecodable body is fixed by the same change -- it was
    # the second instance of this bug.
    #
    # NOTE: the body-read timeout loop ABOVE is deliberately left OUTSIDE
    # the try. It writes its own MQ.put(0x01) before returning; pulling
    # it inside would hand it a SECOND pre-load from the finally, and
    # that orphan byte is exactly what produces Report R on the next
    # data block.
    # ---------------------------------------------------------------------
    cmd_abort = 0        # CmdAbort code, if the output was stopped
    cmd_exec = "?"        # the tail logs this; it must exist even when
                          # the decode below never gets to assign it

    try:
        # A bad checksum means the body was damaged or misaligned on the
        # wire: answer Report R (as a LOAD parity error does) rather
        # than run whatever the bytes happen to spell.
        chk = 0
        for b in cmd[:long - 1]:
            chk ^= b
        if chk != cmd[long - 1]:
            LOG("PROCESS_CMD bad command checksum: got 0x%02X, expected 0x%02X" % (
                cmd[long - 1], chk), 2)
            TLM("PROCESS_CMD checksum FAILED -- Report R, tail restores V6")
            FAIL_CMD(_2_R_Tape_load)
            return

        if getattr(TSP, "listing_stale", False):                               # a ZX48 SAVE added a file
            REFRESH_LISTING()

        try:
            # Decode only the text: 'D' and the 16-bit length in front of it
            # are binary, and a length of 128 or more isn't valid UTF-8 (a
            # tpi:chwr of 60+ bytes, a 64-character path). "D.." keeps every
            # handler's cmd[3:] / cmd[7:] offsets where they were.
            cmd = "D.." + bytes(cmd[3:long - 1]).decode()
        except:
            LOG("Unrecognized string in PROCESS_CMD: FIFO Status:%d %d" % (MQ.tx_fifo(), MQ.rx_fifo()), 2)
            TLM("PROCESS_CMD decode FAILED — status sent, tail restores V6")
            # Garbage on the wire, not a handler bug — but the Z80 is still
            # waiting for this command's status byte. Hand it one, then let
            # the finally below re-arm the V6 chain for the NEXT command.
            # (Before issue #42 this `return` skipped the tail entirely.)
            FAIL_CMD(_5_C_Nonsense)
            return

        cmd_exec = cmd[3:].upper() # Command starting with "TPI:" in uppercase
        rest_cmd = cmd[7:] # Command after "tpi:"

        TLM("PROCESS_CMD parsed", "cmd_exec=%r rest_cmd=%r" % (cmd_exec, rest_cmd))

        # gc.collect()

        # Split command word from any arguments
        sp = cmd_exec.find(' ')
        if sp >= 0:
            cmd_word = cmd_exec[:sp]
        else:
            cmd_word = cmd_exec

        # No card: a command that needs one gets told so, once, clearly. The
        # card is looked for again first (one quick try), so putting one in
        # is all it takes; one that has come back is set up on the way.
        if SD_NEEDED(load_cmd, cmd_word, cmd_exec, SA_funct) and not TSP.sd_present \
                and not SD_PROBE():
            NO_CARD_REPLY(cmd_word)

        elif load_cmd:                                                                                  # Is it a "LOAD:tpi:..." command.....?

            msg, rest_cmd, status = LOAD_TPI(rest_cmd)
            SEND_MSG(msg, rest_cmd, status, " files match: " in msg)   # that one says what to do: always show it

        else:                                                                                                 # ...or it's a "SAVE:tpi:..." command

            TLM("PROCESS_CMD SAVE branch", "cmd_word=%r in_SA_funct=%s in_EXT=%s" % (
                cmd_word, cmd_word in SA_funct, cmd_word in EXT_SA_FUNCT))

            if cmd_word in SA_funct:
                EXEC = SA_funct[cmd_word]
                TLM("PROCESS_CMD dispatching SA_funct", "cmd_word=%r" % cmd_word)
                EXEC(pre, cmd)
                TLM("PROCESS_CMD SA_funct returned", "cmd_word=%r" % cmd_word)

            elif cmd_word in EXT_SA_FUNCT:                                                                                # Is an external cmd?
                EXEC = EXT_SA_FUNCT[cmd_word]
                TLM("PROCESS_CMD dispatching EXT_SA_FUNCT", "cmd_word=%r" % cmd_word)
                EXEC(MQ, TSP, pre, cmd)
                TLM("PROCESS_CMD EXT_SA_FUNCT returned", "cmd_word=%r" % cmd_word)

            else:
                msg = "Unrecognized command: %s" % cmd_exec
                SEND_MSG(msg, 'SAVE "tpi:help" for info', _5_C_Nonsense)    # If none of the above, raise error
                LOG(msg, 2)


    except CmdAbort as _a:
        # The Z80 stopped this command's output: BREAK at a key wait (the
        # 1.8b ROM's 0Fh write) or it stopped reading. Nothing more goes to
        # it -- empty both FIFOs; the tail below stages the one pre-load and
        # says READY + IDLE (RECOVERED if it went silent).
        CMD_FLUSH()
        cmd_abort = _a.args[0]
        LOG("%s stopped by %s" % (cmd_exec, "BREAK" if cmd_abort == 1 else "a Z80 that stopped reading"),
            1 if cmd_abort == 1 else 2)
    except Exception as _e:
        # Any handler that raised.
        #
        # Protocol FIRST, diagnostics second. FAIL_CMD allocates nothing
        # and cannot block, so it runs before the logging: if the handler
        # died of MemoryError, LOG/TLM may well fail too, and the one
        # thing that must not fail is getting a status byte to a Z80
        # that is sitting in WAIT EXECUTION.
        FAIL_CMD(_10_J_Invalid_IO)
        try:
            LOG("EXCEPTION in handler for %s: %s" % (cmd_exec, _e), 3)
            TLM("PROCESS_CMD handler raised", "cmd=%r err=%s" % (cmd_exec, _e))
        except:
            pass                  # never let logging mask the real failure

    finally:
        # ─── DUAL-PORT MIGRATION: inline FIFO drains ──────────────────────
        # Replaces WAIT_TX_RECEIVED() and EMPTY_RX_FIFO() (single-port
        # helpers being retired in stage 7). Behavior is identical.
        # ──────────────────────────────────────────────────────────────────
        TLM("PROCESS_CMD draining tx_fifo at exit")
        # Bounded by time, not by a loop count whose length depended on the
        # MicroPython version (audit §4): 3 s for the Z80 to read the tail.
        drain_tx = 0
        _t0 = time.ticks_ms()
        while MQ.tx_fifo() != 0:
            drain_tx += 1
            if time.ticks_diff(time.ticks_ms(), _t0) >= 3000:
                TLM("PROCESS_CMD STUCK draining tx", "tx=%d" % MQ.tx_fifo())
                break

        drain_rx = 0
        while MQ.rx_fifo() != 0 and drain_rx < 64:  # a Z80 that keeps writing can't hold it here
            MQ.get()
            drain_rx += 1

        TLM("PROCESS_CMD exit", "drain_tx=%d drain_rx=%d cmd=%r" % (drain_tx, drain_rx, cmd_exec))

        # ─── DUAL-PORT MIGRATION: V6 tail pre-load ────────────────────────
        # Pre-load 0x01 status for the NEXT command's initial $0E read.
        # This is the V6 chain — every command handler ends with a 0x01
        # in TX so the next command's pre-header phase finds a valid
        # status byte already waiting. Without this, the next command
        # would read stale 0x00 -> Report J - Invalid I/O Device.
        # See docs/PROTOCOL.md "Writing a new command handler" for details.
        # ──────────────────────────────────────────────────────────────────
        MQ.put(0x01)

        # ─── Issue #14: re-assert Y=READY after the V6 pre-load ───────────
        # The PIO drops Y to 0 on every Z80 OUT (pre-header + body bytes
        # for this command have all been Z80 OUTs). Without an explicit
        # MQ_READY here, Y stays BUSY and the Z80's WAIT EXECUTION before
        # its next status read blocks until timeout → Report J. The
        # pre-load byte sits in TX but the Z80 never reads it.
        # ──────────────────────────────────────────────────────────────────
        # Arm the pre-header's DMA channel BEFORE saying IDLE, as the SYNC
        # path does: the Z80 sends its next command the moment it sees IDLE
        # -- a BASIC program's next tpi: line, or a SYNC this tail's drain
        # just swallowed -- and between here and the top of the main loop
        # (a LOG, the return, a TLM) the 4-deep FIFO overflowed: "Partial
        # pre-header 4/10: 42 00 FF 00", Report T (hardware, 2026-10-03).
        if RXD is not None:
            RXD.arm(MQ)
        MQ_STATUS(MQ, "recovered" if cmd_abort == 3 else "idle")

        LOG("Exiting CMD processing: %s %d %d" % (cmd_exec, MQ.tx_fifo(), MQ.rx_fifo()), 0)

    return


######################
# MAIN LOOP ROUTINES #
######################


def TS2068_IO():                                                         # Main IO loop, for SAVE, LOAD and commands processing
    
    global busy                                                        # whether 2nd core is busy
    global dead                                                        # boolean to indicate whether an IO routine is "alive" or not. Used for watchdog CHK_STATUS
    global files                                                       # array of only the files of current directory; used for index mounting of files ( LOAD "TPI:*nn") 
    global kill                                                        # boolean set to True when watchdog wants to end a misbehaving IO routine 
    global lista                                                       # all contents of current dir, in string format to be displayed by "TPI:DIR"
    global log_entries                                                 # log entries to be saved during next loop
    global log_to_serial                                               # If TRUE, all logging messages will be displayed on screen instead of the logfile
    
    global ROM
    global BANK
    global MQ
    global led
    global TSP
    
    global alldirs
    global EXT_SA_FUNCT
    
    busy = False
    dead = True
    kill = False
    
    files = []
    lista = ""
    log_entries = []
    log_to_serial = False
    
    led = Pin(25, Pin.OUT)

    init_values = LOAD_CONFIG()
    TSP = PICO_STATUS(init_values)
    
    try:
        log_len = os.stat("/activity.log")[6]
    except:
        log_len = 0
        
    if log_len >= 64_000:                                            # If log >= 64K generate a new log file
        
        try:
            os.remove("/activity.old")
        except:
            pass
        
        os.rename("/activity.log", "/activity.old")
        LOG("Starting new log file", 3)
    
    LOG("Starting TS Pico. Memory at startup: %d" % gc.mem_free(), 0)
    SAVE_LOG()
        

#     Uncomment the following two lines, for DCK *AND* ROM mapping
    ROM = StateMachine(4, set_ctrl, freq=150_000_000, in_base=Pin(0, Pin.IN), jmp_pin=Pin(26), set_base=Pin(21, Pin.OUT), out_base=Pin(19, Pin.OUT))
    ROM.active(1)

#     Uncomment the following two lines, for DCK access and no ROM mapping
#     ROM = StateMachine(4, set_dck, freq=150_000_000, jmp_pin=Pin(26), out_base=Pin(19, Pin.OUT))
#     ROM.active(1)

    BANK = StateMachine(5, sel_bank, freq=150_000_000, jmp_pin=Pin(26), out_base=Pin(15, Pin.OUT))
    BANK.active(1)

    ROM.put(TSP.ROM_SM)
    BANK.put(TSP.bank_sm)
    
    LOG("After StateMachine setup, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)
    gc.collect()
    LOG("After gc.collect, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)

    REMOVE_DIR("/TMP")
    os.mkdir("/TMP")
    
    # LOG("After re-make /TMP, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)
    # gc.collect()
    # LOG("After gc.collect, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)

    os.chdir('/')
    
    # Commands expecting a name following the command word need a space at the
    # end of their dictionary key string.

    SA_funct = {
        "TPI:APPEND" : APPEND,
        "TPI:BLKRCV" : BLKRCV,
        "TPI:CD" : CDIR,
        "TPI:CLOSE": UNMOUNT,
        "TPI:DIR": DIR,
        "TPI:COPY": DISK_COPY,
        "TPI:ERASE": DISK_ERASE,
        "TPI:FORMAT": DISK_FORMAT,
        "TPI:REN": DISK_REN,
        "TPI:FOPEN": NATIVE_OPEN,
        "TPI:CHOPEN": CH_OPEN,
        "TPI:CHWR": CH_WRITE,
        "TPI:CHRD": CH_READ,
        "TPI:CHCLOSE": CH_CLOSE,
        "TPI:FFW" : FWD,
        "TPI:HELP" : GETHELP,
        "TPI:IDIR" : IDIR,
        "TPI:INFO" : GETINFO,
        "TPI:LOG" : GETLOG, 
        "TPI:LOGLEVEL" : LOGLEVEL,
        "TPI:MD" : MDIR,
        "TPI:BOOT" : MEMBOOT,
        "TPI:MEMBOOT" : MEMBOOT,
        "TPI:DOCK" : MEMDOCK,
        "TPI:MEMDOCK" : MEMDOCK,
        "TPI:NOP" : NOP,                                                                      # This is to test Ryan's new Commander
        "TPI:PATH" : PATH,
        "TPI:REW" : REW,
        "TPI:RM" : RM, # dir or file
        "TPI:NEWTAP" : NEW_TAP,
        "TPI:TAPDIR" : TAPDIR,
        "TPI:VERBOSE" : VERB_TOGGLE, 
        "TPI:ZX48" : ZX48,
        "TPI:AUTOLF" : PRN_FLAG,
        "TPI:AUTOPG" : PRN_FLAG,
        "TPI:BMP" : PRN_BMP,
        "TPI:CLPRINT" : PRN_CLOSE,
        "TPI:CONFIG" : SA_NOT_IMP,
        "TPI:DELETE" : SA_NOT_IMP,
        "TPI:FRESET" : SA_NOT_IMP,
        "TPI:GETCONFIG" : SA_NOT_IMP, 
        "TPI:LIST" : SA_NOT_IMP,
        "TPI:MEMINFO" : SA_NOT_IMP,
        "TPI:NOAUTOLF" : PRN_FLAG,
        "TPI:NOAUTOPG" : PRN_FLAG,
        "TPI:OPPRINT" : PRN_OPEN,
        "TPI:PRNSZ" : PRN_SIZE,
        "TPI:STOP" : SA_NOT_IMP,
        }
    
    # Imported external SA/LD commands or empty dictionary
    
    # LOG("After SA_funct setup, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)
    # gc.collect()
    # LOG("After gc.collect, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)

    # ─── Prefer the dev_extcmd override if present ──────────────────────
    # TS/extcmd.py is frozen into the UF2. A /dev_extcmd.py on the flash
    # root overrides it without a rebuild, the same way /dev_tspico.py
    # shadows TS.tspico: handy for trying out a new extension command.
    # Try the override first.
    # ─────────────────────────────────────────────────────────────────────
    try:
        from dev_extcmd import EXT_SA_FUNCT
        LOG("Loaded EXT_SA_FUNCT from /dev_extcmd.py override", 0)
    except ImportError:
        try:
            from TS.extcmd import EXT_SA_FUNCT
            LOG("Loaded EXT_SA_FUNCT from frozen TS.extcmd", 0)
        except Exception as e:
            LOG("Unable to import external commands; using empty SA_EXT_CMD dictionary: " + str(e), 0)
            EXT_SA_FUNCT = {}

    LOG("After Ext cmd load, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)
    gc.collect()
    LOG("After gc.collect, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)

    dead = False
    _thread.start_new_thread(BLINK_LED, (0.9, ))
    
    # LOG("After start thread blink, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)
    # gc.collect()
    # LOG("After gc.collect, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)

    # The card. ACTIVATE_SD's first successful mount sets everything up
    # (SD_REVALIDATE: makes /TAP on a blank card, reads the folder, builds
    # the directory list). No card, or one that can't be used, is not the end
    # of the boot any more: the TS-Pico runs without one -- LOAD "" still has
    # the flash assets, commands that need a card say so -- and the next
    # command that needs one looks again. The LED double-blinks meanwhile.
    try:
        ACTIVATE_SD(tries=5)                                           # a cold card can take a few tries
    except OSError as e:
        TSP.sd_present = False
        LOG("Starting without an SD card: %s" % e, 1)

    dead = True                                                        # tells BLINK_LED (core1) to stop

    # Wait for BLINK_LED to finish before core1 is used for anything else.
    # Unlike the waits on SAVE_LOG further down, this one is safe unbounded:
    # BLINK_LED only sleeps and toggles the LED, it can't raise, and it sets
    # `busy = False` within one blink period (0.9 s) of seeing `dead`.
    while busy:
        pass

    sd_ok = TSP.sd_present and TSP.sd_listing_ok
    LOG("After the SD card setup, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)
    gc.collect()
    LOG("After gc.collect, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)

    # ─── DUAL-PORT MIGRATION: explicit SD-teardown before MQ activation ───
    # ACTIVATE_MQ no longer unmounts /sd itself; we must do it explicitly
    # via DEACTIVATE_SD first (see stage-3 comments above ACTIVATE_MQ).
    # This also clamps GPIO 2-4 LOW before the PIO reclaims them, which
    # closes the tri-state window that was the original Report D root
    # cause (docs/DUAL_PORT_DEVELOPMENT.md §1).
    # ─────────────────────────────────────────────────────────────────────
    DEACTIVATE_SD()
    ACTIVATE_MQ()

    # ─── Boot-noise flush (Ryan's diagnostic loop, kept) ──────────────────
    # BEFORE the boot pre-load and READY (2026-10-03, audit §4): it used to
    # run after them, ~0.5 s into a window in which the 2068 may already be
    # sending its first command -- which this would have eaten. With Y still
    # BUSY, the Z80 waits; only noise can arrive.
    # The Z80 may emit stray bytes during its own power-on reset / boot
    # window. We drain anything sitting in RX FIFO so the first "real"
    # protocol byte isn't preceded by garbage. Per-byte LOG kept for
    # diagnostic value — useful when chasing power-sequence weirdness.
    # ─────────────────────────────────────────────────────────────────────
    LOG("Boot noise flush: starting", 0)
    boot_garbage = []
    empty_start = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), empty_start) < 500:
        if MQ.rx_fifo() != 0:
            b = MQ.get()
            boot_garbage.append(b)
            LOG("Boot noise: got byte " + str(b) + " (total: " + str(len(boot_garbage)) + ")", 0)
            empty_start = time.ticks_ms()  # Reset timer when we get data
        time.sleep_ms(10)
    LOG("Boot noise flush: done, FIFO empty for 500ms", 0)
    if boot_garbage:
        LOG("Flushed " + str(len(boot_garbage)) + " bytes of boot noise: " + str(boot_garbage), 0)
    else:
        LOG("No boot noise detected", 0)
    # SAVE_LOG()

    # ─── DUAL-PORT MIGRATION: boot-time status pre-load + explicit ready ──
    # Pre-load a single 0x01 status byte into TX FIFO. The very first Z80
    # command will read this from $0E as its initial OK status. Every
    # command handler ends with its own MQ.put(0x01), so this chain
    # continues automatically across subsequent commands without needing
    # any further pre-loads from the dispatcher.
    #
    # CRITICAL #1: this MQ.put(0x01) must happen ONCE, here, and not inside
    # ACTIVATE_MQ. Doing it inside ACTIVATE_MQ would also fire it on
    # every mid-command SD round-trip (MOUNT_FILE etc.), producing a
    # stray 0x01 that gets misread later in the protocol. This was
    # "Bug 1" in docs/DUAL_PORT_DEVELOPMENT.md §8.
    #
    # CRITICAL #2: ACTIVATE_MQ no longer sets Y=READY (see its function
    # body for the race-fix rationale). We MUST explicitly call MQ_READY()
    # here AFTER loading the pre-load byte, so the Z80's $0F polls
    # succeed and it can read the pre-loaded 0x01 from $0E. The order is
    # non-negotiable: put-then-ready, never ready-then-put.
    # ─────────────────────────────────────────────────────────────────────

    MQ.put(0x01)
    MQ_READY()

    # ─── DUAL-PORT MIGRATION: pre-open /assets/nofile.tap ─────────────────
    # OPEN_NOFILE_TAP caches a read handle to /assets/nofile.tap so that
    # LOAD "" (no prior mount) doesn't pay file-open latency in the
    # time-critical response path. Without this, the open takes 1-5 ms
    # during which the Z80 reads stale 0x00 bytes and reports Report J.
    # See docs/DUAL_PORT_DEVELOPMENT.md §8 (Bug 3 area / nofile pre-open).
    # ─────────────────────────────────────────────────────────────────────
    if OPEN_NOFILE_TAP():
        LOG("/assets/nofile.tap pre-opened OK", 0)
    else:
        LOG('WARNING: /assets/nofile.tap MISSING from Pico flash. '
            'LOAD "" without a prior mount will return Report R until '
            'you copy assets/*.tap from the repo onto Pico flash.', 1)

    if sd_ok:
        LOG("SD Card initialized and mounted OK", 0)
    elif TSP.sd_present:
        LOG("SD card mounted but failing; continuing without a directory listing", 1)
    else:
        LOG("No SD card; commands that need one will say so", 1)
    SAVE_LOG()

    wrt = MQ.put


    LOG("Before main loop, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)
    gc.collect()
    LOG("After gc.collect, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)

    LOG("TS Pico initialized OK. Waiting for commands...", 0)
    SAVE_LOG()
    
    led.value(0)

    pre = bytearray(10)
    pre_raw = array("I", [0] * 10)          # 9-bit capture: bit 8 = port 0Fh write
    rxd = RX_DMA(pre_raw)                   # caught by DMA while idle; None: polled
    global RXD
    RXD = rxd                               # PROCESS_CMD's tail arms it before IDLE
    r1 = range(10)

    ts = time.ticks_us()                                                                           # ts -> timestamp
    
    # ─── The service loop, restarted after an unexpected error ──────────
    # David, 2026-10-02: after a crash the 2068 should get its TS-Pico back.
    # Not machine.reset(): that releases the pins that select the 2068's
    # ROM bank, and a running 2068 would crash. Not TS2068_IO() again
    # either: that rebuilds the ROM / BANK state machines and re-reads
    # config.ini, whose one-shot tpi:boot could switch the ROM slot under
    # the running 2068. Only the bus link is reset here -- the ROM and bank
    # lines are never touched -- with RECOVERED staged, so the 2068's next
    # command gets "T TS-Pico reset, try again". Three failures within a
    # minute: give up and let main.py log it and stop, as before.
    # BaseExceptions (Ctrl-C from the host, CmdAbort) pass straight through.
    # (2026-09-30 audit, §4.)
    # ─────────────────────────────────────────────────────────────────────
    failures = []
    while True:
        try:
            while True:                                                                                    # main execution loop

                if rxd is not None:
                    rxd.arm(MQ)                     # idle: a DMA channel takes the next pre-header
                if (rxd.waiting() if rxd is not None else MQ.rx_fifo()) != 0:

                    ts = time.ticks_us()                                                                   # reset timestamp

                    # ─── DUAL-PORT MIGRATION: tight blocking pre-header read ─────
                    # Replaces Ryan's earlier "count up to 30,000 polls" read loop
                    # with a production-tight blocking burst: ten back-to-back
                    # MQ.get() calls and NOTHING in between.
                    #
                    # Why so strict: the PIO RX FIFO is only 4 entries deep, and
                    # the Z80 OUTs bytes at ~30 us each. Any Python work between
                    # successive gets (conditionals, counters, polling-fifo) risks
                    # letting the FIFO overflow, at which point PIO push(noblock)
                    # silently drops bytes. The Z80 doesn't know; the dispatcher
                    # sees a truncated pre-header and dispatches to the wrong
                    # branch (or no branch at all -> Report J).
                    #
                    # Also removed: the per-iteration `wrt(0x01)` that used to
                    # live right above this read. In the dual-port V6 chain, the
                    # status byte for THIS command was already pre-loaded into
                    # TX by the PREVIOUS command's tail (or by the boot pre-load
                    # for the very first command). Adding another wrt(0x01) here
                    # would inject a stray byte that gets misread later in the
                    # protocol (orphan-byte family of bugs).
                    # ────────────────────────────────────────────────────────────
                    # ─── Issue #51: SYNC and a bounded, tight capture ────────────
                    # Still a tight burst read (the rule above stands), but into a
                    # 9-bit word array, and it can't block forever:
                    #
                    #  * The 1.8b ROM opens every command with OUT (0Fh),03h (SYNC)
                    #    and then waits for READY + IDLE before sending the pre-
                    #    header. That write arrives as 0x103. Old code stored it as
                    #    pre[0] and then blocked for ten bytes that were never coming.
                    #  * A half-sent pre-header used to hang here for good (the
                    #    main-loop case in docs/OPEN_QUESTIONS.md); now it's a 1 s
                    #    stall and a RECOVERED status.
                    #
                    # ROMs up to v1.7 never write 0Fh: for them only the stall path
                    # is new.
                    # ────────────────────────────────────────────────────────────
                    if rxd is not None:
                        got = rxd.take(1000)        # the same results, from the DMA channel
                    else:
                        got = RX_CAPTURE(MQ, pre_raw, 10, 1000)
                    if got < 0:
                        # A write to 0Fh, with the Z80 now held until we say IDLE:
                        # SYNC, a BREAK abort that landed after its transaction had
                        # finished, or a SYNC right behind a half-sent pre-header
                        # (2068 reset). Reset, do any slow work NOW, then IDLE and
                        # straight back to the capture -- nothing slow after IDLE,
                        # the pre-header follows within microseconds.
                        MQ_TO_IDLE(MQ, status=False)
                        if got != -1:               # a lone SYNC is every command: not logged
                            TLM("Pre-header: 0Fh write", "%s" % " ".join(
                                "%03X" % pre_raw[i] for i in range(-got)))
                            LOG("0Fh write after %d pre-header byte(s) -- resynced" % (-got - 1), 1)
                        # A log write on core1 (SAVE_LOG) stops BOTH cores while it
                        # programs flash, and the Z80 sends its pre-header the moment
                        # we say IDLE: a freeze mid-burst lost bytes (hardware,
                        # 2026-09-27: "Partial pre-header 8/10" -> RECOVERED -> Report
                        # T in Commander). The Z80 waits up to ~1 s for IDLE after a
                        # SYNC, so let the write finish first (bounded).
                        _t = time.ticks_ms()
                        while busy and time.ticks_diff(time.ticks_ms(), _t) < 800:
                            pass
                        # (No gc.collect() here: 4.6 ms on every SYNC -- every LPRINT
                        # character -- and not needed: RX_CAPTURE allocates nothing,
                        # so no GC can start during the pre-header burst.)
                        if rxd is not None:
                            rxd.arm(MQ)             # before IDLE: the pre-header follows at once
                        MQ_STATUS(MQ, "idle")
                        continue
                    if got != 10:
                        # Part of a pre-header, then a second of silence: a 2068
                        # reset, a lost byte, or noise. Don't guess at a command.
                        LOG("Partial pre-header %d/10: %s -- RECOVERED" % (
                            got, " ".join("%03X" % pre_raw[i] for i in range(got))), 2)
                        TLM("Partial pre-header -- RECOVERED", "%d/10" % got)   # the next command gets Report T
                        MQ_TO_IDLE(MQ, recovered=True)
                        continue
                    for i in r1:
                        pre[i] = pre_raw[i]

                    # ─── Issue #14: signal READY before Z80's status-read poll ────
                    # The PIO drops Y to 0 on every Z80 OUT (per the issue-#14
                    # `mov(y, null)` in TS_IO_DUAL's z80_out path). By the time
                    # this for-loop finishes, Y has been dropped 10 times and is
                    # currently BUSY. The Z80 has finished its pre-header OUTs
                    # and is now in WAIT EXECUTION polling $0F bit 6, expecting
                    # to read the V6 pre-load 0x01 (already sitting in TX from
                    # the previous command's tail, or from the boot pre-load
                    # for the very first command). Without an explicit MQ_READY
                    # here the Z80 polls $0F for ~700ms with bit 6 = 0, times
                    # out → Report J → aborts before sending the command body.
                    # The pre-load byte sits in TX never to be read.
                    #
                    # EXCEPT for LOAD (issue #51): LOAD_TS says READY itself, once
                    # the block's first bytes are queued. The ROM reads the pre-load
                    # status with no wait, then waits for READY and reads the flag
                    # at once -- READY here, before LOAD_TS has queued anything,
                    # raced LOAD_TS's start (TLM print, watchdog thread, file seek,
                    # any gc) against the ROM's ~88 ms poll. Losing it hands the ROM
                    # 0x00 from an empty TX for the flag: Report R, the ROM stops
                    # reading, and the Pico waits on a full TX for the watchdog.
                    # Seen on hardware after a BREAK. The ROM's ready-wait allows
                    # ~20 s, so saying READY later costs nothing.
                    #
                    # And SAVE (stage 3): the Z80 streams the 21-byte header block,
                    # ~43 us a byte into a 4-deep RX FIFO, the moment it sees READY
                    # -- while this loop was still logging and SAVE_TS was still in
                    # its TLM print and gc.collect(). SAVE_TS says READY straight
                    # before its capture loop.
                    # ──────────────────────────────────────────────────────────────
                    # Printer text still in RAM: put it on the SD card now, while this
                    # command's Z80 is parked in its READY wait (it read its pre-load
                    # status straight after the pre-header; give it a moment, and put
                    # the status back if the SD access wiped it unread).
                    if PRT.buf and not (pre[0] == PRE_CMD and pre[1] in (4, 5, 6)):     # 66 'B'; 4-6 printer
                        _unread = not PRELOAD_READ()
                        PRINT_FLUSH()
                        if _unread:
                            MQ.put(0x01)
                    # ─── No early READY for ANY LOAD/SAVE pre-header ───────────────
                    # LOAD_TS / SAVE_TS raise READY themselves once the first bytes
                    # are queued (#64): READY before that lets the Z80 read an empty
                    # TX as 00 -- Report R, seen on hardware after a BREAK. This test
                    # used to be `not ((pre[0] == 0 or pre[0] == 255) and pre[1] < 10)`,
                    # Ryan's "for simplicity" split of LOAD by pre[1] (TADDR). A
                    # headerless LOAD -- machine code calling LD-BYTES, with whatever
                    # TADDR held, often >= 10 -- fell outside it and still got the
                    # early READY, though it goes to the very same LOAD_SERVE. Now
                    # every flag-00/FF pre-header is left to its handler, as are
                    # commands and the printer (42h). (2026-09-30 audit.)
                    # ──────────────────────────────────────────────────────────────
                    if pre[0] not in (PRE_HEADER, PRE_DATA, PRE_CMD):   # 0, 255, 66: LOAD/SAVE, commands, printer: the handler says READY
                        MQ_READY()

                    # Snapshot pre[] for any later TLM that wants to print it.
                    # Cheap when TLM_ENABLED=False (the TLM() calls below no-op
                    # and this list construction is the only residual overhead;
                    # ~10us at most, well outside the hot RX-drain path).
                    _pre_snapshot = list(pre)
                                                                                                              # pre(header)[0] is a command
                    # gc.collect()
                    # gc.mem_free() walks the whole heap: 3.1 ms on the Pico, paid on
                    # every transaction -- every LPRINT / LLIST character -- for a
                    # line only kept at LOG_LEVEL 0. Only then.
                    if TSP.LOG_LEVEL == 0:
                        LOG("Top of main loop, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)

                    if pre[0] == PRE_HEADER and pre[1] == 0:                                                  # 0, 0: pre[1] specifies which: if 0 -> SAVE   
                        LOG("Starting SAVE TS", 0)
                
                        led.value(1)

                        # Don't start a SAVE while core1 is writing the log to flash:
                        # the flash write stops both cores, and the header and data
                        # blocks that follow arrive with no flow control. Bounded --
                        # see WAIT_CORE1 for why this is no longer `while busy: pass`.
                        # The Z80 waits ~20 s for READY here, so 3 s is safe.
                        WAIT_CORE1(3000, "SAVE")

                        # The card first, before SAVE_TS says READY for the header: a
                        # SAVE with no card (or one pulled since the last command) is
                        # refused at the header, before the 2068 sends any data, and the
                        # program stays in its memory. Without this the save said "0 OK"
                        # and the write failed after it, silently. The Z80 is waiting
                        # for READY (Y BUSY) meanwhile; one mount costs ~0.1-0.3 s.
                        # SD_PROBE rebuilds the bus state machine, which empties
                        # TX: let the Z80 read its pre-load status first, as
                        # PRINT_FLUSH's caller does, and put it back if not.
                        # On hardware the Z80 reads it microseconds after the
                        # pre-header; in the emulator (tools/emu) every port
                        # access is a round trip and it lost: SAVE gave up on
                        # its header (2026-10-04).
                        _unread = not PRELOAD_READ()
                        TSP.save_no_card = not SD_PROBE()
                        if _unread:
                            MQ.put(0x01)
                        if TSP.save_no_card:
                            LOG("SAVE: no SD card; refused", 1)

                        # Save some state for possible restoration
                        pf_name = TSP.f_name
                        pappend = TSP.append
                        pidx = TSP.tap_idx
                        # SAVE_TS changes TSP.f_name to the new file name if append is False 

                        MQ, TSP, new_logs, saved = SAVE_TS(MQ, TSP, pre)
                        TSP.save_no_card = False
                        # log_entries += new_logs
                        # log_entries.extend(new_logs) # For when SAVE_TS returns an array
                        log_entries.append(new_logs) # For when SAVE_TS returns as one string as now
                        # `saved` comes straight from SAVE_TS: True only if a .tap
                        # actually reached the card. This used to be
                        #     save_aborted = "sd" not in os.listdir("/")
                        # i.e. reading the mount table to guess whether a file had
                        # been written. That guess is right for the refusal paths
                        # only by accident (they return before ENA_SD, so /sd is
                        # still unmounted), and it is WRONG for the case that
                        # matters most: a write that fails after ENA_SD -- card
                        # pulled, disk full -- where /sd IS mounted, no file exists,
                        # and the block below would go on to mount a ghost.

                        # ─── DUAL-PORT MIGRATION: explicit SD-teardown ────────────
                        # SAVE_TS may leave /sd mounted; ACTIVATE_MQ no longer
                        # unmounts it, so we do it here. See stage-3 comments
                        # on ACTIVATE_MQ for the rationale.
                        # ──────────────────────────────────────────────────────────
                        DEACTIVATE_SD()

                        # ─── ARM EXACTLY ONCE, AFTER ALL SD WORK ──────────────────
                        # This used to do ACTIVATE_MQ() + MQ.put(0x01) + MQ_READY()
                        # RIGHT HERE, and then fall into the `saved`
                        # block below, which calls MOUNT_FILE (-> ACTIVATE_SD) and
                        # ACTIVATE_SD + DIR_FILES before arming a SECOND time.
                        #
                        # That told the 2068 "ready, status waiting" and then spent
                        # hundreds of milliseconds on the SD card. ACTIVATE_SD grabs
                        # GPIO 2-4 for SPI -- the same pins the PIO drives D0-D2 on
                        # -- so it is exactly the pin-grab race #40 fixed inside
                        # SAVE_TS, reintroduced one level up. And the second
                        # ACTIVATE_MQ() builds a fresh StateMachine, so a next
                        # command that started during that window had the SM torn
                        # down underneath it mid-transaction.
                        #
                        # The 2068 prints "0 OK" and returns to the prompt while we
                        # are still doing this work, so the window is genuinely
                        # reachable by a fast typist or a running program.
                        #
                        # Now: all SD work first, then arm once at the bottom. Y
                        # stays BUSY throughout, which is precisely what $0F is for.
                        # ──────────────────────────────────────────────────────────
                        if saved:

                            # Handle re-mounting an appended file, possibly mounting a
                            # new file, or restoring the mounted file's name. Then
                            # update the directory list with changes.

                            # MOUNT_FILE raises when the card has stopped answering
                            # (ACTIVATE_SD gives up). This is the dispatcher, not a
                            # PROCESS_CMD handler, so nothing above would catch it
                            # and it would end TS2068_IO. The SAVE itself already
                            # reached the card; log and fall through to the re-arm.
                            sd_gone = False
                            try:
                                if getattr(TSP, "native_saved", False):
                                    # SAVE "f:..." wrote a native file (SAVE_TS): the mount,
                                    # its position and append are untouched.
                                    TSP.native_saved = False
                                    TSP.f_name = pf_name
                                    LOG("Saved a native file; mount unchanged", 0)
                                elif pappend:
                                    # We will re-mount the updated tap from SD for the user to
                                    # see the addition (other original content is the same)
                                    if MOUNT_FILE(TSP.f_name, True):
                                        # Restore the previous index that got reset on mount
                                        TSP.append = True
                                        TSP.tap_idx = pidx
                                        TSP.offset = TSP.offset_tbl[TSP.tap_idx][0]
                                        LOG("Re-mounted appended file: %s" % TSP.f_name, 0)
                                    else:
                                        LOG("Re-mount appended file failed", 2)
                                    # ACTIVATE_MQ()

                                elif not pf_name:

                                    # No file mounted before                        
                                    if TSP.f_name:
                                        # SAVE_TS saved saved a new file.
                                        # Mount new saved file if no file was already mounted, but
                                        # we don't set append on.
                                        if MOUNT_FILE(TSP.f_name, True):
                                            LOG("Mounted new file: %s" % TSP.f_name, 0)
                                        else:
                                            LOG("Re-mount failed for: %s" % TSP.f_name, 2)
                                        # ACTIVATE_MQ()
                        
                                elif TSP.f_name == pf_name:
                                    # This overwrote tap file that was mounted. The original
                                    # copy is still mounted, and the new tap on SD will only 
                                    # contain the one new saved file. You could turn on append,
                                    # and this will get re-mounted with the original content lost.
                                    LOG("Append is off. Overwrote mounted tap on SD but no re-mount.", 0)

                                else:
                                    # Saved to a new file while one is mounted with append off.
                                    LOG("Append is off. Saved to new file: %s" % TSP.f_name, 0)
                                    # Put mounted file name back as we continue using it
                                    TSP.f_name = pf_name
                            except Exception as e:
                                LOG("Re-mount after save failed: %s" % e, 2)
                                sd_gone = True

                            # Update the directory list with the changes
                            # (skipped if the re-mount just watched the card fail:
                            # another 5 attempts would only push the Z80 toward J)
                            if not sd_gone:
                                try:
                                    ACTIVATE_SD()
                                    os.chdir(TSP.cur_path) # MOUNT_FILE doesn't set this
                                    LOG("os.chdir to:" + TSP.cur_path, 0) # debug
                                    try:
                                        if DIR_FILES():
                                            LOG("DIR_FILES OK", 0) # debug
                                    except:
                                        LOG("DIR_FILES failed after save", 2)
                                except Exception as e:
                                    LOG("SD refresh failed after save: %s" % e, 2)

                            # ─── DUAL-PORT MIGRATION: pair with DEACTIVATE_SD ─────
                            # /sd was just mounted via ACTIVATE_SD above for the
                            # DIR refresh; tear it down before reactivating MQ.
                            # ──────────────────────────────────────────────────────
                            DEACTIVATE_SD()

                        # Single arm point for BOTH outcomes (saved or aborted), and
                        # the first moment in this branch that no further SD access
                        # is pending. ACTIVATE_MQ leaves Y=BUSY, so the order is
                        # fixed: rebuild the SM, stage the status byte the next
                        # pre-header phase will read, and only then signal ready --
                        # READY + idle, or RECOVERED when SAVE_TS gave up on a Z80
                        # that went silent mid-transfer (the 1.8b ROM reports T).
                        ACTIVATE_MQ()
                        MQ.put(0x01)
                        MQ_STATUS(MQ, "recovered" if getattr(TSP, "save_recovered", False) else "idle")

                        led.value(0)
                
                    elif (pre[0] == PRE_HEADER or pre[0] == PRE_DATA) and pre[1] < 10:  # 0 / 255: for simplicity if 0 < pre[1] < 10: call LOAD routine
                        TLM("LVM LOAD enter", "pre=%s f_name=%s tap_idx=%d offset=%d" % (
                            _pre_snapshot, TSP.f_name, TSP.tap_idx, TSP.offset))
                        LOG("Starting TS LVM", 0)

                        # Same reason as SAVE above: a log write on core1 would stop
                        # both cores while LOAD_TS streams a block the Z80 reads with
                        # no handshake (a byte every ~50 us). Bounded; the Z80 waits
                        # ~20 s for READY at this point.
                        WAIT_CORE1(3000, "LOAD")
                        MQ, TSP, new_logs = LOAD_SERVE(pre, MQ, TSP)
                        # log_entries += new_logs
                        log_entries.append(new_logs) # for now
                        # log_entries.extend(new_logs) # when LOAD_TS returns an array
                        TLM("LVM LOAD exit", "tap_idx=%d offset=%d" % (TSP.tap_idx, TSP.offset))

                    elif (pre[0] == PRE_HEADER or pre[0] == PRE_DATA):                                        # 0 / 255: Headerless LOAD
                        TLM("LVM Headerless LOAD enter", "pre=%s tap_idx=%d offset=%d" % (
                            _pre_snapshot, TSP.tap_idx, TSP.offset))
                        LOG("Starting TS LVM - Headerless LOAD", 0)

                        WAIT_CORE1(3000, "headerless LOAD")                     # as for LOAD above
                        MQ, TSP, new_logs = LOAD_SERVE(pre, MQ, TSP)
                        # log_entries += new_logs
                        log_entries.append(new_logs) # for now
                        # log_entries.extend(new_logs) # when LOAD_TS returns an array
                        TLM("LVM Headerless LOAD exit", "tap_idx=%d offset=%d" % (TSP.tap_idx, TSP.offset))

                    elif pre[0] == PRE_CMD and pre[1] in (4, 5, 6):                           # 66 'B': LPRINT / LLIST char, COPY
                        PRINT_IO(pre)

                    elif pre[0] == PRE_CMD:                                                   # 66 'B': a tpi: command

                        LOG("Starting TS COMMAND " + str(pre), 0)

                        try:
                            PROCESS_CMD(pre, SA_funct, EXT_SA_FUNCT)
                            TLM("main loop: PROCESS_CMD returned", "pre=%s" % _pre_snapshot)
                        except Exception as _e:
                            LOG("Invalid data received from PROCESS_CMD: " + str(pre), 2)
                            TLM("main loop: PROCESS_CMD raised exception", str(_e))
                            continue
                
                        if TSP.zx48:
                            if rxd is not None and rxd.armed:
                                rxd.stop()          # ZX48_IO reads RX by hand
                            ZX48_IO(pre)
                    
                    # ─── No 'A' (41h) branch any more ──────────────────────────────
                    # There was one: `elif pre[0] == 65:` ran PROCESS_ASM(pre) then
                    # DIR_FILES(), a placeholder for an "assembler command" block in
                    # Gustavo's design. No ROM sends 41h -- the EXROM's pre-header
                    # builder only does LD A,42h (docs/rom-analysis/
                    # PROTOCOL_FROM_ROM.md) -- and PROTOCOL.md calls it vestigial. If
                    # line noise ever produced one, the stub queued two bytes on top
                    # of the staged pre-load (an orphan byte for the next command) and
                    # listed the folder with /sd unmounted. A 41h now lands in the
                    # unrecognised branch below like any other unknown pre-header.
                    # Removed by the 2026-09-30 audit, with PROCESS_ASM.
                    # ──────────────────────────────────────────────────────────────
                    else:
                        try:
                            LOG("Unrecognized command! " + str(list(pre)), 1)
                        except:
                            LOG("Unrecognized command! Cannot get pre[] data", 1)

                        # ─── Back to a known state, WITH the pre-load staged ─────────
                        # This branch used to drain both FIFOs, restart the state
                        # machine and blink the LED for a second. That is Ryan's
                        # single-port recovery: his loop wrote a fresh 0x01 status at
                        # the top of every pass, so throwing TX away was safe. In the
                        # dual-port V6 chain the 0x01 the next command reads is staged
                        # ONCE, by whoever ran last -- so the drain left none, and the
                        # next command on a ROM without SYNC read 00: Report J
                        # (PROTOCOL.md 4.3 described exactly this). The 1 s BLINK_ERROR
                        # also blocked while the Z80 could already be sending its next
                        # pre-header. MQ_TO_IDLE (#51) is the bounded, standard way
                        # back: empty FIFOs, exactly one 0x01 staged, status RECOVERED
                        # -- the same as the partial-pre-header path above.
                        # (2026-09-30 audit.)
                        # ──────────────────────────────────────────────────────────────
                        MQ_TO_IDLE(MQ, recovered=True)

                    # ─── DUAL-PORT MIGRATION: bottom-of-loop drains REMOVED ───────
                    # Ryan's original code had defensive drains here ("clean up
                    # whatever the handler left behind"). In dual-port V6 those
                    # drains MASK bugs rather than fix them: each handler's V6
                    # tail must leave TX with exactly one 0x01 (the pre-load for
                    # the next command) and RX empty. If those invariants are
                    # ever violated, we want to see the resulting Report J/R
                    # immediately, not paper over it.
                    #
                    # If a bug ever causes orphan bytes here, you'll see the
                    # next command misbehave — which is the correct signal to
                    # go find the handler that didn't clean up after itself.
                    # ──────────────────────────────────────────────────────────────

                else:
                    # Nothing to do, so check if time to save the log
                    # ─── DUAL-PORT MIGRATION: use ticks_diff to handle wrap ──
                    # `time.ticks_us()` on rp2 wraps at 2**30 us (~17.9 min).
                    # Plain subtraction goes negative after wrap, satisfying
                    # both <2_000_000 and <2_100_000 conditions forever, so
                    # the loop spins in `continue` and the heartbeat never
                    # fires. User's reported "Pico halt with LED stopped
                    # blinking" was this — caught via Ctrl-C in Thonny
                    # showing the stuck line at the continue below.
                    # ────────────────────────────────────────────────────────
                    # Heartbeat: one 0.1 s flash every 2 s; with no SD card, two.
                    _hb = time.ticks_diff(time.ticks_us(), ts)
                    if _hb < 2_000_000:
                        continue
                    elif _hb < 2_100_000:
                        led.value(1)
                    elif not TSP.sd_present and _hb < 2_250_000:
                        led.value(0)
                    elif not TSP.sd_present and _hb < 2_350_000:
                        led.value(1)
                    else:
                        if log_entries:
                            if not busy:
                                # ─── DUAL-PORT MIGRATION: protect start_new_thread ─
                                # SAVE_LOG sets `busy = False` BEFORE the thread
                                # function actually returns, so core1 may still be
                                # mid-cleanup here. A second start_new_thread call
                                # in that window raises OSError "core1 in use".
                                # Catch it and skip — we'll save the log on the
                                # next idle pass once core1 is free.
                                #
                                # Without this guard, the OSError propagates up
                                # through TS2068_IO to main.py (which has no
                                # try/except) and drops the Pico to a REPL —
                                # manifests as "Pico locked up, LED stops
                                # blinking." Painful to diagnose.
                                # ──────────────────────────────────────────────────
                                # ─── DUAL-PORT MIGRATION: gc.collect REMOVED here ─
                                # Previous code did LOG + gc.collect + LOG before
                                # starting the SAVE_LOG thread. MicroPython's
                                # gc.collect() is a stop-the-world operation that
                                # routinely takes 10-100ms. During that pause, the
                                # 2068 can send the entire next-command pre-header
                                # (10 bytes in ~300us) — the 4-deep PIO RX FIFO
                                # fills, and `push noblock` silently drops bytes
                                # 4-9. When the main loop resumes, it reads 4 stale
                                # pre-header bytes + 6 body bytes, producing a
                                # malformed pre-header (decoded body-length of
                                # 28791 etc.) and a J error on the 2068. Diagnosed
                                # via trace showing pre=[66, 0, 255, 2, 'D', 7, 0,
                                # 't', 'p', 'i'] for a SAVE "tpi:dir" — body bytes
                                # leaked into the pre-header read.
                                #
                                # MicroPython's automatic GC runs when allocations
                                # require it; no need to force it here. SAVE_LOG
                                # on core1 can do its own gc.collect if memory
                                # pressure becomes an issue inside the thread.
                                # ──────────────────────────────────────────────────
                                # `busy` goes True HERE, on core0, before the thread
                                # starts -- not only inside SAVE_LOG. Otherwise there
                                # is a window between start_new_thread returning and
                                # core1 reaching SAVE_LOG's first line in which `busy`
                                # is still False: a SAVE or LOAD that arrived in that
                                # window would see core1 idle and start its transfer
                                # just as the flash write begins. If the thread can't
                                # be started (core1 still in use), nothing will clear
                                # `busy` for us, so we clear it ourselves.
                                busy = True
                                try:
                                    _thread.start_new_thread(SAVE_LOG, ())
                                except OSError:
                                    busy = False

                        # Host text the firmware never reads fills MicroPython's
                        # stdin buffer, and then Ctrl-C can't get in (see
                        # DRAIN_STDIN). Keep it empty while idle.
                        DRAIN_STDIN(MQ)
                        led.value(0)
                        ts = time.ticks_us()
        except Exception as err:
            now = time.ticks_ms()
            failures = [f for f in failures if time.ticks_diff(now, f) < 60_000]
            failures.append(now)
            LOG("Unexpected error; restarting the service loop (%d in the last minute): %r"
                % (len(failures), err), 2)
            pe = getattr(sys, "print_exception", None)               # MicroPython's traceback printer
            if pe:
                try:
                    with open("/activity.log", "a") as f:
                        pe(err, f)
                except Exception:
                    pass
            SAVE_LOG()
            if len(failures) >= 3:
                raise
            if rxd is not None and rxd.armed:
                rxd.stop()                  # re-armed at the top of the loop
            if sd_active:
                DEACTIVATE_SD()
            ACTIVATE_MQ()
            MQ_TO_IDLE(MQ, recovered=True)
            TSP.zx48 = False
            ts = time.ticks_us()
                

# The ZX v3 ROM raises the report whose ERR_NR it is sent; FFh is 0 OK.
ZX_REPORT = {_1_OK: 0xFF, _2_R_Tape_load: 0x1A, _3_F_Invalid_file: 0x0E,
             _4_Q_Parameter: 0x19}


def ZX_TPI():
    """LOAD "tpi:<name>" in ZX48 mode -- the ZX v3 ROM's 'T' command, which
    ZX48_IO has taken. Returns nxt, as LOAD_ZX.

    The ROM (src/rom/patches/tspico-zx48-v3.asm) waits for READY, then
    sends op (0 SAVE, 1 LOAD, 2 VERIFY, 3 MERGE), the length and the name
    after "tpi:", ~54 us a byte. It waits up to ~30 s for READY again
    (BREAK gives Report D), then reads a status -- FFh OK, else a report
    code -- the message length and the message, which it prints.

    LOAD (.tap files only), and from the ZX v4 ROM SAVE "tpi:dir [arg]";
    the rest of the tpi: commands need the TS-2068 ROM. Every wait is
    bounded; nothing here blocks on the bus.

    v4 ROM (op with bit 7 set): the reply after the status is pieces -- a
    length 1-255, that many bytes, ... -- ended by a 0, so a folder listing
    fits. v3 (bit 7 clear): one length and at most 200 bytes, as before.
    """
    global MQ

    hdr = bytearray(2)
    name = bytearray(255)
    gc.collect()                            # before READY: the name streams with no handshake
    if tspico_io._ring is not None:
        # By DMA: op, length and name in ONE run (RX_RING's len_at), not two
        # -- the name's first bytes overflowed the FIFO while a second run was
        # set up (Report J, hardware 2026-10-03).
        both = bytearray(257)
        code, got = tspico_io.RX_RING(tspico_io._ring, MQ, both, False, 257,
                                      ZX_STALL_MS, ZX_STALL_MS, 1, "ready")
        hdr[:] = both[:2]
        name[:] = both[2:]
    else:
        MQX(MQ, "mov(y, invert(null))")     # READY: listening
        code, got = RX_BLOCK(MQ, hdr, 2, ZX_STALL_MS, ZX_STALL_MS)
        if code == RXB_OK:
            code, got = RX_BLOCK(MQ, name, hdr[1], ZX_STALL_MS, ZX_STALL_MS)
    if code != RXB_OK:
        LOG("ZX tpi: command stopped after %d bytes" % got, 2)
        return -1                           # the ROM gives up: Report J (or D)

    rest = "".join(chr(b) for b in name[:hdr[1]] if 0x20 <= b < 0x7F)
    pieces = hdr[0] & 0x80                  # the v4 ROM: the reply in pieces
    op = hdr[0] & 0x7F
    TLM("ZX_TPI", "op=%d%s name=%r" % (op, " (v4)" if pieces else "", rest))
    word = rest.lower()
    listing = None
    stall = ZX_STALL_MS
    if op == 0 and (word == "dir" or word.startswith("dir ")):
        if not pieces:
            msg, rest, st = 'SAVE "tpi:dir" needs ZX ROM v4', "", _4_Q_Parameter
        else:
            if getattr(TSP, "listing_stale", False):
                REFRESH_LISTING()
            try:
                ACTIVATE_SD()
                try:
                    text, st = CATALOG_TEXT(rest[3:].strip())
                finally:
                    DEACTIVATE_SD()
                    ACTIVATE_MQ()
            except OSError as e:
                LOG("ZX tpi:dir: SD card error: %s" % e, 2)
                text, st = "SD card error", _3_F_Invalid_file
            if st == _1_OK:
                listing = CAT_COLOUR(text)  # CAT's look: the Spectrum has the same colour codes
                stall = CMD_STALL_MS        # its "scroll?" waits for the user; a new command ends it
            msg, rest = text, ""
    elif op != 1:
        msg, rest, st = 'Only LOAD "tpi:..." and SAVE "tpi:dir" in ZX48 mode', "", _4_Q_Parameter
    else:
        if getattr(TSP, "listing_stale", False):        # a ZX SAVE added a file: LOAD_TPI matches names in it
            REFRESH_LISTING()
        msg, rest, st = LOAD_TPI(rest, only_tap=True)   # may use the SD card: MQ is rebuilt
    if listing is not None:
        text = bytes(b if b < 0x80 else 0x3F for b in listing.encode())
        LOG("ZX48 tpi:dir: %d bytes" % len(text), 0)
    else:
        text = (msg.strip() + " " + rest).strip().encode()[:200]
        LOG("ZX48 tpi: %s" % text.decode(), 0 if st == _1_OK else 2)

    # The reply: status, then (v3) the length and the message, or (v4) the
    # message in pieces of up to 255 and a 0. The first bytes go in before
    # READY -- the ROM reads the instant it sees it -- the rest as it reads.
    if pieces:
        k = (len(text) + 254) // 255
        out = bytearray(1 + len(text) + k + 1)
        j = 1
        for i in range(0, len(text), 255):
            part = text[i:i + 255]
            out[j] = len(part)
            out[j + 1:j + 1 + len(part)] = part
            j += 1 + len(part)
        out[j] = 0
    else:
        out = bytearray(2 + len(text))
        out[1] = len(text)
        out[2:] = text
    out[0] = ZX_REPORT.get(st, 0x19)
    ZX_FLUSH_TX(MQ)
    gc.collect()
    n = len(out)
    # By DMA where there is one, READY once the channel runs: the ROM reads
    # the moment it sees READY, blind.
    r = STREAM_DMA(MQ, out, None, stall, True)
    if r is not None:
        if r[0]:
            w = r[2] if r[0] == 4 else -2
            ZX_FLUSH_TX(MQ)
            LOG("ZX tpi: reply stopped at byte %d of %d" % (r[1], n), 2)
            return w if w >= 0 else -1
        return -1
    i = 0
    while i < len(out) and MQ.tx_fifo() < TX_DEPTH:
        MQ.put(out[i])
        i += 1
    MQX(MQ, "mov(y, invert(null))")         # READY: the reply is waiting
    # The ROM reads the rest blind, one byte every ~45 us (TPI_DLY), so this
    # loop has to stay ahead of it. ZX_ROOM only when the FIFO is full, as
    # LOAD_ZX does: calling it for every byte cost ~20 us a byte on
    # MicroPython v1.20 but ~49 us on v1.29 (function calls and ticks_ms got
    # slower), so on v1.29 the FIFO ran dry and the mount message came out
    # garbled (hardware, 2026-10-02; src/test/mp_timing_bench.py). This
    # shape is ~9 us a byte on both.
    txf = MQ.tx_fifo
    put = MQ.put
    while i < n:
        if txf() >= TX_DEPTH:
            w = ZX_ROOM(MQ, stall)
            if w != -1:
                ZX_FLUSH_TX(MQ)
                LOG("ZX tpi: reply stopped at byte %d of %d" % (i, n), 2)
                return w if w >= 0 else -1
        put(out[i])
        i += 1
    return -1


def ZX48_IO(pre):                                                                   # Main IO loop, for SAVE, LOAD and commands processing
                                                                                    # ZX Spectrum mode
    global MQ                                                                                    
    global TSP
    global log_entries
    global led
    
    led.value(0)
    
    par1, par2 = PARAMS(pre)

    # ─── DUAL-PORT MIGRATION: ZX48_IO SM creation ─────────────────────────
    # Same change as ACTIVATE_MQ: TS_IO -> TS_IO_DUAL, 15 MHz -> 30 MHz,
    # add Y=READY initialization after activation. Without this, ZX
    # Spectrum mode would NameError on TS_IO (we removed that import in
    # stage 1) and even if imported wouldn't work because of the bus
    # protocol mismatch.
    # ─────────────────────────────────────────────────────────────────────
    MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000, out_base=Pin(2, Pin.OUT), in_base=Pin(2, Pin.IN), jmp_pin=Pin(11), sideset_base=Pin(12, Pin.OUT))
    MQ.active(0)

    utime.sleep(0.01)
    MQ.active(1)
    MQX(MQ, "mov(y, invert(null))")    # Y = READY for the entire ZX session

    TLM("ZX48_IO enter", "par1=%d par2=%d ZX_TAPE_COMPAT=%s" % (
        par1, par2, TSP.ZX_TAPE_COMPAT))
    LOG("Starting ZX Mode...", 0)

    ts = time.ticks_us()
    nxt = -1        # a command byte a handler took in the middle of its block

    while True:

        if nxt >= 0 or MQ.rx_fifo():

            ts = time.ticks_us()
            if nxt >= 0:
                a, nxt = nxt, -1
            else:
                a = MQ.get()
            TLM("ZX48_IO byte received", "a=%d (0x%02X)" % (a, a))

            # Wait (bounded) for a SAVE_LOG still writing the log on core1:
            # a flash write stops both cores, so it must not overlap a block.
            # The ZX v2 ROM waits up to ~3.8 s for READY after its 'L' / 'S'.
            # The handlers themselves use no core1 watchdog (issue #51).
            _t = time.ticks_ms()
            while busy:
                if time.ticks_diff(time.ticks_ms(), _t) >= 3000:
                    LOG("ZX48_IO gave up waiting for core1", 2)
                    break

            if a == 76:                                                    # ASCII 'L' - for LOAD

                TLM("ZX48_IO dispatching LOAD")

                if TSP.ZX_TAPE_COMPAT:                                      # compatible-mode ZX Spectrum LOAD

                    if par2 >= 16384:
                        buf_size = par2
                        LOG("ZX48 buffer size = %d" % par2, 0)
                    else:
                        buf_size = 52100                                          # lower this if mem allocation error arises
                    MQ, TSP, new_logs, nxt = LOAD_ZX_C(MQ, TSP, buf_size)
                else:
                    # 'regular' ZX Spectrum LOAD
                    LOG("Starting ZX LOAD", 0)
                    MQ, TSP, new_logs, nxt = LOAD_ZX(MQ, TSP)
                if new_logs.strip():
                    log_entries.append(new_logs)

                TLM("ZX48_IO LOAD returned")

            elif a == 83:                                                  # ASCII 'S' - for SAVE

                TLM("ZX48_IO dispatching SAVE")
                LOG("Starting ZX SAVE", 0)
                MQ, TSP, new_logs, nxt = SAVE_ZX(MQ, TSP)
                if new_logs:
                    log_entries.append(new_logs)
                TLM("ZX48_IO SAVE returned")

            elif a == 84:                                                  # ASCII 'T' - LOAD "tpi:..." (ZX v3 ROM)

                TLM("ZX48_IO dispatching tpi:")
                nxt = ZX_TPI()

            elif a == 14:                                                  # OUT 14,14 from 2068 — canonical exit from ZX48 mode
                # ─── ZX48 exit-via-byte ───────────────────────────────────
                # The user exits ZX48 mode from the 2068 with `OUT 14,14`.
                #
                # Why port 14: post dual-port migration the PIO only listens
                # on ports $0E (decimal 14) and $0F (decimal 15). Before the
                # migration the single-port PIO picked up writes on ports
                # 0–15, so the original guard was `a == 100` (`OUT 10,100`).
                # That stopped working once the dual-port PIO landed because
                # port $0A is no longer routed to the RX FIFO. Switching the
                # 2068-side command to `OUT 14,14` puts the byte on a port
                # the Pico actually listens to.
                #
                # Why the value 14 specifically: it's arbitrary — any byte
                # other than the ones the SAVE/LOAD branches above already
                # claim (`a == 76` for 'L', `a == 83` for 'S') would work.
                # We picked 14 to match the port and keep the BASIC line
                # easy to remember (`OUT 14,14`).
                #
                # Clearing TSP.zx48 releases the re-entry guard in
                # TS2068_IO so the main loop resumes TS-2068 mode cleanly
                # on the next iteration.
                # ──────────────────────────────────────────────────────────
                TLM("ZX48_IO byte 14 received — exiting ZX48 mode")
                LOG("Ending ZX mode. Free mem: %d. Returning to TS processing." % gc.mem_free(), 0)
                gc.collect()
                TSP.zx48 = False

                break

            else:
                TLM("ZX48_IO unrecognized byte — draining FIFOs and continuing", "a=%d" % a)
                LOG("Unrecognized ZX command", 1)
                # ─── DUAL-PORT MIGRATION: inline FIFO drains ──────────────
                while MQ.rx_fifo() != 0:
                    MQ.get()
                while MQ.tx_fifo() != 0:
                    MQX(MQ, "pull (noblock)")
                    MQX(MQ, "mov (osr, null)")
                MQ.active(0)
                utime.sleep(.01)
                MQ.active(1)

                LOG("Cleared TX/RX FIFO after unrecognized ZX command: %d %d" % (MQ.tx_fifo(), MQ.rx_fifo()), 0)

        else:
            # ─── DUAL-PORT MIGRATION: use ticks_diff to handle wrap (same
            # fix as TS2068_IO's main idle loop) ─────────────────────────
            # Heartbeat: one 0.1 s flash every 2 s; with no SD card, two.
            _hb = time.ticks_diff(time.ticks_us(), ts)
            if _hb < 2_000_000:
                continue
            elif _hb < 2_100_000:
                led.value(1)
            elif not TSP.sd_present and _hb < 2_250_000:
                led.value(0)
            elif not TSP.sd_present and _hb < 2_350_000:
                led.value(1)
            else:

                if log_entries:
                    SAVE_LOG()
                    # log_entries = [] # SAVE does this
                    
                DRAIN_STDIN(MQ)                                     # Ctrl-C stays reachable (see TS2068_IO)
                led.value(0)
                ts = time.ticks_us()

    # Leaving ZX48 mode with bytes still in TX: a ZX LOAD that stopped before
    # the end of what was queued (the ROM asked for fewer bytes than the
    # block holds, or the user broke in). Seen on hardware 2026-10-02 (tx=4
    # at the exit). Empty it, or the 2068 ROM's next status read would get
    # one of them. (Ricardo's fix, 21 Aug 2025; the audit thought it
    # obsolete after #52, but that only fixed one cause.)
    if MQ.tx_fifo() != 0:
        print("MQ FIFO: ", MQ.tx_fifo())
        LOG("TX FIFO not empty after ZX mode. Trying to force cleanup", 1)

        # ─── DUAL-PORT MIGRATION: inline TX drain ─────────────────────────
        while MQ.tx_fifo() != 0:
            MQX(MQ, "pull (noblock)")
            MQX(MQ, "mov (osr, null)")

        MQ.active(0)
        utime.sleep(.01)
        MQ.active(1)

        LOG("TX FIFO succesfully cleared before returning from ZX mode", 0)

    else:
        LOG("Returning from ZX mode; TX FIFO is empty: ", 0)

    TLM("ZX48_IO exit", "TSP.zx48=%s" % TSP.zx48)
