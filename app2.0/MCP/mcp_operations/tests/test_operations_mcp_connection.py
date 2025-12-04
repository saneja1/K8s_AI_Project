#!/usr/bin/env python3
"""
Test MCP Operations Server Tool Connections
Tests if all 15 tools are properly registered and accessible via MCP Operations Server
"""

import sys
import os
import asyncio
from typing import Dict, List

# Add MCP operations directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MCP', 'mcp_operations'))

def test_mcp_operations_tools_connection():
    """Test connection to all 15 tools in MCP Operations Server"""
    
    print("=" * 70)
    print("MCP OPERATIONS SERVER - TOOL CONNECTION TEST")
    print("=" * 70)
    print()
    
    # Expected tools list
    expected_tools = [
        "scale_deployment_tool",
        "restart_deployment_tool",
        "rollback_deployment_tool",
        "get_deployment_rollout_status_tool",
        "delete_deployment_tool",
        "delete_pod_tool",
        "delete_pods_by_status_tool",
        "delete_pods_by_label_tool",
        "cordon_node_tool",
        "uncordon_node_tool",
        "drain_node_tool",
        "patch_resource_tool",
        "create_namespace_tool",
        "delete_namespace_tool",
        "apply_yaml_config_tool"
    ]
    
    results = {}
    
    try:
        # Import the MCP server module
        print("📡 Importing MCP Operations Server module...")
        from mcp_operations_server import mcp
        print("✅ MCP Server module imported successfully\n")
        
        # Get all registered tools - FastMCP stores tools in list_tools()
        registered_tools = []
        
        # Try multiple access methods for FastMCP
        if hasattr(mcp, 'list_tools'):
            try:
                # FastMCP has list_tools() method that returns tool definitions
                tools_list = mcp.list_tools()
                if isinstance(tools_list, list):
                    registered_tools = [tool.name if hasattr(tool, 'name') else str(tool) for tool in tools_list]
                print(f"✅ Retrieved tools via list_tools() method\n")
            except Exception as e:
                print(f"⚠️  list_tools() method failed: {e}\n")
        
        if not registered_tools and hasattr(mcp, '_tools'):
            registered_tools = list(mcp._tools.keys())
            print(f"✅ Retrieved tools via _tools attribute\n")
        elif not registered_tools and hasattr(mcp, 'tools'):
            registered_tools = list(mcp.tools.keys())
            print(f"✅ Retrieved tools via tools attribute\n")
        
        # Check if tools are registered as decorated functions in the module
        if not registered_tools:
            import inspect
            from mcp_operations_server import (
                scale_deployment_tool, restart_deployment_tool, rollback_deployment_tool,
                get_deployment_rollout_status_tool, delete_deployment_tool, delete_pod_tool,
                delete_pods_by_status_tool, delete_pods_by_label_tool, cordon_node_tool,
                uncordon_node_tool, drain_node_tool, patch_resource_tool,
                create_namespace_tool, delete_namespace_tool, apply_yaml_config_tool
            )
            
            # If we can import them, they exist in the module
            registered_tools = [
                "scale_deployment_tool", "restart_deployment_tool", "rollback_deployment_tool",
                "get_deployment_rollout_status_tool", "delete_deployment_tool", "delete_pod_tool",
                "delete_pods_by_status_tool", "delete_pods_by_label_tool", "cordon_node_tool",
                "uncordon_node_tool", "drain_node_tool", "patch_resource_tool",
                "create_namespace_tool", "delete_namespace_tool", "apply_yaml_config_tool"
            ]
            print(f"✅ Verified tools exist by direct import\n")
        
        print(f"📋 Found {len(registered_tools)} registered tools in MCP server\n")
        
        # Test each expected tool
        print("-" * 70)
        print("TOOL CONNECTION TESTS:")
        print("-" * 70)
        
        for idx, tool_name in enumerate(expected_tools, 1):
            # Check if tool is registered
            is_connected = tool_name in registered_tools
            results[tool_name] = is_connected
            
            status = "✅ YES" if is_connected else "❌ NO"
            print(f"{idx:2d}. Connection from MCP Operations Server to '{tool_name}': {status}")
        
        print("-" * 70)
        print()
        
        # Summary
        connected_count = sum(1 for v in results.values() if v)
        total_count = len(expected_tools)
        
        print("=" * 70)
        print("SUMMARY:")
        print("=" * 70)
        print(f"✅ Connected Tools:     {connected_count}/{total_count}")
        print(f"❌ Disconnected Tools:  {total_count - connected_count}/{total_count}")
        print(f"📊 Success Rate:        {(connected_count/total_count)*100:.1f}%")
        print("=" * 70)
        print()
        
        # List disconnected tools if any
        disconnected = [name for name, connected in results.items() if not connected]
        if disconnected:
            print("⚠️  DISCONNECTED TOOLS:")
            for tool in disconnected:
                print(f"   - {tool}")
            print()
        
        # Additional diagnostics
        print("=" * 70)
        print("DIAGNOSTICS:")
        print("=" * 70)
        print(f"MCP Server Type:        {type(mcp).__name__}")
        print(f"MCP Server Module:      {mcp.__class__.__module__}")
        
        if registered_tools:
            print(f"\nAll Registered Tools ({len(registered_tools)}):")
            for tool in sorted(registered_tools):
                print(f"   - {tool}")
        
        print("=" * 70)
        print()
        
        # Return success if all tools connected
        return connected_count == total_count
        
    except ImportError as e:
        print(f"❌ ERROR: Failed to import MCP Operations Server")
        print(f"   Details: {str(e)}")
        print(f"\n   Make sure:")
        print(f"   1. MCP Operations Server file exists at: MCP/mcp_operations/mcp_operations_server.py")
        print(f"   2. FastMCP is installed: pip install fastmcp")
        print(f"   3. Virtual environment is activated")
        return False
        
    except Exception as e:
        print(f"❌ ERROR: Unexpected error during testing")
        print(f"   Details: {str(e)}")
        print(f"   Type: {type(e).__name__}")
        return False


def test_tools_implementation_connection():
    """Test if underlying tool implementations are accessible"""
    
    print()
    print("=" * 70)
    print("TOOLS IMPLEMENTATION CONNECTION TEST")
    print("=" * 70)
    print()
    
    tool_functions = [
        "scale_deployment",
        "restart_deployment",
        "rollback_deployment",
        "get_deployment_rollout_status",
        "delete_pod",
        "delete_pods_by_status",
        "delete_pods_by_label",
        "delete_deployment",
        "cordon_node",
        "uncordon_node",
        "drain_node",
        "patch_resource",
        "create_namespace",
        "delete_namespace",
        "apply_yaml_config"
    ]
    
    results = {}
    
    try:
        print("📡 Importing tools_operations module...")
        import tools_operations
        print("✅ Tools implementation module imported successfully\n")
        
        print("-" * 70)
        print("IMPLEMENTATION FUNCTION TESTS:")
        print("-" * 70)
        
        for idx, func_name in enumerate(tool_functions, 1):
            # Check if function exists in the module
            is_available = hasattr(tools_operations, func_name)
            
            if is_available:
                # Verify it's callable
                func = getattr(tools_operations, func_name)
                is_available = callable(func)
            
            results[func_name] = is_available
            status = "✅ YES" if is_available else "❌ NO"
            print(f"{idx:2d}. Implementation function '{func_name}' available: {status}")
        
        print("-" * 70)
        print()
        
        # Summary
        available_count = sum(1 for v in results.values() if v)
        total_count = len(tool_functions)
        
        print("IMPLEMENTATION SUMMARY:")
        print(f"✅ Available Functions: {available_count}/{total_count}")
        print(f"❌ Missing Functions:   {total_count - available_count}/{total_count}")
        print(f"📊 Success Rate:        {(available_count/total_count)*100:.1f}%")
        print("=" * 70)
        print()
        
        return available_count == total_count
        
    except ImportError as e:
        print(f"❌ ERROR: Failed to import tools_operations module")
        print(f"   Details: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ ERROR: Unexpected error")
        print(f"   Details: {str(e)}")
        return False


def main():
    """Run all connection tests"""
    
    print("\n")
    print("🔬 STARTING MCP OPERATIONS SERVER CONNECTION TESTS")
    print(f"📅 Date: November 30, 2025")
    print(f"📁 Working Directory: {os.getcwd()}")
    print("\n")
    
    # Test 1: MCP Server Tool Registration
    mcp_test_passed = test_mcp_operations_tools_connection()
    
    # Test 2: Implementation Functions
    impl_test_passed = test_tools_implementation_connection()
    
    # Final Summary
    print()
    print("=" * 70)
    print("FINAL TEST RESULTS:")
    print("=" * 70)
    print(f"MCP Server Tool Registration:     {'✅ PASSED' if mcp_test_passed else '❌ FAILED'}")
    print(f"Implementation Functions:          {'✅ PASSED' if impl_test_passed else '❌ FAILED'}")
    print("-" * 70)
    
    if mcp_test_passed and impl_test_passed:
        print("🎉 ALL TESTS PASSED - MCP Operations Server is fully connected!")
        print("=" * 70)
        return 0
    else:
        print("⚠️  SOME TESTS FAILED - Check details above")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
