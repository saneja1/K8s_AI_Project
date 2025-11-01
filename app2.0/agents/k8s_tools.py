"""
Kubernetes Tools - kubectl commands via SSH
Separated from agent logic for better organization
"""

import time
from langchain_core.tools import tool

# Simple cache for kubectl responses (30 second TTL)
_kubectl_cache = {}
_cache_ttl = 30


# ============================================================================
# CACHING HELPER (Speed Optimization)
# ============================================================================

def _cached_kubectl_command(cache_key: str, command_func, *args, **kwargs):
    """Cache kubectl responses for 30 seconds to speed up repeated queries."""
    current_time = time.time()
    
    # Check cache
    if cache_key in _kubectl_cache:
        cached_result, timestamp = _kubectl_cache[cache_key]
        if current_time - timestamp < _cache_ttl:
            return cached_result
    
    # Execute command and cache result
    result = command_func(*args, **kwargs)
    _kubectl_cache[cache_key] = (result, current_time)
    
    # Clean old cache entries (keep cache small)
    for key in list(_kubectl_cache.keys()):
        if current_time - _kubectl_cache[key][1] > _cache_ttl:
            del _kubectl_cache[key]
    
    return result


# ============================================================================
# KUBERNETES TOOLS (kubectl commands via SSH)
# ============================================================================

@tool
def get_cluster_pods(namespace: str = "all") -> str:
    """
    Get list of all pods in the cluster or specific namespace.
    Args:
        namespace: Namespace to filter pods (default: "all" for all namespaces)
    Returns:
        String with pod information
    """
    cache_key = f"pods_{namespace}"
    
    def _execute():
        import subprocess
        try:
            if namespace == "all":
                full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods --all-namespaces -o wide"
            else:
                full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -n {namespace} -o wide"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
                "--zone=us-central1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=8)
            
            if result.returncode == 0:
                return result.stdout
            else:
                return f"Error: {result.stderr}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    return _cached_kubectl_command(cache_key, _execute)


@tool
def get_cluster_nodes() -> str:
    """
    Get list of all nodes in the cluster with detailed information.
    Returns:
        String with node information including status, roles, age, and version
    """
    cache_key = "nodes"
    
    def _execute():
        import subprocess
        try:
            full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get nodes -o wide"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
                "--zone=us-central1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=8)
            
            if result.returncode == 0:
                return result.stdout
            else:
                return f"Error: {result.stderr}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    return _cached_kubectl_command(cache_key, _execute)


@tool
def describe_node(node_name: str) -> str:
    """
    Get detailed information about a specific node including taints, labels, and conditions.
    Args:
        node_name: Name of the node (e.g., 'k8s-master-001' or 'k8s-worker-01')
    Returns:
        Detailed node description including taints, capacity, allocatable resources, and conditions
    """
    import subprocess
    
    try:
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl describe node {node_name}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
            "--zone=us-central1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=8)
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


@tool
def describe_pod(pod_name: str, namespace: str = "default") -> str:
    """
    Get detailed information about a specific pod.
    Args:
        pod_name: Name of the pod
        namespace: Namespace of the pod (default: "default")
    Returns:
        Detailed pod description including events, status, and configuration
    """
    import subprocess
    
    try:
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl describe pod {pod_name} -n {namespace}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
            "--zone=us-central1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=8)
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


@tool
def get_pod_logs(pod_name: str, namespace: str = "default", tail: int = 50) -> str:
    """
    Get logs from a specific pod.
    Args:
        pod_name: Name of the pod
        namespace: Namespace of the pod (default: "default")
        tail: Number of recent log lines to retrieve (default: 50)
    Returns:
        Pod logs
    """
    import subprocess
    
    try:
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl logs {pod_name} -n {namespace} --tail={tail}"
        
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


@tool
def get_cluster_events(namespace: str = "all") -> str:
    """
    Get cluster events to see what's happening in the cluster.
    Args:
        namespace: Namespace to filter events (default: "all" for all namespaces)
    Returns:
        String with cluster events
    """
    cache_key = f"events_{namespace}"
    
    def _execute():
        import subprocess
        try:
            if namespace == "all":
                full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get events --all-namespaces --sort-by='.lastTimestamp'"
            else:
                full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get events -n {namespace} --sort-by='.lastTimestamp'"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
                "--zone=us-central1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=8)
            
            if result.returncode == 0:
                return result.stdout
            else:
                return f"Error: {result.stderr}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    return _cached_kubectl_command(cache_key, _execute)


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
            "--zone=us-central1-a", f"--command={full_command}", "--quiet"
        ], capture_output=True, text=True, timeout=8)
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        count, pod_list = 0, []
        for line in result.stdout.strip().split('\n'):
            if node_name in line:
                count += 1
                parts = line.split()
                if len(parts) >= 2:
                    pod_list.append(parts[1])
        
        return f"Count: {count} pods on {node_name}\nPods: {', '.join(pod_list)}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool
def count_resources(resource_type: str, filter_by: str, filter_value: str) -> str:
    """
    Generic tool to count Kubernetes resources with flexible filtering.
    Args:
        resource_type: Type of resource ('pods', 'nodes', 'services', 'deployments')
        filter_by: Field to filter by ('status', 'namespace', 'node', 'ready')
        filter_value: Value to match (e.g., 'Running', 'kube-system', 'k8s-master-001', 'true')
    Returns:
        Count with list of matching resources
    Examples:
        count_resources('pods', 'status', 'Running') -> counts running pods
        count_resources('pods', 'namespace', 'kube-system') -> counts pods in kube-system
        count_resources('pods', 'ready', '0/1') -> counts pods not ready
    """
    import subprocess
    try:
        # Build kubectl command based on resource type
        if resource_type == "pods":
            full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods --all-namespaces -o wide"
        elif resource_type == "nodes":
            full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get nodes -o wide"
        elif resource_type == "services":
            full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get services --all-namespaces"
        elif resource_type == "deployments":
            full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get deployments --all-namespaces"
        else:
            return f"Error: Unsupported resource_type '{resource_type}'"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
            "--zone=us-central1-a", f"--command={full_command}", "--quiet"
        ], capture_output=True, text=True, timeout=8)
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        # Parse and filter results
        lines = result.stdout.strip().split('\n')
        header = lines[0].split() if lines else []
        count, resource_list = 0, []
        
        # Map filter_by to column index
        filter_col_map = {
            'namespace': 0, 'status': 3, 'ready': 2, 'node': 7,
            'name': 1, 'age': 5, 'ip': 6
        }
        
        col_idx = filter_col_map.get(filter_by.lower())
        if col_idx is None:
            return f"Error: Unsupported filter_by '{filter_by}'. Use: namespace, status, ready, node, name, age, ip"
        
        for line in lines[1:]:  # Skip header
            parts = line.split()
            if len(parts) > col_idx and filter_value.lower() in parts[col_idx].lower():
                count += 1
                # Get resource name (column 1 for pods/services, column 0 for nodes)
                name_idx = 1 if resource_type in ['pods', 'services', 'deployments'] else 0
                if len(parts) > name_idx:
                    resource_list.append(parts[name_idx])
        
        return f"Count: {count} {resource_type} where {filter_by}='{filter_value}'\nMatching: {', '.join(resource_list) if resource_list else 'none'}"
    except Exception as e:
        return f"Error: {str(e)}"
