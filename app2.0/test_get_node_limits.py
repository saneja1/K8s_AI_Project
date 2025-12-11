#!/usr/bin/env python3
"""Test the new get_node_limits tool"""

import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient


async def test_tool():
    """Test get_node_limits tool"""
    client = MultiServerMCPClient(
        {
            "k8s_resources": {
                "transport": "streamable_http",
                "url": "http://127.0.0.1:8001/mcp"
            }
        }
    )
    
    # Get all tools
    tools = await client.get_tools()
    
    print("Available tools:")
    for tool in tools:
        print(f"  - {tool.name}")
    
    # Find get_node_limits
    limits_tool = None
    for tool in tools:
        if tool.name == "get_node_limits":
            limits_tool = tool
            break
    
    if limits_tool:
        print(f"\n✅ Found get_node_limits tool!")
        print(f"Description: {limits_tool.description}")
        
        # Call it
        print("\n📞 Calling get_node_limits(node_name='k8s-master-01')...")
        result = await limits_tool.ainvoke({"node_name": "k8s-master-01"})
        print(f"\nResult:\n{result}")
    else:
        print("\n❌ get_node_limits tool NOT FOUND")
        print("Available tools are:", [t.name for t in tools])


if __name__ == "__main__":
    asyncio.run(test_tool())
