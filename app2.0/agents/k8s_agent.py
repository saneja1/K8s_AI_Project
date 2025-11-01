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
        Uses LLM to classify the query and delegate to appropriate agent.
        """
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        
        messages = state["messages"]
        
        # Get the user's question
        user_question = None
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_question = msg.content
                break
        
        if not user_question:
            return {"messages": [AIMessage(content="I didn't receive a question. Please ask me about your Kubernetes cluster.")]}
        
        # Routing logic: Classify which agent should handle this query
        routing_prompt = f"""Classify this Kubernetes query into ONE category:

Query: "{user_question}"

Categories:
1. HEALTH - cluster health, node status, pod counts, events, errors, warnings, ready state
2. RESOURCES - CPU, memory, disk, capacity, resource allocation, limits, requests
3. DESCRIBE - detailed info about specific pods, nodes, deployments, services
4. MONITOR - performance metrics, resource usage over time, trends
5. SECURITY - RBAC, roles, permissions, network policies, secrets
6. OPERATIONS - scaling, updates, rollouts, restarts, maintenance

Respond with ONLY the category name (e.g., "HEALTH" or "RESOURCES").
"""
        
        # Ask LLM to classify
        classification_response = model.invoke([HumanMessage(content=routing_prompt)])
        category = classification_response.content.strip().upper()
        
        # Route to appropriate agent
        if "HEALTH" in category:
            # Call Health Agent
            try:
                result = ask_health_agent(user_question, api_key=anthropic_api_key, verbose=verbose)
                answer = result.get('answer', 'No response from Health Agent')
                return {"messages": [AIMessage(content=answer)]}
            except Exception as e:
                return {"messages": [AIMessage(content=f"Error routing to Health Agent: {str(e)}")]}
        
        elif "RESOURCES" in category:
            return {"messages": [AIMessage(content="Resources Agent is not yet implemented. This would handle CPU/memory/capacity queries.")]}
        
        elif "DESCRIBE" in category:
            return {"messages": [AIMessage(content="Describe Agent is not yet implemented. This would handle detailed pod/node information queries.")]}
        
        elif "MONITOR" in category:
            return {"messages": [AIMessage(content="Monitor Agent is not yet implemented. This would handle performance metrics queries.")]}
        
        elif "SECURITY" in category:
            return {"messages": [AIMessage(content="Security Agent is not yet implemented. This would handle RBAC/security queries.")]}
        
        elif "OPERATIONS" in category:
            return {"messages": [AIMessage(content="Operations Agent is not yet implemented. This would handle scaling/updates queries.")]}
        
        else:
            return {"messages": [AIMessage(content=f"I couldn't classify your query (detected: {category}). Please try rephrasing your question about cluster health, resources, describe, monitor, security, or operations.")]}
    
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
