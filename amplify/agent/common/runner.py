# -*- coding: utf-8 -*-
import signal
import logging

import daemon
from daemon.pidfile import PIDLockFile

from amplify.agent.common.context import context

__author__ = "Mike Belov"
__copyright__ = "Copyright (C) Nginx, Inc. All rights reserved."
__license__ = ""
__maintainer__ = "Andrei Belov"
__email__ = "a.belov@f5.com"


class Runner:
    def __init__(self, app):
        self.logger = logging.getLogger(__name__)
        
        def cleanup(signum, frame):
            self.logger.info(f"Received signal {signum}, stopping application")
            app.stop()

        self.daemon_context = daemon.DaemonContext()

        self.app = app
        self.daemon_context.detach_process = True
        self.daemon_context.pidfile = PIDLockFile('/var/run/amplify-agent/amplify-agent.pid')
        self.daemon_context.files_preserve = context.get_file_handlers()
        self.daemon_context.signal_map = {
            signal.SIGTERM: cleanup
        }
        self._open_streams_from_app_stream_paths(app)
        self.logger.info("Runner initialized with daemon context")

    def _open_streams_from_app_stream_paths(self, app):
        self.logger.debug(f"Opening streams - stdin: {app.stdin_path}, stdout: {app.stdout_path}, stderr: {app.stderr_path}")
        self.daemon_context.stdin = open(app.stdin_path, 'rt')
        self.daemon_context.stdout = open(app.stdout_path, 'w+t')
        self.daemon_context.stderr = open(app.stderr_path, 'w+t')
        self.logger.debug("Daemon streams configured successfully")

    def do_action(self):
        """
        Stub function to mock old DaemonRunner behavior
        """
        self.logger.info("Starting daemon context")
        try:
            with self.daemon_context:
                self.logger.info("Application starting")
                self.app.run()
        except Exception as e:
            self.logger.error(f"Error in daemon context: {e}")
            raise
        finally:
            self.logger.info("Daemon context closed")
