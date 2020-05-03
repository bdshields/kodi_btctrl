import sys
import re

import pexpect
from time import sleep

import xbmc
import logging
from __builtin__ import list


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
    xbmc.log(message, level=xbmc.LOGNOTICE)
    #logger.debug(message, *args)
    
def infoPrint(message, *args):
    xbmc.log(message, level=xbmc.LOGINFO)
    #logger.info(message, *args)
    
def errorPrint(message, *args):
    xbmc.log(message, level=xbmc.LOGERROR)
    #logger.error(message, *args)


def decode_response(message):
    response={}
    offset = 0
    ''' Remove colours '''
    ansi_escape =re.compile(r'(\x9B|\x1B\[)[0-?]*[ -\/]*[@-~]')
    cleaned = ansi_escape.sub('',message)

    ''' Remove leading prompt '''
    cleaned = cleaned.replace("[bluetooth]#",'')
    cleaned = cleaned.replace("Waiting to connect to bluetoothd...",'').lstrip()
    
    cleaned = cleaned.rstrip()
    debugPrint(cleaned)
    if cleaned.startswith("[NEW]"):
        response['action']="new"
        offset = 6
    elif cleaned.startswith("[DEL]"):
        response['action']="delete"
        offset = 6
    elif cleaned.startswith("[CHG]"):
        response['action']="change"
        offset = 6
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
        debugPrint ("Unknown response")
        response['action']="none"
        offset = -1
    
    
    if offset >= 0:
        response['data'] = {}
        response['data']['type'], response['data']['addr'], response['data']['desc'] = cleaned[offset:].split(' ', 2)
    #debugPrint (response)
    return response

class btdevices:
    devices = []
    scanning = False
    ready = False
    infoIndex = -1
    def __init__(self):
        infoPrint("starting")
        
        self.bt_proc = pexpect.spawn("/usr/bin/bluetoothctl")
        if not self.bt_proc.isalive():
            errorPrint ("Process failed to start")
            
        if self.waitfor('Agent registered',5) == 1:
            self.ready = True
        
        return None

    def quit(self):
        self.bt_proc.sendline('quit')
        
    def __del__(self):
        self.quit()

    
    def wait(self, timeout):
        delay = 0
        while delay < timeout:
            if self.waitfor('#') == 0:
                delay = delay + 1
            else:
                sleep(0.1)
                delay = delay + 0.1
    
    def waitfor(self,message, timeout=1):
        if type(message) is list:
            prompt = ['\n'] + message
        else:
            prompt = ['\n', message]
        while True:
            try:
                i = self.bt_proc.expect(prompt, timeout=timeout)
                output = self.bt_proc.before
                result = decode_response(output)
                if result['action'] == 'new' and result['data']['type'] == 'Device' :
                    self.devices.append(result['data'])
                elif result['action'] == 'scan':
                    self.scanning = result['data']
                elif result['action'] == 'agent':
                    self.ready = result['data']
                elif result['action'] == 'update':
                    if self.infoIndex != -1 and len(self.devices) > self.infoIndex:
                        self.devices[self.infoIndex][result['data']['attr']] = result['data']['value']
                if i > 0:
                    return 1
            except pexpect.EOF:
                errorPrint ("read end")
                return 0
            except pexpect.TIMEOUT:
                errorPrint ("read timeout")
                return 0
            except:
                errorPrint ("Process not running")
                return 0
    
    def scan(self, state):
        if self.ready:
            if self.scanning == False and state == True:
                self.bt_proc.sendline('scan on')
                self.waitfor('#')
                
            elif self.scanning == True and state == False:
                self.bt_proc.sendline('scan off')
                self.waitfor('#')

    def unpair(self, addr):
        if self.ready:
            self.bt_proc.sendline('remove {}'.format(addr))
            self.waitfor('#')
            
    def pair(self, addr):
        if self.ready:
            self.bt_proc.sendline('pair {}'.format(addr))
            if self.waitfor(['Pairing successful', 'Failed to pair'],10) == 1:
                self.bt_proc.sendline('trust {}'.format(addr))
                self.waitfor('#',10)
                self.bt_proc.sendline('connect {}'.format(addr))
                self.waitfor('#',10)


    def findDevice(self, data):
        index = 0
        while index < len(self.devices):
            if 'desc' in data:
                if data['desc'] == self.devices[index]['desc']:
                    return index
            elif 'addr' in data:
                if data['addr'] == self.devices[index]['addr']:
                    return index
            else:
                raise KeyError("Invalid key used in device search")
            index = index + 1
        raise StopIteration("Device not found")

    def info(self, data):
        if self.ready:
            self.infoIndex = -1
            try:
                index = self.findDevice(data)
            except:
                errorPrint("Device not found")
            else:
                self.infoIndex = index
                self.bt_proc.sendline('info {}\n'.format(self.devices[index]['addr']))
                self.waitfor('#')
                self.infoIndex = -1
