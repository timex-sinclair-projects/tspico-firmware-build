################################
# DATE: 04/22/2025 10:33 GMT-3 #
# FIRMWARE VERSION: 1.2        #
################################

#######################
# DATE: 2025/09/09    #
# Ryan's Mods for 1.2 #
#######################

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
# - Broke out the part of CD that cheks the new name and does the change into a
#   separate routine so it can be called by the interactive CD routine.
# - Changed findArgs to getArgs and have it return the arg string instead.
# - Moved the command help files all to the SD card in an /sd/help folder.
# - Extended the zx48 compatible loader option to be able to give a custom
#   buffer size by giving the value as >= 16384 on the CODE 1,* option. CODE 1,1
#   uses the default buffer size.

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

from rp2 import StateMachine, asm_pio, PIO
from machine import Pin, freq, SPI

from TS.sdcard import *

from TS.tspico_io import patch, sel_bank, set_ctrl, set_dck, TS_IO_DUAL, LOAD_TS, LOAD_ZX, LOAD_ZX_C, SAVE_TS, SAVE_ZX
#from TS.tspico_io import sel_bank, set_ctrl, set_dck, TS_IO, LOAD_TS, LOAD_ZX, LOAD_ZX_C, SAVE_TS, SAVE_ZX

#####################
# SERVICE FUNCTIONS #
#####################

@asm_pio(
    autopull=True,
    pull_thresh=8,
)
def NULL_SM():
    nop()

# Error status return values showing BASIC error given.
# These match the TPI protocol spec exactly. Note: previous STAT_*
# names used different numeric values which sent the wrong BASIC
# error to the TS-2068 (e.g. "invalid filename" was mapped to 2 which
# is "tape load error R" per protocol). The values below align with
# the EXROM error dispatch at $1BF3.
from micropython import const

_0_J_Invalid_IO   = const(0)    # Report J - Invalid I/O device
_1_OK             = const(1)    # No error
_2_R_Tape_load    = const(2)    # Report R - Tape loading error
_3_F_Invalid_file = const(3)    # Report F - Invalid file name
_4_Q_Parameter    = const(4)    # Report Q - Parameter error
_5_C_Nonsense     = const(5)    # Report C - Nonsense in BASIC
_6_6_Num2Big      = const(6)    # Report 6 - Number too big
_7_8_EOF          = const(7)    # Report 8 - End of file
_8_A_Invalid_arg  = const(8)    # Report A - Invalid argument
_9_9_STOP         = const(9)    # Report 9 - STOP
_10_D_Break       = const(10)   # Report D - Break/CONT (any value >= 10)


# ---------------- TELEMETRY ----------------
# Comprehensive event logging. Each TLM() call prints an event with
# timestamp (microseconds since boot), delta from previous TLM call,
# and TX/RX FIFO occupancy. Frozen-module overhead is negligible.

_tlm_last = 0   # last TLM timestamp


def TLM(action, detail=""):
    """Log one event to the REPL with timing and FIFO state."""
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
    """Reset TLM timer at the start of a new operation."""
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

    # GPIO 2-4 are shared with SPI (SCK/MOSI/MISO). Drive them LOW before
    # the PIO state machine reclaims them.
    for p in (2, 3, 4):
        Pin(p, Pin.OUT).value(0)
    TLM("DEACTIVATE_SD exit", "GPIO 2-4 clamped LOW, U3_CS=HIGH")
    return


def ACTIVATE_MQ(ready=True):
    """Create the dual-port TS_IO_DUAL state machine.

    ready=True  (default): activate the SM immediately. Use at boot,
                or any time the FIFO is already loaded with the
                response and no Z80 poll is in progress.
    ready=False: create the SM but DON'T activate it. The caller must
                load the response into the TX FIFO with MQ.put(),
                then call MQ.active(1), then signal MQ_READY().
                Use during MOUNT_FILE / SD-access flows so GPIO 12
                stays LOW (Z80 sees 'not ready') until the response
                is genuinely in the FIFO.

    Caller MUST invoke DEACTIVATE_SD() first if the SD card was active.
    Scratch register Y resets to 0 ('not ready') on SM creation.

    Note: PIO clocked at 30MHz (was 15MHz). The dual-port decode adds
    ~7 instructions to the read path; 30MHz keeps the total under the
    Z80's data setup window with margin. The RP2040 PIO can run up to
    half the system clock (135MHz at 270MHz CPU), so 30MHz is safe.
    """
    global MQ

    TLM("ACTIVATE_MQ enter", "ready=%s" % ready)
    MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000, out_base=Pin(2, Pin.OUT),
                      in_base=Pin(2, Pin.IN), jmp_pin=Pin(11),
                      sideset_base=Pin(12, Pin.OUT))

    if ready:
        MQ.active(1)
        TLM("ACTIVATE_MQ exit", "SM active, Y=0 (busy until MQ_READY called)")
    else:
        TLM("ACTIVATE_MQ exit", "SM created but NOT active")

    return


def MQ_READY():
    """Signal 'ready' to Z80 — bit 6 set on port $0F reads.

    Sets PIO scratch register Y to all-ones (0xFFFFFFFF). The Z80
    WF_NPH polling loop tests BIT 6,A — any value with bit 6 set
    works, so 0xFF is functionally equivalent to 0x40 here.

    Call this AFTER MQ.put() has loaded the response into the TX FIFO.
    The Z80 will see 'ready' on its next IN A,($0F), then read the
    actual data via IN A,($0E).
    """
    # invert(null) is the documented MicroPython PIO syntax. The tilde
    # form `~null` does NOT parse correctly via runtime sm.exec() in
    # v1.20.0 — confirmed by REPL test. Without this, Y stays at 0,
    # port $0F always reads 0, Z80 sees "never ready" and reports J.
    MQ.exec("mov(y, invert(null))")
    # NOTE: no TLM here. MQ_READY is called in time-critical receive
    # paths where a print() takes ~1-10ms — long enough for the 4-deep
    # RX FIFO to overflow and lose bytes from the Z80. Caller can TLM
    # at a safer point if needed.


def MQ_BUSY():
    """Signal 'not ready' to Z80 — bit 6 clear on port $0F reads.

    Sets PIO scratch register Y to 0. The Z80 WF_NPH polling loop
    will continue spinning until either MQ_READY() is called or the
    Z80's own 2.8ms timeout expires (whichever comes first).

    Call this BEFORE doing slow work (SD card access) and after the
    response has been read by the Z80 (to clear ready for the next
    cycle).
    """
    MQ.exec("set(y, 0)")
    # NOTE: no TLM here — same critical-path concern as MQ_READY.


def ACTIVATE_SD():                                                                              # Enable SD-Card access SM, after TX/RX operation

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

    except:
        LOG("ERROR: Mounting SD Card failed in ACTIVATE_SD!", 2)
        SAVE_LOG()
        spi = -99
        TLM("ACTIVATE_SD FAILED — entering BLINK_ERROR loop")
        while True:
            BLINK_ERROR()
        pass

    return spi


def BACKUP_DIR(d, dest_dir):                                                               # Recursively backs-up folders and files of a provided "d" folder; typically d="/" (root of the Flash)
                                                                                           # and dest_dir = /sd/BACKUP
    if os.stat(d)[0] & 0x4000:  # Dir
        
        copy_path = str(dest_dir) + str(d)
        
        if (copy_path == dest_dir + "/"):
            copy_path = dest_dir
            
        try:
            os.mkdir(copy_path)
        except:
            FINISH("Fatal error. Could not create folder " + copy_path + ". Verify SD Card contents. Terminating", False)
        
        for f in os.ilistdir(d):
            if f[0].startswith("sd"):
                continue
            
            if f[1] & 0x8000:
                copy_src = d + '/' + f[0]
                copy_dst = copy_path + '/' + f[0]
                LOG("Copying file " + copy_src + " to " + copy_dst, 4)
                
                COPY_FILE(copy_src, copy_dst)
                continue
            
            if f[0] not in ('.', '..'):
                folder_name = d + '/' + f[0]
                LOG("Processing folder " + folder_name, 4)
                BACKUP_DIR(folder_name, dest_dir)  # File or Dir
        
    return


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
    
    LOG("INFO: Starting watchdog...", 0)
    secs = secs * 1_000_000
    
    t_init = time.ticks_us()
    while (time.ticks_us() - t_init) < secs:
        if dead:
            break
    if not dead:
        LOG("ERROR: Abnormal termination. Clearing TX/RX FIFO....", 2)
        while not dead:
            MQ.exec("pull (noblock)")
            MQ.exec("mov (osr, null)")
            MQ.exec("mov (isr, null)")
            MQ.exec("push (noblock)")
            kill = True
             
        while MQ.rx_fifo() != 0:
            MQ.get()
        while MQ.tx_fifo() != 0:
            MQ.exec("pull (noblock)")
            MQ.exec("set (osr, null)")
        MQ.active(0)
        
        LOG("INFO: TX/RX FIFO successfully cleared. Operation finished", 0)
        
        BLINK_ERROR()
        
        MQ.active(1)
        
        LOG("INFO: Ending watchdog. Operation ended normally", 0)
        
    kill = False
    busy = False
    
    return


def COPY_FILE(src_file, dst_file):                                                          # Copy the large .TAP file to Pico's internal flash
                                                                                             # best compatibility and performance
    global dead
    global busy
    global led
    
    dead = False
    
    buf = bytearray(512)
    bytes_rd = 0
    
    led.value(1)
    
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
                            
    led.value(0)
    dead = True
    
    del buf                                                                             # OPTIMIZATION - CHECK!       
    gc.collect()
    
    while busy:
        pass
    
    return


def DCK_IMAGE():                                                                              # Generates a full 64Kb image from a .DCK file
                                                                                              # This will be used by the Flash write pgm
    gc.collect()
    header = bytearray(9)
    chunk_len = 8192
    empty = bytearray(chunk_len)
    cur_chunk = bytearray(chunk_len)
    
    LOG("INFO: Start processing DCK file", 0)
    
#     try:
#         os.remove("/TMP/temp.bin")
#     except:
#         pass

    f_in = open("/TMP/temp.bin", "rb")
    f_out = open("/TMP/temp_dck.bin", "wb")

    f_in.readinto(header)

    if header[0] != 0x00:
        LOG("CRITICAL ERROR! Not a valid DOCK image; wrong header. Aborting...", 3)
        
        f_in.close()
        f_out.close()
        gc.collect()
        
        return False

    LOG("INFO: DCK header:" + str(header), 0)

    for el in range(1, 9):                                                              # Byte 0 is bank, bytes 1-8 are the 8x 8kb chunk types
        if (header[el] == 0x00 or header[el] == 0x01):                                  # Non-existent chunk type (8kb data is not in the file)
            f_out.write(empty)	
        elif header[el] == 0x02 or header[el] == 0x03:                                  # Chunk data is in the file
            f_in.readinto(cur_chunk)
            f_out.write(cur_chunk)
        else:                                                                           # Invalid
            LOG("CRITICAL ERROR! Not a valid DOCK image; wrong chunk type. Aborting...", 3)
            f_in.close()
            f_out.close()
            gc.collect()
            
            return False        

    LOG("INFO: Image of DCK file generated succesfully", 0)
    
    f_in.close()
    f_out.close()
    
    os.remove("/TMP/temp.bin")
    os.rename("/TMP/temp_dck.bin", "/TMP/temp.bin")
    
    gc.collect()
    
    return True


def DIR_FILES():                                                                             # Get all files and directories from current path
    
    global files
    global dirs
    global lista
    global files_upper
    global isdir
    
    files = []
    dirs = []
    files_upper = []
    lista = ""
    header = ""
    isdir = {};
    
    dirinfo = []
    tap_blk = []
    tap_hdr = []
    num_dirs = 0
    num_files = 0
    
    ext = ['TAP', 'TZX', 'DCK', 'ROM', 'BIN']                                                 # extensions to be included 
    starts = ['.']                                                                            # first characters of files to be excluded
    
    ordered = True                                                                            # In the future, this could be controlled by an option
    
    try:
        os.remove("dirinfo.tap")
    except:
        pass
    
    if ordered:
        listing = sorted(os.ilistdir(), key=lambda fname: fname[0].lower())
    else:
        listing = [item for item in os.ilistdir()]
    
    sd_block = os.statvfs("")[0]
    sd_tot = os.statvfs("")[2]
    sd_free = os.statvfs("")[3]
    
    sd_free = (sd_free * sd_block) / 1_073_741_824
    sd_tot = (sd_tot *sd_block) / 1_073_741_824
    
    sd_stat = "SD: " + '%02.4f' % (sd_tot ) + "GB; free: " + '%02.4f' % (sd_free) + "GB"
    sd_stat = "%-32s" % (sd_stat)

    for archs in listing:
        uname = archs[0].upper()
        if archs[1] == 16384:
            nom = archs[0][:20]
            new_item = ("%-32s" %  nom )
            dirinfo.append(new_item)
            dirs.append(archs[0])
            isdir[uname] = True
            lista += "%-22s" % ("<" + nom + ">") + "%10s" % "0 b"
        else:
            isdir[uname] = False
    num_dirs = len(dirinfo)
    
    i = 0
    
    for archs in listing:
        if archs[1] == 32768:
            if (archs[0][-3:].upper() not in ext) or (archs[0][0] in starts):
                continue
            
            nom = archs[0]
            size = len(nom)
            j = nom.find('.')
            if size > 18:
                if j >= 0: # There is a file extension
                    # A ">" before the dot means the long name was truncated
                    nom = nom[:17-(size-j)] + ">" + nom[j:]
                else: # No extension
                    nom = nom[:17] + ">"
            else:
                nom = "%-18s" % (nom)
            nom = "%03d " % i + nom[:18]

            size = int(archs[3])
            if size >= 1024:
                size = size / 1024
                size_txt = "%.2f" % (size) + " Kb"
            else:
                size_txt = str(size) + " b"
            a = nom + "%10s" % (size_txt)
            lista += a
            new_item = (a)
#             new_item = new_item[4:]
            dirinfo.append(new_item)
            files.append(archs[0])
            files_upper.append(archs[0].upper())
            i += 1
    
    header = "Path:" + public_path()
    header = header[:32]
    header = "%-32s" % (header)
    header += sd_stat 
    header += "%-22s" % "File Name" + "%-10s" % "    Size"  
    header += "--------------------------------"
    
    if not lista:
        lista = "%-32s" % ("Directory is empty")
    lista = header + lista

    num_files = len(dirinfo) - num_dirs
    
    new_item = "%-32s" % (num_dirs)
    dirinfo.insert(0, new_item)
    
    new_item = "%-32s" % (num_files)
    dirinfo.insert(1, new_item)
    
    tap_blk = (NEW_TAPBLK(dirinfo, 32))
    long = len(tap_blk) - 4                                        # this is the pure data blk size stored in header; it's the block minus the first 4 bytes
    fname = "dirinfo"
    tap_hdr = NEW_HDR(2, fname, long)                             # generate header for each block, with parameters
    
    with open("dirinfo.tap", "wb") as f_out:
        f_out.write(tap_hdr)                                          # now write the header
        f_out.write(tap_blk)                                           # and then the block

    return 


def FINISH(msg, success):                                                                 # For use with UPDATE() function. Logs the final status msg, and blinks LED at different intervals, to indicate 
                                                                                          # either success or fail. msg=text to be displayed/logged; success=boolean if status is ok or failed
    if success:
        interval = 0.8
    else:
        interval = 0.08
    
    led = Pin(25, Pin.OUT)
    
    LOG(msg, 4)
    SAVE_LOG()
    
    os.umount("/sd")
    
    while True:
        led.toggle()
        time.sleep(interval)
        

def LOG(msg, level):                                                                    # Adds a timestamped new entry to log_entries
    
    global log_entries
    global log_to_serial
    global TSP
    
    if log_to_serial:                                                                    # If enabled, send log msg to console instead of logfile
        print(msg)
    
    if TSP.LOG_LEVEL:                                                                    # TSP is not initialized at startup, so this check is required
        if level < TSP.LOG_LEVEL:
            return
    
    log_entries += "[" + str(time.ticks_us()) + "] "                                    # on Pico W, timestamp can be replaced by local time provided by ntp
    log_entries += msg + "\n"
    
    return


def MOUNT_FILE(f_name, remounting=False):                                                    # Mount file from a LOAD "tpi:..." command
                                                                                             # and performs actions according to file type
    """Mount the given file f_name. On failure, optionally remount the
    previously mounted file. The remounting flag is used internally to
    prevent infinite recursion.

    Side effects:
    - Calls ACTIVATE_SD() at start, DEACTIVATE_SD() + ACTIVATE_MQ() at end
    - Only commits TSP.f_name on success (caller does NOT need to save/restore)
    """
    global TSP
    global led

    U3_CS = Pin(28, Pin.OUT, Pin.PULL_UP)
    U3_CS.value(1)

    TSP.offset = 0
    TSP.tap_idx = 0
    TSP.offset_tbl = []
    TSP.append = False

    try:
        os.remove("/TMP/temp.tap")
        os.remove("/TMP/temp.bin")
    except:
        pass

    msg = "INFO: File " + f_name + " mounted correctly"
    err_level = 0
    remount = False                                  # True = trigger remount of previous file on failure

    ACTIVATE_SD()
    led.value(1)

    totlen = os.stat(f_name)[6]

    if f_name[-4:].upper() in [".BIN", ".DCK", ".ROM"]:

        COPY_FILE(f_name, "/TMP/temp.bin")

        if f_name[-4:].upper() == ".DCK":

            if DCK_IMAGE():
                COPY_FILE("/assets/dckupdate.tap", "/TMP/temp.tap")              # Special 'seudo' TAP that contains Flash/SRAM DCK update program
            else:
                err_level = 2
                remount = True
                msg = "ERROR: creating DCK image for " + f_name + ". See logfile for details"

        else:

            len_hi = int(totlen / 256)
            len_lo = totlen - (len_hi * 256)

            try:
                with open("/assets/romupdate.tap", "rb") as f_in:                 # Same for updating ROM images. We open the seudo TAP, as we need to update it
                    buf = bytearray(f_in.read())

                # Parse the romupdate.tap file blocks to get the offset of block 3
                # where the machine code is. As long as the MC doesn't change those
                # offsets, and they are in block 3 of the .tap, you can change the
                # BASIC program and not change this code.
                x = 0
                for i in range(2):
                    l = buf[x] + 256 * buf[x+1]                              # length of block
                    x += l + 2

                x += 104                                                     # offset to first length location
                buf[x]   = len_lo                                            # update TAP file ML routine, with length of block
                buf[x+1] = len_hi                                            # to be written to the Flash/SRAM

                x += 200                                                     # offset to second length location
                buf[x]   = len_lo                                            # Same for second part of ML routine (Update LOWER block)
                buf[x+1] = len_hi
                remount = True                                               # if writing fails, try a remount

                with open("/TMP/temp.tap", "wb") as f_out:                   # And we update the seudo TAP
                    f_out.write(buf)
            except:
                err_level = 2
                msg = "ERROR: copying romupdate.tap"

    elif f_name[-4:].upper() == ".TAP":

        s = os.stat(f_name)
        if s[6] != 0:                                                        # An empty .tap is OK, otherwise check it
            with open(f_name, "rb") as f_check:

                file_type = f_check.read(7)
                if file_type.decode() == "ZXTape!":
                    msg = "ERROR!: Wrong file type while mounting: " + f_name + ". It's a TZX file"
                    err_level = 2

                if ((int(file_type[0]) > 19)):
                    msg = "INFO: Non-standard first block while mounting file " + f_name + ". Expected 19, read " + str(int(file_type[0]))

        if err_level < 2:
            COPY_FILE(f_name, "/TMP/temp.tap")

    else:
        msg = "ERROR!: Wrong filename while mounting: " + f_name
        err_level = 2

    # Single SD→MQ transition for ALL paths.
    # ready=False keeps GPIO 12 LOW (Z80 sees "not ready") until the
    # response is loaded into the FIFO and MQ_READY() is called by SEND_MSG.
    DEACTIVATE_SD()
    ACTIVATE_MQ(ready=False)

    LOG(msg, err_level)

    if err_level > 1:
        LOG("ERROR: Failed to mount: " + f_name, err_level)
        BLINK_ERROR()
        if remounting or not TSP.f_name:
            # Don't recurse further, but don't leave a bad file mounted
            UNMOUNT_INTERNAL()
        elif remount:
            # Try re-mounting the previously mounted file
            if MOUNT_FILE(TSP.f_name, True):
                err_level = 0
                LOG("INFO: Remounted " + TSP.f_name, 0)
    else:
        try:
            TSP.totlen = os.stat("/TMP/temp.tap")[6]                         # We mount this file as a regular TAP to perform Flash write
            TSP.f_name = f_name                                              # COMMIT only on success
            TSP.append = False
            OFF_TABLE()                                                      # Build offset table from /TMP/temp.tap
        except:
            UNMOUNT_INTERNAL()

    led.value(0)
    return (err_level == 0)


def UNMOUNT_INTERNAL():
    """Internal version of UNMOUNT (no Z80 response). Used by MOUNT_FILE
    error path so we don't try to send messages while the bus is
    transitioning."""
    global TSP
    TSP.f_name = ""
    TSP.offset_tbl = []
    TSP.offset = 0
    TSP.tap_idx = 0
    TSP.append = False
        

def NEW_HDR(type_hdr: int, fname, long: int):                      # This routine returns a new TAP header with the required parameters: header type, file name, and length of data block
    
    if (long < 0 or long > 65535):                                 # Validate data block length
        LOG("ERROR!!! Wrong block length in NEW_HDR", 2)
        return
    
    if (type_hdr > 3) or (type_hdr < 0):
        LOG("ERROR!!! Wrong header type in NEW_HDR", 2)                  # Also validate header type 
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
    offset_tbl = []
    
    blks = ['Program', 'Number arr.', 'Char arr.', 'Code blk']
    
    while TSP.offset < TSP.totlen:
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
    if TSP.totlen > 0:
        del rd_bytes
    
    arch.close()
    gc.collect()
    
    return


def PARAMS(pre):                                                                         # Returns calculated parameters from pre-header
    
    par1 = (pre[4] * 256) + pre[3]
    par2 = (pre[6] * 256) + pre[5]
        
    return par1, par2


def RESTORE_FILES(src, dst):                                                             # Restores prev backed-up files; typically scr=/sd/BACKUP - dst = / (root of the Flash)

    if os.stat(src)[0] == 0x4000:
    
        for el in os.listdir(src):
            f_name = src + '/' + el
            
            if (dst == "/"):
                new_path = dst + el
            else:
                new_path = dst + '/' + el
                
            if os.stat(f_name)[0] == 0x4000:
                
                LOG("Restoring folder " + f_name, 4)
                SAVE_LOG()
                
                try:
                    os.mkdir(new_path)
                    LOG("RESTORE: folder " + new_path + " not found; succesfully created", 4)
                    SAVE_LOG()
                
                except:
                    LOG("WARNING: Folder " + new_path + " already exists during RESTORE. Moving on", 4)
                    SAVE_LOG()
                
                RESTORE_FILES(f_name, new_path)
                
            else:
                
                LOG("Restoring file " + f_name + " to " +  new_path, 4)
                SAVE_LOG()
                
                COPY_FILE(f_name, new_path)


def SAVE_LOG():                                                                         # Saves log_entries to the 'activity.log' file in flash
    
    global busy
    global log_entries
    
    busy = True
    
    with open("/activity.log", "a") as logfile:
        logfile.write(log_entries)
        
    log_entries = ""
    
    busy = False

    return


def CLEAR_LOG():                                                                         # Clear log_entries and the 'activity.log' file in flash
    
    global busy
    global log_entries
    
    busy = True
    ok = True

    try:
        with open("/activity.log", "w") as logfile:
            #logfile.truncate() # being explicit but seems to fail
            log_entries = ""
        LOG("INFO: Log file was cleared", 0)
    except:
        LOG("ERROR: clearing log file", 2)
        ok = False

    busy = False

    return ok


def SEND_MSG(msg, msg1, st: bytes, forceDisplay=False):                                         # Sends one-line status message(s)
                                                                                                # back to the TS, once a command is finished
    global MQ
    global TSP

    # NO TLM HERE — Z80 polling $0F. Get to FIFO load + MQ_READY ASAP.
    wrt = MQ.put

    # Dual-port: continue flag (was wrt(0x40)) is now signaled via
    # MQ_READY() on port $0F. Only the data bytes go into the TX FIFO.
    if TSP.VERBOSE or forceDisplay:

        wrt(0x81)               # PRINT STRING — this IS the D-block status
        wrt(st)                 # Return code
        wrt(0x0D)               # Start with a newline
        for m in msg:           # Write message
            wrt(m)              # Will let ~ and | pass as FREE and STICK
        if msg1:                # Write msg1
            wrt(0x0D)
            for m in msg1:
                wrt(m)
        wrt(0x00)               # End of string

    else:

        wrt(st)                 # Return code — IS the D-block status

    MQ_READY()                  # Z80 sees "ready" on port $0F → reads bytes from $0E

    # Now safe to TLM
    TLM("SEND_MSG enter+loaded", "msg=%r msg1=%r st=%d verbose=%s force=%s" % (
        msg[:30] if isinstance(msg, str) else msg, msg1, st, TSP.VERBOSE, forceDisplay))

    drain_loops = 0
    while(MQ.tx_fifo() != 0):   # Wait until Z80 has drained the FIFO
        drain_loops += 1
        if drain_loops > 1000000:
            TLM("SEND_MSG STUCK", "tx still has %d bytes after 1M loops" % MQ.tx_fifo())
            break

    TLM("SEND_MSG exit", "drain_loops=%d" % drain_loops)
    # NOTE: do NOT call MQ_BUSY() here. The Pico is ready for the next
    # command — staying ready is correct. MQ_BUSY() is reserved for
    # genuine slow operations (SD card access in MOUNT_FILE).
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

    scroll = "scroll? (Y/n)"
    if not new_rom:
        scroll += chr(13)
    s = len(scroll)
    n = len(msg)

    wrt = MQ.put
    # CRITICAL: load FIFO + signal ready WITHOUT any TLM/print between.
    # Z80 has been polling $0F since the end of PROCESS_CMD's cmd-block
    # drain. Only ~2.8ms before WF_NPH timeout. NO prints here.
    wrt(0x86)   # PRINT STRING WITH LOOP — this IS the D-block status
    wrt(st)     # BASIC return code
    wrt(0x0D)   # Start with a newline
    MQ_READY()  # Z80 sees "ready" on port $0F → can read header bytes

    # Now safe to TLM and do non-time-critical work.
    while (MQ.rx_fifo() > 0):   # Flush receive buffer?
        MQ.get()
    
    # We handle each character. If a scroll answer is N, we will just break

    c = 0 # char count
    l = 0 # line count
    ll = 21 # Initial line limit
    if not new_rom:
        wrt(0x0D)       # Another newline for old ROM
    i = -1
    prompt = True
    m = ""

    while i < n - 1:
        
        i += 1
        ch = ord(msg[i]) # needed to be able to test ch == int

        # Handle some special characters. Not handling keywords though.
        if ch >= 0x10 and ch <= 0x15:
            # Attribute control: two chars that don't move the column
            # For now, just eat these since they don't advance the column and 
            # many have the second byte as 0 which will end the current print string.
            i += 1
            continue
        elif ch == 0x00 or ch == 0x03:
            # Not allowed since the mark the end of the strings to send
            ch = 0x3F # '?'
            c += 1
        elif ch == 0x08 and (l>0 or c>0):
            # Handle a backspace character
            if c == 0:
                c = 31
                l -= 1
            else:
                c -= 1
        elif ch == 0x0D:
            # Timex or PC line ending
            if i+1 < n and ord(msg[i+1]) == 0x0A:
                # PC line ending
                i += 1 # Skip the 0x0A
            c = 32 # End of line
        elif ch == 0x0A:
            # Unix line ending
            ch = 0x0D # Change to Timex
            c = 32 # End of line
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
        elif ch == 124: # Tilde will expand to FREE
            if expandKeywords:
                c += 6
            else:
                ch = 63
                c += 1
        elif ch == 126: # vbar will expand to STICK
            if expandKeywords:
                c += 7
            else:
                ch = 63
                c += 1
            # DELETE, ON ERR, SOUND, and RESET don't expand to keywords in L mode
        elif ch > 127:
            # Currently printing high-bit chars crashes, so protect this.
            ch = 63 # '?'
            c += 1
        else:
            c += 1

        wrt(ch) # If 0x0D or we wrote to the last column, next will be on a new line

        if c == 32: # written one line

            if ch == 0x0D:
                if i == 0 or (i == 1 and msg[1] == chr(0x0A)):
                    # Newline at start we don't count.
                    # This allows you to put a blank line at the start to 
                    # separate the message from the prior text but not count
                    # toward the first screen scroll lines.
                    l -= 1
            else: # if ch != 0x0D:
                # Check for newline at end of 32
                if i + 1 < n:
                    nx = ord(msg[i+1])
                else:
                    nx = 0
                if nx == 0x0D: # Timex or PC
                    if i + 2 < n and ord(msg[i+2]) == 0x0A:
                        i += 1 # Skip extra PC EOL char
                    continue # skip it
                elif nx == 0x0A: # Unix
                    continue # skip it
                else: # Write a nl
                    wrt(0x0D)
            l += 1

            if l == ll and (not new_rom or n > i + 34):

                l = 0 # reset line count
                if not new_rom and i == n - 1:
                    scroll = "--- End of list (N to exit) ---"+ chr(13)

                for m in scroll:    # Write scroll prompt (empty if last screen)
                    wrt(m)

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
                
                if new_rom:
                    for b in range(s):      # Erase scroll prompt
                        wrt(0x08)
                        wrt(0x20)
                        wrt(0x08)
                else:
                    wrt(0x0D)       # Another newline for old ROM

            c = 0 # reset column count
        
    wrt(end_char)               # Write end_char (done with loops)
    TLM("SEND_MSG2 end_char written", "0x%02X" % end_char)

    drain_loops = 0
    while(MQ.tx_fifo() != 0):   # Write out message
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


##########################
# LOAD COMMAND FUNCTIONS #
##########################


def LD_NOT_IMP():                                                                       # Output for not implemented LOAD Command 
    
    SEND_MSG("CMD OK but not yet implemented", "", _5_C_Nonsense)
    
    return


##########################
# SAVE COMMAND FUNCTIONS #
##########################


def DIR(pre, cmd):                                                                              # Directory listing

    # SAVE "tpi:dir"            - Normal directory of files
    # SAVE "tpi:dir"CODE 1,nn   - Show long name for file nn
    # SAVE "tpi:dir"CODE 2,0    - Show a dir of files with their index and whole names

    global lista
    global led
    global files
    global files_upper
    global MQ
    global TSP

    par1, par2 = PARAMS(pre)
    nl = chr(13)

    TLM("DIR enter", "par1=%d par2=%d files=%d lista_len=%d" % (
        par1, par2, len(files) if files else 0,
        len(lista) if lista else 0))

    if par1 == 0: # CODE 0,0 or CODE 0,1 passed from CD, MD, etc.
        # Regular listing
        TLM("DIR par1=0 — regular listing via SEND_MSG2")
        led.value(1)
        SEND_MSG2(nl + lista, 1, False)
        TLM("DIR SEND_MSG2 returned")
        led.value(1)
        utime.sleep(2)
        led.value(0)

    elif par1 == 1:

        # Long name of a file by index
        if par2 >= len(files):
            msg = "ERROR: file index %d too large" % par2
            LOG(msg, 2)
            SEND_MSG(msg, "", _6_6_Num2Big)
        else:
            SEND_MSG("Path: " + public_path(), "File: " + files[par2], _1_OK, True)

    elif par1 == 2 or par1 == 3:

        n = len(files)
        hdr = nl + "Path:" + public_path() + nl
        idx = 0

        if par1 == 2:

            # Index and full names of only files
            msg = hdr
            msg += "  #  File Name         %3d files" % n
            msg += "---- ---------------------------"
            for f in files:
                msg += ">%03d %s" % (idx, f) + nl
                idx += 1
            SEND_MSG2(msg, 1)

        else: # par1 == 3:

            # Interactive dir
            oldfname = TSP.f_name
            oldindex = TSP.tap_idx
            oldoffs  = TSP.offset
            oldappend= TSP.append
            wrt = MQ.put
            # Dual-port: continue flag now on port $0F via MQ_READY
            wrt(0x86)   # PRINT STRING WITH LOOP
            wrt(1)      # BASIC return code
            wrt(0x0D)   # Start with a newline
            MQ_READY()  # Z80 sees "ready" on port $0F
            while (MQ.rx_fifo() > 0):   # Flush receive buffer?
                MQ.get()
            sel = -1
            pgs = n // 10 + 1

            while idx < n:
                for i in range(6):
                    wrt(0x0D)
                i = 0
                pg = "%d of %d" % (idx // 10 + 1, pgs)
                msg = hdr
                msg += "# Idx File Name         %8s" % pg
                msg += "- --- --------------------------"
                while i < 10 and idx + i < n:
                    msg += "%d:%03d %s" % (i, idx + i, files[idx+i]) + nl
                    i += 1
                msg += "--------------------------------"
                msg += nl + "0..9 to mount, N=stop," + nl + "B=back, or other for next:"
                # Write screen
                for m in msg:
                    wrt(m)
                wrt(0x00)       # End of this string
                wrt(0x40)       # Start new string
                ch = MQ.get()   # Get a key
                if ch == 78:    # 'N' then done (ROM ended the loops)
                    return # OK
                wrt(0x08)
                wrt(':')
                wrt(ch)
                wrt(0x0D)
                if ch == 66: # B
                    if idx >= 10:
                        idx -= 10
                    else:
                        idx = 0
                elif ch >= 48 and ch <= 57:
                    j = idx + ch - 48
                    if j < n:
                        # Mount it
                        sel = j
                        break
                    idx += i
                else:
                    idx += i
                # Back to top for next screenful

            if sel >= 0:
                for m in "Mounting: %s" % files[sel] + nl:
                    wrt(ord(m))
            wrt(0x03) # End string loop
            while(MQ.tx_fifo() != 0):   # Write out message
                pass
            while(MQ.rx_fifo() != 0):   # Flush input buffer to console
                print(MQ.get())
            
            if sel >= 0:
                # MOUNT_FILE handles SD activation, MQ restoration, and
                # remount-on-failure internally. Don't manage TSP.f_name here.
                if not MOUNT_FILE(TSP.cur_path + '/' + files[sel]):
                    LOG("ERROR: failed to mount: " + TSP.cur_path + '/' + files[sel], 2)
                    try:
                        if MOUNT_FILE(oldfname):
                            TSP.tap_idx = oldindex
                            TSP.offset  = oldoffs
                            TSP.append  = oldappend
                    except:
                        LOG("ERROR: failed to re-mount: " + oldfname, 2)
                        UNMOUNT_INTERNAL()

    else:
        msg = BAD_CODE("DIR", par1, par2)
        LOG("ERROR: " + msg, 2)
        SEND_MSG(msg, "", _8_A_Invalid_arg)
  
   
def PATH(pre, cmd):                                                                             # Show current directory
    
    # SAVE "tpi:path"               - Show current path
    # SAVE "tpi:path"CODE 1,0       - Show current mounted file path

    global TSP
    
    par1, par2 = PARAMS(pre)

    if par1 == 0:
        SEND_MSG("Current working dir is: ", public_path(), _1_OK, True)
    else:
        if TSP.f_name:
            SEND_MSG("Current mounted file is: ", public_fname(), _1_OK, True)
        else:
            SEND_MSG("No file mounted!", "", _1_OK, True)
    
    return
    

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

    # if TSP.offset_tbl:
    if TSP.f_name:

        nom = "File: " + public_fname()
        if len(nom) > 32:
            nom = nom[:15] + ".." + nom[-15:]
        else:
            nom = "%-32s" % (nom)
        nom += "Pointer at block: %02d, Append:" % TSP.tap_idx
        if TSP.append:
            nom += "on "
        else:
            nom += "off"
        if par1 == 0:
            nom += " #  Offset   Len  Hdr?   Desc.  "
        elif par1 == 1:
            nom += " #  File         Len  Desc.     "
        else:
            msg = BAD_CODE("TAPDIR", par1, par2)
            LOG("ERROR: " + msg, 2)
            SEND_MSG(msg, "", _8_A_Invalid_arg)
            return
        nom += "--------------------------------"

        if not TSP.offset_tbl:

            nom += "<empty file>"

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
                            nom += ">%02d " % idx
                        else:
                            nom += " %02d " % idx
                            
                        nom += "%6s  " % el[0]  # Offset
                        nom += "%5s " % el[1]   # Len
                        nom += el[2] + "  "     # Hdr?
                        nom += "%-10s" % el[3]  # Desc.
                    
                    idx += 1
                
            else: # Header listing

                for el in TSP.offset_tbl:

                    if idx >= idx1 and idx <= idx2:

                        if el[2] == " Y" or idx == TSP.tap_idx:

                            # Block number
                            if idx == TSP.tap_idx:
                                nom += ">%02d " % idx
                            else:
                                nom += " %02d " % idx
                            if el[2] == " Y":
                                nom += "%-11s " % TSP.offset_tbl[idx+1][3] # File type
                                nom += "%5s " % TSP.offset_tbl[idx+1][1]   # Len
                            else:
                                nom += "Data block  "
                                nom += "%5s " % el[1] # Len
                            nom += "%-10s" % el[3]    # Desc.
                    
                    idx += 1

    else:
        nom = " --  No .TAP file mounted!  --  "
        LOG("WARNING: no file mounted in TAPDIR", 1)
        
    SEND_MSG2(nom, 1)

    return


def NEW_TAP(pre, cmd):

    # Create a new empty tap file of the given name and mount it.
    # SAVE "tpi:tap name"       # 
    # SAVE "tpi:tap name.tap"   # 

    arg = getArgs(cmd)
    if arg == "":
        msg = "Name required for new .tap file"
        LOG("ERROR: " + msg, 1)
        SEND_MSG(msg, "", _3_F_Invalid_file, True)
        return
    # Check for extension
    jarg = arg.find('.')
    if jarg >= 0 and arg[jarg:].lower() == '.tap':
        filename = "%s" % arg[:jarg]
    else:
        filename = "%s" % arg
    # Make new .tap file name
    filename = filename.strip()
    # Check for invalid chars
    clean_fname = ''.join(l for l in filename if (l>=' ' and l<chr(127) and (l not in r':*\/|"<>')))
    if clean_fname != filename or clean_fname == "":
        msg = 'Filename "%s" not allowed' % filename
        LOG("ERROR: " + msg, 2)
        SEND_MSG(msg, "", _3_F_Invalid_file)
        return
    filename = clean_fname + ".tap"
    filename = TSP.cur_path + "/" + filename

    # Make new empty .tap file
    try:
        ACTIVATE_SD()
        with open(filename, "w") as newfile:
            pass
        LOG("New empty file: " + filename, 0)
        os.chdir(TSP.cur_path)
        DIR_FILES()
        DEACTIVATE_SD()
        ACTIVATE_MQ()
    except:
        msg = "Can't create empty file: "
        LOG("ERROR: " + msg + filename, 2)
        SEND_MSG(msg, filename, _4_Q_Parameter)
        return

    # Mount .tap file
    # MOUNT_FILE handles ACTIVATE_SD/DEACTIVATE_SD/ACTIVATE_MQ internally
    # and only commits TSP.f_name on success. We save the previous index/offset
    # state for the manual remount-and-restore flow below.
    oldname = TSP.f_name
    oldidx  = TSP.tap_idx
    oldoff  = TSP.offset
    oldapp  = TSP.append

    if not MOUNT_FILE(filename):
        msg = "Failed to mount new .tap file: "
        LOG("ERROR: " + msg + filename, 2)
        st = _4_Q_Parameter
        if oldname:                                    # Re-mount previous file
            if MOUNT_FILE(oldname):
                TSP.tap_idx = oldidx
                TSP.offset = oldoff
                TSP.append = oldapp
            else:
                TSP.f_name = ""
    else:
        # Set append on
        TSP.append = True
        msg = "New .tap file mounted: "
        LOG("INFO:" + msg + filename, 0)
        filename = public_fname()
        st = _1_OK
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
    # Expand or replace character
    ch = ord(m)
    if ch < 32 or ch > 127:
        return '?'
    elif ch == 124:
        return ' STICK '
    elif ch == 126:
        return ' FREE '
    else:
        return m


def xstr(s):
    # Expand or replace chars in string
    x = ""
    for m in s:
        x += xchr(m)
    return x


def public_path():                                                                                     # Returns the public version of the path
    
    global TSP
    
    return xstr("/" + TSP.cur_path[4:])
    

def public_fname():                                                                                     # Returns the public version of the TSP.f_name
    
    global TSP
    
    if TSP.f_name:
        return xstr(TSP.f_name[3:])
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
    
    status = _1_OK
    msg2 = ""
    viz = False
    par1, par2 = PARAMS(pre)
    arg = getArgs(cmd)
    arg = arg.lower()

    if arg != '':
        par1 = 1
        if arg == 'on':
            par2 = 1
        elif arg == 'off':
            par2 = 0
        else:
            msg = "APPEND: Bad argument: %s" % arg
            LOG("ERROR: " + msg, 2)
            par2 = -1

    if par1 == 0:
        # Display
        if not TSP.f_name:
            msg = "No file mounted"
        elif TSP.append:
            msg = "Append is ON"
        else:
            msg = "Append is OFF"
        SEND_MSG(msg, "", _1_OK, True)

    elif par1 == 1:
        # Set
        if par2 < 0:
            SEND_MSG(msg, "", _8_A_Invalid_arg)
        elif TSP.f_name:
            TSP.append = (par2 != 0)
            if TSP.append:
                msg = "Append new files to: "
            else:
                msg = "Append is OFF for: "
            LOG("INFO: " + msg + public_fname(), 0)
            SEND_MSG(msg, public_fname(), _1_OK)
        else:
            msg = "No file mounted. Append failed."
            LOG("ERROR: " + msg, 2)
            SEND_MSG(msg, "", _4_Q_Parameter)
    else:
        msg = BAD_CODE("APPEND", par1, par2)
        LOG("ERROR: " + msg, 2)
        SEND_MSG(msg, "", _8_A_Invalid_arg)

    return 


def BLKRCV(pre, cmd):                                                                                  # 'Internal' command to send block to be written to Flash
    
    global MQ
    global TSP
    global led
    
    wrt = MQ.put
    
    status = _1_OK
    buf = []
    
    led.value(1)
    
    if TSP.f_name[-4:].upper() == ".DCK":

        wrt(status)
        MQ_READY()                          # dual-port: continue flag via port $0F

        buf = bytearray(32768)
        
        with open("/TMP/temp.bin", "rb") as file:
            
            for i in range(2):
                file.readinto(buf)
                for el in buf:
                        wrt(el)
                        
        del buf
        gc.collect()
        
        LOG("INFO: DCK image write successfully completed", 0)
        
    elif TSP.f_name[-4:].upper() in [".BIN", ".ROM"]:
        
        file_len = os.stat("/TMP/temp.bin")[6]
        send_len = file_len
        
        par1, par2 = PARAMS(pre)
        
        if ((par1 + par2) > file_len):
            status = _4_Q_Parameter
            BLINK_ERROR()

        wrt(status)
        MQ_READY()                          # dual-port: continue flag via port $0F
        
        if (status == 1):
            
            rd_offset = par2
            
            if (par1 != 0):
                send_len = par1
            else:            
                send_len = file_len - rd_offset
            
            buf = bytearray(send_len)
            
            with open("/TMP/temp.bin", "rb") as file:
                file.seek(rd_offset)
                file.readinto(buf)
                
            for el in buf:
                    wrt(el)
                    
            del buf            
            gc.collect()
            
        led.value(0)
        
        LOG("INFO: ROM image write successfully completed", 0)
    
    return


def ChangeDir(potential_new_path, SDactive = False):

    global TSP
    global MQ

    status =  _1_OK
    if not SDactive:
        ACTIVATE_SD()

    if potential_new_path == ".." and TSP.cur_path.count("/") > 2:
        # remove the last element from the current path
        # unless the last element is TAP
        #print("attempt to move up one directory")
        path_list = list(TSP.cur_path.split("/"))       # convert current path to a list
        path_list.pop(0)  # remove the first element, which is blank
        path_list.pop()   # remove the last element
        new_path = "/".join(path_list)
        
    elif potential_new_path == ".." and TSP.cur_path.count("/") == 2:
        new_path = "/sd/TAP"
        
    elif potential_new_path == "/":
        # move to the top
        new_path = "/sd/TAP"
        
    elif (dir_exists(TSP.cur_path + "/" + potential_new_path)):
        new_path = TSP.cur_path + "/" + potential_new_path
        
    else:
        # no changes bc it doesn't meet any of the tests above
        new_path = TSP.cur_path
        status = _3_F_Invalid_file

    #new_path = cur_path + "/" + cmd[10:]
    #print (cur_path,new_path)
    #os.chdir(cur_path)

    #message = "Changed dir to: "  + cmd[10:]
    #status = 1

    if status == _1_OK:
    
        try:
            os.chdir(new_path)
            TSP.cur_path = os.getcwd()
        except:
            status = _4_Q_Parameter
        
    if status == _1_OK:
        message = "Changed dir to: "  + potential_new_path
        LOG(message, 0)
        gc.collect()
        DIR_FILES()
    else:
        message = "OS error changing to: "  + potential_new_path
        LOG("ERROR: " + message, 2)
            
    if not SDactive:
        DEACTIVATE_SD()
        ACTIVATE_MQ()

    return status, message


def CDIR(pre, cmd):                                                                                            # Changes path to specified DIRectory
    
    # tpi:cd name
    # SAVE "tpi:cd name"            - Change current directory to name (can be . or .. as well)
    # SAVE "tpi:cd name" CODE 1,0   - Change dir and then do a tpi:dir
    # SAVE "tpi:cd name" CODE 2,0   - Change dir and then display new path
    # SAVE "tpi:cd "                 - Interactive CD

    # global TSP
    # global MQ
    global lista
    
    status = _1_OK
    par1, par2 = PARAMS(pre)
 
    potential_new_path = getArgs(cmd)

    if potential_new_path == "":
        ChangeDirMenu()
        return

    status, message = ChangeDir(potential_new_path)

    if par1 == 1 and par2 == 0:
        SEND_MSG2(chr(13) + lista, 1, False)
    else:
        SEND_MSG(message, "Current: " + public_path(), status, par1 == 2 and par2 == 0)

    return 


def ChangeDirMenu():

    # Interactive cd

    global TSP
    global MQ
    global dirs

    nl = chr(0x0D)
    D = ['..'] + dirs
    n = len(dirs) + 1

    hdr  = nl + "Path:" + public_path() + nl

    wrt = MQ.put
    # Dual-port: continue flag now on port $0F via MQ_READY
    wrt(0x86)   # PRINT STRING WITH LOOP
    wrt(0x01)   # BASIC return code
    wrt(0x0D)   # Start with a newline
    MQ_READY()  # Z80 sees "ready" on port $0F
    while (MQ.rx_fifo() > 0):   # Flush receive buffer
        MQ.get()
    sel = ""
    nmax = 16 # Max files to show at a time
    L = '0123456789QWERTYUIOP'
    idx = 0
    pgs = n // nmax + 1
    
    while idx < n:
        for i in range(15 - nmax):
            wrt(0x0D)
        i = 0
        pg = "%d of %d" % (idx // nmax + 1, pgs)
        msg  = hdr
        msg += "# Directory Name        %8s" % pg
        msg += "- ------------------------------"
        while i < nmax and idx + i < n:
            msg += "%c: %s" % (L[i], D[idx+i]) + nl
            i += 1
        msg += "--------------------------------"
        msg += nl + "0..9, Q..P to CD, N=stop," + nl + "B=back, or other for next:"
        # Write screen
        for m in msg:
            wrt(m)
        wrt(0x00)       # End of this string
        wrt(0x40)       # Start new string
        ch = MQ.get()   # Get a key
        if ch == 78:    # 'N' then done (ROM ended the loops)
            return
        wrt(0x08)
        wrt(':')
        wrt(ch)
        wrt(0x0D)
        if ch == 66: # B
            if idx >= nmax:
                idx -= nmax
            else:
                idx = 0
        else:
            j = L.find(chr(ch))
            if j >= 0 and idx + j < n:
                sel = D[idx + j]
                for m in "Changing to: %s" % sel + nl:
                    wrt(m)
                break
            idx += i
        # Back to top for next screenful
    
    wrt(0x03) # End string loop
    while(MQ.tx_fifo() != 0):   # Write out message
        pass
    while(MQ.rx_fifo() != 0):   # Flush input buffer to console
        print(MQ.get())            
    if sel:
        status, message = ChangeDir(sel)
    return


def FWD(pre, cmd):                                                                                     # Moves pointer to next block in TAP file; also can skip
                                                                                                       # 'CODE n,0' # of blocks or 'CODE n,1' files forward
    # SAVE "tpi:ffw"          - Move forward 1 block  (CODE 0,0)
    # SAVE "tpi:ffw" CODE 0,1 - Move forward 1 block
    # SAVE "tpi:ffw" CODE 0,n - Move forward n blocks
    # SAVE "tpi:ffw" CODE 1,n - Move forward n files
    # SAVE "tpi:ffw" CODE 1,0 - Move forward 1 files
    # SAVE "tpi:ffw" CODE 1,1 - Move forward 1 files
    # SAVE "tpi:ffw" CODE 2,n - Move forward n blocks and do "tpi:tapdir"CODE 0,0
    # SAVE "tpi:ffw" CODE 3,n - Move forward n files  and do "tpi:tapdir"CODE 1,0

    global TSP
    
    num_blks = len(TSP.offset_tbl) - 1
    
    par1, par2 = PARAMS(pre)
    st = _1_OK
    forth = par2
    if par1 > 1:
        doTapdir = True
        par1 = par1 - 2
    else:
        doTapdir = False

    if num_blks < 0:
        msg = "Empty or no file, can't FFW"
        LOG("INFO: " + msg, 2)
        forth = 0
        
    elif par1 == 0:

        # Move by block
        forth = max(par2,1)
        if TSP.tap_idx >= num_blks:
            
            msg = "Can't FWD. Already on last block"
            # st = _5_C_Nonsense
        else:
            TSP.tap_idx += forth
        if TSP.tap_idx > num_blks:
            TSP.tap_idx = num_blks

    elif par1 == 1:

        # Move by file
        h = max(par2, 1)
        i = TSP.tap_idx
        hdr = TSP.offset_tbl[i][2]
        if hdr[1] == 'Y':
            l = i
        else:
            l = -1
        i += 1

        while i < num_blks and h > 0:

            while (i < num_blks - 1) and (TSP.offset_tbl[i][2][1] == 'N'):
                i += 1
            if TSP.offset_tbl[i][2][1] == 'Y':
                h -= 1
                l = i # Last header index seen
                i += 1

        if l < 0:
            # Didn't see any headers
            i = num_blks - 1
        else:
            i = l
        TSP.tap_idx = i

    else:
        # Invalid option
        msg = BAD_CODE("FFW", par1, par2)
        LOG("ERROR: " + msg, 2)
        st = _8_A_Invalid_arg

    if st == _1_OK and forth != 0:
            
        TSP.offset = TSP.offset_tbl[TSP.tap_idx][0]
        gc.collect()
        msg = "Moved ahead to block # " + str(TSP.tap_idx)
        LOG(msg, 0)
        if doTapdir:
            # Chain to TAPDIR
            pre = [0] * 10
            if par1 == 1: # do TAPDIR by file as well
                pre[3] = 1 # CODE(1,0)
            TAPDIR(pre, cmd)
            return

    SEND_MSG(msg, "", st)
    
    return 


def getArgs(cmd):

    # Return the string of arguments to the command after the command word and a space.

    sp = cmd[7:].find(' ')
    if sp >= 0:
        return cmd[sp+8:]
    else:
        return ""


def GETHELP(pre, cmd):                                                 # Shows TS-Pico command help

    # SAVE "tpi:gethelp"            General help
    # SAVE "tpi:gethelp <command>"  Get help on a specific command
    # For help on a specific command, a file with that name in lowercase and a
    # .txt extension needs to be present in the /TS/help folder containing the 
    # text. It can be broken into short lines with CR/LF,  LF, or CR line endings.

    global TSP
    
    user_help_dir = "/sd/help"
    nl = chr(0x0D)
    arg = getArgs(cmd)
    arg = arg.lower()

    if arg != "":

        # Look for help file
        msg = nl
        ACTIVATE_SD()
        if dir_exists(user_help_dir):
            hname = user_help_dir + "/" + arg + ".txt"
            if file_exists(hname):
                with open(hname, 'rt') as help:
                    msg += help.read()
            else:
                msg += nl + 'Help for "' + arg + '" not found'
        else:
            msg += nl + "SD card help folder not found."

        DEACTIVATE_SD()
        ACTIVATE_MQ()

    else:
        #               01234567890123456789012345678901
        msg  = "%-32s" % ('LOAD: mount a file')
        msg += "%-32s" % ('================================')
        msg += "%-32s" % ('"tpi:<filename>" Mount by name')
        msg += "%-32s" % ('"tpi:nnn"        Mount by index')
        msg += "%-32s" % (' ')
        msg += "%-32s" % ('SAVE commands: [ ]-> optional')
        msg += "%-32s" % ('================================')
        msg += "%-32s" % ('"tpi:append"[CODE 1,0/1]')
        msg += "%-32s" % ('"tpi:append on/off"')
        msg += "%-32s" % ('"tpi:blkrcv"[CODE len,offset]')
        msg += "%-32s" % ('"tpi:cd <name>"[CODE 1/2,0]')
        msg += "%-32s" % ('"tpi:close"')
        msg += "%-32s" % ('"tpi:dir"[CODE 1/2/3,index]')
        msg += "%-32s" % ('"tpi:ffw"[CODE 0/1/2/3,n]')
        msg += "%-32s" % ('"tpi:gethelp [command]"')
        msg += "%-32s" % ('"tpi:getinfo"')
        msg += "%-32s" % ('"tpi:getlog [clear]"[CODE 0,n]')
        msg += "%-32s" % ('"tpi:loglevel"[CODE 1,n]')
        msg += "%-32s" % ('"tpi:loglevel n"')
        msg += "%-32s" % ('"tpi:md <folder>"[CODE 1,0]')
        msg += "%-32s" % ('"tpi:memboot"[CODE loc,slot]')
        msg += "%-32s" % ('"tpi:memdock"[CODE loc,slot]')
        msg += "%-32s" % ('"tpi:nop"')
        msg += "%-32s" % ('"tpi:path"[CODE 1,0]')
        msg += "%-32s" % ('"tpi:rew"[CODE 0/1/2/3,n]')
        msg += "%-32s" % ('"tpi:rm <name>"[CODE 255,0]')
        msg += "%-32s" % ('"tpi:rompatch"')
        msg += "%-32s" % ('"tpi:tap <name>[.tap]"')
        msg += "%-32s" % ('"tpi:tapdir"[CODE 0/1,n]')
        #                  01234567890123456789012345678901
        msg += "%-32s" % ('"tpi:tape"    <=>   "tpi:sdcard"')
        msg += "%-32s" % ('"tpi:ts2040"  <=>   "tpi:picopt"')
        msg += "%-32s" % ('"tpi:upgrade"')
        msg += "%-32s" % ('"tpi:verbose"[CODE 1,0/1]')
        msg += "%-32s" % ('"tpi:verbose on/off"')
        msg += "%-32s" % ('"tpi:zx48"[CODE 1/2,0/1]')

        # List specific help file names
        ACTIVATE_SD()
        if dir_exists(user_help_dir):
            listing = sorted(os.ilistdir(user_help_dir), key=lambda fname: fname[0].lower())
            msg += nl + nl + 'Commands for "tpi:gethelp cmd":' + nl + nl
            l = 0
            for name in listing:
                i = name[0].find('.')
                if i > 0:
                    hlp = name[0][:i]
                    if l + i + (l>0) > 32:
                        msg += nl + hlp
                        l = i
                    elif l == 0:
                        msg += hlp
                        l = i
                    else:
                        msg += " " + hlp
                        l += i + 1
        else:
            msg += nl + nl + "SD card help folder not found."

        DEACTIVATE_SD()
        ACTIVATE_MQ()

    SEND_MSG2(msg, 1)

    return


def GETINFO(pre, cmd):                                                 # Shows TS-Pico internal status

    global TSP
    global files
    global lista
    
    cop = chr(127)
    nl = chr(13)
    sd_stat = lista[32:63]
    
    fl_block = os.statvfs("")[0]
    fl_tot = os.statvfs("")[2]
    fl_free = os.statvfs("")[3]

    fl_free = (fl_free * fl_block) / 1_048_576
    fl_tot = (fl_tot * fl_block) / 1_048_576
    
    fl_stat = ">Flash: " + '%02.2f' % (fl_tot ) + "MB; free: " + '%02.2f' % (fl_free) + "MB"
    fl_stat = "%-32s" % (fl_stat)

    memfree = '%06.2f' % (gc.mem_free() / 1024)
    
    msg = " * TS-Pico interface status *" + nl
    msg += cop + " 2023, 2024 TS Pico Dev Team" + nl
    msg += "--------------------------------"
    msg += "%-32s" % (">FW Rev.:" + TSP.FW_VERSION + "; uPython: 1.20.0") + nl
    msg += ">Default ROM version: " + TSP.ROM_VERSION + nl
    msg += ">Board Rev.: V2.2; " + "Log level:%d" % TSP.LOG_LEVEL + nl
    msg += ">Pico Free RAM: " + memfree + " Kb." + nl
    msg += fl_stat
    msg += ">" + sd_stat
    mem, page = getBoot()
    msg += ">MemBoot: %d,%d" % (mem, page) 
    mem, page = getDock()
    msg += ";  MemDock: %d,%d" % (mem, page) + nl
    msg += ">Append: " + str(TSP.append)
    msg += "; Verbose: " + str(TSP.VERBOSE) + nl
    msg += ">Mounted file: " 
    
    if TSP.f_name:
        msg += public_fname() + nl
        i = TSP.tap_idx
        msg += ">Block:%02d" % i
        if TSP.offset_tbl:
            blk = TSP.offset_tbl[i]
            if blk[2] == " Y":
                msg += ":%s" % blk[3]
                msg += ":%s" % TSP.offset_tbl[i+1][3]
            else:
                msg += "Data block :%s" % blk[3]
        else:
            msg += ":<empty>"
        msg += nl
    else:
        msg += "none" + nl
    
    msg += ">Current path: " + public_path() + nl
    msg += ">Files in dir: " + str(len(files)) + nl

    SEND_MSG2(msg, 1)

    return


def GETLOG(pre, cmd):                                                 # Shows the last nn bytes of the events log file 

    # SAVE "tpi:getlog"
    # SAVE "tpi:getlog"CODE 0,n     - Show n bytes of the end of the file
    # SAVE "tpi:getlog"CODE 255,0   - Clear the log file
    # SAVE "tpi:getlog clear"       - Clear the log file

    global TSP
    global led
    
    status = _1_OK
    par1, par2 = PARAMS(pre)
    arg = getArgs(cmd)
    arg = arg.lower()

    if arg != '':
        if arg == 'clear':
            par1 = 255
            par2 = 0
        else:
            par1 = -1

    if par1 == 255 and par2 == 0:
        
        if CLEAR_LOG():
            msg = "Log file was cleared"
            SEND_MSG(msg, "", _1_OK)
            return
        else:
            msg = "ERROR clearing log file"
            status = _4_Q_Parameter

    elif par1 < 0:
        msg = BAD_ARG("GETLOG", arg)
        status = _8_A_Invalid_arg

    elif par1 != 0:
        msg = BAD_CODE("GETLOG", par1, par2)
        status = _8_A_Invalid_arg

    if status != _1_OK:
        LOG("ERROR: " + msg, 2)
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

    msg = bytearray(len_read)

    with open(log_fname, "r") as logfile:
        
        if file_seek:
            logfile.seek(file_seek)
            
        logfile.readinto(msg)

    SEND_MSG2(msg.decode('utf-8'), 1) # Convert bytes to string

    led.value(0)
    
    return


def LOAD_CONFIG():
        
    init_values = {}
    return_values = {}
    defaulted = False
    
    try:
        with open("config.ini", "r") as f:                      # We first try to load config values from config.ini file
            init_values = json.load(f)
    except:                                                     # If fails, we load default hard-wired values
        LOG("WARNING: Failed to load initial values from config.ini. Using default values instead", 1)

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
        LOG("ERROR: Incorrect initial ROM_SM value. Using default value of %d instead" % default_values["ROM_SM"], 2)

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
            LOG("ERROR: while updating config.ini!", 2)
            SAVE_LOG()
        
        if return_ROM_SLOT >= 0:
            init_values["ROM_SLOT"] = return_ROM_SLOT
            
    SAVE_LOG()
    
    return init_values            


def LOGLEVEL(pre, cmd):

    # Display or set the log level
    # SAVE "tpi:loglevel"           - Report log level (CODE 0,0)
    # SAVE "tpi:loglevel"CODE 1,n   - Set log level to n (n>=0)

    global TSP

    LABELS = ["INFO", "WARNINGS","ERRORS","CRITICAL"]

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
        if TSP.LOG_LEVEL <= 3:
            lbl = LABELS[TSP.LOG_LEVEL]
        else:
            lbl = ""
        msg = "LOG level is %d %s" % (TSP.LOG_LEVEL, lbl)
        viz = True
        
    elif par1 == 1:
        # Set level
        if par2 < 0:
            msg = BAD_ARG("LOGLEVEL", arg)
            status = _8_A_Invalid_arg
            LOG("ERROR: " + msg, 2)
        elif par2 > 3:
            msg = "Bad log level: %d" % par2
            status = _8_A_Invalid_arg
            LOG("ERROR: " + msg, 2)
        else:
            TSP.LOG_LEVEL = par2
            lbl = LABELS[TSP.LOG_LEVEL]
            msg = "LOG level set to %d %s" % (TSP.LOG_LEVEL, lbl)
            LOG("INFO: " + msg, 0)
    else:
        msg = BAD_CODE("LOGLEVEL", par1, par2)
        LOG("ERROR: " + msg, 2)
        status = _8_A_Invalid_arg

    SEND_MSG(msg, "", status, viz)

    return 


def MDIR(pre, cmd):                                                                                         # MAKE DIRectory in the current path                         
    
    # Make a new directory
    # SAVE "tpi:md <name>"              - Create a directory
    # SAVE "tpi:md <name>" CODE 1,0     - Also change to the new directory

    global TSP
    
    name = cmd[10:]
    message = "Created dir: "  + name
    status = _1_OK
    
    ACTIVATE_SD()
    os.chdir(TSP.cur_path)

    try:
        os.mkdir(name)
        DIR_FILES()

    except OSError:

        message = "OS error creating: "  + name
        LOG("MD: " + message, 2)
        status = _4_Q_Parameter

    DEACTIVATE_SD()
    ACTIVATE_MQ()
    
    par1, par2 = PARAMS(pre)

    if status == _1_OK and par1 == 1 and par2 == 0:
        # Change to new DIR with show path option
        pre = [0] * 10
        PATH(pre, cmd)
    else:
        SEND_MSG(message, "", status)
            
    return 
                

def MEMBOOT(pre, cmd):                                           # Changes ROM slot to boot from; either SRAM or Flash
    
    global TSP
    
    global BANK
    global ROM
    
    par1, par2 = PARAMS(pre)
    
    if par1 == 0 and par2 == 0:
        # Report setting
        mem, page = getBoot()
        SEND_MSG("BOOT is MEM=%d, PAGE=%d" % (mem, page), "", _1_OK, True)

    elif (par1 == 0 or par1 > 3 or par2 > 15):
        SEND_MSG('Wrong values, MEM=' + str(par1) + ', PAGE=' + str(par2), "OK values: MEM=1..3, PAGE=0..15", _8_A_Invalid_arg)
        LOG("WARNING: Wrong values in MEMBOOT, MEM=" + str(par1) + ", PAGE=" + str(par2) + ". Command ignored", 1) 
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
            
        SEND_MSG('Change ROM to MEM=' + str(par1) + ', PAGE=' + str(par2), "", _1_OK)
#         LOG("INFO: Change ROM to MEM=" + str(par1) + ", PAGE=" + str(par2) + " in MEMBOOT", 0)
        
        utime.sleep(.100)
        
        ROM.put(TSP.ROM_SM)
        BANK.put(TSP.bank_sm)
        
#         while(MQ.tx_fifo() != 0):
#             pass

    return 


def getBoot():

    global TSP

    val1 = TSP.ROM_SM & 12
    mem = TSP.ROM_SM - val1
    val1 = TSP.bank_sm & 240
    page = TSP.bank_sm - val1
    return mem, page


def getDock():

    global TSP

    val1 = TSP.ROM_SM & 3
    mem = int((TSP.ROM_SM - val1) / 4)
    val1 = TSP.bank_sm & 15
    page = int((TSP.bank_sm - val1) / 16)
    return mem, page


def MEMDOCK(pre, cmd):                                                   # Changes DCK slot; either SRAM or Flash

    # tpi:memdock
    # SAVE "tpi:memdock" CODE 0,0   - Display setting
    # SAVE "tpi:memdock" CODE 1,m   - Assign SRAM page m to dock
    # SAVE "tpi:memdock" CODE 2,m   - Assign flash page m to dock

    global TSP
    global BANK
    global ROM
    
    par1, par2 = PARAMS(pre)
    
    if par1 == 0 and par2 == 0:
        # Report setting
        mem, page = getDock()
        SEND_MSG("DOCK is MEM=%d, PAGE=%d" % (mem, page), "", _1_OK, True)

    elif (par1 == 0 or par1 > 2 or par2 > 15):
        info = "MEM=%d, PAGE=%d" % (par1, par2)
        SEND_MSG('Wrong values, ' + info, "OK values: MEM=1..2, PAGE=0..15", _8_A_Invalid_arg)
        LOG("WARNING: Wrong values in MEMDOCK, " + info + ". Command ignored", 1) 
    else:            
        val1 = TSP.ROM_SM & 3
        TSP.ROM_SM = val1 + (par1 * 4)
        val1 = TSP.bank_sm & 15
        TSP.bank_sm = val1 + (par2 * 16)
        
        info = "MEM=%d, PAGE=%d" % (par1, par2)
        SEND_MSG('Change DCK to ' + info, "", _1_OK)
        LOG("INFO: Change DCK to " + info + " in MEMDOCK", 0)
        
        ROM.put(TSP.ROM_SM)
        BANK.put(TSP.bank_sm)
        
    return 


def REMOVE_DIR(d):                                                        # Recursively remove a directory and all its contents
    
    try:
        if os.stat(d)[0] & 0x4000:  # Dir
            for f in os.ilistdir(d):
                if f[0] not in ('.', '..'):
                    REMOVE_DIR("/".join((d, f[0])))  # File or Dir
            os.rmdir(d)
        else:  # File
            os.remove(d)
        
    except:
        LOG("WARNING: could not remove directory " + d, 1)
        
    return


def REW(pre, cmd):                                                                                           # Moves pointer to previous block in TAP file; also 
                                                                                                             # can skip 'CODE n' # of blocks backwards
    # SAVE "tpi:rew"         - Rewind 1 block (CODE 0,0)
    # SAVE "tpi:rew"CODE 0,n - Rewind by n blocks
    # SAVE "tpi:rew"CODE 1,n - Rewind by n files
    # SAVE "tpi:rew"CODE 2,n - Rewind n blocks and do "tpi:tapdir"CODE 0,0
    # SAVE "tpi:rew"CODE 3,n - Rewind n files  and do "tpi:tapdir"CODE 1,0

    global TSP
    
    par1, par2 = PARAMS(pre)
    st = _1_OK
    if par1 > 1:
        doTapdir = True
        par1 = par1 - 2
    else:
        doTapdir = False

    if len(TSP.offset_tbl) == 0:

        msg = "Empty or no file, can't REW"
        LOG("INFO: " + msg, 0)
        back = 0

    elif par1 == 0 or len(TSP.offset_tbl) == 0:

        # Move by block
        back = max(par2,1)
        if TSP.tap_idx <= 0:
            msg = "Can't REW. Already on first block"
            # st = _5_C_Nonsense
        else:
            TSP.tap_idx -= back
        if TSP.tap_idx <= 0:
            TSP.tap_idx = 0

    elif par1 == 1:

        # Move by file
        h = max(par2, 1)
        i = TSP.tap_idx
        hdr = TSP.offset_tbl[i][2]
        if hdr[1] == 'Y':
            l = i
        else:
            l = -1
        i -= 1

        while i >= 0 and h > 0:

            while (i >= 0) and (TSP.offset_tbl[i][2][1] == 'N'):
                i -= 1
            if TSP.offset_tbl[i][2][1] == 'Y':
                h -= 1
                l = i # Last header index seen
                i -= 1

        if l < 0:
            # Didn't see any headers
            i = 0
        else:
            i = l
        TSP.tap_idx = i

    else:
        # Invalid
        if doTapdir:
            par1 += 2
        msg = BAD_CODE("REW", par1, par2)
        LOG("WARNING: " + msg, 1)
        st = _8_A_Invalid_arg

    if st == _1_OK and back != 0:
            
        TSP.offset = TSP.offset_tbl[TSP.tap_idx][0]
        gc.collect()
        msg = "Moved back to block # " + str(TSP.tap_idx) 
        LOG(msg, 0)
        if doTapdir:
            # Chain to TAPDIR
            pre = [0] * 10
            if par1 == 1: # do TAPDIR by file as well
                pre[3] = 1 # CODE(1,0)
            TAPDIR(pre, cmd)
            return
    
    SEND_MSG(msg, "", st)

    return

    
def ROMPATCH(pre, cmd):                                                                                      # Patch for system ROM
    
    global TSP
    global led
    
    led.value(1)

    MOUNT_FILE("/assets/rompatch.tap")                                       # handles SD/MQ transition internally

    SEND_MSG("System prepared to patch ROM.", 'Use LOAD "" to start.', _1_OK)

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


def SEND_MSG_PROMPT_YN(prompt, echoY = True):

    # Prints prompt string, waits for a character and returns that char
    # Assumes MQ is active. This cannot be followed by another SEND_MSG* call.

    global MQ

    wrt = MQ.put
    # Dual-port: continue flag now on port $0F via MQ_READY
    wrt(0x86)   # PRINT STRING WITH LOOP
    wrt(0x01)   # BASIC return code
    wrt(0x0D)   # Start a new line
    MQ_READY()  # Z80 sees "ready" on port $0F
    while (MQ.rx_fifo() > 0):   # Flush receive buffer
        MQ.get()
    for ch in prompt:
        wrt(ch)
    wrt(0x00)   # End string and wait for char
    wrt(0x40)   # Read continue flag
    ch = MQ.get()
    if ch != 78: # 'N' causes the ROM to end the string loop and any exchange
        if ch < 33 or echoY:
            wrt(89) # 89='Y' Echo Y for space or control char
        else:
            wrt(ch)
        wrt(0x03) # End the string loop
        while(MQ.tx_fifo() != 0):
            pass
        while(MQ.rx_fifo() != 0):
            print(MQ.get())

    return ch

def BAD_CODE(command, par1, par2):

    return command + ": CODE %s,%s" % (par1,par2) + " not supported"


def BAD_ARG(command, arg):

    return command + ": Bad argument: %s" % arg

def RM(pre, cmd):                                                        # Output for not implemented SAVE Command 
    
    # Remove a named file or directory (combine RM and RMDIR, act based on type)
    # Assumes file/dir to remove is in TSP.cur_path
    # SAVE "tpi:rm <name>"            - Remove file or empty folder
    # SAVE "tpi:rm <name>" CODE 255,0 - Bypass confirmation prompt

    global TSP
    global isdir
    
    name = cmd[10:]
    status = _1_OK
    log = 0
    message = ""
    sent = False
    par1, par2 = PARAMS(pre)

    name, idx = ResolveIndexName(name)

    if name.upper() not in isdir:

        message = "RM file not found " + name
        status = _3_F_Invalid_file
        log = 2

    else:

        adir = isdir[name.upper()]

        if par1 == 0 and par2 == 0:

            sent = True
            ch = SEND_MSG_PROMPT_YN('Remove "%s" (y/N)?' % name)
            if ch != 89: # 89='Y'
                LOG("INFO: %s not removed from %s" % (name, TSP.cur_path), 0)
                return

        elif par1 != 255 or par2 != 0:
            message = BAD_CODE("RM", par1, par2)
            LOG("ERROR: " + message, 2)
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
            else:
                os.remove(name)
            DIR_FILES()
            message = "Removed " + kind +": "  + name

        except OSError:

            message = "ERROR: OS error removing: " + name
            status = _4_Q_Parameter
            log = 2

        DEACTIVATE_SD()
        ACTIVATE_MQ()
    
    LOG(message, log)
    if not sent:
        SEND_MSG(message, "", status)
    
    return 
                

def SYS_CMD(pre, cmd):                                                                                      # Various system cmds
    
    global led
    
    par1, par2 = PARAMS(pre)
    
    if (par1 == 1 and par2 == 0):                                                                           # CODE 1,0 -> Retrieve ROM patch from firmware
        SEND_MSG("SYS CMD finished OK", "", _1_OK)
        LOG("INFO: Received SYS CMD 1,0 - Patch update", 0)
        
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
        LOG("ERROR: Wrong syntax SYS CMD", 2)
        SAVE_LOG()
        
        while True:
            BLINK_ERROR()
    
    
    led.value(0)
    UNMOUNT()
    
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
    
    global TSP
    global log_to_serial
    global buf                                                                             # global buffer to be used by COPY_FILE
    
    SEND_MSG("Upgrade started.DON'T INTERRUPT", "after the first 10 blinks!", _1_OK, True)
    
    last_run = {}                                                           # dictionary to hold last upgrade run's status
    new_values = {}                                                         # dictionary of upgraded config.ini values
    upgrade_dict = {}                                                       # dictionary of files to be upgraded
    restored = False
    
    led = Pin(25, Pin.OUT)
    U6_EN = Pin(12, Pin.OUT, Pin.PULL_UP)
    
    U6_EN.value(1)                                                          # We disable U6_ENABLE, just in case.....
    
    buf = bytearray(32768)
    
    for i in range(20):                                                     # We give the user 10s and 20 LED blinks to abort installation
        time.sleep(.5)
        led.toggle()

    led.value(1)
    
    log_to_serial = True
    LOG("**********************************************", 4)
    LOG("TS Pico Upgrade setup (c) 2024 TS-Pico DevTeam", 4)
    LOG("IMPORTANT!!!! DO *NOT* INTERRUPT THIS SEQUENCE!!!!", 4)
    LOG("**********************************************", 4)
    SAVE_LOG()
    
    time.sleep(1)

    LOG("Mounting SD Card", 4)
    SAVE_LOG()

    try:
        ACTIVATE_SD()
    except:
        FINISH("Fatal error. Could not mount SD Card. Terminating", False)

    led.value(0)

    LOG("TS-Pico Upgrade Setup initialized ok", 4)
    LOG("SD Card mounted ok", 4)
    SAVE_LOG()
    
    try:
        with open("/upgrade.ini", "r") as f:                             # Try to determine last run's status
            last_run = json.load(f)
            last_run_status = last_run["status"]
    except:
        last_run_status = "None"

    LOG("Previous run status: " + last_run_status, 4)
    SAVE_LOG()
    
    try:
        os.chdir("/sd/UPGRADE")
    except:
        FINISH("Fatal error. Could not find UPGRADE folder on the SD Card. Terminating", False)

    LOG("UPGRADE folder found in SD Card", 4)
    SAVE_LOG()

    if last_run_status == "BACKUP_PERFORMED":                                # If last run was unsuccessfull, but the backup creation wasn't, we restore that backup 
                                                                             # in case something went wrong last time
        LOG("Previous run was unsuccessful. Attempting to roll back...", 4)
        SAVE_LOG()
        
        try:
            RESTORE_FILES("/sd/UPGRADE/BACKUP", "/")                                      # if so, restore backup
            LOG("System rolled back successfully. Continue with upgrade process", 4)
            SAVE_LOG()
            
            restored = True
            
        except Exception as err:
            LOG("System roll back failed. Reason: ", 4)
            
            with open("/activity.log", "a") as log:
                sys.print_exception(err, log)
            
            FINISH("Fatal error. Could not rollback system. ", False)

    try:
        with open("/config.ini", "r") as f:                                  # try to load config values from config.ini file
            init_values = json.load(f)
    except:
        pass
            
    try:
        with open("/sd/UPGRADE/config.ini", "r") as f:                      # load values from config.ini file on the /sd/UPGRADE folder
            new_values = json.load(f)
    except:
        FINISH("Fatal error. Could not find config.ini file in UPGRADE folder. Terminating", False)

    LOG("Current firmware version: " + TSP.FW_VERSION, 4)
    
    LOG("New firmware version: " + new_values["FW_VERSION"], 4)

    if (TSP.FW_VERSION == new_values["FW_VERSION"]):
       FINISH("Current version is the same as upgrade. Nothing to do. Terminating", True)
       
    SAVE_LOG()
    os.chdir("/sd/UPGRADE")
    
    if restored:
        LOG("Bypass system backup due to recent succesful RESTORE", 4)
        SAVE_LOG
        
    else:
        
        if "BACKUP" in os.listdir():
            
            LOG("Removing old BACKUP folder from previous run", 4)
            
            try:
                REMOVE_DIR("/sd/UPGRADE/BACKUP")
                LOG("Previous BACKUP folder removed", 4)
                SAVE_LOG()
            except:
                FINISH("Error removing previous backup folder. Terminating", False)
                
        dest_dir = "/sd/UPGRADE/BACKUP"
        
        LOG("Starting current firmware backup", 4)
        SAVE_LOG()
                 
        led.toggle()
        time.sleep(.1)                                                      # Short LED blink = stage 1 completed ok (initialization)
        led.toggle()
        
        BACKUP_DIR("/", dest_dir)
        os.chdir("/")

        with open("/upgrade.ini", "w") as f:
            last_run["status"] = "BACKUP_PERFORMED"
            json.dump(last_run, f)

    LOG("Firmware backup finished ok", 4)
    LOG("Processing new files", 4)

    time.sleep(1)

    led.value(0)
    time.sleep(.1)
    led.toggle()
    time.sleep(.1)                                                      # Two short LED blinks = stage 2 completed ok (backup)
    led.toggle()
    time.sleep(.1)
    led.toggle()
    led.value(1)


    os.chdir("/sd/UPGRADE")
    
    with open("/sd/UPGRADE/upgrade.json", "r") as f:                                  # try to load config values from config.ini file
        upgrade_dict = json.load(f)
    
    for el in upgrade_dict["dirs"]:
        
        try:
            REMOVE_DIR(el)
        except:
            LOG("Warning: could not remove folder " + el + "; continue process...", 4)
            SAVE_LOG()
            pass
        
        try:
            os.mkdir(el)
            
        except:                
            FINISH("Fatal error: unable to create folder " + el + " during Update. Terminating.", False)
            
    for el in upgrade_dict:
        
        if el == "dirs":
            continue
        
        if el == "main.py":
            os.rename("/main.py", "/main.old")
            LOG("'main.py' renamed to 'main.old'", 4)
            SAVE_LOG()
        try:
            COPY_FILE(el, upgrade_dict[el]+el)
        except:
            FINISH("Fatal error: unable to copy file " + el + " during Update. Terminating", log_ena, False)

    os.remove("/main.old")
    LOG("'main.old' removed ok", 4)

    with open("/upgrade.ini", "w") as f:
        last_run["status"] = "UPGRADE_PERFORMED"
        json.dump(last_run, f)

    try:
        new_folder = "/sd/BACKUP_FIRMWARE_V" + new_values["FW_VERSION"]
        os.rename("/sd/BACKUP", new_folder)
    except:
        LOG("Error attempting to rename BACKUP folder; trying another name", 4)
        SAVE_LOG()
        
        try:
            num = str(len(os.listdir("/sd")) - 5)                                              # At this point, there are 6 elements on the '/' folder. So, subsequent BACKUP files 
            new_folder = "/sd/BACKUP_FIRMWARE_V" + new_values["FW_VERSION"] + "[" + num + "]"                # will be named BACKUP_FIRMWARE_V1.1c[1], ....FIRMWARE_V1.1c[2], etc

            os.rename("/sd/BACKUP", new_folder)
            
        except:
            LOG("WARNING: Error renaming folder " + new_folder, 4)
            SAVE_LOG()
            
    LOG("Finished renaming BACKUP folder", 4)
    SAVE_LOG()

    FINISH("All process finished successfully. Check the activity.log file for more info", True)
    
    return 


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

    if arg != '':
        par1 = 1
        if arg == 'on':
            par2 = 1
        elif arg == 'off':
            par2 = 0
        else:
            msg = "VERBOSE: Bad argument: %s" % arg
            LOG("ERROR: " + msg, 2)
            par2 = -1
    
    if par1 == 0:
        # Display
        if TSP.VERBOSE:
            msg = "Verbose is enabled"
        else:    
            msg = "Verbose is disabled"
        SEND_MSG(msg, "", _1_OK, True)
    elif par1 == 1:
        # Set
        if par2 < 0:
            SEND_MSG(msg, "", _8_A_Invalid_arg)
        else:
            TSP.VERBOSE = (par2 != 0)
            if TSP.VERBOSE:
                msg = "Verbose is now enabled"
            else:    
                msg = "Verbose is now disabled"
            LOG("INFO: " + msg, 0)
            SEND_MSG(msg, "", _1_OK)
    else:
        msg = BAD_CODE("VERBOSE", par1, par2)
        LOG("ERROR: " + msg, 2)
        SEND_MSG(msg, "", _8_A_Invalid_arg)
        
    return 


def ZX48(pre, cmd):                                                           # Changes to ZX Spectrum 48 compat mode 
    
    # Put Pico in ZX Spectrum communication mode
    # SAVE "tpi:zx48"           - put in ZX48 mode (with current tape compat mode)
    # SAVE "tpi:zx48"CODE 1,0   - Set normal tape load routine 
    # SAVE "tpi:zx48"CODE 1,1   - Set compatible tape load routine 
    # SAVE "tpi:zx48"CODE 1,bufsize - compatible load with buffer size spec. 
    #                               Size >= 16384
    # SAVE "tpi:zx48"CODE 2,x   - Don't display help

    global TSP
    
    par1, par2 = PARAMS(pre)

    if par1 > 2:
        msg = BAD_CODE("ZX48", par1, par2)
        LOG("ERROR: " + msg, 2)
        SEND_MSG(msg, "", _8_A_Invalid_arg)
        return

    TSP.zx48 = True

    msg  = chr(13) + 'Changing TS-Pico to ZX48 mode.  '

    if par1 > 0:
        TSP.ZX_TAPE_COMPAT = par2 > 0
          
    if TSP.ZX_TAPE_COMPAT == True:
        msg += '(Compatible tape load mode)     '
        msg += '(Buffer size = %d)' % par2
    else:
        msg += '(Normal tape load mode)         '
    msg += 'Use "OUT 244,3" to switch to the'
    msg += 'Spectrum ROM. To return to Timex'
    msg += 'mode, use OUT 10,100 followed by'
    msg += 'OUT 244,0 and then press the TS ' 
    msg += 'Reset button on the TS-Pico.'

    SEND_MSG(msg, "", _1_OK, par1 != 2)
            
    return 


def NOP(pre, cmd):                                                           # Test for Ryan's Timex Commander Program

    global MQ

    # Dual-port: continue flag now on port $0F via MQ_READY
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

        # Dual-port: continue flag now on port $0F via MQ_READY
        wrt(0x01)
        MQ_READY()

        pre = [0] * 10
        for i in r1:
            pre[i] = MQ.get()
        if pre[1] != 5:
            break
        # NOTE: do not MQ_BUSY here — Pico stays ready for next iteration

    wrt(0x01)
    MQ_READY()

    SEND_MSG(end_msg, "", _1_OK)
    
    while (MQ.tx_fifo() != 0):
        pass
  
    while (MQ.rx_fifo() != 0):
        fff = MQ.get()
        
    prn = prn[:pos]

    with open("/PRN/0001.txt", "w") as sal:                                           # PRINT output filename is fixed on this version; can be set up
            sal.write(prn)                                                            # in future version

    return


def PROCESS_ASM(pre):                                                                 # Processes AU (Assembler) commands sent by the TS

    global MQ

    cmd = pre[:5].decode()
    wrt = MQ.put

    # Dual-port: initial "ready" before any data follows
    MQ_READY()

    print(pre)
    print(cmd)

    par3 = int(pre[8])
    par4 = int(pre[9])

    print(par3, par4)

    # Dual-port: load ack into FIFO then signal ready again
    wrt(0x01)
    MQ_READY()

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

    # CRITICAL TIGHT RECEIVE — drain cmd block. Do NOT put $01 in the FIFO
    # here! The byte-24 response in the protocol is provided by SEND_MSG /
    # SEND_MSG2 (called by EXEC below). For commands that need a directive
    # (0x86 = PRINT_STRING_LOOP for DIR, 0x81 = PRINT_STRING for verbose),
    # putting a $01 here makes Z80 see "OK done" and never enter the loop.
    # MQ_READY is also deferred — SEND_MSG/SEND_MSG2 sets it after loading
    # the response into the FIFO. Z80 polls $0F (~2.8ms budget) until then.
    for l in rl:
        cmd[l] = MQ.get()

    # Stay BUSY until SEND_MSG fills the FIFO and signals ready.
    MQ_BUSY()

    # Now safe to TLM
    TLM("PROCESS_CMD enter", "load_cmd=%d cmd_len=%d cmd=%r" % (
        load_cmd, long, bytes(cmd[:long])))

    try:
        cmd = cmd[:long].decode()
    except:
        LOG("ERROR: Unrecognized string in PROCESS_CMD: FIFO Status:" + str(MQ.tx_fifo()) + " " + str(MQ.rx_fifo()), 2)
        TLM("PROCESS_CMD decode FAILED — returning early")
        return

    cmd_exec = cmd[3:].upper() # Command starting with "TPI:" in uppercase
    rest_cmd = cmd[7:] # Command after "tpi:"

    TLM("PROCESS_CMD parsed", "cmd_exec=%r rest_cmd=%r" % (cmd_exec, rest_cmd))

    gc.collect()

    if load_cmd:                                                                                    # Is it a "LOAD:tpi:..." command.....?

        # MQ_BUSY ensures Z80 sees "not ready" during the SD work that follows.
        # MOUNT_FILE handles SD/MQ transitions internally (DEACTIVATE_SD +
        # ACTIVATE_MQ(ready=False)). SEND_MSG calls MQ_READY() at the end after
        # the response is loaded into the FIFO.
        MQ_BUSY()

        if rest_cmd == "dirinfo.tap":
            if MOUNT_FILE(TSP.cur_path + "/dirinfo.tap"):
                msg = "Mounting dir info: "
                status = _1_OK
            else:
                msg = "Error mounting file: "
                status = _2_R_Tape_load
            SEND_MSG(msg, rest_cmd, status)

        else:
            rest_cmd, idx = ResolveIndexName(rest_cmd)
            if idx < 0:
                if rest_cmd.upper() in files_upper:                                                                                  # Is rest_cmd a valid file?
                    idx = files_upper.index(rest_cmd.upper())

            if idx >= 0:
                if MOUNT_FILE(TSP.cur_path + "/" + files[idx]):
                    msg = "File mounted OK"
                    status = _1_OK
                else:
                    msg = "Error mounting file:"
                    status = _4_Q_Parameter
                SEND_MSG(msg, rest_cmd, status)

            else:
                msg = "ERROR: File does not exist: "
                SEND_MSG(msg, rest_cmd, _3_F_Invalid_file)                                       # If none of the above, raise error
                LOG(msg + rest_cmd, 2)
            
    else:                                                                                                 # ...or it's a "SAVE:tpi:..." command
        # Split command word from any arguments
        sp = cmd_exec.find(' ')
        if sp >= 0:
            cmd_word = cmd_exec[:sp]
            cmd_args = cmd[sp+4:]
        else:
            cmd_word = cmd_exec
            cmd_args = ""

        TLM("PROCESS_CMD SAVE branch", "cmd_word=%r in_SA_funct=%s in_EXT=%s" % (
            cmd_word, cmd_word in SA_funct, cmd_word in EXT_SA_FUNCT))

        if cmd_word in SA_funct:
            EXEC = SA_funct[cmd_word]
            TLM("PROCESS_CMD dispatching SA_funct", "cmd_word=%r" % cmd_word)
            EXEC(pre, cmd)
            TLM("PROCESS_CMD SA_funct returned", "cmd_word=%r" % cmd_word)

        elif cmd_exec == "TPI:TEST":                                                                               # Remove in production!!!

            # Dual-port: ack into FIFO, signal ready on port $0F
            MQ.put(0x01)
            MQ_READY()

            chunk = bytearray(8192)
            
            with open("dck_dump.bin", "wb") as f_out:
                for ch in range(8):
                    for i in range(8192):
                        MQ.get(chunk[i])
                        
                    f_out.write(chunk)
                    
                    del chunk
                    chunk = bytearray(8192)

                    gc.collect()
            
#             while True:
#                 print(MQ.get())

        elif cmd_word in EXT_SA_FUNCT:                                                                                # Is an external cmd?
            EXEC = EXT_SA_FUNCT[cmd_word]
            EXEC(pre, cmd)
            
        else:
            SEND_MSG("Unrecognized command: " + cmd_exec,'SAVE "tpi:gethelp" for info', _5_C_Nonsense)    # If none of the above, raise error
            LOG("ERROR: Unrecognized command: " + cmd_exec, 2)
    
    TLM("PROCESS_CMD draining tx_fifo at exit")
    drain_tx = 0
    while(MQ.tx_fifo() != 0):
        drain_tx += 1
        if drain_tx > 1000000:
            TLM("PROCESS_CMD STUCK draining tx", "tx=%d" % MQ.tx_fifo())
            break

    drain_rx = 0
    while MQ.rx_fifo() != 0:
        fff = MQ.get()
        drain_rx += 1

    TLM("PROCESS_CMD exit", "drain_tx=%d drain_rx=%d cmd=%r" % (drain_tx, drain_rx, cmd_exec))

    # NOTE: stay ready. The Pico IS ready for the next command. Setting
    # busy here would cause Z80 to time out (Report J) when it polls
    # port $0F immediately after this command's last response byte.

    LOG("INFO: Exiting CMD processing: " + cmd_exec + " " + str(MQ.tx_fifo()) + " " + str(MQ.rx_fifo()), 0)

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
    
    busy = False
    dead = True
    kill = False
    
    files = []
    lista = ""
    log_entries = ""
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
        LOG("INFO: Starting new log file", 3)
    
    LOG("INFO: Starting TS Pico. Memory at startup: " + str(gc.mem_free()), 0)
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
    
    REMOVE_DIR("/TMP")
    os.mkdir("/TMP")
    
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
        "TPI:GETHELP" : GETHELP,
        "TPI:GETINFO" : GETINFO,
        "TPI:GETLOG" : GETLOG, 
        "TPI:LOGLEVEL" : LOGLEVEL,
        "TPI:MD" : MDIR,
        "TPI:MEMBOOT" : MEMBOOT,
        "TPI:MEMDOCK" : MEMDOCK,
        "TPI:NOP" : NOP,                                                                      # This is to test Ryan's new Commander
        "TPI:PATH" : PATH,
        "TPI:REW" : REW,
        "TPI:ROMPATCH" : ROMPATCH,
        "TPI:RM" : RM, # dir or file
        "TPI:SYS" : SYS_CMD,
        "TPI:TAP" : NEW_TAP,
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
    
    # Placeholder for External SAVE commands
    
    EXT_SA_FUNCT = {
    
    }

    dead = False
    _thread.start_new_thread(BLINK_LED, (0.9, ))
    
    ACTIVATE_SD()
    
    dead = True
    
    while busy:
        pass
    
    try:
        os.chdir(TSP.cur_path)
        DIR_FILES()
    
    except:
        LOG("CRITICAL ERROR! Cannot mount /TAP directory; aborting.", 3)
        SAVE_LOG()
        
        while True:
            BLINK_ERROR()
            
    # Boot sequence: SD was active, switch to PIO.
    DEACTIVATE_SD()
    ACTIVATE_MQ()
    MQ_READY()                                                                                   # Default to ready so Z80 isn't blocked. Pico is alive!

    LOG("INFO: SD Card initialized and mounted OK", 0)
    SAVE_LOG()
    
    wrt = MQ.put
    
    LOG("INFO: TS Pico initialized OK. Waiting for commands...", 0)
    SAVE_LOG()
    
    led.value(0)

    pre = bytearray(10)
    r1 = range(10)

    ts = time.ticks_us()                                                                           # ts -> timestamp
    
    while True:                                                                                    # main execution loop

        if (MQ.rx_fifo()) != 0:

            ts = time.ticks_us()                                                                   # reset timestamp

            # CRITICAL TIGHT RECEIVE PATH — NO PYTHON OVERHEAD ALLOWED
            #
            # The PIO's RX FIFO is only 4 entries deep. The Z80 sends bytes
            # in bursts that finish in ~50us. Any Python work (print/TLM) in
            # this region takes ms-scale time, during which the FIFO fills
            # and bytes are dropped by PIO push(noblock).
            #
            # Also: between MQ_READY and PROCESS_CMD's drain loop, the Z80's
            # WF_NPH polls $0F for only ~4.3ms before timeout. TLM prints
            # eat that budget too.
            #
            # Sequence: drain pre-header, queue ACK, signal ready, then call
            # PROCESS_CMD which IMMEDIATELY does its own drain. NO TLM in
            # this path. PROCESS_CMD will TLM after its drain completes.
            for i in r1:
                pre[i] = MQ.get()
            wrt(0x01)
            MQ_READY()
            # (deferred) snapshot pre[] for later TLM
            _pre_snapshot = list(pre)
            # NOTE: do NOT MQ_BUSY here! The Z80 polls port $0F AFTER
            # reading the $01 status byte, AFTER it has finished sending
            # the pre-header. If we go busy here, Z80 sees "not ready"
            # and times out → Report J. Stay ready until we hit a real
            # slow operation (LOAD branch handles its own MQ_BUSY).
                                                                                                      # pre(header)[0] is a command
            if pre[0] == 0 and pre[1] == 0:                                                           # pre[1] specifies which: if 0 -> SAVE   
                LOG("INFO: Starting SAVE TS", 0)
                
                led.value(1)
                
                while busy:
                    pass
                
                # Save some state for possible retoration
                pf_name = TSP.f_name
                pappend = TSP.append
                pidx = TSP.tap_idx
                # SAVE_TS changes TSP.f_name to the new file name if append is False 

                MQ, TSP, new_logs = SAVE_TS(MQ, TSP)
                log_entries += new_logs
                gc.collect()

                if pappend:
                    # Re-mount the updated tap from SD so the user sees the
                    # addition. MOUNT_FILE handles SD/MQ transition internally.
                    try:
                        MOUNT_FILE(TSP.f_name)
                        # Restore the previous index that got reset on mount
                        TSP.append = True
                        TSP.tap_idx = pidx
                        TSP.offset = TSP.offset_tbl[TSP.tap_idx][0]
                        LOG("INFO: Re-mounted appended file: %s" % TSP.f_name, 0)
                    except:
                        LOG("ERROR: Re-mount appended file failed", 2)

                elif not pf_name:

                    if TSP.f_name:
                        # Mount new saved file if no file was already mounted, but
                        # we don't set append on.
                        try:
                            MOUNT_FILE(TSP.f_name)
                            LOG("INFO: Mounted new file: %s" % TSP.f_name, 0)
                        except:
                            LOG("ERROR: Re-mount failed for: " + TSP.f_name, 2)
                    else:
                        LOG("ERROR: Append is off. Saved to new file but TSP.f_name not set to mount it.", 0)

                elif TSP.f_name == pf_name:
                    # This overwrote tap file that was mounted. The original
                    # copy is still mounted, and the new tap on SD will only 
                    # contain the one new saved file. You could turn on append,
                    # and this will get re-mounted with the original content lost.
                    LOG("INFO: Append is off. Overwrote mounted tap on SD but no re-mount.", 0)

                else:
                    LOG("INFO: Append is off. Saved to new file: %s" % TSP.f_name, 0)
                    # Put mounted name back as we continue with the current mount
                    TSP.f_name = pf_name

                # This expects MQ inactive and SD mounted and it worked fine before
                try:
                    os.chdir(TSP.cur_path) # MOUNT_FILE doesn't set this
                    DIR_FILES()
                except:
                    LOG("ERROR: DIR_FILES failed after SAVE", 2)
                
                try:
                    DEACTIVATE_SD()
                    ACTIVATE_MQ()

                except:
                    pass
                
                led.value(0)
                
            elif (pre[0] == 0 or pre[0] == 255) and pre[1] < 10:                                      # for simplicity if 0 < pre[1] < 10: call LOAD routine 
                LOG("INFO: Starting TS LVM", 0)
                
                while busy:
                    pass
                MQ, TSP, new_logs = LOAD_TS(pre, MQ, TSP)
                log_entries += new_logs
                
            elif (pre[0] == 0 or pre[0] == 255):                                                      # Headerless LOAD
                LOG("INFO: Starting TS LVM - Headerless LOAD", 0)
                
                while busy:
                    pass
                MQ, TSP, new_logs = LOAD_TS(pre, MQ, TSP)
                log_entries += new_logs
                
            elif pre[0] == 66 and pre[1] == 5:                                                        # commands are pre[0] == 66. PRINT commands are pre[1] == 5
                LOG("INFO: Starting PRINT", 0)
                PRINT_IO(pre)
                DIR_FILES()
                
            elif pre[0] == 66:

                # NO TLM HERE — PROCESS_CMD must reach its for loop within
                # ~4.3ms of the MQ_READY above (Z80 WF_NPH timeout). A print
                # statement takes 5-10ms and would cause byte drops.
                try:
                    PROCESS_CMD(pre, SA_funct, EXT_SA_FUNCT)
                    TLM("main loop: PROCESS_CMD returned", "pre=%s" % _pre_snapshot)
                except Exception as _e:
                    LOG("ERROR: Invalid data received from PROCESS_CMD: " + str(pre), 2)
                    TLM("main loop: PROCESS_CMD raised exception", str(_e))
                    import sys
                    sys.print_exception(_e)
                    continue

                if TSP.zx48:
                    ZX48_IO(pre)
                    
            elif pre[0] == 65:
                LOG('INFO: Starting "A" COMMAND', 0)
                
                PROCESS_ASM(pre)
                DIR_FILES()
                
            else:
                try:
                    LOG("WARNING: Unrecognized command! " +  pre, 1)
                except:
                    LOG("WARNING: Unrecognized command! Cannot get pre[] data", 1)
                
                while MQ.rx_fifo() != 0:
                    MQ.get()
                while MQ.tx_fifo() != 0:
                    MQ.exec("pull (noblock)")
                    MQ.exec("set (osr, null)")
                MQ.active(0)
                utime.sleep(.01)
                MQ.active(1)
                
                BLINK_ERROR()
                
                LOG("INFO: Cleared TX/RX FIFO after unrecognized cmd: " + str(MQ.tx_fifo()) + " " + str(MQ.rx_fifo()), 0)
                
        else:
            if time.ticks_us() - ts < 2_000_000:
                continue
            elif time.ticks_us() - ts < 2_100_000:
                led.value(1)
            else:
                if log_entries:
                    if not busy:
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

    MQ = StateMachine(0, TS_IO_DUAL, freq=30_000_000, out_base=Pin(2, Pin.OUT), in_base=Pin(2, Pin.IN), jmp_pin=Pin(11), sideset_base=Pin(12, Pin.OUT))
    MQ.active(0)
    
    utime.sleep(0.01)
    MQ.active(1)
    
    LOG("INFO: Starting ZX Mode...", 0)

    ts = time.ticks_us()
    
    while True:
        
        if (MQ.rx_fifo()) != 0:
            
            ts = time.ticks_us()
            a = MQ.get()
            
            if a == 76:                                                    # ASCII 'L' - for LOAD

                if TSP.ZX_TAPE_COMPAT:                                      # compatible-mode ZX Spectrum LOAD

                    if par1 == 1 and par2 >= 16384:
                        buf_size = par2
                        LOG("INFO: ZX48 buffer size = %d" % par2, 0)
                    else:
                        buf_size = 52100                                          # lower this if mem allocation error arises
                    MQ, TSP, new_logs = LOAD_ZX_C(MQ, TSP, buf_size)
                    log_entries += new_logs
                else:
                    # 'regular' ZX Spectrum LOAD
                    LOG("INFO: Starting ZX LOAD", 0)
                    MQ, TSP, new_logs = LOAD_ZX(MQ, TSP)
                
            elif a == 83:                                                  # ASCII 'S' - for SAVE
                
                LOG("INFO: Starting ZX SAVE", 0)
                MQ, TSP, new_logs = SAVE_ZX(MQ, TSP)
                log_entries += new_logs
                      
            elif a == 100:                                                  # ASCII 'X' - for EXIT. David, change this to whatever you thing suits better
                LOG("INFO: Ending ZX mode. Free mem: " + str(gc.mem_free()) + ". Returning to TS processing.", 0)
                gc.collect()
                
                break
            
            else:
                LOG("WARNING: Unrecognized ZX command", 1)
                while MQ.rx_fifo() != 0:
                    MQ.get()
                while MQ.tx_fifo() != 0:
                    MQ.exec("pull (noblock)")
                    MQ.exec("set (osr, null)")
                MQ.active(0)
                utime.sleep(.01)
                MQ.active(1)
                
                LOG("INFO: Cleared TX/RX FIFO after unrecognized ZX command: " + str(MQ.tx_fifo()) + " " + str(MQ.rx_fifo()), 0)

        else:
            if time.ticks_us() - ts < 2_000_000:
                continue
            elif time.ticks_us() - ts < 2_100_000:
                led.value(1)
            else:
                
                if log_entries:
                    SAVE_LOG()
                    log_entries = ""
                    
                led.value(0)
                ts = time.ticks_us()

    # Debug - Ricardo 21 Aug 2025 for returning from Spectrum mode problem
    if MQ.tx_fifo() != 0:
        print("MQ FIFO: ", MQ.tx_fifo())
        LOG("WARNING: TX FIFO not empty after ZX mode. Trying to force cleanup", 1)
        
        while MQ.tx_fifo() != 0:
            MQ.exec("pull (noblock)")
            MQ.exec("set (osr, null)")
            
        MQ.active(0)
        utime.sleep(.01)
        MQ.active(1)
        
        LOG("INFO: TX FIFO succesfully cleared before returning from ZX mode", 0)
        
    else:
        LOG("INFO: Returning from ZX mode; TX FIFO is empty: ", 0)
