import sys
import re

#import pexpect
import subprocess
from time import sleep

import xbmc
import logging


''' Filter for std error '''
class debugFilter(logging.Filter):
    def filter(self, record):
        if record.levelno < logging.INFO:
            return True
        else:
            return False

''' Create logger '''
logger = logging.getLogger("btctrl")
logger.setLevel(logging.DEBUG)

''' INFO level and above go to std out '''
hdlInfo = logging.StreamHandler(sys.stdout)
hdlInfo.setLevel(logging.CRITICAL)
logger.addHandler(hdlInfo)

''' DEBUG level go to std err '''
hdlDebug = logging.StreamHandler(sys.stderr)
hdlDebug.setLevel(logging.INFO)
f = debugFilter()
hdlDebug.addFilter(f)
logger.addHandler(hdlDebug)


def debugPrint(message, *args):
    xbmc.log("{}".format(message), level=xbmc.LOGDEBUG)
    #logger.debug(message, *args)
    
def infoPrint(message, *args):
    xbmc.log("{}".format(message), level=xbmc.LOGINFO)
    #logger.info(message, *args)
    
def errorPrint(message, *args):
    xbmc.log("{}".format(message), level=xbmc.LOGERROR)
    #logger.error(message, *args)

def notify(message, delay=2000):
    xbmc.executebuiltin('Notification(%s, %s, %d)'%("Bluetooth",message, delay))

def decode_response(message):
    response={}
    offset = 0
    ''' Remove colours '''
    ansi_escape =re.compile(r'(\x01.*?\x02)')
    cleaned = ansi_escape.sub('',message)

    ''' Remove leading prompt '''
    cleaned = cleaned.replace("[bluetooth]#",'')
    cleaned = cleaned.replace("Waiting to connect to bluetoothd...",'').lstrip()
    
    cleaned = cleaned.rstrip()
    infoPrint(cleaned)
    if cleaned.startswith("[NEW]"):
        response['action']="new"
        offset = 6
    elif cleaned.startswith("[DEL]"):
        response['action']="delete"
        offset = 6
    elif cleaned.startswith("[CHG]"):
        response['action']="change"
        offset = 6
    elif cleaned.startswith("Device "):
        response['action']="existing"
        offset = 0
    elif cleaned.startswith("Agent registered"):
        response['action']="agent"
        response['data']=True
        offset = -1
    elif cleaned.startswith("Agent unregistered"):
        response['action']="agent"
        response['data']=False
        offset = -1
    elif cleaned.startswith("Discovery started"):
        response['action']="scan"
        response['data']=True
        offset = -1
    elif cleaned.startswith("Discovery stopped"):
        response['action']="scan"
        response['data']=False
        offset = -1
    elif cleaned.find(": ") != -1:
        response['action']="update"
        response['data']={}
        response['data']['attr'], response['data']['value']=cleaned.split(': ',1)
        offset = -1
    else:
        response['action']="message"
        response['data']=cleaned
        offset = -1

    if offset >= 0:
        response['data'] = {}
        response['data']['type'], response['data']['addr'], response['data']['desc'] = cleaned[offset:].split(' ', 2)
    infoPrint(response)
    return response

def process_response(resp):
    data=resp.decode('utf-8').splitlines()
    response = {}
    response['devices']=[]
    for line in data:
        line_decoded = decode_response(line)
        if line_decoded['action'] == "new":
            response['devices'].append(line_decoded['data'])
        if line_decoded['action'] == "existing":
            response['devices'].append(line_decoded['data'])
        elif line_decoded['action'] == "update":
            response[line_decoded['data']['attr']] = line_decoded['data']['value']        
    infoPrint(response)
    return response


class btdevices:
    devices = []
    scanning = False
    ready = False
    infoIndex = -1
    infoDevice = None
    def __init__(self, exe="/usr/bin/bluetoothctl"):
        infoPrint("starting")
        self.exe = exe
#        self.bt_proc = pexpect.spawn(exe)
#        if not self.bt_proc.isalive():
#            errorPrint ("Process failed to start")
#            
#        if self.waitfor('Agent registered',5) == 1:
#            self.ready = True
        
        return None

    def quit(self):
        return
        self.waitfor("Agent unregistered", 5)
        self.ready = False
        
    def __del__(self):
        if self.ready == True:
            self.quit()

    
    def getDeviceList(self):
        if self.ready:
            self.waitIdle()
            self.bt_proc.sendline('devices')
            self.waitfor('#')
        
    def getPairedList(self):
        response = subprocess.check_output([self.exe, 'paired-devices'])
        result = process_response(response)
        return result['devices']


    def scan(self):
        response = subprocess.check_output([self.exe, '--timeout=10','scan', 'on'])
        result = process_response(response)
        return result['devices']

    def unpair(self, addr):
        response = subprocess.check_output([self.exe, 'remove', addr])
        result = process_response(response)
        notify('Device unpaired', 1000)
            
    def pair(self, addr):
        response = subprocess.check_output([self.exe, 'pair', addr])
        result = process_response(response)
        response = subprocess.check_output([self.exe, 'trust', addr])
        result = process_response(response)
        response = subprocess.check_output([self.exe, 'connect', addr])
        result = process_response(response)
        return

                
        
        if self.ready:
            self.bt_proc.sendline('pair {}'.format(addr))
            response = self.waitfor(['Confirm passkey \d+ ', 'Pairing successful', 'Failed to pair','Device {} not available'.format(addr)],60)
            if response == 1:
                notify(self.bt_proc.after, 5000)
                self.bt_proc.sendline('yes')
                response = self.waitfor(['Confirm passkey', 'Pairing successful', 'Failed to pair'],10)
            if response == 2:
                notify(self.bt_proc.after, 1000)
                self.bt_proc.sendline('trust {}'.format(addr))
                self.waitfor('#',10)
                self.bt_proc.sendline('connect {}'.format(addr))
                self.waitfor('#',10)
            if response == 3 or response == 4:
                notify(self.bt_proc.after, 1000)

    def connect(self, addr):
        response = subprocess.check_output([self.exe, 'connect', addr])
        result = process_response(response)
        notify('Device connected', 1000)


    def disconnect(self, addr):
        response = subprocess.check_output([self.exe, 'disconnect', addr])
        result = process_response(response)
        notify('Device disconnected', 1000)


    def info(self, addr):
        response = subprocess.check_output([self.exe, 'info', addr])
        result = process_response(response)
        return result
'''
        if self.ready:
            self.infoDevice = {'addr':addr}
            self.waitIdle()
            self.bt_proc.sendline('info {}\n'.format(addr))
            if self.waitfor(['Device {} not available'.format(addr), '#']) == 1:
                notify("Device not available", 1000)
                return None
            else:
                self.waitIdle()
                newDevice = self.infoDevice
                #debugPrint(newDevice)
                self.infoDevice = None
                
                return newDevice
        else:
            return None
'''
