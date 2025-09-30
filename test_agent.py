#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os

# Add the project path
project_path = '/home/edmund/Projects/nginx-amplify-agent'
sys.path.insert(0, project_path)

# Set up configuration file path
config_file = os.path.join(project_path, 'etc', 'agent.conf')

# Mock command line arguments for testing
sys.argv = ['test_agent.py', 'configtest', '--config', config_file]

# Import and run
from amplify.agent import main
main.run('amplify')