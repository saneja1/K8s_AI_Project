from flask import Flask, render_template_string, jsonify, request, redirect, url_for, flash
import datetime
import subprocess
import json
import os
from dotenv import load_dotenv
import graphviz

# Flask-Login & Authentication (STEP 2)
from flask_login import LoginManager, login_required, current_user, login_user, logout_user

# Load environment variables
load_dotenv()

# Import K8s Agent
import sys
sys.path.append(os.path.dirname(__file__))
from agents.k8s_agent import ask_k8s_agent

# Import authentication models
from models import db, User, init_db, create_default_admin

app = Flask(__name__)

# STEP 2: Configure Flask app for authentication
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///k8s_dashboard.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# STEP 2: Initialize LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Redirect to login page if not authenticated
login_manager.login_message = '⚠️ Please log in to access this page.'

# STEP 2: Initialize database and create default admin
init_db(app)
create_default_admin(app)

# STEP 2: User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    """
    Load user by ID from database
    Called by Flask-Login on every request to check if user is logged in
    """
    return User.query.get(int(user_id))

# VM Configuration - from dashboard.py
VM_LIST = [
    {"name": "k8s-master-01", "zone": "us-west1-a", "role": "Master", "internal_ip": "10.138.0.2", "external_ip": "TBD"},
    {"name": "k8s-worker-01", "zone": "us-west1-a", "role": "Worker", "internal_ip": "10.138.0.3", "external_ip": "TBD"}
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
        
        # Execute kubectl on master node via SSH (needs sudo for kubeconfig access)
        full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods --all-namespaces -o json"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "pggo890@k8s-master-01",
            "--zone=us-west1-a", 
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
        
        # Execute kubectl on the master node via SSH (needs sudo for kubeconfig access)
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl {command}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "pggo890@k8s-master-01",
            "--zone=us-west1-a",
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
            max-width: 1400px;
            margin: 0 auto;
            display: flex;
            justify-content: flex-start;
            align-items: center;
            padding: 0 20px;
            gap: 40px;
        }
        
        .logo {
            font-size: 20px;
            font-weight: bold;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            white-space: nowrap;
            flex-shrink: 0;
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
                    <li><a href="/docs" class="{{ 'active' if page == 'docs' else '' }}">Docs</a></li>
                    <li><a href="/faq" class="{{ 'active' if page == 'faq' else '' }}">FAQ</a></li>
                    {% if current_user.is_admin() %}
                    <li><a href="/user-management" class="{{ 'active' if page == 'user-management' else '' }}">👥 Users</a></li>
                    {% endif %}
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
            " onmouseover="this.style.transform='scale(1.05)'" onmouseout="this.style.transform='scale(1)'">
                <span id="themeIcon">🌙</span>
                <span id="themeText">Dark</span>
            </button>
            
            <!-- User Info & Logout -->
            <div style="
                margin-left: 20px;
                display: flex;
                align-items: center;
                gap: 15px;
                padding-left: 20px;
                border-left: 2px solid rgba(102, 126, 234, 0.3);
            ">
                <div style="
                    text-align: right;
                    color: var(--text-primary);
                ">
                    <div style="font-weight: 600; font-size: 0.9rem;">{{ current_user.username }}</div>
                    <div style="font-size: 0.75rem; opacity: 0.7;">
                        {% if current_user.role == 'admin' %}👑 Admin
                        {% elif current_user.role == 'operator' %}🔧 Operator
                        {% else %}👁️ Viewer{% endif %}
                    </div>
                </div>
                <a href="/logout" style="
                    background: rgba(239, 68, 68, 0.1);
                    border: 1px solid rgba(239, 68, 68, 0.3);
                    color: #ef4444;
                    padding: 6px 14px;
                    border-radius: 20px;
                    text-decoration: none;
                    font-weight: 500;
                    font-size: 0.85rem;
                    transition: all 0.2s ease;
                " onmouseover="this.style.background='#ef4444'; this.style.color='white';" onmouseout="this.style.background='rgba(239, 68, 68, 0.1)'; this.style.color='#ef4444';">
                    🚪 Logout
                </a>
            </div>
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
            
            <div class="card">
                <div class="card-icon">📚</div>
                <h3 class="card-title">Documentation</h3>
                <p class="card-description">Comprehensive documentation, guides, and resources for the Kubernetes AI Dashboard.</p>
                <a href="/docs" class="card-button">View Docs</a>
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

# ============================================================================
# STEP 3: LOGIN & LOGOUT ROUTES
# ============================================================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Login page and authentication handler
    
    GET: Show login form
    POST: Validate credentials and create session
    """
    # If already logged in, redirect to home
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        # Validate inputs
        if not username or not password:
            flash('❌ Username and password are required', 'error')
            return redirect(url_for('login'))
        
        # Find user in database
        user = User.query.filter_by(username=username).first()
        
        # Check credentials
        if user and user.check_password(password):
            # Login successful - create session
            login_user(user, remember=True)
            user.update_last_login()
            
            flash(f'✅ Welcome back, {user.username}! (Role: {user.role})', 'success')
            
            # Redirect to originally requested page or home
            next_page = request.args.get('next')
            return redirect(next_page if next_page else url_for('home'))
        else:
            # Login failed
            flash('❌ Invalid username or password', 'error')
            return redirect(url_for('login'))
    
    # GET request - show login form
    login_html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - K8s Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
        }
        
        .login-container {
            background: white;
            padding: 40px;
            border-radius: 16px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            width: 100%;
            max-width: 420px;
        }
        
        .logo-section {
            text-align: center;
            margin-bottom: 30px;
        }
        
        .logo-icon {
            font-size: 4rem;
            margin-bottom: 10px;
        }
        
        h1 {
            font-size: 1.75rem;
            color: #1a202c;
            margin-bottom: 8px;
        }
        
        .subtitle {
            color: #718096;
            font-size: 0.95rem;
        }
        
        .flash-messages {
            margin-bottom: 20px;
        }
        
        .flash {
            padding: 12px 16px;
            border-radius: 8px;
            margin-bottom: 12px;
            font-size: 0.9rem;
            animation: slideIn 0.3s ease-out;
        }
        
        .flash.error {
            background: #fee;
            color: #c53030;
            border-left: 4px solid #c53030;
        }
        
        .flash.success {
            background: #efe;
            color: #2f855a;
            border-left: 4px solid #2f855a;
        }
        
        @keyframes slideIn {
            from { transform: translateY(-20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            color: #4a5568;
            font-weight: 600;
            margin-bottom: 8px;
            font-size: 0.9rem;
        }
        
        input {
            width: 100%;
            padding: 12px 16px;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            font-size: 1rem;
            transition: all 0.2s;
        }
        
        input:focus {
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }
        
        .btn-login {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .btn-login:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
        }
        
        .btn-login:active {
            transform: translateY(0);
        }
        
        .default-creds {
            margin-top: 24px;
            padding: 16px;
            background: #fffaeb;
            border: 1px solid #f6e05e;
            border-radius: 8px;
            font-size: 0.85rem;
            color: #744210;
        }
        
        .default-creds strong {
            display: block;
            margin-bottom: 8px;
            color: #744210;
        }
        
        .default-creds code {
            background: #fef5e7;
            padding: 2px 6px;
            border-radius: 4px;
            font-family: 'Courier New', monospace;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo-section">
            <div class="logo-icon">🔐</div>
            <h1>K8s Dashboard</h1>
            <p class="subtitle">Kubernetes Cluster Management</p>
        </div>
        
        <!-- Flash Messages -->
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                <div class="flash-messages">
                    {% for category, message in messages %}
                        <div class="flash {{ category }}">{{ message | safe }}</div>
                    {% endfor %}
                </div>
            {% endif %}
        {% endwith %}
        
        <form method="POST" action="{{ url_for('login') }}">
            <div class="form-group">
                <label for="username">Username</label>
                <input type="text" id="username" name="username" required autofocus placeholder="Enter your username">
            </div>
            
            <div class="form-group">
                <label for="password">Password</label>
                <input type="password" id="password" name="password" required placeholder="Enter your password">
            </div>
            
            <button type="submit" class="btn-login">🚀 Login</button>
        </form>
        
        <div class="default-creds">
            <strong>⚠️ Default Credentials (First Login)</strong>
            Username: <code>admin</code><br>
            Password: <code>admin123</code><br>
            Role: <code>admin</code>
        </div>
    </div>
</body>
</html>
    """
    return render_template_string(login_html)


@app.route('/logout')
@login_required
def logout():
    """
    Logout handler - destroy session and redirect to login
    """
    username = current_user.username
    logout_user()
    flash(f'✅ Goodbye, {username}! You have been logged out.', 'success')
    return redirect(url_for('login'))


# ============================================================================
# PROTECTED DASHBOARD ROUTES (Require Authentication)
# ============================================================================

@app.route('/')
@login_required
def home():
    return render_template_string(dashboard_template, 
                                title="Kubernetes AI Dashboard",
                                page="home",
                                current_year=datetime.datetime.now().year,
                                current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/k8s-assistant')
@login_required
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
@login_required
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
@login_required
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
@login_required
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

@app.route('/docs')
@login_required
def docs():
    content = """
    <div style="margin: -120px -40px -70px -40px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; text-align: center;">
            <h2 style="margin: 0; font-size: 2rem; font-weight: 600; color: white;">📚 Documentation</h2>
            <p style="margin: 15px 0 0 0; opacity: 0.95; font-size: 1.1rem; color: white;">Guides, resources, and comprehensive documentation</p>
        </div>
        
        <div style="padding: 40px; background: white;">
            <!-- Architecture Subpages -->
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 30px; margin-bottom: 40px;">
                <a href="/docs/full-architecture" style="text-decoration: none;">
                    <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; border-left: 4px solid #667eea; cursor: pointer; transition: all 0.3s ease;" onmouseover="this.style.transform='translateY(-5px)'; this.style.boxShadow='0 8px 16px rgba(0,0,0,0.1)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                        <h3 style="margin: 0 0 15px 0; color: #667eea;">📊 Full Architecture</h3>
                        <p style="margin: 0; color: #4a5568;">Complete system architecture diagram showing all components and their interactions</p>
                    </div>
                </a>
                
                <a href="/docs/detailed-flow" style="text-decoration: none;">
                    <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; border-left: 4px solid #4CAF50; cursor: pointer; transition: all 0.3s ease;" onmouseover="this.style.transform='translateY(-5px)'; this.style.boxShadow='0 8px 16px rgba(0,0,0,0.1)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                        <h3 style="margin: 0 0 15px 0; color: #4CAF50;">🔍 Detailed Flow Examples</h3>
                        <p style="margin: 0; color: #4a5568;">Step-by-step execution flows for each agent with MCP communication details</p>
                    </div>
                </a>
                
                <a href="/docs/component-glossary" style="text-decoration: none;">
                    <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; border-left: 4px solid #FF9800; cursor: pointer; transition: all 0.3s ease;" onmouseover="this.style.transform='translateY(-5px)'; this.style.boxShadow='0 8px 16px rgba(0,0,0,0.1)'" onmouseout="this.style.transform='translateY(0)'; this.style.boxShadow='none'">
                        <h3 style="margin: 0 0 15px 0; color: #FF9800;">📖 Component Glossary</h3>
                        <p style="margin: 0; color: #4a5568;">Detailed reference guide for all agents, tools, and system components</p>
                    </div>
                </a>
            </div>
            
            <div style="border-top: 2px solid #e2e8f0; margin: 40px 0; padding-top: 40px;">
                <h2 style="color: #2d3748; margin-bottom: 30px;">📚 General Documentation</h2>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 30px; margin-bottom: 40px;">
                <!-- Quick Links -->
                <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; border-left: 4px solid #667eea;">
                    <h3 style="margin: 0 0 15px 0; color: #2d3748;">🚀 Quick Start</h3>
                    <ul style="list-style: none; padding: 0; margin: 0;">
                        <li style="margin-bottom: 10px;"><a href="#getting-started" style="color: #667eea; text-decoration: none;">→ Getting Started</a></li>
                        <li style="margin-bottom: 10px;"><a href="#setup" style="color: #667eea; text-decoration: none;">→ Installation & Setup</a></li>
                    </ul>
                </div>
                
                <!-- Features -->
                <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; border-left: 4px solid #4CAF50;">
                    <h3 style="margin: 0 0 15px 0; color: #2d3748;">✨ Features</h3>
                    <ul style="list-style: none; padding: 0; margin: 0;">
                        <li style="margin-bottom: 10px;"><a href="#ai-assistant" style="color: #4CAF50; text-decoration: none;">→ AI Assistant</a></li>
                        <li style="margin-bottom: 10px;"><a href="#monitoring" style="color: #4CAF50; text-decoration: none;">→ Monitoring & Metrics</a></li>
                        <li style="margin-bottom: 10px;"><a href="#operations" style="color: #4CAF50; text-decoration: none;">→ Cluster Operations</a></li>
                    </ul>
                </div>
                
                <!-- API Reference -->
                <div style="background: #f8f9fa; padding: 25px; border-radius: 8px; border-left: 4px solid #FF9800;">
                    <h3 style="margin: 0 0 15px 0; color: #2d3748;">🔧 API Reference</h3>
                    <ul style="list-style: none; padding: 0; margin: 0;">
                        <li style="margin-bottom: 10px;"><a href="#mcp-servers" style="color: #FF9800; text-decoration: none;">→ MCP Servers</a></li>
                        <li style="margin-bottom: 10px;"><a href="#endpoints" style="color: #FF9800; text-decoration: none;">→ API Endpoints</a></li>
                    </ul>
                </div>
            </div>
            
            <!-- Main Documentation Content -->
            <div style="max-width: 900px; margin: 0 auto;">
                <section id="getting-started" style="margin-bottom: 50px;">
                    <h2 style="color: #2d3748; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px;">🚀 Getting Started</h2>
                    <p style="line-height: 1.8; color: #4a5568;">
                        The Kubernetes AI Dashboard is a multi-agent system powered by Claude Sonnet 4.5 and LangGraph, 
                        designed to provide intelligent cluster management, monitoring, and operations capabilities.
                    </p>
                    <div style="background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <strong style="color: #1976d2;">💡 Key Capabilities:</strong>
                        <ul style="margin-top: 10px;">
                            <li>Natural language query interface for cluster operations</li>
                            <li>Real-time monitoring with Prometheus integration</li>
                            <li>Multi-agent architecture with specialized agents</li>
                            <li>MCP (Model Context Protocol) for tool execution</li>
                        </ul>
                    </div>
                </section>
                
                <section id="setup" style="margin-bottom: 50px;">
                    <h2 style="color: #2d3748; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px;">⚙️ Installation & Setup</h2>
                    <h3 style="color: #4a5568;">Prerequisites</h3>
                    <pre style="background: white; color: black; padding: 20px; border-radius: 8px; overflow-x: auto; border: 1px solid #e2e8f0;">
Python 3.12+
Virtual environment (.venv)
Graphviz (system package)
Google Cloud SDK (for cluster access)
                    </pre>
                    
                    <h3 style="color: #4a5568; margin-top: 30px;">Starting the Dashboard</h3>
                    <pre style="background: white; color: black; padding: 20px; border-radius: 8px; overflow-x: auto; border: 1px solid #e2e8f0;">
cd /home/saneja/K8s_AI_Project/app2.0
./startup.sh start
                    </pre>
                    
                    <p style="line-height: 1.8; color: #4a5568; margin-top: 20px;">
                        This will start the Flask dashboard on port 7000 and all MCP servers on ports 8000-8004.
                    </p>
                </section>
                
                <section id="architecture" style="margin-bottom: 50px;">
                    <h2 style="color: #2d3748; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px;">🏗️ System Architecture</h2>
                    <p style="line-height: 1.8; color: #4a5568;">
                        The system follows a supervisor-agent pattern where a central supervisor routes queries to specialized agents:
                    </p>
                    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0;">
                        <div style="background: #f0f4f8; padding: 20px; border-radius: 8px;">
                            <h4 style="color: #667eea; margin: 0 0 10px 0;">🎯 Supervisor Agent</h4>
                            <p style="margin: 0; font-size: 0.9rem; color: #4a5568;">Routes queries to specialized agents based on keywords and intent</p>
                        </div>
                        <div style="background: #f0f4f8; padding: 20px; border-radius: 8px;">
                            <h4 style="color: #f44336; margin: 0 0 10px 0;">❤️ Health Agent</h4>
                            <p style="margin: 0; font-size: 0.9rem; color: #4a5568;">Pod health, readiness, and liveness checks</p>
                        </div>
                        <div style="background: #f0f4f8; padding: 20px; border-radius: 8px;">
                            <h4 style="color: #2196F3; margin: 0 0 10px 0;">📋 Describe Agent</h4>
                            <p style="margin: 0; font-size: 0.9rem; color: #4a5568;">Resource details and configurations</p>
                        </div>
                        <div style="background: #f0f4f8; padding: 20px; border-radius: 8px;">
                            <h4 style="color: #4CAF50; margin: 0 0 10px 0;">📊 Resources Agent</h4>
                            <p style="margin: 0; font-size: 0.9rem; color: #4a5568;">Capacity planning and resource allocation</p>
                        </div>
                        <div style="background: #f0f4f8; padding: 20px; border-radius: 8px;">
                            <h4 style="color: #FF9800; margin: 0 0 10px 0;">⚙️ Operations Agent</h4>
                            <p style="margin: 0; font-size: 0.9rem; color: #4a5568;">Cluster modifications and scaling</p>
                        </div>
                        <div style="background: #f0f4f8; padding: 20px; border-radius: 8px;">
                            <h4 style="color: #9C27B0; margin: 0 0 10px 0;">📈 Monitor Agent</h4>
                            <p style="margin: 0; font-size: 0.9rem; color: #4a5568;">Prometheus metrics and real-time data</p>
                        </div>
                    </div>
                </section>
                
                <section id="mcp-servers" style="margin-bottom: 50px;">
                    <h2 style="color: #2d3748; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px;">🔌 MCP Servers</h2>
                    <p style="line-height: 1.8; color: #4a5568;">
                        Model Context Protocol servers expose tools as HTTP endpoints that agents can call:
                    </p>
                    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                        <thead>
                            <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
                                <th style="padding: 12px; text-align: left;">Server</th>
                                <th style="padding: 12px; text-align: left;">Port</th>
                                <th style="padding: 12px; text-align: left;">Tools</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr style="background: #f8f9fa;">
                                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">Health MCP</td>
                                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">8000</td>
                                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">check_pod_health, check_readiness</td>
                            </tr>
                            <tr style="background: white;">
                                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">Describe MCP</td>
                                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">8002</td>
                                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">describe_resource, get_yaml</td>
                            </tr>
                            <tr style="background: #f8f9fa;">
                                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">Resources MCP</td>
                                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">8001</td>
                                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">get_node_resources, get_pod_resources</td>
                            </tr>
                            <tr style="background: white;">
                                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">Operations MCP</td>
                                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">8003</td>
                                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">scale_deployment, create_resource</td>
                            </tr>
                            <tr style="background: #f8f9fa;">
                                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">Monitor MCP</td>
                                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">8004</td>
                                <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">query_prometheus, get_metrics</td>
                            </tr>
                        </tbody>
                    </table>
                </section>
                
                <section id="endpoints" style="margin-bottom: 50px;">
                    <h2 style="color: #2d3748; border-bottom: 2px solid #e2e8f0; padding-bottom: 10px;">🌐 API Endpoints</h2>
                    <div style="background: white; color: black; padding: 20px; border-radius: 8px; font-family: monospace; margin: 20px 0; border: 1px solid #e2e8f0;">
                        <div style="margin-bottom: 15px;">
                            <strong style="color: #4CAF50;">POST</strong> /api/chat - Send query to AI assistant
                        </div>
                        <div style="margin-bottom: 15px;">
                            <strong style="color: #2196F3;">GET</strong> /api/vm-data - Get VM status data
                        </div>
                        <div style="margin-bottom: 15px;">
                            <strong style="color: #2196F3;">GET</strong> /api/pod-data - Get pod status data
                        </div>
                        <div style="margin-bottom: 15px;">
                            <strong style="color: #FF9800;">POST</strong> /api/kubectl - Execute kubectl command
                        </div>
                    </div>
                </section>
                
                <section style="background: #e8f5e9; padding: 30px; border-radius: 8px; border-left: 4px solid #4CAF50;">
                    <h3 style="color: #2d3748; margin-top: 0;">💡 Need Help?</h3>
                    <p style="line-height: 1.8; color: #4a5568;">
                        For additional documentation, check the <code>/docs</code> folder in the project repository, 
                        or try asking the <a href="/k8s-assistant" style="color: #667eea;">K8s AI Assistant</a> directly!
                    </p>
                </section>
            </div>
        </div>
    </div>
    """
    
    return render_template_string(dashboard_template,
                                title="Documentation - Kubernetes AI Dashboard",
                                page="docs",
                                page_title="",
                                content=content,
                                current_year=datetime.datetime.now().year,
                                current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/faq')
@login_required
def faq():
    content = """
    <div style="margin: -120px -40px -70px -40px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; text-align: center;">
            <h2 style="margin: 0; font-size: 2rem; font-weight: 600; color: white;">❓ Frequently Asked Questions</h2>
            <p style="margin: 15px 0 0 0; opacity: 0.95; font-size: 1.1rem; color: white;">Everything you need to know about the Kubernetes AI Dashboard</p>
        </div>
        
        <div style="padding: 40px; background: white; max-width: 1200px; margin: 0 auto;">
            
            <!-- FAQ 1 -->
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #667eea;">
                <h3 style="color: #667eea; margin: 0 0 10px 0; font-size: 1.2rem;">1. What is the Kubernetes AI Dashboard?</h3>
                <p style="line-height: 1.7; color: #4a5568; margin: 0;">
                    A web application that helps you manage and monitor your Kubernetes cluster using AI. 
                    Instead of typing complex commands, you can ask questions in plain English and get instant answers. 
                    It combines monitoring, server validation, and pod management in one place.
                </p>
            </div>
            
            <!-- FAQ 2 -->
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #4CAF50;">
                <h3 style="color: #4CAF50; margin: 0 0 10px 0; font-size: 1.2rem;">2. How do I use the dashboard?</h3>
                <p style="line-height: 1.7; color: #4a5568; margin: 0;">
                    Simply open it in your web browser after starting the application. The dashboard has different sections you can click through - 
                    an AI assistant, server validator, VM monitoring, and pod tracking. Everything is accessible through the navigation menu at the top.
                </p>
            </div>
            
            <!-- FAQ 3 -->
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #FF9800;">
                <h3 style="color: #FF9800; margin: 0 0 10px 0; font-size: 1.2rem;">3. What is the AI Assistant?</h3>
                <p style="line-height: 1.7; color: #4a5568; margin: 0;">
                    An intelligent chat interface that answers questions about your Kubernetes cluster. 
                    Just type your question in plain English, and the AI will figure out what you need and provide the answer. 
                    It understands questions about cluster health, resources, operations, and monitoring.
                </p>
            </div>
            
            <!-- FAQ 4 -->
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #2196F3;">
                <h3 style="color: #2196F3; margin: 0 0 10px 0; font-size: 1.2rem;">4. How does the AI understand my questions?</h3>
                <p style="line-height: 1.7; color: #4a5568; margin: 0;">
                    The AI analyzes your question and determines what type of information you need. It then routes your question to specialized agents 
                    that focus on specific tasks - like checking health, monitoring resources, or making changes. These agents work together to provide you with accurate answers.
                </p>
            </div>
            
            <!-- FAQ 5 -->
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #9C27B0;">
                <h3 style="color: #9C27B0; margin: 0 0 10px 0; font-size: 1.2rem;">5. What are specialized agents?</h3>
                <p style="line-height: 1.7; color: #4a5568; margin: 0 0 10px 0;">
                    Think of agents as expert team members. Each agent specializes in a specific area:
                </p>
                <ul style="line-height: 1.7; color: #4a5568; margin: 0; padding-left: 25px; font-size: 0.95rem;">
                    <li><strong>Health Agent:</strong> Checks if your nodes and cluster are healthy</li>
                    <li><strong>Describe Agent:</strong> Shows details about your resources and pods</li>
                    <li><strong>Resources Agent:</strong> Tracks CPU, memory, and storage usage</li>
                    <li><strong>Operations Agent:</strong> Helps you scale, restart, or modify resources</li>
                    <li><strong>Monitor Agent:</strong> Analyzes performance metrics and trends</li>
                </ul>
            </div>
            
            <!-- FAQ 6 -->
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #667eea;">
                <h3 style="color: #667eea; margin: 0 0 10px 0; font-size: 1.2rem;">6. What is the Host Validator?</h3>
                <p style="line-height: 1.7; color: #4a5568; margin: 0;">
                    A tool that checks if a server has enough resources to join your Kubernetes cluster. 
                    It verifies that the server has sufficient CPU, memory, and disk space before you add it to your cluster. 
                    This prevents problems caused by underpowered servers.
                </p>
            </div>
            
            <!-- FAQ 7 -->
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #4CAF50;">
                <h3 style="color: #4CAF50; margin: 0 0 10px 0; font-size: 1.2rem;">7. What does VM Status show?</h3>
                <p style="line-height: 1.7; color: #4a5568; margin: 0;">
                    This page shows real-time information about your virtual machines. You can see CPU usage, memory consumption, disk space, 
                    and whether each VM is functioning properly. It helps you quickly identify which machines might need attention.
                </p>
            </div>
            
            <!-- FAQ 8 -->
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #FF9800;">
                <h3 style="color: #FF9800; margin: 0 0 10px 0; font-size: 1.2rem;">8. What is the Pod Monitor?</h3>
                <p style="line-height: 1.7; color: #4a5568; margin: 0;">
                    A live view of all your Kubernetes pods. It shows which pods are running, failing, or pending, along with their status, 
                    restart counts, and age. This helps you quickly spot and troubleshoot any pod issues in your cluster.
                </p>
            </div>
            
            <!-- FAQ 9 -->
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #2196F3;">
                <h3 style="color: #2196F3; margin: 0 0 10px 0; font-size: 1.2rem;">9. What questions can I ask the AI?</h3>
                <p style="line-height: 1.7; color: #4a5568; margin: 0 0 10px 0;">
                    You can ask questions in everyday language. Examples:
                </p>
                <ul style="line-height: 1.7; color: #4a5568; margin: 0; padding-left: 25px; font-size: 0.95rem;">
                    <li>"Show me all pods"</li>
                    <li>"What's the CPU usage on my nodes?"</li>
                    <li>"Scale my nginx deployment to 3 instances"</li>
                    <li>"Which pod is using the most memory?"</li>
                    <li>"Are there any unhealthy pods?"</li>
                </ul>
            </div>
            
            <!-- FAQ 10 -->
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #9C27B0;">
                <h3 style="color: #9C27B0; margin: 0 0 10px 0; font-size: 1.2rem;">10. Can the AI make changes to my cluster?</h3>
                <p style="line-height: 1.7; color: #4a5568; margin: 0;">
                    Yes, but safely. The AI can help you scale deployments, restart pods, or delete resources when you ask it to. 
                    These operations are performed carefully and all changes are logged so you can track what was done.
                </p>
            </div>
            
            <!-- FAQ 11 -->
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #667eea;">
                <h3 style="color: #667eea; margin: 0 0 10px 0; font-size: 1.2rem;">11. What's the difference between real-time usage and configured limits?</h3>
                <p style="line-height: 1.7; color: #4a5568; margin: 0;">
                    <strong>Real-time usage</strong> shows what's actually happening right now - how much CPU or memory a pod is currently using. 
                    <strong>Configured limits</strong> show what you've set as the maximum a pod is allowed to use. 
                    The AI can tell you either depending on what you ask.
                </p>
            </div>
            
            <!-- FAQ 12 -->
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #4CAF50;">
                <h3 style="color: #4CAF50; margin: 0 0 10px 0; font-size: 1.2rem;">12. Is this dashboard beginner-friendly?</h3>
                <p style="line-height: 1.7; color: #4a5568; margin: 0;">
                    Absolutely! You don't need to be a Kubernetes expert. The dashboard translates your plain English questions into technical commands, 
                    and presents results in an easy-to-understand format. It's designed to help both beginners and experts manage their clusters efficiently.
                </p>
            </div>
            
            <!-- FAQ 13 -->
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #FF9800;">
                <h3 style="color: #FF9800; margin: 0 0 10px 0; font-size: 1.2rem;">13. How does the dashboard monitor performance?</h3>
                <p style="line-height: 1.7; color: #4a5568; margin: 0;">
                    The dashboard collects metrics from your cluster continuously - things like CPU usage, memory consumption, disk activity, and network traffic. 
                    It can show you current values or historical trends, helping you understand your cluster's performance over time.
                </p>
            </div>
            
            <!-- FAQ 14 -->
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #2196F3;">
                <h3 style="color: #2196F3; margin: 0 0 10px 0; font-size: 1.2rem;">14. Can I see what happened in the past?</h3>
                <p style="line-height: 1.7; color: #4a5568; margin: 0;">
                    Yes! You can ask for historical data like "Show CPU usage for the last hour" or "What were the top 5 pods using memory yesterday?" 
                    The dashboard keeps track of metrics over time so you can analyze trends and troubleshoot issues.
                </p>
            </div>
            
            <!-- FAQ 15 -->
            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #9C27B0;">
                <h3 style="color: #9C27B0; margin: 0 0 10px 0; font-size: 1.2rem;">15. What makes this different from other Kubernetes tools?</h3>
                <p style="line-height: 1.7; color: #4a5568; margin: 0;">
                    Instead of memorizing commands or navigating complex interfaces, you simply have a conversation with the AI. 
                    It combines monitoring, troubleshooting, and operations in one intelligent interface that understands natural language. 
                    Everything you need is in one place, accessible through simple questions.
                </p>
            </div>
            
            <!-- Need More Help Section -->
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 8px; text-align: center; margin-top: 40px;">
                <h3 style="margin: 0 0 15px 0; color: white;">📚 Need More Help?</h3>
                <p style="line-height: 1.8; margin: 0 0 20px 0; opacity: 0.95; color: white;">
                    Check out our comprehensive documentation for detailed guides, architecture diagrams, and examples.
                </p>
                <a href="/docs" style="display: inline-block; background: #4a5fd9; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: 600; transition: all 0.2s; box-shadow: 0 2px 8px rgba(0,0,0,0.2);" 
                   onmouseover="this.style.background='#3d4fc7'; this.style.transform='scale(1.05)'; this.style.boxShadow='0 4px 12px rgba(0,0,0,0.3)'" 
                   onmouseout="this.style.background='#4a5fd9'; this.style.transform='scale(1)'; this.style.boxShadow='0 2px 8px rgba(0,0,0,0.2)'">
                    View Documentation →
                </a>
            </div>
        </div>
    </div>
    """
    
    return render_template_string(dashboard_template,
                                title="FAQ - Kubernetes AI Dashboard",
                                page="faq",
                                page_title="",
                                content=content,
                                current_year=datetime.datetime.now().year,
                                current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/docs/full-architecture')
@login_required
def docs_full_architecture():
    """Full Architecture documentation subpage."""
    import graphviz
    
    # Create the main architecture diagram - Compact version for web display
    dot = graphviz.Digraph(comment='K8s Multi-Agent Architecture')
    dot.attr(rankdir='TB', splines='ortho', nodesep='0.35', ranksep='0.6', bgcolor='white')
    dot.attr('node', shape='box', style='rounded,filled', fontname='Arial', fontsize='9', margin='0.2')
    dot.attr('edge', fontname='Arial', fontsize='8', color='#666666')
    
    # User Layer
    with dot.subgraph(name='cluster_user') as c:
        c.attr(label='👤 USER INTERFACE', style='filled,rounded', color='#E3F2FD', fontsize='11', fontname='Arial Bold', labeljust='l')
        c.node('CLI', '🖥️ CLI\n(cli.py)\nCommand: python cli.py -q "query"', fillcolor='#BBDEFB', shape='box', width='2.2')
        c.node('WebUI', '🌐 Web UI\n(Flask app.py:7000)\nBrowser Interface', fillcolor='#BBDEFB', shape='box', width='2.2')
    
    # Supervisor Layer with routing logic
    with dot.subgraph(name='cluster_supervisor') as c:
        c.attr(label='🎯 SUPERVISOR (LangGraph + Claude Sonnet 4.5)', style='filled,rounded', color='#C8E6C9', fontsize='11', fontname='Arial Bold', labeljust='l')
        c.node('Supervisor', '''🎯 Supervisor Agent\nRouting Logic:\n• Analyzes query keywords\n• Checks agent capabilities\n• Routes to best agent\n• Can call multiple agents''', 
               fillcolor='#A5D6A7', shape='box', style='rounded,filled,bold', width='3.5')
    
    # Agent Layer
    with dot.subgraph(name='cluster_agents') as c:
        c.attr(label='🤖 SPECIALIZED AGENTS (Each has LangGraph workflow)', style='filled,rounded', color='#FFF9C4', fontsize='11', fontname='Arial Bold', labeljust='l')
        c.node('HealthAgent', '''❤️ Health Agent\nHandles: health, status,\nready, liveness checks''', fillcolor='#FFF59D', width='1.8', height='0.9')
        c.node('DescribeAgent', '''📋 Describe Agent\nHandles: describe, get,\nshow details, config''', fillcolor='#FFF59D', width='1.8', height='0.9')
        c.node('ResourcesAgent', '''📊 Resources Agent\nHandles: capacity, limits,\nquotas, allocations''', fillcolor='#FFF59D', width='1.8', height='0.9')
        c.node('OperationsAgent', '''⚙️ Operations Agent\nHandles: create, delete,\nscale, apply, patch''', fillcolor='#FFF59D', width='1.8', height='0.9')
        c.node('MonitorAgent', '''📈 Monitor Agent\nHandles: metrics, CPU,\nmemory, Prometheus''', fillcolor='#FFF59D', width='1.8', height='0.9')
    
    # MCP Server Layer
    with dot.subgraph(name='cluster_mcp') as c:
        c.attr(label='🔌 MCP SERVERS (FastMCP - Model Context Protocol)', style='filled,rounded', color='#FFCDD2', fontsize='11', fontname='Arial Bold', labeljust='l')
        c.node('MCP_Health', '''🔌 Health MCP\n:8000\nTools:\n• check_pod_health\n• check_readiness''', fillcolor='#EF9A9A', shape='component', width='1.8', height='0.9')
        c.node('MCP_Describe', '''🔌 Describe MCP\n:8002\nTools:\n• describe_resource\n• get_yaml''', fillcolor='#EF9A9A', shape='component', width='1.8', height='0.9')
        c.node('MCP_Resources', '''🔌 Resources MCP\n:8001\nTools:\n• get_node_resources\n• get_pod_resources''', fillcolor='#EF9A9A', shape='component', width='1.8', height='0.9')
        c.node('MCP_Operations', '''🔌 Operations MCP\n:8003\nTools:\n• scale_deployment\n• create_resource''', fillcolor='#EF9A9A', shape='component', width='1.8', height='0.9')
        c.node('MCP_Monitor', '''🔌 Monitor MCP\n:8004\nTools:\n• query_prometheus\n• get_metrics''', fillcolor='#EF9A9A', shape='component', width='1.8', height='0.9')
    
    # Data Source Layer
    with dot.subgraph(name='cluster_sources') as c:
        c.attr(label='💾 DATA SOURCES', style='filled,rounded', color='#E1BEE7', fontsize='11', fontname='Arial Bold', labeljust='l')
        c.node('K8s', '''☸️ Kubernetes Cluster\nMaster: k8s-master-01 (10.138.0.2)\nWorker: k8s-worker-01 (10.138.0.3)\nAccess: SSH + kubectl commands''', fillcolor='#CE93D8', shape='cylinder', width='2.8', height='1.1')
        c.node('Prometheus', '''📊 Prometheus Server\nVM: prometheus-monitoring-01\nURL: http://35.233.152.108:9090\nData: node_exporter, cAdvisor,\nkube-state-metrics''', fillcolor='#CE93D8', shape='cylinder', width='2.8', height='1.1')
    
    # User to Supervisor edges
    dot.edge('CLI', 'Supervisor', label=' Query String ', color='#2196F3', penwidth='1.5', fontcolor='#2196F3')
    dot.edge('WebUI', 'Supervisor', label=' HTTP Request ', color='#2196F3', penwidth='1.5', fontcolor='#2196F3')
    
    # Supervisor to Agents with routing info
    dot.edge('Supervisor', 'HealthAgent', label=' "health" ', color='#4CAF50', penwidth='1.5', fontcolor='#4CAF50')
    dot.edge('Supervisor', 'DescribeAgent', label=' "describe" ', color='#4CAF50', penwidth='1.5', fontcolor='#4CAF50')
    dot.edge('Supervisor', 'ResourcesAgent', label=' "resources" ', color='#4CAF50', penwidth='1.5', fontcolor='#4CAF50')
    dot.edge('Supervisor', 'OperationsAgent', label=' "scale/create" ', color='#4CAF50', penwidth='1.5', fontcolor='#4CAF50')
    dot.edge('Supervisor', 'MonitorAgent', label=' "metrics" ', color='#4CAF50', penwidth='1.5', fontcolor='#4CAF50')
    
    # Agents to MCP Servers
    dot.edge('HealthAgent', 'MCP_Health', label=' HTTP POST\nMCP ', color='#FF9800', penwidth='1.5', style='dashed', fontcolor='#FF9800')
    dot.edge('DescribeAgent', 'MCP_Describe', label=' HTTP POST\nMCP ', color='#FF9800', penwidth='1.5', style='dashed', fontcolor='#FF9800')
    dot.edge('ResourcesAgent', 'MCP_Resources', label=' HTTP POST\nMCP ', color='#FF9800', penwidth='1.5', style='dashed', fontcolor='#FF9800')
    dot.edge('OperationsAgent', 'MCP_Operations', label=' HTTP POST\nMCP ', color='#FF9800', penwidth='1.5', style='dashed', fontcolor='#FF9800')
    dot.edge('MonitorAgent', 'MCP_Monitor', label=' HTTP POST\nMCP ', color='#FF9800', penwidth='1.5', style='dashed', fontcolor='#FF9800')
    
    # MCP Servers to Data Sources
    dot.edge('MCP_Health', 'K8s', label=' SSH\nkubectl get pods ', color='#9C27B0', penwidth='1.5', style='dotted', fontcolor='#9C27B0')
    dot.edge('MCP_Describe', 'K8s', label=' SSH\nkubectl describe ', color='#9C27B0', penwidth='1.5', style='dotted', fontcolor='#9C27B0')
    dot.edge('MCP_Resources', 'K8s', label=' SSH\nkubectl get nodes ', color='#9C27B0', penwidth='1.5', style='dotted', fontcolor='#9C27B0')
    dot.edge('MCP_Operations', 'K8s', label=' SSH\nkubectl scale/apply ', color='#9C27B0', penwidth='1.5', style='dotted', fontcolor='#9C27B0')
    dot.edge('MCP_Monitor', 'Prometheus', label=' HTTP GET\nPromQL Query ', color='#F44336', penwidth='1.5', style='dotted', fontcolor='#F44336')
    
    # Generate SVG
    svg_graph = dot.pipe(format='svg').decode('utf-8')
    
    content = f"""
    <style>
        /* Full width container only for architecture page */
        .architecture-full-width {{
            max-width: 100% !important;
            width: 100% !important;
            padding-left: 10px !important;
            padding-right: 10px !important;
        }}
        .architecture-diagram {{
            width: 100%;
            height: auto;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .architecture-diagram svg {{
            max-width: 100%;
            height: auto;
        }}
    </style>
    <div class="container-fluid architecture-full-width">
        <div class="row">
            <div class="col-12"
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <div>
                        <h2 style="color: #1a73e8; margin-bottom: 5px;">📊 Full Architecture</h2>
                        <nav aria-label="breadcrumb">
                            <ol class="breadcrumb" style="background: none; padding: 0; margin: 0;">
                                <li class="breadcrumb-item"><a href="/docs" style="color: #1a73e8;">Docs</a></li>
                                <li class="breadcrumb-item active">Full Architecture</li>
                            </ol>
                        </nav>
                    </div>
                </div>
                
                <div class="alert alert-info" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border: none; color: white; border-radius: 10px;">
                    <strong>💡 System Flow:</strong> User Query → Supervisor analyzes & routes → Agent calls tool via MCP → Tool executes on K8s/Prometheus → Response flows back
                </div>
                
                <section style="background: white; padding: 20px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 30px;">
                    <h3 style="color: #333; margin-bottom: 20px; border-bottom: 2px solid #1a73e8; padding-bottom: 10px;">
                        Complete System Architecture
                    </h3>
                    
                    <div class="architecture-diagram" style="text-align: center; background: #f8f9fa; padding: 15px; border-radius: 10px; width: 100%; overflow: hidden;">
                        {svg_graph}
                    </div>
                    
                    <div style="margin-top: 30px;">
                        <h4 style="color: #1a73e8; margin-bottom: 15px;">🔑 Key Components</h4>
                        <div class="row">
                            <div class="col-md-6">
                                <div style="background: #E3F2FD; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                                    <h5 style="color: #1976D2; margin-bottom: 10px;">👤 User Interface Layer</h5>
                                    <ul style="margin: 0; padding-left: 20px;">
                                        <li><strong>CLI (cli.py):</strong> Command-line interface for direct queries</li>
                                        <li><strong>Web UI (Flask app.py:7000):</strong> Browser-based dashboard interface</li>
                                    </ul>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div style="background: #C8E6C9; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                                    <h5 style="color: #388E3C; margin-bottom: 10px;">🎯 Supervisor Layer</h5>
                                    <ul style="margin: 0; padding-left: 20px;">
                                        <li><strong>LangGraph + Claude Sonnet 4.5</strong></li>
                                        <li>Analyzes query keywords and context</li>
                                        <li>Routes to appropriate specialized agent</li>
                                        <li>Can orchestrate multiple agents</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                        
                        <div class="row">
                            <div class="col-md-6">
                                <div style="background: #FFF9C4; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                                    <h5 style="color: #F57C00; margin-bottom: 10px;">🤖 Specialized Agents</h5>
                                    <ul style="margin: 0; padding-left: 20px;">
                                        <li><strong>❤️ Health Agent:</strong> Pod health, readiness, liveness checks</li>
                                        <li><strong>📋 Describe Agent:</strong> Resource details, YAML configs, descriptions</li>
                                        <li><strong>📊 Resources Agent:</strong> Capacity, limits, quotas, allocations</li>
                                        <li><strong>⚙️ Operations Agent:</strong> Create, delete, scale, apply operations</li>
                                        <li><strong>📈 Monitor Agent:</strong> Metrics, CPU, memory, Prometheus queries</li>
                                    </ul>
                                </div>
                            </div>
                            <div class="col-md-6">
                                <div style="background: #FFCDD2; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                                    <h5 style="color: #C62828; margin-bottom: 10px;">🔌 MCP Server Layer</h5>
                                    <ul style="margin: 0; padding-left: 20px;">
                                        <li><strong>FastMCP Protocol:</strong> Model Context Protocol implementation</li>
                                        <li><strong>Ports 8000-8004:</strong> Each agent has dedicated MCP server</li>
                                        <li><strong>Tool Execution:</strong> Agents call tools via HTTP POST</li>
                                        <li>Handles actual Kubernetes/Prometheus interactions</li>
                                    </ul>
                                </div>
                            </div>
                        </div>
                        
                        <div class="row">
                            <div class="col-md-12">
                                <div style="background: #E1BEE7; padding: 15px; border-radius: 8px; margin-bottom: 15px;">
                                    <h5 style="color: #6A1B9A; margin-bottom: 10px;">💾 Data Sources</h5>
                                    <div class="row">
                                        <div class="col-md-6">
                                            <strong>☸️ Kubernetes Cluster:</strong>
                                            <ul style="margin: 5px 0 0 20px;">
                                                <li>Master: k8s-master-01 (10.138.0.2)</li>
                                                <li>Worker: k8s-worker-01 (10.138.0.3)</li>
                                                <li>Access: SSH + kubectl commands</li>
                                            </ul>
                                        </div>
                                        <div class="col-md-6">
                                            <strong>📊 Prometheus Server:</strong>
                                            <ul style="margin: 5px 0 0 20px;">
                                                <li>VM: prometheus-monitoring-01</li>
                                                <li>URL: http://35.233.152.108:9090</li>
                                                <li>Exporters: node_exporter, cAdvisor, kube-state-metrics</li>
                                            </ul>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div style="margin-top: 30px; padding: 20px; background: #f0f7ff; border-left: 4px solid #1a73e8; border-radius: 5px;">
                        <h4 style="color: #1a73e8; margin-bottom: 15px;">🔄 Communication Flow</h4>
                        <ol style="margin: 0; padding-left: 20px; line-height: 2;">
                            <li><span style="color: #2196F3;">●</span> <strong>User → Supervisor:</strong> Query submitted via CLI or Web UI</li>
                            <li><span style="color: #4CAF50;">●</span> <strong>Supervisor → Agent:</strong> Routes based on keyword analysis</li>
                            <li><span style="color: #FF9800;">●</span> <strong>Agent → MCP Server:</strong> HTTP POST with MCP Protocol</li>
                            <li><span style="color: #9C27B0;">●</span> <strong>MCP → Kubernetes:</strong> SSH + kubectl commands</li>
                            <li><span style="color: #F44336;">●</span> <strong>MCP → Prometheus:</strong> HTTP GET with PromQL queries</li>
                            <li><strong>Response flows back:</strong> Data sources → MCP → Agent → Supervisor → User</li>
                        </ol>
                    </div>
                    
                    <div style="margin-top: 40px;">
                        <h3 style="color: #333; margin-bottom: 25px; border-bottom: 2px solid #1a73e8; padding-bottom: 10px;">
                            🔗 MCP Protocol Communication
                        </h3>
                        
                        <div class="row">
                            <div class="col-md-4">
                                <div style="background: #f8f9fa; color: #333; padding: 20px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border: 1px solid #dee2e6;">
                                    <h5 style="color: #1a73e8; margin-bottom: 15px; border-bottom: 2px solid #1a73e8; padding-bottom: 8px;">1️⃣ Agent → MCP Server</h5>
                                    <pre style="background: #ffffff; padding: 15px; border-radius: 5px; overflow-x: auto; font-size: 12px; line-height: 1.6; margin: 0; border: 1px solid #dee2e6;"><code style="color: #212529;">POST http://localhost:8000/mcp
Content-Type: application/json

{{
  "method": "tools/call",
  "params": {{
    "name": "check_pod_health",
    "arguments": {{
      "namespace": "kube-system"
    }}
  }}
}}</code></pre>
                                </div>
                            </div>
                            
                            <div class="col-md-4">
                                <div style="background: #f8f9fa; color: #333; padding: 20px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border: 1px solid #dee2e6;">
                                    <h5 style="color: #1a73e8; margin-bottom: 15px; border-bottom: 2px solid #1a73e8; padding-bottom: 8px;">2️⃣ MCP Server → K8s/Prometheus</h5>
                                    <pre style="background: #ffffff; padding: 15px; border-radius: 5px; overflow-x: auto; font-size: 12px; line-height: 1.6; margin: 0; border: 1px solid #dee2e6;"><code style="color: #212529;"># For Kubernetes tools:
SSH pggo890@k8s-master-01
→ kubectl get pods -n kube-system -o json

# For Prometheus tools:
GET http://35.233.152.108:9090/api/v1/query
→ ?query=up</code></pre>
                                </div>
                            </div>
                            
                            <div class="col-md-4">
                                <div style="background: #f8f9fa; color: #333; padding: 20px; border-radius: 8px; margin-bottom: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); border: 1px solid #dee2e6;">
                                    <h5 style="color: #1a73e8; margin-bottom: 15px; border-bottom: 2px solid #1a73e8; padding-bottom: 8px;">3️⃣ MCP Server → Agent</h5>
                                    <pre style="background: #ffffff; padding: 15px; border-radius: 5px; overflow-x: auto; font-size: 12px; line-height: 1.6; margin: 0; border: 1px solid #dee2e6;"><code style="color: #212529;">HTTP/1.1 200 OK
Content-Type: application/json

{{
  "result": {{
    "content": [
      {{
        "type": "text",
        "text": "Pod health report..."
      }}
    ]
  }}
}}</code></pre>
                                </div>
                            </div>
                        </div>
                    </div>
                    
                    <div style="margin-top: 30px; padding: 25px; background: #d4edda; border-left: 4px solid #28a745; border-radius: 8px;">
                        <h3 style="color: #155724; margin-bottom: 20px;">🎯 Key Architecture Insights:</h3>
                        <ol style="margin: 0; padding-left: 25px; line-height: 2; color: #155724;">
                            <li><strong>Separation of Concerns:</strong> Each agent specializes in one domain (health, operations, monitoring, etc.)</li>
                            <li><strong>MCP Protocol:</strong> Standardized communication between agents and tools via HTTP/JSON</li>
                            <li><strong>Multiple Data Sources:</strong> Kubernetes (via SSH + kubectl) and Prometheus (via HTTP API)</li>
                            <li><strong>Supervisor Pattern:</strong> Single entry point routes queries intelligently to specialized agents</li>
                            <li><strong>Scalable Design:</strong> Easy to add new agents or tools without modifying existing components</li>
                        </ol>
                    </div>
                    
                    <div style="margin-top: 20px; padding: 25px; background: #d1ecf1; border-left: 4px solid #0c5460; border-radius: 8px;">
                        <h4 style="color: #0c5460; margin-bottom: 15px;">💡 Want to see this in action? Try these queries in the CLI:</h4>
                        <ul style="margin: 0; padding-left: 25px; line-height: 2; color: #0c5460;">
                            <li><code style="background: #bee5eb; padding: 2px 6px; border-radius: 3px; color: #004085;">"Check health of all pods in kube-system"</code></li>
                            <li><code style="background: #bee5eb; padding: 2px 6px; border-radius: 3px; color: #004085;">"Show me CPU usage from Prometheus"</code></li>
                            <li><code style="background: #bee5eb; padding: 2px 6px; border-radius: 3px; color: #004085;">"Scale my deployment to 5 replicas"</code></li>
                        </ul>
                    </div>
                </section>
            </div>
        </div>
    </div>
    """
    
    return render_template_string(dashboard_template,
                                title="Full Architecture - Kubernetes AI Dashboard",
                                page="docs",
                                page_title="",
                                content=content,
                                current_year=datetime.datetime.now().year,
                                current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/docs/detailed-flow')
@login_required
def docs_detailed_flow():
    """Detailed Flow Examples documentation subpage."""
    
    # Create execution flow diagram for Health Agent
    health_flow = graphviz.Digraph()
    health_flow.attr(rankdir='TB')
    health_flow.attr('node', shape='box', style='rounded,filled', fontsize='10', width='3.5')
    
    health_flow.node('1', '1. User Query\n"Check pod health in kube-system"', fillcolor='#E3F2FD')
    health_flow.node('2', '2. Supervisor routes to Health Agent\n(keyword: "health")', fillcolor='#C8E6C9')
    health_flow.node('3', '3. Agent → MCP Client\nHTTP POST to localhost:8000/mcp', fillcolor='#FFF9C4')
    health_flow.node('4', '4. MCP Server receives request\nParses tool name & parameters', fillcolor='#FFCDD2')
    health_flow.node('5', '5. Tool executes:\ngcloud ssh to k8s-master-01', fillcolor='#F8BBD0')
    health_flow.node('6', '6. Run kubectl command:\nkubectl get pods -n kube-system -o json', fillcolor='#E1BEE7')
    health_flow.node('7', '7. K8s API returns JSON\nwith pod status, conditions', fillcolor='#D1C4E9')
    health_flow.node('8', '8. Parse JSON → Extract:\nname, status, ready, restarts', fillcolor='#FFCCBC')
    health_flow.node('9', '9. MCP Server → MCP Client\nHTTP 200 with health data', fillcolor='#C8E6C9')
    health_flow.node('10', '10. Agent formats response\nReturns to user', fillcolor='#B2DFDB')
    
    health_flow.edge('1', '2', label='query')
    health_flow.edge('2', '3', label='tool call')
    health_flow.edge('3', '4', label='HTTP')
    health_flow.edge('4', '5', label='invoke')
    health_flow.edge('5', '6', label='SSH')
    health_flow.edge('6', '7', label='kubectl')
    health_flow.edge('7', '8', label='JSON')
    health_flow.edge('8', '9', label='result')
    health_flow.edge('9', '10', label='response')
    
    health_flow_diagram = health_flow.pipe(format='svg').decode('utf-8')
    
    # Create execution flow diagram for Describe Agent
    describe_flow = graphviz.Digraph()
    describe_flow.attr(rankdir='TB')
    describe_flow.attr('node', shape='box', style='rounded,filled', fontsize='10', width='3.5')
    
    describe_flow.node('1', '1. User Query\n"Describe pod coredns-xxx"', fillcolor='#E3F2FD')
    describe_flow.node('2', '2. Supervisor routes to Describe Agent\n(keyword: "describe")', fillcolor='#C8E6C9')
    describe_flow.node('3', '3. Agent → MCP Client\nHTTP POST to localhost:8002/mcp', fillcolor='#FFF9C4')
    describe_flow.node('4', '4. MCP Server receives request\nExtracts: type=pod, name=coredns-xxx', fillcolor='#FFCDD2')
    describe_flow.node('5', '5. Tool executes:\ngcloud ssh to k8s-master-01', fillcolor='#F8BBD0')
    describe_flow.node('6', '6. Run kubectl describe:\nkubectl describe pod coredns-xxx', fillcolor='#E1BEE7')
    describe_flow.node('7', '7. K8s returns full description:\nspec, status, events', fillcolor='#D1C4E9')
    describe_flow.node('8', '8. MCP Server formats output\nReturns complete description', fillcolor='#FFCCBC')
    describe_flow.node('9', '9. Agent receives text\nPasses to Claude for analysis', fillcolor='#C8E6C9')
    describe_flow.node('10', '10. User gets formatted\nresource description', fillcolor='#B2DFDB')
    
    describe_flow.edge('1', '2')
    describe_flow.edge('2', '3')
    describe_flow.edge('3', '4')
    describe_flow.edge('4', '5')
    describe_flow.edge('5', '6')
    describe_flow.edge('6', '7')
    describe_flow.edge('7', '8')
    describe_flow.edge('8', '9')
    describe_flow.edge('9', '10')
    
    describe_flow_diagram = describe_flow.pipe(format='svg').decode('utf-8')
    
    # Create execution flow diagram for Resources Agent
    resources_flow = graphviz.Digraph()
    resources_flow.attr(rankdir='TB')
    resources_flow.attr('node', shape='box', style='rounded,filled', fontsize='10', width='3.5')
    
    resources_flow.node('1', '1. User Query\n"Show node resources"', fillcolor='#E3F2FD')
    resources_flow.node('2', '2. Supervisor routes to Resources Agent\n(keyword: "resources")', fillcolor='#C8E6C9')
    resources_flow.node('3', '3. Agent → MCP Client\nHTTP POST to localhost:8001/mcp', fillcolor='#FFF9C4')
    resources_flow.node('4', '4. MCP Server receives request\nPrepares kubectl command', fillcolor='#FFCDD2')
    resources_flow.node('5', '5. Tool executes:\ngcloud ssh to k8s-master-01', fillcolor='#F8BBD0')
    resources_flow.node('6', '6. Run: kubectl get nodes -o json\nGet all node specs', fillcolor='#E1BEE7')
    resources_flow.node('7', '7. K8s returns node data:\ncapacity, allocatable fields', fillcolor='#D1C4E9')
    resources_flow.node('8', '8. Parse each node:\nextract CPU, memory, storage', fillcolor='#FFCCBC')
    resources_flow.node('9', '9. MCP Server → Agent\nJSON with resource summary', fillcolor='#C8E6C9')
    resources_flow.node('10', '10. Agent formats output\nShows capacity vs allocatable', fillcolor='#B2DFDB')
    
    resources_flow.edge('1', '2')
    resources_flow.edge('2', '3')
    resources_flow.edge('3', '4')
    resources_flow.edge('4', '5')
    resources_flow.edge('5', '6')
    resources_flow.edge('6', '7')
    resources_flow.edge('7', '8')
    resources_flow.edge('8', '9')
    resources_flow.edge('9', '10')
    
    resources_flow_diagram = resources_flow.pipe(format='svg').decode('utf-8')
    
    # Create execution flow diagram for Operations Agent
    operations_flow = graphviz.Digraph()
    operations_flow.attr(rankdir='TB')
    operations_flow.attr('node', shape='box', style='rounded,filled', fontsize='10', width='3.5')
    
    operations_flow.node('1', '1. User Command\n"Scale deployment to 3 replicas"', fillcolor='#E3F2FD')
    operations_flow.node('2', '2. Supervisor routes to Operations Agent\n(keyword: "scale")', fillcolor='#C8E6C9')
    operations_flow.node('3', '3. Agent → MCP Client\nHTTP POST to localhost:8003/mcp', fillcolor='#FFF9C4')
    operations_flow.node('4', '4. MCP Server receives:\nname, replicas, namespace', fillcolor='#FFCDD2')
    operations_flow.node('5', '5. Tool executes:\ngcloud ssh to k8s-master-01', fillcolor='#F8BBD0')
    operations_flow.node('6', '6. Run: kubectl scale deployment\n--replicas=3', fillcolor='#E1BEE7')
    operations_flow.node('7', '7. K8s applies changes:\nupdates ReplicaSet', fillcolor='#D1C4E9')
    operations_flow.node('8', '8. Verify with kubectl get:\ncheck current vs desired', fillcolor='#FFCCBC')
    operations_flow.node('9', '9. MCP Server → Agent\nConfirmation with status', fillcolor='#C8E6C9')
    operations_flow.node('10', '10. Agent returns success:\nScaled to 3, Ready: 3/3', fillcolor='#B2DFDB')
    
    operations_flow.edge('1', '2')
    operations_flow.edge('2', '3')
    operations_flow.edge('3', '4')
    operations_flow.edge('4', '5')
    operations_flow.edge('5', '6')
    operations_flow.edge('6', '7')
    operations_flow.edge('7', '8')
    operations_flow.edge('8', '9')
    operations_flow.edge('9', '10')
    
    operations_flow_diagram = operations_flow.pipe(format='svg').decode('utf-8')
    
    # Create execution flow diagram for Monitor Agent
    monitor_flow = graphviz.Digraph()
    monitor_flow.attr(rankdir='TB')
    monitor_flow.attr('node', shape='box', style='rounded,filled', fontsize='10', width='3.5')
    
    monitor_flow.node('1', '1. User Query\n"Show me CPU usage"', fillcolor='#E3F2FD')
    monitor_flow.node('2', '2. Supervisor routes to Monitor Agent\n(keyword: "CPU usage")', fillcolor='#C8E6C9')
    monitor_flow.node('3', '3. Agent → MCP Client\nHTTP POST to localhost:8004/mcp', fillcolor='#FFF9C4')
    monitor_flow.node('4', '4. MCP Server receives request\nBuilds PromQL query', fillcolor='#FFCDD2')
    monitor_flow.node('5', '5. Tool executes:\nHTTP GET to Prometheus', fillcolor='#F8BBD0')
    monitor_flow.node('6', '6. Query Prometheus API:\n/api/v1/query?query=node_cpu...', fillcolor='#E1BEE7')
    monitor_flow.node('7', '7. Prometheus returns metrics:\nJSON with instance, value pairs', fillcolor='#D1C4E9')
    monitor_flow.node('8', '8. Parse metrics data:\nExtract instance & percentage', fillcolor='#FFCCBC')
    monitor_flow.node('9', '9. MCP Server → Agent\nReturns formatted metrics', fillcolor='#C8E6C9')
    monitor_flow.node('10', '10. Agent formats for user:\nmaster: 13%, worker: 7%', fillcolor='#B2DFDB')
    
    monitor_flow.edge('1', '2')
    monitor_flow.edge('2', '3')
    monitor_flow.edge('3', '4')
    monitor_flow.edge('4', '5')
    monitor_flow.edge('5', '6')
    monitor_flow.edge('6', '7')
    monitor_flow.edge('7', '8')
    monitor_flow.edge('8', '9')
    monitor_flow.edge('9', '10')
    
    monitor_flow_diagram = monitor_flow.pipe(format='svg').decode('utf-8')
    
    content = f"""
    <div class="container-fluid architecture-full-width">
        <div class="row">
            <div class="col-12">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <div>
                        <h2 style="color: #1a73e8; margin-bottom: 5px;">🔍 Detailed Flow Examples</h2>
                        <nav aria-label="breadcrumb">
                            <ol class="breadcrumb" style="background: none; padding: 0; margin: 0;">
                                <li class="breadcrumb-item"><a href="/docs" style="color: #1a73e8;">Docs</a></li>
                                <li class="breadcrumb-item active">Detailed Flow Examples</li>
                            </ol>
                        </nav>
                    </div>
                </div>
                
                <section style="background: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 30px;">
                    <h3 style="color: #333; margin-bottom: 20px; border-bottom: 2px solid #1a73e8; padding-bottom: 10px;">
                        🎯 How Supervisor Routes Queries
                    </h3>
                    
                    <div class="row">
                        <div class="col-md-6">
                            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                                <h5 style="color: #1a73e8; margin-bottom: 15px;">Supervisor's System Prompt</h5>
                                <pre style="background: #ffffff; padding: 15px; border-radius: 5px; font-size: 13px; line-height: 1.6; border: 1px solid #dee2e6;"><code style="color: #212529;"># Supervisor Agent receives:
user_query = "Check pod health in kube-system"

# Claude analyzes query using this prompt:
You are a supervisor routing queries to specialized agents:
- health_agent: Pod status, readiness, liveness checks
- describe_agent: Resource details, configurations
- resources_agent: CPU/memory capacity, limits
- operations_agent: Create, delete, scale resources  
- monitor_agent: Prometheus metrics, real-time data

Analyze the query and route to appropriate agent.</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-6">
                            <div style="background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                                <h5 style="color: #1a73e8; margin-bottom: 15px;">Routing Decision</h5>
                                <pre style="background: #ffffff; padding: 15px; border-radius: 5px; font-size: 13px; line-height: 1.6; border: 1px solid #dee2e6;"><code style="color: #212529;"># Claude's reasoning:
Query: "Check pod health in kube-system"

Analysis:
- Contains "health" keyword ✓
- Refers to "pod" status ✓
- About checking current state ✓

Decision: Route to HEALTH_AGENT

Response:
{{
  "next": "health_agent",
  "reasoning": "Query asks about pod health status"
}}</code></pre>
                            </div>
                        </div>
                    </div>
                </section>
                
                <section style="background: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 30px;">
                    <h3 style="color: #333; margin-bottom: 20px; border-bottom: 2px solid #28a745; padding-bottom: 10px;">
                        1️⃣ Health Agent → <code>check_pod_health</code> Tool
                    </h3>
                    
                    <div class="row">
                        <div class="col-md-6 mb-4">
                            <h5 style="color: #28a745; margin-bottom: 15px;">📝 Tool Definition</h5>
                            <pre style="background: #ffffff; padding: 20px; border-radius: 8px; font-size: 12px; line-height: 1.6; overflow-x: auto; border: 1px solid #dee2e6;"><code style="color: #212529;">@mcp.tool()
def check_pod_health(namespace: str = "default", pod_name: str = "") -> str:
    '''Check health status of pods'''
    
    # 1. Build kubectl command
    cmd = f"kubectl get pods -n {{namespace}} -o json"
    
    # 2. Execute via gcloud SSH to K8s master
    ssh_cmd = (
        f"gcloud compute ssh pggo890@k8s-master-01 "
        f"--zone=us-west1-a --project=beaming-age-463822-k7 "
        f"--command='{{cmd}}'"
    )
    result = subprocess.check_output(ssh_cmd, shell=True)
    
    # 3. Parse JSON response - Tool PARSES JSON:
    data = json.loads(result)
    pod = data["items"][0]
    
    name = pod["metadata"]["name"]
    status = pod["status"]["phase"]
    ready = "1/1"  # from conditions
    restarts = pod["status"]["containerStatuses"][0]["restartCount"]
    
    # Tool returns text:
    return f"Pod: {{name}}\\nStatus: {{status}}\\nReady: {{ready}}\\nRestarts: {{restarts}}"</code></pre>
                        </div>
                        
                        <div class="col-md-6 mb-4">
                            <h5 style="color: #28a745; margin-bottom: 15px;">🔄 Execution Flow</h5>
                            <div class="architecture-diagram">
                                {health_flow_diagram}
                            </div>
                        </div>
                    </div>
                    
                    <h5 style="color: #1a73e8; margin-bottom: 15px; margin-top: 20px;">📤 MCP Communication - Complete Round-Trip Flow</h5>
                    <div class="row">
                        <div class="col-md-4">
                            <div style="background: #e3f2fd; padding: 15px; border-radius: 8px; border-left: 4px solid #2196f3; margin-bottom: 15px;">
                                <h6 style="color: #1976d2; margin-bottom: 10px;">1️⃣ Agent → MCP Server</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code>POST http://localhost:8000/mcp

{{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {{
    "name": "check_pod_health",
    "arguments": {{
      "namespace": "kube-system"
    }}
  }}
}}</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #c8e6c9; padding: 15px; border-radius: 8px; border-left: 4px solid #4caf50; margin-bottom: 15px;">
                                <h6 style="color: #388e3c; margin-bottom: 10px;">2️⃣ MCP Server → Tool</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># MCP parses JSON-RPC request
# and invokes tool function:

check_pod_health(
    namespace="kube-system",
    pod_name=""
)</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #fff9c4; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107; margin-bottom: 15px;">
                                <h6 style="color: #f57c00; margin-bottom: 10px;">3️⃣ Tool → K8s Cluster</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># Tool executes:
gcloud compute ssh \\
  pggo890@k8s-master-01 \\
  --zone=us-west1-a \\
  --command="kubectl get pods \\
    -n kube-system -o json"</code></pre>
                            </div>
                        </div>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-4">
                            <div style="background: #ffcdd2; padding: 15px; border-radius: 8px; border-left: 4px solid #f44336; margin-bottom: 15px;">
                                <h6 style="color: #c62828; margin-bottom: 10px;">4️⃣ K8s Cluster → Tool</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># K8s returns RAW JSON:
{{
  "items": [{{
    "metadata": {{
      "name": "coredns-xxx"
    }},
    "status": {{
      "phase": "Running",
      "conditions": [{{
        "type": "Ready",
        "status": "True"
      }}],
      "containerStatuses": [{{
        "restartCount": 0
      }}]
    }}
  }}]
}}</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #e1bee7; padding: 15px; border-radius: 8px; border-left: 4px solid #9c27b0; margin-bottom: 15px;">
                                <h6 style="color: #6a1b9a; margin-bottom: 10px;">5️⃣ Tool Parses → MCP Server</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># Tool PARSES JSON:
data = json.loads(output)
pod = data["items"][0]

name = pod["metadata"]["name"]
status = pod["status"]["phase"]
ready = "1/1"
restarts = pod["status"]["containerStatuses"][0]["restartCount"]

# Tool returns text:
return f"Pod: {{name}}\\nStatus: {{status}}\\nReady: {{ready}}\\nRestarts: {{restarts}}"</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #b2dfdb; padding: 15px; border-radius: 8px; border-left: 4px solid #009688; margin-bottom: 15px;">
                                <h6 style="color: #00695c; margin-bottom: 10px;">6️⃣ MCP Server → Agent</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># MCP wraps tool output:
{{
  "jsonrpc": "2.0",
  "result": {{
    "content": [{{
      "type": "text",
      "text": "Pod: coredns-xxx
Status: Running
Ready: 1/1
Restarts: 0"
    }}]
  }}
}}

# Agent extracts:
text = response["result"]["content"][0]["text"]</code></pre>
                            </div>
                        </div>
                    </div>
                </section>
                
                <section style="background: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 30px;">
                    <h3 style="color: #333; margin-bottom: 20px; border-bottom: 2px solid #ff9800; padding-bottom: 10px;">
                        2️⃣ Describe Agent → <code>describe_resource</code> Tool
                    </h3>
                    
                    <div class="row">
                        <div class="col-md-6 mb-4">
                            <h5 style="color: #ff9800; margin-bottom: 15px;">📝 Tool Definition</h5>
                            <pre style="background: #ffffff; padding: 15px; border-radius: 8px; font-size: 12px; line-height: 1.6; border: 1px solid #dee2e6;"><code style="color: #212529;">@mcp.tool()
def describe_resource(
    resource_type: str,
    resource_name: str,
    namespace: str = "default"
) -> str:
    '''Get detailed info about a resource'''
    
    # 1. Build kubectl describe command
    cmd = f"kubectl describe {{resource_type}} {{resource_name}}"
    cmd += f" -n {{namespace}}"
    
    # 2. Execute via gcloud SSH to K8s master
    ssh_cmd = (
        f"gcloud compute ssh pggo890@k8s-master-01 "
        f"--zone=us-west1-a --project=beaming-age-463822-k7 "
        f"--command='{{cmd}}'"
    )
    result = subprocess.check_output(ssh_cmd, shell=True)
    
    # 3. Read output (detailed description)
    output = result.decode()
    
    # kubectl describe returns human-readable text (NOT JSON)
    # No parsing needed - just return as-is:
    return output
    
    # Output contains:
    # - Name, Namespace, Labels
    # - Status, Conditions
    # - Container specs, Volumes
    # - Events (last 10 minutes)</code></pre>
                        </div>
                        
                        <div class="col-md-6 mb-4">
                            <h5 style="color: #ff9800; margin-bottom: 15px;">🔄 Execution Flow</h5>
                            <div class="architecture-diagram">
                                {describe_flow_diagram}
                            </div>
                        </div>
                    </div>
                    
                    <h5 style="color: #ff9800; margin-bottom: 15px;">📤 Example Response</h5>
                    <pre style="background: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6; font-size: 12px;"><code>Name:         coredns-5dd5756b68-bhkdv
Namespace:    kube-system
Node:         k8s-master-01
Status:       Running
IP:           10.244.0.2
Containers:
  coredns:
    Image:      registry.k8s.io/coredns/coredns:v1.11.1
    Port:       53/UDP, 53/TCP
    State:      Running</code></pre>
                    
                    <h5 style="color: #1a73e8; margin-bottom: 15px; margin-top: 20px;">📤 MCP Communication - Complete Round-Trip Flow</h5>
                    <div class="row">
                        <div class="col-md-4">
                            <div style="background: #e3f2fd; padding: 15px; border-radius: 8px; border-left: 4px solid #2196f3; margin-bottom: 15px;">
                                <h6 style="color: #1976d2; margin-bottom: 10px;">1️⃣ Agent → MCP Server</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code>POST http://localhost:8002/mcp

{{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {{
    "name": "describe_resource",
    "arguments": {{
      "resource_type": "pod",
      "resource_name": "coredns-xxx",
      "namespace": "kube-system"
    }}
  }}
}}</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #c8e6c9; padding: 15px; border-radius: 8px; border-left: 4px solid #4caf50; margin-bottom: 15px;">
                                <h6 style="color: #388e3c; margin-bottom: 10px;">2️⃣ MCP Server → Tool</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># MCP parses and invokes:

describe_resource(
    resource_type="pod",
    resource_name="coredns-xxx",
    namespace="kube-system"
)</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #fff9c4; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107; margin-bottom: 15px;">
                                <h6 style="color: #f57c00; margin-bottom: 10px;">3️⃣ Tool → K8s Cluster</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># Tool executes:
gcloud compute ssh \\
  pggo890@k8s-master-01 \\
  --zone=us-west1-a \\
  --command="kubectl describe \\
    pod coredns-xxx \\
    -n kube-system"</code></pre>
                            </div>
                        </div>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-4">
                            <div style="background: #ffcdd2; padding: 15px; border-radius: 8px; border-left: 4px solid #f44336; margin-bottom: 15px;">
                                <h6 style="color: #c62828; margin-bottom: 10px;">4️⃣ K8s Cluster → Tool</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># K8s returns RAW TEXT:
Name:       coredns-xxx
Namespace:  kube-system
Node:       k8s-master-01
Status:     Running
IP:         10.244.0.2
Containers:
  coredns:
    Image:  coredns:v1.11.1
    State:  Running
Events:     &lt;none&gt;</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #e1bee7; padding: 15px; border-radius: 8px; border-left: 4px solid #9c27b0; margin-bottom: 15px;">
                                <h6 style="color: #6a1b9a; margin-bottom: 10px;">5️⃣ Tool Returns → MCP Server</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># Tool returns text as-is
# (kubectl describe already
# gives human-readable format)

return output
# No JSON parsing needed!

# Returns complete description
# text to MCP Server</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #b2dfdb; padding: 15px; border-radius: 8px; border-left: 4px solid #009688; margin-bottom: 15px;">
                                <h6 style="color: #00695c; margin-bottom: 10px;">6️⃣ MCP Server → Agent</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># MCP wraps tool output:
{{
  "jsonrpc": "2.0",
  "result": {{
    "content": [{{
      "type": "text",
      "text": "Name: coredns-xxx
Namespace: kube-system
Status: Running
IP: 10.244.0.2..."
    }}]
  }}
}}

# Agent extracts:
text = response["result"]["content"][0]["text"]</code></pre>
                            </div>
                        </div>
                    </div>
                </section>
                
                <section style="background: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 30px;">
                    <h3 style="color: #333; margin-bottom: 20px; border-bottom: 2px solid #2196f3; padding-bottom: 10px;">
                        3️⃣ Resources Agent → <code>get_node_resources</code> Tool
                    </h3>
                    
                    <div class="row">
                        <div class="col-md-6 mb-4">
                            <h5 style="color: #2196f3; margin-bottom: 15px;">📝 Tool Definition</h5>
                            <pre style="background: #ffffff; padding: 15px; border-radius: 8px; font-size: 12px; line-height: 1.6; border: 1px solid #dee2e6;"><code style="color: #212529;">@mcp.tool()
def get_node_resources() -> str:
    '''Get CPU and memory capacity of nodes'''
    
    # 1. Build kubectl command for node resources
    cmd = "kubectl get nodes -o json"
    
    # 2. Execute via gcloud SSH to K8s master
    ssh_cmd = (
        f"gcloud compute ssh pggo890@k8s-master-01 "
        f"--zone=us-west1-a --project=beaming-age-463822-k7 "
        f"--command='{{cmd}}'"
    )
    result = subprocess.check_output(ssh_cmd, shell=True).decode()
    
    # 3. Parse JSON to extract capacity/allocatable
    # Tool PARSES JSON:
    data = json.loads(result)
    node = data["items"][0]
    
    name = node["metadata"]["name"]
    cpu = node["status"]["capacity"]["cpu"]
    mem_ki = node["status"]["capacity"]["memory"]
    
    # Convert Ki to GiB:
    mem_gib = int(mem_ki.replace('Ki', '')) / 1024 / 1024
    
    # Tool returns text:
    return f"{{name}}:\\n    CPU: {{cpu}} cores\\n    Memory: {{mem_gib:.1f}} GiB"</code></pre>
                        </div>
                        
                        <div class="col-md-6 mb-4">
                            <h5 style="color: #2196f3; margin-bottom: 15px;">🔄 Execution Flow</h5>
                            <div class="architecture-diagram">
                                {resources_flow_diagram}
                            </div>
                        </div>
                    </div>
                    
                    <h5 style="color: #1a73e8; margin-bottom: 15px; margin-top: 20px;">📤 MCP Communication - Complete Round-Trip Flow</h5>
                    <div class="row">
                        <div class="col-md-4">
                            <div style="background: #e3f2fd; padding: 15px; border-radius: 8px; border-left: 4px solid #2196f3; margin-bottom: 15px;">
                                <h6 style="color: #1976d2; margin-bottom: 10px;">1️⃣ Agent → MCP Server</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code>POST http://localhost:8001/mcp

{{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {{
    "name": "get_node_resources",
    "arguments": {{}}
  }}
}}</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #c8e6c9; padding: 15px; border-radius: 8px; border-left: 4px solid #4caf50; margin-bottom: 15px;">
                                <h6 style="color: #388e3c; margin-bottom: 10px;">2️⃣ MCP Server → Tool</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># MCP parses JSON-RPC request
# and invokes tool function:

get_node_resources()</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #fff9c4; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107; margin-bottom: 15px;">
                                <h6 style="color: #f57c00; margin-bottom: 10px;">3️⃣ Tool → K8s Cluster</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># Tool executes:
gcloud compute ssh \\
  pggo890@k8s-master-01 \\
  --zone=us-west1-a \\
  --command="kubectl get nodes \\
    -o json"</code></pre>
                            </div>
                        </div>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-4">
                            <div style="background: #ffcdd2; padding: 15px; border-radius: 8px; border-left: 4px solid #f44336; margin-bottom: 15px;">
                                <h6 style="color: #c62828; margin-bottom: 10px;">4️⃣ K8s Cluster → Tool</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># K8s returns RAW JSON:
{{
  "items": [{{
    "metadata": {{
      "name": "k8s-master-01"
    }},
    "status": {{
      "capacity": {{
        "cpu": "2",
        "memory": "3926600Ki"
      }},
      "allocatable": {{
        "cpu": "2",
        "memory": "3824200Ki"
      }}
    }}
  }}]
}}</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #e1bee7; padding: 15px; border-radius: 8px; border-left: 4px solid #9c27b0; margin-bottom: 15px;">
                                <h6 style="color: #6a1b9a; margin-bottom: 10px;">5️⃣ Tool Parses → MCP Server</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># Tool PARSES JSON:
data = json.loads(output)
node = data["items"][0]

name = node["metadata"]["name"]
cpu = node["status"]["capacity"]["cpu"]
mem_ki = node["status"]["capacity"]["memory"]

# Convert Ki to GiB:
mem_gib = int(mem_ki.replace('Ki', '')) / 1024 / 1024

# Tool returns text:
return f"{{name}}:\\n    CPU: {{cpu}} cores\\n    Memory: {{mem_gib:.1f}} GiB"</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #b2dfdb; padding: 15px; border-radius: 8px; border-left: 4px solid #009688; margin-bottom: 15px;">
                                <h6 style="color: #00695c; margin-bottom: 10px;">6️⃣ MCP Server → Agent</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># MCP wraps tool output:
{{
  "jsonrpc": "2.0",
  "result": {{
    "content": [{{
      "type": "text",
      "text": "k8s-master-01:
    CPU: 2 cores
    Memory: 3.7 GiB
k8s-worker-01:
    CPU: 2 cores
    Memory: 3.7 GiB"
    }}]
  }}
}}

# Agent extracts:
text = response["result"]["content"][0]["text"]</code></pre>
                            </div>
                        </div>
                    </div>
                    
                    <h5 style="color: #2196f3; margin-bottom: 15px;">📤 Example Response</h5>
                    <pre style="background: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6; font-size: 12px;"><code>[
  {{
    "name": "k8s-master-01",
    "cpu": "2",
    "memory": "4007084Ki",
    "allocatable_cpu": "2",
    "allocatable_memory": "3884492Ki"
  }},
  {{
    "name": "k8s-worker-01",
    "cpu": "2",
    "memory": "4007076Ki",
    "allocatable_cpu": "2",
    "allocatable_memory": "3884484Ki"
  }}
]</code></pre>
                </section>
                
                <section style="background: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 30px;">
                    <h3 style="color: #333; margin-bottom: 20px; border-bottom: 2px solid #ff5722; padding-bottom: 10px;">
                        4️⃣ Operations Agent → <code>scale_deployment</code> Tool
                    </h3>
                    
                    <div class="row">
                        <div class="col-md-6 mb-4">
                            <h5 style="color: #ff5722; margin-bottom: 15px;">📝 Tool Definition</h5>
                            <pre style="background: #ffffff; padding: 15px; border-radius: 8px; font-size: 12px; line-height: 1.6; border: 1px solid #dee2e6;"><code style="color: #212529;">@mcp.tool()
def scale_deployment(
    deployment_name: str,
    replicas: int,
    namespace: str = "default"
) -> str:
    '''Scale a deployment to specified replicas'''
    
    # 1. Build kubectl scale command
    cmd = f"kubectl scale deployment {{deployment_name}}"
    cmd += f" --replicas={{replicas}} -n {{namespace}}"
    
    # 2. Execute via gcloud SSH to K8s master
    ssh_cmd = (
        f"gcloud compute ssh pggo890@k8s-master-01 "
        f"--zone=us-west1-a --project=beaming-age-463822-k7 "
        f"--command='{{cmd}}'"
    )
    scale_result = subprocess.check_output(ssh_cmd, shell=True).decode()
    # Output: "deployment.apps/nginx scaled"
    
    # 3. Verify the scaling worked
    verify_cmd = f"kubectl get deployment {{deployment_name}}"
    verify_cmd += f" -n {{namespace}} -o json"
    stdin, stdout, stderr = ssh_client.exec_command(verify_cmd)
    
    # Tool PARSES JSON:
    data = json.loads(output)
    
    name = data["metadata"]["name"]
    desired = data["spec"]["replicas"]
    current = data["status"]["replicas"]
    ready = data["status"]["readyReplicas"]
    
    # Tool returns text:
    return f"Successfully scaled deployment {{name}} to {{desired}} replicas.\\nCurrent status: {{ready}}/{{current}} ready"</code></pre>
                        </div>
                        
                        <div class="col-md-6 mb-4">
                            <h5 style="color: #ff5722; margin-bottom: 15px;">🔄 Execution Flow</h5>
                            <div class="architecture-diagram">
                                {operations_flow_diagram}
                            </div>
                        </div>
                    </div>
                    
                    <h5 style="color: #1a73e8; margin-bottom: 15px; margin-top: 20px;">📤 MCP Communication - Complete Round-Trip Flow</h5>
                    <div class="row">
                        <div class="col-md-4">
                            <div style="background: #e3f2fd; padding: 15px; border-radius: 8px; border-left: 4px solid #2196f3; margin-bottom: 15px;">
                                <h6 style="color: #1976d2; margin-bottom: 10px;">1️⃣ Agent → MCP Server</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code>POST http://localhost:8003/mcp

{{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {{
    "name": "scale_deployment",
    "arguments": {{
      "deployment_name": "nginx",
      "replicas": 3,
      "namespace": "default"
    }}
  }}
}}</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #c8e6c9; padding: 15px; border-radius: 8px; border-left: 4px solid #4caf50; margin-bottom: 15px;">
                                <h6 style="color: #388e3c; margin-bottom: 10px;">2️⃣ MCP Server → Tool</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># MCP parses JSON-RPC request
# and invokes tool function:

scale_deployment(
    deployment_name="nginx",
    replicas=3,
    namespace="default"
)</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #fff9c4; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107; margin-bottom: 15px;">
                                <h6 style="color: #f57c00; margin-bottom: 10px;">3️⃣ Tool → K8s Cluster</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># Tool executes:
gcloud compute ssh \\
  pggo890@k8s-master-01 \\
  --zone=us-west1-a \\
  --command="kubectl scale \\
    deployment nginx \\
    --replicas=3 -n default &amp;&amp; \\
    kubectl get deployment nginx \\
    -n default -o json"</code></pre>
                            </div>
                        </div>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-4">
                            <div style="background: #ffcdd2; padding: 15px; border-radius: 8px; border-left: 4px solid #f44336; margin-bottom: 15px;">
                                <h6 style="color: #c62828; margin-bottom: 10px;">4️⃣ K8s Cluster → Tool</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># K8s returns RAW JSON:
{{
  "metadata": {{
    "name": "nginx"
  }},
  "spec": {{
    "replicas": 3
  }},
  "status": {{
    "replicas": 3,
    "readyReplicas": 3,
    "availableReplicas": 3
  }}
}}</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #e1bee7; padding: 15px; border-radius: 8px; border-left: 4px solid #9c27b0; margin-bottom: 15px;">
                                <h6 style="color: #6a1b9a; margin-bottom: 10px;">5️⃣ Tool Parses → MCP Server</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># Tool PARSES JSON:
data = json.loads(output)

name = data["metadata"]["name"]
desired = data["spec"]["replicas"]
current = data["status"]["replicas"]
ready = data["status"]["readyReplicas"]

# Tool returns text:
return f"Successfully scaled deployment {{name}} to {{desired}} replicas. Current status: {{ready}}/{{current}} ready"</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #b2dfdb; padding: 15px; border-radius: 8px; border-left: 4px solid #009688; margin-bottom: 15px;">
                                <h6 style="color: #00695c; margin-bottom: 10px;">6️⃣ MCP Server → Agent</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># MCP wraps tool output:
{{
  "jsonrpc": "2.0",
  "result": {{
    "content": [{{
      "type": "text",
      "text": "Successfully scaled deployment nginx to 3 replicas.
Current status: 3/3 ready"
    }}]
  }}
}}

# Agent extracts:
text = response["result"]["content"][0]["text"]</code></pre>
                            </div>
                        </div>
                    </div>
                    
                    <h5 style="color: #ff5722; margin-bottom: 15px;">📤 Example Response</h5>
                    <pre style="background: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6; font-size: 12px;"><code>deployment.apps/nginx-deployment scaled

NAME               READY   UP-TO-DATE   AVAILABLE   AGE
nginx-deployment   3/3     3            3           10m</code></pre>
                </section>
                
                <section style="background: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 30px;">
                    <h3 style="color: #333; margin-bottom: 20px; border-bottom: 2px solid #9c27b0; padding-bottom: 10px;">
                        5️⃣ Monitor Agent → <code>query_prometheus_instant</code> Tool
                    </h3>
                    
                    <div class="row">
                        <div class="col-md-6 mb-4">
                            <h5 style="color: #9c27b0; margin-bottom: 15px;">📝 Tool Definition</h5>
                            <pre style="background: #ffffff; padding: 15px; border-radius: 8px; font-size: 12px; line-height: 1.6; border: 1px solid #dee2e6;"><code style="color: #212529;">@mcp.tool()
def query_prometheus_instant(
    query: str,
    time: str = ""
) -> str:
    '''Execute instant Prometheus query'''
    
    # 1. Build Prometheus API URL
    PROMETHEUS_URL = "http://35.233.152.108:9090"
    url = f"{{PROMETHEUS_URL}}/api/v1/query"
    
    # 2. Prepare query parameters
    params = {{"query": query}}
    if time:
        params["time"] = time  # Unix timestamp
    
    # Example query:
    # "node_memory_MemTotal_bytes" - Total memory
    # "100 - (node_memory_MemAvailable_bytes / 
    #         node_memory_MemTotal_bytes * 100)" - Memory usage %
    
    # 3. Execute HTTP GET request
    response = requests.get(url, params=params, timeout=10)
    
    # 4. Parse JSON response
    # Tool PARSES JSON:
    data = response.json()
    results = data["data"]["result"]
    
    metrics = []
    for r in results:
        instance = r["metric"]["instance"]
        # e.g. "10.138.0.2:9100"
        
        value = r["value"][1]
        # e.g. "15.23"
        
        # Map IP to node name:
        node = map_ip_to_node(instance)
        
        metrics.append(f"{{node}}: {{value}}%")
    
    # Tool returns text:
    return '\\n'.join(metrics)</code></pre>
                        </div>
                        
                        <div class="col-md-6 mb-4">
                            <h5 style="color: #9c27b0; margin-bottom: 15px;">🔄 Execution Flow</h5>
                            <div class="architecture-diagram">
                                {monitor_flow_diagram}
                            </div>
                        </div>
                    </div>
                    
                    <h5 style="color: #1a73e8; margin-bottom: 15px; margin-top: 20px;">📤 MCP Communication & Prometheus Query</h5>
                    <div class="row">
                        <div class="col-md-4">
                            <div style="background: #e3f2fd; padding: 15px; border-radius: 8px; border-left: 4px solid #2196f3; margin-bottom: 15px;">
                                <h6 style="color: #1976d2; margin-bottom: 10px;">1️⃣ Agent → MCP Server</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code>POST http://localhost:8004/mcp

{{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {{
    "name": "query_prometheus_instant",
    "arguments": {{
      "query": "100 - (avg by(instance) 
        (rate(node_cpu_seconds_total
        {{mode='idle'}}[5m])) * 100)"
    }}
  }}
}}</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #c8e6c9; padding: 15px; border-radius: 8px; border-left: 4px solid #4caf50; margin-bottom: 15px;">
                                <h6 style="color: #388e3c; margin-bottom: 10px;">2️⃣ MCP Server → Tool</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># MCP parses JSON-RPC request
# and invokes tool function:

query_prometheus_instant(
    query="100 - (avg by(instance) 
      (rate(node_cpu_seconds_total
      {{mode='idle'}}[5m])) * 100)"
)</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #fff9c4; padding: 15px; border-radius: 8px; border-left: 4px solid #ffc107; margin-bottom: 15px;">
                                <h6 style="color: #f57c00; margin-bottom: 10px;">3️⃣ Tool → Prometheus</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># Tool executes HTTP request:
GET http://35.233.152.108:9090/api/v1/query

Query params:
query=100 - (avg by(instance)
  (rate(node_cpu_seconds_total
  {{mode='idle'}}[5m])) * 100)</code></pre>
                            </div>
                        </div>
                    </div>
                    
                    <div class="row">
                        <div class="col-md-4">
                            <div style="background: #ffcdd2; padding: 15px; border-radius: 8px; border-left: 4px solid #f44336; margin-bottom: 15px;">
                                <h6 style="color: #c62828; margin-bottom: 10px;">4️⃣ Prometheus → Tool</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># Prometheus returns RAW JSON:
{{
  "status": "success",
  "data": {{
    "resultType": "vector",
    "result": [
      {{
        "metric": {{
          "instance": "10.138.0.2:9100"
        }},
        "value": [1234567, "15.23"]
      }},
      {{
        "metric": {{
          "instance": "10.138.0.3:9100"
        }},
        "value": [1234567, "8.45"]
      }}
    ]
  }}
}}</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #e1bee7; padding: 15px; border-radius: 8px; border-left: 4px solid #9c27b0; margin-bottom: 15px;">
                                <h6 style="color: #6a1b9a; margin-bottom: 10px;">5️⃣ Tool Parses → MCP Server</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># Tool PARSES JSON:
data = response.json()
results = data["data"]["result"]

metrics = []
for r in results:
    instance = r["metric"]["instance"]
    # e.g. "10.138.0.2:9100"
    
    value = r["value"][1]
    # e.g. "15.23"
    
    # Map IP to node name:
    node = map_ip_to_node(instance)
    
    metrics.append(f"{{node}}: {{value}}%")

# Tool returns text:
return '\\n'.join(metrics)</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4">
                            <div style="background: #b2dfdb; padding: 15px; border-radius: 8px; border-left: 4px solid #009688; margin-bottom: 15px;">
                                <h6 style="color: #00695c; margin-bottom: 10px;">6️⃣ MCP Server → Agent</h6>
                                <pre style="background: white; padding: 12px; border-radius: 5px; font-size: 11px; margin: 0;"><code># MCP wraps tool output:
{{
  "jsonrpc": "2.0",
  "result": {{
    "content": [{{
      "type": "text",
      "text": "k8s-master-01: 15.23%
k8s-worker-01: 8.45%"
    }}]
  }}
}}

# Agent extracts:
text = response["result"]["content"][0]["text"]</code></pre>
                            </div>
                        </div>
                    </div>
                </section>
                
                <hr style="margin: 40px 0; border: 0; border-top: 2px solid #dee2e6;">
                
                <section style="background: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 30px;">
                    <h3 style="color: #333; margin-bottom: 20px; border-bottom: 2px solid #1a73e8; padding-bottom: 10px;">
                        🔗 MCP Protocol Communication
                    </h3>
                    
                    <div class="row">
                        <div class="col-md-4 mb-3">
                            <div style="background: #e3f2fd; padding: 20px; border-radius: 8px; border-left: 4px solid #2196f3;">
                                <h5 style="color: #1976d2; margin-bottom: 15px;">1️⃣ Agent → MCP Server</h5>
                                <pre style="background: white; padding: 15px; border-radius: 5px; font-size: 12px; margin: 0;"><code>POST http://localhost:8000/mcp
Content-Type: application/json

{{
  "method": "tools/call",
  "params": {{
    "name": "check_pod_health",
    "arguments": {{
      "namespace": "kube-system"
    }}
  }}
}}</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4 mb-3">
                            <div style="background: #c8e6c9; padding: 20px; border-radius: 8px; border-left: 4px solid #4caf50;">
                                <h5 style="color: #388e3c; margin-bottom: 15px;">2️⃣ MCP Server → K8s/Prometheus</h5>
                                <pre style="background: white; padding: 15px; border-radius: 5px; font-size: 12px; margin: 0;"><code># For Kubernetes tools:
SSH pggo890@k8s-master-01
→ kubectl get pods -n kube-system -o json

# For Prometheus tools:
GET http://35.233.152.108:9090/api/v1/query
→ ?query=up</code></pre>
                            </div>
                        </div>
                        
                        <div class="col-md-4 mb-3">
                            <div style="background: #fff9c4; padding: 20px; border-radius: 8px; border-left: 4px solid #ffc107;">
                                <h5 style="color: #f57c00; margin-bottom: 15px;">3️⃣ MCP Server → Agent</h5>
                                <pre style="background: white; padding: 15px; border-radius: 5px; font-size: 12px; margin: 0;"><code>HTTP/1.1 200 OK
Content-Type: application/json

{{
  "result": {{
    "content": [
      {{
        "type": "text",
        "text": "Pod health report..."
      }}
    ]
  }}
}}</code></pre>
                            </div>
                        </div>
                    </div>
                </section>
                
                <div style="margin-top: 30px; padding: 25px; background: #d1ecf1; border-left: 4px solid #0c5460; border-radius: 8px;">
                    <h4 style="color: #0c5460; margin-bottom: 15px;">💡 Key Takeaways</h4>
                    <ul style="margin: 0; padding-left: 25px; line-height: 2; color: #0c5460;">
                        <li><strong>Tool Diversity:</strong> Some tools parse JSON (like check_pod_health), others return raw text (like describe_resource)</li>
                        <li><strong>MCP Standard:</strong> All communication uses JSON-RPC 2.0 protocol regardless of tool implementation</li>
                        <li><strong>Agent Intelligence:</strong> Claude analyzes tool outputs and formats responses in natural language</li>
                        <li><strong>Separation of Concerns:</strong> Tools handle data retrieval, Agents handle interpretation</li>
                        <li><strong>Error Handling:</strong> Each layer (Agent, MCP, Tool, K8s) can fail independently with proper error propagation</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
    """
    
    return render_template_string(dashboard_template,
                                title="Detailed Flow Examples - Kubernetes AI Dashboard",
                                page="docs",
                                page_title="",
                                content=content,
                                current_year=datetime.datetime.now().year,
                                current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/docs/component-glossary')
@login_required
def docs_component_glossary():
    """Component Glossary documentation subpage."""
    
    content = f"""
    <div class="container-fluid architecture-full-width">
        <div class="row">
            <div class="col-12">
                <div class="d-flex justify-content-between align-items-center mb-4">
                    <div>
                        <h2 style="color: #1a73e8; margin-bottom: 5px;">📖 Component Glossary</h2>
                        <nav aria-label="breadcrumb">
                            <ol class="breadcrumb" style="background: none; padding: 0; margin: 0;">
                                <li class="breadcrumb-item"><a href="/docs" style="color: #1a73e8;">Docs</a></li>
                                <li class="breadcrumb-item active">Component Glossary</li>
                            </ol>
                        </nav>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6 mb-4">
                        <div style="background: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); height: 100%;">
                            <h4 style="color: #1a73e8; margin-bottom: 20px; border-bottom: 2px solid #1a73e8; padding-bottom: 10px;">🎯 Supervisor Agent</h4>
                            <div style="background: #e3f2fd; padding: 20px; border-radius: 8px; border-left: 4px solid #2196f3;">
                                <p style="margin: 0; line-height: 1.8; color: #424242;">
                                    <strong>Role:</strong> Query router and orchestrator<br><br>
                                    <strong>Technology:</strong> LangGraph workflow with Claude Sonnet 4.5<br><br>
                                    <strong>Function:</strong> Analyzes user queries and routes them to the appropriate specialized agent. 
                                    Maintains conversation context and combines responses from multiple agents when needed.
                                </p>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6 mb-4">
                        <div style="background: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); height: 100%;">
                            <h4 style="color: #28a745; margin-bottom: 20px; border-bottom: 2px solid #28a745; padding-bottom: 10px;">❤️ Health Agent</h4>
                            <div style="background: #d4edda; padding: 20px; border-radius: 8px; border-left: 4px solid #28a745;">
                                <p style="margin: 0; line-height: 1.8; color: #424242;">
                                    <strong>Specialization:</strong> Pod health monitoring<br><br>
                                    <strong>Tools:</strong> check_pod_health, check_pod_readiness, check_pod_liveness<br><br>
                                    <strong>Data Source:</strong> Kubernetes API via kubectl
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6 mb-4">
                        <div style="background: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); height: 100%;">
                            <h4 style="color: #ff9800; margin-bottom: 20px; border-bottom: 2px solid #ff9800; padding-bottom: 10px;">📋 Describe Agent</h4>
                            <div style="background: #fff3e0; padding: 20px; border-radius: 8px; border-left: 4px solid #ff9800;">
                                <p style="margin: 0; line-height: 1.8; color: #424242;">
                                    <strong>Specialization:</strong> Resource details and configurations<br><br>
                                    <strong>Tools:</strong> describe_resource, get_resource_yaml, get_resource_events<br><br>
                                    <strong>Data Source:</strong> Kubernetes API via kubectl describe/get
                                </p>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6 mb-4">
                        <div style="background: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); height: 100%;">
                            <h4 style="color: #2196f3; margin-bottom: 20px; border-bottom: 2px solid #2196f3; padding-bottom: 10px;">📊 Resources Agent</h4>
                            <div style="background: #e3f2fd; padding: 20px; border-radius: 8px; border-left: 4px solid #2196f3;">
                                <p style="margin: 0; line-height: 1.8; color: #424242;">
                                    <strong>Specialization:</strong> Capacity planning and resource allocation<br><br>
                                    <strong>Tools:</strong> get_node_resources, get_pod_resources, get_namespace_quota<br><br>
                                    <strong>Data Source:</strong> Kubernetes API via kubectl
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6 mb-4">
                        <div style="background: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); height: 100%;">
                            <h4 style="color: #ff5722; margin-bottom: 20px; border-bottom: 2px solid #ff5722; padding-bottom: 10px;">⚙️ Operations Agent</h4>
                            <div style="background: #fbe9e7; padding: 20px; border-radius: 8px; border-left: 4px solid #ff5722;">
                                <p style="margin: 0; line-height: 1.8; color: #424242;">
                                    <strong>Specialization:</strong> Cluster modifications<br><br>
                                    <strong>Tools:</strong> scale_deployment, create_resource, delete_resource, apply_yaml<br><br>
                                    <strong>Data Source:</strong> Kubernetes API via kubectl (write operations)
                                </p>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6 mb-4">
                        <div style="background: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); height: 100%;">
                            <h4 style="color: #9c27b0; margin-bottom: 20px; border-bottom: 2px solid #9c27b0; padding-bottom: 10px;">📈 Monitor Agent</h4>
                            <div style="background: #f3e5f5; padding: 20px; border-radius: 8px; border-left: 4px solid #9c27b0;">
                                <p style="margin: 0; line-height: 1.8; color: #424242;">
                                    <strong>Specialization:</strong> Real-time metrics and monitoring<br><br>
                                    <strong>Tools:</strong> query_prometheus_instant, query_prometheus_range, get_node_metrics, get_pod_metrics<br><br>
                                    <strong>Data Source:</strong> Prometheus HTTP API (PromQL queries)
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6 mb-4">
                        <div style="background: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); height: 100%;">
                            <h4 style="color: #00897b; margin-bottom: 20px; border-bottom: 2px solid #00897b; padding-bottom: 10px;">🔌 MCP Servers</h4>
                            <div style="background: #e0f2f1; padding: 20px; border-radius: 8px; border-left: 4px solid #00897b;">
                                <p style="margin: 0; line-height: 1.8; color: #424242;">
                                    <strong>Technology:</strong> FastMCP (Model Context Protocol)<br><br>
                                    <strong>Protocol:</strong> HTTP/JSON over ports 8000-8004<br><br>
                                    <strong>Function:</strong> Expose tools as API endpoints that agents can call. Handle authentication, 
                                    command execution, and response formatting.
                                </p>
                            </div>
                        </div>
                    </div>
                    
                    <div class="col-md-6 mb-4">
                        <div style="background: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); height: 100%;">
                            <h4 style="color: #326ce5; margin-bottom: 20px; border-bottom: 2px solid #326ce5; padding-bottom: 10px;">☸️ Kubernetes Cluster</h4>
                            <div style="background: #e8f0fe; padding: 20px; border-radius: 8px; border-left: 4px solid #326ce5;">
                                <p style="margin: 0; line-height: 1.8; color: #424242;">
                                    <strong>Access Method:</strong> SSH to master node + kubectl commands<br><br>
                                    <strong>Components:</strong> 2 nodes (master + worker), various system pods<br><br>
                                    <strong>Monitoring:</strong> node_exporter, cAdvisor, kube-state-metrics
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div class="row">
                    <div class="col-md-6 mb-4">
                        <div style="background: white; padding: 25px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); height: 100%;">
                            <h4 style="color: #e6522c; margin-bottom: 20px; border-bottom: 2px solid #e6522c; padding-bottom: 10px;">📊 Prometheus</h4>
                            <div style="background: #fbe9e7; padding: 20px; border-radius: 8px; border-left: 4px solid #e6522c;">
                                <p style="margin: 0; line-height: 1.8; color: #424242;">
                                    <strong>Location:</strong> prometheus-monitoring-01 VM (35.233.152.108:9090)<br><br>
                                    <strong>Scrapers:</strong> node_exporter (node metrics), cAdvisor (container metrics), 
                                    kube-state-metrics (K8s object state)<br><br>
                                    <strong>Access:</strong> HTTP API with PromQL query language
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
                
                <div style="margin-top: 30px; padding: 25px; background: #d1ecf1; border-left: 4px solid #0c5460; border-radius: 8px;">
                    <h4 style="color: #0c5460; margin-bottom: 15px;">🎯 Key Architecture Insights</h4>
                    <ul style="margin: 0; padding-left: 25px; line-height: 2; color: #0c5460;">
                        <li><strong>Separation of Concerns:</strong> Each agent specializes in one domain (health, operations, monitoring, etc.)</li>
                        <li><strong>MCP Protocol:</strong> Standardized communication between agents and tools via HTTP/JSON</li>
                        <li><strong>Multiple Data Sources:</strong> Kubernetes (via SSH + kubectl) and Prometheus (via HTTP API)</li>
                        <li><strong>Supervisor Pattern:</strong> Single entry point routes queries intelligently to specialized agents</li>
                        <li><strong>Scalable Design:</strong> Easy to add new agents or tools without modifying existing components</li>
                    </ul>
                </div>
                
                <div style="margin-top: 20px; padding: 25px; background: #e8f5e9; border-left: 4px solid #4caf50; border-radius: 8px;">
                    <h4 style="color: #2e7d32; margin-bottom: 15px;">💡 Want to see this in action?</h4>
                    <p style="margin: 0; line-height: 2; color: #2e7d32;">Try these queries in the CLI:</p>
                    <ul style="margin: 10px 0 0 25px; padding: 0; line-height: 2; color: #2e7d32;">
                        <li>"Check health of all pods in kube-system"</li>
                        <li>"Show me CPU usage from Prometheus"</li>
                        <li>"Scale my deployment to 5 replicas"</li>
                    </ul>
                </div>
            </div>
        </div>
    </div>
    """
    
    return render_template_string(dashboard_template,
                                title="Component Glossary - Kubernetes AI Dashboard",
                                page="docs",
                                page_title="",
                                content=content,
                                current_year=datetime.datetime.now().year,
                                current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

@app.route('/api/vm-data')
@login_required
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
@login_required
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
@login_required
def clear_logs():
    """API endpoint to clear command logs."""
    global command_logs
    command_logs.clear()
    return jsonify({'status': 'success', 'message': 'Logs cleared'})

@app.route('/api/kubectl', methods=['POST'])
@login_required
def execute_kubectl():
    """
    API endpoint to execute kubectl commands with RBAC protection.
    
    RBAC Rules:
    - Viewers: Read-only commands (get, describe, logs)
    - Operators: Read + safe operations (scale, rollout restart)
    - Admins: Full access (including delete, apply)
    """
    data = request.get_json()
    command = data.get('command', '').strip()
    
    if not command:
        return jsonify({'success': False, 'error': 'No command provided'}), 400
    
    # Parse command to detect operation type
    command_lower = command.lower()
    
    # Destructive operations - Admin only
    destructive_ops = ['delete', 'drain', 'cordon', 'taint', 'label --overwrite']
    if any(op in command_lower for op in destructive_ops):
        if not current_user.can_delete():
            return jsonify({
                'success': False, 
                'error': f'❌ Admin role required for destructive operations (delete, drain, cordon). Your role: {current_user.role}'
            }), 403
    
    # Write operations - Operator or Admin
    write_ops = ['apply', 'create', 'scale', 'patch', 'edit', 'rollout', 'set']
    if any(op in command_lower for op in write_ops):
        if not current_user.can_operate():
            return jsonify({
                'success': False, 
                'error': f'❌ Operator or Admin role required for write operations. Your role: {current_user.role}'
            }), 403
    
    # Execute command (all read operations allowed for all roles)
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
@login_required
def chat():
    """
    API endpoint for AI chat using LangGraph K8s Agent with smart caching.
    Includes RBAC protection for write and delete operations.
    """
    try:
        data = request.get_json()
        message = data.get('message', '')
        client_cache = data.get('clientCache', {})  # Client-side cached data from other tabs
        
        if not message:
            return jsonify({'success': False, 'error': 'No message provided'})
        
        # ===== RBAC PERMISSION CHECKS =====
        message_lower = message.lower()
        
        # Detect destructive operations - Admin only
        destructive_keywords = ['delete', 'drain', 'cordon', 'remove']
        if any(keyword in message_lower for keyword in destructive_keywords):
            if not current_user.can_delete():
                return jsonify({
                    'success': False, 
                    'error': f'🔒 <strong>Admin role required</strong><br><br>Your role (<strong>{current_user.role}</strong>) cannot perform destructive operations like delete, drain, or cordon.<br><br>Contact an administrator for assistance.'
                }), 403
        
        # Detect write operations - Operator or Admin
        write_keywords = ['scale', 'restart', 'rollout', 'patch', 'apply', 'create', 'set', 'edit', 'update']
        if any(keyword in message_lower for keyword in write_keywords):
            if not current_user.can_operate():
                return jsonify({
                    'success': False, 
                    'error': f'🔒 <strong>Operator or Admin role required</strong><br><br>Your role (<strong>{current_user.role}</strong>) is read-only and cannot perform write operations like scale, restart, or apply changes.<br><br>Contact an administrator to upgrade your permissions.'
                }), 403
        
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


# ============================================================================
# USER MANAGEMENT ROUTES (Admin Only)
# ============================================================================

@app.route('/user-management')
@login_required
def user_management():
    """
    User Management page - Admin only
    Allows creating, editing, and deleting users
    """
    # Check if user is admin
    if not current_user.is_admin():
        flash('❌ Admin access required for User Management', 'error')
        return redirect(url_for('home'))
    
    # Get all users from database
    users = User.query.all()
    
    content = f"""
    <div style="margin: -120px -40px -70px -40px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 40px; text-align: center;">
            <h2 style="margin: 0; font-size: 2rem; font-weight: 600; color: white;">👥 User Management</h2>
            <p style="margin: 10px 0 0 0; opacity: 0.9; font-size: 1rem; color: white;">Manage users and access permissions</p>
        </div>
        
        <div style="padding: 30px; background: white;">
            
            <!-- Add New User Button -->
            <div style="margin-bottom: 30px;">
                <button onclick="showAddUserModal()" style="
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    border: none;
                    padding: 12px 24px;
                    border-radius: 8px;
                    font-size: 1rem;
                    font-weight: 600;
                    cursor: pointer;
                    transition: transform 0.2s;
                " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
                    ➕ Add New User
                </button>
            </div>
            
            <!-- Users Table -->
            <div style="overflow-x: auto; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);">
                <table style="width: 100%; border-collapse: collapse; background: white;">
                    <thead>
                        <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                            <th style="padding: 15px; text-align: left; color: white; font-weight: 600;">ID</th>
                            <th style="padding: 15px; text-align: left; color: white; font-weight: 600;">Username</th>
                            <th style="padding: 15px; text-align: left; color: white; font-weight: 600;">Role</th>
                            <th style="padding: 15px; text-align: left; color: white; font-weight: 600;">Created At</th>
                            <th style="padding: 15px; text-align: left; color: white; font-weight: 600;">Last Login</th>
                            <th style="padding: 15px; text-align: center; color: white; font-weight: 600;">Actions</th>
                        </tr>
                    </thead>
                    <tbody>
                        {''.join([f'''
                        <tr style="border-bottom: 1px solid #e2e8f0;">
                            <td style="padding: 15px; color: #2d3748;">{user.id}</td>
                            <td style="padding: 15px; color: #2d3748; font-weight: 600;">{user.username}</td>
                            <td style="padding: 15px;">
                                <span style="
                                    display: inline-block;
                                    padding: 4px 12px;
                                    border-radius: 12px;
                                    font-size: 0.85rem;
                                    font-weight: 600;
                                    background: {'#fef3c7' if user.role == 'admin' else '#dbeafe' if user.role == 'operator' else '#f3f4f6'};
                                    color: {'#92400e' if user.role == 'admin' else '#1e40af' if user.role == 'operator' else '#374151'};
                                ">
                                    {'👑 ' if user.role == 'admin' else '🔧 ' if user.role == 'operator' else '👁️ '}{user.role.capitalize()}
                                </span>
                            </td>
                            <td style="padding: 15px; color: #718096; font-size: 0.9rem;">{user.created_at.strftime('%Y-%m-%d %H:%M') if user.created_at else 'N/A'}</td>
                            <td style="padding: 15px; color: #718096; font-size: 0.9rem;">{user.last_login.strftime('%Y-%m-%d %H:%M') if user.last_login else 'Never'}</td>
                            <td style="padding: 15px; text-align: center;">
                                <button onclick="changePassword({user.id}, '{user.username}')" style="
                                    background: #3b82f6;
                                    color: white;
                                    border: none;
                                    padding: 6px 12px;
                                    border-radius: 6px;
                                    margin-right: 8px;
                                    cursor: pointer;
                                    font-size: 0.85rem;
                                ">🔑 Password</button>
                                {'<button onclick="deleteUser(' + str(user.id) + ', \'' + user.username + '\')" style="background: #ef4444; color: white; border: none; padding: 6px 12px; border-radius: 6px; cursor: pointer; font-size: 0.85rem;">🗑️ Delete</button>' if user.id != current_user.id else '<span style="color: #9ca3af; font-size: 0.85rem;">(Current User)</span>'}
                            </td>
                        </tr>
                        ''' for user in users])}
                    </tbody>
                </table>
            </div>
            
            <!-- Stats -->
            <div style="margin-top: 30px; display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;">
                <div style="background: linear-gradient(135deg, #fef3c7, #fde68a); padding: 20px; border-radius: 12px; text-align: center;">
                    <div style="font-size: 2rem; font-weight: bold; color: #92400e;">{sum(1 for u in users if u.role == 'admin')}</div>
                    <div style="color: #92400e; font-weight: 600; margin-top: 5px;">👑 Admins</div>
                </div>
                <div style="background: linear-gradient(135deg, #dbeafe, #bfdbfe); padding: 20px; border-radius: 12px; text-align: center;">
                    <div style="font-size: 2rem; font-weight: bold; color: #1e40af;">{sum(1 for u in users if u.role == 'operator')}</div>
                    <div style="color: #1e40af; font-weight: 600; margin-top: 5px;">🔧 Operators</div>
                </div>
                <div style="background: linear-gradient(135deg, #f3f4f6, #e5e7eb); padding: 20px; border-radius: 12px; text-align: center;">
                    <div style="font-size: 2rem; font-weight: bold; color: #374151;">{sum(1 for u in users if u.role == 'viewer')}</div>
                    <div style="color: #374151; font-weight: 600; margin-top: 5px;">👁️ Viewers</div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Add User Modal -->
    <div id="addUserModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center;">
        <div style="background: white; padding: 30px; border-radius: 16px; max-width: 500px; width: 90%;">
            <h3 style="margin: 0 0 20px 0; color: #2d3748;">➕ Add New User</h3>
            <form id="addUserForm">
                <div style="margin-bottom: 15px;">
                    <label style="display: block; color: #4a5568; font-weight: 600; margin-bottom: 5px;">Username</label>
                    <input type="text" id="newUsername" required style="width: 100%; padding: 10px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 1rem;">
                </div>
                <div style="margin-bottom: 15px;">
                    <label style="display: block; color: #4a5568; font-weight: 600; margin-bottom: 5px;">Password</label>
                    <input type="password" id="newPassword" required style="width: 100%; padding: 10px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 1rem;">
                </div>
                <div style="margin-bottom: 20px;">
                    <label style="display: block; color: #4a5568; font-weight: 600; margin-bottom: 5px;">Role</label>
                    <select id="newRole" style="width: 100%; padding: 10px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 1rem;">
                        <option value="viewer">👁️ Viewer (Read-only)</option>
                        <option value="operator">🔧 Operator (Read + Write)</option>
                        <option value="admin">👑 Admin (Full access)</option>
                    </select>
                </div>
                <div style="display: flex; gap: 10px;">
                    <button type="submit" style="flex: 1; background: linear-gradient(135deg, #667eea, #764ba2); color: white; border: none; padding: 12px; border-radius: 8px; font-weight: 600; cursor: pointer;">Create User</button>
                    <button type="button" onclick="closeAddUserModal()" style="flex: 1; background: #e5e7eb; color: #4a5568; border: none; padding: 12px; border-radius: 8px; font-weight: 600; cursor: pointer;">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <!-- Change Password Modal -->
    <div id="changePasswordModal" style="display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 1000; align-items: center; justify-content: center;">
        <div style="background: white; padding: 30px; border-radius: 16px; max-width: 500px; width: 90%;">
            <h3 style="margin: 0 0 20px 0; color: #2d3748;">🔑 Change Password</h3>
            <p style="color: #718096; margin-bottom: 20px;">Changing password for: <strong id="changePasswordUsername"></strong></p>
            <form id="changePasswordForm">
                <input type="hidden" id="changePasswordUserId">
                <div style="margin-bottom: 20px;">
                    <label style="display: block; color: #4a5568; font-weight: 600; margin-bottom: 5px;">New Password</label>
                    <input type="password" id="changePasswordNew" required style="width: 100%; padding: 10px; border: 2px solid #e2e8f0; border-radius: 8px; font-size: 1rem;">
                </div>
                <div style="display: flex; gap: 10px;">
                    <button type="submit" style="flex: 1; background: #3b82f6; color: white; border: none; padding: 12px; border-radius: 8px; font-weight: 600; cursor: pointer;">Update Password</button>
                    <button type="button" onclick="closeChangePasswordModal()" style="flex: 1; background: #e5e7eb; color: #4a5568; border: none; padding: 12px; border-radius: 8px; font-weight: 600; cursor: pointer;">Cancel</button>
                </div>
            </form>
        </div>
    </div>
    
    <script>
        // Add User Modal Functions
        function showAddUserModal() {{
            document.getElementById('addUserModal').style.display = 'flex';
        }}
        
        function closeAddUserModal() {{
            document.getElementById('addUserModal').style.display = 'none';
            document.getElementById('addUserForm').reset();
        }}
        
        // Change Password Modal Functions
        function changePassword(userId, username) {{
            document.getElementById('changePasswordUserId').value = userId;
            document.getElementById('changePasswordUsername').textContent = username;
            document.getElementById('changePasswordModal').style.display = 'flex';
        }}
        
        function closeChangePasswordModal() {{
            document.getElementById('changePasswordModal').style.display = 'none';
            document.getElementById('changePasswordForm').reset();
        }}
        
        // Add User Form Submit
        document.getElementById('addUserForm').addEventListener('submit', async (e) => {{
            e.preventDefault();
            
            const username = document.getElementById('newUsername').value;
            const password = document.getElementById('newPassword').value;
            const role = document.getElementById('newRole').value;
            
            try {{
                const response = await fetch('/api/users/create', {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{username, password, role}})
                }});
                
                const data = await response.json();
                
                if (data.success) {{
                    alert('✅ User created successfully!');
                    location.reload();
                }} else {{
                    alert('❌ Error: ' + data.error);
                }}
            }} catch (error) {{
                alert('❌ Error creating user: ' + error.message);
            }}
        }});
        
        // Change Password Form Submit
        document.getElementById('changePasswordForm').addEventListener('submit', async (e) => {{
            e.preventDefault();
            
            const userId = document.getElementById('changePasswordUserId').value;
            const newPassword = document.getElementById('changePasswordNew').value;
            
            try {{
                const response = await fetch(`/api/users/${{userId}}/change-password`, {{
                    method: 'POST',
                    headers: {{'Content-Type': 'application/json'}},
                    body: JSON.stringify({{password: newPassword}})
                }});
                
                const data = await response.json();
                
                if (data.success) {{
                    alert('✅ Password updated successfully!');
                    closeChangePasswordModal();
                }} else {{
                    alert('❌ Error: ' + data.error);
                }}
            }} catch (error) {{
                alert('❌ Error changing password: ' + error.message);
            }}
        }});
        
        // Delete User Function
        async function deleteUser(userId, username) {{
            if (!confirm(`⚠️ Are you sure you want to delete user "${{username}}"?\\n\\nThis action cannot be undone.`)) {{
                return;
            }}
            
            try {{
                const response = await fetch(`/api/users/${{userId}}`, {{
                    method: 'DELETE'
                }});
                
                const data = await response.json();
                
                if (data.success) {{
                    alert('✅ User deleted successfully!');
                    location.reload();
                }} else {{
                    alert('❌ Error: ' + data.error);
                }}
            }} catch (error) {{
                alert('❌ Error deleting user: ' + error.message);
            }}
        }}
    </script>
    """
    
    return render_template_string(dashboard_template, 
                                title="User Management",
                                page="user-management",
                                content=content,
                                current_year=datetime.datetime.now().year,
                                current_time=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


@app.route('/api/users/create', methods=['POST'])
@login_required
def api_create_user():
    """Create a new user - Admin only"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    data = request.get_json()
    username = data.get('username', '').strip()
    password = data.get('password', '')
    role = data.get('role', 'viewer')
    
    # Validate inputs
    if not username or not password:
        return jsonify({'success': False, 'error': 'Username and password are required'}), 400
    
    if role not in ['viewer', 'operator', 'admin']:
        return jsonify({'success': False, 'error': 'Invalid role'}), 400
    
    # Check if username already exists
    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'error': 'Username already exists'}), 400
    
    try:
        # Create new user
        new_user = User(username=username, role=role)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'User {username} created successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/users/<int:user_id>/change-password', methods=['POST'])
@login_required
def api_change_password(user_id):
    """Change user password - Admin only"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    data = request.get_json()
    new_password = data.get('password', '')
    
    if not new_password:
        return jsonify({'success': False, 'error': 'Password is required'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    
    try:
        user.set_password(new_password)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Password updated for {user.username}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@login_required
def api_delete_user(user_id):
    """Delete a user - Admin only"""
    if not current_user.is_admin():
        return jsonify({'success': False, 'error': 'Admin access required'}), 403
    
    # Cannot delete yourself
    if user_id == current_user.id:
        return jsonify({'success': False, 'error': 'Cannot delete your own account'}), 400
    
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False, 'error': 'User not found'}), 404
    
    try:
        username = user.username
        db.session.delete(user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'User {username} deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    import socket
    
    # Get WSL2 IP address
    hostname = socket.gethostname()
    wsl_ip = socket.gethostbyname(hostname)
    
    print("\n" + "="*60)
    print("🚀 K8s Multi-Agent Dashboard Started!")
    print("="*60)
    print(f"📍 Local URL:      http://localhost:7000")
    print(f"📍 WSL2 URL:       http://{wsl_ip}:7000")
    print(f"📍 Network URL:    http://0.0.0.0:7000")
    print("="*60 + "\n")
    
    app.run(host='0.0.0.0', port=7000, debug=True)
