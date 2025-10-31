"""
Kubernetes Supervisor Agent using LangGraph
Single agent that manages all Kubernetes operations - following the sample pattern
"""

import os
import time
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.tools import tool
from langgraph.graph import StateGraph, MessagesState

# Load environment variables
load_dotenv()

# Simple cache for kubectl responses (30 second TTL)
_kubectl_cache = {}
_cache_ttl = 30


# ============================================================================
# CACHING HELPER (Speed Optimization)
# ============================================================================

def _cached_kubectl_command(cache_key: str, command_func, *args, **kwargs):
    """Cache kubectl responses for 30 seconds to speed up repeated queries."""
    current_time = time.time()
    
    # Check cache
    if cache_key in _kubectl_cache:
        cached_result, timestamp = _kubectl_cache[cache_key]
        if current_time - timestamp < _cache_ttl:
            return cached_result
    
    # Execute command and cache result
    result = command_func(*args, **kwargs)
    _kubectl_cache[cache_key] = (result, current_time)
    
    # Clean old cache entries (keep cache small)
    for key in list(_kubectl_cache.keys()):
        if current_time - _kubectl_cache[key][1] > _cache_ttl:
            del _kubectl_cache[key]
    
    return result

# ============================================================================
# KUBERNETES TOOLS (kubectl commands via SSH) - LangGraph style
# ============================================================================

@tool
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
        ], capture_output=True, text=True, timeout=8)
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


@tool
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
        ], capture_output=True, text=True, timeout=8)
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


@tool
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
        ], capture_output=True, text=True, timeout=8)
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


@tool
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
        ], capture_output=True, text=True, timeout=8)
        
        if result.returncode == 0:
            return result.stdout if result.stdout else "No logs available"
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


@tool
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
        ], capture_output=True, text=True, timeout=8)
        
        if result.returncode == 0:
            return result.stdout
        else:
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Error executing command: {str(e)}"


# ============================================================================
# KUBERNETES SUPERVISOR AGENT (LangGraph Manual Build - New Version)
# ============================================================================

def create_k8s_supervisor_agent(api_key: str = None, verbose: bool = False):
    """
    Create a single Kubernetes supervisor agent using LangGraph StateGraph.
    This is the equivalent of create_react_agent but built manually for the new LangGraph version.
    
    Args:
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        verbose: Whether to show agent reasoning steps
    
    Returns:
        Compiled LangGraph workflow (equivalent to sample pattern)
    """
    # Get API key
    anthropic_api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
    if not anthropic_api_key:
        raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY environment variable.")
    
    # Initialize Claude model (optimized for speed)
    model = ChatAnthropic(
        model="claude-3-haiku-20240307",  # Haiku is fastest Claude model
        anthropic_api_key=anthropic_api_key,
        temperature=0,  # Deterministic for faster responses
        max_tokens=1024  # Reduced from 2048 for faster generation
    )
    
    # ========================================================================
    # DEFINE TOOLS (Already decorated with @tool above)
    # ========================================================================
    
    tools = [get_cluster_pods, get_cluster_nodes, describe_pod, get_pod_logs, get_cluster_events]
    
    # Bind tools to model (LangGraph pattern)
    model_with_tools = model.bind_tools(tools)
    
    # ========================================================================
    # CREATE AGENT NODE FUNCTION (Manual replacement for create_react_agent)
    # ========================================================================
    
    def k8s_supervisor_node(state):
        """
        Kubernetes supervisor agent node - handles all K8s operations.
        This replaces create_react_agent functionality.
        """
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
        
        messages = state["messages"]
        
        # Add system prompt for this agent (optimized for speed)
        system_msg = """You are a fast Kubernetes agent. Use tools to get real cluster data and respond concisely.

TOOLS: get_cluster_pods, get_cluster_nodes, describe_pod, get_pod_logs, get_cluster_events

BE FAST AND DIRECT - Use the appropriate tool and give clear, brief answers."""
        
        # Add system message if not present
        if not messages or messages[0].content != system_msg:
            messages = [AIMessage(content="", additional_kwargs={"system": system_msg})] + messages
        
        # Call model with tools
        response = model_with_tools.invoke(messages)
        
        return {"messages": messages + [response]}
    
    # ========================================================================
    # CREATE TOOL NODE (Manual replacement for ToolNode)
    # ========================================================================
    
    def tool_node(state):
        """Execute tools and return results"""
        from langchain_core.messages import ToolMessage
        
        messages = state["messages"]
        last_message = messages[-1]
        
        tool_results = []
        
        # Execute tool calls if any
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call.get("args", {})
                
                # Find and execute the tool
                for tool in tools:
                    if tool.name == tool_name:
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
        
        return {"messages": messages + tool_results}
    
    # ========================================================================
    # BUILD LANGGRAPH WORKFLOW (Following Sample Pattern)
    # ========================================================================
    
    # Create the graph
    workflow = StateGraph(MessagesState)
    
    # Add nodes
    workflow.add_node("k8s_supervisor", k8s_supervisor_node)
    workflow.add_node("tools", tool_node)
    
    # Define the flow
    workflow.set_entry_point("k8s_supervisor")
    
    # Add conditional edge: if tool calls exist, go to tools, otherwise end
    def should_continue(state):
        messages = state["messages"]
        last_message = messages[-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        return "__end__"
    
    workflow.add_conditional_edges("k8s_supervisor", should_continue, {"tools": "tools", "__end__": "__end__"})
    workflow.add_edge("tools", "k8s_supervisor")
    
    return workflow


# ============================================================================
# AGENT INVOCATION FUNCTION
# ============================================================================

def ask_k8s_agent(question: str, api_key: str = None, verbose: bool = False) -> dict:
    """
    Ask the Kubernetes supervisor agent a question and get a response.
    Uses LangGraph StateGraph pattern (equivalent to sample's create_react_agent approach).
    
    Args:
        question: User's question about the K8s cluster
        api_key: Anthropic API key (optional)
        verbose: Whether to show detailed agent reasoning
    
    Returns:
        Dict with 'answer' and 'messages' (full conversation)
    """
    try:
        # Create supervisor workflow (manual replacement for create_react_agent)
        workflow = create_k8s_supervisor_agent(api_key=api_key, verbose=verbose)
        
        # Compile the workflow (same as sample pattern)
        app = workflow.compile()
        
        # Execute with user question (following sample pattern exactly)
        from langchain_core.messages import HumanMessage
        
        result = app.invoke({
            "messages": [
                HumanMessage(content=question)
            ]
        })
        
        # Extract final answer (last AI message from supervisor)
        messages = result.get("messages", [])
        final_answer = "No response generated."
        
        # Get the last AI message with actual content (following sample pattern)
        for message in reversed(messages):
            if hasattr(message, 'content') and message.content:
                # Skip system messages and tool messages
                if not hasattr(message, 'tool_calls') or not message.tool_calls:
                    if message.content.strip() and not message.content.startswith("Error"):
                        final_answer = message.content
                        break
        
        return {
            "answer": final_answer,
            "messages": messages
        }
        
    except Exception as e:
        # Fallback to direct tool execution if supervisor fails
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
    # Example: Test Kubernetes supervisor agent
    print("Testing Kubernetes Supervisor Agent (LangGraph)...")
    
    # Test 1: Pod listing
    response = ask_k8s_agent("List all pods in the cluster")
    print("\n=== POD LISTING TEST ===")
    print(response["answer"][:200] + "..." if len(response["answer"]) > 200 else response["answer"])
    
    # Test 2: Node status
    response = ask_k8s_agent("Show me cluster nodes")
    print("\n=== NODE STATUS TEST ===")
    print(response["answer"][:200] + "..." if len(response["answer"]) > 200 else response["answer"])
    
    # Test 3: Cluster events
    response = ask_k8s_agent("What are recent cluster events?")
    print("\n=== CLUSTER EVENTS TEST ===") 
    print(response["answer"][:200] + "..." if len(response["answer"]) > 200 else response["answer"])
    
    print("\nKubernetes supervisor agent test completed!")
