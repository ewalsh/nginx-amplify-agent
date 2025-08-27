# -*- coding: utf-8 -*-
#import signal

#from daemon import runner

from amplify.agent.common.context import context

#__author__ = "Mike Belov"
#__copyright__ = "Copyright (C) Nginx, Inc. All rights reserved."
#__license__ = ""
#__maintainer__ = "Mike Belov"
#__email__ = "dedm@nginx.com"


#class Runner(runner.DaemonRunner):
#    def __init__(self, app):
#        super(Runner, self).__init__(app)

#        def cleanup(signum, frame):
#            app.stop()

#        self.app = app
#        self.daemon_context.detach_process = True
#        self.daemon_context.files_preserve = context.get_file_handlers()
#        self.daemon_context.signal_map = {
#            signal.SIGTERM: cleanup
#        }

#    def _open_streams_from_app_stream_paths(self, app):
#        self.daemon_context.stdin = open(app.stdin_path, 'rt')
#        self.daemon_context.stdout = open(app.stdout_path, 'w+t')
#        self.daemon_context.stderr = open(app.stderr_path, 'w+t')


#import signal
#from daemon import DaemonContext
#from daemon.daemon import DaemonContext
#import os
#import sys

#class Runner:
#    def __init__(self, app):
#        self.app = app
#        self.daemon_context = DaemonContext(
#            detach_process=True,
#            files_preserve=context.get_file_handlers(),
#            signal_map={signal.SIGTERM: self._cleanup},
#            stdin=open(app.stdin_path, 'rt'),
#            stdout=open(app.stdout_path, 'w+t'),
#            stderr=open(app.stderr_path, 'w+t')
#        )

#    def do_action(self):
#        action = sys.argv[1] if len(sys.argv) > 1 else 'start'
#        
#        if action == 'start':
#            self.start()
#        elif action == 'stop':
#            self.stop()
#        elif action == 'restart':
#            self.restart()
#        else:
#            print(f"Unknown action: {action}")
#            sys.exit(1)
#
#    def _cleanup(self, signum, frame):
#        self.app.stop()
#
#    def start(self):
#        with self.daemon_context:
#            self.app.run()
#
#    def stop(self):
#        # Read PID and send SIGTERM
#        with open(self.app.pidfile_path, 'r') as f:
#            pid = int(f.read().strip())
#        os.kill(pid, signal.SIGTERM)



import signal
import sys
import os
from daemon import DaemonContext

class Runner:
    def __init__(self, app):
        self.app = app
        self.daemon_context = DaemonContext(
            detach_process=True,
            signal_map={signal.SIGTERM: self._cleanup}
        )
        self._open_streams_from_app_stream_paths(app)

    def _cleanup(self, signum, frame):
        self.app.stop()

    def _open_streams_from_app_stream_paths(self, app):
        self.daemon_context.stdin = open(app.stdin_path, 'rt')
        self.daemon_context.stdout = open(app.stdout_path, 'w+t')
        self.daemon_context.stderr = open(app.stderr_path, 'w+t')

    def do_action(self):
        action = sys.argv[1] if len(sys.argv) > 1 else 'start'
        
        if action == 'start':
            self._start()
        elif action == 'stop':
            self._stop()
        elif action == 'restart':
            self._restart()
        else:
            print(f"Unknown action: {action}")
            sys.exit(1)

    def _start(self):
        if os.path.exists(self.app.pidfile_path):
            print("Daemon already running")
            return
        
        with self.daemon_context:
            with open(self.app.pidfile_path, 'w') as f:
                f.write(str(os.getpid()))
            self.app.run()

    def _stop(self):
        if not os.path.exists(self.app.pidfile_path):
            print("Daemon not running")
            return
            
        with open(self.app.pidfile_path, 'r') as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGTERM)
        os.remove(self.app.pidfile_path)

    def _restart(self):
        self._stop()
        self._start()
