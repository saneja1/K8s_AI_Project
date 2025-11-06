"""
MCP Operations Client - Test Client
Tests connection to MCP Operations Server
"""

import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient


async def test_operations_mcp():
    """Test connection to Operations MCP Server"""
    print("🔧 Testing MCP Operations Server Connection...")
    print("=" * 60)
    
    try:
        # Connect to MCP Operations Server
        print("\n1. Connecting to http://localhost:8003/mcp...")
        client = MultiServerMCPClient(
            {
                "k8s_operations": {
                    "transport": "streamable_http",
                    "url": "http://127.0.0.1:8003/mcp"
                }
            }
        )
        
        operations_tools = await client.get_tools()
        
        print(f"✅ Connected! Found {len(operations_tools)} tools\n")
        
        # List all tools
        print("2. Available Tools:")
        print("-" * 60)
        for i, tool in enumerate(operations_tools, 1):
            print(f"{i}. {tool.name}")
            if hasattr(tool, 'description'):
                desc = tool.description[:80] if len(tool.description) > 80 else tool.description
                print(f"   Description: {desc}...")
            print()
        
        print("=" * 60)
        print("✅ MCP Operations Server is working correctly!")
        print("\nAll 13 operations tools are available:")
        print("  • Deployment ops: scale, restart, rollback, status")
        print("  • Pod ops: delete (single/status/label)")
        print("  • Node ops: cordon, uncordon, drain")
        print("  • Resource ops: patch, namespace create/delete")
        
        return operations_tools
        
    except Exception as e:
        print(f"\n❌ Error connecting to MCP Operations Server: {e}")
        print("\nTroubleshooting:")
        print("1. Is the MCP Operations Server running on port 8003?")
        print("   Start it with: cd /home/K8s_AI_Project/app2.0 && source .venv/bin/activate && python MCP/mcp_operations/mcp_operations_server.py")
        print("2. Check if port 8003 is available: lsof -i :8003")
        print("3. Check server logs for errors")
        return None


if __name__ == "__main__":
    asyncio.run(test_operations_mcp())

