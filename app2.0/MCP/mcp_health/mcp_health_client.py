"""
MCP Client for Health Agent
Connects to K8s Health MCP Server and provides tools to LangGraph agent
"""

import asyncio
import os
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, MessagesState, START, END

# Load environment variables
load_dotenv()


async def main():
    # Get API key from environment
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    
    # Initialize Claude model
    model = ChatAnthropic(
        model="claude-3-haiku-20240307",
        anthropic_api_key=anthropic_key,
        temperature=0
    )
    
    # Connect to MCP server
    client = MultiServerMCPClient(
        {
            "k8s_health": {
                "transport": "streamable_http",
                "url": "http://127.0.0.1:8000/mcp"
            }
        }
    )
    
    # Get tools from MCP server
    tools = await client.get_tools()
    print(f"✅ Connected to MCP server. Available tools: {[t.name for t in tools]}")
    
    # Bind tools to model
    model_with_tools = model.bind_tools(tools)
    
    # Define routing logic
    def should_continue(state: MessagesState):
        messages = state["messages"]
        last_message = messages[-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        return END
    
    # Define agent node
    async def call_model(state: MessagesState):
        from langchain_core.messages import SystemMessage
        messages = state["messages"]
        
        # Add system message if not present
        if not messages or not isinstance(messages[0], SystemMessage):
            system_msg = SystemMessage(content="You are a Kubernetes health monitoring agent. Use the available tools to check cluster health.")
            messages = [system_msg] + messages
        
        response = await model_with_tools.ainvoke(messages)
        return {"messages": [response]}
    
    # Define tool execution node
    async def call_tools(state: MessagesState):
        from langchain_core.messages import ToolMessage
        messages = state["messages"]
        last_message = messages[-1]
        
        tool_results = []
        for tool_call in last_message.tool_calls:
            # Find the tool
            tool = next((t for t in tools if t.name == tool_call['name']), None)
            if tool:
                # Execute the tool
                result = await tool.ainvoke(tool_call['args'])
                tool_results.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call['id']
                    )
                )
        
        return {"messages": tool_results}
    
    # Build graph
    builder = StateGraph(MessagesState)
    builder.add_node("agent", call_model)
    builder.add_node("tools", call_tools)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue)
    builder.add_edge("tools", "agent")
    
    # Compile graph
    graph = builder.compile()
    
    # Test query
    print("\n🔍 Query: Are all nodes healthy?\n")
    result = await graph.ainvoke({"messages": [{"role": "user", "content": "Are all nodes healthy?"}]})
    
    # Print final answer
    final_message = result["messages"][-1]
    print(f"\n✅ Answer:\n{final_message.content}\n")


if __name__ == "__main__":
    asyncio.run(main())
