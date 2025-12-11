"""Test describe agent with full tool call debugging"""
import asyncio
import os
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

async def test_describe_agent():
    # Get API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set")
        return
    
    # Initialize model
    model = ChatAnthropic(
        model="claude-3-haiku-20240307",
        anthropic_api_key=api_key,
        temperature=0
    )
    
    # Get tools from MCP server
    client = MultiServerMCPClient({
        "k8s_describe": {
            "transport": "streamable_http",
            "url": "http://127.0.0.1:8002/mcp"
        }
    })
    tools = await client.get_tools()
    print(f"✓ Loaded {len(tools)} tools from MCP server\n")
    
    # Bind tools
    model_with_tools = model.bind_tools(tools)
    
    # Test query
    query = "How many pods are running on k8s-master-01?"
    print(f"Query: {query}\n")
    
    messages = [HumanMessage(content=query)]
    
    # Agent loop
    max_iterations = 3
    for i in range(max_iterations):
        print(f"--- Iteration {i+1} ---")
        
        response = model_with_tools.invoke(messages)
        messages.append(response)
        
        # Check if AI wants to call tools
        if hasattr(response, 'tool_calls') and response.tool_calls:
            print(f"AI wants to call {len(response.tool_calls)} tool(s):")
            
            for tool_call in response.tool_calls:
                print(f"  Tool: {tool_call['name']}")
                print(f"  Args: {tool_call['args']}")
                
                # Execute tool
                tool_name = tool_call['name']
                tool_args = tool_call['args']
                
                # Find and call the tool
                tool_obj = next((t for t in tools if t.name == tool_name), None)
                if tool_obj:
                    try:
                        result = await tool_obj.ainvoke(tool_args)
                        print(f"  Result preview: {str(result)[:200]}...")
                        
                        # Add tool result to messages
                        messages.append(ToolMessage(
                            content=str(result),
                            tool_call_id=tool_call['id']
                        ))
                    except Exception as e:
                        print(f"  ERROR: {e}")
                        messages.append(ToolMessage(
                            content=f"Error: {e}",
                            tool_call_id=tool_call['id']
                        ))
        else:
            # No more tool calls - this is the final answer
            print(f"\nFinal Answer:")
            print(response.content)
            break

asyncio.run(test_describe_agent())
