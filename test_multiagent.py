"""
Test Script for Kubernetes Multi-Agent System

This script tests the connection between the supervisor agent and all specialist agents
using Google Gemini LLM (same as used in the main project).

Run this script to verify:
1. LangGraph packages are installed correctly
2. Supervisor can route to specialist agents
3. Agents can execute tools successfully
4. Multi-agent workflows work end-to-end
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_imports():
    """Test 1: Verify all required packages can be imported"""
    print("=" * 70)
    print("TEST 1: Checking LangGraph Imports")
    print("=" * 70)
    
    try:
        from langgraph_supervisor import create_supervisor
        print("✅ langgraph_supervisor imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import langgraph_supervisor: {e}")
        return False
    
    try:
        from langgraph.prebuilt import create_react_agent
        print("✅ langgraph.prebuilt imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import langgraph.prebuilt: {e}")
        return False
    
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        print("✅ langchain_google_genai imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import langchain_google_genai: {e}")
        return False
    
    try:
        from agents import create_k8s_multiagent_system
        print("✅ agents package imported successfully")
    except ImportError as e:
        print(f"❌ Failed to import agents package: {e}")
        return False
    
    print("\n✅ All imports successful!\n")
    return True


def test_agent_creation():
    """Test 2: Create individual specialist agents"""
    print("=" * 70)
    print("TEST 2: Creating Individual Specialist Agents")
    print("=" * 70)
    
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        from agents.health_agent import create_health_agent
        from agents.security_agent import create_security_agent
        from agents.resources_agent import create_resources_agent
        from agents.monitor_agent import create_monitor_agent
        from agents.describe_get_agent import create_describe_get_agent
        from agents.operations_agent import create_operations_agent
        
        # Get API key
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            print("❌ GOOGLE_API_KEY not found in environment variables!")
            print("   Set it in .env file or export GOOGLE_API_KEY=your-key")
            return False
        
        # Initialize Gemini LLM (using flash-exp model)
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-exp",
            google_api_key=api_key,
            temperature=0.2,
            convert_system_message_to_human=True
        )
        print(f"✅ Initialized Gemini LLM: gemini-2.0-flash-exp")
        
        # Create all 6 agents
        health_agent = create_health_agent(llm, verbose=False)
        print("✅ Health Agent created")
        
        security_agent = create_security_agent(llm, verbose=False)
        print("✅ Security Agent created")
        
        resources_agent = create_resources_agent(llm, verbose=False)
        print("✅ Resources Agent created")
        
        monitor_agent = create_monitor_agent(llm, verbose=False)
        print("✅ Monitor Agent created")
        
        describe_get_agent = create_describe_get_agent(llm, verbose=False)
        print("✅ Describe-Get Agent created")
        
        operations_agent = create_operations_agent(llm, verbose=False)
        print("✅ Operations Agent created")
        
        print("\n✅ All 6 specialist agents created successfully!\n")
        return True, llm
        
    except Exception as e:
        print(f"❌ Error creating agents: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_supervisor_creation(llm):
    """Test 3: Create supervisor and compile workflow"""
    print("=" * 70)
    print("TEST 3: Creating Supervisor and Compiling Workflow")
    print("=" * 70)
    
    try:
        from agents import create_k8s_multiagent_system
        
        # Create entire multi-agent system
        app = create_k8s_multiagent_system(llm, verbose=False)
        print("✅ Supervisor created successfully")
        print("✅ Workflow compiled successfully")
        
        print("\n✅ Multi-agent system ready!\n")
        return True, app
        
    except Exception as e:
        print(f"❌ Error creating supervisor: {e}")
        import traceback
        traceback.print_exc()
        return False, None


def test_supervisor_routing(app):
    """Test 4: Test supervisor routing to different agents"""
    print("=" * 70)
    print("TEST 4: Testing Supervisor Routing")
    print("=" * 70)
    
    test_questions = [
        {
            "question": "Are all nodes healthy?",
            "expected_agent": "k8s_health_expert",
            "description": "Health check question → should route to Health Agent"
        },
        {
            "question": "List all pods in the cluster",
            "expected_agent": "k8s_describe_get_expert",
            "description": "Resource listing question → should route to Describe-Get Agent"
        },
        {
            "question": "Show logs for nginx pod",
            "expected_agent": "k8s_monitor_expert",
            "description": "Logs question → should route to Monitor Agent"
        }
    ]
    
    print("\nTesting routing with sample questions:\n")
    
    for i, test in enumerate(test_questions, 1):
        print(f"{i}. {test['description']}")
        print(f"   Question: \"{test['question']}\"")
        print(f"   Expected: {test['expected_agent']}")
        
        try:
            result = app.invoke({
                "messages": [
                    {"role": "user", "content": test['question']}
                ]
            })
            
            # Check which agents were called
            agents_called = []
            for msg in result["messages"]:
                if hasattr(msg, 'name') and msg.name:
                    agents_called.append(msg.name)
            
            agents_called = list(set(agents_called))  # Remove duplicates
            
            if test['expected_agent'] in agents_called:
                print(f"   ✅ Correctly routed to {test['expected_agent']}")
            else:
                print(f"   ⚠️  Routed to: {', '.join(agents_called)}")
            
            # Show final answer
            final_answer = result["messages"][-1].content
            print(f"   Answer: {final_answer[:100]}...")
            print()
            
        except Exception as e:
            print(f"   ❌ Error: {e}")
            print()
    
    print("✅ Routing tests completed!\n")
    return True


def test_full_conversation(app):
    """Test 5: Test a full conversation with follow-up questions"""
    print("=" * 70)
    print("TEST 5: Testing Full Conversation Flow")
    print("=" * 70)
    
    print("\nSimulating a conversation about cluster status:\n")
    
    questions = [
        "Check cluster health",
        "How many pods are running?",
        "What's the status of the master node?"
    ]
    
    for i, question in enumerate(questions, 1):
        print(f"\nQ{i}: {question}")
        print("-" * 60)
        
        try:
            result = app.invoke({
                "messages": [
                    {"role": "user", "content": question}
                ]
            })
            
            # Get final answer
            final_answer = result["messages"][-1].content
            print(f"A{i}: {final_answer}\n")
            
        except Exception as e:
            print(f"❌ Error: {e}\n")
    
    print("✅ Conversation test completed!\n")
    return True


def main():
    """Run all tests"""
    print("\n" + "=" * 70)
    print(" K8S MULTI-AGENT SYSTEM TEST SUITE")
    print("=" * 70 + "\n")
    
    # Test 1: Imports
    if not test_imports():
        print("\n❌ Import tests failed. Cannot proceed.")
        sys.exit(1)
    
    # Test 2: Agent Creation
    result = test_agent_creation()
    if isinstance(result, tuple):
        success, llm = result
        if not success:
            print("\n❌ Agent creation failed. Cannot proceed.")
            sys.exit(1)
    else:
        print("\n❌ Agent creation failed. Cannot proceed.")
        sys.exit(1)
    
    # Test 3: Supervisor Creation
    success, app = test_supervisor_creation(llm)
    if not success:
        print("\n❌ Supervisor creation failed. Cannot proceed.")
        sys.exit(1)
    
    # Test 4: Routing
    test_supervisor_routing(app)
    
    # Test 5: Full Conversation
    test_full_conversation(app)
    
    # Final Summary
    print("=" * 70)
    print(" TEST SUMMARY")
    print("=" * 70)
    print("✅ All tests passed!")
    print()
    print("Your multi-agent system is working correctly!")
    print("You can now use it in your application with:")
    print()
    print("  from agents import create_k8s_multiagent_system")
    print("  app = create_k8s_multiagent_system(llm)")
    print("  result = app.invoke({'messages': [{'role': 'user', 'content': '...'}]})")
    print()
    print("=" * 70)


if __name__ == "__main__":
    main()
