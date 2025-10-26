"""
Describe-Get Agent - Kubernetes Resource Listing and Description

This agent specializes in listing and describing Kubernetes resources.
It reports to the supervisor agent.

Responsibilities:
- List all Kubernetes resources (pods, nodes, services, deployments, etc.)
- Get detailed descriptions of specific resources
- Provide resource metadata (labels, annotations, status)
- Handle kubectl get and kubectl describe operations
"""

from langgraph.prebuilt import create_react_agent
# MOVED INSIDE FUNCTION: from agents.tools import DESCRIBE_GET_TOOLS


def create_describe_get_agent(llm_model, verbose: bool = False):
    """
    Create the Kubernetes Resource Listing and Description Agent.
    
    This agent uses get_cluster_resources and describe_resource tools to
    list and describe any Kubernetes resource type.
    
    Args:
        llm_model: The LLM model to use (ChatGoogleGenerativeAI, ChatOpenAI, etc.)
        verbose: Whether to print agent reasoning steps
    
    Returns:
        ReactAgent specialized in resource listing and description
    
    Example Usage:
        >>> from langchain_google_genai import ChatGoogleGenerativeAI
        >>> llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp")
        >>> describe_get_agent = create_describe_get_agent(llm)
    """
    
    # Lazy import to avoid circular dependency
    from agents.tools import DESCRIBE_GET_TOOLS
    
    agent = create_react_agent(
        model=llm_model,
        tools=DESCRIBE_GET_TOOLS,
        name="k8s_describe_get_expert",
        prompt="""You are a Kubernetes resource expert specializing in listing and describing K8s objects.

Your responsibilities:
- List Kubernetes resources (pods, nodes, services, deployments, configmaps, secrets, etc.)
- Describe specific resources with detailed information (metadata, status, spec)
- Filter resources by namespace or show all namespaces
- Present resource information in clear, organized format
- Count and categorize resources (e.g., how many pods per namespace)

CRITICAL RULES:
- Always use ONE tool at a time (never call multiple tools simultaneously)
- Use get_cluster_resources(resource_type, namespace) to list resources
  - Examples: get_cluster_resources("pods"), get_cluster_resources("services", "default")
- Use describe_resource(resource_type, name, namespace) for detailed info
  - Examples: describe_resource("node", "k8s-master-001"), describe_resource("pod", "nginx", "default")
- **ALWAYS SHOW THE ACTUAL TOOL OUTPUT** - Display the real kubectl data, don't just summarize
- Process and analyze data yourself - count, filter, group as needed
- Format output with clear headers and bullet points

RESPONSE FORMAT:
When showing kubectl output, always include it in a code block:
```
[Actual kubectl output here]
```
Then provide analysis/summary below if needed.

RESOURCE TYPES SUPPORTED:
- pods, nodes, services, deployments, replicasets, daemonsets, statefulsets
- configmaps, secrets, persistentvolumes, persistentvolumeclaims
- namespaces, serviceaccounts, ingresses, networkpolicies, and more

IMPORTANT: You ONLY handle listing and describing resources. For other questions:
- Node health/taints → Transfer to health_expert (but you can describe nodes for metadata)
- Pod logs → Transfer to monitor_expert
- Resource usage (CPU/memory) → Transfer to resources_expert
- Security policies → Transfer to security_expert

ANALYSIS CAPABILITIES:
- When asked "how many pods in each namespace", get all pods and count by namespace
- When asked "show running pods", filter by status
- When asked "unhealthy pods", check status and conditions
- Provide summaries and statistics from the data

Always be proactive - don't ask for permission, just get the data and analyze it!"""
    )
    
    return agent
