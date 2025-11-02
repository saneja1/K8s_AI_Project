# K8s Tools Reference - For Future Agents

This document contains tools from the old `k8s_tools.py` file that can be used when creating new specialized agents.

## Tools Already Migrated:

### Health Agent (in health_agent.py):
- ✅ `get_cluster_nodes()` - List all nodes with status
- ✅ `get_cluster_events(namespace)` - Get cluster events

### Describe Agent (in describe_agent.py):
- ✅ `list_k8s_resources(resource_type, namespace)` - Generic list tool
- ✅ `describe_k8s_resource(resource_type, resource_name, namespace)` - Generic describe tool
- ✅ `count_k8s_resources(resource_type, namespace, filter_by, filter_value)` - Generic count tool
- ✅ `get_all_resources_in_namespace(namespace)` - kubectl get all
- ✅ `get_resource_yaml(resource_type, resource_name, namespace)` - Get YAML

---

## Tools Available for Future Agents:

### 1. get_pod_logs (for Operations/Monitor Agent)
```python
@tool
def get_pod_logs(pod_name: str, namespace: str = "default", tail: int = 50) -> str:
    """
    Get logs from a specific pod. Auto-detects full pod name from partial name.
    Args:
        pod_name: Full or partial name of the pod
        namespace: Namespace of the pod (default: "default")
        tail: Number of recent log lines (default: 50)
    Returns:
        Pod logs
    """
    import subprocess
    
    try:
        # First, find the full pod name if partial name given
        get_pods_cmd = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -n {namespace} -o name"
        pods_result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
            "--zone=us-central1-a",
            f"--command={get_pods_cmd}",
            "--quiet"
        ], capture_output=True, text=True, timeout=8)
        
        if pods_result.returncode == 0:
            full_pod_name = pod_name
            for line in pods_result.stdout.strip().split('\n'):
                if pod_name.lower() in line.lower():
                    full_pod_name = line.replace('pod/', '').strip()
                    break
        else:
            full_pod_name = pod_name
        
        # Get logs
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl logs {full_pod_name} -n {namespace} --tail={tail}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
            "--zone=us-central1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=8)
        
        if result.returncode == 0:
            return result.stdout if result.stdout else "No logs available"
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"
```

**Use case:** Operations Agent for troubleshooting pods

---

### 2. count_pods_on_node (for Operations Agent)
```python
@tool
def count_pods_on_node(node_name: str) -> str:
    """
    Count how many pods are running on a specific node.
    Args:
        node_name: Name of the node (e.g., 'k8s-master-001', 'k8s-worker-01')
    Returns:
        Count of pods on that node with pod names listed
    """
    import subprocess
    try:
        full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods --all-namespaces -o wide"
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
            "--zone=us-central1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=8)
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        # Count pods on this node
        lines = result.stdout.split('\n')
        pod_count = 0
        pod_names = []
        
        for line in lines[1:]:  # Skip header
            if node_name in line:
                pod_count += 1
                parts = line.split()
                if len(parts) >= 2:
                    pod_names.append(f"{parts[0]}/{parts[1]}")
        
        response = f"Found {pod_count} pods on node '{node_name}':\n\n"
        for pod in pod_names:
            response += f"- {pod}\n"
        
        return response
        
    except Exception as e:
        return f"Error executing command: {str(e)}"
```

**Use case:** Operations Agent for node management

**Note:** This can be replaced by Describe Agent's `count_k8s_resources('pods', 'all', 'node', node_name)` generic tool.

---

## Caching Helper Function:

```python
import time

_cache = {}
_cache_ttl = 30

def _cached_kubectl_command(cache_key, execute_fn):
    """Helper to cache kubectl command results for 30 seconds"""
    current_time = time.time()
    
    if cache_key in _cache:
        result, timestamp = _cache[cache_key]
        if current_time - timestamp < _cache_ttl:
            return result
    
    result = execute_fn()
    _cache[cache_key] = (result, current_time)
    return result
```

---

## Future Agent Recommendations:

### Operations Agent:
- `get_pod_logs` ✅
- `restart_pod` (new - to be created)
- `scale_deployment` (new - to be created)
- `delete_pod` (new - to be created)

### Monitor Agent:
- `get_pod_logs` ✅
- `get_resource_usage` (new - top pods, top nodes)
- `get_metrics` (new - if metrics-server installed)

### Resources Agent:
- `get_node_capacity` (can use Describe's describe_k8s_resource)
- `get_resource_quotas` (new)
- `get_limit_ranges` (new)

### Security Agent:
- `list_secrets` (can use Describe's list_k8s_resources)
- `list_rbac_roles` (new)
- `list_network_policies` (new)
- `check_pod_security` (new)

---

## Migration Complete:
- ✅ Health Agent has 2 tools defined internally
- ✅ Describe Agent has 5 generic tools defined internally
- ✅ k8s_tools.py can now be safely removed
- ✅ Future agents can copy tools from this reference document
