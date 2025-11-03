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


@mcp.tool()
def describe_node(node_name: str = "all") -> str:
    """Get detailed node conditions including Ready, MemoryPressure, DiskPressure, PIDPressure status."""
    cache_key = f"describe_node_{node_name}"
    
    def _execute():
        try:
            if node_name == "all":
                full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{\"\\n\"}{range .status.conditions[*]}{\"  \"}{.type}{\" = \"}{.status}{\" (Reason: \"}{.reason}{\" | Message: \"}{.message}{\")\"}  {\"\\n\"}{end}{\"\\n\"}{end}'"
            else:
                # For specific nodes, use a simpler approach with json output and parse it
                # This avoids jsonpath escaping issues with node names containing dots
                full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get node {node_name} -o json"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
                "--zone=us-central1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=8)
            
            if result.returncode == 0:
                if node_name == "all":
                    return result.stdout if result.stdout.strip() else "No node conditions found"
                else:
                    # Parse JSON output for specific node
                    import json
                    try:
                        node_data = json.loads(result.stdout)
                        node_name_full = node_data.get('metadata', {}).get('name', node_name)
                        conditions = node_data.get('status', {}).get('conditions', [])
                        
                        output = f"{node_name_full}\n"
                        for condition in conditions:
                            ctype = condition.get('type', 'Unknown')
                            status = condition.get('status', 'Unknown')
                            reason = condition.get('reason', 'Unknown')
                            message = condition.get('message', 'No message')
                            output += f"  {ctype} = {status} (Reason: {reason} | Message: {message})\n"
                        
                        return output.strip()
                    except json.JSONDecodeError:
                        return result.stdout if result.stdout.strip() else "No node conditions found"
            else:
                return f"Error: {result.stderr}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    return _cached_kubectl_command(cache_key, _execute)


@mcp.tool()
def get_cluster_events(namespace: str = "all") -> str:
    """Get cluster events to see what's happening in the cluster."""
    cache_key = f"events_{namespace}"
    
    def _execute():
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


if __name__ == "__main__":
    # Run server on HTTP transport
    mcp.run(transport="streamable-http")
