"""
Kubernetes Multi-Agent System using LangGraph Supervisor Pattern
Based on the sample multi-agent architecture for specialized K8s operations
"""

import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph_supervisor import create_supervisor

# Load environment variables
load_dotenv()


# ============================================================================
# KUBERNETES TOOLS (kubectl commands via SSH)
# ============================================================================

def get_cluster_pods(namespace: str = "all") -> str:
    """
    Get list of all pods in the cluster or specific namespace.
    Args:
        namespace: Namespace to filter pods (default: "all" for all namespaces)
    Returns:
        String with pod information
    """
    import subprocess
    
    try:
        if namespace == "all":
            command = "kubectl get pods --all-namespaces -o wide"
        else:
            command = f"kubectl get pods -n {namespace} -o wide"
        
        # Execute on master node via SSH
        full_command = f"export KUBECONFIG=/etc/kubernetes/admin.conf && {command}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "k8s-master-001",
            "--zone=us-central1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


def get_cluster_nodes() -> str:
    """
    Get list of all nodes in the cluster with detailed information.
    Returns:
        String with node information including status, roles, age, and version
    """
    import subprocess
    
    try:
        command = "kubectl get nodes -o wide"
        full_command = f"export KUBECONFIG=/etc/kubernetes/admin.conf && {command}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "k8s-master-001",
            "--zone=us-central1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


def describe_pod(pod_name: str, namespace: str = "default") -> str:
    """
    Get detailed information about a specific pod.
    Args:
        pod_name: Name of the pod
        namespace: Namespace of the pod (default: "default")
    Returns:
        Detailed pod description including events, status, and configuration
    """
    import subprocess
    
    try:
        command = f"kubectl describe pod {pod_name} -n {namespace}"
        full_command = f"export KUBECONFIG=/etc/kubernetes/admin.conf && {command}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "k8s-master-001",
            "--zone=us-central1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


def get_pod_logs(pod_name: str, namespace: str = "default", tail: int = 50) -> str:
    """
    Get logs from a specific pod.
    Args:
        pod_name: Name of the pod
        namespace: Namespace of the pod (default: "default")
        tail: Number of recent log lines to retrieve (default: 50)
    Returns:
        Pod logs
    """
    import subprocess
    
    try:
        command = f"kubectl logs {pod_name} -n {namespace} --tail={tail}"
        full_command = f"export KUBECONFIG=/etc/kubernetes/admin.conf && {command}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "k8s-master-001",
            "--zone=us-central1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            return result.stdout if result.stdout else "No logs available"
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


def get_cluster_events(namespace: str = "all") -> str:
    """
    Get cluster events to see what's happening in the cluster.
    Args:
        namespace: Namespace to filter events (default: "all" for all namespaces)
    Returns:
        Recent cluster events
    """
    import subprocess
    
    try:
        if namespace == "all":
            command = "kubectl get events --all-namespaces --sort-by='.lastTimestamp'"
        else:
            command = f"kubectl get events -n {namespace} --sort-by='.lastTimestamp'"
        
        full_command = f"export KUBECONFIG=/etc/kubernetes/admin.conf && {command}"
        
        result = subprocess.run([
            "gcloud", "compute", "ssh", "k8s-master-001",
            "--zone=us-central1-a",
            f"--command={full_command}",
            "--quiet"
        ], capture_output=True, text=True, timeout=15)
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


# ============================================================================
# MULTI-AGENT KUBERNETES SYSTEM SETUP (Following Sample Pattern)
# ============================================================================

def create_k8s_multiagent_system(api_key: str = None, verbose: bool = False):
    """
    Create a multi-agent Kubernetes system using LangGraph supervisor pattern.
    Following the architecture from sample/multiagent_sample.py
    
    Args:
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        verbose: Whether to show agent reasoning steps
    
    Returns:
        Compiled LangGraph multi-agent workflow
    """
    # Get API key
    anthropic_api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
    if not anthropic_api_key:
        raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY environment variable.")
    
    # Initialize Claude model
    model = ChatAnthropic(
        model="claude-3-haiku-20240307",
        anthropic_api_key=anthropic_api_key,
        temperature=0.2,
        max_tokens=2048
    )
    
    # ========================================================================
    # SPECIALIZED AGENTS (Using langgraph-supervisor approach)
    # ========================================================================
    
    # Define agent configurations for langgraph-supervisor
    agents = [
        {
            "name": "pod_expert",
            "tools": [get_cluster_pods, describe_pod, get_pod_logs],
            "prompt": "You are a Kubernetes pod management expert. Handle pod listing, descriptions, logs, and troubleshooting. Always use appropriate tools to get accurate data."
        },
        {
            "name": "node_expert", 
            "tools": [get_cluster_nodes],
            "prompt": "You are a Kubernetes node management expert. Handle node status, health checks, and node-related operations. Always use appropriate tools to get accurate data."
        },
        {
            "name": "cluster_expert",
            "tools": [get_cluster_events],
            "prompt": "You are a Kubernetes cluster monitoring expert. Handle cluster events, overall health, and system-wide monitoring. Always use appropriate tools to get accurate data."
        }
    ]
    
    # ========================================================================
    # SUPERVISOR WORKFLOW (Using langgraph-supervisor)
    # ========================================================================
    
    # Create supervisor workflow using agent configurations
    workflow = create_supervisor(
        agents=agents,
        model=model,
        supervisor_prompt=(
            "You are a Kubernetes cluster supervisor managing three expert agents:\n\n"
            "ROUTING RULES:\n"
            "- For pod questions (list pods, pod logs, pod details, troubleshooting) → pod_expert\n"
            "- For node questions (node status, node health, worker/master info) → node_expert\n" 
            "- For cluster-wide questions (events, overall health, system status) → cluster_expert\n\n"
            "GUIDELINES:\n"
            "- Use the most appropriate expert for each question\n"
            "- For complex questions, use multiple experts sequentially\n"
            "- Always synthesize agent responses into a clear, comprehensive final answer\n"
            "- Provide actionable insights based on the expert data\n\n"
            "Be helpful and provide detailed information from your expert agents."
        )
    )
    
    return workflow


# ============================================================================
# AGENT INVOCATION FUNCTION
# ============================================================================

def ask_k8s_agent(question: str, api_key: str = None, verbose: bool = False) -> dict:
    """
    Ask the Kubernetes multi-agent system a question and get a response.
    Uses the LangGraph supervisor pattern to route questions to appropriate expert agents.
    
    Args:
        question: User's question about the K8s cluster
        api_key: Anthropic API key (optional)
        verbose: Whether to show detailed agent reasoning
    
    Returns:
        Dict with 'answer' and 'messages' (full conversation)
    """
    try:
        # Create multi-agent workflow
        workflow = create_k8s_multiagent_system(api_key=api_key, verbose=verbose)
        
        # Compile the workflow
        app = workflow.compile()
        
        # Execute with user question (following sample pattern)
        result = app.invoke({
            "messages": [
                {
                    "role": "user", 
                    "content": question
                }
            ]
        })
        
        # Extract final answer (last AI message from supervisor)
        messages = result.get("messages", [])
        final_answer = "No response generated."
        
        # Get the last supervisor message (following sample pattern)
        for message in reversed(messages):
            if hasattr(message, 'content') and message.content:
                # Check if it's a supervisor message (final answer)
                if hasattr(message, 'name') and message.name == 'supervisor':
                    final_answer = message.content
                    break
                elif not hasattr(message, 'name'):  # Fallback
                    final_answer = message.content
                    break
        
        return {
            "answer": final_answer,
            "messages": messages
        }
        
    except Exception as e:
        # Fallback to direct tool execution if multi-agent fails
        return _fallback_direct_response(question, str(e))


# ============================================================================
# FALLBACK FUNCTION (Direct Tool Execution)
# ============================================================================

def _fallback_direct_response(question: str, error_msg: str) -> dict:
    """
    Fallback function that directly executes appropriate tools if multi-agent system fails.
    """
    question_lower = question.lower()
    
    try:
        if any(keyword in question_lower for keyword in ['pod', 'pods', 'list', 'show', 'get']):
            pod_data = get_cluster_pods("all")
            return {
                "answer": f"**ALL PODS** (via fallback):\n\n```\n{pod_data}\n```\n\n*Note: Used fallback mode due to: {error_msg}*",
                "messages": []
            }
        elif any(keyword in question_lower for keyword in ['node', 'nodes']):
            node_data = get_cluster_nodes()
            return {
                "answer": f"**NODES** (via fallback):\n\n```\n{node_data}\n```\n\n*Note: Used fallback mode due to: {error_msg}*",
                "messages": []
            }
        elif 'event' in question_lower:
            event_data = get_cluster_events()
            return {
                "answer": f"**EVENTS** (via fallback):\n\n```\n{event_data}\n```\n\n*Note: Used fallback mode due to: {error_msg}*",
                "messages": []
            }
        else:
            return {
                "answer": f"I encountered an error with the multi-agent system: {error_msg}\n\nPlease try asking about:\n• **'list all pods'**\n• **'show nodes'**\n• **'show events'**",
                "messages": []
            }
    except Exception as fallback_error:
        return {
            "answer": f"Both multi-agent and fallback systems failed. Please check your cluster connection.\n\nErrors:\n- Multi-agent: {error_msg}\n- Fallback: {str(fallback_error)}",
            "messages": []
        }


# ============================================================================
# EXAMPLE USAGE (for testing)
# ============================================================================

if __name__ == "__main__":
    # Example: Test multi-agent system
    print("Testing Kubernetes Multi-Agent System...")
    
    # Test 1: Pod listing (should route to pod_expert)
    response = ask_k8s_agent("List all pods in the cluster")
    print("\n=== POD LISTING TEST ===")
    print(response["answer"][:200] + "...")
    
    # Test 2: Node status (should route to node_expert)  
    response = ask_k8s_agent("Show me cluster nodes")
    print("\n=== NODE STATUS TEST ===")
    print(response["answer"][:200] + "...")
    
    # Test 3: Cluster events (should route to cluster_expert)
    response = ask_k8s_agent("What are recent cluster events?")
    print("\n=== CLUSTER EVENTS TEST ===") 
    print(response["answer"][:200] + "...")
    
    print("\nMulti-agent system test completed!")
