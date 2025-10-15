"""
Test script for LangChain agent integration.
Run this to verify the agent works before testing in the UI.
"""

import os
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import our modules
from utils.langchain_agent import create_k8s_agent
from utils.langchain_tools import ALL_TOOLS

def test_agent():
    """Test the LangChain agent with a simple question."""
    
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("❌ GOOGLE_API_KEY not found in .env file")
        return
    
    print("✅ API Key found")
    print(f"✅ {len(ALL_TOOLS)} tools loaded")
    
    # Create agent
    print("\n🔧 Creating LangChain agent...")
    try:
        agent = create_k8s_agent(
            tools=ALL_TOOLS,
            api_key=api_key,
            verbose=True  # Show reasoning steps
        )
        print("✅ Agent created successfully!")
    except Exception as e:
        print(f"❌ Failed to create agent: {e}")
        return
    
    # Test with a simple question
    print("\n🤖 Testing agent with question: 'Check cluster health'")
    print("-" * 60)
    
    try:
        result = agent.answer_question(
            question="Check cluster health",
            cluster_context="Test cluster with 2 nodes"
        )
        
        if result['success']:
            print("\n✅ Agent Response:")
            print(result['answer'])
            print(f"\n📊 Used {len(result.get('intermediate_steps', []))} tool(s)")
        else:
            print(f"\n❌ Agent failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🧪 LangChain K8s Agent Test")
    print("=" * 60)
    test_agent()
