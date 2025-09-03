# Enable SSH Server on Windows Laptop - Step by Step Guide

## Prerequisites
- Windows 10 version 1809 or later, or Windows 11
- Administrator privileges

## Step 1: Open PowerShell as Administrator
1. Press `Win + X`
2. Select "Windows PowerShell (Admin)" or "Terminal (Admin)"
3. Click "Yes" when prompted by UAC

## Step 2: Check OpenSSH Installation Status
```powershell
Get-WindowsCapability -Online | Where-Object Name -like 'OpenSSH*'
```

Expected output should show:
- OpenSSH.Client (usually already installed)
- OpenSSH.Server (may need installation)

## Step 3: Install OpenSSH Server (if needed)
```powershell
Add-WindowsCapability -Online -Name OpenSSH.Server~~~~0.0.1.0
```

## Step 4: Start SSH Service
```powershell
# Start the service
Start-Service sshd

# Set to start automatically
Set-Service -Name sshd -StartupType 'Automatic'
```

## Step 5: Configure Windows Firewall
```powershell
# Add firewall rule for SSH (port 22)
New-NetFirewallRule -Name sshd -DisplayName 'OpenSSH Server (sshd)' -Enabled True -Direction Inbound -Protocol TCP -Action Allow -LocalPort 22
```

## Step 6: Verify SSH Service Status
```powershell
Get-Service sshd
```

Should show: Status = Running

## Step 7: Test SSH Connection
```powershell
# Get your computer's IP address
Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -ne "127.0.0.1"}

# Test SSH from another machine or WSL:
# ssh username@your-ip-address
```

## Step 8: Configure SSH (Optional)
SSH config file location: `C:\ProgramData\ssh\sshd_config`

Common configurations:
```
# Allow password authentication
PasswordAuthentication yes

# Change default port (optional)
Port 22

# Allow specific users only
AllowUsers your-username
```

After editing config, restart the service:
```powershell
Restart-Service sshd
```

## Security Notes
- Consider using SSH keys instead of passwords
- Change the default port if exposing to internet
- Use Windows Defender or third-party firewall rules
- Only allow necessary users access

## Test Your Setup
Once enabled, you can test SSH from the K8s AI Project:
1. Use localhost or your laptop's IP as the target host
2. Use your Windows username and password
3. Test the system requirements checker on your own machine!
