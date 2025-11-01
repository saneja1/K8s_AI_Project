"""
Health Agent - Monitors cluster health and status
Handles queries about node health, cluster events, and overall cluster status
"""

import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, MessagesState

# Import health-related tools
try:
    # Try relative import (when used as module)
    from .k8s_tools import (
        get_cluster_nodes,
        get_cluster_events
        # count_resources removed - belongs to Describe/Operations agents
    )
except ImportError:
    # Fallback to absolute import (when run directly)
    from k8s_tools import (
        get_cluster_nodes,
        get_cluster_events
        # count_resources removed - belongs to Describe/Operations agents
    )

# Load environment variables
load_dotenv()


def create_health_agent(api_key: str = None, verbose: bool = False):
    """
    Create a Health Agent that monitors cluster health.
    
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
    
    # Initialize Claude model
    model = ChatAnthropic(
        model="claude-3-haiku-20240307",
        anthropic_api_key=anthropic_api_key,
        temperature=0,
        max_tokens=1024
    )
    
    # Define tools for health monitoring (focused on node health and events only)
    tools = [get_cluster_nodes, get_cluster_events]
    
    # Bind tools to model
    model_with_tools = model.bind_tools(tools)
    
    # Create agent node function
    def health_agent_node(state):
        """Health agent node - monitors cluster health"""
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
        
        messages = state["messages"]
        
        # System prompt for health agent
        system_msg = """You are a Kubernetes Health Agent specializing in cluster health monitoring.

YOUR RESPONSIBILITY:
Monitor and report on NODE HEALTH and CLUSTER EVENTS only. 
Do NOT handle pod counting, pod listing, or resource capacity questions.

AVAILABLE TOOLS:
- get_cluster_nodes: Show all nodes with their status (Ready/NotReady), roles, age, version
- get_cluster_events: Show recent cluster events (warnings, errors, failures)

WHEN TO USE EACH TOOL:
- "Is my cluster healthy?" → use get_cluster_nodes to check node status
- "Are nodes ready?" → use get_cluster_nodes
- "Any errors or warnings?" → use get_cluster_events
- "What's the status of nodes?" → use get_cluster_nodes

RESPONSE RULES:
- Focus ONLY on node health and cluster events
- If asked about pods, CPU, memory, or resource capacity → say "That's handled by another agent"
- Be direct and clear about health status
- If nodes are NotReady, say so explicitly
- If get_cluster_events returns empty or "No resources found" → that means NO events (cluster is quiet/healthy)
- If there are warnings/errors in events, highlight them
- For "is cluster healthy" questions:
  * Check node status (all should be Ready)
  * Check recent events (should not have critical errors)
- When asked to "show events" and there are none → say "No recent events found. The cluster is operating normally."

EXAMPLES:
User: "Are all nodes healthy?"
  → Call get_cluster_nodes
  → Check STATUS column
  → Answer: "Yes, all nodes are Ready" OR "No, node X is NotReady"

User: "Any recent problems?"
  → Call get_cluster_events
  → Look for Warning/Error types
  → Summarize issues found

User: "How many nodes are ready?"
  → Call count_resources with resource_type='nodes', filter_by='status', filter_value='Ready'
  → Answer with the count
"""
        
        # Check if we have tool results and need final answer
        has_tool_results = any(isinstance(m, ToolMessage) for m in messages)
        last_message = messages[-1]
        has_pending_tool_calls = hasattr(last_message, 'tool_calls') and last_message.tool_calls
        
        if has_tool_results and not has_pending_tool_calls:
            # Force final answer
            messages_with_system = [SystemMessage(content=system_msg)] + messages + [
                HumanMessage(content="Provide a direct, concise answer about cluster health.")
            ]
            response = model_with_tools.invoke(messages_with_system)
        else:
            # Normal flow
            if not messages or not isinstance(messages[0], SystemMessage):
                messages = [SystemMessage(content=system_msg)] + messages
            
            response = model_with_tools.invoke(messages)
        
        return {"messages": [response]}
    
    # Create tool node
    def tool_node(state):
        """Execute tools and return results"""
        from langchain_core.messages import ToolMessage
        
        messages = state["messages"]
        last_message = messages[-1]
        
        tool_results = []
        
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call.get("args", {})
                
                # Find and execute the tool
                tool_found = False
                for tool in tools:
                    if tool.name == tool_name:
                        tool_found = True
                        try:
                            result = tool.invoke(tool_args)
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
        
        return {"messages": tool_results}
    
    # Build workflow
    workflow = StateGraph(MessagesState)
    
    # Add nodes
    workflow.add_node("health_agent", health_agent_node)
    workflow.add_node("tools", tool_node)
    
    # Set entry point
    workflow.set_entry_point("health_agent")
    
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
    
    workflow.add_conditional_edges("health_agent", should_continue, {"tools": "tools", "__end__": "__end__"})
    workflow.add_edge("tools", "health_agent")
    
    return workflow


def ask_health_agent(question: str, api_key: str = None, verbose: bool = False) -> dict:
    """
    Ask the Health Agent a question about cluster health.
    
    Args:
        question: Question about cluster health
        api_key: Anthropic API key (optional)
        verbose: Whether to show detailed reasoning
    
    Returns:
        Dict with 'answer' and 'messages'
    """
    try:
        # Create workflow
        workflow = create_health_agent(api_key=api_key, verbose=verbose)
        
        # Compile
        app = workflow.compile()
        
        # Execute
        from langchain_core.messages import HumanMessage
        
        result = app.invoke({
            "messages": [HumanMessage(content=question)]
        })
        
        # Extract final answer
        messages = result.get("messages", [])
        final_answer = "No response generated."
        
        from langchain_core.messages import AIMessage
        for message in reversed(messages):
            if isinstance(message, AIMessage) and message.content and message.content.strip():
                final_answer = message.content
                break
        
        return {
            "answer": final_answer,
            "messages": messages
        }
        
    except Exception as e:
        return {
            "answer": f"Health Agent error: {str(e)}",
            "messages": []
        }


# Test function
if __name__ == "__main__":
    print("Testing Health Agent...")
    
    # Test 1: Node health
    print("\n=== TEST 1: Node Health ===")
    result = ask_health_agent("Are all nodes healthy?")
    print(result["answer"])
    
    # Test 2: Recent events
    print("\n=== TEST 2: Recent Events ===")
    result = ask_health_agent("Any recent problems in the cluster?")
    print(result["answer"])
    
    # Test 3: Overall cluster health
    print("\n=== TEST 3: Overall Cluster Health ===")
    result = ask_health_agent("Is my cluster healthy?")
    print(result["answer"])
    
    print("\nHealth Agent tests completed!")
