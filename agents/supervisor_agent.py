"""
Supervisor Agent - Kubernetes Multi-Agent System Coordinator

This is the main supervisor agent that manages all specialist agents and routes
user questions to the appropriate expert. It acts as the intelligent router and
synthesizes responses from multiple agents when needed.

Specialist Agents Managed:
1. Health Agent - Node and cluster health monitoring
2. Security Agent - Security policies, RBAC, and compliance
3. Resources Agent - CPU/memory usage monitoring and analysis
4. Monitor Agent - Logs, events, and troubleshooting
5. Describe-Get Agent - Resource listing and description
6. Operations Agent - Cluster modifications (delete, scale, create) WITH CONFIRMATIONS

The supervisor uses LangGraph's create_supervisor pattern to automatically
handle agent routing, state management, and response synthesis.
"""

from langgraph_supervisor import create_supervisor
from typing import Optional


def create_k8s_supervisor(
    llm_model,
    health_agent,
    security_agent,
    resources_agent,
    monitor_agent,
    describe_get_agent,
    operations_agent,
    verbose: bool = False
):
    """
    Create the Kubernetes Supervisor Agent that manages all specialist agents.
    
    The supervisor analyzes user questions and routes them to the appropriate
    specialist agent(s). It can call multiple agents sequentially for complex
    questions and synthesizes their responses into a coherent answer.
    
    Args:
        llm_model: The LLM model to use (ChatGoogleGenerativeAI, ChatOpenAI, etc.)
        health_agent: The health monitoring specialist agent
        security_agent: The security monitoring specialist agent
        resources_agent: The resource monitoring specialist agent
        monitor_agent: The logs/events monitoring specialist agent
        describe_get_agent: The resource listing/description specialist agent
        operations_agent: The cluster operations specialist agent (delete, scale, create)
        verbose: Whether to print routing decisions
    
    Returns:
        Compiled LangGraph workflow ready for execution
    
    Example Usage:
        >>> from langchain_google_genai import ChatGoogleGenerativeAI
        >>> from agents.health_agent import create_health_agent
        >>> from agents.monitor_agent import create_monitor_agent
        >>> from agents.operations_agent import create_operations_agent
        >>> # ... create other agents ...
        >>> 
        >>> llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0.2)
        >>> 
        >>> health = create_health_agent(llm)
        >>> monitor = create_monitor_agent(llm)
        >>> operations = create_operations_agent(llm)
        >>> # ... create other agents ...
        >>> 
        >>> supervisor = create_k8s_supervisor(llm, health, security, resources, monitor, describe_get, operations)
        >>> app = supervisor.compile()
        >>> 
        >>> result = app.invoke({
        >>>     "messages": [{"role": "user", "content": "Are all nodes healthy?"}]
        >>> })
    """
    
    workflow = create_supervisor(
        # List of all specialist agents the supervisor manages
        [
            health_agent,
            security_agent, 
            resources_agent,
            monitor_agent,
            describe_get_agent,
            operations_agent
        ],
        model=llm_model,
        prompt="""You are a Kubernetes cluster management supervisor coordinating a team of specialist agents.

Your team of experts:
1. **k8s_health_expert** - Node and cluster health monitoring
   - Use for: node health checks, taints, readiness, cluster-wide node status
   - Examples: "Are nodes healthy?", "What taints are on master?", "Check node status"

2. **k8s_security_expert** - Security monitoring, RBAC, and compliance
   - Use for: RBAC permissions, network policies, secrets listing, security compliance
   - Examples: "Check RBAC permissions", "List network policies", "Security audit", "Show secrets"

3. **k8s_resources_expert** - Resource usage monitoring and analysis
   - Use for: CPU/memory usage (kubectl top), resource quotas, capacity planning
   - Examples: "What's the CPU usage?", "Which pod uses most memory?", "Check quotas"

4. **k8s_monitor_expert** - Logs, events, and troubleshooting
   - Use for: pod logs, events, error analysis, troubleshooting, root cause analysis
   - Examples: "Show logs for nginx pod", "Why is pod crashing?", "Check pod events"

5. **k8s_describe_get_expert** - Resource listing and description
   - Use for: listing resources, describing objects, counting resources, metadata
   - Examples: "List all pods", "How many pods per namespace?", "Describe service X"

6. **k8s_operations_expert** - Cluster modifications and operations (WITH CONFIRMATIONS)
   - Use for: delete pods, scale deployments, restart deployments, create resources
   - Examples: "Delete failed pods", "Scale nginx to 5", "Create ConfigMap", "Restart deployment"
   - CRITICAL: This agent requires user confirmation for ALL destructive operations

ROUTING RULES (CRITICAL):
- **Health questions** → k8s_health_expert
- **Security questions** → k8s_security_expert
- **Resource usage (CPU/memory)** → k8s_resources_expert
- **Logs/events/troubleshooting** → k8s_monitor_expert
- **Listing/describing resources** → k8s_describe_get_expert
- **Delete/scale/create/restart** → k8s_operations_expert

COMPLEX WORKFLOWS (use multiple agents sequentially):
Example 1: "Show unhealthy pods and their logs"
  Step 1: describe_get_expert (find unhealthy pods)
  Step 2: monitor_expert (get logs from those pods)
  Step 3: Synthesize results

Example 2: "Find pods crashing and delete them"
  Step 1: monitor_expert (identify crashing pods)
  Step 2: operations_expert (delete with confirmation)
  Step 3: Report results

Example 3: "Why is nginx pod crashing? Create the missing ConfigMap."
  Step 1: monitor_expert (troubleshoot - finds missing ConfigMap)
  Step 2: operations_expert (create ConfigMap with user confirmation)
  Step 3: Confirm resolution

CRITICAL EXECUTION RULES:
- **Call agents ONE AT A TIME** - Never call multiple agents in parallel
- Wait for agent response before deciding next action
- For multi-step workflows, execute sequentially:
  1. Route to first agent
  2. Get response
  3. Decide next action based on response
  4. Route to next agent if needed
  5. Synthesize final answer

CONFIRMATION WORKFLOW (for operations_expert):
1. Operations agent returns confirmation request
2. You relay confirmation to user with details
3. Wait for user explicit confirmation ("yes delete", "yes scale", etc.)
4. If confirmed, operations agent executes
5. If cancelled, abort operation
6. Report final result

RESPONSE SYNTHESIS:
- Combine information from multiple agents seamlessly
- Present data in clear, organized format (headers, bullet points, tables)
- **ALWAYS SHOW ACTUAL TOOL OUTPUT** - Don't summarize logs/events, display them in code blocks
- Highlight critical issues (failures, warnings, errors)
- Provide actionable recommendations
- For operations, clearly state what changed
- When displaying logs, use markdown code blocks: ```text ... ```

ERROR HANDLING:
- If agent returns error, explain clearly to user
- Suggest alternatives or next steps
- Don't proceed with operations if validation fails
- For confirmation cancellations, acknowledge and don't retry

IMPORTANT NOTES:
- Operations agent ALWAYS requires user confirmation for destructive actions
- Monitor agent is READ-ONLY (diagnosis only, doesn't fix issues)
- Operations agent is WRITE (makes actual changes with confirmation)
- Never assume user consent - always wait for explicit confirmation

Remember: You are the intelligent router. Analyze the question, pick the right expert(s), 
execute sequentially, handle confirmations properly, and synthesize results into a helpful answer!"""
    )
    
    return workflow


def create_k8s_multiagent_system(llm_model, verbose: bool = False):
    """
    Convenience function to create the entire K8s multi-agent system.
    
    This function creates all 6 specialist agents and the supervisor in one call.
    
    Args:
        llm_model: The LLM model to use for all agents
        verbose: Whether to print agent reasoning
    
    Returns:
        Compiled supervisor workflow ready to use
    
    Example Usage:
        >>> from langchain_google_genai import ChatGoogleGenerativeAI
        >>> llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash-exp", temperature=0.2)
        >>> app = create_k8s_multiagent_system(llm)
        >>> 
        >>> result = app.invoke({
        >>>     "messages": [{"role": "user", "content": "Check cluster health"}]
        >>> })
        >>> 
        >>> for msg in result["messages"]:
        >>>     msg.pretty_print()
    """
    from agents.health_agent import create_health_agent
    from agents.security_agent import create_security_agent
    from agents.resources_agent import create_resources_agent
    from agents.monitor_agent import create_monitor_agent
    from agents.describe_get_agent import create_describe_get_agent
    from agents.operations_agent import create_operations_agent
    
    # Create all 6 specialist agents
    health_agent = create_health_agent(llm_model, verbose=verbose)
    security_agent = create_security_agent(llm_model, verbose=verbose)
    resources_agent = create_resources_agent(llm_model, verbose=verbose)
    monitor_agent = create_monitor_agent(llm_model, verbose=verbose)
    describe_get_agent = create_describe_get_agent(llm_model, verbose=verbose)
    operations_agent = create_operations_agent(llm_model, verbose=verbose)
    
    # Create supervisor
    workflow = create_k8s_supervisor(
        llm_model=llm_model,
        health_agent=health_agent,
        security_agent=security_agent,
        resources_agent=resources_agent,
        monitor_agent=monitor_agent,
        describe_get_agent=describe_get_agent,
        operations_agent=operations_agent,
        verbose=verbose
    )
    
    # Compile and return
    return workflow.compile()
