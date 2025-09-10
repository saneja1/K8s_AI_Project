import streamlit as st
import os
import subprocess
import json
import pandas as pd
from dotenv import load_dotenv
import time
from datetime import datetime
import re

# Load environment variables
load_dotenv()

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
        "default_username": "swinvm15",
        "requires_zone": True,
        "description": "Uses gcloud compute ssh or direct SSH"
    },
    "AWS EC2": {
        "auth_methods": ["AWS CLI", "SSH Key", "Password"],
        "default_username": "ec2-user",
        "requires_zone": False,
        "description": "Uses aws ssm or direct SSH"
    },
    "Azure VM": {
        "auth_methods": ["Azure CLI", "SSH Key", "Password"],
        "default_username": "azureuser",
        "requires_zone": False,
        "description": "Uses az vm run-command or direct SSH"
    },
    "VirtualBox VM": {
        "auth_methods": ["SSH Key", "Password"],
        "default_username": "user",
        "requires_zone": False,
        "description": "Direct SSH connection"
    },
    "Generic SSH": {
        "auth_methods": ["SSH Key", "Password"],
        "default_username": "",
        "requires_zone": False,
        "description": "Standard SSH connection"
    }
}

def execute_cloud_ssh_command(vm_type, instance_name, username, command, zone=None, auth_method=None, password=None, key_path=None, region=None):
    """
    Execute SSH command on different cloud providers using their CLI tools or direct SSH.
    
    Args:
        vm_type: Type of VM (Google Cloud, AWS, Azure, etc.)
        instance_name: VM instance name or IP
        username: SSH username
        command: Command to execute
        zone: Zone/region for cloud VMs
        auth_method: Authentication method
        password: SSH password (optional)
        key_path: SSH key path (optional)
        region: Region for AWS/Azure
    
    Returns:
        dict: {'success': bool, 'output': str, 'error': str}
    """
    try:
        if vm_type == "Google Cloud (GCE)" and auth_method == "GCloud CLI":
            # Use gcloud compute ssh
            cmd = [
                "gcloud", "compute", "ssh", 
                f"{username}@{instance_name}",
                "--command", command
            ]
            if zone:
                cmd.extend(["--zone", zone])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return {
                'success': result.returncode == 0,
                'output': result.stdout,
                'error': result.stderr
            }
            
        elif vm_type == "AWS EC2" and auth_method == "AWS CLI":
            # Use AWS Systems Manager Session Manager
            cmd = [
                "aws", "ssm", "send-command",
                "--instance-ids", instance_name,
                "--document-name", "AWS-RunShellScript",
                "--parameters", f"commands='{command}'",
                "--output", "json"
            ]
            if region:
                cmd.extend(["--region", region])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                # Parse the command ID and get output
                response = json.loads(result.stdout)
                command_id = response["Command"]["CommandId"]
                
                # Wait and get command output
                import time
                time.sleep(2)  # Wait for command execution
                
                get_output_cmd = [
                    "aws", "ssm", "get-command-invocation",
                    "--command-id", command_id,
                    "--instance-id", instance_name,
                    "--output", "json"
                ]
                if region:
                    get_output_cmd.extend(["--region", region])
                
                output_result = subprocess.run(get_output_cmd, capture_output=True, text=True, timeout=15)
                if output_result.returncode == 0:
                    output_data = json.loads(output_result.stdout)
                    return {
                        'success': True,
                        'output': output_data.get("StandardOutputContent", ""),
                        'error': output_data.get("StandardErrorContent", "")
                    }
            
            return {
                'success': False,
                'output': result.stdout,
                'error': result.stderr
            }
            
        elif vm_type == "Azure VM" and auth_method == "Azure CLI":
            # Use Azure CLI run-command
            cmd = [
                "az", "vm", "run-command", "invoke",
                "--name", instance_name,
                "--command-id", "RunShellScript",
                "--scripts", command,
                "--output", "json"
            ]
            if region:
                cmd.extend(["--resource-group", region])  # Using region as resource group
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                response = json.loads(result.stdout)
                output = ""
                error = ""
                if "value" in response and len(response["value"]) > 0:
                    if "message" in response["value"][0]:
                        output = response["value"][0]["message"]
                
                return {
                    'success': True,
                    'output': output,
                    'error': error
                }
            
            return {
                'success': False,
                'output': result.stdout,
                'error': result.stderr
            }
        
        else:
            # Fall back to direct SSH for all other cases
            return execute_direct_ssh(instance_name, username, command, password, key_path)
            
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'output': "",
            'error': "Command timed out"
        }
    except Exception as e:
        return {
            'success': False,
            'output': "",
            'error': f"Error executing command: {str(e)}"
        }

def execute_direct_ssh(host, username, command, password=None, key_path=None, port=22):
    """
    Execute SSH command using direct SSH connection.
    """
    try:
        # Import the system check module
        import sys
        import paramiko
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Connect using password or key
        if password:
            ssh_client.connect(
                hostname=host,
                port=port,
                username=username,
                password=password,
                timeout=10
            )
        elif key_path and os.path.exists(key_path):
            ssh_client.connect(
                hostname=host,
                port=port,
                username=username,
                key_filename=key_path,
                timeout=10
            )
        else:
            # Try without explicit authentication (use system SSH agent)
            ssh_client.connect(
                hostname=host,
                port=port,
                username=username,
                timeout=10
            )
        
        # Execute command
        stdin, stdout, stderr = ssh_client.exec_command(command, timeout=15)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        ssh_client.close()
        
        return {
            'success': True,
            'output': output,
            'error': error
        }
        
    except Exception as e:
        return {
            'success': False,
            'output': "",
            'error': f"SSH connection failed: {str(e)}"
        }

def main():
    # Main navigation
    st.sidebar.title("🎛️ Navigation")
    page = st.sidebar.radio(
        "Select Page:",
        ["📋 Host Validator", "🎛️ Cluster Dashboard"],
        help="Choose between validating individual hosts or monitoring the cluster"
    )
    
    if page == "📋 Host Validator":
        # Original host validator functionality
        st.title("Kubernetes Cluster Host Validator")
        st.write("This tool checks if a server meets the minimum requirements to join a Kubernetes cluster.")
        
        # Static text as specified in requirements
        st.write("### Does this server meet minimum cluster requirements?")
        
        # VM Type Selection
        st.subheader("VM Configuration")
        vm_type = st.selectbox(
            "VM Type",
            options=list(VM_TYPES.keys()),
            help="Select the type of VM you want to validate"
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
                    placeholder="e.g., my-vm-instance",
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
        else:
            identifier_type = "IP Address"  # For non-cloud VMs, always treat as IP/DNS
            host = st.text_input("Host IP/DNS", placeholder="e.g., 192.168.1.100")
        
        username = st.text_input(
            "SSH Username", 
            value=VM_TYPES[vm_type]['default_username'] or DEFAULT_SSH_USERNAME, 
            placeholder="e.g., ubuntu"
        )
        port = st.number_input("SSH Port", value=DEFAULT_SSH_PORT, min_value=1, max_value=65535)
        
        # Zone/Region field for cloud VMs
        if VM_TYPES[vm_type]['requires_zone'] or vm_type == "AWS EC2":
            if vm_type == "Google Cloud (GCE)":
                zone_region = st.text_input(
                    "Zone (optional)", 
                    placeholder="e.g., us-central1-c",
                    help="Leave empty to auto-detect zone"
                )
            elif vm_type == "AWS EC2":
                zone_region = st.text_input(
                    "Region (optional)", 
                    placeholder="e.g., us-east-1",
                    help="AWS region where the instance is located"
                )
            elif vm_type == "Azure VM":
                zone_region = st.text_input(
                    "Resource Group", 
                    placeholder="e.g., my-resource-group",
                    help="Azure resource group containing the VM"
                )
        else:
            zone_region = None
    
    with col2:
        # For cloud VMs, always show all authentication methods
        auth_method = st.selectbox(
            "Authentication Method",
            options=VM_TYPES[vm_type]['auth_methods']
        )
        
        password = None
        key_path = None
        
        if auth_method == "Password":
            password = st.text_input("SSH Password", type="password")
        elif auth_method == "SSH Key":
            key_path = st.text_input(
                "SSH Private Key Path", 
                placeholder="e.g., ~/.ssh/id_rsa or ~/.ssh/google_compute_engine"
            )
        
        # Show info about the selected VM type and authentication
        if auth_method in ["GCloud CLI", "AWS CLI", "Azure CLI"]:
            st.info(f"ℹ️ Using {auth_method} - no password/SSH key required (uses your configured CLI authentication)")
        else:
            st.info(f"ℹ️ {VM_TYPES[vm_type]['description']}")
    
    # Display current minimum requirements
    st.write("#### Minimum Requirements:")
    st.write(f"- CPU cores: {MIN_CPU_CORES}")
    st.write(f"- Memory: {MIN_MEMORY_MIB} MiB ({MIN_MEMORY_MIB/1024:.1f} GiB)")
    st.write(f"- Disk space (root /): {MIN_DISK_GIB} GiB free")
    
    # Test button
    if st.button("Test", type="primary"):
        if not host:
            if vm_type in ["Google Cloud (GCE)", "AWS EC2", "Azure VM"]:
                st.error("Please enter an instance name/ID.")
            else:
                st.error("Please enter a host IP or DNS name.")
            return
        
        if not username:
            st.error("Please enter a SSH username.")
            return
        
        if auth_method == "Password" and not password:
            if auth_method in VM_TYPES[vm_type]['auth_methods'] and auth_method not in ["GCloud CLI", "AWS CLI", "Azure CLI"]:
                st.warning("No password provided. Will attempt connection without explicit authentication.")
        
        if auth_method == "SSH Key" and key_path and not os.path.exists(key_path):
            st.error(f"SSH key file not found: {key_path}")
            return
        
        # For direct SSH methods, ensure we have either password or key
        if (auth_method in ["Password", "SSH Key"] and 
            not password and not (key_path and os.path.exists(key_path))):
            st.error("For direct SSH connections, either password or valid SSH key path must be provided.")
            return
        
        # Show spinner while checking
        with st.spinner("Checking server requirements..."):
            try:
                # Import the system check module
                import sys
                sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                
                # Determine whether to use cloud CLI or direct SSH
                use_cloud_cli = (vm_type in ["Google Cloud (GCE)", "AWS EC2", "Azure VM"] and 
                               auth_method in ["GCloud CLI", "AWS CLI", "Azure CLI"])
                
                if use_cloud_cli:
                    # Use cloud-specific SSH CLI (works with instance names, IDs, and IP addresses)
                    from core.system import check_requirements_cloud
                    
                    result = check_requirements_cloud(
                        vm_type=vm_type,
                        instance_name=host,
                        username=username,
                        zone=zone_region,
                        auth_method=auth_method,
                        min_cpu_cores=MIN_CPU_CORES,
                        min_memory_mib=MIN_MEMORY_MIB,
                        min_disk_gib=MIN_DISK_GIB
                    )
                else:
                    # Use standard SSH for direct connections
                    from core.system import check_requirements
                    
                    result = check_requirements(
                        host=host,
                        username=username,
                        password=password,
                        key_path=key_path,
                        port=port,
                        min_cpu_cores=MIN_CPU_CORES,
                        min_memory_mib=MIN_MEMORY_MIB,
                        min_disk_gib=MIN_DISK_GIB
                    )
                
                # Display results
                st.write("### Test Results")
                
                if result.get('error'):
                    st.error(f"Error: {result['error']}")
                    return
                
                # Show comparison table
                st.write("#### 📊 VM Specifications vs Minimum Requirements")
                
                # Create comparison data
                comparison_data = {
                    "Requirement": ["CPU Cores", "Memory (MiB)", "Disk Free (GiB)"],
                    "Your VM": [
                        f"{result['cpu_cores']} cores",
                        f"{result['memory_mib']} MiB ({result['memory_mib']/1024:.1f} GiB)",
                        f"{result['disk_gib_free']} GiB"
                    ],
                    "Minimum Required": [
                        f"{MIN_CPU_CORES} cores",
                        f"{MIN_MEMORY_MIB} MiB ({MIN_MEMORY_MIB/1024:.1f} GiB)",
                        f"{MIN_DISK_GIB} GiB"
                    ],
                    "Status": [
                        "✅ PASS" if result['cpu_cores'] >= MIN_CPU_CORES else "❌ FAIL",
                        "✅ PASS" if result['memory_mib'] >= MIN_MEMORY_MIB else "❌ FAIL",
                        "✅ PASS" if result['disk_gib_free'] >= MIN_DISK_GIB else "❌ FAIL"
                    ]
                }
                
                # Display as a nice table
                df = pd.DataFrame(comparison_data)
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Show overall result with clear messaging
                st.write("#### 🎯 Overall Result")
                if result['ok']:
                    st.success("✅ **SUCCESS: Your VM meets all minimum requirements for Kubernetes cluster!**")
                    st.balloons()  # Celebration animation
                else:
                    st.error("❌ **FAILED: Your VM does not meet minimum requirements for Kubernetes cluster**")
                    
                    # Show specific failures
                    st.write("**❗ Issues found:**")
                    for failure in result['failures']:
                        st.write(f"- {failure}")
                    
                    st.write("**💡 Next Steps:**")
                    if result['cpu_cores'] < MIN_CPU_CORES:
                        st.write(f"- Upgrade CPU: Add {MIN_CPU_CORES - result['cpu_cores']} more core(s)")
                    if result['memory_mib'] < MIN_MEMORY_MIB:
                        needed_mib = MIN_MEMORY_MIB - result['memory_mib']
                        st.write(f"- Upgrade Memory: Add {needed_mib} MiB ({needed_mib/1024:.1f} GiB) more RAM")
                    if result['disk_gib_free'] < MIN_DISK_GIB:
                        needed_gib = MIN_DISK_GIB - result['disk_gib_free']
                        st.write(f"- Free up Disk Space: Need {needed_gib} GiB more free space on root partition")
                
                # Command Execution Log
                st.write("#### 📋 Command Execution Log")
                with st.expander("🔍 View Commands & Results", expanded=False):
                    if hasattr(result, 'execution_log') and result['execution_log']:
                        st.write("**Commands executed and their results:**")
                        
                        # Create a scrollable text area with all command logs
                        log_content = ""
                        for i, log_entry in enumerate(result['execution_log'], 1):
                            log_content += f"**Command {i}:**\n"
                            log_content += f"```bash\n{log_entry['command']}\n```\n"
                            log_content += f"**Return Code:** {log_entry['return_code']}\n"
                            if log_entry['output']:
                                log_content += f"**Output:**\n```\n{log_entry['output']}\n```\n"
                            if log_entry['error']:
                                log_content += f"**Error:**\n```\n{log_entry['error']}\n```\n"
                            log_content += "---\n\n"
                        
                        # Display in a text area with scroll
                        st.text_area(
                            "Execution Details:",
                            value=log_content,
                            height=400,
                            disabled=True,
                            key="command_log"
                        )
                    else:
                        st.info("No detailed command logs available for this execution method.")
                
            except Exception as e:
                st.error(f"Error during check: {str(e)}")
                st.write("Please check your connection details and try again.")
    
    elif page == "🎛️ Cluster Dashboard":
        # Cluster monitoring dashboard
        cluster_monitoring_dashboard()

def get_cluster_info():
    """Get basic cluster information and node status."""
    try:
        # Get cluster info
        result = subprocess.run(
            ["kubectl", "cluster-info"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        cluster_info = result.stdout if result.returncode == 0 else "Cluster info unavailable"
        
        # Get nodes
        result = subprocess.run(
            ["kubectl", "get", "nodes", "-o", "json"], 
            capture_output=True, 
            text=True, 
            timeout=10
        )
        
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
                
                # Get node age
                creation_time = node['metadata'].get('creationTimestamp', '')
                if creation_time:
                    from datetime import datetime
                    try:
                        created = datetime.fromisoformat(creation_time.replace('Z', '+00:00'))
                        age_seconds = (datetime.now(created.tzinfo) - created).total_seconds()
                        if age_seconds < 3600:
                            node_info['age'] = f"{int(age_seconds/60)}m"
                        elif age_seconds < 86400:
                            node_info['age'] = f"{int(age_seconds/3600)}h"
                        else:
                            node_info['age'] = f"{int(age_seconds/86400)}d"
                    except:
                        pass
                
                # Get IP addresses
                for address in node['status'].get('addresses', []):
                    if address['type'] == 'InternalIP':
                        node_info['internal_ip'] = address['address']
                    elif address['type'] == 'ExternalIP':
                        node_info['external_ip'] = address['address']
                
                nodes_data.append(node_info)
        
        return cluster_info, nodes_data
    except Exception as e:
        return f"Error getting cluster info: {str(e)}", []

def get_node_resources():
    """Get resource usage for all nodes."""
    try:
        # Try to get node resource usage with kubectl top
        result = subprocess.run(
            ["kubectl", "top", "nodes", "--no-headers"], 
            capture_output=True, 
            text=True, 
            timeout=15
        )
        
        resources_data = []
        if result.returncode == 0:
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 5:
                        resources_data.append({
                            'node': parts[0],
                            'cpu_usage': parts[1],
                            'cpu_percent': parts[2],
                            'memory_usage': parts[3],
                            'memory_percent': parts[4]
                        })
        else:
            # Fallback: get resource allocatable from node descriptions
            result = subprocess.run(
                ["kubectl", "get", "nodes", "-o", "json"], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            
            if result.returncode == 0:
                nodes_json = json.loads(result.stdout)
                for node in nodes_json.get('items', []):
                    name = node['metadata']['name']
                    allocatable = node['status'].get('allocatable', {})
                    resources_data.append({
                        'node': name,
                        'cpu_usage': 'N/A',
                        'cpu_percent': 'N/A',
                        'memory_usage': 'N/A',
                        'memory_percent': 'N/A',
                        'cpu_allocatable': allocatable.get('cpu', 'Unknown'),
                        'memory_allocatable': allocatable.get('memory', 'Unknown'),
                        'pods_allocatable': allocatable.get('pods', 'Unknown')
                    })
        
        return resources_data
    except Exception as e:
        return [{'error': f"Error getting node resources: {str(e)}"}]

def get_pods_info():
    """Get information about all pods in the cluster."""
    try:
        result = subprocess.run(
            ["kubectl", "get", "pods", "--all-namespaces", "-o", "json"], 
            capture_output=True, 
            text=True, 
            timeout=15
        )
        
        pods_data = []
        if result.returncode == 0:
            pods_json = json.loads(result.stdout)
            for pod in pods_json.get('items', []):
                pod_info = {
                    'name': pod['metadata']['name'],
                    'namespace': pod['metadata']['namespace'],
                    'status': pod['status'].get('phase', 'Unknown'),
                    'node': pod['spec'].get('nodeName', 'Unknown'),
                    'ready': '0/0',
                    'restarts': 0,
                    'age': 'Unknown'
                }
                
                # Calculate ready containers
                container_statuses = pod['status'].get('containerStatuses', [])
                ready_containers = sum(1 for c in container_statuses if c.get('ready', False))
                total_containers = len(container_statuses)
                pod_info['ready'] = f"{ready_containers}/{total_containers}"
                
                # Count restarts
                pod_info['restarts'] = sum(c.get('restartCount', 0) for c in container_statuses)
                
                # Calculate age
                creation_time = pod['metadata'].get('creationTimestamp', '')
                if creation_time:
                    try:
                        created = datetime.fromisoformat(creation_time.replace('Z', '+00:00'))
                        age_seconds = (datetime.now(created.tzinfo) - created).total_seconds()
                        if age_seconds < 3600:
                            pod_info['age'] = f"{int(age_seconds/60)}m"
                        elif age_seconds < 86400:
                            pod_info['age'] = f"{int(age_seconds/3600)}h"
                        else:
                            pod_info['age'] = f"{int(age_seconds/86400)}d"
                    except:
                        pass
                
                pods_data.append(pod_info)
        
        return pods_data
    except Exception as e:
        return [{'error': f"Error getting pods info: {str(e)}"}]

def execute_kubectl_command(command):
    """Execute a kubectl command and return the result."""
    try:
        result = subprocess.run(
            ["kubectl"] + command.split(), 
            capture_output=True, 
            text=True, 
            timeout=30
        )
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'command': f"kubectl {command}"
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'stdout': '',
            'stderr': 'Command timed out',
            'command': f"kubectl {command}"
        }
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'command': f"kubectl {command}"
        }

def get_vm_system_resources(vm_name, zone="us-central1-a"):
    """Get detailed system resources from a VM using SSH."""
    try:
        # Get CPU, Memory, and Disk usage via SSH
        commands = {
            'cpu_usage': 'top -bn1 | grep "Cpu(s)" | sed "s/.*, *\\([0-9.]*\\)%* id.*/\\1/" | awk \'{print 100 - $1}\'',
            'memory_info': 'free -m | awk \'NR==2{printf "%.1f %.1f %.1f", $3*100/$2, $2, $3}\'',
            'disk_info': 'df -h / | awk \'NR==2{printf "%s %s %s", $2, $3, $4}\'',
            'load_average': 'uptime | awk -F\'load average:\' \'{print $2}\' | awk \'{print $1}\'',
            'uptime': 'uptime -p'
        }
        
        vm_resources = {'vm_name': vm_name, 'zone': zone}
        
        for metric, command in commands.items():
            result = subprocess.run([
                "gcloud", "compute", "ssh", f"swinvm15@{vm_name}",
                "--command", command,
                "--zone", zone,
                "--quiet"
            ], capture_output=True, text=True, timeout=15)
            
            if result.returncode == 0:
                vm_resources[metric] = result.stdout.strip()
            else:
                vm_resources[metric] = 'N/A'
        
        return vm_resources
    except Exception as e:
        return {'vm_name': vm_name, 'error': str(e)}

def cluster_monitoring_dashboard():
    """Display the cluster monitoring dashboard."""
    st.markdown("## 🎛️ Kubernetes Cluster Dashboard")
    st.markdown("---")
    
    # Auto-refresh toggle
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown("### Real-time Cluster Monitoring")
    with col2:
        auto_refresh = st.checkbox("🔄 Auto-refresh (30s)", value=False)
    
    if auto_refresh:
        time.sleep(1)  # Small delay to avoid too frequent updates
        st.rerun()
    
    # Manual refresh button
    if st.button("🔄 Refresh Now"):
        st.rerun()
    
    st.markdown("---")
    
    # Cluster Info Section
    with st.container():
        st.markdown("### 📊 Cluster Overview")
        cluster_info, nodes_data = get_cluster_info()
        
        if "Error" not in cluster_info:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📡 Cluster Status", "Online" if nodes_data else "Offline")
            with col2:
                ready_nodes = sum(1 for node in nodes_data if node['status'] == 'Ready')
                st.metric("🖥️ Ready Nodes", f"{ready_nodes}/{len(nodes_data)}")
            with col3:
                pods_data = get_pods_info()
                running_pods = sum(1 for pod in pods_data if pod.get('status') == 'Running')
                st.metric("🚀 Running Pods", running_pods)
        else:
            st.error(cluster_info)
    
    st.markdown("---")
    
    # VM Status Table
    with st.container():
        st.markdown("### 🖥️ VM Status & Resources")
        
        # Get VM information from kubectl nodes
        if nodes_data:
            # Create VM status dataframe
            vm_status_data = []
            for node in nodes_data:
                vm_status_data.append({
                    'VM Name': node['name'],
                    'Status': '🟢 Ready' if node['status'] == 'Ready' else '🔴 Not Ready',
                    'Role': ', '.join(node['roles']),
                    'Internal IP': node['internal_ip'],
                    'External IP': node['external_ip'] if node['external_ip'] != 'Unknown' else 'N/A',
                    'K8s Version': node['version'],
                    'Age': node['age']
                })
            
            df_vm_status = pd.DataFrame(vm_status_data)
            st.dataframe(df_vm_status, use_container_width=True)
        else:
            st.warning("No node information available. Please check kubectl connectivity.")
    
    st.markdown("---")
    
    # Resource Monitoring
    with st.container():
        st.markdown("### 📈 Resource Monitoring")
        
        resources_data = get_node_resources()
        if resources_data and 'error' not in resources_data[0]:
            # Create tabs for different resource views
            tab1, tab2 = st.tabs(["📊 Resource Usage", "💾 System Details"])
            
            with tab1:
                if all('cpu_usage' in resource for resource in resources_data):
                    # Display current resource usage
                    resource_df = pd.DataFrame(resources_data)
                    st.dataframe(resource_df, use_container_width=True)
                else:
                    st.info("Resource usage metrics require 'kubectl top nodes' (metrics-server).")
                    # Show allocatable resources instead
                    alloc_df = pd.DataFrame(resources_data)
                    st.dataframe(alloc_df, use_container_width=True)
            
            with tab2:
                # Get detailed system info for each VM
                st.markdown("#### System Resource Details")
                for i, node in enumerate(nodes_data):
                    with st.expander(f"🖥️ {node['name']} - System Resources"):
                        vm_resources = get_vm_system_resources(node['name'])
                        
                        if 'error' not in vm_resources:
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.markdown("**💻 CPU**")
                                if 'cpu_usage' in vm_resources:
                                    try:
                                        cpu_usage = float(vm_resources['cpu_usage'])
                                        st.metric("CPU Usage", f"{cpu_usage:.1f}%")
                                    except:
                                        st.text("CPU Usage: N/A")
                                
                                if 'load_average' in vm_resources:
                                    st.text(f"Load Average: {vm_resources['load_average']}")
                            
                            with col2:
                                st.markdown("**🧠 Memory**")
                                if 'memory_info' in vm_resources:
                                    try:
                                        mem_parts = vm_resources['memory_info'].split()
                                        if len(mem_parts) >= 3:
                                            mem_percent = float(mem_parts[0])
                                            mem_total = mem_parts[1]
                                            mem_used = mem_parts[2]
                                            st.metric("Memory Usage", f"{mem_percent:.1f}%")
                                            st.text(f"Used: {mem_used} MB / {mem_total} MB")
                                    except:
                                        st.text("Memory: N/A")
                            
                            with col3:
                                st.markdown("**💿 Disk**")
                                if 'disk_info' in vm_resources:
                                    disk_parts = vm_resources['disk_info'].split()
                                    if len(disk_parts) >= 3:
                                        st.text(f"Total: {disk_parts[0]}")
                                        st.text(f"Used: {disk_parts[1]}")
                                        st.text(f"Available: {disk_parts[2]}")
                                
                                if 'uptime' in vm_resources:
                                    st.text(f"Uptime: {vm_resources['uptime']}")
                        else:
                            st.error(f"Error getting resources: {vm_resources['error']}")
        else:
            st.warning("Unable to retrieve resource information.")
    
    st.markdown("---")
    
    # Pods Overview
    with st.container():
        st.markdown("### 🚀 Pods Overview")
        
        pods_data = get_pods_info()
        if pods_data and 'error' not in pods_data[0]:
            # Create namespace filter
            namespaces = sorted(list(set(pod['namespace'] for pod in pods_data)))
            selected_namespace = st.selectbox("Filter by namespace:", ["All"] + namespaces)
            
            # Filter pods by namespace
            filtered_pods = pods_data
            if selected_namespace != "All":
                filtered_pods = [pod for pod in pods_data if pod['namespace'] == selected_namespace]
            
            # Create pods dataframe
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
                    'Age': pod['age']
                })
            
            if pods_df_data:
                df_pods = pd.DataFrame(pods_df_data)
                st.dataframe(df_pods, use_container_width=True)
                
                # Pod statistics
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    total_pods = len(filtered_pods)
                    st.metric("Total Pods", total_pods)
                with col2:
                    running = sum(1 for pod in filtered_pods if pod['status'] == 'Running')
                    st.metric("Running", running)
                with col3:
                    pending = sum(1 for pod in filtered_pods if pod['status'] == 'Pending')
                    st.metric("Pending", pending)
                with col4:
                    failed = sum(1 for pod in filtered_pods if pod['status'] == 'Failed')
                    st.metric("Failed", failed)
            else:
                st.info("No pods found in the selected namespace.")
        else:
            st.warning("Unable to retrieve pods information.")
    
    st.markdown("---")
    
    # Quick Actions Section
    with st.container():
        st.markdown("### ⚡ Quick Actions")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**Cluster Commands**")
            if st.button("📋 Get Cluster Info"):
                result = execute_kubectl_command("cluster-info")
                if result['success']:
                    st.success("Cluster info retrieved successfully!")
                    st.code(result['stdout'])
                else:
                    st.error(f"Error: {result['stderr']}")
        
        with col2:
            st.markdown("**Node Commands**")
            if st.button("🖥️ Describe Nodes"):
                result = execute_kubectl_command("get nodes -o wide")
                if result['success']:
                    st.success("Nodes information:")
                    st.code(result['stdout'])
                else:
                    st.error(f"Error: {result['stderr']}")
        
        with col3:
            st.markdown("**Pod Commands**")
            if st.button("🚀 List All Pods"):
                result = execute_kubectl_command("get pods --all-namespaces")
                if result['success']:
                    st.success("All pods:")
                    st.code(result['stdout'])
                else:
                    st.error(f"Error: {result['stderr']}")
    
    # Custom kubectl command section
    with st.expander("🔧 Custom kubectl Commands"):
        st.markdown("**Execute custom kubectl commands**")
        custom_command = st.text_input("Enter kubectl command (without 'kubectl'):", 
                                     placeholder="get pods -n default")
        
        if st.button("Execute Command") and custom_command:
            result = execute_kubectl_command(custom_command)
            
            if result['success']:
                st.success(f"Command executed successfully!")
                st.code(result['stdout'])
            else:
                st.error(f"Command failed!")
                if result['stderr']:
                    st.code(result['stderr'])
    
    # Footer with last update time
    st.markdown("---")
    st.markdown(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

if __name__ == "__main__":
    main()
