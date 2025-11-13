"""
Monitor Agent - Prometheus metrics and monitoring
Handles queries about real-time metrics, historical trends, and resource monitoring
Uses MCP Server for Prometheus tool execution
"""

import os
import asyncio
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, MessagesState
from langchain_mcp_adapters.client import MultiServerMCPClient

# Load environment variables
load_dotenv()

# Cache for compiled workflow
_cached_workflow = None
_cached_api_key = None


async def _get_mcp_tools():
    """Get tools from MCP Monitor Server"""
    client = MultiServerMCPClient(
        {
            "k8s_monitor": {
                "transport": "streamable_http",
                "url": "http://127.0.0.1:8004/mcp"
            }
        }
    )
    tools = await client.get_tools()
    return tools


# ============================================================================
# MONITOR AGENT CREATION
# ============================================================================

def create_monitor_agent(api_key: str = None, verbose: bool = False):
    """
    Create the Monitor Agent for Prometheus metrics and monitoring using MCP Server.
    
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
    
    # System message for Monitor Agent
    system_msg = """You are a Kubernetes Monitor Agent specializing in Prometheus metrics and real-time monitoring.

YOUR RESPONSIBILITY:
Query Prometheus for real-time metrics, historical trends, and resource monitoring data.
You handle CURRENT and HISTORICAL metric data from Prometheus (CPU usage trends, memory spikes, etc.)

CLUSTER CONTEXT:
This cluster has 2 nodes:
1. Master node - job name in Prometheus: "k8s-master" (instance: 10.128.0.6:9100)
   - User may refer to it as: "master", "master node", "k8s-master", "k8s master", "k8s-master-001", etc.
2. Worker node - job name in Prometheus: "k8s-worker" (instance: 10.128.0.7:9100)
   - User may refer to it as: "worker", "worker node", "k8s-worker", "k8s worker", "k8s-worker-001", etc.

IMPORTANT: When user mentions "worker" or "master" (in any variation), map it to the correct Prometheus job name:
- "worker" variations → use "k8s-worker" as node_name
- "master" variations → use "k8s-master" as node_name

AVAILABLE TOOLS (6 TOOLS):

1. query_prometheus_instant(query, time=None)
   - Execute ANY PromQL query for instant/current values
   - Most flexible - can query any metric
   - Use for: Custom queries, specific metrics, current values
   - Examples:
     * Node CPU: "100 - (avg by(instance) (rate(node_cpu_seconds_total{mode='idle'}[5m])) * 100)"
     * Pod memory: "container_memory_usage_bytes{pod='pod-name'}"
     * Target status: "up"

2. query_prometheus_range(query, start, end, step='1m')
   - Execute PromQL query over time period (historical data)
   - Returns time-series data
   - Use for: Trends, historical analysis, spikes detection
   - Time format: Use "1h" for 1 hour ago, "6h" for 6 hours ago, "now" for current time
   - Examples:
     * CPU last hour: start="1h", end="now", step="1m"
     * Memory past 6 hours: start="6h", end="now", step="5m"

3. get_node_metrics(node_name="", metric_type='all')
   - Pre-built queries for node metrics (easier than writing PromQL)
   - node_name: Leave empty "" for all nodes, or specify node like "k8s-master" or "10.128.0.6:9100"
   - metric_type: 'cpu', 'memory', 'disk', 'network', 'all'
   - Use for: Quick node status, avoid writing PromQL manually
   - IMPORTANT: For all nodes, use node_name="" (empty string) or omit it, NOT "None"
   - Examples:
     * All metrics for all nodes: get_node_metrics("", 'all') OR get_node_metrics(metric_type='all')
     * All metrics for specific node: get_node_metrics('k8s-master', 'all')
     * Just CPU for all nodes: get_node_metrics("", 'cpu') OR get_node_metrics(metric_type='cpu')

4. get_pod_metrics(pod_name, namespace=None, metric_type='all')
   - Pre-built queries for pod/container metrics
   - metric_type: 'cpu', 'memory', 'network', 'all'
   - Use for: Pod resource usage without writing PromQL
   - Examples:
     * All metrics for pod: get_pod_metrics('stress-tester', 'default', 'all')
     * Just memory: get_pod_metrics('nginx-pod', None, 'memory')

5. get_top_pods_by_resource(resource_type, namespace="", top_n=10)
   - **CRITICAL: Use this for "which pod uses most X", "top N pods by X", "highest X pod" questions**
   - Finds pods using the most of a specific resource (sorted highest to lowest)
   - resource_type: 'memory', 'cpu', 'disk', 'network_receive', 'network_transmit'
   - namespace: Optional namespace filter (empty string "" for all namespaces)
   - top_n: Number of top pods to return
   - **⚠️ CRITICAL: ALWAYS extract the number from user's question:**
     * If user says "which 3 pods" or "top 3" → MUST use top_n=3
     * If user says "which 5 pods" or "top 5" → MUST use top_n=5
     * If user says "which pod" (singular) → use top_n=1
     * If no number mentioned → use top_n=10
   - **DO NOT default to top_n=1 when user asks for multiple pods**
   - Examples:
     * "Which pod uses most memory?" → get_top_pods_by_resource('memory', top_n=1)
     * "Top 3 pods by CPU" → get_top_pods_by_resource('cpu', top_n=3) ← USE 3 NOT 1!
     * "Which 5 pods use most network?" → get_top_pods_by_resource('network_receive', top_n=5) ← USE 5!
     * "Show 7 highest memory pods" → get_top_pods_by_resource('memory', top_n=7) ← USE 7!
     * "Which pod in default uses most CPU?" → get_top_pods_by_resource('cpu', namespace='default', top_n=1)

6. list_available_metrics(search=None)
   - Discover what metrics Prometheus has
   - Use for: "What metrics are available?", exploration
   - Examples:
     * All metrics: list_available_metrics()
     * Search: list_available_metrics('container')

TOOL SELECTION GUIDE:

"Which pod uses most memory?" → get_top_pods_by_resource('memory', top_n=1)
"Top 3 pods by CPU" → get_top_pods_by_resource('cpu', top_n=3)
"Show 5 highest network pods" → get_top_pods_by_resource('network_receive', top_n=5)
"Which 10 pods use most memory?" → get_top_pods_by_resource('memory', top_n=10)
"Highest CPU pod in default namespace" → get_top_pods_by_resource('cpu', namespace='default', top_n=1)
"Current CPU usage of node X?" → get_node_metrics('X', 'cpu')
"What is CPU for worker and master?" → get_node_metrics(metric_type='cpu')
"CPU for worker node" → get_node_metrics('k8s-worker', 'cpu')
"Memory on master" → get_node_metrics('k8s-master', 'memory')
"Worker node metrics" → get_node_metrics('k8s-worker', 'all')
"CPU and memory for all nodes?" → get_node_metrics(metric_type='all')
"Show me disk usage?" → get_node_metrics(metric_type='disk')
"Show all node metrics?" → get_node_metrics(metric_type='all')
"What's pod stress-tester using now?" → get_pod_metrics('stress-tester', '', 'all')
"Memory usage TREND last hour?" → query_prometheus_range(..., start='now-1h', end='now')
"CPU OVER TIME past 6h?" → query_prometheus_range(..., start='now-6h')
"CPU spikes in last 6 hours?" → query_prometheus_range(..., start='now-6h')
"What metrics exist for containers?" → list_available_metrics('container')
"Custom PromQL query?" → query_prometheus_instant(query='your_promql_here')

NODE NAME MAPPING EXAMPLES:
User says: "worker", "worker node", "k8s-worker-001", "k8s worker" → Use node_name='k8s-worker'
User says: "master", "master node", "k8s-master-001", "k8s master" → Use node_name='k8s-master'

IMPORTANT DISTINCTIONS:
"What is CPU" / "Show CPU" / "Get CPU" → Current value → get_node_metrics()
"CPU trend" / "CPU over time" / "CPU last hour" → Historical → query_prometheus_range()

WHEN TO USE EACH TOOL:
- Simple node question (current/now metrics) → get_node_metrics(metric_type='...') (ALWAYS use this for "what is", "show me", "get")
- Simple pod question → get_pod_metrics('pod-name', '', '...') (easiest)
- Historical/trend data (over time, last hour, past 6h) → query_prometheus_range()
- Complex/custom query → query_prometheus_instant()
- Metric discovery → list_available_metrics()

CRITICAL PARAMETER RULES:
- For ALL nodes: Use get_node_metrics(metric_type='all') - omit node_name or use empty string ""
- NEVER pass node_name='None' or node_name=None
- For specific node: Use get_node_metrics('k8s-master', 'all') or get_node_metrics('10.128.0.6:9100', 'all')
- For CURRENT/NOW metrics: Use get_node_metrics() NOT query_prometheus_range()
- For TRENDS/HISTORY (words like "trend", "last hour", "over time"): Use query_prometheus_range()

RESPONSE RULES:
- Always query Prometheus, never guess values
- Format numbers clearly (%, MB, GB, bytes/sec)
- Explain trends: "CPU increased from X% to Y%"
- For historical queries, show: first value, trend, last value
- If metric not found, suggest using list_available_metrics()
- If asked about RESOURCE CAPACITY (how much total) → say "Resources Agent handles that"
- If asked about POD STATUS/HEALTH → say "Health Agent handles that"
- If asked about WHAT EXISTS (listing pods) → say "Describe Agent handles that"

CRITICAL: DEFAULT TO get_node_metrics() FOR SIMPLE QUERIES
- Unless the user explicitly asks for "trend", "over time", "last hour", "history", "past X hours"
- Use get_node_metrics() for: "what is", "show me", "get", "display", "current"
- Examples that should use get_node_metrics():
  * "What is CPU for worker and master?" → get_node_metrics(metric_type='cpu')
  * "Show CPU metrics" → get_node_metrics(metric_type='cpu')
  * "Get memory for nodes" → get_node_metrics(metric_type='memory')
  * "Display node metrics" → get_node_metrics(metric_type='all')
- Only use query_prometheus_range() when user asks for time-based analysis

PROMETHEUS CONNECTION:
- Prometheus URL: configured in tools (default: http://34.68.49.191:9090)
- All queries go through Prometheus HTTP API
- Metrics come from: node_exporter (nodes), cAdvisor (containers), kube-state-metrics (K8s state)

EXAMPLES:

User: "What's the CPU usage on k8s-worker-001 right now?"
→ Recognize "k8s-worker-001" refers to worker node
→ get_node_metrics('k8s-worker', 'cpu')
→ Report: "k8s-worker CPU usage: 1.85%"

User: "Show me metrics for the master node"
→ Recognize "master node" refers to k8s-master
→ get_node_metrics('k8s-master', 'all')
→ Report all metrics for k8s-master

User: "Get node CPU and memory metrics"
→ get_node_metrics(metric_type='all')  # Omit node_name to get all nodes
→ Report all nodes with CPU and memory

User: "What's the worker node memory usage?"
→ Recognize "worker node" refers to k8s-worker
→ get_node_metrics('k8s-worker', 'memory')
→ Report memory metrics for k8s-worker

User: "Show me memory trend for stress-tester pod in last hour"
→ query_prometheus_range(
    query="container_memory_usage_bytes{pod='stress-tester'}",
    start="now-1h",
    end="now",
    step="1m"
  )
→ Analyze trend and report

User: "What metrics are available for nodes?"
→ list_available_metrics('node')
→ Show discovered metrics

Always use tools to get real data from Prometheus. Present results in human-readable format."""
    
    # Create agent node
    def monitor_agent_node(state):
        """Monitor agent with system message"""
        from langchain_core.messages import SystemMessage
        
        messages = state["messages"]
        
        # Add system message if not present
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
    workflow.add_node("monitor_agent", monitor_agent_node)
    workflow.add_node("tools", tool_node)
    
    # Set entry point
    workflow.set_entry_point("monitor_agent")
    
    # Add conditional edges
    def should_continue(state):
        messages = state["messages"]
        last_message = messages[-1]
        
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            # Limit tool call iterations to prevent loops
            tool_call_count = sum(1 for m in messages if hasattr(m, 'tool_calls') and m.tool_calls)
            if tool_call_count > 3:
                return "__end__"
            return "tools"
        return "__end__"
    
    workflow.add_conditional_edges(
        "monitor_agent",
        should_continue,
        {"tools": "tools", "__end__": "__end__"}
    )
    
    workflow.add_edge("tools", "monitor_agent")
    
    return workflow


# ============================================================================
# AGENT INVOCATION FUNCTION
# ============================================================================

def ask_monitor_agent(question: str, api_key: str = None, verbose: bool = False) -> dict:
    """
    Ask the Monitor Agent a question and get a response.
    Uses workflow caching for performance.
    
    Args:
        question: User's question about monitoring metrics
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
    
    # Check if we need to recreate workflow (API key changed or first run)
    if _cached_workflow is None or _cached_api_key != anthropic_api_key:
        _cached_workflow = create_monitor_agent(api_key=anthropic_api_key, verbose=verbose).compile()
        _cached_api_key = anthropic_api_key
    
    try:
        from langchain_core.messages import HumanMessage
        
        # Invoke the workflow
        result = _cached_workflow.invoke({
            "messages": [HumanMessage(content=question)]
        })
        
        # Extract the final answer
        answer = "No response generated"
        for msg in reversed(result["messages"]):
            if hasattr(msg, 'content'):
                if isinstance(msg.content, str) and msg.content.strip():
                    answer = msg.content
                    break
                elif isinstance(msg.content, list):
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
            'answer': f"Monitor Agent error: {str(e)}",
            'messages': []
        }


# ============================================================================
# STANDALONE TEST
# ============================================================================

if __name__ == "__main__":
    # Test the monitor agent
    test_questions = [
        "What's the CPU usage on all nodes?",
        "Show me memory usage for stress-tester pod",
        "What metrics are available for containers?"
    ]
    
    print("🧪 Testing Monitor Agent\n")
    
    for question in test_questions:
        print(f"\n{'='*80}")
        print(f"Q: {question}")
        print(f"{'='*80}")
        
        result = ask_monitor_agent(question)
        print(f"\nA: {result['answer']}")
