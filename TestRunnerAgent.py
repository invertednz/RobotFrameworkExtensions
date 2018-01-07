# Copyright 2010 Orbitz WorldWide
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Modified by Mikko Korpela under NSN copyrights
#  Copyright 2008-2012 Nokia Siemens Networks Oyj
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

'''A Robot Framework listener that sends information to a socket

This uses the "pickle" module of python to send objects to the
listening server. It should probably be refactored to call an
XMLRPC server.
'''
from __future__ import with_statement
import os
import socket
import threading
import SocketServer
import jprops


try:
    # RF 2.7.5
    from robot.running import EXECUTION_CONTEXTS
    def _is_logged(level):
        current = EXECUTION_CONTEXTS.current
        if current is None:
            return True
        out = current.output
        if out is None:
            return True
        return out._xmllogger._log_message_is_logged(level)
except ImportError:
    # RF 2.5.6
    # RF 2.6.3
    def _is_logged(level):
        from robot.output import OUTPUT # Needs to be imported in the function as OUTPUT is not a constant
        if OUTPUT is None:
            return True
        return OUTPUT._xmllogger._log_message_is_logged(level)

from robot.running.signalhandler import STOP_SIGNAL_MONITOR
from robot.errors import ExecutionFailed


try:
    import cPickle as pickle
except ImportError:
    import pickle

PORT = 5007
HOST = "localhost"


# Setting Output encoding to UTF-8 and ignoring the platform specs
# RIDE will expect UTF-8
import robot.utils.encoding
from datetime import datetime
robot.utils.encoding.OUTPUT_ENCODING = 'UTF-8' # Set output encoding to UTF-8 for piped output streams
robot.utils.encoding._output_encoding = robot.utils.encoding.OUTPUT_ENCODING # RF 2.6.3 and RF 2.5.7

class TestRunnerAgent:
    """Pass all listener events to a remote listener

    If called with one argument, that argument is a port
    If called with two, the first is a hostname, the second is a port
    """
    ROBOT_LISTENER_API_VERSION = 2

    def __init__(self, *args):
        self.port = PORT
        self.host = HOST
        self.sock = None
        if len(args) == 1:
            self.port = int(args[0])
        elif len(args) >= 2:
            self.host = args[0]
            self.port = int(args[1])
        self._connect()
        self._send_pid()
        self._create_debugger()
        self._create_kill_server()

    def _create_debugger(self):
        self._debugger = RobotDebugger()

    def _create_kill_server(self):
        self._killer = RobotKillerServer(self._debugger)
        self._server_thread = threading.Thread(target=self._killer.serve_forever)
        self._server_thread.setDaemon(True)
        self._server_thread.start()
        self._send_server_port(self._killer.server_address[1])

    def _send_pid(self):
        self._send_socket("pid", os.getpid())

    def _send_server_port(self, port):
        self._send_socket("port", port)

    def start_test(self, name, attrs):
        self._send_socket("start_test", name, attrs)

    def end_test(self, name, attrs):
        self._send_socket("end_test", name, attrs)

    def start_suite(self, name, attrs):
        self._send_socket("start_suite", name, attrs)

    def end_suite(self, name, attrs):
        self._send_socket("end_suite", name, attrs)

    def start_keyword(self, name, attrs):
        #print 'About to execute keyword %s with arguments %s' % (name, attrs['args'])
        envLocation = os.environ.get('AUTOMATED_HOME')
        propLocation = os.path.join(envLocation, 'listenerLog0.properties')
        propLocation = os.path.abspath(propLocation)
        lastKeyword = ""
        with open(propLocation) as fp:
            for key, value in jprops.iter_properties(fp):
                if key.startswith('lastKeyword'):
                    lastKeyword = value     
        #print lastKeyword
        self._send_socket("start_keyword", name, attrs)
        if self._debugger.is_breakpoint(name, attrs):
            self._debugger.pause()
        paused = self._debugger.is_paused()
        if paused:
            self._send_socket('paused')
        self._debugger.start_keyword()
        if paused:
            self._send_socket('continue')

    def end_keyword(self, name, attrs):
        #print 'COMPLETED %s' % (str(datetime.now()))
        self._send_socket("end_keyword", name, attrs)
        self._debugger.end_keyword(attrs['status']=='PASS')

    def message(self, message):
        pass

    def log_message(self, message):
        if _is_logged(message['level']):
            self._send_socket("log_message", message)

    def log_file(self, path):
        self._send_socket("log_file", path)

    def output_file(self, path):
        pass

    def report_file(self, path):
        self._send_socket("report_file", path)

    def summary_file(self, path):
        pass

    def debug_file(self, path):
        pass

    def close(self):
        self._send_socket("close")
        if self.sock:
            self.filehandler.close()
            self.sock.close()

    def _connect(self):
        '''Establish a connection for sending pickles'''
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            # Iron python does not return right kind of objects if binary mode is not used
            self.filehandler = self.sock.makefile('wb')
            self.pickler = pickle.Pickler(self.filehandler)
        except socket.error, e:
            print 'unable to open socket to "%s:%s" error: %s' % (self.host, self.port, str(e))
            self.sock = None

    def _send_socket(self, name, *args):
        if self.sock:
            packet = (name, args)
            self.pickler.dump(packet)
            self.filehandler.flush()


class RobotDebugger(object):

    def __init__(self):
        self._state = 'running'
        self._keyword_level = 0
        self._pause_when_on_level = -1
        self._pause_on_failure = False
        self._resume = threading.Event()

    def is_breakpoint(self, name, attrs):
        return (name == 'BuiltIn.Comment' and attrs['args'] == ['PAUSE']) or name == 'scenario.framework.main.Keyword.Break Point'

    def check_status(self):
        envLocation = os.environ.get('AUTOMATED_HOME')
        propLocation = os.path.join(envLocation, 'listenerLog0.properties')
        propLocation = os.path.abspath(propLocation)
        data = ""
        
        with open(propLocation) as fp:
            for key, value in jprops.iter_properties(fp):
                if key.startswith('data'):
                    data = value
        return data
        
    def set_state(self, valueData):
        envLocation = os.environ.get('AUTOMATED_HOME')
        propLocation = os.path.join(envLocation, 'listenerLog0.properties')
        propLocation = os.path.abspath(propLocation)
        lastTestPassed = "true"
        onHold = "false"
        breakPoint = "false"
        lastKeyword = ""
        with open(propLocation) as fp:
            for key, value in jprops.iter_properties(fp):
                if key.startswith('lastTestPassed'):
                    try:
                        lastTestPassed = value
                    except:
                        lastTestPassed = "true"
                if key.startswith('onHold'):
                    try:
                        onHold = value
                    except:
                        onHold = "false"
                if key.startswith('breakPoint'):
                    try:
                        breakPoint = value
                    except:
                        breakPoint = "false"
                if key.startswith('lastKeyword'):
                    try:
                        lastKeyword = value
                    except:
                        lastKeyword = "none"
        with open(propLocation, 'w') as fp:
            jprops.write_property(fp, 'data', valueData)
            jprops.write_property(fp, 'lastTestPassed', lastTestPassed)
            jprops.write_property(fp, 'onHold', onHold)
            jprops.write_property(fp, 'lastKeyword', lastKeyword)
            jprops.write_property(fp, 'breakPoint', 'true')
    
    def pause(self):
        self._resume.clear()
        self.set_state('pause')
        #self._state = 'pause'

    def pause_on_failure(self, pause):
        self._pause_on_failure = pause

    def resume(self):
        self.set_state('running')
        #self._state = 'running'
        self._pause_when_on_level = -1
        self._resume.set()

    def step_next(self):
        self.set_state('step_next')
        self._state = 'step_next'
        self._resume.set()

    def step_over(self):
        self.set_state('step_over')
        self._state = 'step_over'
        self._resume.set()

    def start_keyword(self):
        datastate = self.check_status()
        # 'State = %s' % (datastate)
        while datastate == 'pause':
            #print 'State = %s' % (datastate)
            #self._resume.wait()
            #print 'Statea = %s' % (datastate)
            #self._resume.clear()
            self._resume.wait(1)
            #print 'Stateb = %s' % (datastate)
            datastate = self.check_status()
            self._resume.wait(1)
            #print 'Statec = %s' % (datastate)
        #print 'State1 = %s' % (datastate)
        if datastate == 'step_next':
            self.set_state('pause')
            self._state = 'pause'
        elif datastate == 'step_over':
            #print 'pause on level'
            #print self._pause_when_on_level
            #print 'keyword level'
            #print self._keyword_level
            #print '1pause on level = %d and keyword level = %d' (self._pause_when_on_level, self._keyword_level)
            self._pause_when_on_level = self._keyword_level
            #print '2pause on level = %d and keyword level = %d' (self._pause_when_on_level, self._keyword_level)
            self._state = 'resume'
            self.set_state('resume')
        self._keyword_level += 1
        #print '3pause on level = %d and keyword level = %d' (self._pause_when_on_level, self._keyword_level)
        '''while self._state == 'pause':
            self._resume.wait()
            self._resume.clear()
        if self._state == 'step_next':
            self._state = 'pause'
        elif self._state == 'step_over':
            self._pause_when_on_level = self._keyword_level
            self._state = 'resume'
        self._keyword_level += 1'''

    def end_keyword(self, passed=True):
        self._keyword_level -= 1
        #print '4pause on level = %d and keyword level = %d' (self._pause_when_on_level, self._keyword_level)
        if self._keyword_level == self._pause_when_on_level \
        or (self._pause_on_failure and not passed):
            self.set_state('pause')
            self._state = 'pause'

    def is_paused(self):
        #return self._state == 'pause'
        return self.check_status() == 'pause'

class RobotKillerServer(SocketServer.TCPServer):
    allow_reuse_address = True
    def __init__(self, debugger):
        SocketServer.TCPServer.__init__(self, ("",0), RobotKillerHandler)
        self.debugger = debugger
        

class RobotKillerHandler(SocketServer.StreamRequestHandler):
    def handle(self):
        envLocation = os.environ.get('AUTOMATED_HOME')
        propLocation = os.path.join(envLocation, 'listenerLog0.properties')
        propLocation = os.path.abspath(propLocation)
        lastTestPassed = "true"
        onHold = "false"
        breakPoint = "false"
        data = ""
        with open(propLocation) as fp:
            for key, value in jprops.iter_properties(fp):
                if key.startswith('data'):
                    data = value
        if data == 'kill':
            self._signal_kill()
        elif data == 'pause':
            self.server.debugger.pause()
        elif data == 'resume':
            self.server.debugger.resume()
        elif data == 'step_next':
            self.server.debugger.step_next()
        elif data == 'step_over':
            self.server.debugger.step_over()
        elif data == 'pause_on_failure':
            self.server.debugger.pause_on_failure(True)
        elif data == 'do_not_pause_on_failure':
            self.server.debugger.pause_on_failure(False)

    def _signal_kill(self):
        try:
            STOP_SIGNAL_MONITOR(1,'')
        except ExecutionFailed:
            pass
