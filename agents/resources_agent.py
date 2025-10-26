"""
Resources Agent - Kubernetes Resource Usage Monitoring

This agent specializes in monitoring CPU, memory, and resource usage across
pods and nodes. It reports to the supervisor agent.

Responsibilities:
- Monitor pod resource usage (CPU, memory via kubectl top)
- Monitor node resource usage (CPU%, memory% via kubectl top)
- Check resource quotas and limits
- Identify resource-constrained pods or nodes

NOTE: Resource monitoring tools are placeholder stubs - implement actual tools in utils/langchain_tools.py
"""

from langgraph.prebuilt import create_react_agent
# MOVED INSIDE FUNCTION: from agents.tools import RESOURCES_TOOLS


def create_resources_agent(llm_model, verbose: bool = False):
    """
    Create the Kubernetes Resource Monitoring Agent.
    
    This agent will handle resource usage queries once monitoring tools are implemented.
    Currently acts as placeholder for future resource monitoring features.
    
    Args:
        llm_model: The LLM model to use (ChatGoogleGenerativeAI, ChatOpenAI, etc.)
        verbose: Whether to print agent reasoning steps
    
    Returns:
        ReactAgent specialized in resource monitoring
    
    Example Usage:
        >>> from langchain_google_genai import ChatGoogleGenerativeAI
        >>> llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp")
        >>> resources_agent = create_resources_agent(llm)
    """
    
    # Lazy import to avoid circular dependency
    from agents.tools import RESOURCES_TOOLS
    
    # Note: RESOURCES_TOOLS is currently empty - this is a placeholder agent
    agent = create_react_agent(
        model=llm_model,
        tools=RESOURCES_TOOLS if RESOURCES_TOOLS else [],  # Handle empty tool list
        name="k8s_resources_expert",
        prompt="""You are a Kubernetes resource monitoring expert specializing in CPU and memory usage analysis.

Your responsibilities:
- Monitor pod resource usage (CPU, memory) using kubectl top pods
- Monitor node resource usage (CPU%, memory%) using kubectl top nodes
- Check resource quotas and limit ranges for namespaces
- Identify pods consuming excessive resources
- Analyze resource efficiency (requested vs actual usage)

Available tools:
1. get_resource_usage(resource_type, namespace) - Get kubectl top for nodes/pods
2. get_resource_quotas(namespace) - Check namespace quotas
3. analyze_resource_requests(namespace) - Compare requested vs actual usage
4. execute_kubectl(command, namespace) - Run kubectl for resource checks
   Examples: "top pods --containers", "describe quota", "get limitranges -A"

CRITICAL RULES:
- Always use ONE tool at a time
- Detect nodes approaching resource limits
- Analyze resource allocation and recommend optimizations

CRITICAL RULES:
- Always use ONE tool at a time (never call multiple tools simultaneously)
- Use get_pod_resource_usage() for pod-level CPU/memory metrics
- Use get_node_resource_usage() for node-level resource metrics
- Provide clear resource usage reports with percentages and trends
- Highlight any pods or nodes with high resource consumption

IMPORTANT: You ONLY handle resource usage questions (CPU, memory). For other questions:
- Node health/taints → Transfer to health_expert
- Pod logs → Transfer to monitor_expert
- Listing resources → Transfer to describe_get_expert
- Security policies → Transfer to security_expert

NOTE: Currently resource monitoring tools are not implemented. If asked about resources:
1. Acknowledge the resource monitoring question
2. Explain that kubectl top tools need to be implemented
3. Suggest checking pod describe output for resource requests/limits
4. Transfer to describe_get_expert to show resource specifications

Always be proactive - don't ask for permission, just execute!"""
    )
    
    return agent
