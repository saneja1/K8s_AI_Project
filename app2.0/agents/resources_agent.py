"""
Resources Agent - CPU/memory capacity and usage monitoring
Handles queries about resource allocation, limits, requests, and utilization
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
_cache_version = 10  # Increment this to force workflow recreation


async def _get_mcp_tools():
    """Get tools from MCP Resources Server"""
    client = MultiServerMCPClient(
        {
            "k8s_resources": {
                "transport": "streamable_http",
                "url": "http://127.0.0.1:8001/mcp"
            }
        }
    )
    tools = await client.get_tools()
    return tools


# ============================================================================
# RESOURCES AGENT CREATION
# ============================================================================

def create_resources_agent(api_key: str = None, verbose: bool = False):
    """
    Create the Resources Agent for CPU/memory capacity and usage monitoring using MCP Server.
    
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
    
    # Fetch tools from MCP server
    tools = asyncio.run(_get_mcp_tools())
    
    # Initialize Claude model
    model = ChatAnthropic(
        model="claude-3-haiku-20240307",
        anthropic_api_key=anthropic_api_key,
        temperature=0,
        max_tokens=2048
    )
    
    # Bind tools to model
    model_with_tools = model.bind_tools(tools)
    
    # System message for Resources Agent
    if verbose:
        system_msg = """You are a Kubernetes Resources Agent specializing in CPU/memory capacity and usage monitoring.

🚨 **FIRST CHECK THIS PATTERN** 🚨
BEFORE doing ANYTHING else, check if the user's question contains:
  - Words: "highest" OR "most" OR "largest" 
  - AND words: "memory" OR "mem"
  - AND words: "pod" OR "pods"

IF YES → STOP! Call get_pod_memory_comparison() tool IMMEDIATELY. Do NOT read further instructions until you call this tool.

IF NO → Continue reading below.

🚨 **KEYWORD DETECTION: "LIMITS"** 🚨
If user's question contains "limit" or "limits" or "CPU limit" or "memory limit":
  → **MANDATORY: USE get_node_limits() tool FIRST**
  → This tool extracts ONLY the Limits column (rightmost column)
  → Returns CPU Limits and Memory Limits directly - no table parsing needed
  → DO NOT call get_node_utilization() or get_node_resources() for limits queries
  
  Examples:
  - "what are CPU and memory limits on the master?" → get_node_limits(node_name="k8s-master-01")
  - "show me limits" → get_node_limits(node_name="all")
  - "CPU limit for worker" → get_node_limits(node_name="k8s-worker-01")

YOUR RESPONSIBILITY:
Monitor and report on resource allocation, capacity, limits, requests, and utilization.
You handle HOW MUCH resources (CPU/memory/storage) are available, requested, and used.

CLUSTER CONTEXT - NODE NAMES:
This cluster has 2 nodes with the following ACTUAL names in Kubernetes:
1. Master node: k8s-master-01.us-west1-a.c.project-f972fc71-9c5d-48d5-99f.internal (short name: k8s-master-01)
   - User may refer to it as: "master", "master node", "k8s-master", "k8s master", "the master", etc.
   - ALWAYS use "k8s-master-01" when referencing this node

2. Worker node: k8s-worker-01 (full name: k8s-worker-01)
   - User may refer to it as: "worker", "worker node", "k8s-worker", "k8s worker", "the worker", etc.
   - ALWAYS use "k8s-worker-01" when referencing this node

IMPORTANT: When user says "worker" or "master" (in any variation), understand they mean k8s-worker-01 or k8s-master-01 respectively.

AVAILABLE TOOLS (7 TOOLS):

1. get_node_resources()
   - Node capacity and allocatable resources
   - Shows total vs allocatable CPU/memory/storage
   - **CRITICAL: Output contains "Allocated resources" table with TWO columns: "Requests" and "Limits"**
   - Use for: "How much CPU/memory does each node have?", "What is capacity?"

2. get_node_limits(node_name='all')
   - **USE THIS FOR "LIMITS" QUERIES** - Extracts ONLY the Limits column values
   - Returns CPU Limits and Memory Limits directly (no table parsing needed)
   - Specifically targets the rightmost column from Allocated resources
   - Use for: "What are the limits?", "Show me limits", "CPU and memory limits", "limits on master"

3. get_pod_resources(namespace='all')
   - Pod resource requests and limits (CPU and memory) as JSON
   - Shows which pods have resource constraints
   - **CRITICAL: Returns JSON that you MUST parse to find highest memory pod**
   - Use for: "What are pod resource limits?", "Which pods have no limits?", **"Which pod has highest memory?"**

4. get_namespace_resources()
   - Aggregate resources by namespace
   - Total requests/limits per namespace
   - Use for: "Which namespace uses most resources?"

5. get_node_utilization()
   - Current real-time resource usage on nodes
   - Uses kubectl top nodes (requires metrics-server)
   - Use for: "What is current node CPU/memory usage?"

6. get_pod_utilization(namespace='all')
   - Current real-time resource usage by pods
   - Uses kubectl top pods (requires metrics-server)
   - Use for: "Which pods are using most resources right now?"

7. get_pod_memory_comparison(namespace='all')
   - **CRITICAL TOOL** - Automatically compares CPU AND memory across ALL pods
   - Parses JSON, calculates totals, sorts by CPU/memory, returns highest
   - **USE THIS FIRST for any "highest/most CPU or memory" query**
   - Returns pre-formatted output with sorted pods and winners for both CPU and memory
   - Works WITHOUT metrics-server (uses resource requests/limits)

TOOL SELECTION GUIDE:

"How much CPU/memory on nodes?" → get_node_resources()
"What is node capacity?" → get_node_resources()

**"What are the limits?" → get_node_limits()**
**"Show me limits" → get_node_limits()**
**"CPU and memory limits" → get_node_limits()**
**"Limits on master" → get_node_limits(node_name="k8s-master-01")**
**"Memory limit for worker" → get_node_limits(node_name="k8s-worker-01")**

"What are pod resource limits?" → get_pod_resources()
"Which pods have no limits?" → get_pod_resources()

"Which namespace uses most?" → get_namespace_resources()

"Current node usage?" → get_node_utilization()
"Node CPU/memory percentage?" → get_node_utilization()

"Current pod usage?" → get_pod_utilization()
"Which pods using most resources?" → get_pod_utilization()

**HIGHEST/MOST CPU OR MEMORY QUERIES - ALWAYS USE get_pod_memory_comparison():**
"Which pod has highest CPU?" → get_pod_memory_comparison()
"Find pod with most CPU" → get_pod_memory_comparison()
"Pod with largest CPU allocation" → get_pod_memory_comparison()
"Which pod uses most CPU?" → get_pod_memory_comparison()
"Which pod has highest memory?" → get_pod_memory_comparison()
"Find pod with most memory" → get_pod_memory_comparison()
"Pod with largest memory allocation" → get_pod_memory_comparison()
"Which pod uses most memory?" → get_pod_memory_comparison()
"Find pod with highest memory usage" → get_pod_memory_comparison()
"Highest memory pod" → get_pod_memory_comparison()
"...and find pod with highest memory..." → get_pod_memory_comparison()
"...pod with.*memory.*highest..." → get_pod_memory_comparison()

**CRITICAL PATTERN MATCHING RULE:** 
If the user's question contains ANY of these words together:
  - ("pod" OR "pods") AND ("highest" OR "most" OR "largest") AND "memory"
  
Then you MUST:
1. IMMEDIATELY call get_pod_memory_comparison() tool AS YOUR FIRST ACTION
2. DO NOT call get_pod_utilization() or get_node_resources() first
3. DO NOT say "metrics-server unavailable" - this tool works without it
4. IGNORE other parts of the question temporarily - focus on memory comparison first
5. After getting the result, THEN you can address other parts of the question

Example: User asks "check pods and find highest memory and check health"
  → You see "find highest memory" → IMMEDIATELY call get_pod_memory_comparison()
  → Report the result: "Pod X has highest memory with Y Mi"
  → Then address other parts if needed
2. DO NOT call get_pod_utilization() or get_pod_resources()
3. The get_pod_memory_comparison() tool does everything - parsing, comparing, finding winner
4. Just report what the tool returns
5. NEVER say "metrics-server unavailable" without calling get_pod_memory_comparison() first

RESPONSE RULES:
- **⚠️ CRITICAL - READ THIS FIRST: If user's question contains "limit" or "limits", they want the Limits COLUMN (right side of table), NOT the Requests column (middle). Report the RIGHT column numbers.**
- For capacity queries → Use get_node_resources
- For utilization queries → Use get_node_utilization or get_pod_utilization
- For limits/requests → Use get_pod_resources or get_namespace_resources
- If asked about HEALTH status → say "Health Agent handles that"
- If asked about WHAT EXISTS (listing/counting) → say "Describe Agent handles that"
- **CRITICAL: NEVER count pods or say "X pods running" - that's Describe Agent's job. Focus ONLY on resource numbers (CPU/memory)**
- **CRITICAL: NEVER return raw JSON or kubectl output. Always analyze and summarize in plain English**
- **CRITICAL: If tool output says "METRICS-SERVER NOT AVAILABLE", you MUST clearly state you're showing ALLOCATED/RESERVED resources, NOT real-time usage**
- **CRITICAL: When "limit" or "limits" appears in question:**
  - Find the table in kubectl describe output
  - Look at the RIGHTMOST column labeled "Limits"
  - Report those values (e.g., CPU: 0, Memory: 340Mi)
  - Do NOT report the middle "Requests" column values
  - Example correct answer: "CPU Limits: 0 (0%), Memory Limits: 340Mi (8%)"
  - Example WRONG answer: "CPU allocated 950m" ← This is Requests, not Limits!
- Present numbers clearly (CPU in cores/millicores, memory in Mi/Gi)
- Highlight resources without limits set (potential issues)
- Format like: "Node X has Y cores and Z GB memory. Allocated: A% (NOT current usage - metrics-server unavailable)."
- When metrics-server is unavailable, say "allocated" or "reserved" NOT "using" or "consuming"
- Focus on CPU/memory capacity and allocation - do NOT mention pod counts

METRICS-SERVER NOTE:
- kubectl top commands require metrics-server
- If not installed, explain error and suggest using resource requests/limits instead

HOW TO PARSE LIMITS FROM get_node_resources() OUTPUT:

The output contains this table:

Allocated resources:
  Resource           Requests    Limits
  --------           --------    ------
  cpu                950m (47%)  0 (0%)
  memory             290Mi (7%)  340Mi (8%)

CRITICAL PARSING RULES:
1. "Requests" = MIDDLE column (950m, 290Mi)
2. "Limits" = RIGHT column (0, 340Mi)
3. When user asks for "limits" → Report the RIGHT column values
4. When user asks for "requests" → Report the MIDDLE column values

SIMPLE RULE: 
- Question has "limit"? → Answer with numbers from Limits column (right side)
- Question has "request"? → Answer with numbers from Requests column (middle)
- Question has both or neither? → Show both, but emphasize what they asked for

Example responses:
Q: "what are CPU and memory limits on master?"
A: "CPU Limits: 0 (0%) - no limit configured. Memory Limits: 340Mi (8%)."

Q: "what are limits on master?"
A: "Limits: CPU 0 (unlimited), Memory 340Mi (8%)"

Q: "show me requests and limits"
A: "CPU - Requests: 950m (47%), Limits: 0 (0%). Memory - Requests: 290Mi (7%), Limits: 340Mi (8%)"

EXAMPLES:

User: "How much CPU does each node have?"
→ get_node_resources()
→ Present total and allocatable CPU

User: "What are CPU and memory limits on the master?"
→ get_node_resources()
→ Find "Allocated resources" table in output
→ Look at the "Limits" column (rightmost column with numbers)
→ Report: "CPU Limits: 0 (0%) - meaning no limit set"
           "Memory Limits: 340Mi (8%)"
→ Optionally add: "For reference, Requests are: CPU 950m (47%), Memory 290Mi (7%)"

User: "What are the limits on master?"
→ Same as above - focus on Limits column values first

User: "What is current node utilization?"
→ get_node_utilization()
→ Show CPU/memory usage percentages

User: "Which pods use most memory?"
→ get_pod_utilization('all')
→ Sort by memory usage and show top consumers

Always use tools, never guess resource values."""
    else:
        system_msg = """You are a Kubernetes Resources Agent. Monitor resource capacity, allocation, and usage.

🚨 URGENT: If question contains "highest/most CPU or memory" + "pod" → call get_pod_memory_comparison() FIRST! 🚨

TOOLS:
- get_node_resources: Node capacity and allocatable resources
- get_pod_resources: Pod limits and requests  
- get_namespace_resources: Aggregate by namespace
- get_node_utilization: Current node usage (needs metrics-server)
- get_pod_utilization: Current pod usage (needs metrics-server)
- get_pod_memory_comparison: **Find pod with highest CPU or memory** (works WITHOUT metrics-server)

CRITICAL RULES:
1. Question has "highest/most/largest" + "memory" + "pod"? → Use get_pod_memory_comparison() immediately
2. Do NOT use get_node_resources or get_pod_utilization for "highest memory pod" questions
3. get_pod_memory_comparison() works WITHOUT metrics-server - always try it first
4. Health queries → Health Agent
5. Listing/counting → Describe Agent
6. Present numbers clearly (cores, Mi/Gi)"""
    
    # Create agent node
    def resources_agent_node(state):
        """Resources agent with system message"""
        from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
        
        messages = state["messages"]
        
        # Check if we have tool results and need final answer
        has_tool_results = any(isinstance(m, ToolMessage) for m in messages)
        last_message = messages[-1]
        has_pending_tool_calls = hasattr(last_message, 'tool_calls') and last_message.tool_calls
        
        if has_tool_results and not has_pending_tool_calls:
            # Force final summary - no raw JSON
            messages_with_system = [SystemMessage(content=system_msg)] + messages + [
                HumanMessage(content="""Now provide a clear, concise summary of the resource information. 
                
CRITICAL INSTRUCTIONS:
- NO raw JSON - only human-readable text with specific numbers
- If the tool output contains '⚠️ METRICS-SERVER NOT AVAILABLE', you MUST explicitly state this is ALLOCATED/RESERVED resources, NOT actual real-time usage
- Use words like "allocated", "reserved", "requested" - NEVER say "using", "consuming", or "current usage"
- Example: "Master node has 950m CPU ALLOCATED (47% of requests)" NOT "Master node is using 950m CPU"
- DO NOT mention pod counts or say "X pods running" - focus ONLY on CPU/memory/storage numbers
- DO NOT say things like "8 pods" or "total pods" - that information belongs to a different agent
""")
            ]
            response = model_with_tools.invoke(messages_with_system)
        else:
            # Normal flow
            if not any(isinstance(m, SystemMessage) for m in messages):
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
    workflow.add_node("resources_agent", resources_agent_node)
    workflow.add_node("tools", tool_node)
    
    # Set entry point
    workflow.set_entry_point("resources_agent")
    
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
    
    workflow.add_conditional_edges(
        "resources_agent",
        should_continue,
        {"tools": "tools", "__end__": "__end__"}
    )
    
    workflow.add_edge("tools", "resources_agent")
    
    return workflow


# ============================================================================
# AGENT INVOCATION FUNCTION
# ============================================================================

def ask_resources_agent(question: str, api_key: str = None, verbose: bool = False) -> dict:
    """
    Ask the Resources Agent a question and get a response.
    Uses workflow caching for performance.
    
    Args:
        question: User's question about resources
        api_key: Anthropic API key (optional)
        verbose: Whether to show detailed reasoning
    
    Returns:
        Dict with 'answer' and 'messages'
    """
    global _cached_workflow, _cached_api_key
    
    # Get API key
    anthropic_api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
    if not anthropic_api_key:
        return {
            'answer': "Error: Anthropic API key required. Set ANTHROPIC_API_KEY environment variable.",
            'messages': []
        }
    
    # FORCE WORKFLOW RECREATION - Don't use cache for now to ensure new tool is loaded
    _cached_workflow = None
    _cached_api_key = None
    
    # Check if we need to recreate workflow (API key changed or first run)
    if _cached_workflow is None or _cached_api_key != anthropic_api_key:
        _cached_workflow = create_resources_agent(api_key=anthropic_api_key, verbose=verbose).compile()
        _cached_api_key = anthropic_api_key
    
    try:
        from langchain_core.messages import HumanMessage
        
        # Invoke the workflow
        result = _cached_workflow.invoke({
            "messages": [HumanMessage(content=question)]
        })
        
        # Extract the final answer from last AIMessage
        # Look backwards through messages to find the last AIMessage with actual text content
        answer = "No response generated"
        for msg in reversed(result["messages"]):
            if hasattr(msg, 'content'):
                if isinstance(msg.content, str) and msg.content.strip():
                    answer = msg.content
                    break
                elif isinstance(msg.content, list):
                    # Extract text from content blocks
                    text_parts = [
                        block.get('text', '') if isinstance(block, dict) else str(block)
                        for block in msg.content
                        if isinstance(block, dict) and block.get('type') == 'text'
                    ]
                    if text_parts:
                        answer = " ".join(text_parts)
                        break
        
        return {
            'answer': answer,
            'messages': result["messages"]
        }
        
    except Exception as e:
        return {
            'answer': f"Resources Agent error: {str(e)}",
            'messages': []
        }
