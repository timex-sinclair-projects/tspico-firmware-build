from random import randint
import math

from TS.sdcard import *

from tspico import ACTIVATE_MQ, ACTIVATE_SD, SEND_MSG, SEND_MSG2
# from TS.tspico import ACTIVATE_MQ, ACTIVATE_SD, SEND_MSG, SEND_MSG2


def FACTORIAL(MQ: StateMachine, TSP, pre, cmd):

    wrt = MQ.put
    
    type_res = 128                                                                     # 128-199 "normal" resp; 200 OK; 201 and up error conditions
    length = 0                                                                         # Length of response
    
    SEND_MSG("Calculating Factorial...", "", 1)                           # Function to send msg after command processing.
    
    par1 = (pre[4] * 256) + pre[3]
    
    if par1 >= 33:                                                                     # TS-2068 can't safely handle factorial values over 33! :(
        type_res = 210                                                                 # If so, we use an error status for response
        msg="Number too big!"                                                          # and send an error msg
        
    else:    
        msg = str(math.factorial(par1))                                                # otherwise, we calculate the factorial and put it on a string
        
    length = len(msg)

    MQ.put(type_res)                                                                   # Send the result as TLV: Type, Length, Value
    MQ.put(length)
    
    for el in msg:
        MQ.put(el)
        
    return    


def RND_WORD(MQ: StateMachine, TSP, pre, cmd):                                         # Sends a random word chosen from '/words.txt' file in Pico Flash
    
    MQ.put(0x40)
    MQ.put(0x01)

    buf = bytearray(10)
    esc = MQ.put
    
    offset = randint(1,85878)                                                          # Generata random offset; 85878 is the position of the last word in the list
    
    with open("/words.txt", "r") as f_in:
        f_in.seek(offset)
        f_in.readline()                                                                # Discard the first word as it most likely is incomplete
        buf = f_in.readline()                                                          # And store the next whole word in buf
        buf = buf[:-2]                                                                 # remove /n/r at the end of the word
    for el in buf:
        MQ.put(el)
    
    return



EXT_SA_FUNCT = {
    
    "TPI:.FACT" : FACTORIAL,
    "TPI:.RNDW" : RND_WORD,
    }
