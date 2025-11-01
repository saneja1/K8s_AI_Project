"""
Kubernetes Supervisor Agent using LangGraph
Single agent that manages all Kubernetes operations - following the sample pattern
Tools are now separated in k8s_tools.py for better organization
"""

import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, MessagesState

# Import tools from separate file
from .k8s_tools import (
    get_cluster_pods,
    get_cluster_nodes,
    describe_node,
    describe_pod,
    get_pod_logs,
    get_cluster_events,
    count_pods_on_node,
    count_resources
)

# Load environment variables
load_dotenv()


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
    
    tools = [get_cluster_pods, get_cluster_nodes, describe_node, describe_pod, get_pod_logs, get_cluster_events, count_pods_on_node, count_resources]
    
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
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
        
        messages = state["messages"]
        
        # Add system prompt for this agent (optimized for speed)
        system_msg = """You are a Kubernetes agent that MUST use tools to get real-time cluster data.

CRITICAL: You MUST call the appropriate tool for EVERY question. NEVER guess or use cached knowledge.

AVAILABLE TOOLS:
- get_cluster_pods: List all pods with their NODE location (use this to see which pods are on which node)
  * ALWAYS use namespace='all' to see ALL pods across all namespaces (kube-system, default, etc.)
  * Only use a specific namespace if user explicitly asks for one namespace
- get_cluster_nodes: Show nodes with ONLY basic info (status, roles, version) - NO capacity/taints/labels
- describe_node: Get DETAILED node information including TAINTS, LABELS, CAPACITY, ALLOCATABLE resources, CONDITIONS
- describe_pod: Get pod details
- get_pod_logs: Retrieve logs
- get_cluster_events: Show events
- count_pods_on_node: **USE THIS for counting pods on a specific node** (e.g., 'k8s-master-001', 'k8s-worker-01')
- count_resources: **FLEXIBLE counting tool** for any resource type with filtering
  * Examples: count_resources('pods', 'status', 'Running') -> running pods
  * count_resources('pods', 'namespace', 'kube-system') -> pods in namespace
  * count_resources('pods', 'ready', '0/1') -> not ready pods
  * Works with: pods, nodes, services, deployments
  * Filters: status, namespace, node, ready, name, age, ip

IMPORTANT - Tool Selection:
- For CAPACITY, MEMORY, CPU resources → use describe_node tool (NOT get_cluster_nodes)
- For TAINTS, LABELS → use describe_node tool
- For basic node list/status → use get_cluster_nodes tool
- To LIST pods on a node: Find ALL rows where the NODE column (not NAME column) contains that node name
- To COUNT pods on a node: Count ALL rows where the NODE column matches that node name
- The NODE column is typically the 6th or 7th column in kubectl output
- Pod names are in NAME column (column 2), but node location is in NODE column
- Example: "kube-flannel-ds-vbnxb" running on "k8s-master-001" - check NODE column, not NAME
- CRITICAL PROCESS for counting/listing pods on a specific node:
  1. Call get_cluster_pods with namespace='all' to get ALL pods
  2. The kubectl output may have WORD-WRAPPED LINES due to terminal width
  3. Each pod is represented by a data row that contains: NAMESPACE, NAME, READY, STATUS, RESTARTS, AGE, IP, NODE columns
  4. The NODE column value tells you which node the pod runs on (e.g., "k8s-master-001" or "k8s-worker-01")
  5. IMPORTANT: Some lines may be split/wrapped - look for the NODE column value in each pod's data
  6. To count pods on a specific node: Search the entire output and count EVERY occurrence of that exact NODE name
     - Example: If you find "k8s-worker-01" 3 times → answer is 3 pods
     - DO NOT subtract or exclude any pods - if the node name appears, count it
  7. To list pods on a specific node: Find each occurrence of that NODE name, then look for the NAME column value in that same pod's data
  8. Do NOT filter by pod NAME containing "master" or "worker" - check the NODE column value instead
  9. CRITICAL: DaemonSet pods (kube-flannel-ds-*, kube-proxy-*, kube-system pods) MUST be counted - they are real pods running on that node
- Example node names: k8s-master-001, k8s-worker-01
- Example pod types that DON'T have node names in their pod names:
  * kube-flannel-ds-* (runs on all nodes via DaemonSet)
  * kube-proxy-* (runs on all nodes via DaemonSet)
  * coredns-* (typically runs on master/control-plane)
  * Application pods (can run on any node)

WORKFLOW:
1. User asks a question
2. You MUST call the appropriate tool that has the needed information
3. If comparing MULTIPLE nodes/pods, call the tool MULTIPLE TIMES (once for each)
4. After getting tool results, analyze the data and provide the answer
5. If the tool output doesn't contain what you need, say so - DON'T guess

RESPONSE RULES:
- Answer directly without mentioning which tool you used
- Be brief and to the point
- When LISTING pods: Include EVERY pod where NODE column matches - don't skip any (especially kube-flannel and kube-proxy)
- When COUNTING pods: Count EVERY row where NODE column matches
- When listing pods on master: MUST include kube-flannel-ds-vbnxb, kube-proxy-2z4vj, AND all pods with "master" in name
- For CAPACITY: extract CPU and memory from describe_node output
- For TAINTS: extract from describe_node output and show the taint key, value, and effect
- If tools don't provide the needed information, say: "I don't have access to that information."

Examples:
User: "how many pods are on master node" 
  → Call count_pods_on_node(node_name='k8s-master-001')
  → "There are X pods running on the master node."

User: "how many pods are on worker node" 
  → Call count_pods_on_node(node_name='k8s-worker-01')
  → "There are X pods running on the worker node."

User: "list the pods on master node" 
  → Call count_pods_on_node(node_name='k8s-master-001')
  → Extract pod names from the result and list them
  
User: "list the pods on worker node" 
  → Call count_pods_on_node(node_name='k8s-worker-01')
  → Extract pod names from the result and list them
User: "which node has more capacity" → 
  Step 1: Call describe_node with node_name='k8s-master-001'
  Step 2: Call describe_node with node_name='k8s-worker-01'
  Step 3: Compare CPU/memory capacity from both results
  Response: "Both nodes have the same capacity with 2 CPU cores and 4GB memory each." OR "The master node has more capacity..."
User: "are there taints on master node" → Call describe_node with node_name='k8s-master-001', then: "No, there are no taints on the master node." OR "Yes, the master node has taint: node-role.kubernetes.io/control-plane:NoSchedule"
"""
        
        # Check if we already have tool results and need to generate final answer
        has_tool_results = any(isinstance(m, ToolMessage) for m in messages)
        last_message = messages[-1]
        has_pending_tool_calls = hasattr(last_message, 'tool_calls') and last_message.tool_calls
        
        # If we have tool results but no pending tool calls, force a final answer
        if has_tool_results and not has_pending_tool_calls:
            # Add instruction to summarize
            messages_with_system = [SystemMessage(content=system_msg)] + messages + [
                HumanMessage(content="Provide a direct, concise answer to the user's question. Don't mention the tools or say 'based on the output'.")
            ]
            response = model_with_tools.invoke(messages_with_system)
        else:
            # Normal flow - add system message if not present
            if not messages or not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=system_msg)] + messages
            
            # Call model with tools
            response = model_with_tools.invoke(messages)
        
        return {"messages": [response]}
    
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
                tool_found = False
                for tool in tools:
                    if tool.name == tool_name:
                        tool_found = True
                        try:
                            # Use .invoke() for LangChain tools
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
                
                # If tool not found, return error message for this tool_call_id
                if not tool_found:
                    tool_results.append(
                        ToolMessage(
                            content=f"Tool '{tool_name}' not found",
                            tool_call_id=tool_call["id"]
                        )
                    )
        
        return {"messages": tool_results}
    
    # ========================================================================
    # BUILD LANGGRAPH WORKFLOW (Following Sample Pattern)
    # ========================================================================
    
    # Create the graph with recursion limit
    workflow = StateGraph(MessagesState)
    
    # Add nodes
    workflow.add_node("k8s_supervisor", k8s_supervisor_node)
    workflow.add_node("tools", tool_node)
    
    # Define the flow
    workflow.set_entry_point("k8s_supervisor")
    
    # Add conditional edge with better stopping logic
    def should_continue(state):
        messages = state["messages"]
        last_message = messages[-1]
        
        # Check if we have tool calls to execute
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            # Count how many times we've already called tools
            tool_call_count = sum(1 for m in messages if hasattr(m, 'tool_calls') and m.tool_calls)
            
            # Stop if we've tried too many times (agent is confused/looping)
            if tool_call_count > 3:
                return "__end__"
            
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
        
        # Get the last AI message with actual content
        from langchain_core.messages import AIMessage, ToolMessage
        for message in reversed(messages):
            # We want the last AIMessage that has text content (not just tool calls)
            if isinstance(message, AIMessage) and message.content and message.content.strip():
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
