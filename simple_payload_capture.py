#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simplified NGINX Amplify Agent Payload Capture Script

This script shows the basic JSON structure that the agent would send to the cloud.
"""
import sys
import os
import json
import time
import socket
import platform

# Add the project path
project_path = '/home/edmund/Projects/nginx-amplify-agent'
sys.path.insert(0, project_path)

def get_system_info():
    """Collect basic system information"""
    return {
        'hostname': socket.gethostname(),
        'platform': platform.platform(),
        'architecture': platform.architecture(),
        'processor': platform.processor(),
        'python_version': platform.python_version(),
        'uname': ' '.join(platform.uname())
    }

def create_root_definition():
    """Create the root object definition (initial handshake)"""
    return {
        'type': 'system',
        'uuid': 'mock-uuid-' + str(int(time.time())),
        'hostname': socket.gethostname()
    }

def create_system_metrics():
    """Create mock system metrics payload"""
    timestamp = time.time()
    
    # Try to get real system metrics if psutil is available
    try:
        import psutil
        
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1, percpu=False)
        cpu_times = psutil.cpu_times_percent()
        
        # Memory metrics
        memory = psutil.virtual_memory()
        swap = psutil.swap_memory()
        
        # Load average (Unix only)
        try:
            load_avg = os.getloadavg()
        except:
            load_avg = [0.0, 0.0, 0.0]
        
        # Disk usage
        disk_usage = psutil.disk_usage('/')
        
        # Network stats
        net_io = psutil.net_io_counters()
        
        metrics = {
            # CPU metrics
            'system.cpu.user': [[timestamp, cpu_times.user + cpu_times.nice]],
            'system.cpu.system': [[timestamp, cpu_times.system + cpu_times.irq]],
            'system.cpu.idle': [[timestamp, cpu_times.idle]],
            
            # Memory metrics
            'system.mem.total': [[timestamp, memory.total]],
            'system.mem.used': [[timestamp, memory.used]],
            'system.mem.free': [[timestamp, memory.free]],
            'system.mem.cached': [[timestamp, memory.cached]],
            'system.mem.buffered': [[timestamp, memory.buffers]],
            'system.mem.pct_used': [[timestamp, memory.percent]],
            'system.mem.available': [[timestamp, memory.available]],
            
            # Swap metrics
            'system.swap.total': [[timestamp, swap.total]],
            'system.swap.used': [[timestamp, swap.used]],
            'system.swap.free': [[timestamp, swap.free]],
            'system.swap.pct_free': [[timestamp, swap.percent]],
            
            # Load average
            'system.load.1': [[timestamp, load_avg[0]]],
            'system.load.5': [[timestamp, load_avg[1]]],
            'system.load.15': [[timestamp, load_avg[2]]],
            
            # Disk metrics
            'system.disk.total': [[timestamp, disk_usage.total]],
            'system.disk.used': [[timestamp, disk_usage.used]],
            'system.disk.free': [[timestamp, disk_usage.free]],
            'system.disk.in_use': [[timestamp, (disk_usage.used / disk_usage.total) * 100]],
            
            # Network metrics
            'system.net.bytes_sent': [[timestamp, net_io.bytes_sent]],
            'system.net.bytes_rcvd': [[timestamp, net_io.bytes_recv]],
            'system.net.packets_out.count': [[timestamp, net_io.packets_sent]],
            'system.net.packets_in.count': [[timestamp, net_io.packets_recv]],
            
            # Agent self-monitoring
            'controller.agent.cpu.user': [[timestamp, 2.1]],
            'controller.agent.cpu.system': [[timestamp, 1.3]],
            'controller.agent.mem.rss': [[timestamp, 52428800]],
            'controller.agent.mem.vms': [[timestamp, 104857600]]
        }
        
    except ImportError:
        # Fallback to mock data if psutil not available
        metrics = {
            'system.cpu.user': [[timestamp, 15.2]],
            'system.cpu.system': [[timestamp, 8.1]],
            'system.cpu.idle': [[timestamp, 76.7]],
            'system.mem.total': [[timestamp, 8589934592]],
            'system.mem.used': [[timestamp, 4294967296]],
            'system.mem.free': [[timestamp, 4294967296]],
            'system.load.1': [[timestamp, 0.5]],
            'system.load.5': [[timestamp, 0.3]],
            'system.load.15': [[timestamp, 0.2]],
            'controller.agent.cpu.user': [[timestamp, 2.1]],
            'controller.agent.cpu.system': [[timestamp, 1.3]],
            'controller.agent.mem.rss': [[timestamp, 52428800]],
            'controller.agent.mem.vms': [[timestamp, 104857600]]
        }
    
    return metrics

def create_system_meta():
    """Create system metadata payload"""
    system_info = get_system_info()
    
    return {
        'system': {
            'uname': system_info['uname'],
            'hostname': system_info['hostname'],
            'uuid': 'mock-uuid-' + str(int(time.time())),
            'boot_time': time.time() - 86400,  # Mock boot time (1 day ago)
            'agent_version': '1.7.0',
            'platform': system_info['platform'],
            'architecture': system_info['architecture'],
            'processor': system_info['processor'],
            'python_version': system_info['python_version']
        }
    }

def create_events():
    """Create events payload"""
    return [
        {
            'timestamp': time.time(),
            'level': 'INFO',
            'message': 'agent started, version: 1.7.0, pid: %d' % os.getpid()
        }
    ]

def create_full_payload():
    """Create the complete payload structure"""
    root_def = create_root_definition()
    
    payload = {
        'object': root_def,
        'metrics': create_system_metrics(),
        'meta': create_system_meta(),
        'events': create_events(),
        'configs': {}
    }
    
    return payload

def simulate_nginx_metrics():
    """Simulate NGINX metrics if nginx is running"""
    nginx_metrics = {
        'nginx.http.request.count': [[time.time(), 1250]],
        'nginx.http.request.current': [[time.time(), 12]],
        'nginx.http.request.reading': [[time.time(), 2]],
        'nginx.http.request.writing': [[time.time(), 8]],
        'nginx.http.request.waiting': [[time.time(), 2]],
        'nginx.http.conn.accepted': [[time.time(), 1200]],
        'nginx.http.conn.handled': [[time.time(), 1200]],
        'nginx.http.conn.dropped': [[time.time(), 0]],
        'nginx.http.conn.current': [[time.time(), 12]]
    }
    return nginx_metrics

def main():
    """Main function to demonstrate payload structure"""
    print("NGINX Amplify Agent - Payload Structure Demo")
    print("=" * 60)
    
    # 1. Initial handshake payload
    print("\n1. INITIAL HANDSHAKE (agent registration)")
    print("-" * 40)
    root_definition = create_root_definition()
    print(json.dumps(root_definition, indent=2))
    
    # 2. Full metrics payload
    print("\n2. METRICS UPDATE PAYLOAD")
    print("-" * 40)
    full_payload = create_full_payload()
    print(json.dumps(full_payload, indent=2, default=str))
    
    # 3. NGINX-specific metrics (if applicable)
    print("\n3. NGINX METRICS (example)")
    print("-" * 40)
    nginx_metrics = simulate_nginx_metrics()
    nginx_payload = {
        'object': {
            'type': 'nginx',
            'local_id': 'nginx001',
            'root_uuid': root_definition['uuid']
        },
        'metrics': nginx_metrics
    }
    print(json.dumps(nginx_payload, indent=2, default=str))
    
    # 4. Explain the structure
    print("\n" + "=" * 60)
    print("PAYLOAD STRUCTURE EXPLANATION")
    print("=" * 60)
    print("""
The NGINX Amplify Agent sends these types of data:

1. INITIAL HANDSHAKE:
   - Agent registration with system/container info
   - Sent to: POST /agent/

2. METRICS UPDATES:
   - System metrics (CPU, memory, disk, network)
   - NGINX metrics (requests, connections, status)
   - Agent self-monitoring metrics
   - Sent to: POST /update/

3. DATA STRUCTURE:
   - object: Identifies the monitored entity
   - metrics: Time-series data [[timestamp, value], ...]
   - meta: Static metadata about the system
   - events: Log events and alerts
   - configs: Configuration snapshots

4. METRIC NAMING CONVENTION:
   - system.*: Host system metrics
   - nginx.*: NGINX server metrics  
   - controller.agent.*: Agent self-monitoring
   
5. ENDPOINTS:
   - /agent/: Initial registration and config updates
   - /update/: Regular metrics and data updates
""")

if __name__ == '__main__':
    main()