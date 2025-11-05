"""
Direct test of get_pod_memory_comparison via MCP
"""

import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient


async def test_tool():
    print("Connecting to MCP Resources Server...")
    
    client = MultiServerMCPClient(
        {
            "k8s_resources": {
                "transport": "streamable_http",
                "url": "http://127.0.0.1:8002/mcp"
            }
        }
    )
    
    print("Getting tools...")
    tools = await client.get_tools()
    
    print(f"\nFound {len(tools)} tools:")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description[:80]}...")
    
    # Find and call get_pod_memory_comparison
    memory_tool = None
    for tool in tools:
        if tool.name == "get_pod_memory_comparison":
            memory_tool = tool
            break
    
    if memory_tool:
        print(f"\n✅ Found get_pod_memory_comparison tool!")
        print("\nCalling tool...")
        result = await memory_tool.ainvoke({"namespace": "all"})
        print("\n" + "="*80)
        print(result)
        print("="*80)
    else:
        print("\n❌ get_pod_memory_comparison tool NOT FOUND!")
        print("Available tools are:")
        for tool in tools:
            print(f"  - {tool.name}")


if __name__ == "__main__":
    asyncio.run(test_tool())
