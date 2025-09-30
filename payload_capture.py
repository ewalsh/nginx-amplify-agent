#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
NGINX Amplify Agent Payload Capture Script

This script captures and prints all JSON payloads that would be sent to the cloud,
allowing you to see exactly what metrics and data the agent collects.
"""
import sys
import os
import json
import time
from collections import defaultdict, deque

# Add the project path
project_path = '/home/edmund/Projects/nginx-amplify-agent'
sys.path.insert(0, project_path)

# Mock the HTTP client to capture payloads instead of sending them
class MockHTTPClient:
    def __init__(self):
        self.captured_payloads = []
        self.url = "https://mock-receiver.amplify.nginx.com:443/1.4"
        
    def post(self, endpoint, data=None, **kwargs):
        payload = {
            'timestamp': time.time(),
            'endpoint': endpoint,
            'data': data
        }
        self.captured_payloads.append(payload)
        print(f"\n{'='*60}")
        print(f"CAPTURED PAYLOAD - Endpoint: {endpoint}")
        print(f"{'='*60}")
        print(json.dumps(data, indent=2, default=str))
        print(f"{'='*60}\n")
        
        # Mock successful response
        return {
            'config': {},
            'messages': [],
            'versions': {'current': '1.7.0', 'obsolete': '1.0.0', 'old': '1.5.0'},
            'capabilities': {'phpfpm': True, 'mysql': True},
            'objects': []
        }
    
    def get(self, url, **kwargs):
        return {}
    
    def update_cloud_url(self):
        pass

# Mock configuration to avoid file dependencies
def create_mock_config():
    return {
        'credentials': {
            'api_key': 'mock_api_key_12345',
            'hostname': 'test-hostname',
            'uuid': 'mock-uuid-12345',
            'imagename': '',
            'store_uuid': False
        },
        'agent': {
            'launchers': []
        },
        'nginx': {},
        'proxies': {'https': ''},
        'cloud': {
            'api_url': 'https://mock-receiver.amplify.nginx.com:443/1.4',
            'api_timeout': 5.0,
            'talk_interval': 60,
            'push_interval': 10,
            'verify_ssl_cert': True,
            'gzip': 1
        },
        'extensions': {
            'phpfpm': True,
            'mysql': False
        },
        'mysql': {
            'unix_socket': '/var/run/mysqld/mysqld.sock',
            'user': 'amplify-agent',
            'password': 'amplify-agent',
            'remote': False
        },
        'containers': {
            'system': {
                'poll_intervals': {
                    'default': 10,
                    'meta': 60,
                    'metrics': 20
                }
            }
        },
        'daemon': {
            'pid': '/tmp/amplify-agent.pid'
        }
    }

def setup_mock_context():
    """Set up a mock context to avoid configuration file dependencies"""
    from amplify.agent.common.context import context
    from amplify.agent.common.util.configtypes import ConfigApplyMixin
    
    # Create mock config
    mock_config = create_mock_config()
    
    # Set up context attributes
    context.app_config = ConfigApplyMixin()
    context.app_config.config = mock_config
    context.app_config.default = mock_config
    
    # Add method to access config like a dict
    def config_get(key, default=None):
        keys = key.split('.')
        value = mock_config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value
    
    context.app_config.__getitem__ = lambda self, key: mock_config[key]
    context.app_config.get = lambda self, key, default=None: mock_config.get(key, default)
    
    # Set basic context attributes
    context.version = '1.7.0'
    context.version_semver = (1, 7, 0)
    context.agent_name = 'amplify'
    context.uuid = 'mock-uuid-12345'
    context.hostname = 'test-hostname'
    context.pid = os.getpid()
    context.start_time = int(time.time())
    context.backpressure_time = 0
    context.cloud_restart = False
    context.freeze_api_url = False
    context.capabilities = defaultdict(bool)
    context.capabilities.update({'phpfpm': True, 'mysql': True})
    
    # Mock HTTP client
    context.http_client = MockHTTPClient()
    
    # Mock logger
    class MockLogger:
        def debug(self, msg, **kwargs): pass
        def info(self, msg, **kwargs): print(f"INFO: {msg}")
        def warn(self, msg, **kwargs): print(f"WARN: {msg}")
        def error(self, msg, **kwargs): print(f"ERROR: {msg}")
    
    context.log = MockLogger()
    context.default_log = MockLogger()
    
    # Mock psutil process
    import psutil
    context.psutil_process = psutil.Process()
    
    return context

def collect_system_metrics():
    """Collect and display system metrics that would be sent"""
    print("\n" + "="*80)
    print("SYSTEM METRICS COLLECTION SIMULATION")
    print("="*80)
    
    try:
        from amplify.agent.collectors.system.metrics import SystemMetricsCollector
        from amplify.agent.objects.system.object import SystemObject
        
        # Create mock system object
        system_data = {
            'uuid': 'mock-uuid-12345',
            'hostname': 'test-hostname',
            'type': 'system'
        }
        
        system_obj = SystemObject(data=system_data)
        
        # Create metrics collector
        collector = SystemMetricsCollector(object=system_obj, interval=20)
        
        print("Collecting system metrics...")
        
        # Collect metrics
        collector.collect()
        
        # Get the collected metrics
        metrics_data = system_obj.flush(clients=['metrics'])
        
        if metrics_data:
            print("\nCOLLECTED SYSTEM METRICS:")
            print(json.dumps(metrics_data, indent=2, default=str))
        
    except Exception as e:
        print(f"Error collecting system metrics: {e}")
        import traceback
        traceback.print_exc()

def simulate_agent_communication():
    """Simulate the full agent communication flow"""
    print("\n" + "="*80)
    print("AGENT COMMUNICATION SIMULATION")
    print("="*80)
    
    try:
        # Set up mock environment
        context = setup_mock_context()
        
        # Import after context is set up
        from amplify.agent.common.util.system import get_root_definition
        from amplify.agent.managers.bridge import Bridge
        
        # Get root definition (what gets sent during initial handshake)
        root_def = get_root_definition()
        print("\nROOT OBJECT DEFINITION (Initial Handshake):")
        print(json.dumps(root_def, indent=2, default=str))
        
        # Simulate initial cloud communication
        print("\nSimulating initial cloud communication...")
        context.http_client.post('agent/', data=root_def)
        
        # Create and simulate bridge manager
        print("\nSimulating metrics collection and bridge communication...")
        bridge = Bridge()
        
        # Mock some objects in context
        class MockObjects:
            def tree(self):
                return {
                    'object': MockSystemObject(),
                    'children': []
                }
        
        class MockSystemObject:
            def flush(self, clients=None):
                return {
                    'object': {
                        'type': 'system',
                        'uuid': 'mock-uuid-12345',
                        'hostname': 'test-hostname'
                    },
                    'metrics': {
                        'system.cpu.user': [[time.time(), 15.2]],
                        'system.cpu.system': [[time.time(), 8.1]],
                        'system.cpu.idle': [[time.time(), 76.7]],
                        'system.mem.total': [[time.time(), 8589934592]],
                        'system.mem.used': [[time.time(), 4294967296]],
                        'system.mem.free': [[time.time(), 4294967296]],
                        'system.load.1': [[time.time(), 0.5]],
                        'system.load.5': [[time.time(), 0.3]],
                        'system.load.15': [[time.time(), 0.2]],
                        'controller.agent.cpu.user': [[time.time(), 2.1]],
                        'controller.agent.cpu.system': [[time.time(), 1.3]],
                        'controller.agent.mem.rss': [[time.time(), 52428800]],
                        'controller.agent.mem.vms': [[time.time(), 104857600]]
                    },
                    'meta': {
                        'system': {
                            'uname': 'Linux test-hostname 5.4.0 #1 SMP x86_64',
                            'hostname': 'test-hostname',
                            'uuid': 'mock-uuid-12345',
                            'boot_time': time.time() - 86400,
                            'agent_version': '1.7.0'
                        }
                    },
                    'events': [
                        {
                            'timestamp': time.time(),
                            'level': 'INFO',
                            'message': 'agent started, version: 1.7.0, pid: %d' % os.getpid()
                        }
                    ],
                    'configs': {}
                }
        
        context.objects = MockObjects()
        
        # Simulate bridge flush
        bridge.flush_all(force=True)
        
        print(f"\nCaptured {len(context.http_client.captured_payloads)} payloads total")
        
    except Exception as e:
        print(f"Error in agent simulation: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main function to run payload capture"""
    print("NGINX Amplify Agent - Payload Capture Tool")
    print("This tool shows you exactly what data the agent would send to the cloud")
    
    # Simulate the agent communication
    simulate_agent_communication()
    
    print("\n" + "="*80)
    print("PAYLOAD CAPTURE COMPLETE")
    print("="*80)
    print("\nThe above JSON payloads show:")
    print("1. Initial handshake data (agent registration)")
    print("2. System metrics (CPU, memory, disk, network)")
    print("3. Agent self-monitoring metrics")
    print("4. System metadata and events")
    print("\nYou can use this data structure to:")
    print("- Understand what metrics are collected")
    print("- Build your own monitoring endpoint")
    print("- Integrate with other monitoring systems")
    print("- Debug agent behavior")

if __name__ == '__main__':
    main()