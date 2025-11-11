"""
MCP Client for Monitor Agent
Connects to Monitor MCP server and retrieves Prometheus monitoring tools
"""

import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient


async def get_monitor_tools():
    """
    Connect to Monitor MCP server and retrieve available tools.
    Returns list of LangChain tools that can be used by agents.
    """
    try:
        # Connect to Monitor MCP server on port 8004
        client = MultiServerMCPClient({
            "k8s_monitor": {
                "transport": "streamable_http",
                "url": "http://127.0.0.1:8004/mcp"
            }
        })
        
        # Get tools from MCP server
        tools = await client.get_tools()
        
        print(f"✅ Connected to Monitor MCP Server! Found {len(tools)} tools:")
        for tool in tools:
            print(f"   - {tool.name}")
        
        return tools
        
    except Exception as e:
        print(f"❌ Error connecting to Monitor MCP server: {str(e)}")
        print("   Make sure mcp_monitor_server.py is running on port 8004")
        return []


def get_monitor_tools_sync():
    """
    Synchronous wrapper to get monitor tools.
    Use this in non-async contexts.
    """
    return asyncio.run(get_monitor_tools())


# Standalone test
async def test_monitor_mcp():
    """Test connection to Monitor MCP server and list available tools"""
    
    print("🔌 Connecting to Monitor MCP Server on port 8004...")
    
    tools = await get_monitor_tools()
    
    if tools:
        print("\n📋 Tool Descriptions:")
        print("=" * 80)
        for tool in tools:
            print(f"\nTool: {tool.name}")
            print(f"Description: {tool.description}")
            print("-" * 80)
    else:
        print("\n❌ No tools retrieved. Server may not be running.")
        print("   Start with: python3 mcp_monitor_server.py")


if __name__ == "__main__":
    asyncio.run(test_monitor_mcp())
