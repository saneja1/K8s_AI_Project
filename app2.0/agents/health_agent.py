"""
Health Agent - Monitors cluster health and status
Handles queries about node health, cluster events, and overall cluster status
"""

import os
import subprocess
import time
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, MessagesState
from langchain_core.tools import tool

# Load environment variables
load_dotenv()

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


# ============================================================================
# HEALTH AGENT TOOLS (Defined in this file)
# ============================================================================

@tool
def get_cluster_nodes() -> str:
    """
    Get list of all nodes in the cluster with detailed information.
    Returns:
        String with node information including status, roles, age, and version
    """
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


@tool
def describe_node(node_name: str = "all") -> str:
    """
    Get detailed node conditions including Ready, MemoryPressure, DiskPressure, PIDPressure status.
    Args:
        node_name: Name of the node to describe (default: "all" for all nodes)
    Returns:
        String with node conditions showing health status
    """
    cache_key = f"describe_node_{node_name}"
    
    def _execute():
        try:
            if node_name == "all":
                # Get conditions for all nodes using jsonpath
                full_command = "sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{\"\\n\"}{range .status.conditions[*]}{\"  \"}{.type}{\" = \"}{.status}{\" (Reason: \"}{.reason}{\" | Message: \"}{.message}{\")\"}  {\"\\n\"}{end}{\"\\n\"}{end}'"
            else:
                # Get conditions for specific node
                full_command = f"sudo -E KUBECONFIG=/etc/kubernetes/admin.conf kubectl get node {node_name} -o jsonpath='{{.metadata.name}}{{\"\\n\"}}{{range .status.conditions[*]}}{{\"  \"}}{{.type}}{{\" = \"}}{{.status}}{{\" (Reason: \"}}{{.reason}}{{\" | Message: \"}}{{.message}}{{\")\"}}{{\"\n\"}}{{end}}'"
            
            result = subprocess.run([
                "gcloud", "compute", "ssh", "swinvm15@k8s-master-001",
                "--zone=us-central1-a",
                f"--command={full_command}",
                "--quiet"
            ], capture_output=True, text=True, timeout=8)
            
            if result.returncode == 0:
                return result.stdout if result.stdout.strip() else "No node conditions found"
            else:
                return f"Error: {result.stderr}"
        except Exception as e:
            return f"Error executing command: {str(e)}"
    
    return _cached_kubectl_command(cache_key, _execute)


@tool
def get_cluster_events(namespace: str = "all") -> str:
    """
    Get cluster events to see what's happening in the cluster.
    Args:
        namespace: Namespace to filter events (default: "all" for all namespaces)
    Returns:
        String with cluster events
    """
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


def create_health_agent(api_key: str = None, verbose: bool = False):
    """
    Create a Health Agent that monitors cluster health.
    
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
    
    # Define tools for health monitoring (focused on node health and events only)
    tools = [get_cluster_nodes, describe_node, get_cluster_events]
    
    # Bind tools to model
    model_with_tools = model.bind_tools(tools)
    
    # Create agent node function
    def health_agent_node(state):
        """Health agent node - monitors cluster health"""
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
        
        messages = state["messages"]
        
        # System prompt for health agent
        system_msg = """You are a Kubernetes Health Agent specializing in cluster health monitoring.

YOUR RESPONSIBILITY:
Monitor and report on NODE HEALTH and CLUSTER EVENTS only. 
Do NOT handle pod counting, pod listing, or resource capacity questions.

AVAILABLE TOOLS:
- get_cluster_nodes: Show all nodes with their status (Ready/NotReady), roles, age, version
- describe_node: Get detailed node information including conditions (MemoryPressure, DiskPressure, PIDPressure, Ready), capacity, and allocatable resources
- get_cluster_events: Show recent cluster events (warnings, errors, failures)

WHEN TO USE EACH TOOL:
- "Is my cluster healthy?" → use get_cluster_nodes to check node status
- "Are nodes ready?" → use get_cluster_nodes
- "Show node conditions" → ALWAYS use describe_node to see detailed conditions (MemoryPressure, DiskPressure, PIDPressure, Ready)
- "List conditions" or "what are the conditions" → ALWAYS use describe_node
- "Node details" or "describe node" → use describe_node
- "Any errors or warnings?" → use get_cluster_events
- "What's the status of nodes?" → use get_cluster_nodes

IMPORTANT: 
- When user asks for "conditions", they want ALL conditions (Ready, MemoryPressure, DiskPressure, PIDPressure, NetworkUnavailable)
- Use describe_node tool for condition details, not just get_cluster_nodes
- get_cluster_nodes only shows basic Ready/NotReady status
- describe_node shows all 5 condition types

RESPONSE RULES:
- Focus ONLY on node health and cluster events
- If asked about pods, CPU, memory, or resource capacity → say "That's handled by another agent"
- Be direct and clear about health status
- If nodes are NotReady, say so explicitly
- If get_cluster_events returns empty or "No resources found" → that means NO events (cluster is quiet/healthy)
- If there are warnings/errors in events, highlight them
- For "is cluster healthy" questions:
  * Check node status (all should be Ready)
  * Check recent events (should not have critical errors)
- When asked to "show events" and there are none → say "No recent events found. The cluster is operating normally."

EXAMPLES:
User: "Are all nodes healthy?"
  → Call get_cluster_nodes
  → Check STATUS column
  → Answer: "Yes, all nodes are Ready" OR "No, node X is NotReady"

User: "List node conditions"
  → Call describe_node
  → Show all conditions: Ready, MemoryPressure, DiskPressure, PIDPressure, NetworkUnavailable
  → Explain status of each

User: "How many nodes and their conditions?"
  → Call get_cluster_nodes (for count)
  → Call describe_node (for detailed conditions)
  → Provide count + detailed condition breakdown

User: "Any recent problems?"
  → Call get_cluster_events
  → Look for Warning/Error types
  → Summarize issues found
"""
        
        # Check if we have tool results and need final answer
        has_tool_results = any(isinstance(m, ToolMessage) for m in messages)
        last_message = messages[-1]
        has_pending_tool_calls = hasattr(last_message, 'tool_calls') and last_message.tool_calls
        
        if has_tool_results and not has_pending_tool_calls:
            # Force final answer
            messages_with_system = [SystemMessage(content=system_msg)] + messages + [
                HumanMessage(content="Provide a direct, concise answer about cluster health.")
            ]
            response = model_with_tools.invoke(messages_with_system)
        else:
            # Normal flow
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
    
    # Build workflow
    workflow = StateGraph(MessagesState)
    
    # Add nodes
    workflow.add_node("health_agent", health_agent_node)
    workflow.add_node("tools", tool_node)
    
    # Set entry point
    workflow.set_entry_point("health_agent")
    
    # Add conditional edges
    def should_continue(state):
        messages = state["messages"]
        last_message = messages[-1]
        
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            # Count tool calls to prevent infinite loops
            tool_call_count = sum(1 for m in messages if hasattr(m, 'tool_calls') and m.tool_calls)
            if tool_call_count > 3:
                return "__end__"
            return "tools"
        return "__end__"
    
    workflow.add_conditional_edges("health_agent", should_continue, {"tools": "tools", "__end__": "__end__"})
    workflow.add_edge("tools", "health_agent")
    
    return workflow


def ask_health_agent(question: str, api_key: str = None, verbose: bool = False) -> dict:
    """
    Ask the Health Agent a question about cluster health.
    
    Args:
        question: Question about cluster health
        api_key: Anthropic API key (optional)
        verbose: Whether to show detailed reasoning
    
    Returns:
        Dict with 'answer' and 'messages'
    """
    try:
        # Create workflow
        workflow = create_health_agent(api_key=api_key, verbose=verbose)
        
        # Compile
        app = workflow.compile()
        
        # Execute
        from langchain_core.messages import HumanMessage
        
        result = app.invoke({
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
            "answer": f"Health Agent error: {str(e)}",
            "messages": []
        }


# Test function
if __name__ == "__main__":
    print("Testing Health Agent...")
    
    # Test 1: Node health
    print("\n=== TEST 1: Node Health ===")
    result = ask_health_agent("Are all nodes healthy?")
    print(result["answer"])
    
    # Test 2: Recent events
    print("\n=== TEST 2: Recent Events ===")
    result = ask_health_agent("Any recent problems in the cluster?")
    print(result["answer"])
    
    # Test 3: Overall cluster health
    print("\n=== TEST 3: Overall Cluster Health ===")
    result = ask_health_agent("Is my cluster healthy?")
    print(result["answer"])
    
    print("\nHealth Agent tests completed!")
