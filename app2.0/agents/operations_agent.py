"""
Operations Agent for Kubernetes Operations
Handles write operations: scale, delete, restart, node maintenance
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
    """Get tools from MCP Operations Server"""
    client = MultiServerMCPClient(
        {
            "k8s_operations": {
                "transport": "streamable_http",
                "url": "http://127.0.0.1:8003/mcp"
            }
        }
    )
    tools = await client.get_tools()
    return tools


def create_operations_agent(api_key: str = None, verbose: bool = False):
    """
    Create an Operations Agent that handles K8s write operations using MCP Server.
    
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
    
    # Cache check
    global _cached_workflow, _cached_api_key
    if _cached_workflow and _cached_api_key == anthropic_api_key:
        return _cached_workflow
    
    # Initialize Claude model
    model = ChatAnthropic(
        model="claude-3-haiku-20240307",
        anthropic_api_key=anthropic_api_key,
        temperature=0,
        max_tokens=2048
    )
    
    # Get tools from MCP server
    tools = asyncio.run(_get_mcp_tools())
    
    # Bind tools to model
    model_with_tools = model.bind_tools(tools)
    
    # Create agent node function
    def operations_agent_node(state):
        """Operations agent node - handles write operations"""
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
        
        messages = state["messages"]
        
        # System prompt for operations agent
        system_msg = """You are a Kubernetes Operations Agent specializing in cluster write operations.

CRITICAL: You MUST use the available tools to perform operations. Always confirm actions before executing destructive operations.

🎯 YOUR RESPONSIBILITIES:
- Scale deployments up/down
- Restart deployments (rollout restart)
- Rollback deployments to previous/specific revision
- Delete pods (single, by status, by label)
- Node maintenance (cordon, uncordon, drain)
- Patch resources with JSON patches
- Create/delete namespaces

⚠️ SAFETY PROTOCOLS (CRITICAL):
1. **Confirmation Required**: For destructive operations (delete, drain), ALWAYS inform user about:
   - What will be deleted/affected
   - How many resources will be impacted
   - Potential consequences
   
2. **Dry Run First**: For scale/patch operations, suggest dry_run=True first to preview changes

3. **Bulk Operations**: When deleting multiple pods (by status/label):
   - Tools have built-in safety checks (>10 pods = warning)
   - Report exact count before deletion
   - List what will be deleted
   
4. **Protected Resources**: 
   - Never delete system namespaces (default, kube-system, etc.)
   - Tools have built-in protection for these

5. **Graceful Defaults**:
   - Default to soft delete (grace_period=30s) unless user says "force" or "immediately"
   - Default to ignore_daemonsets=True for drain operations
   - Always explain force vs graceful options

🔧 TOOL USAGE PATTERNS:

**Scaling**: scale_deployment_tool(name, namespace, replicas, dry_run)
- Example: Scale deployment "nginx" to 3 replicas
- Use dry_run=True to preview first

**Restarting**: restart_deployment_tool(name, namespace, dry_run)
- Example: Restart deployment to pick up config changes
- This triggers rolling update

**Rollback**: rollback_deployment_tool(name, namespace, revision=None, dry_run)
- revision=None → previous revision
- revision=2 → specific revision number
- Check status with get_deployment_rollout_status_tool() after

**Pod Deletion**:
- Single: delete_pod_tool(name, namespace, grace_period=30, force=False)
- By status: delete_pods_by_status_tool(status, namespace, force)
  - Status: Failed, Pending, Unknown, Error, CrashLoopBackOff
- By label: delete_pods_by_label_tool(label_selector, namespace, force)
  - Example: "app=nginx" or "env=dev,tier=frontend"

**Node Maintenance**:
- cordon_node_tool(node_name) → Mark unschedulable
- uncordon_node_tool(node_name) → Mark schedulable
- drain_node_tool(node_name, force, ignore_daemonsets, delete_emptydir_data)
  - Always cordon before drain
  - Uncordon after maintenance complete

**Resource Patching**: patch_resource_tool(resource_type, name, namespace, patch_json, dry_run)
- Example patch: '{"spec":{"replicas":5}}'
- Always use dry_run=True first

**Namespace**: 
- create_namespace_tool(name, dry_run)
- delete_namespace_tool(name, force) ← Use extreme caution!

📊 RESPONSE FORMAT:
1. **Action Summary**: What operation was performed
2. **Status**: Success/Failure with details
3. **Impact**: What changed (before → after)
4. **Next Steps**: Recommendations if any

🚨 ERROR HANDLING:
- If operation fails, explain why and suggest alternatives
- For permission errors, mention RBAC requirements
- For not found errors, suggest checking name/namespace

Remember: With great power comes great responsibility! Always prioritize cluster safety.
"""
        
        # Check if we have tool results and need final answer
        has_tool_results = any(isinstance(m, ToolMessage) for m in messages)
        last_message = messages[-1]
        has_pending_tool_calls = hasattr(last_message, 'tool_calls') and last_message.tool_calls
        
        if has_tool_results and not has_pending_tool_calls:
            # Force final answer
            messages_with_system = [SystemMessage(content=system_msg)] + messages + [
                HumanMessage(content="Provide a clear summary of the operation result.")
            ]
            response = model_with_tools.invoke(messages_with_system)
        else:
            # Normal flow - prepend system message if not already there
            if not messages or not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=system_msg)] + messages
            
            response = model_with_tools.invoke(messages)
        
        return {"messages": [response]}
    
    # Create tool execution node
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
    
    # Build the graph
    workflow = StateGraph(MessagesState)
    
    # Add nodes
    workflow.add_node("operations_agent", operations_agent_node)
    workflow.add_node("tools", tool_node)
    
    # Set entry point
    workflow.set_entry_point("operations_agent")
    
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
    
    workflow.add_conditional_edges("operations_agent", should_continue, {"tools": "tools", "__end__": "__end__"})
    workflow.add_edge("tools", "operations_agent")
    
    return workflow


def run_operations_agent(query: str, api_key: str = None) -> str:
    """
    Run the Operations Agent with a query.
    
    Args:
        query: User query about operations
        api_key: Optional Anthropic API key
        
    Returns:
        Agent's response as string
    """
    from langchain_core.messages import HumanMessage
    
    global _cached_workflow, _cached_api_key
    
    try:
        # Get or create cached workflow
        current_api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        
        # Only recreate workflow if API key changed or not cached
        if _cached_workflow is None or _cached_api_key != current_api_key:
            _cached_workflow = create_operations_agent(api_key=current_api_key).compile()
            _cached_api_key = current_api_key
        
        # Run agent
        result = _cached_workflow.invoke({
            "messages": [HumanMessage(content=query)]
        })
        
        # Extract final AI message
        final_message = result["messages"][-1]
        return final_message.content
        
    except Exception as e:
        return f"Error running Operations Agent: {str(e)}"


# Test function
if __name__ == "__main__":
    print("🔧 Testing Operations Agent...")
    print("=" * 60)
    
    # Test query (dry run to be safe)
    test_query = "Show me how to scale nginx deployment to 3 replicas with dry run first"
    
    print(f"\n📝 Query: {test_query}\n")
    
    try:
        result = run_operations_agent(test_query)
        print(f"✅ Result:\n{result}")
    except Exception as e:
        print(f"❌ Error: {e}")
