#!/usr/bin/env python3
"""
Direct test of Monitor Agent - CPU Trend Query
"""

from agents.monitor_agent import monitor_agent_executor

def test_monitor_cpu_trend():
    """Test monitor agent with CPU trend query"""
    
    print("="*80)
    print("TESTING MONITOR AGENT")
    print("="*80)
    print("\nQuery: What was the CPU trend in the last hour?\n")
    
    try:
        # Directly invoke monitor agent
        result = monitor_agent_executor.invoke({
            "messages": [("user", "What was the CPU trend in the last hour?")]
        })
        
        print("\n" + "="*80)
        print("MONITOR AGENT RESPONSE:")
        print("="*80)
        
        # Extract the response
        if "messages" in result:
            for msg in result["messages"]:
                if hasattr(msg, 'content'):
                    print(msg.content)
                else:
                    print(msg)
        else:
            print(result)
        
        print("\n" + "="*80)
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_monitor_cpu_trend()
