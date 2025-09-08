"""
SSH-based system requirements checker for Kubernetes cluster hosts.
"""
import paramiko
import re
import os
import subprocess
import json
from typing import Dict, Optional, Union
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Default configuration
DEFAULT_MIN_CPU_CORES = int(os.getenv('MIN_CPU_CORES', 2))
DEFAULT_MIN_MEMORY_MIB = int(os.getenv('MIN_MEMORY_MIB', 4096))
DEFAULT_MIN_DISK_GIB = int(os.getenv('MIN_DISK_GIB', 30))

def check_requirements_cloud(
    vm_type: str,
    instance_name: str,
    username: str,
    zone: Optional[str] = None,
    auth_method: str = "GCloud CLI",
    min_cpu_cores: int = DEFAULT_MIN_CPU_CORES,
    min_memory_mib: int = DEFAULT_MIN_MEMORY_MIB,
    min_disk_gib: int = DEFAULT_MIN_DISK_GIB
) -> Dict[str, Union[bool, int, list]]:
    """
    Check requirements using cloud provider CLI tools.
    
    Args:
        vm_type: Type of VM (Google Cloud, AWS, Azure)
        instance_name: VM instance name or IP address
        username: SSH username
        zone: Zone/region for the VM
        auth_method: Authentication method (CLI tools)
        min_cpu_cores: Minimum CPU cores required
        min_memory_mib: Minimum memory in MiB required
        min_disk_gib: Minimum disk space in GiB required
    
    Returns:
        Dict with 'ok', 'cpu_cores', 'memory_mib', 'disk_gib_free', 'failures', 'error', 'execution_log'
    """
    result = {
        'ok': False,
        'cpu_cores': 0,
        'memory_mib': 0,
        'disk_gib_free': 0,
        'failures': [],
        'error': None,
        'execution_log': []
    }
    
    # If instance_name looks like an IP address, try to find the actual instance name and zone
    actual_instance_name = instance_name
    actual_zone = zone
    
    if vm_type == "Google Cloud (GCE)" and re.match(r'^\d+\.\d+\.\d+\.\d+$', instance_name):
        # It's an IP address, try to find the instance name and zone
        try:
            find_cmd = [
                "gcloud", "compute", "instances", "list",
                f"--filter=networkInterfaces.accessConfigs.natIP={instance_name}",
                "--format=value(name,zone)"
            ]
            find_result = subprocess.run(find_cmd, capture_output=True, text=True, timeout=15)
            if find_result.returncode == 0 and find_result.stdout.strip():
                parts = find_result.stdout.strip().split('\t')
                if len(parts) >= 2:
                    actual_instance_name = parts[0]
                    actual_zone = parts[1].split('/')[-1]  # Extract zone from full path
                    result['execution_log'].append({
                        'command': ' '.join(find_cmd),
                        'return_code': 0,
                        'output': f'Found instance: {actual_instance_name} in zone: {actual_zone}',
                        'error': ''
                    })
        except Exception as e:
            result['execution_log'].append({
                'command': 'Instance lookup',
                'return_code': 1,
                'output': '',
                'error': f'Failed to find instance for IP {instance_name}: {str(e)}'
            })
    
    try:
        # Check CPU cores - use simple command
        cpu_result = _execute_cloud_command(vm_type, actual_instance_name, username, "nproc", actual_zone, auth_method)
        result['execution_log'].append({
            'command': f'gcloud compute ssh {username}@{actual_instance_name} --command="nproc"' + (f' --zone={actual_zone}' if actual_zone else ''),
            'return_code': 0 if cpu_result['success'] else 1,
            'output': cpu_result['output'],
            'error': cpu_result['error']
        })
        
        if cpu_result['success'] and cpu_result['output'].strip().isdigit():
            result['cpu_cores'] = int(cpu_result['output'].strip())
        else:
            # Fallback command for CPU
            cpu_result = _execute_cloud_command(vm_type, actual_instance_name, username, "grep -c processor /proc/cpuinfo", actual_zone, auth_method)
            result['execution_log'].append({
                'command': f'gcloud compute ssh {username}@{actual_instance_name} --command="grep -c processor /proc/cpuinfo"' + (f' --zone={actual_zone}' if actual_zone else ''),
                'return_code': 0 if cpu_result['success'] else 1,
                'output': cpu_result['output'],
                'error': cpu_result['error']
            })
            if cpu_result['success'] and cpu_result['output'].strip().isdigit():
                result['cpu_cores'] = int(cpu_result['output'].strip())
        
        if result['cpu_cores'] < min_cpu_cores:
            result['failures'].append(f"CPU cores: {result['cpu_cores']} < {min_cpu_cores} required")
        
        # Check memory - use awk to extract memory in MiB
        mem_command = "awk '/MemTotal/ {printf \"%.0f\", $2/1024}' /proc/meminfo"
        mem_result = _execute_cloud_command(vm_type, actual_instance_name, username, mem_command, actual_zone, auth_method)
        result['execution_log'].append({
            'command': f'gcloud compute ssh {username}@{actual_instance_name} --command="{mem_command}"' + (f' --zone={actual_zone}' if actual_zone else ''),
            'return_code': 0 if mem_result['success'] else 1,
            'output': mem_result['output'],
            'error': mem_result['error']
        })
        
        if mem_result['success'] and mem_result['output'].strip().isdigit():
            result['memory_mib'] = int(mem_result['output'].strip())
        
        if result['memory_mib'] < min_memory_mib:
            result['failures'].append(f"Memory: {result['memory_mib']} MiB < {min_memory_mib} MiB required")
        
        # Check disk space - use simpler df command
        disk_command = "df -BG / | tail -1 | awk '{print $4}' | sed 's/G//'"
        disk_result = _execute_cloud_command(vm_type, actual_instance_name, username, disk_command, actual_zone, auth_method)
        result['execution_log'].append({
            'command': f'gcloud compute ssh {username}@{actual_instance_name} --command="{disk_command}"' + (f' --zone={actual_zone}' if actual_zone else ''),
            'return_code': 0 if disk_result['success'] else 1,
            'output': disk_result['output'],
            'error': disk_result['error']
        })
        
        if disk_result['success'] and disk_result['output'].strip().isdigit():
            gb = int(disk_result['output'].strip())
            # Convert GB to GiB (1 GiB = 1.073741824 GB)
            result['disk_gib_free'] = int(gb / 1.073741824)
        
        if result['disk_gib_free'] < min_disk_gib:
            result['failures'].append(f"Disk space: {result['disk_gib_free']} GiB < {min_disk_gib} GiB required")
        
        # Overall result
        result['ok'] = len(result['failures']) == 0
        
    except Exception as e:
        result['error'] = f"Error checking requirements: {str(e)}"
    
    return result

def _execute_cloud_command(vm_type: str, instance_name: str, username: str, command: str, zone: Optional[str] = None, auth_method: str = "GCloud CLI") -> Dict[str, Union[bool, str]]:
    """
    Execute a command on a cloud VM using provider CLI tools.
    """
    try:
        if vm_type == "Google Cloud (GCE)" and auth_method == "GCloud CLI":
            # Use gcloud compute ssh with proper command escaping
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
        
        # Add other cloud providers here as needed
        else:
            return {
                'success': False,
                'output': "",
                'error': f"Unsupported VM type or auth method: {vm_type} with {auth_method}"
            }
            
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

def check_requirements(
    host: str,
    username: str,
    password: Optional[str] = None,
    key_path: Optional[str] = None,
    port: int = 22,
    timeouts: Optional[Dict] = None,
    min_cpu_cores: int = DEFAULT_MIN_CPU_CORES,
    min_memory_mib: int = DEFAULT_MIN_MEMORY_MIB,
    min_disk_gib: int = DEFAULT_MIN_DISK_GIB
) -> Dict[str, Union[bool, int, list]]:
    """
    Check if a remote host meets minimum requirements for Kubernetes cluster.
    
    Args:
        host: IP address or hostname
        username: SSH username
        password: SSH password (if using password auth)
        key_path: Path to SSH private key (if using key auth)
        port: SSH port (default 22)
        timeouts: Dict with 'connect' and 'command' timeout values
        min_cpu_cores: Minimum CPU cores required
        min_memory_mib: Minimum memory in MiB required
        min_disk_gib: Minimum disk space in GiB required
    
    Returns:
        Dict with 'ok', 'cpu_cores', 'memory_mib', 'disk_gib_free', 'failures', 'error', 'execution_log'
    """
    if timeouts is None:
        timeouts = {'connect': 10, 'command': 15}
    
    execution_log = []
    result = {
        'ok': False,
        'cpu_cores': 0,
        'memory_mib': 0,
        'disk_gib_free': 0,
        'failures': [],
        'error': None,
        'execution_log': execution_log
    }
    
    ssh_client = None
    try:
        # Create SSH client
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        # Log connection attempt
        auth_method = "SSH key" if key_path else "password"
        execution_log.append({
            'command': f'SSH connect to {username}@{host}:{port} using {auth_method}',
            'stdout': '',
            'stderr': '',
            'success': False
        })
        
        # Connect using password or key
        if password:
            ssh_client.connect(
                hostname=host,
                port=port,
                username=username,
                password=password,
                timeout=timeouts['connect']
            )
        elif key_path:
            if not os.path.exists(key_path):
                result['error'] = f"SSH key file not found: {key_path}"
                execution_log[-1]['stderr'] = result['error']
                return result
            ssh_client.connect(
                hostname=host,
                port=port,
                username=username,
                key_filename=key_path,
                timeout=timeouts['connect']
            )
        else:
            result['error'] = "Either password or key_path must be provided"
            execution_log[-1]['stderr'] = result['error']
            return result
        
        # Mark connection as successful
        execution_log[-1]['stdout'] = f'Successfully connected to {host}:{port}'
        execution_log[-1]['success'] = True
        
        # Check CPU cores
        cpu_cores = _get_cpu_cores(ssh_client, timeouts['command'], execution_log)
        result['cpu_cores'] = cpu_cores
        if cpu_cores < min_cpu_cores:
            result['failures'].append(f"CPU cores: {cpu_cores} < {min_cpu_cores} required")
        
        # Check memory
        memory_mib = _get_memory_mib(ssh_client, timeouts['command'], execution_log)
        result['memory_mib'] = memory_mib
        if memory_mib < min_memory_mib:
            result['failures'].append(f"Memory: {memory_mib} MiB < {min_memory_mib} MiB required")
        
        # Check disk space
        disk_gib_free = _get_disk_gib_free(ssh_client, timeouts['command'], execution_log)
        result['disk_gib_free'] = disk_gib_free
        if disk_gib_free < min_disk_gib:
            result['failures'].append(f"Disk space: {disk_gib_free} GiB < {min_disk_gib} GiB required")
        
        # Overall result
        result['ok'] = len(result['failures']) == 0
        
    except paramiko.AuthenticationException:
        result['error'] = "SSH authentication failed. Check username/password or key."
        if execution_log:
            execution_log[-1]['stderr'] = result['error']
    except paramiko.SSHException as e:
        result['error'] = f"SSH connection error: {str(e)}"
        if execution_log:
            execution_log[-1]['stderr'] = result['error']
    except TimeoutError:
        result['error'] = f"Connection timeout to {host}:{port}"
        if execution_log:
            execution_log[-1]['stderr'] = result['error']
    except Exception as e:
        result['error'] = f"Unexpected error: {str(e)}"
        if execution_log:
            execution_log[-1]['stderr'] = result['error']
    finally:
        if ssh_client:
            ssh_client.close()
    
    return result

def _get_cpu_cores(ssh_client: paramiko.SSHClient, timeout: int, execution_log: list) -> int:
    """Get number of CPU cores using nproc, /proc/cpuinfo, or Windows commands."""
    # Try Linux commands first
    try:
        # Try nproc first
        command = 'nproc'
        execution_log.append({
            'command': command,
            'stdout': '',
            'stderr': '',
            'success': False
        })
        
        stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        execution_log[-1]['stdout'] = output
        execution_log[-1]['stderr'] = error
        
        if output and output.isdigit():
            execution_log[-1]['success'] = True
            return int(output)
    except Exception as e:
        if execution_log:
            execution_log[-1]['stderr'] = str(e)

    try:
        # Fallback to /proc/cpuinfo
        command = 'grep -c "^processor" /proc/cpuinfo'
        execution_log.append({
            'command': command,
            'stdout': '',
            'stderr': '',
            'success': False
        })
        
        stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        execution_log[-1]['stdout'] = output
        execution_log[-1]['stderr'] = error
        
        if output and output.isdigit():
            execution_log[-1]['success'] = True
            return int(output)
    except Exception as e:
        if execution_log:
            execution_log[-1]['stderr'] = str(e)
    
    # Try Windows commands
    try:
        # Windows: Get number of logical processors
        command = 'echo $env:NUMBER_OF_PROCESSORS'
        execution_log.append({
            'command': command,
            'stdout': '',
            'stderr': '',
            'success': False
        })
        
        stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        execution_log[-1]['stdout'] = output
        execution_log[-1]['stderr'] = error
        
        if output and output.isdigit():
            execution_log[-1]['success'] = True
            return int(output)
    except Exception as e:
        if execution_log:
            execution_log[-1]['stderr'] = str(e)
    
    try:
        # Windows: Alternative using wmic
        command = 'wmic cpu get NumberOfLogicalProcessors /value'
        execution_log.append({
            'command': command,
            'stdout': '',
            'stderr': '',
            'success': False
        })
        
        stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
        output = stdout.read().decode()
        error = stderr.read().decode().strip()
        
        execution_log[-1]['stdout'] = output
        execution_log[-1]['stderr'] = error
        
        for line in output.split('\n'):
            if 'NumberOfLogicalProcessors=' in line:
                value = line.split('=')[1].strip()
                if value.isdigit():
                    execution_log[-1]['success'] = True
                    return int(value)
    except Exception as e:
        if execution_log:
            execution_log[-1]['stderr'] = str(e)

    return 0

def _get_memory_mib(ssh_client: paramiko.SSHClient, timeout: int, execution_log: list) -> int:
    """Get available memory in MiB from /proc/meminfo or Windows commands."""
    # Try Linux first
    try:
        command = 'cat /proc/meminfo'
        execution_log.append({
            'command': command,
            'stdout': '',
            'stderr': '',
            'success': False
        })
        
        stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
        output = stdout.read().decode()
        error = stderr.read().decode().strip()
        
        execution_log[-1]['stdout'] = output[:500] + '...' if len(output) > 500 else output  # Truncate long output
        execution_log[-1]['stderr'] = error
        
        # Look for MemTotal (we'll use total as the available memory for simplicity)
        # In a real scenario, you might want to use MemAvailable if present
        mem_total_match = re.search(r'MemTotal:\s+(\d+)\s+kB', output)
        if mem_total_match:
            kb = int(mem_total_match.group(1))
            execution_log[-1]['success'] = True
            return kb // 1024  # Convert KB to MiB
    except Exception as e:
        if execution_log:
            execution_log[-1]['stderr'] = str(e)
    
    # Try Windows commands
    try:
        # Windows: Get total physical memory in bytes
        command = 'wmic computersystem get TotalPhysicalMemory /value'
        execution_log.append({
            'command': command,
            'stdout': '',
            'stderr': '',
            'success': False
        })
        
        stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
        output = stdout.read().decode()
        error = stderr.read().decode().strip()
        
        execution_log[-1]['stdout'] = output
        execution_log[-1]['stderr'] = error
        
        for line in output.split('\n'):
            if 'TotalPhysicalMemory=' in line:
                value = line.split('=')[1].strip()
                if value.isdigit():
                    bytes_mem = int(value)
                    execution_log[-1]['success'] = True
                    return bytes_mem // (1024 * 1024)  # Convert bytes to MiB
    except Exception as e:
        if execution_log:
            execution_log[-1]['stderr'] = str(e)
    
    try:
        # Windows: Alternative using PowerShell
        command = 'powershell "Get-CimInstance -ClassName Win32_ComputerSystem | Select-Object -ExpandProperty TotalPhysicalMemory"'
        execution_log.append({
            'command': command,
            'stdout': '',
            'stderr': '',
            'success': False
        })
        
        stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        execution_log[-1]['stdout'] = output
        execution_log[-1]['stderr'] = error
        
        if output.isdigit():
            bytes_mem = int(output)
            execution_log[-1]['success'] = True
            return bytes_mem // (1024 * 1024)  # Convert bytes to MiB
    except Exception as e:
        if execution_log:
            execution_log[-1]['stderr'] = str(e)

    return 0

def _get_disk_gib_free(ssh_client: paramiko.SSHClient, timeout: int, execution_log: list) -> int:
    """Get free disk space in GiB for root filesystem or C: drive."""
    # Try Linux first
    try:
        # Use df -BG to get output in GB, then convert to GiB
        command = 'df -BG /'
        execution_log.append({
            'command': command,
            'stdout': '',
            'stderr': '',
            'success': False
        })
        
        stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
        output = stdout.read().decode()
        error = stderr.read().decode().strip()
        
        execution_log[-1]['stdout'] = output
        execution_log[-1]['stderr'] = error
        
        # Parse df output: filesystem 1G-blocks Used Available Use% Mounted-on
        lines = output.strip().split('\n')
        if len(lines) >= 2:
            # Get the data line (might be line 1 or 2 depending on filesystem name length)
            data_line = lines[1] if not lines[1].startswith(' ') else lines[1].strip()
            parts = data_line.split()
            if len(parts) >= 4:
                available_gb_str = parts[3].rstrip('G')
                if available_gb_str.isdigit():
                    gb = int(available_gb_str)
                    # Convert GB to GiB (1 GiB = 1.073741824 GB)
                    execution_log[-1]['success'] = True
                    return int(gb / 1.073741824)
    except Exception as e:
        if execution_log:
            execution_log[-1]['stderr'] = str(e)
    
    # Try Windows commands
    try:
        # Windows: Get free space on C: drive (fixed command)
        command = 'wmic logicaldisk where "size>0" get size,freespace,caption /value'
        execution_log.append({
            'command': command,
            'stdout': '',
            'stderr': '',
            'success': False
        })
        
        stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
        output = stdout.read().decode()
        error = stderr.read().decode().strip()
        
        execution_log[-1]['stdout'] = output
        execution_log[-1]['stderr'] = error
        
        # Parse wmic output for C: drive
        lines = output.split('\n')
        caption = None
        freespace = None
        
        for line in lines:
            line = line.strip()
            if line.startswith('Caption='):
                caption = line.split('=')[1].strip()
            elif line.startswith('FreeSpace='):
                freespace_str = line.split('=')[1].strip()
                if freespace_str.isdigit():
                    freespace = int(freespace_str)
            
            # If we found C: drive data, calculate free space in GiB
            if caption == 'C:' and freespace is not None:
                execution_log[-1]['success'] = True
                return freespace // (1024 * 1024 * 1024)  # Convert bytes to GiB
                
    except Exception as e:
        if execution_log:
            execution_log[-1]['stderr'] = str(e)
    
    try:
        # Windows: Alternative using PowerShell
        command = 'powershell "Get-CimInstance -ClassName Win32_LogicalDisk -Filter \\"DriveType=3\\" | Where-Object {$_.DeviceID -eq \\"C:\\"} | Select-Object -ExpandProperty FreeSpace"'
        execution_log.append({
            'command': command,
            'stdout': '',
            'stderr': '',
            'success': False
        })
        
        stdin, stdout, stderr = ssh_client.exec_command(command, timeout=timeout)
        output = stdout.read().decode().strip()
        error = stderr.read().decode().strip()
        
        execution_log[-1]['stdout'] = output
        execution_log[-1]['stderr'] = error
        
        if output.isdigit():
            bytes_free = int(output)
            execution_log[-1]['success'] = True
            return bytes_free // (1024 * 1024 * 1024)  # Convert bytes to GiB
    except Exception as e:
        if execution_log:
            execution_log[-1]['stderr'] = str(e)

    return 0
