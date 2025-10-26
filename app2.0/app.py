from flask import Flask, render_template_string
import datetime

app = Flask(__name__)

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
    content = """
    <h2>🖥️ Virtual Machine Status</h2>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0;">
        <div style="padding: 20px; background: #f0fff4; border-radius: 8px; text-align: center;">
            <h3 style="color: #38a169;">Active VMs</h3>
            <div style="font-size: 36px; font-weight: bold; color: #38a169; margin: 10px 0;">3</div>
            <p style="color: #718096;">Currently Running</p>
        </div>
        <div style="padding: 20px; background: #fffaf0; border-radius: 8px; text-align: center;">
            <h3 style="color: #d69e2e;">Pending VMs</h3>
            <div style="font-size: 36px; font-weight: bold; color: #d69e2e; margin: 10px 0;">1</div>
            <p style="color: #718096;">Starting Up</p>
        </div>
        <div style="padding: 20px; background: #fed7d7; border-radius: 8px; text-align: center;">
            <h3 style="color: #e53e3e;">Offline VMs</h3>
            <div style="font-size: 36px; font-weight: bold; color: #e53e3e; margin: 10px 0;">0</div>
            <p style="color: #718096;">Not Responding</p>
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
                        <th style="padding: 12px; text-align: left; border-bottom: 2px solid #e2e8f0;">Uptime</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;"><strong>k8s-master-01</strong></td>
                        <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;"><span class="status-indicator status-online"></span>Running</td>
                        <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">45%</td>
                        <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">2.1GB / 4GB</td>
                        <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">2d 14h</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;"><strong>k8s-worker-01</strong></td>
                        <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;"><span class="status-indicator status-online"></span>Running</td>
                        <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">32%</td>
                        <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">1.8GB / 4GB</td>
                        <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">2d 14h</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;"><strong>k8s-worker-02</strong></td>
                        <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;"><span class="status-indicator status-online"></span>Running</td>
                        <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">28%</td>
                        <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">1.5GB / 4GB</td>
                        <td style="padding: 12px; border-bottom: 1px solid #e2e8f0;">2d 14h</td>
                    </tr>
                </tbody>
            </table>
        </div>
        <div style="margin-top: 20px; display: flex; gap: 15px; flex-wrap: wrap;">
            <button class="card-button" style="width: auto; padding: 10px 20px;">Refresh Status</button>
            <button class="card-button" style="width: auto; padding: 10px 20px;">Export Report</button>
        </div>
    </div>
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=7000, debug=True)
