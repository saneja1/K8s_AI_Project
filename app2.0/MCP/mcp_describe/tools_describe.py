"""
Describe Agent Tools - Generic K8s resource operations
Handles listing, describing, counting, and inspecting any K8s resource type
"""

import subprocess
import time
from langchain_core.tools import tool

# Cache for kubectl commands (5 seconds TTL for testing)
_cache = {}
_cache_ttl = 5

def _cached_kubectl_command(cache_key, execute_fn):
    """Helper to cache kubectl command results"""
    current_time = time.time()
    
    if cache_key in _cache:
        result, timestamp = _cache[cache_key]
        if current_time - timestamp < _cache_ttl:
            return result
    
    result = execute_fn()
    _cache[cache_key] = (result, current_time)
    return result


@tool
def list_k8s_resources(resource_type: str, namespace: str = "all") -> str:
    """
    List any Kubernetes resource type in the cluster.
    
    Args:
        resource_type: Type of resource (pods, services, deployments, nodes, namespaces, configmaps, 
                       secrets, replicasets, statefulsets, daemonsets, ingresses, persistentvolumes, 
                       persistentvolumeclaims, etc.)
        namespace: Namespace to filter resources (default: "all" for all namespaces, ignored for cluster-scoped resources)
    
    Returns:
        String with resource listing
    
    Examples:
        list_k8s_resources('pods', 'all') -> all pods
        list_k8s_resources('services', 'default') -> services in default namespace
        list_k8s_resources('nodes') -> all nodes (cluster-scoped)
        list_k8s_resources('namespaces') -> all namespaces (cluster-scoped)
    """
    cache_key = f"list_{resource_type}_{namespace}"
    
    def _execute():
        try:
            # Cluster-scoped resources (ignore namespace parameter)
            cluster_scoped = ['nodes', 'namespaces', 'persistentvolumes', 'storageclasses', 
                            'clusterroles', 'clusterrolebindings']
            
            if resource_type in cluster_scoped or namespace == "cluster":
                full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get {resource_type} -o wide"
            elif namespace == "all":
                full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get {resource_type} --all-namespaces -o wide"
            else:
                full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get {resource_type} -n {namespace} -o wide"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "pggo890@k8s-master-01",
                "--zone=us-west1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=8)
            
            if result.returncode == 0:
                return result.stdout if result.stdout else f"No {resource_type} found"
            else:
                return f"Error: {result.stderr}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    return _cached_kubectl_command(cache_key, _execute)


@tool
def describe_k8s_resource(resource_type: str, resource_name: str, namespace: str = "default") -> str:
    """
    Get detailed information about any specific Kubernetes resource.
    
    Args:
        resource_type: Type of resource (pod, service, deployment, node, configmap, secret, etc.)
        resource_name: Name of the resource (can be partial for pods, will auto-match)
        namespace: Namespace of the resource (default: "default", ignored for cluster-scoped resources like nodes)
    
    Returns:
        String with detailed resource information
    
    Examples:
        describe_k8s_resource('pod', 'nginx-abc', 'default')
        describe_k8s_resource('service', 'kubernetes', 'default')
        describe_k8s_resource('node', 'k8s-master-01')
        describe_k8s_resource('deployment', 'coredns', 'kube-system')
    """
    try:
        # Cluster-scoped resources don't need namespace
        cluster_scoped = ['node', 'nodes', 'namespace', 'namespaces', 'persistentvolume', 
                         'persistentvolumes', 'storageclass', 'storageclasses']
        
        # Auto-detect full name for pods (partial name matching)
        if resource_type in ['pod', 'pods']:
            if namespace == "all":
                list_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods --all-namespaces -o name"
            else:
                list_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get pods -n {namespace} -o name"
            
            list_result = subprocess.run([
                "gcloud", "compute", "ssh", "pggo890@k8s-master-01",
                "--zone=us-west1-a",
                f"--command={list_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=8)
            
            full_resource_name = resource_name
            if list_result.returncode == 0:
                for line in list_result.stdout.splitlines():
                    resource_full = line.replace("pod/", "")
                    if resource_name in resource_full:
                        full_resource_name = resource_full
                        break
            resource_name = full_resource_name
        
        # Build describe command
        if resource_type in cluster_scoped:
            full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl describe {resource_type} {resource_name}"
        else:
            full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl describe {resource_type} {resource_name} -n {namespace}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "pggo890@k8s-master-01",
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


@tool
def count_k8s_resources(resource_type: str, namespace: str = "all", filter_by: str = None, filter_value: str = None) -> str:
    """
    Count Kubernetes resources with optional filtering.
    
    Args:
        resource_type: Type of resource to count (pods, services, deployments, nodes, etc.)
        namespace: Namespace to query (default: "all", ignored for cluster-scoped resources)
        filter_by: Optional filter field (status, namespace, node, ready, name, label)
        filter_value: Value to filter by (e.g., 'Running', 'kube-system', 'k8s-master-01')
    
    Returns:
        String with count and details of matching resources
    
    Examples:
        count_k8s_resources('pods', 'all', 'status', 'Running') -> counts running pods
        count_k8s_resources('pods', 'kube-system') -> counts pods in kube-system
        count_k8s_resources('pods', 'all', 'node', 'k8s-master-01') -> counts pods on master node
        count_k8s_resources('services', 'default') -> counts services in default namespace
        count_k8s_resources('nodes', filter_by='status', filter_value='Ready') -> counts ready nodes
    """
    try:
        # Cluster-scoped resources
        cluster_scoped = ['nodes', 'namespaces', 'persistentvolumes', 'storageclasses']
        
        # Build kubectl command
        if resource_type in cluster_scoped:
            command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get {resource_type} -o wide"
        elif namespace == "all":
            command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get {resource_type} --all-namespaces -o wide"
        else:
            command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get {resource_type} -n {namespace} -o wide"
        
        # Execute command
        result = subprocess.run([
            "gcloud", "compute", "ssh", "pggo890@k8s-master-01",
            "--zone=us-west1-a",
            f"--command={command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=8)
        
        if result.returncode != 0:
            return f"Error: {result.stderr}"
        
        output = result.stdout
        lines = output.strip().split('\n')
        
        if len(lines) <= 1:
            return f"No {resource_type} found"
        
        # Filter and count
        data_lines = lines[1:]  # Skip header
        matching_resources = []
        
        for line in data_lines:
            if not line.strip():
                continue
            
            # Apply filter if specified
            if filter_by and filter_value:
                if filter_by == "status":
                    if filter_value in line:
                        matching_resources.append(line)
                
                elif filter_by == "namespace":
                    if line.startswith(filter_value) or f" {filter_value} " in line:
                        matching_resources.append(line)
                
                elif filter_by == "node":
                    if filter_value in line:
                        matching_resources.append(line)
                
                elif filter_by == "ready":
                    if filter_value in line:
                        matching_resources.append(line)
                
                elif filter_by == "name":
                    if filter_value in line:
                        matching_resources.append(line)
                
                elif filter_by == "label":
                    # Would need kubectl with label selector
                    if filter_value in line:
                        matching_resources.append(line)
                
                else:
                    # Generic filter
                    if filter_value in line:
                        matching_resources.append(line)
            else:
                # No filter - count all
                matching_resources.append(line)
        
        count = len(matching_resources)
        
        # Build response
        if filter_by and filter_value:
            response = f"Found {count} {resource_type} matching {filter_by}='{filter_value}':\n\n"
        else:
            response = f"Found {count} {resource_type} total:\n\n"
        
        # Add header
        response += lines[0] + "\n"
        
        # Add matching lines (limit to 20 for readability)
        for line in matching_resources[:20]:
            response += line + "\n"
        
        if len(matching_resources) > 20:
            response += f"\n... and {len(matching_resources) - 20} more"
        
        return response
        
    except Exception as e:
        return f"Error counting resources: {str(e)}"


@tool
def get_all_resources_in_namespace(namespace: str = "default") -> str:
    """
    Get all main resources in a namespace (kubectl get all).
    Shows pods, services, deployments, replicasets, statefulsets, daemonsets together.
    
    Args:
        namespace: Namespace to query (default: "default")
    
    Returns:
        String with all resource information
    
    Example:
        get_all_resources_in_namespace('kube-system') -> shows all resources in kube-system
    """
    cache_key = f"all_resources_{namespace}"
    
    def _execute():
        try:
            full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get all -n {namespace} -o wide"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "pggo890@k8s-master-01",
                "--zone=us-west1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=8)
            
            if result.returncode == 0:
                return result.stdout if result.stdout else f"No resources found in namespace '{namespace}'"
            else:
                return f"Error: {result.stderr}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    return _cached_kubectl_command(cache_key, _execute)


@tool
def get_resource_yaml(resource_type: str, resource_name: str, namespace: str = "default") -> str:
    """
    Get the YAML definition of any Kubernetes resource.
    Useful for inspecting exact configurations, labels, annotations, etc.
    
    Args:
        resource_type: Type of resource (pod, service, deployment, configmap, etc.)
        resource_name: Name of the resource
        namespace: Namespace of the resource (default: "default", ignored for cluster-scoped resources)
    
    Returns:
        String with YAML definition
    
    Examples:
        get_resource_yaml('pod', 'nginx-abc', 'default')
        get_resource_yaml('service', 'kubernetes', 'default')
        get_resource_yaml('deployment', 'coredns', 'kube-system')
    """
    try:
        # Cluster-scoped resources
        cluster_scoped = ['node', 'nodes', 'namespace', 'namespaces', 'persistentvolume']
        
        # Build command
        if resource_type in cluster_scoped:
            full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get {resource_type} {resource_name} -o yaml"
        else:
            full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get {resource_type} {resource_name} -n {namespace} -o yaml"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "pggo890@k8s-master-01",
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
