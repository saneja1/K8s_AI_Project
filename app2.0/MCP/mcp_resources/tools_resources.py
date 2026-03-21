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
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
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
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
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
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
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
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={top_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and "error" not in result.stderr.lower():
            return result.stdout
        
        # Fallback to kubectl describe nodes for allocated resources
        describe_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl describe nodes"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
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
    Falls back to pod resource requests/limits if metrics-server unavailable.
    
    Args:
        namespace: Namespace to check (default: "all" for all namespaces)
    
    Returns:
        String with pod utilization metrics or allocated resources per pod
    """
    try:
        # First try kubectl top pods for real-time metrics
        if namespace == "all":
            top_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl top pods -A"
        else:
            top_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl top pods -n {namespace}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={top_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0 and "error" not in result.stderr.lower():
            return result.stdout
        
        # Fallback: Use get_pod_resources to show individual pod allocations
        fallback_msg = (
            "⚠️ METRICS-SERVER NOT AVAILABLE ⚠️\n"
            "Showing ALLOCATED RESOURCES (memory requests/limits) per pod instead of real-time usage.\n"
            "Use get_pod_resources() tool to get detailed JSON with memory values for comparison.\n\n"
            "HINT: To find pod with highest memory, call get_pod_resources() and parse the JSON output.\n"
        )
        return fallback_msg
    except Exception as e:
        return f"Error executing command: {str(e)}"


@tool
def get_pod_memory_comparison(namespace: str = "all") -> str:
    """
    Compare CPU and memory allocation/requests across all pods to find highest usage.
    Parses pod resource requests to identify which pod has highest CPU or memory configured.
    
    Args:
        namespace: Namespace to check (default: "all" for all namespaces)
    
    Returns:
        String with pods sorted by CPU and memory allocation (highest first)
    """
    import json
    
    try:
        # Get pod resources as JSON
        if namespace == "all":
            full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -A -o json"
        else:
            full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -n {namespace} -o json"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=10)
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        # Parse JSON and extract CPU and memory requests/limits
        pods_data = json.loads(result.stdout)
        pod_resources_list = []
        
        for pod in pods_data.get('items', []):
            pod_name = pod['metadata']['name']
            pod_namespace = pod['metadata']['namespace']
            
            # Extract CPU and memory from all containers in pod
            total_cpu_request = 0
            total_cpu_limit = 0
            total_memory_request = 0
            total_memory_limit = 0
            
            for container in pod['spec'].get('containers', []):
                resources = container.get('resources', {})
                
                # CPU requests and limits
                cpu_request = resources.get('requests', {}).get('cpu', '0')
                total_cpu_request += _parse_cpu_to_millicores(cpu_request)
                
                cpu_limit = resources.get('limits', {}).get('cpu', '0')
                total_cpu_limit += _parse_cpu_to_millicores(cpu_limit)
                
                # Memory requests and limits
                mem_request = resources.get('requests', {}).get('memory', '0')
                total_memory_request += _parse_memory_to_bytes(mem_request)
                
                mem_limit = resources.get('limits', {}).get('memory', '0')
                total_memory_limit += _parse_memory_to_bytes(mem_limit)
            
            if total_cpu_request > 0 or total_cpu_limit > 0 or total_memory_request > 0 or total_memory_limit > 0:
                pod_resources_list.append({
                    'name': pod_name,
                    'namespace': pod_namespace,
                    'cpu_request_millicores': total_cpu_request,
                    'cpu_limit_millicores': total_cpu_limit,
                    'memory_request_bytes': total_memory_request,
                    'memory_limit_bytes': total_memory_limit,
                    'memory_request_mb': total_memory_request / (1024 * 1024),
                    'memory_limit_mb': total_memory_limit / (1024 * 1024)
                })
        
        if not pod_resources_list:
            return "No pods found with CPU or memory requests/limits configured."
        
        # Sort by CPU first, then memory
        pods_by_cpu = sorted(pod_resources_list, key=lambda x: max(x['cpu_request_millicores'], x['cpu_limit_millicores']), reverse=True)
        pods_by_memory = sorted(pod_resources_list, key=lambda x: max(x['memory_request_bytes'], x['memory_limit_bytes']), reverse=True)
        
        # Format output
        output = "Pods sorted by resource allocation:\n\n"
        output += "=" * 120 + "\n"
        output += "TOP PODS BY CPU:\n"
        output += f"{'Pod Name':<40} {'Namespace':<20} {'CPU Request':<15} {'CPU Limit':<15}\n"
        output += "-" * 120 + "\n"
        
        for pod in pods_by_cpu[:10]:  # Show top 10
            cpu_req_str = f"{pod['cpu_request_millicores']}m" if pod['cpu_request_millicores'] > 0 else "Not set"
            cpu_lim_str = f"{pod['cpu_limit_millicores']}m" if pod['cpu_limit_millicores'] > 0 else "Not set"
            output += f"{pod['name']:<40} {pod['namespace']:<20} {cpu_req_str:<15} {cpu_lim_str:<15}\n"
        
        output += "\n" + "=" * 120 + "\n"
        output += "TOP PODS BY MEMORY:\n"
        output += f"{'Pod Name':<40} {'Namespace':<20} {'Memory Request':<15} {'Memory Limit':<15}\n"
        output += "-" * 120 + "\n"
        
        for pod in pods_by_memory[:10]:  # Show top 10
            mem_req_str = f"{pod['memory_request_mb']:.0f}Mi" if pod['memory_request_mb'] > 0 else "Not set"
            mem_lim_str = f"{pod['memory_limit_mb']:.0f}Mi" if pod['memory_limit_mb'] > 0 else "Not set"
            output += f"{pod['name']:<40} {pod['namespace']:<20} {mem_req_str:<15} {mem_lim_str:<15}\n"
        
        # Summary
        output += "\n" + "=" * 120 + "\n"
        output += "🏆 HIGHEST RESOURCE ALLOCATIONS:\n"
        output += f"  • CPU: {pods_by_cpu[0]['name']} (Namespace: {pods_by_cpu[0]['namespace']}"
        if pods_by_cpu[0]['cpu_request_millicores'] > 0:
            output += f", Request: {pods_by_cpu[0]['cpu_request_millicores']}m"
        if pods_by_cpu[0]['cpu_limit_millicores'] > 0:
            output += f", Limit: {pods_by_cpu[0]['cpu_limit_millicores']}m"
        output += ")\n"
        
        output += f"  • Memory: {pods_by_memory[0]['name']} (Namespace: {pods_by_memory[0]['namespace']}"
        if pods_by_memory[0]['memory_request_mb'] > 0:
            output += f", Request: {pods_by_memory[0]['memory_request_mb']:.0f}Mi"
        if pods_by_memory[0]['memory_limit_mb'] > 0:
            output += f", Limit: {pods_by_memory[0]['memory_limit_mb']:.0f}Mi"
        output += ")\n"
        
        return output
        
    except json.JSONDecodeError as e:
        return f"Error parsing JSON: {str(e)}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


def _parse_memory_to_bytes(mem_str: str) -> int:
    """
    Parse Kubernetes memory string to bytes.
    Handles formats like: 128Mi, 1Gi, 512Mi, 2048Ki, etc.
    """
    if not mem_str or mem_str == '0':
        return 0
    
    mem_str = mem_str.strip()
    
    # Remove any suffix and extract number
    import re
    match = re.match(r'(\d+(?:\.\d+)?)\s*([A-Za-z]*)', mem_str)
    if not match:
        return 0
    
    value = float(match.group(1))
    unit = match.group(2).upper()
    
    # Convert to bytes
    multipliers = {
        'K': 1000,
        'KI': 1024,
        'M': 1000 * 1000,
        'MI': 1024 * 1024,
        'G': 1000 * 1000 * 1000,
        'GI': 1024 * 1024 * 1024,
        'T': 1000 * 1000 * 1000 * 1000,
        'TI': 1024 * 1024 * 1024 * 1024,
    }
    
    multiplier = multipliers.get(unit, 1)
    return int(value * multiplier)


def _parse_cpu_to_millicores(cpu_str: str) -> int:
    """
    Parse Kubernetes CPU string to millicores.
    Handles formats like: 100m, 1, 0.5, 2 (cores)
    
    Returns:
        CPU value in millicores (1 core = 1000 millicores)
    """
    if not cpu_str or cpu_str == '0':
        return 0
    
    cpu_str = cpu_str.strip()
    
    # Handle millicores format (e.g., "100m")
    if cpu_str.endswith('m'):
        return int(cpu_str[:-1])
    
    # Handle cores format (e.g., "1", "0.5", "2")
    try:
        cores = float(cpu_str)
        return int(cores * 1000)
    except ValueError:
        return 0


