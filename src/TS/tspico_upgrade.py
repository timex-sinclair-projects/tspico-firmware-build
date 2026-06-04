# TS-Pico Upgrade Module
#
# 2026-04-06
#
# Separated from tspico.py to reduce memory usage - only loaded when needed
# (The original tspico.py was near the memory limit of the Micropython parser)

# Changelog:
# - Optimizing string construction
# - Remove unused global 32K bytearray un UPGRADE()
# - 2026-05: Fix imports for runtime usability — previously this module
#   referenced SEND_MSG, LOG, SAVE_LOG, ACTIVATE_SD, REMOVE_DIR, COPY_FILE,
#   dir_exists, _1_OK, TSP, log_to_serial without importing them, so the
#   first call into UPGRADE() raised NameError. Also fixed STAT_1_OK ->
#   _1_OK rename and a leftover log_ena argument on a FINISH() call.

import os
import time
import json
import sys

from machine import Pin

# ─── DUAL-PORT MIGRATION: imports from the caller module ─────────────────
# This module is loaded lazily from dev_tspico.UPGRADE() (via
# `from TS.tspico_upgrade import UPGRADE`), so dev_tspico is fully
# initialized by the time this `import dev_tspico` line runs. No
# circular-import risk.
#
# We import:
#   - dev_tspico as a module (for access to mutable globals like TSP
#     and log_to_serial, which may be reassigned by dev_tspico after
#     boot — module attribute access always reads the current value)
#   - stateless helpers by name (they don't change after definition)
#
# If this module is ever called from the frozen production firmware
# instead of the dev override, swap the import to `import TS.tspico as
# dev_tspico` (or do a try/except chain).
# ─────────────────────────────────────────────────────────────────────────
import dev_tspico
from dev_tspico import (
    SEND_MSG, LOG, SAVE_LOG,
    ACTIVATE_SD, REMOVE_DIR, COPY_FILE, dir_exists,
    _1_OK as STAT_1_OK,
)


def BACKUP_DIR(d, dest_dir):                                                               # Recursively backs-up folders and files of a provided "d" folder; typically d="/" (root of the Flash)
                                                                                           # and dest_dir = /sd/BACKUP
    if dir_exists(d):
        
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
                msg = "Copying file %s to %s" % (copy_src, copy_dst)
                LOG(msg, 4)
                
                if not COPY_FILE(copy_src, copy_dst):
                    FINISH("Fatal error: %s. Terminating" % msg, False)
                continue
            
            if f[0] not in ('.', '..'):
                folder_name = '%s/%s' % (d, f[0])
                LOG("Processing folder %s" % folder_name, 4)
                BACKUP_DIR(folder_name, dest_dir)  # File or Dir
        
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
    

def RESTORE_FILES(src, dst):                                                             # Restores prev backed-up files; typically scr=/sd/BACKUP - dst = / (root of the Flash)

    if dir_exists(src):
    
        for el in os.listdir(src):
            f_name = src + '/' + el
            
            if (dst == "/"):
                new_path = dst + el
            else:
                new_path = dst + '/' + el
                
            if dir_exists(f_name):
                
                LOG("Restoring folder %s" % f_name, 4)
                SAVE_LOG()
                
                try:
                    os.mkdir(new_path)
                    LOG('RESTORE: folder "%s" not found; succesfully created' % new_path, 4)
                    SAVE_LOG()
                
                except:
                    LOG('Folder "%s" already exists during RESTORE. Moving on' % new_path, 4)
                    SAVE_LOG()
                
                RESTORE_FILES(f_name, new_path)
                
            else:
                
                LOG('Restoring file "%s" to %s' % (f_name, new_path), 4)
                SAVE_LOG()
                
                if COPY_FILE(f_name, new_path):
                    pass


def UPGRADE(pre, cmd):

    # ─── DUAL-PORT MIGRATION ─────────────────────────────────────────
    # Was:  global TSP; global log_to_serial
    # These were broken — `global` refers to THIS module's globals,
    # but TSP and log_to_serial live in dev_tspico. Use module-attribute
    # access on dev_tspico.* instead (reads always see the current
    # value, writes propagate back to dev_tspico).
    # ─────────────────────────────────────────────────────────────────

    SEND_MSG("Upgrade started. DON'T INTERRUPT", "after the first 10 blinks!", STAT_1_OK, True)
    
    last_run = {}                                                           # dictionary to hold last upgrade run's status
    new_values = {}                                                         # dictionary of upgraded config.ini values
    upgrade_dict = {}                                                       # dictionary of files to be upgraded
    restored = False
    
    led = Pin(25, Pin.OUT)
    U6_EN = Pin(12, Pin.OUT, Pin.PULL_UP)
    
    U6_EN.value(1)                                                          # We disable U6_ENABLE, just in case.....
    
    for i in range(20):                                                     # We give the user 10s and 20 LED blinks to abort installation
        time.sleep(.5)
        led.toggle()

    led.value(1)
    
    dev_tspico.log_to_serial = True            # was: log_to_serial = True (broken: local, not dev_tspico's)
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

    LOG("Previous run status: %s" % last_run_status, 4)
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
            LOG(f"System roll back failed. Reason: {err}", 4)
            
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

    LOG("Current firmware version: %s" % dev_tspico.TSP.FW_VERSION, 4)

    LOG("New firmware version: %s" % new_values["FW_VERSION"], 4)

    if (dev_tspico.TSP.FW_VERSION == new_values["FW_VERSION"]):
       FINISH("Current version is the same as upgrade. Nothing to do. Terminating", True)
       
    SAVE_LOG()
    os.chdir("/sd/UPGRADE")
    
    if restored:
        LOG("Bypass system backup due to recent succesful RESTORE", 4)
        SAVE_LOG()
        
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
            LOG('Could not remove folder "%s"; continue process...' % el, 4)
            SAVE_LOG()
            pass
        
        try:
            os.mkdir(el)
            
        except:                
            FINISH('Fatal error: unable to create folder "%s" during Update. Terminating.' % el, False)
            
    for el in upgrade_dict:
        
        if el == "dirs":
            continue
        
        if el == "main.py":
            os.rename("/main.py", "/main.old")
            LOG("'main.py' renamed to 'main.old'", 4)
            SAVE_LOG()
        if not COPY_FILE(el, upgrade_dict[el]+el):
            # Was: FINISH('Fatal error...' % el, log_ena, False)
            # log_ena was an undefined name AND FINISH only takes (msg, success).
            # Looks like a leftover from an older 3-arg signature. Fixed:
            FINISH('Fatal error: unable to copy file "%s" during Update. Terminating' % el, False)

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
            LOG("Error renaming folder: %s" % new_folder, 4)
            SAVE_LOG()
            
    LOG("Finished renaming BACKUP folder", 4)
    SAVE_LOG()

    FINISH("All process finished successfully. Check the activity.log file for more info", True)
    
    return


