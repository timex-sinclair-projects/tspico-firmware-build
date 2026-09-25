#################################
# DATE: 2026/04/15              #
# FIRMWARE VERSION: 1.5         #
# ROM: 1.5W                     #
# DEPENDS: tspico_upgrade.py    #
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
    patch, sel_bank, set_ctrl, set_dck,
    TS_IO_DUAL,                          # was: TS_IO (single-port)
    LOAD_TS, LOAD_ZX, LOAD_ZX_C,
    SAVE_TS, SAVE_ZX,
    CORE1_BUSY,                          # core1 flag lives in tspico_io, not here
    OPEN_NOFILE_TAP,                     # added: cached nofile handle
)

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

# Build version stamp — bumped on each mpy rebuild so we can confirm
# at a glance which build is actually loaded on the Pico. Logged at
# LOAD_CONFIG entry and via __init__-time print so it appears even
# before TLM is enabled.
BUILD_VERSION = "2026-05-27-J (inline-wrt SEND_MSG2 + suppress_scroll<500)"
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
    dt = (now - _tlm_last) if _tlm_last else 0
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
        err_msg = "d"                                                                                
        err_st = 10
        
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
        try:                                                                    # try to retrieve configuration values from init_values passed on startup
            self.FW_VERSION = init_values["FW_VERSION"]                         # Current firmware version.
        except:                                                                 # if fail, assume hard-wired values
            self.FW_VERSION = "Unknown"
        try:                                                                    # try to retrieve configuration values from init_values passed on startup
            self.ROM_VERSION = init_values["ROM_VERSION"]                       # Current ROM version.
        except:                                                                 # if fail, assume hard-wired values
            self.ROM_VERSION = "1.0"
        try:                                                                    # try to retrieve configuration values from init_values passed on startup
            self.ZX_TAPE_COMPAT = init_values["ZX_TAPE_COMPAT"]                 # boolean for ZX Spectrum "compatible" tape routine (True) or normal (False)
        except:                                                                 # if fail, assume hard-wired values
            self.ZX_TAPE_COMPAT = False

        self.bank_sm = (self.DCK_SLOT * 16) + self.ROM_SLOT                    # bit pattern to store slot of DCK/ROM. 4 bits each. Default 0001 0000
        self.dck_prev_slot = self.DCK_SLOT
        self.dck_prev_mem  = 2


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

    # GPIO 2-4 are shared with SPI (SCK/MOSI/MISO). Drive them LOW
    # before the PIO state machine reclaims them. This is the Report D
    # fix from the dual-port migration.
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
#   3. Y = READY after activation
#      The new line `MQ.exec("mov(y, invert(null))")` sets Y to
#      0xFFFFFFFF so $0F reads always have bit 6 set (= ready).
#      We keep Y at READY for the entire session; the protocol's
#      natural pacing via TX FIFO depth handles flow control.
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
#
# The `ready=True` parameter is for the rare path that needs to
# create the SM but defer activation (currently unused but kept for
# parity with our reference implementation).
# ───────────────────────────────────────────────────────────────────────
def ACTIVATE_MQ(ready=True):                                                                      # Re-enable TX/RX SM, after a SDCard access (DUAL-PORT)

    global MQ

    TLM("ACTIVATE_MQ enter", "ready=%s" % ready)
    MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000, out_base=Pin(2, Pin.OUT),
                      in_base=Pin(2, Pin.IN), jmp_pin=Pin(11),
                      sideset_base=Pin(12, Pin.OUT))

    if ready:
        MQ.active(1)
        # ─── DUAL-PORT MIGRATION: Y stays at BUSY here ──────────────────
        # We INTENTIONALLY do NOT set Y=READY in this function. Caller
        # MUST load any response bytes into TX and then call MQ_READY()
        # to signal ready, in that order.
        #
        # The old behavior was:
        #     MQ.exec("mov(y, invert(null))")    # Y=READY immediately
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
    else:
        TLM("ACTIVATE_MQ exit", "SM created but NOT active")

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
    # sm.exec() in MicroPython v1.20.0 — confirmed by REPL test.
    MQ.exec("mov(y, invert(null))")


def MQ_BUSY():
    """Signal 'not ready' to Z80 — bit 6 clear on $0F reads (Y = 0).

    With the issue-#14 PIO auto-busy, MQ_BUSY is rarely needed
    explicitly — the PIO drops Y to 0 on every Z80 OUT. Kept for:
      - ACTIVATE_MQ initialization (ensures known state at boot).
      - Code paths that want to assert BUSY without an inbound write
        (e.g., signalling an aborted exchange or a long-pause
        background operation).
    """
    MQ.exec("set(y, 0)")


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


def ACTIVATE_SD():                                                                              # Enable SD-Card access SM, after TX/RX operation

    global MQ

    TLM("ACTIVATE_SD enter")
    MQ = StateMachine(0, NULL_SM, freq=15_000_000)
    MQ.active(1)
    MQ.active(0)

    U3_CS       = Pin(28, Pin.OUT, Pin.PULL_UP)
    D0          = Pin(2,  Pin.IN)
    D1          = Pin(3,  Pin.IN)
    D2          = Pin(4,  Pin.IN)

    try:
        spi = SPI(0, sck=D0, mosi=D1, miso=D2)
        sd = SDCard(spi, U3_CS)
        os.mount(sd, "/sd")
        TLM("ACTIVATE_SD exit", "SD mounted at /sd")

    except Exception as e:
        TLM("ACTIVATE_SD FAILED — entering BLINK_ERROR loop")
        LOG(f"Mounting SD Card failed in ACTIVATE_SD! {e}", 2)
        SAVE_LOG()
        spi = -99

        while True:
            BLINK_ERROR()

    return spi


def BLINK_ERROR():                                                             # An onboard LED-blinking routine. This for an error condition. Interval is fixed

    global led
    
    led.value(1)

    for i in range(10):
        utime.sleep(.1)
        led.toggle()
    
    led.value(0)
        
    return


def BLINK_LED(pause):                                                           # Another routine that ...well...blinks the onboard LED!
                                                                                # Used by the COPY_FILE routine
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


def CHK_STATUS(secs):                                                                                 # Watchdog that executes on the second thread, 
                                                                                                      # and kills the IO routine if needed.
    global MQ                                                                                                      
                                                                                                      
    global kill
    global dead
    global busy
    
    global led
    
    kill = False
    busy = True
    
    LOG("Starting watchdog...", 0)
    secs = secs * 1_000_000
    
    t_init = time.ticks_us()
    # ─── DUAL-PORT MIGRATION: use ticks_diff to handle 30-bit wrap ───────
    # `time.ticks_us()` on rp2 wraps at 2**30 us (~17.9 min). Plain
    # subtraction goes negative after wrap (negative < secs → True → spin
    # forever). ticks_diff() handles wrap correctly.
    # ─────────────────────────────────────────────────────────────────────
    while time.ticks_diff(time.ticks_us(), t_init) < secs:
        if dead:
            break
    if not dead:
        LOG("Abnormal termination. Clearing TX/RX FIFO....", 2)
        while not dead:
            MQ.exec("pull (noblock)")
            MQ.exec("mov (osr, null)")
            MQ.exec("mov (isr, null)")
            MQ.exec("push (noblock)")
            kill = True
             
        # ─── DUAL-PORT MIGRATION: inline FIFO drains ──────────────────────
        while MQ.rx_fifo() != 0:
            MQ.get()
        while MQ.tx_fifo() != 0:
            MQ.exec("pull (noblock)")
            MQ.exec("mov (osr, null)")
        MQ.active(0)

        LOG("TX/RX FIFO successfully cleared. Operation finished", 0)
        
        BLINK_ERROR()
        
        MQ.active(1)
        
        LOG("Ending watchdog. Operation ended normally", 0)
        
    kill = False
    busy = False
    
    return


def COPY_FILE(src_file, dst_file):                                                          # Copy the large .TAP file to Pico's internal flash
                                                                                             # best compatibility and performance
    global dead
    global busy
    global led
    
    dead = False
    
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
    dead = True
    
    del buf                                                                             # OPTIMIZATION - CHECK!       
    gc.collect()
    
    while busy:
        pass
    
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


def DIR_FILES():                                                                             # Get all files and directories from current path
    
    global files
    global dirs
    global lista
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
    
    ext = ['TAP', 'TZX', 'DCK', 'ROM', 'BIN']                                                 # extensions to be included
    starts = ['.']                                                                            # first characters of files to be excluded
    
    ordered = True                                                                            # In the future, this could be controlled by an option

    # ─── DUAL-PORT MIGRATION: remove stale dirinfo.tap before listing ─────
    # dirinfo.tap is a synthetic TAP file DIR_FILES writes at the end of
    # this function (containing the directory listing in a format the 2068
    # can LOAD). Without removing the PREVIOUS one before listing the
    # directory, os.ilistdir() picks it up and adds it to the files[] and
    # lista listings sent to the 2068. End-user sees dirinfo.tap as if it
    # were a real file they put there. (Was uncommented in production
    # TS/tspico.py line 758-761; was commented out in Ryan's version,
    # causing the visibility bug reported during picotest's directory
    # listing tests.)
    # ─────────────────────────────────────────────────────────────────────
    try:
        os.remove("dirinfo.tap")
    except:
        pass

    if ordered:
        listing = sorted(os.ilistdir(), key=lambda fname: fname[0].lower())
    else:
        listing = [item for item in os.ilistdir()]
    
    nom = bytearray(32)
    
    for archs in listing:
        if archs[1] == 16384:
            dirs.append(archs[0])
            dirs_upper.append(archs[0].upper())
            nom = shorten_filename(archs[0].replace("~", "?"), 20)
            dirinfo.append("%-32s" %  nom)
            L.append("<%-21s       0 B" % (nom + ">"))

    num_dirs = len(dirinfo)
    i = 0
    
    for archs in listing:
        if archs[1] == 32768:
            if (archs[0][-3:].upper() not in ext) or (archs[0][0] in starts):
                continue
            files.append(archs[0])
            files_upper.append(archs[0].upper())
            
            size = int(archs[3])
            if size >= 1024:
                size = size >> 10
                size_txt = "%.2f kB" % size
            else:
                size_txt = "%d B" % size

            nom = "%03d %-18s%10s" % (i, shorten_filename(archs[0].replace("~", "?"), 18), size_txt)
            L.append(nom)
            dirinfo.append(nom)

            i += 1
    
    del listing

    sd_block = os.statvfs("")[0]
    sd_tot   = os.statvfs("")[2]
    sd_free  = os.statvfs("")[3]
    sd_free  = (sd_free * sd_block) / 1_073_741_824
    sd_tot   = (sd_tot  * sd_block) / 1_073_741_824
    sd_stat  = "SD: %02.4fGB; free: %02.4fGB" % (sd_tot, sd_free)

    header = "Path:%-27s%-32sFile Name                   Size--------------------------------" % (public_path(27), sd_stat[:32])
    
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
    
    if TSP.LOG_LEVEL:                                                                    # TSP is not initialized at startup, so this check is required
        if level < TSP.LOG_LEVEL:
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
    
    U3_CS = Pin(28, Pin.OUT, Pin.PULL_UP)
    U3_CS.value(1)
    
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
                
                file_type = f_check.read(7)
                if file_type.decode() == "ZXTape!":
                    msg = "Wrong file type while mounting: %s. It's a TZX file" % f_name
                    err_level = 2
                    
                if ((int(file_type[0]) > 19)):
                    msg = "Non-standard first block while mounting file %s. Expected 19, read %d" % (f_name, int(file_type[0]))
                
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
    TSP.offset_tbl = []
    TSP.offset = 0
    TSP.tap_idx = 0
    # Get file size
    arch.seek(0,2)
    fsize = arch.tell()
    arch.seek(0,0)
    
    blks = ['Program', 'Number arr.', 'Char arr.', 'Code blk']
    
    while TSP.offset < fsize:
        rd_bytes = bytearray(30)
        arch.seek(TSP.offset)
        arch.readinto(rd_bytes)
        long = rd_bytes[0] + (256*rd_bytes[1])
        
        code_blk = rd_bytes[2]

        if (code_blk == 0):
            hdr = " Y"
            try:
                name_raw = rd_bytes[4:14].decode()
                name = ''.join(' ' if ((ord(l) <= 30) or (ord(l) >= 127)) else l for l in name_raw)
                blk_type = blks[rd_bytes[3]]
            except:
                name = "??????????"
                blk_type = "undefined"
        else:
            hdr = " N"
            name = blk_type
            
        values = [TSP.offset, long, hdr, name]
        TSP.offset_tbl.append(values)
            
        long += 2
        TSP.offset += long
    
    TSP.offset = 0
    if fsize > 0:
        del rd_bytes
    
    arch.close()
    gc.collect()
    
    return


def PARAMS(pre):
    """Returns calculated CODE parameters from pre-header."""

    par1 = (pre[4] << 8) | pre[3]
    par2 = (pre[6] << 8) | pre[5]
        
    return par1, par2


def SAVE_LOG():                                                                         # Saves log_entries to the 'activity.log' file in flash
    
    global busy
    global log_entries
    
    busy = True
    
    with open("/activity.log", "a") as logfile:
        for e in log_entries:
            logfile.write(e)
        # writelines doesn't add newlines, but our log strings already have them.
        
    log_entries = []
    
    busy = False

    return


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


def SEND_MSG(msg, msg1, st: bytes, forceDisplay=False):                                         # Sends one-line status message(s)
                                                                                                # back to the TS, once a command is finished
    global MQ
    global TSP

    wrt = MQ.put

    # ─── DUAL-PORT MIGRATION ──────────────────────────────────────────────
    # The two `wrt(0x40)` "Read continue flag" writes in the single-port
    # version have been removed. The continue flag now lives on $0F via
    # the Y register (kept at READY for the entire session). A 0x40 in
    # the TX FIFO would have been consumed by the Z80's $0E read as if
    # it were data — orphaning the rest of the response by one byte.
    #
    # `MQ_READY()` is called after the data is loaded as belt-and-
    # suspenders: in case any prior code path left Y at BUSY, this
    # guarantees $0F answers ready by the time the Z80 polls. With
    # current dual-port handlers Y stays at READY always, so MQ_READY()
    # here is functionally redundant but kept for self-documentation.
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
        wrt(0x81)               # PRINT STRING — this IS the D-block status
        wrt(st)                 # Return code
        wrt(0x0D)               # Start with a newline
        MQ_READY()              # Z80 starts reading the 3-byte header
        for m in msg:           # Write message (paced by Z80 reads)
            wrt(m) # Will let ~ and | pass as FREE and STICK
        if msg1:                # Write msg1
            wrt(0x0D)
            for m in msg1:
                wrt(m)
        wrt(0x00)               # End of string

    else:

        wrt(st)                 # Return code (< 0x80) — IS the D-block status
        MQ_READY()              # one-byte status is in TX; signal ready

    TLM("SEND_MSG enter+loaded", "msg=%r msg1=%r st=%d verbose=%s force=%s" % (
        msg[:30] if isinstance(msg, str) else msg, msg1, st, TSP.VERBOSE, forceDisplay))

    # ─── DUAL-PORT MIGRATION: inline drain (was WAIT_TX_RECEIVED) ─────────
    drain_loops = 0
    while MQ.tx_fifo() != 0:
        drain_loops += 1
        if drain_loops > 1000000:
            TLM("SEND_MSG STUCK", "tx still has %d bytes after 1M loops" % MQ.tx_fifo())
            break

    TLM("SEND_MSG exit", "drain_loops=%d" % drain_loops)
    return


def SEND_MSG2(msg, st: bytes, expandKeywords = True):                                         # Sends a SCROLLING status message back to the TS,
                                                                                              # once a command is finished
    # msg: a string of the message (no bytearrays)
    # st:  report status

    global MQ
    global TSP
    
    global kill
    global dead

    TLM("SEND_MSG2 enter", "msg_len=%d st=%d expand=%s rom_ver=%s" % (
        len(msg), st, expandKeywords, TSP.ROM_VERSION))

    if TSP.ROM_VERSION == "1.0":
        new_rom = False
        end_char = 0x00
    else:
        new_rom = True
        end_char = 0x03

    scroll = "Scroll? (Y/n)"

    s = len(scroll) + 6
    n = len(msg)

    # ─── Inline-wrt SEND_MSG2 + suppress_scroll for short messages ────────
    # Confirmed by regression test: the buffer-prebuild + preload-then-
    # MQ_READY refactor caused `tpi:help border` to consistently fail,
    # even though both patterns place the same 4 header bytes in TX at
    # the moment Y=READY fires. The original inline-wrt pattern (bytes
    # go directly to TX as the per-char loop produces them) handles
    # border correctly, so we're back to that.
    #
    # We keep suppress_scroll for short messages (<500 chars) so that
    # picotest's auto-runner doesn't hang on the "Scroll? (Y/n)" prompt
    # — there's no user to press a key, and the 2068 ROM's $86 handler
    # doesn't reliably auto-N for short outputs. For long outputs that
    # would overflow the screen, the prompt still fires.
    # ─────────────────────────────────────────────────────────────────────
    SCROLL_THRESHOLD = 500
    suppress_scroll = (n < SCROLL_THRESHOLD)

    wrt = MQ.put

    # Write the 4 header bytes directly to TX, then set Y=READY.
    # FIFO is 4-deep so this fills it; MQ_READY immediately after means
    # Z80's first $0E read finds a real byte.
    wrt(0x86)   # PRINT_STRING_WITH_LOOP (this IS the D-block status)
    wrt(st)     # BASIC return code
    wrt(0x0D)   # Start on a new line
    wrt(0x0D)   # Start with a blank line we don't count

    MQ_READY()
    while MQ.rx_fifo() != 0:    # Flush any stray keystrokes
        MQ.get()

    TLM("SEND_MSG2 inline-wrt start", "header+MQ_READY done")

    if not new_rom:
        wrt(0x0D)   # Another newline for old ROM

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
                if ch == 124:
                    c += 6
                elif ch == 126:
                    c += 7
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

        if c == 32:

            l += 1
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

            if not suppress_scroll and l == ll and (not new_rom or n > i + 34):
                # Scroll-prompt path (inline-wrt style).
                l = 0
                if not new_rom and i == n - 1:
                    scroll_str = "--- End of list (N to exit) ---"
                else:
                    scroll_str = scroll
                    for m in "(%2d%%) " % ((i * 100) // n):
                        wrt(ord(m))
                for m in scroll_str:
                    wrt(ord(m))
                if not new_rom:
                    wrt(13)
                wrt(0x00)       # end of this page
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

                ch = MQ.get()   # wait for keypress (PIO auto-drops Y on Z80 OUT)
                if ch == 78:    # 'N' → done. Z80 exits 0x86 without bit-6 check
                    MQ_READY()  # restore Y for downstream reads (V6 pre-load)
                    return
                if ch == 48:
                    ll = 10
                elif ch >= 49 and ch <= 57:
                    ll = ch - 48
                else:
                    ll = 21

                # Re-assert Y=READY immediately before the next-page
                # writes so the Z80's wait_bit6 finds bit 6 = 1 the
                # moment we start pushing erase-prompt bytes.
                MQ_READY()
                if new_rom:
                    for _eb in range(s):
                        wrt(0x08)
                        wrt(0x20)
                        wrt(0x08)
                else:
                    wrt(0x0D)

    wrt(end_char)
    TLM("SEND_MSG2 end_char written", "0x%02X" % end_char)

    # ─── DUAL-PORT MIGRATION: inline drain (was WAIT_TX_RECEIVED) ─────────
    drain_loops = 0
    while MQ.tx_fifo() != 0:
        drain_loops += 1
        if drain_loops > 1000000:
            TLM("SEND_MSG2 STUCK", "tx still has %d after 1M loops" % MQ.tx_fifo())
            break

    rx_drained = 0
    while(MQ.rx_fifo() != 0):   # Flush input buffer to console
        b = MQ.get()
        rx_drained += 1
        print(b)

    TLM("SEND_MSG2 exit", "drain_loops=%d rx_drained=%d tx=%d rx=%d" % (
        drain_loops, rx_drained, MQ.tx_fifo(), MQ.rx_fifo()))


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

    global lista
    global led
    global files

    par1, par2 = PARAMS(pre)

    TLM("DIR enter", "par1=%d par2=%d files=%d lista_len=%d" % (
        par1, par2, len(files), len(lista)))

    if par1 == 0:
        # Regular listing
        TLM("DIR par1=0 — regular listing via SEND_MSG2")
        led.value(1)
        SEND_MSG2(lista, 1, False)
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
        M = ["Path:%s\r" % public_path(27)]
        M.append("  #  File Name         %3d files" % n)
        M.append("---- ---------------------------")
        for f in range(par2, n):
            M.append(">%03d %s\r" % (idx, files[f]))
            idx += 1
        msg = "".join(M)
        SEND_MSG2(msg, 1)
        led.value(0)

    else:
        msg = BAD_CODE("DIR", par1, par2)
        LOG(msg, 2)
        SEND_MSG(msg, "", _8_A_Invalid_arg)
  
    return


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


def ListMenu(List, hdr1, hdr2, hdr3, action, chosen):

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
    # Removed leading EMPTY_RX_FIFO() — at this point the Z80 hasn't been
    # told to read yet, so RX has nothing in it. We drain RX AFTER setting
    # ready (Z80 may then dump stale keystrokes from prior input).
    #
    # Removed wrt(0x40) "Read continue" from start of every loop iteration
    # — the continue flag now lives on $0F via Y register (kept at READY
    # for the entire session by MQ_READY() below).
    # ─────────────────────────────────────────────────────────────────────
    wrt = MQ.put
    Init = True
    sel = -1
    pgs = (n - 1) // nmax + 1

    MQ_READY()                          # Y = READY → $0F polls succeed

    while MQ.rx_fifo() != 0:            # Drain any pre-existing keystrokes
        MQ.get()

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
        wrt(0x86)                       # PRINT_STRING_WITH_LOOP function code
        wrt(1)                          # status: no error
        wrt(0x0D)
        wrt(0x0D)
        for m in hdr1:
            wrt(m)
        wrt(0x0D)
        for m in "(no items available)":
            wrt(m)
        wrt(0x03)                       # end of loop (no scroll, no keypress)
        while MQ.tx_fifo() != 0:
            pass
        while MQ.rx_fifo() != 0:
            MQ.get()
        return -1

    while idx < n:
        i = 0
        # Write screen

        if Init:
            wrt(0x86)   # PRINT STRING WITH LOOP — this IS the D-block status
            wrt(1)      # BASIC return code
            Init = False
        else:
            wrt(ch)     # Show previous choice
        wrt(0x0D)
        wrt(0x0D)
        for m in hdr1:
            wrt(m)
        wrt(0x0D)
        pg = "%d of %d" % (idx // nmax + 1, pgs)
        for m in "%-24s%8s\r" % (hdr2, pg):
            wrt(m)
        for m in hdr3:
            wrt(m)
        wrt(0x0D)
        while i < nmax and idx + i < n:
            x = letters[i]
            wrt(x)
            wrt(0x20)
            for m in List[idx+i]:
                wrt(m)
            wrt(0x0D)
            i += 1
        j = i
        while i < nmax:
            wrt(0x0D)
            i += 1
        a = (idx * 32 / n + 0.5) // 1
        for k in range(a):
            wrt('-')
        w = (j * 32 / n + 0.5) // 1
        for k in range(w):
            wrt('=')
        for k in range(32 - a - w):
            wrt('-')
        wrt(0x0D)
        for m in prompt1:
            wrt(m)
        wrt(x)
        for m in prompt2:
            wrt(m)
            
        wrt(0x00)       # End of this string (Z80 displays + waits for key)
        # ─── Issue #14: 0x86 bit-6 ack (PIO auto-busy variant) ────────
        # PIO drops Y to 0 automatically when the Z80 writes the
        # keypress (its OUT $0E). MQ.get() returns with us already in
        # BUSY state. Re-assert MQ_READY() before the next wrt for
        # both branches: the navigation paths fall through to the
        # next `while idx < n` iteration which redraws, and the
        # selection path writes the echo + erase bytes.
        # ──────────────────────────────────────────────────────────────
        ch = MQ.get()   # Get a key (PIO auto-drops Y on Z80 OUT)
        if ch == 78:    # 'N' then done (ROM ended the loops)
            MQ_READY()  # restore Y for downstream reads
            return -1
        MQ_READY()      # Y → READY before any next-iteration / echo write
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
            
    wrt(0x03) # End string loop
    # ─── DUAL-PORT MIGRATION: inline tail drains ──────────────────────────
    while MQ.tx_fifo() != 0:
        pass
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

                for el in TSP.offset_tbl:

                    if idx >= idx1 and idx <= idx2:

                        if el[2] == " Y" or idx == TSP.tap_idx:

                            # Block number
                            if idx == TSP.tap_idx:
                                N.append(">")
                            else:
                                N.append(" ")
                            N.append("%02d " % idx)
                            if el[2] == " Y":
                                N.append("%-11s %5s " % (TSP.offset_tbl[idx+1][3], TSP.offset_tbl[idx+1][1])) # File type, Len
                            else:
                                N.append("Data block  %5s " % el[1]) # Len
                            N.append("%-10s" % el[3]) # Desc.
                    
                    idx += 1
                    
        nom = "".join(N)

    SEND_MSG2(nom, _1_OK)

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

    # Make new empty .tap file
    ACTIVATE_SD()
    try:
        with open(filename, "w") as newfile:
            pass
        LOG("New empty file:%s" % filename, 0)
        os.chdir(TSP.cur_path)
        DIR_FILES()
        # ─── DUAL-PORT MIGRATION: pair with DEACTIVATE_SD ─────────────────
        DEACTIVATE_SD()
        ACTIVATE_MQ()
    except:
        # ─── DUAL-PORT MIGRATION: pair with DEACTIVATE_SD ─────────────────
        DEACTIVATE_SD()
        ACTIVATE_MQ()
        msg = "Can't create new file: "
        LOG(msg + filename, 2)
        SEND_MSG(msg, filename, _4_Q_Parameter)
        return

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
    """Expand or replace character"""
    ch = ord(m)
    if ch < 32 or ch > 127:
        return '?' # Replace control code or high-ASCII
    elif ch == 124: # tilde
        return ' STICK '
    elif ch == 126: # vert. bar
        return ' FREE '
    else:
        return m


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
    
    led.value(1)
    
    if TSP.f_name[-4:].upper() == ".DCK":

        # ─── DUAL-PORT MIGRATION: status + MQ_READY (was wrt(0x40); wrt(status)) ──
        wrt(status)
        MQ_READY()

        try:
            
            with open("/TMP/temp.bin", "rb") as file:
                
                r = range(65536 // _BUFSZ)
                for i in r:
                    n = file.readinto(buf)
                    for i in range(n):
                        wrt(mv[i])
        
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
            
            num_blk = send_len // _BUFSZ
                             
            with open("/TMP/temp.bin", "rb") as file:
                file.seek(rd_offset)
                
                for i in range(num_blk):
                    n = file.readinto(buf)
                
                    for i in range(n):
                        wrt(mv[i])
                            
                n = file.readinto(buf, send_len % _BUFSZ)
                
                for i in range(n):
                    wrt(mv[i])
                            
            del buf
            del mv
            
            # gc.collect()
            
        led.value(0)
    
    return


def ChangeDir(potential_new_path, SDactive = False):

    global TSP
    global MQ

    TLM("ChangeDir enter", "path=%r SDactive=%s" % (potential_new_path, SDactive))
    status = _1_OK
    if not SDactive:
        ACTIVATE_SD()
    npath = "%s/%s" % (TSP.cur_path, potential_new_path)

    if potential_new_path == ".." and TSP.cur_path.count("/") > 2:
        # remove the last element from the current path
        # unless the last element is TAP
        #print("attempt to move up one directory")
        path_list = list(TSP.cur_path.split("/"))       # convert current path to a list
        path_list.pop(0)  # remove the first element, which is blank
        path_list.pop()   # remove the last element
        new_path = "/".join(path_list)
        
    elif (potential_new_path == ".." and TSP.cur_path.count("/") == 2) or potential_new_path == "/" or potential_new_path.lower() == "/tap":
        new_path = "/sd/TAP"
        
    elif potential_new_path[0:5].lower() == "/tap/":
        new_path = "/sd" + potential_new_path

    elif dir_exists(npath):
        new_path = npath
        
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
        isel = ListMenu(List, hdr1, hdr2, hdr3, "Change to dir", "Changing dir to: ")
        if isel >= 0:
            status, message = ChangeDir(List[isel])
        led.value(0)
        return

    status, message = ChangeDir(potential_new_path)

    if status == 1 and par1 == 1 and par2 <= 2:
        if par2 == 0:
            SEND_MSG2(lista, _1_OK, False)
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
                            msg = help.read()
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
        M.append('"tpi:rompatch"')
        M.append('"tpi:tapdir"[CODE 0/1,n]')
        M.append('"tpi:tape"    <=>   "tpi:sdcard"')
        M.append('"tpi:ts2040"  <=>   "tpi:picopt"')
        M.append('"tpi:upgrade"')
        M.append('"tpi:verbose"[CODE 1,0/1]')
        M.append('"tpi:verbose on/off"')
        M.append('"tpi:zx48"[CODE 0/1,0/1/2/n]')
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


def GETINFO(pre, cmd):                                                 # Shows TS-Pico internal status

    global TSP
    global files
    global lista
    
    cop = chr(127)
    nl = chr(13)
    
    fl_block = os.statvfs("")[0]
    fl_tot = os.statvfs("")[2]
    fl_free = os.statvfs("")[3]

    fl_free = (fl_free * fl_block) / 1_048_576
    fl_tot = (fl_tot * fl_block) / 1_048_576
    
    M     = ["  * TS-Pico interface status *", nl]
    M.append(" %s 2023, 2024 TS Pico Dev Team\r" % cop)
    M.append("--------------------------------")
    M.append(">FW Rev.:%s; uPython: 1.20.0\r" % TSP.FW_VERSION)
    M.append(">Default ROM version: %s\r" % TSP.ROM_VERSION)
    M.append(">Board Rev.: V2.2; Log level:%d\r" % TSP.LOG_LEVEL)
    M.append(">Pico Free RAM: %06.2fkB\r" % (gc.mem_free() >> 10))
    M.append(">Flash: %02.2fMB; free: %02.2fMB\r" % (fl_tot, fl_free))
    M.append(">%s\r" % lista[32:63]) # sd_stat
    mem, page = getBoot()
    M.append(">Boot: %d,%d" % (mem, page))
    mem, page = getDock()
    M.append(";     Dock: %d,%d\r" % (mem, page))
    M.append(">Append: %s; Verbose: %s\r" % (str(TSP.append), str(TSP.VERBOSE)))
    M.append(">Mounted file: ")
    
    if not TSP.f_name:
        M.append("%s\r" % "none")
    else:
        M.append("%s\r" % public_fname())
        if isTapMounted():
            i = TSP.tap_idx
            M.append(">Block:%02d" % i)
            if TSP.offset_tbl:
                blk = TSP.offset_tbl[i]
                if blk[2] == " Y":
                    M.append(":%s:%s" % (blk[3], TSP.offset_tbl[i+1][3]))
                else:
                    M.append(":Data block:%s" % blk[3])
            else:
                M.append(":<empty>")
            M.append(nl)
    
    M.append(">Current path: %s\r" % public_path())
    M.append(">Files in dir: %d\r" % len(files))
    msg = "".join(M)
    SEND_MSG2(msg, _1_OK)

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

    try:
        msg = bytearray(len_read)

        with open(log_fname, "r") as logfile:
            
            if file_seek:
                logfile.seek(file_seek)
                
            logfile.readinto(msg)

        SEND_MSG2(msg.decode('utf-8'), 1) # Convert bytes to string

    except:
        msg = "Log file too large"
        LOG(msg, 2)
        SEND_MSG(msg, "", _4_Q_Parameter)

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
    default_values["FW_VERSION"] = "Unknown"
    default_values["ZX_TAPE_COMPAT"] = False                   # Use regular tape load routine in zx48 mode
    default_values["FW_VERSION"] = "1.00"
    default_values["ROM_VERSION"] = "1.00"
    # Fill any missing values with the default
    for key, value in default_values.items():
        if key not in init_values:
            init_values[key] = default_values[key]
            defaulted = True
        
    if (init_values["ROM_SM"] <= 4) or (init_values["ROM_SM"] in [8, 12]):
        init_values["ROM_SM"] = default_values["ROM_SM"]
        LOG("Incorrect initial ROM_SM value. Using default value of %d instead" % default_values["ROM_SM"], 2)

    return_ROM_SLOT = -1
    if init_values["ROM_SLOT"] != default_values["ROM_SLOT"]:           # If we started with a non-default ROM slot, we use it on this run,
                                                                        # but reverse back to default hard-wired 1 for next boot (after power-cycle the Pico)
        return_ROM_SLOT = init_values["ROM_SLOT"]                                                                       
        init_values["ROM_SLOT"] = default_values["ROM_SLOT"]
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

    elif (par1 == 0 or par1 > 3 or par2 > 15):
        msg = "Wrong values, %s" % new
        SEND_MSG(msg, "OK values: MEM=1..3, PAGE=0..15", _8_A_Invalid_arg)
        LOG("BOOT: %s. Command ignored" % msg, 1) 
    else:            
        val1 = TSP.ROM_SM & 12
        TSP.ROM_SM = val1 + par1
        
        val1 = TSP.bank_sm & 240
        TSP.bank_sm = val1 + par2
        
        with open("config.ini", "r") as f:                                                    # As sometimes this change can hang the machine,
            init_values = json.load(f)                                                        # we modify the init values for next startup
                                                                                              # so changes will take effect next reboot
        init_values["ROM_SLOT"] = par2
        
        with open("config.ini", "w") as f:
            json.dump(init_values, f)
            
        msg = 'Change ROM to %s' % new
        SEND_MSG(msg, "", _1_OK)
        LOG(msg, 0)
        
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


def MEMDOCK(pre, cmd):                                                   # Changes DCK slot; either SRAM or Flash

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

    
def ROMPATCH(pre, cmd):                                                                                      # Patch for system ROM
    
    global TSP
    global led
    
    # was /TS/rompatch.tap; moved to /assets/ during dual-port migration
    # to avoid being shadowed by the frozen TS/ package.
    TLM("ROMPATCH enter")
    if MOUNT_FILE("/assets/rompatch.tap"):
        # ACTIVATE_MQ()
        SEND_MSG("System prepared to patch ROM.", 'Use LOAD "" to start.', _1_OK)
    else:
        SEND_MSG("Failed to mount rompatch.tap", "", _2_R_Tape_load)

    return


def ResolveIndexName(name):

    # name, found = ResolveIndexName(name)
    # If name is a file index reference, a number within the range of files, 
    # then resolve it to the actual name. If the name is not an index, the index
    # is not found, or the file is not found, the given name is returned as-is.

    global TSP
    global files

    try:
        index = int(name)
        if index < len(files):
            return files[index], index
    except:
        pass

    return name, -1


def SEND_MSG_PROMPT_YN(prompt, echo = True):

    # Prints prompt string, waits for a character and returns that char
    # Assumes MQ is active. This cannot be followed by another SEND_MSG* call.

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
    wrt = MQ.put
    wrt(0x86)   # PRINT STRING WITH LOOP — this IS the D-block status
    wrt(0x01)   # BASIC return code
    wrt(0x0D)   # Start a new line
    MQ_READY()  # Z80 sees "ready" on $0F → starts reading bytes from $0E

    while MQ.rx_fifo() != 0:    # Flush any stray keystrokes
        MQ.get()

    for ch in prompt:
        wrt(ch)
    wrt(0x00)   # End string (Z80 prints + waits for key)
    # ─── Issue #14: 0x86 bit-6 ack (PIO auto-busy variant) ───────────────
    # PIO drops Y to 0 automatically on the Z80's keypress OUT, so by
    # the time MQ.get() returns we're already BUSY. Re-assert MQ_READY()
    # before pushing the echo + 0x03 so the Z80's wait_bit6 exits with
    # real bytes ready to read.
    # ──────────────────────────────────────────────────────────────────────

    ch = MQ.get()       # PIO auto-drops Y on Z80 OUT (keypress)
    MQ_READY()          # both branches need Y=READY for downstream reads
    if ch != 78: # 'N' causes the ROM to end the string loop and any exchange
        if echo:
            if ch < 32 or ch > 127:
                wrt(89) # Y
            else:
                wrt(ch)
        wrt(0x03) # End the string loop
        # Could add an option to not wrt(0x03) and let the caller do that after
        # writing some more text to indicate the result of the action.

        # ─── DUAL-PORT MIGRATION: inline drains ───────────────────────
        while MQ.tx_fifo() != 0:
            pass
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
    
    # Remove a named file or directory (combine RM and RMDIR, act based on type)
    # Assumes file/dir to remove is in TSP.cur_path
    # SAVE "tpi:rm <name>"            - Remove file or empty folder
    # SAVE "tpi:rm <name>" CODE 255,0 - Bypass confirmation prompt

    global TSP
    global dirs_upper
    global files_upper
    global alldirs
    
    TLM("RM enter")
    name = cmd[10:]
    status = _1_OK
    message = ""
    sent = False
    par1, par2 = PARAMS(pre)

    name, idx = ResolveIndexName(name)
    uname = name.upper()
    adir  = uname in dirs_upper
    afile = uname in files_upper

    if not name:
        message = "RM: Filename required"
        status = _8_A_Invalid_arg
        LOG(message, 2)

    elif not adir and not afile:

        message = "RM: File not found: "
        status = _3_F_Invalid_file
        LOG(message + name, 2)

    else:

        if par1 == 0 and par2 == 0:

            sent = True
            ch = SEND_MSG_PROMPT_YN('Remove "%s" (y/N)?' % name)
            if ch != 89: # 89='Y'
                LOG("%s not removed from %s" % (name, TSP.cur_path), 0)
                return

        elif par1 != 255 or par2 != 0:
            message = BAD_CODE("RM", par1, par2)
            LOG(message, 2)
            SEND_MSG(message, "", _8_A_Invalid_arg)
            return
            
        ACTIVATE_SD()
        os.chdir(TSP.cur_path)

        if adir:
            kind = "dir"
            # Remove a dirinfo.tap if it exists since it is not visible to the user
            # and prevents os.rmdir from working. We could later add a CODE 255,255
            # option to force removal of a non-empty dir and call REMOVE_DIR.
            try:
                os.remove(name + "/dirinfo.tap")
            except:
                pass
        else:
            kind = "file"

        try:
            if adir:
                os.rmdir(name)
                # Update alldirs w/o calling GET_DIRS()
                try:
                    alldirs.remove("%s/%s" % (TSP.cur_path[3:], name))
                except:
                    pass
            else:
                os.remove(name)
            DIR_FILES() # Update local files list
            # gc.collect()
            message = "Removed %s: " % kind
            LOG(message + name, 0)

        except OSError:

            message = "OS error removing: "
            status = _4_Q_Parameter
            LOG(message + name, 2)

        # ─── DUAL-PORT MIGRATION: pair with DEACTIVATE_SD ─────────────────
        DEACTIVATE_SD()
        ACTIVATE_MQ()

    if not sent:
        SEND_MSG(message, name, status)
    
    return 
                

def SYS_CMD(pre, cmd):                                                                                      # Various system cmds
    
    global led
    global patch
    
    TLM("SYS_CMD enter")
    par1, par2 = PARAMS(pre)
    
    if par1 == 1 and par2 == 0:                                                                           # CODE 1,0 -> Retrieve ROM patch from firmware
        SEND_MSG("SYS CMD finished OK", "", _1_OK)
        LOG("Received SYS CMD 1,0 - Patch update", 0)
        
        led.value(1)

        for i in patch:
            MQ.put(i)
            
        with open("/config.ini", "r") as f:
            init_values = json.load(f)

        init_values["ROM_VERSION"] = "1.2"
        
        with open("/config.ini", "w") as f:
            json.dump(init_values, f)
            
        led.value(0)
        
    else:
        SEND_MSG("Error! Undefined SYS CMD", "", _5_C_Nonsense)
        LOG("Wrong syntax SYS CMD", 2)
        SAVE_LOG()
        
        while True:
            BLINK_ERROR()
        
    led.value(0)
    UNMOUNT(pre, cmd)
    
    return


def UNMOUNT(pre, cmd):                                                                                       # Unmount currently mounted file 
    
    global TSP
    
    TLM("UNMOUNT enter")
    SEND_MSG("Unmounting file. ", "", _1_OK)
    
    TSP.f_name = ""
    TSP.offset_tbl = []
    TSP.offset = 0
    TSP.tap_idx = 0
    TSP.append = False
    
    try:
        os.remove("/TMP/temp.bin")    
        os.remove("/TMP/temp.tap")    
    except:
        pass
    
    return 


def UPGRADE(pre, cmd):
    """Wrapper that lazily imports and calls the upgrade module to save memory."""
    global TSP
    from TS.tspico_upgrade import UPGRADE as _UPGRADE
    _UPGRADE(pre, cmd)


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
    M.append('Use "OUT 244,3" to switch to the')
    M.append('Spectrum ROM. To return to Timex')
    M.append('mode, do OUT 244,0 then OUT 14,14')
    M.append('to exit ZX48 mode and resume normal')
    M.append('TS-Pico operation.')
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


def PRINT_IO(pre):                                                                                                           # LPRINT and LLIST processing

    global MQ
    global TSP

    prn = bytearray(10000)
    end_msg = "File 0001.txt closed OK"
    r1 = range(10)
    wrt = MQ.put

    pos = 0
    while True:
        prn[pos] = pre[3]
        pos += 1

        # ─── DUAL-PORT MIGRATION ──────────────────────────────────────
        # Was:  wrt(0x40); wrt(0x01)
        # Now:  wrt(0x01); MQ_READY()
        # The 0x40 (continue) is no longer a FIFO byte — it's the Y
        # register signalled via MQ_READY(). The 0x01 is the status
        # the Z80 reads from $0E after seeing ready on $0F.
        # ──────────────────────────────────────────────────────────────
        wrt(0x01)
        MQ_READY()

        pre = [0] * 10
        for i in r1:
            pre[i] = MQ.get()
        if pre[1] != 5:
            break

    # ─── DUAL-PORT MIGRATION (loop exit, same pattern as in-loop) ─────
    wrt(0x01)
    MQ_READY()

    SEND_MSG(end_msg, "", _1_OK)

    # ─── DUAL-PORT MIGRATION: inline FIFO drains ──────────────────────
    # Replaces WAIT_TX_RECEIVED() and EMPTY_RX_FIFO() (single-port
    # helpers being retired in stage 7). Behavior is identical.
    # ──────────────────────────────────────────────────────────────────
    while MQ.tx_fifo() != 0:
        pass

    while MQ.rx_fifo() != 0:
        MQ.get()

    prn = prn[:pos]

    with open("/PRN/0001.txt", "w") as sal:                                           # PRINT output filename is fixed on this version; can be set up
            sal.write(prn)                                                            # in future version

    return


def PROCESS_ASM(pre):                                                                 # Processes AU (Assembler) commands sent by the TS

    global MQ

    cmd = pre[:5].decode()
    wrt = MQ.put

    # ─── DUAL-PORT MIGRATION: leading wrt(0x40) REMOVED ───────────────
    # Was the single-port "continue flag" byte indicating Pico is ready
    # to receive the command body. In dual-port the Z80 polls $0F (Y
    # register, kept at READY all session) for ready and reads $0E for
    # data — so the 0x40 in TX served no purpose and would have been
    # read by the Z80 as an unexpected data byte.
    # ──────────────────────────────────────────────────────────────────

    print(pre)
    print(cmd)

    par3 = int(pre[8])
    par4 = int(pre[9])

    print(par3, par4)

    # ─── DUAL-PORT MIGRATION: V6 tail (final status + pre-load) ───────
    # Was:  wrt(0x40); wrt(0x01)   (0x40 = continue flag, 0x01 = status)
    # Now:  wrt(0x01); wrt(0x01)
    #   - First 0x01: final status response for THIS command (Z80 reads
    #     as "0 OK" via $0E).
    #   - Second 0x01: pre-load for the NEXT command's initial status.
    #     This is the V6 chain that keeps back-to-back commands working
    #     without re-arming status in the main dispatcher.
    # The continue flag has moved off the FIFO entirely — Y register
    # stays at READY so $0F always answers ready.
    # ──────────────────────────────────────────────────────────────────
    wrt(0x01)        # final status — Z80 reads as "0 OK"
    wrt(0x01)        # pre-load for next command's initial status
    MQ_READY()       # #14: Y was dropped by Z80's command-body OUTs; restore

    return


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

    # Both loops are bounded. The equivalent drains elsewhere in this
    # file spin freely, which is fine on a healthy path -- but this is
    # the recovery path, and an unbounded loop here would be the very
    # hang we are trying to prevent. The FIFOs are 4 deep; anything
    # past a few iterations means the SM is not draining and spinning
    # will not help.
    for _ in range(64):
        if MQ.tx_fifo() == 0:
            break
        MQ.exec("pull (noblock)")
        MQ.exec("mov (osr, null)")
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
    cmd = bytearray(100)
    
    load_cmd = pre[1]

    long = pre[7] + 256*pre[8] + 3
    rl = range(long)

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

    for l in rl:
        start = time.ticks_ms()
        while MQ.rx_fifo() == 0:
            if time.ticks_diff(time.ticks_ms(), start) > BODY_READ_TIMEOUT_MS:
                TLM("PROCESS_CMD body-read timeout — aborting",
                    "byte=%d/%d (Z80 likely aborted after J at pre-header)" % (l, long))
                LOG("PROCESS_CMD body-read timeout at byte %d/%d" % (l, long), 2)
                # Drain any partial state so the next command starts clean
                while MQ.rx_fifo() != 0:
                    MQ.get()
                while MQ.tx_fifo() != 0:
                    pass
                # V6 pre-load so the next command's pre-header phase works
                MQ.put(0x01)
                MQ_READY()  # #14: Y was dropped by partial Z80 OUTs; restore
                return
        cmd[l] = MQ.get()

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
    cmd_exec = "?"        # the tail logs this; it must exist even when
                          # the decode below never gets to assign it

    try:
        try:
            cmd = cmd[:long].decode()
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

        if load_cmd:                                                                                    # Is it a "LOAD:tpi:..." command.....?

            if rest_cmd == "dirinfo.tap":
                if MOUNT_FILE("%s/dirinfo.tap" % TSP.cur_path):
                    msg = "Mounting dir info: "
                    status = _1_OK
                else:
                    msg = "Error mounting file: "
                    status = _2_R_Tape_load
                    LOG(msg + rest_cmd, 2)

                # ACTIVATE_MQ()
                SEND_MSG(msg, rest_cmd, status)

            else:
                rest_cmd, idx = ResolveIndexName(rest_cmd)
                if idx < 0:
                    if rest_cmd.upper() in files_upper:                                                                                  # Is rest_cmd a valid file?
                        idx = files_upper.index(rest_cmd.upper())

                if idx >= 0:
                
                    if MOUNT_FILE("%s/%s" % (TSP.cur_path, files[idx])):
                        msg = "File mounted OK"
                        status = _1_OK
                    else:
                        msg = "Error mounting file:"
                        status = _4_Q_Parameter
                    
                    # ACTIVATE_MQ()
                    SEND_MSG(msg, rest_cmd, status)
                
                else:
                    msg = "File does not exist: "
                    SEND_MSG(msg, rest_cmd, _3_F_Invalid_file)                                       # If none of the above, raise error
                    LOG(msg + rest_cmd, 2)
            
        else:                                                                                                 # ...or it's a "SAVE:tpi:..." command
            # Split command word from any arguments
            sp = cmd_exec.find(' ')
            if sp >= 0:
                cmd_word = cmd_exec[:sp]
                # cmd_args = cmd[sp+4:]
            else:
                cmd_word = cmd_exec
                # cmd_args = ""

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
        drain_tx = 0
        while MQ.tx_fifo() != 0:
            drain_tx += 1
            if drain_tx > 1000000:
                TLM("PROCESS_CMD STUCK draining tx", "tx=%d" % MQ.tx_fifo())
                break

        drain_rx = 0
        while MQ.rx_fifo() != 0:
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
        MQ_READY()

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
        "TPI:ROMPATCH" : ROMPATCH,
        "TPI:RM" : RM, # dir or file
        "TPI:SYS" : SYS_CMD,
        "TPI:NEWTAP" : NEW_TAP,
        "TPI:TAPDIR" : TAPDIR,
        "TPI:UPGRADE" : UPGRADE,
        "TPI:VERBOSE" : VERB_TOGGLE, 
        "TPI:ZX48" : ZX48,
        "TPI:AUTOLF" : SA_NOT_IMP,
        "TPI:AUTOPG" : SA_NOT_IMP,
        "TPI:BMP" : SA_NOT_IMP,
        "TPI:CLPRINT" : SA_NOT_IMP,
        "TPI:CONFIG" : SA_NOT_IMP,
        "TPI:DELETE" : SA_NOT_IMP,
        "TPI:FRESET" : SA_NOT_IMP,
        "TPI:GETCONFIG" : SA_NOT_IMP, 
        "TPI:LIST" : SA_NOT_IMP,
        "TPI:MEMINFO" : SA_NOT_IMP,
        "TPI:NOAUTOLF" : SA_NOT_IMP,
        "TPI:OPPRINT" : SA_NOT_IMP,
        "TPI:PRNSZ" : SA_NOT_IMP,
        "TPI:STOP" : SA_NOT_IMP,
        }
    
    # Imported external SA/LD commands or empty dictionary
    
    # LOG("After SA_funct setup, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)
    # gc.collect()
    # LOG("After gc.collect, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)

    # ─── DUAL-PORT MIGRATION: prefer dev_extcmd override if present ──────
    # The frozen TS/extcmd.py has a `from tspico import ...` line that
    # fails on the current module layout (helpers live in TS.tspico or
    # dev_tspico, not bare `tspico`). The fix lives in TS/extcmd.py on
    # this branch but needs a UF2 rebuild to take effect, since
    # TS/extcmd.py is frozen. The parallel /dev_extcmd.py on flash root
    # provides a dev-mode override (same pattern as dev_tspico.py
    # shadowing TS.tspico). Try the override first.
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

    ACTIVATE_SD()
    
    dead = True
    
    while busy:
        pass

    LOG("After ACTIVATE_SD, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)
    gc.collect()
    LOG("After gc.collect, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)
    alldirs = GET_DIRS()
    LOG("After GET_DIRS, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)
    gc.collect()
    LOG("After gc.collect, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)

    try:
        os.chdir(TSP.cur_path)
    except:
        LOG("Cannot mount /TAP directory; aborting.", 3)
        SAVE_LOG()
        
        while True:
            BLINK_ERROR()
            
    DIR_FILES()
    LOG("After DIR_FILES, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)
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

    LOG("SD Card initialized and mounted OK", 0)
    SAVE_LOG()

    wrt = MQ.put

    # ─── Boot-noise flush (Ryan's diagnostic loop, kept) ──────────────────
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

    LOG("Before main loop, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)
    gc.collect()
    LOG("After gc.collect, gc.memfree()=%.1f" % (gc.mem_free() >> 10), 0)

    LOG("TS Pico initialized OK. Waiting for commands...", 0)
    SAVE_LOG()
    
    led.value(0)

    pre = bytearray(10)
    r1 = range(10)

    ts = time.ticks_us()                                                                           # ts -> timestamp
    
    while True:                                                                                    # main execution loop

        if (MQ.rx_fifo()) != 0:

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
            for i in r1:
                pre[i] = MQ.get()                                          # blocking

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
            # ──────────────────────────────────────────────────────────────
            MQ_READY()

            # Snapshot pre[] for any later TLM that wants to print it.
            # Cheap when TLM_ENABLED=False (the TLM() calls below no-op
            # and this list construction is the only residual overhead;
            # ~10us at most, well outside the hot RX-drain path).
            _pre_snapshot = list(pre)
                                                                                                      # pre(header)[0] is a command
            # gc.collect()
            fr1 = gc.mem_free()
            LOG("Top of main loop, gc.memfree()=%.1f" % (fr1 >> 10), 0)

            if pre[0] == 0 and pre[1] == 0:                                                           # pre[1] specifies which: if 0 -> SAVE   
                LOG("Starting SAVE TS", 0)
                
                led.value(1)
                
                while busy:
                    pass
                
                # Save some state for possible restoration
                pf_name = TSP.f_name
                pappend = TSP.append
                pidx = TSP.tap_idx
                # SAVE_TS changes TSP.f_name to the new file name if append is False 

                MQ, TSP, new_logs, saved = SAVE_TS(MQ, TSP)
                # log_entries += new_logs
                # log_entries.extend(new_logs) # For when SAVE_TS returns an array
                log_entries.append(new_logs) # For when SAVE_TS returns as one string as now
                # SAVE_TS reports whether a .tap actually reached the card;
                # this used to sniff the mount table for it. Kept in step with
                # TS/tspico.py -- SAVE_TS returns a 4-tuple now, so unpacking
                # three here would ValueError the moment this override loads.

                # ─── DUAL-PORT MIGRATION: explicit SD-teardown ────────────
                # SAVE_TS may leave /sd mounted; ACTIVATE_MQ no longer
                # unmounts it, so we do it here. See stage-3 comments
                # on ACTIVATE_MQ for the rationale.
                # ──────────────────────────────────────────────────────────
                DEACTIVATE_SD()

                # ARM EXACTLY ONCE, AFTER ALL SD WORK. Arming here and then
                # calling MOUNT_FILE / DIR_FILES below re-created the #40
                # pin-grab race (ACTIVATE_SD takes GPIO 2-4; GPIO 2 is D0),
                # and the second ACTIVATE_MQ() tore the SM down under any
                # command that started meanwhile. See TS/tspico.py for the
                # full note.
                if saved:

                    # Handle re-mounting an appended file, possibly mounting a
                    # new file, or restoring the mounted file's name. Then
                    # update the directory list with changes.

                    if pappend:
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

                    # Update the directory list with the changes
                    try:
                        ACTIVATE_SD()
                        os.chdir(TSP.cur_path) # MOUNT_FILE doesn't set this
                        LOG("os.chdir to:" + TSP.cur_path, 0) # debug
                        try:
                            DIR_FILES()
                            LOG("DIR_FILES OK", 0) # debug
                        except:
                            LOG("DIR_FILES failed after save", 2)
                    except:
                        LOG("os.chdir failed after save", 2)

                    # ─── DUAL-PORT MIGRATION: pair with DEACTIVATE_SD ─────
                    # /sd was just mounted via ACTIVATE_SD above for the
                    # DIR refresh; tear it down before reactivating MQ.
                    # ──────────────────────────────────────────────────────
                    DEACTIVATE_SD()

                # Single arm point for both outcomes, after the last SD access.
                ACTIVATE_MQ()
                MQ.put(0x01)
                MQ_READY()

                led.value(0)
                
            elif (pre[0] == 0 or pre[0] == 255) and pre[1] < 10:                                      # for simplicity if 0 < pre[1] < 10: call LOAD routine
                TLM("LVM LOAD enter", "pre=%s f_name=%s tap_idx=%d offset=%d" % (
                    _pre_snapshot, TSP.f_name, TSP.tap_idx, TSP.offset))
                LOG("Starting TS LVM", 0)

                while busy:
                    pass
                MQ, TSP, new_logs = LOAD_TS(pre, MQ, TSP)
                # log_entries += new_logs
                log_entries.append(new_logs) # for now
                # log_entries.extend(new_logs) # when LOAD_TS returns an array
                TLM("LVM LOAD exit", "tap_idx=%d offset=%d" % (TSP.tap_idx, TSP.offset))

            elif (pre[0] == 0 or pre[0] == 255):                                                      # Headerless LOAD
                TLM("LVM Headerless LOAD enter", "pre=%s tap_idx=%d offset=%d" % (
                    _pre_snapshot, TSP.tap_idx, TSP.offset))
                LOG("Starting TS LVM - Headerless LOAD", 0)

                while busy:
                    pass
                MQ, TSP, new_logs = LOAD_TS(pre, MQ, TSP)
                # log_entries += new_logs
                log_entries.append(new_logs) # for now
                # log_entries.extend(new_logs) # when LOAD_TS returns an array
                TLM("LVM Headerless LOAD exit", "tap_idx=%d offset=%d" % (TSP.tap_idx, TSP.offset))

            elif pre[0] == 66 and pre[1] == 5:                                                        # commands are pre[0] == 66. PRINT commands are pre[1] == 5
                LOG("Starting PRINT", 0)
                PRINT_IO(pre)
                DIR_FILES()

            elif pre[0] == 66:

                LOG("Starting TS COMMAND " + str(pre), 0)

                try:
                    PROCESS_CMD(pre, SA_funct, EXT_SA_FUNCT)
                    TLM("main loop: PROCESS_CMD returned", "pre=%s" % _pre_snapshot)
                except Exception as _e:
                    LOG("Invalid data received from PROCESS_CMD: " + str(pre), 2)
                    TLM("main loop: PROCESS_CMD raised exception", str(_e))
                    continue
                
                if TSP.zx48:
                    ZX48_IO(pre)
                    
            elif pre[0] == 65:
                LOG('Starting "A" COMMAND', 0)
                
                PROCESS_ASM(pre)
                DIR_FILES()
                
            else:
                try:
                    LOG("Unrecognized command! " + str(list(pre)), 1)
                except:
                    LOG("Unrecognized command! Cannot get pre[] data", 1)

                # ─── DUAL-PORT MIGRATION: inline FIFO drains ──────────────
                # Replaces EMPTY_RX_FIFO() / EMPTY_TX_FIFO() (single-port
                # helpers being retired). The behavior is identical; just
                # inlined so the handler is self-contained.
                # ──────────────────────────────────────────────────────────
                while MQ.rx_fifo() != 0:
                    MQ.get()
                while MQ.tx_fifo() != 0:
                    MQ.exec("pull (noblock)")
                    MQ.exec("mov (osr, null)")
                MQ.active(0)
                utime.sleep(.01)
                MQ.active(1)

                BLINK_ERROR()

                LOG("Cleared TX/RX FIFO after unrecognized cmd: %d %d" % (MQ.tx_fifo(), MQ.rx_fifo()), 0)

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
            if time.ticks_diff(time.ticks_us(), ts) < 2_000_000:
                continue
            elif time.ticks_diff(time.ticks_us(), ts) < 2_100_000:
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
                        try:
                            _thread.start_new_thread(SAVE_LOG, ())
                        except OSError:
                            pass

                led.value(0)
                ts = time.ticks_us()
                

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
    MQ.exec("mov(y, invert(null))")    # Y = READY for the entire ZX session

    TLM("ZX48_IO enter", "par1=%d par2=%d ZX_TAPE_COMPAT=%s" % (
        par1, par2, TSP.ZX_TAPE_COMPAT))
    LOG("Starting ZX Mode...", 0)

    ts = time.ticks_us()

    while True:

        if (MQ.rx_fifo()) != 0:

            ts = time.ticks_us()
            a = MQ.get()
            TLM("ZX48_IO byte received", "a=%d (0x%02X)" % (a, a))

            # Wait for core1 before dispatching, the way the three
            # main-loop LVM branches do. Without it a watchdog left
            # over from the previous ZX transaction is still inside
            # its cleanup -- which ends with a ~1s BLINK() -- and the
            # spawn in the handler below raises OSError 'core1 in
            # use'. Nothing here or in main.py catches that, so the
            # Pico drops to a REPL. START_WATCHDOG() now survives it,
            # but waiting means we keep the watchdog instead of
            # running the transfer unguarded. Bounded, so a thread
            # that died without clearing the flag cannot wedge us.
            # BOTH flags: `busy` here is tspico.py's own (SAVE_LOG,
            # BLINK_LED, CHK_STATUS); CORE1_BUSY() is tspico_io's
            # WATCHDOG. They are different variables -- see that
            # function's docstring -- and core1 is one resource.
            _t = time.ticks_ms()
            while busy or CORE1_BUSY():
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
                    MQ, TSP, new_logs = LOAD_ZX_C(MQ, TSP, buf_size)
                    # log_entries += new_logs
                    log_entries.append(new_logs) # for now
                    # log_entries.extend(new_logs) # when LOAD_TS returns an array
                else:
                    # 'regular' ZX Spectrum LOAD
                    LOG("Starting ZX LOAD", 0)
                    MQ, TSP, new_logs = LOAD_ZX(MQ, TSP)

                TLM("ZX48_IO LOAD returned")

            elif a == 83:                                                  # ASCII 'S' - for SAVE

                TLM("ZX48_IO dispatching SAVE")
                LOG("Starting ZX SAVE", 0)
                MQ, TSP, new_logs = SAVE_ZX(MQ, TSP)
                # log_entries += new_logs
                log_entries.append(new_logs) # for now
                # log_entries.extend(new_logs) # when LOAD_TS returns an array
                TLM("ZX48_IO SAVE returned")

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
                    MQ.exec("pull (noblock)")
                    MQ.exec("mov (osr, null)")
                MQ.active(0)
                utime.sleep(.01)
                MQ.active(1)

                LOG("Cleared TX/RX FIFO after unrecognized ZX command: %d %d" % (MQ.tx_fifo(), MQ.rx_fifo()), 0)

        else:
            # ─── DUAL-PORT MIGRATION: use ticks_diff to handle wrap (same
            # fix as TS2068_IO's main idle loop) ─────────────────────────
            if time.ticks_diff(time.ticks_us(), ts) < 2_000_000:
                continue
            elif time.ticks_diff(time.ticks_us(), ts) < 2_100_000:
                led.value(1)
            else:

                if log_entries:
                    SAVE_LOG()
                    # log_entries = [] # SAVE does this
                    
                led.value(0)
                ts = time.ticks_us()

    # Debug - Ricardo 21 Aug 2025 for returning from Spectrum mode problem
    if MQ.tx_fifo() != 0:
        print("MQ FIFO: ", MQ.tx_fifo())
        LOG("TX FIFO not empty after ZX mode. Trying to force cleanup", 1)

        # ─── DUAL-PORT MIGRATION: inline TX drain ─────────────────────────
        while MQ.tx_fifo() != 0:
            MQ.exec("pull (noblock)")
            MQ.exec("mov (osr, null)")

        MQ.active(0)
        utime.sleep(.01)
        MQ.active(1)

        LOG("TX FIFO succesfully cleared before returning from ZX mode", 0)

    else:
        LOG("Returning from ZX mode; TX FIFO is empty: ", 0)

    TLM("ZX48_IO exit", "TSP.zx48=%s" % TSP.zx48)
