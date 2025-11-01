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
