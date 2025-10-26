"""
Kubernetes Multi-Agent System

This package provides a supervisor-based multi-agent architecture for managing
Kubernetes clusters. The system includes:

- Supervisor Agent: Routes questions to specialist agents
- Health Agent: Node and cluster health monitoring
- Security Agent: Security policies and RBAC (placeholder)
- Resources Agent: CPU/memory monitoring (placeholder)
- Monitor Agent: Logs, events, and troubleshooting
- Describe-Get Agent: Resource listing and description

Quick Start:
    >>> from langchain_google_genai import ChatGoogleGenerativeAI
    >>> from agents import create_k8s_multiagent_system
    >>> 
    >>> llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0.2)
    >>> app = create_k8s_multiagent_system(llm)
    >>> 
    >>> result = app.invoke({
    >>>     "messages": [{"role": "user", "content": "Check cluster health"}]
    >>> })
    >>> 
    >>> # Print conversation flow
    >>> for msg in result["messages"]:
    >>>     msg.pretty_print()
    >>> 
    >>> # Get final answer
    >>> print(result["messages"][-1].content)

Advanced Usage (Individual Agents):
    >>> from agents.supervisor_agent import create_k8s_supervisor
    >>> from agents.health_agent import create_health_agent
    >>> from agents.monitor_agent import create_monitor_agent
    >>> # ... import other agents as needed
    >>> 
    >>> llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp")
    >>> 
    >>> health = create_health_agent(llm)
    >>> monitor = create_monitor_agent(llm)
    >>> # ... create other agents
    >>> 
    >>> supervisor = create_k8s_supervisor(llm, health, security, resources, monitor, describe_get)
    >>> app = supervisor.compile()
"""

# Main entry point - DO NOT import at module level to avoid circular dependency
# Import these directly when needed:
# from agents.supervisor_agent import create_k8s_multiagent_system, create_k8s_supervisor

# Individual agent creators - Also avoid module-level import
# These should be imported directly when creating agents:
# from agents.health_agent import create_health_agent
# from agents.security_agent import create_security_agent
# from agents.resources_agent import create_resources_agent
# from agents.monitor_agent import create_monitor_agent
# from agents.describe_get_agent import create_describe_get_agent

# Tool organization - COMMENTED OUT to avoid circular import
# Tools are imported lazily inside each agent creation function
# from agents.tools import (
#     HEALTH_TOOLS,
#     SECURITY_TOOLS,
#     RESOURCES_TOOLS,
#     MONITOR_TOOLS,
#     DESCRIBE_GET_TOOLS,
#     ALL_TOOLS
# )


__all__ = [
    # Main factory function
    'create_k8s_multiagent_system',
    
    # Supervisor
    'create_k8s_supervisor',
    
    # Individual agent creators
    'create_health_agent',
    'create_security_agent',
    'create_resources_agent',
    'create_monitor_agent',
    'create_describe_get_agent',
    
    # Tool collections - Not exported to avoid circular import
    # 'HEALTH_TOOLS',
    # 'SECURITY_TOOLS',
    # 'RESOURCES_TOOLS',
    # 'MONITOR_TOOLS',
    # 'DESCRIBE_GET_TOOLS',
    # 'ALL_TOOLS',
]


# Package metadata
__version__ = '1.0.0'
__author__ = 'K8s AI Project'
__description__ = 'Multi-agent system for Kubernetes cluster management'
