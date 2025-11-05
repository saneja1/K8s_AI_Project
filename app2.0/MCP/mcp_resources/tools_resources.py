"""
Resource Tools for Kubernetes
Tools for CPU/memory capacity, usage, and resource allocation monitoring
"""

import subprocess
from langchain_core.tools import tool


@tool
def get_node_resources() -> str:
    """
    Get node capacity and allocatable resources (CPU, memory, storage).
    Shows total vs allocatable resources for each node.
    
    Returns:
        String with node resource capacity information
    """
    try:
        full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl describe nodes"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
            "--zone=us-central1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


@tool
def get_pod_resources(namespace: str = "all") -> str:
    """
    Get pod resource requests and limits (CPU and memory).
    Shows which pods have resource constraints configured.
    
    Args:
        namespace: Namespace to check (default: "all" for all namespaces)
    
    Returns:
        String with pod resource requests and limits
    """
    try:
        if namespace == "all":
            full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -A -o json"
        else:
            full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -n {namespace} -o json"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
            "--zone=us-central1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


@tool
def get_namespace_resources() -> str:
    """
    Get aggregate resource requests and limits by namespace.
    Shows total CPU/memory requests and limits for each namespace.
    
    Returns:
        String with namespace resource aggregation
    """
    try:
        full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -A -o json"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
            "--zone=us-central1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


@tool
def get_node_utilization() -> str:
    """
    Get current resource usage on nodes.
    First tries kubectl top nodes (real-time usage via metrics-server).
    Falls back to kubectl describe nodes (allocated requests) if metrics-server unavailable.
    
    Returns:
        String with node utilization metrics or allocated resources
    """
    try:
        # First try kubectl top nodes for real-time metrics
        top_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl top nodes"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
            "--zone=us-central1-a",
            f"--command={top_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and "error" not in result.stderr.lower():
            return result.stdout
        
        # Fallback to kubectl describe nodes for allocated resources
        describe_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl describe nodes"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
            "--zone=us-central1-a",
            f"--command={describe_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            fallback_msg = (
                "⚠️ METRICS-SERVER NOT AVAILABLE ⚠️\n"
                "Showing ALLOCATED RESOURCES (pod requests) instead of real-time utilization.\n"
                "This represents resources RESERVED for pods, not actual current usage.\n\n"
            )
            return fallback_msg + result.stdout
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


@tool
def get_pod_utilization(namespace: str = "all") -> str:
    """
    Get current resource usage by pods (requires metrics-server).
    Shows real-time CPU and memory usage for pods.
    Falls back to pod resource requests if metrics-server unavailable.
    
    Args:
        namespace: Namespace to check (default: "all" for all namespaces)
    
    Returns:
        String with pod utilization metrics or allocated resources
    """
    try:
        # First try kubectl top pods for real-time metrics
        if namespace == "all":
            top_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl top pods -A"
        else:
            top_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl top pods -n {namespace}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
            "--zone=us-central1-a",
            f"--command={top_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and "error" not in result.stderr.lower():
            return result.stdout
        
        # Fallback to kubectl describe nodes for allocated resources
        describe_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl describe nodes"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
            "--zone=us-central1-a",
            f"--command={describe_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            fallback_msg = (
                "⚠️ METRICS-SERVER NOT AVAILABLE ⚠️\n"
                "Showing ALLOCATED RESOURCES (pod requests/limits) instead of real-time usage.\n"
                "This represents resources RESERVED for pods, not actual current consumption.\n\n"
            )
            return fallback_msg + result.stdout
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"
