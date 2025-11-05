"""
Kubernetes Supervisor Agent using LangGraph
Supervisor that delegates to specialized agents (no direct tools)
"""

import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, MessagesState

# Tools are now in specialized agents, not here
# from .k8s_tools import (...)

# Import specialized agents
from .health_agent import ask_health_agent
from .describe_agent import ask_describe_agent
from .resources_agent import ask_resources_agent

# Load environment variables
load_dotenv()


# ============================================================================
# KUBERNETES SUPERVISOR AGENT (LangGraph Manual Build - New Version)
# ============================================================================

def create_k8s_supervisor_agent(api_key: str = None, verbose: bool = False):
    """
    Create a single Kubernetes supervisor agent using LangGraph StateGraph.
    This is the equivalent of create_react_agent but built manually for the new LangGraph version.
    
    Args:
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        verbose: Whether to show agent reasoning steps
    
    Returns:
        Compiled LangGraph workflow (equivalent to sample pattern)
    """
    # Get API key
    anthropic_api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
    if not anthropic_api_key:
        raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY environment variable.")
    
    # Initialize Claude model (optimized for speed)
    model = ChatAnthropic(
        model="claude-3-haiku-20240307",  # Haiku is fastest Claude model
        anthropic_api_key=anthropic_api_key,
        temperature=0,  # Deterministic for faster responses
        max_tokens=1024  # Reduced from 2048 for faster generation
    )
    
    # ========================================================================
    # TOOLS NOW IN SPECIALIZED AGENTS
    # ========================================================================
    
    # Tools are no longer bound to supervisor
    # tools = [get_cluster_pods, get_cluster_nodes, describe_node, describe_pod, get_pod_logs, get_cluster_events, count_pods_on_node, count_resources]
    
    # No tool binding - supervisor will route to specialized agents instead
    # model_with_tools = model.bind_tools(tools)
    
    # ========================================================================
    # CREATE ROUTING SUPERVISOR NODE
    # ========================================================================
    
    def k8s_supervisor_node(state):
        """
        Kubernetes supervisor that routes queries to specialized agents.
        Uses LLM to classify the query and delegate to appropriate agent(s).
        Can execute multiple agents in parallel if query requires multiple perspectives.
        """
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        import asyncio
        import concurrent.futures
        
        messages = state["messages"]
        
        # Get the user's question
        user_question = None
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_question = msg.content
                break
        
        if not user_question:
            return {"messages": [AIMessage(content="I didn't receive a question. Please ask me about your Kubernetes cluster.")]}
        
        # Routing logic: Classify which agent(s) should handle this query
        routing_prompt = f"""Classify this Kubernetes query into ONE OR MORE categories (can select multiple):

Query: "{user_question}"

Categories:
1. HEALTH - node health status, cluster events, errors, warnings (node-level only)
2. RESOURCES - CPU, memory, disk capacity, resource allocation, limits, requests, utilization
3. DESCRIBE - list/count/describe specific K8s resources (pods, services, deployments, namespaces, etc.)
4. MONITOR - performance metrics, resource usage over time, trends
5. SECURITY - RBAC, roles, permissions, network policies, secrets
6. OPERATIONS - scaling, updates, rollouts, restarts, maintenance

IMPORTANT ROUTING RULES:
- "cluster status" → HEALTH,RESOURCES (never DESCRIBE unless asking to list specific resources)
- "cluster health" or "is cluster healthy" → HEALTH (ONLY)
- "resources" (without "list" or "show me all") → RESOURCES (ONLY)

- "CPU/memory/disk capacity" → RESOURCES (ONLY)
- "resource limits/requests/allocation" → RESOURCES (ONLY)
- "pod resource" or "node resource" → RESOURCES (ONLY)
- "resource usage/utilization" → RESOURCES (ONLY)

- "list pods/services/deployments" → DESCRIBE (ONLY)
- "how many pods/services" → DESCRIBE (ONLY)
- "describe pod/service/deployment" → DESCRIBE (ONLY)
- "what namespaces exist" → DESCRIBE (ONLY)
- "show me all X" → DESCRIBE (where X is specific resource type like pods, not general status)

- "show me all pods AND their health" → DESCRIBE,HEALTH (parallel)
- "list nodes with their status" → DESCRIBE,HEALTH (parallel)
- "node capacity AND health" → RESOURCES,HEALTH (parallel)

CRITICAL: Respond with ONLY comma-separated category names, nothing else.
Examples:
- "HEALTH"
- "DESCRIBE"
- "RESOURCES,HEALTH"
- "DESCRIBE,HEALTH"
- "RESOURCES,HEALTH"

Your response (category names only):"""
        
        # Ask LLM to classify
        classification_response = model.invoke([HumanMessage(content=routing_prompt)])
        categories_str = classification_response.content.strip().upper()
        categories = [cat.strip() for cat in categories_str.split(',')]
        
        # Collect agents to execute
        agents_to_run = []
        
        if "HEALTH" in categories:
            agents_to_run.append(("Health Agent", lambda: ask_health_agent(user_question, api_key=anthropic_api_key, verbose=verbose)))
        
        if "DESCRIBE" in categories:
            agents_to_run.append(("Describe Agent", lambda: ask_describe_agent(user_question, api_key=anthropic_api_key, verbose=verbose)))
        
        if "RESOURCES" in categories:
            agents_to_run.append(("Resources Agent", lambda: ask_resources_agent(user_question, api_key=anthropic_api_key, verbose=verbose)))
        
        # Check for unimplemented agents
        unimplemented = []
        if "MONITOR" in categories:
            unimplemented.append("Monitor Agent (performance metrics)")
        if "SECURITY" in categories:
            unimplemented.append("Security Agent (RBAC/security)")
        if "OPERATIONS" in categories:
            unimplemented.append("Operations Agent (scaling/updates)")
        
        # Execute agents (parallel if multiple)
        if not agents_to_run and not unimplemented:
            return {"messages": [AIMessage(content=f"I couldn't classify your query (detected: {categories_str}). Please try rephrasing your question about cluster health, resources, describe, monitor, security, or operations.")]}
        
        results = []
        
        if len(agents_to_run) == 1:
            # Single agent - execute directly
            agent_name, agent_func = agents_to_run[0]
            try:
                result = agent_func()
                answer = result.get('answer', f'No response from {agent_name}')
                results.append(f"**{agent_name}:**\n{answer}")
            except Exception as e:
                results.append(f"**{agent_name} Error:** {str(e)}")
        
        elif len(agents_to_run) > 1:
            # Multiple agents - execute SEQUENTIALLY to prevent output mixing
            # (Parallel execution causes subprocess stdout leakage)
            for agent_name, agent_func in agents_to_run:
                try:
                    result = agent_func()
                    answer = result.get('answer', f'No response from {agent_name}')
                    results.append(f"**{agent_name}:**\n{answer}")
                except Exception as e:
                    results.append(f"**{agent_name} Error:** {str(e)}")
        
        # Add unimplemented agents notice
        if unimplemented:
            results.append(f"\n**Not yet implemented:** {', '.join(unimplemented)}")
        
        # If multiple agents responded, synthesize the answers
        if len(agents_to_run) > 1:
            from langchain_anthropic import ChatAnthropic
            
            # Combine all agent responses
            combined_responses = "\n\n".join(results)
            
            # Create synthesis prompt
            synthesis_prompt = f"""You are a Kubernetes cluster assistant. Multiple specialized agents have provided information about different aspects of the cluster.

User's original question: "{user_question}"

Agent responses:
{combined_responses}

Synthesize these responses into a single, coherent answer that:
1. Directly answers the user's question
2. Combines insights from all agents
3. Is concise and well-organized
4. Removes redundancy between agent answers
5. Presents a unified view of the cluster state

Provide ONLY the synthesized answer, without mentioning the agents or showing their individual responses."""

            try:
                synthesizer = ChatAnthropic(
                    model="claude-3-haiku-20240307",
                    api_key=anthropic_api_key,
                    temperature=0
                )
                
                synthesis_result = synthesizer.invoke(synthesis_prompt)
                final_answer = synthesis_result.content
            except Exception as e:
                # Fallback to simple concatenation if synthesis fails
                final_answer = combined_responses
        else:
            # Single agent - no synthesis needed
            final_answer = "\n\n".join(results)
        
        return {"messages": [AIMessage(content=final_answer)]}
    
    # ========================================================================
    # TOOL NODE REMOVED - Tools now in specialized agents
    # ========================================================================
    
    # def tool_node(state):
    #     """Execute tools and return results"""
    #     ... (removed - supervisor no longer executes tools directly)
    
    # ========================================================================
    # BUILD LANGGRAPH WORKFLOW (Following Sample Pattern)
    # ========================================================================
    
    # Create the graph with recursion limit
    workflow = StateGraph(MessagesState)
    
    # Add only supervisor node (no tools node)
    workflow.add_node("k8s_supervisor", k8s_supervisor_node)
    # workflow.add_node("tools", tool_node)  # Removed - tools in specialized agents
    
    # Define the flow - supervisor directly to END (no tool execution)
    workflow.set_entry_point("k8s_supervisor")
    
    # Simplified flow - no conditional edges (supervisor will route to specialized agents later)
    # def should_continue(state):
    #     ... (removed - no tools to execute)
    
    # Direct edge to end
    workflow.add_edge("k8s_supervisor", "__end__")
    # workflow.add_conditional_edges("k8s_supervisor", should_continue, {"tools": "tools", "__end__": "__end__"})  # Removed
    # workflow.add_edge("tools", "k8s_supervisor")  # Removed
    
    return workflow


# ============================================================================
# AGENT INVOCATION FUNCTION
# ============================================================================

def ask_k8s_agent(question: str, api_key: str = None, verbose: bool = False) -> dict:
    """
    Ask the Kubernetes supervisor agent a question and get a response.
    Uses LangGraph StateGraph pattern (equivalent to sample's create_react_agent approach).
    
    Args:
        question: User's question about the K8s cluster
        api_key: Anthropic API key (optional)
        verbose: Whether to show detailed agent reasoning
    
    Returns:
        Dict with 'answer' and 'messages' (full conversation)
    """
    try:
        # Create supervisor workflow (manual replacement for create_react_agent)
        workflow = create_k8s_supervisor_agent(api_key=api_key, verbose=verbose)
        
        # Compile the workflow (same as sample pattern)
        app = workflow.compile()
        
        # Execute with user question (following sample pattern exactly)
        from langchain_core.messages import HumanMessage
        
        result = app.invoke({
            "messages": [
                HumanMessage(content=question)
            ]
        })
        
        # Extract final answer (last AI message from supervisor)
        messages = result.get("messages", [])
        final_answer = "No response generated."
        
        # Get the last AI message with actual content
        from langchain_core.messages import AIMessage, ToolMessage
        for message in reversed(messages):
            # We want the last AIMessage that has text content (not just tool calls)
            if isinstance(message, AIMessage) and message.content and message.content.strip():
                final_answer = message.content
                break
        
        return {
            "answer": final_answer,
            "messages": messages
        }
        
    except Exception as e:
        # Fallback to direct tool execution if supervisor fails
        return _fallback_direct_response(question, str(e))


# ============================================================================
# FALLBACK FUNCTION (Direct Tool Execution)
# ============================================================================

def _fallback_direct_response(question: str, error_msg: str) -> dict:
    """
    Fallback function that directly executes appropriate tools if multi-agent system fails.
    """
    question_lower = question.lower()
    
    try:
        if any(keyword in question_lower for keyword in ['pod', 'pods', 'list', 'show', 'get']):
            pod_data = get_cluster_pods("all")
            return {
                "answer": f"**ALL PODS** (via fallback):\n\n```\n{pod_data}\n```\n\n*Note: Used fallback mode due to: {error_msg}*",
                "messages": []
            }
        elif any(keyword in question_lower for keyword in ['node', 'nodes']):
            node_data = get_cluster_nodes()
            return {
                "answer": f"**NODES** (via fallback):\n\n```\n{node_data}\n```\n\n*Note: Used fallback mode due to: {error_msg}*",
                "messages": []
            }
        elif 'event' in question_lower:
            event_data = get_cluster_events()
            return {
                "answer": f"**EVENTS** (via fallback):\n\n```\n{event_data}\n```\n\n*Note: Used fallback mode due to: {error_msg}*",
                "messages": []
            }
        else:
            return {
                "answer": f"I encountered an error with the multi-agent system: {error_msg}\n\nPlease try asking about:\n• **'list all pods'**\n• **'show nodes'**\n• **'show events'**",
                "messages": []
            }
    except Exception as fallback_error:
        return {
            "answer": f"Both multi-agent and fallback systems failed. Please check your cluster connection.\n\nErrors:\n- Multi-agent: {error_msg}\n- Fallback: {str(fallback_error)}",
            "messages": []
        }


# ============================================================================
# EXAMPLE USAGE (for testing)
# ============================================================================

if __name__ == "__main__":
    # Example: Test Kubernetes supervisor agent
    print("Testing Kubernetes Supervisor Agent (LangGraph)...")
    
    # Test 1: Pod listing
    response = ask_k8s_agent("List all pods in the cluster")
    print("\n=== POD LISTING TEST ===")
    print(response["answer"][:200] + "..." if len(response["answer"]) > 200 else response["answer"])
    
    # Test 2: Node status
    response = ask_k8s_agent("Show me cluster nodes")
    print("\n=== NODE STATUS TEST ===")
    print(response["answer"][:200] + "..." if len(response["answer"]) > 200 else response["answer"])
    
    # Test 3: Cluster events
    response = ask_k8s_agent("What are recent cluster events?")
    print("\n=== CLUSTER EVENTS TEST ===") 
    print(response["answer"][:200] + "..." if len(response["answer"]) > 200 else response["answer"])
    
    print("\nKubernetes supervisor agent test completed!")
