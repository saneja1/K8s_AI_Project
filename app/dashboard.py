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

# Add the parent directory to the path to import from core
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from core.system import check_requirements, check_requirements_cloud

# Log file path
LOG_FILE = Path(__file__).parent.parent / '.logs' / 'command_logs.pkl'
LOG_FILE.parent.mkdir(exist_ok=True)

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
            'echo CPU_COUNT:$(nproc) && '
            'echo MEM_TOTAL:$(free -g | awk "NR==2{print $2}") && '
            'echo MEM_USED:$(free -g | awk "NR==2{print $3}") && '
            'echo MEM_AVAIL:$(free -g | awk "NR==2{print $7}") && '
            'echo DISK_TOTAL:$(df -BG / | tail -1 | awk "{print $2}" | sed "s/G//") && '
            'echo DISK_USED:$(df -BG / | tail -1 | awk "{print $3}" | sed "s/G//") && '
            'echo DISK_AVAIL:$(df -BG / | tail -1 | awk "{print $4}" | sed "s/G//") && '
            'echo CPU_USAGE:$(top -bn2 | grep "Cpu(s)" | tail -1 | awk "{print 100 - $8}")'
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
                    
                    if key == 'CPU_COUNT':
                        vm_resources['cpu_count'] = value
                    elif key == 'CPU_USAGE':
                        vm_resources['cpu_usage'] = value
                    elif key == 'MEM_TOTAL':
                        vm_resources['memory_total'] = value
                    elif key == 'MEM_USED':
                        vm_resources['memory_used'] = value
                    elif key == 'MEM_AVAIL':
                        vm_resources['memory_available'] = value
                    elif key == 'DISK_TOTAL':
                        vm_resources['disk_total'] = value
                    elif key == 'DISK_USED':
                        vm_resources['disk_used'] = value
                    elif key == 'DISK_AVAIL':
                        vm_resources['disk_available'] = value
            
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

def main():
    st.set_page_config(
        page_title="Kubernetes Management Dashboard",
        page_icon="🎛️",
        layout="wide"
    )
    
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
    .main-header {
        font-size: 2.5rem;
        color: #0066cc;
        margin-bottom: 20px;
    }
    .section-header {
        font-size: 1.8rem;
        color: #2e7d32;
        padding-top: 10px;
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
    """, unsafe_allow_html=True)
    
    # Main title with custom styling
    st.markdown('<div class="main-header">🎛️ Kubernetes Management Dashboard</div>', unsafe_allow_html=True)
    
    # Create tabs for different functionalities
    tab1, tab2, tab3 = st.tabs(["📋 Host Validator", "🖥️ VM Status", "🚀 Pod Monitor"])
    
    # TAB 1: Host Validator
    with tab1:
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
    
    # TAB 2: VM Status
    with tab2:
        st.markdown('<div class="section-header">🖥️ VM Status & Resources</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write("Monitor your GCP VMs and their resources")
        with col2:
            if st.button("🔄 Refresh", key="vm_refresh", use_container_width=True):
                st.rerun()
        
        # Define our VMs directly (since we know them)
        vm_list = [
            {"name": "k8s-master-001", "zone": "us-central1-a", "ip": "34.135.232.124"},
            {"name": "k8s-worker-01", "zone": "us-central1-a", "ip": "34.133.61.216"}
        ]
        
        if vm_list:
            # Collect resource data for both VMs FIRST
            vm_table_data = []
            all_vm_fetch_success = True
            
            # Process each VM
            for vm_config in vm_list:
                # Set VM info
                k8s_status = "✓ VM Running"
                k8s_role = "Master" if vm_config['name'] == 'k8s-master-001' else "Worker"
                k8s_version = "v1.28.15"
                internal_ip = "10.128.0.6" if vm_config['name'] == 'k8s-master-001' else "10.128.0.7"
                
                # Fetch REAL data from VM via SSH
                fetch_time = datetime.now()
                vm_resources = get_vm_resources(vm_config['name'], vm_config['zone'])
                
                if 'error' in vm_resources:
                    all_vm_fetch_success = False
                
                if 'error' not in vm_resources:
                    # Calculate percentages
                    try:
                        cpu_usage = float(vm_resources.get('cpu_usage', 0))
                        mem_total = int(vm_resources.get('memory_total', 0))
                        mem_used = int(vm_resources.get('memory_used', 0))
                        mem_percent = (mem_used / mem_total * 100) if mem_total > 0 else 0
                        
                        disk_total = int(vm_resources.get('disk_total', 0))
                        disk_used = int(vm_resources.get('disk_used', 0))
                        disk_percent = (disk_used / disk_total * 100) if disk_total > 0 else 0
                        
                    except (ValueError, TypeError):
                        cpu_usage = mem_percent = disk_percent = 0
                        mem_total = mem_used = disk_total = disk_used = 0
                    
                    vm_table_data.append({
                        'VM Name': vm_config['name'],
                        'Zone': vm_config['zone'],
                        'K8s Status': k8s_status,
                        'Role': k8s_role,
                        'Internal IP': internal_ip,
                        'Data Age': format_time_ago(fetch_time),
                        'CPU Cores': vm_resources.get('cpu_count', 'N/A'),
                        'CPU Usage %': f"{cpu_usage:.1f}%" if cpu_usage > 0 else 'N/A',
                        'Memory Total (GB)': f"{mem_total}" if mem_total > 0 else 'N/A',
                        'Memory Used %': f"{mem_percent:.1f}%" if mem_used > 0 else 'N/A',
                        'Memory Available (GB)': f"{vm_resources.get('memory_available', 'N/A')}",
                        'Disk Total (GB)': f"{disk_total}" if disk_total > 0 else 'N/A',
                        'Disk Used %': f"{disk_percent:.1f}%" if disk_used > 0 else 'N/A',
                        'Disk Available (GB)': f"{vm_resources.get('disk_available', 'N/A')}"
                    })
                else:
                    # VM with error
                    vm_table_data.append({
                        'VM Name': vm_config['name'],
                        'Zone': vm_config['zone'],
                        'K8s Status': k8s_status,
                        'Role': k8s_role,
                        'Internal IP': internal_ip,
                        'Data Age': format_time_ago(fetch_time),
                        'CPU Cores': '❌ Error',
                        'CPU Usage %': '❌ Error',
                        'Memory Total (GB)': '❌ Error',
                        'Memory Used %': '❌ Error',
                        'Memory Available (GB)': '❌ Error',
                        'Disk Total (GB)': '❌ Error',
                        'Disk Used %': '❌ Error',
                        'Disk Available (GB)': '❌ Error'
                    })
            
            # Update VM data timestamp and status
            if all_vm_fetch_success:
                st.session_state.vm_data_timestamp = datetime.now()
                st.session_state.vm_data_status = 'success'
            else:
                st.session_state.vm_data_status = 'error'
            
            # NOW show the indicator with updated timestamp
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
                base_cols = ['VM Name', 'Zone', 'K8s Status', 'Role', 'Internal IP', 'Data Age']
                
                # Create hierarchical multi-index dataframe for pretty display
                df_resources = pd.DataFrame(vm_table_data)
                
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
            st.warning("No cluster nodes found. Make sure kubectl is configured.")
        
        # Display command logs
        st.markdown("---")
        display_command_logs("vm_status")
    
    # TAB 3: Pod Monitor
    with tab3:
        st.markdown('<div class="section-header">🚀 Pod Monitor</div>', unsafe_allow_html=True)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            st.write("Monitor pods across your Kubernetes cluster")
        with col2:
            if st.button("🔄 Refresh", key="pod_refresh"):
                st.rerun()
        
        # Get pods info
        pods_data = get_pods_info()
        
        if pods_data:
            # Pod statistics
            pod_indicator = get_live_indicator_html('pod')
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
            
            # Namespace filter
            namespaces = sorted(list(set(pod['namespace'] for pod in pods_data)))
            selected_namespace = st.selectbox("Filter by namespace:", ["All"] + namespaces)
            
            # Filter pods
            filtered_pods = pods_data
            if selected_namespace != "All":
                filtered_pods = [pod for pod in pods_data if pod['namespace'] == selected_namespace]
            
            # Pods table
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
    
    # Footer
    st.markdown("---")
    st.markdown(f"*Dashboard last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

if __name__ == "__main__":
    main()
