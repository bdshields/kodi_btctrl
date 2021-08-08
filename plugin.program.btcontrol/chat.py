#!/usr/bin/python
import sys
import signal
import select
import subprocess
import time
import re

class chat():
    def __init__(self):
        self.proc=None
        self.prompt=None
        self.local_echo=False
        self.echo_not_eaten=False
        self.line_ending="\r"
        self.timeout=0
        self._match=None
        self._data=None

    def __del__(self):
        if self.proc.poll() == None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except:
                self.proc.kill()
            

    @classmethod
    def process(cls, exe_list, **kwargs):
        """
        Constructor version of run() method
        """
        obj=cls()
        obj.run(exe_list, **kwargs)
        return obj
    
    def run(self,exe_list, **kwargs):
        """
        Starts a process.
        Options:
            line_ending : specify the line ending
            local_echo  : Does the process echo what is written.
                            The option will drop any local echos
        """
        self.proc = subprocess.Popen(exe_list,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
        if 'prompt' in kwargs.keys():
            self.prompt = kwargs['prompt']
        if 'local_echo' in kwargs.keys():
            self.local_echo=kwargs['local_echo']
        if 'line_ending' in kwargs.keys():
            self.line_ending=kwargs['line_ending']
        if 'timeout' in kwargs.keys():
            self.timeout = args.timeout

    def _assertrunning(self):
        if self.proc.poll() != None:
            raise Exception("Process not running")

    def _readall(self, timeout=0):
        self._assertrunning()
        r,w,e = select.select([self.proc.stdout],[self.proc.stdin],[],timeout)
        if self.proc.stdout in r:
            return self.proc.stdout.read1().decode()
        else:
            return None

    def read(self, timeout=None):
        """
        Reads data from stdout of the process.
        Returns a list of strings split by the line_ending
        """
        if timeout == None:
            timeout = self.timeout
        data = self._readall(timeout)
        if data != None:
            response = data.rstrip(self.line_ending).split(self.line_ending)
            if self.local_echo and self.echo_not_eaten:
                response.pop(0)
                self.echo_not_eaten = False
            return response
        else:
            return None

    def _write(self, data):
        self._assertrunning()
        self.proc.stdin.write(data.encode())
        self.proc.stdin.flush()
    
    def write(self, line):
        """
        Writes a string to stdin of the process.
        Appends line_ending before passing it on.
        """
        self._write(line+self.line_ending)
        self.echo_not_eaten=True
        self._data=None

    def _waitfor(self, expect_regex, timeout=None):
        """
        Waits for the desired response
        expect_regex can be a string or list of strings that get interpretted as regex.
        Returns a tuple:
            True or False if match was successful
            Index into expect_regex that represents the successful match
        """
        if type(expect_regex) is list:
            regex_list = expect_regex
        else:
            regex_list = [expect_regex]
        if timeout == None:
            timeout = self.timeout

        self._data=[]
        self._match=None
        started = time.time()
        while True:
            data = self.read(0)
            if data != None:
                for line in data:
                    for regex_idx in range(0, len(regex_list)):
                        match = re.search(regex_list[regex_idx],line)
                        if match != None:
                            self._match = match
                            self._data += data
                            return True, regex_idx
                self._data +=  data
            if started + timeout < time.time():
                return False, None

    @property
    def data(self):
        """
        returns the data from recent call to waitfor()
        """
        return self._data

    @property
    def match(self):
        """
        returns the match object found in recent call to waitfor()
        """
        return self._match
    
    def waitfor(self, expect_regex, timeout=None):
        self.echo_not_eaten=False
        return self._waitfor(expect_regex, timeout)

    def expect(self, message, expect_regex, timeout=None):
        """
        Writes a message to stdin of the process, and waits for the desired response
        expect_regex can be a string or list of strings that get interpretted as regex.
        Returns a tuple:
            True or False if match was successful
            Index into expect_regex that represents the successful match
            List of all lines read from stdout when waiting for the match
        """
        self.write(message)
        return self._waitfor(expect_regex, timeout)

    def isrunning(self):
        if self.proc.poll() == None:
            return True
        else:
            return False


