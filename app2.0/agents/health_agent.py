"""
Health Agent - Monitors cluster health and status
Handles queries about node health, cluster events, and overall cluster status
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


async def _get_mcp_tools():
    """Get tools from MCP Health Server"""
    client = MultiServerMCPClient(
        {
            "k8s_health": {
                "transport": "streamable_http",
                "url": "http://127.0.0.1:8000/mcp"
            }
        }
    )
    tools = await client.get_tools()
    return tools


def create_health_agent(api_key: str = None, verbose: bool = False):
    """
    Create a Health Agent that monitors cluster health using MCP Server.
    
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
    def health_agent_node(state):
        """Health agent node - monitors cluster health"""
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
        
        messages = state["messages"]
        
        # System prompt for health agent
        system_msg = """You are a Kubernetes Health Agent specializing in cluster health monitoring.

CRITICAL: You MUST use the available tools to answer questions. Never make assumptions or provide generic responses without calling tools first.

YOUR RESPONSIBILITY:
Monitor and report on NODE HEALTH and CLUSTER EVENTS only. 
Do NOT handle pod counting, pod listing, or resource capacity questions.

AVAILABLE TOOLS (ALWAYS USE THESE):
- get_cluster_nodes: Show all nodes with their status (Ready/NotReady), roles, age, version
- describe_node: Get detailed node information including conditions (MemoryPressure, DiskPressure, PIDPressure, Ready), capacity, and allocatable resources
- get_cluster_events: Show recent cluster events (warnings, errors, failures)

MANDATORY TOOL USAGE RULES:
- "Is my cluster healthy?" → MUST call get_cluster_nodes AND get_cluster_events
- "How many nodes?" → MUST call get_cluster_nodes
- "Node conditions?" → MUST call describe_node
- "Any errors?" → MUST call get_cluster_events
- "List conditions" → MUST call describe_node
- ALWAYS call tools before answering. NEVER respond without tool results.

RESPONSE FORMAT FOR CONDITIONS:
When user asks for "node conditions", "detailed conditions", or "what are the conditions", you MUST:
1. Call describe_node tool
2. COPY THE EXACT TOOL OUTPUT IN YOUR RESPONSE - DO NOT PARAPHRASE OR SUMMARIZE
3. The tool returns data in this format which you MUST preserve:
   node-name:
     Condition = Status (Reason: X | Message: Y)
     Condition = Status (Reason: X | Message: Y)
     ...
4. After showing the raw output, you can add a brief summary like "All nodes are healthy" or "Node X has issues"
5. CRITICAL: When user says "detailed", "show", "list", "what are" - they want to SEE the actual data, not just hear "everything is fine"

Example response format:
"Here are the detailed node conditions:

k8s-master-001:
  NetworkUnavailable = False (Reason: FlannelIsUp | Message: Flannel is running on this node)
  MemoryPressure = False (Reason: KubeletHasSufficientMemory | Message: kubelet has sufficient memory available)
  DiskPressure = False (Reason: KubeletHasNoDiskPressure | Message: kubelet has no disk pressure)
  PIDPressure = False (Reason: KubeletHasSufficientPID | Message: kubelet has sufficient PID available)
  Ready = True (Reason: KubeletReady | Message: kubelet is posting ready status)

k8s-worker-01:
  NetworkUnavailable = False (Reason: FlannelIsUp | Message: Flannel is running on this node)
  MemoryPressure = False (Reason: KubeletHasSufficientMemory | Message: kubelet has sufficient memory available)
  DiskPressure = False (Reason: KubeletHasNoDiskPressure | Message: kubelet has no disk pressure)
  PIDPressure = False (Reason: KubeletHasSufficientPID | Message: kubelet has sufficient PID available)
  Ready = True (Reason: KubeletReady | Message: kubelet is posting ready status)

All nodes are in healthy state."

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
  → Example output format:
    "Found 2 nodes in the cluster:
    
    k8s-master-001:
      NetworkUnavailable = False (Reason: FlannelIsUp | Message: Flannel is running on this node)
      MemoryPressure = False (Reason: KubeletHasSufficientMemory | Message: kubelet has sufficient memory available)
      DiskPressure = False (Reason: KubeletHasNoDiskPressure | Message: kubelet has no disk pressure)
      PIDPressure = False (Reason: KubeletHasSufficientPID | Message: kubelet has sufficient PID available)
      Ready = True (Reason: KubeletReady | Message: kubelet is posting ready status)
    
    k8s-worker-01:
      NetworkUnavailable = False (Reason: FlannelIsUp | Message: Flannel is running on this node)
      MemoryPressure = False (Reason: KubeletHasSufficientMemory | Message: kubelet has sufficient memory available)
      DiskPressure = False (Reason: KubeletHasNoDiskPressure | Message: kubelet has no disk pressure)
      PIDPressure = False (Reason: KubeletHasSufficientPID | Message: kubelet has sufficient PID available)
      Ready = True (Reason: KubeletReady | Message: kubelet is posting ready status)"

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
        tool_outputs = []
        
        from langchain_core.messages import AIMessage, ToolMessage
        
        # Collect tool outputs for detailed queries
        for message in messages:
            if isinstance(message, ToolMessage) and message.content:
                tool_outputs.append(str(message.content))
        
        # Get the final AI response
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content:
                # Handle both string and list content types
                if isinstance(message.content, str) and message.content.strip():
                    final_answer = message.content
                    break
                elif isinstance(message, list) and len(message.content) > 0:
                    # Extract text from content blocks
                    text_parts = []
                    for block in message.content:
                        if isinstance(block, dict) and 'text' in block:
                            text_parts.append(block['text'])
                        elif hasattr(block, 'text'):
                            text_parts.append(block.text)
                    if text_parts:
                        final_answer = '\n'.join(text_parts)
                        break
        
        # If user asked for "detailed" or "show" or "list" conditions, prepend tool output
        detail_keywords = ['detailed', 'detail', 'show', 'list', 'what are', 'conditions']
        if any(keyword in question.lower() for keyword in detail_keywords) and tool_outputs:
            # Check if it's a describe_node query by looking for condition-related content
            for tool_output in tool_outputs:
                if 'NetworkUnavailable' in tool_output or 'MemoryPressure' in tool_output:
                    final_answer = f"**Detailed Node Conditions:**\n\n{tool_output}\n\n**Summary:** {final_answer}"
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
