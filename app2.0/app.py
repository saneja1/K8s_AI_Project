from flask import Flask, render_template_string, jsonify, request
import datetime
import subprocess
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import K8s Agent
import sys
sys.path.append(os.path.dirname(__file__))
from agents.k8s_agent import ask_k8s_agent

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

# Global cache for cluster context
cluster_cache = {
    'data': None,
    'timestamp': None,
    'cache_duration': 30  # Cache for 30 seconds
}

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

def _try_answer_from_client_cache(message, client_cache):
    """
    Try to answer simple questions using client-side cached data from other tabs.
    Returns None if cannot answer from cache.
    """
    if not client_cache:
        return None
    
    msg_lower = message.lower()
    
    # Check for pod count questions
    if any(phrase in msg_lower for phrase in ['how many pod', 'count pod', 'number of pod', 'list pod', 'show pod']):
        pods_data = client_cache.get('pods')
        if pods_data and isinstance(pods_data, list):
            pod_count = len(pods_data)
            running = sum(1 for p in pods_data if p.get('status') == 'Running')
            return f"There are <strong>{pod_count} pods</strong> in the cluster.<br><br>{running} are running, {pod_count - running} are in other states.<br><br><em>⚡ Instant answer from Pod Monitor tab data</em>"
    
    # Check for node questions
    if any(phrase in msg_lower for phrase in ['how many node', 'count node', 'show node', 'list node', 'cluster node']):
        nodes_data = client_cache.get('nodes')
        if nodes_data and isinstance(nodes_data, list):
            node_count = len(nodes_data)
            ready = sum(1 for n in nodes_data if n.get('status') == 'Ready')
            return f"There are <strong>{node_count} nodes</strong> in the cluster.<br><br>{ready} are Ready, {node_count - ready} have issues.<br><br><em>⚡ Instant answer from VM Status tab data</em>"
    
    # Cannot answer from cache
    return None

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

def get_pods_info():
    """Get information about all pods in the cluster."""
    fetch_time = datetime.datetime.now()
    try:
        log_command("kubectl get pods --all-namespaces -o json", "Running", "Fetching pod data from cluster via SSH")
        
        # Execute kubectl on master node via SSH
        full_command = "export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl get pods --all-namespaces -o json"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "k8s-master-001",
            "--zone=us-central1-a", 
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15)
        
        pods_data = []
        if result.returncode == 0:
            pods_json = json.loads(result.stdout)
            pod_count = len(pods_json.get('items', []))
            log_command("kubectl get pods --all-namespaces", "✅ Success", f"Found {pod_count} pods")
            
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
        
        return pods_data, fetch_time
    except Exception as e:
        log_command("kubectl get pods", "❌ Failed", f"Exception: {str(e)}")
        return [], fetch_time

def execute_kubectl_command(command, timeout=10):
    """Execute kubectl command on master node via SSH."""
    try:
        log_command(f"kubectl {command}", "Running", f"Executing kubectl command on master node")
        
        # Execute kubectl on the master node via SSH
        full_command = f"export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl {command}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "k8s-master-001",
            "--zone=us-central1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=timeout)
        
        if result.returncode == 0:
            log_command(f"kubectl {command}", "✅ Success", f"Command completed successfully")
            return {'success': True, 'output': result.stdout}
        else:
            error_msg = result.stderr[:200] if result.stderr else "Unknown error"
            log_command(f"kubectl {command}", "❌ Failed", f"Error: {error_msg}")
            return {'success': False, 'error': error_msg}
            
    except subprocess.TimeoutExpired:
        log_command(f"kubectl {command}", "❌ Failed", "Timeout")
        return {'success': False, 'error': 'Command timed out'}
    except Exception as e:
        log_command(f"kubectl {command}", "❌ Failed", f"Exception: {str(e)}")
        return {'success': False, 'error': str(e)}

def format_time_ago(timestamp):
    """Format datetime as 'X seconds/minutes ago'."""
    if timestamp is None:
        return 'Never'
    elapsed = (datetime.datetime.now() - timestamp).total_seconds()
    if elapsed < 60:
        return f"{int(elapsed)}s ago"
    elif elapsed < 3600:
        return f"{int(elapsed / 60)}m ago"
    else:
        return f"{int(elapsed / 3600)}h ago"

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
        
        /* Light Theme (Default) */
        :root {
            --bg-gradient-start: #667eea;
            --bg-gradient-end: #764ba2;
            --header-bg: rgba(255, 255, 255, 0.95);
            --header-shadow: rgba(0, 0, 0, 0.1);
            --text-primary: #333;
            --text-secondary: #555;
            --card-bg: rgba(255, 255, 255, 0.95);
            --content-area-bg: rgba(255, 255, 255, 0.95);
            --card-title: #2d3748;
            --card-description: #718096;
            --table-text: #2d3748;
            --table-border: #e2e8f0;
        }
        
        /* Dark Theme */
        body.dark-theme {
            --bg-gradient-start: #2d3748;
            --bg-gradient-end: #1a202c;
            --header-bg: rgba(45, 55, 72, 0.95);
            --header-shadow: rgba(0, 0, 0, 0.5);
            --text-primary: #f7fafc;
            --text-secondary: #e2e8f0;
            --card-bg: rgba(45, 55, 72, 0.95);
            --content-area-bg: rgba(45, 55, 72, 0.95);
            --card-title: #f7fafc;
            --card-description: #cbd5e1;
            --table-text: #f7fafc;
            --table-border: #4a5568;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, var(--bg-gradient-start) 0%, var(--bg-gradient-end) 100%);
            min-height: 100vh;
            transition: all 0.3s ease;
        }
        
        /* Force black text for all content except nav menu and page headers */
        .content-area, .content-area * {
            color: #000000 !important;
        }
        
        /* Ensure nav menu uses theme colors */
        .nav-menu, .nav-menu * {
            color: var(--text-primary) !important;
        }
        
        /* Page headers always white regardless of theme - stronger override */
        .content-area > div > div[style*="linear-gradient"],
        .content-area > div > div[style*="linear-gradient"] *,
        .content-area div[style*="background: linear-gradient"],
        .content-area div[style*="background: linear-gradient"] * {
            color: white !important;
        }
        
        /* Table headers with gradient background always white */
        table thead tr[style*="linear-gradient"] th,
        table thead tr[style*="linear-gradient"] * {
            color: white !important;
        }
        
        .header {
            background: var(--header-bg);
            backdrop-filter: blur(10px);
            padding: 15px 0;
            box-shadow: 0 2px 20px var(--header-shadow);
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
            color: var(--text-primary);
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
            color: var(--text-primary);
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
            background: var(--card-bg);
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
            color: var(--card-title);
            text-align: center;
        }
        
        .card-description {
            color: var(--card-description);
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
            background: var(--content-area-bg);
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
            <button id="themeToggle" onclick="toggleTheme()" style="
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                border: none;
                color: white;
                padding: 8px 16px;
                border-radius: 20px;
                cursor: pointer;
                font-weight: 500;
                font-size: 0.9rem;
                display: flex;
                align-items: center;
                gap: 8px;
                transition: all 0.3s ease;
                margin-left: auto;
            " onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
                <span id="themeIcon">🌙</span>
                <span id="themeText">Dark</span>
            </button>
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
    
    <script>
    // Theme toggle functionality
    function toggleTheme() {
        const body = document.body;
        const themeIcon = document.getElementById('themeIcon');
        const themeText = document.getElementById('themeText');
        
        body.classList.toggle('dark-theme');
        
        if (body.classList.contains('dark-theme')) {
            themeIcon.textContent = '☀️';
            themeText.textContent = 'Light';
            localStorage.setItem('theme', 'dark');
        } else {
            themeIcon.textContent = '🌙';
            themeText.textContent = 'Dark';
            localStorage.setItem('theme', 'light');
        }
    }
    
    // Load saved theme on page load
    document.addEventListener('DOMContentLoaded', function() {
        const savedTheme = localStorage.getItem('theme');
        const body = document.body;
        const themeIcon = document.getElementById('themeIcon');
        const themeText = document.getElementById('themeText');
        
        if (savedTheme === 'dark') {
            body.classList.add('dark-theme');
            themeIcon.textContent = '☀️';
            themeText.textContent = 'Light';
        }
    });
    </script>
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
    <!-- ChatGPT-style AI Assistant Interface -->
    <div style="height: calc(100vh - 60px); display: flex; flex-direction: column; background: #ffffff; box-shadow: 0 4px 12px rgba(0,0,0,0.1); overflow: hidden; margin: -120px -40px -70px -40px;">
        
        <!-- Chat Header -->
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; text-align: center;">
            <h2 style="margin: 0; font-size: 1.5rem; font-weight: 600; color: white;">🤖 Kubernetes AI Assistant</h2>
            <p style="margin: 8px 0 0 0; opacity: 0.9; font-size: 0.95rem; color: white;">Ask me anything about your Kubernetes cluster</p>
        </div>
        
        <!-- Chat Messages Container -->
        <div id="chatMessages" style="flex: 1; overflow-y: auto; padding: 20px; background: #f8fafc; display: flex; flex-direction: column; gap: 16px;">
            
            <!-- Welcome Message -->
            <div style="display: flex; align-items: flex-start; gap: 12px;">
                <div style="width: 36px; height: 36px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                    <span style="color: white; font-size: 1.2rem;">🤖</span>
                </div>
                <div style="background: white; padding: 16px 20px; border-radius: 18px 18px 18px 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); max-width: 80%; line-height: 1.5;">
                    <p style="margin: 0; color: #2d3748;">Hello! I'm your Kubernetes AI Assistant. I can help you with:</p>
                    <ul style="margin: 12px 0 0 0; padding-left: 20px; color: #4a5568;">
                        <li>Cluster analysis and troubleshooting</li>
                        <li>Pod and deployment management</li>
                        <li>Resource optimization recommendations</li>
                        <li>Best practices and configurations</li>
                    </ul>
                    <p style="margin: 12px 0 0 0; color: #2d3748;">What would you like to know?</p>
                </div>
            </div>
            
        </div>
        
        <!-- Chat Input Area -->
        <div style="background: white; border-top: 1px solid #e2e8f0; padding: 20px;">
            <div style="display: flex; gap: 12px; align-items: flex-end;">
                <div style="flex: 1; position: relative;">
                    <textarea 
                        id="chatInput" 
                        placeholder="Ask about your Kubernetes cluster..." 
                        style="
                            width: 100%; 
                            min-height: 50px; 
                            max-height: 120px; 
                            padding: 12px 50px 12px 16px; 
                            border: 2px solid #e2e8f0; 
                            border-radius: 25px; 
                            resize: none; 
                            outline: none; 
                            font-family: inherit; 
                            font-size: 0.95rem; 
                            line-height: 1.4;
                            background: #f8fafc;
                            transition: all 0.2s ease;
                        "
                        onkeydown="handleKeyDown(event)"
                        oninput="autoResize(this)"
                        onfocus="this.style.background='white'; this.style.borderColor='#667eea';"
                        onblur="this.style.background='#f8fafc'; this.style.borderColor='#e2e8f0';"
                    ></textarea>
                    <button 
                        id="sendButton"
                        onclick="sendMessage()" 
                        style="
                            position: absolute; 
                            right: 8px; 
                            bottom: 8px; 
                            width: 36px; 
                            height: 36px; 
                            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            border: none; 
                            border-radius: 50%; 
                            color: white; 
                            cursor: pointer; 
                            display: flex; 
                            align-items: center; 
                            justify-content: center; 
                            transition: all 0.2s ease;
                            opacity: 0.7;
                        "
                        onmouseover="this.style.opacity='1'; this.style.transform='scale(1.05)'"
                        onmouseout="this.style.opacity='0.7'; this.style.transform='scale(1)'"
                        disabled
                    >
                        <span style="font-size: 1.1rem;">↗</span>
                    </button>
                </div>
            </div>
            
            <!-- Typing Indicator (hidden by default) -->
            <div id="typingIndicator" style="display: none; margin-top: 12px; padding-left: 48px;">
                <div style="display: flex; align-items: center; gap: 8px; color: #6b7280; font-size: 0.9rem;">
                    <div style="display: flex; gap: 2px;">
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                        <div class="typing-dot"></div>
                    </div>
                    <span>AI is thinking...</span>
                </div>
            </div>
        </div>
        
    </div>
    
    <style>
    /* Typing indicator animation */
    .typing-dot {
        width: 6px;
        height: 6px;
        background: #667eea;
        border-radius: 50%;
        animation: typing 1.4s infinite ease-in-out;
    }
    
    .typing-dot:nth-child(1) { animation-delay: -0.32s; }
    .typing-dot:nth-child(2) { animation-delay: -0.16s; }
    
    @keyframes typing {
        0%, 80%, 100% { 
            transform: scale(0.8);
            opacity: 0.5;
        }
        40% { 
            transform: scale(1);
            opacity: 1;
        }
    }
    
    /* Chat message animations */
    .message-fade-in {
        animation: fadeInUp 0.3s ease-out;
    }
    
    @keyframes fadeInUp {
        from {
            opacity: 0;
            transform: translateY(10px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    /* Scrollbar styling */
    #chatMessages::-webkit-scrollbar {
        width: 6px;
    }
    
    #chatMessages::-webkit-scrollbar-track {
        background: #f1f5f9;
        border-radius: 3px;
    }
    
    #chatMessages::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 3px;
    }
    
    #chatMessages::-webkit-scrollbar-thumb:hover {
        background: #94a3b8;
    }
    </style>
    
    <script>
    let isWaitingForResponse = false;
    
    // Get client-side cached data from localStorage (shared across tabs)
    function getClientCacheData() {
        try {
            const cache = {};
            
            // Get pods data from Pod Monitor tab
            const podsCache = localStorage.getItem('k8s_pods_cache');
            if (podsCache) {
                const parsed = JSON.parse(podsCache);
                // Check if cache is fresh (< 2 minutes old)
                if (parsed.timestamp && (Date.now() - parsed.timestamp) < 120000) {
                    cache.pods = parsed.data;
                }
            }
            
            // Get nodes data from VM Status tab
            const nodesCache = localStorage.getItem('k8s_nodes_cache');
            if (nodesCache) {
                const parsed = JSON.parse(nodesCache);
                if (parsed.timestamp && (Date.now() - parsed.timestamp) < 120000) {
                    cache.nodes = parsed.data;
                }
            }
            
            return cache;
        } catch (e) {
            console.error('Error reading client cache:', e);
            return {};
        }
    }
    
    // Auto-resize textarea
    function autoResize(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
        
        // Enable/disable send button based on content
        const sendButton = document.getElementById('sendButton');
        const hasContent = textarea.value.trim().length > 0;
        sendButton.disabled = !hasContent || isWaitingForResponse;
        sendButton.style.opacity = (hasContent && !isWaitingForResponse) ? '1' : '0.7';
    }
    
    // Handle Enter key
    function handleKeyDown(event) {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            sendMessage();
        }
    }
    
    // Send message function
    function sendMessage() {
        const input = document.getElementById('chatInput');
        const message = input.value.trim();
        
        if (!message || isWaitingForResponse) return;
        
        // Add user message to chat
        addMessage(message, 'user');
        
        // Clear input and reset height
        input.value = '';
        input.style.height = '50px';
        
        // Show typing indicator
        showTypingIndicator();
        
        // Disable input during response
        isWaitingForResponse = true;
        input.disabled = true;
        document.getElementById('sendButton').disabled = true;
        document.getElementById('sendButton').style.opacity = '0.5';
        
        // Send to API with client-side cache data
        fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                message: message,
                model: 'claude',
                clientCache: getClientCacheData()  // Send cached data from other tabs
            })
        })
        .then(response => response.json())
        .then(data => {
            hideTypingIndicator();
            
            if (data.success) {
                addMessage(data.response, 'assistant');
            } else {
                addMessage('Error: ' + (data.error || 'Failed to get response'), 'assistant');
            }
            
            // Re-enable input
            isWaitingForResponse = false;
            input.disabled = false;
            input.focus();
            autoResize(input);
        })
        .catch(error => {
            hideTypingIndicator();
            addMessage('Error: ' + error.message, 'assistant');
            
            // Re-enable input
            isWaitingForResponse = false;
            input.disabled = false;
            input.focus();
            autoResize(input);
        });
    }
    
    // Add message to chat
    function addMessage(text, sender) {
        const chatMessages = document.getElementById('chatMessages');
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message-fade-in';
        
        if (sender === 'user') {
            messageDiv.innerHTML = `
                <div style="display: flex; align-items: flex-start; gap: 12px; justify-content: flex-end;">
                    <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 16px 20px; border-radius: 18px 18px 4px 18px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); max-width: 80%; line-height: 1.5;">
                        <p style="margin: 0;">${text}</p>
                    </div>
                    <div style="width: 36px; height: 36px; background: #e2e8f0; border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                        <span style="color: #4a5568; font-size: 1.2rem;">👤</span>
                    </div>
                </div>
            `;
        } else {
            messageDiv.innerHTML = `
                <div style="display: flex; align-items: flex-start; gap: 12px;">
                    <div style="width: 36px; height: 36px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 50%; display: flex; align-items: center; justify-content: center; flex-shrink: 0;">
                        <span style="color: white; font-size: 1.2rem;">🤖</span>
                    </div>
                    <div style="background: white; padding: 16px 20px; border-radius: 18px 18px 18px 4px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); max-width: 80%; line-height: 1.5;">
                        <p style="margin: 0; color: #2d3748;">${text}</p>
                    </div>
                </div>
            `;
        }
        
        chatMessages.appendChild(messageDiv);
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }
    
    // Show typing indicator
    function showTypingIndicator() {
        document.getElementById('typingIndicator').style.display = 'block';
    }
    
    // Hide typing indicator
    function hideTypingIndicator() {
        document.getElementById('typingIndicator').style.display = 'none';
    }
    
    // Initialize
    document.addEventListener('DOMContentLoaded', function() {
        document.getElementById('chatInput').focus();
    });
    </script>
    """
    return render_template_string(dashboard_template,
                                title="K8s AI Assistant - Kubernetes AI Dashboard",
                                page="assistant",
                                page_title="",
                                content=content,
                                current_year=datetime.datetime.now().year,
                                current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/host-validator')
def host_validator():
    content = """
    <div style="margin: -120px -40px -70px -40px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
        <div>
            <h3 style="margin: 0; font-size: 1.2rem; color: white;">✅ Host Validator</h3>
            <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 0.9rem; color: white;">Validate server requirements for Kubernetes</p>
        </div>
    </div>
    <div style="padding: 30px;">
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-top: 0;">
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
    </div>
    </div>
    """
    return render_template_string(dashboard_template,
                                title="Host Validator - Kubernetes AI Dashboard",
                                page="validator",
                                page_title="",
                                content=content,
                                current_year=datetime.datetime.now().year,
                                current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/vm-status')
def vm_status():
    # Get VM data with fetch timestamp
    fetch_time = datetime.datetime.now()
    vm_table_data = []
    total_vms = len(VM_LIST)
    active_vms = 0
    error_vms = 0
    
    # Calculate how long ago the data was fetched
    time_since_fetch = datetime.datetime.now() - fetch_time
    seconds_ago = int(time_since_fetch.total_seconds())
    
    if seconds_ago < 60:
        time_ago_str = f"{seconds_ago} seconds ago"
    elif seconds_ago < 3600:
        minutes_ago = seconds_ago // 60
        time_ago_str = f"{minutes_ago} minute{'s' if minutes_ago != 1 else ''} ago"
    else:
        hours_ago = seconds_ago // 3600
        time_ago_str = f"{hours_ago} hour{'s' if hours_ago != 1 else ''} ago"
    
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
    <div style="margin: -120px -40px -70px -40px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0; padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
        <div>
            <h3 style="margin: 0; font-size: 1.2rem;">🖥️ Virtual Machine Status</h3>
            <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 0.9rem;">Real-time infrastructure monitoring</p>
        </div>
        <div style="display: flex; align-items: center; gap: 20px;">
            <div style="text-align: right;">
                <div style="font-size: 0.9rem; opacity: 0.9; margin-bottom: 2px;">Last updated:</div>
                <div id="timeAgo" style="font-weight: bold; font-size: 1rem;">🕒 {time_ago_str}</div>
                <div id="lastUpdateTime" style="font-size: 0.8rem; opacity: 0.8; margin-top: 2px;" data-timestamp="{fetch_time.isoformat()}">{fetch_time.strftime('%Y-%m-%d %H:%M:%S')}</div>
            </div>
            <button onclick="refreshVMData()" style="
                background: rgba(255, 255, 255, 0.15);
                border: 2px solid rgba(255, 255, 255, 0.3);
                color: white;
                padding: 10px 16px;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 500;
                font-size: 0.9rem;
                transition: all 0.3s ease;
                display: flex;
                align-items: center;
                gap: 8px;
                backdrop-filter: blur(10px);
            " onmouseover="this.style.background='rgba(255, 255, 255, 0.25)'; this.style.transform='translateY(-1px)'" 
               onmouseout="this.style.background='rgba(255, 255, 255, 0.15)'; this.style.transform='translateY(0)'">
                <span id="refreshIcon" style="font-size: 1.1em;">🔄</span>
                <span id="refreshText">Refresh</span>
            </button>
        </div>
    </div>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0;">
        <div style="padding: 20px; background: #d1fae5; border-radius: 12px; text-align: center; border: 2px solid #6ee7b7;">
            <h3 style="color: #047857;">Active VMs</h3>
            <div id="activeVMs" style="font-size: 36px; font-weight: bold; color: #047857; margin: 10px 0;">{active_vms}</div>
            <p style="color: #065f46;">Currently Running</p>
        </div>
        <div style="padding: 20px; background: #fecaca; border-radius: 12px; text-align: center; border: 2px solid #f87171;">
            <h3 style="color: #b91c1c;">Error VMs</h3>
            <div id="errorVMs" style="font-size: 36px; font-weight: bold; color: #b91c1c; margin: 10px 0;">{error_vms}</div>
            <p style="color: #991b1b;">Connection Issues</p>
        </div>
        <div style="padding: 20px; background: #bfdbfe; border-radius: 12px; text-align: center; border: 2px solid #60a5fa;">
            <h3 style="color: #1e40af;">Total VMs</h3>
            <div id="totalVMs" style="font-size: 36px; font-weight: bold; color: #1e40af; margin: 10px 0;">{total_vms}</div>
            <p style="color: #1e3a8a;">Configured</p>
        </div>
    </div>
    
    <div style="background: white; border-radius: 8px; padding: 25px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
        <h3>VM Details</h3>
        <div style="overflow-x: auto; margin-top: 20px;">
            <table style="width: 100%; border-collapse: collapse;">
                <thead>
                    <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; color: white;">VM Name</th>
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; color: white;">Status</th>
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; color: white;">CPU Usage</th>
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; color: white;">Memory</th>
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; color: white;">Role</th>
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; color: white;">Internal IP</th>
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0; color: white;">External IP</th>
                    </tr>
                </thead>
                <tbody id="vmTableBody">
                    {table_rows}
                </tbody>
            </table>
        </div>
        <div style="margin-top: 20px; display: flex; gap: 15px; flex-wrap: wrap;">
            <button class="card-button" style="width: auto; padding: 10px 20px;" onclick="refreshVMData()">Refresh Status</button>
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
                        <th style="padding: 12px 16px; text-align: left; font-weight: 600; color: white;">Timestamp</th>
                        <th style="padding: 12px 16px; text-align: left; font-weight: 600; color: white;">Command</th>
                        <th style="padding: 12px 16px; text-align: center; font-weight: 600; color: white;">Status</th>
                        <th style="padding: 12px 16px; text-align: left; font-weight: 600; color: white;">Details</th>
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
    
    content += logs_html + f"""
        </div>
    </div>
    
    <script>
    let lastFetchTime = new Date('{fetch_time.isoformat()}');
    
    // Update time ago display every second
    function updateTimeAgo() {{
        const now = new Date();
        const timeDiff = Math.floor((now - lastFetchTime) / 1000);
        
        let timeAgoStr;
        if (timeDiff < 60) {{
            timeAgoStr = timeDiff + ' seconds ago';
        }} else if (timeDiff < 3600) {{
            const minutes = Math.floor(timeDiff / 60);
            timeAgoStr = minutes + (minutes === 1 ? ' minute ago' : ' minutes ago');
        }} else {{
            const hours = Math.floor(timeDiff / 3600);
            timeAgoStr = hours + (hours === 1 ? ' hour ago' : ' hours ago');
        }}
        
        document.getElementById('timeAgo').innerHTML = '🕒 ' + timeAgoStr;
    }}
    
    // Start the timer to update "time ago" every second
    setInterval(updateTimeAgo, 1000);
    
    function refreshVMData() {{
        const refreshIcon = document.getElementById('refreshIcon');
        const refreshText = document.getElementById('refreshText');
        
        // Show loading state
        refreshIcon.style.animation = 'spin 1s linear infinite';
        refreshText.textContent = 'Loading...';
        
        fetch('/api/vm-data')
        .then(response => response.json())
        .then(data => {{
            // Update timestamp
            lastFetchTime = new Date(data.last_updated);
            document.getElementById('lastUpdateTime').textContent = lastFetchTime.toLocaleString();
            document.getElementById('lastUpdateTime').setAttribute('data-timestamp', data.last_updated);
            
            // Update metrics
            document.getElementById('activeVMs').textContent = data.summary.active;
            document.getElementById('errorVMs').textContent = data.summary.error;
            document.getElementById('totalVMs').textContent = data.summary.total;
            
            // Update table
            updateVMTable(data.vms);
            
            // Reset button state
            refreshIcon.style.animation = '';
            refreshText.textContent = 'Refresh';
            
            // Update time ago immediately
            updateTimeAgo();
        }})
        .catch(error => {{
            console.error('Error refreshing VM data:', error);
            refreshIcon.style.animation = '';
            refreshText.textContent = 'Error';
            setTimeout(() => {{
                refreshText.textContent = 'Refresh';
            }}, 2000);
        }});
    }}
    
    function updateVMTable(vms) {{
        const tbody = document.getElementById('vmTableBody');
        let tableRows = '';
        
        // Cache nodes data in localStorage for AI Assistant
        try {{
            const nodesData = vms.map(vm => ({{
                name: vm.name,
                status: vm.status,
                role: vm.role || 'Worker'
            }}));
            localStorage.setItem('k8s_nodes_cache', JSON.stringify({{
                data: nodesData,
                timestamp: Date.now()
            }}));
        }} catch(e) {{ console.error('Cache error:', e); }}
        
        vms.forEach(vm => {{
            const statusIndicator = vm.status === 'Running' ? 'status-online' : 'status-offline';
            const memoryDisplay = vm.memory_used_gib && vm.memory_total_gib ? 
                `${{vm.memory_used_gib.toFixed(1)}}GB / ${{vm.memory_total_gib.toFixed(1)}}GB` : 'Error';
            const cpuUsage = vm.cpu_usage_percent !== null ? `${{vm.cpu_usage_percent.toFixed(1)}}%` : 'Error';
            
            tableRows += `
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;"><strong>${{vm.name}}</strong></td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;"><span class="status-indicator ${{statusIndicator}}"></span>${{vm.status}}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">${{cpuUsage}}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">${{memoryDisplay}}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">${{vm.role}}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">${{vm.internal_ip}}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">${{vm.external_ip}}</td>
            </tr>`;
        }});
        
        tbody.innerHTML = tableRows;
    }}
    
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
    
    <style>
    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}
    </style>
    </div>
    """
    return render_template_string(dashboard_template,
                                title="VM Status - Kubernetes AI Dashboard",
                                page="vm-status",
                                page_title="",
                                content=content,
                                current_year=datetime.datetime.now().year,
                                current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/pod-monitor')
def pod_monitor():
    # Get pod data with fetch timestamp
    pods_data, last_fetch_time = get_pods_info()
    
    # Calculate how long ago the data was fetched
    time_since_fetch = datetime.datetime.now() - last_fetch_time
    seconds_ago = int(time_since_fetch.total_seconds())
    
    if seconds_ago < 60:
        time_ago_str = f"{seconds_ago} seconds ago"
    elif seconds_ago < 3600:
        minutes_ago = seconds_ago // 60
        time_ago_str = f"{minutes_ago} minute{'s' if minutes_ago != 1 else ''} ago"
    else:
        hours_ago = seconds_ago // 3600
        time_ago_str = f"{hours_ago} hour{'s' if hours_ago != 1 else ''} ago"
    
    # Calculate metrics
    total_pods = len(pods_data)
    running_pods = sum(1 for pod in pods_data if pod['status'] == 'Running')
    pending_pods = sum(1 for pod in pods_data if pod['status'] == 'Pending')
    failed_pods = sum(1 for pod in pods_data if pod['status'] == 'Failed')
    
    # Get unique namespaces
    namespaces = sorted(list(set(pod['namespace'] for pod in pods_data))) if pods_data else []
    
    # Generate pod table rows
    pod_table_rows = ""
    if pods_data:
        for pod in pods_data:
            status_icon = "🟢" if pod['status'] == 'Running' else "🔴" if pod['status'] == 'Failed' else "🟡"
            status_indicator = 'status-online' if pod['status'] == 'Running' else 'status-offline' if pod['status'] == 'Failed' else 'status-warning'
            
            pod_table_rows += f"""
            <tr style="transition: background-color 0.2s ease;" onmouseover="this.style.backgroundColor='#f8fafc'" onmouseout="this.style.backgroundColor='transparent'">
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; font-weight: 500;">{pod['name']}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">
                    <span style="background: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: 500; white-space: nowrap;">
                        {pod['namespace']}
                    </span>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">
                    {status_icon} {pod['status']}
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; color: #6b7280;">{pod['node']}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: center;">{pod['ready']}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: center;">{pod['restarts']}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; color: #6b7280; font-size: 0.9rem;">{format_time_ago(pod['fetch_timestamp'])}</td>
            </tr>"""
    else:
        pod_table_rows = """
        <tr>
            <td colspan="7" style="padding: 40px; text-align: center; color: #9ca3af;">
                <div style="font-size: 2rem; margin-bottom: 12px;">🚀</div>
                <div style="font-weight: 500; margin-bottom: 8px;">No pods found</div>
                <div style="font-size: 0.9rem;">Make sure kubectl is configured and cluster is running</div>
            </td>
        </tr>"""

    # Namespace filter dropdown
    namespace_options = ""
    for ns in ["All"] + namespaces:
        namespace_options += f'<option value="{ns}">{ns}</option>'

    content = f"""
    <div style="margin: -120px -40px -70px -40px;">
    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0; padding: 15px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; box-shadow: 0 4px 12px rgba(0,0,0,0.15);">
        <div>
            <h3 style="margin: 0; font-size: 1.2rem;">📊 Kubernetes Pod Status</h3>
            <p style="margin: 5px 0 0 0; opacity: 0.9; font-size: 0.9rem;">Real-time cluster monitoring</p>
        </div>
        <div style="display: flex; align-items: center; gap: 20px;">
            <div style="text-align: right;">
                <div style="font-size: 0.9rem; opacity: 0.9; margin-bottom: 2px;">Last updated:</div>
                <div id="timeAgo" style="font-weight: bold; font-size: 1rem;">🕒 {time_ago_str}</div>
                <div id="lastUpdateTime" style="font-size: 0.8rem; opacity: 0.8; margin-top: 2px;" data-timestamp="{last_fetch_time.isoformat()}">{last_fetch_time.strftime('%Y-%m-%d %H:%M:%S')}</div>
            </div>
            <button onclick="refreshPodData()" style="
                background: rgba(255, 255, 255, 0.15);
                border: 2px solid rgba(255, 255, 255, 0.3);
                color: white;
                padding: 10px 16px;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 500;
                font-size: 0.9rem;
                transition: all 0.3s ease;
                display: flex;
                align-items: center;
                gap: 8px;
                backdrop-filter: blur(10px);
            " onmouseover="this.style.background='rgba(255, 255, 255, 0.25)'; this.style.transform='translateY(-1px)'" 
               onmouseout="this.style.background='rgba(255, 255, 255, 0.15)'; this.style.transform='translateY(0)'">
                <span id="refreshIcon" style="font-size: 1.1em;">🔄</span>
                <span id="refreshText">Refresh</span>
            </button>
        </div>
    </div>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0;">
        <div style="padding: 20px; background: #d1fae5; border-radius: 12px; text-align: center; border: 2px solid #6ee7b7;">
            <h4 style="color: #047857; margin: 0 0 10px 0;">Running Pods</h4>
            <div id="runningPods" style="font-size: 32px; font-weight: bold; color: #047857;">{running_pods}</div>
        </div>
        <div style="padding: 20px; background: #fef3c7; border-radius: 12px; text-align: center; border: 2px solid #fcd34d;">
            <h4 style="color: #b45309; margin: 0 0 10px 0;">Pending Pods</h4>
            <div id="pendingPods" style="font-size: 32px; font-weight: bold; color: #b45309;">{pending_pods}</div>
        </div>
        <div style="padding: 20px; background: #fecaca; border-radius: 12px; text-align: center; border: 2px solid #f87171;">
            <h4 style="color: #b91c1c; margin: 0 0 10px 0;">Failed Pods</h4>
            <div id="failedPods" style="font-size: 32px; font-weight: bold; color: #b91c1c;">{failed_pods}</div>
        </div>
        <div style="padding: 20px; background: #bfdbfe; border-radius: 12px; text-align: center; border: 2px solid #60a5fa;">
            <h4 style="color: #1e40af; margin: 0 0 10px 0;">Total Pods</h4>
            <div id="totalPods" style="font-size: 32px; font-weight: bold; color: #1e40af;">{total_pods}</div>
        </div>
    </div>
    
    <div style="background: white; border-radius: 12px; padding: 30px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); margin-top: 30px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;">
            <h3 style="margin: 0; color: #2d3748;">Pod Details</h3>
            <div style="display: flex; align-items: center; gap: 15px;">
                <label for="namespaceFilter" style="color: #4a5568; font-weight: 500;">Filter by namespace:</label>
                <select id="namespaceFilter" onchange="filterPods()" style="padding: 8px 12px; border: 2px solid #e2e8f0; border-radius: 8px; background: white; color: #2d3748;">
                    {namespace_options}
                </select>
            </div>
        </div>
        
        <div style="overflow-x: auto; border-radius: 8px; border: 1px solid #e5e7eb;">
            <table id="podsTable" style="width: 100%; border-collapse: collapse; font-size: 14px;">
                <thead>
                    <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
                        <th style="padding: 14px 12px; text-align: left; font-weight: 600; color: white;">Pod Name</th>
                        <th style="padding: 14px 12px; text-align: left; font-weight: 600; color: white;">Namespace</th>
                        <th style="padding: 14px 12px; text-align: left; font-weight: 600; color: white;">Status</th>
                        <th style="padding: 14px 12px; text-align: left; font-weight: 600; color: white;">Node</th>
                        <th style="padding: 14px 12px; text-align: center; font-weight: 600; color: white;">Ready</th>
                        <th style="padding: 14px 12px; text-align: center; font-weight: 600; color: white;">Restarts</th>
                        <th style="padding: 14px 12px; text-align: left; font-weight: 600; color: white;">Data Age</th>
                    </tr>
                </thead>
                <tbody id="podsTableBody">
                    {pod_table_rows}
                </tbody>
            </table>
        </div>
    </div>

    <!-- Quick Actions Section -->
    <div style="background: white; border-radius: 12px; padding: 30px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); margin-top: 30px;">
        <h3 style="margin: 0 0 20px 0; color: #2d3748;">Quick Actions</h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px;">
            <button class="card-button" onclick="executeKubectl('cluster-info')" style="display: flex; align-items: center; gap: 10px; justify-content: center;">
                <span>📋</span> Get Cluster Info
            </button>
            <button class="card-button" onclick="executeKubectl('get nodes -o wide')" style="display: flex; align-items: center; gap: 10px; justify-content: center;">
                <span>🖥️</span> List Nodes
            </button>
            <button class="card-button" onclick="executeKubectl('get pods --all-namespaces')" style="display: flex; align-items: center; gap: 10px; justify-content: center;">
                <span>🚀</span> All Pods
            </button>
            <button class="card-button" onclick="location.reload()" style="display: flex; align-items: center; gap: 10px; justify-content: center;">
                <span>🔄</span> Refresh Data
            </button>
        </div>
        
        <!-- Command Output Area -->
        <div id="commandOutput" style="margin-top: 20px; padding: 15px; background: #1a202c; color: #e2e8f0; border-radius: 8px; font-family: monospace; white-space: pre-wrap; max-height: 300px; overflow-y: auto; display: none;"></div>
    </div>
    
    <script>
    let lastFetchTime = new Date('{last_fetch_time.isoformat()}');
    
    // Update time ago display every second
    function updateTimeAgo() {{
        const now = new Date();
        const timeDiff = Math.floor((now - lastFetchTime) / 1000);
        
        let timeAgoStr;
        if (timeDiff < 60) {{
            timeAgoStr = timeDiff + ' seconds ago';
        }} else if (timeDiff < 3600) {{
            const minutes = Math.floor(timeDiff / 60);
            timeAgoStr = minutes + (minutes === 1 ? ' minute ago' : ' minutes ago');
        }} else {{
            const hours = Math.floor(timeDiff / 3600);
            timeAgoStr = hours + (hours === 1 ? ' hour ago' : ' hours ago');
        }}
        
        document.getElementById('timeAgo').innerHTML = '🕒 ' + timeAgoStr;
    }}
    
    // Start the timer to update "time ago" every second
    setInterval(updateTimeAgo, 1000);
    
    function refreshPodData() {{
        const refreshIcon = document.getElementById('refreshIcon');
        const refreshText = document.getElementById('refreshText');
        
        // Show loading state
        refreshIcon.style.animation = 'spin 1s linear infinite';
        refreshText.textContent = 'Loading...';
        
        fetch('/api/pod-data')
        .then(response => response.json())
        .then(data => {{
            // Update timestamp
            lastFetchTime = new Date(data.last_updated);
            document.getElementById('lastUpdateTime').textContent = lastFetchTime.toLocaleString();
            document.getElementById('lastUpdateTime').setAttribute('data-timestamp', data.last_updated);
            
            // Update metrics
            document.getElementById('runningPods').textContent = data.summary.running;
            document.getElementById('pendingPods').textContent = data.summary.pending;
            document.getElementById('failedPods').textContent = data.summary.failed;
            document.getElementById('totalPods').textContent = data.summary.total;
            
            // Update table
            updatePodsTable(data.pods);
            
            // Update namespace filter
            updateNamespaceFilter(data.namespaces);
            
            // Reset button state
            refreshIcon.style.animation = '';
            refreshText.textContent = 'Refresh';
            
            // Update time ago immediately
            updateTimeAgo();
        }})
        .catch(error => {{
            console.error('Error refreshing pod data:', error);
            refreshIcon.style.animation = '';
            refreshText.textContent = 'Error';
            setTimeout(() => {{
                refreshText.textContent = 'Refresh';
            }}, 2000);
        }});
    }}
    
    function updatePodsTable(pods) {{
        const tbody = document.getElementById('podsTableBody');
        let tableRows = '';
        
        // Cache pods data in localStorage for AI Assistant
        try {{
            localStorage.setItem('k8s_pods_cache', JSON.stringify({{
                data: pods,
                timestamp: Date.now()
            }}));
        }} catch(e) {{ console.error('Cache error:', e); }}
        
        if (pods.length > 0) {{
            pods.forEach(pod => {{
                const statusIcon = pod.status === 'Running' ? '🟢' : (pod.status === 'Failed' ? '🔴' : '🟡');
                const statusIndicator = pod.status === 'Running' ? 'status-online' : (pod.status === 'Failed' ? 'status-offline' : 'status-warning');
                
                tableRows += `
                <tr style="transition: background-color 0.2s ease;" onmouseover="this.style.backgroundColor='#f8fafc'" onmouseout="this.style.backgroundColor='transparent'">
                    <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; font-weight: 500;">${{pod.name}}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">
                        <span style="background: #e0e7ff; color: #3730a3; padding: 2px 8px; border-radius: 12px; font-size: 0.8rem; font-weight: 500; white-space: nowrap;">
                            ${{pod.namespace}}
                        </span>
                    </td>
                    <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">
                        ${{statusIcon}} ${{pod.status}}
                    </td>
                    <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; color: #6b7280;">${{pod.node}}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: center;">${{pod.ready}}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; text-align: center;">${{pod.restarts}}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #e2e8f0; color: #6b7280; font-size: 0.9rem;">Just now</td>
                </tr>`;
            }});
        }} else {{
            tableRows = `
            <tr>
                <td colspan="7" style="padding: 40px; text-align: center; color: #9ca3af;">
                    <div style="font-size: 2rem; margin-bottom: 12px;">🚀</div>
                    <div style="font-weight: 500; margin-bottom: 8px;">No pods found</div>
                    <div style="font-size: 0.9rem;">Make sure kubectl is configured and cluster is running</div>
                </td>
            </tr>`;
        }}
        
        tbody.innerHTML = tableRows;
    }}
    
    function updateNamespaceFilter(namespaces) {{
        const select = document.getElementById('namespaceFilter');
        const currentValue = select.value;
        
        select.innerHTML = '<option value="All">All</option>';
        namespaces.forEach(ns => {{
            select.innerHTML += `<option value="${{ns}}">${{ns}}</option>`;
        }});
        
        // Restore previous selection if it still exists
        if (namespaces.includes(currentValue) || currentValue === 'All') {{
            select.value = currentValue;
        }}
    }}
    
    function filterPods() {{
        const filter = document.getElementById('namespaceFilter').value;
        const table = document.getElementById('podsTable');
        const rows = table.getElementsByTagName('tbody')[0].getElementsByTagName('tr');
        
        for (let i = 0; i < rows.length; i++) {{
            const namespaceCell = rows[i].getElementsByTagName('td')[1];
            if (namespaceCell) {{
                const namespace = namespaceCell.textContent.trim();
                if (filter === 'All' || namespace === filter) {{
                    rows[i].style.display = '';
                }} else {{
                    rows[i].style.display = 'none';
                }}
            }}
        }}
    }}
    
    function executeKubectl(command) {{
        const outputDiv = document.getElementById('commandOutput');
        outputDiv.style.display = 'block';
        outputDiv.textContent = 'Executing: kubectl ' + command + '\\n\\nLoading...';
        
        fetch('/api/kubectl', {{
            method: 'POST',
            headers: {{'Content-Type': 'application/json'}},
            body: JSON.stringify({{'command': command}})
        }})
        .then(response => response.json())
        .then(data => {{
            if (data.success) {{
                outputDiv.textContent = 'kubectl ' + command + ':\\n\\n' + data.output;
            }} else {{
                outputDiv.textContent = 'Error executing kubectl ' + command + ':\\n\\n' + data.error;
                outputDiv.style.background = '#7f1d1d';
            }}
        }})
        .catch(error => {{
            outputDiv.textContent = 'Error: ' + error;
            outputDiv.style.background = '#7f1d1d';
        }});
    }}
    </script>
    
    <style>
    @keyframes spin {{
        0% {{ transform: rotate(0deg); }}
        100% {{ transform: rotate(360deg); }}
    }}
    </style>
    </div>
    """

    return render_template_string(dashboard_template,
                                title="Pod Monitor - Kubernetes AI Dashboard",
                                page="pod-monitor",
                                page_title="",
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

@app.route('/api/pod-data')
def get_pod_data():
    """API endpoint to get pod data as JSON for AJAX refresh."""
    pods_data, last_fetch_time = get_pods_info()
    
    # Calculate metrics
    total_pods = len(pods_data)
    running_pods = sum(1 for pod in pods_data if pod['status'] == 'Running')
    pending_pods = sum(1 for pod in pods_data if pod['status'] == 'Pending')
    failed_pods = sum(1 for pod in pods_data if pod['status'] == 'Failed')
    
    # Get unique namespaces
    namespaces = sorted(list(set(pod['namespace'] for pod in pods_data))) if pods_data else []
    
    return jsonify({
        'pods': pods_data,
        'summary': {
            'total': total_pods,
            'running': running_pods,
            'pending': pending_pods,
            'failed': failed_pods
        },
        'namespaces': namespaces,
        'last_updated': last_fetch_time.isoformat()
    })

@app.route('/api/clear-logs', methods=['POST'])
def clear_logs():
    """API endpoint to clear command logs."""
    global command_logs
    command_logs.clear()
    return jsonify({'status': 'success', 'message': 'Logs cleared'})

@app.route('/api/kubectl', methods=['POST'])
def execute_kubectl():
    """API endpoint to execute kubectl commands."""
    data = request.get_json()
    command = data.get('command', '')
    
    if not command:
        return jsonify({'success': False, 'error': 'No command provided'})
    
    result = execute_kubectl_command(command)
    return jsonify(result)

def get_cluster_context(use_cache=True):
    """Get current cluster context from VM and Pod data with caching."""
    global cluster_cache
    
    # Check cache validity
    if use_cache and cluster_cache['data'] is not None and cluster_cache['timestamp'] is not None:
        elapsed = (datetime.datetime.now() - cluster_cache['timestamp']).total_seconds()
        if elapsed < cluster_cache['cache_duration']:
            return cluster_cache['data']
    
    context = {
        'vms': [],
        'pods': [],
        'summary': {}
    }
    
    try:
        # Get VM data (lightweight - only names and roles for speed)
        for vm_config in VM_LIST:
            context['vms'].append({
                'name': vm_config['name'],
                'role': vm_config['role'],
                'status': 'Available'  # Assume available unless we need details
            })
        
        # Get Pod data (this is already relatively fast)
        pods_data, _ = get_pods_info()
        context['pods'] = pods_data
        
        # Calculate summary
        context['summary'] = {
            'total_vms': len(VM_LIST),
            'active_vms': len(VM_LIST),  # Assume all active for quick response
            'total_pods': len(pods_data),
            'running_pods': sum(1 for pod in pods_data if pod['status'] == 'Running'),
            'pending_pods': sum(1 for pod in pods_data if pod['status'] == 'Pending'),
            'failed_pods': sum(1 for pod in pods_data if pod['status'] == 'Failed')
        }
        
        # Update cache
        cluster_cache['data'] = context
        cluster_cache['timestamp'] = datetime.datetime.now()
        
    except Exception as e:
        context['error'] = str(e)
    
    return context

def execute_kubectl_tool(command):
    """Execute kubectl command and return result."""
    result = execute_kubectl_command(command)
    if result['success']:
        return result['output']
    else:
        return f"Error executing command: {result['error']}"

@app.route('/api/chat', methods=['POST'])
def chat():
    """API endpoint for AI chat using LangGraph K8s Agent with smart caching."""
    try:
        data = request.get_json()
        message = data.get('message', '')
        client_cache = data.get('clientCache', {})  # Client-side cached data from other tabs
        
        if not message:
            return jsonify({'success': False, 'error': 'No message provided'})
        
        # Get Anthropic API key
        anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
        
        if not anthropic_api_key:
            return jsonify({'success': False, 'error': 'Anthropic API key not configured'})
        
        try:
            # Check if we can answer from client cache (instant response)
            quick_response = _try_answer_from_client_cache(message, client_cache)
            if quick_response:
                log_command(f"AI Agent Query", "⚡ Instant", "Answered from client cache")
                return jsonify({
                    'success': True,
                    'response': quick_response,
                    'source': 'client_cache'
                })
            
            # Use LangGraph K8s Agent for intelligent responses
            log_command(f"AI Agent Query: {message[:100]}...", "Running", "Processing with K8s Agent")
            
            result = ask_k8s_agent(question=message, api_key=anthropic_api_key, verbose=False)
            
            # Format response with HTML for proper display
            answer = result['answer']
            
            # Convert markdown-style formatting to HTML
            answer = answer.replace('\n\n', '<br><br>')
            answer = answer.replace('\n', '<br>')
            
            log_command(f"AI Agent Query", "✅ Success", f"Response generated successfully")
            
            return jsonify({
                'success': True, 
                'response': answer,
                'agent_used': True
            })
            
        except Exception as e:
            log_command(f"AI Agent Query", "❌ Failed", f"Error: {str(e)}")
            return jsonify({'success': False, 'error': f'Agent error: {str(e)}'})
            
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000, debug=True)
