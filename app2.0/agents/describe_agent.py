"""
Describe Agent - Information retrieval and resource inspection
Handles queries about listing, describing, and counting K8s resources
"""

import os
import subprocess
from functools import lru_cache
import time
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, MessagesState
from langchain_core.tools import tool

# Load environment variables
load_dotenv()

# Cache for kubectl commands (30 seconds TTL)
_cache = {}
_cache_ttl = 30

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


# ============================================================================
# DESCRIBE AGENT TOOLS - GENERIC APPROACH (All tools defined here, not imported)
# ============================================================================

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
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
                "--zone=us-central1-a",
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
        describe_k8s_resource('node', 'k8s-master-001')
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
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
                "--zone=us-central1-a",
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


@tool
def count_k8s_resources(resource_type: str, namespace: str = "all", filter_by: str = None, filter_value: str = None) -> str:
    """
    Count Kubernetes resources with optional filtering.
    
    Args:
        resource_type: Type of resource to count (pods, services, deployments, nodes, etc.)
        namespace: Namespace to query (default: "all", ignored for cluster-scoped resources)
        filter_by: Optional filter field (status, namespace, node, ready, name, label)
        filter_value: Value to filter by (e.g., 'Running', 'kube-system', 'k8s-master-001')
    
    Returns:
        String with count and details of matching resources
    
    Examples:
        count_k8s_resources('pods', 'all', 'status', 'Running') -> counts running pods
        count_k8s_resources('pods', 'kube-system') -> counts pods in kube-system
        count_k8s_resources('pods', 'all', 'node', 'k8s-master-001') -> counts pods on master node
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
            "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
            "--zone=us-central1-a",
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
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
                "--zone=us-central1-a",
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


# Remove all old specific tools (get_cluster_pods, describe_node, etc.)
# They are replaced by the 5 generic tools above


# ============================================================================
# DESCRIBE AGENT CREATION
# ============================================================================

def create_describe_agent(api_key: str = None, verbose: bool = False):
    """
    Create the Describe Agent for resource information retrieval.
    
    Args:
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        verbose: Whether to show agent reasoning steps
    
    Returns:
        Compiled LangGraph workflow
    """
    # Get API key
    anthropic_api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
    if not anthropic_api_key:
        raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY environment variable.")
    
    # Initialize Claude model
    model = ChatAnthropic(
        model="claude-3-haiku-20240307",
        anthropic_api_key=anthropic_api_key,
        temperature=0,
        max_tokens=1024
    )
    
    # Define tools for describe agent - 5 GENERIC tools
    tools = [
        list_k8s_resources,
        describe_k8s_resource,
        count_k8s_resources,
        get_all_resources_in_namespace,
        get_resource_yaml
    ]
    
    # Bind tools to model
    model_with_tools = model.bind_tools(tools)
    
    # Create agent node function
    def describe_agent_node(state):
        """Describe agent node - handles resource information queries"""
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
        
        messages = state["messages"]
        
        # System prompt for describe agent
        system_msg = """You are a Kubernetes Describe Agent specializing in resource information and discovery.

YOUR RESPONSIBILITY:
List, describe, count, and provide information about ANY Kubernetes resources.
You handle WHAT EXISTS in the cluster, not health status or resource usage.

AVAILABLE TOOLS (5 GENERIC TOOLS):

1. list_k8s_resources(resource_type, namespace='all')
   - List ANY K8s resource type
   - resource_type: pods, services, deployments, nodes, namespaces, configmaps, secrets, replicasets, 
                    statefulsets, daemonsets, ingresses, persistentvolumes, etc.
   - Works with ALL resource types that kubectl supports

2. describe_k8s_resource(resource_type, resource_name, namespace='default')
   - Get detailed info about ANY specific resource
   - Works with ANY resource type (pod, service, deployment, node, etc.)
   - Auto-matches partial pod names

3. count_k8s_resources(resource_type, namespace='all', filter_by=None, filter_value=None)
   - Count ANY resources with optional filtering
   - filter_by: status, namespace, node, ready, name, label
   - ALWAYS use this for counting, never manually count

4. get_all_resources_in_namespace(namespace='default')
   - Quick overview: pods, services, deployments, replicasets together
   - Equivalent to: kubectl get all -n <namespace>

5. get_resource_yaml(resource_type, resource_name, namespace='default')
   - Get YAML definition of ANY resource
   - Useful for inspecting configurations, labels, annotations

TOOL SELECTION GUIDE:

"List all X" → list_k8s_resources('X', 'all')
  Examples: "list all pods", "show me services", "what deployments exist"

"Describe X named Y" → describe_k8s_resource('X', 'Y', namespace)
  Examples: "describe pod nginx", "describe node k8s-master-001"

"How many X" → count_k8s_resources('X', ...)
  Examples: "how many pods", "count services in default", "how many pods on node-1"

"What's in namespace X" → get_all_resources_in_namespace('X')
  Example: "show me everything in kube-system"

"Get YAML of X" → get_resource_yaml('X', 'name', namespace)
  Example: "show me the yaml for service kubernetes"

COUNTING BEST PRACTICES:
- ALWAYS use count_k8s_resources, NEVER manually count tool output
- For pods on a node: count_k8s_resources('pods', 'all', 'node', 'k8s-master-001')
- For running pods: count_k8s_resources('pods', 'all', 'status', 'Running')
- For resources in namespace: count_k8s_resources('services', 'kube-system')

RESOURCE TYPE NAMES (use plural forms):
- pods (not pod)
- services (not svc or service)
- deployments (not deploy)
- nodes (not node)
- namespaces (not ns)
- configmaps, secrets, replicasets, statefulsets, daemonsets, ingresses, persistentvolumes, etc.

RESPONSE RULES:
- Present information clearly and organized
- Highlight important fields (status, replicas, conditions)
- If asked about resource HEALTH → say "Health Agent handles that"
- If asked about resource USAGE/CAPACITY (CPU/memory) → say "Resources Agent handles that"
- For large outputs, summarize key points
- Always use the generic tools, not specific ones

EXAMPLES:

User: "list all pods"
→ list_k8s_resources('pods', 'all')
→ Present the pod list

User: "how many pods are on k8s-master-001"
→ count_k8s_resources('pods', 'all', 'node', 'k8s-master-001')
→ Report count with pod names

User: "describe the nginx pod in default namespace"
→ describe_k8s_resource('pod', 'nginx', 'default')
→ Present key information

User: "show me all services"
→ list_k8s_resources('services', 'all')
→ Present service list

User: "what namespaces exist"
→ list_k8s_resources('namespaces')
→ List all namespaces

User: "what's deployed in kube-system"
→ get_all_resources_in_namespace('kube-system')
→ Summarize all resources
"""
        
        # Check if we have tool results
        has_tool_results = any(isinstance(m, ToolMessage) for m in messages)
        last_message = messages[-1]
        has_pending_tool_calls = hasattr(last_message, 'tool_calls') and last_message.tool_calls
        
        # Force final answer if we have tool results but no pending calls
        if has_tool_results and not has_pending_tool_calls:
            messages_with_system = [SystemMessage(content=system_msg)] + messages + [
                HumanMessage(content="Provide a clear, organized answer based on the tool results. Don't mention the tools.")
            ]
            response = model_with_tools.invoke(messages_with_system)
        else:
            # Normal flow - add system message if not present
            if not messages or not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=system_msg)] + messages
            
            response = model_with_tools.invoke(messages)
        
        return {"messages": [response]}
    
    # Create tool node
    def tool_node(state):
        """Execute tools and return results"""
        from langchain_core.messages import ToolMessage
        
        messages = state["messages"]
        last_message = messages[-1]
        
        tool_results = []
        
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call.get("args", {})
                
                # Find and execute the tool
                tool_found = False
                for tool in tools:
                    if tool.name == tool_name:
                        tool_found = True
                        try:
                            result = tool.invoke(tool_args)
                            tool_results.append(
                                ToolMessage(
                                    content=str(result),
                                    tool_call_id=tool_call["id"]
                                )
                            )
                        except Exception as e:
                            tool_results.append(
                                ToolMessage(
                                    content=f"Error executing {tool_name}: {str(e)}",
                                    tool_call_id=tool_call["id"]
                                )
                            )
                        break
                
                if not tool_found:
                    tool_results.append(
                        ToolMessage(
                            content=f"Tool '{tool_name}' not found",
                            tool_call_id=tool_call["id"]
                        )
                    )
        
        return {"messages": tool_results}
    
    # Build LangGraph workflow
    workflow = StateGraph(MessagesState)
    
    workflow.add_node("describe_agent", describe_agent_node)
    workflow.add_node("tools", tool_node)
    
    workflow.set_entry_point("describe_agent")
    
    def should_continue(state):
        messages = state["messages"]
        last_message = messages[-1]
        
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            tool_call_count = sum(1 for m in messages if hasattr(m, 'tool_calls') and m.tool_calls)
            if tool_call_count > 3:
                return "__end__"
            return "tools"
        return "__end__"
    
    workflow.add_conditional_edges("describe_agent", should_continue, {"tools": "tools", "__end__": "__end__"})
    workflow.add_edge("tools", "describe_agent")
    
    return workflow


def ask_describe_agent(question: str, api_key: str = None, verbose: bool = False) -> dict:
    """
    Ask the Describe Agent a question about cluster resources.
    
    Args:
        question: Question about cluster resources
        api_key: Anthropic API key (optional)
        verbose: Show reasoning steps (optional)
    
    Returns:
        dict with 'answer' and 'messages' keys
    """
    try:
        # Create agent
        agent_workflow = create_describe_agent(api_key=api_key, verbose=verbose)
        agent = agent_workflow.compile()
        
        # Invoke agent
        from langchain_core.messages import HumanMessage
        result = agent.invoke({
            "messages": [HumanMessage(content=question)]
        })
        
        # Extract final answer
        messages = result.get("messages", [])
        final_answer = "No response generated."
        
        from langchain_core.messages import AIMessage
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content and message.content.strip():
                final_answer = message.content
                break
        
        return {
            "answer": final_answer,
            "messages": messages
        }
        
    except Exception as e:
        return {
            "answer": f"Describe Agent error: {str(e)}",
            "messages": []
        }


# Test function
if __name__ == "__main__":
    print("Testing Describe Agent...")
    
    # Test 1: List pods
    print("\n=== TEST 1: List All Pods ===")
    result = ask_describe_agent("List all pods in the cluster")
    print(result["answer"])
    
    # Test 2: Count pods on node
    print("\n=== TEST 2: Count Pods on Master Node ===")
    result = ask_describe_agent("How many pods are running on k8s-master-001?")
    print(result["answer"])
    
    # Test 3: List namespaces
    print("\n=== TEST 3: List Namespaces ===")
    result = ask_describe_agent("What namespaces exist in the cluster?")
    print(result["answer"])
    
    print("\nDescribe Agent tests completed!")
