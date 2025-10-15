"""
LangChain tools for Kubernetes cluster management.
Converts the custom tool functions into LangChain-compatible tools.
"""

from langchain.tools import tool
from typing import Optional
import json


def execute_kubectl_command(command, node="k8s-master-001", zone="us-central1-a", timeout=20):
    """Execute kubectl command on master node via SSH. Returns dict with success, output, error."""
    import subprocess
    
    # Import log_command only when needed to avoid circular imports
    try:
        from app.dashboard import log_command
    except:
        # If dashboard not available (e.g., during testing), use print
        def log_command(cmd, status, details):
            print(f"[{status}] {cmd}: {details}")
    
    try:
        full_command = f"export KUBECONFIG=/etc/kubernetes/admin.conf && kubectl {command} || kubectl --kubeconfig=/etc/kubernetes/admin.conf {command} || kubectl --kubeconfig=$HOME/.kube/config {command}"
        ssh_command = [
            "gcloud", "compute", "ssh", node,
            f"--zone={zone}",
            f"--command={full_command}"
        ]
        
        result = subprocess.run(
            ssh_command,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        if result.returncode == 0:
            log_command(f"kubectl {command}", "✓ Success", f"Output: {len(result.stdout)} bytes")
            return {'success': True, 'output': result.stdout, 'error': None}
        else:
            error_msg = result.stderr[:500] if result.stderr else "Unknown error"
            log_command(f"kubectl {command}", "❌ Failed", error_msg)
            return {'success': False, 'output': None, 'error': error_msg}
            
    except subprocess.TimeoutExpired:
        log_command(f"kubectl {command}", "❌ Failed", f"Timeout after {timeout}s")
        return {'success': False, 'output': None, 'error': f'Command timed out after {timeout} seconds'}
    except Exception as e:
        log_command(f"kubectl {command}", "❌ Failed", str(e))
        return {'success': False, 'output': None, 'error': str(e)}


@tool
def get_cluster_resources(resource_type: str, namespace: Optional[str] = None) -> str:
    """
    List Kubernetes resources like pods, nodes, services, deployments.
    
    Args:
        resource_type: Type of resource (pods, nodes, services, deployments, etc.)
        namespace: Optional namespace to filter resources. If not provided, shows all namespaces.
    
    Returns:
        JSON string with resource information or error details.
    
    Examples:
        - get_cluster_resources("pods") - List all pods
        - get_cluster_resources("services", "default") - List services in default namespace
    """
    if namespace:
        result = execute_kubectl_command(f"get {resource_type} -n {namespace} -o json")
    else:
        result = execute_kubectl_command(f"get {resource_type} --all-namespaces -o json")
    
    return json.dumps(result)


@tool
def describe_resource(resource_type: str, name: str, namespace: Optional[str] = "default") -> str:
    """
    Get detailed information about a specific Kubernetes resource including taints, labels, conditions, and events.
    
    Args:
        resource_type: Type of resource (node, pod, service, deployment, etc.)
        name: Name of the specific resource
        namespace: Namespace of the resource (not needed for nodes). Default is "default".
    
    Returns:
        JSON string with detailed resource information or error details.
    
    Examples:
        - describe_resource("node", "k8s-master-001") - Get master node details including taints
        - describe_resource("pod", "nginx-pod", "default") - Get pod details
    """
    if resource_type == "node":
        result = execute_kubectl_command(f"describe {resource_type} {name}")
        
        # For successful node descriptions, extract key sections
        if result.get('success') and result.get('output'):
            output = result['output']
            
            # Extract important sections
            sections_to_extract = {
                'Taints': [],
                'Conditions': [],
                'Capacity': [],
                'Allocatable': [],
                'System Info': []
            }
            
            lines = output.split('\n')
            current_section = None
            
            for line in lines:
                if line.startswith('Taints:'):
                    current_section = 'Taints'
                    sections_to_extract['Taints'].append(line)
                elif line.startswith('Conditions:'):
                    current_section = 'Conditions'
                    sections_to_extract['Conditions'].append(line)
                elif line.startswith('Capacity:'):
                    current_section = 'Capacity'
                    sections_to_extract['Capacity'].append(line)
                elif line.startswith('Allocatable:'):
                    current_section = 'Allocatable'
                    sections_to_extract['Allocatable'].append(line)
                elif line.startswith('System Info:'):
                    current_section = 'System Info'
                    sections_to_extract['System Info'].append(line)
                elif current_section and line.strip():
                    sections_to_extract[current_section].append(line)
                    if current_section == 'Conditions' and len(sections_to_extract['Conditions']) > 20:
                        current_section = None
                    elif current_section and len(sections_to_extract[current_section]) > 15:
                        current_section = None
                elif not line.strip():
                    current_section = None
            
            # Build condensed output
            condensed_parts = []
            for section, lines in sections_to_extract.items():
                if lines:
                    condensed_parts.append('\n'.join(lines))
            
            if condensed_parts:
                result['output'] = '\n\n'.join(condensed_parts)
        
        return json.dumps(result)
    else:
        result = execute_kubectl_command(f"describe {resource_type} {name} -n {namespace}")
        return json.dumps(result)


@tool
def get_pod_logs(name: str, namespace: Optional[str] = "default", tail_lines: Optional[int] = 50) -> str:
    """
    Get logs from a specific pod. Supports partial pod names and will search for matching pods.
    
    Args:
        name: Name of the pod (can be partial, e.g., "nginx" will match "nginx-deployment-abc123")
        namespace: Namespace where the pod is running. Default is "default".
        tail_lines: Number of recent log lines to retrieve. Default is 50.
    
    Returns:
        JSON string with log content or error details.
    
    Examples:
        - get_pod_logs("nginx") - Get logs for nginx pod (searches for match)
        - get_pod_logs("coredns", "kube-system", 100) - Get 100 lines from coredns in kube-system
    """
    # First, try direct pod name
    result = execute_kubectl_command(f"logs {name} -n {namespace} --tail={tail_lines}")
    
    # If failed, try to search for matching pods
    if not result.get('success', False):
        pods_result = execute_kubectl_command(f"get pods -n {namespace} -o json")
        if pods_result.get('success'):
            try:
                import json as json_lib
                pods_data = json_lib.loads(pods_result['output'])
                matching_pods = [
                    pod['metadata']['name'] 
                    for pod in pods_data.get('items', [])
                    if name.lower() in pod['metadata']['name'].lower()
                ]
                
                if matching_pods:
                    full_pod_name = matching_pods[0]
                    result = execute_kubectl_command(f"logs {full_pod_name} -n {namespace} --tail={tail_lines}")
                    if result.get('success'):
                        result['output'] = f"[Logs from pod: {full_pod_name}]\n\n{result.get('output', '')}"
                    else:
                        result['error'] = f"Found pod {full_pod_name} but failed to get logs: {result.get('error', '')}"
                else:
                    result['error'] = f"No pods found matching '{name}' in namespace '{namespace}'. Use 'kubectl get pods -n {namespace}' to list available pods."
            except Exception as e:
                result['error'] = f"Error searching for pod '{name}': {str(e)}. Original error: {result.get('error', '')}"
    
    return json.dumps(result)


@tool
def check_node_health(name: str) -> str:
    """
    Check if a specific node is healthy by getting its conditions, taints, and status.
    
    Args:
        name: Name of the node to check (e.g., "k8s-master-001", "k8s-worker-01")
    
    Returns:
        JSON string with node health information including Ready status, taints, and conditions.
    
    Examples:
        - check_node_health("k8s-master-001") - Check master node health
        - check_node_health("k8s-worker-01") - Check worker node health
    """
    result = execute_kubectl_command(f"describe node {name}")
    return json.dumps(result)


@tool
def check_cluster_health() -> str:
    """
    Check overall cluster health including all nodes status, roles, versions, and IPs.
    
    Returns:
        JSON string with comprehensive cluster health information.
    
    Examples:
        - check_cluster_health() - Get overview of all cluster nodes
    """
    result = execute_kubectl_command("get nodes -o wide")
    return json.dumps(result)


# Export all tools as a list for easy agent initialization
ALL_TOOLS = [
    get_cluster_resources,
    describe_resource,
    get_pod_logs,
    check_node_health,
    check_cluster_health
]
