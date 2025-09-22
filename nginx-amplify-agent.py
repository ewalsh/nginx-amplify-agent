#!/usr/bin/python3
# -*- coding: utf-8 -*-
import sys
import subprocess

def install_if_missing(module):
    try:
        __import__(module)
    # except ImportError:
    #     subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--system', module])
    except ImportError:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', module])

# Auto-install required modules
install_if_missing('gevent')
install_if_missing('amplify')

__author__ = "Mike Belov"
__copyright__ = "Copyright (C) Nginx, Inc. All rights reserved."
__license__ = ""
__maintainer__ = "Andrei Belov"
__email__ = "defan@nginx.com"
__credits__ = []  # check amplify/agent/main.py for the actual credits list


# import amplify python package and add it's path to sys path
# (this needs to be done in order to load all requirements from amplify python package)
import amplify
amplify_path = '/'.join(amplify.__file__.split('/')[:-1])
sys.path.insert(0, amplify_path)

# import gevent and make appropriate patches
from gevent import monkey
monkey.patch_all()

# run the main script
from amplify.agent import main
main.run('amplify')
