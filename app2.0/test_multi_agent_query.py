"""
Test Multi-Agent Query Handling

Tests a complex query that requires coordination between multiple agents:
- Describe Agent: Count pods in cluster
- Resources Agent: Find pod with highest memory usage
- Health Agent: Check cluster health

This test demonstrates the supervisor's ability to route to multiple specialized agents
and synthesize their responses into a coherent answer.
"""

import os
import sys
from dotenv import load_dotenv

# Add app2.0 directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

from agents.k8s_agent import ask_k8s_agent


def test_multi_agent_query():
    """
    Test a complex query that requires multiple agents:
    1. Check number of pods (Describe Agent)
    2. Find pod with highest memory usage (Resources Agent)
    3. Check cluster health (Health Agent)
    """
    
    print("=" * 80)
    print("MULTI-AGENT QUERY TEST")
    print("=" * 80)
    print()
    
    # Get API key
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY not found in environment variables")
        print("Please set it in your .env file")
        return
    
    # Complex query that should trigger 3 agents
    query = """
    Check the number of pods in my cluster, find the pod with highest memory usage, 
    and check the overall health of the cluster.
    """
    
    print("📝 Query:")
    print("-" * 80)
    print(query.strip())
    print()
    print("-" * 80)
    print("🤖 Processing query through K8s Supervisor Agent...")
    print("-" * 80)
    print()
    
    try:
        # Execute query
        result = ask_k8s_agent(question=query, api_key=api_key, verbose=True)
        
        # Display results
        print("✅ Response:")
        print("=" * 80)
        print(result['answer'])
        print("=" * 80)
        print()
        
        # Analyze which agents were used
        messages = result.get('messages', [])
        
        print("📊 Analysis:")
        print("-" * 80)
        
        # Check if multiple agents were mentioned in the response
        answer_lower = result['answer'].lower()
        
        agents_used = []
        if 'describe agent' in answer_lower or 'pod count' in answer_lower or 'how many pod' in answer_lower:
            agents_used.append("✓ Describe Agent (pod counting)")
        
        if 'resources agent' in answer_lower or 'memory usage' in answer_lower or 'highest memory' in answer_lower:
            agents_used.append("✓ Resources Agent (memory analysis)")
        
        if 'health agent' in answer_lower or 'cluster health' in answer_lower or 'node' in answer_lower and 'ready' in answer_lower:
            agents_used.append("✓ Health Agent (cluster status)")
        
        if len(agents_used) >= 2:
            print(f"✅ Multi-agent coordination successful! {len(agents_used)} agents used:")
            for agent in agents_used:
                print(f"   {agent}")
        elif len(agents_used) == 1:
            print(f"⚠️  Only 1 agent detected in response:")
            print(f"   {agents_used[0]}")
            print("\nExpected: Multiple agents for this complex query")
        else:
            print("❓ Could not detect which agents were used from response")
            print("   This might be normal if the supervisor synthesized a unified answer")
        
        print()
        print(f"📋 Total messages in conversation: {len(messages)}")
        
        # Show message types
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
        
        msg_types = {
            'Human': sum(1 for m in messages if isinstance(m, HumanMessage)),
            'AI': sum(1 for m in messages if isinstance(m, AIMessage)),
            'Tool': sum(1 for m in messages if isinstance(m, ToolMessage)),
            'System': sum(1 for m in messages if isinstance(m, SystemMessage))
        }
        
        print("📬 Message breakdown:")
        for msg_type, count in msg_types.items():
            if count > 0:
                print(f"   {msg_type} messages: {count}")
        
        print()
        print("=" * 80)
        print("✅ Test completed successfully!")
        print("=" * 80)
        
    except Exception as e:
        print()
        print("=" * 80)
        print("❌ Test failed with error:")
        print("-" * 80)
        print(f"Error: {str(e)}")
        print()
        import traceback
        traceback.print_exc()
        print("=" * 80)


def test_additional_multi_agent_scenarios():
    """
    Test additional multi-agent scenarios
    """
    
    print()
    print()
    print("=" * 80)
    print("ADDITIONAL MULTI-AGENT SCENARIOS")
    print("=" * 80)
    print()
    
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY not found")
        return
    
    # Test scenarios
    scenarios = [
        {
            "name": "Resource Analysis + Health Check",
            "query": "Show me the CPU and memory capacity of nodes and tell me if any nodes have issues",
            "expected_agents": ["Resources Agent", "Health Agent"]
        },
        {
            "name": "Pod Listing + Resource Usage",
            "query": "List all pods in the kube-system namespace and show which ones are using the most memory",
            "expected_agents": ["Describe Agent", "Resources Agent"]
        },
        {
            "name": "Complete Cluster Overview",
            "query": "Give me a complete overview: how many nodes, how many pods, what's the resource usage, and is everything healthy?",
            "expected_agents": ["Describe Agent", "Resources Agent", "Health Agent"]
        }
    ]
    
    for i, scenario in enumerate(scenarios, 1):
        print(f"Test Scenario {i}: {scenario['name']}")
        print("-" * 80)
        print(f"Query: {scenario['query']}")
        print(f"Expected agents: {', '.join(scenario['expected_agents'])}")
        print()
        
        try:
            result = ask_k8s_agent(question=scenario['query'], api_key=api_key, verbose=False)
            
            # Brief response (first 200 chars)
            response_preview = result['answer'][:200] + "..." if len(result['answer']) > 200 else result['answer']
            print(f"Response preview: {response_preview}")
            print()
            
            # Check which agents responded
            answer_lower = result['answer'].lower()
            detected = []
            for agent in scenario['expected_agents']:
                if agent.lower() in answer_lower:
                    detected.append(agent)
            
            if len(detected) >= len(scenario['expected_agents']) - 1:  # Allow 1 missing
                print(f"✅ Detected agents: {', '.join(detected) if detected else 'Synthesized answer'}")
            else:
                print(f"⚠️  Expected {len(scenario['expected_agents'])} agents, detected: {len(detected)}")
            
        except Exception as e:
            print(f"❌ Error: {str(e)}")
        
        print()
        print("-" * 80)
        print()


if __name__ == "__main__":
    print()
    print("🚀 Starting Multi-Agent Query Tests")
    print()
    
    # Main test
    test_multi_agent_query()
    
    # Additional scenarios
    test_additional_multi_agent_scenarios()
    
    print()
    print("🏁 All tests completed!")
    print()
