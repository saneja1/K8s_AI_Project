"""
Health Agent - Kubernetes Node and Cluster Health Monitoring

This agent specializes in checking node health, taints, conditions, and overall
cluster health. It reports to the supervisor agent.

Responsibilities:
- Check individual node health (taints, conditions, status)
- Check overall cluster health (all nodes overview)
- Monitor node readiness and resource allocation
- Detect unhealthy nodes or taints blocking scheduling
"""

from langgraph.prebuilt import create_react_agent


def create_health_agent(llm_model, verbose: bool = False):
    """
    Create the Kubernetes Health Monitoring Agent.
    
    This agent uses check_node_health and check_cluster_health tools to monitor
    the health status of nodes and the overall cluster.
    
    Args:
        llm_model: The LLM model to use (ChatGoogleGenerativeAI, ChatOpenAI, etc.)
        verbose: Whether to print agent reasoning steps
    
    Returns:
        ReactAgent specialized in health monitoring
    
    Example Usage:
        >>> from langchain_google_genai import ChatGoogleGenerativeAI
        >>> llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp")
        >>> health_agent = create_health_agent(llm)
    """
    
    # Lazy import to avoid circular dependency
    from agents.tools import HEALTH_TOOLS
    
    agent = create_react_agent(
        model=llm_model,
        tools=HEALTH_TOOLS,
        name="k8s_health_expert",
        prompt="""You are a Kubernetes health monitoring expert specializing in node and cluster health.

Your responsibilities:
- Check node health including taints, conditions (Ready, MemoryPressure, DiskPressure, etc.)
- Monitor overall cluster health and node status
- Identify unhealthy nodes or nodes with taints that block pod scheduling
- Report on node readiness and resource allocation issues

Available tools:
1. check_node_health(name) - Check specific node with conditions and taints
2. check_cluster_health() - Get overview of all nodes
3. execute_kubectl(command, namespace) - Run any kubectl command for health checks
   Examples: "get nodes -o json", "get componentstatuses", "get --raw /healthz"

CRITICAL RULES:
- Always use ONE tool at a time (never call multiple tools simultaneously)
- Use check_node_health() for specific node health checks
- Use check_cluster_health() for cluster-wide node overview
- **ALWAYS SHOW THE ACTUAL KUBECTL OUTPUT** - Display real node data in code blocks
- Provide clear, actionable health status reports
- Highlight any warnings (taints, NotReady status, conditions)

RESPONSE FORMAT:
Always show the actual tool output in a code block:
```
[Real kubectl/health check output here]
```
Then provide analysis/summary.

IMPORTANT: You ONLY handle health-related questions. For other questions:
- Pod logs/events → Transfer to monitor_expert
- Resource usage (CPU/memory) → Transfer to resources_expert
- Listing resources → Transfer to describe_get_expert

Always be proactive - don't ask for permission to check health, just do it!"""
    )
    
    return agent
