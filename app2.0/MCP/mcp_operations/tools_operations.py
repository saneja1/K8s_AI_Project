"""
Operations Tools for Kubernetes
Tools for deployments, pods, nodes operations (write actions)
NOTE: These are standalone functions that will be wrapped by FastMCP @mcp.tool() decorator in the server
"""

import subprocess
import json



def scale_deployment(name: str, namespace: str, replicas: int, dry_run: bool = False) -> str:
    """
    Scale a deployment to specified number of replicas.
    
    Args:
        name: Deployment name
        namespace: Namespace
        replicas: Target replica count
        dry_run: If True, test without applying (default: False)
    
    Returns:
        String with operation result
    """
    try:
        dry_run_flag = "--dry-run=client" if dry_run else ""
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl scale deployment {name} -n {namespace} --replicas={replicas} {dry_run_flag}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
        
        if result.returncode == 0:
            mode = "DRY RUN" if dry_run else "APPLIED"
            return f"[{mode}] Successfully scaled deployment '{name}' in namespace '{namespace}' to {replicas} replicas.\n\n{result.stdout}"
        else:
            return f"Error scaling deployment: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"



def restart_deployment(name: str, namespace: str, dry_run: bool = False) -> str:
    """
    Restart (rollout restart) a deployment by recreating pods.
    
    Args:
        name: Deployment name
        namespace: Namespace
        dry_run: If True, test without applying (default: False)
    
    Returns:
        String with operation result
    """
    try:
        dry_run_flag = "--dry-run=client" if dry_run else ""
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl rollout restart deployment/{name} -n {namespace} {dry_run_flag}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
        
        if result.returncode == 0:
            mode = "DRY RUN" if dry_run else "APPLIED"
            return f"[{mode}] Successfully restarted deployment '{name}' in namespace '{namespace}'.\n\n{result.stdout}"
        else:
            return f"Error restarting deployment: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"



def rollback_deployment(name: str, namespace: str, revision: int = None, dry_run: bool = False) -> str:
    """
    Rollback a deployment to previous revision or specific revision.
    
    Args:
        name: Deployment name
        namespace: Namespace
        revision: Specific revision number (optional, defaults to previous)
        dry_run: If True, test without applying (default: False)
    
    Returns:
        String with operation result
    """
    try:
        dry_run_flag = "--dry-run=client" if dry_run else ""
        revision_flag = f"--to-revision={revision}" if revision else ""
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl rollout undo deployment/{name} -n {namespace} {revision_flag} {dry_run_flag}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
        
        if result.returncode == 0:
            mode = "DRY RUN" if dry_run else "APPLIED"
            rev_msg = f"revision {revision}" if revision else "previous revision"
            return f"[{mode}] Successfully rolled back deployment '{name}' in namespace '{namespace}' to {rev_msg}.\n\n{result.stdout}"
        else:
            return f"Error rolling back deployment: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"



def get_deployment_rollout_status(name: str, namespace: str) -> str:
    """
    Get the rollout status of a deployment.
    
    Args:
        name: Deployment name
        namespace: Namespace
    
    Returns:
        String with rollout status
    """
    try:
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl rollout status deployment/{name} -n {namespace}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
        
        if result.returncode == 0:
            return f"Rollout status for deployment '{name}' in namespace '{namespace}':\n\n{result.stdout}"
        else:
            return f"Error getting rollout status: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"



def delete_pod(name: str, namespace: str, grace_period: int = 30, force: bool = False) -> str:
    """
    Delete a specific pod.
    
    Args:
        name: Pod name
        namespace: Namespace
        grace_period: Grace period in seconds (default: 30, soft delete)
        force: If True, force delete immediately (hard delete)
    
    Returns:
        String with operation result
    """
    try:
        force_flag = "--force --grace-period=0" if force else f"--grace-period={grace_period}"
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl delete pod {name} -n {namespace} {force_flag}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
        
        if result.returncode == 0:
            delete_type = "FORCE" if force else "GRACEFUL"
            return f"[{delete_type}] Successfully deleted pod '{name}' in namespace '{namespace}'.\n\n{result.stdout}"
        else:
            return f"Error deleting pod: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"



def delete_pods_by_status(status: str, namespace: str = "all", force: bool = False) -> str:
    """
    Delete all pods with specific status (Failed, Pending, Unknown, Error, CrashLoopBackOff).
    ⚠️ WARNING: This is a bulk delete operation. Use with caution!
    
    Args:
        status: Pod status to filter (Failed, Pending, Unknown, Error, CrashLoopBackOff)
        namespace: Namespace (default: "all" for all namespaces)
        force: If True, force delete (hard delete)
    
    Returns:
        String with operation result and count of deleted pods
    """
    try:
        # First, get list of pods with matching status
        if namespace == "all":
            list_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -A --field-selector=status.phase={status} -o json"
        else:
            list_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -n {namespace} --field-selector=status.phase={status} -o json"
        
        list_result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={list_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
        
        if list_result.returncode != 0:
            return f"Error listing pods: {list_result.stderr}"
        
        pods_data = json.loads(list_result.stdout)
        pods = pods_data.get('items', [])
        
        if not pods:
            return f"No pods found with status '{status}' in namespace '{namespace}'."
        
        # Safety check
        pod_count = len(pods)
        if pod_count > 10:
            return f"⚠️ SAFETY CHECK: Found {pod_count} pods with status '{status}'. This is a large number. Please confirm if you want to delete all of them. Consider deleting in smaller batches or targeting specific namespace."
        
        # Delete pods
        deleted_pods = []
        errors = []
        
        for pod in pods:
            pod_name = pod['metadata']['name']
            pod_ns = pod['metadata']['namespace']
            
            force_flag = "--force --grace-period=0" if force else "--grace-period=30"
            delete_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl delete pod {pod_name} -n {pod_ns} {force_flag}"
            
            delete_result = subprocess.run([
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
                "--zone=us-west1-a",
                f"--command={delete_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
            
            if delete_result.returncode == 0:
                deleted_pods.append(f"{pod_name} (ns: {pod_ns})")
            else:
                errors.append(f"{pod_name}: {delete_result.stderr}")
        
        delete_type = "FORCE" if force else "GRACEFUL"
        result = f"[{delete_type}] Bulk delete operation for pods with status '{status}':\n\n"
        result += f"Successfully deleted {len(deleted_pods)} pods:\n"
        for pod in deleted_pods:
            result += f"  - {pod}\n"
        
        if errors:
            result += f"\nErrors ({len(errors)}):\n"
            for error in errors:
                result += f"  - {error}\n"
        
        return result
        
    except Exception as e:
        return f"Error executing command: {str(e)}"



def delete_pods_by_label(label_selector: str, namespace: str = "all", force: bool = False) -> str:
    """
    Delete all pods matching a label selector.
    ⚠️ WARNING: This is a bulk delete operation. Use with caution!
    
    Args:
        label_selector: Label selector (e.g., "app=nginx", "env=dev,tier=frontend")
        namespace: Namespace (default: "all" for all namespaces)
        force: If True, force delete (hard delete)
    
    Returns:
        String with operation result
    """
    try:
        # First, get count of pods matching label
        if namespace == "all":
            count_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -A -l {label_selector} -o json"
        else:
            count_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -n {namespace} -l {label_selector} -o json"
        
        count_result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={count_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
        
        if count_result.returncode != 0:
            return f"Error listing pods: {count_result.stderr}"
        
        pods_data = json.loads(count_result.stdout)
        pod_count = len(pods_data.get('items', []))
        
        if pod_count == 0:
            return f"No pods found with label selector '{label_selector}' in namespace '{namespace}'."
        
        # Safety check
        if pod_count > 10:
            return f"⚠️ SAFETY CHECK: Found {pod_count} pods with label '{label_selector}'. This is a large number. Please confirm if you want to delete all of them."
        
        # Delete pods
        force_flag = "--force --grace-period=0" if force else "--grace-period=30"
        if namespace == "all":
            delete_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl delete pods -A -l {label_selector} {force_flag}"
        else:
            delete_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl delete pods -n {namespace} -l {label_selector} {force_flag}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={delete_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
        
        if result.returncode == 0:
            delete_type = "FORCE" if force else "GRACEFUL"
            return f"[{delete_type}] Successfully deleted {pod_count} pods with label '{label_selector}'.\n\n{result.stdout}"
        else:
            return f"Error deleting pods: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"



def delete_deployment(name: str, namespace: str = "default", force: bool = False) -> str:
    """
    Delete a Kubernetes deployment and all its pods.
    ⚠️ WARNING: This will delete the deployment and all its managed pods!
    
    Args:
        name: Deployment name to delete
        namespace: Namespace (default: "default")
        force: If True, force delete immediately (hard delete)
    
    Returns:
        String with operation result
    """
    try:
        # Safety check for system deployments
        if namespace in ['kube-system', 'kube-public', 'kube-node-lease']:
            return f"⚠️ SAFETY CHECK: Deleting deployments in system namespace '{namespace}' requires extra caution. Please confirm this action."
        
        force_flag = "--force --grace-period=0" if force else "--grace-period=30"
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl delete deployment {name} -n {namespace} {force_flag}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        
        if result.returncode == 0:
            delete_type = "FORCE" if force else "GRACEFUL"
            return f"[{delete_type}] Successfully deleted deployment '{name}' in namespace '{namespace}' and all its pods.\n\n{result.stdout}"
        else:
            return f"Error deleting deployment: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"



def cordon_node(node_name: str) -> str:
    """
    Mark a node as unschedulable (cordon). Prevents new pods from being scheduled on this node.
    Existing pods remain running.
    
    Args:
        node_name: Node name to cordon
    
    Returns:
        String with operation result
    """
    try:
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl cordon {node_name}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
        
        if result.returncode == 0:
            return f"Successfully cordoned node '{node_name}'. Node is now unschedulable.\n\n{result.stdout}"
        else:
            return f"Error cordoning node: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"



def uncordon_node(node_name: str) -> str:
    """
    Mark a node as schedulable (uncordon). Allows new pods to be scheduled on this node.
    
    Args:
        node_name: Node name to uncordon
    
    Returns:
        String with operation result
    """
    try:
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl uncordon {node_name}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
        
        if result.returncode == 0:
            return f"Successfully uncordoned node '{node_name}'. Node is now schedulable.\n\n{result.stdout}"
        else:
            return f"Error uncordoning node: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"



def drain_node(node_name: str, force: bool = False, ignore_daemonsets: bool = True, delete_emptydir_data: bool = False) -> str:
    """
    Drain a node by safely evicting all pods. Useful for node maintenance.
    ⚠️ WARNING: This will evict all pods from the node!
    
    Args:
        node_name: Node name to drain
        force: If True, force drain even if pods are not managed by controller
        ignore_daemonsets: If True, ignore DaemonSet pods (default: True)
        delete_emptydir_data: If True, delete pods using emptyDir volumes (default: False)
    
    Returns:
        String with operation result
    """
    try:
        flags = []
        if force:
            flags.append("--force")
        if ignore_daemonsets:
            flags.append("--ignore-daemonsets")
        if delete_emptydir_data:
            flags.append("--delete-emptydir-data")
        
        flags_str = " ".join(flags)
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl drain {node_name} {flags_str} --grace-period=30"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=60, stdin=subprocess.DEVNULL)  # Longer timeout for drain
        
        if result.returncode == 0:
            return f"Successfully drained node '{node_name}'. All pods have been evicted.\n\n{result.stdout}"
        else:
            return f"Error draining node: {result.stderr}\n\nTip: If drain fails, you may need to set force=True or delete_emptydir_data=True"
    except Exception as e:
        return f"Error executing command: {str(e)}"



def patch_resource(resource_type: str, name: str, namespace: str, patch_json: str, dry_run: bool = False) -> str:
    """
    Apply a JSON patch to any Kubernetes resource.
    
    Args:
        resource_type: Resource type (e.g., "deployment", "service", "pod")
        name: Resource name
        namespace: Namespace
        patch_json: JSON patch string (e.g., '{"spec":{"replicas":3}}')
        dry_run: If True, test without applying (default: False)
    
    Returns:
        String with operation result
    """
    try:
        dry_run_flag = "--dry-run=client" if dry_run else ""
        # Escape quotes in JSON for shell
        patch_escaped = patch_json.replace('"', '\\"')
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl patch {resource_type} {name} -n {namespace} -p \"{patch_escaped}\" --type=merge {dry_run_flag}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
        
        if result.returncode == 0:
            mode = "DRY RUN" if dry_run else "APPLIED"
            return f"[{mode}] Successfully patched {resource_type} '{name}' in namespace '{namespace}'.\n\n{result.stdout}"
        else:
            return f"Error patching resource: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"



def create_namespace(name: str, dry_run: bool = False) -> str:
    """
    Create a new Kubernetes namespace.
    
    Args:
        name: Namespace name
        dry_run: If True, test without applying (default: False)
    
    Returns:
        String with operation result
    """
    try:
        dry_run_flag = "--dry-run=client" if dry_run else ""
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl create namespace {name} {dry_run_flag}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15, stdin=subprocess.DEVNULL)
        
        if result.returncode == 0:
            mode = "DRY RUN" if dry_run else "CREATED"
            return f"[{mode}] Successfully created namespace '{name}'.\n\n{result.stdout}"
        else:
            return f"Error creating namespace: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"



def delete_namespace(name: str, force: bool = False) -> str:
    """
    Delete a Kubernetes namespace and all resources within it.
    ⚠️ WARNING: This will delete ALL resources in the namespace!
    
    Args:
        name: Namespace name to delete
        force: If True, force delete immediately (skip grace period)
    
    Returns:
        String with operation result
    """
    try:
        # Safety check for system namespaces
        protected_namespaces = ['default', 'kube-system', 'kube-public', 'kube-node-lease']
        if name in protected_namespaces:
            return f"⚠️ SAFETY CHECK: Cannot delete protected namespace '{name}'. This is a system namespace."
        
        force_flag = "--force --grace-period=0" if force else ""
        full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl delete namespace {name} {force_flag}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        
        if result.returncode == 0:
            delete_type = "FORCE" if force else "GRACEFUL"
            return f"[{delete_type}] Successfully deleted namespace '{name}' and all its resources.\n\n{result.stdout}"
        else:
            return f"Error deleting namespace: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


def apply_yaml_config(yaml_content: str, namespace: str = "default", dry_run: bool = False) -> str:
    """
    Apply YAML configuration to create or update any Kubernetes resource.
    Supports: pods, deployments, services, configmaps, secrets, ingress, jobs, cronjobs, etc.
    
    Args:
        yaml_content: YAML configuration as string
        namespace: Target namespace (default: "default")
        dry_run: If True, validate without applying (default: False)
    
    Returns:
        String with operation result
    """
    try:
        # Basic YAML validation
        if not yaml_content or not yaml_content.strip():
            return "Error: YAML content is empty"
        
        # Check for common YAML issues
        if not any(keyword in yaml_content for keyword in ['apiVersion:', 'kind:']):
            return "Error: Invalid YAML - missing required fields 'apiVersion' and/or 'kind'"
        
        # Safety check for protected namespaces
        protected_namespaces = ['kube-system', 'kube-public', 'kube-node-lease']
        if namespace in protected_namespaces:
            return f"⚠️ SAFETY CHECK: Cannot apply resources to protected namespace '{namespace}'. Choose a different namespace."
        
        # Escape YAML content for shell (replace single quotes with '\'' pattern)
        yaml_escaped = yaml_content.replace("'", "'\"'\"'")
        
        dry_run_flag = "--dry-run=client" if dry_run else ""
        
        # Use kubectl apply with stdin
        full_command = f"echo '{yaml_escaped}' | sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl apply -f - -n {namespace} {dry_run_flag}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        
        if result.returncode == 0:
            mode = "DRY RUN" if dry_run else "APPLIED"
            return f"[{mode}] Successfully applied YAML configuration to namespace '{namespace}'.\n\n{result.stdout}"
        else:
            return f"Error applying YAML configuration: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"
