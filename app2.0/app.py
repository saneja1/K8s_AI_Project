from flask import Flask, render_template_string, jsonify
import datetime
import subprocess
import json

app = Flask(__name__)

# VM Configuration - from dashboard.py
VM_LIST = [
    {"name": "k8s-master-001", "zone": "us-central1-a", "role": "Master", "internal_ip": "10.128.0.6", "external_ip": "34.69.84.204"},
    {"name": "k8s-worker-01", "zone": "us-central1-a", "role": "Worker", "internal_ip": "10.128.0.7", "external_ip": "34.133.61.216"}
]

# Constants
MIB_PER_GIB = 1024

# Global command logs storage
command_logs = []

def log_command(command, status="Running", details=""):
    """Log a command execution with timestamp."""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = {
        'timestamp': timestamp,
        'command': command,
        'status': status,
        'details': details
    }
    command_logs.append(log_entry)
    
    # Keep only last 50 logs
    if len(command_logs) > 50:
        command_logs[:] = command_logs[-50:]

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

def get_vm_resources(vm_name, zone="us-central1-a"):
    """Get detailed system resources from a VM using SSH."""
    try:
        log_command(f"gcloud compute ssh {vm_name}", "Running", f"Fetching metrics from {vm_name}")
        
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

# HTML template for the dashboard
dashboard_template = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: #333;
        }
        
        .header {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            padding: 15px 0;
            box-shadow: 0 2px 20px rgba(0,0,0,0.1);
            position: sticky;
            top: 0;
            z-index: 100;
        }
        
        .header-content {
            max-width: 1200px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 20px;
        }
        
        .logo {
            font-size: 24px;
            font-weight: bold;
            color: #4a5568;
            display: flex;
            align-items: center;
        }
        
        .logo::before {
            content: "⚙️";
            margin-right: 10px;
            font-size: 28px;
        }
        
        .nav-menu {
            display: flex;
            gap: 20px;
            list-style: none;
        }
        
        .nav-menu a {
            text-decoration: none;
            color: #4a5568;
            font-weight: 500;
            padding: 8px 16px;
            border-radius: 8px;
            transition: all 0.3s ease;
        }
        
        .nav-menu a:hover, .nav-menu a.active {
            background: #667eea;
            color: white;
            transform: translateY(-2px);
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 40px 20px;
        }
        
        .page-title {
            text-align: center;
            color: white;
            font-size: 36px;
            font-weight: 300;
            margin-bottom: 50px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 30px;
            margin-bottom: 40px;
        }
        
        .card {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 30px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            transition: all 0.3s ease;
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        .card:hover {
            transform: translateY(-8px);
            box-shadow: 0 16px 48px rgba(0,0,0,0.15);
        }
        
        .card-icon {
            font-size: 48px;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .card-title {
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 15px;
            color: #2d3748;
            text-align: center;
        }
        
        .card-description {
            color: #718096;
            line-height: 1.6;
            text-align: center;
            margin-bottom: 20px;
        }
        
        .card-button {
            display: block;
            width: 100%;
            padding: 12px 24px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            text-decoration: none;
            border-radius: 8px;
            text-align: center;
            font-weight: 500;
            transition: all 0.3s ease;
            border: none;
            cursor: pointer;
        }
        
        .card-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(102, 126, 234, 0.4);
        }
        
        .status-indicator {
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        
        .status-online { background-color: #48bb78; }
        .status-offline { background-color: #f56565; }
        .status-warning { background-color: #ed8936; }
        
        .footer {
            text-align: center;
            color: rgba(255,255,255,0.8);
            padding: 20px;
            font-size: 14px;
        }
        
        .content-area {
            background: rgba(255, 255, 255, 0.95);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 40px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
            margin-bottom: 30px;
        }
        
        @media (max-width: 768px) {
            .header-content {
                flex-direction: column;
                gap: 15px;
            }
            
            .nav-menu {
                flex-wrap: wrap;
                justify-content: center;
            }
            
            .page-title {
                font-size: 28px;
            }
            
            .dashboard-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="header-content">
            <div class="logo">Kubernetes AI Dashboard</div>
            <nav>
                <ul class="nav-menu">
                    <li><a href="/" class="{{ 'active' if page == 'home' else '' }}">Home</a></li>
                    <li><a href="/k8s-assistant" class="{{ 'active' if page == 'assistant' else '' }}">K8s AI Assistant</a></li>
                    <li><a href="/host-validator" class="{{ 'active' if page == 'validator' else '' }}">Host Validator</a></li>
                    <li><a href="/vm-status" class="{{ 'active' if page == 'vm-status' else '' }}">VM Status</a></li>
                    <li><a href="/pod-monitor" class="{{ 'active' if page == 'pod-monitor' else '' }}">Pod Monitor</a></li>
                </ul>
            </nav>
        </div>
    </header>

    <div class="container">
        {% if page == 'home' %}
        <h1 class="page-title">Kubernetes AI Dashboard</h1>
        <div class="dashboard-grid">
            <div class="card">
                <div class="card-icon">🤖</div>
                <h3 class="card-title">K8s AI Assistant</h3>
                <p class="card-description">Intelligent AI-powered assistant for Kubernetes cluster management, troubleshooting, and optimization.</p>
                <a href="/k8s-assistant" class="card-button">Launch Assistant</a>
            </div>
            
            <div class="card">
                <div class="card-icon">✅</div>
                <h3 class="card-title">Host Validator</h3>
                <p class="card-description">Validate and verify host systems for Kubernetes compatibility and readiness requirements.</p>
                <a href="/host-validator" class="card-button">Validate Hosts</a>
            </div>
            
            <div class="card">
                <div class="card-icon">🖥️</div>
                <h3 class="card-title">VM Status</h3>
                <p class="card-description">Monitor virtual machine health, resources, and status across your infrastructure.</p>
                <a href="/vm-status" class="card-button">View VM Status</a>
            </div>
            
            <div class="card">
                <div class="card-icon">📊</div>
                <h3 class="card-title">Pod Monitor</h3>
                <p class="card-description">Real-time monitoring and management of Kubernetes pods, deployments, and services.</p>
                <a href="/pod-monitor" class="card-button">Monitor Pods</a>
            </div>
        </div>
        {% else %}
        <h1 class="page-title">{{ page_title }}</h1>
        <div class="content-area">
            {{ content | safe }}
        </div>
        {% endif %}
    </div>

    <footer class="footer">
        <p>&copy; {{ current_year }} Kubernetes AI Dashboard | Last updated: {{ current_time }}</p>
    </footer>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(dashboard_template, 
                                title="Kubernetes AI Dashboard",
                                page="home",
                                current_year=datetime.datetime.now().year,
                                current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/k8s-assistant')
def k8s_assistant():
    content = """
    <h2>🤖 Kubernetes AI Assistant</h2>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 30px;">
        <div style="padding: 20px; background: #f7fafc; border-radius: 8px; border-left: 4px solid #667eea;">
            <h3>Cluster Analysis</h3>
            <p>Get intelligent insights about your Kubernetes cluster health and performance.</p>
            <div style="margin-top: 15px;">
                <span class="status-indicator status-online"></span>AI Analysis Ready
            </div>
        </div>
        <div style="padding: 20px; background: #f7fafc; border-radius: 8px; border-left: 4px solid #48bb78;">
            <h3>Smart Troubleshooting</h3>
            <p>AI-powered problem detection and resolution recommendations.</p>
            <div style="margin-top: 15px;">
                <span class="status-indicator status-online"></span>Diagnostics Active
            </div>
        </div>
        <div style="padding: 20px; background: #f7fafc; border-radius: 8px; border-left: 4px solid #ed8936;">
            <h3>Resource Optimization</h3>
            <p>Get recommendations for optimal resource allocation and scaling.</p>
            <div style="margin-top: 15px;">
                <span class="status-indicator status-warning"></span>Monitoring
            </div>
        </div>
    </div>
    <div style="margin-top: 30px; padding: 20px; background: #e6fffa; border-radius: 8px;">
        <h3>Quick Actions</h3>
        <div style="display: flex; gap: 15px; margin-top: 15px; flex-wrap: wrap;">
            <button class="card-button" style="width: auto; padding: 10px 20px;">Analyze Cluster</button>
            <button class="card-button" style="width: auto; padding: 10px 20px;">Check Pod Health</button>
            <button class="card-button" style="width: auto; padding: 10px 20px;">Resource Report</button>
        </div>
    </div>
    """
    return render_template_string(dashboard_template,
                                title="K8s AI Assistant - Kubernetes AI Dashboard",
                                page="assistant",
                                page_title="K8s AI Assistant",
                                content=content,
                                current_year=datetime.datetime.now().year,
                                current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/host-validator')
def host_validator():
    content = """
    <h2>✅ Host Validator</h2>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-top: 30px;">
        <div style="padding: 20px; background: #f0fff4; border-radius: 8px; border: 1px solid #9ae6b4;">
            <h3>System Requirements</h3>
            <ul style="list-style: none; padding: 0; margin-top: 15px;">
                <li style="margin: 8px 0;"><span class="status-indicator status-online"></span>CPU: 2+ cores</li>
                <li style="margin: 8px 0;"><span class="status-indicator status-online"></span>RAM: 4GB+ available</li>
                <li style="margin: 8px 0;"><span class="status-indicator status-online"></span>Disk: 20GB+ free</li>
                <li style="margin: 8px 0;"><span class="status-indicator status-online"></span>Network: Internet access</li>
            </ul>
        </div>
        <div style="padding: 20px; background: #fffaf0; border-radius: 8px; border: 1px solid #fbd38d;">
            <h3>Validation Status</h3>
            <div style="margin-top: 15px;">
                <div style="margin: 10px 0;">
                    <strong>Last Check:</strong> 2024-10-25 14:30:00
                </div>
                <div style="margin: 10px 0;">
                    <span class="status-indicator status-warning"></span>Pending Validation
                </div>
                <button class="card-button" style="margin-top: 15px; width: 100%;">Run Validation</button>
            </div>
        </div>
    </div>
    <div style="margin-top: 30px; padding: 25px; background: #f7fafc; border-radius: 8px;">
        <h3>Host Configuration</h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-top: 20px;">
            <input type="text" placeholder="Host IP Address" style="padding: 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px;">
            <input type="text" placeholder="SSH Username" style="padding: 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px;">
            <input type="password" placeholder="SSH Password" style="padding: 12px; border: 1px solid #e2e8f0; border-radius: 6px; font-size: 14px;">
            <button class="card-button">Validate Host</button>
        </div>
    </div>
    """
    return render_template_string(dashboard_template,
                                title="Host Validator - Kubernetes AI Dashboard",
                                page="validator",
                                page_title="Host Validator",
                                content=content,
                                current_year=datetime.datetime.now().year,
                                current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/vm-status')
def vm_status():
    # Get VM data
    vm_table_data = []
    total_vms = len(VM_LIST)
    active_vms = 0
    error_vms = 0
    
    for vm_config in VM_LIST:
        vm_resources = get_vm_resources(vm_config['name'], vm_config['zone'])
        
        if 'error' not in vm_resources:
            active_vms += 1
            cpu_count_val = parse_int(vm_resources.get('CPU_COUNT'))
            cpu_idle_percent = parse_float(vm_resources.get('CPU_IDLE_PERCENT'))
            cpu_usage_val = None
            if cpu_idle_percent is not None:
                cpu_usage_val = 100.0 - cpu_idle_percent

            mem_total_mib = parse_int(vm_resources.get('MEM_TOTAL_MIB'))
            mem_used_mib = parse_int(vm_resources.get('MEM_USED_MIB'))
            mem_free_mib = parse_int(vm_resources.get('MEM_FREE_MIB'))

            disk_total_mib = parse_int(vm_resources.get('DISK_TOTAL_MIB'))
            disk_used_mib = parse_int(vm_resources.get('DISK_USED_MIB'))

            vm_data = {
                'name': vm_config['name'],
                'role': vm_config['role'],
                'status': 'Running',
                'internal_ip': vm_config['internal_ip'],
                'external_ip': vm_config['external_ip'],
                'cpu_cores': cpu_count_val if cpu_count_val is not None else 'N/A',
                'cpu_usage': format_percent(cpu_usage_val),
                'memory_total': format_gib(mem_total_mib),
                'memory_used': format_gib(mem_used_mib),
                'memory_free': format_gib(mem_free_mib),
                'disk_total': format_gib(disk_total_mib),
                'disk_used': format_gib(disk_used_mib)
            }
        else:
            error_vms += 1
            vm_data = {
                'name': vm_config['name'],
                'role': vm_config['role'],
                'status': 'Error',
                'internal_ip': vm_config['internal_ip'],
                'external_ip': vm_config['external_ip'],
                'cpu_cores': 'Error',
                'cpu_usage': 'Error',
                'memory_total': 'Error',
                'memory_used': 'Error',
                'memory_free': 'Error',
                'disk_total': 'Error',
                'disk_used': 'Error',
                'error': vm_resources.get('error', 'Unknown error')
            }
        
        vm_table_data.append(vm_data)
    
    # Generate table rows
    table_rows = ""
    for vm in vm_table_data:
        status_indicator = 'status-online' if vm['status'] == 'Running' else 'status-offline'
        memory_display = f"{vm['memory_used']}GB / {vm['memory_total']}GB" if vm['memory_used'] != 'Error' else 'Error'
        
        table_rows += f"""
        <tr>
            <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;"><strong>{vm['name']}</strong></td>
            <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;"><span class="status-indicator {status_indicator}"></span>{vm['status']}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">{vm['cpu_usage']}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">{memory_display}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">{vm['role']}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">{vm['internal_ip']}</td>
            <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">{vm['external_ip']}</td>
        </tr>"""
    
    content = f"""
    <h2>🖥️ Virtual Machine Status</h2>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0;">
        <div style="padding: 20px; background: #f0fff4; border-radius: 8px; text-align: center;">
            <h3 style="color: #38a169;">Active VMs</h3>
            <div style="font-size: 36px; font-weight: bold; color: #38a169; margin: 10px 0;">{active_vms}</div>
            <p style="color: #718096;">Currently Running</p>
        </div>
        <div style="padding: 20px; background: #fed7d7; border-radius: 8px; text-align: center;">
            <h3 style="color: #e53e3e;">Error VMs</h3>
            <div style="font-size: 36px; font-weight: bold; color: #e53e3e; margin: 10px 0;">{error_vms}</div>
            <p style="color: #718096;">Connection Issues</p>
        </div>
        <div style="padding: 20px; background: #ebf8ff; border-radius: 8px; text-align: center;">
            <h3 style="color: #3182ce;">Total VMs</h3>
            <div style="font-size: 36px; font-weight: bold; color: #3182ce; margin: 10px 0;">{total_vms}</div>
            <p style="color: #718096;">Configured</p>
        </div>
    </div>
    
    <div style="background: white; border-radius: 8px; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
        <h3>VM Details</h3>
        <div style="overflow-x: auto; margin-top: 20px;">
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background: #f7fafc;">
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">VM Name</th>
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">Status</th>
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">CPU Usage</th>
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">Memory</th>
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">Role</th>
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">Internal IP</th>
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">External IP</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
        </div>
        <div style="margin-top: 20px; display: flex; gap: 15px; flex-wrap: wrap;">
            <button class="card-button" style="width: auto; padding: 10px 20px;" onclick="location.reload()">Refresh Status</button>
            <button class="card-button" style="width: auto; padding: 10px 20px;" onclick="downloadVMReport()">Export Report</button>
            <button class="card-button" style="width: auto; padding: 10px 20px;" onclick="clearLogs()">Clear Logs</button>
        </div>
    </div>
    
    <!-- Command Execution Logs Section -->
    <div style="background: white; border-radius: 12px; padding: 30px; margin-top: 30px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
        <div style="display: flex; align-items: center; margin-bottom: 20px;">
            <h3 style="margin: 0; color: #2d3748; display: flex; align-items: center; gap: 10px;">
                <span style="font-size: 1.5rem;">📋</span>
                Command Execution Logs
            </h3>
            <div style="margin-left: auto; display: flex; align-items: center; gap: 15px;">
                <div style="background: #f0f9ff; padding: 8px 16px; border-radius: 20px; font-size: 0.9rem; color: #0369a1;">
                    <strong>Total Commands:</strong> {len(command_logs)}
                </div>
                <div style="background: #f0fdf4; padding: 8px 16px; border-radius: 20px; font-size: 0.9rem; color: #15803d;">
                    <strong>Updated:</strong> {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                </div>
            </div>
        </div>
        
        <div style="overflow-x: auto; border-radius: 8px; border: 1px solid #e5e7eb;">"""

    # Generate logs table
    if command_logs:
        logs_html = """
            <table style="width: 100%; border-collapse: collapse; font-size: 0.9rem;">
                <thead>
                    <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
                        <th style="padding: 12px 16px; text-align: left; font-weight: 600;">Timestamp</th>
                        <th style="padding: 12px 16px; text-align: left; font-weight: 600;">Command</th>
                        <th style="padding: 12px 16px; text-align: center; font-weight: 600;">Status</th>
                        <th style="padding: 12px 16px; text-align: left; font-weight: 600;">Details</th>
                    </tr>
                </thead>
                <tbody>"""
        
        # Reverse logs to show newest first
        for i, log in enumerate(reversed(command_logs)):
            # Determine row styling based on status
            if log['status'] == '✅ Success':
                row_bg = '#f0fdf4' if i % 2 == 0 else '#dcfce7'
                status_color = '#15803d'
                status_bg = '#bbf7d0'
            elif log['status'] == '❌ Failed':
                row_bg = '#fef2f2' if i % 2 == 0 else '#fee2e2'
                status_color = '#dc2626'
                status_bg = '#fecaca'
            else:  # Running
                row_bg = '#fffbeb' if i % 2 == 0 else '#fef3c7'
                status_color = '#d97706'
                status_bg = '#fed7aa'
            
            logs_html += f"""
                    <tr style="background: {row_bg}; transition: all 0.2s ease;">
                        <td style="padding: 12px 16px; color: #6b7280; font-family: monospace;">{log['timestamp']}</td>
                        <td style="padding: 12px 16px; color: #374151; font-family: monospace; font-weight: 500;">{log['command']}</td>
                        <td style="padding: 12px 16px; text-align: center;">
                            <span style="display: inline-block; padding: 4px 12px; border-radius: 20px; background: {status_bg}; color: {status_color}; font-weight: 600; font-size: 0.8rem;">
                                {log['status']}
                            </span>
                        </td>
                        <td style="padding: 12px 16px; color: #6b7280; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="{log['details']}">{log['details']}</td>
                    </tr>"""
        
        logs_html += """
                </tbody>
            </table>"""
    else:
        logs_html = """
            <div style="text-align: center; padding: 40px; color: #6b7280;">
                <div style="font-size: 3rem; margin-bottom: 16px;">📝</div>
                <h4 style="color: #9ca3af; margin: 0;">No commands executed yet</h4>
                <p style="color: #d1d5db; margin: 8px 0 0 0;">Command logs will appear here when VM status is refreshed</p>
            </div>"""
    
    content += logs_html + """
        </div>
    </div>
    
    <script>
    function downloadVMReport() {{
        const data = {json.dumps(vm_table_data)};
        const blob = new Blob([JSON.stringify(data, null, 2)], {{type: 'application/json'}});
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'vm-status-report-{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}.json';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }}
    
    function clearLogs() {{
        fetch('/api/clear-logs', {{method: 'POST'}})
            .then(() => location.reload())
            .catch(err => console.error('Failed to clear logs:', err));
    }}
    </script>
    """
    return render_template_string(dashboard_template,
                                title="VM Status - Kubernetes AI Dashboard",
                                page="vm-status",
                                page_title="Virtual Machine Status",
                                content=content,
                                current_year=datetime.datetime.now().year,
                                current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/pod-monitor')
def pod_monitor():
    content = """
    <h2>📊 Pod Monitor</h2>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0;">
        <div style="padding: 20px; background: #f0fff4; border-radius: 8px; text-align: center;">
            <h4 style="color: #38a169;">Running Pods</h4>
            <div style="font-size: 28px; font-weight: bold; color: #38a169;">12</div>
        </div>
        <div style="padding: 20px; background: #fffaf0; border-radius: 8px; text-align: center;">
            <h4 style="color: #d69e2e;">Pending Pods</h4>
            <div style="font-size: 28px; font-weight: bold; color: #d69e2e;">2</div>
        </div>
        <div style="padding: 20px; background: #fed7d7; border-radius: 8px; text-align: center;">
            <h4 style="color: #e53e3e;">Failed Pods</h4>
            <div style="font-size: 28px; font-weight: bold; color: #e53e3e;">0</div>
        </div>
        <div style="padding: 20px; background: #ebf8ff; border-radius: 8px; text-align: center;">
            <h4 style="color: #3182ce;">Total Pods</h4>
            <div style="font-size: 28px; font-weight: bold; color: #3182ce;">14</div>
        </div>
    </div>
    
    <div style="display: grid; grid-template-columns: 1fr 300px; gap: 20px; margin-top: 30px;">
        <div style="background: white; border-radius: 8px; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <h3>Pod Status</h3>
            <div style="overflow-x: auto; margin-top: 20px;">
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <thead>
                        <tr style="background: #f7fafc;">
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #e2e8f0;">Pod Name</th>
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #e2e8f0;">Namespace</th>
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #e2e8f0;">Status</th>
                            <th style="padding: 10px; text-align: left; border-bottom: 2px solid #e2e8f0;">Restarts</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">nginx-deployment-1</td>
                            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">default</td>
                            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;"><span class="status-indicator status-online"></span>Running</td>
                            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">0</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">api-service-2</td>
                            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">production</td>
                            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;"><span class="status-indicator status-online"></span>Running</td>
                            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">1</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">database-pod</td>
                            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">production</td>
                            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;"><span class="status-indicator status-warning"></span>Pending</td>
                            <td style="padding: 10px; border-bottom: 1px solid #e2e8f0;">0</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </div>
        
        <div style="background: white; border-radius: 8px; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
            <h3>Quick Actions</h3>
            <div style="display: flex; flex-direction: column; gap: 10px; margin-top: 20px;">
                <button class="card-button">View All Pods</button>
                <button class="card-button">Check Logs</button>
                <button class="card-button">Restart Failed</button>
                <button class="card-button">Scale Deployment</button>
            </div>
            
            <div style="margin-top: 30px; padding: 15px; background: #f7fafc; border-radius: 6px;">
                <h4>Resource Usage</h4>
                <div style="margin-top: 10px; font-size: 14px;">
                    <div>CPU: 2.4 / 8 cores</div>
                    <div>Memory: 6.2 / 16 GB</div>
                    <div>Storage: 45 / 100 GB</div>
                </div>
            </div>
        </div>
    </div>
    """
    return render_template_string(dashboard_template,
                                title="Pod Monitor - Kubernetes AI Dashboard",
                                page="pod-monitor",
                                page_title="Pod Monitor",
                                content=content,
                                current_year=datetime.datetime.now().year,
                                current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/api/vm-data')
def get_vm_data():
    """API endpoint to get VM data as JSON for AJAX refresh."""
    vm_data = []
    
    for vm_config in VM_LIST:
        vm_resources = get_vm_resources(vm_config['name'], vm_config['zone'])
        
        if 'error' not in vm_resources:
            cpu_count_val = parse_int(vm_resources.get('CPU_COUNT'))
            cpu_idle_percent = parse_float(vm_resources.get('CPU_IDLE_PERCENT'))
            cpu_usage_val = None
            if cpu_idle_percent is not None:
                cpu_usage_val = 100.0 - cpu_idle_percent

            mem_total_mib = parse_int(vm_resources.get('MEM_TOTAL_MIB'))
            mem_used_mib = parse_int(vm_resources.get('MEM_USED_MIB'))
            disk_total_mib = parse_int(vm_resources.get('DISK_TOTAL_MIB'))
            disk_used_mib = parse_int(vm_resources.get('DISK_USED_MIB'))

            vm_info = {
                'name': vm_config['name'],
                'role': vm_config['role'],
                'status': 'Running',
                'zone': vm_config['zone'],
                'internal_ip': vm_config['internal_ip'],
                'external_ip': vm_config['external_ip'],
                'cpu_cores': cpu_count_val,
                'cpu_usage_percent': cpu_usage_val,
                'memory_total_gib': mem_total_mib / MIB_PER_GIB if mem_total_mib else None,
                'memory_used_gib': mem_used_mib / MIB_PER_GIB if mem_used_mib else None,
                'disk_total_gib': disk_total_mib / MIB_PER_GIB if disk_total_mib else None,
                'disk_used_gib': disk_used_mib / MIB_PER_GIB if disk_used_mib else None,
                'timestamp': datetime.datetime.now().isoformat()
            }
        else:
            vm_info = {
                'name': vm_config['name'],
                'role': vm_config['role'],
                'status': 'Error',
                'zone': vm_config['zone'],
                'internal_ip': vm_config['internal_ip'],
                'external_ip': vm_config['external_ip'],
                'error': vm_resources.get('error', 'Unknown error'),
                'timestamp': datetime.datetime.now().isoformat()
            }
        
        vm_data.append(vm_info)
    
    return jsonify({
        'vms': vm_data,
        'summary': {
            'total': len(VM_LIST),
            'active': len([vm for vm in vm_data if vm['status'] == 'Running']),
            'error': len([vm for vm in vm_data if vm['status'] == 'Error'])
        },
        'last_updated': datetime.datetime.now().isoformat()
    })

@app.route('/api/clear-logs', methods=['POST'])
def clear_logs():
    """API endpoint to clear command logs."""
    global command_logs
    command_logs.clear()
    return jsonify({'status': 'success', 'message': 'Logs cleared'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000, debug=True)
