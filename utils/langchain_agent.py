"""
LangChain-based Kubernetes AI Agent.
Replaces the custom K8sAgent with LangChain's agent framework.
"""

import os
from typing import List, Optional
from langchain.agents import AgentExecutor, create_openai_functions_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.memory import ConversationBufferMemory
from langchain.schema import SystemMessage, HumanMessage, AIMessage

# Import Claude support (optional - only used when llm_provider="claude")
try:
    from langchain_anthropic import ChatAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class LangChainK8sAgent:
    """
    LangChain-powered Kubernetes assistant that uses AI to intelligently
    select and execute tools for answering cluster-related questions.
    """
    
    def __init__(self, tools: List, api_key: Optional[str] = None, verbose: bool = True):
        """
        Initialize the LangChain agent with tools and configuration.
        
        Args:
            tools: List of LangChain tools the agent can use
            api_key: Google API key for Gemini (defaults to GOOGLE_API_KEY env var)
            verbose: Whether to print agent reasoning steps
        """
        self.tools = tools
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY')
        self.verbose = verbose
        
        # Initialize Gemini LLM
        self.llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=self.api_key,
            temperature=0.2,
            convert_system_message_to_human=True  # Gemini requires this
        )
        
        # Create system prompt (no variables - just static instructions)
        self.system_prompt = """You are a helpful Kubernetes cluster assistant with access to live cluster data.

Your capabilities:
- Access real-time cluster information via kubectl commands
- Check node health, taints, labels, and conditions
- View pod status, logs, and resource usage
- Analyze cluster health and provide recommendations

CRITICAL RULES FOR TOOL USAGE:
- **ALWAYS call tools ONE AT A TIME** - Never make multiple tool calls in a single response
- When asked about multiple resources (e.g., "check master and worker nodes"), call the tool once, get the result, then call it again for the next resource
- Wait for each tool response before making the next tool call
- This prevents errors with parallel function execution

IMPORTANT - BE PROACTIVE:
- **DO NOT ask for permission** to use tools - just use them!
- **DO NOT ask clarifying questions** if you can figure it out - just get the data!
- When asked "How many pods are in each namespace?", immediately call get_cluster_resources with resource_type='pods' and analyze the results
- When asked about multiple resources, check them sequentially without asking
- Process and analyze the data yourself - count, filter, group as needed
- Only ask clarifying questions if the request is genuinely ambiguous

Guidelines:
- Use the provided tools to gather accurate, live data
- Provide clear, concise answers based on actual cluster state
- Format output clearly with headers, bullet points, or tables when appropriate
- If a tool fails, explain what went wrong and suggest alternatives
- Be direct and action-oriented - users want answers, not questions

Remember: You have direct access to the live Kubernetes cluster - use your tools proactively and sequentially to get accurate information!"""
        
        # Create prompt template with only 'input' variable
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", self.system_prompt),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")
        ])
        
        # Initialize memory for conversation history
        self.memory = ConversationBufferMemory(
            memory_key="chat_history",
            return_messages=True,
            output_key="output"
        )
        
        # Create the agent
        self.agent = create_openai_functions_agent(
            llm=self.llm,
            tools=self.tools,
            prompt=self.prompt
        )
        
        # Create executor with early_stopping_method to prevent parallel issues
        self.executor = AgentExecutor(
            agent=self.agent,
            tools=self.tools,
            memory=self.memory,
            verbose=self.verbose,
            handle_parsing_errors=True,
            max_iterations=10,  # Allow more iterations for sequential tool calls
            max_execution_time=120,  # Increase timeout for multiple tool calls
            return_intermediate_steps=True,
            early_stopping_method="generate"  # Helps with function calling issues
        )
    
    def answer_question(self, question: str, cluster_context: str = "") -> dict:
        """
        Answer a user's question using the LangChain agent.
        
        Args:
            question: User's question about the cluster
            cluster_context: Current cluster state from cached data (included in question if provided)
        
        Returns:
            dict with 'answer' (str), 'intermediate_steps' (list), and 'success' (bool)
        """
        try:
            # If cluster context provided, prepend it to the question
            if cluster_context:
                enhanced_question = f"Context about current cluster state:\n{cluster_context[:500]}\n\nUser question: {question}"
            else:
                enhanced_question = question
            
            # Invoke the agent with only 'input' key
            result = self.executor.invoke({
                "input": enhanced_question
            })
            
            return {
                "answer": result.get("output", "No response generated."),
                "intermediate_steps": result.get("intermediate_steps", []),
                "success": True
            }
            
        except ValueError as ve:
            # Handle function calling errors specifically
            if "function response parts" in str(ve) or "function call parts" in str(ve):
                error_msg = "I encountered an issue with parallel tool execution. Let me try a different approach.\n\n"
                error_msg += "Please try rephrasing your question to focus on one resource at a time, "
                error_msg += "or I can check resources sequentially if you ask again."
                return {
                    "answer": error_msg,
                    "intermediate_steps": [],
                    "success": False,
                    "error": str(ve)
                }
            raise  # Re-raise if it's a different ValueError
            
        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}\n\nI'll try to help based on cached data instead."
            return {
                "answer": error_msg,
                "intermediate_steps": [],
                "success": False,
                "error": str(e)
            }
    
    def clear_memory(self):
        """Clear the conversation history."""
        self.memory.clear()
    
    def get_memory(self) -> List:
        """Get the current conversation history."""
        return self.memory.chat_memory.messages


def create_k8s_agent(tools: List, api_key: Optional[str] = None, verbose: bool = False) -> LangChainK8sAgent:
    """
    Factory function to create a LangChain K8s agent.
    
    Args:
        tools: List of LangChain tools
        api_key: Google API key
        verbose: Whether to show agent reasoning
    
    Returns:
        Initialized LangChainK8sAgent
    """
    return LangChainK8sAgent(tools=tools, api_key=api_key, verbose=verbose)


def create_k8s_multiagent_system(api_key: Optional[str] = None, verbose: bool = False, llm_provider: str = "gemini"):
    """
    Create the complete 6-agent Kubernetes multi-agent system with supervisor.
    
    This is the main entry point for the Streamlit dashboard to create
    the full multi-agent system with:
    - 6 specialist agents (Health, Security, Resources, Monitor, Describe/Get, Operations)
    - 1 supervisor agent for intelligent routing
    
    Args:
        api_key: API key for the selected LLM provider (defaults to GOOGLE_API_KEY or ANTHROPIC_API_KEY env var)
        verbose: Whether to show agent reasoning steps
        llm_provider: Which LLM to use - "gemini" or "claude" (default: "gemini")
    
    Returns:
        Supervisor agent (LangGraph CompiledGraph) that routes to all 6 specialists
    """
    # Import all agent creation functions
    from agents.health_agent import create_health_agent
    from agents.security_agent import create_security_agent
    from agents.resources_agent import create_resources_agent
    from agents.monitor_agent import create_monitor_agent
    from agents.describe_get_agent import create_describe_get_agent
    from agents.operations_agent import create_operations_agent
    from agents.supervisor_agent import create_k8s_supervisor
    
    # Initialize LLM based on provider
    if llm_provider.lower() == "claude":
        if not ANTHROPIC_AVAILABLE:
            raise ImportError("langchain-anthropic package not installed. Run: pip install langchain-anthropic")
        
        # Get API key
        actual_api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not actual_api_key:
            raise ValueError("Anthropic API key required. Set ANTHROPIC_API_KEY environment variable.")
        
        # Initialize Claude LLM
        llm = ChatAnthropic(
            model="claude-3-5-sonnet-20241022",  # Latest Claude 3.5 Sonnet
            anthropic_api_key=actual_api_key,
            temperature=0.2,
            max_tokens=4096
        )
    else:  # Default to Gemini
        # Get API key
        actual_api_key = api_key or os.getenv('GOOGLE_API_KEY')
        if not actual_api_key:
            raise ValueError("Google API key required. Set GOOGLE_API_KEY environment variable.")
        
        # Initialize Gemini LLM
        llm = ChatGoogleGenerativeAI(
            model="gemini-1.5-flash",  # Higher free tier: 1500 requests/day vs 50/day
            google_api_key=actual_api_key,
            temperature=0.2,
            convert_system_message_to_human=True
        )
    
    # Create all 6 specialist agents
    health_agent = create_health_agent(llm, verbose=verbose)
    security_agent = create_security_agent(llm, verbose=verbose)
    resources_agent = create_resources_agent(llm, verbose=verbose)
    monitor_agent = create_monitor_agent(llm, verbose=verbose)
    describe_get_agent = create_describe_get_agent(llm, verbose=verbose)
    operations_agent = create_operations_agent(llm, verbose=verbose)
    
    # Create supervisor that routes to all 6 agents
    supervisor = create_k8s_supervisor(
        llm_model=llm,  # Note: parameter is llm_model, not llm
        health_agent=health_agent,
        security_agent=security_agent,
        resources_agent=resources_agent,
        monitor_agent=monitor_agent,
        describe_get_agent=describe_get_agent,
        operations_agent=operations_agent
    )
    
    # Compile the StateGraph into an executable workflow
    return supervisor.compile()
