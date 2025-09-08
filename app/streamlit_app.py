import streamlit as st
import os
import subprocess
import json
import pandas as pd
from dotenv import load_dotenv

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

if __name__ == "__main__":
    main()
