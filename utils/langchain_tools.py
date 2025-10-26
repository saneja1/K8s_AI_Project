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
    
    # Lazy import to avoid circular dependency with dashboard
    # Only import log_command when it's actually needed (not during module import)
    def get_log_command():
        try:
            from app.dashboard import log_command as _log_cmd
            return _log_cmd
        except (ImportError, AttributeError):
            # Fallback: silent logging or print
            return lambda cmd, status, details: None  # Silent fallback
    
    log_command = get_log_command()
    
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


# ============================================================================
# GENERIC KUBECTL TOOL - Covers any kubectl command not in specialized tools
# ============================================================================

@tool
def execute_kubectl(command: str, namespace: Optional[str] = None) -> str:
    """
    Execute any kubectl command dynamically. This is the catch-all tool for kubectl 
    operations not covered by specialized tools.
    
    Args:
        command: The kubectl command WITHOUT 'kubectl' prefix
                 Examples: "get pods", "describe deployment nginx", 
                          "top nodes", "get crd", "api-resources"
        namespace: Optional namespace to add -n flag
    
    Returns:
        JSON string with command output or error details.
    
    Examples:
        - execute_kubectl("get crd") - List custom resource definitions
        - execute_kubectl("api-resources") - List all resource types
        - execute_kubectl("top pods", "default") - Resource usage
        - execute_kubectl("get events --sort-by='.lastTimestamp'")
        - execute_kubectl("explain pods") - Show pod documentation
        - execute_kubectl("rollout history deployment/nginx", "default")
    """
    if namespace:
        full_command = f"{command} -n {namespace}"
    else:
        full_command = command
    
    result = execute_kubectl_command(full_command)
    return json.dumps(result)


# ============================================================================
# MONITOR AGENT TOOLS - Logs, events, and troubleshooting
# ============================================================================

@tool
def get_cluster_events(namespace: Optional[str] = None, event_type: Optional[str] = None) -> str:
    """
    Get recent cluster events sorted by timestamp. Useful for troubleshooting.
    
    Args:
        namespace: Optional namespace to filter events. If None, shows all namespaces.
        event_type: Optional event type filter (Warning, Normal, Error)
    
    Returns:
        JSON string with events sorted by time.
    
    Examples:
        - get_cluster_events() - All events across cluster
        - get_cluster_events("default", "Warning") - Warnings in default namespace
        - get_cluster_events(event_type="Error") - All error events
    """
    cmd = "get events --sort-by='.lastTimestamp'"
    
    if namespace:
        cmd += f" -n {namespace}"
    else:
        cmd += " --all-namespaces"
    
    if event_type:
        cmd += f" --field-selector type={event_type}"
    
    result = execute_kubectl_command(cmd)
    return json.dumps(result)


@tool
def troubleshoot_pod(name: str, namespace: Optional[str] = "default") -> str:
    """
    Complete pod troubleshooting workflow. Gathers status, logs, events, and describe
    information in one comprehensive analysis.
    
    Args:
        name: Pod name (supports partial matching)
        namespace: Namespace where pod is running. Default is "default".
    
    Returns:
        JSON string with comprehensive troubleshooting data including:
        - Pod status and conditions
        - Recent logs (last 100 lines)
        - Events related to pod
        - Describe output with key sections
        - Analysis and recommendations
    
    Examples:
        - troubleshoot_pod("nginx") - Full analysis of nginx pod
        - troubleshoot_pod("api-server", "production") - Troubleshoot in prod namespace
    """
    import json as json_lib
    
    troubleshooting_data = {
        'success': False,
        'pod_name': name,
        'namespace': namespace,
        'status': None,
        'logs': None,
        'events': None,
        'describe': None,
        'error': None
    }
    
    # Step 1: Find pod (handle partial names)
    pods_result = execute_kubectl_command(f"get pods -n {namespace} -o json")
    if not pods_result.get('success'):
        troubleshooting_data['error'] = f"Failed to list pods: {pods_result.get('error')}"
        return json.dumps(troubleshooting_data)
    
    try:
        pods_data = json_lib.loads(pods_result['output'])
        matching_pods = [
            pod['metadata']['name'] 
            for pod in pods_data.get('items', [])
            if name.lower() in pod['metadata']['name'].lower()
        ]
        
        if not matching_pods:
            troubleshooting_data['error'] = f"No pods found matching '{name}' in namespace '{namespace}'"
            return json.dumps(troubleshooting_data)
        
        full_pod_name = matching_pods[0]
        troubleshooting_data['pod_name'] = full_pod_name
        
    except Exception as e:
        troubleshooting_data['error'] = f"Error parsing pod list: {str(e)}"
        return json.dumps(troubleshooting_data)
    
    # Step 2: Get pod status
    status_result = execute_kubectl_command(f"get pod {full_pod_name} -n {namespace} -o json")
    if status_result.get('success'):
        try:
            pod_data = json_lib.loads(status_result['output'])
            troubleshooting_data['status'] = {
                'phase': pod_data.get('status', {}).get('phase'),
                'conditions': pod_data.get('status', {}).get('conditions', []),
                'containerStatuses': pod_data.get('status', {}).get('containerStatuses', [])
            }
        except:
            pass
    
    # Step 3: Get logs
    logs_result = execute_kubectl_command(f"logs {full_pod_name} -n {namespace} --tail=100")
    if logs_result.get('success'):
        troubleshooting_data['logs'] = logs_result['output']
    else:
        troubleshooting_data['logs'] = f"Failed to get logs: {logs_result.get('error')}"
    
    # Step 4: Get events
    events_result = execute_kubectl_command(
        f"get events -n {namespace} --field-selector involvedObject.name={full_pod_name} "
        f"--sort-by='.lastTimestamp'"
    )
    if events_result.get('success'):
        troubleshooting_data['events'] = events_result['output']
    
    # Step 5: Describe pod
    describe_result = execute_kubectl_command(f"describe pod {full_pod_name} -n {namespace}")
    if describe_result.get('success'):
        troubleshooting_data['describe'] = describe_result['output']
    
    troubleshooting_data['success'] = True
    return json.dumps(troubleshooting_data)


# ============================================================================
# SECURITY AGENT TOOLS - RBAC, secrets, network policies
# ============================================================================

@tool
def check_rbac_permissions(user_or_serviceaccount: str, namespace: Optional[str] = None) -> str:
    """
    Check what permissions a user or service account has in the cluster.
    
    Args:
        user_or_serviceaccount: User or service account name
                                Format: "username" or "system:serviceaccount:namespace:sa-name"
        namespace: Optional namespace to check permissions in
    
    Returns:
        JSON string with list of permissions (resources and verbs).
    
    Examples:
        - check_rbac_permissions("system:serviceaccount:default:my-sa")
        - check_rbac_permissions("john@example.com", "production")
    """
    cmd = f"auth can-i --list --as={user_or_serviceaccount}"
    if namespace:
        cmd += f" -n {namespace}"
    
    result = execute_kubectl_command(cmd)
    return json.dumps(result)


@tool
def list_secrets_and_configmaps(namespace: str) -> str:
    """
    List secrets and configmaps in a namespace WITHOUT showing sensitive values.
    
    Args:
        namespace: Namespace to list secrets/configmaps from
    
    Returns:
        JSON string with list of secrets and configmaps (values masked for security).
    
    Examples:
        - list_secrets_and_configmaps("default")
        - list_secrets_and_configmaps("kube-system")
    """
    result = execute_kubectl_command(f"get secrets,configmaps -n {namespace}")
    return json.dumps(result)


@tool
def check_network_policies(namespace: Optional[str] = None) -> str:
    """
    Check network policies (pod-to-pod firewall rules) in cluster.
    
    Args:
        namespace: Optional namespace to filter policies. If None, shows all namespaces.
    
    Returns:
        JSON string with network policies and their rules.
    
    Examples:
        - check_network_policies() - All policies cluster-wide
        - check_network_policies("production") - Policies in production namespace
    """
    if namespace:
        cmd = f"get networkpolicies -n {namespace} -o wide"
    else:
        cmd = "get networkpolicies --all-namespaces -o wide"
    
    result = execute_kubectl_command(cmd)
    return json.dumps(result)


# ============================================================================
# RESOURCES AGENT TOOLS - CPU/memory monitoring and analysis
# ============================================================================

@tool
def get_resource_usage(resource_type: str, namespace: Optional[str] = None) -> str:
    """
    Get current CPU and memory usage of nodes or pods.
    
    Args:
        resource_type: "nodes" or "pods"
        namespace: Optional namespace for pods. Ignored for nodes.
    
    Returns:
        JSON string with resource usage statistics.
    
    Examples:
        - get_resource_usage("nodes") - CPU/memory usage of all nodes
        - get_resource_usage("pods", "default") - Pod resource usage in default namespace
    """
    if resource_type == "nodes":
        cmd = "top nodes"
    elif resource_type == "pods":
        if namespace:
            cmd = f"top pods -n {namespace}"
        else:
            cmd = "top pods --all-namespaces"
    else:
        return json.dumps({'success': False, 'error': f"Invalid resource_type: {resource_type}. Use 'nodes' or 'pods'."})
    
    result = execute_kubectl_command(cmd)
    return json.dumps(result)


@tool
def get_resource_quotas(namespace: str) -> str:
    """
    Check resource quotas (limits) set on a namespace.
    
    Args:
        namespace: Namespace to check quotas for
    
    Returns:
        JSON string with quota information (used vs hard limits).
    
    Examples:
        - get_resource_quotas("production") - Check production namespace quotas
        - get_resource_quotas("default") - Check default namespace quotas
    """
    result = execute_kubectl_command(f"get resourcequota -n {namespace} -o wide")
    return json.dumps(result)


@tool
def analyze_resource_requests(namespace: str) -> str:
    """
    Analyze resource requests vs actual usage to identify over/under-provisioning.
    
    Args:
        namespace: Namespace to analyze
    
    Returns:
        JSON string with analysis of requested vs actual resource usage.
    
    Examples:
        - analyze_resource_requests("default")
        - analyze_resource_requests("production")
    """
    # Get pod specs (requests/limits)
    pods_result = execute_kubectl_command(f"get pods -n {namespace} -o json")
    
    # Get actual usage
    usage_result = execute_kubectl_command(f"top pods -n {namespace}")
    
    analysis = {
        'success': True,
        'namespace': namespace,
        'pod_specs': pods_result.get('output') if pods_result.get('success') else None,
        'actual_usage': usage_result.get('output') if usage_result.get('success') else None,
        'error': None
    }
    
    if not pods_result.get('success') or not usage_result.get('success'):
        analysis['success'] = False
        analysis['error'] = f"Failed to gather data. Pods: {pods_result.get('error')}. Usage: {usage_result.get('error')}"
    
    return json.dumps(analysis)


# ============================================================================
# OPERATIONS AGENT TOOLS - Delete, scale, restart, create (WITH CONFIRMATIONS)
# ============================================================================

@tool
def delete_pod(name: str, namespace: Optional[str] = "default", force: bool = False) -> str:
    """
    Delete a pod with safety confirmation. This tool requires user confirmation before deletion.
    
    Args:
        name: Pod name to delete
        namespace: Namespace where pod is located. Default is "default".
        force: Force deletion (use with caution). Default is False.
    
    Returns:
        JSON string with confirmation request or deletion result.
    
    Note: This tool will return a confirmation message first. Agent must wait for 
          user to reply 'yes delete' before actually deleting.
    
    Examples:
        - delete_pod("nginx-abc123", "default")
        - delete_pod("failed-job", "production", force=True)
    """
    # Step 1: Check if pod exists
    check_result = execute_kubectl_command(f"get pod {name} -n {namespace}")
    if not check_result.get('success'):
        return json.dumps({
            'success': False,
            'error': f"Pod '{name}' not found in namespace '{namespace}'"
        })
    
    # Step 2: Return confirmation request
    confirmation_msg = {
        'requires_confirmation': True,
        'action': 'delete_pod',
        'details': {
            'pod_name': name,
            'namespace': namespace,
            'force': force
        },
        'message': f"⚠️ Are you sure you want to delete pod '{name}' in namespace '{namespace}'? "
                   f"This action cannot be undone. Reply 'yes delete' to confirm or 'cancel' to abort."
    }
    
    return json.dumps(confirmation_msg)


@tool
def scale_deployment(name: str, replicas: int, namespace: Optional[str] = "default") -> str:
    """
    Scale a deployment to specified number of replicas with confirmation.
    
    Args:
        name: Deployment name
        replicas: Target number of replicas (1-100)
        namespace: Namespace where deployment is located. Default is "default".
    
    Returns:
        JSON string with confirmation request or scaling result.
    
    Examples:
        - scale_deployment("nginx", 5, "default")
        - scale_deployment("api-server", 10, "production")
    """
    # Validate replica count
    if replicas < 1 or replicas > 100:
        return json.dumps({
            'success': False,
            'error': f"Invalid replica count: {replicas}. Must be between 1 and 100."
        })
    
    # Check if deployment exists
    check_result = execute_kubectl_command(f"get deployment {name} -n {namespace}")
    if not check_result.get('success'):
        return json.dumps({
            'success': False,
            'error': f"Deployment '{name}' not found in namespace '{namespace}'"
        })
    
    # Return confirmation request
    confirmation_msg = {
        'requires_confirmation': True,
        'action': 'scale_deployment',
        'details': {
            'deployment_name': name,
            'target_replicas': replicas,
            'namespace': namespace
        },
        'message': f"⚠️ Scale deployment '{name}' to {replicas} replicas in namespace '{namespace}'? "
                   f"Reply 'yes scale' to confirm or 'cancel' to abort."
    }
    
    return json.dumps(confirmation_msg)


@tool
def restart_deployment(name: str, namespace: Optional[str] = "default") -> str:
    """
    Restart a deployment (rollout restart) with confirmation.
    
    Args:
        name: Deployment name
        namespace: Namespace where deployment is located. Default is "default".
    
    Returns:
        JSON string with confirmation request or restart result.
    
    Examples:
        - restart_deployment("nginx", "default")
        - restart_deployment("api-server", "production")
    """
    # Check if deployment exists
    check_result = execute_kubectl_command(f"get deployment {name} -n {namespace}")
    if not check_result.get('success'):
        return json.dumps({
            'success': False,
            'error': f"Deployment '{name}' not found in namespace '{namespace}'"
        })
    
    # Return confirmation request
    confirmation_msg = {
        'requires_confirmation': True,
        'action': 'restart_deployment',
        'details': {
            'deployment_name': name,
            'namespace': namespace
        },
        'message': f"⚠️ Restart deployment '{name}' in namespace '{namespace}'? "
                   f"This will perform a rolling restart of all pods. "
                   f"Reply 'yes restart' to confirm or 'cancel' to abort."
    }
    
    return json.dumps(confirmation_msg)


@tool
def delete_failed_pods(namespace: str, max_count: int = 50) -> str:
    """
    Delete all failed/completed pods in a namespace with confirmation.
    
    Args:
        namespace: Namespace to clean up failed pods from
        max_count: Maximum number of pods to delete at once (safety limit). Default is 50.
    
    Returns:
        JSON string with list of failed pods and confirmation request.
    
    Examples:
        - delete_failed_pods("default")
        - delete_failed_pods("production", max_count=20)
    """
    # Get all pods in namespace
    result = execute_kubectl_command(f"get pods -n {namespace} -o json")
    if not result.get('success'):
        return json.dumps({
            'success': False,
            'error': f"Failed to list pods: {result.get('error')}"
        })
    
    try:
        import json as json_lib
        pods_data = json_lib.loads(result['output'])
        
        # Find failed/completed pods
        failed_statuses = ['Failed', 'Error', 'Completed', 'CrashLoopBackOff', 'ImagePullBackOff']
        failed_pods = []
        
        for pod in pods_data.get('items', []):
            pod_name = pod['metadata']['name']
            phase = pod.get('status', {}).get('phase', '')
            container_statuses = pod.get('status', {}).get('containerStatuses', [])
            
            # Check pod phase
            if phase in failed_statuses:
                failed_pods.append({'name': pod_name, 'reason': phase})
                continue
            
            # Check container statuses
            for container in container_statuses:
                state = container.get('state', {})
                waiting = state.get('waiting', {})
                reason = waiting.get('reason', '')
                
                if reason in failed_statuses:
                    failed_pods.append({'name': pod_name, 'reason': reason})
                    break
        
        if not failed_pods:
            return json.dumps({
                'success': True,
                'message': f"No failed pods found in namespace '{namespace}'"
            })
        
        if len(failed_pods) > max_count:
            return json.dumps({
                'success': False,
                'error': f"Found {len(failed_pods)} failed pods, which exceeds the safety limit of {max_count}. "
                         f"Please clean up manually or increase max_count parameter."
            })
        
        # Return confirmation request
        confirmation_msg = {
            'requires_confirmation': True,
            'action': 'delete_failed_pods',
            'details': {
                'namespace': namespace,
                'failed_pods': failed_pods,
                'count': len(failed_pods)
            },
            'message': f"⚠️ Found {len(failed_pods)} failed pods in namespace '{namespace}':\n" +
                       '\n'.join([f"  • {p['name']} ({p['reason']})" for p in failed_pods[:10]]) +
                       (f"\n  ... and {len(failed_pods) - 10} more" if len(failed_pods) > 10 else "") +
                       f"\n\nDelete these {len(failed_pods)} pods? Reply 'yes delete' to confirm or 'cancel' to abort."
        }
        
        return json.dumps(confirmation_msg)
        
    except Exception as e:
        return json.dumps({
            'success': False,
            'error': f"Error parsing pod data: {str(e)}"
        })


@tool
def cordon_drain_node(name: str, action: str) -> str:
    """
    Cordon, drain, or uncordon a node for maintenance with confirmation.
    
    Args:
        name: Node name
        action: Action to perform - "cordon", "drain", or "uncordon"
    
    Returns:
        JSON string with confirmation request or action result.
    
    Examples:
        - cordon_drain_node("k8s-worker-01", "cordon") - Mark unschedulable
        - cordon_drain_node("k8s-worker-01", "drain") - Evict all pods
        - cordon_drain_node("k8s-worker-01", "uncordon") - Allow scheduling again
    """
    if action not in ['cordon', 'drain', 'uncordon']:
        return json.dumps({
            'success': False,
            'error': f"Invalid action: {action}. Must be 'cordon', 'drain', or 'uncordon'."
        })
    
    # Check if node exists
    check_result = execute_kubectl_command(f"get node {name}")
    if not check_result.get('success'):
        return json.dumps({
            'success': False,
            'error': f"Node '{name}' not found"
        })
    
    # For drain action, show pods on node first
    if action == 'drain':
        pods_result = execute_kubectl_command(f"get pods --all-namespaces --field-selector spec.nodeName={name}")
        
        confirmation_msg = {
            'requires_confirmation': True,
            'action': 'cordon_drain_node',
            'details': {
                'node_name': name,
                'action': action,
                'pods_on_node': pods_result.get('output') if pods_result.get('success') else 'Unable to list pods'
            },
            'message': f"⚠️ Drain node '{name}'? This will evict all pods from this node.\n\n"
                       f"Pods on node:\n{pods_result.get('output', 'Unable to list')}\n\n"
                       f"Reply 'yes drain' to confirm or 'cancel' to abort."
        }
    else:
        confirmation_msg = {
            'requires_confirmation': True,
            'action': 'cordon_drain_node',
            'details': {
                'node_name': name,
                'action': action
            },
            'message': f"⚠️ {action.capitalize()} node '{name}'? "
                       f"Reply 'yes {action}' to confirm or 'cancel' to abort."
        }
    
    return json.dumps(confirmation_msg)


@tool
def create_configmap(name: str, data_dict: dict, namespace: Optional[str] = "default") -> str:
    """
    Create a ConfigMap from provided data with confirmation.
    
    Args:
        name: ConfigMap name
        data_dict: Dictionary of key-value pairs for configmap data
        namespace: Namespace to create configmap in. Default is "default".
    
    Returns:
        JSON string with confirmation request or creation result.
    
    Examples:
        - create_configmap("nginx-config", {"nginx.conf": "server { listen 80; }"}, "default")
        - create_configmap("app-config", {"api_url": "https://api.example.com"}, "production")
    """
    # Validate data
    if not data_dict or not isinstance(data_dict, dict):
        return json.dumps({
            'success': False,
            'error': "data_dict must be a non-empty dictionary"
        })
    
    # Check if configmap already exists
    check_result = execute_kubectl_command(f"get configmap {name} -n {namespace}")
    if check_result.get('success'):
        return json.dumps({
            'success': False,
            'error': f"ConfigMap '{name}' already exists in namespace '{namespace}'. Use 'kubectl delete configmap {name}' first."
        })
    
    # Return confirmation request
    confirmation_msg = {
        'requires_confirmation': True,
        'action': 'create_configmap',
        'details': {
            'name': name,
            'namespace': namespace,
            'data': data_dict
        },
        'message': f"⚠️ Create ConfigMap '{name}' in namespace '{namespace}' with {len(data_dict)} key(s)? "
                   f"Reply 'yes create' to confirm or 'cancel' to abort."
    }
    
    return json.dumps(confirmation_msg)


@tool
def create_secret(name: str, data_dict: dict, secret_type: str = "Opaque", namespace: Optional[str] = "default") -> str:
    """
    Create a Secret from provided data with confirmation.
    
    Args:
        name: Secret name
        data_dict: Dictionary of key-value pairs for secret data (will be base64 encoded)
        secret_type: Type of secret (Opaque, kubernetes.io/tls, etc.). Default is "Opaque".
        namespace: Namespace to create secret in. Default is "default".
    
    Returns:
        JSON string with confirmation request or creation result.
    
    Examples:
        - create_secret("db-password", {"password": "mypassword"}, "Opaque", "default")
        - create_secret("tls-cert", {"tls.crt": "...", "tls.key": "..."}, "kubernetes.io/tls", "default")
    """
    # Validate data
    if not data_dict or not isinstance(data_dict, dict):
        return json.dumps({
            'success': False,
            'error': "data_dict must be a non-empty dictionary"
        })
    
    # Check if secret already exists
    check_result = execute_kubectl_command(f"get secret {name} -n {namespace}")
    if check_result.get('success'):
        return json.dumps({
            'success': False,
            'error': f"Secret '{name}' already exists in namespace '{namespace}'. Use 'kubectl delete secret {name}' first."
        })
    
    # Return confirmation request (don't show secret values)
    confirmation_msg = {
        'requires_confirmation': True,
        'action': 'create_secret',
        'details': {
            'name': name,
            'namespace': namespace,
            'type': secret_type,
            'keys': list(data_dict.keys())  # Only show keys, not values
        },
        'message': f"⚠️ Create Secret '{name}' (type: {secret_type}) in namespace '{namespace}' with {len(data_dict)} key(s): {', '.join(data_dict.keys())}? "
                   f"Reply 'yes create' to confirm or 'cancel' to abort."
    }
    
    return json.dumps(confirmation_msg)


@tool
def apply_manifest(yaml_content: str, namespace: Optional[str] = None) -> str:
    """
    Apply a Kubernetes manifest (YAML) with confirmation.
    
    Args:
        yaml_content: YAML content of the manifest to apply
        namespace: Optional namespace to apply manifest in (if not specified in YAML)
    
    Returns:
        JSON string with confirmation request or apply result.
    
    Examples:
        - apply_manifest("apiVersion: v1\\nkind: ConfigMap\\nmetadata:\\n  name: my-config...")
    """
    # Validate YAML
    if not yaml_content or not yaml_content.strip():
        return json.dumps({
            'success': False,
            'error': "yaml_content cannot be empty"
        })
    
    # Return confirmation request
    confirmation_msg = {
        'requires_confirmation': True,
        'action': 'apply_manifest',
        'details': {
            'namespace': namespace,
            'yaml_preview': yaml_content[:500] + ('...' if len(yaml_content) > 500 else '')
        },
        'message': f"⚠️ Apply the following manifest" + (f" in namespace '{namespace}'" if namespace else "") + "?\n\n"
                   f"```yaml\n{yaml_content[:300]}{'...' if len(yaml_content) > 300 else ''}\n```\n\n"
                   f"Reply 'yes apply' to confirm or 'cancel' to abort."
    }
    
    return json.dumps(confirmation_msg)


# Export all tools as a list for easy agent initialization
ALL_TOOLS = [
    # Core tools (existing)
    get_cluster_resources,
    describe_resource,
    get_pod_logs,
    check_node_health,
    check_cluster_health,
    
    # Generic kubectl tool
    execute_kubectl,
    
    # Monitor tools
    get_cluster_events,
    troubleshoot_pod,
    
    # Security tools
    check_rbac_permissions,
    list_secrets_and_configmaps,
    check_network_policies,
    
    # Resources tools
    get_resource_usage,
    get_resource_quotas,
    analyze_resource_requests,
    
    # Operations tools
    delete_pod,
    scale_deployment,
    restart_deployment,
    delete_failed_pods,
    cordon_drain_node,
    create_configmap,
    create_secret,
    apply_manifest
]
