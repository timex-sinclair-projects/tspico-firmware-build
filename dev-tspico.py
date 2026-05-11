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
    try:
        os.umount("/sd")
    except:
        pass                                # already unmounted is fine

    U3_CS = Pin(28, Pin.OUT, Pin.PULL_UP)
    U3_CS.value(1)

    # GPIO 2-4 are shared with SPI (SCK/MOSI/MISO). Drive them LOW
    # before the PIO state machine reclaims them. This is the Report D
    # fix from the dual-port migration.
    for p in (2, 3, 4):
        Pin(p, Pin.OUT).value(0)
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

    MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000, out_base=Pin(2, Pin.OUT),
                      in_base=Pin(2, Pin.IN), jmp_pin=Pin(11),
                      sideset_base=Pin(12, Pin.OUT))

    if ready:
        MQ.active(1)
        # Y = 0xFFFFFFFF → $0F always returns 0xFF → D6=1=ready.
        # Stays at READY for the entire session.
        MQ.exec("mov(y, invert(null))")

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
    """Signal 'ready' to Z80 — bit 6 set on $0F reads (Y = 0xFFFFFFFF)."""
    # invert(null) is the documented MicroPython PIO syntax for ~0.
    # The tilde form `~null` does NOT parse correctly via runtime
    # sm.exec() in MicroPython v1.20.0 — confirmed by REPL test.
    # Without this, Y stays at 0, $0F always reads 0, Z80 sees
    # "never ready" and reports J.
    MQ.exec("mov(y, invert(null))")


def MQ_BUSY():
    """Signal 'not ready' to Z80 — bit 6 clear on $0F reads (Y = 0).

    In normal operation we keep Y=READY constantly; the protocol's
    natural pacing via TX FIFO depth handles flow control. MQ_BUSY
    is here for completeness and any future code that needs an
    explicit busy signal.
    """
    MQ.exec("set(y, 0)")


def WAIT_TX_RECEIVED():

    global MQ

    while MQ.tx_fifo() != 0:
        pass


def EMPTY_TX_FIFO():
 
    global MQ
 
    while MQ.tx_fifo() != 0:
        MQ.exec("pull (noblock)")
        MQ.exec("mov (osr, null)")
        
    return

def EMPTY_RX_FIFO():
    
    global MQ
    
    while MQ.rx_fifo() != 0:
        MQ.get()

    return


def ACTIVATE_SD():                                                                              # Enable SD-Card access SM, after TX/RX operation
    
    global MQ

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

    except Exception as e:
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
    while (time.ticks_us() - t_init) < secs:
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
             
        EMPTY_RX_FIFO()
        EMPTY_TX_FIFO()
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
    
    # try:
    #     os.remove("dirinfo.tap")
    # except:
    #     pass
    
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
                    if not COPY_FILE("/TS/dckupdate.tap", "/TMP/temp.tap"):       # Special 'seudo' TAP that contains Flash/SRAM DCK update program
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
                    with open("/TS/romupdate.tap", "rb") as f_in:                 # Same for updating ROM images. We open the seudo TAP, as we need to update it
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
    
    if TSP.VERBOSE or forceDisplay:
    
        wrt(0x40)               # Read continue flag
        wrt(0x81)               # PRINT STRING
        wrt(st)                 # Return code
        wrt(0x0D)               # Start with a newline
        for m in msg:           # Write message
            wrt(m) # Will let ~ and | pass as FREE and STICK
        if msg1:                # Write msg1
            wrt(0x0D)
            for m in msg1:
                wrt(m)
        wrt(0x00)               # End of string
        
    else:
        
        wrt(0x40)               # Read continue flag
        wrt(st)                 # Return code (< 0x80)
        
    WAIT_TX_RECEIVED()
    
    return


def SEND_MSG2(msg, st: bytes, expandKeywords = True):                                         # Sends a SCROLLING status message back to the TS,
                                                                                              # once a command is finished
    # msg: a string of the message (no bytearrays)
    # st:  report status

    global MQ
    global TSP
    
    global kill
    global dead

    if TSP.ROM_VERSION == "1.0":
        new_rom = False
        end_char = 0x00
    else:    
        new_rom = True
        end_char = 0x03

    scroll = "Scroll? (Y/n)"
    
    s = len(scroll) + 6
    n = len(msg)

    EMPTY_RX_FIFO()

    wrt = MQ.put
    wrt(0x40)   # Read continue
    wrt(0x86)   # PRINT STRING WITH LOOP
    wrt(st)     # BASIC return code
    wrt(0x0D)   # Start on a new line
    wrt(0x0D)   # Start with a blank line we don't count
            
    # We handle each character. If a scroll answer is N, we will just break

    c = 0 # char count
    l = 0 # line count
    ll = 21 # Initial line limit
    if not new_rom:
        wrt(0x0D)       # Another newline for old ROM
    i = -1

    while i < n - 1:
        
        i += 1
        ch = ord(msg[i]) # needed to be able to test ch == int

        # Handle special character cases

        if ch < 32:
            
            if ch == 0x0D:
                # Timex or PC line ending
                if i+1 < n and msg[i+1] == '\n':
                    # PC line ending
                    i += 1 # Skip extra char
                c = 32 # End of line
                
            elif ch == 0x0A:
                # Unix line ending
                ch = 0x0D # Change to Timex
                c = 32 # End of line

            elif ch == 0x08:
                # Handle a backspace character
                if l > 0 or c > 0:
                    if c == 0:
                        c = 31
                        l -= 1
                    else:
                        c -= 1
                else:
                    continue # ignore
                
            elif ch >= 0x10 and ch <= 0x15:
                # Attribute control: first of two chars that don't move the column
                # For now, just eat these since they don't advance the column and 
                # many have the second byte as 0 which will end the current print string.
                i += 1
                continue
            
            else:
                # 00 and 03 not allowed since they mark the end of the strings 
                # to send and others < 32 print as ?
                ch = 0x3F # '?'
                c += 1
            
        elif ch >= 124:
            
            if ch > 127:
                # Currently printing high-bit chars crashes, so protect this.
                ch = 63 # Change to '?'
                c += 1
            elif expandKeywords:
                if ch == 124: # Tilde ~
                    c += 6 # Let expand to " FREE "
                elif ch == 126: # vbar |
                    c += 7 # Let expand to " STICK "
                else: # 125
                    c += 1
            else:
                c += 1
            # DELETE, ON ERR, SOUND, and RESET don't expand to keywords in L
            # mode but will in K mode. If in a program, and no printing or INPUT
            # has been done yet, the BASIC is still in K mode. So, for now you
            # should issue a `PRINT ;` or other PRINT or INPUT statement in your
            # program before executing TS-Pico commands that print text.
            
        elif msg[i] == '\\':
            # Possible zmakebas escape
            # cc, ln = zmakebas2Timex(msg, i)
            # ch = ord(cc)
            # if ln > 1:
                # i += ln - 1
            # Only handle copyright until we can print codes > 127
            if i+1 < n and msg[i+1] == '*':
                ch = 127
                i += 1
            c += 1

        else: # Regular character
            c += 1

        wrt(ch)

        if c == 32: # We've written one line

            l += 1 # Inc line count
            c = 0  # Reset column count
        
            if ch == 0x0D: # A short line (we already printed the 0x0D)
                if i == 0 or (i == 1 and msg[1] == '\n'):
                    # Newline at start we don't count.
                    # This allows you to put a blank line at the start to 
                    # separate the message from the prior text but not count
                    # toward the first screen scroll lines.
                    l -= 1
            else: # ch != 0x0D:
                # Check for newline at end of 32
                if i + 1 < n:
                    if msg[i+1] == '\r': # Timex or PC
                        if i + 2 < n and msg[i+2] == '\n':
                            i += 1 # Skip extra PC EOL char
                        i += 1 # Skip EOL char
                    elif msg[i+1] == '\n': # Unix
                        i += 1 # Skip EOL char
                wrt(0x0D)

            if l == ll and (not new_rom or n > i + 34):

                l = 0 # reset line count
                if not new_rom and i == n - 1:
                    scroll = "--- End of list (N to exit) ---"
                else:
                    for m in "(%2d%%) " % ((i * 100) // n):
                        wrt(m)
                for m in scroll:    # Write scroll prompt (empty if last screen)
                    wrt(m)
                if not new_rom:
                    wrt(13)

                wrt(0x00)       # End of this page
                wrt(0x40)       # Read continue flag
                
                ch = MQ.get()   # Get keypress from user
                if (ch == 78):  # If 'N' then done (ROM loops stops on old rom)
                    return
                if ch == 48:
                    ll = 10
                elif ch >= 49 and ch <= 57:
                    ll = ch - 48
                else:
                    ll = 21

                wrt(0x40)       # Start new string
                
                if new_rom:
                    for b in range(s):      # Erase scroll prompt
                        wrt(0x08)
                        wrt(0x20)
                        wrt(0x08)
                else:
                    wrt(0x0D)       # Another newline for old ROM

    wrt(end_char)               # Write end_char (done with loops)

    WAIT_TX_RECEIVED()

    while(MQ.rx_fifo() != 0):   # Flush input buffer to console
        print(MQ.get())
    
    print(MQ.tx_fifo(), MQ.rx_fifo()) # Report FIFO queue sizes


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

    if par1 == 0:
        # Regular listing
        led.value(1)
        SEND_MSG2(lista, 1, False)
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

    EMPTY_RX_FIFO()
    wrt = MQ.put
    Init = True
    sel = -1
    pgs = (n - 1) // nmax + 1

    while idx < n:
        i = 0
        # Write screen
        
        wrt(0x40)   # Read continue
        if Init:
            wrt(0x86)   # PRINT STRING WITH LOOP
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
            
        wrt(0x00)       # End of this string
        wrt(0x40)       # First 0x40; wait for keypress
        ch = MQ.get()   # Get a key
        if ch == 78:    # 'N' then done (ROM ended the loops)
            return -1
        if ch == 66: # B
            if idx >= nmax:
                idx -= nmax
            else:
                idx = 0
        elif ch in LISTMENU_CHOICES:
            j = idx + LISTMENU_CHOICES[ch]
            if j < n:
                wrt(0x40)   # Start last string
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
    WAIT_TX_RECEIVED()
    EMPTY_RX_FIFO()

    return sel


def PATH(pre, cmd):                                                                             # Show current directory
    
    # SAVE "tpi:path"               - Show current path
    # SAVE "tpi:path"CODE 1,0       - Show current mounted file path

    global TSP
    
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
        ACTIVATE_MQ()
    except:
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

    _BUFSZ = 256
    buf = bytearray(_BUFSZ)
    mv = memoryview(buf)  # Faster indexing than bytearray
    
    wrt = MQ.put
    
    status = _1_OK
    
    led.value(1)
    
    if TSP.f_name[-4:].upper() == ".DCK":
        
        wrt(0x40)
        wrt(status)
        
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
        
        wrt(0x40)
        wrt(status)
        
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
    
    if MOUNT_FILE("/TS/rompatch.tap"):
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

    EMPTY_RX_FIFO()
    wrt = MQ.put
    wrt(0x40)   # Read continue
    wrt(0x86)   # PRINT STRING WITH LOOP
    wrt(0x01)   # BASIC return code
    wrt(0x0D)   # Start a new line
    for ch in prompt:
        wrt(ch)
    wrt(0x00)   # End string
    wrt(0x40)   # Read continue to get char
    ch = MQ.get()
    if ch != 78: # 'N' causes the ROM to end the string loop and any exchange
        wrt(0x40) # Start a new string
        if echo:
            if ch < 32 or ch > 127:
                wrt(89) # Y
            else:
                wrt(ch)
        wrt(0x03) # End the string loop
        # Could add an option to not wrt(0x03) and let the caller do that after
        # writing some more text to indicate the result of the action.
        WAIT_TX_RECEIVED()
        EMPTY_RX_FIFO()

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

        ACTIVATE_MQ()
    
    if not sent:
        SEND_MSG(message, name, status)
    
    return 
                

def SYS_CMD(pre, cmd):                                                                                      # Various system cmds
    
    global led
    global patch
    
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
    M.append('mode, use OUT 10,100 followed by')
    M.append('OUT 244,0 and then press the TS ')
    M.append('Reset button on the TS-Pico.')
    M.append(nl)
    msg = "".join(M)

    SEND_MSG(msg, "", _1_OK, par1 == 0)
            
    return 


def NOP(pre, cmd):
    """A 'no operation' command"""
    
    global MQ
    
    MQ.put(0x40)
    MQ.put(0x01)
    
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
        
        wrt(0x40)
        wrt(0x01)
        
        pre = [0] * 10
        for i in r1:
            pre[i] = MQ.get()
        if pre[1] != 5:
            break
    
    wrt(0x40)
    wrt(0x01)
    
    SEND_MSG(end_msg, "", _1_OK)
    
    WAIT_TX_RECEIVED()
  
    EMPTY_RX_FIFO()
        
    prn = prn[:pos]

    with open("/PRN/0001.txt", "w") as sal:                                           # PRINT output filename is fixed on this version; can be set up
            sal.write(prn)                                                            # in future version

    return


def PROCESS_ASM(pre):                                                                 # Processes AU (Assembler) commands sent by the TS
    
    global MQ
    
    cmd = pre[:5].decode()
    wrt = MQ.put
    
    wrt(0x40)
    
    print(pre)
    print(cmd)
    
    par3 = int(pre[8])
    par4 = int(pre[9])
    
    print(par3, par4)
    
    wrt(0x40)
    wrt(0x01)
    
    return


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
    
    wrt(0x40)
    wrt(0x01)
    
    for l in rl:
        cmd[l] = MQ.get()
    
    try:
        cmd = cmd[:long].decode()
    except:
        LOG("Unrecognized string in PROCESS_CMD: FIFO Status:%d %d" % (MQ.tx_fifo(), MQ.rx_fifo()), 2)
        return

    cmd_exec = cmd[3:].upper() # Command starting with "TPI:" in uppercase
    rest_cmd = cmd[7:] # Command after "tpi:"

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
            
        if cmd_word in SA_funct:
            EXEC = SA_funct[cmd_word]
            EXEC(pre, cmd)
            
        elif cmd_word in EXT_SA_FUNCT:                                                                                # Is an external cmd?
            EXEC = EXT_SA_FUNCT[cmd_word]
            EXEC(MQ, TSP, pre, cmd)
            
        else:
            msg = "Unrecognized command: %s" % cmd_exec
            SEND_MSG(msg, 'SAVE "tpi:help" for info', _5_C_Nonsense)    # If none of the above, raise error
            LOG(msg, 2)
    
    WAIT_TX_RECEIVED()
    
    EMPTY_RX_FIFO()
        
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

    try:
        from TS.extcmd import EXT_SA_FUNCT
    except Exception as e:
        LOG(f"Unable to import external commands; using emtpy SA_EXT_CMD dictionary: {e}", 0)
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
    
    ACTIVATE_MQ()
    
    LOG("SD Card initialized and mounted OK", 0)
    SAVE_LOG()
    
    wrt = MQ.put
    
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
            # reset timestamp
            count = 0
            idx = 0
            
            wrt(0x01)
            while (count <= 30_000) and (idx <= 9):
                if (MQ.rx_fifo()) != 0:
                    pre[idx] = MQ.get()
                    idx += 1
                    
                else:
                    count += 1
                    
            if (count >= 30_000):
                LOG("Incomplete command received", 2)
                BLINK_ERROR()
                continue
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

                MQ, TSP, new_logs = SAVE_TS(MQ, TSP)
                # log_entries += new_logs
                # log_entries.extend(new_logs) # For when SAVE_TS returns an array
                log_entries.append(new_logs) # For when SAVE_TS returns as one string as now
                save_aborted = "sd" not in os.listdir("/")

                # Make sure MQ is active (SAVE_TS normally leaves SD active)
                ACTIVATE_MQ() # Also fixes ENA_SD leaving MQ active with SD active as well

                if not save_aborted:

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
                    
                    ACTIVATE_MQ()
                
                led.value(0)
                
            elif (pre[0] == 0 or pre[0] == 255) and pre[1] < 10:                                      # for simplicity if 0 < pre[1] < 10: call LOAD routine 
                LOG("Starting TS LVM", 0)
                
                while busy:
                    pass
                MQ, TSP, new_logs = LOAD_TS(pre, MQ, TSP)
                # log_entries += new_logs
                log_entries.append(new_logs) # for now
                # log_entries.extend(new_logs) # when LOAD_TS returns an array
                
            elif (pre[0] == 0 or pre[0] == 255):                                                      # Headerless LOAD
                LOG("Starting TS LVM - Headerless LOAD", 0)
                
                while busy:
                    pass
                MQ, TSP, new_logs = LOAD_TS(pre, MQ, TSP)
                # log_entries += new_logs
                log_entries.append(new_logs) # for now
                # log_entries.extend(new_logs) # when LOAD_TS returns an array
                
            elif pre[0] == 66 and pre[1] == 5:                                                        # commands are pre[0] == 66. PRINT commands are pre[1] == 5
                LOG("Starting PRINT", 0)
                PRINT_IO(pre)
                DIR_FILES()
                
            elif pre[0] == 66:

                LOG("Starting TS COMMAND " + str(pre), 0)
                
                try:
                    PROCESS_CMD(pre, SA_funct, EXT_SA_FUNCT)
                except:
                    LOG("Invalid data received from PROCESS_CMD: " + str(pre), 2)
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
                
                EMPTY_RX_FIFO()
                EMPTY_TX_FIFO()
                MQ.active(0)
                utime.sleep(.01)
                MQ.active(1)
                
                BLINK_ERROR()
                
                LOG("Cleared TX/RX FIFO after unrecognized cmd: %d %d" % (MQ.tx_fifo(), MQ.rx_fifo()), 0)
                
            # fr2 = gc.mem_free()
            # LOG("End of main loop, free=%.1f" % (fr2 >> 10), 0)
            # gc.collect()
            # LOG("After gc.collect, free=%.1f" % (gc.mem_free() >> 10), 0)
            n = MQ.tx_fifo()
            if n > 0:
                EMPTY_TX_FIFO()
                LOG("Bottom of main loop: TX FIFO was cleared, it had %d bytes in it." % n, 0)
            n = MQ.rx_fifo()
            if n > 0:
                b = bytearray(n)
                for i in range(n):
                    b[i] = MQ.get()
                LOG("Bottom of main loop: RX FIFO was cleared, it had %d bytes in it: %s" % str(b), 0)
                
        else:
            # Nothing to do, so check if time to save the log
            if time.ticks_us() - ts < 2_000_000:
                continue
            elif time.ticks_us() - ts < 2_100_000:
                led.value(1)
            else:
                if log_entries:
                    if not busy:
                        LOG("Before SAVE_LOG, free=%.1f" % (gc.mem_free() >> 10), 0)
                        gc.collect()
                        LOG("After gc.collect, free=%.1f" % (gc.mem_free() >> 10), 0)
                        _thread.start_new_thread(SAVE_LOG, ())
    
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

    MQ = StateMachine(0, TS_IO, freq=15_000_000, out_base=Pin(2, Pin.OUT), in_base=Pin(2, Pin.IN), jmp_pin=Pin(11), sideset_base=Pin(12, Pin.OUT))
    MQ.active(0)
    
    utime.sleep(0.01)
    MQ.active(1)
    
    LOG("Starting ZX Mode...", 0)

    ts = time.ticks_us()
    
    while True:
        
        if (MQ.rx_fifo()) != 0:
            
            ts = time.ticks_us()
            a = MQ.get()
            
            if a == 76:                                                    # ASCII 'L' - for LOAD

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
                
            elif a == 83:                                                  # ASCII 'S' - for SAVE
                
                LOG("Starting ZX SAVE", 0)
                MQ, TSP, new_logs = SAVE_ZX(MQ, TSP)
                # log_entries += new_logs
                log_entries.append(new_logs) # for now
                # log_entries.extend(new_logs) # when LOAD_TS returns an array
                      
            elif a == 100:                                                  # ASCII 'X' - for EXIT. David, change this to whatever you thing suits better
                LOG("Ending ZX mode. Free mem: %d. Returning to TS processing." % gc.mem_free(), 0)
                gc.collect()
                
                break
            
            else:
                LOG("Unrecognized ZX command", 1)
                EMPTY_RX_FIFO()
                EMPTY_TX_FIFO()
                MQ.active(0)
                utime.sleep(.01)
                MQ.active(1)
                
                LOG("Cleared TX/RX FIFO after unrecognized ZX command: %d %d" % (MQ.tx_fifo(), MQ.rx_fifo()), 0)

        else:
            if time.ticks_us() - ts < 2_000_000:
                continue
            elif time.ticks_us() - ts < 2_100_000:
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
        
        EMPTY_TX_FIFO()
            
        MQ.active(0)
        utime.sleep(.01)
        MQ.active(1)
        
        LOG("TX FIFO succesfully cleared before returning from ZX mode", 0)
        
    else:
        LOG("Returning from ZX mode; TX FIFO is empty: ", 0)
