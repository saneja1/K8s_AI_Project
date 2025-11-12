"""
Describe Agent - Information retrieval and resource inspection
Handles queries about listing, describing, and counting K8s resources
Uses MCP Server for tool execution
"""

import os
import asyncio
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, MessagesState
from langchain_mcp_adapters.client import MultiServerMCPClient

# Load environment variables
load_dotenv()

# Cache for compiled workflow to avoid recreating on every query
_cached_workflow = None
_cached_api_key = None


async def _get_mcp_tools():
    """Get tools from MCP Describe Server"""
    client = MultiServerMCPClient(
        {
            "k8s_describe": {
                "transport": "streamable_http",
                "url": "http://127.0.0.1:8001/mcp"
            }
        }
    )
    tools = await client.get_tools()
    return tools


# ============================================================================
# DESCRIBE AGENT CREATION
# ============================================================================

def create_describe_agent(api_key: str = None, verbose: bool = False):
    """
    Create the Describe Agent for resource information retrieval using MCP Server.
    
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
    
    # Get tools from MCP server (this is async, so we need to handle it)
    tools = asyncio.run(_get_mcp_tools())
    
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
- For "list" or "what are" queries: ALWAYS show actual resource NAMES, not summaries
- For "running pods" queries: List ALL pod names with their status
- Highlight important fields (status, replicas, conditions)
- If asked about resource HEALTH → say "Health Agent handles that"
- If asked about resource USAGE/CAPACITY (CPU/memory) → say "Resources Agent handles that"
- For large outputs (>50 items), show all names in a compact list
- Always use the generic tools, not specific ones

RAW OUTPUT RULES:
- If user asks for "raw yaml", "yaml definition", "yaml output", or "show yaml":
  → Use get_resource_yaml tool and return the EXACT output WITHOUT interpretation
  → DO NOT summarize, DO NOT explain, just return the raw YAML as-is
  → Start response with: "Here is the raw YAML:" followed by the tool output
- Only interpret/summarize when user asks for "describe", "explain", or "what is"

EXAMPLES:

User: "list all pods"
→ list_k8s_resources('pods', 'all')
→ Show ALL pod names with namespace and status

User: "what are running pods in cluster"
→ list_k8s_resources('pods', 'all')
→ Filter for Running status and list ALL pod names
→ Format: "Pod Name (Namespace): Status"

User: "how many pods are on k8s-master-001"
→ count_k8s_resources('pods', 'all', 'node', 'k8s-master-001')
→ Report count with pod names

User: "describe the nginx pod in default namespace"
→ describe_k8s_resource('pod', 'nginx', 'default')
→ Present key information

User: "show me all services"
→ list_k8s_resources('services', 'all')
→ List ALL service names

User: "what namespaces exist"
→ list_k8s_resources('namespaces')
→ List all namespace names

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
    
    # Create tool node with async support for MCP tools
    def tool_node(state):
        """Execute MCP tools (async) and return results"""
        from langchain_core.messages import ToolMessage
        import asyncio
        
        messages = state["messages"]
        last_message = messages[-1]
        
        async def execute_tools_async():
            tool_results = []
            
            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                for tool_call in last_message.tool_calls:
                    tool_name = tool_call["name"]
                    tool_args = tool_call.get("args", {})
                    
                    # Find and execute the MCP tool
                    tool_found = False
                    for tool in tools:
                        if tool.name == tool_name:
                            tool_found = True
                            try:
                                # MCP tools require async invocation
                                result = await tool.ainvoke(tool_args)
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
            
            return tool_results
        
        # Run async execution
        tool_results = asyncio.run(execute_tools_async())
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
    Uses cached workflow for better performance.
    
    Args:
        question: Question about cluster resources
        api_key: Anthropic API key (optional)
        verbose: Show reasoning steps (optional)
    
    Returns:
        dict with 'answer' and 'messages' keys
    """
    global _cached_workflow, _cached_api_key
    
    try:
        # Get or create cached workflow
        current_api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        
        # Only recreate workflow if API key changed or not cached
        if _cached_workflow is None or _cached_api_key != current_api_key:
            _cached_workflow = create_describe_agent(api_key=current_api_key, verbose=verbose).compile()
            _cached_api_key = current_api_key
        
        app = _cached_workflow
        app = _cached_workflow
        
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
