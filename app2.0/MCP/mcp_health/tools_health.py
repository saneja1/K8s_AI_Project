"""
Health Agent Tools - Kubernetes cluster health monitoring tools
"""

import subprocess
import time
from langchain_core.tools import tool

# Cache for kubectl commands (60 seconds TTL)
_command_cache = {}
_cache_ttl = 60

def _cached_kubectl_command(cache_key: str, execute_fn) -> str:
    """Helper to cache kubectl command results"""
    current_time = time.time()
    
    if cache_key in _command_cache:
        result, timestamp = _command_cache[cache_key]
        if current_time - timestamp < _cache_ttl:
            return result
    
    result = execute_fn()
    _command_cache[cache_key] = (result, current_time)
    return result


# ============================================================================
# HEALTH AGENT TOOLS
# ============================================================================

@tool
def get_cluster_nodes() -> str:
    """
    Get list of all nodes in the cluster with detailed information.
    Returns:
        String with node information including status, roles, age, and version
    """
    cache_key = "nodes"
    
    def _execute():
        try:
            full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get nodes -o wide"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
                "--zone=us-west1-a",
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
def describe_node(node_name: str = "all") -> str:
    """
    Get detailed node conditions including Ready, MemoryPressure, DiskPressure, PIDPressure status.
    Also includes lastTransitionTime for Ready condition (indicates when node was last restarted/became ready).
    Args:
        node_name: Name of the node to describe (default: "all" for all nodes)
    Returns:
        String with node conditions showing health status and last transition times
    """
    cache_key = f"describe_node_{node_name}"
    
    def _execute():
        try:
            if node_name == "all":
                # Get conditions for all nodes with lastTransitionTime - simpler format
                full_command = """sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get nodes -o json | jq -r '.items[] | "\\(.metadata.name):", (.status.conditions[] | "  \\(.type) = \\(.status) | LastTransition: \\(.lastTransitionTime) | Reason: \\(.reason) | Message: \\(.message)"), ""'"""
            else:
                # Get conditions for specific node with lastTransitionTime - simpler format
                full_command = f"""sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get node {node_name} -o json | jq -r '"\\(.metadata.name):", (.status.conditions[] | "  \\(.type) = \\(.status) | LastTransition: \\(.lastTransitionTime) | Reason: \\(.reason) | Message: \\(.message)"), ""'"""
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
                "--zone=us-west1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=8)
            
            if result.returncode == 0:
                return result.stdout if result.stdout.strip() else "No node conditions found"
            else:
                return f"Error: {result.stderr}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    return _cached_kubectl_command(cache_key, _execute)


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
        try:
            if namespace == "all":
                full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get events --all-namespaces --sort-by='.lastTimestamp'"
            else:
                full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get events -n {namespace} --sort-by='.lastTimestamp'"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
                "--zone=us-west1-a",
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
