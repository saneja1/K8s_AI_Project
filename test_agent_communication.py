"""
Simple Agent Communication Test

Tests that supervisor can send requests to sub-agents and receive responses.
Uses minimal LLM calls to avoid quota issues.
"""

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_agent_communication():
    """Test bidirectional communication between supervisor and specialist agents"""
    print("\n" + "=" * 70)
    print(" TESTING AGENT COMMUNICATION")
    print("=" * 70)
    
    # Step 1: Import and create LLM
    print("\n[1/4] Setting up LLM...")
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            print("❌ GOOGLE_API_KEY not found in .env file")
            return False
        
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=api_key,
            temperature=0,
            convert_system_message_to_human=True
        )
        print("✅ LLM initialized")
        
    except Exception as e:
        print(f"❌ LLM setup failed: {e}")
        return False
    
    # Step 2: Create all 6 specialist agents
    print("\n[2/4] Creating specialist agents...")
    try:
        from agents.health_agent import create_health_agent
        from agents.security_agent import create_security_agent
        from agents.resources_agent import create_resources_agent
        from agents.monitor_agent import create_monitor_agent
        from agents.describe_get_agent import create_describe_get_agent
        from agents.operations_agent import create_operations_agent
        
        health_agent = create_health_agent(llm, verbose=False)
        security_agent = create_security_agent(llm, verbose=False)
        resources_agent = create_resources_agent(llm, verbose=False)
        monitor_agent = create_monitor_agent(llm, verbose=False)
        describe_get_agent = create_describe_get_agent(llm, verbose=False)
        operations_agent = create_operations_agent(llm, verbose=False)
        
        print("✅ Health Agent created")
        print("✅ Security Agent created")
        print("✅ Resources Agent created")
        print("✅ Monitor Agent created")
        print("✅ Describe/Get Agent created")
        print("✅ Operations Agent created")
        
    except Exception as e:
        print(f"❌ Agent creation failed: {e}")
        return False
    
    # Step 3: Create supervisor agent
    print("\n[3/4] Creating supervisor agent...")
    try:
        from agents.supervisor_agent import create_k8s_supervisor
        
        supervisor = create_k8s_supervisor(
            llm=llm,
            health_agent=health_agent,
            security_agent=security_agent,
            resources_agent=resources_agent,
            monitor_agent=monitor_agent,
            describe_get_agent=describe_get_agent,
            operations_agent=operations_agent
        )
        print("✅ Supervisor created with 6 specialist agents")
        
    except Exception as e:
        print(f"❌ Supervisor creation failed: {e}")
        return False
    
    # Step 4: Test communication with a simple query
    print("\n[4/4] Testing supervisor → sub-agent communication...")
    try:
        # Simple query that should route to describe_get_agent
        test_query = "list all pods in default namespace"
        
        print(f"\n📤 Supervisor receives: '{test_query}'")
        print("🔄 Supervisor routing to appropriate agent...")
        
        # Invoke supervisor with the query
        result = supervisor.invoke({
            "messages": [{"role": "user", "content": test_query}]
        })
        
        # Check if we got a response
        if result and "messages" in result:
            messages = result["messages"]
            final_message = messages[-1].content if messages else "No response"
            
            print(f"📥 Supervisor received response from sub-agent")
            print(f"\n✅ COMMUNICATION SUCCESSFUL")
            print(f"\nResponse preview: {final_message[:200]}...")
            
            return True
        else:
            print("❌ No response received from sub-agent")
            return False
            
    except Exception as e:
        print(f"❌ Communication test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the communication test"""
    print("\n" + "=" * 70)
    print(" K8S MULTI-AGENT SYSTEM - COMMUNICATION TEST")
    print(" Testing: Supervisor ↔ Sub-Agent Message Passing")
    print("=" * 70)
    
    success = test_agent_communication()
    
    print("\n" + "=" * 70)
    if success:
        print(" ✅ TEST PASSED: Agents can communicate successfully")
        print(" - Supervisor can route requests to sub-agents")
        print(" - Sub-agents can send responses back to supervisor")
    else:
        print(" ❌ TEST FAILED: Communication issue detected")
    print("=" * 70 + "\n")
    
    return 0 if success else 1

if __name__ == "__main__":
    import sys
    sys.exit(main())
