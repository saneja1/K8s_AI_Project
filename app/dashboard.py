import streamlit as st
import os
import subprocess
import json
import pandas as pd
from dotenv import load_dotenv
import time
from datetime import datetime
import re
import pickle
from pathlib import Path

# Load environment variables
load_dotenv()

# Import Google Gemini AI
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

# Add the parent directory to the path to import from core
import sys
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
from core.system import check_requirements, check_requirements_cloud
from utils.gen_api import generate_content

# Log file path
LOG_FILE = Path(__file__).parent.parent / '.logs' / 'command_logs.pkl'
LOG_FILE.parent.mkdir(exist_ok=True)

# Constants
MIB_PER_GIB = 1024


def parse_int(value):
    """Safely parse integers from string values."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return None


def parse_float(value):
    """Safely parse floats from string values."""
    try:
        return float(str(value).strip())
    except (TypeError, ValueError, AttributeError):
        return None


def format_gib(value_mib):
    """Convert MiB value to GiB string with one decimal place."""
    if value_mib is None:
        return 'N/A'
    gib = value_mib / MIB_PER_GIB
    if abs(gib) < 0.05:
        gib = 0.0
    return f"{gib:.1f}"


def format_percent(value):
    """Format a float percentage with one decimal place."""
    if value is None:
        return 'N/A'
    clamped = max(0.0, min(100.0, value))
    if clamped < 0.05:
        clamped = 0.0
    return f"{clamped:.1f}%"

def load_logs_from_file():
    """Load logs from persistent file."""
    if LOG_FILE.exists():
        try:
            with open(LOG_FILE, 'rb') as f:
                data = pickle.load(f)
                return data.get('logs', []), data.get('started', datetime.now())
        except:
            return [], datetime.now()
    return [], datetime.now()

def save_logs_to_file(logs, started_time):
    """Save logs to persistent file."""
    try:
        with open(LOG_FILE, 'wb') as f:
            pickle.dump({'logs': logs, 'started': started_time}, f)
    except Exception as e:
        print(f"Error saving logs: {e}")

# Initialize session state for logs and startup time
if 'command_logs' not in st.session_state:
    # Load from file if exists, otherwise start fresh
    logs, started = load_logs_from_file()
    st.session_state.command_logs = logs
    st.session_state.dashboard_started = started
    
    # If this is a fresh start (no logs), record it
    if not logs:
        st.session_state.dashboard_started = datetime.now()
        save_logs_to_file([], st.session_state.dashboard_started)

# Initialize session state for data freshness tracking
if 'vm_data_timestamp' not in st.session_state:
    st.session_state.vm_data_timestamp = None
if 'vm_data_status' not in st.session_state:
    st.session_state.vm_data_status = 'unknown'
if 'pod_data_timestamp' not in st.session_state:
    st.session_state.pod_data_timestamp = None
if 'pod_data_status' not in st.session_state:
    st.session_state.pod_data_status = 'unknown'

# Initialize manual refresh state
if 'manual_refresh' not in st.session_state:
    st.session_state.manual_refresh = True
if 'last_data_refresh_time' not in st.session_state:
    st.session_state.last_data_refresh_time = 0.0
if 'vm_table_cache' not in st.session_state:
    st.session_state.vm_table_cache = []
if 'vm_fetch_success' not in st.session_state:
    st.session_state.vm_fetch_success = False
if 'pods_cache' not in st.session_state:
    st.session_state.pods_cache = []
if 'pods_fetch_success' not in st.session_state:
    st.session_state.pods_fetch_success = False

def log_command(command, status="Running", details=""):
    """Log a command execution with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        'timestamp': timestamp,
        'command': command,
        'status': status,
        'details': details
    }
    st.session_state.command_logs.append(log_entry)
    
    # Keep only last 50 logs
    if len(st.session_state.command_logs) > 50:
        st.session_state.command_logs = st.session_state.command_logs[-50:]
    
    # Save to file after each log
    save_logs_to_file(st.session_state.command_logs, st.session_state.dashboard_started)

def display_command_logs(tab_name=""):
    """Display command execution logs."""
    if st.session_state.command_logs:
        st.markdown("### 📋 Command Execution Logs")
        
        # Show dashboard info
        uptime = datetime.now() - st.session_state.dashboard_started
        st.info(f"🚀 Dashboard started: {st.session_state.dashboard_started.strftime('%Y-%m-%d %H:%M:%S')} (Uptime: {str(uptime).split('.')[0]}) | Total logs: {len(st.session_state.command_logs)}/50")
        
        # Add clear logs button with unique key per tab
        if st.button("🗑️ Clear All Logs", key=f"clear_logs_{tab_name}"):
            st.session_state.command_logs = []
            st.session_state.dashboard_started = datetime.now()
            save_logs_to_file([], st.session_state.dashboard_started)
            st.rerun()
        
        # Create logs dataframe
        logs_df = pd.DataFrame(st.session_state.command_logs)
        # Reverse to show newest first
        logs_df = logs_df.iloc[::-1].reset_index(drop=True)
        
        # Color code status
        def color_status(row):
            if row['status'] == '✅ Success':
                return ['background-color: #1e4620'] * len(row)
            elif row['status'] == '❌ Failed':
                return ['background-color: #4a1a1a'] * len(row)
            else:
                return ['background-color: #1a3a4a'] * len(row)
        
        styled_logs = logs_df.style.apply(color_status, axis=1)
        st.dataframe(styled_logs, use_container_width=True, height=300)
    else:
        st.info("No commands executed yet")

def is_data_fresh(timestamp, max_age_seconds=30):
    """Check if data is fresh (within max_age_seconds)."""
    if timestamp is None:
        return False
    age = (datetime.now() - timestamp).total_seconds()
    return age <= max_age_seconds

def format_time_ago(timestamp):
    """Format datetime as 'X seconds/minutes ago'."""
    if timestamp is None:
        return 'Never'
    elapsed = (datetime.now() - timestamp).total_seconds()
    if elapsed < 60:
        return f"{int(elapsed)}s ago"
    elif elapsed < 3600:
        return f"{int(elapsed / 60)}m ago"
    else:
        return f"{int(elapsed / 3600)}h ago"

def get_live_indicator_html(data_type='vm'):
    """Generate HTML for live status indicator based on data freshness."""
    if data_type == 'vm':
        timestamp = st.session_state.vm_data_timestamp
        status = st.session_state.vm_data_status
    else:  # pod
        timestamp = st.session_state.pod_data_timestamp
        status = st.session_state.pod_data_status
    
    is_fresh = is_data_fresh(timestamp)
    
    if status == 'success' and is_fresh:
        # Green pulsing dot - data is fresh
        indicator_class = 'live-indicator'
        status_text = 'LIVE'
        age = int((datetime.now() - timestamp).total_seconds()) if timestamp else 0
        tooltip = f'Data updated {age}s ago'
    elif status == 'success' and not is_fresh:
        # Yellow static dot - data is stale
        indicator_class = 'stale-indicator'
        status_text = 'STALE'
        age = int((datetime.now() - timestamp).total_seconds()) if timestamp else 0
        tooltip = f'Data is {age}s old (stale)'
    else:
        # Red static dot - error or no data
        indicator_class = 'error-indicator'
        status_text = 'ERROR'
        tooltip = 'Failed to fetch data'
    
    return f'''<span class="{indicator_class}" title="{tooltip}"></span>
               <span style="font-size: 0.7rem; color: #888; margin-right: 10px;">{status_text}</span>'''

# Configuration from environment variables
DEFAULT_SSH_PORT = int(os.getenv('SSH_PORT', 22))
DEFAULT_SSH_USERNAME = os.getenv('SSH_USERNAME', '')
MIN_CPU_CORES = int(os.getenv('MIN_CPU_CORES', 2))
MIN_MEMORY_MIB = int(os.getenv('MIN_MEMORY_MIB', 4096))
MIN_DISK_GIB = int(os.getenv('MIN_DISK_GIB', 30))

# VM Type configurations
VM_TYPES = {
    "Google Cloud (GCE)": {
        "auth_methods": ["GCloud CLI", "SSH Key", "Password"],
        "zones": ["us-central1-a", "us-central1-b", "us-central1-c", "us-east1-a", "us-west1-a"],
        "default_username": "swinvm15"
    },
    "AWS EC2": {
        "auth_methods": ["AWS CLI", "SSH Key", "Password"],
        "regions": ["us-east-1", "us-west-2", "eu-west-1"],
        "default_username": "ec2-user"
    },
    "Azure VM": {
        "auth_methods": ["Azure CLI", "SSH Key", "Password"],
        "regions": ["eastus", "westus2", "westeurope"],
        "default_username": "azureuser"
    },
    "Direct SSH": {
        "auth_methods": ["SSH Key", "Password"],
        "default_username": "root"
    }
}

def get_cluster_info():
    """Get basic cluster information and node status."""
    try:
        # Get nodes using kubectl directly (via SSH tunnel)
        result = subprocess.run([
            "kubectl", "get", "nodes", "-o", "json"
        ], capture_output=True, text=True, timeout=30)
        
        nodes_data = []
        if result.returncode == 0:
            nodes_json = json.loads(result.stdout)
            for node in nodes_json.get('items', []):
                node_info = {
                    'name': node['metadata']['name'],
                    'status': 'Unknown',
                    'roles': [],
                    'age': 'Unknown',
                    'version': node['status'].get('nodeInfo', {}).get('kubeletVersion', 'Unknown'),
                    'internal_ip': 'Unknown',
                    'external_ip': 'Unknown'
                }
                
                # Get node status
                for condition in node['status'].get('conditions', []):
                    if condition['type'] == 'Ready':
                        node_info['status'] = 'Ready' if condition['status'] == 'True' else 'NotReady'
                        break
                
                # Get node roles
                labels = node['metadata'].get('labels', {})
                if 'node-role.kubernetes.io/control-plane' in labels:
                    node_info['roles'].append('control-plane')
                if 'node-role.kubernetes.io/master' in labels:
                    node_info['roles'].append('master')
                if not node_info['roles']:
                    node_info['roles'] = ['worker']
                
                # Get IP addresses
                for address in node['status'].get('addresses', []):
                    if address['type'] == 'InternalIP':
                        node_info['internal_ip'] = address['address']
                    elif address['type'] == 'ExternalIP':
                        node_info['external_ip'] = address['address']
                
                nodes_data.append(node_info)
        
        return nodes_data
    except Exception as e:
        return []

def get_pods_info():
    """Get information about all pods in the cluster."""
    try:
        # Log command execution
        log_command("kubectl get pods --all-namespaces -o json", "Running", "Fetching pod data from cluster")
        
        # Get pods using kubectl directly (via SSH tunnel)
        result = subprocess.run([
            "kubectl", "get", "pods", "--all-namespaces", "-o", "json"
        ], capture_output=True, text=True, timeout=15)
        
        pods_data = []
        if result.returncode == 0:
            pods_json = json.loads(result.stdout)
            pod_count = len(pods_json.get('items', []))
            log_command("kubectl get pods --all-namespaces", "✅ Success", f"Found {pod_count} pods")
            
            # Update timestamp and status for successful fetch
            fetch_time = datetime.now()
            st.session_state.pod_data_timestamp = fetch_time
            st.session_state.pod_data_status = 'success'
            
            for pod in pods_json.get('items', []):
                pod_info = {
                    'name': pod['metadata']['name'],
                    'namespace': pod['metadata']['namespace'],
                    'status': pod['status'].get('phase', 'Unknown'),
                    'node': pod['spec'].get('nodeName', 'Unknown'),
                    'ready': '0/0',
                    'restarts': 0,
                    'fetch_timestamp': fetch_time
                }
                
                # Calculate ready containers
                container_statuses = pod['status'].get('containerStatuses', [])
                ready_containers = sum(1 for c in container_statuses if c.get('ready', False))
                total_containers = len(container_statuses)
                pod_info['ready'] = f"{ready_containers}/{total_containers}"
                
                # Count restarts
                pod_info['restarts'] = sum(c.get('restartCount', 0) for c in container_statuses)
                
                pods_data.append(pod_info)
        else:
            log_command("kubectl get pods", "❌ Failed", f"Error: {result.stderr[:100]}")
            st.session_state.pod_data_status = 'error'
        
        return pods_data
    except Exception as e:
        log_command("kubectl get pods", "❌ Failed", f"Exception: {str(e)}")
        st.session_state.pod_data_status = 'error'
        return []

def get_vm_resources(vm_name, zone="us-central1-a"):
    """Get detailed system resources from a VM using SSH - OPTIMIZED single SSH call."""
    try:
        log_command(f"gcloud compute ssh {vm_name}", "Running", f"Fetching metrics from {vm_name}")
        
        # Simple, working command - tested manually
        combined_command = (
            "CPU_COUNT=$(nproc); "
            "read MEM_TOTAL MEM_USED MEM_FREE MEM_AVAIL <<< $(free -m | awk 'NR==2 {print $2, $3, $4, $7}'); "
            "read DISK_TOTAL DISK_USED DISK_AVAIL <<< $(df -BM / | tail -1 | awk '{print int($2), int($3), int($4)}'); "
            "CPU_IDLE=$(top -bn1 | awk '/Cpu\\(s\\)/ {print $8}' | sed 's/[^0-9.]//g'); "
            "echo CPU_COUNT:${CPU_COUNT}; "
            "echo MEM_TOTAL_MIB:${MEM_TOTAL}; "
            "echo MEM_USED_MIB:${MEM_USED}; "
            "echo MEM_FREE_MIB:${MEM_FREE}; "
            "echo MEM_AVAIL_MIB:${MEM_AVAIL}; "
            "echo DISK_TOTAL_MIB:${DISK_TOTAL}; "
            "echo DISK_USED_MIB:${DISK_USED}; "
            "echo DISK_AVAIL_MIB:${DISK_AVAIL}; "
            "echo CPU_IDLE_PERCENT:${CPU_IDLE}"
        )
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", vm_name,
            "--command", combined_command,
            "--zone", zone,
            "--quiet"
        ], capture_output=True, text=True, timeout=15)
        
        vm_resources = {'vm_name': vm_name, 'zone': zone}
        
        if result.returncode == 0:
            # Parse the output
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    vm_resources[key] = value
            
            log_command(f"gcloud compute ssh {vm_name}", "✅ Success", f"Retrieved all metrics from {vm_name}")
            return vm_resources
        else:
            error_msg = result.stderr[:200] if result.stderr else "Unknown error"
            log_command(f"gcloud compute ssh {vm_name}", "❌ Failed", f"Error: {error_msg}")
            return {'vm_name': vm_name, 'zone': zone, 'error': error_msg}
            
    except subprocess.TimeoutExpired:
        log_command(f"gcloud compute ssh {vm_name}", "❌ Failed", "Timeout after 15 seconds")
        return {'vm_name': vm_name, 'zone': zone, 'error': 'Timeout after 15 seconds'}
    except Exception as e:
        log_command(f"gcloud compute ssh {vm_name}", "❌ Failed", f"Exception: {str(e)}")
        return {'vm_name': vm_name, 'zone': zone, 'error': str(e)}

def build_cluster_context():
    """Build a comprehensive context string about the current cluster state for the AI."""
    context_parts = []
    
    # Header
    context_parts.append("=== KUBERNETES CLUSTER CONTEXT ===\n")
    
    # Monitoring duration
    if 'dashboard_started' in st.session_state:
        duration = datetime.now() - st.session_state.dashboard_started
        hours = int(duration.total_seconds() // 3600)
        minutes = int((duration.total_seconds() % 3600) // 60)
        context_parts.append(f"Dashboard Monitoring: {hours}h {minutes}m\n")
    
    # VM Status
    vm_data = st.session_state.get('vm_table_cache', [])
    if vm_data:
        context_parts.append(f"\n=== VIRTUAL MACHINES ({len(vm_data)} VMs) ===")
        for i, vm in enumerate(vm_data, 1):
            context_parts.append(f"\n{i}. {vm.get('VM Name', 'Unknown')} ({vm.get('Zone', 'N/A')})")
            context_parts.append(f"   Role: {vm.get('Role', 'N/A')}")
            context_parts.append(f"   K8s Status: {vm.get('K8s Status', 'N/A')}")
            context_parts.append(f"   IPs: Internal={vm.get('Internal IP', 'N/A')}, External={vm.get('External IP', 'N/A')}")
            context_parts.append(f"   CPU: {vm.get('CPU Cores', 'N/A')} cores ({vm.get('CPU %', 'N/A')})")
            context_parts.append(f"   Memory: {vm.get('Memory Total', 'N/A')} total, {vm.get('Memory Used', 'N/A')} used ({vm.get('Memory %', 'N/A')})")
            context_parts.append(f"   Disk: {vm.get('Disk Total', 'N/A')} total, {vm.get('Disk Used', 'N/A')} used ({vm.get('Disk %', 'N/A')})")
    else:
        context_parts.append("\n=== VIRTUAL MACHINES ===")
        context_parts.append("No VM data available yet. User needs to visit 'VM Status' tab or click Refresh.")
    
    # Pod Status
    pod_data = st.session_state.get('pods_cache', [])
    if pod_data:
        running = sum(1 for p in pod_data if p.get('status') == 'Running')
        pending = sum(1 for p in pod_data if p.get('status') == 'Pending')
        failed = sum(1 for p in pod_data if p.get('status') == 'Failed')
        
        context_parts.append(f"\n\n=== PODS ({len(pod_data)} total) ===")
        context_parts.append(f"Status Summary: {running} Running, {pending} Pending, {failed} Failed")
        
        # Show first 10 pods with details
        context_parts.append("\nPod Details:")
        for i, pod in enumerate(pod_data[:10], 1):
            context_parts.append(f"\n{i}. {pod.get('name', 'Unknown')}")
            context_parts.append(f"   Namespace: {pod.get('namespace', 'N/A')}")
            context_parts.append(f"   Status: {pod.get('status', 'N/A')}")
            context_parts.append(f"   Node: {pod.get('node', 'N/A')}")
            context_parts.append(f"   Age: {pod.get('age', 'N/A')}")
            if pod.get('cpu_request') or pod.get('memory_request'):
                context_parts.append(f"   Resources: CPU={pod.get('cpu_request', 'N/A')}, Memory={pod.get('memory_request', 'N/A')}")
        
        if len(pod_data) > 10:
            context_parts.append(f"\n... and {len(pod_data) - 10} more pods")
    else:
        context_parts.append("\n\n=== PODS ===")
        context_parts.append("No pod data available yet. User needs to visit 'Pod Monitor' tab or click Refresh.")
    
    # Recent command logs
    logs = st.session_state.get('command_logs', [])
    if logs:
        recent_logs = logs[-5:]  # Last 5 commands
        context_parts.append("\n\n=== RECENT COMMANDS ===")
        for i, log in enumerate(recent_logs, 1):
            timestamp = log.get('timestamp', 'N/A')
            command = log.get('command', 'N/A')
            status = log.get('status', 'N/A')
            context_parts.append(f"{i}. [{timestamp}] {command} - {status}")
    
    return '\n'.join(context_parts)

def main():
    st.set_page_config(
        page_title="AI Powered K8s Virtual Assistant",
        page_icon="🤖",
        layout="wide"
    )

    current_time = time.time()
    last_refresh = st.session_state.last_data_refresh_time or 0.0
    should_refresh = False
    
    if st.session_state.manual_refresh or last_refresh == 0.0:
        should_refresh = True
    
    # Define cluster VM configuration
    vm_list = [
        {"name": "k8s-master-001", "zone": "us-central1-a", "role": "Master", "internal_ip": "10.128.0.6", "external_ip": "34.69.84.204"},
        {"name": "k8s-worker-01", "zone": "us-central1-a", "role": "Worker", "internal_ip": "10.128.0.7", "external_ip": "34.133.61.216"}
    ]
    
    if should_refresh:
        refresh_timestamp = datetime.now()
        vm_table_data = []
        all_vm_fetch_success = True
        
        for vm_config in vm_list:
            vm_resources = get_vm_resources(vm_config['name'], vm_config['zone'])
            row_base = {
                'VM Name': vm_config['name'],
                'Zone': vm_config['zone'],
                'K8s Status': "✓ VM Running",
                'Role': vm_config['role'],
                'Internal IP': vm_config['internal_ip'],
                'External IP': vm_config['external_ip'],
                'data_timestamp': refresh_timestamp
            }

            if 'error' not in vm_resources:
                cpu_count_val = parse_int(vm_resources.get('CPU_COUNT'))
                cpu_idle_percent = parse_float(vm_resources.get('CPU_IDLE_PERCENT'))
                cpu_usage_val = None
                if cpu_idle_percent is not None:
                    cpu_usage_val = 100.0 - cpu_idle_percent

                mem_total_mib = parse_int(vm_resources.get('MEM_TOTAL_MIB'))
                mem_used_mib = parse_int(vm_resources.get('MEM_USED_MIB'))
                mem_free_mib = parse_int(vm_resources.get('MEM_FREE_MIB'))
                mem_avail_mib = parse_int(vm_resources.get('MEM_AVAIL_MIB'))

                disk_total_mib = parse_int(vm_resources.get('DISK_TOTAL_MIB'))
                disk_used_mib = parse_int(vm_resources.get('DISK_USED_MIB'))
                disk_avail_mib = parse_int(vm_resources.get('DISK_AVAIL_MIB'))

                mem_percent = None
                if mem_total_mib is not None and mem_used_mib is not None:
                    if mem_total_mib > 0:
                        mem_percent = (mem_used_mib / mem_total_mib) * 100
                    else:
                        mem_percent = 0.0

                disk_percent = None
                if disk_total_mib is not None and disk_used_mib is not None:
                    if disk_total_mib > 0:
                        disk_percent = (disk_used_mib / disk_total_mib) * 100
                    else:
                        disk_percent = 0.0

                row = {
                    **row_base,
                    'CPU Cores': cpu_count_val if cpu_count_val is not None else 'N/A',
                    'CPU Usage %': format_percent(cpu_usage_val),
                    'Memory Total (GiB)': format_gib(mem_total_mib),
                    'Memory Used (GiB)': format_gib(mem_used_mib),
                    'Memory Used %': format_percent(mem_percent),
                    'Memory Free (GiB)': format_gib(mem_free_mib),
                    'Memory Available (GiB)': format_gib(mem_avail_mib),
                    'Disk Total (GiB)': format_gib(disk_total_mib),
                    'Disk Used (GiB)': format_gib(disk_used_mib),
                    'Disk Used %': format_percent(disk_percent),
                    'Disk Available (GiB)': format_gib(disk_avail_mib)
                }
            else:
                all_vm_fetch_success = False
                row = {
                    **row_base,
                    'K8s Status': '⚠️ Data Fetch Error',
                    'CPU Cores': '❌ Error',
                    'CPU Usage %': '❌ Error',
                    'Memory Total (GiB)': '❌ Error',
                    'Memory Used (GiB)': '❌ Error',
                    'Memory Used %': '❌ Error',
                    'Memory Free (GiB)': '❌ Error',
                    'Memory Available (GiB)': '❌ Error',
                    'Disk Total (GiB)': '❌ Error',
                    'Disk Used (GiB)': '❌ Error',
                    'Disk Used %': '❌ Error',
                    'Disk Available (GiB)': '❌ Error'
                }

            vm_table_data.append(row)

        st.session_state.vm_table_cache = vm_table_data
        st.session_state.vm_fetch_success = all_vm_fetch_success
        if all_vm_fetch_success:
            st.session_state.vm_data_timestamp = refresh_timestamp
            st.session_state.vm_data_status = 'success'
        else:
            st.session_state.vm_data_status = 'error'

        pods_data = get_pods_info()
        st.session_state.pods_cache = pods_data
        st.session_state.pods_fetch_success = st.session_state.pod_data_status == 'success'

        st.session_state.last_data_refresh_time = time.time()
        current_time = st.session_state.last_data_refresh_time
        st.session_state.manual_refresh = False
    else:
        vm_table_data = st.session_state.vm_table_cache
        all_vm_fetch_success = st.session_state.vm_fetch_success
        pods_data = st.session_state.pods_cache
    
    # Set theme to dark mode to match the image
    st.markdown("""
        <style>
            .stApp {
                background-color: #0e1117;
                color: white;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # Custom CSS for better appearance
    st.markdown("""
    <style>
    /* Reduce overall page padding */
    .block-container {
        padding-top: 0.5rem !important;
        padding-bottom: 0rem !important;
        scroll-behavior: auto !important;
    }
    
    /* Prevent automatic scrolling on rerun */
    .main .block-container {
        overflow: visible !important;
        position: relative !important;
    }
    
    .main-header {
        font-size: 2.5rem;
        color: #0066cc;
        margin-bottom: 10px;
        margin-top: 0px;
        padding-top: 5px;
        padding-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 15px;
        position: -webkit-sticky;
        position: sticky;
        top: 0;
        background-color: #0e1117;
        z-index: 999;
    }
    
    /* Make the emoji larger */
    .main-header::first-letter {
        font-size: 3.5rem;
    }
    
    /* Style navigation radio buttons */
    div[role="radiogroup"] {
        gap: 15px !important;
        margin-top: 10px !important;
        margin-bottom: 5px !important;
    }
    
    div[role="radiogroup"] label {
        font-size: 0.95rem !important;
        padding: 10px 20px !important;
        background-color: #2d3748 !important;
        color: #e2e8f0 !important;
        border-radius: 8px !important;
        cursor: pointer !important;
        border: 1px solid #4a5568 !important;
        transition: all 0.2s ease !important;
    }
    
    div[role="radiogroup"] label:hover {
        background-color: #3d4758 !important;
        border-color: #0066cc !important;
    }
    
    div[role="radiogroup"] label[data-checked="true"] {
        background-color: #0066cc !important;
        color: white !important;
        border-color: #0066cc !important;
        font-weight: 600 !important;
    }
    
    /* Align buttons with navigation tabs */
    button[kind="primary"], button[kind="secondary"] {
        margin-top: 10px !important;
        padding: 10px 20px !important;
        border-radius: 8px !important;
    }
    
    /* Hide radio button circles */
    div[role="radiogroup"] label div[data-testid="stMarkdownContainer"] {
        color: inherit !important;
    }
    
    div[role="radiogroup"] input[type="radio"] {
        display: none !important;
    }
    
    /* Remove extra spacing after button container */
    .element-container:has(button) + div[data-testid="stVerticalBlock"] {
        margin-top: 0px !important;
        padding-top: 0px !important;
    }
    
    .section-header {
        font-size: 1.8rem;
        color: #2e7d32;
        padding-top: 0px;
        margin-top: 0px;
        margin-bottom: 10px;
    }
    .subsection-header {
        font-size: 1.3rem;
        color: #0066cc;
        padding-top: 5px;
    }
    .dashboard-metrics {
        background-color: #f5f5f5;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.1);
    }
    /* Dark theme for the table header background */
    [data-testid="stDataFrame"] thead {
        background-color: #1e1e1e !important;
    }
    
    /* Style ALL table headers - make them look like the image */
    [data-testid="stDataFrame"] th {
        background-color: #1e1e1e !important; /* Dark background like the image */
        color: white !important;
        text-align: center !important;
        font-weight: bold !important;
        vertical-align: middle !important;
        padding: 10px 5px !important;
        border: none !important;
        border-right: 1px solid #333333 !important;
    }
    
    /* Force ALL header text to be horizontally centered */
    [data-testid="stDataFrame"] th div,
    [data-testid="stDataFrame"] th span,
    [data-testid="stDataFrame"] th p,
    [data-testid="stDataFrame"] th * {
        text-align: center !important;
        justify-content: center !important;
        margin: 0 auto !important;
        width: 100% !important;
    }
    
    /* Target the main group headers (CPU, MEMORY, DISK) - fix vertical centering */
    [data-testid="stDataFrame"] thead tr:first-child th {
        background-color: #1e1e1e !important;
        color: #3498db !important;
        text-align: center !important;
        font-weight: bold !important;
        font-size: 1.1rem !important;
        padding: 0 !important;
        height: 50px !important;
        vertical-align: middle !important;
        position: relative !important;
    }
    
    /* Force the group header content to be absolutely centered */
    [data-testid="stDataFrame"] thead tr:first-child th > div {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        height: 100% !important;
        width: 100% !important;
        position: absolute !important;
        top: 0 !important;
        left: 0 !important;
        right: 0 !important;
        bottom: 0 !important;
    }
    
    /* Additional targeting for nested divs in group headers */
    [data-testid="stDataFrame"] thead tr:first-child th div div {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        height: 100% !important;
        width: 100% !important;
    }
    
    /* Target all th elements to ensure vertical centering */
    [data-testid="stDataFrame"] th div {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        height: 100% !important;
        width: 100% !important;
    }
    
    /* Ensure all header rows have consistent height */
    [data-testid="stDataFrame"] thead tr th {
        height: 50px !important;
    }
    
    /* Target the body of the table */
    [data-testid="stDataFrame"] tbody {
        background-color: #1e1e1e !important;
    }
    
    /* Style the table cells */
    [data-testid="stDataFrame"] td {
        text-align: center !important;
        vertical-align: middle !important;
        background-color: #1e1e1e !important;
        color: white !important;
        border: none !important;
        border-right: 1px solid #333333 !important;
        border-top: 1px solid #333333 !important;
    }
    
    /* Force all header text to be centered with line-height */
    [data-testid="stDataFrame"] th {
        line-height: 50px !important;
    }
    
    /* Override Streamlit's default table cell styling for headers */
    [data-testid="stDataFrame"] thead tr:first-child th * {
        vertical-align: middle !important;
        line-height: 50px !important;
    }
    
    /* Center group headers with blue styling */
    [data-testid="stDataFrame"] thead tr:first-child th {
        background-color: #0066cc !important;
        color: white !important;
        text-align: center !important;
        font-weight: bold !important;
        font-size: 1.1rem !important;
        padding: 12px 8px !important;
        vertical-align: middle !important;
    }
    
    /* Style the table cells */
    [data-testid="stDataFrame"] td {
        text-align: center !important;
        vertical-align: middle !important;
    }
    
    /* Improve table appearance with subtle borders */
    [data-testid="stDataFrame"] table {
        border-collapse: collapse !important;
        border: none !important;
    }
    
    /* Remove white lines and use subtle borders */
    [data-testid="stDataFrame"] th, [data-testid="stDataFrame"] td {
        border: none !important;
        border-bottom: 1px solid #f0f0f0 !important;
        padding: 10px 8px !important;
    }
    
    /* Add alternating row colors for better readability */
    [data-testid="stDataFrame"] tbody tr:nth-child(odd) {
        background-color: #f9f9f9 !important;
    }
    
    /* Live status indicator - pulsing green dot */
    .live-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        background-color: #00ff00;
        border-radius: 50%;
        margin-right: 10px;
        animation: pulse 2s infinite;
        box-shadow: 0 0 8px #00ff00, 0 0 12px #00ff00;
        border: 2px solid #00cc00;
    }
    
    /* Stale status indicator - yellow static dot */
    .stale-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        background-color: #ffaa00;
        border-radius: 50%;
        margin-right: 10px;
        box-shadow: 0 0 5px #ffaa00;
        border: 2px solid #cc8800;
    }
    
    /* Error status indicator - red static dot */
    .error-indicator {
        display: inline-block;
        width: 12px;
        height: 12px;
        background-color: #ff0000;
        border-radius: 50%;
        margin-right: 10px;
        box-shadow: 0 0 5px #ff0000;
        border: 2px solid #cc0000;
    }
    
    @keyframes pulse {
        0% {
            opacity: 1;
            transform: scale(1);
            box-shadow: 0 0 8px #00ff00, 0 0 12px #00ff00;
        }
        50% {
            opacity: 0.6;
            transform: scale(1.2);
            box-shadow: 0 0 12px #00ff00, 0 0 20px #00ff00;
        }
        100% {
            opacity: 1;
            transform: scale(1);
            box-shadow: 0 0 8px #00ff00, 0 0 12px #00ff00;
        }
    }
    </style>
    
    <script>
    // Keep page at top when switching tabs
    const targetNode = document.querySelector('.main');
    if (targetNode) {
        const config = { childList: true, subtree: true };
        const callback = function(mutationsList, observer) {
            // Force scroll to top
            window.scrollTo({top: 0, behavior: 'instant'});
            document.querySelector('.main').scrollTop = 0;
        };
        const observer = new MutationObserver(callback);
        observer.observe(targetNode, config);
    }
    
    // Also force on load
    window.scrollTo({top: 0, behavior: 'instant'});
    </script>
    """, unsafe_allow_html=True)
    
    # Title at the top
    st.markdown('<div class="main-header"><span style="font-size: 3.5rem;">🤖</span> AI Powered K8s Virtual Assistant</div>', unsafe_allow_html=True)
    
    # Navigation and buttons in same row - aligned
    col_nav, col_spacer, col_button = st.columns([3, 0.5, 0.5])
    
    with col_nav:
        page = st.radio(
            "",
            ["🤖 AI Assistant", "📋 Host Validator", "🖥️ VM Status", "🚀 Pod Monitor"],
            index=0,
            label_visibility="collapsed",
            horizontal=True
        )
    
    with col_button:
        if page == "🤖 AI Assistant":
            if st.button("🗑️ Clear Chat", key="clear_chat_button", use_container_width=True):
                st.session_state.chat_history = []
                st.rerun()
        else:
            if st.button("🔄 Refresh", key="manual_refresh_button", use_container_width=True):
                st.session_state.manual_refresh = True
                st.rerun()
    
    # Show selected page in main area
    if page == "📋 Host Validator":
        st.markdown('<div class="section-header">📋 Host Validation</div>', unsafe_allow_html=True)
        st.write("Check if a server meets the minimum requirements to join a Kubernetes cluster.")
        
        # VM Type Selection
        col1, col2 = st.columns(2)
        
        with col1:
            vm_type = st.selectbox(
                "VM Type",
                options=list(VM_TYPES.keys()),
                help="Select the type of VM you want to validate"
            )
        
        with col2:
            if vm_type != "Direct SSH":
                zone = st.selectbox(
                    "Zone/Region",
                    options=VM_TYPES[vm_type].get("zones", VM_TYPES[vm_type].get("regions", [])),
                    help="Select the zone or region"
                )
        
        # Input fields
        col1, col2 = st.columns(2)
        
        with col1:
            if vm_type in ["Google Cloud (GCE)", "AWS EC2", "Azure VM"]:
                # Add identifier type dropdown for cloud VMs
                identifier_type = st.selectbox(
                    "VM Identifier Type",
                    options=["VM Name", "VM ID", "IP Address"],
                    help="Select how you want to identify your VM"
                )
                
                if identifier_type == "VM Name":
                    host = st.text_input(
                        "Instance Name", 
                        placeholder="e.g., k8s-node-1",
                        help="The name of your VM instance"
                    )
                elif identifier_type == "VM ID":
                    host = st.text_input(
                        "Instance ID", 
                        placeholder="e.g., i-1234567890abcdef0 (AWS) or 123456789012345678 (GCP)",
                        help="The unique ID of your VM instance"
                    )
                else:  # IP Address
                    host = st.text_input(
                        "IP Address",
                        placeholder="e.g., 34.68.49.191",
                        help="The external IP address of your VM"
                    )
            else:  # Direct SSH
                host = st.text_input("Host/IP Address", placeholder="192.168.1.100")
            
            username = st.text_input(
                "Username", 
                value=VM_TYPES[vm_type]["default_username"],
                placeholder="Enter SSH username"
            )
        
        with col2:
            auth_method = st.selectbox(
                "Authentication Method",
                options=VM_TYPES[vm_type]["auth_methods"]
            )
            
            if auth_method == "Password":
                password = st.text_input("Password", type="password")
            elif auth_method == "SSH Key":
                key_path = st.text_input("SSH Key Path", placeholder="/path/to/private/key")
        
        # Requirements
        st.subheader("Requirements")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            min_cpu = st.number_input("Min CPU Cores", value=MIN_CPU_CORES, min_value=1)
        with col2:
            min_memory = st.number_input("Min Memory (MiB)", value=MIN_MEMORY_MIB, min_value=512)
        with col3:
            min_disk = st.number_input("Min Disk (GiB)", value=MIN_DISK_GIB, min_value=1)
        
        # Validate button
        if st.button("🔍 Validate Host", type="primary"):
            if not host or not username:
                st.error("Please provide both host and username")
            else:
                with st.spinner("Checking requirements..."):
                    try:
                        if vm_type == "Direct SSH":
                            # Use direct SSH
                            kwargs = {"password": password} if auth_method == "Password" else {"key_path": key_path}
                            result = check_requirements(
                                host=host,
                                username=username,
                                min_cpu_cores=min_cpu,
                                min_memory_mib=min_memory,
                                min_disk_gib=min_disk,
                                **kwargs
                            )
                        else:
                            # Use cloud SSH
                            result = check_requirements_cloud(
                                vm_type=vm_type,
                                instance_name=host,
                                username=username,
                                zone=zone,
                                auth_method=auth_method,
                                min_cpu_cores=min_cpu,
                                min_memory_mib=min_memory,
                                min_disk_gib=min_disk
                            )
                        
                        # Display results
                        if result.get('error'):
                            st.error(f"❌ Error: {result['error']}")
                        elif result['ok']:
                            st.success("✅ Host meets all requirements!")
                        else:
                            st.error("❌ Host does not meet requirements:")
                            for failure in result['failures']:
                                st.write(f"• {failure}")
                        
                        # Show metrics
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("CPU Cores", result.get('cpu_cores', 0))
                        with col2:
                            st.metric("Memory (MiB)", result.get('memory_mib', 0))
                        with col3:
                            st.metric("Disk Free (GiB)", result.get('disk_gib_free', 0))
                    
                    except Exception as e:
                        st.error(f"Validation failed: {str(e)}")
    
    elif page == "🖥️ VM Status":
        st.markdown('<div class="section-header">🖥️ VM Status & Resources</div>', unsafe_allow_html=True)
        
        st.write("Monitor your GCP VMs and their resources")

        if vm_table_data:
            # Show indicator using cached status
            vm_indicator = get_live_indicator_html('vm')
            st.markdown(f"""
                <div style="color: #3498db; font-size: 1.2rem; margin-bottom: 10px; display: flex; align-items: center;">
                    <span style="margin-right: 8px;">📊</span>
                    {vm_indicator}
                    <span>VM Resources Overview</span>
                </div>
            """, unsafe_allow_html=True)
            
            # Display the comprehensive table with grouped columns
            if vm_table_data:
                # Create dataframe with reorganized columns for grouping
                display_rows = []
                for row in vm_table_data:
                    display_row = row.copy()
                    display_row['Data Age'] = format_time_ago(row['data_timestamp'])
                    display_row.pop('data_timestamp', None)
                    display_rows.append(display_row)
                base_cols = ['VM Name', 'Zone', 'K8s Status', 'Role', 'Internal IP', 'External IP', 'Data Age']
                
                # Create hierarchical multi-index dataframe for pretty display
                df_resources = pd.DataFrame(display_rows)
                
                # Rename columns with tuples for hierarchical display
                renamed_columns = {}
                for col in df_resources.columns:
                    if col in base_cols:
                        # Center-align text with HTML
                        centered_col = col
                        renamed_columns[col] = (centered_col, '')
                    elif col.startswith('CPU'):
                        renamed_columns[col] = ('CPU', col.replace('CPU ', ''))
                    elif col.startswith('Memory'):
                        renamed_columns[col] = ('MEMORY', col.replace('Memory ', ''))
                    elif col.startswith('Disk'):
                        renamed_columns[col] = ('DISK', col.replace('Disk ', ''))
                
                df_resources = df_resources.rename(columns=renamed_columns)
                
                # Create multi-index columns
                df_resources.columns = pd.MultiIndex.from_tuples(df_resources.columns)
                
                # Display with streamlit using styled dataframe for proper centering
                st.markdown('<div class="dashboard-metrics">', unsafe_allow_html=True)
                
                # Use styled dataframe to force center alignment
                styled_df = df_resources.style.set_table_styles([
                    {'selector': 'th', 'props': [
                        ('text-align', 'center'),
                        ('background-color', '#1e1e1e'),
                        ('color', 'white'),
                        ('font-weight', 'bold'),
                        ('padding', '10px'),
                        ('border', '1px solid #333333')
                    ]},
                    {'selector': 'td', 'props': [
                        ('text-align', 'center'),
                        ('background-color', '#1e1e1e'),
                        ('color', 'white'),
                        ('padding', '8px'),
                        ('border', '1px solid #333333')
                    ]},
                    {'selector': 'thead tr:first-child th', 'props': [
                        ('text-align', 'center'),
                        ('color', '#3498db'),
                        ('font-size', '1.1rem')
                    ]}
                ]).set_properties(**{
                    'text-align': 'center'
                })
                
                st.dataframe(
                    styled_df,
                    width='stretch',
                    height=300,
                    hide_index=True
                )
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.warning("No VM data available")
        else:
            st.warning("No VM data available. Use refresh to fetch the latest metrics.")
        
        # Display command logs
        st.markdown("---")
        display_command_logs("vm_status")
    
    elif page == "🚀 Pod Monitor":
        st.markdown('<div class="section-header">🚀 Pod Monitor</div>', unsafe_allow_html=True)
        
        st.write("Monitor pods across your Kubernetes cluster")
        
        pod_indicator = get_live_indicator_html('pod')
        if pods_data:
            st.markdown(f"""
                <div style="font-size: 1.5rem; font-weight: 600; margin-bottom: 1rem; display: flex; align-items: center;">
                    {pod_indicator}
                    <span>Pod Overview</span>
                </div>
            """, unsafe_allow_html=True)
            col1, col2, col3, col4 = st.columns(4)
            
            total_pods = len(pods_data)
            running_pods = sum(1 for pod in pods_data if pod['status'] == 'Running')
            pending_pods = sum(1 for pod in pods_data if pod['status'] == 'Pending')
            failed_pods = sum(1 for pod in pods_data if pod['status'] == 'Failed')
            
            with col1:
                st.metric("Total Pods", total_pods)
            with col2:
                st.metric("Running", running_pods)
            with col3:
                st.metric("Pending", pending_pods)
            with col4:
                st.metric("Failed", failed_pods)
            
            namespaces = sorted(list(set(pod['namespace'] for pod in pods_data)))
            selected_namespace = st.selectbox("Filter by namespace:", ["All"] + namespaces)
            
            filtered_pods = pods_data
            if selected_namespace != "All":
                filtered_pods = [pod for pod in pods_data if pod['namespace'] == selected_namespace]
            
            st.subheader("Pod Details")
            if filtered_pods:
                pods_df_data = []
                for pod in filtered_pods:
                    status_icon = "🟢" if pod['status'] == 'Running' else "🔴" if pod['status'] == 'Failed' else "🟡"
                    pods_df_data.append({
                        'Name': pod['name'],
                        'Namespace': pod['namespace'],
                        'Status': f"{status_icon} {pod['status']}",
                        'Node': pod['node'],
                        'Ready': pod['ready'],
                        'Restarts': pod['restarts'],
                        'Data Age': format_time_ago(pod['fetch_timestamp'])
                    })
                
                df_pods = pd.DataFrame(pods_df_data)
                st.dataframe(df_pods, use_container_width=True)
            else:
                st.info("No pods found in selected namespace.")
        else:
            st.markdown(f"""
                <div style="font-size: 1.5rem; font-weight: 600; margin-bottom: 1rem; display: flex; align-items: center;">
                    {pod_indicator}
                    <span>Pod Overview</span>
                </div>
            """, unsafe_allow_html=True)
            st.warning("No pods found. Make sure kubectl is configured and cluster is running.")
        
        # Quick kubectl commands
        st.subheader("Quick Actions")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📋 Get Cluster Info"):
                try:
                    result = subprocess.run(["kubectl", "cluster-info"], capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        st.code(result.stdout)
                    else:
                        st.error("Failed to get cluster info")
                except:
                    st.error("kubectl command failed")
        
        with col2:
            if st.button("🖥️ List Nodes"):
                try:
                    result = subprocess.run(["kubectl", "get", "nodes", "-o", "wide"], capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        st.code(result.stdout)
                    else:
                        st.error("Failed to list nodes")
                except:
                    st.error("kubectl command failed")
        
        with col3:
            if st.button("🚀 All Pods"):
                try:
                    result = subprocess.run(["kubectl", "get", "pods", "--all-namespaces"], capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        st.code(result.stdout)
                    else:
                        st.error("Failed to list pods")
                except:
                    st.error("kubectl command failed")
        
        # Display command logs
        st.markdown("---")
        display_command_logs("pod_monitor")
    
    elif page == "🤖 AI Assistant":
        # Check if API key is configured
        api_key = os.getenv('GOOGLE_API_KEY')
        
        if not GEMINI_AVAILABLE:
            st.error("❌ Google Generative AI library not installed. Install it with: `pip install google-generativeai`")
        elif not api_key:
            st.warning("⚠️ Google API Key not configured")
            st.info("""
            **To enable the AI Assistant:**
            1. Get a free API key from: https://makersuite.google.com/app/apikey
            2. Add it to your `.env` file: `GOOGLE_API_KEY=your-api-key-here`
            3. Restart the dashboard
            
            The Gemini API has a generous free tier with no credit card required!
            """)
        else:
            # Initialize Gemini
            try:
                # Initialize chat session in session state
                if 'chat_history' not in st.session_state:
                    st.session_state.chat_history = []
                
                # Add custom CSS to reduce all spacing around chat
                st.markdown("""
                <style>
                    /* Reduce spacing before chat container */
                    div[data-testid="stVerticalBlock"] > div:has(div.stChatFloatingInputContainer) {
                        margin-top: 0px !important;
                        padding-top: 0px !important;
                    }
                    
                    /* Reduce spacing in chat container */
                    div[data-testid="stVerticalBlock"] {
                        gap: 0.5rem !important;
                    }
                    
                    /* Remove extra padding from elements */
                    .element-container {
                        margin-bottom: 0px !important;
                    }
                </style>
                """, unsafe_allow_html=True)
                
                # K8s logo URL
                k8s_avatar = "https://raw.githubusercontent.com/kubernetes/kubernetes/master/logo/logo.png"
                
                chat_container = st.container(height=500)
                with chat_container:
                    # Display welcome message if no chat history
                    if not st.session_state.chat_history:
                        with st.chat_message("assistant", avatar=k8s_avatar):
                            # Get cluster status for welcome message
                            vm_count = len(st.session_state.get('vm_table_cache', []))
                            pod_count = len(st.session_state.get('pods_cache', []))
                            
                            welcome_msg = f"""👋 **Hi! I'm your Kubernetes AI Assistant with LIVE cluster access!**

**I can see YOUR cluster:**
- 🖥️ VMs: {vm_count if vm_count > 0 else '❌ No data yet - visit VM Status tab'}
- 🚀 Pods: {pod_count if pod_count > 0 else '❌ No data yet - visit Pod Monitor tab'}
- 📝 Command history: Available

**Ask me about:**
- "What's the status of my cluster?"
- "Show me my VMs and their resource usage"
- "Which pods are running?"
- "Is my master node healthy?"
- "Any pods in failed state?"
- Or any Kubernetes concept/troubleshooting question!

💡 **Tip:** Visit VM Status and Pod Monitor tabs first for full cluster visibility!"""
                            
                            st.markdown(welcome_msg)
                    
                    # Display all chat history
                    for message in st.session_state.chat_history:
                        avatar = k8s_avatar if message["role"] == "assistant" else None
                        with st.chat_message(message["role"], avatar=avatar):
                            st.markdown(message["content"])
                
                # Chat input fixed at the bottom
                if prompt := st.chat_input("Ask me about YOUR cluster (VMs, pods, resources)..."):
                    # Add user message to chat history
                    st.session_state.chat_history.append({"role": "user", "content": prompt})
                    
                    # Get AI response with cluster context
                    try:
                        # Build cluster context
                        cluster_context = build_cluster_context()
                        
                        # Create full prompt with context
                        full_prompt = f"""You are a Kubernetes cluster assistant with access to real-time data from the user's cluster.

{cluster_context}

User Question: {prompt}

Instructions:
- Answer based on the ACTUAL cluster data provided above
- Reference specific VMs, pods, namespaces, or metrics when relevant
- If the data shows issues or anomalies, point them out clearly
- If no data is available for a specific area, mention that the user should visit that tab and refresh
- Be concise, technical, and actionable
- Use the exact VM names, pod names, and values from the data
"""
                        
                        # Send message to Gemini via REST helper with increased token limit
                        resp_json = generate_content(full_prompt, api_key=api_key, max_tokens=2000, temperature=0.2)
                        # parse first candidate text
                        candidate = resp_json.get('candidates', [{}])[0]
                        ai_parts = candidate.get('content', {}).get('parts', [])
                        ai_response = ''
                        if ai_parts:
                            ai_response = ''.join([p.get('text', '') for p in ai_parts])
                        else:
                            ai_response = json.dumps(resp_json)

                        # Add AI response to history
                        st.session_state.chat_history.append({"role": "assistant", "content": ai_response})

                    except Exception as e:
                        error_msg = f"Error getting AI response: {str(e)}"
                        st.session_state.chat_history.append({"role": "assistant", "content": error_msg})
                    
                    # Rerun to display new messages
                    st.rerun()
            
            except Exception as e:
                st.error(f"Failed to initialize AI: {str(e)}")
                st.info("Check your API key configuration in the `.env` file.")
    
    # Footer
    st.markdown("---")
    st.markdown(f"*Dashboard last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

if __name__ == "__main__":
    main()
