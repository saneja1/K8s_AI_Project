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
from .operations_agent import run_operations_agent
from .monitor_agent import ask_monitor_agent

# Load environment variables
load_dotenv()

# ============================================================================
# CONVERSATION STATE MANAGEMENT
# ============================================================================

# Global conversation state (persists across calls)
_conversation_state = {"messages": []}

def get_conversation_state():
    """Get the current conversation state"""
    return _conversation_state

def reset_conversation():
    """Reset the conversation history"""
    global _conversation_state
    _conversation_state = {"messages": []}
    return "Conversation history cleared."


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
        
        # Check if this is a greeting or non-K8s question
        greeting_check_prompt = f"""Is this a Kubernetes-related question, a greeting, casual conversation, or a meta-question about our conversation?

Question: "{user_question}"

Respond with ONLY one word:
- "K8S" if it's about Kubernetes (pods, nodes, deployments, metrics, health, resources, etc.)
- "GREETING" if it's a greeting (hi, hello, hey, good morning, etc.)
- "META" if asking about conversation history (last questions, previous queries, what did I ask, etc.)
- "CASUAL" if it's casual conversation or non-K8s question

Your response (one word only):"""
        
        check_response = model.invoke([HumanMessage(content=greeting_check_prompt)])
        question_type = check_response.content.strip().upper()
        
        # Handle greetings and casual conversation
        if question_type == "GREETING":
            return {"messages": [AIMessage(content="Hello! I'm your Kubernetes cluster assistant. I can help you with:\n\n• Cluster health and node status\n• Resource listings (pods, services, deployments)\n• Performance metrics and monitoring\n• Operations like scaling and updates\n\nWhat would you like to know about your cluster?")]}
        
        if question_type == "META":
            # Extract user's previous questions from conversation history
            previous_questions = []
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    previous_questions.append(msg.content)
            
            if len(previous_questions) <= 1:
                return {"messages": [AIMessage(content="This is your first question in this conversation session.")]}
            
            # Get last 5 questions (excluding current one)
            recent_questions = previous_questions[-6:-1] if len(previous_questions) > 5 else previous_questions[:-1]
            recent_questions.reverse()  # Most recent first
            
            response_text = f"Here are your last {len(recent_questions)} question(s):\n\n"
            for i, q in enumerate(recent_questions, 1):
                response_text += f"{i}. {q}\n"
            
            return {"messages": [AIMessage(content=response_text)]}
        
        if question_type == "CASUAL":
            return {"messages": [AIMessage(content="I'm a specialized Kubernetes assistant. I can help you monitor and manage your K8s cluster. Would you like to ask about your cluster's health, resources, metrics, or operations?")]}
        
        # Routing logic: Classify which agent(s) should handle this query
        routing_prompt = f"""Classify this Kubernetes query into ONE OR MORE categories (can select multiple):

Query: "{user_question}"

Categories:
1. HEALTH - Node health status, node readiness, cluster-level events, control plane component health, cluster health check (NOT individual pod health/status, NOT metrics/usage)
2. RESOURCES - Resource allocation/limits/requests ONLY (NOT actual usage). Use ONLY when query explicitly mentions "allocation", "limits", "requests", "capacity", or "quotas"
3. DESCRIBE - List/count/describe K8s resources (pods, services, deployments, namespaces), pod status (Running/Failed/Pending), unhealthy pods, POD LOGS (get/show/retrieve logs)
4. MONITOR - ALL CPU/MEMORY/DISK usage queries, metrics, percentages, actual resource consumption (default for any "usage" questions)
5. SECURITY - RBAC, roles, permissions, network policies, secrets
6. OPERATIONS - Scaling deployments, updates, rollouts, restarts, maintenance, creating/deleting resources, applying YAML configs

IMPORTANT ROUTING RULES:

HEALTH CATEGORY (node/cluster health, NOT resource usage):
- "cluster health" or "is cluster healthy" or "cluster status" → HEALTH
- **"node health" or "node status" or "check nodes" or "node readiness"** → HEALTH
- "control plane health" → HEALTH
- "cluster events" → HEALTH
- NOTE: For listing node names, use DESCRIBE instead
- NOTE: For node metrics (CPU/memory), use MONITOR instead

RESOURCES CATEGORY (allocation/limits/requests ONLY - NOT usage):
- **ONLY use if query explicitly mentions: "allocation", "limits", "requests", "capacity", "quotas", "allocatable"**
- **"resource allocation" or "resource limits" or "resource requests"** → RESOURCES
- **"allocatable resources" or "capacity" or "resource quotas"** → RESOURCES
- **NEVER use RESOURCES for "usage", "metrics", "CPU", "memory", "disk"** → those go to MONITOR
- NOTE: For actual CPU/memory/disk usage metrics, ALWAYS use MONITOR instead

MONITOR CATEGORY (ALL usage/metrics queries - default for resource consumption):
- **DEFAULT: ANY mention of "usage", "CPU", "memory", "disk", "metrics", "consumption"** → MONITOR (ONLY)
- **"cpu usage" or "memory usage" or "disk usage"** → MONITOR (ONLY)
- **"what is cpu" or "what is memory" or "get cpu" or "get memory"** → MONITOR (ONLY)
- **"node cpu" or "node memory" or "pod cpu" or "pod memory"** → MONITOR (ONLY)
- **"CPU for node X" or "memory for node X" or "metrics for node X"** → MONITOR (ONLY)
- **"get node CPU" or "get memory" or "node memory"** → MONITOR (ONLY)
- **"CPU and memory" or "CPU/memory metrics"** → MONITOR (ONLY)
- **"show metrics" or "get metrics" or "node metrics" or "performance metrics"** → MONITOR (ONLY)
- **"worker node metrics" or "master node metrics" or "metrics for worker/master"** → MONITOR (ONLY)
- **"CPU, memory, disk" or "all metrics" or "comprehensive metrics"** → MONITOR (ONLY)
- **"CPU trend" or "memory trend" or "show CPU last hour"** → MONITOR (ONLY)
- **"CPU usage over time" or "historical metrics"** → MONITOR (ONLY)
- **"highest memory" or "most memory" or "which pod uses most memory"** → MONITOR (ONLY)
- **"which pod uses most CPU" or "largest CPU/memory"** → MONITOR (ONLY)
- **"find pod with highest/most resource"** → MONITOR (ONLY)
- **"network traffic" or "network metrics"** → MONITOR (ONLY)
- **"monitor nodes" or "node monitoring" or "cluster monitoring"** → MONITOR (ONLY)
- **"percentage" or "%" (any percentage-based metrics)** → MONITOR (ONLY)
- **ANY query with "usage" in it** → MONITOR (ONLY)
- Any query asking for CPU/memory/disk/network consumption/metrics → MONITOR
- Any query asking for trends/history/time-series → MONITOR
- Any query asking for actual resource values → MONITOR

DESCRIBE CATEGORY (listing/counting resources, pod status):
- **"list pods/services/deployments"** → DESCRIBE (ONLY)
- **"how many pods/services" or "count pods"** → DESCRIBE (ONLY)
- **"list nodes" or "show nodes" or "node names" or "what are the nodes"** → DESCRIBE (ONLY)
- **"names of nodes" or "which nodes" or "what nodes exist"** → DESCRIBE (ONLY)
- **"taints" or "what taints" or "node taints" or "show taints"** → DESCRIBE (ONLY)
- "describe pod/service/deployment" → DESCRIBE
- "what namespaces exist" → DESCRIBE
- **"pod health" or "unhealthy pods" or "pod status"** → DESCRIBE
- **"pods failing" or "pods in error" or "crashed pods"** → DESCRIBE
- **"which pods are running/pending/failed"** → DESCRIBE
- **"logs" or "pod logs" or "get logs" or "show logs" or "retrieve logs" or "output from pod"** → DESCRIBE (ONLY)
- **"last N lines of logs" or "tail logs" or "recent logs"** → DESCRIBE (ONLY)
- **"logs from X pod" or "X pod logs" or "logs for X"** → DESCRIBE (ONLY)
- NOTE: For metrics like CPU/memory usage, use MONITOR instead

OPERATIONS CATEGORY (write operations and deployment management):
- **"scale deployment" or "scale to X replicas"** → OPERATIONS (ONLY)
- **"create configmap/pod/deployment" or "delete namespace"** → OPERATIONS (ONLY)
- **"apply YAML" or "restart deployment" or "rollback"** → OPERATIONS (ONLY)
- **"rollout status" or "deployment rollout status" or "get rollout status"** → OPERATIONS (ONLY)
- **"rollout restart" or "rollback deployment"** → OPERATIONS (ONLY)

- "list pods/services/deployments" → DESCRIBE (ONLY)
- "how many pods/services" → DESCRIBE (ONLY)
- "describe pod/service/deployment" → DESCRIBE (ONLY)
- "what namespaces exist" → DESCRIBE (ONLY)
- "show me all X" → DESCRIBE (where X is specific resource type like pods, not general status)

MULTI-AGENT EXAMPLES:
- "show me all pods AND their health" → DESCRIBE,HEALTH (parallel)
- **"what are the names of nodes" or "list node names"** → DESCRIBE (ONLY)
- **"what are the 2 nodes in cluster"** → DESCRIBE (ONLY)
- **"node names" or "which nodes exist"** → DESCRIBE (ONLY)
- "list nodes with their status" → DESCRIBE,HEALTH (parallel)
- **"get node CPU and memory metrics"** → MONITOR (ONLY)
- **"show node CPU and memory"** → MONITOR (ONLY)
- **"node CPU usage"** → MONITOR (ONLY)
- **"get memory metrics"** → MONITOR (ONLY)
- **"show me CPU, memory, and disk for all nodes"** → MONITOR (ONLY)
- **"get node metrics"** → MONITOR (ONLY)
- **"show metrics for node X"** → MONITOR (ONLY)
- **"performance metrics"** → MONITOR (ONLY)
- **"count pods AND highest memory AND cluster health"** → DESCRIBE,MONITOR,HEALTH (all 3)
- **"CPU trend last hour"** → MONITOR (ONLY)
- **"which pod uses most memory"** → MONITOR (ONLY)
- **"scale deployment AND check node health"** → OPERATIONS,HEALTH (parallel)
- **"list deployments AND which pod uses most memory"** → DESCRIBE,MONITOR (parallel)

CRITICAL: Respond with ONLY comma-separated category names, nothing else.
Examples:
- "HEALTH"
- "DESCRIBE"
- "MONITOR"
- "RESOURCES"
- "MONITOR,HEALTH"
- "DESCRIBE,HEALTH"
- "MONITOR,HEALTH"
- "OPERATIONS,HEALTH"
- "OPERATIONS,DESCRIBE"

Your response (category names only):"""
        
        # Ask LLM to classify
        classification_response = model.invoke([HumanMessage(content=routing_prompt)])
        categories_str = classification_response.content.strip().upper()
        categories = [cat.strip() for cat in categories_str.split(',')]
        
        # Extract sub-questions for each agent
        extraction_prompt = f"""Break down this complex question into specific sub-questions for each category.

Original question: "{user_question}"

Categories detected: {categories_str}

For each category, extract ALL relevant parts of the question:

HEALTH category: Extract node health, cluster health, control plane health parts
DESCRIBE category: Extract listing/counting/describing pods/services/deployments/namespaces parts, pod status/health parts (unhealthy pods, failing pods, pod errors), AND node taints/labels/annotations
RESOURCES category: Extract kubectl top, current snapshot parts (no trends/history)
MONITOR category: Extract CPU/memory trends, historical data, highest/most resource usage, time-series analysis parts. **CRITICAL: Preserve ALL numbers (top 3, top 5, etc.) in the sub-question**
OPERATIONS category: Extract scaling, deployment updates, rollouts, restarts, pod/namespace creation/deletion, YAML apply parts. **CRITICAL: Preserve ALL numbers (scale to 3, 5 replicas, etc.)**

Format your response EXACTLY like this:
HEALTH: <health sub-question or "N/A">
DESCRIBE: <describe sub-question or "N/A">
RESOURCES: <resources sub-question or "N/A">
MONITOR: <monitor sub-question or "N/A">
OPERATIONS: <operations sub-question or "N/A">

Examples:
Original: "check no of pods and find highest memory pod and check cluster health"
HEALTH: check cluster health
DESCRIBE: how many pods in the cluster
RESOURCES: N/A
MONITOR: find pod with highest memory
OPERATIONS: N/A

Original: "what taints are on k8s-master-01"
HEALTH: N/A
DESCRIBE: what taints are on node k8s-master-01
RESOURCES: N/A
MONITOR: N/A
OPERATIONS: N/A

Original: "which 3 pods have the highest CPU usage"
HEALTH: N/A
DESCRIBE: N/A
RESOURCES: N/A
MONITOR: which 3 pods have the highest CPU usage
OPERATIONS: N/A

Original: "show me top 5 pods by memory"
HEALTH: N/A
DESCRIBE: N/A
RESOURCES: N/A
MONITOR: show me top 5 pods by memory
OPERATIONS: N/A

Original: "what was the CPU trend in the last hour"
HEALTH: N/A
DESCRIBE: N/A
RESOURCES: N/A
MONITOR: CPU trend in the last hour
OPERATIONS: N/A

Original: "scale stress-tester to 5 replicas and check node health"
HEALTH: check node health
DESCRIBE: N/A
RESOURCES: N/A
MONITOR: N/A
OPERATIONS: scale stress-tester deployment to 5 replicas

Original: "create a configmap named test-config and list all pods"
HEALTH: N/A
DESCRIBE: list all pods
RESOURCES: N/A
OPERATIONS: create a configmap named test-config

Your response:"""

        extraction_response = model.invoke([HumanMessage(content=extraction_prompt)])
        extraction_text = extraction_response.content.strip()
        
        # Parse extracted sub-questions
        sub_questions = {}
        for line in extraction_text.split('\n'):
            if ':' in line:
                category, question = line.split(':', 1)
                category = category.strip().upper()
                question = question.strip()
                if question and question.upper() != 'N/A':
                    sub_questions[category] = question
        
        # Collect agents to execute with their specific sub-questions
        agents_to_run = []
        
        # Debug flag (set SHOW_ROUTING=1 to see sub-question routing)
        show_routing = os.getenv('SHOW_ROUTING', '0') == '1'
        
        if "HEALTH" in categories:
            health_q = sub_questions.get('HEALTH', user_question)
            if show_routing:
                print(f"🔧 DEBUG: Health Agent sub-question: '{health_q}'")
            agents_to_run.append(("Health Agent", lambda q=health_q: ask_health_agent(q, api_key=anthropic_api_key, verbose=verbose)))
        
        if "DESCRIBE" in categories:
            describe_q = sub_questions.get('DESCRIBE', user_question)
            if show_routing:
                print(f"🔧 DEBUG: Describe Agent sub-question: '{describe_q}'")
            agents_to_run.append(("Describe Agent", lambda q=describe_q: ask_describe_agent(q, api_key=anthropic_api_key, verbose=verbose)))
        
        if "RESOURCES" in categories:
            resources_q = sub_questions.get('RESOURCES', user_question)
            if show_routing:
                print(f"🔧 DEBUG: Resources Agent sub-question: '{resources_q}'")
            agents_to_run.append(("Resources Agent", lambda q=resources_q: ask_resources_agent(q, api_key=anthropic_api_key, verbose=verbose)))
        
        if "MONITOR" in categories:
            monitor_q = sub_questions.get('MONITOR', user_question)
            if show_routing:
                print(f"🔧 DEBUG: Monitor Agent sub-question: '{monitor_q}'")
            agents_to_run.append(("Monitor Agent", lambda q=monitor_q: ask_monitor_agent(q, api_key=anthropic_api_key, verbose=verbose)))
        
        if "OPERATIONS" in categories:
            operations_q = sub_questions.get('OPERATIONS', user_question)
            if show_routing:
                print(f"🔧 DEBUG: Operations Agent sub-question: '{operations_q}'")
            agents_to_run.append(("Operations Agent", lambda q=operations_q: {"answer": run_operations_agent(q, api_key=anthropic_api_key)}))
        
        # Check for unimplemented agents
        unimplemented = []
        if "SECURITY" in categories:
            unimplemented.append("Security Agent (RBAC/security)")
        
        # Execute agents (parallel if multiple)
        if not agents_to_run and not unimplemented:
            return {"messages": [AIMessage(content=f"I couldn't classify your query (detected: {categories_str}). Please try rephrasing your question about cluster health, resources, describe, monitor, security, or operations.")]}
        
        results = []
        
        if len(agents_to_run) == 1:
            # Single agent - execute directly
            agent_name, agent_func = agents_to_run[0]
            try:
                result = agent_func()
                
                # Use the agent's synthesized answer (not raw tool output)
                answer = result.get('answer', f'No response from {agent_name}')
                
                results.append(f"**{agent_name}:**\n{answer}")
            except Exception as e:
                results.append(f"**{agent_name} Error:** {str(e)}")
        
        elif len(agents_to_run) > 1:
            # Multiple agents - execute in PARALLEL using ThreadPoolExecutor
            # This is faster than sequential execution
            import concurrent.futures
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(agents_to_run)) as executor:
                # Submit all agent functions to thread pool
                future_to_agent = {
                    executor.submit(agent_func): agent_name 
                    for agent_name, agent_func in agents_to_run
                }
                
                # Collect results as they complete
                for future in concurrent.futures.as_completed(future_to_agent):
                    agent_name = future_to_agent[future]
                    try:
                        result = future.result()
                        
                        # Use the agent's synthesized answer (not raw tool output)
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
    Maintains conversation history across calls.
    
    Args:
        question: User's question about the K8s cluster
        api_key: Anthropic API key (optional)
        verbose: Whether to show detailed agent reasoning
    
    Returns:
        Dict with 'answer' and 'messages' (full conversation)
    """
    global _conversation_state
    
    try:
        # Create supervisor workflow (manual replacement for create_react_agent)
        workflow = create_k8s_supervisor_agent(api_key=api_key, verbose=verbose)
        
        # Compile the workflow (same as sample pattern)
        app = workflow.compile()
        
        # Add new question to conversation history
        from langchain_core.messages import HumanMessage
        _conversation_state["messages"].append(HumanMessage(content=question))
        
        # Execute with full conversation context
        result = app.invoke(_conversation_state)
        
        # Update conversation state with result
        _conversation_state["messages"] = result.get("messages", [])
        
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
