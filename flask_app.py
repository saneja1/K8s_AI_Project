from flask import Flask, render_template, jsonify
import time
import subprocess
import json

app = Flask(__name__)
start_time = time.time()

def get_pods_info():
    """Get information about all pods in the cluster."""
    try:
        result = subprocess.run([
            "kubectl", "get", "pods", "--all-namespaces", "-o", "json"
        ], capture_output=True, text=True, timeout=15)
        
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
                    'restarts': 0
                }
                
                # Calculate ready containers
                container_statuses = pod['status'].get('containerStatuses', [])
                ready_containers = sum(1 for c in container_statuses if c.get('ready', False))
                total_containers = len(container_statuses)
                pod_info['ready'] = f"{ready_containers}/{total_containers}"
                
                # Count restarts
                pod_info['restarts'] = sum(c.get('restartCount', 0) for c in container_statuses)
                
                pods_data.append(pod_info)
        
        return pods_data
    except Exception as e:
        return []

@app.route('/')
@app.route('/<page>')
def home(page='ai_llm'):
    load_time_ms = (time.time() - start_time) * 1000
    
    # Get pods data if on pod_monitor page
    pods_data = []
    if page == 'pod_monitor':
        pods_data = get_pods_info()
    
    return render_template('dashboard.html', 
                          active_page=page, 
                          load_time=load_time_ms,
                          pods=pods_data)

@app.route('/api/pods')
def api_pods():
    """API endpoint to get pod data"""
    pods_data = get_pods_info()
    return jsonify(pods_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=False)
