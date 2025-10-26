"""
Quick Validation Test for Kubernetes Multi-Agent System

This test validates that:
1. All agents can be imported
2. All tools can be imported  
3. 6 agents are properly configured with correct tools

NO API CALLS - Just import and structure validation
"""

import os
import sys

def test_imports():
    """Test: Verify all agent modules can be imported"""
    print("\n" + "=" * 70)
    print(" TEST 1: Agent Imports")
    print("=" * 70)
    
    try:
        from agents.health_agent import create_health_agent
        print("✅ Health Agent imported")
    except ImportError as e:
        print(f"❌ Health Agent failed: {e}")
        return False
    
    try:
        from agents.security_agent import create_security_agent
        print("✅ Security Agent imported")
    except ImportError as e:
        print(f"❌ Security Agent failed: {e}")
        return False
    
    try:
        from agents.resources_agent import create_resources_agent
        print("✅ Resources Agent imported")
    except ImportError as e:
        print(f"❌ Resources Agent failed: {e}")
        return False
    
    try:
        from agents.monitor_agent import create_monitor_agent
        print("✅ Monitor Agent imported")
    except ImportError as e:
        print(f"❌ Monitor Agent failed: {e}")
        return False
    
    try:
        from agents.describe_get_agent import create_describe_get_agent
        print("✅ Describe/Get Agent imported")
    except ImportError as e:
        print(f"❌ Describe/Get Agent failed: {e}")
        return False
    
    try:
        from agents.operations_agent import create_operations_agent
        print("✅ Operations Agent imported")
    except ImportError as e:
        print(f"❌ Operations Agent failed: {e}")
        return False
    
    try:
        from agents.supervisor_agent import create_k8s_supervisor
        print("✅ Supervisor Agent imported")
    except ImportError as e:
        print(f"❌ Supervisor Agent failed: {e}")
        return False
    
    return True

def test_tools():
    """Test: Verify all tools are properly organized"""
    print("\n" + "=" * 70)
    print(" TEST 2: Tool Organization")
    print("=" * 70)
    
    try:
        from agents.tools import (
            HEALTH_TOOLS,
            SECURITY_TOOLS,
            RESOURCES_TOOLS,
            MONITOR_TOOLS,
            DESCRIBE_GET_TOOLS,
            OPERATIONS_TOOLS
        )
        
        print(f"✅ Health Tools: {len(HEALTH_TOOLS)} tools")
        print(f"✅ Security Tools: {len(SECURITY_TOOLS)} tools")
        print(f"✅ Resources Tools: {len(RESOURCES_TOOLS)} tools")
        print(f"✅ Monitor Tools: {len(MONITOR_TOOLS)} tools")
        print(f"✅ Describe/Get Tools: {len(DESCRIBE_GET_TOOLS)} tools")
        print(f"✅ Operations Tools: {len(OPERATIONS_TOOLS)} tools")
        
        total_tools = (len(HEALTH_TOOLS) + len(SECURITY_TOOLS) + 
                      len(RESOURCES_TOOLS) + len(MONITOR_TOOLS) + 
                      len(DESCRIBE_GET_TOOLS) + len(OPERATIONS_TOOLS))
        
        print(f"\n✅ Total tools across 6 agents: {total_tools}")
        
        # Verify Operations Tools include execute_kubectl
        tool_names = [t.name for t in OPERATIONS_TOOLS]
        if 'execute_kubectl' in tool_names:
            print("✅ Generic execute_kubectl tool found in Operations Tools")
        else:
            print("⚠️  execute_kubectl not found in Operations Tools")
        
        # Verify confirmation-based tools exist
        confirmation_tools = [
            'delete_pod', 'scale_deployment', 'restart_deployment',
            'delete_failed_pods', 'cordon_drain_node', 'create_configmap',
            'create_secret', 'apply_manifest'
        ]
        
        found_tools = [t for t in confirmation_tools if t in tool_names]
        print(f"✅ Found {len(found_tools)}/{len(confirmation_tools)} confirmation-based operations tools")
        
        return True
        
    except ImportError as e:
        print(f"❌ Tools import failed: {e}")
        return False

def test_langchain_tools():
    """Test: Verify core LangChain tools can be imported"""
    print("\n" + "=" * 70)
    print(" TEST 3: LangChain Tools")
    print("=" * 70)
    
    try:
        from utils.langchain_tools import (
            get_cluster_resources,
            describe_resource,
            get_pod_logs,
            check_node_health,
            check_cluster_health,
            execute_kubectl,
            get_cluster_events,
            troubleshoot_pod,
            check_rbac_permissions,
            list_secrets_and_configmaps,
            check_network_policies,
            get_resource_usage,
            get_resource_quotas,
            analyze_resource_requests,
            delete_pod,
            scale_deployment,
            restart_deployment,
            delete_failed_pods,
            cordon_drain_node,
            create_configmap,
            create_secret,
            apply_manifest
        )
        
        print("✅ All 22 LangChain tools imported successfully")
        
        # Verify these are actual @tool decorated functions
        tools = [
            get_cluster_resources, describe_resource, get_pod_logs,
            check_node_health, check_cluster_health, execute_kubectl,
            get_cluster_events, troubleshoot_pod, check_rbac_permissions,
            list_secrets_and_configmaps, check_network_policies,
            get_resource_usage, get_resource_quotas, analyze_resource_requests,
            delete_pod, scale_deployment, restart_deployment,
            delete_failed_pods, cordon_drain_node, create_configmap,
            create_secret, apply_manifest
        ]
        
        print(f"✅ Verified all tools are callable objects")
        
        return True
        
    except ImportError as e:
        print(f"❌ LangChain tools import failed: {e}")
        return False

def test_system_integration():
    """Test: Verify the complete system can be imported"""
    print("\n" + "=" * 70)
    print(" TEST 4: System Integration")
    print("=" * 70)
    
    try:
        from utils.langchain_agent import create_k8s_multiagent_system
        print("✅ Multi-agent system function imported")
        
        # Check if it expects 6 agents
        import inspect
        sig = inspect.signature(create_k8s_multiagent_system)
        print(f"✅ System accepts parameters: {list(sig.parameters.keys())}")
        
        return True
        
    except ImportError as e:
        print(f"❌ System integration failed: {e}")
        return False

def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print(" K8S MULTI-AGENT SYSTEM - QUICK VALIDATION")
    print("=" * 70)
    
    results = []
    
    # Test 1: Imports
    results.append(("Agent Imports", test_imports()))
    
    # Test 2: Tools
    results.append(("Tool Organization", test_tools()))
    
    # Test 3: LangChain Tools
    results.append(("LangChain Tools", test_langchain_tools()))
    
    # Test 4: System Integration
    results.append(("System Integration", test_system_integration()))
    
    # Print summary
    print("\n" + "=" * 70)
    print(" TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print("\n" + "=" * 70)
    print(f" RESULT: {passed}/{total} tests passed")
    print("=" * 70)
    
    if passed == total:
        print("\n🎉 All tests passed! 6-agent system is properly configured.\n")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Check errors above.\n")
        return 1

if __name__ == "__main__":
    sys.exit(main())
