"""
MCP Server for Health Agent Tools
Exposes Kubernetes health monitoring tools via MCP protocol
"""

import subprocess
import time
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("K8s-Health")

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
def get_cluster_nodes() -> str:
    """Get list of all nodes in the cluster with detailed information."""
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


@mcp.tool()
def describe_node(node_name: str = "all") -> str:
    """Get detailed node conditions including Ready, MemoryPressure, DiskPressure, PIDPressure status.
    Also shows lastTransitionTime for each condition (indicates when node was last restarted/became ready).
    Includes node taints information."""
    cache_key = f"describe_node_{node_name}"
    
    def _execute():
        try:
            if node_name == "all":
                # Get all nodes with lastTransitionTime and taints using jq
                full_command = """sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get nodes -o json | jq -r '.items[] | "\\(.metadata.name):", "Taints: " + (if (.spec.taints | length) > 0 then (.spec.taints | map("\\(.key)=\\(.value):\\(.effect)") | join(", ")) else "<none>" end), (.status.conditions[] | "  \\(.type) = \\(.status) | LastTransition: \\(.lastTransitionTime) | Reason: \\(.reason) | Message: \\(.message)"), ""'"""
            else:
                # Get specific node with lastTransitionTime and taints using jq
                full_command = f"""sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get node {node_name} -o json | jq -r '"\\(.metadata.name):", "Taints: " + (if (.spec.taints | length) > 0 then (.spec.taints | map("\\(.key)=\\(.value):\\(.effect)") | join(", ")) else "<none>" end), (.status.conditions[] | "  \\(.type) = \\(.status) | LastTransition: \\(.lastTransitionTime) | Reason: \\(.reason) | Message: \\(.message)"), ""'"""
            
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


@mcp.tool()
def get_cluster_events(namespace: str = "all", minutes: int = 10) -> str:
    """Get recent cluster events from the last N minutes (default: 10 minutes).
    This shows only REAL-TIME events, not old/stale events."""
    cache_key = f"events_{namespace}_{minutes}"
    
    def _execute():
        try:
            # Use field-selector to get events from last N minutes
            # Calculate time window: now - N minutes
            time_window = f"{minutes}m"
            
            if namespace == "all":
                full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get events --all-namespaces --sort-by='.lastTimestamp' --field-selector type!=Normal"
            else:
                full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get events -n {namespace} --sort-by='.lastTimestamp' --field-selector type!=Normal"
            
            # Add filter to only show recent events (last N minutes)
            # Use jq to filter by lastTimestamp
            full_command += f" -o json | jq -r '.items | map(select(.lastTimestamp != null and (now - ((.lastTimestamp | fromdateiso8601))) < {minutes * 60})) | if length == 0 then \"No recent events found in the last {minutes} minutes. Cluster is operating normally.\" else (map(\"\\(.lastTimestamp) | \\(.metadata.namespace) | \\(.type) | \\(.reason) | \\(.message)\") | join(\"\\n\")) end'"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
                "--zone=us-west1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=8)
            
            if result.returncode == 0:
                output = result.stdout.strip()
                if not output or output == "null":
                    return f"No recent events found in the last {minutes} minutes. Cluster is operating normally."
                return output
            else:
                return f"Error: {result.stderr}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    return _cached_kubectl_command(cache_key, _execute)


if __name__ == "__main__":
    # Run server on HTTP transport
    mcp.run(transport="streamable-http")
