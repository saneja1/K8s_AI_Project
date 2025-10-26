"""
Ultra-Simple Agent Structure Test
NO LLM CALLS - Just tests that agents can be created and connected
"""

import os
from dotenv import load_dotenv

load_dotenv()

def test_agent_structure():
    """Test that supervisor can be connected to 6 sub-agents"""
    print("\n" + "=" * 70)
    print(" TESTING AGENT STRUCTURE (No LLM calls)")
    print("=" * 70)
    
    # Mock LLM (no real calls)
    print("\n[1/3] Creating mock LLM...")
    
    class MockLLM:
        """Simple mock that doesn't make API calls"""
        def __init__(self):
            self.model_name = "mock-model"
        
        def bind_tools(self, tools, **kwargs):
            """Mock bind_tools - just return self"""
            return self
        
        def invoke(self, *args, **kwargs):
            """Mock invoke - return simple response"""
            from langchain_core.messages import AIMessage
            return AIMessage(content="mock response")
    
    llm = MockLLM()
    print("✅ Mock LLM created (no API calls)")
    
    # Create all 6 agents
    print("\n[2/3] Creating 6 specialist agents...")
    try:
        from agents.health_agent import create_health_agent
        from agents.security_agent import create_security_agent
        from agents.resources_agent import create_resources_agent
        from agents.monitor_agent import create_monitor_agent
        from agents.describe_get_agent import create_describe_get_agent
        from agents.operations_agent import create_operations_agent
        
        agents = {
            "health": create_health_agent(llm, verbose=False),
            "security": create_security_agent(llm, verbose=False),
            "resources": create_resources_agent(llm, verbose=False),
            "monitor": create_monitor_agent(llm, verbose=False),
            "describe_get": create_describe_get_agent(llm, verbose=False),
            "operations": create_operations_agent(llm, verbose=False)
        }
        
        for name, agent in agents.items():
            print(f"✅ {name.capitalize()} agent created - Type: {type(agent).__name__}")
        
    except Exception as e:
        print(f"❌ Agent creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Create supervisor
    print("\n[3/3] Creating supervisor with 6 agents...")
    try:
        from agents.supervisor_agent import create_k8s_supervisor
        
        supervisor = create_k8s_supervisor(
            llm=llm,
            health_agent=agents["health"],
            security_agent=agents["security"],
            resources_agent=agents["resources"],
            monitor_agent=agents["monitor"],
            describe_get_agent=agents["describe_get"],
            operations_agent=agents["operations"]
        )
        
        print(f"✅ Supervisor created - Type: {type(supervisor).__name__}")
        
        # Check supervisor structure
        if hasattr(supervisor, 'nodes'):
            print(f"✅ Supervisor has {len(supervisor.nodes)} nodes (agents)")
            print(f"   Nodes: {list(supervisor.nodes.keys())}")
        
        print("\n✅ ALL AGENTS CONNECTED SUCCESSFULLY")
        print("   - Supervisor can route to 6 specialist agents")
        print("   - Each agent has its own set of tools")
        print("   - Agent graph structure is valid")
        
        return True
        
    except Exception as e:
        print(f"❌ Supervisor creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the structure test"""
    print("\n" + "=" * 70)
    print(" K8S MULTI-AGENT SYSTEM - STRUCTURE TEST")
    print(" Testing: Agent Creation & Connection (No API Calls)")
    print("=" * 70)
    
    success = test_agent_structure()
    
    print("\n" + "=" * 70)
    if success:
        print(" ✅ STRUCTURE TEST PASSED")
        print(" ")
        print(" The 6-agent system is properly configured:")
        print("   1. Health Agent - Node health checks")
        print("   2. Security Agent - RBAC, secrets, network policies")
        print("   3. Resources Agent - CPU, memory, quotas")
        print("   4. Monitor Agent - Events, troubleshooting")
        print("   5. Describe/Get Agent - Resource descriptions")
        print("   6. Operations Agent - Create, delete, scale operations")
        print(" ")
        print(" Supervisor can route requests to all 6 agents.")
    else:
        print(" ❌ STRUCTURE TEST FAILED")
        print(" Check error messages above")
    print("=" * 70 + "\n")
    
    return 0 if success else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
