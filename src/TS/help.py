SA_NO_HLP = "Sorry, no further help for this subject. Please see manual or ask on the online forums for help"
APPEND_HLP = "Configure whether or not the next SAVE will be appended to the currently opened TAP file. Default is Disabled"
BITSTREAM_HLP = "Send the mounted file, byte by byte, to the TS. Each byte can be read by issuing LET a = IN (14) in BASIC or IN (A), 14 in Assembler. If mounting a .BIN or .ROM file,"
BITSTREAM_HLP += "it is possible to send only nn bytes with CODE nn, 0 "
CDIR_HLP = "Change the working dir to "
SA_HLP = {
    "TPI:APPEND" : APPEND_HLP,
    "TPI:BITSTREAM": BITSTREAM_HLP,
    "TPI:CD " : CDIR_HLP,
#     "TPI:CLOSE": UNMOUNT_HLP,
#     "TPI:FFW" : FWD_HLP,
#     "TPI:GETHELP" : GETHELP_HLP,
#     "TPI:GETINFO" : GETINFO_HLP,
#     "TPI:GETLOG" : GETLOG_HLP, 
#     "TPI:MD " : MDIR_HLP,
#     "TPI:MEMBOOT" : MEMBOOT_HLP,
#     "TPI:MEMDOCK" : MEMDOCK_HLP,
#     "TPI:RM " : RMDIR_HLP, 
#     "TPI:REW" : REW_HLP,
#     "TPI:ZX48" : ZX48_HLP,
    "TPI:AUTOLF" : SA_NO_HLP,
    "TPI:AUTOPG" : SA_NO_HLP,
    "TPI:BMP" : SA_NO_HLP,
    "TPI:CLPRINT" : SA_NO_HLP,
    "TPI:CONFIG" : SA_NO_HLP,
    "TPI:DELETE" : SA_NO_HLP,
    "TPI:FRESET" : SA_NO_HLP,
    "TPI:GETCONFIG" : SA_NO_HLP, 
    "TPI:MEMINFO" : SA_NO_HLP,
    "TPI:NOAUTOLF" : SA_NO_HLP,
    "TPI:OPPRINT" : SA_NO_HLP,
    "TPI:PRNSZ" : SA_NO_HLP,
    "TPI:SDCARD" : SA_NO_HLP, 
    "TPI:STOP" : SA_NO_HLP,
    "TPI:TAPE" : SA_NO_HLP, 
    }

nl = chr(13)
    
msg = 'LOAD cmds:' + nl
msg += '"tpi:dir" : Show all files in current dir' + nl
msg += '"tpi:path": Full path to current directory' + nl
msg += '"tpi:tapdir": List all TAPs in mounted file' + nl

msg += 'SAVE cmds: ()-> optional' + nl
msg += '"tpi:bitstream" CODE nn, 0: Sends bytes of mounted file to the TS. If nn, send up to nn bytes' + nl
msg += '"tpi:cd <name>": Change to <name> directory. Relative names allowed' + nl
msg += '"tpi:close": Close currently mounted file' + nl
msg += '"tpi:ffw" (CODE nn, 0): FFW (nn) blocks in mounted file' + nl
msg += '"tpi:gethelp": This screen' + nl
msg += '"tpi:getinfo": Show system info' + nl
msg += '"tpi:getlog" (CODE nn,0): Get last nn bytes of logfile' + nl
msg += '"tpi:md ": Make new folder in current dir' + nl
msg += '"tpi:memboot" CODE n,yy: Select slot 0..15 for ROM from SRAM(1) or Flash(2)' + nl
msg += '"tpi:memdock" CODE n,yy: Select slot 0..15 for DCK from SRAM(1) or Flash(2)' + nl
msg += '"tpi:rm <name>": Remove <name> folder from current dir' + nl
msg += '"tpi:rew" (CODE nn,0): REW (nn) blocks in mounted file' + nl
msg += '"tpi:zx48": Start ZX Spec mode. Return with OUT 10,100'
