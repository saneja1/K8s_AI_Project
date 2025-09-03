"""
Unit tests for core.system module
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import paramiko
import sys
import os

# Add the project root to the Python path so we can import our modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.system import check_requirements, _get_cpu_cores, _get_memory_mib, _get_disk_gib_free

class TestCheckRequirements:
    
    def test_missing_auth_credentials(self):
        """Test error when neither password nor key_path is provided."""
        result = check_requirements("test-host", "test-user")
        assert result['ok'] is False
        assert result['error'] == "Either password or key_path must be provided"
    
    def test_missing_ssh_key_file(self):
        """Test error when SSH key file doesn't exist."""
        result = check_requirements("test-host", "test-user", key_path="/nonexistent/key")
        assert result['ok'] is False
        assert result['error'].startswith("SSH key file not found:")
    
    @patch('core.system.paramiko.SSHClient')
    def test_authentication_failure(self, mock_ssh_class):
        """Test SSH authentication failure."""
        mock_ssh = Mock()
        mock_ssh_class.return_value = mock_ssh
        mock_ssh.connect.side_effect = paramiko.AuthenticationException("Auth failed")
        
        result = check_requirements("test-host", "test-user", password="wrong-pass")
        assert result['ok'] is False
        assert result['error'] == "SSH authentication failed. Check username/password or key."
        mock_ssh.close.assert_called_once()
    
    @patch('core.system.paramiko.SSHClient')
    def test_ssh_connection_error(self, mock_ssh_class):
        """Test SSH connection error."""
        mock_ssh = Mock()
        mock_ssh_class.return_value = mock_ssh
        mock_ssh.connect.side_effect = paramiko.SSHException("Connection failed")
        
        result = check_requirements("test-host", "test-user", password="test-pass")
        assert result['ok'] is False
        assert result['error'] == "SSH connection error: Connection failed"
        mock_ssh.close.assert_called_once()
    
    @patch('core.system._get_disk_gib_free')
    @patch('core.system._get_memory_mib')
    @patch('core.system._get_cpu_cores')
    @patch('core.system.paramiko.SSHClient')
    def test_successful_check_meets_requirements(self, mock_ssh_class, mock_cpu, mock_memory, mock_disk):
        """Test successful check where host meets all requirements."""
        mock_ssh = Mock()
        mock_ssh_class.return_value = mock_ssh
        
        # Mock system metrics that meet requirements
        mock_cpu.return_value = 4  # > 2 required
        mock_memory.return_value = 8192  # > 4096 required
        mock_disk.return_value = 50  # > 30 required
        
        result = check_requirements("test-host", "test-user", password="test-pass")
        
        assert result['ok'] is True
        assert result['cpu_cores'] == 4
        assert result['memory_mib'] == 8192
        assert result['disk_gib_free'] == 50
        assert result['failures'] == []
        assert result['error'] is None
        mock_ssh.close.assert_called_once()
    
    @patch('core.system._get_disk_gib_free')
    @patch('core.system._get_memory_mib')
    @patch('core.system._get_cpu_cores')
    @patch('core.system.paramiko.SSHClient')
    def test_successful_check_fails_requirements(self, mock_ssh_class, mock_cpu, mock_memory, mock_disk):
        """Test successful check where host fails to meet requirements."""
        mock_ssh = Mock()
        mock_ssh_class.return_value = mock_ssh
        
        # Mock system metrics that don't meet requirements
        mock_cpu.return_value = 1  # < 2 required
        mock_memory.return_value = 2048  # < 4096 required
        mock_disk.return_value = 20  # < 30 required
        
        result = check_requirements("test-host", "test-user", password="test-pass")
        
        assert result['ok'] is False
        assert result['cpu_cores'] == 1
        assert result['memory_mib'] == 2048
        assert result['disk_gib_free'] == 20
        assert len(result['failures']) == 3
        assert "CPU cores: 1 < 2 required" in result['failures']
        assert "Memory: 2048 MiB < 4096 MiB required" in result['failures']
        assert "Disk space: 20 GiB < 30 GiB required" in result['failures']
        assert result['error'] is None
        mock_ssh.close.assert_called_once()
    
    @patch('core.system.os.path.exists')
    @patch('core.system._get_disk_gib_free')
    @patch('core.system._get_memory_mib')
    @patch('core.system._get_cpu_cores')
    @patch('core.system.paramiko.SSHClient')
    def test_ssh_key_authentication(self, mock_ssh_class, mock_cpu, mock_memory, mock_disk, mock_exists):
        """Test SSH key authentication."""
        mock_ssh = Mock()
        mock_ssh_class.return_value = mock_ssh
        mock_exists.return_value = True
        
        mock_cpu.return_value = 4
        mock_memory.return_value = 8192
        mock_disk.return_value = 50
        
        result = check_requirements("test-host", "test-user", key_path="/path/to/key")
        
        assert result['ok'] is True
        mock_ssh.connect.assert_called_once_with(
            hostname="test-host",
            port=22,
            username="test-user",
            key_filename="/path/to/key",
            timeout=10
        )

class TestSystemMetrics:
    
    def test_get_cpu_cores_nproc_success(self):
        """Test _get_cpu_cores with successful nproc command."""
        mock_ssh = Mock()
        mock_stdout = Mock()
        mock_stdout.read.return_value = b"4\n"
        mock_ssh.exec_command.return_value = (None, mock_stdout, None)
        
        result = _get_cpu_cores(mock_ssh, 10)
        assert result == 4
        mock_ssh.exec_command.assert_called_with('nproc', timeout=10)
    
    def test_get_cpu_cores_fallback_to_proc_cpuinfo(self):
        """Test _get_cpu_cores fallback to /proc/cpuinfo."""
        mock_ssh = Mock()
        
        # First call (nproc) fails, second call (proc/cpuinfo) succeeds
        mock_stdout1 = Mock()
        mock_stdout1.read.side_effect = Exception("nproc failed")
        mock_stdout2 = Mock()
        mock_stdout2.read.return_value = b"2\n"
        
        mock_ssh.exec_command.side_effect = [
            Exception("nproc failed"),
            (None, mock_stdout2, None)
        ]
        
        result = _get_cpu_cores(mock_ssh, 10)
        assert result == 2
    
    def test_get_memory_mib_success(self):
        """Test _get_memory_mib with successful parsing."""
        mock_ssh = Mock()
        mock_stdout = Mock()
        # Simulate /proc/meminfo output (4 GB = 4194304 KB)
        mock_stdout.read.return_value = b"""MemTotal:        4194304 kB
MemFree:         2097152 kB
MemAvailable:    3145728 kB"""
        mock_ssh.exec_command.return_value = (None, mock_stdout, None)
        
        result = _get_memory_mib(mock_ssh, 10)
        assert result == 4096  # 4194304 KB / 1024 = 4096 MiB
    
    def test_get_disk_gib_free_success(self):
        """Test _get_disk_gib_free with successful parsing."""
        mock_ssh = Mock()
        mock_stdout = Mock()
        # Simulate df -BG / output
        mock_stdout.read.return_value = b"""Filesystem     1G-blocks  Used Avail Use% Mounted on
/dev/sda1            100G   50G   45G  53% /"""
        mock_ssh.exec_command.return_value = (None, mock_stdout, None)
        
        result = _get_disk_gib_free(mock_ssh, 10)
        # 45 GB converted to GiB: 45 / 1.073741824 ≈ 41
        assert result == 41
    
    def test_system_metrics_return_zero_on_failure(self):
        """Test that all metric functions return 0 on failure."""
        mock_ssh = Mock()
        mock_ssh.exec_command.side_effect = Exception("Command failed")
        
        assert _get_cpu_cores(mock_ssh, 10) == 0
        assert _get_memory_mib(mock_ssh, 10) == 0
        assert _get_disk_gib_free(mock_ssh, 10) == 0

if __name__ == "__main__":
    pytest.main([__file__])
