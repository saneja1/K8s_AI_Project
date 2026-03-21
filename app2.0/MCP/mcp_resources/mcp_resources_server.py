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
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
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
    Get ALL pod resource fields (cpu limits, memory limits, cpu requests, memory requests).
    Use this when user asks for ALL resource info together, not just one field.

    Args:
        namespace: Namespace to check (default: "all" for all namespaces)

    Returns:
        Pre-formatted table with all 4 resource fields per pod
    """
    cache_key = f"pod_resources_formatted_{namespace}"

    def _execute():
        import json
        try:
            if namespace == "all":
                full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -A -o json"
            else:
                full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -n {namespace} -o json"

            result = subprocess.run([
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
                "--zone=us-west1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)

            if result.returncode != 0:
                return f"Error: {result.stderr}"

            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            return f"Error parsing JSON: {str(e)}"
        except Exception as e:
            return f"Error executing command: {str(e)}"

        ns_display = namespace if namespace != "all" else "all namespaces"
        lines = [f"Pod resource limits and requests ({ns_display}):",
                 f"{'Pod':<55} {'CPU Limit':<12} {'Mem Limit':<12} {'CPU Request':<14} {'Mem Request':<12}",
                 "-" * 105]

        for pod in data.get("items", []):
            pod_name = pod["metadata"]["name"]
            pod_ns   = pod["metadata"].get("namespace", namespace)
            containers = pod.get("spec", {}).get("containers", [])

            cpu_lim = mem_lim = cpu_req = mem_req = "not set"

            for c in containers:
                res = c.get("resources", {})
                lim = res.get("limits", {})
                req = res.get("requests", {})
                if lim.get("cpu"):      cpu_lim = lim["cpu"]
                if lim.get("memory"):   mem_lim = lim["memory"]
                if req.get("cpu"):      cpu_req = req["cpu"]
                if req.get("memory"):   mem_req = req["memory"]

            display_name = f"{pod_ns}/{pod_name}" if namespace == "all" else pod_name
            lines.append(f"{display_name:<55} {cpu_lim:<12} {mem_lim:<12} {cpu_req:<14} {mem_req:<12}")

        return "\n".join(lines)

    return _cached_kubectl_command(cache_key, _execute)


@mcp.tool()
def get_namespace_resources() -> str:
    """
    Get aggregate resource requests and limits by namespace.
    Shows total CPU/memory requests and limits summed per namespace.

    Returns:
        Pre-formatted table with per-namespace CPU and memory totals
    """
    cache_key = "namespace_resources_formatted"

    def _execute():
        import json, re

        def parse_cpu_to_mc(val: str) -> float:
            if not val:
                return 0.0
            if val.endswith('m'):
                return float(val[:-1])
            try:
                return float(val) * 1000
            except ValueError:
                return 0.0

        def parse_mem_to_mib(val: str) -> float:
            if not val:
                return 0.0
            m = re.match(r'([\d.]+)\s*(Ki|Mi|Gi|K|M|G)?', val)
            if not m:
                return 0.0
            v, unit = float(m.group(1)), (m.group(2) or '')
            if unit == 'Ki': return v / 1024
            if unit == 'Mi' or unit == 'M': return v
            if unit == 'Gi' or unit == 'G': return v * 1024
            if unit == 'K': return v / 1024
            return v  # assume MiB

        try:
            full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -A -o json"
            result = subprocess.run([
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
                "--zone=us-west1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)

            if result.returncode != 0:
                return f"Error: {result.stderr}"

            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            return f"Error parsing JSON: {str(e)}"
        except Exception as e:
            return f"Error: {str(e)}"

        # Aggregate per namespace
        ns_data = {}
        for pod in data.get('items', []):
            ns = pod['metadata'].get('namespace', 'default')
            if ns not in ns_data:
                ns_data[ns] = {'cpu_req': 0.0, 'mem_req': 0.0, 'cpu_lim': 0.0, 'mem_lim': 0.0, 'pods': 0}
            ns_data[ns]['pods'] += 1
            for c in pod.get('spec', {}).get('containers', []):
                res = c.get('resources', {})
                req = res.get('requests', {})
                lim = res.get('limits', {})
                ns_data[ns]['cpu_req'] += parse_cpu_to_mc(req.get('cpu', ''))
                ns_data[ns]['mem_req'] += parse_mem_to_mib(req.get('memory', ''))
                ns_data[ns]['cpu_lim'] += parse_cpu_to_mc(lim.get('cpu', ''))
                ns_data[ns]['mem_lim'] += parse_mem_to_mib(lim.get('memory', ''))

        def fmt_cpu(mc): return f"{mc:.0f}m" if mc > 0 else "not set"
        def fmt_mem(mib): return (f"{mib/1024:.2f}Gi" if mib >= 1024 else f"{mib:.0f}Mi") if mib > 0 else "not set"

        lines = [
            "Resource allocation by namespace:",
            f"{'Namespace':<25} {'Pods':>5} {'CPU Req':>10} {'Mem Req':>10} {'CPU Lim':>10} {'Mem Lim':>10}",
            "-" * 72
        ]
        for ns in sorted(ns_data):
            d = ns_data[ns]
            lines.append(f"{ns:<25} {d['pods']:>5} {fmt_cpu(d['cpu_req']):>10} {fmt_mem(d['mem_req']):>10} {fmt_cpu(d['cpu_lim']):>10} {fmt_mem(d['mem_lim']):>10}")

        return "\n".join(lines)

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
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
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
                    if node_name != "all" and node_name.lower() not in current_node.lower():
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


@mcp.tool()
def get_pod_specific_resource(field: str, namespace: str = "default") -> str:
    """
    Get ONE specific resource field for all pods — no mixing of other fields.
    Returns pre-formatted output with ONLY the requested field.

    USE THIS TOOL when user asks specifically about pod-level limits or requests:
    - "what are the cpu limits for pods" → field="cpu_limits"
    - "what are the memory limits for pods" → field="memory_limits"
    - "what are the cpu requests for pods" → field="cpu_requests"
    - "what are the memory requests for pods" → field="memory_requests"

    Args:
        field: One of: cpu_limits, memory_limits, cpu_requests, memory_requests
        namespace: Namespace to check (default: "default", use "all" for all namespaces)

    Returns:
        Pre-formatted string with ONLY the requested field for each pod.
        Never mixes other fields.
    """
    cache_key = f"pod_specific_{field}_{namespace}"

    def _execute():
        import json

        try:
            if namespace == "all":
                full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -A -o json"
            else:
                full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -n {namespace} -o json"

            result = subprocess.run([
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
                "--zone=us-west1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=10, stdin=subprocess.DEVNULL)

            if result.returncode != 0:
                return f"Error: {result.stderr}"

            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            return f"Error parsing JSON: {str(e)}"
        except Exception as e:
            return f"Error executing command: {str(e)}"

        # Determine which sub-field to extract
        resource_type, limit_or_request = {
            "cpu_limits":       ("cpu",    "limits"),
            "memory_limits":    ("memory", "limits"),
            "cpu_requests":     ("cpu",    "requests"),
            "memory_requests":  ("memory", "requests"),
        }.get(field, (None, None))

        if resource_type is None:
            return f"Unknown field '{field}'. Use: cpu_limits, memory_limits, cpu_requests, memory_requests"

        label_map = {
            "cpu_limits":      "CPU Limits",
            "memory_limits":   "Memory Limits",
            "cpu_requests":    "CPU Requests",
            "memory_requests": "Memory Requests",
        }
        label = label_map[field]
        ns_display = namespace if namespace != "all" else "all namespaces"
        lines = [f"{label} for pods in namespace '{ns_display}':"]

        for pod in data.get("items", []):
            pod_name = pod["metadata"]["name"]
            pod_ns   = pod["metadata"].get("namespace", namespace)
            containers = pod.get("spec", {}).get("containers", [])

            # Collect values across all containers
            values = []
            for c in containers:
                res = c.get("resources", {})
                val = res.get(limit_or_request, {}).get(resource_type)
                if val:
                    cname = c.get("name", "")
                    if len(containers) > 1:
                        values.append(f"{cname}: {val}")
                    else:
                        values.append(val)

            if values:
                entry = ", ".join(values)
            else:
                entry = "not set"

            if namespace == "all":
                lines.append(f"  {pod_ns}/{pod_name}: {entry}")
            else:
                lines.append(f"  {pod_name}: {entry}")

        return "\n".join(lines)

    return _cached_kubectl_command(cache_key, _execute)


if __name__ == "__main__":
    # Run server on HTTP transport
    # Port should be set via PORT environment variable when launching this script
    # Example: PORT=8002 python3 mcp_resources_server.py
    mcp.run(transport="streamable-http")
