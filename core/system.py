"""
SSH-based system requirements checker for Kubernetes cluster hosts.
"""
import paramiko
import re
import os
from typing import Dict, Optional, Union
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Default configuration
DEFAULT_MIN_CPU_CORES = int(os.getenv('MIN_CPU_CORES', 2))
DEFAULT_MIN_MEMORY_MIB = int(os.getenv('MIN_MEMORY_MIB', 4096))
DEFAULT_MIN_DISK_GIB = int(os.getenv('MIN_DISK_GIB', 30))

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
        Dict with 'ok', 'cpu_cores', 'memory_mib', 'disk_gib_free', 'failures', 'error'
    """
    if timeouts is None:
        timeouts = {'connect': 10, 'command': 15}
    
    result = {
        'ok': False,
        'cpu_cores': 0,
        'memory_mib': 0,
        'disk_gib_free': 0,
        'failures': [],
        'error': None
    }
    
    ssh_client = None
    try:
        # Create SSH client
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
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
            return result
        
        # Check CPU cores
        cpu_cores = _get_cpu_cores(ssh_client, timeouts['command'])
        result['cpu_cores'] = cpu_cores
        if cpu_cores < min_cpu_cores:
            result['failures'].append(f"CPU cores: {cpu_cores} < {min_cpu_cores} required")
        
        # Check memory
        memory_mib = _get_memory_mib(ssh_client, timeouts['command'])
        result['memory_mib'] = memory_mib
        if memory_mib < min_memory_mib:
            result['failures'].append(f"Memory: {memory_mib} MiB < {min_memory_mib} MiB required")
        
        # Check disk space
        disk_gib_free = _get_disk_gib_free(ssh_client, timeouts['command'])
        result['disk_gib_free'] = disk_gib_free
        if disk_gib_free < min_disk_gib:
            result['failures'].append(f"Disk space: {disk_gib_free} GiB < {min_disk_gib} GiB required")
        
        # Overall result
        result['ok'] = len(result['failures']) == 0
        
    except paramiko.AuthenticationException:
        result['error'] = "SSH authentication failed. Check username/password or key."
    except paramiko.SSHException as e:
        result['error'] = f"SSH connection error: {str(e)}"
    except TimeoutError:
        result['error'] = f"Connection timeout to {host}:{port}"
    except Exception as e:
        result['error'] = f"Unexpected error: {str(e)}"
    finally:
        if ssh_client:
            ssh_client.close()
    
    return result

def _get_cpu_cores(ssh_client: paramiko.SSHClient, timeout: int) -> int:
    """Get number of CPU cores using nproc, /proc/cpuinfo, or Windows commands."""
    # Try Linux commands first
    try:
        # Try nproc first
        stdin, stdout, stderr = ssh_client.exec_command('nproc', timeout=timeout)
        output = stdout.read().decode().strip()
        if output and output.isdigit():
            return int(output)
    except:
        pass
    
    try:
        # Fallback to /proc/cpuinfo
        stdin, stdout, stderr = ssh_client.exec_command('grep -c "^processor" /proc/cpuinfo', timeout=timeout)
        output = stdout.read().decode().strip()
        if output and output.isdigit():
            return int(output)
    except:
        pass
    
    # Try Windows commands
    try:
        # Windows: Get number of logical processors
        stdin, stdout, stderr = ssh_client.exec_command('echo $env:NUMBER_OF_PROCESSORS', timeout=timeout)
        output = stdout.read().decode().strip()
        if output and output.isdigit():
            return int(output)
    except:
        pass
    
    try:
        # Windows: Alternative using wmic
        stdin, stdout, stderr = ssh_client.exec_command('wmic cpu get NumberOfLogicalProcessors /value', timeout=timeout)
        output = stdout.read().decode()
        for line in output.split('\n'):
            if 'NumberOfLogicalProcessors=' in line:
                value = line.split('=')[1].strip()
                if value.isdigit():
                    return int(value)
    except:
        pass
    
    return 0

def _get_memory_mib(ssh_client: paramiko.SSHClient, timeout: int) -> int:
    """Get available memory in MiB from /proc/meminfo or Windows commands."""
    # Try Linux first
    try:
        stdin, stdout, stderr = ssh_client.exec_command('cat /proc/meminfo', timeout=timeout)
        output = stdout.read().decode()
        
        # Look for MemTotal (we'll use total as the available memory for simplicity)
        # In a real scenario, you might want to use MemAvailable if present
        mem_total_match = re.search(r'MemTotal:\s+(\d+)\s+kB', output)
        if mem_total_match:
            kb = int(mem_total_match.group(1))
            return kb // 1024  # Convert KB to MiB
    except:
        pass
    
    # Try Windows commands
    try:
        # Windows: Get total physical memory in bytes
        stdin, stdout, stderr = ssh_client.exec_command('wmic computersystem get TotalPhysicalMemory /value', timeout=timeout)
        output = stdout.read().decode()
        for line in output.split('\n'):
            if 'TotalPhysicalMemory=' in line:
                value = line.split('=')[1].strip()
                if value.isdigit():
                    bytes_mem = int(value)
                    return bytes_mem // (1024 * 1024)  # Convert bytes to MiB
    except:
        pass
    
    try:
        # Windows: Alternative using PowerShell
        stdin, stdout, stderr = ssh_client.exec_command('powershell "Get-CimInstance -ClassName Win32_ComputerSystem | Select-Object -ExpandProperty TotalPhysicalMemory"', timeout=timeout)
        output = stdout.read().decode().strip()
        if output.isdigit():
            bytes_mem = int(output)
            return bytes_mem // (1024 * 1024)  # Convert bytes to MiB
    except:
        pass
    
    return 0

def _get_disk_gib_free(ssh_client: paramiko.SSHClient, timeout: int) -> int:
    """Get free disk space in GiB for root filesystem or C: drive."""
    # Try Linux first
    try:
        # Use df -BG to get output in GB, then convert to GiB
        stdin, stdout, stderr = ssh_client.exec_command('df -BG /', timeout=timeout)
        output = stdout.read().decode()
        
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
                    return int(gb / 1.073741824)
    except:
        pass
    
    # Try Windows commands
    try:
        # Windows: Get free space on C: drive (fixed command)
        stdin, stdout, stderr = ssh_client.exec_command('wmic logicaldisk where "size>0" get size,freespace,caption /value', timeout=timeout)
        output = stdout.read().decode()
        
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
                return freespace // (1024 * 1024 * 1024)  # Convert bytes to GiB
                
    except:
        pass
    
    try:
        # Windows: Alternative using PowerShell
        stdin, stdout, stderr = ssh_client.exec_command('powershell "Get-CimInstance -ClassName Win32_LogicalDisk -Filter \\"DriveType=3\\" | Where-Object {$_.DeviceID -eq \\"C:\\"} | Select-Object -ExpandProperty FreeSpace"', timeout=timeout)
        output = stdout.read().decode().strip()
        if output.isdigit():
            bytes_free = int(output)
            return bytes_free // (1024 * 1024 * 1024)  # Convert bytes to GiB
    except:
        pass
    
    return 0
