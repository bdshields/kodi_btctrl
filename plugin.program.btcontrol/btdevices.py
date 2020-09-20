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
    xbmc.log("{}".format(message), level=xbmc.LOGNOTICE)
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
        response['action']="none"
        offset = -1
    
    
    if offset >= 0:
        response['data'] = {}
        response['data']['type'], response['data']['addr'], response['data']['desc'] = cleaned[offset:].split(' ', 2)
    return response

class btdevices:
    devices = []
    scanning = False
    ready = False
    infoIndex = -1
    infoDevice = None
    def __init__(self, exe="/usr/bin/bluetoothctl"):
        infoPrint("starting")

        self.bt_proc = pexpect.spawn(exe)
        if not self.bt_proc.isalive():
            errorPrint ("Process failed to start")
            
        if self.waitfor('Agent registered',5) == 1:
            self.ready = True
        
        return None

    def quit(self):
        self.bt_proc.sendline('quit')
        self.waitfor("Agent unregistered", 5)
        
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
                output = self.bt_proc.before + self.bt_proc.after
                result = decode_response(output)
                if result['action'] == 'new' and result['data']['type'] == 'Device' :
                    self.devices.append(result['data'])
                elif result['action'] == 'existing':
                    self.devices.append(result['data'])
                elif result['action'] == 'scan':
                    self.scanning = result['data']
                elif result['action'] == 'agent':
                    self.ready = result['data']
                elif result['action'] == 'update':
                    if self.infoIndex != -1 and len(self.devices) > self.infoIndex:
                        self.devices[self.infoIndex][result['data']['attr']] = result['data']['value']
                    elif self.infoDevice is not None:
                        self.infoDevice[result['data']['attr']] = result['data']['value']
                if i > 0:
                    return i
            except pexpect.EOF:
                errorPrint ("read end")
                return 0
            except pexpect.TIMEOUT:
                errorPrint ("read timeout")
                return 0
            #except:
            #    errorPrint ("Process not running")
            #    return 0
    
    def getDeviceList(self):
        if self.ready:
            self.bt_proc.sendline('devices')
            self.waitfor('#')
            self.wait(1)
        
    def getPairedList(self):
        if self.ready:
            self.bt_proc.sendline('paired-devices')
            self.waitfor('#')
            self.wait(1)


    def scan(self, state):
        if self.ready:
            if self.scanning == False and state == True:
                self.bt_proc.sendline('scan on')
                self.waitfor('#')
                self.wait(1)
                if self.scanning == False:
                    notify('Failed to scan', 1000)
                    errorPrint ("Failed to start scanning")

                
            elif self.scanning == True and state == False:
                self.bt_proc.sendline('scan off')
                self.waitfor('#')

    def unpair(self, addr):
        if self.ready:
            self.bt_proc.sendline('remove {}'.format(addr))
            self.waitfor('#')
            notify('Device unpaired', 1000)
            
    def pair(self, addr):
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
        if self.ready:
            self.bt_proc.sendline('connect {}'.format(addr))
            self.waitfor(['Connection successful', 'Failed to connect'],10)
            notify(self.bt_proc.after, 1000)

    def disconnect(self, addr):
        if self.ready:
            self.bt_proc.sendline('disconnect {}'.format(addr))
            self.waitfor(['Successful disconnected','Device {} not available'.format(addr)],10)
            notify(self.bt_proc.after, 1000)

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

    def info(self, addr):
        if self.ready:
            self.waitfor('#')
            self.infoDevice = {'addr':addr}
            self.bt_proc.sendline('info {}\n'.format(addr))
            self.waitfor('#')
            newDevice = self.infoDevice
            debugPrint(newDevice)
            self.infoDevice = None
            
            return newDevice
