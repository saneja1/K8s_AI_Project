"""
MCP Client for Resources Agent (Standalone Test)
Tests the Resources MCP server connection and tool execution
"""

import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, MessagesState
from langchain_core.messages import HumanMessage
import os
from dotenv import load_dotenv

load_dotenv()


async def test_resources_mcp():
    """Test connection to Resources MCP server and execute a tool"""
    
    print("🔌 Connecting to Resources MCP Server on port 8002...")
    
    # Connect to Resources MCP server
    client = MultiServerMCPClient({
        "k8s_resources": {
            "transport": "streamable_http",
            "url": "http://127.0.0.1:8002/mcp"
        }
    })
    
    # Get tools from MCP server
    tools = await client.get_tools()
    print(f"✅ Connected! Found {len(tools)} tools:")
    for tool in tools:
        print(f"   - {tool.name}")
    
    # Initialize Claude with tools
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not found in environment")
        return
    
    model = ChatAnthropic(
        model="claude-3-haiku-20240307",
        anthropic_api_key=api_key,
        temperature=0
    )
    
    model_with_tools = model.bind_tools(tools)
    
    # Create a simple workflow to test
    def agent_node(state):
        messages = state["messages"]
        response = model_with_tools.invoke(messages)
        return {"messages": [response]}
    
    async def tool_node(state):
        from langchain_core.messages import ToolMessage
        messages = state["messages"]
        last_message = messages[-1]
        
        tool_results = []
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            for tool_call in last_message.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call.get("args", {})
                
                for tool in tools:
                    if tool.name == tool_name:
                        try:
                            result = await tool.ainvoke(tool_args)
                            tool_results.append(
                                ToolMessage(
                                    content=str(result),
                                    tool_call_id=tool_call["id"]
                                )
                            )
                        except Exception as e:
                            tool_results.append(
                                ToolMessage(
                                    content=f"Error: {str(e)}",
                                    tool_call_id=tool_call["id"]
                                )
                            )
                        break
        
        return {"messages": tool_results}
    
    # Build workflow
    workflow = StateGraph(MessagesState)
    workflow.add_node("agent", agent_node)
    workflow.add_node("tools", tool_node)
    workflow.set_entry_point("agent")
    
    def should_continue(state):
        messages = state["messages"]
        last_message = messages[-1]
        if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
            return "tools"
        return "__end__"
    
    workflow.add_conditional_edges("agent", should_continue, {"tools": "tools", "__end__": "__end__"})
    workflow.add_edge("tools", "agent")
    
    app = workflow.compile()
    
    # Test query
    print("\n🧪 Testing with query: 'What is the node utilization?'")
    
    result = await app.ainvoke({
        "messages": [HumanMessage(content="What is the node utilization?")]
    })
    
    print("\n📊 Result:")
    print(result["messages"][-1].content)


if __name__ == "__main__":
    asyncio.run(test_resources_mcp())
