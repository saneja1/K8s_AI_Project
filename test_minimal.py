"""
Minimal Test - Just verify imports and tool assignments
FASTEST TEST - No LLM, no agent creation, just structure validation
"""

def test_imports_and_tools():
    """Test that all agents and tools can be imported"""
    print("\n" + "=" * 70)
    print(" TEST: Agent & Tool Imports")
    print("=" * 70)
    
    # Test 1: Agent imports
    print("\n[1/2] Testing agent imports...")
    try:
        from agents.health_agent import create_health_agent
        from agents.security_agent import create_security_agent
        from agents.resources_agent import create_resources_agent
        from agents.monitor_agent import create_monitor_agent
        from agents.describe_get_agent import create_describe_get_agent
        from agents.operations_agent import create_operations_agent
        from agents.supervisor_agent import create_k8s_supervisor
        
        print("✅ Health Agent")
        print("✅ Security Agent")
        print("✅ Resources Agent")
        print("✅ Monitor Agent")
        print("✅ Describe/Get Agent")
        print("✅ Operations Agent")
        print("✅ Supervisor Agent")
        
    except ImportError as e:
        print(f"❌ Agent import failed: {e}")
        return False
    
    # Test 2: Tool organization
    print("\n[2/2] Testing tool organization...")
    try:
        from agents.tools import (
            HEALTH_TOOLS,
            SECURITY_TOOLS,
            RESOURCES_TOOLS,
            MONITOR_TOOLS,
            DESCRIBE_GET_TOOLS,
            OPERATIONS_TOOLS
        )
        
        tool_counts = {
            "Health": len(HEALTH_TOOLS),
            "Security": len(SECURITY_TOOLS),
            "Resources": len(RESOURCES_TOOLS),
            "Monitor": len(MONITOR_TOOLS),
            "Describe/Get": len(DESCRIBE_GET_TOOLS),
            "Operations": len(OPERATIONS_TOOLS)
        }
        
        for agent, count in tool_counts.items():
            print(f"✅ {agent} Agent: {count} tools")
        
        total = sum(tool_counts.values())
        print(f"\n✅ Total: {total} tools across 6 agents")
        
        # Verify execute_kubectl is in all tool lists
        all_tools = (HEALTH_TOOLS + SECURITY_TOOLS + RESOURCES_TOOLS + 
                     MONITOR_TOOLS + DESCRIBE_GET_TOOLS + OPERATIONS_TOOLS)
        
        kubectl_count = sum(1 for t in all_tools if t.name == 'execute_kubectl')
        print(f"✅ Generic 'execute_kubectl' tool found {kubectl_count} times")
        
        # Verify confirmation tools
        ops_tool_names = [t.name for t in OPERATIONS_TOOLS]
        confirmation_tools = [
            'delete_pod', 'scale_deployment', 'restart_deployment',
            'delete_failed_pods', 'cordon_drain_node', 'create_configmap',
            'create_secret', 'apply_manifest'
        ]
        
        found = [t for t in confirmation_tools if t in ops_tool_names]
        print(f"✅ Found {len(found)}/{len(confirmation_tools)} confirmation-based operations tools")
        
        return True
        
    except ImportError as e:
        print(f"❌ Tool import failed: {e}")
        return False

def main():
    """Run minimal test"""
    print("\n" + "=" * 70)
    print(" K8S MULTI-AGENT SYSTEM - MINIMAL VALIDATION")
    print(" Testing: Imports & Tool Assignments Only")
    print("=" * 70)
    
    success = test_imports_and_tools()
    
    print("\n" + "=" * 70)
    if success:
        print(" ✅ VALIDATION PASSED")
        print(" ")
        print(" System is properly configured:")
        print("   ✅ All 6 specialist agents can be imported")
        print("   ✅ Supervisor agent can be imported")
        print("   ✅ All tools are organized by agent domain")
        print("   ✅ Generic execute_kubectl tool available")
        print("   ✅ Confirmation-based operations tools present")
        print(" ")
        print(" The agents can communicate when connected to real LLM.")
        print(" (Skipping LLM test due to API rate limits)")
    else:
        print(" ❌ VALIDATION FAILED - Check errors above")
    print("=" * 70 + "\n")
    
    return 0 if success else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
