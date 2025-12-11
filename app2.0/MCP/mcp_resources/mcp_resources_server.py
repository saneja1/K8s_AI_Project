"""
MCP Server for Resources Agent Tools
Exposes Kubernetes resource capacity and usage monitoring tools via MCP protocol
"""

import os
import subprocess
import time
from mcp.server.fastmcp import FastMCP

# Import tool implementations from tools_resources
from tools_resources import get_pod_memory_comparison as _get_pod_memory_comparison_impl

# Get port from environment or default to 8002
port = int(os.getenv('PORT', '8002'))

# Initialize MCP server with explicit port
mcp = FastMCP("K8s-Resources", port=port)

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


@mcp.tool()
def get_node_resources() -> str:
    """
    Get node capacity and allocatable resources (CPU, memory, storage).
    Shows total vs allocatable resources for each node.
    
    Returns:
        String with node resource capacity information
    """
    cache_key = "node_resources"
    
    def _execute():
        try:
            full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl describe nodes"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "pggo890@k8s-master-01",
                "--zone=us-west1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
            
            if result.returncode == 0:
                return result.stdout
            else:
                return f"Error: {result.stderr}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    return _cached_kubectl_command(cache_key, _execute)


@mcp.tool()
def get_pod_resources(namespace: str = "all") -> str:
    """
    Get pod resource requests and limits (CPU and memory).
    Shows which pods have resource constraints configured.
    
    Args:
        namespace: Namespace to check (default: "all" for all namespaces)
    
    Returns:
        String with pod resource requests and limits
    """
    cache_key = f"pod_resources_{namespace}"
    
    def _execute():
        try:
            if namespace == "all":
                full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -A -o json"
            else:
                full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -n {namespace} -o json"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "pggo890@k8s-master-01",
                "--zone=us-west1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
            
            if result.returncode == 0:
                return result.stdout
            else:
                return f"Error: {result.stderr}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    return _cached_kubectl_command(cache_key, _execute)


@mcp.tool()
def get_namespace_resources() -> str:
    """
    Get aggregate resource requests and limits by namespace.
    Shows total CPU/memory requests and limits for each namespace.
    
    Returns:
        String with namespace resource aggregation
    """
    cache_key = "namespace_resources"
    
    def _execute():
        try:
            full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -A -o json"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "pggo890@k8s-master-01",
                "--zone=us-west1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
            
            if result.returncode == 0:
                return result.stdout
            else:
                return f"Error: {result.stderr}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    return _cached_kubectl_command(cache_key, _execute)


@mcp.tool()
def get_node_utilization() -> str:
    """
    Get current resource usage on nodes.
    First tries kubectl top nodes (real-time usage via metrics-server).
    Falls back to kubectl describe nodes (allocated requests) if metrics-server unavailable.
    
    Returns:
        String with node utilization metrics or allocated resources
    """
    cache_key = "node_utilization"
    
    def _execute():
        try:
            # First try kubectl top nodes for real-time metrics
            top_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl top nodes"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "pggo890@k8s-master-01",
                "--zone=us-west1-a",
                f"--command={top_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
            
            if result.returncode == 0 and "error" not in result.stderr.lower():
                return result.stdout
            
            # Fallback to kubectl describe nodes for allocated resources
            describe_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl describe nodes"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "pggo890@k8s-master-01",
                "--zone=us-west1-a",
                f"--command={describe_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
            
            if result.returncode == 0:
                fallback_msg = (
                    "NOTE: Metrics server is not available. Showing ALLOCATED RESOURCES (pod requests) "
                    "instead of real-time utilization. This shows what resources are promised to pods, "
                    "not actual current usage.\n\n"
                )
                return fallback_msg + result.stdout
            else:
                return f"Error: {result.stderr}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    return _cached_kubectl_command(cache_key, _execute)


@mcp.tool()
def get_pod_utilization(namespace: str = "all") -> str:
    """
    Get current resource usage by pods (requires metrics-server).
    Shows real-time CPU and memory usage for pods.
    
    Args:
        namespace: Namespace to check (default: "all" for all namespaces)
    
    Returns:
        String with pod utilization metrics
    """
    cache_key = f"pod_utilization_{namespace}"
    
    def _execute():
        try:
            if namespace == "all":
                full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl top pods -A"
            else:
                full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl top pods -n {namespace}"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "pggo890@k8s-master-01",
                "--zone=us-west1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
            
            if result.returncode == 0:
                return result.stdout
            else:
                return f"Error: {result.stderr}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    return _cached_kubectl_command(cache_key, _execute)


@mcp.tool()
def get_pod_memory_comparison(namespace: str = "all") -> str:
    """
    Compare CPU and memory allocation/requests across all pods to find highest usage.
    Parses pod resource requests/limits to identify which pod has highest CPU or memory configured.
    BEST TOOL for finding "which pod has highest CPU or memory" questions.
    
    Args:
        namespace: Namespace to check (default: "all" for all namespaces)
    
    Returns:
        String with pods sorted by CPU and memory allocation (highest first)
    """
    # Use the implementation from tools_resources.py (call .invoke() on StructuredTool)
    return _get_pod_memory_comparison_impl.invoke({"namespace": namespace})


@mcp.tool()
def get_node_limits(node_name: str = "all") -> str:
    """
    **PRIMARY TOOL FOR "LIMITS" QUERIES** - Get ONLY the Limits column values for CPU and memory.
    
    ⚠️ USE THIS TOOL whenever user asks about "limits" or "limit":
    - "what are CPU and memory limits?"
    - "show me limits on master"
    - "CPU limit for worker"
    - "memory limits"
    
    This extracts ONLY the rightmost "Limits" column from kubectl describe node output.
    Returns clean CPU Limits and Memory Limits values without other columns.
    
    Args:
        node_name: Node name to check, or "all" for all nodes (default: "all")
                   Examples: "k8s-master-01", "k8s-worker-01", "all"
    
    Returns:
        String with CPU limits and memory limits extracted from Limits column only
    """
    cache_key = f"node_limits_{node_name}"
    
    def _execute():
        try:
            full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl describe nodes"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "pggo890@k8s-master-01",
                "--zone=us-west1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)
            
            if result.returncode != 0:
                return f"Error: {result.stderr}"
            
            # Parse the output to extract only Limits column
            output = result.stdout
            lines = output.split('\n')
            
            result_text = ""
            current_node = None
            in_allocated_section = False
            
            for i, line in enumerate(lines):
                # Track current node name
                if line.startswith("Name:"):
                    current_node = line.split("Name:")[1].strip()
                    if node_name != "all" and current_node != node_name:
                        current_node = None
                        continue
                
                # Find Allocated resources section
                if current_node and "Allocated resources:" in line:
                    in_allocated_section = True
                    result_text += f"\nNode: {current_node}\n"
                    continue
                
                # Parse the Limits column (rightmost column)
                if in_allocated_section and current_node:
                    # Look for cpu line
                    if line.strip().startswith("cpu"):
                        parts = line.split()
                        if len(parts) >= 4:
                            cpu_limits = parts[3]  # Rightmost column
                            result_text += f"  CPU Limits: {cpu_limits}\n"
                    
                    # Look for memory line
                    elif line.strip().startswith("memory"):
                        parts = line.split()
                        if len(parts) >= 4:
                            memory_limits = parts[3]  # Rightmost column
                            result_text += f"  Memory Limits: {memory_limits}\n"
                        in_allocated_section = False  # Done with this node
            
            if not result_text:
                return "No limits data found for specified node(s)"
            
            return result_text.strip()
            
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    return _cached_kubectl_command(cache_key, _execute)


if __name__ == "__main__":
    # Run server on HTTP transport
    # Port should be set via PORT environment variable when launching this script
    # Example: PORT=8002 python3 mcp_resources_server.py
    mcp.run(transport="streamable-http")
