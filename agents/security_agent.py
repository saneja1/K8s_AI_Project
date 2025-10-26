"""
Security Agent - Kubernetes Security Monitoring

This agent specializes in security-related monitoring including RBAC, network policies,
secrets, and security best practices. It reports to the supervisor agent.

Responsibilities:
- Check RBAC permissions and role bindings
- Monitor network policies and security groups
- List and validate secrets (without exposing values)
- Security compliance and best practice checks

NOTE: Security tools are placeholder stubs - implement actual tools in utils/langchain_tools.py
"""

from langgraph.prebuilt import create_react_agent
# MOVED INSIDE FUNCTION: from agents.tools import SECURITY_TOOLS


def create_security_agent(llm_model, verbose: bool = False):
    """
    Create the Kubernetes Security Monitoring Agent.
    
    This agent will handle security-related queries once security tools are implemented.
    Currently acts as placeholder for future security features.
    
    Args:
        llm_model: The LLM model to use (ChatGoogleGenerativeAI, ChatOpenAI, etc.)
        verbose: Whether to print agent reasoning steps
    
    Returns:
        ReactAgent specialized in security monitoring
    
    Example Usage:
        >>> from langchain_google_genai import ChatGoogleGenerativeAI
        >>> llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp")
        >>> security_agent = create_security_agent(llm)
    """
    
    # Lazy import to avoid circular dependency
    from agents.tools import SECURITY_TOOLS
    
    # Note: SECURITY_TOOLS is currently empty - this is a placeholder agent
    agent = create_react_agent(
        model=llm_model,
        tools=SECURITY_TOOLS if SECURITY_TOOLS else [],  # Handle empty tool list
        name="k8s_security_expert",
        prompt="""You are a Kubernetes security expert specializing in cluster security monitoring.

Your responsibilities:
- Check RBAC (Role-Based Access Control) permissions and role bindings
- Monitor network policies and pod security policies
- Review secret configurations (without exposing sensitive data)
- Identify security vulnerabilities and compliance issues

Available tools:
1. check_rbac_permissions(user_or_serviceaccount, namespace) - Check permissions
2. list_secrets_and_configmaps(namespace) - List WITHOUT showing values
3. check_network_policies(namespace) - List network policies
4. execute_kubectl(command, namespace) - Run kubectl for security checks
   Examples: "get rolebindings -A", "auth can-i --list", "get podsecuritypolicies"

CRITICAL RULES:
- Always use ONE tool at a time
- NEVER expose secret values - list_secrets_and_configmaps masks sensitive data
- Recommend security best practices

CRITICAL RULES:
- Always use ONE tool at a time (never call multiple tools simultaneously)
- NEVER expose secret values or sensitive data in responses
- Provide clear security recommendations and risk assessments
- Highlight any security misconfigurations or vulnerabilities

IMPORTANT: You ONLY handle security-related questions. For other questions:
- Node health → Transfer to health_expert
- Resource usage → Transfer to resources_expert  
- Pod logs → Transfer to monitor_expert
- Listing resources → Transfer to describe_get_expert

NOTE: Currently security tools are not implemented. If asked about security:
1. Acknowledge the security question
2. Explain that security monitoring tools need to be implemented
3. Suggest what security checks would be performed
4. Transfer back to supervisor for alternative approaches

Always be proactive - don't ask for permission, just execute!"""
    )
    
    return agent
